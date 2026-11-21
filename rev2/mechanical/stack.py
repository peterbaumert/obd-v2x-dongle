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
PLUG_Z0 = -1.0                   # housing bottom = leg tips, 1.0 mm below the carrier's bottom face, as in rev 1
PLUG_D, PLUG_H, KEY_H = 20.0, 17.8, 1.5
BODY_W = 40.26

# ------------------------------------------------------------------ boards
BT = 1.6                         # board thickness (both)
BW, BL = 45.0, 45.0              # board width (x), length (y)
BX0, BX1 = PLUG_CX - BW / 2, PLUG_CX + BW / 2
BYF = PLUG_REAR - 0.35           # front edge of both boards, just behind the plug's rear face
BYR = BYF - BL
# Gap between the boards: M2.5 x 12 mm spacers. The connectors must not bottom out before the spacers do:
# SMD socket on the carrier, top 8.9 +-0.2 above its board (it stands on its leads); through-hole header on the
# upper board, base 2.5 +-0.2 flat on the board: 11.4 nominal, 11.8 at most. (An SMD header + SMD socket pair
# bottoms out at 12.1 +-0.4 and would bow the boards on 12 mm spacers.)
STACK = 12.0
SOCKET_H, HEADER_H = 8.9, 2.5
UZ0 = BT + STACK                 # upper board bottom face
UZ1 = UZ0 + BT

# ------------------------------------------------------------------ case envelope
WALL, FLOOR, ROOF, GAP = 2.0, 1.6, 2.0, 0.3
MODEM_H = 2.6                    # EC200U 2.4 +-0.2
PATCH_H = 4.4                    # CGGBP.25.4.A.02 4.0 +-0.4 (its feed pin head adds up to 1.0: pocket in the lid)
Z_IN_BOT = -(MODEM_H + 0.3)
Z_IN_TOP = max(PLUG_Z0 + PLUG_H + KEY_H, UZ1 + PATCH_H) + 0.3   # plug key or GNSS patch, whichever is higher
CLEAR = 0.3                      # wanted clearance between parts that do not touch by design


def part(name, x0, y0, w, l, z0, h, group, note=''):
    """box from its low corner (x0, y0 = rear / left corner), w along x, l along y, h along z"""
    return dict(name=name, x=(x0, x0 + w), y=(y0, y0 + l), z=(z0, z0 + h), group=group, note=note)


HDR_L, HDR_W = 20.3, 5.0         # 2 x 8, 2.54 mm (body)
HDR_X = 2.2                      # body this far inside the board edge: the SMD pads need 8.2 mm, 0.6 mm from the edge
HDR_Y = BYF - 8.0 - HDR_L        # headers start 8 mm behind the front edge (behind the plug legs)
CELL = (30.0, 20.0, 5.2)         # x, y, z: the larger common format, lying across
UNDER_CELL = 2.9                 # tallest part allowed under the cell (the 1210 capacitors are 2.85 at most)
CELL_X0, CELL_Y0, CELL_Z0 = PLUG_CX - 15.0, BYR + 1.0, BT + UNDER_CELL + 0.1
ESP_H = 3.45                     # ESP32-C5-WROOM-1U 3.3 +-0.15; its U.FL is on the shield side and, mated, no higher

# Heights are data-sheet maxima (see ../README.md, "Checked against sources").
PARTS = [
    # --- carrier board
    part('carrier PCB', BX0, BYR, BW, BL, 0, BT, 'pcb'),
    part('plug legs (above)', 110.0, -66.0, 32.0, 6.75, BT, PLUG_Z0 + 13.6 - BT, 'plug',
         'drawing: upper leg row 13.2 above the housing bottom, legs 0.8 thick'),
    part('plug leg tips (below)', 110.0, -66.0, 32.0, 6.75, PLUG_Z0, -PLUG_Z0, 'plug'),
    part('EC200U', BX0 + 14.0, BYR + 3.0, 28.0, 31.0, -MODEM_H, MODEM_H, 'carrier-bottom',
         'body; pads reach 1.65 mm further'),
    part('socket L', BX0 + HDR_X, HDR_Y, HDR_W, HDR_L, BT, SOCKET_H, 'header'),
    part('socket R', BX1 - HDR_X - HDR_W, HDR_Y, HDR_W, HDR_L, BT, SOCKET_H, 'header'),
    part('JST-PH side entry', BX0 + 26.25, BYF - 15.65, 8.6, 7.9, BT, 5.5, 'carrier-top',
         'S2B-PH-SM4-TB, plug goes in from the left (-x)'),
    part('battery plug', BX0 + 22.65, BYF - 14.6, 3.6, 5.8, BT + 0.5, 4.5, 'carrier-top',
         'mated PHR-2; its wires run on to the left and back to the cell'),
    part('buck inductor', BX0 + 18.4, BYF - 23.25, 7.0, 6.6, BT, 5.0, 'carrier-top', 'beside U102, in front of the cell'),
    part('buck diode SMC', BX0 + 12.8, BYF - 32.0, 6.0, 7.0, BT, 2.62, 'carrier-top', 'under the cell'),
    part('C401 polymer 220u', BX0 + 11.35, BYF - 38.15, 7.3, 4.3, BT, 2.0, 'carrier-top',
         'KEMET T520V, over the modem VBAT pins, under the cell'),
    part('C506 tantalum 220u', BX0 + 27.35, BYF - 21.15, 7.3, 4.3, BT, 3.1, 'carrier-top'),
    part('TVS SMC', BX0 + 3.05, BYF - 18.65, 5.9, 8.0, -2.62, 2.62, 'carrier-bottom', 'beside the modem'),
    part('LTE U.FL', BX0 + 2.5, BYF - 42.0, 3.0, 3.0, BT, 2.5, 'carrier-top', 'mated, beside the cell'),
    part('GNSS U.FL', BX0 + 39.5, BYF - 42.0, 3.0, 3.0, BT, 2.5, 'carrier-top', 'jumper to the upper board'),
    # --- between the boards
    part('spacer L', BX0 + 1.0, BYF - 6.5, 5.0, 5.0, BT, STACK, 'header', 'M2.5 x 12 mm, front corner'),
    part('spacer R', BX1 - 6.0, BYF - 6.5, 5.0, 5.0, BT, STACK, 'header'),
    part('cell', CELL_X0, CELL_Y0, CELL[0], CELL[1], CELL_Z0, CELL[2], 'cell',
         f'5.2 x 20 x 30 mm, on carrier parts up to {UNDER_CELL} mm tall'),
    # --- upper board
    part('upper PCB', BX0, BYR, BW, BL, UZ0, BT, 'pcb'),
    part('header L', BX0 + HDR_X, HDR_Y, HDR_W, HDR_L, UZ0 - HEADER_H, HEADER_H, 'header', 'through-hole'),
    part('header R', BX1 - HDR_X - HDR_W, HDR_Y, HDR_W, HDR_L, UZ0 - HEADER_H, HEADER_H, 'header'),
    part('ESP32-C5 module', PLUG_CX - 9.0, -66.5 - 21.2, 18.0, 21.2, UZ0 - ESP_H, ESP_H, 'upper-bottom'),
    part('USB-C', BX0 + 35.0, BYR - 0.5, 9.0, 7.5, UZ0 - 3.36, 3.36, 'upper-bottom', 'overhangs the rear edge'),
    part('micro-SIM holder', BX0, BYR + 0.5, 15.45, 12.65 + 2.35, UZ0 - 1.55, 1.55, 'upper-bottom',
         'Molex 78646-3001 (1.45 +-0.1), card enters from the left edge'),
    part('GNSS patch', BX0 + 21.0 - 12.55, BYR + 2.95, 25.1, 25.1, UZ1, PATCH_H, 'upper-top',
         'Taoglas CGGBP.25.4.A.02; 1.5 mm left of centre, clear of the USB-C legs'),
]

# pairs that touch or overlap by design
ALLOWED = {
    frozenset(p) for p in [
        ('plug legs (above)', 'carrier PCB'), ('plug leg tips (below)', 'carrier PCB'),
        ('JST-PH side entry', 'battery plug'),
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
