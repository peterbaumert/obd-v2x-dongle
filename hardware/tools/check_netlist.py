"""Compare the current schematic's connectivity with the reviewed reference netlist.

    python hardware/tools/check_netlist.py            compare
    python hardware/tools/check_netlist.py --update   accept the current connectivity (after review)

Exports a netlist with kicad-cli and compares nets as sets of (ref, pin), ignoring net
names (local labels get sheet-prefixed names) and #FLG/#PWR symbols.
The stored reference has the absolute source path and export date stripped (no local paths in git).
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kicad_env import CLI  # noqa: E402

HW = Path(__file__).resolve().parents[1]
REF = HW / 'tools' / 'reference.net'


def export(out):
    subprocess.run([str(CLI), 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', str(out),
                    str(HW / 'obd-v2x-dongle.kicad_sch')], check=True, capture_output=True)


def sanitize(text):
    text = re.sub(r'\(source "[^"]*[\\/]([^"\\/]+)"\)', r'(source "\1")', text, count=1)
    return re.sub(r'\(date "[^"]*"\)', '(date "")', text, count=1)


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
    if '--update' in sys.argv:
        with tempfile.TemporaryDirectory() as d:
            cur = Path(d) / 'cur.net'
            export(cur)
            REF.write_text(sanitize(cur.read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
        print(f'updated {REF.name}: {len(nets(REF))} nets')
        return 0
    with tempfile.TemporaryDirectory() as d:
        cur = Path(d) / 'cur.net'
        export(cur)
        a, b = nets(REF), nets(cur)
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
