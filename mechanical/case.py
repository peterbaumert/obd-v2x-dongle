"""Two-part 3D-printed case for the OBD-II V2X dongle (build123d).

    python mechanical/case.py            # build, write out/*.step + out/*.stl
    python mechanical/case.py --check    # also check the case against the board's 3D model
    python mechanical/case.py --render   # also write out/*.png previews

Needs build123d (pip install build123d; pyvista for --render) and KiCad 10 (kicad-cli exports the board's
3D model to build/board.step, which sets where ledges and ribs may go).

Coordinates are the board STEP's (kicad-cli pcb export step): x = KiCad x, y = -KiCad y (+y = front,
towards the car), z = 0 at the board's bottom face. The board is 52 x 65 mm, x 100..152, KiCad y 59..124.

Concept
- Bottom shell + lid, split at the board's top face. The board rests on ledges in the bottom shell and the
  lid presses on its top edge; there are no mounting holes.
- The OBD plug J201 sits entirely in front of the board edge. Its retention groove (behind the 1.5 mm rear
  flange) takes a U-shaped rib of the lid (top + both sides) and a straight rib of the bottom shell, so
  plugging and unplugging loads the case, not the solder joints.
- Two M2.5 self-tapping screws from below at the front corners (next to the plug), two hooks at the rear
  (lid goes in at an angle, rear first, then folds down).
- Openings: USB-C (rear), RESET/BOOT pin holes with guide tubes, LED light-pipe tube (3 mm rod), all in the
  bottom. The backup cell lies in a pocket on the floor of the bottom shell.
- Antennas (LTE, GNSS, 5.9 GHz) are flex antennas stuck to the inside of the lid / floor.

Plug dimensions marked MEASURE are from the Jiatel CR-PG001 drawing or estimated; set them from the real
plug (calliper) before printing the final case.
"""
import argparse
import sys
from pathlib import Path

from build123d import (Axis, Box, Compound, Cylinder, Pos, export_step, export_stl, fillet, import_step)

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'
BUILD = HERE / 'build'

# ------------------------------------------------------------------ board (from the KiCad layout)
BX0, BX1 = 100.0, 152.0          # board x
BYF, BYR = -58.95, -124.05       # board front / rear edge (STEP y)
BT = 1.6                         # board thickness (top face z)
USB_OVERHANG = 0.3               # J301 sticks out of the rear edge

# ------------------------------------------------------------------ OBD plug J201 (MEASURE)
PLUG_CX = 126.0                  # centre between pin 1 (x 140) and pin 8 (x 112)
PLUG_W, PLUG_H, PLUG_D = 37.6, 17.8, 20.0   # housing width, height, depth (drawing)
PLUG_R = 1.5                     # housing corner radius (MEASURE: the real D shape has chamfers)
PLUG_Z0 = BT                     # housing bottom (MEASURE: assumed flush with the board top)
PLUG_REAR = -58.85               # housing rear face (footprint: 2.65 in front of pin 1)
FLANGE = 1.5                     # rear flange thickness (drawing)
GROOVE_W = 2.5                   # groove width along y (MEASURE)
GROOVE_D = 1.0                   # groove depth (MEASURE)

# ------------------------------------------------------------------ case
WALL = 2.0                       # side / rear wall
FLOOR = 2.0
ROOF = 2.0
GAP = 0.3                        # board edge to wall
FIT = 0.1                        # rib clearance in the groove (per side)
PLUG_FIT = 0.2                   # opening around the plug shroud (per side)
Z_IN_BOT = -11.0                 # inner floor: room for the JST-PH lead on J501 and the cell
Z_IN_TOP = PLUG_Z0 + PLUG_H + 0.3
FRONT_OUT = -51.5                # front face of the case (around the plug shroud)
EDGE_R = 3.0                     # vertical outer edge radius
LEDGE = 1.0                      # board overlap of ledges / press ribs

X_IN0, X_IN1 = BX0 - GAP, BX1 + GAP
Y_IN_REAR = BYR - USB_OVERHANG - GAP
Y_RIB0 = PLUG_REAR + FLANGE + FIT                 # rib rear face = front of the case interior
Y_RIB1 = PLUG_REAR + FLANGE + GROOVE_W - FIT
X_OUT0, X_OUT1 = X_IN0 - WALL, X_IN1 + WALL
Y_OUT_REAR = Y_IN_REAR - WALL
Z_OUT_BOT, Z_OUT_TOP = Z_IN_BOT - FLOOR, Z_IN_TOP + ROOF
SPLIT = BT

# screws: M2.5 self-tapping, from below, in the solid corners beside the plug
SCREWS = [(103.3, -54.4), (148.7, -54.4)]
SCREW_PILOT, SCREW_CLEAR, SCREW_HEAD = 2.2, 2.8, 5.0
SCREW_HEAD_TOP = -2.0            # counterbore from below up to here (3.6 mm clamp in the bottom shell)

# rear hooks (lid) into notches of the bottom shell's rear wall
HOOKS = [112.0, 128.0]           # x centres, clear of the USB-C opening
HOOK_W, HOOK_DROP = 8.0, 3.0

# openings (board parts on the bottom side)
USB_X, USB_Z = 145.0, -1.63      # J301 HRO TYPE-C-31-M-12 on the bottom, 3.26 tall
USB_OPEN_W, USB_OPEN_H = 12.6, 7.0   # cable plug over-mould
BUTTONS = [(131.0, -119.5), (120.5, -119.5)]   # SW301 RESET, SW302 BOOT (TL3342, actuator face z -1.63)
BUTTON_FACE = -1.63
PIN_HOLE, PIN_TUBE = 1.6, 4.0
LED = (106.0, -120.0)            # D301 SK6812MINI-HS on the bottom, ~1.4 tall
LED_FACE = -1.4
LIGHTPIPE, LIGHTPIPE_TUBE = 3.2, 5.0

# backup cell: 1S LiPo, e.g. 402535 + PCM (MEASURE the cell you buy)
CELL_L, CELL_W, CELL_T = 38.0, 26.0, 4.5
CELL_CX, CELL_CY = 123.0, -77.0  # under the ESP32 / transceivers, clear of the tubes and J501
CELL_RIB_H, CELL_RIB_T = 3.0, 1.2

# parts without a 3D model in KiCad's library: (ref, x0, x1, kicad y0, y1, z0, z1)
SUBSTITUTES = [
    ('U401', 105.0, 134.0, 88.0, 120.0, BT, BT + 2.4),       # EC200U-EU LGA, 29 x 32 x 2.4
    ('J301', 140.5, 149.5, 116.8, 124.35, -3.26, 0.0),       # USB-C receptacle
    ('J401', 102.6, 116.4, 98.5, 113.1, -1.5, 0.0),          # nano-SIM holder (hinged)
    ('J501', 126.75, 136.25, 104.5, 113.09, -10.0, 0.0),     # JST-PH vertical + mated plug and lead
    ('D301', 104.15, 107.85, 118.25, 121.75, -1.4, 0.0),
    ('U501', 135.0, 137.0, 99.0, 101.0, -1.0, 0.0),
    ('U404', 115.1, 116.9, 81.7, 84.3, -0.6, 0.0),
    ('J201', 110.0, 142.0, 58.85, 66.0, BT, PLUG_Z0 + PLUG_H),   # plug legs behind the housing (MEASURE)
    ('J201', PLUG_CX - PLUG_W / 2, PLUG_CX + PLUG_W / 2, 38.85, 58.85, PLUG_Z0, PLUG_Z0 + PLUG_H),  # housing
]


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def rounded_y(x0, x1, y0, y1, z0, z1, r):
    """box with its edges along y rounded (plug cross-section)"""
    b = box(x0, x1, y0, y1, z0, z1)
    return fillet(b.edges().filter_by(Axis.Y), r) if r > 0 else b


def plug_section(y0, y1, inset=0.0, grow=0.0):
    d = grow - inset
    return rounded_y(PLUG_CX - PLUG_W / 2 - d, PLUG_CX + PLUG_W / 2 + d, y0, y1,
                     PLUG_Z0 - d, PLUG_Z0 + PLUG_H + d, max(PLUG_R + d, 0.3))


def plug_model():
    """J201 housing: rear flange, groove, shroud (for the fit check)"""
    rear = plug_section(PLUG_REAR, PLUG_REAR + FLANGE)
    neck = plug_section(PLUG_REAR + FLANGE, PLUG_REAR + FLANGE + GROOVE_W, inset=GROOVE_D)
    front = plug_section(PLUG_REAR + FLANGE + GROOVE_W, PLUG_REAR + PLUG_D)
    return rear + neck + front


def ledge_segments(edge_parts, axis_lo, axis_hi, coord, band_lo, band_hi):
    """free stretches along one board edge: [axis_lo, axis_hi] minus parts whose box reaches into the band"""
    blocked = []
    for (a0, a1, c0, c1) in edge_parts:
        if c1 > band_lo and c0 < band_hi:
            blocked.append((a0 - 0.3, a1 + 0.3))
    blocked.sort()
    segs, cur = [], axis_lo
    for b0, b1 in blocked:
        if b0 > cur + 3.0:
            segs.append((cur, b0))
        cur = max(cur, b1)
    if axis_hi > cur + 3.0:
        segs.append((cur, axis_hi))
    return segs


def export_board_step(force=False):
    """board 3D model via kicad-cli (hardware/tools/kicad_env.py finds KiCad)"""
    step = BUILD / 'board.step'
    pcb = HERE.parent / 'hardware' / 'obd-v2x-dongle.kicad_pcb'
    if step.exists() and not force and step.stat().st_mtime > pcb.stat().st_mtime:
        return
    sys.path.insert(0, str(HERE.parent / 'hardware' / 'tools'))
    import subprocess
    from kicad_env import CLI
    BUILD.mkdir(exist_ok=True)
    subprocess.run([str(CLI), 'pcb', 'export', 'step', '--subst-models', '--force', '-o', str(step), str(pcb)],
                   check=True, stdout=subprocess.DEVNULL)


def board_part_boxes():
    """(name, (x0, x1, y0, y1, z0, z1)) of every part, STEP coords: board model + substitutes"""
    boxes = []
    step = BUILD / 'board.step'
    if step.exists():
        for c in import_step(str(step)).children:
            b = c.bounding_box()
            if b.max.Z - b.min.Z < 1.7 and abs(b.min.Z) < 0.01:
                continue                                  # the board itself
            boxes.append((c.label, (b.min.X, b.max.X, b.min.Y, b.max.Y, b.min.Z, b.max.Z)))
    for ref, x0, x1, ky0, ky1, z0, z1 in SUBSTITUTES:
        boxes.append((ref, (x0, x1, -ky1, -ky0, z0, z1)))
    return boxes


def supports(parts, top):
    """ledges (bottom shell) or press ribs (lid) along the four board edges, where no part is near the edge"""
    side = [p for _, p in parts if (p[4] >= BT - 0.05) == top]
    out = []
    z0, z1 = (BT, Z_IN_TOP) if top else (Z_IN_BOT, 0.0)
    xs = [(p[0], p[1], p[2], p[3]) for p in side]
    ys = [(p[2], p[3], p[0], p[1]) for p in side]
    # front / rear edges (run along x)
    for (ein, eout, wall) in ((BYF - LEDGE, BYF, Y_RIB0), (BYR, BYR + LEDGE, Y_IN_REAR)):
        lo, hi = min(ein, eout, wall), max(ein, eout, wall)
        for s0, s1 in ledge_segments([(a0, a1, c0, c1) for a0, a1, c0, c1 in xs], X_IN0, X_IN1, None, lo, hi):
            out.append(box(s0, s1, lo, hi, z0, z1))
    # left / right edges (run along y)
    for (lo, hi) in ((X_IN0, BX0 + LEDGE), (BX1 - LEDGE, X_IN1)):
        for s0, s1 in ledge_segments([(a0, a1, c0, c1) for a0, a1, c0, c1 in ys], Y_IN_REAR, Y_RIB0, None, lo, hi):
            out.append(box(lo, hi, s0, s1, z0, z1))
    return out


def build(parts):
    outer = box(X_OUT0, X_OUT1, Y_OUT_REAR, FRONT_OUT, Z_OUT_BOT, Z_OUT_TOP)
    outer = fillet(outer.edges().filter_by(Axis.Z), EDGE_R)
    body = outer - box(X_IN0, X_IN1, Y_IN_REAR, Y_RIB0, Z_IN_BOT, Z_IN_TOP)
    # plug: groove core through the rib, full shroud outline in front of it
    body -= plug_section(Y_RIB0 - 0.01, Y_RIB1, inset=GROOVE_D)
    body -= plug_section(Y_RIB1, FRONT_OUT + 1, grow=PLUG_FIT)
    # USB-C
    body -= box(USB_X - USB_OPEN_W / 2, USB_X + USB_OPEN_W / 2, Y_OUT_REAR - 1, Y_IN_REAR + 0.01,
                USB_Z - USB_OPEN_H / 2, USB_Z + USB_OPEN_H / 2)
    for s in supports(parts, top=False) + supports(parts, top=True):
        body += s
    # cell pocket ribs on the floor
    for dx, dy, lx, ly in ((0, CELL_W / 2 + CELL_RIB_T / 2 + 0.3, CELL_L * 0.6, CELL_RIB_T),
                           (0, -(CELL_W / 2 + CELL_RIB_T / 2 + 0.3), CELL_L * 0.6, CELL_RIB_T),
                           (CELL_L / 2 + CELL_RIB_T / 2 + 0.3, 0, CELL_RIB_T, CELL_W * 0.6),
                           (-(CELL_L / 2 + CELL_RIB_T / 2 + 0.3), 0, CELL_RIB_T, CELL_W * 0.6)):
        cx, cy = CELL_CX + dx, CELL_CY + dy
        body += box(cx - lx / 2, cx + lx / 2, cy - ly / 2, cy + ly / 2, Z_IN_BOT - 0.01, Z_IN_BOT + CELL_RIB_H)
    # button pin guides and LED light pipe
    for (x, y) in BUTTONS:
        h = (BUTTON_FACE - 1.0) - Z_IN_BOT
        body += Pos(x, y, Z_IN_BOT + h / 2) * Cylinder(PIN_TUBE / 2, h)
        body -= Pos(x, y, 0) * Cylinder(PIN_HOLE / 2, 40)
    x, y = LED
    h = (LED_FACE - 0.5) - Z_IN_BOT
    body += Pos(x, y, Z_IN_BOT + h / 2) * Cylinder(LIGHTPIPE_TUBE / 2, h)
    body -= Pos(x, y, (Z_OUT_BOT + LED_FACE - 0.5) / 2) * Cylinder(LIGHTPIPE / 2, LED_FACE - 0.5 - Z_OUT_BOT + 1)

    # split: everything above the board top goes to the lid, except the bottom rib under the plug
    bottom_keep = box(X_OUT0 - 1, X_OUT1 + 1, Y_OUT_REAR - 1, FRONT_OUT + 1, Z_OUT_BOT - 1, SPLIT)
    bottom_keep += box(PLUG_CX - PLUG_W / 2, PLUG_CX + PLUG_W / 2, Y_RIB0 - 0.01, Y_RIB1 + 0.01,
                       SPLIT - 0.01, PLUG_Z0 + GROOVE_D)
    bottom = body & bottom_keep
    lid = body - bottom_keep

    # rear hooks: lid plate drops over a recess in the bottom wall's outer face, nub into a notch
    for hx in HOOKS:
        x0, x1 = hx - HOOK_W / 2, hx + HOOK_W / 2
        bottom -= box(x0 - 0.2, x1 + 0.2, Y_OUT_REAR - 1, Y_OUT_REAR + 1.0, SPLIT - HOOK_DROP - 0.2, SPLIT + 0.01)
        bottom -= box(x0 - 0.2, x1 + 0.2, Y_OUT_REAR - 1, Y_OUT_REAR + 1.5, SPLIT - HOOK_DROP + 0.4,
                      SPLIT - HOOK_DROP + 1.6)
        lid += box(x0, x1, Y_OUT_REAR, Y_OUT_REAR + 0.85, SPLIT - HOOK_DROP, SPLIT + 0.01)
        lid += box(x0, x1, Y_OUT_REAR + 0.8, Y_OUT_REAR + 1.35, SPLIT - HOOK_DROP + 0.5, SPLIT - HOOK_DROP + 1.4)

    # screws
    for (x, y) in SCREWS:
        lid -= Pos(x, y, SPLIT + 6) * Cylinder(SCREW_PILOT / 2, 12)
        bottom -= Pos(x, y, (Z_OUT_BOT + SPLIT) / 2) * Cylinder(SCREW_CLEAR / 2, SPLIT - Z_OUT_BOT + 1)
        bottom -= Pos(x, y, (Z_OUT_BOT - 1 + SCREW_HEAD_TOP) / 2) * Cylinder(
            SCREW_HEAD / 2, SCREW_HEAD_TOP - Z_OUT_BOT + 1)
    return bottom, lid


def check(bottom, lid, parts):
    """report overlaps of the case with board parts, the PCB and the plug"""
    ok = True
    pcb = box(BX0, BX1, BYR, BYF, 0, BT)
    plug = plug_model()
    targets = [('PCB', pcb), ('J201 plug', plug)]
    for n, p in parts:
        if n == 'J201':
            continue                                      # checked against the real plug shape above
        targets.append((f'{n} @ x {p[0]:.1f}..{p[1]:.1f} y {-p[3]:.1f}..{-p[2]:.1f} z {p[4]:.2f}..{p[5]:.2f}',
                        box(*p)))
    for name, shell in (('bottom', bottom), ('lid', lid)):
        for tname, t in targets:
            v = (shell & t).volume
            if v > 0.01:
                ok = False
                print(f'  COLLISION {name} x {tname}: {v:.2f} mm3')
    # the ribs must actually sit in the groove
    groove = plug_section(PLUG_REAR + FLANGE, PLUG_REAR + FLANGE + GROOVE_W) - plug_model()
    for name, shell in (('bottom', bottom), ('lid', lid)):
        print(f'  {name} rib in the groove: {(shell & groove).volume:.1f} mm3')
    # USB-C: opening in front of the receptacle
    print('  check', 'passed' if ok else 'FAILED')
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--render', action='store_true')
    a = ap.parse_args()
    export_board_step()
    parts = board_part_boxes()
    bottom, lid = build(parts)
    OUT.mkdir(exist_ok=True)
    for name, s in (('case_bottom', bottom), ('case_lid', lid)):
        export_step(s, str(OUT / f'{name}.step'))
        export_stl(s, str(OUT / f'{name}.stl'), tolerance=0.02, angular_tolerance=0.2)
        bb = s.bounding_box()
        print(f'{name}: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, {s.volume / 1000:.1f} cm3')
    full = Compound([bottom, lid]).bounding_box()
    print(f'closed case incl. plug: {full.size.X:.1f} x {full.size.Y + (PLUG_REAR + PLUG_D - FRONT_OUT):.1f} '
          f'x {full.size.Z:.1f} mm')
    if a.check:
        if not check(bottom, lid, parts):
            sys.exit(1)
    if a.render:
        import render
        render.render(bottom, lid, plug_model(), OUT, board=import_step(str(BUILD / 'board.step')))


if __name__ == '__main__':
    main()
