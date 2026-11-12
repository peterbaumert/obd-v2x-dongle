"""Fabrication + assembly outputs for PCBWay (run with KiCad's Python: <KiCad>/bin/python hardware/tools/fab.py).

Writes hardware/fab/ (git-ignored):
  obd-v2x-dongle-gerber.zip   Gerber X2 (4 copper, mask, paste, silk, edge) + Excellon PTH/NPTH drill + drill map
  obd-v2x-dongle-cpl.csv      pick & place, both sides, mm, origin = board bottom-left (drill/place origin), DNP left out
  obd-v2x-dongle-bom.csv      assembly BOM: parts PCBWay places (no DNP, no J201, no test pads), MPN / LCSC, SMD/THT, side
Also refreshes docs/bom.csv (full BOM incl. DNP).

Order notes (also in docs/design-review.md): 4 layers, 1.6 mm, 1 oz outer / 1 oz inner, PCBWay standard stack-up
with 7628 prepreg; impedance control 50 ohm on L1 (RF lines, 0.32 mm GCPW, gap 0.25 mm, reference L2);
double-sided assembly; J201 (OBD plug) is not assembled (hand-soldered).
"""
import csv
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
import kicad_env  # noqa: E402

HW = Path(__file__).resolve().parents[1]
ROOT = HW.parent
PCB = HW / 'obd-v2x-dongle.kicad_pcb'
SCH = HW / 'obd-v2x-dongle.kicad_sch'
OUT = HW / 'fab'
NAME = 'obd-v2x-dongle'
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
# fitted parts PCBWay should not place (hand-soldered after assembly, see docs/bom-notes.md)
NOT_ASSEMBLED = {'J201': 'hand-solder after assembly (OBD-II plug, AliExpress part)'}


def cli(*args):
    subprocess.run([str(kicad_env.CLI), *args], check=True, stdout=subprocess.DEVNULL)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    gdir = OUT / 'gerber'
    gdir.mkdir(parents=True)

    cli('pcb', 'export', 'gerbers', '-o', str(gdir) + '/', '-l', LAYERS, '--use-drill-file-origin', str(PCB))
    cli('pcb', 'export', 'drill', '-o', str(gdir) + '/', '--format', 'excellon', '--drill-origin', 'plot',
        '--excellon-units', 'mm', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', str(PCB))
    with zipfile.ZipFile(OUT / f'{NAME}-gerber.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gdir.iterdir()):
            z.write(f, f.name)

    # pick & place
    raw = OUT / 'pos-raw.csv'
    cli('pcb', 'export', 'pos', '-o', str(raw), '--side', 'both', '--format', 'csv', '--units', 'mm',
        '--use-drill-file-origin', '--exclude-dnp', str(PCB))
    rows = list(csv.DictReader(raw.open(newline='')))
    raw.unlink()
    with (OUT / f'{NAME}-cpl.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation', 'Value', 'Package'])
        for r in rows:
            if r['Ref'].startswith(('FID', 'REF')) or r['Ref'] in NOT_ASSEMBLED:
                continue
            w.writerow([r['Ref'], r['PosX'], r['PosY'], 'Top' if r['Side'] == 'top' else 'Bottom', r['Rot'],
                        r['Val'], r['Package']])

    # BOM (full, for docs) and assembly BOM
    full = ROOT / 'docs' / 'bom.csv'
    cli('sch', 'export', 'bom', '--fields', 'Reference,Value,Footprint,MPN,Manufacturer,LCSC,${QUANTITY},${DNP}',
        '--labels', 'Reference,Value,Footprint,MPN,Manufacturer,LCSC,Qty,DNP',
        '--group-by', 'Value,Footprint,MPN,${DNP}', '--ref-range-delimiter', '', '-o', str(full), str(SCH))
    board = pcbnew.LoadBoard(str(PCB))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def kind(ref):          # footprint type, not pads: thermal vias in an SMD footprint are PTH pads
        return 'THT' if fps[ref].GetAttributes() & pcbnew.FP_THROUGH_HOLE else 'SMD'

    def placed(ref):        # nothing to place: test pads etc. are excluded from the position files
        return ref not in NOT_ASSEMBLED and not fps[ref].GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES

    with full.open(newline='') as f, (OUT / f'{NAME}-bom.csv').open('w', newline='') as g:
        w = csv.writer(g)
        w.writerow(['Item', 'Designator', 'Qty', 'Value', 'Manufacturer', 'Manufacturer Part Number', 'LCSC',
                    'Package', 'Type', 'Side', 'Note'])
        n = 0
        for r in csv.DictReader(f):
            if r['DNP']:
                continue
            refs = [x for x in r['Reference'].split(',') if placed(x)]
            if not refs:
                continue
            side = sorted({'Bottom' if fps[x].IsFlipped() else 'Top' for x in refs})
            note = 'generic: any in-stock part with this value and package' if not r['MPN'] else ''
            n += 1
            w.writerow([n, ' '.join(refs), len(refs), r['Value'], r['Manufacturer'], r['MPN'], r['LCSC'],
                        r['Footprint'].split(':')[-1], ' / '.join(sorted({kind(x) for x in refs})), ' / '.join(side), note])
    print('wrote', ', '.join(p.name for p in sorted(OUT.iterdir()) if p.is_file()), '+ docs/bom.csv')


if __name__ == '__main__':
    main()
