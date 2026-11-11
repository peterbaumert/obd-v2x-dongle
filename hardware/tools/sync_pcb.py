"""Update the routed PCB from the schematic (KiCad's "Update PCB from Schematic", scripted).

    <KiCad>/bin/python hardware/tools/sync_pcb.py [--dry-run]

- adds footprints that are new in the schematic (positions from NEW_PLACE, else packed next to an anchor pad)
- updates value, fields, DNP / BOM flags and pad nets of existing footprints
- deletes tracks/vias of nets whose pad membership changed in a way that could short (listed nets are re-routed later)
- reports footprints that are on the board but no longer in the schematic (not deleted automatically)
Afterwards: route the new connections (maze.py / KiCad), refill zones, DRC with --schematic-parity.
"""
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
import gen_pcb as G  # noqa: E402  (netlist reader, footprint loader, placement helpers)

T, B = G.T, G.B
# new parts: ref: (x, y, rot, side)  -- board-relative mm, top view
NEW_PLACE = {
    # backup battery block, bottom side under the modem
    'U502': (45.0, 48.5, 0, B),
    'C506': (44.5, 54.0, 0, B),
    'U501': (36.0, 50.0, 0, B),
    'J501': (31.5, 59.3, 0, B),
    # eSIM next to the nano-SIM holder and the modem's SIM pins
    'U403': (23.0, 53.5, 90, B),
}
# small parts: ref: (anchor ref, anchor pad)
NEW_ANCHOR = {
    'C507': ('U502', '1'), 'R505': ('U502', '6'), 'R506': ('U502', '6'), 'R507': ('U502', '10'), 'C504': ('U502', '11'),
    'R501': ('U501', '1'), 'D501': ('U501', '1'), 'C501': ('U501', '1'), 'C502': ('U501', '10'),
    'R502': ('U501', '2'), 'R503': ('U501', '9'), 'R504': ('U501', '6'), 'RT501': ('J501', '1'), 'C505': ('J501', '1'),
    'R411': ('U403', '3'), 'R412': ('U403', '6'), 'R413': ('U403', '7'), 'C415': ('U403', '8'),
}
# nets whose existing copper must go (pad membership split; would short the new nets)
RIP_NETS = set()   # e.g. {'VSYS_3V8'} when a net is split (was used for the backup-battery change)


def main(dry):
    comps, nets = G.read_netlist()
    board = pcbnew.LoadBoard(str(G.PCB))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    netinfo = {str(n): ni for n, ni in board.GetNetsByName().items()}

    def net(name):
        if name not in netinfo:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            netinfo[name] = ni
            print('  new net', name)
        return netinfo[name]

    gone = [r for r in fps if r not in comps and not r.startswith(('FID', 'REF', '#'))]
    if gone:
        print('on board but not in schematic (left alone):', ' '.join(gone))

    # existing footprints: fields, DNP, pad nets
    changed_pads = 0
    for ref, c in comps.items():
        fp = fps.get(ref)
        if fp is None:
            continue
        if fp.GetValue() != c['value']:
            print(f'  {ref}: value {fp.GetValue()} -> {c["value"]}')
            fp.SetValue(c['value'])
        for k, v in c['fields'].items():
            if k in ('Datasheet', 'Description'):
                fp.GetField(k).SetText(v)
            elif k != 'Footprint':
                fp.SetField(k, v)
                fp.GetField(k).SetVisible(False)
        if fp.IsDNP() != c['dnp']:
            print(f'  {ref}: DNP {fp.IsDNP()} -> {c["dnp"]}')
            fp.SetDNP(c['dnp'])
        fp.SetExcludedFromBOM(c['no_bom'])
        for p in fp.Pads():
            want = nets.get((ref, p.GetNumber()))
            if want and p.GetNetname() != want:
                p.SetNet(net(want))
                changed_pads += 1
    print('pad nets changed:', changed_pads)

    # remove copper of split nets
    rip = [t for t in board.GetTracks() if t.GetNetname() in RIP_NETS]
    for t in rip:
        board.Delete(t)
    print('ripped track/via items:', len(rip), 'on', ', '.join(sorted(RIP_NETS)))

    # new footprints
    placed = {T: [], B: []}
    for fp in board.GetFootprints():
        side = B if fp.IsFlipped() else T
        placed[side].append((fp.GetReference(), G.crt_box(fp)))
        holes = [p for p in fp.Pads() if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)]
        if holes:
            xs = [pcbnew.ToMM(p.GetPosition().x) - G.OX for p in holes]
            ys = [pcbnew.ToMM(p.GetPosition().y) - G.OY for p in holes]
            placed[T if side == B else B].append((fp.GetReference() + '-pins',
                                                   (min(xs) - 1.5, min(ys) - 1.5, max(xs) + 1.5, max(ys) + 1.5)))
    new = [r for r in comps if r not in fps]
    missing = [r for r in new if r not in NEW_PLACE and r not in NEW_ANCHOR]
    if missing:
        raise SystemExit(f'no placement for new parts: {missing}')

    def make(ref):
        c = comps[ref]
        fp = G.load_fp(c['fp'])
        board.Add(fp)
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        for k, v in c['fields'].items():
            if k in ('Datasheet', 'Description'):
                fp.GetField(k).SetText(v)
            elif k != 'Footprint':
                fp.SetField(k, v)
                fp.GetField(k).SetVisible(False)
        fp.SetPath(pcbnew.KIID_PATH(c['sheetstamps'] + c['stamp']))
        fp.SetSheetname(c['sheetnames'])
        fp.SetSheetfile(c['sheetfile'])
        fp.SetDNP(c['dnp'])
        fp.SetExcludedFromBOM(c['no_bom'])
        for p in fp.Pads():
            n = nets.get((ref, p.GetNumber()))
            if n:
                p.SetNet(net(n))
        fp.Value().SetVisible(False)
        sz = pcbnew.FromMM(0.8)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(sz, sz))
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.12))
        fps[ref] = fp
        return fp

    def free(bx, side):
        return G.inside(bx) and all(not G.overlaps(bx, o) for _, o in placed[side])

    for ref in [r for r in new if r in NEW_PLACE]:
        x, y, rot, side = NEW_PLACE[ref]
        fp = make(ref)
        G.place(fp, x, y, rot, side)
        bx = G.crt_box(fp)
        clash = [r for r, o in placed[side] if G.overlaps(bx, o)]
        if clash:
            print(f'  WARNING {ref} overlaps {clash}')
        placed[side].append((ref, bx))
        print(f'  placed {ref} at ({x}, {y}) {side}')

    import math
    for ref in [r for r in new if r in NEW_ANCHOR]:
        aref, apad = NEW_ANCHOR[ref]
        fp = make(ref)
        side = B if fps[aref].IsFlipped() else T
        ax, ay = G.pad_xy(fps[aref], apad)
        best = None
        for rot in (0, 90):
            G.place(fp, ax, ay, rot, side)
            for ring in range(0, 120):
                rr = ring * 0.5
                steps = max(1, int(2 * math.pi * rr / 0.5))
                hit = None
                for k in range(steps):
                    a = 2 * math.pi * k / steps
                    x, y = round((ax + rr * math.cos(a)) * 4) / 4, round((ay + rr * math.sin(a)) * 4) / 4
                    fp.SetPosition(G.pt(x, y))
                    if free(G.crt_box(fp), side):
                        hit = (rr, x, y, rot)
                        break
                if hit:
                    break
            if hit and (best is None or hit[0] < best[0]):
                best = hit
        if best is None:
            raise SystemExit(f'no room for {ref}')
        _, x, y, rot = best
        G.place(fp, x, y, rot, side)
        placed[side].append((ref, G.crt_box(fp)))
        print(f'  packed {ref} near {aref}.{apad} at ({x}, {y}) {side}')

    # existing copper under the new parts: same-side tracks crossing their courtyard and vias inside it
    ripped_nets = set()
    newfps = [fps[r] for r in new]
    for t in list(board.GetTracks()):
        for fp in newfps:
            side_layer = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
            bb = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
            bb.Inflate(pcbnew.FromMM(0.2))
            if isinstance(t, pcbnew.PCB_VIA):
                hit = bb.Contains(t.GetPosition())
            else:
                hit = t.GetLayer() == side_layer and (bb.Contains(t.GetStart()) or bb.Contains(t.GetEnd())
                                                      or bb.Intersects(pcbnew.BOX2I(t.GetStart(), t.GetEnd() - t.GetStart())))
            if hit:
                ripped_nets.add(t.GetNetname())
                board.Delete(t)
                break
    print('copper removed under new parts, nets to re-route:', ', '.join(sorted(n.split('/')[-1] for n in ripped_nets)))

    if dry:
        print('dry run: not saved')
        return
    board.Save(str(G.PCB))
    print('saved', G.PCB.name)


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
