#!/usr/bin/env python3
"""Regular blocks of the timing ablation grouped by the execution thread's slot misses under stock reth: what plans add.
Inputs: results/main/raw/e270abl-{0,4,8}/results/blocks_abl*.csv (rows H0, H3, H4, H5) and
paper/data/f270_blockreads_blocks.csv.
usage: python3 paper/scripts/plans_by_reads270.py > paper/data/f270_plans_by_reads.txt"""
import collections
import csv
import glob
import random
import statistics as st

import os
P = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repository root
E = f'{P}/results/main'
reads = {int(r['block']): (r['cls'], int(r['slot_miss']))
         for r in csv.DictReader(open(f'{P}/paper/data/f270_blockreads_blocks.csv'))}
K = ['new_payload_ms', 'exec_ms', 'proc_cpu_ms']
C = ['H0', 'H3', 'H4', 'H5']
d = collections.defaultdict(lambda: collections.defaultdict(list))
files = sorted(glob.glob(f'{E}/raw/e270abl-*/results/blocks_abl*.csv'))
for f in files:
    for r in csv.DictReader(open(f)):
        if r['role'] == 'measured' and r['cfg'] in C:
            d[int(r['block'])][r['cfg']].append([float(r[k] or 0) for k in K])
blocks = sorted(b for b, v in d.items() if b in reads and all(c in v for c in C))
mean = {b: {c: [st.mean(x[i] for x in d[b][c]) for i in range(len(K))] for c in C} for b in blocks}
reg = sorted((reads[b][1], b) for b in blocks if reads[b][0] == 'nomint')
print(f'# files: {len(files)}; blocks with all four rows: {len(blocks)}; regular: {len(reg)}')
print('# groups by the block slot misses in the recorder process (f257_blockreads_blocks.csv slot_miss)')


def ratio_ci(g, a, b):
    seg = collections.defaultdict(list)
    for _, blk in g:
        seg[blk // 10].append(blk)
    seg = list(seg.values())
    rng = random.Random(20261108)
    draws = []
    for _ in range(2000):
        s = [rng.choice(seg) for _ in seg]
        num = sum(mean[x][a][0] for grp in s for x in grp)
        den = sum(mean[x][b][0] for grp in s for x in grp)
        draws.append(num / den)
    draws.sort()
    return sum(mean[x][a][0] for _, x in g) / sum(mean[x][b][0] for _, x in g), draws[50], draws[1949]


def report(name, g):
    m = {c: st.mean(mean[x][c][0] for _, x in g) for c in C}
    out = [f'{name}: {len(g)} blocks, misses {g[0][0]}-{g[-1][0]}',
           ' '.join(f'{c} {m[c]:.2f}' for c in C)]
    for a, b in [('H4', 'H0'), ('H4', 'H3'), ('H5', 'H0')]:
        r, lo, hi = ratio_ci(g, a, b)
        out.append(f'{a}/{b} {r:.3f} ({lo:.3f}-{hi:.3f})')
    dn = st.mean(mean[x]['H4'][0] - mean[x]['H3'][0] for _, x in g)
    de = st.mean(mean[x]['H4'][1] - mean[x]['H3'][1] for _, x in g)
    dc = st.mean(mean[x]['H4'][2] - mean[x]['H3'][2] for _, x in g)
    out.append(f'G4-G3 newPayload {dn:+.2f} ms, execution {de:+.2f}, outside {dn - de:+.2f}, process CPU {dc:+.1f}')
    print('  '.join(out))


n = len(reg)
report('all regular', reg)
for q in range(5):
    report(f'quintile {q + 1}', reg[q * n // 5:(q + 1) * n // 5])
report('lightest 80%', reg[:int(0.8 * n)])
report('top 10%', reg[int(0.9 * n):])
