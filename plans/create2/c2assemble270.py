#!/usr/bin/python3
"""Assemble the node's CREATE2 record directory from one or more record directories (which must not overlap), with a
MANIFEST: "files N" and "content_sha256 H", H = sha256 of the sorted lines "<name> <sha256 of the file>\n".
usage: python3 c2assemble270.py OUT RECORD_DIR [RECORD_DIR ...]"""
import hashlib, json, os, shutil, sys
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=False)
assert len(sys.argv) > 2, 'usage: c2assemble270.py OUT RECORD_DIR [RECORD_DIR ...]'
sets = sys.argv[2:]
seen = set()
for d in sets:
    names = sorted(n for n in os.listdir(d) if n.endswith('.json'))
    assert not seen & set(names), 'overlap'
    seen |= set(names)
    withrec = 0
    for n in names:
        shutil.copy2(f'{d}/{n}', f'{OUT}/{n}')
        j = json.load(open(f'{d}/{n}'))
        withrec += bool(j.get('records'))
    print(f'{d}: {len(names)} files, {withrec} with records')
names = sorted(seen)
h = hashlib.sha256(''.join(f'{n} {hashlib.sha256(open(f"{OUT}/{n}", "rb").read()).hexdigest()}\n' for n in names).encode()).hexdigest()
open(f'{OUT}/MANIFEST', 'w').write(f'files {len(names)}\ncontent_sha256 {h}\n')
print(f'{OUT}: files {len(names)}, content_sha256 {h}')
