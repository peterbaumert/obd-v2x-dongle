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
| J401 / U403 / U404 | **SIM switch U404 (onsemi FSA2567UMX, C357761, 4431 pcs)** selects SIM 1 = nano-SIM holder J401 (default) or SIM 2 = soldered MFF2 eSIM U403; the eSIM chip itself is DNP | Holder in stock (GCT SIM8060); no MFF2 eSIM chosen yet | Firmware drives SIM_SEL (ESP IO12; R414 pulls it low = holder). Only switch while the modem is off or in `AT+CFUN=0`, then re-enable. Holder: any operator's plug-in SIM (Telekom, Vodafone, congstar, ...) or a removable eSIM card (9eSIM / eSIM.me). U403 can be fitted later without other changes (R411–R413, C415 are fitted). Second source NXP NX3DV2567GU (C2151045): checked against its datasheet (Rev. 2.1, XQFN16 SOT1161-1): same 16 pin functions on the same pins (1Y0 = 1VSIM, S = Sel, nY1 = SIM 2, ...), same 1.8 × 2.6 mm 0.4 mm-pitch package with elongated pin 1, VCC 1.4–4.3 V: drop-in |
| J501 + cell | 1S Li-ion/LiPo 250–400 mAh **with protection PCM**, JST-PH 2-pin lead | Cell not on the PCB BOM | Buy separately; check polarity of the JST lead (pin 1 = +) before plugging in. NTC RT501 sits next to J501: mount the cell against it |
| U501 | BQ25171-Q1 charger (C2861221) | LCSC **141 pcs** | Low stock: order soon; Digi-Key/Mouser as fallback |
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
D202 B0540WS (785) · D203 PESD1LIN (104k) · D301 SK6812MINI-HS (89k) · U302 USBLC6-2SC6 (220k) ·
J301 HRO TYPE-C-31-M-12 (283k) · U402 TXS0108EPWR (93k) · Q401/402 MMBT3904 (4.2M) ·
J401 GCT SIM8060-6-0-14-00 (2.2k) · J402–404 Hirose U.FL-R-SMT-1(10) (17k)

## Design notes

- U102 compensation (R106 12k / C105 5.6 nF / C106 47 pF) follows the TPS54360 datasheet's Type II method; see
  design-review.md. Not run in WEBENCH.
- D301 SK6812MINI-HS: own symbol/footprint (its pinout differs from KiCad's SK6812MINI). Spec VDD is 3.7–5.5 V: fine on
  the buck (3.79 V); on the backup cell VSYS follows the cell (down to ~3.0 V), so the LED may misbehave or stay dark –
  firmware should not rely on it on battery.
- C411–C414 antenna pi-match caps are DNP until the antennas are tuned (R409/R410 = 0 Ω).
- U301: the 5.9 GHz antenna plugs into the module's own U.FL (ANT1, default). Pad 31 (ANT2) is disabled by
  default and left unconnected; pin 19 (IO15) is the PSRAM chip select on N16R8 and must stay unconnected.
- U401 footprint follows Quectel's recommended land pattern; keep 3 mm clearance around the module.

## Antennas (case design)
- The board has no on-board antennas: ESP32-C5-WROOM-1U (5.9 GHz) uses the module's U.FL; LTE main (J402) and
  GNSS (J403) are U.FL. No PCB keep-out needed; what matters is where the antennas sit in the case.
- Mount the three antennas away from the PCB / ground planes (e.g. flex antennas on the inner case walls),
  on different walls, a few cm apart (LTE TX can desensitise GNSS). Plastic case only.
- Under the dash GNSS reception is poor: optional U.FL->SMA pigtail to an external GNSS antenna behind the windscreen.
- Combined LTE + GNSS antennas (one body, two U.FL leads) fit: LTE lead -> J402, GNSS lead -> J403.
- **GNSS antenna bias** (J403): 3.3 V on the U.FL centre pin while the modem is powered, so active GNSS antennas
  (with LNA) work. U405 TPS2552DBVR-1 (C140331) limits it to 100–137 mA and latches off on a short; it re-arms when
  the modem is power-cycled (LTE_PWR_EN). Passive antennas that are DC-open just ignore it; a DC-shorted passive
  antenna trips the latch, and the antenna then works passively. Feed: L401 27 nH (LQG15HS27NJ02D, SRF ~1.7 GHz) with
  C418 33 pF bypass; C417 33 pF C0G (was the 0 Ω R410) keeps the DC off the modem's ANT_GNSS pin. Active antennas
  must accept 3.3 V (most are specified 2.7–5 V).

## Backup battery (sheet 6)
- Charger BQ25171-Q1 from VIN_PROT via R501 33 Ω 0.5 W + D501 SMF24A clamp (keeps the charger input < 40 V abs max);
  70 mA (R502 4.3k), 4.10 V float (R503 24k), Li-ion + 10 h timer (R504 82k), NTC RT501 blocks charging outside ~0–45 °C.
- TPS2121 priority mux: IN1 = buck (VBUCK_3V8), IN2 = cell (VCELL), OUT = VSYS_3V8 (all loads). PR1 = VIN_PROT / 9.2:
  below ~9.7 V (unplugged, cranking) the system runs from the cell. ILIM 30.1k ≈ 3.5 A.
- Firmware: on battery use LTE only (lower burst current), shut the modem down below ~3.6 V cell; VSENSE tells the
  ESP32 that car power is gone. Parked + unplugged the board draws ~0.35 mA from the cell (mux Iq), so a 300 mAh cell
  lasts ~5 weeks before its PCM cuts off.
