"""Local rip-up for connections that finish.py cannot make (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/localfix.py carrier|upper [rounds] [radius_mm]

For every open connection whose endpoint is boxed in: delete the track segments and vias of OTHER nets within
`radius` of that endpoint (GND and RF nets stay), route the boxed-in connection first, then let finish.py reconnect
what was cut. Repeats while the number of open connections goes down. What a person does by hand with
push-and-shove, done bluntly: review the result in KiCad and run DRC.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BOARD = next((a for a in sys.argv[1:] if a in ('carrier', 'upper')), None)
if BOARD is None:
    raise SystemExit('usage: localfix.py carrier|upper [rounds] [radius_mm]')
nums = [a for a in sys.argv[1:] if a.replace('.', '', 1).isdigit()]
ROUNDS = int(nums[0]) if nums else 3
RADIUS = float(nums[1]) if len(nums) > 1 else 1.2
os.environ['REV2_BOARD'] = BOARD
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pcbnew  # noqa: E402
import maze  # noqa: E402
from kicad_env import CLI  # noqa: E402

PCB = maze.PCB
OX, OY = maze.OX, maze.OY
STAY = ('GND', 'LTE_ANT', 'Net-(J402-In)', 'Net-(J403-In)', 'Net-(J801-In)', 'Net-(AE801-A)', 'Net-(U801-')


def drc():
    out = Path(tempfile.gettempdir()) / f'obd-v2x-rev2-{BOARD}-localfix.json'
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-error', '--format', 'json',
                    '-o', str(out), PCB.name], capture_output=True)
    return json.loads(out.read_text(encoding='utf-8'))


def opens(d):
    return [v for v in d.get('unconnected_items', []) if not all('Zone' in i['description'] for i in v['items'])]


def layer(desc):
    for name in ('In2', 'B', 'F'):
        if f'on {name}.Cu' in desc and name in maze.LNAME:
            return name
    return 'B' if 'B' in maze.LNAME else 'F'


def dist_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def P(p):
    return (pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY)


def rip(point, own):
    b = pcbnew.LoadBoard(PCB.name)
    k = 0
    for t in list(b.GetTracks()):
        n = t.GetNetname()
        if n == own or any(s in n for s in STAY):
            continue
        d = dist_seg(point, P(t.GetPosition()), P(t.GetPosition())) if isinstance(t, pcbnew.PCB_VIA) \
            else dist_seg(point, P(t.GetStart()), P(t.GetEnd()))
        if d <= RADIUS:
            b.Delete(t)
            k += 1
    b.Save(PCB.name)
    return k


def route(net, pa, la, pb, lb):
    for clr in ((0.26, 0.21) if net.endswith('GND') else (0.21, 0.16)):
        for w in (0.2, 0.15):
            maze.CLR = clr
            board = pcbnew.LoadBoard(PCB.name)
            try:
                maze.route(board, maze.full_net(board, net.split('/')[-1]), pa, maze.LNAME[la], pb, maze.LNAME[lb], w)
            except SystemExit:
                continue
            board.Save(PCB.name)
            return True
    return False


def main():
    best = None
    for rnd in range(ROUNDS):
        todo = opens(drc())
        print(f'round {rnd}: {len(todo)} open connections')
        if not todo or (best is not None and len(todo) >= best):
            break
        best = len(todo)
        for v in todo:
            a, b = v['items'][0], v['items'][1]
            if 'Zone' in a['description']:
                a, b = b, a
            if 'Zone' in b['description']:
                continue                                   # a pad against a pour: finish.py handles those
            net = a['description'].split('[')[1].split(']')[0]
            pa, pb = (a['pos']['x'] - OX, a['pos']['y'] - OY), (b['pos']['x'] - OX, b['pos']['y'] - OY)
            la, lb = layer(a['description']), layer(b['description'])
            n = rip(pa, net) + rip(pb, net)
            ok = route(net, pa, la, pb, lb)
            print(f'   {net.split("/")[-1]}: cut {n} neighbouring items, {"routed" if ok else "still open"}')
        # reconnect what was cut
        r = subprocess.run([sys.executable, str(HERE / 'finish.py'), BOARD, '3'], capture_output=True, text=True)
        print('   ' + (r.stdout.strip().splitlines() or ['(no output)'])[-1][:160])
    d = drc()
    print(f'after localfix: {len(opens(d))} open connections, {len(d.get("unconnected_items", []))} unconnected in all, '
          f'{sum(1 for v in d["violations"] if v["type"] != "starved_thermal")} rule errors')


if __name__ == '__main__':
    main()
