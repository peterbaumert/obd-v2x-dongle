# BOM / sourcing notes

Status: schematic v0.1. Stock not yet checked against PCBWay.

| Ref | Part | Sourcing risk | Notes |
|---|---|---|---|
| U401 | Quectel EG25-G (EG25GGB) | Medium | Sold via Digi-Key/Mouser; LGA-144 needs a custom footprint (Hardware Design V1.5 §7.2). |
| U301 | ESP32-C5-WROOM-1U-N8R4 | Low–medium | Newer module, check stock. 1U footprint still to create (WROOM-1 SparkFun footprint in `lib/obd-v2x.pretty` as reference). |
| J201 | OBD-II J1962 male plug | **High** | PCB-mount J1962 plugs are rare; may be consigned or a wired plug. Footprint TBD once part chosen. |
| J401 | GCT SIM8060-6-0-14-00 nano-SIM | Low | |
| U102 | TI TPS54360DDA | Low | Compensation values (R106/C105/C106) are first-pass — verify with TI WEBENCH. |
| U101 / Q101 | TI LM74700-Q1 + Nexperia PSMN5R2-60YL | Low | Ideal-diode reverse protection. |
| U201 | TI TCAN334 | Low | |
| U202 | NXP TJA1021T/20 | Low | Used as K-Line transceiver (10.4 kbit/s, within LIN 20 kbit/s slope). |
| U402 | TI TXS0108EPW | Low | |
| C411–C416 | Antenna π-match | — | DNP until antennas are tuned. |
