"""Replace placed footprints on a routed rev 2 board with the current library version (KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/swapfp.py carrier|upper REF [REF ...]

After changing a footprint in rev2/hardware/lib/gen_footprints.py: keeps each part's position, rotation, side,
fields and pad nets (by pad number); tracks stay. Run DRC afterwards: copper that no longer fits the new pads shows
up there.
"""
import sys
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
args = sys.argv[1:]
if len(args) < 2 or args[0] not in ('carrier', 'upper'):
    raise SystemExit('usage: swapfp.py carrier|upper REF [REF ...]')
BOARD, REFS = args[0], args[1:]
PCB = HW / BOARD / ({'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD] + '.kicad_pcb')
LIB = HW / 'lib' / 'obd-v2x.pretty'


def main():
    b = pcbnew.LoadBoard(str(PCB))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    for ref in REFS:
        old = fps[ref]
        name = old.GetFPID().GetLibItemName().wx_str()
        new = pcbnew.FootprintLoad(str(LIB), name)
        if new is None:
            raise SystemExit(f'{ref}: {name} not in {LIB}')
        new.SetFPID(old.GetFPID())
        new.SetParent(b)
        b.Add(new)
        if old.IsFlipped():
            new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        new.SetOrientation(old.GetOrientation())
        new.SetPosition(old.GetPosition())
        new.SetReference(ref)
        new.SetValue(old.GetValue())
        for fld in old.GetFields():
            if not fld.IsReference() and not fld.IsValue():
                nf = new.GetField(fld.GetName())
                if nf is not None:
                    nf.SetText(fld.GetText())
                else:
                    new.SetField(fld.GetName(), fld.GetText())
        new.Reference().SetPosition(old.Reference().GetPosition())
        new.Value().SetPosition(old.Value().GetPosition())
        for nt, ot in ((new.Reference(), old.Reference()), (new.Value(), old.Value())):
            nt.SetLayer(ot.GetLayer())
            nt.SetMirrored(ot.IsMirrored())
            nt.SetTextAngle(ot.GetTextAngle())
            nt.SetVisible(ot.IsVisible())
        new.SetPath(old.GetPath())
        new.SetSheetname(old.GetSheetname())
        new.SetSheetfile(old.GetSheetfile())
        new.SetAttributes(old.GetAttributes())
        nets = {p.GetNumber(): p.GetNet() for p in old.Pads()}
        for p in new.Pads():
            if p.GetNumber() in nets:
                p.SetNet(nets[p.GetNumber()])
        b.Remove(old)
        print(f'{ref}: {name} replaced')
    b.Save(str(PCB))


if __name__ == '__main__':
    main()
