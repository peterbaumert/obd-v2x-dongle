# Rev 1 bring-up

> Rev 1 was cancelled before production and never built. This procedure is the starting point for the first rev 2
> boards; check its test points and part references against the rev 2 schematics first (`rev2/README.md`,
> "Still open").

Step-by-step first power-on for a new rev 1 board. Do the steps in order. Every step
says what to measure and what counts as a pass; stop at the first failure and note it in the results table at the
end. Part references, test points and nets: `rev1/docs/schematic.pdf`.

## What you need

- Bench supply 0–30 V with current limit (or a 12 V supply with a 100 mA / 1 A fuse as a poor substitute).
- Multimeter; a USB-C cable to a computer with ESPHome (`pip install esphome`, 2026.10 or newer for the bring-up
  firmware; 2026.11 for the main firmware).
- Nano-SIM with data and **its PIN switched off** (put it in a phone first).
- LTE antenna (U.FL) and an active GNSS antenna (U.FL, 3.3 V) — the GNSS antenna can also be passive.
- The backup cell (1S Li-ion/LiPo with protection PCM, JST-PH lead): **check the lead's polarity, pin 1 = +**.
- Soldering iron for the OBD plug J201 (not assembled by PCBWay).

Two rules for the whole bring-up:

- **Never power the modem without the LTE antenna on J402.** The modem transmits as soon as it attaches.
- The board has no 120 Ω CAN termination on purpose; never add one (see `CLAUDE.md`).

## 1. Look and solder (no power)

1. Inspect both sides under a lens: modem U401 (LGA, flat, no lifted corner), ESP32 module U301, TSSOP U402,
   the small QFN/DFN parts (U404 0.4 mm pitch, U502, U501): no bridges, no tombstoned 0402s.
2. Polarity of the two tantalum capacitors C401 / C506 (stripe = +, towards the supply net in the PCB view), the
   diodes D101–D103, and the LED D301 orientation mark.
3. Solder the OBD plug J201 (all 16 legs). Pin 16 is +12 V, pins 4 and 5 are
   ground: confirm with the continuity tester from pin 16 to F101 and from pins 4/5 to TP303 (GND).

## 2. Resistance to ground (no power)

Measure each net to GND (TP303) with the multimeter, both probe orientations. Capacitors make the reading climb;
what matters is that none stays below ~100 Ω.

| Net (where to probe) | Pass |
|---|---|
| OBD pin 16 (OBD_VBAT) | > 10 kΩ (reverse-polarity FET off) |
| VIN_PROT (cathode of D102) | > 1 kΩ |
| VBUCK_3V8 (L101 output side) | > 1 kΩ |
| VSYS_3V8 / +3V3 (C107, C110, LDO U103 output) | > 500 Ω |
| VBAT_LTE (C401 +) | > 1 kΩ (load switch Q102 off) |
| CANH–CANL (OBD pins 6–14) | > 10 kΩ (no termination) |

## 3. First power from the bench supply (no SIM, no cell, no USB)

Connect the supply to OBD pin 16 (+) and pin 4 or 5 (−). Limit **100 mA**, start at 0 V and turn up to 12.0 V.

| Check | Pass |
|---|---|
| Current at 12 V | ~15–40 mA once the ESP32 has booted (no firmware yet: it sits in the ROM loader) |
| VIN_PROT | 11.9–12.0 V |
| VBUCK_3V8 | 3.75–3.83 V (0.8 V × (1 + 37.4k / 10k) = 3.79 V) |
| VSYS_3V8 (after the power mux U502) | 3.7–3.83 V |
| +3V3 | 3.25–3.35 V |
| VBAT_LTE | ~0 V (modem supply off until the firmware turns it on) |
| Nothing warm after a minute | U102, D103, L101, U103 at room temperature |

Then turn the supply down to 0 and check the input range:

- **Reverse polarity:** swap the leads, −12 V with 50 mA limit for a few seconds: current < 1 mA (LM74700 + Q101
  block it). Swap back.
- **Low input:** from 12 V slowly down: the buck keeps 3.8 V down to ~5 V input, the ESP32 restarts somewhere below.
- **Optional, jump-start:** 24 V with 100 mA limit for a few seconds: rails unchanged. Do not go above 30 V on the
  bench (the input TVS D101 starts conducting at 33 V).

## 4. Flash the bring-up firmware (USB)

USB-C VBUS also feeds VIN_PROT through D102, so the bench supply can stay on or be off; with USB alone, VIN_PROT
reads ~4.5 V and the modem must not be started (a USB port cannot supply its 2 A bursts).

```powershell
esphome run firmware/bringup.yaml
```

The ESP32-C5's USB-Serial-JTAG enters download mode by itself; if not, hold BOOT (SW302), tap RESET (SW301),
release BOOT. Then watch the log (`esphome logs firmware/bringup.yaml`). The bring-up firmware has no network and
needs no secrets. It never transmits on the car bus (CAN in standby, K-line asleep).

| Check | Pass |
|---|---|
| Flash and boot | log shows `=== self-test` 5 s after boot |
| LED D301 | red, green, blue for one second each (if the colours are swapped, change `rgb_order`) |
| `VIN_PROT` | bench supply voltage − ~0.1 V (USB only: ~4.5 V), within ±3 % |
| BOOT button | pressing SW302 logs `BOOT pressed` and runs the test again |

## 5. Modem power-on (bench supply 12 V, limit 1 A)

LTE antenna on J402, GNSS antenna on J403, nano-SIM in J401. Raise the current limit to **1 A** and press BOOT to
rerun the test (or tap RESET).

| Check | Pass |
|---|---|
| VBAT_LTE (C401 +) after `modem supply on` | 3.6–3.8 V |
| `modem STATUS -> HIGH` | within ~10 s after the PWRKEY pulse (the firmware waits 2 s after the supply, holds PWRKEY 2.5 s) |
| LTE_1V8 (TP407) | 1.75–1.85 V while the modem runs |
| GNSS bias on J403's centre pin (antenna off, modem on) | 3.2–3.3 V; 0 V with the modem off |
| Modem answers | `<<< RDY` and `<<< OK` to `AT`; `ATI` shows `EC200U`, `AT+QGMR` the firmware version |

If STATUS stays low: check VBAT_LTE, LTE_1V8 at TP407, and that PWRKEY at the modem goes low during the 2.5 s pulse
(Q401 collector). If STATUS is high but no answer: check MCU_TX/RX on both sides of U402 (3.3 V side idles high,
1.8 V side idles at 1.8 V) and try 921600 baud in `bringup.yaml` in case a previous firmware changed the rate.

## 6. SIM and LTE

From the AT log (the identity list runs once, then CSQ / CEREG / GNSS every 20 s):

| Command | Pass |
|---|---|
| `AT+CPIN?` | `+CPIN: READY` (`SIM PIN` = PIN still on; `+CME ERROR: 10` = no SIM: check J401 and the SIM switch U404) |
| `AT+QCCID` | the SIM's ICCID |
| `AT+CSQ` | first number 10–31 (99 = no signal yet: antenna, or still searching) |
| `AT+CEREG?` | `+CEREG: 0,1` (home) or `0,5` (roaming) within ~1 min |
| `AT+QNWINFO` | `"FDD LTE"` (or GSM) and an operator |
| `AT+CBC` | about 3700–3800 (mV at the modem) |

Watch the supply current during registration: peaks to ~0.4–0.7 A at 12 V are normal (LTE / GSM bursts). The
3.8 V rail must not drop below ~3.4 V (measure at C401 with the meter's min/max function).

## 7. GNSS

Take the board (or the antenna on its cable) outside or to a window with open sky. `AT+QGPSLOC=2` answers
`+CME ERROR: 516` until it has a fix, then `+QGPSLOC: <time>,<lat>,<lon>,...`.

| Check | Pass |
|---|---|
| First fix | within ~5 min (cold start, no assistance data) |
| Position | within ~10 m of the real one |

If there is no fix after 15 min with open sky: check the GNSS bias (step 5), the antenna cable, and try a passive
patch antenna (the bias is harmless for most passive antennas with a DC-blocked feed; check its data sheet).

## 8. Backup cell, charger and power mux

Bench supply at 12 V. Plug the cell into J501 (polarity checked).

| Check | Pass |
|---|---|
| Charge current | supply current rises by ~70 mA (linear charger: the charge current comes straight from VIN_PROT) |
| VCELL (J501 pin 1) | rises towards 4.10 V and stops there (VSET 24k); RT501 against the cell |
| Supply off, cell on | the ESP32 keeps running (log continues), VSYS_3V8 ≈ cell voltage, LED still works |
| `AT+CBC` on cell | cell voltage in mV |
| Supply back on | VSYS_3V8 back to 3.8 V, no reset |

Leave it charging until the supply current drops back by the ~70 mA, to see that the charge terminates.

## 9. Main firmware (bench)

Copy `firmware/secrets.example.yaml` to `firmware/secrets.yaml`, fill in APN, WireGuard and MQTT, then
`esphome run firmware/obd-v2x-dongle.yaml` (ESPHome 2026.11 or newer). On the bench at 12.0 V (below the 13.2 V
"engine running" threshold) it behaves as parked.

| Check | Pass |
|---|---|
| LTE + PPP | log shows the modem connected, LED goes red → yellow → green |
| WireGuard / MQTT | entities appear in Home Assistant, "Car battery" ≈ 12.0 V |
| GPS | position in Home Assistant and Traccar |
| Parking mode | after "Sleep after engine off" the modem shuts down (`AT+QPOWD`) and the board sleeps |
| Parked current | with the board asleep and the cell full: **< 1 mA** at 12.6 V (meter in series, µA/mA range) |
| Engine simulation | supply up to 13.8 V: "Engine running" turns on after 5 s, the CAN transceiver leaves standby |

## 10. In the car (Mercedes C-Class W205)

1. **Engine off:** plug in. The dongle must stay silent on CAN (no requests below 13.2 V). Car battery value OK.
2. **Engine on:** OBD values within ~10 s (speed, RPM, coolant), VIN read once, no fault code appears in the car.
3. **Drive:** GPS track in Traccar; V2X frames counted when equipped cars are around (VW Golf 8 / ID family and
   others with ITS-G5); "V2X data sent" grows.
4. **Engine off again:** OBD stops, the board goes to parked mode and then sleeps; check the next day that the car
   started normally and the parked reports arrived.

## 11. Case

Print `rev1/mechanical/out/` (front at the plug's retention groove, ST2.2 × 9.5 screws), fit the board with the
plug, and check: board seats without force, rib sits in the plug's groove, USB-C, BOOT/RESET pinholes and LED window
line up, the cell fits next to RT501, the case closes over the U.FL cables. Note the real plug measurements (see
`rev1/docs/bom-notes.md`, J201).

## Results

Copy this table per board (serial = the number written on the board with a marker).

| Step | Board 1 | Board 2 | Notes |
|---|---|---|---|
| 1 Visual / J201 | | | |
| 2 Resistances | | | |
| 3 Rails, reverse polarity | | | |
| 4 Flash, LED, ADC | | | |
| 5 Modem on, 1V8, GNSS bias | | | |
| 6 SIM, LTE registration | | | |
| 7 GNSS fix | | | |
| 8 Cell, charger, mux | | | |
| 9 Main firmware, parked current | | | |
| 10 Car | | | |
| 11 Case | | | |

Findings here go into rev 2 (`rev2/README.md`, "Still open") before rev 2 is ordered.
