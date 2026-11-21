"""Last-connections pass for a rev 2 board (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/finish.py carrier|upper [rounds]

route_unconnected.py routes with 0.2 mm tracks and extra clearance and leaves GND to the pours. This pass takes
what is still open after it: every unconnected pair from DRC, GND included, is routed with maze.py, 0.2 mm wide
and then 0.15 mm if that fails, keeping 0.21 mm from other copper (0.26 mm for GND, which runs next to the RF
and supply classes). A GND pad that DRC pairs with a pour is routed to the
nearest GND via instead. Pour-to-pour gaps are left to stitch.py. Run DRC afterwards.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BOARD = next((a for a in sys.argv[1:] if a in ('carrier', 'upper')), None)
if BOARD is None:
    raise SystemExit('usage: finish.py carrier|upper [rounds]')
ROUNDS = next((int(a) for a in sys.argv[1:] if a.isdigit()), 3)
os.environ['REV2_BOARD'] = BOARD
sys.path.insert(0, str(Path(__file__).parent))
import pcbnew  # noqa: E402
import maze  # noqa: E402
from kicad_env import CLI  # noqa: E402

PCB = maze.PCB
SUPPLY = {'OBD_VBAT', 'VBAT_F', 'VIN_PROT', 'VSYS_3V8', 'VBAT_LTE', 'VBUCK_3V8', 'VCELL', 'Net-(D103-K)'}   # wider tracks first
OX, OY = maze.OX, maze.OY


def drc():
    out = Path(tempfile.gettempdir()) / f'obd-v2x-rev2-{BOARD}-finish.json'
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-error', '--format', 'json',
                    '-o', str(out), PCB.name], capture_output=True)
    return json.loads(out.read_text(encoding='utf-8'))


def layer(desc):
    for name in ('In2', 'B', 'F'):
        if f'on {name}.Cu' in desc and name in maze.LNAME:
            return name
    return 'B' if 'B' in maze.LNAME else 'F'          # vias, through-hole pads


def nearest_gnd_via(board, x, y, skip=0.9):
    best = None
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == 'GND':
            vx, vy = pcbnew.ToMM(t.GetPosition().x) - OX, pcbnew.ToMM(t.GetPosition().y) - OY
            d = ((vx - x) ** 2 + (vy - y) ** 2) ** 0.5
            if d >= skip and (best is None or d < best[0]):
                best = (d, vx, vy)
    return best


def main():
    failed = set()
    for rnd in range(ROUNDS):
        d = drc()
        unc = d.get('unconnected_items', [])
        todo = [v for v in unc if not all('Zone' in i['description'] for i in v['items'])]
        print(f'round {rnd}: {len(unc)} unconnected, {len(todo)} with a pad or track')
        progress = False
        for v in todo:
            a, b = v['items'][0], v['items'][1]
            if 'Zone' in a['description']:
                a, b = b, a
            full = a['description'].split('[')[1].split(']')[0]        # whole name: net names may contain '/'
            net = full[1:] if full.startswith('/') else full
            pa = (a['pos']['x'] - OX, a['pos']['y'] - OY)
            la = layer(a['description'])
            if 'Zone' in b['description']:
                board = pcbnew.LoadBoard(PCB.name)
                hit = nearest_gnd_via(board, *pa)
                if hit is None:
                    continue
                pb, lb = (hit[1], hit[2]), la
            else:
                pb, lb = (b['pos']['x'] - OX, b['pos']['y'] - OY), layer(b['description'])
            key = (net, round(pa[0], 2), round(pa[1], 2), round(pb[0], 2), round(pb[1], 2))
            if key in failed:
                continue
            maze.CLR = 0.26 if net == 'GND' else 0.21
            for w in ((0.4, 0.3, 0.2) if net in SUPPLY else (0.2, 0.15)):
                board = pcbnew.LoadBoard(PCB.name)
                try:
                    maze.route(board, maze.full_net(board, net), pa, maze.LNAME[la], pb, maze.LNAME[lb], w)
                except SystemExit as e:
                    msg = str(e)
                    continue
                board.Save(PCB.name)
                progress = True
                break
            else:
                failed.add(key)
                print(f'   open: {net} ({pa[0]:.2f}, {pa[1]:.2f}) {la} -> ({pb[0]:.2f}, {pb[1]:.2f}) {lb}: {msg}')
        if not progress:
            break
    d = drc()
    print(f'after finish: {len(d.get("unconnected_items", []))} unconnected, '
          f'{sum(1 for v in d["violations"] if v["type"] != "starved_thermal")} rule errors')


if __name__ == '__main__':
    main()
