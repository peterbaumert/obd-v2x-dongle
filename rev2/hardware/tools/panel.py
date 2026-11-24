"""Assembly panel: one carrier and one upper board in a 5 mm frame, tab-routed with mouse bites (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/panel.py

Writes rev2/hardware/panel/obd-v2x-panel.kicad_pcb (+ .kicad_pro copied from the carrier for the design rules).
The two boards are copied unchanged (the upper board's nets get the prefix "U."), the boards' outlines are replaced by
the panel outline: frame and boards joined by tabs, everything else milled away (2 mm gaps). Tabs sit only where no pad
or courtyard on either side comes within 1.5 mm of the edge; their mouse bites lie just outside the board edge, so
the stubs left after breaking stay outside the board and are filed flush. Three fiducials per side and four tooling
holes on the frame. The carrier keeps its own coordinates; the upper board sits to its right.
Not a source file: regenerate it after any change to either board, then run fab.py panel.
"""
import shutil
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
OUT = HW / 'panel'
NAME = 'obd-v2x-panel'
mm, tomm = pcbnew.FromMM, pcbnew.ToMM

BX0, BY0, BS = 100.0, 50.0, 45.0     # both boards: outline (100, 50)..(145, 95) in their own files
GAP, FRAME = 2.0, 5.0                 # milled gap around the boards, frame width
DX = BS + GAP                         # upper board offset (x) in the panel
BITE_D, BITE_PITCH, BITE_OUT = 0.5, 0.75, 0.25   # mouse bites: hole, pitch, centre this far outside the board edge

# tabs: (board, edge, position along the edge in board mm (from the left / from the front), width)
# free stretches (no pad / courtyard within 1.5 mm): carrier top 8-37, bottom 0-10.3, left 30.4-34.9, right none;
# upper top 31.8-37, bottom 18-32.6, left 8.5-28.1, right 8.5-28.7
TABS = [('carrier', 'top', 13.0, 4.0), ('carrier', 'top', 32.0, 4.0), ('carrier', 'bottom', 5.0, 4.0),
        ('carrier', 'left', 32.6, 3.0),
        ('upper', 'top', 34.4, 3.0), ('upper', 'bottom', 21.5, 4.0), ('upper', 'bottom', 29.0, 4.0),
        ('upper', 'right', 12.0, 4.0), ('upper', 'right', 25.0, 4.0)]

PX0, PY0 = BX0 - GAP - FRAME, BY0 - GAP - FRAME                 # panel outline
PX1, PY1 = BX0 + DX + BS + GAP + FRAME, BY0 + BS + GAP + FRAME


def dup(item):
    """copy of a board item (footprints take an argument, tracks do not)"""
    try:
        return item.Duplicate(False).Cast()
    except TypeError:
        return item.Duplicate().Cast()


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def rect_poly(x0, y0, x1, y1):
    p = pcbnew.SHAPE_POLY_SET()
    p.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        p.Append(mm(x), mm(y))
    return p


def board_origin(board):
    return (BX0 + (DX if board == 'upper' else 0.0), BY0)


def tab_geometry(board, edge, pos, w):
    """tab rectangle across the gap, and the mouse-bite centres (just outside the board edge)"""
    ox, oy = board_origin(board)
    n = int(w / BITE_PITCH)
    offs = [(i - (n - 1) / 2) * BITE_PITCH for i in range(n)]
    if edge in ('top', 'bottom'):
        x = ox + pos
        if edge == 'top':
            r, by = (x - w / 2, oy - GAP - 0.01, x + w / 2, oy + 0.01), oy - BITE_OUT
        else:
            r, by = (x - w / 2, oy + BS - 0.01, x + w / 2, oy + BS + GAP + 0.01), oy + BS + BITE_OUT
        return r, [(x + o, by) for o in offs]
    y = oy + pos
    if edge == 'left':
        r, bx = (ox - GAP - 0.01, y - w / 2, ox + 0.01, y + w / 2), ox - BITE_OUT
    else:
        r, bx = (ox + BS - 0.01, y - w / 2, ox + BS + GAP + 0.01, y + w / 2), ox + BS + BITE_OUT
    return r, [(bx, y + o) for o in offs]


def add_seg(b, a, c):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(a)
    s.SetEnd(c)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(mm(0.1))
    b.Add(s)


def add_chain(b, chain):
    n = chain.PointCount()
    for i in range(n):
        add_seg(b, chain.CPoint(i), chain.CPoint((i + 1) % n))


def hole_fp(b, ref, x, y, d):
    fp = pcbnew.FOOTPRINT(b)
    fp.SetReference(ref)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    p = pcbnew.PAD(fp)
    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(V(d, d))
    p.SetDrillSize(V(d, d))
    ls = pcbnew.LSET.AllCuMask()
    ls.AddLayer(pcbnew.F_Mask)
    ls.AddLayer(pcbnew.B_Mask)
    p.SetLayerSet(ls)
    fp.Add(p)
    fp.SetPosition(V(x, y))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
    b.Add(fp)


def fiducial(b, ref, x, y, bottom):
    fp = pcbnew.FOOTPRINT(b)
    fp.SetReference(ref)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    p = pcbnew.PAD(fp)
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(V(1.0, 1.0))
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.F_Mask)
    p.SetLayerSet(ls)
    p.SetLocalSolderMaskMargin(mm(0.5))
    fp.Add(p)
    fp.SetPosition(V(x, y))
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)
    b.Add(fp)
    if bottom:
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def main():
    b = pcbnew.LoadBoard(str(HW / 'carrier' / 'obd-v2x-carrier.kicad_pcb'))
    u = pcbnew.LoadBoard(str(HW / 'upper' / 'obd-v2x-upper.kicad_pcb'))
    off = V(DX, 0)

    # the upper board's nets, renamed so its GND etc. stay separate from the carrier's
    nets = {}
    for name, ni in u.GetNetsByName().items():
        name = str(name)
        if not name:
            continue
        nn = pcbnew.NETINFO_ITEM(b, 'U.' + name)
        b.Add(nn)
        nets[name] = nn

    def net(item):
        return nets.get(item.GetNetname())

    for f in list(u.GetFootprints()):
        nf = dup(f)
        b.Add(nf)
        nf.Move(off)
        for po, p in zip(f.Pads(), nf.Pads()):          # net from the original pad: Add() remaps by net code
            n = nets.get(po.GetNetname())
            p.SetNet(n if n else b.FindNet(''))
    for t in list(u.GetTracks()):
        nt = dup(t)
        b.Add(nt)
        nt.Move(off)
        if net(t):
            nt.SetNet(net(t))
    for z in list(u.Zones()):
        nz = dup(z)
        b.Add(nz)
        nz.Move(off)
        if not z.GetIsRuleArea() and net(z):
            nz.SetNet(net(z))
    for d in list(u.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            continue
        nd = dup(d)
        b.Add(nd)
        nd.Move(off)
    # carrier outline goes; the panel outline replaces both boards' outlines
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            b.Remove(d)

    keep = pcbnew.SHAPE_POLY_SET()
    for brd in ('carrier', 'upper'):
        ox, oy = board_origin(brd)
        keep.BooleanAdd(rect_poly(ox, oy, ox + BS, oy + BS))
    bites = []
    for brd, edge, pos, w in TABS:
        r, bb = tab_geometry(brd, edge, pos, w)
        keep.BooleanAdd(rect_poly(*r))
        bites += bb
    gaps = rect_poly(PX0 + FRAME, PY0 + FRAME, PX1 - FRAME, PY1 - FRAME)
    gaps.BooleanSubtract(keep)
    outer = rect_poly(PX0, PY0, PX1, PY1)          # keep a reference: Outline() points into it
    add_chain(b, outer.Outline(0))
    for i in range(gaps.OutlineCount()):
        add_chain(b, gaps.Outline(i))
        for j in range(gaps.HoleCount(i)):
            add_chain(b, gaps.Hole(i, j))

    for k, (x, y) in enumerate(bites, 1):
        hole_fp(b, f'MB{k}', x, y, BITE_D)
    c = FRAME / 2
    for k, (x, y) in enumerate(((PX0 + c, PY0 + c), (PX1 - c, PY0 + c), (PX0 + c, PY1 - c), (PX1 - c, PY1 - c)), 1):
        hole_fp(b, f'TH{k}', x, y, 2.0)                       # tooling holes
    fids = ((PX0 + 10, PY0 + c), (PX1 - 10, PY0 + c), (PX0 + 10, PY1 - c))   # asymmetric: orientation check
    for k, (x, y) in enumerate(fids, 1):
        fiducial(b, f'FID{k}', x, y, False)
        fiducial(b, f'FID{k + 3}', x, y, True)

    txt = pcbnew.PCB_TEXT(b)
    txt.SetText('obd-v2x rev 2 panel: carrier + upper')
    txt.SetPosition(V((PX0 + PX1) / 2, PY1 - c))
    txt.SetLayer(pcbnew.F_SilkS)
    txt.SetTextSize(V(1.0, 1.0))
    txt.SetTextThickness(mm(0.15))
    b.Add(txt)

    b.GetDesignSettings().SetAuxOrigin(V(PX0, PY1))      # drill / place origin: panel bottom-left corner
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    OUT.mkdir(exist_ok=True)
    shutil.copy(HW / 'carrier' / 'obd-v2x-carrier.kicad_pro', OUT / f'{NAME}.kicad_pro')
    b.Save(str(OUT / f'{NAME}.kicad_pcb'))
    print(f'panel {PX1 - PX0:.1f} x {PY1 - PY0:.1f} mm, {len(TABS)} tabs, {len(bites)} mouse bites, '
          f'{gaps.OutlineCount()} milled gap(s) -> {OUT / (NAME + ".kicad_pcb")}')


if __name__ == '__main__':
    sys.exit(main())
