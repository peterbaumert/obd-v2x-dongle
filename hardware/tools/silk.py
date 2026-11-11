"""Place reference designators on the silkscreen so they don't overlap pads, other silk or the edge.

    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" hardware/tools/silk.py

For each footprint, tries positions above / below / left / right of its courtyard (left/right also
rotated 90 deg). If none fits, the silkscreen reference is hidden (the F.Fab/B.Fab reference stays,
so the assembly drawing still has it). Safe to re-run.
"""
import os
import subprocess
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
PCB = HW / 'obd-v2x-dongle.kicad_pcb'
KICAD = Path(os.environ['LOCALAPPDATA']) / 'Programs/KiCad/10.0'
CLR = pcbnew.FromMM(0.15)      # silk-to-pad / silk-to-silk clearance
EDGE = pcbnew.FromMM(0.3)


def grow(bb, d):
    b = pcbnew.BOX2I(bb.GetOrigin(), bb.GetSize())
    b.Inflate(d)
    return b


def main():
    board = pcbnew.LoadBoard(str(PCB))
    outline = board.GetBoardEdgesBoundingBox()
    inner = grow(outline, -EDGE)
    obst = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    cu = {pcbnew.F_SilkS: pcbnew.F_Cu, pcbnew.B_SilkS: pcbnew.B_Cu}
    fps = list(board.GetFootprints())
    # obstacles: exposed pads on the matching side, footprint silk graphics
    for fp in fps:
        for p in fp.Pads():
            for silk, layer in cu.items():
                if p.IsOnLayer(layer):
                    obst[silk].append(grow(p.GetBoundingBox(), CLR))
        for g in fp.GraphicalItems():
            if g.GetLayer() in obst and g.GetClass() != 'PCB_TEXT':
                obst[g.GetLayer()].append(g.GetBoundingBox())
    for g in board.GetDrawings():
        if g.GetLayer() in obst:
            obst[g.GetLayer()].append(g.GetBoundingBox())

    placed = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    hidden = []
    # big parts first: they have the most room around them
    def area(fp):
        bb = fp.GetBoundingBox(False)
        return bb.GetWidth() * bb.GetHeight()

    for fp in sorted(fps, key=area, reverse=True):
        ref = fp.Reference()
        silk = pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS
        ref.SetLayer(silk)
        ref.SetVisible(True)
        crt = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        cb = crt.BBox() if crt.OutlineCount() else fp.GetBoundingBox(False)
        cx, cy = cb.GetCenter().x, cb.GetCenter().y
        th = ref.GetTextHeight()
        gap = pcbnew.FromMM(0.25)
        cands = [
            (cx, cb.GetTop() - gap - th // 2, 0), (cx, cb.GetBottom() + gap + th // 2, 0),
            (cb.GetLeft() - gap - th // 2, cy, 90), (cb.GetRight() + gap + th // 2, cy, 90),
            (cb.GetLeft() - gap, cy, 0), (cb.GetRight() + gap, cy, 0),
        ]
        ok = False
        for x, y, rot in cands:
            ref.SetTextAngleDegrees(rot)
            ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            if rot == 0 and (x == cb.GetLeft() - gap):
                ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if not fp.IsFlipped() else pcbnew.GR_TEXT_H_ALIGN_LEFT)
            if rot == 0 and (x == cb.GetRight() + gap):
                ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if not fp.IsFlipped() else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
            ref.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
            tb = ref.GetBoundingBox()
            if not inner.Contains(tb):
                continue
            if any(tb.Intersects(o) for o in obst[silk]) or any(tb.Intersects(o) for o in placed[silk]):
                continue
            placed[silk].append(grow(tb, CLR))
            ok = True
            break
        if not ok:
            ref.SetVisible(False)
            hidden.append(fp.GetReference())
    board.Save(str(PCB))
    print(f'{len(fps) - len(hidden)} references placed, {len(hidden)} hidden: {" ".join(sorted(hidden))}')


if __name__ == '__main__':
    main()
