#!/usr/bin/env python3
"""the v1 analyzer's call records list the argument words in write order, so that a later
write wins on overlap. The program stores the free memory pointer (0x80 at 0x40) first, then builds
transferFrom(CD[4], CD[36], 0) in scratch memory at 0 and calls CD[68] with 100 bytes: the word at 0x24 overwrites the
first 4 bytes of the pointer word, so the pointer word must come before it (with ascending offsets it came after and
cleared the recipient's last 4 bytes; a1513fb2, block 26,264,501 transaction 39).
usage: python3 test_v1_write_order.py   (exit 0: passed)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evm_static as ES

sel = 0x23b872dd << 224
# the CALL: rsz 0, roff 0, asz 100, aoff 0, value 0, to CD[68], gas
code = bytes.fromhex('6080604052') + b'\x7f' + sel.to_bytes(32, 'big') + bytes.fromhex('600052') + \
    bytes.fromhex('6004356004526024356024526000604452') + bytes.fromhex('60006000606460006000604435' '5a' 'f1' '00')
a = ES.Analyzer(code); a.run()
calls = [c for c in a.calls if c[1] == 'CALL']
assert len(calls) == 1, calls
pc, name, to, argwords, argsize, cons = calls[0]
rels = [r for r, _ in argwords]
assert argsize == 100, argsize
assert rels == [64, 0, 4, 36, 68], rels
# applied in order, bytes 64..67 come from the word written at 0x24 (CD[36]), bytes 68..99 from the constant 0
buf = [None] * 100
for r, e in argwords:
    for i in range(32):
        if 0 <= r + i < 100: buf[r + i] = (r, e)
assert all(buf[i][0] == 36 for i in range(36, 68)), [buf[i][0] for i in range(60, 70)]
assert all(buf[i][0] == 68 for i in range(68, 100))
assert buf[0][0] == 0 and all(buf[i][0] == 4 for i in range(4, 36))
print('ok', rels)
