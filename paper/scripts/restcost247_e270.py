#!python3
"""Step 2 of 2 of the per-transaction cost comparison: the execution thread's time per transaction under rows H3
(Prologue without plans), H4 (Prologue) and H5 (stock reth plus plans) against stock reth (H0) on the same transactions,
split into waits and computation and by whether the pre-execution result was reused.
Input: paper/data/f270_tx/tx_rec<k><p>.csv.gz. Output: text to stdout, paper/data/f270_restcost.csv.
usage (repository root): python3 paper/scripts/restcost247_e270.py > paper/data/f270_restcost.txt"""
import collections, csv, gzip, os, sys

TAG = 'e270'
X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # paper/
E270 = os.path.join(os.path.dirname(X), 'results/main/raw')
CONF = {'e270': ([(f'{E270}/e270rec-{k}', f'rec{k}') for k in (0, 4, 8)], 5, 'H0', ['H3', 'H4', 'H5'])}
TXD = os.path.join(X, 'data', 'f270_tx')
RUNS, NPASS, REF, ROWS = CONF[TAG]
if len(sys.argv) > 1:
    ROWS = sys.argv[1].split(',')
W = ('sw0', 'sw1', 'sw2', 'sw3', 'aw', 'cw')
CLS = ('reused', 'executed', 'late', 'small')
tx = {}         # (row, block) -> {i: (busy, waits, comp, late)}
blk = {}        # (row, block) -> dict of block values
for run, lab in RUNS:
    for p in range(NPASS):
        L = f'{lab}{p}'
        for r in csv.DictReader(gzip.open(f'{TXD}/tx_{L}.csv.gz', 'rt')):
            c = r['cfg']
            if c != REF and c not in ROWS:
                continue
            es, ee = int(r['es']), int(r['ee'])
            if es < 0 or ee < es:
                continue
            w = sum(float(r[k] or 0) for k in W)
            busy = ee - es
            late = r['st'] == '6' and int(r['ws']) >= 0 and es < int(r['we'])
            tx.setdefault((c, int(r['block'])), {})[int(r['i'])] = (busy, w, busy - w, late)
        for r in csv.DictReader(open(f'{run}/results/blocks_{L}.csv')):
            c = r['cfg'].split('+')[0]
            if r['role'] == 'measured' and int(float(r['pos'])) >= 2 and (c == REF or c in ROWS):
                blk[(c, int(r['block']))] = {k: float(r[k] or 0) for k in ('exec_ms', 'engine_runq_ms', 'engine_cpu_ms',
                                                                          'engine_minflt', 'engine_majflt', 'engine_ivcsw')}
print(f'# paper restcost247_e270.py: reference {REF}, rows {ROWS}; '
      f'counted blocks; per block means (ms unless noted)')
out = []
for c in ROWS:
    B = sorted(b for (cc, b) in blk if cc == c and (REF, b) in blk and (c, b) in tx and (REF, b) in tx)
    n = len(B)
    acc = {k: collections.defaultdict(float) for k in CLS}
    outside = outside0 = 0.0
    for b in B:
        t, t0 = tx[(c, b)], tx[(REF, b)]
        outside += blk[(c, b)]['exec_ms'] - sum(v[0] for v in t.values()) / 1000
        outside0 += blk[(REF, b)]['exec_ms'] - sum(v[0] for v in t0.values()) / 1000
        for i, (busy, w, comp, late) in t.items():
            if i not in t0:
                continue
            b0, w0, c0, _ = t0[i]
            k = 'late' if late else 'reused' if (c0 >= 40 and comp < 0.5 * c0) else 'executed' if c0 >= 40 else 'small'
            a = acc[k]
            a['n'] += 1
            a['busy'] += busy / 1000
            a['wait'] += w / 1000
            a['comp'] += comp / 1000
            a['busy0'] += b0 / 1000
            a['wait0'] += w0 / 1000
            a['comp0'] += c0 / 1000
    mean = lambda key, rr: sum(blk[(rr, b)][key] for b in B) / n  # noqa: E731
    dexec = mean('exec_ms', REF) - mean('exec_ms', c)
    print(f'\n== {c} against {REF} on the same {n} blocks: execution {mean("exec_ms", REF):.3f} -> {mean("exec_ms", c):.3f} ms '
          f'(shorter by {dexec:.3f})')
    tot = collections.defaultdict(float)
    for k in CLS:
        a = acc[k]
        if not a['n']:
            continue
        d_wait, d_comp = (a['wait0'] - a['wait']) / n, (a['comp0'] - a['comp']) / n
        tot['wait'] += d_wait
        tot['comp'] += d_comp
        print(f'  {k:>8}: {a["n"] / n:6.1f} transactions per block; execution thread {a["busy"] / n:7.3f} ms (waits {a["wait"] / n:.3f}, '
              f'computation {a["comp"] / n:.3f}); under {REF} on the same transactions {a["busy0"] / n:7.3f} ms (waits {a["wait0"] / n:.3f}, '
              f'computation {a["comp0"] / n:.3f}); shorter by {d_wait + d_comp:+.3f} (waits {d_wait:+.3f}, computation {d_comp:+.3f}); '
              f'per transaction {a["busy"] / a["n"] * 1000:.1f} us against {a["busy0"] / a["n"] * 1000:.1f} us; computation ratio '
              f'{a["comp"] / a["comp0"]:.3f}')
        out.append(dict(row=c, cls=k, n=round(a['n'] / n, 2), d_wait=round(d_wait, 4), d_comp=round(d_comp, 4),
                        us_row=round(a['busy'] / a['n'] * 1000, 1), us_ref=round(a['busy0'] / a['n'] * 1000, 1)))
    d_out = (outside0 - outside) / n
    print(f'  outside transactions: {outside / n:.3f} ms against {outside0 / n:.3f} (shorter by {d_out:+.3f})')
    print(f'  sum: waits {tot["wait"]:+.3f} + computation {tot["comp"]:+.3f} + outside {d_out:+.3f} = '
          f'{tot["wait"] + tot["comp"] + d_out:+.3f} ms; execution shorter by {dexec:+.3f}')
    print(f'  execution thread per block: run-queue {mean("engine_runq_ms", REF):.3f} -> {mean("engine_runq_ms", c):.3f} ms, cpu '
          f'{mean("engine_cpu_ms", REF):.3f} -> {mean("engine_cpu_ms", c):.3f} ms, involuntary switches {mean("engine_ivcsw", REF):.1f} -> '
          f'{mean("engine_ivcsw", c):.1f}, minor faults {mean("engine_minflt", REF):.1f} -> {mean("engine_minflt", c):.1f}, major '
          f'{mean("engine_majflt", REF):.1f} -> {mean("engine_majflt", c):.1f}')
    out.append(dict(row=c, cls='outside', n='', d_wait=0.0, d_comp=round(d_out, 4), us_row='', us_ref=''))
    out.append(dict(row=c, cls='exec', n='', d_wait='', d_comp=round(dexec, 4), us_row='', us_ref=''))
with open(os.path.join(X, 'data', 'f270_restcost.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
