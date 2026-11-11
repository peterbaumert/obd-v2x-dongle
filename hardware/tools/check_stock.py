"""Check LCSC stock for every BOM line via the public JLCPCB parts search.

    python hardware/tools/check_stock.py

LCSC is one of the distributors PCBWay sources from; a part in stock here is very likely
orderable through PCBWay assembly. Final confirmation: PCBWay BOM upload quote.
"""
import json
import sys
import urllib.request

URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'

# ref(s), description, MPN candidates (first = preferred)
BOM = [
    ('F101', 'Fuse 2 A slow-blow 1206', ['0466002.NR', '1206L200SLYR', 'SMD1206P200TF']),
    ('D101', 'TVS 33 V bidir SMC', ['SMCJ33CA']),
    ('U101', 'Ideal diode controller', ['LM74700QDBVRQ1']),
    ('Q101', 'N-MOSFET 60 V LFPAK56', ['PSMN7R0-60YS,115', 'PSMN7R0-60YS']),
    ('D102', 'Schottky 1 A SMA', ['SS14']),
    ('U102', 'Buck 60 V 3.5 A', ['TPS54360DDAR']),
    ('D103', 'Schottky 5 A 60 V SMC', ['B560C-13-F', 'B560C']),
    ('L101', 'Inductor 6.8 uH', ['MWSA0605S-6R8MT']),
    ('U103', 'LDO 3.3 V 1 A', ['TLV75733PDBVR']),
    ('Q102', 'P-MOSFET SOT-23', ['AO3401A']),
    ('Q103', 'N-MOSFET SOT-23', ['2N7002']),
    ('U201', 'CAN transceiver 3.3 V', ['TCAN334DR', 'TCAN334GDR', 'TCAN334DCNR']),
    ('D201', 'CAN ESD', ['NUP2105LT1G']),
    ('U202', 'LIN transceiver (K-Line)', ['TJA1021T/20/C,118', 'TJA1021T/20']),
    ('D202', 'Schottky SOD-323', ['B0540WS-7', 'B0540WS']),
    ('D203', 'LIN ESD SOD-323', ['PESD1LIN,115', 'PESD1LIN']),
    ('U301', 'ESP32-C5 module, U.FL', ['ESP32-C5-WROOM-1U-N16R8-V1.2', 'ESP32-C5-WROOM-1U-N8R8-V1.2', 'ESP32-C5-WROOM-1U-N8R4']),
    ('D301', 'RGB LED', ['SK6812MINI-HS', 'SK6812MINI']),
    ('U302', 'USB ESD', ['USBLC6-2SC6']),
    ('J301', 'USB-C 16P', ['TYPE-C-31-M-12']),
    ('SW301,SW302', 'Tactile switch', ['TL3342F160QG', 'TL3342']),
    ('U401', 'LTE Cat 1 module + GNSS', ['EC200UEUAA-N05-SGNSA', 'EC200UEUAA']),
    ('U402', 'Level shifter 8 ch', ['TXS0108EPWR']),
    ('Q401,Q402', 'NPN SOT-23', ['MMBT3904']),
    ('J401', 'Nano-SIM holder', ['SIM8060-6-0-14-00']),
    ('J402,J403', 'U.FL connector', ['U.FL-R-SMT-1(10)', 'U.FL-R-SMT-1']),
    ('C401', '220 uF 6.3 V tantalum D', ['T495D227K006ATE100']),
    ('J201', 'OBD-II J1962 male plug', ['J1962', 'OBD2 male', 'OBD-II']),
]


def search(kw):
    body = json.dumps({'keyword': kw, 'currentPage': 1, 'pageSize': 10}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return (d.get('data') or {}).get('componentPageInfo', {}).get('list') or []


def main():
    rows = []
    for refs, desc, cands in BOM:
        best = None
        for kw in cands:
            try:
                res = search(kw)
            except Exception as e:  # noqa: BLE001
                res = []
                print('error', kw, e, file=sys.stderr)
            for c in res:
                mpn = c.get('componentModelEn', '')
                if kw.split(',')[0].split('(')[0].upper().replace('-', '')[:8] not in mpn.upper().replace('-', ''):
                    continue
                if best is None or (c.get('stockCount') or 0) > (best[2] or 0):
                    best = (mpn, c.get('componentCode'), c.get('stockCount') or 0, kw)
            if best and best[2] > 0:
                break
        rows.append((refs, desc, best))
    print(f"{'Ref':12} {'Part':28} {'LCSC MPN':28} {'LCSC#':10} {'Stock':>8}")
    for refs, desc, b in rows:
        if b:
            print(f'{refs:12} {desc[:28]:28} {b[0][:28]:28} {b[1]:10} {b[2]:>8}')
        else:
            print(f'{refs:12} {desc[:28]:28} {"-- not found --":28}')
    json.dump([{'refs': r, 'desc': d, 'mpn': b[0] if b else None, 'lcsc': b[1] if b else None,
                'stock': b[2] if b else 0} for r, d, b in rows],
              open(__file__.replace('check_stock.py', 'stock.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
