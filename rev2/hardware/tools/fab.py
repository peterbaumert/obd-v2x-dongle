"""Fabrication + assembly outputs for PCBWay, one set per rev 2 board (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/fab.py [carrier|upper]     (default: both)

Writes rev2/hardware/fab/<board>/ (git-ignored):
  obd-v2x-<board>-gerber.zip   Gerber X2 (4 copper, mask, paste, silk, edge) + Excellon PTH/NPTH drill + drill map
  obd-v2x-<board>-cpl.csv      pick & place, both sides, mm, origin = board bottom-left (drill/place origin)
  obd-v2x-<board>-bom.csv      assembly BOM: parts PCBWay fits (no DNP, no J201, no test pads / mounting holes)
Also refreshes rev2/docs/bom-<board>.csv (full BOM incl. DNP). Order settings: rev2/docs/bom-notes.md.
"""
import csv
import shutil
import subprocess
import sys
from pathlib import Path
import zipfile

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
import kicad_env  # noqa: E402

HW = Path(__file__).resolve().parents[1]
DOCS = HW.parent / 'docs'
BOARDS = ('carrier', 'upper')
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
# fitted parts PCBWay does not fit (see rev2/docs/bom-notes.md)
NOT_ASSEMBLED = {'J201': 'OBD-II plug: hand-soldered after assembly (AliExpress part)'}
# notes for parts PCBWay fits by hand
NOTES = {
    'AE801': 'pin-fed ceramic patch: fit after reflow, feed pin soldered from the bottom, fixed with its adhesive pad',
    'J701': 'through-hole pin header: base flat on the board',
    'J702': 'through-hole pin header: base flat on the board',
}


def cli(*args):
    subprocess.run([str(kicad_env.CLI), *args], check=True, stdout=subprocess.DEVNULL)


def build(board):
    name = f'obd-v2x-{board}'
    pcb = HW / board / f'{name}.kicad_pcb'
    sch = HW / board / f'{name}.kicad_sch'
    out = HW / 'fab' / board
    if out.exists():
        shutil.rmtree(out)
    gdir = out / 'gerber'
    gdir.mkdir(parents=True)

    cli('pcb', 'export', 'gerbers', '-o', str(gdir) + '/', '-l', LAYERS, '--use-drill-file-origin', str(pcb))
    cli('pcb', 'export', 'drill', '-o', str(gdir) + '/', '--format', 'excellon', '--drill-origin', 'plot',
        '--excellon-units', 'mm', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', str(pcb))
    with zipfile.ZipFile(out / f'{name}-gerber.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gdir.iterdir()):
            z.write(f, f.name)

    board_obj = pcbnew.LoadBoard(str(pcb))
    fps = {fp.GetReference(): fp for fp in board_obj.GetFootprints()}

    def placed(ref):        # test pads, mounting holes etc. are excluded from the position files
        fp = fps.get(ref)
        return fp is not None and ref not in NOT_ASSEMBLED and not fp.GetAttributes() & pcbnew.FP_EXCLUDE_FROM_POS_FILES

    def kind(ref):          # footprint type, not pads: thermal vias in an SMD footprint are PTH pads
        return 'THT' if fps[ref].GetAttributes() & pcbnew.FP_THROUGH_HOLE else 'SMD'

    # pick & place
    raw = out / 'pos-raw.csv'
    cli('pcb', 'export', 'pos', '-o', str(raw), '--side', 'both', '--format', 'csv', '--units', 'mm',
        '--use-drill-file-origin', '--exclude-dnp', str(pcb))
    rows = list(csv.DictReader(raw.open(newline='')))
    raw.unlink()
    with (out / f'{name}-cpl.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation', 'Value', 'Package'])
        for r in rows:
            if not placed(r['Ref']):
                continue
            w.writerow([r['Ref'], r['PosX'], r['PosY'], 'Top' if r['Side'] == 'top' else 'Bottom', r['Rot'],
                        r['Val'], r['Package']])

    # BOM (full, for docs) and assembly BOM
    full = DOCS / f'bom-{board}.csv'
    DOCS.mkdir(exist_ok=True)
    cli('sch', 'export', 'bom', '--fields', 'Reference,Value,Footprint,MPN,Manufacturer,LCSC,${QUANTITY},${DNP}',
        '--labels', 'Reference,Value,Footprint,MPN,Manufacturer,LCSC,Qty,DNP',
        '--group-by', 'Value,Footprint,MPN,${DNP}', '--ref-range-delimiter', '', '-o', str(full), str(sch))
    n = 0
    with full.open(newline='') as f, (out / f'{name}-bom.csv').open('w', newline='') as g:
        w = csv.writer(g)
        w.writerow(['Item', 'Designator', 'Qty', 'Value', 'Manufacturer', 'Manufacturer Part Number', 'LCSC',
                    'Package', 'Type', 'Side', 'Note'])
        for r in csv.DictReader(f):
            if r['DNP']:
                continue
            refs = [x for x in r['Reference'].split(',') if placed(x)]
            if not refs:
                continue
            side = sorted({'Bottom' if fps[x].IsFlipped() else 'Top' for x in refs})
            note = '; '.join(sorted({NOTES[x] for x in refs if x in NOTES}))
            if not r['MPN']:
                note = 'generic: any in-stock part with this value and package'
            n += 1
            w.writerow([n, ' '.join(refs), len(refs), r['Value'], r['Manufacturer'], r['MPN'], r['LCSC'],
                        r['Footprint'].split(':')[-1], ' / '.join(sorted({kind(x) for x in refs})), ' / '.join(side), note])
    print(f'{board}: {n} BOM lines, {sum(1 for r in rows if placed(r["Ref"]))} placements ->',
          ', '.join(p.name for p in sorted(out.iterdir()) if p.is_file()), f'+ rev2/docs/{full.name}')


def main():
    for b in [a for a in sys.argv[1:] if a in BOARDS] or BOARDS:
        build(b)


if __name__ == '__main__':
    main()
