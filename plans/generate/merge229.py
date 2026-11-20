#!/usr/bin/env python3
"""export-time merge of family call groups whose target and payload do
not use a loop index and that have no key index (nkey = 0), by expression structure only.
Per plan: such groups with the same kind, target and payload structure (eapf.Canon) form a class; the class keeps its
first group, all alternatives of the class point to it (union of the alternatives, original order, so the selector
order of `fcalts` is kept); alternatives of a kept group whose structure (selector, extra selectors, fixed-index lists
with the indices renamed by position, multi-index list) equals an earlier one are dropped; a kept group whose
alternatives have no fixed-index list, no multi-index list and no extra selector is rewritten as an index-free call group
(cgroups / calts with an empty condition list, calts re-sorted stably by selector). Removed family groups are renumbered.
Plans without a change are written byte for byte.
usage: merge229.py SRC_DIR DST_DIR STATS.csv [SHARD NSHARDS]   (files i % NSHARDS == SHARD; stats get .s<SHARD>)"""
import csv, os, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eapf
from eapf import NONE32
SRC, DST, ST = sys.argv[1:4]
SH, NSH = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (0, 1)
if NSH > 1: ST = f'{ST}.s{SH}'
os.makedirs(DST, exist_ok=True)
t0 = time.time()
COLS = ['plan', 'changed', 'fcgroups', 'fcgroups_after', 'fcalts', 'fcalts_after', 'free0', 'classes', 'classes_multi', 'groups_merged',
        'alts_dropped', 'converted', 'calts_added', 'cgroups', 'cgroups_after']


def merge(p):
    s = defaultdict(int)
    s['fcgroups'] = len(p.fcgroups); s['fcalts'] = len(p.fcalts); s['cgroups'] = len(p.cgroups)
    C = eapf.Canon(p)
    rep = {}; cls = {}
    for g, cg in enumerate(p.fcgroups):
        if cg[5] != 0: continue
        ns = C.call_nodes(cg)
        if any(eapf.dep(p, j) for j in ns): continue
        ids = set()
        for j in ns: eapf.idx_ids(p, j, ids)
        assert not ids, (g, ids)   # the dependency flag and the subtree agree
        s['free0'] += 1
        k = C.target(cg)
        if k not in cls: cls[k] = g
        rep[g] = cls[k]
    s['classes'] = len(cls)
    members = defaultdict(int)
    for g, r in rep.items(): members[r] += 1
    s['classes_multi'] = sum(1 for v in members.values() if v > 1)
    s['groups_merged'] = sum(v - 1 for v in members.values())
    # alternatives: re-point, drop structural duplicates within a kept group
    seen = set(); alts = []
    for al in p.fcalts:
        g = al[0]
        if g in rep:
            key = (rep[g], C.falt(al))
            if key in seen: s['alts_dropped'] += 1; continue
            seen.add(key); al = [rep[g]] + list(al[1:])
        alts.append(list(al))
    # rewrite as index-free call groups where no index condition is left
    by = defaultdict(list)
    for i, al in enumerate(alts): by[al[0]].append(i)
    conv = set()
    for r in set(rep.values()):
        ix = by.get(r, [])
        if ix and all(alts[i][5] == 0 and alts[i][8] == NONE32 and alts[i][4] == 0 for i in ix): conv.add(r)
    s['converted'] = len(conv)
    changed = s['groups_merged'] > 0 or s['alts_dropped'] > 0 or conv
    if not changed: return None, s
    if conv:
        empty = next((i for i in range(len(p.list_off) - 1) if p.list_off[i] == p.list_off[i + 1]), None)
        if empty is None: p.list_off.append(p.list_off[-1]); empty = len(p.list_off) - 2
        newc = []
        for r in sorted(conv):
            cg = p.fcgroups[r]; gi = len(p.cgroups)
            p.cgroups.append([cg[0], cg[1], cg[2], cg[3], cg[4], 0])
            sels = []
            for i in by[r]:
                k = (alts[i][1], alts[i][2] if alts[i][1] else 0)
                if k not in sels: sels.append(k)
            for hs, sl in sels: newc.append([gi, hs, sl, empty])
            s['calts_added'] += len(sels)
        calts = [list(a) for a in p.calts] + newc
        p.calts = sorted(calts, key=lambda a: (a[1], a[2] if a[1] else 0))   # stable: generic first, then by selector
        alts = [al for al in alts if al[0] not in conv]
    keep = [g for g in range(len(p.fcgroups)) if not (g in rep and (rep[g] != g or g in conv))]
    newi = {g: i for i, g in enumerate(keep)}
    p.fcgroups = [p.fcgroups[g] for g in keep]
    p.fcalts = [[newi[al[0]]] + al[1:] for al in alts]
    s['fcgroups_after'] = len(p.fcgroups); s['fcalts_after'] = len(p.fcalts); s['cgroups_after'] = len(p.cgroups)
    return eapf.to_bytes(p), s


rows = []
names = sorted(f for f in os.listdir(SRC) if f.endswith('.eapf'))
for n_, fn in enumerate(names):
    if n_ % NSH != SH: continue
    if n_ % 2000 < NSH: print('progress', n_, round(time.time() - t0), flush=True, file=sys.stderr)
    with open(os.path.join(SRC, fn), 'rb') as fh: b = fh.read()
    p = eapf.parse(b)
    out = None; s = {}
    if p.kind == 0 and p.fcgroups:
        out, s = merge(p)
    with open(os.path.join(DST, fn), 'wb') as fh: fh.write(b if out is None else out)
    if s:
        s = dict(s); s['plan'] = fn[:-5]; s['changed'] = int(out is not None)
        if out is None: s['fcgroups_after'] = s['fcgroups']; s['fcalts_after'] = s['fcalts']; s['cgroups_after'] = s['cgroups']
        rows.append(s)
with open(ST, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader()
    for r in rows: w.writerow({k: r.get(k, 0) for k in COLS})
tot = defaultdict(int)
for r in rows:
    for k in COLS[1:]: tot[k] += r.get(k, 0)
print('done', len(rows), dict(tot), round(time.time() - t0), 's')
