# BOM / sourcing notes

Full BOM: [`bom.csv`](bom.csv) (exported from the schematic; MPN / Manufacturer / LCSC fields come from
`SOURCING` in `rev1/hardware/tools/gen_schematic.py`).

Stock checked **2026-11-11** with `python rev1/hardware/tools/check_stock.py` (LCSC via the JLCPCB parts API) plus
Digi-Key for the critical parts. LCSC, Digi-Key and Mouser are PCBWay's main sources; the final word is the
PCBWay BOM-upload quote. Generic passives (R/C) are left as value + footprint so PCBWay can pick in-stock parts.

## Needs attention

| Ref | Part | Status | Plan |
|---|---|---|---|
| U301 | ESP32-C5-WROOM-1U-N16R8-V1.2 (C54951857) | LCSC **21 pcs**, ~$5.84 | Low stock: order soon. Fallbacks: ESP32-C5-WROOM-1-N16R8-V1.2 (PCB antenna, 323 pcs, but no U.FL, so not for the 5.9 GHz external antenna) or consign. All other C5 module variants were 0 on 2026-11-11 |
| U401 | Quectel EC200UEUAA-N05-SGNSA (C2942341) | LCSC 65 pcs, ~$13 @1 | Replaced EG25-G (~$66 LCSC / $126 Digi-Key). "SGNS" = GNSS variant per Quectel ordering code: confirm GNSS on order. |
| J401 / U403 / U404 | **SIM switch U404 (onsemi FSA2567UMX, C357761, 4431 pcs)** selects SIM 1 = nano-SIM holder J401 (default) or SIM 2 = soldered MFF2 eSIM U403; the eSIM chip itself is DNP | Holder in stock (GCT SIM8060); no MFF2 eSIM chosen yet | Firmware drives SIM_SEL (ESP IO12; R414 pulls it low = holder). Only switch while the modem is off or in `AT+CFUN=0`, then re-enable. Holder: any operator's plug-in SIM (Telekom, Vodafone, congstar, ...) or a removable eSIM card (9eSIM / eSIM.me). U403 can be fitted later without other changes (R411–R413, C415 are fitted). Second source NXP NX3DV2567GU (C2151045): checked against its datasheet (Rev. 2.1, XQFN16 SOT1161-1): same 16 pin functions on the same pins (1Y0 = 1VSIM, S = Sel, nY1 = SIM 2, ...), same 1.8 × 2.6 mm 0.4 mm-pitch package with elongated pin 1, VCC 1.4–4.3 V: drop-in |
| J501 + cell | 1S Li-ion/LiPo 250–400 mAh **with protection PCM**, JST-PH 2-pin lead | Cell not on the PCB BOM | Buy separately (products: "Bought separately" below); check polarity of the JST lead (pin 1 = +) before plugging in. NTC RT501 sits next to J501: mount the cell against it |
| U501 | BQ25171-Q1 charger (C2861221) | LCSC **141 pcs** | Low stock: order soon; Digi-Key/Mouser as fallback |
| J201 | OBD-II J1962 male plug, 90° THT (Jiatel CR-PG001 or same-mould equivalent, "OBD2 Stecker 16 Pin 90 Grad Platine") | Not stocked by LCSC/Digi-Key; ~€1–3 from AliExpress/eBay | **Hand-solder** after assembly. Footprint follows the CR-PG001 drawing: holes 2×8, P4.00, rows 3.00, Ø1.35 pins; the drawing's top view and section A-A give the pinout (leg row nearer the housing = pins 1–8, pin 1 and 9 at the same end, pin 16 = +12 V) and the housing rear face in front of the leg rows: the drawing's 5.65 mm goes to the outer leg's outer edge, so the leg centres are 5.25 / 2.25 mm behind the rear face (checked in the PDF's vector data; the Elecbee drawing is the same CR-PG001). The leg tips end level with the housing bottom, so the housing hangs ~1 mm below the board; the board's front edge sits 0.35 mm behind the rear face. Check with a caliper on the real plug. Drawing: [Jiatel](https://www.jiatelcn.com/wp-content/uploads/2025/05/OBDII-Male-90-RA-Model.pdf). PCBWay-assemblable alternative: Antenk OBD-FMB-16-SN-B-E-R-V2 (C46459580), contacts only, case must form the D-shroud |

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

## Bought separately (not on the PCB BOM)

Checked 2026-11-18: each item has a real product that ships to Germany. Prices and stock are from that day. Check
again before ordering. Antennas, pigtail and light pipe come from Digi-Key, which ships to Germany
free from €75. Digi-Key's backup cells are Marketplace items (shipped separately), so the cell comes from elsewhere.

| Item | Pick | Alternatives | Notes |
|---|---|---|---|
| LTE antenna (J402) | **Quectel YF0006AA**, FPC 50 × 25 × 0.13 mm, 698–960 / 1710–2690 MHz, U.FL, **30 mm cable** ([Digi-Key](https://www.digikey.de/en/products/detail/quectel/YF0006AA/17101890), ~€2.90) | YF0006PA: same antenna with a 90 mm cable (Avnet / Quectel only). Taoglas FXUB63.07.0150C (96 × 21 mm) or Molex 2091420180 (85 × 14.5 mm): better at low band but longer than the case, so they would have to bend over a wall | With the 30 mm cable the antenna has to sit on the lid right above J402 (rear right). No flat antenna that fits 52 × 70 mm is fully efficient at 700–800 MHz (B20/B28). |
| GNSS antenna (J403) | **Taoglas AGGP.25F.07.0060A**, active patch 25 × 25 × 7.4 mm, GPS/GLONASS/Galileo/BeiDou, 1.8–5.5 V, ~10 mA, 60 mm cable, MHF I ([Digi-Key](https://www.digikey.de/en/products/result?keywords=AGGP.25F.07.0060A), ~€17.70) | Quectel YFGA025E3CM (~€4.80, GPS/Galileo/BeiDou, **no GLONASS**). Electrokit 41037124 (25 × 25 × 4.6 mm, GPS L1 only) | Patch on the lid, facing up, at the front half (away from the LTE antenna). Its current is well inside U405's 100 mA limit. |
| 5.9 GHz antenna (ESP32 module) | **Molex 2119960100**, flex 16.4 × 7.6 mm, 5.85–5.925 GHz (DSRC/ITS-G5), 100 mm cable, U.FL ([Digi-Key](https://www.digikey.de/en/products/detail/molex/2119960100/10270663), ~€2) | Taoglas FXP830.07.0100C (Wi-Fi 6E dipole, 2.4 / 5 / 6 GHz, ~€6.25). Choose it if the ESP32 ever needs Wi-Fi/BLE too: the Molex is 5.9 GHz only. The firmware has no `wifi:` today | Module U.FL faces the floor. Stick the antenna on the floor, beside the cell. |
| Backup cell (J501) | **YDL 402535 320 mAh**, 4 × 25 × 37 mm, PCM, JST PH 2.0 (PHR-2) fitted, red = + ([ydlbattery.com](https://ydlbattery.com/products/ydl-402535-320mah-3-7v-lithium-polymer-battery-4x25x37mm-with-ph2-0-connector), $2.95 each, **minimum 4**, shipped from China, 20–30 days) | [ampul.eu 402535 350 mAh](https://ampul.eu/de/li-po-akkus/3180-lipo-akku-350-mah-3-7-v-402535) (€5.05, PCM, **bare wires**) or Amazon.de B0G6455WR2 (320 mAh, JST 1.25 plug). Either needs the pigtail below. | Most 402535 cells come with JST 1.25 / 1.0 plugs or bare wires. Always measure the polarity: J501 pin 1 = +. PHR-2 contacts can be swapped. |
| JST PH 2.0 pigtail | **Adafruit 261**: PHR-2 housing, 100 mm red/black 26 AWG, mates with J501 ([Digi-Key 1528-261-ND](https://www.digikey.de/en/products/detail/adafruit-industries-llc/261/5353586), ~€0.67) | [BerryBase AK-PH20-LP2P](https://www.berrybase.de/en/cable-lipo-compatible-with-2-pin-jst-ph-2.0mm-connector-awg26-20cm) (€0.33). Not Adafruit 3814 (wrong gender) | Only for a cell without a PH plug. Solder and heat-shrink one wire at a time. |
| Light pipe | **Bivar PLP2-10MM**: press-fit light pipe, Ø 3 mm, 10 mm long ([Digi-Key 492-2112-ND](https://www.digikey.de/en/products/detail/bivar-inc/PLP2-10MM/5721982), ~€0.61) | VCC LFB037CTP (9.5 mm, diffused, Digi-Key). Clear PMMA rod Ø 3 mm cut to 11 mm (diconfa.de, Amazon.de sturiz B0F4X96P7N) | Case hole is Ø 3.0 mm (`LIGHTPIPE`, Bivar recommends 2.92 mm). Press the pipe in from outside, flush with the floor. Its inner end then sits ~1.6 mm below the LED. |
| Case screws (2×) | **ST2.2 × 9.5 DIN 7981** (ISO 7049) pan-head self-tapping screw, A2 stainless, head Ø 4.2 mm (a standard size at fastener suppliers, e.g. [Keller & Kalmbach](https://www.keller-kalmbach.de/p/D7981CBGAABV002295/pdf), whose data sheet gives the head size, or [Galaxus, 100 pcs](https://www.galaxus.de/en/s4/product/self-tapping-screws-22-mm-95-mm-k-100-screws-per-piece-screws-8407513)) | ST2.2 × 9.5 DIN 7981 in steel (zinc) from any hardware store | Case changed 2026-11-20 (front face at the plug groove); the earlier #4 / 2.5 mm screws no longer fit. Head counterbore Ø 4.6 mm, pilot 1.8 mm. |
| OBD plug J201 | see "Needs attention" above (ordered, hand-soldered) | | |
| SIM | any nano-SIM data plan (Telekom/Vodafone/O2 networks) | | If you want SMS, the plan must include it (many data-only SIMs don't). |

## Backup battery (sheet 6)
- Charger BQ25171-Q1 from VIN_PROT via R501 33 Ω 0.5 W + D501 SMF24A clamp (keeps the charger input < 40 V abs max);
  70 mA (R502 4.3k), 4.10 V float (R503 24k), Li-ion + 10 h timer (R504 82k), NTC RT501 blocks charging outside ~0–45 °C.
- TPS2121 priority mux: IN1 = buck (VBUCK_3V8), IN2 = cell (VCELL), OUT = VSYS_3V8 (all loads). PR1 = VIN_PROT / 9.2:
  below ~9.7 V (unplugged, cranking) the system runs from the cell. ILIM 30.1k ≈ 3.5 A.
- Firmware: on battery use LTE only (lower burst current), shut the modem down below ~3.6 V cell; VSENSE tells the
  ESP32 that car power is gone. Parked + unplugged the board draws ~0.35 mA from the cell (mux Iq), so a 300 mAh cell
  lasts ~5 weeks before its PCM cuts off.
