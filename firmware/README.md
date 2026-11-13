# Firmware (ESPHome)

ESPHome configuration for the obd-v2x-dongle board (ESP32-C5-WROOM-1U-N16R8, Quectel EC200U-EU).
**Status: v0.6, compiles (ESPHome 2026.11.0b4, ESP-IDF 5.5.6). No board has run it yet.**

| File | Purpose |
|---|---|
| `obd-v2x-dongle.yaml` | main configuration |
| `components/otm_uplink/` | second MQTT connection to the OpenTrafficMap C-ITS server |
| `components/obd2/` | OBD-II over CAN on ESP-IDF's TWAI node driver |
| `components/ec200u_gnss/` | GPS position from the EC200U's GNSS receiver (`AT+QGPSLOC`) |
| `components/power_manager/` | parking mode / deep sleep (modes, wake timing in RTC memory) |
| `tools/make_release.py` | packs a compiled firmware as an update for the dongle (manifest + image) |
| `tools/obd_probe.py` | read-only OBD/UDS probe from a laptop via a WiCAN (ELM327 over TCP): supported PIDs, Mercedes DIDs, ECU/DID scan, live change watch (`--help`) |
| `secrets.example.yaml` | keys the configuration needs (copy to `secrets.yaml`, which git ignores) |

Requires **ESPHome 2026.11 or newer**: the LTE `modem:` component first ships in that release
(until it is out: the ESPHome beta add-on / `pip install esphome==2026.11.0b4`).

## Architecture

- **Uplink: LTE only.** The ESP32-C5's Wi-Fi radio runs in 802.11p mode as the ITS-G5 receiver
  ([hn/esphome-its-g5](https://github.com/hn/esphome-its-g5), based on
  [opentrafficmap's firmware](https://codeberg.org/opentrafficmap/its-g5-receiver-firmware)),
  so the dongle has no Wi-Fi. The EC200U provides IP over PPP (ESPHome `modem:`, CMUX) at 921600 baud with RTS/CTS
  (115200 would cap it at ~11 kB/s, too little on busy roads). The 8 MB PSRAM holds the TLS, WireGuard and MQTT buffers.
- **Data usage.** Every received ITS-G5 frame (~300-800 bytes) goes to OpenTrafficMap. With a few equipped cars
  around that is roughly 10-20 MB per hour of driving, so use a SIM with a normal monthly data allowance (not a
  small-volume IoT plan). "V2X data sent" shows the volume; if frames come in faster than LTE sends them, the send
  queue is capped at 64 KB and new frames are dropped ("V2X upload dropped") instead of running out of memory.
- **WireGuard tunnel to the home network.** The car sits behind the mobile network's carrier NAT. The dongle
  connects out to your WireGuard server (Home Assistant add-on or router), so the MQTT broker, Traccar and the
  update files stay inside your network; only the WireGuard port is open, and it does not answer anything without the
  right key. Only the home network's range goes through the tunnel; OpenTrafficMap is reached directly.
  Keepalive every 25 s keeps the NAT mapping open, so the ESPHome Builder can connect in at the tunnel address.
- **Home Assistant via MQTT** (MQTT discovery), not the native API: the dongle sleeps most of the time, and with
  MQTT Home Assistant keeps the last values and the broker holds changed settings until the next wake. The native
  API is only there for the ESPHome Builder (logs); don't add the dongle to HA's ESPHome integration (duplicate
  entities).
- **V2X → OpenTrafficMap:** received frames go to `cits1.opentrafficmap.org:8883` (TLS, anonymous
  publishing) under `its/<node_id>/...`, like the reference receiver. ESPHome's `mqtt:` holds only one
  broker, so `otm_uplink` runs a second esp-mqtt client.
- **OBD-II: own component.** ESPHome's `esp32_can` uses ESP-IDF's legacy TWAI driver, which ESP-IDF does not
  build for CAN-FD capable chips like the ESP32-C5 (it fails to link). `obd2` uses the new TWAI node driver,
  sends requests to 0x7DF and decodes the answers from 0x7E8..0x7EF; multi-frame answers (ISO-TP) are
  reassembled per ECU, with flow control to 0x7E0..0x7E7. Besides mode 01 live data it reads the VIN once
  (mode 09/02) and the stored fault codes (mode 03) at engine start and every 5 min, and can clear them (mode 04).
  Many ECUs only clear with the ignition on and the engine off, but the dongle only talks while the engine runs: a
  refusal shows in the log as NRC 0x22 (conditions not correct).
- **GPS: EC200U GNSS over the modem's AT channel.** ESPHome's `modem.send_at` only logs the reply, so
  `ec200u_gnss` sends `AT+QGPS=1` / `AT+QGPSLOC=2` through it and reads the answer from the modem's log line
  with a logger listener (works with the stock modem component). The position goes to Home Assistant as
  sensors and as a `device_tracker` (MQTT discovery, map) and to **Traccar** (OsmAnd protocol over HTTP:
  every "Traccar interval driving" while the engine runs, "Parked position report every" parked; ignition and
  car battery voltage as attributes, so Traccar can split the drives into trips).
- **OBD-II only while the engine runs.** Engine running = car battery above 13.2 V (alternator charging).
  With the engine off the CAN transceiver stays in standby and nothing is sent: on cars like the
  Mercedes W205 the gateway sleeps with the ignition off and requests would wake the bus.

## Parking mode / deep sleep (`power_manager`)

| Mode | When | What happens |
|---|---|---|
| driving | car battery above "Engine running above" (alternator charging) | everything on, OBD-II polling, Traccar every "Traccar interval driving" |
| parked | engine stopped, or after power-on | stays awake for "Sleep after engine off", then shuts the modem down (`AT+QPOWD`, supply off) and sleeps |
| check | timer wake from deep sleep | one ADC reading of the car battery, back to sleep at once unless the engine runs, the car was unplugged or a report is due (~1 s awake) |
| report | report due ("Parked position report every", or "Report every (battery low)" below "Car battery low below"), or just unplugged | modem + GPS on until Traccar accepted a position, or "Report timeout" |

All values are Home Assistant entities under *Configuration* (stored on the dongle). They are published with
`command_retain`, so the broker keeps a change until the sleeping dongle wakes and picks it up. "Stay awake"
keeps it awake (diagnostics, updates), and so does a **computer on USB-C** (detected by its USB frames; a charger
or power bank does not count). The MQTT birth/will messages are off: while it sleeps Home Assistant keeps
the last values instead of showing the entities as unavailable. "Power mode" shows the current mode.

**Unplugged** the board runs from its backup cell. The ESP32 cannot measure the cell, so the modem reports its supply
(`AT+CBC`, "Supply voltage": ~3.8 V from the buck on car power, the cell voltage when unplugged). Below
"Backup cell cut-off" (3.6 V) it shuts the modem down and sleeps, overriding "Stay awake"; until car power returns it
only wakes to check for it ("Power mode" shows "backup cell low"). This stops before the cell's own protection
cuts off.

Defaults: engine running above 13.2 V, battery low below 12.0 V, unplugged below 6 V, sleep 5 min after engine off,
battery check every 60 s, position every 30 min parked / 120 min with a low battery, report timeout 3 min.

## Firmware updates over LTE

Two ways, both through the tunnel:

**ESPHome default (`ota: esphome`):** in the ESPHome Builder, *Install → Wirelessly* to the dongle's tunnel address
(the config sets `use_address` to the `wireguard_address`, so the Builder knows where to connect). Works while the dongle is
awake and the tunnel is up: driving, "Stay awake", or a computer on USB-C. Encrypted with the API key.

**The dongle fetches it itself (`update: http_request`)** for a parked car or when the Builder can't connect:

1. Raise `version` under `esphome: project:` in `obd-v2x-dongle.yaml` and compile (ESPHome Builder:
   *Install → Manual download → OTA format*, or `esphome compile`).
2. `python firmware/tools/make_release.py <the .ota.bin> <dir>` writes `firmware.ota.bin` and `manifest.json`.
3. Put both where `ota_manifest_url` (secrets) points. Easiest: Home Assistant's `config/www/<dir>/`, served as
   `http://<HA's home address>:8123/local/<dir>/` and reached through the tunnel. Don't use a public URL: the image
   contains your secrets (MQTT password, WireGuard key, ...).
4. The dongle checks at every network connect and every 6 h. Home Assistant shows a "Firmware" update entity.
   *Install* only reaches it while it is awake (driving, "Stay awake"). For a parked car turn on
   "Install updates automatically": the next wake with network installs it.

Safety: ESPHome `safe_mode` with ESP-IDF app rollback. If the new firmware crashes within 2 min of its first boot,
the bootloader goes back to the previous one. USB-C stays the fallback.

## Entities (Home Assistant)

Car battery, car battery low, unplugged, engine running, power mode · speed, engine RPM, coolant / intake / ambient temperature,
engine load, fuel level, ECU voltage (OBD-II mode 01, CAN 11-bit 500 kbit/s), VIN, fault codes, fault code count,
"Clear fault codes" button · firmware update, "Install updates automatically" · supply / backup cell voltage · LTE signal, LTE modem
running · position (device tracker), latitude, longitude, altitude, GPS speed, course, HDOP, satellites ·
V2X packets received / dropped, V2X data sent, V2X upload dropped · status LED, "Use eSIM" switch · uptime.

Status LED: red = no LTE, yellow = LTE but no MQTT, green = connected, blue flash = V2X frame.

## Build and flash

1. Set up a WireGuard peer for the dongle (Home Assistant WireGuard add-on or your router) and add the keys from
   `secrets.example.yaml` to your ESPHome `secrets.yaml` (APN, MQTT broker, Traccar, WireGuard, API key, OpenTrafficMap node ID).
2. Home Assistant ESPHome add-on (2026.11+ / beta): copy `obd-v2x-dongle.yaml` and the `components/` folder into
   `/config/esphome/`, then *Install → Plug into this computer* with the dongle on USB-C (ESP32 USB-Serial-JTAG).
   Or locally: `esphome run obd-v2x-dongle.yaml`. On Windows run ESPHome from PowerShell/cmd, not Git Bash
   (ESP-IDF's installer refuses MSYS).
3. **Emergency access is always USB-C**: flash and logs over the ESP32's USB-Serial-JTAG. If the firmware is
   broken, hold BOOT and press RESET (pinholes in the case bottom) to start the ESP32's ROM bootloader. A sleeping
   dongle: press RESET (it then stays awake for "Sleep after engine off"), or just plug in a computer.
   There is no Wi-Fi fallback: the radio is the V2X receiver.
4. First flash over USB. After that, updates go over LTE through the WireGuard tunnel (see above).

## Testing the car with a WiCAN (`tools/obd_probe.py`)

Before a value goes into the `obd2` component, check what the car actually answers, from a laptop with a
[WiCAN OBD](https://docs.meatpi.com/wican-obd/) (ELM327 over Wi-Fi, same CAN pins 6/14 as the dongle).
Python standard library only. Candidates come from [OBDb](https://github.com/OBDb/Mercedes-Benz-C-Class)
(CC-BY-SA-4.0); for a 2015 C-Class only the standard mode-01 PIDs are confirmed, the Mercedes DIDs are untested.

The script only sends read services (01, 21, 22, 1A, 3E, 10 01/03) and refuses anything that could write, code,
reset or clear codes. It refuses to run unless the engine is running (`--no-engine-check` for ignition-only tests).
Unplug the WiCAN afterwards: it and the dongle must not poll at the same time.

**Setup:** WiCAN web UI → Protocol *ELM327*, Port Type *TCP*, note the port (default assumed `3333`, else `--port`).
Join the WiCAN's Wi-Fi (`192.168.80.1`, else `--host`), start the engine.

1. Standard OBD: which mode-01 PIDs each ECU supports, one decoded read of each.
   `python firmware/tools/obd_probe.py standard`
2. Mercedes candidates (odometer, oil temp, fuel litres, gear, ATF temp, boost/DPF), decoded with OBDb's formulas.
   Compare the odometer with the instrument cluster.
   `python firmware/tools/obd_probe.py mercedes`
3. ECU discovery behind the gateway: tester present (3E 00) to every 11-bit ID, takes a few minutes.
   `python firmware/tools/obd_probe.py find-ecus`
   If only 7E8–7EF answer, the WiCAN is probably filtering response IDs; repeat the discovery over SLCAN/SavvyCAN.
4. DID scan of one ECU found in step 3 (request ID `XXX`, response ID `YYY`). Try other ranges if little answers
   (e.g. `--from 0100 --to 01FF`, `--from 1000 --to 10FF`, `--from 2000 --to 20FF`), add `--extended` for the
   extended session.
   `python firmware/tools/obd_probe.py dids --tx XXX --rx YYY --out scan.json`
5. Hunt for a state bit (door, lock, window, trunk): watch every DID that answered while you change it in the car;
   each changed byte is printed with time and changed bits.
   `python firmware/tools/obd_probe.py watch --scan scan.json`

Also: `diff a.json b.json` (byte differences between two scans: scan, change something, scan again) and
`raw --tx 7E0 --rx 7E8 22016B` (one request). Body modules are asleep when the car is parked, so such values are
only available with the ignition on.

**Privacy:** VINs are masked on screen and in scan files. The raw logs in `firmware/tools/probe-logs/` (git-ignored)
still contain them – don't share those unedited, and never commit a VIN.

## Roadmap

| Feature | State / plan |
|---|---|
| GPS position, Traccar | done (untested on hardware); possible upstream improvement: a `send_at` reply callback in ESPHome's modem component instead of the logger listener |
| Backup cell, OTA over LTE, VIN / fault codes | done (untested on hardware) |
| More OBD | pending fault codes (mode 07), check-engine light (PID 01), 29-bit / 250 kbit/s auto-detect, K-line (older cars), OEM PIDs (e.g. Mercedes odometer / fuel level) |
| Trip logic | trip start/stop from engine running + speed, distance, idling time (like a Teltonika FMC003) |
| Crash / towing detection | needs an accelerometer – not on this board revision |
