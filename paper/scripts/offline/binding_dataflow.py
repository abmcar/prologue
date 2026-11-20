#!/usr/bin/env python3
"""Restructured paper (2026-11-06): the binding time of
every storage read from the replay's dataflow labels alone, without the access plans, on the reads, blocks and stock
slot-wait weights of Table 1.

Inputs (read only):
  derived/why234_*.jsonl: eap-why (src/history_replay/src/why.rs) at the first access of each (block, tx,
    address, key) of export216 (regular blocks) and export234 (batch-mint blocks); items of kind "s". Fields used:
    kl  labels local to the read's call frame (why.rs lines 140-150): calldata 1, caller 2, value 4, storage address 8,
        environment 16 (origin, block fields, calldata size) | storage value read in the frame 32, transient storage 64,
        return data or success flag of a sub-call 128, balance/code/gas/gas price/block hash/msize 256, precompile
        output 512, created address 1024;
    kd  number of chained storage reads over the transaction (0: transaction input and constants only);
    kg  transaction-level flags: 1 a storage value read was changed earlier in the block, 2 EXT value, 4 transient
        storage, 8 precompile output;
    chain_d, chain_g  the same over the inputs (target, value, calldata) of every call on the stack above the entry call;
    depth (0 = entry call), scheme (4 = creation frame).
  results/b3/w290_{general,mint}_blocks.txt (the blocks of Table 1) and w290_{general,mint}_slots.tsv.gz
    (stock reth 2.9.0 execution-thread slot wait per read, ns; the lab run).
  results/b3/cls_{general,mint}_290/cls234_sum.csv: Table 1's plan-based class amounts on the same reads and
    weights (rw234.py), used for the cross-tabulation.
  results/blocks_class_zk_a1.csv: block classes, for the population weights (as look234w.py).

Classes (labels only; no plan is consulted):
  relative to the call:  start  the key depends on none of 32..1024 (only on the call's calldata, caller, value,
                                storage address, environment and constants): it binds at the latest when the call starts;
                         stor   the key depends on a storage or transient-storage value read in the call;
                         ret    on a sub-call's return data (and not on the above);
                         oth    on another run-time value (EXT, precompile output, created address).
  relative to the transaction (sufficient and necessary bounds for binding when the transaction starts):
                         arr_lo  kd = chain_d = 0 and no EXT or transient-storage flag in kg or chain_g: the key and
                                 every input of the calls that lead to the read depend only on the transaction's input,
                                 the block's fields, code and constants;
                         arr_hi  the key alone satisfies this (ignores how the read's storage address was chosen).
  stale: a storage value the key or the chain depends on was changed earlier in the block (kg or chain_g bit 1).
Cross-tabulation with Table 1 (exact by algebra; reads in creation frames are left out on both sides and must equal
  Table 1's class X): plan and dataflow = labelled start minus class 4; plan only = labelled during minus classes
  3b + 3c + O; dataflow only = class 4; neither = 3b + 3c + O.

usage: binding_dataflow.py OUTDIR   -> OUTDIR/binding_dataflow_agg.csv (raw sums), OUTDIR/binding_dataflow.txt (tables)
11-07: env POP=eval weights the two classes by the composition of the evaluated blocks (8,950
regular and 1,050 batch-mint of the main comparison's 10,000 blocks) instead of the blocks of 26,263,606-26,268,604 (POP=pop,
the default, as before); env AGG=FILE reads the raw sums from an earlier run's binding_dataflow_agg.csv instead of the
replay records (the sums do not depend on the weights); the tables then go to OUTDIR/binding_dataflow_<POP>.txt.
Run (paper copy): labq run -k heavy -l prologue-paper-binding-dataflow -m 6 -- python3 scripts/binding_dataflow.py data
"""
import csv, glob, gzip, json, os, sys
from collections import defaultdict

X = os.environ.get("TRACE_ROOT", "traces")   # per-read traces and exports, not in the repository
WHY = sorted(glob.glob(f'{X}/key-determination-time/derived/why234_*.jsonl'))
B3 = f'{X}/prediction-vs-official/results/b3'
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

L_DUR = 32 | 64 | 128 | 256 | 512 | 1024
L_STOR, L_RET = 32 | 64, 128
G_STALE, G_RUN = 1, 2 | 4


def na(a):
    a = a.strip().lower().removeprefix('0x'); return '0x' + a.rjust(40, '0')[-40:]


def nk(k):
    k = k.strip().lower().removeprefix('0x'); return '0x' + k.rjust(64, '0')[-64:]


kept = {}
for c in ('general', 'mint'):
    for b in open(f'{B3}/w290_{c}_blocks.txt').read().split():
        kept[int(b)] = c
W = {}
for c in ('general', 'mint'):
    with gzip.open(f'{B3}/w290_{c}_slots.tsv.gz', 'rt') as f:
        f.readline()
        for l in f:
            r = l.rstrip('\n').split('\t')
            W[(int(r[0]), int(r[1]), na(r[2]), nk(r[3]))] = float(r[4])
print('kept blocks', len(kept), 'weights', len(W), 'files', len(WHY), flush=True)
POP, AGG = os.environ.get('POP', 'pop'), os.environ.get('AGG')

# raw sums: (class, scope, fr, cre, ent, txl, stale) -> amount
agg = defaultdict(float)
seen = set(); dup = 0; items = 0
LIMIT = int(os.environ.get('LIMIT', '0'))   # smoke test: lines per file
if AGG:
    for r in csv.DictReader(open(AGG)):
        agg[(r['class'], r['scope'], r['fr'], int(r['creation']), int(r['entry']), r['txl'], int(r['stale']))] += float(r['amount'])
    items = int(sum(v for k, v in agg.items() if k[1] == 'all'))
for fn in ([] if AGG else WHY):
    with open(fn) as fh:
        for i, l in enumerate(fh):
            if LIMIT and i >= LIMIT:
                break
            if '"kind":"s"' not in l:
                continue
            j = json.loads(l)
            if j.get('kind') != 's':
                continue
            b = j['block']; c = kept.get(b)
            if c is None:
                continue
            k = (b, j['tx'], na(j['a']), nk(j['k']))
            if k in seen:
                dup += 1; continue
            seen.add(k); items += 1
            kl, kd, kg = j.get('kl', 0), j.get('kd', 0), j.get('kg', 0)
            cd, cg = j.get('chain_d', 0), j.get('chain_g', 0)
            if kl & L_DUR == 0: fr = 'start'
            elif kl & L_STOR: fr = 'stor'
            elif kl & L_RET: fr = 'ret'
            else: fr = 'oth'
            key_ok = kd == 0 and kg & G_RUN == 0
            txl = ('arr_lo' if cd == 0 and cg & G_RUN == 0 else 'arr_hi') if key_ok else 'no'
            stale = int(bool((kg | cg) & G_STALE))
            a = (fr, int(j.get('scheme', 0) == 4), int(j.get('depth', 0) == 0), txl, stale)
            w = W.get(k, 0.0)
            agg[(c, 'all') + a] += 1
            if w > 0:
                agg[(c, 'miss_n') + a] += 1
                agg[(c, 'miss_wr_ns') + a] += w
    print(fn.rsplit('/', 1)[1], 'items so far', items, flush=True)
print('items', items, 'duplicates', dup, flush=True)
with open(os.devnull if AGG else f'{OUT}/binding_dataflow_agg.csv', 'w', newline='') as fh:
    cw = csv.writer(fh)
    cw.writerow(['class', 'scope', 'fr', 'creation', 'entry', 'txl', 'stale', 'amount'])
    for k in sorted(agg):
        cw.writerow(list(k) + [f'{agg[k]:.0f}'])

# ---- tables ----
C = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(f'{X}/eap-stepwise/results/blocks_class_zk_a1.csv'))}
bl = [b for b in C if 26263606 <= b <= 26268604]
N = {'mint': sum(1 for b in bl if C[b] == 'mint')}; N['general'] = len(bl) - N['mint']
if POP == 'eval':
    N = {'general': 8950, 'mint': 1050}
n = {c: sum(1 for v in kept.values() if v == c) for c in ('general', 'mint')}
T1 = {c: {(r['scope'], r['class']): float(r['amount']) for r in csv.DictReader(open(f'{B3}/cls_{c}_290/cls234_sum.csv'))}
      for c in ('general', 'mint')}
lines = [f'POP={POP}; weights: general {N["general"]}, batch-mint {N["mint"]}; samples {n}; items {items}, duplicates {dup}']


def S(c, scope, pred):
    return sum(v for k, v in agg.items() if k[0] == c and k[1] == scope and pred(*k[2:]))


for scope in ('all', 'miss_n', 'miss_wr_ns'):
    lines.append(f'== scope {scope}')
    res = {}
    for c in ('general', 'mint'):
        r = {}
        tot = S(c, scope, lambda *a: True)
        r['_total'] = tot
        r['_total_table1'] = T1[c][(scope, 'total')]
        r['_creation'] = S(c, scope, lambda fr, cre, ent, txl, st: cre == 1)
        r['_X_table1'] = T1[c][(scope, 'X')]
        # relative to the call, labels only (all reads)
        for f in ('start', 'stor', 'ret', 'oth'):
            r[f'call: {f}'] = S(c, scope, lambda fr, cre, ent, txl, st, f=f: fr == f)
        r['call: start, entry call'] = S(c, scope, lambda fr, cre, ent, txl, st: fr == 'start' and ent == 1)
        r['call: start, inner calls'] = S(c, scope, lambda fr, cre, ent, txl, st: fr == 'start' and ent == 0)
        # cross-tabulation with Table 1 (creation frames left out)
        st_nc = S(c, scope, lambda fr, cre, ent, txl, st: cre == 0 and fr == 'start')
        du_nc = S(c, scope, lambda fr, cre, ent, txl, st: cre == 0 and fr != 'start')
        t = lambda *cl: sum(T1[c].get((scope, x), 0.0) for x in cl)
        r['x: plan and dataflow'] = st_nc - t('4')
        r['x: plan only'] = du_nc - t('3b', '3c', 'O')
        r['x: dataflow only'] = t('4')
        r['x: neither'] = t('3b', '3c', 'O')
        r['x: creation frames'] = r['_creation']
        r['x: check plan total (= Table 1 class 1+2)'] = r['x: plan and dataflow'] + r['x: plan only']
        r['table1: class 1+2'] = t('1', '2')
        # relative to the transaction
        r['tx: arr_lo'] = S(c, scope, lambda fr, cre, ent, txl, st: txl == 'arr_lo')
        r['tx: arr_hi (incl. arr_lo)'] = S(c, scope, lambda fr, cre, ent, txl, st: txl != 'no')
        r['tx: arr_lo, entry call'] = S(c, scope, lambda fr, cre, ent, txl, st: txl == 'arr_lo' and ent == 1)
        r['tx: arr_lo, inner calls'] = S(c, scope, lambda fr, cre, ent, txl, st: txl == 'arr_lo' and ent == 0)
        r['tx: arr_hi, inner calls'] = S(c, scope, lambda fr, cre, ent, txl, st: txl != 'no' and ent == 0)
        r['tx: call start but not arr_hi'] = S(c, scope, lambda fr, cre, ent, txl, st: fr == 'start' and txl == 'no')
        r['tx: not arr_hi, nothing changed earlier in the block'] = S(c, scope, lambda fr, cre, ent, txl, st: txl == 'no' and st == 0)
        res[c] = r
    w = {c: N[c] / n[c] for c in ('general', 'mint')}
    res['all'] = {k: sum(w[c] * res[c][k] for c in ('general', 'mint')) for k in res['general']}
    for k in res['general']:
        if k.startswith('_'):
            lines.append(f'  {k:52s} ' + '  '.join(f'{c} {res[c][k]:,.0f}' for c in ('general', 'mint', 'all')))
        else:
            lines.append(f'  {k:52s} ' + '  '.join(f'{c} {100 * res[c][k] / res[c]["_total"]:7.3f}%' for c in ('general', 'mint', 'all')))
open(f'{OUT}/binding_dataflow' + (f'_{POP}' if AGG else '') + '.txt', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
