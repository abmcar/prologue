#!/usr/bin/env python3
"""What becomes of the values that Prologue's reader threads read (recording processes, row H4 = Prologue, 2,700
blocks of segments 0, 4, 8): where the reads were issued, how many the execution thread used, and the reuse rate from
the node's `eap reuse` log lines, each pass matched against its own schedule.
usage: python3 paper/scripts/reader_reads_split_e270.py > paper/data/reader_reads_split_e270.txt   (repository root)"""
import csv, glob, re
from collections import defaultdict
E = 'results/main/raw'
CLS = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open('measurement/block_classes.csv'))}
PH = [f'{t}_hit_{s}' for t in ('acct', 'slot', 'code') for s in ('eap', 'cs0', 'cs1')]
NEED = PH + ['eap_reads', 'eap_dup', 'eap_reads_tx', 'eap_reads_pw', 'slot_hit_pw', 'd_lk_pw', 'd_lk_reader', 'proc_read_mb', 'txs', 'slot_miss']
ROWS = ('H0n', 'H0', 'H3', 'H4', 'H5')
def f(r, k):
    v = r.get(k) or ''
    return 0.0 if v in ('', 'nan') else float(v)
R = defaultdict(dict)
for k in (0, 4, 8):
    for fn in glob.glob(f'{E}/e270rec-{k}/results/blocks_rec*.csv'):
        for r in csv.DictReader(open(fn)):
            if r['role'] == 'measured' and int(float(r['pos'])) >= 2 and r['cfg'] in ROWS:
                R[(k, int(r['block']))][r['cfg']] = {c: r.get(c) for c in NEED}
keys = sorted(x for x in R if all(c in R[x] for c in ROWS))
KV = re.compile(r'(\w+)=(\S+)')
REU = {}
for k in (0, 4, 8):
    # each pass file runs every block under one row: a pass's log is matched against that pass's schedule only
    for sf in glob.glob(f'{E}/e270rec-{k}/raw/rec*.schedule.csv'):
        g4 = {int(r['block']) for r in csv.DictReader(open(sf)) if r['cfg'] == 'H4'}
        for line in open(sf.replace('.schedule.csv', '.node.log'), errors='replace'):
            if ' eap reuse block=' in line:
                q = dict(KV.findall(line)); b = int(q['block'])
                if b in g4 and q['mode'] == '2' and (k, b) not in REU:
                    REU[(k, b)] = (int(q['reused']), int(q['txs']))
sel = {'all': keys, 'reg': [x for x in keys if CLS.get(x[1]) == 'nomint'], 'mint': [x for x in keys if CLS.get(x[1]) == 'mint']}
S = lambda ks, c, k: sum(f(R[x][c], k) for x in ks)   # noqa: E731
print(f'recorder process, row G4: {len(keys)} blocks (regular {len(sel["reg"])}, batch-mint {len(sel["mint"])})')
for g, ks in sel.items():
    m = len(ks); rd = S(ks, 'H4', 'eap_reads')
    used = sum(S(ks, 'H4', k) for k in PH)
    by = {t: sum(S(ks, 'H4', f'{t}_hit_{s}') for s in ('eap', 'cs0', 'cs1')) for t in ('acct', 'slot', 'code')}
    tx, pw = S(ks, 'H4', 'eap_reads_tx'), S(ks, 'H4', 'eap_reads_pw')
    ru = [REU[x] for x in ks if x in REU]
    print(f'{g:4s} ({m} blocks), per block:')
    print(f'  reader reads {rd / m:.1f} = issued at transaction arrival {tx / m:.1f} ({tx / rd:.1%}) + at call starts on pre-execution threads {pw / m:.1f} ({pw / rd:.1%}) + other sources {(rd - tx - pw) / m:.1f} ({(rd - tx - pw) / rd:.1%})')
    print(f'  read by the execution thread itself {used / m:.1f} ({used / rd:.1%}): accounts {by["acct"] / m:.1f}, slots {by["slot"] / m:.1f}, code {by["code"] / m:.1f}')
    print(f'  not read by the execution thread {(rd - used) / m:.1f} ({(rd - used) / rd:.1%}); not divisible further (see the docstring)')
    print(f'  check: slot_hit_pw - d_lk_pw = {(S(ks, "H4", "slot_hit_pw") - S(ks, "H4", "d_lk_pw")) / m:.2f}; d_lk_reader {S(ks, "H4", "d_lk_reader") / m:.1f} (slot hits on reader-loaded values, EAP_DIAG)')
    print(f'  transactions {S(ks, "H4", "txs") / m:.1f}; pre-executed result committed for {sum(a for a, _ in ru) / sum(b for _, b in ru):.1%} of them ({len(ru)} blocks with an `eap reuse` line)')
    print(f'  disk reads MB per block: G0 {S(ks, "H0", "proc_read_mb") / m:.2f}, G4 {S(ks, "H4", "proc_read_mb") / m:.2f}')
