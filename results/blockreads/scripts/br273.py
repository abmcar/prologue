#!python3
"""Per-block slot reads of the 10,000 blocks of the main comparison.
Inputs: results/blockreads/recorded_10k_blocks.csv (one recording process over the 10,000 blocks, row without
prewarming; unpack the .zst first), paper/data/f270_blockreads_blocks.csv (the 2,700 blocks of the recording processes,
for a block-by-block check), the main comparison's block files and measurement/block_classes.csv.
  [1] check of the slot reads against the 2,700-block file (they must be equal)
  [2] data file results/br273_blocks.csv: block, cls, slot_reads, slot_miss, mgas, np_up, np_ur, np_pn
  [3] tenths of the blocks by slot reads: ratios with 95% intervals
  [4] windows of WINSIZE blocks moved by WINSTEP over the blocks sorted by slot reads
usage: cd results/blockreads && python3 scripts/br273.py > results/br273.txt"""
import csv, glob, os, sys
import numpy as np
P = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # repository root
RUN = os.environ.get('RUN', f'{P}/results/blockreads/recorded_10k_blocks.csv')
SRC = ('pw', 'old', 'eap', 'cs0', 'cs1')
WINSIZE, WINSTEP = int(os.environ.get('WINSIZE', '1000')), int(os.environ.get('WINSTEP', '200'))
CL = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(f'{P}/measurement/block_classes.csv'))}
X = {}
for r in csv.DictReader(open(RUN)):
    if r['role'] == 'measured':
        X[int(r['block'])] = (sum(float(r[f'slot_hit_{s}'] or 0) for s in SRC) + float(r['slot_miss'] or 0), float(r['slot_miss'] or 0),
                              float(r['gas_used'] or 0) / 1e6, {s: float(r[f'slot_hit_{s}'] or 0) for s in SRC})
print(f'br273: x273 measured blocks {len(X)} ({min(X)}-{max(X)})')
F = {int(r['block']): r for r in csv.DictReader(open(f'{P}/paper/data/f270_blockreads_blocks.csv'))}
both = sorted(b for b in F if b in X)
d = np.array([X[b][0] - float(F[b]['slot_reads']) for b in both])
eq = int((d == 0).sum())
print(f'\n[1] check against f270_blockreads_blocks.csv: {len(both)} of {len(F)} blocks present; equal {eq}; '
      f'differences min {d.min():.0f}, 1% {np.percentile(d, 1):.0f}, 50% {np.median(d):.0f}, 99% {np.percentile(d, 99):.0f}, max {d.max():.0f}')
dm = np.array([X[b][1] - float(F[b]['slot_miss']) for b in both])
print(f'    slot_miss (depends on the cache state, not expected equal): equal {int((dm == 0).sum())}, median difference {np.median(dm):.0f}')
for b in [b for b in both if X[b][0] != float(F[b]['slot_reads'])][:10]:
    print(f'    {b}: x273 {X[b][0]:.0f} (' + ' '.join(f'{s} {X[b][3][s]:.0f}' for s in SRC) + f' miss {X[b][1]:.0f}), paper {F[b]["slot_reads"]}')
if eq != len(both) or len(both) != len(F):
    print('    not all equal: stop before [2]-[4]'); sys.exit(0 if os.environ.get('CHECK_ONLY') else 1)
M = {c: {} for c in ('up', 'ur', 'pn')}
for c in M:
    for f in glob.glob(f'{P}/results/main/raw/e270{c}-[0-9]/results/blocks_*.csv'):
        for r in csv.DictReader(open(f)):
            if r['role'] == 'measured':   # all measured blocks, as ana257 (each main-comparison process runs one column, no rotation)
                M[c][int(r['block'])] = float(r['new_payload_ms'])
B = sorted(b for b in X if all(b in M[c] for c in M))
print(f'\n[2] blocks under all three columns of the main comparison and in x273: {len(B)}')
with open('results/br273_blocks.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['block', 'cls', 'slot_reads', 'slot_miss', 'mgas', 'np_up', 'np_ur', 'np_pn'])
    for b in B:
        w.writerow([b, CL.get(b, ''), int(X[b][0]), int(X[b][1]), f'{X[b][2]:.3f}', f'{M["up"][b]:.6f}', f'{M["ur"][b]:.6f}', f'{M["pn"][b]:.6f}'])
rng0 = 247
def ratio(bs, a, c):
    va = np.array([M[a][b] for b in bs]); vc = np.array([M[c][b] for b in bs])
    rng = np.random.default_rng(rng0); n = len(bs)
    sims = [(lambda i: va[i].sum() / vc[i].sum())(rng.integers(0, n, n)) for _ in range(2000)]
    return va.sum() / vc.sum(), np.percentile(sims, 2.5), np.percentile(sims, 97.5)
f = lambda t: f'{t[0]:.3f} ({t[1]:.3f}-{t[2]:.3f})'
order = sorted(B, key=lambda b: X[b][0])   # stable over ascending block number
print('\n[3] the tenth with the most slot reads')
for name, bs in (('all blocks', order), ('regular blocks', [b for b in order if CL.get(b) == 'nomint'])):
    top = bs[int(0.9 * len(bs)):]
    print(f'  {name}: {len(top)} blocks, reads {X[top[0]][0]:.0f}-{X[top[-1]][0]:.0f}; PN/UP {f(ratio(top, "pn", "up"))}, PN/UR {f(ratio(top, "pn", "ur"))}')
print(f'\n[4] windows of {WINSIZE} blocks by slot reads, moved by {WINSTEP}')
i = 0; k = 0
while i + WINSIZE <= len(order):
    wb = order[i:i + WINSIZE]; k += 1
    rd = [X[b][0] for b in wb]
    print(f'  window {k:2d}: reads {min(rd):.0f}-{max(rd):.0f} (median {np.median(rd):.1f}), {sum(1 for b in wb if CL.get(b) == "mint")} batch-mint; '
          f'PN/UP {f(ratio(wb, "pn", "up"))}, PN/UR {f(ratio(wb, "pn", "ur"))}, UR/UP {f(ratio(wb, "ur", "up"))}')
    i += WINSTEP
