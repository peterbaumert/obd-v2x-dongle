"""Bootstrap hardware/obd-v2x-dongle.kicad_pcb from the schematic: outline, stack-up, rules,
footprints with nets, first-pass placement, GND planes.

Run with KiCad's Python (needs pcbnew):
    "%LOCALAPPDATA%\\Programs\\KiCad\\10.0\\bin\\python.exe" hardware/tools/gen_pcb.py [--force]

The PCB is generated ONCE. After routing starts it is edited in KiCad (Tools > Update PCB from
Schematic for netlist changes). --force overwrites the board, including any routing.

Coordinates below are board-relative mm, top view: x right, y away from the OBD plug
(front edge y=0, rear edge y=BOARD_L). Bottom-side parts are given in the same top-view frame.
"""
import math
import os
import subprocess
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
from sexp import parse, find  # noqa: E402

HW = Path(__file__).resolve().parents[1]
PCB = HW / 'obd-v2x-dongle.kicad_pcb'
SCH = HW / 'obd-v2x-dongle.kicad_sch'
KICAD = Path(os.environ['LOCALAPPDATA']) / 'Programs/KiCad/10.0'
STOCK_FP = KICAD / 'share/kicad/footprints'

OX, OY = 100.0, 50.0          # board origin on the page
BOARD_W, BOARD_L = 52.0, 74.0
CORNER_R = 2.0

T, B = 'top', 'bottom'
# ref: (x, y, rot, side) -- explicit placement of the parts that define the layout
PLACE = {
    # OBD plug: pin 1 at (40, 11.5), housing overhangs the front edge by 12 mm
    'J201': (40.0, 11.5, 0, T),
    # power strip (top), flow left -> right
    'F101': (5.5, 19.0, 0, T),
    'D101': (6.5, 25.5, 0, T),
    'Q101': (16.5, 20.5, 0, T),
    'U101': (16.0, 27.5, 0, T),
    'C102': (23.5, 19.0, 0, T),
    'U102': (25.0, 25.5, 0, T),
    'L101': (36.0, 21.0, 0, T),
    'D103': (37.5, 29.0, 0, T),
    'C107': (45.0, 20.0, 90, T),
    'C108': (49.0, 20.0, 90, T),
    'Q102': (46.5, 27.0, 0, T),
    # LTE (top)
    'U401': (19.5, 54.0, 0, T),
    'C401': (27.5, 34.5, 0, T),
    # antenna chains in a straight line from the modem pin (y = pin y) to the U.FL; shunt caps' GND ends
    # point away from the other channel (pad 1 on the RF line)
    'C411': (38.3, 48.05 - 0.48, 90, T), 'R409': (40.3, 48.05, 0, T), 'C412': (42.6, 48.05 - 0.48, 90, T),
    'J402': (47.0, 48.05, 0, T),
    'C413': (38.3, 53.75 + 0.48, 270, T), 'R410': (40.3, 53.75, 0, T), 'C414': (42.6, 53.75 + 0.48, 270, T),
    'J403': (47.0, 53.75, 0, T),
    # vehicle side (bottom, under the plug)
    'U201': (22.0, 5.0, 0, B),
    'U202': (8.5, 5.0, 0, B),
    'D201': (30.0, 5.0, 0, B),
    # MCU (bottom)
    'U301': (40.5, 30.0, 0, B),
    'J401': (9.5, 56.0, 0, B),
    'U402': (26.0, 46.0, 90, B),
    'J301': (45.0, None, 0, B),            # y: receptacle front 0.3 mm past the rear edge (below)
    'SW301': (31.0, 69.5, 0, B),
    'SW302': (20.5, 69.5, 0, B),
    'D301': (6.0, 70.0, 0, B),
}

# small parts: ref: (anchor ref, anchor pad, side or None = side of anchor)
ANCHOR = {
    'C101': ('U101', '1', None), 'C103': ('U102', '2', None), 'C104': ('U102', '1', None),
    'C105': ('U102', '6', None), 'C106': ('U102', '6', None), 'R106': ('U102', '6', None),
    'R101': ('U102', '3', None), 'R102': ('U102', '3', None), 'R103': ('U102', '4', None),
    'R104': ('U102', '5', None), 'R105': ('U102', '5', None),
    'R107': ('Q102', '1', None), 'Q103': ('Q102', '1', None), 'R108': ('Q102', '1', None),
    'U103': ('U301', '2', None), 'C109': ('U301', '2', None), 'C110': ('U301', '2', None),
    'C302': ('U301', '2', None), 'C303': ('U301', '2', None),
    'C301': ('U301', '3', None), 'R301': ('U301', '3', None), 'R302': ('U301', '15', None),
    'C111': ('U301', '7', None), 'R109': ('U301', '7', None), 'R110': ('U301', '7', None),
    'TP301': ('U301', '25', None), 'TP302': ('U301', '24', None), 'TP303': ('U301', '1', None),
    'C304': ('D301', '4', None),
    'R303': ('J301', 'A5', None), 'R304': ('J301', 'B5', None), 'U302': ('J301', 'A6', None),
    'D102': ('J301', 'A4', None),
    'C201': ('U201', '3', None), 'R201': ('U201', '8', None),
    'C202': ('U202', '7', None), 'R202': ('U202', '1', None), 'R203': ('U202', '2', None),
    'C203': ('U202', '6', None), 'D203': ('U202', '6', None), 'D202': ('U202', '7', None),
    'R204': ('U202', '7', None),
    'C402': ('U401', '59', None), 'C403': ('U401', '58', None), 'C404': ('U401', '57', None),
    'C405': ('U401', '7', B),
    'C406': ('U402', '1', None),
    'Q401': ('U401', '21', B), 'Q402': ('U401', '20', B),
    'R401': ('U401', '21', B), 'R402': ('U401', '21', B), 'R403': ('U401', '20', B), 'R404': ('U401', '20', B),
    'R405': ('J401', '7', None), 'R406': ('J401', '3', None), 'R407': ('J401', '2', None),
    'R408': ('J401', '7', None), 'C407': ('J401', '7', None), 'C408': ('J401', '3', None),
    'C409': ('J401', '2', None), 'C410': ('J401', '1', None),
    'TP401': ('U401', '71', B), 'TP402': ('U401', '69', B), 'TP403': ('U401', '70', B),
    'TP404': ('U401', '115', B), 'TP405': ('U401', '12', B), 'TP406': ('U401', '11', B),
    'TP407': ('U401', '7', B),
}

GAP = 0.3          # min gap between courtyards when auto-placing
SOLID_GND = {'U102', 'U401', 'U301'}   # thermal / RF ground pads: solid zone connection
EDGE = 0.8         # keep courtyards this far inside the outline

# design rules (PCBWay standard 4-layer capability, with margin)
RULES = dict(track=0.15, clearance=0.15, via_d=0.6, via_drill=0.3, min_drill=0.3,
             annular=0.15, hole_to_hole=0.25, edge=0.4)


PRO = HW / 'obd-v2x-dongle.kicad_pro'
NETCLASSES = [
    # name, track, clearance, via_d, via_drill, net-name patterns
    ('Power', 0.6, 0.2, 0.8, 0.4, ['OBD_VBAT', 'VBAT_F', 'VIN_PROT', 'VSYS_3V8', 'VBAT_LTE', 'Net-(D103-K)',
                                  'Net-(D202-K)', 'VBUS_USB']),
    # 50 ohm placeholder: confirm width/gap with PCBWay's impedance calculator for the ordered stack-up
    ('RF', 0.35, 0.25, 0.6, 0.3, ['*LTE_ANT_*', 'Net-(J402-In)', 'Net-(J403-In)']),
]


def write_project_rules():
    import json
    d = json.loads(PRO.read_text(encoding='utf-8'))
    rules = d.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {})
    rules.update({
        'min_clearance': RULES['clearance'], 'min_track_width': RULES['track'],
        'min_via_diameter': RULES['via_d'], 'min_through_hole_diameter': RULES['min_drill'],
        'min_via_annular_width': RULES['annular'], 'min_hole_to_hole': RULES['hole_to_hole'],
        'min_copper_edge_clearance': RULES['edge'], 'min_hole_clearance': 0.25,
        'min_silk_clearance': 0.0, 'min_text_height': 0.8, 'min_text_thickness': 0.12,
    })
    ns = d.setdefault('net_settings', {})
    default = next(c for c in ns['classes'] if c['name'] == 'Default')
    default.update(track_width=0.2, clearance=0.15, via_diameter=0.6, via_drill=0.3)
    ns['classes'] = [default]
    patterns = []
    for name, tw, cl, vd, vdr, pats in NETCLASSES:
        c = dict(default, name=name, track_width=tw, clearance=cl, via_diameter=vd, via_drill=vdr, priority=len(ns['classes']))
        ns['classes'].append(c)
        patterns += [{'netclass': name, 'pattern': p} for p in pats]
    ns['netclass_patterns'] = patterns
    PRO.write_text(json.dumps(d, indent=2) + '\n', encoding='utf-8')


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


# ------------------------------------------------------------------ netlist
def read_netlist():
    out = Path(os.environ.get('TEMP', '.')) / 'obd-v2x-gen_pcb.net'
    subprocess.run([str(KICAD / 'bin/kicad-cli.exe'), 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
                    '-o', str(out), str(SCH)], check=True, capture_output=True)
    n = parse(out.read_text(encoding='utf-8'))
    comps = {}
    for c in find(find(n, 'components')[0], 'comp'):
        ref = find(c, 'ref')[0][1]
        sp = find(c, 'sheetpath')[0]
        fields = {}
        for fs in find(c, 'fields'):
            for fld in find(fs, 'field'):
                key = fld[1][1] if isinstance(fld[1], list) else fld[1]
                fields[key] = fld[2] if len(fld) > 2 else ''
        for key in ('datasheet', 'description'):
            e = find(c, key)
            if e and len(e[0]) > 1:
                fields[key.capitalize()] = e[0][1]
        comps[ref] = dict(
            value=find(c, 'value')[0][1], fp=find(c, 'footprint')[0][1],
            sheetnames=find(sp, 'names')[0][1], sheetstamps=find(sp, 'tstamps')[0][1],
            stamp=find(c, 'tstamps')[0][1], fields=fields,
            sheetfile=(find(find(c, 'property')[0:0] or [['', '']], 'x') and '') or '')
        props = set()
        for p in find(c, 'property'):
            props.add(find(p, 'name')[0][1])
            if find(p, 'name')[0][1] == 'Sheetfile':
                comps[ref]['sheetfile'] = find(p, 'value')[0][1]
        comps[ref]['dnp'] = 'dnp' in props
        comps[ref]['no_bom'] = 'exclude_from_bom' in props
    nets = {}
    for net in find(find(n, 'nets')[0], 'net'):
        name = find(net, 'name')[0][1]
        for nd in find(net, 'node'):
            nets[(find(nd, 'ref')[0][1], find(nd, 'pin')[0][1])] = name
    return comps, nets


def load_fp(fpid):
    lib, name = fpid.split(':', 1)
    path = HW / 'lib/obd-v2x.pretty' if lib == 'obd-v2x' else STOCK_FP / f'{lib}.pretty'
    fp = pcbnew.FootprintLoad(str(path), name)
    if fp is None:
        raise SystemExit(f'footprint not found: {fpid}')
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


# ------------------------------------------------------------------ geometry helpers
def crt_box(fp):
    """courtyard bbox (board coords, mm) of a placed footprint on its own side"""
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    poly = fp.GetCourtyard(layer)
    bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False)
    return (pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY,
            pcbnew.ToMM(bb.GetRight()) - OX, pcbnew.ToMM(bb.GetBottom()) - OY)


def overlaps(a, b, gap=GAP):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def inside(bx):
    return bx[0] >= EDGE and bx[1] >= EDGE and bx[2] <= BOARD_W - EDGE and bx[3] <= BOARD_L - EDGE


def place(fp, x, y, rot, side):
    fp.SetPosition(pt(x, y))
    fp.SetOrientationDegrees(rot)
    if side == B and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def pad_xy(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == num:
            q = p.GetPosition()
            return pcbnew.ToMM(q.x) - OX, pcbnew.ToMM(q.y) - OY
    raise KeyError((fp.GetReference(), num))


# ------------------------------------------------------------------ board
def build():
    comps, nets = read_netlist()
    board = pcbnew.NewBoard(str(PCB))
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(RULES['track'])
    ds.m_MinClearance = mm(RULES['clearance'])
    ds.m_ViasMinSize = mm(RULES['via_d'])
    ds.m_MinThroughDrill = mm(RULES['min_drill'])
    ds.m_ViasMinAnnularWidth = mm(RULES['annular'])
    ds.m_HoleToHoleMin = mm(RULES['hole_to_hole'])
    ds.m_CopperEdgeClearance = mm(RULES['edge'])
    ds.m_HoleClearance = mm(0.25)

    # outline with rounded corners
    r = CORNER_R
    segs = [((r, 0), (BOARD_W - r, 0)), ((BOARD_W, r), (BOARD_W, BOARD_L - r)),
            ((BOARD_W - r, BOARD_L), (r, BOARD_L)), ((0, BOARD_L - r), (0, r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        board.Add(s)
    k = r * (1 - math.sqrt(0.5))
    for (sx, sy), (mx, my), (ex, ey) in (
            ((0, r), (k, k), (r, 0)),
            ((BOARD_W - r, 0), (BOARD_W - k, k), (BOARD_W, r)),
            ((BOARD_W, BOARD_L - r), (BOARD_W - k, BOARD_L - k), (BOARD_W - r, BOARD_L)),
            ((r, BOARD_L), (k, BOARD_L - k), (0, BOARD_L - r))):
        a = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(pt(sx, sy), pt(mx, my), pt(ex, ey))
        a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(mm(0.1))
        board.Add(a)

    # nets
    netinfo = {}
    for name in sorted(set(nets.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni

    # footprints
    fps = {}
    for ref, c in comps.items():
        fp = load_fp(c['fp'])
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        for k, v in c['fields'].items():
            if k == 'Footprint':
                continue
            if k in ('Datasheet', 'Description'):
                fp.GetField(k).SetText(v)
                continue
            fp.SetField(k, v)
            fld = fp.GetField(k)
            if fld:
                fld.SetVisible(False)
        fp.SetPath(pcbnew.KIID_PATH(c['sheetstamps'] + c['stamp']))
        fp.SetDNP(c['dnp'])
        fp.SetExcludedFromBOM(c['no_bom'])
        fp.SetSheetname(c['sheetnames'])
        fp.SetSheetfile(c['sheetfile'])
        for p in fp.Pads():
            n = nets.get((ref, p.GetNumber()))
            if n:
                p.SetNet(netinfo[n])
                if n == 'GND' and ref in SOLID_GND:
                    p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        fp.Value().SetVisible(False)
        big = ref in ('U401', 'U301', 'J201', 'J401')
        sz = mm(1.0 if big else 0.8)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(sz, sz))
        fp.Reference().SetTextThickness(mm(0.15 if big else 0.12))
        board.Add(fp)
        fps[ref] = fp

    placed = {T: [], B: []}

    def claim(fp, side):
        bx = crt_box(fp)
        placed[side].append((fp.GetReference(), bx))
        holes = [p for p in fp.Pads() if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)]
        if holes:                                   # through-hole pins block the other side too
            xs = [pcbnew.ToMM(p.GetPosition().x) - OX for p in holes]
            ys = [pcbnew.ToMM(p.GetPosition().y) - OY for p in holes]
            placed[B if side == T else T].append((fp.GetReference() + '-pins',
                                                   (min(xs) - 1.5, min(ys) - 1.5, max(xs) + 1.5, max(ys) + 1.5)))

    # explicit parts
    for ref, (x, y, rot, side) in PLACE.items():
        fp = fps[ref]
        place(fp, x, 0 if y is None else y, rot, side)
        if y is None:     # USB-C (HRO TYPE-C-31-M-12): body front is 3.65 mm in front of the origin
            fp.SetPosition(pt(x, BOARD_L - 3.65 + 0.3))
        claim(fp, side)

    # anchored small parts: spiral search around the anchor pad
    def free(bx, side):
        if not inside(bx):
            return False
        return all(not overlaps(bx, o) for _, o in placed[side])

    for ref, (aref, apad, side) in ANCHOR.items():
        fp = fps[ref]
        side = side or (B if fps[aref].IsFlipped() else T)
        ax, ay = pad_xy(fps[aref], apad)
        best = None
        for rot in (0, 90):
            place(fp, ax, ay, rot, side)
            for ring in range(0, 120):
                rr = ring * 0.5
                steps = max(1, int(2 * math.pi * rr / 0.5))
                hit = None
                for s in range(steps):
                    a = 2 * math.pi * s / steps
                    x, y = ax + rr * math.cos(a), ay + rr * math.sin(a)
                    x, y = round(x * 4) / 4, round(y * 4) / 4
                    fp.SetPosition(pt(x, y))
                    if free(crt_box(fp), side):
                        hit = (rr, x, y, rot)
                        break
                if hit:
                    break
            if hit and (best is None or hit[0] < best[0]):
                best = hit
        if best is None:
            raise SystemExit(f'no room for {ref}')
        _, x, y, rot = best
        place(fp, x, y, rot, side)
        claim(fp, side)

    missing = [r for r in fps if r not in PLACE and r not in ANCHOR]
    if missing:
        raise SystemExit(f'not placed: {missing}')

    # GND planes: inner layers solid, outer layers GND pour
    gnd = netinfo['GND']
    for layer, prio in ((pcbnew.In1_Cu, 0), (pcbnew.In2_Cu, 0), (pcbnew.F_Cu, 0), (pcbnew.B_Cu, 0)):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetAssignedPriority(prio)
        z.SetLocalClearance(mm(0.25))
        z.SetMinThickness(mm(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.3))
        ol = z.Outline()
        ol.NewOutline()
        c = CORNER_R                               # chamfered so it stays inside the rounded corners
        for x, y in ((c, 0.2), (BOARD_W - c, 0.2), (BOARD_W - 0.2, c), (BOARD_W - 0.2, BOARD_L - c),
                     (BOARD_W - c, BOARD_L - 0.2), (c, BOARD_L - 0.2), (0.2, BOARD_L - c), (0.2, c)):
            ol.Append(mm(OX + x), mm(OY + y))
        z.SetZoneName('GND')
        board.Add(z)
    board.Save(str(PCB))
    # fill zones with KiCad's own filler and save (pcbnew's in-process fill misses some clearances)
    subprocess.run([str(KICAD / 'bin/kicad-cli.exe'), 'pcb', 'drc', '--refill-zones', '--save-board',
                    '-o', os.path.join(os.environ.get('TEMP', '.'), 'obd-v2x-gen_pcb.drc'), str(PCB)],
                   check=False, capture_output=True)
    print(f'wrote {PCB} ({len(fps)} footprints, {len(netinfo)} nets)')
    for side in (T, B):
        print(side, ' '.join(r for r, _ in placed[side]))


if __name__ == '__main__':
    if PCB.exists() and '--force' not in sys.argv:
        raise SystemExit(f'{PCB.name} exists; edit it in KiCad or re-run with --force (loses routing)')
    write_project_rules()
    build()
