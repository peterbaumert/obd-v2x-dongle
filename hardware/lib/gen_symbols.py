"""Generate hardware/lib/obd-v2x.kicad_sym (project symbol library).

Pin data sources:
  ESP32-C5-WROOM-1U : Espressif ESP32-C5-WROOM-1/1U datasheet v1.3, Table 3-2
  EC200U-EU         : Quectel EC200U Series QuecOpen Hardware Design V1.0, Figure 2 / Table 5
  OBD2 J1962        : SAE J1962 / ISO 15031-3 pinout

Run:  python hardware/lib/gen_symbols.py
"""
from pathlib import Path

G = 2.54
FONT = '(effects (font (size 1.27 1.27)))'


def pin(ptype, name, number, x, y, angle, hide=False):
    h = ' (hide yes)' if hide else ''
    return (f'\t\t\t(pin {ptype} line (at {x:.2f} {y:.2f} {angle}) (length 2.54){h}\n'
            f'\t\t\t\t(name "{name}" {FONT})\n'
            f'\t\t\t\t(number "{number}" {FONT})\n\t\t\t)\n')


def prop(key, val, x, y, hide=False):
    eff = '(effects (font (size 1.27 1.27)) (hide yes))' if hide else FONT
    return f'\t\t(property "{key}" "{val}" (at {x:.2f} {y:.2f} 0) {eff})\n'


def symbol(name, ref, fp, ds, desc, kw, left, right, bottom=(), top=(), width=12 * G):
    """left/right: list of (type, name, number) top->bottom; None = gap.
    bottom/top: list of (type, name, number, column) — pins with same column stack."""
    rows = max(len(left), len(right))
    half_w = width / 2
    y_top = (rows / 2) * G + G
    y_bot = y_top - (rows + 1) * G
    y_top = round(y_top / G) * G
    y_bot = round(y_bot / G) * G
    s = f'\t(symbol "{name}" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
    s += prop('Reference', ref, -half_w, y_top + G)
    s += prop('Value', name, half_w - 4 * G, y_top + G)
    s += prop('Footprint', fp, 0, y_bot - 2 * G, True)
    s += prop('Datasheet', ds, 0, y_bot - 3 * G, True)
    s += prop('Description', desc, 0, y_bot - 4 * G, True)
    s += prop('ki_keywords', kw, 0, y_bot - 5 * G, True)
    s += (f'\t\t(symbol "{name}_0_1"\n\t\t\t(rectangle (start {-half_w:.2f} {y_top:.2f}) (end {half_w:.2f} {y_bot:.2f})'
          f' (stroke (width 0.254) (type default)) (fill (type background)))\n\t\t)\n')
    s += f'\t\t(symbol "{name}_1_1"\n'
    for i, p in enumerate(left):
        if p:
            s += pin(p[0], p[1], p[2], -half_w - G, y_top - (i + 1) * G, 0)
    for i, p in enumerate(right):
        if p:
            s += pin(p[0], p[1], p[2], half_w + G, y_top - (i + 1) * G, 180)
    seen = set()
    for t, n, num, col in bottom:
        s += pin(t, n, num, col * G, y_bot - G, 90, hide=(('b', col) in seen))
        seen.add(('b', col))
    for t, n, num, col in top:
        s += pin(t, n, num, col * G, y_top + G, 270, hide=(('t', col) in seen))
        seen.add(('t', col))
    s += '\t\t)\n\t\t(embedded_fonts no)\n\t)\n'
    return s


B, I, O, P, PI, PO, OD, NC = ('bidirectional', 'input', 'output', 'passive', 'power_in',
                              'power_out', 'open_collector', 'no_connect')

# ---------------- ESP32-C5-WROOM-1U (32 pins) ----------------
esp = symbol(
    'ESP32-C5-WROOM-1U', 'U',
    'obd-v2x:ESP32-C5-WROOM-1U',
    'https://documentation.espressif.com/esp32-c5-wroom-1_wroom-1u_datasheet_en.pdf',
    'ESP32-C5 module, dual-band Wi-Fi 6 / BLE 5 / 802.15.4, CAN FD, external antenna (U.FL)',
    'ESP32 C5 WiFi 5GHz BLE module',
    left=[(PI, '3V3', 2), (I, 'EN', 3), None,
          (B, 'IO0/XTAL_32K_P', 6), (B, 'IO1/ADC1_CH0', 7), (B, 'IO2/MTMS', 4), (B, 'IO3/MTDI', 5),
          (B, 'IO4/MTCK', 17), (B, 'IO5/MTDO', 16), (B, 'IO6', 8), (B, 'IO7', 9), (B, 'IO8', 10),
          (B, 'IO9', 11), (B, 'IO10', 12), (B, 'NC/IO15', 19)],
    right=[(B, 'IO11/TXD0', 25), (B, 'IO12/RXD0', 24), (B, 'IO13/USB_D-', 13), (B, 'IO14/USB_D+', 14),
           (B, 'IO23', 21), (B, 'IO24', 23), (B, 'IO25', 26), (B, 'IO26', 27), (B, 'IO27', 18),
           (B, 'IO28', 15), None, (B, 'ANT2', 31), (NC, 'NC', 20), (NC, 'NC', 22)],
    bottom=[(PI, 'GND', n, 0) for n in (1, 28, 29, 30, 32)],
    width=16 * G,
)

# ---------------- Quectel EC200U-EU (LCC+LGA 144, used pins) ----------------
# Source: Quectel EC200U Series QuecOpen Hardware Design V1.0, Table 5. Pin 76 is GND on EC200U.
GND_PINS = [8, 9, 19, 22, 36, 46, 48, 50, 51, 52, 53, 54, 56, 72, 76] + list(range(85, 113))
eg25 = symbol(
    'EC200U-EU', 'U',
    'obd-v2x:Quectel_EC200U',
    'https://python.quectel.com/en/wp-content/uploads/sites/2/2024/11/Quectel_EC200U_Series_QuecOpen_Hardware_Design_V1.0.pdf',
    'Quectel EC200U-EU LTE Cat 1 module (GNSS variant -SGNSA), LCC+LGA-144 28x31 mm. Logic I/O 1.8 V. '
    'Unused/RESERVED pins not drawn.',
    'LTE Cat1 cellular modem GNSS Quectel EC200U',
    left=[(PI, 'VBAT_BB', 59), (PI, 'VBAT_BB', 60), (PI, 'VBAT_RF', 57), (PI, 'VBAT_RF', 58),
          (PO, 'VDD_EXT', 7), None,
          (I, 'PWRKEY', 21), (I, 'RESET_N', 20), (OD, 'STATUS', 61), (O, 'NET_STATUS', 6), (O, 'NET_MODE', 5),
          (I, 'W_DISABLE#', 4), (I, 'AP_READY', 2), (I, 'WAKEUP_IN', 1), (I, 'USB_BOOT', 115), None,
          (I, 'USB_VBUS', 71), (B, 'USB_DP', 69), (B, 'USB_DM', 70), None,
          (I, 'ADC0', 45), (I, 'ADC1', 44)],
    right=[(I, 'RXD', 68), (O, 'TXD', 67), (I, 'RTS', 65), (O, 'CTS', 64), (I, 'DTR', 66), (O, 'RI', 62),
           (O, 'DCD', 63), (I, 'DBG_RXD', 11), (O, 'DBG_TXD', 12), None,
           (PO, 'USIM_VDD', 14), (B, 'USIM_DATA', 15), (O, 'USIM_CLK', 16), (O, 'USIM_RST', 17),
           (I, 'USIM_DET', 13), (P, 'USIM_GND', 10), None,
           (B, 'ANT_MAIN', 49), (B, 'ANT_BT/WIFI', 35), (I, 'ANT_GNSS', 47)],
    bottom=[(PI, 'GND', n, 0) for n in GND_PINS],
    width=18 * G,
)

# ---------------- OBD-II J1962 male plug ----------------
obd = symbol(
    'OBD2_J1962_Plug', 'J',
    'obd-v2x:OBD2_J1962_Plug_PCB',
    'https://en.wikipedia.org/wiki/On-board_diagnostics#OBD-II_diagnostic_connector',
    'OBD-II (SAE J1962) 16-pin male plug, vehicle side pinout',
    'OBD OBD2 J1962 diagnostic connector',
    left=[(P, 'OEM1', 1), (P, 'OEM3', 3), (P, 'OEM8', 8), (P, 'OEM9', 9), (P, 'OEM11', 11),
          (P, 'OEM12', 12), (P, 'OEM13', 13), (P, 'J1850+', 2), (P, 'J1850-', 10), (P, 'L_LINE', 15)],
    right=[(P, 'VBAT', 16), None, (P, 'CAN_H', 6), (P, 'CAN_L', 14), None, (P, 'K_LINE', 7), None,
           (P, 'SIGNAL_GND', 5), (P, 'CHASSIS_GND', 4)],
    width=10 * G,
)


# ---------------- MFF2 eSIM (ETSI TS 102 671, 6 x 5 mm QFN-8, 1.27 mm) ----------------
# Pinout per vendor datasheets (Velocity IoT, Soracom, u-blox): 1 GND(C5), 2 VPP(C6), 3 I/O(C7), 4/5 NC,
# 6 CLK(C3), 7 RST(C2), 8 VCC(C1); exposed pad not connected.
esim = symbol(
    'eSIM_MFF2', 'U',
    'Package_SON:WSON-8-1EP_6x5mm_P1.27mm_EP3.4x4mm',
    'https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/4887/VIOT-1SIM-MFF2.pdf',
    'Embedded SIM / eUICC chip, MFF2 package (6 x 5 mm QFN-8); exposed pad not connected',
    'eSIM eUICC MFF2 SIM chip',
    left=[(PI, 'VCC', 8), (I, 'RST', 7), (I, 'CLK', 6), (B, 'I/O', 3)],
    right=[(PI, 'GND', 1), (NC, 'VPP', 2), (NC, 'NC', 4), (NC, 'NC', 5), (NC, 'EP', 9)],
    width=10 * G,
)


# ---------------- rail power symbols (cloned from KiCad's power:+3V3) ----------------
def rail_symbols(names):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    from sexp import parse, dump, find
    from kicad_env import SYMBOLS
    stock = SYMBOLS / 'power.kicad_sym'
    tree = parse(stock.read_text(encoding='utf-8'))
    base = [s for s in find(tree, 'symbol') if s[1] == '+3V3'][0]
    src = dump(base, 1)
    out = ''
    for n in names:
        out += '\t' + src.replace('"+3V3', '"' + n).replace('Power symbol creates a global label with name \\"' + n + '\\"',
                                                           'Power symbol creates a global label with name \\"' + n + '\\"') + '\n'
    return out


RAILS = ['VIN_PROT', 'VSYS_3V8', 'VBAT_LTE', 'LTE_1V8']

lib = ('(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "obd-v2x-gen_symbols")\n'
       '\t(generator_version "1.0")\n' + esp + eg25 + obd + esim + rail_symbols(RAILS) + ')\n')
out = Path(__file__).with_name('obd-v2x.kicad_sym')
out.write_text(lib, encoding='utf-8')
print('wrote', out)
