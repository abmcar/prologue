#!/usr/bin/env python3
"""Copied 11-07 from master/scripts/verify_lateslots_stream.py for the paper (review item 10): the same
rules and records; added at the end the all-block shares with the classes weighted by the composition of the evaluated blocks
(8,950 regular and 1,050 batch-mint, 10.5%) instead of the lab run's own (7,475 and 2,525). Usage (repository root):
  python3 paper/scripts/offline/lateslots_eval.py m3 3 AB1ng > paper/data/offline/lateslots_m3_eval.txt
Original header:: independent check of the earlier split of the stock slot wait (scripts/x290_lateslots.py, x290_stockside.py).

Record layout read from reth-2.9.0-eap ca7f4a9 crates/engine/execution-cache/src/cached_state.rs 3537-3577:
  tx    [i, status, dispatch_us, ws_us, we_us, pw0n, pw0us, pw1n, pw1us, pw2n, pw2us, es_us, ee_us, ...]  (-1 absent)
  miss2 [i, t_ns, cls, src, dt_ns, addr, key, dur_ns, frame]   (i < 0: system calls before/after the transactions)
Counted blocks: blocks_<L><p>.csv role measured, cfg CFG, pos >= 2.
Prints, per block class (all, general, mint):
  (1) transactions whose own prewarm ended (status 6 and 0 <= we <= es) before the execution thread started them: share of
      transactions, share of the transaction slot misses and of their wait;
  (2) state of the own prewarm at each miss: running (ws <= t < we or we absent), ended before (we <= t), not started or
      absent (ws absent or ws > t);
  (3) among misses with the own prewarm ended before the miss: share filled by nobody in this block (cls 0).
usage: python3 master/scripts/verify_lateslots_stream.py [LBL] [NPASS] [CFG]: streaming copy of verify_lateslots.py (same rules; records are aggregated as they are read, so memory stays small)."""
import collections, csv, json, sys

EXP = os.environ.get("TRACE_ROOT", "traces") + "/own-prewarm"
CLASS = os.environ.get("TRACE_ROOT", "traces") + "/stepwise/results/blocks_class_zk_a1.csv"
lbl = sys.argv[1] if len(sys.argv) > 1 else 'tf3'
npass = int(sys.argv[2]) if len(sys.argv) > 2 else 3
cfg = sys.argv[3] if len(sys.argv) > 3 else 'AB1ng'
cls_of = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(CLASS))}
names = (('all', None), ('general', 'nomint'), ('mint', 'mint'))
A = {n: dict(nb=0, ntx=0, nend=0, m=collections.Counter(), w=collections.Counter(), st=collections.Counter(), sw=collections.Counter(), d0=collections.Counter()) for n, _ in names}
for p in range(npass):
    want = set()
    for r in csv.DictReader(open(f'{EXP}/results/blocks_{lbl}{p}.csv')):
        if r['role'] == 'measured' and r['cfg'] == cfg and int(float(r['pos'])) >= 2:
            want.add(int(r['block']))
    for line in open(f'{EXP}/raw/{lbl}{p}.diag.jsonl'):
        if line.startswith('{"block":'):   # skip unwanted records without parsing them
            j = line.index(',', 9)
            if int(line[9:j]) not in want:
                continue
        r = json.loads(line)
        if r['block'] not in want:
            continue
        tx = r['tx']; ended = {}; ntx = nend = 0
        for x in tx:
            if x[11] < 0:
                continue
            ntx += 1
            e = x[1] == 6 and 0 <= x[4] <= x[11]
            ended[x[0]] = e; nend += e
        rows = []
        for x in r['miss2']:
            i = x[0]
            if i < 0 or i >= len(tx):
                continue
            g = 'ended' if ended.get(i, False) else 'not ended'
            t = x[1] / 1000; ws, we = tx[i][3], tx[i][4]
            if ws < 0 or ws > t:
                s = 'not started or absent'
            elif we < 0 or we > t:
                s = 'running'
            else:
                s = 'ended before the miss'
            rows.append((g, s, x[2], x[7]))
        for n, sel in names:
            if sel is not None and cls_of.get(r['block']) != sel:
                continue
            a = A[n]; a['nb'] += 1; a['ntx'] += ntx; a['nend'] += nend
            for g, s, c, w in rows:
                a['m'][g] += 1; a['w'][g] += w; a['st'][s] += 1; a['sw'][s] += w
                if s == 'ended before the miss':
                    a['d0']['n'] += 1; a['d0']['w'] += w
                    if c == 0:
                        a['d0']['n0'] += 1; a['d0']['w0'] += w
print(f'{lbl} x{npass} {cfg}')
for n, _ in names:
    a = A[n]
    if not a['nb']:
        continue
    m, w, st, sw, d0, ntx, nend = a['m'], a['w'], a['st'], a['sw'], a['d0'], a['ntx'], a['nend']
    tm = sum(m.values()) or 1; tw = sum(w.values()) or 1
    print(f'\n== {n}: {a["nb"]} blocks, {ntx} transactions, {tm} slot misses, wait {tw / 1e6:.1f} ms')
    print(f'(1) own prewarm not ended at execution start: {(ntx - nend) / ntx:.1%} of transactions, '
          f'{m["not ended"] / tm:.1%} of misses, {w["not ended"] / tw:.1%} of wait')
    for s in ('running', 'ended before the miss', 'not started or absent'):
        print(f'(2) {s:24s} {st[s] / tm:6.1%} of misses  {sw[s] / tw:6.1%} of wait')
    if d0['n']:
        print(f'(3) own ended before the miss and nobody filled the slot in this block: {d0["w0"] / tw:.1%} of all wait '
              f'({d0["w0"] / d0["w"]:.1%} of the ended-before wait)')

# ---- added 11-07: all blocks with the classes weighted by the evaluated blocks' composition ----
EVAL = {'general': 8950, 'mint': 1050}
g, mt = A['general'], A['mint']
sc = {'general': EVAL['general'] / g['nb'], 'mint': EVAL['mint'] / mt['nb']}
def wsum(key, sub):
    return sum(sc[c] * A[c][key][sub] for c in ('general', 'mint'))
tw = sum(sc[c] * sum(A[c]['w'].values()) for c in ('general', 'mint'))
ntx = sum(sc[c] * A[c]['ntx'] for c in ('general', 'mint')); nend = sum(sc[c] * A[c]['nend'] for c in ('general', 'mint'))
print(f'\n== all, classes weighted {EVAL["general"]} : {EVAL["mint"]} (evaluated blocks; lab run {g["nb"]} : {mt["nb"]})')
print(f'(1) own prewarm not ended at execution start: {(ntx - nend) / ntx:.1%} of transactions, {wsum("w", "not ended") / tw:.1%} of wait')
for st in ('running', 'ended before the miss', 'not started or absent'):
    print(f'(2) {st:24s} {wsum("sw", st) / tw:6.1%} of wait')
print(f'(3) own ended before the miss and nobody filled the slot in this block: {wsum("d0", "w0") / tw:.1%} of all wait')
