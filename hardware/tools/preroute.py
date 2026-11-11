"""Hand-specified routing for the critical nets, applied to the existing board (idempotent:
removes its own previous tracks/vias/zones on these nets first). Run before autorouting:

    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" hardware/tools/preroute.py

- LTE main / GNSS antenna chains: straight 0.35 mm F.Cu lines (50 ohm placeholder), GND vias at the
  shunt caps and U.FL shields, via fence on both sides.
- Buck switch node (Net-(D103-K)): solid F.Cu copper area joining U102 SW, D103 cathode, L101.
"""
import os
import subprocess
from pathlib import Path

import pcbnew

HW = Path(__file__).resolve().parents[1]
PCB = HW / 'obd-v2x-dongle.kicad_pcb'
KICAD = Path(os.environ['LOCALAPPDATA']) / 'Programs/KiCad/10.0'
OX, OY = 100.0, 50.0
RF_W = 0.35
VIA_D, VIA_DR = 0.6, 0.3


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


board = pcbnew.LoadBoard(str(PCB))
nets = {n: board.FindNet(n) for n in ('GND', '/LTE + GNSS (EC200U)/LTE_ANT_MAIN', '/LTE + GNSS (EC200U)/LTE_ANT_GNSS',
                                      'Net-(J402-In)', 'Net-(J403-In)', 'Net-(D103-K)')}
for k, v in nets.items():
    assert v is not None, k
OWN = {'/LTE + GNSS (EC200U)/LTE_ANT_MAIN', '/LTE + GNSS (EC200U)/LTE_ANT_GNSS', 'Net-(J402-In)', 'Net-(J403-In)'}
MARK = 'preroute'

# remove what a previous run added
for t in list(board.GetTracks()):
    if t.GetNetname() in OWN:
        board.Delete(t)
for z in list(board.Zones()):
    if z.GetZoneName() in ('SW_NODE',) or z.GetZoneName().startswith(MARK):
        board.Delete(z)
added_gnd = []   # GND vias from a previous run are recognised by position (planned_vias)


def pad(ref, num, which=0):
    ps = [p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num]
    q = ps[which].GetPosition()
    return pcbnew.ToMM(q.x) - OX, pcbnew.ToMM(q.y) - OY


def track(a, b, net, w=RF_W, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(*a)); t.SetEnd(pt(*b)); t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(nets[net] if net in nets else board.FindNet(net))
    board.Add(t)


def via(x, y, net='GND'):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DR)); v.SetNet(nets[net])
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(v)
    added_gnd.append((round(x, 3), round(y, 3)))


# drop old GND vias at the exact positions we are about to add (re-run safety)
def planned_vias():
    out = []
    for ch in (('U401', '49', 'C411', 'R409', 'C412', 'J402', -1), ('U401', '47', 'C413', 'R410', 'C414', 'J403', +1)):
        out += rf_chain(*ch, dry=True)
    return out


def rf_chain(u, pin, c1, r, c2, j, away, dry=False):
    """away = -1: shunt GND ends / fence side away from the other channel is -y"""
    p0 = pad(u, pin)
    xs = (p0[0], pad(c1, '1')[0], pad(r, '1')[0])
    y = p0[1]
    vias = []
    # shunt cap GND vias, 0.8 mm beyond the GND pad, plus short stub
    for c in (c1, c2):
        gx, gy = pad(c, '2')
        vias.append((gx, gy + away * 0.85, (gx, gy)))
    # U.FL shield vias (outside the pads, towards +x)
    for i in (0, 1):
        gx, gy = pad(j, '2', i)
        vias.append((gx + 1.75, gy, (gx, gy)))
    # fence: both sides of the line, between the parts
    for fx in (37.4, 41.7, 44.2):
        for side in (-1, 1):
            vias.append((fx, y + side * 1.05, None))
    if dry:
        return [(round(v[0], 3), round(v[1], 3)) for v in vias]
    net_a = board.FindFootprintByReference(u).FindPadByNumber(pin).GetNetname()
    net_b = board.FindFootprintByReference(r).FindPadByNumber('2').GetNetname()
    track(p0, pad(r, '1'), net_a)
    track(pad(r, '2'), pad(j, '1'), net_b)
    for vx, vy, stub in vias:
        via(vx, vy)
        if stub:
            track(stub, (vx, vy), 'GND', w=0.4)
    return vias


plan = set(planned_vias())
for t in list(board.GetTracks()):
    if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == 'GND':
        q = t.GetPosition()
        if (round(pcbnew.ToMM(q.x) - OX, 3), round(pcbnew.ToMM(q.y) - OY, 3)) in plan:
            board.Delete(t)
    elif t.GetNetname() == 'GND' and t.GetWidth() == mm(0.4):
        for e in (t.GetStart(), t.GetEnd()):
            if (round(pcbnew.ToMM(e.x) - OX, 3), round(pcbnew.ToMM(e.y) - OY, 3)) in plan:
                board.Delete(t)
                break

rf_chain('U401', '49', 'C411', 'R409', 'C412', 'J402', -1)
rf_chain('U401', '47', 'C413', 'R410', 'C414', 'J403', +1)

# buck switch node copper area
z = pcbnew.ZONE(board)
z.SetLayer(pcbnew.F_Cu)
z.SetNet(nets['Net-(D103-K)'])
z.SetZoneName('SW_NODE')
z.SetAssignedPriority(10)
z.SetLocalClearance(mm(0.3))
z.SetMinThickness(mm(0.25))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
ol = z.Outline()
ol.NewOutline()
for x, y in ((28.3, 22.9), (31.5, 19.0), (34.4, 19.0), (34.4, 27.4), (36.0, 27.4), (36.0, 30.5),
             (32.2, 30.5), (28.3, 24.3)):
    ol.Append(mm(OX + x), mm(OY + y))
board.Add(z)

board.Save(str(PCB))
subprocess.run([str(KICAD / 'bin/kicad-cli.exe'), 'pcb', 'drc', '--refill-zones', '--save-board',
                '-o', os.path.join(os.environ.get('TEMP', '.'), 'obd-v2x-preroute.drc'), str(PCB)],
               check=False, capture_output=True)
print('pre-routed RF chains + SW node;', len(added_gnd), 'GND vias')
