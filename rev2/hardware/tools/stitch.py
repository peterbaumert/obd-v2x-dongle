"""Stitch the GND pours of a rev 2 board together with vias (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/stitch.py carrier|upper [pitch_mm]

After autorouting, the pours on the outer layers break into islands. This adds a GND via wherever the pours of
all copper layers overlap (on a grid, default 2.5 mm), at least 0.5 mm inside both pours, outside every pad and not
within 1.2 mm of another via. Then it refills the pours. Run DRC afterwards.
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
    raise SystemExit('usage: stitch.py carrier|upper [pitch_mm]')
PITCH = next((float(a) for a in sys.argv[1:] if a.replace('.', '', 1).isdigit()), 2.5)
PCB = HW / BOARD / ({'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD] + '.kicad_pcb')
VIA_D, VIA_DR, MARGIN, VIA_GAP, PAD_GAP = 0.6, 0.3, 0.4, 1.0, 0.3


def mm(v):
    return pcbnew.FromMM(float(v))


def main():
    os.chdir(PCB.parent)
    b = pcbnew.LoadBoard(PCB.name)
    gnd = b.FindNet('GND')
    # every copper layer that has a GND pour: a via must sit inside the pour on all of them, or it would hit
    # other copper on an inner layer
    layers = [L for L in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if b.IsLayerEnabled(L)]
    zones = {L: [z for z in b.Zones() if z.GetNetname() == 'GND' and z.IsOnLayer(L)] for L in layers}
    if any(not z for z in zones.values()):
        raise SystemExit('a copper layer has no GND pour: stitching would not see its tracks')

    def filled(L, x, y):
        p = pcbnew.VECTOR2I(mm(x), mm(y))
        return any(z.HitTestFilledArea(L, p, 0) for z in zones[L])

    def in_pour(x, y):
        pts = [(x, y), (x + MARGIN, y), (x - MARGIN, y), (x, y + MARGIN), (x, y - MARGIN)]
        return all(filled(L, px, py) for L in zones for px, py in pts)

    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            pads.append((pcbnew.ToMM(bb.GetLeft()) - PAD_GAP - VIA_D / 2, pcbnew.ToMM(bb.GetTop()) - PAD_GAP - VIA_D / 2,
                         pcbnew.ToMM(bb.GetRight()) + PAD_GAP + VIA_D / 2, pcbnew.ToMM(bb.GetBottom()) + PAD_GAP + VIA_D / 2))
    vias = [(pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)) for t in b.GetTracks()
            if isinstance(t, pcbnew.PCB_VIA)]
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
    n = 0
    y = y0 + 1.0
    while y < y1 - 0.9:
        x = x0 + 1.0
        while x < x1 - 0.9:
            if (not any(a <= x <= c and bb_ <= y <= d for a, bb_, c, d in pads)
                    and all((x - vx) ** 2 + (y - vy) ** 2 >= VIA_GAP ** 2 for vx, vy in vias) and in_pour(x, y)):
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
                v.SetWidth(mm(VIA_D))
                v.SetDrill(mm(VIA_DR))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(gnd)
                b.Add(v)
                vias.append((x, y))
                n += 1
            x += PITCH
        y += PITCH
    b.Save(PCB.name)
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board',
                    '-o', str(Path(tempfile.gettempdir()) / f'obd-v2x-rev2-{BOARD}-stitch.drc'), PCB.name], capture_output=True)
    print(f'{BOARD}: {n} GND stitching vias added')


if __name__ == '__main__':
    main()
