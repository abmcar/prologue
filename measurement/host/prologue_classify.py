#!/usr/bin/env python3
"""Pre-execution class of every block FROM..TO from a blocks pool (X-028, Master 11-04 16:1x: the measured segment of the
server runs). Copy of EXP-172 scripts/classes172.py (batch-mint class) and EXP-193 scripts/classify193.py (proof-entry
class and the class file), merged and changed only so that the pool, the output and the entry list are arguments and
blocks are read by several processes. The rules are unchanged:
  - xen_txs: transactions to XEN 0x0de8bf93 with selector b1ae2ed1 or c2580804; minter_txs: transactions to any other
    EXP-145 entry (raw/minters.txt plus the 6 salt-template entries kept in classes172.py), or to XEN with another
    selector; usdt_txs: USDT distributor 0x7ec8a30a transfers (a9059cbb);
  - cls: A xen >= 2, B xen == 1, C usdt >= 1, D other; cls_mint: 'mint' when xen_txs + minter_txs >= 1, else 'nomint';
  - cls_zk: 'zk' when a raw transaction contains the RLP recipient 0x94 + 82c89d6b...ba1f (classify193.py), zk_n the count.
One extra column, for information only: extra_txs, transactions to the entries EXP-246 found outside the list
(results/extra_entries246.txt), and cls_mint_x, the class with them (EXP-246's second series).
Every pool file must exist and carry its own block number (payload.block_number); missing or wrong files are listed and
the exit code is 1.
Reads downloaded files: run with python3 -I.
usage: [MINTERS=<EXP-145 raw/minters.txt>] [EXTRA=<EXP-246 extra_entries246.txt>] python3 -I prologue_classify.py POOL FROM TO OUT_CSV [JOBS]"""
import csv, json, os, sys
from multiprocessing import Pool

POOL, FROM, TO, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
JOBS = int(sys.argv[5]) if len(sys.argv) > 5 else 8
X = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'classify_inputs')
XEN = '0x0de8bf93da2f7eecb3d9169422413a9bef4ef628'; XEN_SELS = {'b1ae2ed1', 'c2580804'}
USDT = ('0x7ec8a30a34b86927dc77b302603d1d53e640bef7', 'a9059cbb')
MINTERS = os.environ.get('MINTERS', os.path.join(X, 'minters.txt'))   # MINTERS=: a copy where raw/ is absent
ENTRIES = {l.strip().lower() for l in open(MINTERS) if l.strip().startswith('0x')}
ENTRIES |= {'0x0a252663dbcc0b073063d6420a40319e438cfa59', '0x0000000000771a79d0fc7f3b7fe270eb4498f20b', '0xdb2c64366d471f025d6a86544ce39159c22361c6',
            '0x6ef3ef48e48cb00a87afe6132d920c498e34a229', '0x2f848984984d6c3c036174ce627703edaf780479', '0x0a9077aa8a6e3b6016e9936ae3541a6bf5740eba'}
EXTRA_F = os.environ.get('EXTRA', os.path.join(X, 'extra_entries.txt'))
EXTRA = {l.strip().lower() for l in open(EXTRA_F) if l.strip().startswith('0x')}
ZKPAT = '9482c89d6ba0881a8b9e804aadfa0955d9acf7ba1f'
POS = {0: (3, 5), 1: (4, 6), 2: (5, 7), 3: (5, 7), 4: (5, 7)}   # (to, input) item positions per transaction type (classes172.py)


def rlp(b, i=0):
    p = b[i]
    if p < 0x80: return b[i:i + 1], i + 1
    if p < 0xb8: l = p - 0x80; return b[i + 1:i + 1 + l], i + 1 + l
    if p < 0xc0: ll = p - 0xb7; l = int.from_bytes(b[i + 1:i + 1 + ll], 'big'); return b[i + 1 + ll:i + 1 + ll + l], i + 1 + ll + l
    if p < 0xf8: l = p - 0xc0; j = i + 1; end = j + l
    else: ll = p - 0xf7; l = int.from_bytes(b[i + 1:i + 1 + ll], 'big'); j = i + 1 + ll; end = j + l
    items = []
    while j < end:
        it, j = rlp(b, j); items.append(it)
    return items, end


def one(n):
    p = os.path.join(POOL, f'{n}.json')
    try:
        d = json.load(open(p))['payload']
    except Exception:
        return n, 'missing', None
    if int(d['block_number']) != n:
        return n, 'wrong', None
    xen = mint = usdt = extra = zk = 0
    for tx in d['transactions']:
        zk += tx.count(ZKPAT)
        raw = bytes.fromhex(tx[2:]); t = raw[0]
        try:
            if t <= 4: items, _ = rlp(raw[1:])
            else: items, _ = rlp(raw); t = 0
            to = '0x' + items[POS[t][0]].hex(); sel = items[POS[t][1]][:4].hex()
        except Exception:
            continue
        if to == XEN and sel in XEN_SELS: xen += 1
        elif to in ENTRIES: mint += 1
        elif to == USDT[0] and sel == USDT[1]: usdt += 1
        if to in EXTRA: extra += 1
    c = 'A' if xen >= 2 else 'B' if xen == 1 else 'C' if usdt >= 1 else 'D'
    cm = 'mint' if xen + mint >= 1 else 'nomint'
    cmx = 'mint' if xen + mint + extra >= 1 else 'nomint'
    return n, 'ok', [n, xen, mint, usdt, extra, c, cm, 'zk' if zk else 'other', zk, cmx]


if __name__ == '__main__':
    bad = {'missing': [], 'wrong': []}; rows = []
    with Pool(JOBS) as pool:
        for n, st, row in pool.imap(one, range(FROM, TO + 1), chunksize=64):
            (rows.append(row) if st == 'ok' else bad[st].append(n))
    with open(OUT, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['block', 'xen_txs', 'minter_txs', 'usdt_txs', 'extra_txs', 'cls', 'cls_mint', 'cls_zk', 'zk_n', 'cls_mint_x'])
        w.writerows(rows)
    nm = sum(r[6] == 'mint' for r in rows); nx = sum(r[9] == 'mint' for r in rows)
    print(f'blocks {FROM}-{TO}: {TO - FROM + 1}; classified {len(rows)}, missing {len(bad["missing"])}'
          + (f' (first {bad["missing"][:3]})' if bad['missing'] else '') + f', wrong number {len(bad["wrong"])}; entries {len(ENTRIES)}, extra {len(EXTRA)}')
    if rows:
        print(f'batch-mint {nm} ({100 * nm / len(rows):.2f}%); with the EXP-246 extra entries {nx} ({100 * nx / len(rows):.2f}%); '
              f'proof-entry blocks {sum(r[7] == "zk" for r in rows)}')
    sys.exit(1 if bad['missing'] or bad['wrong'] else 0)
