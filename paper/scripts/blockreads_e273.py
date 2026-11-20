#!python3
"""Time ratio against per-block slot reads over the 10,000 blocks of the main comparison (figure "blockreads").
Inputs: results/blockreads/results/br273_blocks.csv and br273.txt (written by results/blockreads/scripts/br273.py).
Outputs (paper/data): f273_blockreads_blocks.csv, f273_blockreads_windows.csv; text to stdout.
Run from the repository root:  python3 paper/scripts/blockreads_e273.py > paper/data/f273_blockreads.txt"""
import csv, re, statistics as st
SRC = 'results/blockreads/results/'
OUT = 'paper/data/f273_blockreads'
rows = list(csv.DictReader(open(SRC + 'br273_blocks.csv')))
for r in rows:
    r['pnup'] = '%.6f' % (float(r['np_pn']) / float(r['np_up']))
with open(OUT + '_blocks.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
pat = re.compile(r'window\s+(\d+): reads (\d+)-(\d+) \(median ([\d.]+)\), (\d+) batch-mint; PN/UP ([\d.]+) \(([\d.]+)-([\d.]+)\), '
                 r'PN/UR ([\d.]+) \(([\d.]+)-([\d.]+)\), UR/UP ([\d.]+) \(([\d.]+)-([\d.]+)\)')
wins = [m.groups() for m in map(pat.search, open(SRC + 'br273.txt')) if m]
hdr = ['window', 'n', 'x_median', 'x_lo', 'x_hi', 'mint', 'PN/UP', 'PN/UP_lo', 'PN/UP_hi', 'PN/UR', 'PN/UR_lo', 'PN/UR_hi',
       'UR/UP', 'UR/UP_lo', 'UR/UP_hi']
with open(OUT + '_windows.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(hdr)
    for g in wins:
        w.writerow([g[0], 1000, g[3], g[1], g[2], g[4]] + list(g[5:]))
print('# paper/scripts/blockreads_e273.py: %d blocks (regular %d, batch-mint %d), %d windows of 1,000 blocks moved by 200'
      % (len(rows), sum(r['cls'] == 'nomint' for r in rows), sum(r['cls'] == 'mint' for r in rows), len(wins)))
# check: recompute every window from the blocks file (stable sort by slot reads over ascending block numbers)
srt = sorted(sorted(rows, key=lambda r: int(r['block'])), key=lambda r: int(r['slot_reads']))
bad = 0
for k, g in enumerate(wins):
    blk = srt[k * 200:k * 200 + 1000]
    s = lambda c: sum(float(r[c]) for r in blk)
    med = st.median(int(r['slot_reads']) for r in blk)
    got = (med, sum(r['cls'] == 'mint' for r in blk), s('np_pn') / s('np_up'), s('np_pn') / s('np_ur'), s('np_ur') / s('np_up'))
    exp = (float(g[3]), int(g[4]), float(g[5]), float(g[8]), float(g[11]))
    if len(blk) != 1000 or abs(got[0] - exp[0]) > 0.01 or got[1] != exp[1] or any(abs(a - b) > 0.00051 for a, b in zip(got[2:], exp[2:])):
        bad += 1; print('MISMATCH window', k + 1, got, exp)
print('windows recomputed from the blocks file: %d of %d agree (median reads, batch-mint count, three ratios within 0.0005)' % (len(wins) - bad, len(wins)))
pn = [float(r['pnup']) for r in rows]
print('per-block PN/UP below 0.3: %d; above 2.0: %d; blocks with fewer than 250 slot reads: %d; with more than 6,500: %d'
      % (sum(v < 0.3 for v in pn), sum(v > 2.0 for v in pn), sum(int(r['slot_reads']) < 250 for r in rows), sum(int(r['slot_reads']) > 6500 for r in rows)))
print('slot reads: min %d, median %.1f, max %d' % (min(int(r['slot_reads']) for r in rows), st.median(int(r['slot_reads']) for r in rows), max(int(r['slot_reads']) for r in rows)))
print('first window: median reads %s, PN/UP %s (%s-%s); last window: median reads %s, PN/UP %s (%s-%s), PN/UR %s, UR/UP %s; UR/UP over windows %.3f-%.3f'
      % (wins[0][3], wins[0][5], wins[0][6], wins[0][7], wins[-1][3], wins[-1][5], wins[-1][6], wins[-1][7], wins[-1][8], wins[-1][11],
         min(float(g[11]) for g in wins), max(float(g[11]) for g in wins)))
