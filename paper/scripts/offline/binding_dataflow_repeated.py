#!/usr/bin/env python3
"""Restructured paper (2026-11-06): the "in repeated inner calls" row of Table 1 with the plan-independent class of
scripts/binding_dataflow.py. Writes items in the format of cls234.py (class '1' = binds at call start by the
labels alone, frame seq of the first access from the export's reads216.tsv) and runs scripts/cls2ub234.py on them
unchanged (frame of the read at index >= 4 of its (selector, calldata length) group among the transaction's inner calls),
then scales the two block classes to the population as look234w.py does.
Inputs: as binding_dataflow.py, plus export216/ and export234/ (reads216.tsv, frames216.jsonl).
usage: binding_dataflow_repeated.py TMPDIR OUTDIR -> OUTDIR/binding_dataflow_repeated_{general,mint}.csv, .txt
Run (paper copy): labq run -k heavy -l prologue-paper-binding-repeated -m 6 -- python3 scripts/binding_dataflow_repeated.py <tmp> data
"""
import csv, glob, gzip, json, os, subprocess, sys

X = os.environ.get("TRACE_ROOT", "traces")   # per-read traces and exports, not in the repository
WHY = sorted(glob.glob(f'{X}/key-determination-time/derived/why234_*.jsonl'))
B3 = f'{X}/prediction-vs-official/results/b3'
EXP = {'general': f'{X}/plan-coverage-gaps/export216', 'mint': f'{X}/key-determination-time/export234'}
UB = f'{X}/key-determination-time/scripts/cls2ub234.py'
TMP, OUT = sys.argv[1], sys.argv[2]
os.makedirs(TMP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
L_DUR, L_STOR, L_RET = 32 | 64 | 128 | 256 | 512 | 1024, 32 | 64, 128


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
SEQ = {}
for c, e in EXP.items():
    for r in csv.DictReader(open(f'{e}/reads216.tsv'), delimiter='\t'):
        b = int(r['block'])
        if kept.get(b) == c:
            SEQ[(b, int(r['tx']), na(r['addr']), nk(r['key']))] = (int(r['seq']), r['op'])
print('reads with seq', len(SEQ), flush=True)
fo = {c: gzip.open(f'{TMP}/items_{c}.tsv.gz', 'wt') for c in ('general', 'mint')}
for f in fo.values():
    f.write('block\ttx\taddr\tkey\top\tseq\tbits\tclass\tw_r_ns\n')
n = 0; noseq = 0; seqdiff = 0
for fn in WHY:
    for l in open(fn):
        if '"kind":"s"' not in l:
            continue
        j = json.loads(l)
        if j.get('kind') != 's':
            continue
        c = kept.get(j['block'])
        if c is None:
            continue
        k = (j['block'], j['tx'], na(j['a']), nk(j['k']))
        s = SEQ.get(k)
        if s is None:
            noseq += 1; continue
        if s[0] != j.get('seq'):
            seqdiff += 1
        kl = j.get('kl', 0)
        cl = '1' if kl & L_DUR == 0 else ('3b' if kl & L_STOR else ('3c' if kl & L_RET else 'O'))
        fo[c].write(f'{k[0]}\t{k[1]}\t{k[2]}\t{k[3]}\t{s[1]}\t{s[0]}\t0\t{cl}\t{W.get(k, 0.0):.0f}\n'); n += 1
for f in fo.values():
    f.close()
print('items', n, 'without an export read', noseq, 'seq differing from the replay record', seqdiff, flush=True)
for c, e in EXP.items():
    subprocess.run([sys.executable, UB, e, f'{TMP}/items_{c}.tsv.gz', f'{OUT}/binding_dataflow_repeated_{c}.csv'], check=True)
# population scaling as look234w.py
C = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(f'{X}/eap-stepwise/results/blocks_class_zk_a1.csv'))}
bl = [b for b in C if 26263606 <= b <= 26268604]
N = {'mint': sum(1 for b in bl if C[b] == 'mint')}; N['general'] = len(bl) - N['mint']
nn = {c: sum(1 for v in kept.values() if v == c) for c in ('general', 'mint')}
U = {c: {r['scope']: r for r in csv.DictReader(open(f'{OUT}/binding_dataflow_repeated_{c}.csv'))} for c in ('general', 'mint')}
lines = [f'items {n}, without an export read {noseq}, seq differing {seqdiff}; population {N}, samples {nn}']
for scope in ('all', 'miss_n', 'miss_wr_ns'):
    w = {c: N[c] / nn[c] for c in N}
    amt = {c: float(U[c][scope]['amount']) for c in N}
    for key in ('class12_share', 'class12_in_late_frame_share'):
        v = {c: float(U[c][scope][key]) for c in N}
        v['all'] = sum(w[c] * amt[c] * v[c] for c in N) / sum(w[c] * amt[c] for c in N)
        lines.append(f'{scope:10s} {key.replace("class12", "labels_start"):40s} ' + '  '.join(f'{c} {100 * v[c]:6.2f}%' for c in ('general', 'mint', 'all')))
open(f'{OUT}/binding_dataflow_repeated.txt', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
