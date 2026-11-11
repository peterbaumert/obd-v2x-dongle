# BOM / sourcing notes

Full BOM: [`bom.csv`](bom.csv) (exported from the schematic; MPN / Manufacturer / LCSC fields come from
`SOURCING` in `hardware/tools/gen_schematic.py`).

Stock checked **2026-11-11** with `python hardware/tools/check_stock.py` (LCSC via the JLCPCB parts API) plus
Digi-Key for the critical parts. LCSC, Digi-Key and Mouser are PCBWay's main sources; the final word is the
PCBWay BOM-upload quote. Generic passives (R/C) are left as value + footprint so PCBWay can pick in-stock parts.

## Needs attention

| Ref | Part | Status | Plan |
|---|---|---|---|
| U301 | ESP32-C5-WROOM-1U-N8R4 | **Out of stock** (LCSC 0, Digi-Key 0, restock est. Jan 2028) | Consign: supply modules to PCBWay yourself, or check stock again at order time |
| U401 | Quectel EC200UEUAA-N05-SGNSA (C2942341) | LCSC 65 pcs, ~$13 @1 | Replaced EG25-G (~$66 LCSC / $126 Digi-Key). "SGNS" = GNSS variant per Quectel ordering code: confirm GNSS on order. LCC+LGA-144 footprint still to create |
| J201 | OBD-II J1962 male plug | **Not available** at LCSC/Digi-Key as a PCB part | Hand-fitted: buy a PCB-pin J1962 male plug separately; footprint once the part is chosen |

## Changed for availability

| Ref | Was | Now | Why |
|---|---|---|---|
| Q101 | PSMN5R2-60YL | PSMN7R0-60YS,115 (C478143, 739 pcs) | only 21 in stock; same LFPAK56 footprint, 7 mOhm is fine at ~1 A |
| L101 | Bourns SRP7028A-6R8M | Sunlord MWSA0605S-6R8MT (C408466, 416 pcs) | 0 in stock; footprint changed to L_Sunlord_MWSA0605S |
| C401 | 220 uF tantalum (generic) | Kemet T495D227K006ATE100 (C2798131, 408 pcs) | first choice 0 in stock; same case D |
| SW301/302 | TL3342 | TL3342F450QG (C2886897) | in-stock variant, same footprint |
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
