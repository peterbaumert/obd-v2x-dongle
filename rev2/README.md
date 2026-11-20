# Rev 2: two stacked boards in a 25 mm case

Status: **design brief, nothing drawn yet.** Rev 1 (`../rev1/`) is the board in production and stays as it is.
Rev 2 lives in this folder (`hardware/`, `mechanical/`, `docs/` once they exist). The firmware (`../firmware/`) is
shared.

## Goal

The size of a commercial OBD tracker: about **68 × 50 × 25 mm including the plug**, instead of rev 1's
87.4 × 56.6 × 34.1 mm. Same functions as rev 1 except for the changes under "Decisions".

## How it gets smaller

Rev 1 is one 52 × 64.4 mm board. The 18 mm above it (the height of the OBD plug) is mostly empty, and parts up to
10 mm tall hang below it. Rev 2 uses that space:

- **Same OBD plug** (CR-PG001, 90° through-hole), still entirely in front of the board edge.
- **Two boards of about 45 × 45 mm**, stacked, joined by board-to-board headers.
- **Carrier board** (lower): the plug, and the LTE module flat on the underside. Nothing else below the board is
  taller than the module (2.4 mm).
- **Upper board**: sits about 11 mm above the carrier, inside the plug's own height.

### Height budget (z = 0 at the carrier's bottom face)

| From | To | What |
|---|---|---|
| −4.3 | −2.7 | floor, 1.6 mm |
| −2.7 | 0 | EC200U (2.4 mm) + 0.3 mm clearance |
| 0 | 1.6 | carrier board |
| 1.6 | 12.8 | gap between the boards, 11.2 mm: carrier top-side parts, the backup cell, upper-board underside parts |
| 12.8 | 14.4 | upper board |
| 14.4 | 18.6 | GNSS patch (4 mm) + clearance; the plug's key ends at 18.3 |
| 18.6 | 20.6 | roof, 2.0 mm |

Total **24.9 mm**. The plug legs reach 10.9 mm above the carrier's bottom face, so the upper board clears them.
A standard 2.54 mm header in a standard socket stacks at 11.0 mm, which fits the 11.2 mm gap.

### Footprint

- Width: 45 mm board + 2 × 0.3 mm gap + 2 × 2 mm wall = **49.6 mm**.
- Length: 2 mm rear wall + 0.3 mm gap + 45 mm board + 0.35 mm + 20 mm plug = **67.7 mm**. The case front ends at the
  plug's retention groove, as in rev 1.

### Does it fit? (part areas from the rev 1 board)

One side of a 45 × 45 mm board is 2025 mm². Rev 1 uses 1272 mm² of parts on top and 1047 mm² below, on 3349 mm².

| Part | Size | Height | Goes on |
|---|---|---|---|
| EC200U-EU | 29 × 32 mm | 2.4 mm | carrier, underside |
| ESP32-C5-WROOM-1U | 18 × 21 mm | 3.4 mm | upper board, underside |
| Nano-SIM holder | 14 × 15 mm | 1.5 mm | carrier, top side, at an edge (slot in the case) |
| Buck inductor | 7 × 7 mm | 4.8 mm | carrier, top side |
| 220 µF tantalums | 7 × 4 mm | 3.1 mm | carrier, top side |
| USB-C | 9 × 8 mm | 3.3 mm | upper board, rear edge |
| Plug legs | 32 × 7 mm | through-hole | carrier, front edge, blocks both sides |

## Board split (proposal)

**Carrier:** J201, input protection, buck, EC200U with its supply caps, nano-SIM holder, level shifter, LTE U.FL,
GNSS U.FL (jumper to the upper board), CAN and K-line / LIN transceivers (short stubs to the plug).

**Upper board:** ESP32-C5 module, USB-C, LED, RESET / BOOT buttons, charger, power mux, cell connector, NTC,
ceramic GNSS patch soldered on the top side, with its U.FL for the jumper.

**Across the headers:** VSYS 3.8 V, 3.3 V, VIN sense, GND (several pins), CAN TX / RX, LIN TX / RX / wake,
modem UART (TX, RX, RTS, CTS), PWRKEY, RESET_N, STATUS, LTE_PWR_EN, cell and charger lines. About 22
signals: two 2 × 8 headers, one at each side, which also hold the boards parallel.

## Decisions (2026-11-20)

- **Backup battery: kept**, with a smaller cell (about 200 mAh, 5 mm thick) lying between the boards.
- **K-line / LIN: kept.** The dongle stays a general OBD device, not CAN-only.
- **eSIM: dropped.** No MFF2 footprint and no SIM switch (rev 1's U403, U404, SIM_SEL); the nano-SIM holder goes
  straight to the modem.
- **GNSS antenna: a ceramic patch soldered on the upper board**, replacing rev 1's cabled active antenna. The modem
  is on the carrier, so a short U.FL jumper carries the signal between the boards.

## Still open

- **Passive patch or patch + LNA:** a passive patch right at the modem input may be enough. Decide from the EC200U
  hardware design guide and rev 1's GNSS results; keep rev 1's 3.3 V bias switch only if an LNA is used.
- **5.9 GHz and LTE antennas:** flex antennas on the case walls as in rev 1. The space is tighter, so check that
  they fit and stay away from the modem shield.

## Before any layout

- Bring up the rev 1 boards (expected mid-December 2026) and carry every fix into rev 2.
- Find buyable parts first: the board-to-board headers at the stack height, the smaller cell, the GNSS patch.
- Two boards mean two PCB orders and two assembly jobs. Get a quote before committing.
