# Vehicle profiles

One JSON file per car (`<make>-<model>-<generation>.json`): what the car's bus carries and how to read it. The
firmware compiles every file in this folder in (`components/obd2/profiles.py`); the *Vehicle profile* select in
Home Assistant chooses the active one, and its `signals` feed the entities declared under `signals:` in the YAML.
Only `signals` are used by the firmware; `candidates`, `obd` and `never_transmit` are documentation.

Never put a VIN, number plate, owner data or exact readings of a specific car in here.

## Format (`"schema": 1`)

| Key | Content |
|---|---|
| `vehicle` | make, model, generation, model years, variant, notes on how it was measured |
| `bus` | OBD pins, bitrate, 11/29-bit IDs, whether the port carries live traffic and when it sleeps |
| `signals` | broadcast values read by **listening only** (see below) |
| `candidates` | fields seen but not confirmed — don't use them in firmware |
| `obd` | diagnostic findings: functional-only addressing, ECUs found, supported mode-01 PIDs, UDS DIDs that answer |
| `never_transmit` | IDs where sent frames triggered car functions; tools and firmware must never send to them |

A signal is one of:

- **number**: `id`, `start_byte`, `length` (bytes), `byte_order` (`little`/`big`, default `big`), `scale` and
  optional `offset` (value = raw × scale + offset), `unit`, optional `invalid` (raw values meaning "not available")
- **flag**: `id`, `start_byte`, `mask` — true when `byte & mask` is non-zero
- **enum**: `id`, `start_byte`, `length`, `byte_order`, `values` (raw value → state), optional `mask` (only these
  bits belong to the field, e.g. when another flag shares the byte), optional `on` (the state that counts as "on"
  when the signal is used as a binary sensor, e.g. `"on": "locked"`)

Only 11-bit IDs, fields within bytes 0–7, numbers up to 4 bytes. The firmware (`components/obd2`) compiles every
profile in this folder in and checks these rules at build time.

Bytes are numbered from 0 in the CAN frame. Every signal has a `verified` note saying how it was checked.

## Finding signals for a new car

With a WiCAN in SLCAN mode and the engine running, `python firmware/tools/obd_probe.py sniff` records the bus
listen-only (nothing is sent); press Enter at each action (door open, locked, …). Compare values with the instrument
cluster or the manufacturer's app at two different readings before calling a signal verified. Do **not** sweep request
IDs over raw CAN: on the W205 that unlocked the doors and started a service call.
