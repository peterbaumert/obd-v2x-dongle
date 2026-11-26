# Rev 2: BOM, sourcing and order notes

Full BOMs: [`bom-carrier.csv`](bom-carrier.csv) and [`bom-upper.csv`](bom-upper.csv), exported from the schematics
by `rev2/hardware/tools/fab.py`. The MPN, Manufacturer and LCSC fields come from `SOURCING` in
`rev2/hardware/tools/gen_schematic.py`. Generic resistors and capacitors are left as value + footprint, so PCBWay can
pick any in-stock part (as in rev 1).

## Order files

Ordered as **one panel**: one carrier and one upper board side by side in a 5 mm frame
(`rev2/hardware/tools/panel.py` -> `rev2/hardware/panel/obd-v2x-panel.kicad_pcb`). One PCB order and one assembly
job instead of two each: on 2026-11-24 PCBWay quoted $217.65 for 5 panels + 2 assembled panels against $300.08 for
the two boards separately (before parts).

`<KiCad>/bin/python rev2/hardware/tools/fab.py` writes the order files to `rev2/hardware/fab/panel/` (and one set per
board to `fab/carrier/`, `fab/upper/`; all git-ignored): Gerber zip, assembly BOM (both boards' parts, unique
designators), pick-and-place file (origin = bottom-left corner of the panel, or of the board).

| Setting | Value |
|---|---|
| Panel | 106 × 59 mm, panel by customer, 2 different designs, X-outs not accepted |
| Board | 4 layers, 1.6 mm, 1 oz outer / 1 oz inner, standard stack-up, 5/5 mil, 0.3 mm min. hole |
| Finish | ENIG (flat pads for the modem, the 0.5 mm-pitch QFNs and the SKY65943-11) |
| Impedance control | none: the RF lines are drawn for the standard stack-up (see `rev2/README.md`) |
| Assembly | turnkey, double-sided, panelized PCBs (quantity = single boards: 2 panels = 4) |

The panel: 2 mm milled gaps, 9 tabs with mouse bites (0.5 mm holes) placed only where no part comes within 1.5 mm
of the edge (the carrier's front edge between the OBD plug's legs, the upper board clear of the USB-C and the SIM
holder, which both overhang their edges), 3 fiducials per side and 4 tooling holes on the frame. The bites sit just
outside the board edge: after breaking out, file the stubs flush (the case leaves 0.3 mm around the boards, and the
OBD plug sits 0.35 mm in front of the carrier's front edge), then fit the plug.

## Not fitted by PCBWay

| Ref | Part | Why |
|---|---|---|
| J201 | OBD-II plug CR-PG001 (carrier) | Not stocked by LCSC or Digi-Key. Hand-solder after assembly; see `rev1/docs/bom-notes.md` |
| H601, H602, H701, H702 | M2.5 holes | Two M2.5 × 12 mm female-female spacers join the boards; per spacer one M2.5 × 8 from below (bottom shell + carrier) and one M2.5 × 10 from above (lid + upper board). DIN 7985 pan head (5.0 mm across, 2.0 high; the case counterbore is Ø5.6 × 2.2). Bought separately, see "Bought separately" below |
| Cell | 1S LiPo with protection, JST-PH lead (pin 1 = +) | Bought separately; see `rev2/README.md` |
| GNSS jumper | U.FL plug to U.FL plug, 50 mm: **Hirose U.FL-2LPHF6-088N1T-AC-50** (LCSC C26098117, 35 in stock 2026-11-25; or U.FL-2LPHF6-088N1T-A-50, C18106195), or any U.FL / IPEX MHF1 plug-to-plug cable of 30 to 100 mm. Bought separately: PCBWay only buys parts that go on the board (asked 2026-11-25), and Digi-Key alone would cost 25 € shipping | Carrier J403 (top) to upper J801 (bottom): 15 mm apart sideways, 12 mm in height. Digi-Key alternatives: Cinch 415-0086-050 (1.13 mm) or 415-0088-050. Not an "extension" cable (plug to jack): both board connectors are jacks |

Test pads and DNP parts are not in the assembly BOM or the pick-and-place file.

## Bought separately (German shops, checked 2026-11-26)

Per dongle; no single shop had everything in stock.

| Part | Shop, article | Note |
|---|---|---|
| GNSS jumper, U.FL plug to plug, 10 cm | Conrad 3384122 (Delock 89607) | BerryBase lists it too (D89607), out of stock |
| 2 × spacer M2.5 × 12 mm, female-female | BerryBase TFF-M2.5 (length 12 mm) | |
| 2 × screw M2.5 × 8, DIN 7985 pan head (from below) | BerryBase D7988 | |
| 2 × screw M2.5 × 10, DIN 7985 pan head (from above) | BerryBase M25X10D7985 | |
| Cell, 1S LiPo, JST-PH | Eckstein ZB07003 (PKNERGY LP521630, 5.2 × 16 × 30 mm, 250 mAh) | Check the polarity before plugging in (pin 1 = +) |
| LED light rod, 3 mm clear acrylic, cut to length | not found at these shops | Optional: the 3 mm hole alone shows the LED |

## Fitted by PCBWay, by hand

| Ref | Part | Note |
|---|---|---|
| AE801 | Taoglas CGGBP.25.4.A.02 GNSS patch (upper, top) | Pin-fed: fit after reflow, solder the feed pin from the bottom, fix the patch with its adhesive pad. Not at LCSC; Digi-Key had 6,403 on 2026-11-20 |
| J701, J702 | Hanxia HX PZ2.54-2x8P ZZ, 2 × 8 header, through-hole (upper, bottom) | Base flat on the board. Not the SMD version HX PZ2.54-2x8P TP (C32713288): an SMD header stands on its leads and the stack would bottom out |

## Stock (LCSC, 2026-11-24, `python rev2/hardware/tools/check_stock.py`)

Enough for a few boards everywhere, with these exceptions or thin stocks:

| Ref | Part | LCSC stock | Plan |
|---|---|---|---|
| SW301, SW302 | E-Switch TL3342F450QG (C2886897) | **11** | Needs 2 per set. Digi-Key about 24,700, active (2026-11-24, read from a summarised page). Any TL3342 force variant fits the same footprint |
| AE801 | Taoglas CGGBP.25.4.A.02 | not at LCSC | Digi-Key 6,403 (2026-11-20) |
| J401 | Molex 78646-3001 micro-SIM | not at LCSC | Digi-Key 113,150 (2026-11-20) |
| U401 | Quectel EC200UEUAA-N05-SGNSA (C2942341) | 50 | Fine for a few sets. "SGNS" = GNSS variant: confirm GNSS when ordering |
| U801 | Skyworks SKY65943-11 (C2654442) | 280 | Digi-Key about 42,000 (2026-11-20) |
| U501 | BQ25171-Q1 (C2861221) | 322 | |
| U201 | TCAN334DR (C2871143) | 388 | |
| U301 | ESP32-C5-WROOM-1U-N16R8-V1.2 (C54951857) | 494 | |
| C506 / C401 | Kemet T495D227K006ATE100 / T520V227M006ATE015 | 378 / 488 | |
| J601, J602 | Hanxia HX PM2.54-2x8P TP socket (C41427537) | 5,060 | Second source Hong Cheng HC-PM254-8.5H-2x8PS (C22436156), 2,430 |
| J701, J702 | Hanxia HX PZ2.54-2x8P ZZ header (C32713281) | 6,384 | Second source HCTL PZ254-2-08-Z-8.5 (C2894969), 2,523 |

All other MPN parts have 680 or more at LCSC (Q101 PSMN7R0-60YS 684, D202 B0540WS-7 785; the rest thousands).
The final word on stock is PCBWay's BOM quote.

## Footprints not checked against a real part

Drawn from the data sheets only: SKY65943-11 (ground pad sizes are my choice), the patch's feed pad (1.4 mm on
all layers + 2.2 mm on B.Cu, hole 1.1 mm) and the Molex micro-SIM holder (checked against the drawing SD-78646-001
rev C1). PCBWay's DFM review sees them before assembly.

## Off-board parts from the rev 1 Digi-Key order (arrived 2026-11-24)

Used in rev 2: Quectel YF0006AA LTE flex antenna, Molex 2119960100 5.9 GHz flex antenna, Adafruit 261 JST-PH lead.
Not used: Taoglas AGGP.25F and Quectel YFGA025E3CM GNSS antennas (rev 2 has the patch on the board), Bivar
PLP2-10MM light pipe (too long for the rev 2 lid: use a 3 mm clear rod cut to length), Keystone 689 #4 screws.
