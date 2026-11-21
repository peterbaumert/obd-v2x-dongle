"""Move one two-pad part next to the pin it belongs to on a routed rev 2 board and reconnect it (KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/movepart.py carrier|upper REF ANCHORREF.PAD [radius_mm]

Example: movepart.py carrier R507 U502.10   -- when the router cannot reach REF's net from where REF sits.
Looks for the spot nearest the anchor pad, on the anchor's side, where REF's courtyard overlaps no other courtyard
and its pads clear all copper of other nets on that layer; moves REF there (both rotations tried), removes the old
copper of the net REF shares with the anchor pad, and routes anchor pad -> REF with maze.py. REF's other pad is
left to finish.py. Run finish.py and DRC afterwards.
"""
import os
import sys
from pathlib import Path

args = [a for a in sys.argv[1:]]
if len(args) < 3 or args[0] not in ('carrier', 'upper'):
    raise SystemExit('usage: movepart.py carrier|upper REF ANCHORREF.PAD [radius_mm]')
BOARD, REF, ANCHOR = args[0], args[1], args[2]
RADIUS = float(args[3]) if len(args) > 3 else 5.0
os.environ['REV2_BOARD'] = BOARD
sys.path.insert(0, str(Path(__file__).parent))
import pcbnew  # noqa: E402
import maze  # noqa: E402

PCB = maze.PCB.name
OX, OY = maze.OX, maze.OY
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
CLR = 0.2


def rect(bb, grow=0.0):
    return (tomm(bb.GetLeft()) - grow, tomm(bb.GetTop()) - grow, tomm(bb.GetRight()) + grow, tomm(bb.GetBottom()) + grow)


def hit(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def seg_rect(a, c, w, r):
    """does a track segment (with half width w) come into rectangle r? sampled"""
    n = max(2, int((((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5) / 0.05))
    for i in range(n + 1):
        x, y = a[0] + (c[0] - a[0]) * i / n, a[1] + (c[1] - a[1]) * i / n
        if r[0] - w < x < r[2] + w and r[1] - w < y < r[3] + w:
            return True
    return False


def main():
    b = pcbnew.LoadBoard(PCB)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    part = fps[REF]
    aref, apad = ANCHOR.split('.')
    anchor = next(p for p in fps[aref].Pads() if p.GetNumber() == apad)
    net = anchor.GetNetname()
    flipped = fps[aref].IsFlipped()
    layer = pcbnew.B_Cu if flipped else pcbnew.F_Cu
    crt = pcbnew.B_CrtYd if flipped else pcbnew.F_CrtYd
    if part.IsFlipped() != flipped:
        part.Flip(part.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    ax, ay = tomm(anchor.GetPosition().x), tomm(anchor.GetPosition().y)
    others = [rect(f.GetCourtyard(crt).BBox()) for r_, f in fps.items()
              if r_ != REF and f.IsFlipped() == flipped and f.GetCourtyard(crt).OutlineCount()]
    holes = [rect(p.GetBoundingBox(), 0.3) for f in fps.values() for p in f.Pads()
             if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)]
    segs, vias = [], []
    for t in b.GetTracks():
        if t.GetNetname() == net:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            vias.append((tomm(p.x), tomm(p.y), tomm(t.GetWidth(pcbnew.F_Cu)) / 2, t.GetNetname()))
        elif t.GetLayer() == layer:
            segs.append(((tomm(t.GetStart().x), tomm(t.GetStart().y)), (tomm(t.GetEnd().x), tomm(t.GetEnd().y)),
                         tomm(t.GetWidth()) / 2, t.GetNetname()))
    edge = b.GetBoardEdgesBoundingBox()
    lim = rect(edge, -0.6)
    cands = []
    steps = int(RADIUS / 0.25)
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            x, y = ax + i * 0.25, ay + j * 0.25
            d = ((x - ax) ** 2 + (y - ay) ** 2) ** 0.5
            if d <= RADIUS:
                cands.append((d, x, y))
    cands.sort()
    for d, x, y in cands:
        for rot in (0, 90, 180, 270):
            part.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            part.SetOrientationDegrees(rot)
            cy = rect(part.GetCourtyard(crt).BBox())
            if cy[0] < lim[0] or cy[1] < lim[1] or cy[2] > lim[2] or cy[3] > lim[3]:
                continue
            if any(hit(cy, o) for o in others) or any(hit(cy, h) for h in holes):
                continue
            ok = True
            for p in part.Pads():
                pr = rect(p.GetBoundingBox(), CLR)
                pnet = p.GetNetname()
                if any(n != pnet and seg_rect(a, c, w, pr) for a, c, w, n in segs) or \
                        any(n != pnet and pr[0] - vr < vx < pr[2] + vr and pr[1] - vr < vy < pr[3] + vr for vx, vy, vr, n in vias):
                    ok = False
                    break
            if not ok:
                continue
            mine = next(p for p in part.Pads() if p.GetNetname() == net)
            mx, my = tomm(mine.GetPosition().x), tomm(mine.GetPosition().y)
            if ((mx - ax) ** 2 + (my - ay) ** 2) ** 0.5 > d + 0.2:
                continue                                    # the pad on the shared net should face the anchor
            for t in list(b.GetTracks()):
                if t.GetNetname() == net:
                    b.Delete(t)
            b.Save(PCB)
            lname = 'B' if flipped else 'F'
            for clr in (0.21, 0.16):
                for w in (0.2, 0.15):
                    maze.CLR = clr
                    board = pcbnew.LoadBoard(PCB)
                    try:
                        maze.route(board, net, (ax - OX, ay - OY), maze.LNAME[lname], (mx - OX, my - OY), maze.LNAME[lname], w)
                    except SystemExit:
                        continue
                    board.Save(PCB)
                    print(f'{REF} moved to {x - OX:.2f}, {y - OY:.2f} rot {rot}, {d:.1f} mm from {ANCHOR}; '
                          f'{net.split("/")[-1]} routed {w} mm wide')
                    return 0
            print(f'  spot {x - OX:.2f}, {y - OY:.2f} rot {rot}: free, but the anchor pad cannot be reached')
            b = pcbnew.LoadBoard(PCB)                        # try the next spot on a fresh copy
            fps = {f.GetReference(): f for f in b.GetFootprints()}
            part = fps[REF]
    print(f'{REF}: no usable spot within {RADIUS} mm of {ANCHOR}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
