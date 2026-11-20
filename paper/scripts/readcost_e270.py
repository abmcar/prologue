#!python3
"""The execution thread's reads per row (table "readcost") on the recording processes (segments 0, 4, 8; rows H0n
without prewarming, H0 stock reth, H3 Prologue without plans, H4 Prologue, H5 stock reth plus plans).
Inputs: results/main/raw/e270rec-<k>/raw/rec<k><p>.diag.jsonl (the per-read records; 60-73 MB each, not in the
repository), rec<k><p>.node.log and results/blocks_rec<k><p>.csv.
Outputs: paper/data/f270_readcost.txt and f270_readcost.csv.
usage (repository root): python3 paper/scripts/readcost_e270.py [e270] [ROWS]"""
import collections, csv, json, os, re, sys

import numpy as np

TAG = sys.argv[1] if len(sys.argv) > 1 else 'e270'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(ROOT)   # repository root
E252 = os.path.join(ROOT, 'results/earlier/raw')   # optional: an earlier measurement (tag e252)
E257 = os.path.join(ROOT, 'results/main/raw')
# 3 segments, 11 passes; rows Q0n (no prewarm), Q0 (stock prewarm), Q2, Q3, Q4 (full)
# recorder process, 3 segments, 5 passes; rows G0n (no prewarm), G0 (stock), G3, G4 (full), G5
CONF = {'e252': ([(f'{E252}/e252abl-{k}', f'abl{k}') for k in (0, 4, 8)], 11, ['Q0n', 'Q0', 'Q2', 'Q3', 'Q4']),
        'e270': ([(f'{E257}/e270rec-{k}', f'rec{k}') for k in (0, 4, 8)], 5, ['H0n', 'H0', 'H3', 'H4', 'H5'])}
PAIRS = {'e252': [('Q0', 'Q4'), ('Q0n', 'Q0'), ('Q0', 'Q2'), ('Q2', 'Q3'), ('Q3', 'Q4'), ('Q0', 'Q3')],
         'e270': [('H0', 'H4'), ('H0n', 'H0'), ('H0', 'H3'), ('H3', 'H4'), ('H0', 'H5'), ('H5', 'H4')]}
OUTP = os.path.join(ROOT, 'paper/data', {'e270': 'f270_readcost', 'e252': 'f270_readcost_e252ref'}[TAG])
RUNS, NPASS, ROWS = CONF[TAG]
if len(sys.argv) > 2:
    ROWS = sys.argv[2].split(',')
PAIRS[TAG] = [(a, b) for a, b in PAIRS[TAG] if a in ROWS and b in ROWS]
_txt = open(OUTP + '.txt', 'w')


class _Tee:  # print to stdout and to the .txt output
    def write(self, s):
        sys.__stdout__.write(s)
        _txt.write(s)

    def flush(self):
        sys.__stdout__.flush()
        _txt.flush()


sys.stdout = _Tee()
FAST = 30.0   # us
SRC = ('pw', 'old', 'eap', 'cs0', 'cs1')
KINDS = ('acct', 'slot', 'code')
OUTC = ('slot_wait', 'slot_fast', 'slot_slow', 'acct_fast', 'acct_slow', 'code_fast', 'code_slow')
KV = re.compile(r'\b(\w+)=(-?\d+|true|false)\b')
strip = lambda s: re.sub(r'\x1b\[[0-9;]*m', '', s)  # noqa: E731
S = {c: collections.defaultdict(float) for c in ROWS}   # sums over counted blocks
D = {c: collections.defaultdict(list) for c in ROWS}    # durations (us) by outcome
FIT = {c: [] for c in ROWS}                             # per block (slow misses, engine major faults)
CHK = {c: collections.defaultdict(float) for c in ROWS}  # added: diag records against the blocks files
for run, lab in RUNS:
    for p in range(NPASS):
        L = f'{lab}{p}'
        want = {}
        brow = {}  # added: the counted blocks' rows, for the checks
        for r in csv.DictReader(open(f'{run}/results/blocks_{L}.csv')):
            c = r['cfg'].split('+')[0]
            if r['role'] != 'measured' or int(float(r['pos'])) < 2 or c not in S:
                continue
            b = int(r['block'])
            want[b] = c
            brow[b] = r
            s = S[c]
            s['blocks'] += 1
            s['mgas'] += float(r['gas_used']) / 1e6
            for k in ('exec_ms', 'new_payload_ms', 'engine_majflt', 'engine_minflt', 'proc_majflt', 'proc_minflt', 'proc_read_mb'):
                s[k] += float(r[k] or 0)
            for k in ('d_slot_miss', 'd_slot_miss_ms'):  # added: storage wait as final252.py, and the checks
                s[k] += float(r[k] or 0)
            for kd in KINDS:
                for src in SRC:
                    s[f'{kd}_hit'] += float(r[f'{kd}_hit_{src}'] or 0)
                    s[f'{kd}_hit_ms'] += float(r[f'{kd}_hit_{src}_ms'] or 0)
                    grp = 'pre' if src == 'pw' else 'old' if src == 'old' else 'plan'
                    s[f'{kd}_hit_{grp}'] += float(r[f'{kd}_hit_{src}'] or 0)
                s[f'{kd}_miss'] += float(r[f'{kd}_miss'] or 0)
                s[f'{kd}_miss_ms'] += float(r[f'{kd}_miss_ms'] or 0)
        for ln in open(f'{run}/raw/{L}.node.log', errors='replace'):
            if 'eap accflt block=' in ln or 'eap block block=' in ln:
                d = dict(KV.findall(strip(ln)))
                b = int(d.get('block', -1))
                if b in want:
                    if 'eap accflt block=' in ln:
                        S[want[b]]['accflt_absent'] += int(d.get('absent', 0))
                        S[want[b]]['accflt_lookups'] += int(d.get('lookups', 0))
                    else:
                        S[want[b]]['ccv_hits'] += int(d.get('ccv_hits', 0))
        maj = {int(r['block']): float(r['engine_majflt'] or 0) for r in csv.DictReader(open(f'{run}/results/blocks_{L}.csv'))
               if int(r['block']) in want}
        seen = set()  # added: for the checks
        for ln in open(f'{run}/raw/{L}.diag.jsonl'):
            if not ln.startswith('{"block":'):
                continue
            b = int(ln[9:ln.index(',', 9)])
            if b not in want:
                continue
            c, r = want[b], json.loads(ln)
            s, dd = S[c], D[c]
            slow = 0
            for x in r['miss2']:
                us = x[7] / 1000
                if x[2] in (1, 2) and x[4] <= x[7]:
                    o = 'slot_wait'
                else:
                    o = 'slot_fast' if us < FAST else 'slot_slow'
                    slow += o == 'slot_slow'
                s[o] += 1
                s[o + '_ms'] += us / 1000
                dd[o].append(us)
            for x in r['other']:
                kd = {0: 'acct', 2: 'code'}.get(x[2])
                if kd is None:
                    continue
                us = x[4] / 1000
                o = f'{kd}_fast' if us < FAST else f'{kd}_slow'
                slow += o.endswith('slow')
                s[o] += 1
                s[o + '_ms'] += us / 1000
                dd[o].append(us)
            FIT[c].append((slow, maj.get(b, 0.0)))
            # added: this block's diag record against its row in the blocks file
            ck, br = CHK[c], brow[b]
            ck['records'] += 1
            ck['repeated'] += b in seen
            seen.add(b)
            n2 = len(r['miss2'])
            na = sum(1 for x in r['other'] if x[2] == 0)
            nc = sum(1 for x in r['other'] if x[2] == 2)
            ck['slot_n'] += n2
            ck['slot_ms'] += sum(x[7] for x in r['miss2']) / 1e6
            ck['acct_n'] += na
            ck['code_n'] += nc
            ck['slot_diff_counter'] += n2 != round(float(br['slot_miss'] or 0))
            ck['slot_diff_driver'] += n2 != round(float(br['d_slot_miss'] or 0))
            ck['acct_diff'] += na != round(float(br['acct_miss'] or 0))
            ck['code_diff'] += nc != round(float(br['code_miss'] or 0))
        for b, c in want.items():
            CHK[c]['missing'] += b not in seen
pb = lambda c, k: S[c][k] / S[c]['blocks']  # noqa: E731
print(f'# readcost_e270.py {TAG} (read costs): rows {ROWS}; counted blocks (role measured, position >= 2); '
      f'per block means; fast/slow split at {FAST:.0f} us')
for c in ROWS:
    print(f'\n== {c}: {S[c]["blocks"]:.0f} blocks, {S[c]["mgas"] / S[c]["blocks"]:.2f} Mgas per block; execution {pb(c, "exec_ms"):.3f} ms, '
          f'newPayload {pb(c, "new_payload_ms"):.3f} ms')
    for kd in KINDS:
        h, m = S[c][f'{kd}_hit'], S[c][f'{kd}_miss']
        print(f'  {kd}: reads {(h + m) / S[c]["blocks"]:.1f}, hits {h / S[c]["blocks"]:.1f} (pre-execution {pb(c, kd + "_hit_pre"):.1f}, '
              f'plan readers {pb(c, kd + "_hit_plan"):.1f}, before {pb(c, kd + "_hit_old"):.1f}), misses {m / S[c]["blocks"]:.2f}; '
              f'hit rate {h / (h + m):.4f}; per hit {S[c][kd + "_hit_ms"] / h * 1000:.2f} us, per miss {S[c][kd + "_miss_ms"] / m * 1000:.1f} us; '
              f'read time {(S[c][kd + "_hit_ms"] + S[c][kd + "_miss_ms"]) / S[c]["blocks"]:.3f} ms')
    for o in ('slot_wait', 'slot_fast', 'slot_slow', 'acct_fast', 'acct_slow', 'code_fast', 'code_slow'):
        v = np.array(D[c][o]) if D[c][o] else np.array([0.0])
        print(f'    {o:>9}: {pb(c, o):7.2f} per block, {pb(c, o + "_ms"):.3f} ms; per read mean {v.mean():6.1f} us, median '
              f'{np.median(v):6.1f}, nine-tenths {np.percentile(v, 90):6.1f}')
    f = np.array(FIT[c])
    if len(f) > 2 and f[:, 0].std() > 0:
        slope, icpt = np.polyfit(f[:, 0], f[:, 1], 1)
        print(f'    check of the threshold: engine major faults per block = {slope:.2f} x slow misses + {icpt:.1f} '
              f'(correlation {np.corrcoef(f[:, 0], f[:, 1])[0, 1]:.3f}; slow misses {f[:, 0].mean():.1f}, faults {f[:, 1].mean():.1f} per block)')
    print(f'  faults per block: execution thread major {pb(c, "engine_majflt"):.1f}, minor {pb(c, "engine_minflt"):.1f}; process major '
          f'{pb(c, "proc_majflt"):.1f}, minor {pb(c, "proc_minflt"):.1f}; other threads major '
          f'{pb(c, "proc_majflt") - pb(c, "engine_majflt"):.1f}; disk reads {pb(c, "proc_read_mb"):.3f} MB per block')
    print(f'  filter answered absent accounts {pb(c, "accflt_absent"):.2f} of {pb(c, "accflt_lookups"):.1f} lookups per block; code '
          f'backup cache hits {pb(c, "ccv_hits"):.2f} per block')


def split(a, b):
    out = {}
    for kd in KINDS:
        LA, LB = (S[x][f'{kd}_hit'] + S[x][f'{kd}_miss'] for x in (a, b))
        LA, LB = LA / S[a]['blocks'], LB / S[b]['blocks']
        rA, rB = (S[x][f'{kd}_miss'] / (S[x][f'{kd}_hit'] + S[x][f'{kd}_miss']) for x in (a, b))
        mA, mB = (S[x][f'{kd}_miss_ms'] / S[x][f'{kd}_miss'] for x in (a, b))
        hA, hB = (S[x][f'{kd}_hit_ms'] / S[x][f'{kd}_hit'] for x in (a, b))
        t = dict(reads=(LA - LB) * (rA * mA + (1 - rA) * hA), hitrate=LB * (rA - rB) * (mA - hA), permiss=LB * rB * (mA - mB),
                 perhit=LB * (1 - rB) * (hA - hB), total=LA * (rA * mA + (1 - rA) * hA) - LB * (rB * mB + (1 - rB) * hB))
        # misses only (hits counted with computation in the rest-of-execution half): the same split without the hit terms
        t.update(reads_m=(LA - LB) * rA * mA, hitrate_m=LB * (rA - rB) * mA, total_m=LA * rA * mA - LB * rB * mB)
        if kd == 'slot':
            cls = ('slot_wait', 'slot_fast', 'slot_slow')
            nA, nB = (sum(S[x][o] for o in cls) for x in (a, b))
            sA, sB = ({o: S[x][o] / n for o in cls} for x, n in ((a, nA), (b, nB)))
            tA, tB = ({o: S[x][o + '_ms'] / S[x][o] if S[x][o] else 0.0 for o in cls} for x in (a, b))
            t['permiss_mix'] = LB * rB * sum((sA[o] - sB[o]) * tA[o] for o in cls)
            t['permiss_time'] = LB * rB * sum(sB[o] * (tA[o] - tB[o]) for o in cls)
        out[kd] = t
    return out


rows_csv = []
for a, b in PAIRS.get(TAG) or [(ROWS[0], ROWS[-1])] + [(ROWS[i], ROWS[i + 1]) for i in range(len(ROWS) - 1)]:
    sp = split(a, b)
    tot = {k: sum(sp[kd][k] for kd in KINDS) for k in ('reads', 'hitrate', 'permiss', 'perhit', 'total', 'reads_m', 'hitrate_m', 'total_m')}
    dx = pb(a, 'exec_ms') - pb(b, 'exec_ms')
    print(f'\n== {a} -> {b}: read time shorter by {tot["total"]:.3f} ms per block (execution {dx:.3f} ms; the rest, '
          f'{dx - tot["total"]:.3f} ms, is not reading)')
    for kd in KINDS:
        t = sp[kd]
        extra = (f' (outcome mix {t["permiss_mix"]:+.3f}, outcome times {t["permiss_time"]:+.3f})' if kd == 'slot' else '')
        print(f'  {kd}: fewer reads {t["reads"]:+.3f}, hit rate {t["hitrate"]:+.3f}, per-miss time {t["permiss"]:+.3f}{extra}, '
              f'per-hit time {t["perhit"]:+.3f}; sum {t["reads"] + t["hitrate"] + t["permiss"] + t["perhit"]:+.3f} = {t["total"]:+.3f}')
    print(f'  all kinds: fewer reads {tot["reads"]:+.3f}, hit rate {tot["hitrate"]:+.3f}, per-miss time {tot["permiss"]:+.3f}, '
          f'per-hit time {tot["perhit"]:+.3f}; sum {tot["total"]:+.3f}')
    print(f'  misses only (all kinds): fewer reads {tot["reads_m"]:+.3f}, hit rate {tot["hitrate_m"]:+.3f}, per-miss time '
          f'{tot["permiss"]:+.3f}; sum {tot["total_m"]:+.3f}')
    rows_csv.append(dict(pair=f'{a}->{b}', **{k: round(v, 4) for k, v in tot.items()}, exec_diff=round(dx, 4),
                         slot_mix=round(sp['slot']['permiss_mix'], 4), slot_time=round(sp['slot']['permiss_time'], 4)))

# ---------------- added: checks and Table 3 ----------------
print('\n== checks: diag records (miss2; other kinds 0 and 2) against the blocks files, per block over the counted blocks')
for c in ROWS:
    ck, n = CHK[c], S[c]['blocks']
    print(f'  {c}: {ck["records"]:.0f} diag records for {n:.0f} counted blocks (without a record {ck["missing"]:.0f}, repeated '
          f'{ck["repeated"]:.0f})')
    print(f'    slot misses: diag {ck["slot_n"] / n:.3f}, slot_miss {pb(c, "slot_miss"):.3f}, d_slot_miss {pb(c, "d_slot_miss"):.3f} '
          f'(blocks that differ from diag: {ck["slot_diff_counter"]:.0f} and {ck["slot_diff_driver"]:.0f}); time ms: diag '
          f'{ck["slot_ms"] / n:.3f}, slot_miss_ms {pb(c, "slot_miss_ms"):.3f}, d_slot_miss_ms {pb(c, "d_slot_miss_ms"):.3f}; '
          f'by outcome {sum(pb(c, o) for o in OUTC[:3]):.3f} misses, {sum(pb(c, o + "_ms") for o in OUTC[:3]):.3f} ms')
    print(f'    account misses: diag {ck["acct_n"] / n:.3f}, acct_miss {pb(c, "acct_miss"):.3f} (blocks that differ {ck["acct_diff"]:.0f}); '
          f'code misses: diag {ck["code_n"] / n:.3f}, code_miss {pb(c, "code_miss"):.3f} (blocks that differ {ck["code_diff"]:.0f})')


def t3(c):
    """Table 3's cells for row c (per block), and the mean time per read by outcome (us)."""
    n, h, m = S[c]['blocks'], S[c]['slot_hit'], S[c]['slot_miss']
    mean = lambda o: float(np.mean(D[c][o])) if D[c][o] else float('nan')  # noqa: E731
    return dict(slot_reads=(h + m) / n, slot_hit_rate=h / (h + m), slot_fast=pb(c, 'slot_fast'), slot_slow=pb(c, 'slot_slow'),
                slot_wait=pb(c, 'slot_wait'), engine_majflt=pb(c, 'engine_majflt'), proc_majflt=pb(c, 'proc_majflt'),
                proc_read_mb=pb(c, 'proc_read_mb'),
                storage_wait_ms=pb(c, 'd_slot_miss_ms') + pb(c, 'acct_miss_ms') + pb(c, 'code_miss_ms'),
                storage_wait_slotmiss_ms=pb(c, 'slot_miss_ms') + pb(c, 'acct_miss_ms') + pb(c, 'code_miss_ms'),
                storage_wait_diag_ms=sum(pb(c, o + '_ms') for o in OUTC), exec_ms=pb(c, 'exec_ms'),
                new_payload_ms=pb(c, 'new_payload_ms'), slot_hit_us=S[c]['slot_hit_ms'] / h * 1000,
                slot_fast_us=mean('slot_fast'), slot_slow_us=mean('slot_slow'), slot_wait_us=mean('slot_wait'),
                plan_hits=sum(pb(c, kd + '_hit_plan') for kd in KINDS))


fmt_us = lambda v: '-' if v != v else f'{v:.2f}' if v < 1 else f'{v:.1f}'  # noqa: E731
print('\n== Table 3 (sec/7_eval.tex, tab:readcost), per block over the counted blocks. Storage wait = d_slot_miss_ms + '
      'acct_miss_ms + code_miss_ms (final252.py, final257.py); in brackets with slot_miss_ms instead (ana257.py), and the sum '
      'of the seven outcomes in the diag records')
for c in ROWS:
    t = t3(c)
    print(f'  {c}: slot reads {t["slot_reads"]:.1f}; hit rate {t["slot_hit_rate"]:.4f}; misses in memory {t["slot_fast"]:.2f}, from disk '
          f'{t["slot_slow"]:.2f}, in flight {t["slot_wait"]:.2f}; major faults: execution thread {t["engine_majflt"]:.1f}, all threads '
          f'{t["proc_majflt"]:.1f}; disk reads {t["proc_read_mb"]:.3f} MB; storage wait {t["storage_wait_ms"]:.3f} ms '
          f'({t["storage_wait_slotmiss_ms"]:.3f}; {t["storage_wait_diag_ms"]:.3f}); execution {t["exec_ms"]:.3f} ms')
    print(f'      mean per read (us): hit {fmt_us(t["slot_hit_us"])}, miss in memory {fmt_us(t["slot_fast_us"])}, from disk '
          f'{fmt_us(t["slot_slow_us"])}, in flight {fmt_us(t["slot_wait_us"])}; values from plan readers that the execution thread read '
          f'(account + slot + code hits) {t["plan_hits"]:.1f}')
with open(OUTP + '.csv', 'w', newline='') as f:
    keys = ['row', 'blocks', 'exec_ms'] + [f'{o}_ms' for o in ('slot_wait', 'slot_fast', 'slot_slow', 'acct_fast', 'acct_slow',
                                                             'code_fast', 'code_slow')] + ['hit_ms', 'engine_majflt',
                                                                                            'other_majflt', 'proc_read_mb']
    T3 = ['slot_reads', 'slot_hit_rate', 'slot_fast', 'slot_slow', 'slot_wait', 'proc_majflt', 'storage_wait_ms',
          'storage_wait_slotmiss_ms', 'storage_wait_diag_ms', 'new_payload_ms', 'slot_hit_us', 'slot_fast_us', 'slot_slow_us',
          'slot_wait_us', 'plan_hits']
    w = csv.writer(f)
    w.writerow(keys + T3)
    for c in ROWS:
        t = t3(c)
        w.writerow([c, int(S[c]['blocks']), round(pb(c, 'exec_ms'), 4)] +
                   [round(pb(c, f'{o}_ms'), 4) for o in ('slot_wait', 'slot_fast', 'slot_slow', 'acct_fast', 'acct_slow', 'code_fast',
                                                       'code_slow')] +
                   [round(sum(pb(c, f'{kd}_hit_ms') for kd in KINDS), 4), round(pb(c, 'engine_majflt'), 2),
                    round(pb(c, 'proc_majflt') - pb(c, 'engine_majflt'), 2), round(pb(c, 'proc_read_mb'), 4)] +
                   [round(t[k], 4) for k in T3])
    w.writerow([])
    w.writerow(list(rows_csv[0].keys()))
    for r in rows_csv:
        w.writerow(list(r.values()))
sys.stdout = sys.__stdout__
_txt.close()
