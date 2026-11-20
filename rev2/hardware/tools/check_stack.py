"""Check the board-to-board connectors: pin n of J601 / J602 (carrier) must carry the same net as pin n of
J701 / J702 (upper board), and every net both boards use by name must cross on a pin.

    python rev2/hardware/tools/check_stack.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kicad_env import CLI  # noqa: E402
from schgen import BOARDS  # noqa: E402

HW = Path(__file__).resolve().parents[1]
MATES = {'J601': 'J701', 'J602': 'J702'}
LOCAL_OK = re.compile(r'^(unconnected-|Net-\()')      # unnamed nets never match by name


def nets(board, tmp):
    out = Path(tmp) / f'{board}.net'
    subprocess.run([str(CLI), 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', str(out),
                    str(HW / board / f'{BOARDS[board]}.kicad_sch')], check=True, capture_output=True)
    t = out.read_text(encoding='utf-8')
    t = t[t.index('(nets'):]
    pins, names = {}, set()
    for p in re.split(r'\n\t\t\(net\s*\n', t)[1:]:
        name = re.search(r'\(name "([^"]*)"\)', p).group(1).lstrip('/')
        nodes = [(r, n) for r, n in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', p) if not r.startswith('#')]
        if nodes:
            names.add(name)
        for r, n in nodes:
            pins[(r, n)] = name
    return pins, names


def main():
    with tempfile.TemporaryDirectory() as d:
        cp, cn = nets('carrier', d)
        up, un = nets('upper', d)
    ok = True
    crossing = set()
    for a, b in MATES.items():
        for n in range(1, 17):
            x, y = cp.get((a, str(n))), up.get((b, str(n)))
            if x != y or x is None:
                ok = False
                print(f'  MISMATCH {a}.{n} = {x}   {b}.{n} = {y}')
            else:
                crossing.add(x)
    shared = {n for n in cn & un if not LOCAL_OK.match(n)}
    for n in sorted(shared - crossing):
        ok = False
        print(f'  NOT CONNECTED: net {n} exists on both boards but is on no connector pin')
    print(f'{len(crossing)} nets cross the stack: {", ".join(sorted(crossing))}')
    print('check passed' if ok else 'check FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
