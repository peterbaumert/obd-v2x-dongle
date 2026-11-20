"""Minimal KiCad 10 schematic writer with real wires.

Coordinates are in mm (KiCad schematic space, y down). Use g(n) for 2.54 mm grid units.
"""
import math
import uuid as _uuid
from pathlib import Path

from sexp import Sym, dump, find, first, parse

G = 2.54
HW = Path(__file__).resolve().parents[1]
from kicad_env import SYMBOLS as KICAD_SYM
PROJECT = 'obd-v2x-dongle'


def g(n):
    return round(n * G, 4)


def uid(seed):
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, 'obd-v2x/' + seed))


def S(x):
    return Sym(x)


# ------------------------------------------------------------------ library cache
_LIB = {}


def _load_cache_from_existing():
    """Flattened lib_symbols already written by KiCad 10 into the current sheets."""
    for f in HW.glob('*.kicad_sch'):
        try:
            t = parse(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        ls = first(t, 'lib_symbols')
        if ls:
            for s in find(ls, 'symbol'):
                _LIB.setdefault(s[1], s)


def _load_from_lib(lib_id):
    lib, name = lib_id.split(':', 1)
    path = HW / 'lib' / 'obd-v2x.kicad_sym' if lib == 'obd-v2x' else KICAD_SYM / f'{lib}.kicad_sym'
    t = parse(path.read_text(encoding='utf-8'))
    for s in find(t, 'symbol'):
        if s[1] == name:
            if first(s, 'extends'):
                raise ValueError(f'{lib_id} uses extends; place it once via KiCad first')
            s = list(s)
            s[1] = lib_id
            return s
    raise KeyError(lib_id)


def libsym(lib_id):
    if not _LIB:
        _load_cache_from_existing()
    if lib_id not in _LIB or (lib_id.startswith('obd-v2x:') and not getattr(libsym, 'fresh', set()) >= {lib_id}):
        _LIB[lib_id] = _load_from_lib(lib_id)   # project symbols: always from the library file
        libsym.fresh = getattr(libsym, 'fresh', set()) | {lib_id}
    return _LIB[lib_id]


def lib_pins(lib_id):
    out = []

    def walk(n):
        for e in n:
            if isinstance(e, list) and e and e[0] == 'pin':
                at = first(e, 'at')
                out.append(dict(num=first(e, 'number')[1], name=first(e, 'name')[1],
                                x=float(at[1]), y=float(at[2]), a=float(at[3])))
            elif isinstance(e, list) and e and e[0] == 'symbol':
                walk(e)
    walk(libsym(lib_id))
    return out


def is_power(lib_id):
    return first(libsym(lib_id), 'power') is not None


# ------------------------------------------------------------------ transforms
def xform(x, y, rot, mirror=None):
    """Library point (y up) -> offset in schematic (y down).
    KiCad rotates first, then mirrors (verified against kicad-cli netlists)."""
    r = math.radians(rot)
    xr = x * math.cos(r) - y * math.sin(r)
    yr = x * math.sin(r) + y * math.cos(r)
    if mirror == 'y':      # left/right flip
        xr = -xr
    elif mirror == 'x':    # up/down flip
        yr = -yr
    return round(xr, 4), round(-yr, 4)


def xdir(a, rot, mirror=None):
    """Library pin angle -> outward unit vector in schematic coords."""
    out = math.radians(a + 180)
    dx, dy = math.cos(out), math.sin(out)
    return xform(dx, dy, rot, mirror)


# ------------------------------------------------------------------ sheet
class Part:
    def __init__(self, sheet, lib_id, ref, value, fp, x, y, rot, mirror, fields, dnp, extra):
        self.sheet, self.lib_id, self.ref, self.value, self.fp = sheet, lib_id, ref, value, fp
        self.x, self.y, self.rot, self.mirror, self.fields, self.dnp = x, y, rot, mirror, fields, dnp
        self.extra = extra or {}
        self.pins = lib_pins(lib_id)

    def _pin(self, key):
        key = str(key)
        m = [p for p in self.pins if p['num'] == key]
        if not m:
            m = [p for p in self.pins if p['name'] == key]
        if not m:
            raise KeyError(f'{self.ref}: no pin {key}')
        return m[0]

    def p(self, key):
        pin = self._pin(key)
        dx, dy = xform(pin['x'], pin['y'], self.rot, self.mirror)
        return (round(self.x + dx, 4), round(self.y + dy, 4))

    def d(self, key):
        pin = self._pin(key)
        return xdir(pin['a'], self.rot, self.mirror)

    def out(self, key, n=1.0):
        """Point n grid units out from the pin tip."""
        (x, y), (dx, dy) = self.p(key), self.d(key)
        return (round(x + dx * g(n), 4), round(y + dy * g(n), 4))

    def __getitem__(self, key):
        return self.p(key)


class Sheet:
    def __init__(self, name, file, sheet_uuid, root_uuid, title='', paper='A4'):
        self.name, self.file, self.sheet_uuid, self.root_uuid = name, file, sheet_uuid, root_uuid
        self.title, self.paper = title, paper
        self.parts, self.wires, self.labels, self.ncs, self.texts = [], [], [], [], []
        self.pwr_n = 0

    # ---- placement
    def part(self, lib_id, ref, value, fp='', x=0, y=0, rot=0, mirror=None, fields=None, dnp=False, extra=None):
        p = Part(self, lib_id, ref, value, fp, x, y, rot, mirror, fields, dnp, extra)
        self.parts.append(p)
        return p

    def _pt(self, a):
        if isinstance(a, tuple) and len(a) == 2 and isinstance(a[0], Part):
            return a[0].p(a[1])
        return (round(a[0], 4), round(a[1], 4))

    # ---- wiring
    def w(self, *pts):
        pts = [self._pt(p) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a != b:
                self.wires.append((a, b))

    def hv(self, a, b):
        """L-route: horizontal first, then vertical."""
        a, b = self._pt(a), self._pt(b)
        self.w(a, (b[0], a[1]), b)

    def vh(self, a, b):
        a, b = self._pt(a), self._pt(b)
        self.w(a, (a[0], b[1]), b)

    def power(self, lib_id, at, rot=0):
        self.pwr_n += 1
        ref = f'#PWR{self.file[:1].upper()}{self.pwr_n:03d}'
        name = lib_id.split(':')[1]
        self.part(lib_id, ref, name, '', at[0], at[1], rot)

    def gnd(self, a, stub=0, rot=0):
        """GND symbol. rot 0 = points down, 90 = points right, 270 = points left."""
        a = self._pt(a)
        vec = {0: (0, 1), 90: (1, 0), 270: (-1, 0), 180: (0, -1)}[rot]
        b = (round(a[0] + vec[0] * g(stub), 4), round(a[1] + vec[1] * g(stub), 4))
        if stub:
            self.w(a, b)
        self.power('power:GND', b, rot)

    def rail(self, name, a, stub=0, rot=0):
        """Rail power symbol for net `name`. rot 0 = arrow up, 180 = down, 90 = left, 270 = right."""
        a = self._pt(a)
        vec = {0: (0, -1), 180: (0, 1), 90: (-1, 0), 270: (1, 0)}[rot]
        b = (round(a[0] + vec[0] * g(stub), 4), round(a[1] + vec[1] * g(stub), 4))
        if stub:
            self.w(a, b)
        lib = 'power:+3V3' if name == '+3V3' else f'obd-v2x:{name}'
        self.power(lib, b, rot)

    def glabel(self, name, a, side='R', shape='bidirectional', stub=0):
        """Global label. side = direction the label text extends from the connection point."""
        a = self._pt(a)
        vec = {'R': (1, 0), 'L': (-1, 0), 'U': (0, -1), 'D': (0, 1)}[side]
        b = (round(a[0] + vec[0] * g(stub), 4), round(a[1] + vec[1] * g(stub), 4))
        if stub:
            self.w(a, b)
        self.labels.append(('global_label', name, b, {'R': 0, 'L': 180, 'U': 90, 'D': 270}[side], shape))

    def label(self, name, a, side='R', stub=0):
        a = self._pt(a)
        vec = {'R': (1, 0), 'L': (-1, 0), 'U': (0, -1), 'D': (0, 1)}[side]
        b = (round(a[0] + vec[0] * g(stub), 4), round(a[1] + vec[1] * g(stub), 4))
        if stub:
            self.w(a, b)
        self.labels.append(('label', name, b, {'R': 0, 'L': 180, 'U': 90, 'D': 270}[side], None))

    def nc(self, part, key):
        self.ncs.append(part.p(key))

    def text(self, s, x, y, size=1.27, bold=False):
        self.texts.append((s, x, y, size, bold))

    # ---- output
    def _junctions(self):
        pts = {}

        def add(p, n=1):
            pts[p] = pts.get(p, 0) + n
        for a, b in self.wires:
            add(a)
            add(b)
        for part in self.parts:
            for loc in {part.p(pin['num']) for pin in part.pins}:
                add(loc)
        # T-junctions: wire endpoint lying inside another segment
        js = set()
        for p, n in pts.items():
            inner = 0
            for a, b in self.wires:
                if p in (a, b):
                    continue
                if (a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1])) or \
                   (a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0])):
                    inner += 2
            on_wire = any(p in (a, b) for a, b in self.wires) or inner
            if on_wire and n + inner >= 3:
                js.add(p)
        # stacked pins at the same spot are not junctions by themselves
        return sorted(js)

    def _field(self, key, val, x, y, hide=False, justify=None, angle=0):
        eff = [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]
        if justify:
            eff.append([S('justify')] + [S(j) for j in justify.split()])
        node = [S('property'), key, val, [S('at'), x, y, angle]]
        if hide:
            node.append([S('hide'), S('yes')])
        node.append(eff)
        return node

    def _symbol_node(self, p):
        lib = libsym(p.lib_id)
        power = is_power(p.lib_id)
        n = [S('symbol'), [S('lib_id'), p.lib_id], [S('at'), p.x, p.y, p.rot]]
        if p.mirror:
            n.append([S('mirror'), S(p.mirror)])
        n += [[S('unit'), 1], [S('exclude_from_sim'), S('no')],
              [S('in_bom'), S('no' if power or p.ref.startswith('#') else 'yes')],
              [S('on_board'), S('yes')], [S('dnp'), S('yes' if p.dnp else 'no')],
              [S('uuid'), uid(f'{self.file}/{p.ref}')]]
        f = p.fields or {}
        if power:
            # power symbols: hidden ref, value text placed by lib default
            libv = [e for e in find(lib, 'property') if e[1] == 'Value'][0]
            lx, ly = xform(float(first(libv, 'at')[1]), float(first(libv, 'at')[2]), p.rot, p.mirror)
            n.append(self._field('Reference', p.ref, p.x, p.y, hide=True))
            n.append(self._field('Value', p.value, round(p.x + lx, 4), round(p.y + ly, 4)))
        else:
            rx, ry, rj = f.get('ref', (p.x + g(1.5), p.y - 1.27, 'left'))
            vx, vy, vj = f.get('val', (p.x + g(1.5), p.y + 1.27, 'left'))
            # field angles are relative to the symbol: counter-rotate so text reads horizontally
            fa = 90 if p.rot % 180 == 90 else 0
            # justification is also relative: it flips for 180/270 (and flips back when mirrored up/down)
            if (p.rot + fa) % 360 == 180:
                sw = {'left': 'right', 'right': 'left'}
                rj, vj = sw.get(rj, rj), sw.get(vj, vj)
            n.append(self._field('Reference', p.ref, rx, ry, justify=rj, angle=fa))
            n.append(self._field('Value', p.value, vx, vy, justify=vj, angle=fa))
        n.append(self._field('Footprint', p.fp, p.x, p.y, hide=True))
        ds = [e for e in find(lib, 'property') if e[1] == 'Datasheet']
        n.append(self._field('Datasheet', ds[0][2] if ds else '', p.x, p.y, hide=True))
        for k, v in p.extra.items():
            n.append(self._field(k, v, p.x, p.y, hide=True))
        for pin in sorted({pp['num'] for pp in p.pins}):
            n.append([S('pin'), pin, [S('uuid'), uid(f'{self.file}/{p.ref}/{pin}')]])
        n.append([S('instances'), [S('project'), PROJECT,
                                   [S('path'), f'/{self.root_uuid}/{self.sheet_uuid}' if self.sheet_uuid else f'/{self.root_uuid}',
                                    [S('reference'), p.ref], [S('unit'), 1]]]])
        return n

    def build(self):
        used = []
        for p in self.parts:
            if p.lib_id not in used:
                used.append(p.lib_id)
        doc = [S('kicad_sch'), [S('version'), S('20260101')], [S('generator'), 'eeschema'],
               [S('generator_version'), '10.0'], [S('uuid'), uid('sheetfile/' + self.file)],
               [S('paper'), self.paper]]
        if self.title:
            doc.append([S('title_block'), [S('title'), self.title], [S('rev'), '0.1']])
        doc.append([S('lib_symbols')] + [libsym(u) for u in used])
        for jp in self._junctions():
            doc.append([S('junction'), [S('at'), jp[0], jp[1]], [S('diameter'), 0],
                        [S('color'), 0, 0, 0, 0], [S('uuid'), uid(f'{self.file}/j/{jp}')]])
        for i, p in enumerate(self.ncs):
            doc.append([S('no_connect'), [S('at'), p[0], p[1]], [S('uuid'), uid(f'{self.file}/nc/{p}')]])
        for i, (a, b) in enumerate(self.wires):
            doc.append([S('wire'), [S('pts'), [S('xy'), a[0], a[1]], [S('xy'), b[0], b[1]]],
                        [S('stroke'), [S('width'), 0], [S('type'), S('default')]],
                        [S('uuid'), uid(f'{self.file}/w/{i}/{a}{b}')]])
        for s, x, y, size, bold in self.texts:
            font = [S('font'), [S('size'), size, size]]
            if bold:
                font.append([S('bold'), S('yes')])
            doc.append([S('text'), s, [S('exclude_from_sim'), S('no')], [S('at'), x, y, 0],
                        [S('effects'), font, [S('justify'), S('left')]], [S('uuid'), uid(f'{self.file}/t/{s}{x}{y}')]])
        for kind, name, (x, y), ang, shape in self.labels:
            just = 'left' if ang == 0 else 'right'
            node = [S(kind), name]
            if shape:
                node.append([S('shape'), S(shape)])
            node += [[S('at'), x, y, ang], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify'), S(just)]],
                     [S('uuid'), uid(f'{self.file}/l/{name}/{x}/{y}')]]
            if kind == 'global_label':
                node.append([S('property'), 'Intersheetrefs', '${INTERSHEET_REFS}', [S('at'), x, y, 0],
                             [S('hide'), S('yes')], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]])
            doc.append(node)
        for p in self.parts:
            doc.append(self._symbol_node(p))
        doc.append([S('sheet_instances'), [S('path'), '/', [S('page'), '1']]])
        return dump(doc) + '\n'

    def write(self):
        (HW / self.file).write_text(self.build(), encoding='utf-8', newline='\n')
