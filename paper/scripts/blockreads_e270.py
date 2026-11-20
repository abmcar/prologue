#!python3
"""Per-block slot reads against the time ratio, on the 2,700 blocks of the recording processes (segments 0, 4, 8).
The slot reads of a block come from the row without prewarming of the recording process (H0n); times from the main
comparison. Outputs: paper/data/f270_blockreads_blocks.csv (per block: class, slot reads, slot misses, Mgas, times) and
f270_blockreads_windows.csv; the text output goes to stdout.
Run from the repository root:  python3 paper/scripts/blockreads_e270.py > paper/data/f270_blockreads.txt"""
import csv, os

import numpy as np

E257 = 'results/main/raw'
E252 = os.environ.get('EARLIER_RAW', 'results/earlier/raw')   # optional: an earlier measurement of the same blocks, for a cross-check
MAIN_RAW, MAIN_TAG = os.environ.get('MAIN_RAW', E257), os.environ.get('MAIN_TAG', 'e270')
ABL_RAW, ABL_TAG = os.environ.get('ABL_RAW', E257), os.environ.get('ABL_TAG', 'e270')
OUT = os.environ.get('OUT_PREFIX', 'paper/data/f270_blockreads')
# windows: the blocks sorted by their slot reads, WINSIZE blocks per window, moved by WINSTEP blocks (overlapping; defaults one
# tenth and one fiftieth of the blocks), so the trend is smooth and every window is a ratio of sums over enough blocks
WINSIZE, WINSTEP = int(os.environ.get('WINSIZE', '270')), int(os.environ.get('WINSTEP', '54'))
CLASS = 'measurement/block_classes.csv'
KS, SRC = (0, 4, 8), ('pw', 'old', 'eap', 'cs0', 'cs1')
NPASS_REC, NPASS_ABL = 5, 9
mint = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(CLASS))}


def measured(path):
    for r in csv.DictReader(open(path)):
        if r['role'] == 'measured' and int(float(r['pos'])) >= 2:
            yield r


def slot_counts(r):
    return (sum(float(r[f'slot_hit_{x}'] or 0) for x in SRC) + float(r['slot_miss'] or 0), float(r['slot_miss'] or 0),
            float(r['gas_used'] or 0) / 1e6)


work, ab = {}, {'H0': {}, 'H4': {}}
for k in KS:
    for p in range(NPASS_REC):   # recorder process: the read counts of the row without prewarming
        for r in measured(f'{ABL_RAW}/{ABL_TAG}rec-{k}/results/blocks_rec{k}{p}.csv'):
            if r['cfg'] == 'H0n':
                work[int(r['block'])] = slot_counts(r)
    for p in range(NPASS_ABL):   # timing ablation: newPayload of stock reth (G0) and Prologue (G4)
        for r in measured(f'{ABL_RAW}/{ABL_TAG}abl-{k}/results/blocks_abl{k}{p}.csv'):
            if r['cfg'] in ab:
                ab[r['cfg']][int(r['block'])] = float(r['new_payload_ms'])
main = {}
for proc in ('up', 'ur', 'pn'):
    main[proc] = {}
    for k in KS:
        for r in csv.DictReader(open(f'{MAIN_RAW}/{MAIN_TAG}{proc}-{k}/results/blocks_{proc}{k}0.csv')):
            if r['role'] == 'measured':
                main[proc][int(r['block'])] = float(r['new_payload_ms'])
B = sorted(b for b in work if b in ab['H0'] and b in ab['H4'] and all(b in main[p] for p in main))
with open(f'{OUT}_blocks.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['block', 'cls', 'slot_reads', 'slot_miss', 'mgas', 'np_up', 'np_ur', 'np_pn', 'np_g0', 'np_g4', 'pnup'])
    for b in B:
        w.writerow([b, mint.get(b, '?'), int(work[b][0]), int(work[b][1]), round(work[b][2], 3), main['up'][b], main['ur'][b],
                    main['pn'][b], ab['H0'][b], ab['H4'][b], f"{main['pn'][b] / main['up'][b]:.6f}"])
s = np.array([work[b][0] for b in B])
order = np.argsort(s, kind='mergesort')
wins = [order[i:i + WINSIZE] for i in range(0, len(order) - WINSIZE + 1, WINSTEP)]
rng = np.random.default_rng(247)
PAIRS = (('PN/UP', main['pn'], main['up']), ('PN/UR', main['pn'], main['ur']), ('UR/UP', main['ur'], main['up']),
         ('G4/G0', ab['H4'], ab['H0']))
print(f'# paper/scripts/blockreads_e270.py (per-block reads): {len(B)} blocks '
      f'(segments {", ".join(map(str, KS))}, position >= 2; regular {sum(1 for b in B if mint.get(b) == "nomint")}, '
      f'batch-mint {sum(1 for b in B if mint.get(b) == "mint")}); {len(wins)} windows of {WINSIZE} blocks by G0n slot reads '
      f'(recorder process), moved by {WINSTEP}; main comparison {MAIN_TAG} up/ur/pn; ablation G4/G0 from the timing process')
rows = []
for wi, idx in enumerate(wins):
    rec = dict(window=wi + 1, n=len(idx), x_median=float(np.median(s[idx])), x_lo=float(s[idx].min()), x_hi=float(s[idx].max()),
               mint=sum(1 for i in idx if mint.get(B[i]) == 'mint'))
    for n, num, den in PAIRS:
        a = np.array([num[B[i]] for i in idx])
        d = np.array([den[B[i]] for i in idx])
        boot = [a[j].sum() / d[j].sum() for j in (rng.integers(0, len(idx), len(idx)) for _ in range(2000))]
        rec[n], rec[n + '_lo'], rec[n + '_hi'] = a.sum() / d.sum(), np.percentile(boot, 2.5), np.percentile(boot, 97.5)
    rows.append(rec)
with open(f'{OUT}_windows.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows([{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows])
for r in rows:
    print(f"  window {r['window']:>2}: reads {r['x_lo']:.0f}-{r['x_hi']:.0f} (median {r['x_median']:.1f}), {r['n']} blocks, {r['mint']} batch-mint; "
          + ', '.join(f"{n} {r[n]:.3f} ({r[n + '_lo']:.3f}-{r[n + '_hi']:.3f})" for n, _, _ in PAIRS))


def rank(v):
    o = np.argsort(v, kind='mergesort')
    rr = np.empty(len(v))
    rr[o] = np.arange(len(v))
    return rr


print('\n== per-block ratios: spread (5th, 25th, 50th, 75th, 95th percentile) and Spearman against the slot reads')
for n, num, den in PAIRS:
    y = np.array([num[b] / den[b] for b in B])
    print(f'  {n}: ' + ', '.join(f'{v:.3f}' for v in np.percentile(y, [5, 25, 50, 75, 95]))
          + f'; Spearman {np.corrcoef(rank(s), rank(y))[0, 1]:+.3f}; outside 0.3-2.0: {int(((y < 0.3) | (y > 2.0)).sum())} blocks'
          + f' ({int((y < 0.3).sum())} below, {int((y > 2.0).sum())} above)')

# the numbers the paper's paragraph and the figure's comments quote, read off the windows (rounded as in the windows file)
R = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]
rng_of = lambda sel, c: (min(r[c] for r in sel), max(r[c] for r in sel))  # noqa: E731
print('\n== windows by median reads (values as in the windows file)')
for lim in (1300, 1500):
    sel = [r for r in R if r['x_median'] < lim]
    if sel:
        lo, hi = rng_of(sel, 'PN/UP')
        print(f"  median reads < {lim:,}: windows {sel[0]['window']}-{sel[-1]['window']} (medians {sel[0]['x_median']:.1f}-{sel[-1]['x_median']:.1f}, "
              f"largest block {max(r['x_hi'] for r in sel):.0f} reads): PN/UP {lo:.4f}-{hi:.4f}, PN/UR {rng_of(sel, 'PN/UR')[0]:.4f}-"
              f"{rng_of(sel, 'PN/UR')[1]:.4f}, UR/UP {rng_of(sel, 'UR/UP')[0]:.4f}-{rng_of(sel, 'UR/UP')[1]:.4f}")
first_below = next((r for r in R if r['PN/UP_hi'] < 1), None)
if first_below:
    print(f"  first window whose PN/UP band lies below 1: window {first_below['window']} (median {first_below['x_median']:.1f}), "
          f"PN/UP {first_below['PN/UP']:.4f} ({first_below['PN/UP_lo']:.4f}-{first_below['PN/UP_hi']:.4f})")
last = R[-1]
print(f"  window with the most reads: window {last['window']}, median {last['x_median']:.1f} ({last['x_lo']:.0f}-{last['x_hi']:.0f}), "
      f"{last['mint']} batch-mint of {last['n']}: PN/UP {last['PN/UP']:.4f} ({last['PN/UP_lo']:.4f}-{last['PN/UP_hi']:.4f}), "
      f"PN/UR {last['PN/UR']:.4f} ({last['PN/UR_lo']:.4f}-{last['PN/UR_hi']:.4f}), UR/UP {last['UR/UP']:.4f}, G4/G0 {last['G4/G0']:.4f}")
print('  over all windows: ' + ', '.join(f'{c} {rng_of(R, c)[0]:.4f}-{rng_of(R, c)[1]:.4f}' for c in ('PN/UP', 'PN/UR', 'UR/UP', 'G4/G0')))
top = R[-6:]
print(f"  windows {top[0]['window']}-{top[-1]['window']} (medians {top[0]['x_median']:.1f}-{top[-1]['x_median']:.1f}): "
      f"PN/UR {top[0]['PN/UR']:.4f} ... {top[-1]['PN/UR']:.4f} (range {rng_of(top, 'PN/UR')[0]:.4f}-{rng_of(top, 'PN/UR')[1]:.4f}), "
      f"PN/UP range {rng_of(top, 'PN/UP')[0]:.4f}-{rng_of(top, 'PN/UP')[1]:.4f}, batch-mint {min(r['mint'] for r in top)}-"
      f"{max(r['mint'] for r in top)} of {WINSIZE} (regular {1 - max(r['mint'] for r in top) / WINSIZE:.1%}-{1 - min(r['mint'] for r in top) / WINSIZE:.1%})")

# layout checks for fig/eval_blockreads.tex: panel (a) draws pnup on a log axis clipped to 0.3-2.0 and x below 250 at 250;
# its legend stood in the lower left corner until 11-07 and stands in the top right corner since; panel (b)'s legend stands in
# the lower left corner. Points listed as (slot reads, ratio as drawn, class).
print('\n== figure layout checks (fig/eval_blockreads.tex)')
x = np.maximum(250, s)
y = np.clip(np.array([main['pn'][b] / main['up'][b] for b in B]), 0.3, 2.0)
pts = lambda cond: sorted((int(s[i]), round(float(y[i]), 3), mint.get(B[i])) for i in range(len(B)) if cond(x[i], y[i]))  # noqa: E731
print(f'  (a) blocks with fewer than 250 slot reads (drawn at 250): {int((s < 250).sum())}; slot reads {s.min():.0f}-{s.max():.0f}')
print(f'  (a) lower left, where the legend stood until 11-07 (320-1,250 reads, ratio <= 0.44): {pts(lambda a, b: 320 <= a <= 1250 and b <= 0.44)}')
print(f'      around it (250-1,400 reads, ratio <= 0.5): {pts(lambda a, b: a <= 1400 and b <= 0.5)}')
print(f'  (a) top right, where the legend stands (2,000 reads or more, ratio >= 1.3): {pts(lambda a, b: a >= 2000 and b >= 1.3)}')
for xlim in (2100,):
    sel = [r for r in R if r['x_median'] < xlim]
    low = min(min(r[c + '_lo'], r[c]) for r in sel for c in ('PN/UP', 'PN/UR', 'UR/UP'))
    print(f'  (b) lowest line or band left of {xlim:,} reads: {low:.4f}')
print(f"  (b) lowest band over all windows: {min(r[c + '_lo'] for r in R for c in ('PN/UP', 'PN/UR', 'UR/UP')):.4f}; "
      f"highest: {max(r[c + '_hi'] for r in R for c in ('PN/UP', 'PN/UR', 'UR/UP')):.4f}; "
      f"last window PN/UP {last['PN/UP']:.4f}, PN/UR {last['PN/UR']:.4f}, UR/UP {last['UR/UP']:.4f}")

# check: the slot reads are a property of the block, so G0n here should count what Q0n counted in an earlier experiment
old = {}
for k in KS:
    for p in range(11):
        fn = f'{E252}/e252abl-{k}/results/blocks_abl{k}{p}.csv'
        if not os.path.exists(fn):
            continue
        for r in measured(fn):
            if r['cfg'] == 'Q0n':
                old[int(r['block'])] = slot_counts(r)
if old:
    both = [b for b in B if b in old]
    same = [sum(1 for b in both if work[b][j] == old[b][j]) for j in range(3)]
    dm = np.array([work[b][1] - old[b][1] for b in both])
    print(f'\n== check against an earlier experiment (ablation Q0n, the same blocks): {len(both)} of {len(B)} blocks in both; identical per block: '
          f'slot reads {same[0]}, Mgas {same[2]}, slot misses {same[1]} (misses depend on the cache: G0n/Q0n total '
          f'{sum(work[b][1] for b in both) / sum(old[b][1] for b in both):.4f}, per block median {np.median(dm):+.0f}, '
          f'5th-95th percentile {np.percentile(dm, 5):+.0f} to {np.percentile(dm, 95):+.0f})')
