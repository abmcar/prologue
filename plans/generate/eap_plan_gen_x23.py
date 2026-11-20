"""copy of scripts/eap_plan_gen_wb.py whose analysers are scripts/sas_x23 (affine memory
reads in loops, AFFINE_MEM) instead of scripts/sas_wb; nothing else changed. Original docstring follows."""
"""deterministic access-plan generation with machine-independent bounds.

Source: copy of scripts/eap_plan_gen.py, changed as follows.
  * analysers are the scripts/sas_wb copies: no wall-clock budget; deterministic work units counted in element counts
    (memory-state copies, dedup keys, records, new expression nodes, forks, memory composition, widening, stack scans)
    and a work cap W <= max_work checked every 256 steps (weights `wk`); a truncated analysis keeps its records, as with
    the step cap, so the product never depends on time, memory limits or the machine;
  * records are stamped with the work of the last check (w_chk) instead of the step count (v1: step count, v1 has no work
    units and its cost per step is nearly constant), so one run with a large cap yields the summaries of every smaller
    cap K (records with stamp <= K);
  * the record order key no longer uses Python's tuple / int hash (implementation specific: CPython and PyPy may differ)
    but an explicit 64-bit combination (_mix), so the order and the compacted summary are the same on every runtime;
  * exploration-only valves (`valve_cpu`, `valve_rss_mb`): stop an analysis on process CPU time or resident memory;
    used only in development runs to bound their cost, reported per analysis (valve column), never in production;
  * no RLIMIT_AS in production (`--as-gib 0`): memory is bounded by the work cap.
  * `--max-work` also accepts per-analyser caps, e.g. `e10=209644284,e2=838577136` (an analyser not named has no
    work cap); a single number keeps the earlier behaviour (same cap for e2 and e10).
usage:
  python eap_plan_gen_wb.py analyze JOBS.json RAWDIR REPORT.csv [--max-steps 3000000] [--analysers v1,e2,e10]
         [--wk 1,0,...] [--max-work inf] [--valve-cpu S] [--valve-rss-mb M] [--tag T]       (sequential, one process)
  python eap_plan_gen_wb.py produce JOBS.json OUTDIR REPORT.csv --chain v1e10 --wk ... --max-work K [--cap-v1 N] [--tag T]
JOBS.json: list of code hashes (or {id, code}); byte code from $EAP_CODES/<code>.hex.
"""
import os, sys, json, time, pickle, csv, argparse, resource, math

HERE = os.path.dirname(os.path.abspath(__file__))
SASDIR = os.path.join(os.path.dirname(HERE), 'analyzer')
CODES = os.environ.get('EAP_CODES', 'codes')   # directory of <codehash>.hex files
CODES_ALT = [d for d in os.environ.get('EAP_CODES_ALT', '').split(':') if d]
MAX_ALTS = 32
CAPS = dict(max_forks=200_000, max_pc_visits=1000)
V1_CAPS = dict(max_forks=200_000, max_pc_visits=1000)
M64 = (1 << 64) - 1


# ---------------------------------------------------------------- canonical order (runtime-independent)
import hashlib
_STR = {}
def _sh_str(x):
    h = _STR.get(x)
    if h is None: h = _STR[x] = int.from_bytes(hashlib.blake2b(x.encode('utf-8', 'surrogatepass'), digest_size=8).digest(), 'little')
    return h


def _mix(hs):
    """explicit 64-bit combination of element hashes (FNV-1a style over 64-bit words with a final avalanche)"""
    h = 0xCBF29CE484222325 ^ len(hs)
    for x in hs:
        h = ((h ^ (x & M64)) * 0x100000001B3) & M64
        h ^= h >> 29
    h = (h * 0xBF58476D1CE4E5B9) & M64
    return h ^ (h >> 31)


def shash_factory():
    """deterministic structural hash of analyser records: ints by value (mod 2^64, sign folded), strings by blake2b,
    tuples by _mix over the element hashes; memoised by object identity (records are interned)"""
    memo = {}
    def sh(x):
        if isinstance(x, tuple):
            r = memo.get(id(x))
            if r is not None and r[0] is x: return r[1]
            h = _mix([sh(i) for i in x]); memo[id(x)] = (x, h); return h
        if isinstance(x, bool): return 0xB0010 + int(x)
        if isinstance(x, int): return (x & M64) ^ ((x >> 64) & M64) ^ (0x5EED if x < 0 else 0)
        if isinstance(x, str): return _sh_str(x)
        if x is None: return 0x4E4F4E45
        if isinstance(x, bytes): return int.from_bytes(hashlib.blake2b(x, digest_size=8).digest(), 'little')
        if isinstance(x, (frozenset, set)): return _mix(sorted(sh(i) for i in x))
        return _sh_str(repr(x))
    return sh


def csorted(recs, sh):
    """records sorted by structural hash; equal hashes of distinct records (collisions) fall back to repr order"""
    out = sorted(recs, key=sh)
    for i in range(1, len(out)):
        if sh(out[i]) == sh(out[i - 1]) and out[i] != out[i - 1]:
            return sorted(recs, key=lambda r: (sh(r), repr(r)))
    return out


def canon_factory():
    memo = {}
    def canon(e):
        r = memo.get(e)
        if r is not None: return r
        r = tuple(canon(x) if isinstance(x, tuple) else x for x in e) if isinstance(e, tuple) else e
        memo[r] = r
        return r
    return canon


def compact_det(s):
    """compact_summaries.compact with deterministic constraint ids and tie-breaking (same output schema, compact == 2);
    unchanged from eap_plan_gen.compact_det except the order key"""
    import tiers as TIERS
    canon = canon_factory()
    table = {}; tab = []
    def cons_ids(cons):
        out = []
        for e, w in cons:
            k = (canon(e), w); i = table.get(k)
            if i is None: i = table[k] = len(tab); tab.append(k)
            out.append(i)
        return tuple(out)
    sh = shash_factory()
    sites = csorted(s['sites'], sh); calls = csorted(s['calls'], sh)
    site_groups = {}
    for pc, op, key, cons in sites:
        g = site_groups.setdefault(canon(key), [set(), []]); g[0].add((pc, op)); g[1].append(frozenset(cons_ids(cons)))
    call_groups = {}
    for pc, kind, to, aw, asz, cons in calls:
        aw2 = None if aw is None else tuple((canon(rel) if isinstance(rel, tuple) else rel, canon(v), nb) for rel, v, nb in aw)
        sig = (kind, canon(to), aw2, canon(asz) if isinstance(asz, tuple) else asz)
        g = call_groups.setdefault(sig, [set(), []]); g[0].add(pc); g[1].append(frozenset(cons_ids(cons)))
    def prune(alts):
        alts = sorted(set(alts), key=lambda a: (len(a), tuple(sorted(a)))); kept = []
        for a in alts:
            if not any(k <= a for k in kept): kept.append(a)
            if len(kept) >= MAX_ALTS: break
        return [tuple(sorted(a)) for a in kept]
    tab_tier = [TIERS.tier(TIERS.expr_flags(e)) for e, _ in tab]
    def ctiers(alts): return [max((tab_tier[i] for i in a), default=0) for a in alts]
    sgs = []
    for key, g in site_groups.items():
        alts = prune(g[1]); sgs.append((key, sorted(g[0]), alts, (TIERS.site_tier(key), ctiers(alts))))
    cgs = []
    for sig, g in call_groups.items():
        kind, to, aw, asz = sig; alts = prune(g[1])
        kt = TIERS.tier(TIERS.expr_flags(asz if isinstance(asz, tuple) else None, TIERS.expr_flags(to)))
        cgs.append((sig, sorted(g[0]), alts, (kt, TIERS.call_tier(to, aw, asz), ctiers(alts))))
    return {'site_groups': sgs, 'call_groups': cgs, 'n_records_raw': (len(sites), len(calls)),
            'n_alts': (sum(len(g[2]) for g in sgs), sum(len(g[2]) for g in cgs)), 'cons_table': tab, 'compact': 2,
            'code_len': s['code_len'], 'analysis_s': 0.0, 'stats': s.get('stats', {})}


# ---------------------------------------------------------------- analysis
class StampSet(set):
    """set that records, at the first insertion of every element, the number of work checks the owner has done (v1: step
    count), and counts record work units (1 + path-constraint length) on the owner"""
    __slots__ = ('owner', 'stamp', 'wu')
    def __init__(self, owner):
        super().__init__(); self.owner = owner; self.stamp = {}; self.wu = hasattr(owner, 'cw')
    def add(self, x):
        if x not in self:
            o = self.owner
            if self.wu:
                self.stamp[x] = len(o._chks); o.cw[3] += 1 + len(x[-1])
            else:
                self.stamp[x] = o.steps
            super().add(x)


def _reset(M):
    for n in ('_intern', '_size', '_order', '_IDX_CACHE'):
        d = getattr(M, n, None)
        if isinstance(d, dict): d.clear()


class Valve(Exception): pass


def analyze_one(code, max_steps, analysers, max_work=float('inf'), wk=None, max_steps_v1=None, valve_cpu=None, valve_rss_mb=None):
    """-> {name: {'sites': [(rec, stamp)], 'calls': [...], 'steps', 'forks', 'work', 'truncated', 'valve', 'cpu', 'marks'}}"""
    import evm_static as E1, evm_static_v2 as E2, evm_static_v210 as E10
    assert os.path.dirname(E2.__file__) == SASDIR, E2.__file__
    out = {}
    for name in analysers:
        M = {'v1': E1, 'e2': E2, 'e10': E10}[name]
        _reset(M)
        c0 = time.process_time()
        if name == 'v1':
            a = M.Analyzer(code, max_steps=max_steps_v1 if max_steps_v1 is not None else max_steps, time_budget=float('inf'), **V1_CAPS)
        else:
            a = M.Analyzer(code, max_steps=max_steps, time_budget=float('inf'), **CAPS)
            a.max_work = max_work.get(name, float('inf')) if isinstance(max_work, dict) else max_work; a.wk = tuple(wk) if wk else None
            if valve_cpu or valve_rss_mb:   # exploration only: wrap the deterministic check with a CPU / RSS valve
                chk = a._wchk; lim_cpu = c0 + valve_cpu if valve_cpu else float('inf'); lim_rss = valve_rss_mb or float('inf')
                def _chk(work, chk=chk, a=a, M=M):
                    chk(work)
                    if (a.steps & 0xFFF) == 0 and (time.process_time() > lim_cpu or M._rss_mb() > lim_rss):
                        a.valve = 'cpu' if time.process_time() > lim_cpu else 'rss'; raise M.Budget()
                a._wchk = _chk
        a.valve = ''
        a.sites = StampSet(a); a.calls = StampSet(a)
        t0 = time.process_time()
        a.run()
        cpu = time.process_time() - c0
        rec = dict(steps=a.steps, forks=a.forks, truncated=bool(a.truncated), valve=a.valve, cpu=cpu, cpu_init=t0 - c0,
                   work=getattr(a, 'w_chk', None), cw=tuple(getattr(a, 'cw', ())), chks=getattr(a, '_chks', None),
                   marks=[(m[0], m[1] - t0) + tuple(m[2:]) for m in a._marks],
                   sites=[(r, a.sites.stamp[r]) for r in a.sites], calls=[(r, a.calls.stamp[r]) for r in a.calls])
        if name != 'v1':   # final work (not only at the last check), for cost models
            cw = a.cw; w = a.wk or M.WK_DEFAULT
            rec['work_end'] = a.steps * w[0] + sum(k * c for k, c in zip(w[1:], cw[1:]))
        out[name] = rec
        _reset(M)
    return out


def _has_fmp(e, E10):
    return 'OPQ:fmp' in E10.leaves(e)


CHAINS = {'v1e2e10': ('v1', 'e2', 'e10'), 'v1e10': ('v1', 'e10'), 'e2e10': ('e2', 'e10'), 'e10': ('e10',)}


def check_work(chks, wk):
    """work W_j at every check j = 0..len(chks) (W_0 = 0) under weights wk"""
    return [0] + [c[0] * wk[0] + sum(k * x for k, x in zip(wk[1:], c[1:])) for c in chks]


def assemble_one(raw, chain, cap, code_len, cap_v1=None, wk=None):
    """raw analyses -> uncompacted summary dict for a chain: e2/e10 records emitted after a check with W <= cap (weights
    wk), v1 records with step stamp <= cap_v1 (None: all)"""
    import evm_static_v210 as E10, predict
    sites = set(); calls = set(); stats = {}
    for name in CHAINS[chain]:
        r = raw[name]
        if name == 'v1':
            k = cap_v1 if cap_v1 is not None else float('inf')
            S = {rec for rec, st in r['sites'] if st <= k}; Cc = {rec for rec, st in r['calls'] if st <= k}
        else:
            W = check_work(r['chks'], wk or (1,) + (0,) * 8); k = cap.get(name, float('inf')) if isinstance(cap, dict) else cap
            S = {rec for rec, st in r['sites'] if W[st] <= k}; Cc = {rec for rec, st in r['calls'] if W[st] <= k}
        if name == 'e10':
            S = {rec for rec in S if not _has_fmp(rec[2], E10)}; Cc = {rec for rec in Cc if not _has_fmp(rec[2], E10)}
        if name == 'v1':
            Cc = {predict.convert_v1_call(rec) for rec in Cc}
        sites |= S; calls |= Cc
        stats[name] = dict(n_sites=len(S), n_calls=len(Cc))
    return {'sites': sites, 'calls': calls, 'code_len': code_len, 'stats': {'exp095': dict(chain=chain, cap=cap, cap_v1=cap_v1, per=stats)}}


def _setup(as_gib):
    os.environ['EVM_STATIC'] = 'v2'
    sys.path.insert(0, SASDIR)
    if as_gib:
        lim = int(as_gib * (1 << 30)); resource.setrlimit(resource.RLIMIT_AS, (lim, lim))


FIELDS = ['id', 'tag', 'cpu', 'cpu_analyse', 'code_len', 'n_site_groups', 'n_call_groups', 'bytes', 'sha256'] + \
         [f'{n}_{k}' for n in ('v1', 'e2', 'e10') for k in ('cpu', 'steps', 'forks', 'work', 'trunc', 'valve', 'sites', 'calls')] + \
         ['error', 'runtime', 'hashseed', 'cpus', 'as_gib']


def _row_common(row, raw):
    for n, r in raw.items():
        if isinstance(r, dict):
            row.update({f'{n}_cpu': r['cpu'], f'{n}_steps': r['steps'], f'{n}_forks': r['forks'], f'{n}_work': r.get('work_end', r['work']),
                        f'{n}_trunc': int(r['truncated']), f'{n}_valve': r['valve'], f'{n}_sites': len(r['sites']), f'{n}_calls': len(r['calls'])})


def _jobs(path):
    j = json.load(open(path))
    return [{'id': x, 'code': x} if isinstance(x, str) else x for x in j]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['analyze', 'produce'])
    ap.add_argument('jobs'); ap.add_argument('out'); ap.add_argument('report')
    ap.add_argument('--max-steps', type=int, default=3_000_000); ap.add_argument('--analysers', default='v1,e2,e10')
    ap.add_argument('--wk', default=None); ap.add_argument('--max-work', default='inf')
    ap.add_argument('--chain', default='v1e10'); ap.add_argument('--cap-v1', type=int, default=None)
    ap.add_argument('--valve-cpu', type=float, default=None); ap.add_argument('--valve-rss-mb', type=float, default=None)
    ap.add_argument('--as-gib', type=float, default=0); ap.add_argument('--tag', default='')
    A = ap.parse_args()
    _setup(A.as_gib)
    wk = tuple(int(x) for x in A.wk.split(',')) if A.wk else None
    A.max_work = {k: float(v) for k, v in (x.split('=') for x in A.max_work.split(','))} if '=' in A.max_work else float(A.max_work)
    jobs = _jobs(A.jobs); os.makedirs(A.out, exist_ok=True)
    done = set()
    if os.path.exists(A.report):
        done = {r['id'] for r in csv.DictReader(open(A.report))}
    jobs = [j for j in jobs if j['id'] not in done]
    new = not os.path.exists(A.report)
    runtime = f"{sys.implementation.name}-{'.'.join(map(str, sys.version_info[:3]))}"
    cpus = ','.join(map(str, sorted(os.sched_getaffinity(0))))
    print(f'{A.mode} jobs {len(jobs)} runtime {runtime} cpus {cpus}', flush=True)
    t0 = time.time()
    with open(A.report, 'a', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction='ignore')
        if new: w.writeheader()
        for i, job in enumerate(jobs, 1):
            row = {'id': job['id'], 'tag': A.tag, 'runtime': runtime, 'hashseed': os.environ.get('PYTHONHASHSEED', ''), 'cpus': cpus, 'as_gib': A.as_gib}
            try:
                cf = next((f for f in [f"{CODES}/{job['code']}.hex"] + [f"{d}/{job['code']}.hex" for d in CODES_ALT] if os.path.exists(f)), f"{CODES}/{job['code']}.hex")
                code = bytes.fromhex(open(cf).read().strip().removeprefix('0x'))
                c = time.process_time()
                if A.mode == 'analyze':
                    raw = analyze_one(code, A.max_steps, tuple(A.analysers.split(',')), max_work=A.max_work, wk=wk,
                                      valve_cpu=A.valve_cpu, valve_rss_mb=A.valve_rss_mb)
                    row.update(cpu=time.process_time() - c, code_len=len(code)); _row_common(row, raw)
                    raw['code_len'] = len(code); p = f"{A.out}/{job['id']}.raw.pkl"
                    data = raw
                else:
                    raw = analyze_one(code, A.max_steps, CHAINS[A.chain], max_work=A.max_work, wk=wk, max_steps_v1=A.cap_v1)
                    t_an = time.process_time() - c
                    s = compact_det(assemble_one(raw, A.chain, A.max_work, len(code), cap_v1=A.cap_v1, wk=wk))
                    row.update(cpu=time.process_time() - c, cpu_analyse=t_an, code_len=len(code),
                               n_site_groups=len(s['site_groups']), n_call_groups=len(s['call_groups'])); _row_common(row, raw)
                    p = f"{A.out}/{job['id']}.pkl"; data = s
                b = pickle.dumps(data, protocol=5)
                tmp = p + f'.tmp{os.getpid()}'
                with open(tmp, 'wb') as q: q.write(b)
                os.replace(tmp, p)
                row.update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
            except MemoryError:
                row['error'] = 'MemoryError'
            except Exception as e:
                row['error'] = repr(e)[:160]
            w.writerow(row); fh.flush()
            if i % 50 == 0 or row.get('error'):
                print(f'[{i}/{len(jobs)} {time.time() - t0:.0f}s]', row['id'][:12], row.get('error', ''), flush=True)
    print(f'DONE {len(jobs)} {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
