"""Small grid maze router for finishing touches on the routed board (run with KiCad's Python).

    <KiCad>/bin/python hardware/tools/maze.py route NET X1 Y1 LAYER1 X2 Y2 LAYER2 [WIDTH]
    <KiCad>/bin/python hardware/tools/maze.py gndvias

Coordinates are board-relative mm (board origin at page 100, 50), layers F/In2/B.
`route` adds tracks/vias for one connection, avoiding all other-net copper with clearance.
`gndvias` gives every outer-layer GND SMD pad without a nearby GND via/hole its own via.
In1 is the GND plane and never gets tracks. Always run DRC afterwards.
"""
import heapq
import math
import os
import sys
from pathlib import Path

import numpy as np
import pcbnew

HW = Path(__file__).resolve().parents[1]
PCB = HW / 'obd-v2x-dongle.kicad_pcb'
OX, OY = 100.0, 50.0
RES = 0.1                      # grid, mm
CLR = float(os.environ.get('MAZE_CLR', 0.2))   # router clearance (rule is 0.15)
VIA_D, VIA_DR = 0.6, 0.3
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
LNAME = {'F': 0, 'In2': 1, 'B': 2}
VIA_COST = 12


def mm(v):
    return pcbnew.FromMM(float(v))


def tomm(v):
    return pcbnew.ToMM(v)


class Grid:
    def __init__(self, board):
        self.b = board
        bb = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = tomm(bb.GetLeft()), tomm(bb.GetTop())
        self.nx = int(tomm(bb.GetWidth()) / RES) + 1
        self.ny = int(tomm(bb.GetHeight()) / RES) + 1
        xs = self.x0 + np.arange(self.nx) * RES
        ys = self.y0 + np.arange(self.ny) * RES
        self.X, self.Y = np.meshgrid(xs, ys)          # [iy, ix]

    def cell(self, x, y):
        return int(round((y - self.y0) / RES)), int(round((x - self.x0) / RES))

    def pos(self, iy, ix):
        return self.x0 + ix * RES, self.y0 + iy * RES

    def _region(self, x0, y0, x1, y1):
        iy0, ix0 = self.cell(x0, y0)
        iy1, ix1 = self.cell(x1, y1)
        iy0, ix0 = max(iy0, 0), max(ix0, 0)
        iy1, ix1 = min(iy1 + 1, self.ny), min(ix1 + 1, self.nx)
        return slice(iy0, iy1), slice(ix0, ix1)

    def mark_rect(self, m, x0, y0, x1, y1, grow):
        s = self._region(x0 - grow, y0 - grow, x1 + grow, y1 + grow)
        m[s] = True

    def mark_seg(self, m, a, c, r):
        s = self._region(min(a[0], c[0]) - r, min(a[1], c[1]) - r, max(a[0], c[0]) + r, max(a[1], c[1]) + r)
        X, Y = self.X[s], self.Y[s]
        dx, dy = c[0] - a[0], c[1] - a[1]
        L2 = dx * dx + dy * dy
        t = np.zeros_like(X) if L2 == 0 else np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0, 1)
        d2 = (X - (a[0] + t * dx)) ** 2 + (Y - (a[1] + t * dy)) ** 2
        m[s] |= d2 <= r * r

    def obstacles(self, netname, hw):
        """per-layer blocked masks for a track of half-width hw, plus a via mask"""
        masks = [np.zeros((self.ny, self.nx), bool) for _ in LAYERS]
        vmask = np.zeros((self.ny, self.nx), bool)
        b = self.b
        r_tr = hw + CLR
        r_via = VIA_D / 2 + CLR
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == netname and netname:
                    continue
                bb = p.GetBoundingBox()
                x0, y0, x1, y1 = tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom())
                hole = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                extra = 0.15 if hole else 0.0          # hole-to-copper / hole-to-hole margin
                for i, L in enumerate(LAYERS):
                    if hole or p.IsOnLayer(L):
                        self.mark_rect(masks[i], x0, y0, x1, y1, r_tr + extra)
                        self.mark_rect(vmask, x0, y0, x1, y1, r_via + extra)
        for t in b.GetTracks():
            if t.GetNetname() == netname:
                continue
            if isinstance(t, pcbnew.PCB_VIA):
                c = (tomm(t.GetPosition().x), tomm(t.GetPosition().y))
                r = tomm(t.GetWidth(pcbnew.F_Cu)) / 2
                for m in masks:
                    self.mark_seg(m, c, c, r + r_tr)
                self.mark_seg(vmask, c, c, r + r_via + 0.05)
                continue
            if t.GetLayer() not in LAYERS:
                continue
            i = LAYERS.index(t.GetLayer())
            a = (tomm(t.GetStart().x), tomm(t.GetStart().y))
            c = (tomm(t.GetEnd().x), tomm(t.GetEnd().y))
            w = tomm(t.GetWidth()) / 2
            self.mark_seg(masks[i], a, c, w + r_tr)
            self.mark_seg(vmask, a, c, w + r_via + 0.05)   # grid-rounding margin
        # non-GND zones of other nets (e.g. none now) block their layer
        for z in b.Zones():
            if z.GetNetname() in ('GND', netname) or z.GetIsRuleArea():
                continue
            bb = z.GetBoundingBox()
            for i, L in enumerate(LAYERS):
                if z.IsOnLayer(L):
                    self.mark_rect(masks[i], tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom()), r_tr)
        # keep-out rule areas inside footprints (U.FL, SIM holder, ...) block tracks and vias
        for fp in b.GetFootprints():
            for z in fp.Zones():
                if not z.GetIsRuleArea():
                    continue
                bb = z.GetBoundingBox()
                x0, y0, x1, y1 = tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom())
                if z.GetDoNotAllowVias():
                    self.mark_rect(vmask, x0, y0, x1, y1, VIA_D / 2)
                if z.GetDoNotAllowTracks():
                    for i, L in enumerate(LAYERS):
                        if z.IsOnLayer(L):
                            self.mark_rect(masks[i], x0, y0, x1, y1, hw)
        # vias of any net (same net included) may not overlap: hole-to-hole spacing
        for t in b.GetTracks():
            if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == netname:
                c = (tomm(t.GetPosition().x), tomm(t.GetPosition().y))
                self.mark_seg(vmask, c, c, VIA_D + 0.25)
        # board edge
        edge = 0.4      # 0.3 mm rule + grid-rounding margin
        for m, r in [(m, r_tr - CLR + edge) for m in masks] + [(vmask, VIA_D / 2 + edge)]:
            k = int(math.ceil(r / RES))
            m[:k, :] = True; m[-k:, :] = True; m[:, :k] = True; m[:, -k:] = True
        return masks, vmask


def astar(grid, masks, vmask, starts, goals):
    """starts/goals: list of (layer, iy, ix). Returns list of (layer, iy, ix)."""
    goalset = set(goals)
    gl = [(g[1], g[2]) for g in goals]
    gy = np.array([g[0] for g in gl]); gx = np.array([g[1] for g in gl])

    def h(iy, ix):
        return float(np.min(np.hypot(gy - iy, gx - ix)))

    openq = []
    best = {}
    prev = {}
    for s in starts:
        best[s] = 0.0
        heapq.heappush(openq, (h(s[1], s[2]), 0.0, s))
    moves = [(0, 1, 1.0), (0, -1, 1.0), (1, 0, 1.0), (-1, 0, 1.0),
             (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    ny, nx = vmask.shape
    n = 0
    while openq:
        f, g, s = heapq.heappop(openq)
        if s in goalset:
            path = [s]
            while s in prev:
                s = prev[s]; path.append(s)
            return path[::-1]
        if g > best.get(s, 1e18):
            continue
        n += 1
        if n > 4_000_000:
            break
        L, iy, ix = s
        nbrs = []
        for dy, dx, c in moves:
            jy, jx = iy + dy, ix + dx
            if 0 <= jy < ny and 0 <= jx < nx and not masks[L][jy, jx]:
                nbrs.append(((L, jy, jx), c))
        if not vmask[iy, ix]:
            for L2 in range(len(LAYERS)):
                if L2 != L and not masks[L2][iy, ix]:
                    nbrs.append(((L2, iy, ix), VIA_COST))
        for t, c in nbrs:
            ng = g + c
            if ng < best.get(t, 1e18):
                best[t] = ng
                prev[t] = s
                heapq.heappush(openq, (ng + h(t[1], t[2]), ng, t))
    return None


def free_cells(grid, masks, x, y, L, radius=0.6):
    """cells near (x, y) on layer L that are free (the endpoint itself may sit in its own copper)"""
    iy, ix = grid.cell(x, y)
    k = int(radius / RES)
    out = []
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            jy, jx = iy + dy, ix + dx
            if 0 <= jy < masks[L].shape[0] and 0 <= jx < masks[L].shape[1] and not masks[L][jy, jx]:
                if dy * dy + dx * dx <= k * k:
                    out.append((L, jy, jx))
    return out


def commit_path(board, grid, path, netname, width, a_xy, b_xy):
    ni = board.FindNet(netname)
    pts = []
    for L, iy, ix in path:
        x, y = grid.pos(iy, ix)
        pts.append((L, x, y))
    # snap the ends exactly onto the requested points
    pts = [(pts[0][0], a_xy[0], a_xy[1])] + pts + [(pts[-1][0], b_xy[0], b_xy[1])]
    segs, vias = [], []
    cur = [pts[0]]
    for p in pts[1:]:
        if p[0] != cur[-1][0]:
            vias.append((cur[-1][1], cur[-1][2]))
            segs.append(cur)
            cur = [(p[0], cur[-1][1], cur[-1][2]), p]
        else:
            cur.append(p)
    segs.append(cur)
    n = 0
    for run in segs:
        # merge collinear points
        simp = [run[0]]
        for i in range(1, len(run) - 1):
            ax, ay = simp[-1][1], simp[-1][2]
            bx, by = run[i][1], run[i][2]
            cx, cy = run[i + 1][1], run[i + 1][2]
            if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-6:
                simp.append(run[i])
        simp.append(run[-1])
        for p, q in zip(simp, simp[1:]):
            if abs(p[1] - q[1]) < 1e-6 and abs(p[2] - q[2]) < 1e-6:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(mm(p[1]), mm(p[2]))); t.SetEnd(pcbnew.VECTOR2I(mm(q[1]), mm(q[2])))
            t.SetWidth(mm(width)); t.SetLayer(LAYERS[p[0]]); t.SetNet(ni)
            board.Add(t); n += 1
    for x, y in vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DR)); v.SetNet(ni)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(v)
    return n, len(vias)


def full_net(board, short):
    for n in board.GetNetsByName().keys():
        s = str(n)
        if s == short or s.endswith('/' + short):
            return s
    raise SystemExit(f'net {short} not found')


def route(board, net, a, La, c, Lc, width):
    grid = Grid(board)
    masks, vmask = grid.obstacles(net, width / 2)
    ax, ay = a[0] + OX, a[1] + OY
    cx, cy = c[0] + OX, c[1] + OY
    starts = free_cells(grid, masks, ax, ay, La)
    goals = free_cells(grid, masks, cx, cy, Lc)
    if not starts or not goals:
        raise SystemExit(f'{net}: no free cell at an endpoint ({len(starts)} / {len(goals)})')
    path = astar(grid, masks, vmask, starts, goals)
    if not path:
        raise SystemExit(f'{net}: no path found')
    n, v = commit_path(board, grid, path, net, width, (ax, ay), (cx, cy))
    print(f'{net}: {n} segments, {v} vias')


def gndvias(board):
    global CLR
    saved, CLR = CLR, max(CLR, 0.25)     # stitching vias also sit next to 0.2 mm-clearance power nets
    try:
        _gndvias(board)
    finally:
        CLR = saved


def _gndvias(board):
    grid = Grid(board)
    masks, vmask = grid.obstacles('GND', 0.15)
    gnd = board.FindNet('GND')
    have = [(tomm(t.GetPosition().x), tomm(t.GetPosition().y)) for t in board.GetTracks()
            if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == 'GND']
    have += [(tomm(p.GetPosition().x), tomm(p.GetPosition().y)) for fp in board.GetFootprints() for p in fp.Pads()
             if p.GetNetname() == 'GND' and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    added = 0
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != 'GND' or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            L = pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
            px, py = tomm(p.GetPosition().x), tomm(p.GetPosition().y)
            if any(math.hypot(px - hx, py - hy) < 1.5 for hx, hy in have):
                continue
            iy, ix = grid.cell(px, py)
            li = LAYERS.index(L)
            best = None
            for r in np.arange(0.6, 2.01, 0.1):
                for k in range(24):
                    a = 2 * math.pi * k / 24
                    vx, vy = px + r * math.cos(a), py + r * math.sin(a)
                    jy, jx = grid.cell(vx, vy)
                    if not (0 <= jy < grid.ny and 0 <= jx < grid.nx) or vmask[jy, jx]:
                        continue
                    # straight stub from pad to via must be free on the pad's layer
                    ok = True
                    for s in np.linspace(0.35, 1, 8):
                        sy, sx = grid.cell(px + (vx - px) * s, py + (vy - py) * s)
                        if masks[li][sy, sx]:
                            ok = False; break
                    if ok:
                        best = (vx, vy); break
                if best:
                    break
            if not best:
                print('no room for GND via at', fp.GetReference(), p.GetNumber())
                continue
            vx, vy = best
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DR)); v.SetNet(gnd)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(p.GetPosition()); t.SetEnd(pcbnew.VECTOR2I(mm(vx), mm(vy))); t.SetWidth(mm(0.3)); t.SetLayer(L); t.SetNet(gnd)
            board.Add(t)
            have.append((vx, vy))
            # block the new via for the following pads
            grid.mark_seg(vmask, (vx, vy), (vx, vy), VIA_D + CLR)
            for m in masks:
                grid.mark_seg(m, (vx, vy), (vx, vy), VIA_D / 2 + CLR + 0.15)
            added += 1
    print('GND vias added', added)


if __name__ == '__main__':
    board = pcbnew.LoadBoard(str(PCB))
    if sys.argv[1] == 'route':
        net = full_net(board, sys.argv[2])
        a = (float(sys.argv[3]), float(sys.argv[4])); La = LNAME[sys.argv[5]]
        c = (float(sys.argv[6]), float(sys.argv[7])); Lc = LNAME[sys.argv[8]]
        w = float(sys.argv[9]) if len(sys.argv) > 9 else 0.2
        route(board, net, a, La, c, Lc, w)
    elif sys.argv[1] == 'gndvias':
        gndvias(board)
    board.Save(str(PCB))
