"""Generate project footprints in hardware/lib/obd-v2x.pretty.

  python hardware/lib/gen_footprints.py

Quectel_EC200U: from Quectel EC200U Series QuecOpen Hardware Design V1.0,
  Figure 2 (Pin Assignment, top view) and Figure 39 (Recommended Footprint, top view).
  Module 31.0 x 28.0 mm, footprint extent 34.3 x 31.3 mm, 80 LCC + 64 LGA pads.
  Origin = module centre, x right, y down (top view).

ESP32-C5-WROOM-1U.kicad_mod is vendored from espressif/kicad-libraries (CC-BY-SA 4.0 with
the KiCad design exception), not generated here.
"""
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


if __name__ == '__main__':
    p = OUT / 'Quectel_EC200U.kicad_mod'
    p.write_text(ec200u(), encoding='utf-8')
    print('wrote', p)
