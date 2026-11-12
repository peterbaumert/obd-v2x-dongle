# Firmware (ESPHome)

ESPHome configuration for the obd-v2x-dongle board (ESP32-C5-WROOM-1U-N16R8, Quectel EC200U-EU).
**Status: first version, compiles (ESPHome 2026.11.0b4, ESP-IDF 5.5.6). No board has run it yet.**

| File | Purpose |
|---|---|
| `obd-v2x-dongle.yaml` | main configuration |
| `components/otm_uplink/` | second MQTT connection to the OpenTrafficMap C-ITS server |
| `components/obd2/` | OBD-II over CAN on ESP-IDF's TWAI node driver |
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
- **OBD-II only while the engine runs.** Engine running = car battery above 13.2 V (alternator charging).
  With the engine off the CAN transceiver stays in standby and nothing is sent: on cars like the
  Mercedes W205 the gateway sleeps with the ignition off and requests would wake the bus.

## Entities (Home Assistant)

Car battery, car battery low, engine running · speed, engine RPM, coolant / intake / ambient temperature,
engine load, fuel level, ECU voltage (OBD-II mode 01, CAN 11-bit 500 kbit/s) · LTE signal, LTE modem
running · V2X packets received / dropped · status LED, "Use eSIM" switch · uptime.

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
| GPS position, trips | EC200U GNSS (`AT+QGPS`, `AT+QGPSLOC`). ESPHome's `modem.send_at` only logs the reply, so this needs a small extension (callback with the response) – upstream PR or local component |
| Traccar | position over LTE with `http_request` (OsmAnd protocol), once GPS works |
| Parking / deep sleep | modem off (`AT+QPOWD`, LTE_PWR_EN), ESP32 deep sleep, wake on timer / battery voltage; backup-cell mode when VSENSE drops (unplugged) |
| OTA over LTE | `ota: platform: http_request` pulling a firmware URL, triggered via MQTT |
| More OBD | multi-frame ISO-TP (VIN, fault codes), 29-bit / 250 kbit/s auto-detect, K-line (older cars), OEM PIDs (e.g. Mercedes odometer / fuel level) |
| Trip logic | trip start/stop from engine running + speed, distance, idling time (like a Teltonika FMC003) |
| Crash / towing detection | needs an accelerometer – not on this board revision |
