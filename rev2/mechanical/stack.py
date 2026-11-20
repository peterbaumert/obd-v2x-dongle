"""Rev 2 stack model: the OBD plug, two stacked boards and their big parts as boxes.

    python rev2/mechanical/stack.py            # check clearances, print the envelope
    python rev2/mechanical/stack.py --render   # also write out/stack_*.png (needs build123d + pyvista)

A planning model, not a case: it shows whether the parts fit the 25 mm stack and where they can go.
Coordinates as in rev 1: x = KiCad x, y = -KiCad y (+y = front, towards the car), z = 0 at the carrier board's
bottom face. The plug is rev 1's (CR-PG001), same position relative to the carrier's front edge.
Part sizes are from rev 1's board model or the data sheets named in ../README.md; boxes marked CHECK are estimates.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'

# ------------------------------------------------------------------ plug (rev 1 values)
PLUG_CX = 126.0
PLUG_REAR = -59.25               # housing rear face
PLUG_Z0 = -2.0                   # housing bottom = leg tips, 2.0 mm below the carrier's bottom face (rev 1: 1.0).
                                 # 1 mm lower keeps the leg bends clear of the upper board; the tips stay inside
                                 # the 2.7 mm space under the carrier, and the bends 0.4 mm above its top face
PLUG_D, PLUG_H, KEY_H = 20.0, 17.8, 1.5
BODY_W = 40.26

# ------------------------------------------------------------------ boards
BT = 1.6                         # board thickness (both)
BW, BL = 45.0, 45.0              # board width (x), length (y)
BX0, BX1 = PLUG_CX - BW / 2, PLUG_CX + BW / 2
BYF = PLUG_REAR - 0.35           # front edge of both boards, just behind the plug's rear face
BYR = BYF - BL
STACK = 11.0                     # gap between the boards: 2.54 mm header 2.5 + socket 8.5, M2.5 x 11 mm spacers
UZ0 = BT + STACK                 # upper board bottom face
UZ1 = UZ0 + BT

# ------------------------------------------------------------------ case envelope
WALL, FLOOR, ROOF, GAP = 2.0, 1.6, 2.0, 0.3
Z_IN_BOT = -2.7                  # EC200U 2.4 mm + 0.3
Z_IN_TOP = max(PLUG_Z0 + PLUG_H + KEY_H, UZ1 + 4.0) + 0.3   # plug key or GNSS patch, whichever is higher
CLEAR = 0.3                      # wanted clearance between parts that do not touch by design


def part(name, x0, y0, w, l, z0, h, group, note=''):
    """box from its low corner (x0, y0 = rear / left corner), w along x, l along y, h along z"""
    return dict(name=name, x=(x0, x0 + w), y=(y0, y0 + l), z=(z0, z0 + h), group=group, note=note)


HDR_L, HDR_W = 20.3, 5.0         # 2 x 8, 2.54 mm (body)
HDR_X = 2.2                      # body this far inside the board edge: the SMD pads need 8.2 mm, 0.6 mm from the edge
HDR_Y = BYF - 8.0 - HDR_L        # headers start 8 mm behind the front edge (behind the plug legs)
CELL = (30.0, 20.0, 5.2)         # x, y, z: the larger common format, lying across
CELL_X0, CELL_Y0, CELL_Z0 = PLUG_CX - 15.0, BYR + 1.0, BT + 2.1   # on parts up to 2.0 mm tall

PARTS = [
    # --- carrier board
    part('carrier PCB', BX0, BYR, BW, BL, 0, BT, 'pcb'),
    part('plug legs (above)', 110.0, -66.0, 32.0, 6.75, BT, PLUG_Z0 + 13.6 - BT, 'plug',
         'drawing: upper leg row 13.2 above the housing bottom, legs 0.8 thick'),
    part('plug leg tips (below)', 110.0, -66.0, 32.0, 6.75, PLUG_Z0, -PLUG_Z0, 'plug'),
    part('EC200U', BX0 + 3.0, BYR + 3.0, 28.0, 31.0, -2.4, 2.4, 'carrier-bottom', 'body; pads reach 1.65 mm further'),
    part('socket L', BX0 + HDR_X, HDR_Y, HDR_W, HDR_L, BT, 8.5, 'header'),
    part('socket R', BX1 - HDR_X - HDR_W, HDR_Y, HDR_W, HDR_L, BT, 8.5, 'header'),
    part('buck inductor', BX0 + 20.3, BYF - 14.3, 7.0, 6.6, BT, 4.8, 'carrier-top'),
    part('tantalum 220u A', BX0 + 28.85, BYF - 15.65, 4.3, 7.3, BT, 3.1, 'carrier-top'),
    part('tantalum 220u B', BX0 + 10.65, BYF - 22.45, 7.3, 4.3, BT, 3.1, 'carrier-top'),
    part('TVS SMC', BX0 + 36.05, BYF - 18.0, 5.9, 8.0, -2.3, 2.3, 'carrier-bottom', 'beside the modem'),
    part('JST-PH side entry', BX0 + 10.3, BYF - 16.3, 8.0, 7.6, BT, 5.5, 'carrier-top',
         'S2B-PH-SM4-TB, 5.5 mm, under the ESP32 module; outline CHECK'),
    part('LTE U.FL', BX0 + 40.0, BYF - 42.5, 3.0, 3.0, BT, 2.6, 'carrier-top', 'mated, beside the cell'),
    part('GNSS U.FL', BX0 + 40.0, BYF - 36.0, 3.0, 3.0, BT, 2.6, 'carrier-top', 'jumper to the upper board'),
    # --- between the boards
    part('spacer L', BX0 + 1.0, BYF - 6.5, 5.0, 5.0, BT, STACK, 'header', 'M2.5 x 11 mm, front corner'),
    part('spacer R', BX1 - 6.0, BYF - 6.5, 5.0, 5.0, BT, STACK, 'header'),
    part('cell', CELL_X0, CELL_Y0, CELL[0], CELL[1], CELL_Z0, CELL[2], 'cell',
         '5.2 x 20 x 30 mm, on carrier parts up to 2.0 mm tall'),
    # --- upper board
    part('upper PCB', BX0, BYR, BW, BL, UZ0, BT, 'pcb'),
    part('header L', BX0 + HDR_X, HDR_Y, HDR_W, HDR_L, UZ0 - 2.5, 2.5, 'header'),
    part('header R', BX1 - HDR_X - HDR_W, HDR_Y, HDR_W, HDR_L, UZ0 - 2.5, 2.5, 'header'),
    part('ESP32-C5 module', PLUG_CX - 9.0, -66.5 - 21.2, 18.0, 21.2, UZ0 - 3.4, 3.4, 'upper-bottom',
         'antenna end / U.FL towards the front'),
    part('ESP32 U.FL plug', PLUG_CX - 9.0 + 1.0, -66.5 - 5.0, 4.0, 4.0, UZ0 - 3.4 - 2.0, 2.0, 'upper-bottom',
         'mated U.FL on the module; height CHECK'),
    part('USB-C', BX0 + 35.0, BYR - 0.5, 9.0, 7.5, UZ0 - 3.3, 3.3, 'upper-bottom', 'overhangs the rear edge 0.5 mm'),
    part('micro-SIM holder', BX0, BYR + 0.5, 16.0, 15.0, UZ0 - 1.45, 1.45, 'upper-bottom',
         'Molex 78646-3001, card enters from the left edge; outline CHECK'),
    part('GNSS patch', BX0 + 21.0 - 12.5, BYR + 3.0, 25.0, 25.0, UZ1, 4.0, 'upper-top',
         'Taoglas CGGBP.25.4.A.02; 1.5 mm left of centre, clear of the USB-C legs'),
]

# pairs that touch or overlap by design
ALLOWED = {
    frozenset(p) for p in [
        ('socket L', 'header L'), ('socket R', 'header R'),
        ('plug legs (above)', 'carrier PCB'), ('plug leg tips (below)', 'carrier PCB'),
        ('ESP32-C5 module', 'ESP32 U.FL plug'),
    ]
}


def gap(a, b):
    """clearance between two boxes: > 0 apart, <= 0 overlapping (largest separation over the three axes)"""
    return max(max(a[k][0] - b[k][1], b[k][0] - a[k][1]) for k in 'xyz')


def check():
    ok = True
    for i, a in enumerate(PARTS):
        for b in PARTS[i + 1:]:
            if frozenset((a['name'], b['name'])) in ALLOWED:
                continue
            g = gap(a, b)
            mounted = ('PCB' in a['name'] or 'PCB' in b['name']) and abs(g) < 1e-6
            if g < -1e-6:
                ok = False
                print(f"  COLLISION {a['name']} x {b['name']}: overlap {-g:.2f} mm")
            elif g < CLEAR - 1e-6 and not mounted:
                print(f"  tight     {a['name']} / {b['name']}: {g:.2f} mm")
    # everything inside the case interior
    x0, x1 = BX0 - GAP, BX1 + GAP
    for p in PARTS:
        if p['group'] == 'plug':
            continue
        if p['z'][0] < Z_IN_BOT - 1e-6 or p['z'][1] > Z_IN_TOP + 1e-6:
            ok = False
            print(f"  OUT OF CASE {p['name']}: z {p['z'][0]:.2f}..{p['z'][1]:.2f} (inside {Z_IN_BOT}..{Z_IN_TOP:.1f})")
        if p['x'][0] < x0 - 1e-6 or p['x'][1] > x1 + 1e-6:
            ok = False
            print(f"  OUT OF CASE {p['name']}: x {p['x'][0]:.2f}..{p['x'][1]:.2f}")
    return ok


def envelope():
    w = BW + 2 * GAP + 2 * WALL
    h = (Z_IN_TOP + ROOF) - (Z_IN_BOT - FLOOR)
    rear = min(p['y'][0] for p in PARTS) - GAP - WALL
    length = (PLUG_REAR + PLUG_D) - rear
    return w, length, h


def render():
    sys.path.insert(0, str(HERE.parents[1] / 'rev1' / 'mechanical'))
    import case as rev1
    import render as r
    colors = {'pcb': '#2e7d32', 'plug': '#b0b0b0', 'carrier-bottom': '#9e9e9e', 'carrier-top': '#6d4c41',
              'header': '#212121', 'cell': '#90caf9', 'upper-bottom': '#757575', 'upper-top': '#d7a98c'}
    items = [(r.mesh(rev1.plug_model(), (0, 0, PLUG_Z0 - rev1.PLUG_Z0)), '#2b2b2b', 1)]
    for p in PARTS:
        b = rev1.box(p['x'][0], p['x'][1], p['y'][0], p['y'][1], p['z'][0], p['z'][1])
        items.append((r.mesh(b), colors[p['group']], 0.35 if p['name'] == 'upper PCB' else 1))
    OUT.mkdir(exist_ok=True)
    c = (PLUG_CX, (BYF + BYR) / 2, 8)
    r._shot(OUT / 'stack_iso.png', items, [(40, -200, 110), c, (0, 0, 1)])
    r._shot(OUT / 'stack_side.png', items, [(-200, c[1], 8), c, (0, 0, 1)])
    r._shot(OUT / 'stack_below.png', items, [(60, -180, -120), c, (0, 0, 1)])
    print('wrote', ', '.join(sorted(f.name for f in OUT.glob('stack_*.png'))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--render', action='store_true')
    a = ap.parse_args()
    print(f'boards {BW:.0f} x {BL:.0f} mm, gap {STACK} mm, upper board z {UZ0:.1f}..{UZ1:.1f}')
    ok = check()
    w, l, h = envelope()
    print(f'case envelope incl. plug: {w:.1f} x {l:.1f} x {h:.1f} mm')
    print('check passed' if ok else 'check FAILED')
    if a.render:
        render()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
