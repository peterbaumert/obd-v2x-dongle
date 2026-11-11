# BOM / sourcing notes

Full BOM: [`bom.csv`](bom.csv) (exported from the schematic; MPN / Manufacturer / LCSC fields come from
`SOURCING` in `hardware/tools/gen_schematic.py`).

Stock checked **2026-11-11** with `python hardware/tools/check_stock.py` (LCSC via the JLCPCB parts API) plus
Digi-Key for the critical parts. LCSC, Digi-Key and Mouser are PCBWay's main sources; the final word is the
PCBWay BOM-upload quote. Generic passives (R/C) are left as value + footprint so PCBWay can pick in-stock parts.

## Needs attention

| Ref | Part | Status | Plan |
|---|---|---|---|
| U301 | ESP32-C5-WROOM-1U-N16R8-V1.2 (C54951857) | LCSC **21 pcs**, ~$5.84 | Low stock: order soon. Fallbacks: ESP32-C5-WROOM-1-N16R8-V1.2 (PCB antenna, 323 pcs, but no U.FL, so not for the 5.9 GHz external antenna) or consign. All other C5 module variants were 0 on 2026-11-11 |
| U401 | Quectel EC200UEUAA-N05-SGNSA (C2942341) | LCSC 65 pcs, ~$13 @1 | Replaced EG25-G (~$66 LCSC / $126 Digi-Key). "SGNS" = GNSS variant per Quectel ordering code: confirm GNSS on order. |
| J201 | OBD-II J1962 male plug, 90° THT (Jiatel CR-PG001 or same-mould equivalent, "OBD2 Stecker 16 Pin 90 Grad Platine") | Not stocked by LCSC/Digi-Key; ~€1–3 from AliExpress/eBay | **Hand-solder** after assembly. Before ordering boards: check the hole pattern (2×8, P4.00, rows 3.00, Ø1.35 pins) and **pinout with a multimeter** on a real plug: footprint assumes the row nearer the housing = pins 1–8, pin 1 and 9 at the same end (pin 16 = +12 V). Drawing: [Jiatel](https://www.jiatelcn.com/wp-content/uploads/2025/05/OBDII-Male-90-RA-Model.pdf). PCBWay-assemblable alternative: Antenk OBD-FMB-16-SN-B-E-R-V2 (C46459580), contacts only, case must form the D-shroud |

## Changed for availability

| Ref | Was | Now | Why |
|---|---|---|---|
| Q101 | PSMN5R2-60YL | PSMN7R0-60YS,115 (C478143, 739 pcs) | only 21 in stock; same LFPAK56 footprint, 7 mOhm is fine at ~1 A |
| L101 | Bourns SRP7028A-6R8M | Sunlord MWSA0605S-6R8MT (C408466, 416 pcs) | 0 in stock; footprint changed to L_Sunlord_MWSA0605S |
| C401 | 220 uF tantalum (generic) | Kemet T495D227K006ATE100 (C2798131, 408 pcs) | first choice 0 in stock; same case D |
| SW301/302 | TL3342 | TL3342F450QG (C2886897) | in-stock variant, same footprint |
| U301 | ESP32-C5-WROOM-1U-N8R4 | ESP32-C5-WROOM-1U-N16R8-V1.2 (C54951857, 21 pcs) | N8R4 0 everywhere; same module, pinout and footprint, more flash/PSRAM, chip rev v1.2 |
| U401 | EG25-G (Cat 4, $66+) | EC200U-EU (Cat 1, ~$13) | cost; Cat 1 is plenty for telemetry/V2X upload. LTE diversity antenna chain removed (EC200U has none) |

## In stock (LCSC, 2026-11-11)

F101 0466002.NRHF (55k) · D101 SMCJ33CA (94k) · U101 LM74700QDBVRQ1 (3.8k) · D102 SS14 (1.5M) ·
U102 TPS54360DDAR (4.6k) · D103 B560C-13-F (65k) · U103 TLV75733PDBVR (24k) · Q102 AO3401A (1.6M) ·
Q103 2N7002 (6M) · U201 TCAN334DR (235) · D201 SZNUP2105LT1G (271k) · U202 TJA1021T/20 (25k) ·
D202 B0540WS (785) · D203 PESD1LIN (104k) · D301 SK6812MINI-E (210k) · U302 USBLC6-2SC6 (220k) ·
J301 HRO TYPE-C-31-M-12 (283k) · U402 TXS0108EPWR (93k) · Q401/402 MMBT3904 (4.2M) ·
J401 GCT SIM8060-6-0-14-00 (2.2k) · J402–404 Hirose U.FL-R-SMT-1(10) (17k)

## Design notes

- U102 compensation (R106/C105/C106) is a first pass — verify with TI WEBENCH.
- C411–C416 antenna pi-match caps are DNP until the antennas are tuned.
- U301: the 5.9 GHz antenna plugs into the module's own U.FL (ANT1, default). Pad 31 (ANT2) is disabled by
  default and left unconnected; pin 19 (IO15) is the PSRAM chip select on N16R8 and must stay unconnected.
- U401 footprint follows Quectel's recommended land pattern; keep 3 mm clearance around the module.
