"""Update the routed PCB from the schematic (KiCad's "Update PCB from Schematic", scripted).

    <KiCad>/bin/python hardware/tools/sync_pcb.py [--dry-run]

- adds footprints that are new in the schematic (positions from NEW_PLACE, else packed next to an anchor pad)
- swaps footprints whose library footprint changed (same place and side, turned to keep each net's pads near
  their old spots); their tracks then end at the old pad positions and need reconnecting
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
    # GNSS antenna bias: switch in the free top-side area below the U.FL sockets, choke + RF bypass at J403
    'U405': (41.0, 58.5, 0, T),
    'L401': (44.2, 52.95, 270, T),   # pad 2 on the GNSS line next to J403's centre pin
    'C418': (43.0, 52.3, 180, T),    # pad 1 (bias side) towards L401
}
# small parts: ref: (anchor ref, anchor pad)
NEW_ANCHOR = {'R415': ('U405', '5'), 'C419': ('U405', '6'), 'C420': ('U405', '1')}
# nets whose existing copper must go (pad membership split; would short the new nets)
RIP_NETS = set()
# nets renamed in the schematic: existing copper is moved to the new name
RENAME_NETS = {'Net-(Q102-G)': 'LTE_PWR_ON_N', 'Net-(J403-In)': '/LTE + GNSS (EC200U)/LTE_ANT_GNSS_UFL'}


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

    # footprints changed in the schematic: swap in place (same position and side), turned so that each
    # net's pads land as close as possible to where that net's pads were; the copper is left as it is
    for ref, c in comps.items():
        old = fps.get(ref)
        if old is None:
            continue
        cur = old.GetFPID()
        if f'{cur.GetLibNickname()}:{cur.GetLibItemName()}' == c['fp']:
            continue
        was = {}
        for p in old.Pads():
            if p.GetNetname() and not p.GetNetname().startswith('unconnected-'):
                was.setdefault(p.GetNetname(), []).append(p.GetPosition())
        new = G.load_fp(c['fp'])
        board.Add(new)
        for k, v in c['fields'].items():
            if k not in ('Footprint', 'Datasheet', 'Description'):
                new.SetField(k, v)
                new.GetField(k).SetVisible(False)
        new.SetReference(ref)
        new.SetValue(c['value'])
        new.SetPath(pcbnew.KIID_PATH(c['sheetstamps'] + c['stamp']))
        new.SetSheetname(old.GetSheetname())
        new.SetSheetfile(old.GetSheetfile())
        new.Reference().SetTextSize(old.Reference().GetTextSize())
        new.Reference().SetTextThickness(old.Reference().GetTextThickness())
        new.Value().SetVisible(False)
        if old.IsFlipped():
            new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        new.SetPosition(old.GetPosition())
        best = None
        for rot in (0, 90, 180, 270):
            new.SetOrientationDegrees(rot)
            cost = 0
            for p in new.Pads():
                want = nets.get((ref, p.GetNumber()))
                if want in was:
                    cost += min((p.GetPosition() - q).EuclideanNorm() for q in was[want])
            if best is None or cost < best[0]:
                best = (cost, rot)
        new.SetOrientationDegrees(best[1])
        new.Reference().SetPosition(old.Reference().GetPosition())
        board.Remove(old)
        fps[ref] = new
        print(f'  {ref}: footprint {cur.GetLibItemName()} -> {c["fp"]} (rot {best[1]}); reconnect its tracks')

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

    # renamed nets: copper follows
    for t in board.GetTracks():
        if t.GetNetname() in RENAME_NETS:
            t.SetNet(net(RENAME_NETS[t.GetNetname()]))
    for z in board.Zones():
        if z.GetNetname() in RENAME_NETS:
            z.SetNet(net(RENAME_NETS[z.GetNetname()]))

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
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.15))
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
        if t.IsLocked():            # pre-routes (RF lines, SW node) stay; DRC shows any real conflict
            continue
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
