# Design review (before ordering)

State reviewed: routed board, DRC 0 errors / 0 unconnected, schematic parity 0, ERC 0/0.

## Fixed in this review

| Item | Problem | Fix |
|---|---|---|
| VBAT_F (fuse → reverse-polarity FET → TVS) | Routed with 0.2 mm tracks: the Power net class pattern `VBAT_F` did not match the net name `/Power/VBAT_F` | Pattern `*VBAT_F`; re-routed 1.0 mm fuse→Q101 and fuse→TVS, 0.7 mm across Q101's source pins, 0.3 mm for the LM74700 sense pins |
| D301 LED | BOM had SK6812MINI-**E** (reverse-mount, shines through a board hole, different pads) on the normal top-emitting footprint | SK6812MINI-HS (LCSC C2922787, top-emitting) |
| D301 pinout | The HS numbers and places its pins differently from KiCad's `LED:SK6812MINI` (HS: 1 GND, 2 DIN, 3 VDD, 4 DOUT, 3.7 × 3.5 mm body): with the stock symbol/footprint VDD and data would have landed on the wrong pads | Own symbol `obd-v2x:SK6812MINI-HS` and footprint `LED_SK6812MINI-HS_3.7x3.5mm` from the OPSCO datasheet (Rev. B/0, pin table + recommended land); LED re-routed |
| Vias in SMD pads | ~90 vias sat in or touched SMD pads (modem GND pads, U.FL grounds, passives); open vias wick solder away from the joint | Moved next to the pads (or dropped where the pad already reaches GND); `maze.py` no longer puts vias in pads. Left on purpose: 5 thermal vias in the ESP32 module's GND pad (Espressif's layout) |
| Silkscreen | Reference text stroke 0.12 mm, below PCBWay's 0.15 mm minimum | 0.15 mm on the board and in the generators |
| Compensation | R106/C105 = 7.5k / 6.8 nF gave a crossover ~40 % below the datasheet design target | 12k / 5.6 nF (see Buck below) |
| Fiducials | None (needed for PCBWay double-sided assembly) | 3 × 1 mm fiducials per side, board-only |
| Battery sense R109/R110 | 100k/15k reached the ESP32 ADC limit (3.3 V) at ~25 V: jump-start (24 V) / load-dump transients overdrive the pin | R110 = 10k: VSENSE = VIN / 11, full scale ~35 V. Firmware: scale × 11 |

## Electrical checks (OK / notes)

- **Buck (TPS54360)**: RT 162k → f_sw ≈ 604 kHz; 6.8 µH gives ~0.7 A ripple at 14 V in (≈ 20 % of 3.5 A); V_OUT =
  0.8 V × (1 + 37.4k/10k) = 3.79 V. Compensation per the datasheet's method (SLVSBB4G §8.2.2.11, gm_ea 350 µA/V,
  gm_ps 12 A/V), C_OUT = 2 × 47 µF derated to ~66 µF at 3.8 V: f_p(mod) = 3.5 A / (2π · 3.79 V · 66 µF) ≈ 2.2 kHz,
  f_co = √(f_p · f_sw/2) ≈ 26 kHz → R106 = 12.1k → **12k**, C105 = 1/(2π · R106 · f_p) = 5.9 nF → **5.6 nF**,
  C106 = 1/(π · R106 · f_sw) = 44 pF → **47 pF**. The method ignores slope compensation, so the real crossover is
  lower; C401 (220 µF behind the load switch, ~0.25 Ω) adds capacitance and damping and lowers it further. Not run
  in WEBENCH.
- **Input protection**: SMCJ33CA (33 V stand-off) + 60 V buck + LM74700 ideal diode; 2 A slow fuse. OK for 12 V cars.
- **Switch node**: 1 mm locked tracks U102 SW → L101 / D103; FB/COMP parts kept out of it (R104 on the bottom).
- **Modem supply (VBAT_LTE)**: 0.6 mm F.Cu, no vias, ~25 mm: ~40 mV drop at 2 A bursts; 220 µF tantalum next to the
  VBAT pins plus 100 nF/33 pF/10 pF. Load switch AO3401A adds ~0.1–0.15 V at 2 A → modem sees ≈ 3.6 V (min 3.3 V). OK.
- **Modem GND / heat**: solid pad connections, 48 GND vias in the module area, In1 solid GND plane under it.
- **RF**: grounded coplanar line on F.Cu, **0.32 mm** wide, 0.25 mm gap to the GND pour, over the In1 plane. PCBWay's
  standard 4-layer 1.6 mm stack-up (1 oz outer/inner, 7628 RC46 % prepreg 0.186 mm after lamination at > 60 %
  inner copper, Dk 4.74 per PCBWay; ~4.4 at GHz) gives ≈ 51 Ω (Dk 4.74) to 53 Ω (Dk 4.4) before solder mask,
  which takes off ~1–2 Ω. Microstrip alone would need ~0.30 mm. The lines are only ~9 mm long (U.FL → match → modem).
  **Order with impedance control: 50 Ω ±10 % on L1 referenced to L2** and let PCBWay adjust the width. Via fences on
  both sides of both lines (two GNSS fence vias gave way to the bias choke L401 / C418 next to J403).
- **GNSS antenna bias**: 3.3 V via U405 (TPS2552-1, latch-off, R_ILIM 232k → 100–137 mA) and L401 27 nH onto the U.FL
  side; C417 33 pF blocks DC towards the modem. Enabled by LTE_PWR_ON_N (Q102 gate, low = modem powered): the bias
  is only on while the modem is, and a latched fault clears with the next modem power cycle. No free ESP32 GPIO was
  left for a separate enable; FAULT is not connected.
- **USB 2.0 FS**: short D+/D− on the bottom, USBLC6 ESD at the connector; 90 Ω not critical at 12 Mbit/s.
- **CAN / K-Line**: ESD (NUP2105L, PESD1LIN) at the plug, no CAN termination (by design).
- **SIM**: 22 Ω series + 33 pF on the lines, no TVS array. Fine while the holder is inside the case; add ESD if the
  SIM becomes user-accessible.
- **Quiescent current** (parked, modem switched off by Q102, ESP32 in deep sleep): buck ≈ 0.15 mA + LM74700 ≈ 0.08 mA
  + LDO + ESP32 — well under 1 mA.

## PCBWay order (outputs: `hardware/tools/fab.py` → `hardware/fab/`, git-ignored)

| Item | Setting |
|---|---|
| Board | 52 × 65 mm, 4 layers, 1.6 mm, FR-4 TG150+, 1 oz outer / 1 oz inner, standard stack-up (7628 prepreg) |
| Impedance | 50 Ω ±10 % single-ended on L1 (RF net class, 0.32 mm GCPW, gap 0.25 mm), reference L2 |
| Rules met | track/space 0.15/0.15 mm (min 0.1), via 0.6/0.3 mm, annular ring 0.15 mm (= minimum), hole-to-hole ≥ 0.35 mm, copper-to-edge 0.3 mm, silk text ≥ 0.8 mm / 0.15 mm stroke |
| Vias | tented, not filled (no via-in-pad except the ESP32 module's EPAD thermal vias) |
| Finish / mask | ENIG recommended (0.4 mm-pitch U404, LGA modem); green mask, smallest mask web 0.155 mm (U404) |
| Assembly | both sides; fiducials 3 per side; J201 OBD plug **not assembled** (hand-solder); DNP parts are left out of BOM and CPL |
| Panel | parts sit 1–2 mm from the edges and J301 (USB-C) overhangs the rear edge by 0.3 mm: let PCBWay add 5 mm rails with tab routing (no V-cut), rails clear of J201 / J301. J201's housing sits entirely in front of the front edge (20 mm); it is hand-soldered after delivery, so the panel never carries it |
| Files | `obd-v2x-dongle-gerber.zip` (Gerber X2 + Excellon), `obd-v2x-dongle-bom.csv`, `obd-v2x-dongle-cpl.csv` (origin = board bottom-left; PCBWay checks rotations) |

## Accessibility (case design)

| What | Where | Access |
|---|---|---|
| OBD plug | top, front edge; housing entirely in front of the board edge (edge = housing rear face) | case rib in the retention groove behind the 1.5 mm rear flange, all four sides |
| USB-C (power, ESP32 flashing/logs) | bottom, rear edge, 0.3 mm overhang | case cut-out ✓ |
| RESET / BOOT buttons | bottom, near rear edge, top-actuated | pinholes in the case bottom (BOOT rarely needed: the C5's USB-Serial-JTAG can enter download mode itself) |
| RGB LED | bottom, rear-left corner | light pipe / window in the case bottom |
| **Nano-SIM** | **bottom, middle; hinged holder** | **case must be opened** – see open decisions |
| U.FL (LTE main, GNSS) | top, right edge | inside the case ✓ |
| U.FL 5.9 GHz | on the ESP32 module (bottom) | inside the case ✓ |
| Test pads: ESP UART0 TX + SIM_SEL, modem USB/USB_BOOT/debug UART | bottom | case open; modem firmware updates need the modem USB pads |

Case: `mechanical/` (build123d script, STL/STEP, see its README).

## Open decisions

1. **SIM** – decided: both SIMs on the modem's one SIM interface through the FSA2567 switch U404, selected by the
   ESP (SIM_SEL = IO12, formerly UART0 RX; console/flashing use USB). Default (SIM_SEL low) is the nano-SIM holder
   (works with Telekom / Vodafone / congstar plug-in SIMs and with removable eSIM cards). The soldered MFF2 eSIM
   (U403) is not fitted yet, for a possible SGP.32 IoT eSIM later. Consumer eSIM profiles on a soldered chip would need an LPA in our firmware and the
   EC200U's support for it is unclear.
2. **Backup battery** – decided: 1S Li-ion/LiPo with BQ25171-Q1 charger and TPS2121 power mux (sheet 6).
3. **Mounting holes** – none; the case has to clamp the board (plug + edges).
