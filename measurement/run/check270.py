#!/usr/bin/python3
"""EXP-270 README 9 (written before the run, 11-13; from EXP-257 scripts/check257.py): checks of one node process of the
final measurement, on the development host after fetch270.sh copied it to raw/<run>. Stops (exit 1) only on conditions the
code guarantees when the run is what it should be. Items as check257.py, with these changes:
  1. NPASS: 1 for up ur un pn pp and the tiers' up un pn pp; 9 for abl, 5 for rec, 4 for tchk and strec; tchk measures
     400 blocks; segment k's base is SEG0 + 1000k (README 2);
  3. the integration build writes an `eap block` line on every measured block of a row with tx=1 only in the processes
     with logq=0 at the end of the control line (rec, strec, tchk; README 1); in every other integration process
     (logq=1) there is no `eap block` line at all;
  4. the rows in the driver's meta: U8 = AB1ng; F8 = G4qaxepkS or G4qaxepkSR; P8 = G3qxS; F8chk, P8chk with reusechk=1;
     H3 = P8 without rdscratch; H4 = F8; H1-H4 each add only their group (as apply_final270.py); H5 = H0 with H4's plan
     tokens; HX, HC, HXC = F8 with pwlx=0, nocons=1, both; H0n = H0 with prewarm=0 (rows compared as {key: last value});
  5. the scope's memory.max is MEMT (16, 32 or 64 GiB); rtprio.txt records the control addition CTRL_ADD: srdiag=0
     ctlcache=1, plus logq=0 for rec/strec and logq=0 xbtl2=1 for tchk;
  9. switches from `eap block` lines in rec, strec, tchk only: every block of F8, H4, H5, HX, HC, HXC has rdpool=true,
     rdjoinlate=true, nb_txs = nb_keys = 0; HX, HXC lx_calls = lx_fit = lx_groups = 0; HC, HXC nocons=true, every other
     integration block nocons=false; H0-H3, H0n and P8 blocks have no readers; summed over the process H4 (or HC) has
     lx_calls > 0; the share of plan lookups without a plan is printed per row;
  10. records: rec and strec have EAP_DIAG, a diag file and cc cache timing lines, H0n with H0 slot waits; the others none;
  13. every pass's node arguments carry --jit and README 15.5's set (--jit.timeout 60s --jit.worker-count JITW
     --jit.max-pending-jobs 8192 --jit.log-compilations); no JIT helper timeout and no failed compilation; at least one
     `jit compiled` line; printed: dropped requests and compilations during and after the first 250 measured blocks;
     the integration build's `salt-template records loaded` line says codes=370 rejected=0 (c2rec_270); records carry the
     driver's gap field (printed per mark);
  12. the integration build's node environment has EAP_C2REC=C2REC (default /prologue/data/c2rec_270; README 1);
  11. every process (not only the tiers): disk counters on every measured record and rd_ios > 0; raw/tier.txt names
     the node database's device; local (TIER local or none): that device is the device of /data; pl1, pl0: it is not.
usage: MODE=<mode> SEG=<k> BIN_SHA=<sha256> [SEG0=..] [TIER=<tier>] [MEMT=32G] check270.py <run directory> [--pair <other run directory>]"""
import csv, json, os, re, sys
from collections import Counter

D = sys.argv[1]
PAIR = sys.argv[sys.argv.index('--pair') + 1] if '--pair' in sys.argv else None
MODE = os.environ['MODE']; SEG = int(os.environ['SEG']); SHA = os.environ['BIN_SHA']; TIER = os.environ.get('TIER', '')
SEG0 = int(os.environ.get('SEG0', '26305830')); MEMT = os.environ.get('MEMT', '32G')
TO = SEG0 + 1000 * SEG; MS = TO + 301; ME = TO + (700 if MODE == 'tchk' else 1300)
L = os.path.basename(D.rstrip('/'))[4:].replace('-', '')        # e270up-0 -> up0, e270m16up-6 -> m16up6, e270spl1pn-6 -> spl1pn6
ROWSETS = {'abl': 'H0 H1 H2 H3 H4 H5 HX HC HXC', 'rec': 'H0n H0 H3 H4 H5', 'tchk': 'H0 H3 H4 HXC', 'strec': 'H0n H0 H3 H4'}
INT = MODE in ('pn', 'pp', 'abl', 'rec', 'tchk', 'stpn', 'stpp', 'strec')
ROWS = ROWSETS[MODE].split() if MODE in ROWSETS else (['F8'] if MODE in ('pn', 'stpn') else ['P8'] if MODE in ('pp', 'stpp') else ['U8'])
NP = len(ROWS) if MODE in ROWSETS else 1
REC = MODE in ('rec', 'strec')
ECHO = MODE in ('rec', 'strec', 'tchk')   # logq=0 at the end of the control line
WANT_CTRL = 'srdiag=0 ctlcache=1' + (' logq=0' if MODE in ('rec', 'strec') else ' logq=0 xbtl2=1' if MODE == 'tchk' else '')
PREWARM = {'ew', 'ewded', 'ewgas', 'ewov', 'pwheavyfirst', 'pwjitpeek', 'pwjitreal', 'reuse', 'reusebal', 'reusechk',
           'reusefast', 'reusefb', 'ewredo', 'reusebalsend', 'ixpf', 'ixpfw'}
SCHED = {'ewcore', 'ewpool', 'exslice', 'exrt', 'ewnear', 'exio', 'srrt'}
READ = {'accflt', 'accfltchk', 'bigra', 'ccv', 'ewinf', 'rdpeek', 'sysn'}
FEAT = {'HX': {'pwlx': '0'}, 'HC': {'nocons': '1'}, 'HXC': {'pwlx': '0', 'nocons': '1'}}
FROZEN = {'F8', 'H4', 'H5', 'HX', 'HC', 'HXC'}
CNT = ('lx_calls', 'lx_fit', 'lx_groups', 'lx_keys', 'nb_txs', 'nb_keys', 'ix_keys', 'cs_keys', 'tx_keys')
FB = re.compile(r' eap reusefb block=(\d+) reused=(\d+) outcome=(\w+)')
PL = re.compile(r' eap plans block=(\d+) .*?hits=(\d+) misses=(\d+) absent=(\d+)')
bad = []
JITD = []
eapv = {}; plans = {}; NODE_PIDS = []; fbs = []; reth_reuse = Counter(); xflag = []; nflag = []


def evict(d, lab):
    f = f'{d}/raw/{lab}.evict.log'
    t = open(f).read() if os.path.exists(f) else ''
    m = re.search(r'evicted (\d+) files, ([\d.]+) GiB advised; Cached (\d+) MiB -> (\d+) MiB', t)
    return tuple(float(x) for x in m.groups()) if m else None


def kv(s):
    return dict(x.partition('=')[::2] for x in s.split())


run_main = open(f'{D}/raw/run_main.log').read() if os.path.exists(f'{D}/raw/run_main.log') else ''
if 'run_main rc=0' not in run_main:
    bad.append('no run_main rc=0 line')
seen = {}; rowof = {}; configs = None; recs = {}
for p in range(NP):
    lab = f'{L}{p}'
    meta = json.load(open(f'{D}/raw/{lab}.meta.json'))
    configs = configs or meta.get('configs')
    if meta.get('binary_sha256') != SHA:
        bad.append(f'pass {p}: binary_sha256 {meta.get("binary_sha256")} is not {SHA[:16]}...')
    if meta.get('warmup') != 300 or meta.get('n_measured') != ME - MS + 1:
        bad.append(f'pass {p}: warm-up {meta.get("warmup")}, measured {meta.get("n_measured")} (want 300, {ME - MS + 1})')
    meas = [r for r in csv.DictReader(open(f'{D}/results/blocks_{lab}.csv')) if r['role'] == 'measured']
    if sorted(int(r['block']) for r in meas) != list(range(MS, ME + 1)):
        bad.append(f'pass {p}: measured blocks are not exactly {MS}-{ME} ({len(meas)} records)')
    for r in meas:
        seen.setdefault(int(r['block']), []).append(r['cfg']); rowof[(p, int(r['block']))] = r
    env, args = meta.get('node_env', ''), ' '.join(meta.get('extra_args') or [])
    xflag.append('--engine.prewarm-reuse' in args); nflag.append('--engine.disable-prewarming' in args)
    jw = os.environ.get('JITW', '8')
    _jx = f'--jit.timeout 60s --jit.worker-count {jw} --jit.max-pending-jobs 8192 --jit.log-compilations'
    if _jx not in args or '--jit' not in args.split():
        bad.append(f'pass {p}: node arguments lack --jit and {_jx!r} (README 15.5)')
    # README 15: the JIT's dropped compile requests during the measured blocks (printed; not a stop condition)
    _cur = 0; _dm = _dl = 0; _ok = _fail = _late = _to = 0; _c2 = None
    for _l in open(f'{D}/raw/{lab}.node.log', errors='replace'):
        _x = re.search(r'Received new payload from consensus engine number=(\d+)', _l)
        if _x:
            _cur = int(_x.group(1))
        elif 'worker pool saturated, dropping request' in _l and _cur >= MS:
            _dm += 1; _dl += _cur >= MS + 250
        elif ' jit compiled ' in _l or _l.rstrip().endswith('jit compiled'):
            if 'success=true' in _l:
                _ok += 1; _late += _cur >= MS + 250
            else:
                _fail += 1
        elif 'JIT helper timed out' in _l:
            _to += 1
        elif 'compilation failed' in _l:
            _fail += 1
        elif 'salt-template records loaded' in _l:
            _c2 = re.search(r'codes=(\d+) rejected=(\d+)', _l)
    JITD.append((p, _dm, _dl, _ok, _fail, _late, _to))
    # README 15.5: the JIT settings are the same for every process: no helper timeout, no failed compilation
    if _to or _fail:
        bad.append(f'pass {p}: JIT helper timeouts {_to}, failed compilations {_fail} (README 15.5 item 4)')
    if not _ok:
        bad.append(f'pass {p}: no `jit compiled` line (--jit.log-compilations)')
    # README 11: the integration build loads c2rec_270: codes with records 370, none rejected
    if INT:
        if not _c2 or _c2.groups() != ('370', '0'):
            bad.append(f'pass {p}: salt-template records loaded {_c2.groups() if _c2 else None}, want codes=370 rejected=0 (c2rec_270)')
    if INT and f"EAP_C2REC={os.environ.get('C2REC', '/prologue/data/c2rec_270')}" not in env:
        bad.append(f'pass {p}: the node environment has not EAP_C2REC={os.environ.get("C2REC", "/prologue/data/c2rec_270")} (README 1)')
    v2 = False; nerr = 0; neap = 0; eapblk = set(); cc = 0
    for line in open(f'{D}/raw/{lab}.node.log', errors='replace'):
        v2 = v2 or 'storage_v2: true' in line
        m = FB.search(line)
        if m:
            fbs.append((p, int(m.group(1)), m.group(3)))
        elif 'panicked' in line or 'nvalid block' in line or 'state root mismatch' in line.lower() or 'mismatched state root' in line.lower():
            nerr += 1
        if 'cc cache timing' in line:
            cc += 1
        if ' reth::eap: ' in line:
            neap += 1
            m = re.search(r' eap block block=(\d+)', line)
            if m:
                eapblk.add(int(m.group(1)))
                eapv[(p, int(m.group(1)))] = dict(re.findall(r'(\w+)=([\w.-]+)', line[m.start():]))
            m = PL.search(line)
            if m:
                plans[(p, int(m.group(1)))] = tuple(int(x) for x in m.groups()[1:])
    if not v2:
        bad.append(f'pass {p}: no storage_v2: true line')
    if nerr:
        bad.append(f'pass {p}: {nerr} panicked or invalid-block lines')
    if not INT and neap:
        bad.append(f'pass {p}: {neap} Prologue lines from the official build')
    if INT:
        cf = meta.get('configs') or {}
        tx1 = {int(r['block']) for r in meas if kv(cf.get(r['cfg'], '')).get('tx') == '1'}
        if ECHO and not tx1 <= eapblk:
            bad.append(f'pass {p}: {len(tx1 - eapblk)} measured blocks of rows with tx=1 without an eap block line')
        _me = {b for b in eapblk if MS <= b <= ME}   # the warm-up rows F8w/P8w and the pre-check F8chk write them (README 16.5)
        if not ECHO and _me:
            bad.append(f'pass {p}: {len(_me)} eap block lines on measured blocks although logq=1 (records-off process)')
        tf = f'{D}/raw/{lab}.threads.txt'; node_pid = None
        if os.path.exists(tf):
            ln = open(tf).read().splitlines()
            node_pid = ln[1].split()[0] if len(ln) > 1 and ln[1].split() else None
        NODE_PIDS.append((p, node_pid))
    # 10. records
    diag = os.path.exists(f'{D}/raw/{lab}.diag.jsonl') or os.path.exists(f'{D}/raw/{lab}.diag.jsonl.gz')
    if REC:
        if 'EAP_DIAG=' not in env:
            bad.append(f'pass {p}: no EAP_DIAG in the node environment (records on expected)')
        if not diag:
            bad.append(f'pass {p}: no diag file')
        if not cc:
            bad.append(f'pass {p}: no cc cache timing lines')
    else:
        if 'EAP_DIAG=' in env or 'EAP_KEYDIAG=' in env:
            bad.append(f'pass {p}: records in the node environment')
        if '--engine.slow-block-threshold' in args:
            bad.append(f'pass {p}: slow-block threshold in the node arguments')
        if diag:
            bad.append(f'pass {p}: diag file exists')
        if cc:
            bad.append(f'pass {p}: {cc} cc cache timing lines')
    modes = Counter(); settle = []; nodisk = 0; rdios = 0
    for line in open(f'{D}/raw/{lab}.jsonl'):
        if not line.startswith('{'):
            continue
        x = json.loads(line)
        if x.get('role') != 'measured':
            continue
        recs[(p, x.get('block'))] = x
        for n, v in (x.get('metrics') or {}).items():
            for k in ('reused_transactions', 'missing_transactions', 'stale_transactions'):
                if n.startswith(f'reth_sync_prewarm_reuse_{k}'):
                    reth_reuse[k] += float(v)
        modes[(x.get('lean') or {}).get('mode')] += 1; settle.append(x.get('settle_s') or 0)
        if True:   # EXP-270: every process has DISK_DEV
            d = x.get('disk') or {}
            if 'rd_ios' not in d:
                nodisk += 1
            else:
                rdios += d['rd_ios']
    if set(modes) != {'fcu'}:
        bad.append(f'pass {p}: lean modes {dict(modes)}, not all fcu')
    if nodisk or rdios <= 0:
        bad.append(f'pass {p}: {nodisk} measured records without disk counters; rd_ios summed {rdios}')
    ev = evict(D, lab)
    if not ev:
        bad.append(f'pass {p}: no eviction record')
    settle.sort()
    print(f'pass {p}: eviction {ev}; settle_s median {settle[len(settle) // 2]:.3f}' + f'; device reads {rdios}')
if any(sorted(seen.get(b, [])) != sorted(ROWS) for b in range(MS, ME + 1)):
    wrong = [b for b in range(MS, ME + 1) if sorted(seen.get(b, [])) != sorted(ROWS)]
    bad.append(f'{len(wrong)} blocks not under each of {ROWS} exactly once (first {wrong[:3]})')
sc = open(f'{D}/raw/scope.txt').read() if os.path.exists(f'{D}/raw/scope.txt') else ''
if f'memory.max {int(MEMT[:-1]) * 2**30}' not in sc:
    bad.append(f'scope memory.max not {MEMT} ({sc.strip()[:80]})')
# 4. the rows ({key: last value}, as the node parses a line)
def M(row):
    d = {}
    for x in row.split():
        k, _, v = x.partition('=')
        d.pop(k, None); d[k] = v
    d.pop('srdiag', None)
    return d
def DIFF(a, b):
    return {k: v for k, v in b.items() if a.get(k) != v}
C = configs or {}
need = ['U8', 'AB1ng'] + ('F8 F8chk P8 P8chk G3qxS G4qaxepkS G4qaxepkSR G0 G1 G2 G3 H0 H1 H2 H3 H4 H5 HX HC HXC H0n'.split() if INT else [])
if any(k not in C for k in need):
    bad.append(f'rows missing in the meta: {[k for k in need if k not in C]}')
else:
    if C['U8'] != C['AB1ng']:
        bad.append('U8 differs from AB1ng')
    if INT:
        m = {r: M(C[r]) for r in need}
        if m['F8'] not in (m['G4qaxepkS'], m['G4qaxepkSR']):
            bad.append('F8 is neither G4qaxepkS nor G4qaxepkSR')
        if m['P8'] != m['G3qxS']:
            bad.append('P8 is not G3qxS')
        p8 = dict(m['P8']); p8.pop('rdscratch', None)
        if m['H3'] != p8:
            bad.append('H3 is not P8 without rdscratch')
        if m['H4'] != m['F8']:
            bad.append('H4 is not F8')
        for a, b, g in (('G0', 'G1', None), ('G1', 'G2', {'excore', 'exsmt', 'exphys'}), ('G2', 'G3', {'srleafselect'})):
            ha, hb = 'H' + a[1], 'H' + b[1]
            want = set(DIFF(m[a], m[b])) | (g or set())
            if set(DIFF(m[ha], m[hb])) != want or not set(m[ha]) <= set(m[hb]):
                bad.append(f'{hb} - {ha} is not only its group')
        plan = DIFF(m['H3'], m['H4'])
        if m['H5'] != {**m['H0'], **plan}:
            bad.append('H5 is not H0 with the plan tokens of H4')
        for r, d in FEAT.items():
            if DIFF(m['F8'], m[r]) != d:
                bad.append(f'{r} is not F8 with {d}')
        for r, b in (('F8chk', 'F8'), ('P8chk', 'P8')):
            if DIFF(m[b], m[r]) != {'reusechk': '1', 'logq': '0'} or set(m[b]) != set(m[r]):
                bad.append(f'{r} is not {b} with reusechk=1 logq=0')
        if DIFF(m['H0'], m['H0n']) != {'prewarm': '0'}:
            bad.append('H0n is not H0 with prewarm=0')
# 6. the real-time permission
exrt1 = INT and kv(C.get('F8', '')).get('exrt', '0') != '0'
want_rt = '1' if exrt1 else 'unset'
rt = open(f'{D}/raw/rtprio.txt').read().splitlines() if os.path.exists(f'{D}/raw/rtprio.txt') else []
if not rt or f'setting NODE_RTPRIO={want_rt} ' not in rt[0] + ' ':
    bad.append(f'rtprio.txt setting {rt[:1]}, want NODE_RTPRIO={want_rt}')
if not rt or not rt[0].rstrip().endswith(f' ctrl {WANT_CTRL}'):
    bad.append(f'rtprio.txt: control addition is not {WANT_CTRL!r}')
lim = '1 1' if exrt1 else '0 0'
lim_of = {l.split()[1]: l.rstrip() for l in rt[1:] if l.startswith('pid ')}
if not INT:
    if not lim_of or any(not l.endswith(f'Max realtime priority {lim}') for l in lim_of.values()):
        bad.append(f'processes with another real-time limit than {lim}')
else:
    for p_, np_ in NODE_PIDS:
        if np_ is None or np_ not in lim_of or not lim_of[np_].endswith(f'Max realtime priority {lim}'):
            bad.append(f'pass {p_}: node process {np_} real-time limit {lim_of.get(np_, "not recorded")}, not {lim}')
# 7. the whole-block fallback
if any(f[2] != 'accepted' for f in fbs):
    bad.append(f'fallback outcomes other than accepted: {[f for f in fbs if f[2] != "accepted"][:5]}')
print(f'fallback (reusefb): {len(fbs)} lines')
# 8. reth's reuse and stock without prewarming
if MODE == 'ur':
    if not all(xflag) or reth_reuse['reused_transactions'] <= 0:
        bad.append(f'reuse flag in passes {xflag}, reused transactions {reth_reuse["reused_transactions"]:.0f}')
elif any(xflag):
    bad.append(f'--engine.prewarm-reuse in a {MODE} process')
if MODE in ('un', 'stun'):
    if not all(nflag):
        bad.append('a pass without --engine.disable-prewarming')
    pw = [(x.get('threads') or {}).get('prewarm', 0.0) for x in recs.values()]
    mpw = sum(pw) / max(len(pw), 1)
    print(f'prewarm threads: {mpw:.1f} ms per measured block')
    if mpw > 5:
        bad.append(f'prewarm threads use {mpw:.1f} ms per measured block with prewarming disabled')
elif any(nflag):
    bad.append(f'--engine.disable-prewarming in a {MODE} process')
# 9. switches (only where logq=0 brings the eap block lines back)
if INT and ECHO:
    num = lambda d, k: float(d.get(k, 'nan'))   # noqa: E731
    by = {}
    for pb, r in rowof.items():
        by.setdefault(r['cfg'], []).append(eapv.get(pb))
    for row, ds in sorted(by.items()):
        have = [d for d in ds if d is not None]
        if row in FROZEN:
            if len(have) != len(ds):
                bad.append(f'{row}: {len(ds) - len(have)} blocks without an eap block line')
            off = [k for k in ('rdpool', 'rdjoinlate') if any(d.get(k) != 'true' for d in have)]
            if off:
                bad.append(f'{row}: blocks with {off} not true')
            if any(num(d, k) != 0 for d in have for k in ('nb_txs', 'nb_keys')):
                bad.append(f'{row}: blocks with nb_txs or nb_keys > 0 (speculation is off)')
            if row in ('HX', 'HXC') and any(num(d, k) != 0 for d in have for k in ('lx_calls', 'lx_fit', 'lx_groups')):
                bad.append(f'{row}: blocks with extrapolation counters > 0')
        elif any(d is not None and num(d, 'readers') > 0 for d in ds):
            bad.append(f'{row}: blocks with readers > 0 (the row has no readers)')
        want_nc = 'true' if row in ('HC', 'HXC') else 'false'
        if any(d.get('nocons') != want_nc for d in have):
            bad.append(f'{row}: blocks whose nocons is not {want_nc}')
        tot = {k: sum(num(d, k) for d in have) for k in CNT}
        if row in ('F8', 'H4', 'HC') and not tot['lx_calls'] > 0:
            bad.append(f'{row}: lx_calls summed over the process is 0')
        pl = [plans[pb] for pb, r in rowof.items() if r['cfg'] == row and pb in plans]
        look = sum(sum(x) for x in pl); ab = sum(x[2] for x in pl)
        print(f'{row}: {len(have)} eap block lines; per block ' + ', '.join(f'{k} {tot[k] / max(len(have), 1):.1f}' for k in CNT)
              + (f'; plan lookups without a plan {ab / look:.4f}' if look else ''))
# 10 (recording processes): G0n's prewarm threads idle, the waits recorded
if REC:
    pw = {'H0': [], 'H0n': []}; sm = {'H0': [], 'H0n': []}
    for pb, r in rowof.items():
        if r['cfg'] in pw and int(float(r['pos'])) >= 2:
            x = recs.get(pb) or {}
            pw[r['cfg']].append((x.get('threads') or {}).get('prewarm', 0.0)); sm[r['cfg']].append(float(r.get('slot_miss_ms') or 0))
    for c in pw:
        n = max(len(pw[c]), 1)
        print(f'{c}: {len(pw[c])} blocks at position >= 2; prewarm threads {sum(pw[c]) / n:.1f} ms; slot_miss_ms {sum(sm[c]) / n:.2f} per block')
    if sum(pw['H0n']) / max(len(pw['H0n']), 1) > 5:
        bad.append("H0n: reth's prewarm threads use more than 5 ms per block")
    if not sum(sm['H0n']) > 0 or not sum(sm['H0']) > 0:
        bad.append('H0 or H0n: no slot waits recorded')
# 11. the device under the node's working database (every process)
tt = open(f'{D}/raw/tier.txt').read() if os.path.exists(f'{D}/raw/tier.txt') else ''
m1 = re.match(r'tier (\S+) dev (\S+) disk \S+ data-dev (\S+)', tt)
base = lambda s: re.sub(r'p\d+$', '', s)   # noqa: E731
if not m1:
    bad.append('raw/tier.txt missing or without its first line')
else:
    tr, dv, dd = m1.groups()
    if tr != (TIER or 'local'):
        bad.append(f'tier.txt names tier {tr}, not {TIER or "local"}')
    if (TIER or 'local') == 'local' and dv != dd:
        bad.append(f'local tier: the database is on {dv}, not on the device of /data ({dd})')
    if TIER in ('pl1', 'pl0') and base(dv) == base(dd):
        bad.append(f'tier {TIER}: the database is on {dv}, the local device of /data')
if PAIR:
    other = os.path.basename(PAIR.rstrip('/'))[4:].replace('-', '') + '0'
    a, b = evict(D, f'{L}0'), evict(PAIR, other)
    if not a or not b or a[:2] != b[:2]:
        bad.append(f'evictions differ from the paired process: {a} vs {b}')
    else:
        print(f'pair: same eviction ({a[0]:.0f} files, {a[1]} GiB); page cache before {a[2]:.0f} vs {b[2]:.0f} MiB')
print('JIT per pass (dropped requests in the measured blocks, after their first 250; compiled ok, failed, ok after the first 250 measured blocks; helper timeouts): '
      + '; '.join(f'{p}: {a}, {b}; {c}, {d}, {e}; {f}' for p, a, b, c, d, e, f in JITD))
# README 1, EXP-269 section 16: the driver's work between blocks (gap marks, ms), mean per measured block, printed only
_g = {}
for _r in recs.values():
    for _k, _v in (_r.get('gap') or {}).items():
        if isinstance(_v, (int, float)):
            _g.setdefault(_k, []).append(_v)
print('driver gap marks, mean ms: ' + (', '.join(f'{k} {sum(v) / len(v):.1f}' for k, v in sorted(_g.items())) if _g else 'none (no gap field)'))
if not _g:
    bad.append('no gap field in the records (the driver of 6ad623cb or later records it)')
print('OK' if not bad else 'FAIL: ' + '; '.join(bad))
sys.exit(1 if bad else 0)
