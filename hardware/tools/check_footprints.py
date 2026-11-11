"""Check that every pin of each project symbol has a pad in its project footprint.

    python hardware/tools/check_footprints.py

Pads without a symbol pin are listed for information (unused / reserved module pads).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sexp import parse, find  # noqa: E402

LIB = Path(__file__).resolve().parents[1] / 'lib'


def main():
    syms = parse((LIB / 'obd-v2x.kicad_sym').read_text(encoding='utf-8'))
    ok = True
    for s in find(syms, 'symbol'):
        fp = [p for p in find(s, 'property') if p[1] == 'Footprint']
        if not fp or not fp[0][2].startswith('obd-v2x:'):
            continue
        pins = {n[1] for u in find(s, 'symbol') for p in find(u, 'pin') for n in find(p, 'number')}
        f = LIB / 'obd-v2x.pretty' / (fp[0][2].split(':', 1)[1] + '.kicad_mod')
        if not f.exists():
            print(f'{s[1]:22} footprint {f.name} missing')
            ok = False
            continue
        pads = {p[1] for p in find(parse(f.read_text(encoding='utf-8')), 'pad')}
        missing = sorted(pins - pads, key=lambda x: (len(x), x))
        unused = sorted(pads - pins, key=lambda x: (len(x), x))
        print(f'{s[1]:22} {len(pins):3} pins / {len(pads):3} pads  '
              f'{"OK" if not missing else "MISSING " + ",".join(missing)}'
              f'{"  (unused pads: " + ",".join(unused) + ")" if unused else ""}')
        ok &= not missing
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
