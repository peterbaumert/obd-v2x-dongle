"""Give a floating GND pad its own via (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/padvia.py carrier|upper REF.PAD [REF.PAD ...]

For a GND pad that DRC reports as cut off with its bit of pour: finds the nearest spot (0.5-4 mm away) where a
0.6 / 0.3 mm via fits, preferring spots that need no other net moved; signal nets in the way are ripped up (run
finish.py afterwards to put them back); routes pad -> spot with maze.py and adds the via. Supply and RF nets are
never ripped. Run DRC afterwards.
"""
import os
import sys

BOARD = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ('carrier', 'upper') else None
if BOARD is None:
    raise SystemExit('usage: padvia.py carrier|upper REF.PAD [REF.PAD ...]')
os.environ['REV2_BOARD'] = BOARD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew  # noqa: E402
import maze  # noqa: E402

PCB = str(maze.PCB)
OX, OY = 100.0, 50.0
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
VIA_D, VIA_DR, CLR = 0.6, 0.3, 0.25
r = VIA_D / 2
KEEP = ('VSYS_3V8', 'VBUCK_3V8', 'VBAT_LTE', 'VCELL', 'VIN_PROT', '+3V3', 'VBAT_F', 'OBD_VBAT', 'LTE_ANT', 'Net-(J402-In)',
        'Net-(J403-In)', 'Net-(D103-K)', 'Net-(J801-In)', 'Net-(AE801-A)', 'Net-(U801-', 'GNSS_VCC')


def dist_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def scan(b):
    xy = lambda p: (tomm(p.x), tomm(p.y))                                    # noqa: E731
    pads, segs, vias = [], [], []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            pads.append(((tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom())), p.GetNetname(), tht))
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            vias.append((xy(t.GetPosition()), tomm(t.GetWidth(pcbnew.F_Cu)) / 2, t.GetNetname()))
        elif t.GetNetname() != 'GND':
            segs.append((xy(t.GetStart()), xy(t.GetEnd()), tomm(t.GetWidth()) / 2, t.GetNetname()))
    return pads, segs, vias


def ok(x, y, pads, segs, vias):
    if not (OX + 0.6 <= x <= OX + 44.4 and OY + 0.6 <= y <= OY + 44.4):
        return False
    for (x0, y0, x1, y1), net, tht in pads:
        gap = 0.05 if net == 'GND' and not tht else CLR
        if x0 - r - gap < x < x1 + r + gap and y0 - r - gap < y < y1 + r + gap:
            return False
    blockers = {n for a, c, w, n in segs if dist_seg((x, y), a, c) < r + w + CLR}
    if any(k in n for n in blockers for k in KEEP):
        return False
    if not all(((x - vx) ** 2 + (y - vy) ** 2) ** 0.5 >= r + vr + (0.1 if net == 'GND' else CLR) for (vx, vy), vr, net in vias):
        return False
    return blockers                                   # signal nets that would have to move (may be empty)


for arg in sys.argv[2:]:
    ref, num = arg.split('.')
    b = pcbnew.LoadBoard(PCB)
    fp = next(f for f in b.GetFootprints() if f.GetReference() == ref)
    pad = next(p for p in fp.Pads() if p.GetNumber() == num)
    px, py = tomm(pad.GetPosition().x), tomm(pad.GetPosition().y)
    layer = 'B' if pad.IsOnLayer(pcbnew.B_Cu) else 'F'
    pads, segs, vias = scan(b)
    cands = []
    for i in range(-40, 41):
        for j in range(-40, 41):
            x, y = px + i * 0.1, py + j * 0.1
            d = (i * i + j * j) ** 0.5 * 0.1
            if 0.5 <= d <= 4.0:
                bl = ok(x, y, pads, segs, vias)
                if bl is not False:
                    cands.append((len(bl) * 3 + d, d, x, y, bl))
    cands.sort()
    done = False
    for _, d, x, y, bl in cands[:int(os.environ.get('PADVIA_N', 30)):int(os.environ.get('PADVIA_STEP', 3))]:
        for clr in (0.26, 0.21):
            maze.CLR = clr
            board = pcbnew.LoadBoard(PCB)
            for t in list(board.GetTracks()):                 # push the blocking signal nets aside: rip them up
                if t.GetNetname() in bl:
                    board.Delete(t)
            try:
                maze.route(board, 'GND', (px - OX, py - OY), maze.LNAME[layer], (x - OX, y - OY), maze.LNAME[layer], 0.2)
            except SystemExit:
                continue
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DR))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(board.FindNet('GND'))
            board.Add(v)
            board.Save(PCB)
            print(f'{arg}: via at {x - OX:.2f}, {y - OY:.2f}, {d:.1f} mm from the pad; ripped up {sorted(n.split("/")[-1] for n in bl)}')
            done = True
            break
        if done:
            break
    if not done:
        print(f'{arg}: no via spot reachable ({len(cands)} candidate spots)')
