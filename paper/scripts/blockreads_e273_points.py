#!python3
"""The points of panel (a) of the per-block slot-read figure, from data/f273_blockreads_blocks.csv.
  f273_blockreads_quarter.csv  a random quarter of the blocks, drawn per class with a fixed seed (random.Random(273))
Run from the repository root: python3 paper/scripts/blockreads_e273_points.py
"""
import csv, random
D = 'paper/data/f273_blockreads'
rows = list(csv.DictReader(open(D + '_blocks.csv')))
rng = random.Random(273); pick = []
for c in ('nomint', 'mint'):
    cl = sorted((r for r in rows if r['cls'] == c), key=lambda r: int(r['block']))
    pick += rng.sample(cl, round(len(cl) / 4))
pick.sort(key=lambda r: int(r['block']))
with open(D + '_quarter.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(pick)
v = [float(r['pnup']) for r in pick]
print('quarter: %d blocks (regular %d, batch-mint %d); ratio below 0.2: %d, above 2.0: %d; fewer than 250 slot reads: %d'
      % (len(pick), sum(r['cls'] == 'nomint' for r in pick), sum(r['cls'] == 'mint' for r in pick),
         sum(a < 0.2 for a in v), sum(a > 2 for a in v), sum(int(r['slot_reads']) < 250 for r in pick)))
