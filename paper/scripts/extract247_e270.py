#!/usr/bin/env python3
"""Step 1 of 2 of the per-transaction cost comparison (paragraph "Reuse"): per-transaction tables of the recording
processes from the per-read records (rec<k><p>.diag.jsonl, not in the repository), written to
paper/data/f270_tx/tx_rec<k><p>.csv.gz. The tables are in the repository, so step 2 (restcost247_e270.py) runs without
this step.
usage: EXP247_REC=<run dir> python3 paper/scripts/extract247_e270.py L P CFG [CFG ...]   (wrapper: extract247_e270.sh)"""
import csv, gzip, json, os, sys

E = os.environ['EXP247_REC']
O = os.environ.get('EXP247_OUT') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'f270_tx')
CLASS = os.environ.get('EXP247_CLASS') or \
    'measurement/block_classes.csv'
GLF = os.environ.get('EXP247_GL') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'gl_none.csv.gz')
POOL = os.environ.get('BLOCKS_POOL', 'blocks_pool')   # only read when a gas-limit table lacks a block
L, P, CFGS = sys.argv[1], int(sys.argv[2]), set(sys.argv[3:])
cls_of = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(CLASS))}
GL = {}
for r in csv.DictReader(gzip.open(GLF, 'rt')):
    GL.setdefault(int(r['block']), []).append((int(r['i']), int(r['gl'])))
GL = {b: [g for _, g in sorted(v)] for b, v in GL.items()}


def rlp_item(b, i):
    c = b[i]
    if c < 0x80: return i, i + 1, i + 1
    if c < 0xb8: return i + 1, i + 1 + c - 0x80, i + 1 + c - 0x80
    if c < 0xc0:
        n = c - 0xb7; ln = int.from_bytes(b[i + 1:i + 1 + n], 'big'); s = i + 1 + n
        return s, s + ln, s + ln
    if c < 0xf8: return i + 1, i + 1 + c - 0xc0, i + 1 + c - 0xc0
    n = c - 0xf7; ln = int.from_bytes(b[i + 1:i + 1 + n], 'big'); s = i + 1 + n
    return s, s + ln, s + ln


def gas_limit(raw):
    b = bytes.fromhex(raw[2:] if raw.startswith('0x') else raw)
    if b[0] >= 0xc0: idx, body = 2, b
    else: idx, body = (3 if b[0] == 1 else 4), b[1:]
    s, e, _ = rlp_item(body, 0); i = s
    for _ in range(idx): i = rlp_item(body, i)[2]
    ps, pe, _ = rlp_item(body, i)
    return int.from_bytes(body[ps:pe], 'big') if pe > ps else 0


want = {}
for r in csv.DictReader(open(f'{E}/results/blocks_{L}{P}.csv')):
    c = r['cfg'].split('+')[0]
    if r['role'] == 'measured' and int(float(r['pos'])) >= 2 and c in CFGS:
        want[int(r['block'])] = c
PRE = os.environ.get('EXP247_OUTPRE', '')
os.makedirs(O, exist_ok=True)
ft = gzip.open(f'{O}/tx_{PRE}{L}{P}.csv.gz', 'wt', compresslevel=5)
wt = csv.writer(ft)
wt.writerow(['block', 'cfg', 'cls', 'i', 'gl', 'st', 'd', 'ws', 'we', 'pwa_n', 'pwa_us', 'pws_n', 'pws_us', 'pwc_n',
             'pwc_us', 'es', 'ee', 'lk_pw', 'lk_rd', 'lk_old', 'lk_miss', 'sm_n', 'sw0', 'sw1', 'sw2', 'sw3', 'aw', 'cw',
             'ru_cpu', 'ru_vcs', 'ru_ivcs', 'ru_flt', 'ru_rq'])
seen = 0
LIMIT = int(os.environ.get('LIMIT', '0'))
for line in open(f'{E}/raw/{L}{P}.diag.jsonl'):
    if LIMIT and seen >= LIMIT:
        break
    if line.startswith('{"block":'):
        j = line.index(',', 9)
        if int(line[9:j]) not in want:
            continue
    r = json.loads(line)
    b = r['block']
    if b not in want:
        continue
    seen += 1
    c, k = want[b], cls_of.get(b, '?')
    if GL:
        gls = GL.get(b, [])
    else:
        raw = json.load(open(f'{POOL}/{b}.json'))['payload']['transactions']
        gls = [gas_limit(t) for t in raw]
    tx = r['tx']
    n = len(tx)
    sw = [[0, 0, 0, 0, 0] for _ in range(n)]  # misses, wait by cls 0-3 (ns)
    ow = [[0, 0] for _ in range(n)]  # account, code wait (ns)
    for x in r['miss2']:
        i, t, cl, src, dt, dur = x[0], x[1], x[2], x[3], x[4], x[7]
        if 0 <= i < n:
            sw[i][0] += 1
            sw[i][1 + cl] += dur
    for x in r['other']:
        i, t, kind, _id, dur = x[0], x[1], x[2], x[3], x[4]
        if 0 <= i < n:
            ow[i][0 if kind == 0 else 1] += dur
    for x in tx:
        i = x[0]
        ru = x[17:22] if len(x) >= 22 else ['', '', '', '', '']
        wt.writerow([b, c, k, i, gls[i] if i < len(gls) else -1] + x[1:17] +
                    [sw[i][0], sw[i][1] // 1000, sw[i][2] // 1000, sw[i][3] // 1000, sw[i][4] // 1000,
                     ow[i][0] // 1000, ow[i][1] // 1000] + list(ru))
ft.close()
print(f'{L}{P}: {seen} of {len(want)} counted blocks written ({sorted(CFGS)})')
