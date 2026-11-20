"""Autoroute one rev 2 board with Freerouting (run with KiCad's Python, from anywhere).

    FREEROUTING_JAR=<path to freerouting-2.x.jar>  <KiCad>/bin/python rev2/hardware/tools/autoroute.py carrier|upper [passes]

Needs Java 25 on PATH. Steps: export a Specctra DSN without the copper pours -> adapt it (see below) -> Freerouting
-> import the session into the board -> refill the pours. Existing tracks stay; locked ones are left out of
Freerouting's result, so save a lock before re-running.

DSN changes:
  upper (2 layers):   none. GND is routed like any other net, so every GND pad has a real track; the pours and
                      stitching vias (stitch.py) come on top. Pours alone leave isolated islands on two layers.
  carrier (4 layers): In1 is declared a power layer with a GND plane, so Freerouting drops a via from each GND pad
                      and routes nothing on In1.
"""
import os
import re
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
    raise SystemExit('usage: autoroute.py carrier|upper [passes]')
PASSES = next((a for a in sys.argv[1:] if a.isdigit()), '30')
PROJECT = {'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD]
PCB = HW / BOARD / f'{PROJECT}.kicad_pcb'


def gnd_plane(dsn):
    """In1 = power layer carrying a GND plane over the whole board"""
    dsn = re.sub(r'(\(layer In1\.Cu\s*\(type )signal', r'\1power', dsn)
    m = re.search(r'\(boundary\s*\(path pcb 0((?:\s+-?[\d.]+)+)\s*\)\s*\)', dsn)
    if not m:
        raise SystemExit('DSN: board boundary not found')
    pts = ' '.join(m.group(1).split())
    return dsn.replace(m.group(0), m.group(0) + f'\n    (plane GND (polygon In1.Cu 0 {pts}))', 1)


def export():
    """write the adapted DSN from a copy of the board without pours (never saved)"""
    os.chdir(PCB.parent)
    dsn = Path(tempfile.gettempdir()) / f'{PROJECT}.dsn'
    b = pcbnew.LoadBoard(PCB.name)
    for z in list(b.Zones()):
        b.Remove(z)
    if not pcbnew.ExportSpecctraDSN(b, str(dsn)):
        raise SystemExit('DSN export failed')
    t = dsn.read_text(encoding='utf-8')
    if BOARD == 'carrier':
        t = gnd_plane(t)
    dsn.write_text(t, encoding='utf-8')


def main():
    jar = os.environ.get('FREEROUTING_JAR')
    if not jar or not Path(jar).exists():
        raise SystemExit('set FREEROUTING_JAR to the Freerouting 2.x jar')
    os.chdir(PCB.parent)                               # pcbnew: load and save next to the project file
    tmp = Path(tempfile.gettempdir())
    dsn, ses = tmp / f'{PROJECT}.dsn', tmp / f'{PROJECT}.ses'
    for f in (dsn, ses):
        f.unlink(missing_ok=True)

    # export in a process of its own: pcbnew cannot load the same board twice in one process
    subprocess.run([sys.executable, __file__, BOARD, '--export'], check=True)

    r = subprocess.run(['java', '-jar', jar, '-de', str(dsn), '-do', str(ses), '-mp', PASSES],
                       capture_output=True, text=True)
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if 'unrouted' in ln.lower() or 'completed' in ln.lower()]
    print('\n'.join(tail[-4:]))
    if not ses.exists():
        raise SystemExit('Freerouting wrote no session:\n' + (r.stdout + r.stderr)[-1500:])

    b = pcbnew.LoadBoard(PCB.name)
    if not pcbnew.ImportSpecctraSES(b, str(ses)):
        raise SystemExit('session import failed')
    thin = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetWidth() < pcbnew.FromMM(0.15)]
    for t in thin:                                     # Freerouting necks down below the board's minimum
        t.SetWidth(pcbnew.FromMM(0.15))
    b.Save(PCB.name)
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board', '-o', str(tmp / f'{PROJECT}.drc'), PCB.name],
                   capture_output=True)
    b = pcbnew.LoadBoard(PCB.name)
    print(f'{BOARD}: {len(b.GetTracks())} tracks and vias after routing')


if __name__ == '__main__':
    export() if '--export' in sys.argv else main()
