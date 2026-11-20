#!/usr/bin/python3
"""EXP-199 screening rounds (Master 11-01, the researcher's request for quicker rounds): two passes, every block measured
under two of the round's NC configurations (3 or 4), so that every pair of configurations shares blocks (a balanced
incomplete block design with block size 2; the comparison then rests on log(exec) = block + configuration + pass, ana199
--passadj and its model section).
Pass 0 is the standard rotation of scripts/schedule_runs3.py over CF (unchanged: segments of 3-4 blocks, the symmetric
order). Pass 1 has the same segments and positions; the configuration of segment s is pass 0's shifted by
d = 1 + (cycle mod (NC - 1)) places in CF, cycle = s // (2 NC) (one pass through the symmetric order). Within a cycle the
shift is a bijection, so every configuration has the same number of segments in pass 1 as in pass 0; over NC - 1
consecutive cycles every unordered pair of configurations shares the same number of segments, half of them in each order
(NC = 4: shifts 1 and 3 give the four neighbouring pairs, each twice per cycle and once in each order; shift 2 the two
opposite pairs, four times; NC = 3: shifts 1 and 2 give the three pairs, twice each). A last incomplete period leaves a
small imbalance, which the check reports.
usage: pairsched199.py derive PASS0.csv CFG [CFG ...] --out PASS1.csv
       pairsched199.py check LABEL CFG [CFG ...]     (raw/<LABEL>0.schedule.csv and raw/<LABEL>1.schedule.csv; exit 1 if
                                                      the passes differ in blocks, segments or positions, or a block gets
                                                      the same configuration twice)"""
import csv, os, sys
from collections import Counter

CLASS = os.environ['CLASSFILE']   # Prologue server copy: scripts/server/apply_server.py


def shift(seg, nc):
    return 1 + (seg // (2 * nc)) % (nc - 1)


def derive(rows, cf):
    nc = len(cf)
    out = []
    for r in rows:
        if r['seg_kind'] != 'general':
            raise SystemExit(f"segment {r['seg']} is a target segment: the pair design covers general segments only")
        r1 = dict(r)
        r1['cfg'] = cf[(cf.index(r['cfg']) + shift(int(r['seg']), nc)) % nc]
        out.append(r1)
    return out


def main():
    a = sys.argv[1:]
    if a[0] == 'derive':
        i = a.index('--out'); out = a[i + 1]; del a[i:i + 2]
        p0, cf = a[1], a[2:]
        if len(cf) < 3 or len(set(cf)) != len(cf):
            raise SystemExit('the pair design needs 3 or more distinct configurations')
        rows = list(csv.DictReader(open(p0)))
        if {r['cfg'] for r in rows} != set(cf):
            raise SystemExit(f'pass 0 uses {sorted({r["cfg"] for r in rows})}, not {sorted(cf)}')
        r1 = derive(rows, cf)
        with open(out, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(r1[0])); w.writeheader(); w.writerows(r1)
        print(f'pass 1 derived from {p0}: {len(r1)} blocks, {len({r["seg"] for r in r1})} segments')
        return
    if a[0] != 'check':
        raise SystemExit(__doc__)
    L, cf = a[1], a[2:]
    mint = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(CLASS))}
    S = [{int(r['block']): r for r in csv.DictReader(open(f'raw/{L}{p}.schedule.csv'))} for p in (0, 1)]
    bad = []
    if set(S[0]) != set(S[1]):
        bad.append('the passes cover different blocks')
    same = [b for b in S[0] if b in S[1] and S[0][b]['cfg'] == S[1][b]['cfg']]
    pos = [b for b in S[0] if b in S[1] and (S[0][b]['pos'], S[0][b]['seg']) != (S[1][b]['pos'], S[1][b]['seg'])]
    if same:
        bad.append(f'{len(same)} blocks with the same configuration in both passes')
    if pos:
        bad.append(f'{len(pos)} blocks at a different segment or position')
    bl = sorted(S[0])
    print(f'pair design: {len(bl)} blocks ({bl[0]}-{bl[-1]}), {len({S[0][b]["seg"] for b in bl})} segments, configurations {cf}')
    for p in (0, 1):
        c = Counter(S[p][b]['cfg'] for b in bl)
        print(f'  pass {p}: blocks per configuration ' + ', '.join(f'{k} {c[k]}' for k in cf))
    sel = {'all': bl, 'position >= 2': [b for b in bl if int(S[0][b]['pos']) >= 2],
           'general, position >= 2': [b for b in bl if int(S[0][b]['pos']) >= 2 and mint.get(b) == 'nomint'],
           'mint, position >= 2': [b for b in bl if int(S[0][b]['pos']) >= 2 and mint.get(b) == 'mint']}
    pairs = [(cf[i], cf[j]) for i in range(len(cf)) for j in range(i + 1, len(cf))]
    print(f'  blocks per pair of configurations (in parentheses: the first of the pair in pass 0 / in pass 1)')
    for name, bs in sel.items():
        un, od = Counter(), Counter()
        for b in bs:
            x, y = S[0][b]['cfg'], S[1][b]['cfg']
            un[frozenset((x, y))] += 1; od[(x, y)] += 1
        print(f'  {name:24s} ' + '; '.join(f'{x}+{y} {un[frozenset((x, y))]} ({od[(x, y)]}/{od[(y, x)]})' for x, y in pairs))
    for m in bad:
        print('  FAILED: ' + m)
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
