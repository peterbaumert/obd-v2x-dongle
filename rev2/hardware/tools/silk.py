"""Place the reference designators of a rev 2 board where they are readable (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/silk.py carrier|upper

For every footprint: tries its reference at spots around the part's courtyard (above, below, left, right, then the
corners; level and turned 90 degrees), and inside the courtyard for large parts, and takes the first spot where the
text stays clear of every pad on that side, of the board edge and of the references and silkscreen already there.
References with no free spot are hidden: the assembly data (CPL) carries the positions, the silkscreen is only an aid.
Run DRC afterwards.
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
BOARD = next((a for a in sys.argv[1:] if a in ('carrier', 'upper')), None)
if BOARD is None:
    raise SystemExit('usage: silk.py carrier|upper')
PCB = HW / BOARD / ({'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD] + '.kicad_pcb')
mm, tomm = pcbnew.FromMM, pcbnew.ToMM
GAP = 0.15          # text to pads, other text, silkscreen
EDGE = 0.5          # text to the board edge


def rect(bb, grow=0.0):
    return (tomm(bb.GetLeft()) - grow, tomm(bb.GetTop()) - grow, tomm(bb.GetRight()) + grow, tomm(bb.GetBottom()) + grow)


def hit(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def main():
    b = pcbnew.LoadBoard(str(PCB))
    edge = rect(b.GetBoardEdgesBoundingBox(), -EDGE)
    sides = {pcbnew.F_SilkS: pcbnew.F_Cu, pcbnew.B_SilkS: pcbnew.B_Cu}
    pads = {L: [] for L in sides}
    silk = {L: [] for L in sides}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for S, C in sides.items():
                if p.IsOnLayer(C):
                    pads[S].append(rect(p.GetBoundingBox(), GAP))
        for g in fp.GraphicalItems():
            if g.GetLayer() in sides and not isinstance(g, pcbnew.PCB_TEXT):
                silk[g.GetLayer()].append(rect(g.GetBoundingBox(), GAP))
    for d in b.GetDrawings():
        if d.GetLayer() in sides:
            silk[d.GetLayer()].append(rect(d.GetBoundingBox(), GAP))
    placed = {L: [] for L in sides}
    fps = sorted(b.GetFootprints(), key=lambda f: -rect(f.GetBoundingBox())[2] + rect(f.GetBoundingBox())[0])
    moved = hidden = 0
    for fp in fps:
        ref = fp.Reference()
        S = ref.GetLayer()
        if S not in sides or not ref.IsVisible():
            continue
        crt = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        cy = rect(crt.BBox()) if crt.OutlineCount() else rect(fp.GetBoundingBox(False))
        cx, cyy = (cy[0] + cy[2]) / 2, (cy[1] + cy[3]) / 2
        best = None
        for ang in (0, 90):
            ref.SetTextAngle(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
            ref.SetPosition(pcbnew.VECTOR2I(mm(cx), mm(cyy)))
            t = rect(ref.GetBoundingBox())
            hw, hh = (t[2] - t[0]) / 2, (t[3] - t[1]) / 2
            d = 0.25
            spots = [(cx, cy[1] - hh - d), (cx, cy[3] + hh + d), (cy[0] - hw - d, cyy), (cy[2] + hw + d, cyy),
                     (cy[0] - hw - d, cy[1] - hh - d), (cy[2] + hw + d, cy[1] - hh - d),
                     (cy[0] - hw - d, cy[3] + hh + d), (cy[2] + hw + d, cy[3] + hh + d)]
            if (cy[2] - cy[0]) > 2.5 * hw and (cy[3] - cy[1]) > 2.5 * hh:
                spots.insert(0, (cx, cyy))
            for x, y in spots:
                r = (x - hw, y - hh, x + hw, y + hh)
                if r[0] < edge[0] or r[1] < edge[1] or r[2] > edge[2] or r[3] > edge[3]:
                    continue
                if any(hit(r, o) for o in pads[S]) or any(hit(r, o) for o in silk[S]) or \
                        any(hit(r, o) for o in placed[S]):
                    continue
                best = (ang, x, y, r)
                break
            if best:
                break
        if best:
            ang, x, y, r = best
            ref.SetTextAngle(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
            ref.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            placed[S].append((r[0] - GAP, r[1] - GAP, r[2] + GAP, r[3] + GAP))
            moved += 1
        else:
            ref.SetVisible(False)
            hidden += 1
    b.Save(str(PCB))
    print(f'{BOARD}: {moved} references placed, {hidden} hidden (no free spot)')


if __name__ == '__main__':
    main()
