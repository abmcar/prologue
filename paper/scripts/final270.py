#!python3
"""Numbers and figure data of the main comparison, the ablation and the recording processes.
Inputs: results/main/raw/<run>/results/blocks_*.csv (main comparison: ten segments, columns up, ur, un, pn; ablation
and recording processes: segments 0, 4, 8) and measurement/block_classes.csv. Ratios are ratios of sums over the same
blocks; storage wait = d_slot_miss_ms + acct_miss_ms + code_miss_ms.
Outputs (paper/data, prefix f270_): main.txt, ccdf_{np,exec}.csv, dist_pct.csv, tailratio{,_marks}.csv, abl.txt,
abl_split.csv, motiv.csv, wait_by_class.txt, funnel.txt.
Run from the repository root:  python3 paper/scripts/final270.py"""
import csv, glob, math
from collections import defaultdict

E = 'results/main/raw'
OUT = 'paper/data/f270_'
CLS = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open('measurement/block_classes.csv'))}
def f(r, k):
    v = r.get(k) or ''
    return 0.0 if v in ('', 'nan') else float(v)
out = open(OUT + 'main.txt', 'w')
def say(s, fh=None):
    print(s); (fh or out).write(s + '\n')

# ---------------- main comparison ----------------
COLS = {'up': 'UP', 'ur': 'UR', 'un': 'UN', 'pn': 'PN'}
V = defaultdict(dict)
for k in range(10):
    for lab, c in COLS.items():
        for fn in glob.glob(f'{E}/e270{lab}-{k}/results/blocks_*.csv'):
            for r in csv.DictReader(open(fn)):
                if r['role'] == 'measured':
                    V[(k, int(r['block']))][c] = r
keys = sorted(x for x in V if len(V[x]) == 4)
sel = {'all': keys, 'reg': [x for x in keys if CLS.get(x[1]) == 'nomint'], 'mint': [x for x in keys if CLS.get(x[1]) == 'mint']}
n = len(keys)
say(f'main comparison: {n} blocks under all four processes (regular {len(sel["reg"])}, batch-mint {len(sel["mint"])}, share {len(sel["mint"]) / n:.4f})')
S = lambda ks, c, k: sum(f(V[x][c], k) for x in ks)   # noqa: E731
for g, ks in sel.items():
    m = len(ks); gas = S(ks, 'UP', 'gas_used')
    say(f'{g:4s}: ' + '; '.join(f'{c} newPayload {S(ks, c, "new_payload_ms") / m:.2f} execution {S(ks, c, "exec_ms") / m:.2f} ms/block '
                                f'({S(ks, c, "exec_ms") / gas * 1e6:.3f} ms/Mgas), outside {(S(ks, c, "new_payload_ms") - S(ks, c, "exec_ms")) / m:.2f}'
                                for c in ('UP', 'UR', 'UN', 'PN')))
def slowest(ks, a, b, frac=0.05):
    return sorted(ks, key=lambda x: -(f(V[x][a], 'new_payload_ms') + f(V[x][b], 'new_payload_ms')))[:round(len(ks) * frac)]
for a, b in (('PN', 'UP'), ('PN', 'UR'), ('PN', 'UN'), ('UR', 'UP'), ('UP', 'UN')):
    rs = []
    for g, ks in sel.items():
        rs.append(f'{g} newPayload {S(ks, a, "new_payload_ms") / S(ks, b, "new_payload_ms"):.4f} execution {S(ks, a, "exec_ms") / S(ks, b, "exec_ms"):.4f}')
    top = slowest(keys, a, b)
    t = (S(top, a, 'new_payload_ms') / len(top), S(top, b, 'new_payload_ms') / len(top))
    cpu = S(keys, a, 'proc_cpu_ms') / S(keys, b, 'proc_cpu_ms')
    say(f'{a}/{b}: ' + '; '.join(rs) + f'; slowest 5% ({len(top)} blocks, {sum(CLS.get(x[1]) == "mint" for x in top)} batch-mint) '
        f'{t[1]:.1f} -> {t[0]:.1f} ms, {t[0] / t[1]:.4f}; process cpu {cpu:.4f}')
    seg = [S([x for x in keys if x[0] == k], a, 'new_payload_ms') / S([x for x in keys if x[0] == k], b, 'new_payload_ms') for k in range(10)]
    say(f'  per segment newPayload {a}/{b}: ' + ' '.join(f'{v:.3f}' for v in seg) + f'; min {min(seg):.3f} max {max(seg):.3f}')
    six = [x for x in keys if x[0] in (1, 4, 5, 6, 7, 9)]
    t6 = slowest(six, a, b)
    say(f'  segments never used in development (1, 4, 5, 6, 7, 9): newPayload {S(six, a, "new_payload_ms") / S(six, b, "new_payload_ms"):.4f} '
        f'execution {S(six, a, "exec_ms") / S(six, b, "exec_ms"):.4f} slowest 5% {S(t6, a, "new_payload_ms") / S(t6, b, "new_payload_ms"):.4f}')
say('process cpu ms/block: ' + ', '.join(f'{c} {S(keys, c, "proc_cpu_ms") / n:.1f}' for c in ('UP', 'UR', 'UN', 'PN')))
for g, ks in sel.items():   # Table 2 cells with three decimals
    m = len(ks); gas = S(ks, 'UP', 'gas_used')
    say(f'table 2 {g:4s}: newPayload ms/block ' + ' '.join(f'{c} {S(ks, c, "new_payload_ms") / m:.3f}' for c in ('UN', 'UP', 'UR', 'PN'))
        + '; execution ms/Mgas ' + ' '.join(f'{c} {S(ks, c, "exec_ms") / gas * 1e6:.4f}' for c in ('UN', 'UP', 'UR', 'PN'))
        + '; execution-thread run-queue wait ms/block ' + ' '.join(f'{c} {S(ks, c, "engine_runq_ms") / m:.2f}' for c in ('UP', 'UR', 'UN', 'PN')))
four = [x for x in keys if x[0] in (0, 2, 3, 8)]
for a, b in (('PN', 'UP'), ('PN', 'UR')):
    t4 = slowest(four, a, b)
    say(f'segments used in development (0, 2, 3, 8) {a}/{b}: newPayload {S(four, a, "new_payload_ms") / S(four, b, "new_payload_ms"):.4f} '
        f'execution {S(four, a, "exec_ms") / S(four, b, "exec_ms"):.4f} slowest 5% {S(t4, a, "new_payload_ms") / S(t4, b, "new_payload_ms"):.4f}')
top = slowest(keys, 'PN', 'UP')
say(f'slowest 5% of the pair PN+UP: mean newPayload UP {S(top, "UP", "new_payload_ms") / len(top):.2f} PN {S(top, "PN", "new_payload_ms") / len(top):.2f}; '
    f'all blocks mean UP {S(keys, "UP", "new_payload_ms") / n:.2f} PN {S(keys, "PN", "new_payload_ms") / n:.2f}; gap UP '
    f'{S(top, "UP", "new_payload_ms") / len(top) / (S(keys, "UP", "new_payload_ms") / n):.3f} PN {S(top, "PN", "new_payload_ms") / len(top) / (S(keys, "PN", "new_payload_ms") / n):.3f}')
pct = []
for m_, col in (('np', 'new_payload_ms'), ('exec', 'exec_ms')):
    so = {c: sorted(f(V[x][c], col) for x in keys) for c in ('UP', 'UR', 'UN', 'PN')}
    for q, nm in ((0.5, 'p50'), (0.95, 'p95'), (0.99, 'p99')):
        j = int(q * n); u, r_, p, un = so['UP'][j], so['UR'][j], so['PN'][j], so['UN'][j]
        pct.append([m_, nm, f'{1 - q:g}', f'{u:.3f}', f'{r_:.3f}', f'{p:.3f}', f'{u / p:.3f}', f'{u / p:.2f}'])
        say(f'{m_:4s} {nm}: no prewarming {un:.1f} stock {u:.1f} reuse {r_:.1f} Prologue {p:.1f} ms; Prologue/stock {p / u:.3f}; Prologue/reuse {p / r_:.3f}; stock/Prologue {u / p:.2f}')
with open(OUT + 'dist_pct.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['m', 'q', 'frac', 'stock', 'reuse', 'sys', 'stock_over_sys', 'rlab']); w.writerows(pct)
for b in (26307110, 26314402):
    x = [y for y in keys if y[1] == b][0]
    say(f'block {b}: ' + ', '.join(f'{c} {f(V[x][c], "new_payload_ms"):.1f}' for c in ('UP', 'UR', 'UN', 'PN')) + ' ms newPayload')
for col, nm in (('new_payload_ms', 'newPayload'), ('exec_ms', 'execution')):
    lo = sum(f(V[x]['PN'], col) > f(V[x]['UP'], col) for x in keys); lo10 = sum(f(V[x]['PN'], col) > 1.1 * f(V[x]['UP'], col) for x in keys)
    say(f'{nm}: blocks longer under Prologue than under stock reth {lo} ({lo / n:.1%}), by more than 10% {lo10} ({lo10 / n:.1%}); '
        f'over 100 ms stock {sum(f(V[x]["UP"], col) > 100 for x in keys)} Prologue {sum(f(V[x]["PN"], col) > 100 for x in keys)}')
for c in ('UP', 'UR'):
    say(f'batch-mint blocks\' share of {c} execution time {S(sel["mint"], c, "exec_ms") / S(keys, c, "exec_ms"):.3f}, newPayload {S(sel["mint"], c, "new_payload_ms") / S(keys, c, "new_payload_ms"):.3f}')
ranks = sorted(set(range(1, 201)) | {max(1, round(math.exp(math.log(n) * i / 300))) for i in range(301)} | {n} | {round(n * q) for q in (0.5, 0.05, 0.01)})
for m_, col in (('np', 'new_payload_ms'), ('exec', 'exec_ms')):
    so = {c: sorted((f(V[x][c], col) for x in keys), reverse=True) for c in ('UP', 'UR', 'PN')}
    with open(OUT + f'ccdf_{m_}.csv', 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['frac', 'stock', 'reuse', 'sys'])
        for r in ranks:
            w.writerow([f'{r / n:.6g}', f'{so["UP"][r - 1]:.3f}', f'{so["UR"][r - 1]:.3f}', f'{so["PN"][r - 1]:.3f}'])
def tail_row(x):
    row = [f'{x:g}']
    for g in ('all', 'reg'):
        for col in ('new_payload_ms', 'exec_ms'):
            ks = sorted(sel[g], key=lambda y: -(f(V[y]['UP'], col) + f(V[y]['PN'], col)))[:max(1, round(len(sel[g]) * x / 100))]
            row.append(f'{S(ks, "PN", col) / S(ks, "UP", col):.4f}')
    return row
H = ['x', 'all_np', 'all_exec', 'reg_np', 'reg_exec']
with open(OUT + 'tailratio.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(H)
    for x in sorted({round(100 * 10 ** (-2 * i / 40), 4) for i in range(41)}, reverse=True):
        w.writerow(tail_row(x))
with open(OUT + 'tailratio_marks.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(H)
    for x in (100, 50, 20, 10, 5, 2, 1):
        w.writerow(tail_row(x))
out.close()

# ---------------- timing ablation (records off) ----------------
ROWS = ('H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'HX', 'HC', 'HXC')
A = defaultdict(dict)
for k in (0, 4, 8):
    for fn in glob.glob(f'{E}/e270abl-{k}/results/blocks_abl*.csv'):
        for r in csv.DictReader(open(fn)):
            if r['role'] == 'measured' and int(float(r['pos'])) >= 2 and r['cfg'] in ROWS:
                A[(k, int(r['block']))][r['cfg']] = r
akeys = sorted(x for x in A if all(c in A[x] for c in ROWS))
asel = {'all': akeys, 'reg': [x for x in akeys if CLS.get(x[1]) == 'nomint'], 'mint': [x for x in akeys if CLS.get(x[1]) == 'mint']}
SA = lambda ks, c, k: sum(f(A[x][c], k) for x in ks)   # noqa: E731
ao = open(OUT + 'abl.txt', 'w')
say(f'timing ablation: {len(akeys)} blocks under all {len(ROWS)} rows (regular {len(asel["reg"])}, batch-mint {len(asel["mint"])})', ao)
for a, b in (('H1', 'H0'), ('H2', 'H1'), ('H3', 'H2'), ('H2', 'H0'), ('H3', 'H0'), ('H4', 'H0'), ('H5', 'H0'), ('H4', 'H3'),
             ('HX', 'H4'), ('HC', 'H4'), ('HXC', 'H4'), ('HXC', 'H3')):
    say(f'{a}/{b}: newPayload ' + ' | '.join(f'{g} {SA(ks, a, "new_payload_ms") / SA(ks, b, "new_payload_ms"):.4f}' for g, ks in asel.items())
        + '; execution ' + ' | '.join(f'{g} {SA(ks, a, "exec_ms") / SA(ks, b, "exec_ms"):.4f}' for g, ks in asel.items()), ao)
for c in ('H0', 'H3', 'H4'):
    for g, ks in asel.items():
        m = len(ks)
        say(f'{c} {g:4s} per block: newPayload {SA(ks, c, "new_payload_ms") / m:.2f} execution {SA(ks, c, "exec_ms") / m:.2f} '
            f'outside {(SA(ks, c, "new_payload_ms") - SA(ks, c, "exec_ms")) / m:.2f} ms', ao)
ao.close()

# ---------------- recorder process (records on; shares and splits only) ----------------
RROWS = ('H0n', 'H0', 'H3', 'H4', 'H5')
NEED = ['new_payload_ms', 'exec_ms', 'gas_used', 'd_slot_miss_ms', 'acct_miss_ms', 'code_miss_ms', 'eap_reads', 'slot_miss', 'proc_read_mb'] + \
    [f'{t}_hit_{s}' for t in ('acct', 'slot', 'code') for s in ('eap', 'cs0', 'cs1')]   # the recorder's files have ~1,400 columns
R = defaultdict(dict)
for k in (0, 4, 8):
    for fn in glob.glob(f'{E}/e270rec-{k}/results/blocks_rec*.csv'):
        for r in csv.DictReader(open(fn)):
            if r['role'] == 'measured' and int(float(r['pos'])) >= 2 and r['cfg'] in RROWS:
                R[(k, int(r['block']))][r['cfg']] = {c: r.get(c) for c in NEED}
rkeys = sorted(x for x in R if all(c in R[x] for c in RROWS))
rsel = {'all': rkeys, 'reg': [x for x in rkeys if CLS.get(x[1]) == 'nomint'], 'mint': [x for x in rkeys if CLS.get(x[1]) == 'mint']}
SR = lambda ks, c, k: sum(f(R[x][c], k) for x in ks)   # noqa: E731
WAIT = ('d_slot_miss_ms', 'acct_miss_ms', 'code_miss_ms')
wo = open(OUT + 'wait_by_class.txt', 'w')
say(f'recorder process: {len(rkeys)} blocks under all {len(RROWS)} rows (regular {len(rsel["reg"])}, batch-mint {len(rsel["mint"])})', wo)
say('per block (ms): execution, storage wait (slot + account + code) and its share, rest, outside execution, newPayload; '
    'and per Mgas: execution, wait, rest', wo)
for c in RROWS:
    for g, ks in rsel.items():
        m = len(ks); ex = SR(ks, c, 'exec_ms') / m; wt = sum(SR(ks, c, k) for k in WAIT) / m; nb = SR(ks, c, 'new_payload_ms') / m
        gas = SR(ks, c, 'gas_used') / m / 1e6
        say(f'{c:3s} {g:4s} n={m:5d} execution {ex:6.2f} wait {wt:6.2f} ({wt / ex:5.1%}) slot {SR(ks, c, "d_slot_miss_ms") / m:6.2f} '
            f'rest {ex - wt:6.2f} outside {nb - ex:5.2f} newPayload {nb:6.2f}; per Mgas execution {ex / gas:.3f} wait {wt / gas:.3f} rest {(ex - wt) / gas:.3f}', wo)
wo.close()
with open(OUT + 'motiv.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['x', 'cls', 'row', 'wait', 'rest', 'total', 'tlab', 'spct'])
    for x, g, c in ((1, 'all', 'H0n'), (2.5, 'all', 'H0'), (4.2, 'reg', 'H0n'), (5.7, 'reg', 'H0'), (7.4, 'mint', 'H0n'), (8.9, 'mint', 'H0')):
        ks = rsel[g]; gas = SR(ks, c, 'gas_used'); ex = SR(ks, c, 'exec_ms') / gas * 1e6; wt = sum(SR(ks, c, k) for k in WAIT) / gas * 1e6
        w.writerow([x, g, c, f'{wt:.4f}', f'{ex - wt:.4f}', f'{ex:.4f}', f'{ex:.2f}', f'{100 * wt / ex:.0f}'])
with open(OUT + 'abl_split.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['y', 'row', 'cfg', 'slot', 'acctcode', 'rest', 'exec', 'np', 'ratio_np', 'ratio_exec', 'rlab'])
    ks = rkeys; gas = SR(ks, 'H0', 'gas_used'); bn = SR(ks, 'H0', 'new_payload_ms'); be = SR(ks, 'H0', 'exec_ms')
    ao = open(OUT + 'abl.txt', 'a')
    say('ablation figure (recorder process, ms per Mgas; ratios of execution within the recorder process):', ao)
    for y, c in ((4, 'H0'), (3, 'H5'), (2, 'H3'), (1, 'H4')):
        sl = SR(ks, c, 'd_slot_miss_ms') / gas * 1e6; ac = (SR(ks, c, 'acct_miss_ms') + SR(ks, c, 'code_miss_ms')) / gas * 1e6
        ex = SR(ks, c, 'exec_ms') / gas * 1e6; rn = SR(ks, c, 'new_payload_ms') / bn; re_ = SR(ks, c, 'exec_ms') / be
        w.writerow([y, c, c, f'{sl:.4f}', f'{ac:.4f}', f'{ex - sl - ac:.4f}', f'{ex:.4f}', f'{SR(ks, c, "new_payload_ms") / len(ks):.3f}', f'{rn:.4f}', f'{re_:.4f}', f'{re_:.2f}'])
        say(f'  {c}: slot {sl:.3f} | account+code {ac:.3f} | rest {ex - sl - ac:.3f} || execution {ex:.3f} ms per Mgas; newPayload {rn:.3f}, execution {re_:.3f} of G0', ao)
    ao.close()
fo = open(OUT + 'funnel.txt', 'w')
PH = [f'{t}_hit_{s}' for t in ('acct', 'slot', 'code') for s in ('eap', 'cs0', 'cs1')]
for g, ks in rsel.items():
    m = len(ks); reads = SR(ks, 'H4', 'eap_reads'); plan = sum(f(R[x]['H4'], k) for x in ks for k in PH)
    m0, m4 = SR(ks, 'H0', 'slot_miss'), SR(ks, 'H4', 'slot_miss'); rd0, rd4 = SR(ks, 'H0', 'proc_read_mb'), SR(ks, 'H4', 'proc_read_mb')
    unused = sorted(f(R[x]['H4'], 'eap_reads') - sum(f(R[x]['H4'], k) for k in PH) for x in ks)
    say(f'{g:4s} ({m} blocks), per block: reader reads {reads / m:.1f}; used from plan fills {plan / m:.1f}, '
        f'not used {(reads - plan) / m:.1f} (used {plan / reads:.1%}); slot misses G0 {m0 / m:.1f} G4 {m4 / m:.1f} ({1 - m4 / m0:.1%} fewer); '
        f'unused median {unused[len(unused) // 2]:.0f}, p99 {unused[int(0.99 * len(unused))]:.0f}, max {unused[-1]:.0f}; storage reads MB per block (read_bytes / 1e6) G0 {rd0 / m:.2f} G4 {rd4 / m:.2f}', fo)
fo.close()
