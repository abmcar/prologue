#!/usr/bin/env python3
"""Rotation schedule of the same-process node runs in runs of 3 blocks (EngineAccessPlan standard from 2026-10-27, Master
11:09 after EXP-189 README section 9; usage notes in scripts/schedule_runs3.md).

Each configuration runs for a segment of 3 consecutive blocks; segments follow a symmetric order of the configurations
(`U F A` gives segments U F A A F U, repeated). Blocks 2 and 3 of a segment follow a block of their own configuration,
as on a real node that runs one configuration throughout: the headline ratios use only them; block 1 of each segment is
reported apart (the carry-over estimate). A segment of 3 consecutive blocks covers the three residues of the block
number modulo 3, so no filler blocks are needed. With segments of exactly 3 blocks, positions 2 and 3 would always fall
on the same two residues; one segment of every pass through the order is therefore 4 blocks long (pass p lengthens its
segment number floor(p / 3) mod the order's length, so the configurations take it in turn), which shifts the alignment
by one block per pass, so over three passes the blocks after their own configuration cover all residues.

Optional target stratum (e.g. blocks carrying a rare transaction kind, known from the block contents before execution):
a segment holding a target block takes the next configuration of the targets' own symmetric order, the other segments
the next of the general order. Segments are anchored so that a target block does not open a segment: when the block
right after a segment would be a target, the segment is lengthened to take it in, so the target lies at a position
>= 2 and follows a block of its own configuration. Segment lengths are therefore 3 to 7 (mostly 3; 7 when a lengthened 4-block segment takes in 3
targets), the last segment of the range may be shorter; the self-check
reports their counts and the residue coverage.

Python use:   from schedule_runs3 import build, check
              rows = build(first, last, cfgs, targets=set(), order=None, target_order=None)
              rows: list of dicts (block, cfg, seg, pos, seglen, target, seg_kind)
CLI:          schedule_runs3.py FIRST LAST CFG [CFG ...] [--targets FILE (column block, or block,cls with --cls VALUE)]
                [--cls VALUE] [--out CSV] [--seglen N] [--no-shift]
              prints the self-check; with --out writes the schedule. --seglen N: segments of N blocks (default 3);
              --no-shift: no lengthened segment (all segments N blocks, the last of the range may be shorter; with N not
              a multiple of 3 the segment starts move through the residues by themselves). apply_sl.py (EXP-199 final runs, segments of 20 and 10)."""
import csv, sys, collections


def symmetric(cfgs):
    """Segment order U F A -> U F A A F U."""
    return list(cfgs) + list(reversed(cfgs))


def build(first, last, cfgs, targets=frozenset(), order=None, target_order=None, seglen=3, shift=True):
    """Segments of `seglen` (3) blocks over [first, last]. A segment whose blocks include a target block takes the next
    configuration of `target_order`; the others the next of `order` (both default to the symmetric order of `cfgs`).
    Phase shift (`shift`): in pass p through `order`, general segment number floor(p / 3) mod len(order) is one block
    longer.
    Anchoring: if the block right after a segment is a target, the segment is lengthened by one block, so that the
    target does not open the next segment (it then lies inside the lengthened segment, at a position >= 2, and the
    segment takes the targets' order). Repeated if the new next block is again a target (up to 3 extra blocks)."""
    order = order or symmetric(cfgs)
    target_order = target_order or symmetric(cfgs)
    rows, n, seg, k_gen, k_tgt = [], first, 0, 0, 0
    while n <= last:
        # the default length; one more for the general segment that ends a pass through the order
        # (passes 3q, 3q+1 and 3q+2 lengthen their segment number q mod len(order): the three shifts of one segment cover
        # the three residues, and every configuration takes the extra blocks in turn)
        length = seglen + (1 if shift and not any(b in targets for b in range(n, n + seglen)) and k_gen % len(order) == (k_gen // len(order) // 3) % len(order) else 0)
        end = min(n + length - 1, last)
        while end + 1 <= last and (end + 1) in targets and end - n + 1 < length + 3:
            end += 1
        blocks = list(range(n, end + 1))
        has_target = any(b in targets for b in blocks)
        if has_target:
            cfg = target_order[k_tgt % len(target_order)]; k_tgt += 1
        else:
            cfg = order[k_gen % len(order)]; k_gen += 1
        for i, b in enumerate(blocks):
            rows.append(dict(block=b, cfg=cfg, seg=seg, pos=i + 1, seglen=len(blocks), target=int(b in targets),
                             seg_kind='target' if has_target else 'general'))
        seg += 1
        n = end + 1
    return rows


def check(rows, cfgs):
    """Self-check: blocks per configuration, blocks at positions >= 2, target blocks at positions >= 2 and at position 1,
    residue coverage (block mod 3) of all blocks and of positions >= 2, segment lengths. Returns (ok, lines)."""
    out, ok = [], True
    seglens = collections.Counter()
    seen = set()
    for r in rows:
        if r['seg'] not in seen:
            seen.add(r['seg']); seglens[r['seglen']] += 1
    out.append(f"blocks {len(rows)} ({rows[0]['block']}-{rows[-1]['block']}), segments {len(seen)}, lengths {dict(sorted(seglens.items()))}")
    for c in cfgs:
        rs = [r for r in rows if r['cfg'] == c]
        own = [r for r in rs if r['pos'] >= 2]
        tg = [r for r in rs if r['target']]
        res_all = collections.Counter(r['block'] % 3 for r in rs)
        res_own = collections.Counter(r['block'] % 3 for r in own)
        out.append(f"{c}: blocks {len(rs)}, after itself {len(own)}, targets {len(tg)} (after itself {sum(r['pos'] >= 2 for r in tg)}, at position 1 "
                   f"{sum(r['pos'] == 1 for r in tg)}), residues all {[res_all[i] for i in range(3)]}, after itself {[res_own[i] for i in range(3)]}")
        if not rs:
            ok = False
    tg1 = sum(1 for r in rows if r['target'] and r['pos'] == 1)
    if tg1:
        out.append(f"target blocks at position 1: {tg1} (the first block of the range, or targets packed closer than the anchoring allows)")
    blocks = [r['block'] for r in rows]
    if blocks != list(range(blocks[0], blocks[-1] + 1)):
        ok = False; out.append('blocks are not contiguous')
    return ok, out


def main():
    a = sys.argv[1:]
    opt = {}
    shift = '--no-shift' not in a
    a = [x for x in a if x != '--no-shift']
    for k in ('--targets', '--cls', '--out', '--seglen'):
        if k in a:
            i = a.index(k); opt[k] = a[i + 1]; del a[i:i + 2]
    first, last, cfgs = int(a[0]), int(a[1]), a[2:]
    targets = set()
    if '--targets' in opt:
        for r in csv.DictReader(open(opt['--targets'])):
            if '--cls' not in opt or opt['--cls'] in r.values():
                targets.add(int(r['block']))
        targets = {b for b in targets if first <= b <= last}
    rows = build(first, last, cfgs, targets, seglen=int(opt.get('--seglen', 3)), shift=shift)
    ok, lines = check(rows, cfgs)
    print('\n'.join(lines))
    if '--out' in opt:
        with open(opt['--out'], 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
