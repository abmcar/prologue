#!/usr/bin/env python3
"""Share of transactions whose pre-execution result the execution thread reuses, and share of pre-executions that are
second runs, under Prologue (recording processes, row H4, segments 0, 4, 8). Inputs: the `eap reuse block=` and
`eap ew block block=` lines of results/main/raw/e270rec-<k>/raw/rec<k>*.node.log, matched against that pass's schedule.
usage: python3 paper/scripts/reuse_redo_e270.py > paper/data/reuse_redo_e270.txt   (repository root)"""
import csv, re, os, sys
ROOT = 'results/main/raw'
import glob
KV = re.compile(r'(\w+)=(\S+)')
tot = {}; nblocks = 0; modes = {}; per_seg = []
def add(d, k, v): d[k] = d.get(k, 0) + v
for k in (0, 4, 8):
    d = f'{ROOT}/e270rec-{k}/raw'
    sched = set(); seen_r = set(); seen_b = set(); seg = {}
    # each pass file rec<k><p> runs every block under one row; its log is matched against its own schedule only
    for sf in sorted(glob.glob(f'{d}/rec*.schedule.csv')):
        mine = {int(r['block']) for r in csv.DictReader(open(sf)) if r['cfg'] == 'H4' and int(float(r['pos'])) >= 2}
        sched |= mine
        for line in open(sf.replace('.schedule.csv', '.node.log'), errors='replace'):
            if ' eap reuse block=' in line:
                f = dict(KV.findall(line)); b = int(f['block'])
                if b not in mine or b in seen_r: continue
                seen_r.add(b); add(modes, f['mode'], 1)
                for key in ('txs', 'stored', 'found', 'missing', 'valid', 'reused', 'checked', 'fee_only'):
                    add(tot, key, int(f[key])); add(seg, key, int(f[key]))
            elif ' eap ew block block=' in line:
                f = dict(KV.findall(line)); b = int(f['block'])
                if b not in mine or b in seen_b: continue
                seen_b.add(b)
                for key in ('redo_runs', 'redo_started', 'redo_skipped', 'queued'):
                    add(tot, key, int(f.get(key, 0))); add(seg, key, int(f.get(key, 0)))
    assert seen_r == sched, (k, len(sched), len(seen_r))
    add(tot, 'blocks_without_ew_line', len(sched - seen_b))  # blocks for which the pre-execution pool logged nothing
    nblocks += len(sched); per_seg.append((k, len(sched), seg))
t = tot
print(f'measured blocks {nblocks}; reuse modes {modes}')
print('totals', {k: t[k] for k in sorted(t)})
print(f"transactions per block {t['txs']/nblocks:.1f}")
print(f"found / txs {t['found']/t['txs']*100:.2f}%   valid / txs {t['valid']/t['txs']*100:.2f}%")
print(f"reused / txs {t['reused']/t['txs']*100:.2f}%   checked / txs {t['checked']/t['txs']*100:.2f}%   (reused+checked) / txs {(t['reused']+t['checked'])/t['txs']*100:.2f}%")
print(f"redo runs started / txs {t['redo_started']/t['txs']*100:.2f}%   redo queued / txs {t['redo_runs']/t['txs']*100:.2f}%   stale not redone / txs {t['redo_skipped']/t['txs']*100:.2f}%")
print(f"redo runs started / all pre-execution runs started {t['redo_started']/(t['queued']+t['redo_started'])*100:.2f}%   first runs queued / txs {t['queued']/t['txs']:.3f}   stored / txs {t['stored']/t['txs']:.3f}")
print('per segment: k blocks reused/txs redo_started/txs')
for k, n, s in per_seg:
    print(f"  {k} {n} {s['reused']/s['txs']*100:.2f}% {s['redo_started']/s['txs']*100:.2f}%")
