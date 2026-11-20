#!/usr/bin/env python3
"""The codes of CODES_TSV (header; columns codehash, bytecode hex) that BASE_LIB has no .eapf file for ->
WORK/codes/<hash>.hex, WORK/jobs<i>.json (NSH shards, round robin over the sorted hashes) and WORK/missing.txt.
Codes with an empty bytecode column are listed in WORK/no_bytecode.txt and not generated.
usage: prep222.py CODES_TSV BASE_LIB WORK NSH"""
import csv, json, os, sys
csv.field_size_limit(1 << 30)
src, base, work, nsh = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
have = {n[:-5].lower().removeprefix('0x') for n in os.listdir(base) if n.endswith('.eapf')}
os.makedirs(os.path.join(work, 'codes'), exist_ok=True)
miss = []; nob = []; n = 0
with open(src) as fh:
    fh.readline()
    for line in fh:
        h, bc = line.rstrip('\n').split('\t', 1)
        h = h.strip().lower().removeprefix('0x'); bc = bc.strip().lower().removeprefix('0x'); n += 1
        if h in have: continue
        if not bc: nob.append(h); continue
        p = os.path.join(work, 'codes', h + '.hex')
        if not os.path.exists(p):
            open(p + '.tmp', 'w').write(bc); os.replace(p + '.tmp', p)
        miss.append(h)
miss.sort()
open(os.path.join(work, 'missing.txt'), 'w').write(''.join(h + '\n' for h in miss))
open(os.path.join(work, 'no_bytecode.txt'), 'w').write(''.join(h + '\n' for h in nob))
for i in range(nsh):
    json.dump(miss[i::nsh], open(os.path.join(work, f'jobs{i}.json'), 'w'))
print(json.dumps({'codes': n, 'in_base': n - len(miss) - len(nob), 'missing': len(miss), 'no_bytecode': len(nob), 'shards': nsh}))
