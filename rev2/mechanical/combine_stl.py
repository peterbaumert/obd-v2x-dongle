"""Put several STL files on one print bed, one behind the other (no dependencies).

    python rev2/mechanical/combine_stl.py OUT.stl IN1.stl IN2.stl ... [--gap 10]

Each part keeps its orientation; parts are centred in x and stacked along y with GAP mm between them, all resting
on z = 0. Default (no arguments): rev 1 and rev 2 plug-end fit tests -> rev2/mechanical/out/fit_tests_rev1_rev2.stl
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_stl(path):
    data = Path(path).read_bytes()
    if len(data) >= 84:
        n = struct.unpack_from('<I', data, 80)[0]
        if len(data) == 84 + 50 * n:                        # binary
            tris = []
            for i in range(n):
                v = struct.unpack_from('<12f', data, 84 + 50 * i)
                tris.append((v[3:6], v[6:9], v[9:12]))
            return tris
    tris, cur = [], []                                     # ASCII
    for line in data.decode('ascii', 'replace').splitlines():
        w = line.split()
        if w and w[0] == 'vertex':
            cur.append(tuple(float(x) for x in w[1:4]))
            if len(cur) == 3:
                tris.append(tuple(cur))
                cur = []
    return tris


def write_stl(path, tris):
    out = bytearray(b'combined by combine_stl.py'.ljust(80, b' '))
    out += struct.pack('<I', len(tris))
    for a, b, c in tris:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ln = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5 or 1.0
        out += struct.pack('<12fH', n[0] / ln, n[1] / ln, n[2] / ln, *a, *b, *c, 0)
    Path(path).write_bytes(bytes(out))


def main():
    args = [a for a in sys.argv[1:]]
    gap = 10.0
    if '--gap' in args:
        k = args.index('--gap')
        gap = float(args[k + 1])
        del args[k:k + 2]
    if not args:
        args = [str(ROOT / 'rev2/mechanical/out/fit_tests_rev1_rev2.stl'),
                str(ROOT / 'rev1/mechanical/out/fit_test_plug_end.stl'),
                str(ROOT / 'rev2/mechanical/out/fit_test_plug_end.stl')]
    out, ins = args[0], args[1:]
    allt, y = [], 0.0
    for f in ins:
        t = read_stl(f)
        xs = [p[0] for tri in t for p in tri]
        ys = [p[1] for tri in t for p in tri]
        zs = [p[2] for tri in t for p in tri]
        dx, dy, dz = -(min(xs) + max(xs)) / 2, y - min(ys), -min(zs)
        allt += [tuple((p[0] + dx, p[1] + dy, p[2] + dz) for p in tri) for tri in t]
        print(f'{Path(f).name}: {max(xs) - min(xs):.1f} x {max(ys) - min(ys):.1f} x {max(zs) - min(zs):.1f} mm')
        y += (max(ys) - min(ys)) + gap
    write_stl(out, allt)
    xs = [p[0] for tri in allt for p in tri]
    ys = [p[1] for tri in allt for p in tri]
    print(f'-> {out}: {max(xs) - min(xs):.1f} x {max(ys) - min(ys):.1f} mm on the bed, {len(allt)} triangles')


if __name__ == '__main__':
    main()
