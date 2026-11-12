# Firmware (ESPHome)

ESPHome configuration for the obd-v2x-dongle board (ESP32-C5-WROOM-1U-N16R8, Quectel EC200U-EU).
**Status: v0.3, compiles (ESPHome 2026.11.0b4, ESP-IDF 5.5.6). No board has run it yet.**

| File | Purpose |
|---|---|
| `obd-v2x-dongle.yaml` | main configuration |
| `components/otm_uplink/` | second MQTT connection to the OpenTrafficMap C-ITS server |
| `components/obd2/` | OBD-II over CAN on ESP-IDF's TWAI node driver |
| `components/ec200u_gnss/` | GPS position from the EC200U's GNSS receiver (`AT+QGPSLOC`) |
| `components/power_manager/` | parking mode / deep sleep (modes, wake timing in RTC memory) |
| `secrets.example.yaml` | keys the configuration needs (copy to `secrets.yaml`, which git ignores) |

Requires **ESPHome 2026.11 or newer**: the LTE `modem:` component first ships in that release
(until it is out: the ESPHome beta add-on / `pip install esphome==2026.11.0b4`).

## Architecture

- **Uplink: LTE only.** The ESP32-C5's Wi-Fi radio runs in 802.11p mode as the ITS-G5 receiver
  ([hn/esphome-its-g5](https://github.com/hn/esphome-its-g5), based on
  [opentrafficmap's firmware](https://codeberg.org/opentrafficmap/its-g5-receiver-firmware)),
  so the dongle has no Wi-Fi. The EC200U provides IP over PPP (ESPHome `modem:`, CMUX).
- **Home Assistant via MQTT** (MQTT discovery): the car sits behind the mobile network's carrier NAT,
  so HA cannot reach the dongle's native API; the dongle publishes to your broker instead.
- **V2X → OpenTrafficMap:** received frames go to `cits1.opentrafficmap.org:8883` (TLS, anonymous
  publishing) under `its/<node_id>/...`, like the reference receiver. ESPHome's `mqtt:` holds only one
  broker, so `otm_uplink` runs a second esp-mqtt client.
- **OBD-II: own component.** ESPHome's `esp32_can` uses ESP-IDF's legacy TWAI driver, which ESP-IDF does not
  build for CAN-FD capable chips like the ESP32-C5 (it fails to link). `obd2` uses the new TWAI node driver,
  sends mode 01 requests to 0x7DF and decodes single-frame answers from 0x7E8..0x7EF.
- **GPS: EC200U GNSS over the modem's AT channel.** ESPHome's `modem.send_at` only logs the reply, so
  `ec200u_gnss` sends `AT+QGPS=1` / `AT+QGPSLOC=2` through it and reads the answer from the modem's log line
  with a logger listener (works with the stock modem component). The position goes to Home Assistant as
  sensors and as a `device_tracker` (MQTT discovery, map) and to **Traccar** (OsmAnd protocol over HTTP:
  every 10 s while the engine runs, every 5 min parked; ignition and car battery voltage as attributes).
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
keeps it awake (diagnostics, updates). The MQTT birth/will messages are off: while it sleeps Home Assistant keeps
the last values instead of showing the entities as unavailable. "Power mode" shows the current mode.

Defaults: engine running above 13.2 V, battery low below 12.0 V, unplugged below 6 V, sleep 5 min after engine off,
battery check every 60 s, position every 30 min parked / 120 min with a low battery, report timeout 3 min.

## Entities (Home Assistant)

Car battery, car battery low, unplugged, engine running, power mode · speed, engine RPM, coolant / intake / ambient temperature,
engine load, fuel level, ECU voltage (OBD-II mode 01, CAN 11-bit 500 kbit/s) · LTE signal, LTE modem
running · position (device tracker), latitude, longitude, altitude, GPS speed, course, HDOP, satellites ·
V2X packets received / dropped · status LED, "Use eSIM" switch · uptime.

Status LED: red = no LTE, yellow = LTE but no MQTT, green = connected, blue flash = V2X frame.

## Build and flash

1. Add the keys from `secrets.example.yaml` to your ESPHome `secrets.yaml` (APN, MQTT broker, OpenTrafficMap node ID).
2. Home Assistant ESPHome add-on (2026.11+ / beta): copy `obd-v2x-dongle.yaml` and the `components/` folder into
   `/config/esphome/`, then *Install → Plug into this computer* with the dongle on USB-C (ESP32 USB-Serial-JTAG).
   Or locally: `esphome run obd-v2x-dongle.yaml`. On Windows run ESPHome from PowerShell/cmd, not Git Bash
   (ESP-IDF's installer refuses MSYS).
3. First flash over USB. There is no Wi-Fi and the car is not reachable from outside, so ESPHome's normal OTA
   does not apply (see roadmap).

## Roadmap

| Feature | State / plan |
|---|---|
| GPS position, Traccar | done (untested on hardware); possible upstream improvement: a `send_at` reply callback in ESPHome's modem component instead of the logger listener |
| Backup cell voltage | read the modem supply (`AT+CBC`) while unplugged, stop reporting when the cell gets low |
| OTA over LTE | `ota: platform: http_request` pulling a firmware URL, triggered via MQTT |
| More OBD | multi-frame ISO-TP (VIN, fault codes), 29-bit / 250 kbit/s auto-detect, K-line (older cars), OEM PIDs (e.g. Mercedes odometer / fuel level) |
| Trip logic | trip start/stop from engine running + speed, distance, idling time (like a Teltonika FMC003) |
| Crash / towing detection | needs an accelerometer – not on this board revision |
