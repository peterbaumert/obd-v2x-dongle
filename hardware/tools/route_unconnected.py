"""Route whatever KiCad's DRC reports as unconnected, one connection at a time, with maze.py.

    <KiCad>/bin/python hardware/tools/route_unconnected.py [max_rounds]

Each round: refill + DRC (JSON) -> delete dangling tracks/vias -> GND stitching vias -> maze-route every
unconnected pair (Power class nets wide, falling back to narrower) -> save. Stops when nothing changes.
Run a final DRC afterwards and review the result in KiCad.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
import maze  # noqa: E402
from kicad_env import CLI  # noqa: E402

PCB = maze.PCB
POWER = {'OBD_VBAT', 'VBAT_F', 'VIN_PROT', 'VSYS_3V8', 'VBAT_LTE', 'Net-(D103-K)', 'Net-(D202-K)', 'VBUCK_3V8', 'VCELL'}
OX, OY = maze.OX, maze.OY


def drc():
    out = Path(tempfile.gettempdir()) / 'obd-v2x-route.json'
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board', '--format', 'json', '-o', str(out), str(PCB)],
                   capture_output=True)
    return json.loads(out.read_text(encoding='utf-8'))


def item_layer(desc):
    if 'on B.Cu' in desc:
        return 'B'
    if 'on F.Cu' in desc:
        return 'F'
    if 'on In2.Cu' in desc:
        return 'In2'
    return 'B'      # PTH pads / vias: any layer works, start on the bottom


def short(net):
    return net.split('/')[-1]


def cleanup(board, d):
    """delete exactly the dangling tracks/vias reported by DRC (matched by net, position and length)"""
    want = []
    for v in d['violations']:
        if v['type'] not in ('track_dangling', 'via_dangling'):
            continue
        i = v['items'][0]
        desc = i['description']
        net = short(desc.split('[')[1].split(']')[0])
        length = float(desc.split('length ')[1].split(' mm')[0].replace(',', '.')) if 'length' in desc else None
        want.append((net, round(i['pos']['x'], 2), round(i['pos']['y'], 2), length))
    n = 0
    for t in list(board.GetTracks()):
        if t.IsLocked():
            continue
        net = short(t.GetNetname())
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            pts, L = [(round(pcbnew.ToMM(p.x), 2), round(pcbnew.ToMM(p.y), 2))], None
        else:
            pts = [(round(pcbnew.ToMM(q.x), 2), round(pcbnew.ToMM(q.y), 2)) for q in (t.GetStart(), t.GetEnd(), t.GetPosition())]
            L = pcbnew.ToMM(t.GetLength())
        for k, (wn, wx, wy, wl) in enumerate(want):
            if wn == net and (wx, wy) in pts and (wl is None or L is None or abs(L - wl) < 0.002):
                board.Delete(t)
                want.pop(k)
                n += 1
                break
    return n


def main(rounds):
    failed = set()
    for rnd in range(rounds):
        d = drc()
        unc = d.get('unconnected_items', [])
        print(f'round {rnd}: {len(unc)} unconnected')
        if not unc:
            break
        board = pcbnew.LoadBoard(str(PCB))
        print('  dangling removed:', cleanup(board, d))
        board.Save(str(PCB))
        # GND: stitching vias for pads that still lack one
        board = pcbnew.LoadBoard(str(PCB))
        maze.gndvias(board)
        board.Save(str(PCB))
        progress = False
        for v in unc:
            a, b = v['items'][0], v['items'][1]
            net = a['description'].split('[')[1].split(']')[0]
            if net == 'GND' or 'Zone' in a['description'] or 'Zone' in b['description']:
                continue
            key = (net, round(a['pos']['x'], 2), round(a['pos']['y'], 2), round(b['pos']['x'], 2), round(b['pos']['y'], 2))
            if key in failed:
                continue
            ax, ay = a['pos']['x'] - OX, a['pos']['y'] - OY
            bx, by = b['pos']['x'] - OX, b['pos']['y'] - OY
            widths = (0.6, 0.4, 0.3) if short(net) in POWER else (0.2,)
            ok = False
            for w in widths:
                board = pcbnew.LoadBoard(str(PCB))
                try:
                    maze.route(board, maze.full_net(board, short(net)), (ax, ay), maze.LNAME[item_layer(a['description'])],
                               (bx, by), maze.LNAME[item_layer(b['description'])], w)
                except SystemExit as e:
                    print('   ', e)
                    continue
                board.Save(str(PCB))
                ok = progress = True
                break
            if not ok:
                failed.add(key)
        if not progress:
            print('no further progress')
            break
    d = drc()
    print('final: unconnected', len(d.get('unconnected_items', [])),
          {k: c for k, c in __import__('collections').Counter(v['type'] for v in d['violations']).items()})


if __name__ == '__main__':
    os.environ.setdefault('MAZE_CLR', '0.21')
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
