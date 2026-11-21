"""Widen supply (and necked-down RF) tracks where there is room (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/widen.py carrier|upper

For every track segment of a supply net, tries the widths in WIDTHS (largest first, never below its current width)
and keeps the first one at which the segment still clears all copper of other nets on its layer (tracks, vias and
pads, with the larger of the two nets' clearances plus a margin) and the board edge. Pours follow on refill. Run DRC
afterwards: anything it reports is put back by running with --undo-errors REPORT.
"""
import math
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
BOARD = next((a for a in sys.argv[1:] if a in ('carrier', 'upper')), None)
if BOARD is None:
    raise SystemExit('usage: widen.py carrier|upper')
PCB = HW / BOARD / ({'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD] + '.kicad_pcb')
SUPPLY = {'OBD_VBAT': 1.0, 'VBAT_F': 1.0, 'VIN_PROT': 0.8, 'VBAT_LTE': 1.0, 'VBUCK_3V8': 0.8, 'VSYS_3V8': 0.8,
          'VCELL': 0.6, '+3V3': 0.5, 'Net-(D103-K)': 1.0, 'SIM_VDD': 0.3, 'LTE_1V8': 0.3,
          # RF lines back to their 0.32 mm where the router necked them down
          'LTE_ANT_MAIN': 0.32, 'Net-(J402-In)': 0.32, 'LTE_ANT_GNSS': 0.32, 'LTE_ANT_GNSS_UFL': 0.32,
          'Net-(J403-In)': 0.32, 'Net-(AE801-A)': 0.32, 'Net-(J801-In)': 0.32, 'Net-(U801-RF_OUT)': 0.32}
STEPS = (1.0, 0.8, 0.6, 0.5, 0.4, 0.32, 0.3)
CLR = {'Power': 0.2, 'Switch': 0.2, 'RF': 0.25 if BOARD == 'carrier' else 0.2}   # wider classes; else 0.15
MARGIN = 0.03
mm, tomm = pcbnew.FromMM, pcbnew.ToMM


def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def seg_seg(a, b, c, d):
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) > 0) != (cross(a, b, d) > 0) and (cross(c, d, a) > 0) != (cross(c, d, b) > 0):
        return 0.0
    return min(seg_dist(a, c, d), seg_dist(b, c, d), seg_dist(c, a, b), seg_dist(d, a, b))


def rect_seg(r, a, b):
    """distance from segment ab to rectangle r (0 if it enters it)"""
    x0, y0, x1, y1 = r
    if any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (a, b)):
        return 0.0
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(seg_seg(a, b, e0, e1) for e0, e1 in edges)


def main():
    b = pcbnew.LoadBoard(str(PCB))
    ds = b.GetDesignSettings()

    def short(n):
        return n.split('/')[-1]

    def clr(net):
        nc = b.FindNet(net).GetNetClassName() if b.FindNet(net) else 'Default'
        return CLR.get(str(nc).split(',')[0], 0.15)

    xy = lambda p: (tomm(p.x), tomm(p.y))                                    # noqa: E731
    tracks = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
    vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
    pads = [p for f in b.GetFootprints() for p in f.Pads()]
    edge = b.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = (tomm(edge.GetLeft()) + 0.4, tomm(edge.GetTop()) + 0.4, tomm(edge.GetRight()) - 0.4,
                          tomm(edge.GetBottom()) - 0.4)
    changed = 0
    for t in tracks:
        n = short(t.GetNetname())
        if n not in SUPPLY:
            continue
        L, net = t.GetLayer(), t.GetNetname()
        a, c = xy(t.GetStart()), xy(t.GetEnd())
        cur = tomm(t.GetWidth())
        mine = clr(net)
        others = []
        for o in tracks:
            if o.GetLayer() == L and o.GetNetname() != net:
                others.append(('seg', xy(o.GetStart()), xy(o.GetEnd()), tomm(o.GetWidth()) / 2, max(mine, clr(o.GetNetname()))))
        for v in vias:
            if v.GetNetname() != net:
                others.append(('pt', xy(v.GetPosition()), None, tomm(v.GetWidth(L)) / 2, max(mine, clr(v.GetNetname()))))
        for p in pads:
            if p.IsOnLayer(L) and p.GetNetname() != net:
                bb = p.GetBoundingBox()
                others.append(('rect', (tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom())),
                               None, 0.0, max(mine, clr(p.GetNetname()))))
        best = cur
        for w in STEPS:
            if w > SUPPLY[n] or w <= cur + 1e-6:
                continue
            h = w / 2
            if min(a[0], c[0]) - h < ex0 or max(a[0], c[0]) + h > ex1 or min(a[1], c[1]) - h < ey0 or max(a[1], c[1]) + h > ey1:
                continue
            ok = True
            for kind, p, q, r, cl in others:
                need = h + r + cl + MARGIN
                if kind == 'seg':
                    d = seg_seg(a, c, p, q)
                elif kind == 'pt':
                    d = seg_dist(p, a, c)
                else:
                    d = rect_seg(p, a, c) + 0.0
                    need = h + cl + MARGIN
                if d < need:
                    ok = False
                    break
            if ok:
                best = w
                break
        if best > cur + 1e-6:
            t.SetWidth(mm(best))
            changed += 1
    b.Save(str(PCB))
    print(f'{BOARD}: {changed} supply segments widened')


if __name__ == '__main__':
    main()
