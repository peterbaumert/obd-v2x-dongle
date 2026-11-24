"""LCSC stock for every rev 2 part with an MPN, read from rev2/docs/bom-<board>.csv (run fab.py first).

    python rev2/hardware/tools/check_stock.py [EXTRA_KEYWORD ...]

Searches the public JLCPCB parts list (LCSC stock) by the LCSC number, else by the MPN. LCSC is one of the
distributors PCBWay buys from; parts it does not carry (the patch, the SIM holder) are checked at Digi-Key by hand.
Final word: PCBWay's BOM quote. Writes rev2/hardware/tools/stock.json.
"""
import csv
import json
import sys
import urllib.request
from pathlib import Path

URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'
HERE = Path(__file__).resolve().parent
DOCS = HERE.parents[1] / 'docs'
LOW = 500           # flag stock below this


def search(kw):
    body = json.dumps({'keyword': kw, 'currentPage': 1, 'pageSize': 10}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return (d.get('data') or {}).get('componentPageInfo', {}).get('list') or []


def norm(s):
    return ''.join(ch for ch in s.upper() if ch.isalnum())


def lookup(lcsc, mpn):
    for kw in [k for k in (lcsc, mpn) if k]:
        try:
            res = search(kw)
        except Exception as e:  # noqa: BLE001
            print('error', kw, e, file=sys.stderr)
            continue
        for c in res:
            if (lcsc and c.get('componentCode') == lcsc) or (mpn and norm(mpn)[:10] in norm(c.get('componentModelEn', ''))):
                return c.get('componentModelEn', ''), c.get('componentCode', ''), c.get('stockCount') or 0
    return None


def main():
    lines = []
    for board in ('carrier', 'upper'):
        for r in csv.DictReader((DOCS / f'bom-{board}.csv').open(newline='', encoding='utf-8')):
            if r['DNP'] or not r['MPN'] or r['Manufacturer'] == 'generic':
                continue
            lines.append((board, r['Reference'], r['MPN'], r['LCSC']))
    for kw in sys.argv[1:]:
        lines.append(('extra', kw, kw, kw if kw.startswith('C') and kw[1:].isdigit() else ''))
    out = []
    print(f"{'Board':8} {'Ref':12} {'MPN':32} {'LCSC':10} {'Stock':>8}")
    for board, refs, mpn, lcsc in lines:
        hit = lookup(lcsc, mpn)
        stock = hit[2] if hit else 0
        flag = '' if hit and stock >= LOW else ('  LOW' if hit else '  not at LCSC')
        print(f'{board:8} {refs[:12]:12} {mpn[:32]:32} {(hit[1] if hit else lcsc)[:10]:10} {stock:>8}{flag}')
        out.append({'board': board, 'refs': refs, 'mpn': mpn, 'lcsc': hit[1] if hit else lcsc,
                    'lcsc_mpn': hit[0] if hit else None, 'stock': stock})
    json.dump(out, (HERE / 'stock.json').open('w'), indent=1)


if __name__ == '__main__':
    main()
