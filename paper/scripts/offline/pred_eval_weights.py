#!python3
"""Offline prediction comparison (Figure 5, Section 7.2) over all blocks under two compositions (11-07, review item 2;
Weights the observation's all-block numbers by the composition of the evaluated blocks).
Adapted from experiments/prediction-vs-official/scripts/table216_all.py (same inputs, same per-class sums, same
stratified bootstrap: numpy default_rng(216), 2,000 draws per class drawn general first, percentile intervals); changes:
  - the class weights are a parameter: POP=pop scales the samples (931 regular, 193 batch-mint blocks with a 2.9.0 weight) to
    the blocks of 26,263,606-26,268,604 (3,419 and 1,580, as the paper so far); POP=eval scales them to the composition of
    the evaluated blocks (8,950 regular and 1,050 batch-mint of the 10,000 blocks of the main comparison, 10.5%);
  - more methods in one table: from results/b3/eval_{general,mint}/blocks.csv (2.9.0 weights) P2, P2t, predictal,
    dowse_main_all, gh_all, P1d; from results/b3/hist_eval_{general,mint}/blocks.csv hist_code; from
    TRACE_ROOT/dowse_write/runs/{general,mint}/eval/blocks.csv dowse_write_all;
    variants all and sload (slots whose first access is a read);
  - also the count coverage (hits / actual reads) that the paper gives for history and Gigahorse;
  - differences with bootstrap intervals for plans - dowse and for dowse with - without its write patch.
With POP=pop the output reproduces results/b3/paper216_all_290.csv and results/write216/table.csv (checked by hand).
usage (repository root): POP=eval python3 paper/scripts/offline/pred_eval_weights.py > paper/data/offline/pred_weights_eval.txt
       (writes paper/data/offline/pred_weights_<POP>.csv)"""
import csv, os
import numpy as np

X = os.environ.get("TRACE_ROOT", "traces") + "/prediction-vs-official/results"
W = os.environ.get("TRACE_ROOT", "traces") + "/dowse_write/runs"
SRC = {'b3': (f'{X}/b3/eval_general', f'{X}/b3/eval_mint'), 'hist': (f'{X}/b3/hist_eval_general', f'{X}/b3/hist_eval_mint'),
       'write': (f'{W}/general/eval', f'{W}/mint/eval')}
METHODS = [('P2', 'b3'), ('P2t', 'b3'), ('predictal', 'b3'), ('dowse_main_all', 'b3'), ('gh_all', 'b3'), ('P1d', 'b3'),
           ('hist_code', 'hist'), ('dowse_write_all', 'write')]
POP = os.environ.get('POP', 'eval')
N = {'pop': {'general': 3419, 'mint': 1580}, 'eval': {'general': 8950, 'mint': 1050}}[POP]
COLS = ('w_r_hit', 'w_r_all', 'hits', 'predicted', 'actual')
KEEP = {c: {int(x) for x in open(f'{X}/b3/w290_{c}_blocks.txt').read().split()} for c in ('general', 'mint')}


def load(d, keep):
    out = {}
    for r in csv.DictReader(open(os.path.join(d, 'blocks.csv'))):
        b = int(r['block'])
        if b in keep:
            out.setdefault((r['method'], r['variant']), {})[b] = [float(r[c] or 0) for c in COLS]
    return out


S = {k: {src: load(dirs[i], KEEP[k]) for src, dirs in SRC.items()} for i, k in enumerate(('general', 'mint'))}
B = {k: sorted(S[k]['b3'][('P2', 'all')]) for k in ('general', 'mint')}
n = {k: len(B[k]) for k in B}
A = {}
for k in ('general', 'mint'):
    for m, src in METHODS:
        for v in ('all', 'sload'):
            d = S[k][src].get((m, v))
            if d is None:
                continue
            assert sorted(d) == B[k], (k, m, v, 'block lists differ')
            A[(k, m, v)] = np.array([d[b] for b in B[k]])
rng = np.random.default_rng(216)
DR = {k: rng.integers(0, n[k], size=(2000, n[k])) for k in ('general', 'mint')}


def metric(m, v, col, draw=None):
    out = {}; tot = 0
    for k in ('general', 'mint'):
        a = A[(k, m, v)] if draw is None else A[(k, m, v)][DR[k][draw]]
        s = a.sum(axis=0)
        out[k] = s[0] / s[1] if col == 'wcov' else (s[2] / s[3] if col == 'acc' else s[2] / s[4])
        tot = tot + s * (N[k] / n[k])
    out['all'] = tot[0] / tot[1] if col == 'wcov' else (tot[2] / tot[3] if col == 'acc' else tot[2] / tot[4])
    return out


def est(m, v, col):
    pt = metric(m, v, col)
    bs = [metric(m, v, col, d) for d in range(2000)]
    return {k: (pt[k], *np.percentile([b[k] for b in bs], [2.5, 97.5])) for k in pt}


print(f'POP={POP}: all blocks = general x {N["general"]}/{n["general"]} + batch-mint x {N["mint"]}/{n["mint"]} '
      f'(batch-mint share of the weighted blocks {N["mint"] / (N["general"] + N["mint"]):.4f})')
rows = []
for m, src in METHODS:
    for v in ('all', 'sload'):
        if (('general', m, v)) not in A:
            continue
        for col in ('wcov', 'acc', 'ccov'):
            r = est(m, v, col)
            print(f'{m:16s} {v:6s} {col:5s} ' + '  '.join(f'{k} {100 * r[k][0]:5.1f} [{100 * r[k][1]:5.1f}, {100 * r[k][2]:5.1f}]' for k in ('all', 'general', 'mint')))
            rows.append([m, v, col] + [f'{x:.6f}' for k in ('all', 'general', 'mint') for x in r[k]])
for a, b in (('P2', 'dowse_write_all'), ('dowse_write_all', 'dowse_main_all')):   # second pair: the write patch (supplement)
    for v in ('all', 'sload'):
        for col in ('wcov', 'acc'):
            if v == 'sload' and col == 'acc':
                continue
            pa, pb = metric(a, v, col)['all'], metric(b, v, col)['all']
            d = [metric(a, v, col, i)['all'] - metric(b, v, col, i)['all'] for i in range(2000)]
            lo, hi = np.percentile(d, [2.5, 97.5])
            print(f'{a} - {b} {v} {col}: {100 * (pa - pb):+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}]')
            rows.append([f'{a}-{b}', v, col, f'{pa - pb:.6f}', f'{lo:.6f}', f'{hi:.6f}'])
with open(f'paper/data/offline/pred_weights_{POP}.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['method', 'variant', 'metric', 'all', 'all_lo', 'all_hi', 'general', 'general_lo', 'general_hi', 'mint', 'mint_lo', 'mint_hi'])
    w.writerows(rows)
