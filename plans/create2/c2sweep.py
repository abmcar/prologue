#!/usr/bin/env python3
"""CREATE2 salt-template records for every code of a table (c2records.py's conversion on the analyzer evm_static_c2.py;
budgets: max_steps 3,000,000, max_forks 200,000, max_pc_visits 1,000, time_budget 60 s).
Input: a table with a header and two tab-separated columns, code hash and bytecode hex. The codes are taken in hash
order; shard i of n takes every n-th from i.
Output: OUT/c2records/<0x hash>.json (the node's format) and OUT/sweep_<shard>.csv (hash, bytes, secs, truncated, sites,
records, not_converted, error). Codes already in the shard's CSV are skipped (resume). Each code is analysed in a forked
child with its address space limited to C2_MEM_GB (default 2.5 GB) and a wall-clock limit of 600 s.
usage: python3 c2sweep.py TABLE SHARD NSHARDS OUT [--only HASH,...]"""
import collections, csv, json, os, resource, select, signal, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import c2records as C   # noqa: E402
E = C.E

TABLE, SHARD, NSH, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
only = set()
if '--only' in sys.argv:
    only = {h.lower().removeprefix('0x') for h in sys.argv[sys.argv.index('--only') + 1].split(',')}
os.makedirs(f'{OUT}/c2records', exist_ok=True)


def signature(r):
    # as in scripts/c2records.py (main loop)
    sig = []
    for sg in r['salt']['segs']:
        if sg['kind'] == 'const' or sg['kind'] == 'index' and sg['from'] is None:
            sig.append('ix0')
        elif sg['kind'] == 'index':
            sig.append(('ix', json.dumps(sg['from'], sort_keys=True)))
        elif sg['kind'] == 'cdarr':
            sig.append(('arr', sg['off_word']))
        else:
            v = sg['val']
            if v['kind'] == 'lin':
                v = v['val']
            sig.append(('arr', v['off_word']) if v['kind'] == 'cdat' else ('v', json.dumps(v, sort_keys=True)))
    return tuple(sig)


def records_for(code):
    # the body of scripts/c2records.py's main loop for one code
    t0 = time.time()
    an = E.analyze(code, max_steps=3_000_000, max_forks=200_000, max_pc_visits=1000, time_budget=60)
    dt = time.time() - t0
    groups = collections.defaultdict(list)
    reasons = collections.Counter()
    seen = set()
    sites = getattr(an, 'c2sites', [])
    for pc, name, salt, init, cons in sites:
        k = (pc, name, repr(salt), repr(init), C.sel_of(cons))
        if k in seen:
            continue
        seen.add(k)
        try:
            r = C.site_record(pc, name, salt, init, cons)
            groups[(r['sel'], name, pc, signature(r))].append(r)
        except C.Unsupported as ex:
            reasons[(pc, name, C.sel_of(cons), str(ex)[:70])] += 1
    records = []
    for key, recs in sorted(groups.items(), key=lambda kv: (kv[0][2], kv[0][1], kv[0][0] or '')):
        try:
            records.append(C.merge(recs))
        except C.Unsupported as ex:
            reasons[(key[2], key[1], key[0], 'merge:' + str(ex)[:60])] += len(recs)
    by_sel = collections.Counter((r['sel'], r['site'], r['pc']) for r in records)
    for r in records:
        r['variants'] = by_sel[(r['sel'], r['site'], r['pc'])]
    C.infer_counts(records)
    C.updates_for(an, records)
    return an, dt, len(seen), records, reasons


MEM_AS = int(float(os.environ.get('C2_MEM_GB', '2.5')) * 2**30)
WALL = 600


def analyse_in_child(code, hx):
    rfd, wfd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(rfd)
        try:
            resource.setrlimit(resource.RLIMIT_AS, (MEM_AS, MEM_AS))
            an, dt, nsites, records, reasons = records_for(code)
            out = {'codehash': hx, 'address': '', 'secs': round(dt, 2), 'records': [C.hexify(r) for r in records],
                   'not_converted': [{'pc': k[0], 'site': k[1], 'sel': k[2], 'why': k[3], 'n': v} for k, v in reasons.items()]}
            json.dump(out, open(f'{OUT}/c2records/{hx}.json', 'w'), indent=1)
            msg = {'ok': [round(dt, 2), int(bool(getattr(an, 'truncated', False))), nsites, len(records), sum(reasons.values())]}
        except MemoryError:
            msg = {'err': f'memory limit of the analysis ({MEM_AS / 2**30:.1f} GB address space)'}
        except BaseException as ex:   # an analyzer failure on one code is recorded, the sweep goes on
            msg = {'err': f'{type(ex).__name__}: {str(ex)[:120]}'}
        try:
            os.write(wfd, json.dumps(msg).encode())
        finally:
            os._exit(0)
    os.close(wfd)
    t0, data = time.time(), b''
    while True:
        left = WALL - (time.time() - t0)
        if left <= 0:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            os.close(rfd)
            return {'err': f'wall-clock limit of the analysis ({WALL} s)'}, time.time() - t0
        r, _, _ = select.select([rfd], [], [], left)
        if r:
            chunk = os.read(rfd, 65536)
            if not chunk:
                break
            data += chunk
    os.close(rfd)
    _, st = os.waitpid(pid, 0)
    if not data:
        return {'err': f'analysis process ended without a result (status {st})'}, time.time() - t0
    return json.loads(data), time.time() - t0


done = set()
csvp = f'{OUT}/sweep_{SHARD}.csv'
stp = f'{OUT}/sweep_{SHARD}.started'
if os.path.exists(csvp):
    done = {r['hash'] for r in csv.DictReader(open(csvp))}
new = not os.path.exists(csvp)
fo = open(csvp, 'a', newline='')
w = csv.writer(fo)
if new:
    w.writerow(['hash', 'bytes', 'secs', 'truncated', 'sites', 'records', 'not_converted', 'error'])
if os.path.exists(stp):
    for h in dict.fromkeys(l.strip() for l in open(stp) if l.strip()):
        if h not in done:
            w.writerow([h, '', '', '', '', '', '', 'killed during the analysis'])
            done.add(h)
    fo.flush()
fs = open(stp, 'a')
rows = []
with open(TABLE) as f:
    next(f)
    for line in f:
        h, b = line.rstrip('\n').split('\t')
        rows.append((h.lower().removeprefix('0x'), b))
rows.sort()
mine = [x for i, x in enumerate(rows) if i % NSH == SHARD and (not only or x[0] in only)]
del rows   # the children are forked from this process: keep it small
t_all = time.time()
for n, (h, b) in enumerate(mine):
    hx = '0x' + h
    if hx in done:
        continue
    code = bytes.fromhex(b.removeprefix('0x'))
    if len(code) == 23 and code[:3] == b'\xef\x01\x00':
        # an EIP-7702 designator, not code (its address bytes decode as a CREATE2 in the byte scan)
        w.writerow([hx, len(code), '', '', '', '', '', 'EIP-7702 designator'])
        fo.flush()
        continue
    if '0x' + E.keccak256(code).hex() != hx:
        w.writerow([hx, len(code), '', '', '', '', '', 'hash mismatch'])
        fo.flush()
        continue
    fs.write(hx + '\n')
    fs.flush()
    res, wall = analyse_in_child(code, hx)
    if 'ok' in res:
        w.writerow([hx, len(code), *res['ok'], ''])
    else:
        w.writerow([hx, len(code), round(wall, 2), '', '', '', '', res['err']])
    fo.flush()
print(f'shard {SHARD}/{NSH}: {len(mine)} codes, {time.time() - t_all:.0f} s')
