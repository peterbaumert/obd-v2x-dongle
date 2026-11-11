"""Compare the current schematic's connectivity with the reviewed reference netlist.

    python hardware/tools/check_netlist.py [reference.net]

Exports a netlist with kicad-cli and compares nets as sets of (ref, pin), ignoring net
names (local labels get sheet-prefixed names) and #FLG/#PWR symbols.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HW = Path(__file__).resolve().parents[1]
CLI = Path.home() / 'AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe'


def nets(path):
    t = Path(path).read_text(encoding='utf-8')
    t = t[t.index('(nets'):]
    out = {}
    for p in re.split(r'\n\t\t\(net\s*\n', t)[1:]:
        name = re.search(r'\(name "([^"]*)"\)', p).group(1)
        nodes = frozenset((r, n) for r, n in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', p)
                          if not r.startswith('#'))
        if nodes:
            out[nodes] = name
    return out


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else HW / 'tools' / 'reference.net'
    with tempfile.TemporaryDirectory() as d:
        cur = Path(d) / 'cur.net'
        subprocess.run([str(CLI), 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', str(cur),
                        str(HW / 'obd-v2x-dongle.kicad_sch')], check=True, capture_output=True)
        a, b = nets(ref), nets(cur)
    missing = [(a[k], sorted(k)) for k in a if k not in b]
    extra = [(b[k], sorted(k)) for k in b if k not in a]
    if not missing and not extra:
        print(f'OK: {len(b)} nets identical to reference')
        return 0
    for name, k in missing:
        print('MISSING ', name, k)
    for name, k in extra:
        print('NEW     ', name, k)
    return 1


if __name__ == '__main__':
    sys.exit(main())
