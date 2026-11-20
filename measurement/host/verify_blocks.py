#!/usr/bin/python3
"""Prologue server: check a block pool (files <number>.json from engine-replay/fetch.py) over FIRST..LAST: every file is
there, the payload's block_number equals the file name, and each payload's parent_hash is the block_hash of the
previous one. Prints the counts and the first problems; exit 1 on any problem. Reads downloaded files: run with python3 -I.
usage: python3 -I verify_blocks.py POOL FIRST LAST"""
import json, os, sys

pool, first, last = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
missing, wrong, broken = [], [], []
prev = None
for n in range(first, last + 1):
    try:
        p = json.load(open(os.path.join(pool, f'{n}.json')))['payload']
    except FileNotFoundError:
        missing.append(n); prev = None; continue
    if int(p['block_number']) != n:
        wrong.append(n)
    if prev is not None and p['parent_hash'] != prev:
        broken.append(n)
    prev = p['block_hash']
print(f'{pool} {first}-{last}: {last - first + 1} blocks, missing {len(missing)} {missing[:5]}, '
      f'number differs from name {len(wrong)} {wrong[:5]}, parent hash not the previous block {len(broken)} {broken[:5]}')
sys.exit(1 if missing or wrong or broken else 0)
