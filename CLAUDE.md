# obd-v2x-dongle — project rules

## Part sourcing (applies to every part choice)
- **PCBWay assembly first.** Pick parts PCBWay can source and assemble (they buy from Digi-Key / Mouser / LCSC etc.). Prefer common, in-stock, multi-source parts.
- A few parts that PCBWay can't source are acceptable (consigned or hand-soldered), but call them out in `docs/bom-notes.md`.
- Every part in the schematic needs a real footprint and a real MPN in the Value (or an `MPN` field) before ordering.

## Design constraints
- ITS-G5 is **receive-only** (ESP32-C5 in undocumented 802.11p mode via esphome-its-g5). Don't add V2X transmit features.
- EG25-G logic I/O is **1.8 V**; ESP32-C5 is 3.3 V. Everything between them goes through the TXS0108E (U402) or the open-collector NPN drivers (PWRKEY, RESET_N).
- The dongle must **not** terminate the vehicle CAN bus (no 120 Ω).
- ESP32-C5 strapping: GPIO28 = BOOT (low = download), GPIO27 must be high at boot (LED data line is fine), GPIO26/25/7 floating OK.

## KiCad
- KiCad 10, project in `hardware/`. Sheets: power, vehicle, mcu, lte. Cross-sheet nets use global labels.
- Project symbols are generated: edit `hardware/lib/gen_symbols.py`, then run `python hardware/lib/gen_symbols.py`. Don't hand-edit `obd-v2x.kicad_sym`.
- Check with `kicad-cli sch erc hardware/obd-v2x-dongle.kicad_sch` (expect 0 errors).
