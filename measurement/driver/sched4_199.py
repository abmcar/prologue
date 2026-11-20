#!/usr/bin/python3
"""EXP-199 final run (Master 11-02): the four-pass schedule of the eight ablation rows.

Every measured block runs four configurations, one per pass: the two base rows (AB1, AB5) on every block, and one of
three groups of two rows ({AB4, AB6}, {AB2, AB3}, {AB7, AB8}), so that each of the six rows runs on about a third of the
blocks and the two-by-two rows (AB1, AB4, AB5, AB6) share their blocks. As in every round since 10-27
(scripts/schedule_runs3.py, after EXP-189 section 9), a configuration runs for a segment of consecutive blocks and only
positions >= 2 enter the headline ratios (they follow a block of their own configuration); the four passes share the
segments, so a block has the same position in every pass.

Construction (seeded, deterministic):
  - segments of 3 blocks; the last segment of every cycle of 12 segments is 4 blocks long, so a cycle is 37 blocks and
    the next starts one residue (block number modulo 3) later: over three cycles positions >= 2 cover the three residues
    equally (the 4-block segment always in the same place: moving it within the cycle with the cycle number, as
    schedule_runs3 does, ties its place to the cycle's starting residue and left residue 0 about 12% ahead);
  - groups: each run of 3 segments takes the three groups in a random order (they interleave along the range);
  - shift k of a segment (0-3): within a cycle each group's 4 segments take the shifts 0, 1, 2, 3 in a random order,
    redrawn until no two consecutive segments have the same shift;
  - pass p runs Q[(p + k) mod 4] on the segment, Q = (base 1, base 2, group row 1, group row 2).
Consequences: every configuration has the same number of segments in each pass (within a complete cycle); two
consecutive segments of a pass never have the same configuration (equal shifts are excluded, and different groups have
different rows); the configuration of the segment before is spread over the others at random. The last, incomplete
cycle leaves a small imbalance, which the check reports.

usage: sched4_199.py build FIRST LAST --base "AB1 AB5" --groups "AB4,AB6 AB2,AB3 AB7,AB8" [--seed 199] --out PREFIX
         writes PREFIX0.schedule.csv .. PREFIX3.schedule.csv and prints the check (exit 1 if it fails)
       sched4_199.py check PREFIX --base ... --groups ...   (the check of written files)"""
import argparse, csv, os, random, sys
from collections import Counter, defaultdict

CLASS = os.environ['CLASSFILE']   # Prologue server copy: scripts/server/apply_server.py
FIELDS = ['block', 'cfg', 'seg', 'pos', 'seglen', 'target', 'seg_kind', 'group', 'shift']
CYCLE = 12


def segments(first, last):
    """(start, length) of every segment: 3 blocks, the last of each cycle of 12 4 blocks; the last may be shorter."""
    out, b, s = [], first, 0
    while b <= last:
        c, i = divmod(s, CYCLE)
        n = 4 if i == CYCLE - 1 else 3
        n = min(n, last - b + 1)
        out.append((b, n))
        b += n
        s += 1
    return out


def assign(nseg, ngroups, rng):
    """Group and shift of every segment (see the module doc)."""
    groups, shifts = [], []
    for c0 in range(0, nseg, CYCLE):
        n = min(CYCLE, nseg - c0)
        for _ in range(10000):
            g = []
            for _t in range(CYCLE // ngroups):
                g += rng.sample(range(ngroups), ngroups)
            perm = {x: rng.sample(range(4), 4) for x in range(ngroups)}
            used = defaultdict(int)
            k = []
            for x in g:
                k.append(perm[x][used[x]])
                used[x] += 1
            g, k = g[:n], k[:n]
            prev = shifts[-1] if shifts else None
            if all(k[i] != k[i - 1] for i in range(1, n)) and (prev is None or k[0] != prev):
                break
        else:
            raise SystemExit(f'no shift order found for cycle at segment {c0}')
        groups += g
        shifts += k
    return groups, shifts


def build(first, last, base, groups, seed):
    rng = random.Random(seed)
    segs = segments(first, last)
    g, k = assign(len(segs), len(groups), rng)
    passes = [[] for _ in range(4)]
    for s, ((b0, n), gi, ki) in enumerate(zip(segs, g, k)):
        q = list(base) + list(groups[gi])
        for p in range(4):
            for j in range(n):
                passes[p].append({'block': b0 + j, 'cfg': q[(p + ki) % 4], 'seg': s, 'pos': j + 1, 'seglen': n, 'target': 0,
                                  'seg_kind': 'general', 'group': gi, 'shift': ki})
    return passes


def check(passes, base, groups):
    ok, out = True, []
    cfgs = list(base) + [c for gr in groups for c in gr]
    mint = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(CLASS))}
    blocks = [r['block'] for r in passes[0]]
    if blocks != list(range(blocks[0], blocks[-1] + 1)):
        ok = False; out.append('FAIL blocks are not contiguous')
    for p in range(1, 4):
        if [(r['block'], r['seg'], r['pos']) for r in passes[p]] != [(r['block'], r['seg'], r['pos']) for r in passes[0]]:
            ok = False; out.append(f'FAIL pass {p}: blocks, segments or positions differ from pass 0')
    # every block: the two base rows and one group, four different configurations
    bad = 0
    gsets = [set(gr) for gr in groups]
    for i in range(len(blocks)):
        cs = [passes[p][i]['cfg'] for p in range(4)]
        if len(set(cs)) != 4 or not set(base) <= set(cs) or set(cs) - set(base) not in gsets:
            bad += 1
    out.append(f'blocks {len(blocks)} ({blocks[0]}-{blocks[-1]}); blocks without the two base rows and one group: {bad}')
    ok &= bad == 0
    seglens = Counter(r['seglen'] for r in passes[0] if r['pos'] == 1)
    out.append(f'segments {len(seglens) and sum(seglens.values())}, lengths {dict(sorted(seglens.items()))}')
    # per pass and configuration: blocks, blocks at positions >= 2
    tab = {c: [sum(r['cfg'] == c for r in passes[p]) for p in range(4)] for c in cfgs}
    tab2 = {c: [sum(r['cfg'] == c and r['pos'] >= 2 for r in passes[p]) for p in range(4)] for c in cfgs}
    for c in cfgs:
        own = [r for p in range(4) for r in passes[p] if r['cfg'] == c and r['pos'] >= 2]
        res = Counter(r['block'] % 3 for r in own)
        nm = sum(mint.get(r['block']) == 'mint' for r in own)
        spread = max(tab[c]) / max(1, min(tab[c]))
        out.append(f'{c}: blocks per pass {tab[c]} (max/min {spread:.3f}), positions >= 2 per pass {tab2[c]}, total {sum(tab2[c])} '
                   f'(batch mint {nm}, general {len(own) - nm}), residues of positions >= 2 {[res[i] for i in range(3)]}')
        ok &= min(tab[c]) > 0 and spread <= 1.05
    # consecutive segments of a pass with the same configuration; the configuration of the segment before
    same = 0
    pred = defaultdict(Counter)
    for p in range(4):
        first = [r for r in passes[p] if r['pos'] == 1]
        for a, b in zip(first, first[1:]):
            same += a['cfg'] == b['cfg']
            pred[b['cfg']][a['cfg']] += 1
    out.append(f'consecutive segments with the same configuration: {same}')
    ok &= same == 0
    for c in cfgs:
        tot = sum(pred[c].values())
        out.append(f'  segment before {c} ({tot}): ' + ', '.join(f'{d} {pred[c][d] / tot:.2f}' for d in cfgs if pred[c][d]))
    gs = Counter(r['group'] for r in passes[0] if r['pos'] == 1)
    out.append(f'segments per group {dict(sorted(gs.items()))}')
    out.append('check ' + ('passed' if ok else 'FAILED'))
    return ok, out


def write(passes, prefix):
    for p, rows in enumerate(passes):
        with open(f'{prefix}{p}.schedule.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)


def read(prefix):
    out = []
    for p in range(4):
        rows = []
        for r in csv.DictReader(open(f'{prefix}{p}.schedule.csv')):
            rows.append({k: (int(v) if k in ('block', 'seg', 'pos', 'seglen', 'target', 'group', 'shift') else v) for k, v in r.items()})
        out.append(rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['build', 'check'])
    ap.add_argument('args', nargs='+')
    ap.add_argument('--base', required=True)
    ap.add_argument('--groups', required=True)
    ap.add_argument('--seed', type=int, default=199)
    ap.add_argument('--out')
    a = ap.parse_args()
    base = a.base.split()
    groups = [tuple(g.split(',')) for g in a.groups.split()]
    if len(base) != 2 or any(len(g) != 2 for g in groups) or len(set(base) | {c for g in groups for c in g}) != 2 + 2 * len(groups):
        raise SystemExit('two base rows and groups of two different rows required')
    if a.mode == 'build':
        first, last = int(a.args[0]), int(a.args[1])
        passes = build(first, last, base, groups, a.seed)
        ok, lines = check(passes, base, groups)
        print('\n'.join(lines))
        if not a.out:
            raise SystemExit('--out PREFIX required')
        write(passes, a.out)
    else:
        ok, lines = check(read(a.args[0]), base, groups)
        print('\n'.join(lines))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
