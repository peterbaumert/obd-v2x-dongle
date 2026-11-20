"""Repair pass after autorouting a rev 2 board (run with KiCad's Python).

    <KiCad>/bin/python rev2/hardware/tools/repair.py carrier|upper [rounds]

1. Vias with a 0.6 mm pad and a drill above 0.3 mm get a 0.3 mm drill (0.15 mm annular ring); tracks narrower than
   the board minimum are widened to it. Freerouting produces both.
2. Each round: run DRC; every signal net with a track or via in a clearance, edge-clearance, short or annular-width
   error is ripped up completely; route_unconnected.py routes those nets again, one connection at a time.
Supply nets (see KEEP) are never ripped up: fix those by hand. Run stitch.py and DRC afterwards.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from kicad_env import CLI  # noqa: E402

BOARD = next((a for a in sys.argv[1:] if a in ('carrier', 'upper')), None)
if BOARD is None:
    raise SystemExit('usage: repair.py carrier|upper [rounds]')
ROUNDS = next((int(a) for a in sys.argv[1:] if a.isdigit()), 3)
PCB = HERE.parent / BOARD / ({'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD] + '.kicad_pcb')
KEEP = ('GND', 'VSYS_3V8', 'VBUCK_3V8', 'VBAT_LTE', 'VCELL', 'VIN_PROT', '+3V3', 'VBAT_F', 'OBD_VBAT', 'LTE_ANT',
        'Net-(J402-In)', 'Net-(J403-In)', 'Net-(D103-K)')
BAD = ('clearance', 'copper_edge_clearance', 'shorting_items', 'annular_width', 'hole_clearance', 'tracks_crossing')
MIN_TRACK = 0.15


def drc():
    out = Path(tempfile.gettempdir()) / f'obd-v2x-rev2-{BOARD}-repair.json'
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-error', '--format', 'json',
                    '-o', str(out), PCB.name], capture_output=True)
    return json.loads(out.read_text(encoding='utf-8'))


def nets_in(d):
    nets = set()
    for v in d['violations']:
        if v['type'] not in BAD:
            continue
        for i in v['items']:
            desc = i['description']
            if not (desc.startswith('Track') or desc.startswith('Via')) or '[' not in desc:
                continue
            net = desc.split('[')[1].split(']')[0]
            if not any(k in net for k in KEEP):
                nets.add(net)
    return nets


def main():
    os.chdir(PCB.parent)
    b = pcbnew.LoadBoard(PCB.name)
    nv = nt = 0
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            if pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) < 0.7 and pcbnew.ToMM(t.GetDrill()) > 0.31:
                t.SetDrill(pcbnew.FromMM(0.3))
                nv += 1
        elif t.GetWidth() < pcbnew.FromMM(MIN_TRACK):
            t.SetWidth(pcbnew.FromMM(MIN_TRACK))
            nt += 1
    b.Save(PCB.name)
    print(f'{nv} via drills set to 0.3 mm, {nt} tracks widened to {MIN_TRACK} mm')
    del b
    for rnd in range(ROUNDS):
        d = drc()
        nets = nets_in(d)
        bad = sum(1 for v in d['violations'] if v['type'] in BAD)
        print(f'round {rnd}: {bad} rule errors, {len(d.get("unconnected_items", []))} unconnected; ripping up {sorted(nets)}')
        if not nets:
            break
        # in a process of its own: pcbnew does not like loading the same board twice
        code = ("import pcbnew, sys\n"
                "b = pcbnew.LoadBoard(sys.argv[1])\n"
                "nets = set(sys.argv[2:])\n"
                "for t in list(b.GetTracks()):\n"
                "    if t.GetNetname() in nets:\n"
                "        b.Delete(t)\n"
                "b.Save(sys.argv[1])\n")
        subprocess.run([sys.executable, '-c', code, PCB.name, *sorted(nets)], check=True, capture_output=True)
        r = subprocess.run([sys.executable, str(HERE / 'route_unconnected.py'), BOARD, '4'], capture_output=True, text=True)
        print('  ' + (r.stdout.strip().splitlines() or ['(no output)'])[-1][:200])
    d = drc()
    print(f'after repair: {sum(1 for v in d["violations"] if v["type"] in BAD)} rule errors, '
          f'{len(d.get("unconnected_items", []))} unconnected')


if __name__ == '__main__':
    main()
