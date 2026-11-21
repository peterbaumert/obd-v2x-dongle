"""Give every isolated GND pour island its own via (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/islands.py carrier|upper

After routing, a GND pad can end up in a fragment of the pour that has no via or through-hole pad: pad and
fragment float together, and DRC reports it as an unconnected pour. For each such fragment this looks for a point
inside it where a 0.6 / 0.3 mm via clears every other net's copper on all layers and sits in no pad, and adds a GND
via there. stitch.py only works where the pours of all layers overlap; this one checks the actual copper instead.
Refills the pours afterwards. Run DRC.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
from kicad_env import CLI  # noqa: E402

HW = Path(__file__).resolve().parents[1]
BOARD = next((a for a in sys.argv[1:] if a in ('carrier', 'upper')), None)
if BOARD is None:
    raise SystemExit('usage: islands.py carrier|upper')
PCB = HW / BOARD / ({'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD] + '.kicad_pcb')
VIA_D, VIA_DR, CLR, STEP = 0.6, 0.3, 0.25, 0.05
mm, tomm = pcbnew.FromMM, pcbnew.ToMM


def dist_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def main():
    os.chdir(PCB.parent)
    b = pcbnew.LoadBoard(PCB.name)
    gnd = b.FindNet('GND')
    xy = lambda p: (tomm(p.x), tomm(p.y))                                    # noqa: E731
    thru = [t.GetPosition() for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == 'GND']
    pads = []                                                                # (bbox, net, through-hole)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            pads.append(((tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom())),
                         p.GetNetname(), tht))
            if tht and p.GetNetname() == 'GND':
                thru.append(p.GetPosition())
    segs, vias = [], []                                                      # other nets' copper, any layer
    for t in b.GetTracks():
        if t.GetNetname() == 'GND':
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            vias.append((xy(t.GetPosition()), tomm(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            segs.append((xy(t.GetStart()), xy(t.GetEnd()), tomm(t.GetWidth()) / 2))
    edge = b.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = (tomm(v) for v in (edge.GetLeft(), edge.GetTop(), edge.GetRight(), edge.GetBottom()))
    r = VIA_D / 2

    def ok(x, y):
        if not (ex0 + 0.3 + r <= x <= ex1 - 0.3 - r and ey0 + 0.3 + r <= y <= ey1 - 0.3 - r):
            return False
        for (x0, y0, x1, y1), net, tht in pads:                              # in no pad; clear of other nets' pads
            gap = 0.05 if net == 'GND' and not tht else CLR
            if x0 - r - gap < x < x1 + r + gap and y0 - r - gap < y < y1 + r + gap:
                return False
        if any(dist_seg((x, y), a, c) < r + w + CLR for a, c, w in segs):
            return False
        return all(((x - vx) ** 2 + (y - vy) ** 2) ** 0.5 >= r + vr + CLR for (vx, vy), vr in vias)

    added = 0
    for z in b.Zones():
        if z.GetNetname() != 'GND':
            continue
        for L in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(L):
                continue
            ps = z.GetFilledPolysList(L)
            for i in range(ps.OutlineCount()):
                ol = ps.Outline(i)
                if any(ol.PointInside(q) for q in thru):
                    continue
                bb = ol.BBox()
                x0, y0, x1, y1 = (tomm(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
                best = None
                y = y0
                while y <= y1 and best is None:
                    x = x0
                    while x <= x1:
                        if ol.PointInside(pcbnew.VECTOR2I(mm(x), mm(y))) and ok(x, y):
                            best = (x, y)
                            break
                        x += STEP
                    y += STEP
                where = f'{b.GetLayerName(L)} island at {x0 - 100:.1f}..{x1 - 100:.1f}, {y0 - 50:.1f}..{y1 - 50:.1f}'
                if best is None:
                    print('  no room for a via:', where)
                    continue
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(mm(best[0]), mm(best[1])))
                v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DR)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
                b.Add(v)
                thru.append(v.GetPosition())
                added += 1
                print(f'  via at {best[0] - 100:.2f}, {best[1] - 50:.2f}:', where)
    b.Save(PCB.name)
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board',
                    '-o', str(Path(tempfile.gettempdir()) / f'obd-v2x-rev2-{BOARD}-islands.drc'), PCB.name], capture_output=True)
    print(f'{BOARD}: {added} island vias added')


if __name__ == '__main__':
    main()
