#!/usr/bin/env python3
"""Intervals for the cells of the main table that results/main/results/ana270.txt does not print (execution time by
block class), with the resampling of results/main/scripts/ana257.py: 2,000 resamples of 10-block groups within each
segment, same seed.
Run from the repository root:  python3 paper/scripts/table2_ci270.py > paper/data/f270_table2_ci.txt"""
import csv, glob
import numpy as np
E = 'results/main/raw'
CLS = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open('measurement/block_classes.csv'))}
SEG0 = 26305830
V = {}
for k in range(10):
    for lab, c in (('up', 'UP'), ('ur', 'UR'), ('un', 'UN'), ('pn', 'PN')):
        for fn in glob.glob(f'{E}/e270{lab}-{k}/results/blocks_*.csv'):
            for r in csv.DictReader(open(fn)):
                if r['role'] == 'measured':
                    V.setdefault((k, int(r['block'])), {})[c] = (float(r['new_payload_ms']), float(r['exec_ms']))
keys = sorted(x for x in V if len(V[x]) == 4)
rng = np.random.default_rng(20261106)
ms_of = lambda k: SEG0 + 300 + 1 + 1000 * k   # first measured block of segment k
g = {}
for i, (k, b) in enumerate(keys):
    g.setdefault((k, (b - ms_of(k)) // 10), []).append(i)
byk = {}
for s in g:
    byk.setdefault(s[0], []).append(s)
draws = []
for _ in range(2000):
    pick = []
    for k, ss in sorted(byk.items()):
        for j in rng.integers(0, len(ss), len(ss)):
            pick.extend(g[ss[j]])
    draws.append(np.array(pick))
A = {c: np.array([V[x][c] for x in keys]) for c in ('UP', 'UR', 'UN', 'PN')}
reg = np.array([CLS.get(b) == 'nomint' for _, b in keys]); sel = {'all': np.ones(len(keys), bool), 'regular': reg, 'batch-mint': ~reg}
print(f'{len(keys)} blocks, {len(g)} groups')
for a, b in (('PN', 'UP'), ('PN', 'UR')):
    for col, name in ((0, 'newPayload'), (1, 'execution')):
        for sn, s in sel.items():
            x, y = A[a][:, col], A[b][:, col]
            bs = [x[ix][s[ix]].sum() / y[ix][s[ix]].sum() for ix in draws]
            lo, hi = np.percentile(bs, [2.5, 97.5])
            print(f'{a}/{b} {name:10s} {sn:10s} {x[s].sum() / y[s].sum():.3f} ({lo:.3f}-{hi:.3f})')
