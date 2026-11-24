# Rev 2: BOM, sourcing and order notes

Full BOMs: [`bom-carrier.csv`](bom-carrier.csv) and [`bom-upper.csv`](bom-upper.csv), exported from the schematics
by `rev2/hardware/tools/fab.py`. The MPN, Manufacturer and LCSC fields come from `SOURCING` in
`rev2/hardware/tools/gen_schematic.py`. Generic resistors and capacitors are left as value + footprint, so PCBWay can
pick any in-stock part (as in rev 1).

## Order files

`<KiCad>/bin/python rev2/hardware/tools/fab.py` writes one set per board to `rev2/hardware/fab/<board>/`
(git-ignored): Gerber zip, assembly BOM, pick-and-place file (origin = board bottom-left corner).

Two PCB orders and two assembly jobs, same settings for both:

| Setting | Value |
|---|---|
| Size | 45 × 45 mm, 4 layers, 1.6 mm, 1 oz outer / 1 oz inner, standard stack-up |
| Finish | ENIG (flat pads for the modem, the 0.5 mm-pitch QFNs and the SKY65943-11) |
| Impedance control | none: the RF lines are drawn for the standard stack-up (see `rev2/README.md`) |
| Assembly | double-sided on both boards |

## Not fitted by PCBWay

| Ref | Part | Why |
|---|---|---|
| J201 | OBD-II plug CR-PG001 (carrier) | Not stocked by LCSC or Digi-Key. Hand-solder after assembly; see `rev1/docs/bom-notes.md` |
| H601, H602, H701, H702 | M2.5 holes | Two M2.5 × 12 mm spacers and four M2.5 × 5 mm pan-head screws join the boards (and the case): bought separately |
| Cell | 1S LiPo with protection, JST-PH lead (pin 1 = +) | Bought separately; see `rev2/README.md` |

Test pads and DNP parts are not in the assembly BOM or the pick-and-place file.

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
