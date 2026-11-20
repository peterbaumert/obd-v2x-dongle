"""Bootstrap one rev 2 board from its schematic: outline, rules, footprints with nets, first-pass placement,
GND pours.

Run with KiCad's bundled Python (it provides pcbnew):
    <KiCad>/bin/python rev2/hardware/tools/gen_pcb.py carrier|upper [--force]

The big parts are placed where rev2/mechanical/stack.py has them (PLACE). Every other part is put next to a
placed part it shares a net with: a starting point for the layout, not a finished placement (part heights under
the cell and around the plug legs are not considered).

A board is generated ONCE. After routing starts it is edited in KiCad (Tools > Update PCB from Schematic for
netlist changes). --force overwrites the board, including any routing.

Coordinates below are board-relative mm, top view: x right, y away from the OBD plug (front edge y = 0, rear edge
y = BOARD_L). Bottom-side parts are given in the same top-view frame. Both boards share the frame: a part of the
upper board lies above the same (x, y) of the carrier.
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
from kicad_env import CLI, FOOTPRINTS as STOCK_FP  # noqa: E402

BOARD = next((a for a in sys.argv[1:] if a in ('carrier', 'upper')), None)
if BOARD is None:
    raise SystemExit('usage: gen_pcb.py carrier|upper [--force]')
PROJECT = {'carrier': 'obd-v2x-carrier', 'upper': 'obd-v2x-upper'}[BOARD]
PCB = HW / BOARD / f'{PROJECT}.kicad_pcb'
SCH = HW / BOARD / f'{PROJECT}.kicad_sch'
PRO = HW / BOARD / f'{PROJECT}.kicad_pro'
LAYERS = {'carrier': 4, 'upper': 2}[BOARD]     # carrier: modem + LTE antenna line; upper: slow signals, short RF

OX, OY = 100.0, 50.0          # board origin on the page
BOARD_W, BOARD_L = 45.0, 45.0
CORNER_R = 1.5

T, B = 'top', 'bottom'
STACK_X = (4.7, 40.3)         # board-to-board connector centres (x): SMD pads end 0.6 mm inside the edge
STACK_Y = 18.15
SPACER = ((3.5, 4.0), (41.5, 4.0))
# ref: (x, y, rot, side) -- the parts that define the stack (see rev2/mechanical/stack.py)
PLACE = {
    'carrier': {
        # OBD plug: leg rows 1.9 / 4.9 mm behind the front edge, pin 1 at x 36.5 (plug centred on the board)
        'J201': (36.5, 1.9, 0, T),
        'H601': (*SPACER[0], 0, T), 'H602': (*SPACER[1], 0, T),
        'J601': (STACK_X[0], STACK_Y, 0, T), 'J602': (STACK_X[1], STACK_Y, 0, T),
        # Modem flat on the underside, long side along y, antenna pins at the rear, UART / status / supply pins on
        # its left side, SIM and power-key pins at the front and right. A strip on its left stays free for parts.
        'U401': (28.0, 26.5, 270, B),
        # underside strip left of the modem, front to rear: input chain from the plug's +12 V pin (x 8.5), level
        # shifter at the modem's UART pins, power mux at its supply pins
        'F101': (5.5, 8.3, 0, B),
        'D101': (6.0, 14.65, 90, B),           # input TVS (2.6 mm)
        'Q101': (6.0, 22.4, 0, B),
        'U101': (6.0, 27.6, 0, B),
        'U402': (6.0, 34.0, 90, B),
        'U502': (6.0, 39.6, 180, B),           # ILIM / soft-start pins towards the rear edge, where there is room
        # tall parts in the front half, between the sockets (the cell lies over the rear half, on parts <= 2.9 mm)
        'L101': (14.0, 11.0, 0, T),
        'U102': (13.6, 19.3, 0, T),            # buck right next to its inductor
        'J501': (30.55, 11.7, 270, T),         # battery, side entry: the plug goes in from the left (-x)
        'C401': (22.2, 19.0, 0, T),
        'C506': (31.25, 19.0, 0, T),
        # under the cell (parts up to 2.9 mm): the buck's diode in line with regulator and inductor, then the rest
        'D103': (14.6, 27.2, 0, T),
        'C107': (12.6, 33.2, 90, T), 'C108': (16.6, 33.2, 90, T),   # buck output capacitors (2.85 mm)
        'U103': (23.5, 27.0, 0, T),            # 3.3 V regulator
        'Q102': (23.5, 32.0, 0, T),
        'U405': (33.5, 34.0, 0, T),            # GNSS antenna bias switch, near J403
        # antenna sockets in the rear corners, beside the cell (a mated U.FL is 2.5 mm tall), each near its modem pin
        'J402': (4.0, 40.5, 0, T),             # LTE antenna
        'J403': (41.0, 40.5, 0, T),            # GNSS: jumper to J801 on the upper board
    },
    'upper': {
        'H701': (*SPACER[0], 0, T), 'H702': (*SPACER[1], 0, T),
        # headers on the bottom side, same rotation as the sockets: pin 1 lands on pin 1
        # through-hole headers on the bottom side: origin = pin 1, which lands on the socket's pin 1
        'J701': (STACK_X[0] + 1.27, STACK_Y - 8.89, 0, B), 'J702': (STACK_X[1] + 1.27, STACK_Y - 8.89, 0, B),
        'U301': (22.5, 17.5, 0, B),            # ESP32-C5 module
        'J301': (39.5, None, 0, B),            # USB-C at the rear edge (y set below)
        'J401': (8.0, 37.0, 0, B),             # micro-SIM, card enters from the left edge
        'AE801': (21.0, 29.5, 0, T),           # GNSS patch, clear of the USB-C legs; feed pin at (21.0, 32.0)
        'U801': (25.0, 33.5, 0, B),            # GNSS front end next to the feed pin
        'J801': (26.0, 40.5, 0, B),
        'U501': (37.0, 32.5, 0, B),            # cell charger; its NTC ends up over the cell
        # the lid side carries what must be reached or seen from outside
        'SW301': (12.5, 12.0, 0, T), 'SW302': (32.5, 12.0, 0, T), 'D301': (22.5, 3.0, 0, T),
        'U201': (14.0, 6.0, 0, T), 'U202': (31.0, 6.0, 0, T),
    },
}[BOARD]
# ref: (anchor ref, anchor pad, side or None): overrides the automatic choice (decoupling at the pin it serves)
ANCHOR = {
    'carrier': {
        'C101': ('U101', '1', None), 'C103': ('U102', '2', None), 'C104': ('U102', '1', None),
        'C105': ('U102', '6', None), 'C106': ('U102', '6', None), 'R106': ('U102', '6', None),
        'R101': ('U102', '3', None), 'R102': ('U102', '3', None), 'R103': ('U102', '4', None),
        'R104': ('U102', '5', None), 'R105': ('U102', '5', None),
        'R107': ('Q102', '1', None), 'Q103': ('Q102', '1', None), 'R108': ('Q102', '1', None),
        'C109': ('U103', '1', None), 'C110': ('U103', '5', None),
        'C402': ('U401', '59', T), 'C403': ('U401', '58', T), 'C404': ('U401', '57', T), 'C405': ('U401', '7', T),
        'C406': ('U402', '1', None),
        'C504': ('U502', '11', None), 'R507': ('U502', '10', None),
        'Q401': ('U401', '21', T), 'Q402': ('U401', '20', T),
        'R401': ('U401', '21', T), 'R402': ('U401', '21', T), 'R403': ('U401', '20', T), 'R404': ('U401', '20', T),
    },
    'upper': {},
}[BOARD]
# areas the automatic placement must leave free: (side, (x0, y0, x1, y1))
KEEP = {'carrier': [(T, (21.0, 8.0, 25.4, 15.5))],     # the battery plug in front of J501, and its wires
        'upper': []}[BOARD]
RAILS = ('GND', '+3V3', 'VSYS_3V8', 'VIN_PROT', 'VBAT_LTE', 'VBUCK_3V8', 'LTE_1V8', 'VCELL')

# Part heights (mm) by footprint name, for the automatic placement: data-sheet maxima where checked (1210, SMC, SMA,
# tantalum, U.FL mated, LED), typical values otherwise. A mated U.FL counts with its plug.
HEIGHT = {'C_0402': 0.55, 'C_0603': 0.9, 'C_0805': 1.35, 'C_1210': 2.85, 'CP_EIA-7343': 3.1, 'D_SMA': 2.62,
          'D_SMC': 2.62, 'D_SOD-123F': 1.1, 'D_SOD-323': 1.1, 'Fuse_1206': 0.8, 'LFPAK56': 1.1, 'L_0402': 0.6, 'R_0402': 0.4,
          'R_0603': 0.5, 'R_1206': 0.65, 'SOIC-8': 1.75, 'SOT-23': 1.45, 'TI_SO-PowerPAD-8': 1.7, 'TSSOP-20': 1.2,
          'TestPoint': 0.0, 'Texas_DRC': 1.0, 'Texas_VQFN': 1.0, 'U.FL': 2.5, 'LED_SK6812': 2.05,
          'Skyworks_SKY65943': 0.7}
HEIGHT_UNKNOWN = 2.0
# Room above each side (mm) and the zones with less: (side, x0, y0, x1, y1, room). See rev2/mechanical/stack.py.
ROOM = {
    'carrier': ({T: 7.0, B: 2.65},                      # top: under the ESP32 module; bottom: the modem's 2.6 mm
                [(T, 7.5, 24.0, 37.5, 44.0, 2.9)]),     # the cell lies on these parts
    'upper': ({T: 4.0, B: 3.6},                         # top: the patch's height; bottom: down to the cell
              [(B, 6.0, 0.0, 39.0, 6.6, 0.7)]),         # over the plug's leg bends (1.0 mm)
}[BOARD]


def height(fp):
    name = fp.GetFPID().GetLibItemName().wx_str()
    return next((h for k, h in HEIGHT.items() if name.startswith(k)), HEIGHT_UNKNOWN)


def room(bx, side):
    r = ROOM[0][side]
    for sd, x0, y0, x1, y1, lim in ROOM[1]:
        if sd == side and not (bx[2] <= x0 or x1 <= bx[0] or bx[3] <= y0 or y1 <= bx[1]):
            r = min(r, lim)
    return r


GAP = 0.3          # min gap between courtyards when auto-placing
SOLID_GND = {'U102', 'U401', 'U301', 'U801'}   # thermal / RF ground pads: solid zone connection
EDGE = 0.8         # keep courtyards this far inside the outline

# design rules (PCBWay standard 4-layer capability, with margin)
RULES = dict(track=0.15, clearance=0.15, via_d=0.6, via_drill=0.3, min_drill=0.3,
             annular=0.15, hole_to_hole=0.25, edge=0.3)


# the SKY65943-11's own pads are 0.225 mm apart, so the upper board's RF class cannot ask for more than 0.2
RF_GAP = 0.25 if BOARD == 'carrier' else 0.2
NETCLASSES = [
    # name, track, clearance, via_d, via_drill, net-name patterns
    # 0.4 mm on the carrier: 0.6 mm supply tracks do not fit between its parts. Short runs; widen by hand or with
    # pours where there is room.
    ('Power', 0.4 if BOARD == 'carrier' else 0.6, 0.2, 0.6, 0.3, ['OBD_VBAT', '*VBAT_F', 'VIN_PROT', 'VSYS_3V8', 'VBAT_LTE', 'Net-(D103-K)',
                                  'Net-(D202-K)', 'VBUCK_3V8', 'VCELL']),   # USB VBUS (<0.5 A) stays default class
    # 50 ohm grounded coplanar (0.32 mm, 0.25 mm gap) over In1 on PCBWay's standard 1.6 mm 4-layer stack-up
    # (7628 prepreg 0.186 mm, Dk ~4.4-4.7): designed to the stack-up, no paid impedance control.
    # On the 2-layer upper board 0.32 / 0.25 is not 50 ohm; its RF runs are a few mm, keep them short.
    ('RF', 0.32, RF_GAP, 0.6, 0.3, ['*LTE_ANT_*', 'Net-(J402-In)', 'Net-(J403-In)', 'Net-(J801-In)',
                                  'Net-(AE801-A)', 'Net-(U801-*)']),
]


def write_project_rules():
    import json
    d = json.loads(PRO.read_text(encoding='utf-8'))
    d.setdefault('board', {}).setdefault('design_settings', {})
    rules = d.setdefault('board', {}).setdefault('design_settings', {}).setdefault('rules', {})
    rules.update({
        'min_clearance': RULES['clearance'], 'min_track_width': RULES['track'],
        'min_via_diameter': RULES['via_d'], 'min_through_hole_diameter': RULES['min_drill'],
        'min_via_annular_width': RULES['annular'], 'min_hole_to_hole': RULES['hole_to_hole'],
        'min_copper_edge_clearance': RULES['edge'], 'min_hole_clearance': 0.25,
        'min_silk_clearance': 0.0, 'min_text_height': 0.8, 'min_text_thickness': 0.15,
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
    out = Path(os.environ.get('TEMP', '.')) / f'obd-v2x-rev2-{BOARD}.net'
    subprocess.run([str(CLI), 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
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
    if (side == B) != fp.IsFlipped():
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
    board.SetCopperLayerCount(LAYERS)
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
        big = ref in ('U401', 'U301', 'J201', 'J401', 'AE801')
        sz = mm(1.0 if big else 0.8)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(sz, sz))
        fp.Reference().SetTextThickness(mm(0.15))   # PCBWay: silk character stroke >= 0.15 mm
        board.Add(fp)
        fps[ref] = fp

    placed = {T: [], B: []}
    for side, bx in KEEP:
        placed[side].append(('keep-out', bx))

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
    def free(bx, side, h=0.0):
        if not inside(bx) or h > room(bx, side):
            return False
        return all(not overlaps(bx, o) for _, o in placed[side])

    def spiral(fp, ax, ay, side):
        """nearest free spot around (ax, ay) on one side: (distance, x, y, rot) or None"""
        best = None
        h = height(fp)
        for rot in (0, 90):
            place(fp, ax, ay, rot, side)
            hit = None
            for ring in range(0, 120):
                rr = ring * 0.5
                steps = max(1, int(2 * math.pi * rr / 0.5))
                for s in range(steps):
                    a = 2 * math.pi * s / steps
                    x, y = ax + rr * math.cos(a), ay + rr * math.sin(a)
                    x, y = round(x * 4) / 4, round(y * 4) / 4
                    fp.SetPosition(pt(x, y))
                    if free(crt_box(fp), side, h):
                        hit = (rr, x, y, rot)
                        break
                if hit:
                    break
            if hit and (best is None or hit[0] < best[0]):
                best = hit
        return best

    def anchor_of(ref):
        """a pad of an already placed part on one of this part's nets: signal nets first, then rails"""
        done = {r for side in placed.values() for r, _ in side}
        for rails in (False, True):
            for p in fps[ref].Pads():
                n = nets.get((ref, p.GetNumber()))
                if not n or n == 'GND' or (n in RAILS) != rails:
                    continue
                cands = [(r2, pin2) for (r2, pin2), n2 in nets.items() if n2 == n and r2 != ref and r2 in done]
                if cands:
                    cands.sort(key=lambda c: (c[0] not in PLACE, c[0]))
                    return cands[0]
        return None

    todo = [r for r in fps if r not in PLACE]
    while todo:
        progress = False
        for ref in list(todo):
            if ref in ANCHOR:
                aref, apad, side = ANCHOR[ref]
            else:
                a = anchor_of(ref)
                if a is None:
                    continue
                (aref, apad), side = a, None
            fp = fps[ref]
            side = side or (B if fps[aref].IsFlipped() else T)
            ax, ay = pad_xy(fps[aref], apad)
            best, used = None, side
            for sd in (side, B if side == T else T):          # the anchor's side first, then the other one
                hit = spiral(fp, ax, ay, sd)
                if hit and (best is None or hit[0] + (0 if sd == side else 6) < best[0]):
                    best, used = (hit[0] + (0 if sd == side else 6), *hit[1:]), sd
                if hit and sd == side and hit[0] <= 8:
                    break
            if best is None:
                raise SystemExit(f'no room for {ref} (anchor {aref}.{apad} at {ax:.1f}, {ay:.1f}, part height {height(fp)})')
            _, x, y, rot = best
            place(fp, x, y, rot, used)
            claim(fp, used)
            todo.remove(ref)
            progress = True
        if not progress:                                      # parts on rails only, or on nothing: board centre
            for ref in todo:
                fp = fps[ref]
                hit = spiral(fp, BOARD_W / 2, BOARD_L / 2, T) or spiral(fp, BOARD_W / 2, BOARD_L / 2, B)
                if hit is None:
                    raise SystemExit(f'no room for {ref} at the board centre (part height {height(fp)})')
                place(fp, hit[1], hit[2], hit[3], T)
                claim(fp, T)
            todo = []

    # GND pours on every copper layer
    gnd = netinfo['GND']
    zone_layers = [pcbnew.F_Cu, pcbnew.B_Cu] + ([pcbnew.In1_Cu, pcbnew.In2_Cu] if LAYERS == 4 else [])
    for layer, prio in [(l, 0) for l in zone_layers]:
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
    subprocess.run([str(CLI), 'pcb', 'drc', '--refill-zones', '--save-board',
                    '-o', os.path.join(os.environ.get('TEMP', '.'), f'obd-v2x-rev2-{BOARD}.drc'), str(PCB)],
                   check=False, capture_output=True)
    print(f'wrote {PCB} ({len(fps)} footprints, {len(netinfo)} nets)')
    for side in (T, B):
        print(side, ' '.join(r for r, _ in placed[side]))


if __name__ == '__main__':
    if PCB.exists() and '--force' not in sys.argv:
        raise SystemExit(f'{PCB.name} exists; edit it in KiCad or re-run with --force (loses routing)')
    write_project_rules()
    build()
