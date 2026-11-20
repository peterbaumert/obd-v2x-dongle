"""Two-part 3D-printed case for the rev 2 stack (build123d).

    python rev2/mechanical/case.py            # build, check against the stack model, write out/*.step + out/*.stl
    python rev2/mechanical/case.py --render   # also write out/case_*.png (needs pyvista)

The case is built around rev2/mechanical/stack.py (same coordinates): the plug, the two boards and their big
parts. It is checked against those boxes, not against the routed boards (they do not exist yet).

Concept
- Bottom shell + lid, split at the upper board's bottom face. The assembled stack (carrier, spacers, upper board,
  plug soldered to the carrier) drops into the bottom shell from above.
- The two M2.5 x 12 mm spacers between the boards hold everything: one M2.5 screw from below through the bottom
  shell and the carrier into each spacer, one from above through the lid and the upper board. No screws into plastic.
- Two hooks at the rear hold the lid there (lid goes on rear first, then folds down), as in rev 1.
- The plug's retention groove takes a rib all around: bottom and both sides in the bottom shell, the top in the lid.
  The case front ends at the groove, so the whole plug body sticks out.
- USB-C: a notch in the rear wall, open towards the split.
- Micro-SIM: a notch in the left wall at the holder. A tooth on the lid closes it and is the card stop (the holder
  has no latch): to change the SIM, take the lid off and pull the card out sideways. The boards stay in.
- Lid: pin holes over the RESET / BOOT buttons and a 3 mm hole over the LED.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'rev1' / 'mechanical'))

import stack as S  # noqa: E402
import case as rev1  # noqa: E402  (plug shape and helpers)
from build123d import Axis, Cylinder, Pos, export_step, export_stl, fillet  # noqa: E402

rev1.PLUG_Z0 = S.PLUG_Z0            # the plug sits 1 mm lower than in rev 1
box, prism = rev1.box, rev1.prism

WALL, FLOOR, ROOF, GAP = S.WALL, S.FLOOR, S.ROOF, S.GAP
FIT = 0.1                           # rib clearance in the groove (per side)
EDGE_R, EDGE_R_H = 3.0, 1.5         # vertical / horizontal outer edge radius
X_IN0, X_IN1 = S.BX0 - GAP, S.BX1 + GAP
Y_IN_REAR = S.BYR - 0.5 - GAP       # USB-C overhangs the rear edge by 0.5 mm
Y_RIB0 = S.PLUG_REAR + rev1.FLANGE_T + FIT                     # rib rear face = front of the interior
Y_RIB1 = S.PLUG_REAR + rev1.FLANGE_T + rev1.GROOVE_W - FIT
FRONT_OUT = Y_RIB1
X_OUT0, X_OUT1, Y_OUT_REAR = X_IN0 - WALL, X_IN1 + WALL, Y_IN_REAR - WALL
Z_IN_BOT, Z_IN_TOP = S.Z_IN_BOT, S.Z_IN_TOP
Z_OUT_BOT, Z_OUT_TOP = Z_IN_BOT - FLOOR, Z_IN_TOP + ROOF
SPLIT = S.UZ0                       # upper board's bottom face

# grip grooves all around, across the plug direction (as rev 1)
GRIP_N, GRIP_PITCH, GRIP_W, GRIP_D, GRIP_REAR = 6, 3.0, 1.2, 0.5, 9.0

# spacer screws (board frame: x from the left edge, y behind the front edge) -> model coordinates
SPACERS = [(S.BX0 + 3.5, S.BYF - 4.0), (S.BX1 - 3.5, S.BYF - 4.0)]
M25_CLEAR, M25_HEAD, HEAD_DEPTH = 2.8, 5.0, 2.0     # pan head 4.5 mm, 1.7 high
BOSS_R = 3.2

# openings
USB_X, USB_W = S.BX0 + 39.5, 11.0                   # USB-C centre, plug over-mould width
USB_Z = (S.UZ0 - 1.63 - 3.5, S.UZ0 - 1.63 + 3.5)    # 7 mm tall around the receptacle's centre
SIM_Y, SIM_W = S.BYF - 37.0, 12.6                   # card centre (holder centre), card 12 mm + play
SIM_Z0 = S.UZ0 - 1.6                                # card plane just under the upper board
BUTTONS = [(S.BX0 + 12.5, S.BYF - 12.0), (S.BX0 + 32.5, S.BYF - 12.0)]  # SW301 RESET, SW302 BOOT
LED = (S.BX0 + 22.5, S.BYF - 3.0)
PIN_HOLE, PIN_BOSS, LIGHTPIPE = 1.6, 4.0, 3.0
BUTTON_TOP = S.UZ1 + 1.75                           # TL3342F450QG actuator top 1.50 +-0.25, actuator 2.0 mm
PATCH_PIN = (S.BX0 + 21.0, S.BYF - 32.0)            # patch feed: its pin head stands up to 1.0 mm above the patch
PIN_POCKET = (4.0, 1.0)                             # pocket in the roof over it: diameter, depth
HOOKS = [S.BX0 + 8.5, S.BX0 + 24.5]                 # x centres, clear of the USB-C opening
HOOK_W, HOOK_DROP = 8.0, 3.0
REAR_LEDGE = (S.BX0 + 6.0, S.BX0 + 30.0, 0.8)       # under the carrier's rear edge: x0, x1, depth
REAR_PRESS = (S.BX0 + 6.0, S.BX0 + 30.0, 0.8)       # lid rib on the upper board's rear edge


def build():
    outer = box(X_OUT0, X_OUT1, Y_OUT_REAR, FRONT_OUT, Z_OUT_BOT, Z_OUT_TOP)
    outer = fillet(outer.edges().filter_by(Axis.Z), EDGE_R)
    fz = outer.faces().sort_by(Axis.Z)
    outer = fillet(fz[0].edges() + fz[-1].edges(), EDGE_R_H)
    for i in range(GRIP_N):
        y = Y_OUT_REAR + GRIP_REAR + i * GRIP_PITCH
        x0, x1, z0, z1 = X_OUT0 + GRIP_D, X_OUT1 - GRIP_D, Z_OUT_BOT + GRIP_D, Z_OUT_TOP - GRIP_D
        core = prism([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y - 1, y + 1, [EDGE_R_H - GRIP_D] * 4)
        outer -= box(X_OUT0 - 1, X_OUT1 + 1, y - GRIP_W / 2, y + GRIP_W / 2, Z_OUT_BOT - 1, Z_OUT_TOP + 1) - core
    body = outer - box(X_IN0, X_IN1, Y_IN_REAR, Y_RIB0, Z_IN_BOT, Z_IN_TOP)
    body -= rev1.plug_neck(Y_RIB0 - 0.01, Y_RIB1 + 0.01, grow=FIT)

    clip = box(X_IN0 - 0.01, X_IN1 + 0.01, Y_IN_REAR - 0.01, Y_RIB0 + 0.01, Z_IN_BOT - 0.01, Z_IN_TOP + 0.01)
    # screw bosses: under the carrier and over the upper board, at the spacers
    for (x, y) in SPACERS:
        body += (Pos(x, y, Z_IN_BOT / 2) * Cylinder(BOSS_R, -Z_IN_BOT)) & clip
        body += (Pos(x, y, (S.UZ1 + Z_IN_TOP) / 2) * Cylinder(BOSS_R, Z_IN_TOP - S.UZ1)) & clip
    # carrier rear edge rests on a ledge; the lid presses on the upper board's rear edge
    x0, x1, d = REAR_LEDGE
    body += box(x0, x1, Y_IN_REAR - 0.01, S.BYR + d, Z_IN_BOT - 0.01, 0.0)
    x0, x1, d = REAR_PRESS
    body += box(x0, x1, Y_IN_REAR - 0.01, S.BYR + d, S.UZ1, Z_IN_TOP + 0.01)
    # button pin holes with short guides, LED hole
    for (x, y) in BUTTONS:
        h = Z_IN_TOP - (BUTTON_TOP + 0.8)
        if h > 0.3:
            body += Pos(x, y, Z_IN_TOP - h / 2) * Cylinder(PIN_BOSS / 2, h)
        body -= Pos(x, y, Z_OUT_TOP - 5) * Cylinder(PIN_HOLE / 2, 12)
    body -= Pos(LED[0], LED[1], Z_OUT_TOP - 2) * Cylinder(LIGHTPIPE / 2, 6)
    body -= Pos(PATCH_PIN[0], PATCH_PIN[1], Z_IN_TOP + PIN_POCKET[1] / 2 - 0.01) * Cylinder(PIN_POCKET[0] / 2, PIN_POCKET[1])
    # USB-C opening through the rear wall
    body -= box(USB_X - USB_W / 2, USB_X + USB_W / 2, Y_OUT_REAR - 1, Y_IN_REAR + 0.01, USB_Z[0], USB_Z[1])

    bottom_keep = box(X_OUT0 - 1, X_OUT1 + 1, Y_OUT_REAR - 1, FRONT_OUT + 1, Z_OUT_BOT - 1, SPLIT)
    bottom = body & bottom_keep
    lid = body - bottom_keep

    # micro-SIM: notch in the bottom shell's left wall, closed by a tooth on the lid (the card stop)
    notch = box(X_OUT0 - 1, X_IN0 + 0.01, SIM_Y - SIM_W / 2, SIM_Y + SIM_W / 2, SIM_Z0, SPLIT + 0.01)
    bottom -= notch
    lid += box(X_OUT0 + 0.0, X_IN0, SIM_Y - SIM_W / 2 + 0.2, SIM_Y + SIM_W / 2 - 0.2, SIM_Z0 + 0.2, SPLIT + 0.01) & outer

    # rear hooks: lid plate drops over a recess in the bottom wall's outer face, nub into a notch (as rev 1)
    for hx in HOOKS:
        x0, x1 = hx - HOOK_W / 2, hx + HOOK_W / 2
        bottom -= box(x0 - 0.2, x1 + 0.2, Y_OUT_REAR - 1, Y_OUT_REAR + 1.0, SPLIT - HOOK_DROP - 0.2, SPLIT + 0.01)
        bottom -= box(x0 - 0.2, x1 + 0.2, Y_OUT_REAR - 1, Y_OUT_REAR + 1.5, SPLIT - HOOK_DROP + 0.4,
                      SPLIT - HOOK_DROP + 1.6)
        lid += box(x0, x1, Y_OUT_REAR, Y_OUT_REAR + 0.85, SPLIT - HOOK_DROP, SPLIT + 0.01)
        lid += box(x0, x1, Y_OUT_REAR + 0.8, Y_OUT_REAR + 1.35, SPLIT - HOOK_DROP + 0.5, SPLIT - HOOK_DROP + 1.4)

    # spacer screws: clearance holes and head counterbores from outside
    for (x, y) in SPACERS:
        bottom -= Pos(x, y, (Z_OUT_BOT + 0.0) / 2) * Cylinder(M25_CLEAR / 2, -Z_OUT_BOT + 1)
        bottom -= Pos(x, y, Z_OUT_BOT + HEAD_DEPTH / 2 - 0.5) * Cylinder(M25_HEAD / 2, HEAD_DEPTH + 1)
        lid -= Pos(x, y, (S.UZ1 + Z_OUT_TOP) / 2) * Cylinder(M25_CLEAR / 2, Z_OUT_TOP - S.UZ1 + 1)
        lid -= Pos(x, y, Z_OUT_TOP - HEAD_DEPTH / 2 + 0.5) * Cylinder(M25_HEAD / 2, HEAD_DEPTH + 1)
    return bottom, lid


def plug_model():
    return rev1.plug_model()


def check(bottom, lid):
    """overlap of each shell with the stack's parts and with the plug; the ribs must sit in the groove"""
    ok = True
    targets = [('plug', plug_model())]
    for p in S.PARTS:
        if p['group'] == 'plug' or p['name'].startswith('spacer'):
            continue                                   # legs are inside the interior; spacers sit between the boards
        targets.append((p['name'], box(p['x'][0], p['x'][1], p['y'][0], p['y'][1], p['z'][0], p['z'][1])))
    for name, shell in (('bottom', bottom), ('lid', lid)):
        for tname, t in targets:
            v = (shell & t).volume
            if v > 0.01:
                ok = False
                print(f'  COLLISION {name} x {tname}: {v:.2f} mm3')
    r = S.PLUG_REAR
    groove = rev1.plug_flange(r + rev1.FLANGE_T, r + rev1.FLANGE_T + rev1.GROOVE_W) - plug_model()
    for name, shell in (('bottom', bottom), ('lid', lid)):
        v = (shell & groove).volume
        print(f'  {name} rib in the groove: {v:.1f} mm3')
        ok = ok and v > 20
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--render', action='store_true')
    a = ap.parse_args()
    bottom, lid = build()
    OUT.mkdir(exist_ok=True)
    for name, shape in (('case_bottom', bottom), ('case_lid', lid)):
        export_step(shape, str(OUT / f'{name}.step'))
        export_stl(shape, str(OUT / f'{name}.stl'))
        bb = shape.bounding_box()
        print(f'{name}: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, {shape.volume / 1000:.1f} cm3')
    length = S.PLUG_REAR + S.PLUG_D - Y_OUT_REAR
    print(f'closed case incl. plug: {X_OUT1 - X_OUT0:.1f} x {length:.1f} x {Z_OUT_TOP - Z_OUT_BOT:.1f} mm')
    ok = check(bottom, lid)
    print('check passed' if ok else 'check FAILED')
    if a.render:
        import render as r
        b, l, pl = r.mesh(bottom), r.mesh(lid), r.mesh(plug_model())
        c = ((X_OUT0 + X_OUT1) / 2, (Y_OUT_REAR + FRONT_OUT) / 2, 8)
        r._shot(OUT / 'case_closed.png', [(b, '#5b7fb5', 1), (l, '#7f9fd0', 1), (pl, '#2b2b2b', 1)],
                [(20, 60, 110), c, (0, 0, 1)])
        r._shot(OUT / 'case_closed_rear.png', [(b, '#5b7fb5', 1), (l, '#7f9fd0', 1), (pl, '#2b2b2b', 1)],
                [(20, -260, 90), c, (0, 0, 1)])
        items = [(b, '#5b7fb5', 1), (r.mesh(lid, (0, 0, 30)), '#7f9fd0', 1), (pl, '#2b2b2b', 1)]
        for p in S.PARTS:
            if p['group'] != 'plug':
                items.append((r.mesh(box(p['x'][0], p['x'][1], p['y'][0], p['y'][1], p['z'][0], p['z'][1])),
                              '#2e7d32' if p['group'] == 'pcb' else '#9e9e9e', 1))
        r._shot(OUT / 'case_open.png', items, [(-160, -230, 150), c, (0, 0, 1)])
        print('wrote case_closed.png, case_closed_rear.png, case_open.png')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
