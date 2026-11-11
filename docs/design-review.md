# Design review (before ordering)

State reviewed: routed board, DRC 0 errors / 0 unconnected, schematic parity 0, ERC 0/0.

## Fixed in this review

| Item | Problem | Fix |
|---|---|---|
| VBAT_F (fuse → reverse-polarity FET → TVS) | Routed with 0.2 mm tracks: the Power net class pattern `VBAT_F` did not match the net name `/Power/VBAT_F` | Pattern `*VBAT_F`; re-routed 1.0 mm fuse→Q101 and fuse→TVS, 0.7 mm across Q101's source pins, 0.3 mm for the LM74700 sense pins |
| D301 LED | BOM had SK6812MINI-**E** (reverse-mount, shines through a board hole, different pads) on the normal top-emitting footprint | SK6812MINI-HS (LCSC C2922787, top-emitting 3535, same footprint). Confirm pinout against its datasheet when ordering |
| Fiducials | None (needed for PCBWay double-sided assembly) | 3 × 1 mm fiducials per side, board-only |
| Battery sense R109/R110 | 100k/15k reached the ESP32 ADC limit (3.3 V) at ~25 V: jump-start (24 V) / load-dump transients overdrive the pin | R110 = 10k: VSENSE = VIN / 11, full scale ~35 V. Firmware: scale × 11 |

## Electrical checks (OK / notes)

- **Buck (TPS54360)**: RT 162k → f_sw ≈ 600 kHz; 6.8 µH gives ~0.7 A ripple at 14 V in (≈ 20 % of 3.5 A). Compensation
  7.5k / 6.8 nF / 47 pF puts crossover around 15–20 kHz with the 2 × 47 µF ceramics (lower with C401 on the modem
  rail) – conservative and stable. Still confirm in TI WEBENCH / the datasheet's Type II calculation.
- **Input protection**: SMCJ33CA (33 V stand-off) + 60 V buck + LM74700 ideal diode; 2 A slow fuse. OK for 12 V cars.
- **Switch node**: 1 mm locked tracks U102 SW → L101 / D103; FB/COMP parts kept out of it (R104 on the bottom).
- **Modem supply (VBAT_LTE)**: 0.6 mm F.Cu, no vias, ~25 mm: ~40 mV drop at 2 A bursts; 220 µF tantalum next to the
  VBAT pins plus 100 nF/33 pF/10 pF. Load switch AO3401A adds ~0.1–0.15 V at 2 A → modem sees ≈ 3.6 V (min 3.3 V). OK.
- **Modem GND / heat**: solid pad connections, 48 GND vias in the module area, In1 solid GND plane under it.
- **RF**: 0.35 mm on F.Cu over In1 with GND pour at 0.25 mm. On a standard 1.6 mm 4-layer stack (≈ 0.2 mm L1–L2
  prepreg, εr ≈ 4.4) that is ≈ 48–55 Ω. **Order with impedance control: 50 Ω ±10 % on L1 referenced to L2**, and
  let PCBWay adjust the width. Via fences on both sides of both lines.
- **USB 2.0 FS**: short D+/D− on the bottom, USBLC6 ESD at the connector; 90 Ω not critical at 12 Mbit/s.
- **CAN / K-Line**: ESD (NUP2105L, PESD1LIN) at the plug, no CAN termination (by design).
- **SIM**: 22 Ω series + 33 pF on the lines, no TVS array. Fine while the holder is inside the case; add ESD if the
  SIM becomes user-accessible.
- **Quiescent current** (parked, modem switched off by Q102, ESP32 in deep sleep): buck ≈ 0.15 mA + LM74700 ≈ 0.08 mA
  + LDO + ESP32 — well under 1 mA.

## Accessibility (case design)

| What | Where | Access |
|---|---|---|
| OBD plug | top, front edge | – |
| USB-C (power, ESP32 flashing/logs) | bottom, rear edge, 0.3 mm overhang | case cut-out ✓ |
| RESET / BOOT buttons | bottom, near rear edge, top-actuated | pinholes in the case bottom (BOOT rarely needed: the C5's USB-Serial-JTAG can enter download mode itself) |
| RGB LED | bottom, rear-left corner | light pipe / window in the case bottom |
| **Nano-SIM** | **bottom, middle; hinged holder** | **case must be opened** – see open decisions |
| U.FL (LTE main, GNSS) | top, right edge | inside the case ✓ |
| U.FL 5.9 GHz | on the ESP32 module (bottom) | inside the case ✓ |
| Test pads: ESP UART, modem USB/USB_BOOT/debug UART | bottom | case open; modem firmware updates need the modem USB pads |

## Open decisions

1. **SIM access** – keep the hinged holder (open the case to change SIM, like many trackers), move to an
   edge-mounted push-push nano-SIM holder with a case slot, or add a soldered MFF2 eSIM (no access needed).
2. **Backup battery** (like Teltonika FMC003) – not in the design yet. Needed for "unplugged / power lost" alerts
   and short GNSS/LTE operation without vehicle power.
3. **Mounting holes** – none; the case has to clamp the board (plug + edges).
