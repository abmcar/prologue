#!python3
"""The "in repeated inner calls" row of Table 1 under two compositions (11-07; weight the
observation's all-block numbers by the composition of the evaluated blocks).
Reads the per-class sums that scripts/binding_dataflow_repeated.py wrote (data/binding_dataflow_repeated_{general,mint}.csv;
they do not depend on the weights) and combines the two classes as that script does (look234w.py): each sampled class is
scaled to its number of blocks, the 931 regular and 193 batch-mint sampled blocks to
  POP=pop : 3,419 and 1,580, the blocks of 26,263,606-26,268,604 (reproduces data/binding_dataflow_repeated.txt), or
  POP=eval: 8,950 and 1,050, the composition of the main comparison's 10,000 blocks (10.5% batch-mint).
usage (repository root): POP=eval python3 scripts/binding_repeated_weights.py   -> data/binding_dataflow_repeated_<POP>.txt"""
import csv, os

POP = os.environ.get('POP', 'eval')
N = {'pop': {'general': 3419, 'mint': 1580}, 'eval': {'general': 8950, 'mint': 1050}}[POP]
nn = {'general': 931, 'mint': 193}
U = {c: {r['scope']: r for r in csv.DictReader(open(f'paper/data/offline/binding_dataflow_repeated_{c}.csv'))} for c in N}
lines = [f'POP={POP}; weights {N}, samples {nn}; per-class sums from data/binding_dataflow_repeated_{{general,mint}}.csv']
for scope in ('all', 'miss_n', 'miss_wr_ns'):
    w = {c: N[c] / nn[c] for c in N}
    amt = {c: float(U[c][scope]['amount']) for c in N}
    for key in ('class12_share', 'class12_in_late_frame_share'):
        v = {c: float(U[c][scope][key]) for c in N}
        v['all'] = sum(w[c] * amt[c] * v[c] for c in N) / sum(w[c] * amt[c] for c in N)
        lines.append(f'{scope:10s} {key.replace("class12", "labels_start"):40s} '
                     + '  '.join(f'{c} {100 * v[c]:6.2f}%' for c in ('general', 'mint', 'all')))
open(f'paper/data/offline/binding_dataflow_repeated_{POP}.txt', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
