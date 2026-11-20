#!/usr/bin/env python3
"""Data of the storage figure (segment 6, 1,000 blocks): local NVMe SSD and ESSD PL1 on one server, ESSD PL0 on another.
Inputs: results/main/results/cmp270_sd.txt and cmp270_sm.txt. Output: paper/data/f270_storage.csv and the time saved
per block.
Run from the repository root:  python3 paper/scripts/fig_storage270.py"""
import csv, re
R = 'results/main/results'
sd, sm = open(f'{R}/cmp270_sd.txt').read(), open(f'{R}/cmp270_sm.txt').read()
def np_(t, c): return re.search(rf'^  {c}: newPayload ([\d.]+) ms', t, re.M).group(1)
def rat(t, a, b): return re.search(rf'^\[ratio\] {a}/{b} \(all\): newPayload ([\d.]+) \(([\d.]+)-([\d.]+)\)', t, re.M).groups()
def rd(t, c): return re.search(rf'^\[dev\] {c}: \d+ reads per block, (\d+) per s', t, re.M).group(1)
def fio(t, name):
    m = re.search(rf'^\[fio\] results/{name}: qd1: iops \d+, mean latency ([\d.]+) us.*\| qd32: iops (\d+)', t, re.M)
    return m.group(2), m.group(1)
rows = []
for tier, y, t, s, f in (('nvme', 3, sd, '', 'fio270_prologue-sd_local.txt'), ('pl1', 2, sd, 'c', 'fio270_prologue-sd_pl1.txt'),
                         ('pl0', 1, sm, 'z', 'fio270_prologue-sm_pl0.txt')):
    r, lo, hi = rat(t, 'PN' + s, 'UP' + s); iops32, lat1 = fio(t, f)
    rows.append([tier, y, np_(t, 'UN' + s), np_(t, 'UP' + s), np_(t, 'PN' + s), r, lo, hi, rd(t, 'UN' + s), rd(t, 'UP' + s), rd(t, 'PN' + s), iops32, lat1])
with open('paper/data/f270_storage.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['tier', 'y', 'np_un', 'np_up', 'np_pn', 'ratio', 'ratio_lo', 'ratio_hi', 'rd_un', 'rd_up', 'rd_pn', 'iops32', 'lat1_us'])
    w.writerows(rows)
for r in rows:
    print(r, 'saved per block', f'{float(r[3]) - float(r[4]):.2f} ms')
