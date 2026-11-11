# obd-v2x-dongle — project rules

## Part sourcing (applies to every part choice)
- **PCBWay assembly first.** Pick parts PCBWay can source and assemble (they buy from Digi-Key / Mouser / LCSC etc.). Prefer common, in-stock, multi-source parts.
- A few parts that PCBWay can't source are acceptable (consigned or hand-soldered), but call them out in `docs/bom-notes.md`.
- Every part in the schematic needs a real footprint and a real MPN in the Value (or an `MPN` field) before ordering.

## Design constraints
- ITS-G5 is **receive-only** (ESP32-C5 in undocumented 802.11p mode via esphome-its-g5). Don't add V2X transmit features.
- LTE modem is the Quectel **EC200U-EU** (Cat 1, chosen over EG25-G for cost: ~$13 vs ~$66). Its logic I/O is **1.8 V**; ESP32-C5 is 3.3 V. Everything between them goes through the TXS0108E (U402) or the open-collector NPN drivers (PWRKEY, RESET_N).
- The dongle must **not** terminate the vehicle CAN bus (no 120 Ω).
- ESP32-C5 strapping: GPIO28 = BOOT (low = download), GPIO27 must be high at boot (LED data line is fine), GPIO26/25/7 floating OK.

## KiCad
- KiCad 10 (per-user install in `%LOCALAPPDATA%\Programs\KiCad\10.0`), project in `hardware/`.
- Sheets power / vehicle / mcu / lte are **generated**: edit `hardware/tools/gen_schematic.py`, then
  `python hardware/tools/gen_schematic.py`. Don't hand-edit those `.kicad_sch` files (changes get overwritten).
  Layout rules: real wires inside a block, GND/rail power symbols, global labels only for cross-sheet nets.
- After any change run `python hardware/tools/check_netlist.py` — connectivity must match
  `hardware/tools/reference.net`. When a connectivity change is intended, review it and then refresh
  `reference.net` (`kicad-cli sch export netlist --format kicadsexpr`).
- Project symbols (incl. rail power symbols) are generated: edit `hardware/lib/gen_symbols.py`, run it.
- ERC: `kicad-cli sch erc hardware/obd-v2x-dongle.kicad_sch` (expect 0 errors; footprint warnings until the
  custom footprints exist). PDF: `kicad-cli sch export pdf -o docs/schematic.pdf hardware/obd-v2x-dongle.kicad_sch`.
- EC200U: PWRKEY must be held low >= 2 s to power on; pin 35 is a BT/Wi-Fi-scan antenna (unused), there is no LTE diversity antenna.
