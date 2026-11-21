"""Replace placed footprints on a routed rev 2 board with the current library version (KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/swapfp.py carrier|upper REF[=Lib:Footprint] [...]

After changing a footprint in rev2/hardware/lib/gen_footprints.py (or, with =Lib:Footprint, after giving a part another
footprint in the schematic; KiCad's own libraries are found next to kicad-cli): keeps each part's position, rotation, side,
fields and pad nets (by pad number); tracks stay. Run DRC afterwards: copper that no longer fits the new pads shows
up there.
"""
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
from kicad_env import CLI  # noqa: E402

HW = Path(__file__).resolve().parents[1]
args = sys.argv[1:]
if len(args) < 2 or args[0] not in ('carrier', 'upper'):
    raise SystemExit('usage: swapfp.py carrier|upper REF [REF ...]')
BOARD, REFS = args[0], args[1:]
PCB = HW / BOARD / ({'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD] + '.kicad_pcb')
LIB = HW / 'lib' / 'obd-v2x.pretty'
STD = Path(CLI).resolve().parent.parent / 'share' / 'kicad' / 'footprints'


def main():
    b = pcbnew.LoadBoard(str(PCB))
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    for arg in REFS:
        ref, _, target = arg.partition('=')
        old = fps[ref]
        lib, name = (target.split(':') if target else
                     (old.GetFPID().GetLibNickname().wx_str(), old.GetFPID().GetLibItemName().wx_str()))
        path = LIB if lib == 'obd-v2x' else STD / f'{lib}.pretty'
        new = pcbnew.FootprintLoad(str(path), name)
        if new is None:
            raise SystemExit(f'{ref}: {name} not in {path}')
        new.SetFPID(pcbnew.LIB_ID(lib, name))
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
