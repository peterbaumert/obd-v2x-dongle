# Vehicle profiles

One JSON file per car (`<make>-<model>-<generation>.json`): what the car's bus carries and how to read it. The
firmware will pick a profile for the passive sensors; until then the files document what was measured.

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
- **enum**: `id`, `start_byte`, `length`, `byte_order`, `values` (raw value → state)

Bytes are numbered from 0 in the CAN frame. Every signal has a `verified` note saying how it was checked.

## Finding signals for a new car

With a WiCAN in SLCAN mode and the engine running, `python firmware/tools/obd_probe.py sniff` records the bus
listen-only (nothing is sent); press Enter at each action (door open, locked, …). Compare values with the instrument
cluster or the manufacturer's app at two different readings before calling a signal verified. Do **not** sweep request
IDs over raw CAN: on the W205 that unlocked the doors and started a service call.
