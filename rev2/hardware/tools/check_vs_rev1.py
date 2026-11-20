"""Compare rev 2's connectivity (both boards joined through the stack connectors) with rev 1's reviewed netlist.

    python rev2/hardware/tools/check_vs_rev1.py

Parts that exist only in one revision are left out of the comparison (see ONLY_REV1 / ONLY_REV2). Everything
else must be connected exactly as in rev 1: the split into two boards must not change the circuit.
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
REV1_REF = HW.parents[1] / 'rev1' / 'hardware' / 'tools' / 'reference.net'
ONLY_REV1 = {'U403', 'U404', 'R411', 'R412', 'R413', 'R414', 'C415', 'C416'}      # eSIM, SIM switch
ONLY_REV2 = {'J601', 'J602', 'J701', 'J702', 'H601', 'H602', 'H701', 'H702'}      # stack connectors, spacers
# rev 1 nets that the removed SIM switch used to join (SIM 1 path): now one net each
REV1_JOIN = [('SIM_VDD', 'SIM1_VDD'), ('LTE_USIM_RST', 'SIM1_RST'), ('LTE_USIM_CLK', 'SIM1_CLK'),
             ('LTE_USIM_DATA', 'SIM1_DAT')]
# intended differences: (ref, pin) nodes whose net changed on purpose
CHANGED = {('U301', '24'), ('TP302', '1')}                                        # IO12: was SIM_SEL, now a spare pad


def read(path):
    t = Path(path).read_text(encoding='utf-8')
    t = t[t.index('(nets'):]
    out = []
    for p in re.split(r'\n\t\t\(net\s*\n', t)[1:]:
        name = re.search(r'\(name "([^"]*)"\)', p).group(1).lstrip('/')
        nodes = {(r, n) for r, n in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', p) if not r.startswith('#')}
        out.append((name, nodes))
    return out


def export(board, tmp):
    out = Path(tmp) / f'{board}.net'
    subprocess.run([str(CLI), 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', str(out),
                    str(HW / board / f'{BOARDS[board]}.kicad_sch')], check=True, capture_output=True)
    return read(out)


def clean(nets, drop):
    out = set()
    for nodes in nets:
        nodes = frozenset(n for n in nodes if n[0] not in drop and n not in CHANGED)
        if len(nodes) > 1:                              # single-pin nets say nothing about connectivity
            out.add(nodes)
    return out


def main():
    with tempfile.TemporaryDirectory() as d:
        boards = [export(b, d) for b in BOARDS]
    merged, unnamed = {}, []
    for nets in boards:
        for name, nodes in nets:
            if re.match(r'^(unconnected-|Net-\()', name):
                unnamed.append(nodes)
            else:
                merged.setdefault(name, set()).update(nodes)       # same name on both boards = joined by the stack
    rev2 = clean(list(merged.values()) + unnamed, ONLY_REV2)
    r1 = read(REV1_REF)
    for a, b in REV1_JOIN:                              # local labels: the name ends in ".../<label>"
        ia = next(i for i, (n, _) in enumerate(r1) if n.rsplit('/', 1)[-1] == a)
        ib = next(i for i, (n, _) in enumerate(r1) if n.rsplit('/', 1)[-1] == b)
        r1[ia] = (r1[ia][0], r1[ia][1] | r1[ib][1])
        del r1[ib]
    rev1 = clean([n for _, n in r1], ONLY_REV1)
    missing, extra = rev1 - rev2, rev2 - rev1
    for k in sorted(map(sorted, missing)):
        print('  ONLY IN REV 1:', k)
    for k in sorted(map(sorted, extra)):
        print('  ONLY IN REV 2:', k)
    ok = not missing and not extra
    print(f'{len(rev2)} nets compared', '- identical to rev 1 apart from the listed changes' if ok else '- DIFFERENT')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
