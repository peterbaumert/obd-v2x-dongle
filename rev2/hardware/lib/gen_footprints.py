"""Generate project footprints in rev2/hardware/lib/obd-v2x.pretty.

  python rev2/hardware/lib/gen_footprints.py

Quectel_EC200U: from Quectel EC200U Series QuecOpen Hardware Design V1.0,
  Figure 2 (Pin Assignment, top view) and Figure 39 (Recommended Footprint, top view).
  Module 31.0 x 28.0 mm, footprint extent 34.3 x 31.3 mm, 80 LCC + 64 LGA pads.
  Origin = module centre, x right, y down (top view).

OBD2_J1962_Plug_PCB: Jiatel CR-PG001 90 deg plug drawing (see obd_plug()).

LED_SK6812MINI-HS_3.7x3.5mm: OPSCO SK6812MINI-HS datasheet Rev. B/0, section 6 (recommended pads, top view).

microSIM_Molex_78646-3001, Skyworks_SKY65943-11_MCM-10_2.5x2.5mm, Antenna_Taoglas_CGGBP.25.4.A.02: rev 2 parts,
  sources in their functions' docstrings.

ESP32-C5-WROOM-1U.kicad_mod is vendored from espressif/kicad-libraries (CC-BY-SA 4.0 with
the KiCad design exception), not generated here.
"""
import math
import uuid
from pathlib import Path

OUT = Path(__file__).with_name('obd-v2x.pretty')


def uid(seed):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'obd-v2x-fp/' + seed))


def f(v):
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s == '-0' else s


def pad(num, shape, x, y, w, h, rot=0, extra=''):
    r = f' {rot}' if rot else ''
    return (f'\t(pad "{num}" smd {shape} (at {f(x)} {f(y)}{r}) (size {f(w)} {f(h)}) '
            f'(layers "F.Cu" "F.Mask" "F.Paste"){extra} (uuid "{uid(f"{num}/{x}/{y}")}"))\n')


def line(x1, y1, x2, y2, layer, w):
    return (f'\t(fp_line (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (stroke (width {w}) (type solid)) '
            f'(layer "{layer}") (uuid "{uid(f"{layer}{x1}{y1}{x2}{y2}")}"))\n')


def rect(x1, y1, x2, y2, layer, w):
    return (line(x1, y1, x2, y1, layer, w) + line(x2, y1, x2, y2, layer, w) +
            line(x2, y2, x1, y2, layer, w) + line(x1, y2, x1, y1, layer, w))


def prop(key, val, x, y, layer, hide=False, size=1.0):
    h = ' (hide yes)' if hide else ''
    return (f'\t(property "{key}" "{val}" (at {f(x)} {f(y)} 0) (layer "{layer}"){h} (uuid "{uid(key)}")\n'
            f'\t\t(effects (font (size {size} {size}) (thickness {size * 0.15:.3f})))\n\t)\n')


def footprint(name, desc, tags, ref_y, body):
    return (f'(footprint "{name}"\n\t(version 20241229)\n\t(generator "obd-v2x-gen_footprints")\n'
            f'\t(generator_version "1.0")\n\t(layer "F.Cu")\n'
            f'\t(descr "{desc}")\n\t(tags "{tags}")\n'
            + prop('Reference', 'REF**', 0, -ref_y, 'F.SilkS')
            + prop('Value', name, 0, ref_y, 'F.Fab')
            + prop('Datasheet', '', 0, 0, 'F.Fab', True)
            + prop('Description', desc, 0, 0, 'F.Fab', True)
            + '\t(attr smd)\n' + body + ')\n')


# ------------------------------------------------------------------ EC200U
def ec200u():
    MOD_W, MOD_H = 31.0, 28.0          # module body (x, y)
    EXT_W, EXT_H = 34.3, 31.3          # outer extent of the LCC pads
    L = 2.5                            # LCC pad length
    W = 0.8                            # LCC pad width
    P = 1.3                            # LCC pitch
    body = ''
    # side pads (left / right): 7 + 13, pitch 1.3, 1.8 between groups; last pad 1.25 from bottom edge
    ys_bot = [MOD_H / 2 - 1.25 - P * i for i in range(13)][::-1]       # -2.85 .. 12.75
    ys_top = [ys_bot[0] - 1.8 - P * i for i in range(7)][::-1]         # -12.45 .. -4.65
    side_y = ys_top + ys_bot                                           # top -> bottom, 20
    xs = EXT_W / 2 - L / 2
    left = [1, 2, 3, 4, 5, 6, 7, 141, 142, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    right = [54, 53, 52, 51, 50, 49, 48, 144, 143, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37]
    for n, y in zip(left, side_y):
        body += pad(n, 'oval', -xs, y, L, W)
    for n, y in zip(right, side_y):
        body += pad(n, 'oval', xs, y, L, W)
    # top / bottom pads: 20, pitch 1.3, last pad 2.95 from the right module edge
    x_last = MOD_W / 2 - 2.95
    tb_x = [x_last - P * (19 - i) for i in range(20)]                  # -12.15 .. 12.55
    ys = EXT_H / 2 - L / 2
    top = [114, 113, 72, 71, 70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 59, 58, 57, 56, 55]
    bot = [116, 115, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36]
    for n, x in zip(top, tb_x):
        body += pad(n, 'oval', x, -ys, W, L)
    for n, x in zip(bot, tb_x):
        body += pad(n, 'oval', x, ys, W, L)
    # inner small-pad columns: 1.1 sq, 2.5 / 4.5 mm in from the left module edge, rows pitch 2.0
    rows12 = [-11 + 2 * i for i in range(12)]
    for n, y in zip(range(129, 141), rows12):
        body += pad(n, 'rect', -MOD_W / 2 + 2.5, y, 1.1, 1.1)
    for n, y in zip(range(117, 129), rows12):
        body += pad(n, 'rect', -MOD_W / 2 + 4.5, y, 1.1, 1.1)
    # large LGA pads 2.0 x 3.0 (ground), columns 3.2/3.4/3.2/3.4/3.2, rows pitch 4.8
    cols = [-8.2, -5.0, -1.6, 1.6, 5.0, 8.2]
    rows = [-9.6, -4.8, 0, 4.8, 9.6]
    big = [[108, 103, 99, 95, 90, 85],
           [109, 104, 100, 96, 91, 86],
           [110, 105, None, None, 92, 87],
           [111, 106, 101, 97, 93, 88],
           [112, 107, 102, 98, 94, 89]]
    for r, y in zip(big, rows):
        for n, x in zip(r, cols):
            if n:
                body += pad(n, 'rect', x, y, 2.0, 3.0)
    # centre 4 x 3 cluster, 1.1 sq, pitch 1.6
    centre = [[82, 79, 76, 73], [83, 80, 77, 74], [84, 81, 78, 75]]
    for r, y in zip(centre, [-1.6, 0, 1.6]):
        for n, x in zip(r, [-2.4, -0.8, 0.8, 2.4]):
            body += pad(n, 'rect', x, y, 1.1, 1.1)
    # graphics
    hx, hy = MOD_W / 2, MOD_H / 2
    body += rect(-hx, -hy, hx, hy, 'F.Fab', 0.1)
    body += line(-hx, -hy + 1.5, -hx + 1.5, -hy, 'F.Fab', 0.1)
    cx, cy = EXT_W / 2 + 0.5, EXT_H / 2 + 0.5
    body += rect(-cx, -cy, cx, cy, 'F.CrtYd', 0.05)
    # silk: corner marks outside the pad extent + pin-1 arrow
    sx, sy, k = EXT_W / 2 + 0.2, EXT_H / 2 + 0.2, 1.5
    for ax, ay in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        body += line(ax * sx, ay * sy, ax * (sx - k), ay * sy, 'F.SilkS', 0.15)
        body += line(ax * sx, ay * sy, ax * sx, ay * (sy - k), 'F.SilkS', 0.15)
    p1y = side_y[0]
    body += line(-sx - 0.8, p1y - 0.5, -sx - 0.2, p1y, 'F.SilkS', 0.15)
    body += line(-sx - 0.2, p1y, -sx - 0.8, p1y + 0.5, 'F.SilkS', 0.15)
    body += line(-sx - 0.8, p1y + 0.5, -sx - 0.8, p1y - 0.5, 'F.SilkS', 0.15)
    n_pads = body.count('(pad ')
    assert n_pads == 144, n_pads
    return footprint('Quectel_EC200U',
                     'Quectel EC200U LTE Cat 1 module, LCC+LGA-144, 31.0x28.0 mm. '
                     'Quectel EC200U Series QuecOpen Hardware Design V1.0, Figure 39',
                     'Quectel EC200U LTE LCC LGA', cy + 1.2, body)


# ------------------------------------------------------------------ OBD-II 90 deg PCB plug
def tht(num, x, y, drill, dia, shape='circle'):
    return (f'\t(pad "{num}" thru_hole {shape} (at {f(x)} {f(y)}) (size {f(dia)} {f(dia)}) (drill {f(drill)}) '
            f'(layers "*.Cu" "*.Mask") (uuid "{uid(f"obd{num}")}"))\n')


def obd_plug():
    """J1962 male plug, 90 deg THT (Jiatel CR-PG001 drawing, same mould sold widely as
    'OBD2 16 pin male 90 degree PCB'). Hole pattern: 2 x 8, pitch 4.00, rows 3.00 apart, hole 1.35 +0.1.

    Origin = pin 1. Mating face points to -y (towards the board edge / car socket).
    Row y=0 (nearer the housing) = pins 1..8, row y=+3 = pins 9..16, pin n and n+8 aligned.
    Pin 1 at x=0, pin 8 at x=-28 (top view). From the drawing: top view numbers the outer tails 9..16,
    section A-A shows the contact row nearer the board bending into the leg row nearer the housing.
    The drawing's 5.65 runs from the housing rear face to the OUTER edge of the 0.8 mm outer leg (checked in the
    PDF's vector data, top view and section A-A agree): leg centres 5.25 / 2.25 behind the rear face.
    The leg tips end level with the housing bottom (3.97 mm straight below the bend), so the housing sits lower
    than the board top and must be fully in front of the board edge (board edge 0.35 behind the rear face).
    Housing (drawing): rear flange 37.6 x 17.2 x 2.0, groove 2.0 (neck 33.6 x 14.0), D-shaped body 40.26 wide
    (37.4 on the key side) x 17.8 x 16.0 with a 13 x 1.5 key bump.
    """
    P, ROW, DRILL, DIA = 4.0, 3.0, 1.45, 2.3
    body = ''
    for k in range(8):
        x = -P * k
        body += tht(k + 1, x, 0, DRILL, DIA, 'rect' if k == 0 else 'circle')
        body += tht(k + 9, x, ROW, DRILL, DIA)
    cx = -P * 3.5                                   # centre between pin 1 and pin 8
    hw = 40.26 / 2                                  # housing (body) width
    rear = -(5.25 - ROW)                            # housing rear face, 5.25 from the outer leg row centres
    front = rear - 20.0                             # housing / shroud front (20.0 deep)
    body += rect(cx - hw, front, cx + hw, rear, 'F.Fab', 0.1)
    # courtyard: the housing (in front of the board edge), and behind it only the two leg rows, so parts and the
    # spacer holes can sit in the board's front corners beside the legs
    x0, x1, xa, xb = cx - hw - 0.5, cx + hw + 0.5, -P * 7 - DIA / 2 - 0.5, DIA / 2 + 0.5
    y0, y1, y2 = front - 0.5, rear + 0.5, ROW + DIA / 2 + 0.5
    pts = [(x0, y0), (x1, y0), (x1, y1), (xb, y1), (xb, y2), (xa, y2), (xa, y1), (x0, y1)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        body += line(ax, ay, bx, by, 'F.CrtYd', 0.05)
    # silk: pin-1 marker only (the housing sits off the board, in front of its edge)
    body += line(1.8, -1.8, 1.8, 1.8, 'F.SilkS', 0.15)
    body += line(cx - hw, front + 2, cx + hw, front + 2, 'F.Fab', 0.1)
    assert body.count('(pad ') == 16
    return footprint('OBD2_J1962_Plug_PCB',
                     'OBD-II SAE J1962 male plug, 16 pin, 90 deg THT, 2x8 P4.00 rows 3.00. '
                     'Jiatel CR-PG001 drawing. Mating face towards -y, housing rear face 2.25 in front of pin 1',
                     'OBD OBD2 J1962 plug connector', 26, body)


def sk6812mini_hs():
    """OPSCO SK6812MINI-HS, body 3.7 x 3.5 mm. Recommended land (datasheet section 6, top view):
    pads 1.5 x 1.0, 1.8 apart in x, 0.8 apart in y. Pin 1 (GND) = chamfered corner, bottom right:
    3 VDD top left, 2 DIN top right, 1 GND bottom right, 4 DOUT bottom left."""
    X, Y, W, H = 1.65, 0.9, 1.5, 1.0
    body = (pad(3, 'rect', -X, -Y, W, H) + pad(2, 'rect', X, -Y, W, H) +
            pad(1, 'rect', X, Y, W, H) + pad(4, 'rect', -X, Y, W, H))
    bx, by, ch = 1.85, 1.75, 0.6
    body += (line(-bx, -by, bx, -by, 'F.Fab', 0.1) + line(bx, -by, bx, by - ch, 'F.Fab', 0.1) +
             line(bx, by - ch, bx - ch, by, 'F.Fab', 0.1) + line(bx - ch, by, -bx, by, 'F.Fab', 0.1) +
             line(-bx, by, -bx, -by, 'F.Fab', 0.1))
    sy = by + 0.15                                   # silk outside the body, clear of the pads
    body += (line(-bx, -sy, bx, -sy, 'F.SilkS', 0.15) + line(-bx, sy, 2.2, sy, 'F.SilkS', 0.15) +
             line(2.2, sy, 2.6, sy - 0.4, 'F.SilkS', 0.15))   # corner tick = pin 1 (chamfered corner), clear of pad 1
    body += rect(-2.75, -2.1, 2.75, 2.1, 'F.CrtYd', 0.05)
    assert body.count('(pad ') == 4
    return footprint('LED_SK6812MINI-HS_3.7x3.5mm',
                     'OPSCO SK6812MINI-HS RGB LED 3.7 x 3.5 mm, top-emitting; pins 1 GND, 2 DIN, 3 VDD, 4 DOUT '
                     '(datasheet Rev. B/0 recommended land)',
                     'LED RGB SK6812 SK6812MINI-HS', 3.0, body)


def microsim_molex():
    """Molex 78646-3001 micro-SIM connector, push in / pull out, 1.45 mm high.
    Molex sales drawing SD-78646-001 rev C1, sheet 2 (recommended PCB layout), read from the Farnell copy.
    Origin = centre of the connector boundary (15.45 x 12.65). The card enters from +x (the side with the two
    large shell pads) and slides towards the contact tails at -x. Drawing y is up: negated here.
    Pads carry the ISO contact numbers (1 VCC, 2 RST, 3 CLK, 5 GND, 6 VPP, 7 I/O) as KiCad's SIM_Card symbols use.
    The two hold-down pads X1 / X2 are NOT ground: the drawing links X1 to C1 (VCC) and X2 to C3 (CLK), so they
    are numbered 1 and 3. The case needs a card stop 0.5 mm outside the +x edge (no latch in the connector)."""
    sx, w, h = -7.295, 1.15, 0.65
    body = ''
    for num, y in ((5, 4.025), (1, 2.755), (6, 1.485), (2, 0.215), (7, -1.055), (3, -2.325)):
        body += pad(num, 'rect', sx, -y, w, h)
    for y in (6.105, -6.105):
        body += pad('SH', 'rect', 6.435, -y, 1.70, 1.40)
    for x in (-3.125, -5.125):
        for y in (6.27, -6.27):
            body += pad('SH', 'rect', x, -y, 1.30, 0.45)
    body += pad(1, 'rect', 5.855, -2.54, 0.80, 0.54)          # X1, linked to C1 inside the connector
    body += pad(3, 'rect', 5.855, 2.54, 0.80, 0.54)           # X2, linked to C3
    bx, by = 7.725, 6.325
    body += rect(-bx, -by, bx, by, 'F.Fab', 0.1)
    body += line(bx, -by, bx + 3.0, -by, 'F.Fab', 0.1) + line(bx, by, bx + 3.0, by, 'F.Fab', 0.1)   # card side
    body += line(-bx, -5.3, -bx, -by - 0.15, 'F.SilkS', 0.15) + line(-bx, -by - 0.15, -6.0, -by - 0.15, 'F.SilkS', 0.15)
    body += line(-2.2, -by - 0.15, 5.3, -by - 0.15, 'F.SilkS', 0.15) + line(-2.2, by + 0.15, 5.3, by + 0.15, 'F.SilkS', 0.15)
    body += rect(-8.4, -7.3, 8.25, 7.3, 'F.CrtYd', 0.05)
    assert body.count('(pad ') == 14
    return footprint('microSIM_Molex_78646-3001',
                     'Molex 78646-3001 micro-SIM connector, push in / pull out, 6 contacts, 1.45 mm high; card enters '
                     'from +x. Pads 1 and 3 near +x are the hold-downs the drawing links to VCC and CLK '
                     '(SD-78646-001 rev C1)', 'SIM micro-SIM 3FF card connector Molex 78646', 8.4, body)


def sky65943():
    """Skyworks SKY65943-11 GNSS front end (SAW + LNA + SAW), MCM-10, 2.5 x 2.5 x 0.65 mm.
    Data sheet 204404H, Figure 7 (PCB metallization, top view): pads 0.425 wide at x +-1.1875, rows at y 0, +-0.5
    (0.275 high) and +-1.1435 (0.515 high); pins 1-5 down the left side, 10-6 down the right. Drawing y is up:
    negated here. Centre ground copper 1.45 wide (0.25 to the pads) over the package height = pad 11.
    Paste on the centre pad as three apertures, the data sheet's stencil (1.4 x 0.745 / 0.67 / 0.745). The data sheet shows 8 filled thermal vias (0.3 mm, 0.6 pitch)
    in the centre pad: optional, add them in the layout."""
    px = 1.1875
    rows = ((1, -px, 1.1435, 0.515), (2, -px, 0.5, 0.275), (3, -px, 0.0, 0.275), (4, -px, -0.5, 0.275),
            (5, -px, -1.1435, 0.515), (6, px, -1.1435, 0.515), (7, px, -0.5, 0.275), (8, px, 0.0, 0.275),
            (9, px, 0.5, 0.275), (10, px, 1.1435, 0.515))
    body = ''.join(pad(n, 'rect', x, -y, 0.425, h) for n, x, y, h in rows)
    body += (f'\t(pad "11" smd rect (at 0 0) (size 1.45 2.4) (layers "F.Cu" "F.Mask") (uuid "{uid("sky/ep")}"))\n')
    for i, (y, h) in enumerate(((-0.82, 0.745), (0, 0.67), (0.82, 0.745))):
        body += (f'\t(pad "" smd rect (at 0 {f(y)}) (size 1.4 {f(h)}) (layers "F.Paste") (uuid "{uid(f"sky/paste{i}")}"))\n')
    b = 1.25
    body += rect(-b, -b, b, b, 'F.Fab', 0.1)
    body += line(-b, -b + 0.5, -b + 0.5, -b, 'F.Fab', 0.1)                       # pin 1 corner
    body += line(-1.75, -1.75, -1.0, -1.75, 'F.SilkS', 0.15)                     # pin 1 mark, clear of the pads
    body += rect(-1.7, -1.7, 1.7, 1.7, 'F.CrtYd', 0.05)
    assert body.count('(pad ') == 14
    return footprint('Skyworks_SKY65943-11_MCM-10_2.5x2.5mm',
                     'Skyworks SKY65943-11 GNSS front-end module (pre-filter, LNA, post-filter), MCM-10 2.5 x 2.5 mm, '
                     'centre ground pad 11 (data sheet 204404H Figure 7)', 'GNSS LNA SAW front end Skyworks SKY65943',
                     2.8, body)


def gnss_patch():
    """Taoglas CGGBP.25.4.A.02 ceramic GNSS patch, 25.1 x 25.1 x 4 mm, pin-fed, stuck down with its adhesive.
    Data sheet SPE-14-8-071-G p.6 / p.9-10: feed pin 0.9 mm (max 1.05), 2.5 mm off centre towards the edge with the
    part marking (+y here); recommended hole 1.0, pads 1.2 top / 2.2 bottom; ground copper cleared 3.0 mm around the
    pin on the top and inner layers and 3.5 mm on the bottom layer. Here: hole 1.1 (the pin tolerance exceeds 1.0),
    1.4 mm pad on all layers (data sheet 1.2; 1.4 keeps the 0.15 mm annular ring PCBWay needs) plus a 2.2 mm pad on B.Cu for the hand-soldered fillet, and the clearances as rule
    areas in the footprint (no pour, no vias; the feed track itself is allowed). The patch is tuned on a 70 x 70 mm ground plane; keep ground under the whole patch: a rule area keeps
    tracks off F.Cu under the body.
    The pin is soldered by hand on the bottom side after reflow."""
    body = (f'\t(pad "1" thru_hole circle (at 0 2.5) (size 1.4 1.4) (drill 1.1) (layers "*.Cu" "F.Mask") '
            f'(uuid "{uid("patch/1")}"))\n'
            f'\t(pad "1" smd circle (at 0 2.5) (size 2.2 2.2) (layers "B.Cu" "B.Mask") (uuid "{uid("patch/1b")}"))\n')
    for d, layers in ((3.0, '"F.Cu" "In1.Cu" "In2.Cu"'), (3.5, '"B.Cu"')):
        pts = ' '.join(f'(xy {f(d / 2 * math.cos(2 * math.pi * i / 32))} {f(2.5 + d / 2 * math.sin(2 * math.pi * i / 32))})'
                       for i in range(32))
        body += (f'\t(zone (net 0) (net_name "") (layers {layers}) (uuid "{uid(f"patch/keep{d}")}") '
                 f'(name "patch feed clearance") (hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25) '
                 f'(filled_areas_thickness no) (keepout (tracks allowed) (vias not_allowed) (pads allowed) '
                 f'(copperpour not_allowed) (footprints allowed)) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
                 f'(polygon (pts {pts})))\n')
    # the patch's ground plane: no tracks on F.Cu under the body (pour, pads and GND vias stay allowed)
    g = 12.55
    body += (f'\t(zone (net 0) (net_name "") (layers "F.Cu") (uuid "{uid("patch/ground")}") '
             f'(name "patch ground plane") (hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25) '
             f'(filled_areas_thickness no) (keepout (tracks not_allowed) (vias allowed) (pads allowed) '
             f'(copperpour allowed) (footprints allowed)) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
             f'(polygon (pts (xy {-g} {-g}) (xy {g} {-g}) (xy {g} {g}) (xy {-g} {g}))))\n')
    for d, layer in ((3.0, 'Cmts.User'), (3.5, 'Dwgs.User')):
        body += (f'\t(fp_circle (center 0 2.5) (end {f(d / 2)} 2.5) (stroke (width 0.1) (type solid)) '
                 f'(layer "{layer}") (uuid "{uid(f"patch/c{d}")}"))\n')
    b = 12.55
    body += rect(-b, -b, b, b, 'F.Fab', 0.1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            body += line(sx * (b + 0.15), sy * (b + 0.15), sx * (b - 3), sy * (b + 0.15), 'F.SilkS', 0.15)
            body += line(sx * (b + 0.15), sy * (b + 0.15), sx * (b + 0.15), sy * (b - 3), 'F.SilkS', 0.15)
    body += rect(-b - 0.4, -b - 0.4, b + 0.4, b + 0.4, 'F.CrtYd', 0.05)
    fp = footprint('Antenna_Taoglas_CGGBP.25.4.A.02',
                   'Taoglas CGGBP.25.4.A.02 GNSS ceramic patch 25 x 25 x 4 mm, pin-fed (feed 2.5 mm off centre, +y), '
                   'adhesive mount; clear ground copper 3.0 mm (top, inner) / 3.5 mm (bottom) around the pin',
                   'GNSS GPS GLONASS Galileo BeiDou patch antenna Taoglas', 13.8, body)
    return fp.replace('\t(attr smd)\n', '\t(attr through_hole)\n')


if __name__ == '__main__':
    for name, fn in (('Quectel_EC200U', ec200u), ('OBD2_J1962_Plug_PCB', obd_plug),
                     ('LED_SK6812MINI-HS_3.7x3.5mm', sk6812mini_hs),
                     ('microSIM_Molex_78646-3001', microsim_molex),
                     ('Skyworks_SKY65943-11_MCM-10_2.5x2.5mm', sky65943),
                     ('Antenna_Taoglas_CGGBP.25.4.A.02', gnss_patch)):
        p = OUT / f'{name}.kicad_mod'
        p.write_text(fn(), encoding='utf-8')
        print('wrote', p)
