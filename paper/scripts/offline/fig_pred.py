#!python3
"""Second-batch figure (11-04): Table 5 as bars by block class. Reads the table's own source,
results/b3/paper216_all_290.csv (offline prediction audit, 2.9.0 stock reth waits; samples 931 regular and 193
batch-mint blocks scaled to 3,419 and 1,580; 95% intervals from 2,000 stratified resamples
master/verify/verify216_290.txt). Rows as Table 5: dowse (every call start), predict-al (at arrival), Prologue (every
call start, P2), Prologue at the node's threshold (P2t).
Output (paper/data/offline): m3_pred_class.csv  metric (wcov = coverage of the slot wait, acc = accuracy), cls (all, reg, mint),
y (bar position), then for each predictor its value, lower and upper bound in % (dowse, predictal, sys, systhr).
Also data/m3_pred_scatter.csv (style sample 2, coverage against accuracy): pred, cls, x, xlo, xhi (coverage %),
y, ylo, yhi (accuracy %), one row per predictor and block class.
Run from the repository root:  python3 paper/scripts/offline/fig_pred.py"""
import csv, os

# 11-07: every value now comes from
# paper/data/offline/pred_weights_<POP>.csv (scripts/pred_eval_weights.py: the same inputs, per-class sums and bootstrap as
# paper216_all_290.csv and write216/table.csv). POP=eval (default) weights the two classes by the composition of the
# evaluated blocks (8,950 regular, 1,050 batch-mint); POP=pop reproduces the earlier figure data byte for byte (checked
# 11-07 against the files written from paper216_all_290.csv and write216/table.csv). dowse = dowse_write_all (with the keys of
# writes, .
POP = os.environ.get('POP', 'eval')
ROWS = {'dowse_write_all': 'dowse', 'predictal': 'predictal', 'P2': 'sys', 'P2t': 'systhr'}
R = {(ROWS[r['method']], r['metric']): r for r in csv.DictReader(open(f'paper/data/offline/pred_weights_{POP}.csv'))
     if r['method'] in ROWS and r['variant'] == 'all'}
assert len(R) == 12


def val(p, src, m):
    r = R[(p, m)]
    return 100 * float(r[src]), 100 * float(r[f'{src}_lo']), 100 * float(r[f'{src}_hi'])
CLS = (('all', 'all', 3), ('reg', 'general', 2), ('mint', 'mint', 1))
with open('paper/data/offline/m3_pred_class.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['metric', 'cls', 'y'] + [f'{p}{s}' for p in ROWS.values() for s in ('', '_lo', '_hi')])
    for m in ('wcov', 'acc'):
        for c, src, y in CLS:
            row = [m, c, y]
            for p in ROWS.values():
                v, lo, hi = val(p, src, m)
                row += [f'{v:.1f}', f'{lo:.1f}', f'{hi:.1f}']
            w.writerow(row)
            print(m, c, ' '.join(f'{p} {r}' for p, r in zip(ROWS.values(), [row[3 + 3 * i] for i in range(4)])))
with open('paper/data/m3_pred_scatter.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['pred', 'cls', 'x', 'xlo', 'xhi', 'y', 'ylo', 'yhi'])
    for p in ROWS.values():
        for c, src, _ in CLS:
            row = [p, c]
            for m in ('wcov', 'acc'):
                v, lo, hi = val(p, src, m)
                row += [f'{v:.1f}', f'{lo:.1f}', f'{hi:.1f}']
            w.writerow(row)
