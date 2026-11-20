"""Concretize storage-access summaries for a transaction and compare with prestate ground truth.

Levels:
  L0  entry frame, class-A keys only (calldata/caller/block env)          -> no state reads at all
  L1  entry frame, + class-B keys resolved through a storage oracle         -> iterative "read-then-derive" prefetch
  L2  L1 + follow CALL/STATICCALL/DELEGATECALL whose target and calldata are derivable (recursive, depth<=4)

Analyzer version is selected by env EVM_STATIC=v1|v2 (default v1):
  v1  evm_static.py,     cache data/summaries.pkl
  v2  evm_static_v2.py,  cache data/summaries_v2.pkl   (base-pointer memory, regions, IDX key families, EIP-7702)
"""
from __future__ import annotations
import os, sys, json, gzip, pickle, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))

VERSION = os.environ.get('EVM_STATIC', 'v1')
if VERSION == 'v2':
    import evm_static_v2 as ES
    SUMMARY_CACHE = "data/summaries_v2.pkl"
    ANALYZE_KW = dict(max_steps=3_000_000, max_forks=200_000, max_pc_visits=1000,
                      time_budget=float(os.environ.get('ANALYZE_TIME_BUDGET', '30')))
else:
    import evm_static as ES
    SUMMARY_CACHE = "data/summaries.pkl"
    ANALYZE_KW = dict(max_steps=3_000_000, max_forks=200_000, max_pc_visits=1000, time_budget=60)
analyze, evaluate, Unknown, classify, is_c, keccak256 = ES.analyze, ES.evaluate, ES.Unknown, ES.classify, ES.is_c, ES.keccak256
_idx_ids_raw = getattr(ES, 'idx_ids', lambda e, acc=None: set())
_idx_ids_c = getattr(ES, 'idx_ids_c', lambda e: frozenset())
def idx_ids(e, acc=None):
    r = _idx_ids_c(e)
    if acc is not None: acc |= r; return acc
    return set(r)
eval_region = getattr(ES, 'eval_region', None)

CODES = os.environ.get("CODES_DIR", "data/codes")   # Phase 12: env override for the C2 code dir (default unchanged)
# cost-model knobs (env-overridable; defaults reproduce the v2 default operating point)
MAX_FAMILY = int(os.environ.get('MAX_FAMILY', '4096'))          # max iterations enumerated per loop index
MAX_FAMILY_CALLS = int(os.environ.get('MAX_FAMILY_CALLS', '512'))  # max call instances per family call record
MAX_DEPTH = int(os.environ.get('MAX_DEPTH', '4'))               # CALL-following depth
DYN_ALLOW = os.environ.get('DYN_ALLOW', '1') != '0'             # follow calls whose arg buffer has unknown words
CALLEE_L1 = os.environ.get('CALLEE_L1', '1') != '0'            # allow the one-hop storage oracle inside
                                                               # FOLLOWED frames too (default: as before);
                                                               # CALLEE_L1=0 restricts L1 to the entry frame
FOLLOW_UNKNOWN_ARGS = os.environ.get('FOLLOW_UNKNOWN_ARGS', '0') != '0'   # v2.1: follow known-target calls with an unreconstructable payload
CALL_IGNORE_CONS = os.environ.get('CALL_IGNORE_CONS', '0') != '0'   # v2.1: follow a call whose target concretizes even if no recorded path constraint set holds
# ---- Phase 7: record transferability tiers (scripts/tiers.py). Tier fields are read from the summary when the
# store carries them (build_guided_summaries.py --tiers) and computed from the expressions otherwise.
#   TIER_POLICY  all   ignore tiers (legacy behaviour; T2 keys/targets still fail to evaluate and are dropped)
#                t0t1  drop T2 records (default);  t0  additionally drop T1 (storage-dependent) records
#   TIER_CONS=1  apply the policy to the CONSTRAINT tier too: an alternative gated by an unverifiable (T2)
#                constraint set is not used (legacy: _cons_ok skips what it cannot evaluate)
#   TIER_PAYLOAD=1  apply the policy to the call PAYLOAD tier (arg words) as well as to the target
#   TIER_HOLE_UNKNOWN=1  bytes of a reconstructed callee buffer that no recorded arg word covers are marked
#                unknown (legacy: they read as zero, exactly as unwritten memory did in the producing pass)
#   FAMILY_IFREE_CONS=1  check the index-free constraints of a family record before enumerating its indices
#                (legacy: _family_assignments silently ignores every constraint without a loop index)
#   PRED_TAGS=1  record, per predicted slot, the provenance tag of its first producer in info['tags']
import tiers as TIERS
from evm_static_v2 import leaves as _leaves
TIER_POLICY = os.environ.get('TIER_POLICY', 't0t1')
TIER_MAX = {'all': 2, 't0t1': 1, 't0': 0}[TIER_POLICY]
TIER_CONS = os.environ.get('TIER_CONS', '0') != '0'
TIER_PAYLOAD = os.environ.get('TIER_PAYLOAD', '0') != '0'
TIER_HOLE_UNKNOWN = os.environ.get('TIER_HOLE_UNKNOWN', '0') != '0'
FAMILY_IFREE_CONS = os.environ.get('FAMILY_IFREE_CONS', '0')
# '0' legacy | '1' every index-free constraint | 'sel' | 'sel+cv+cds' ... a '+'-separated list of constraint CLASSES
# (see Predictor._cons_class): a family record is skipped when an index-free constraint of a listed class fails.
_FIC_CLASSES = frozenset({'sel', 'selcmp', 'cv', 'cds', 'sl', 'cd', 'env', 'oth'})
if FAMILY_IFREE_CONS == '0': FAMILY_IFREE_CONS, FIC_CLASSES = 0, frozenset()
elif FAMILY_IFREE_CONS == '1': FAMILY_IFREE_CONS, FIC_CLASSES = 1, _FIC_CLASSES
else:
    FIC_CLASSES = frozenset(FAMILY_IFREE_CONS.split('+')); assert FIC_CLASSES <= _FIC_CLASSES, FAMILY_IFREE_CONS
    FAMILY_IFREE_CONS = 2
PRED_TAGS = os.environ.get('PRED_TAGS', '0') != '0'
DESIGNATOR = bytes.fromhex('ef0100')

V1_CACHE = "data/summaries.pkl"
_v1_cache = None
def v1_summary(codehash):
    """v1 summary record (if the v1 cache exists) -- used to union path records under v2 (guards budget truncation)."""
    global _v1_cache
    if _v1_cache is None:
        _v1_cache = pickle.load(open(V1_CACHE, 'rb')) if (VERSION == 'v2' and os.path.exists(V1_CACHE)) else {}
    return _v1_cache.get(codehash)

def convert_v1_call(rec):
    """v1 call record -> v2 format: argwords (rel, expr, nbytes) in write order, argsize expr"""
    pc, kind, to, aw, asz, cons = rec
    if aw is None: return (pc, kind, to, None, None, cons)
    if asz == -1:   # ('FWD', src, size): verbatim calldata forwarding
        return (pc, kind, to, ((0, ('REGION', 'CD', aw[1], aw[2]), None),), aw[2], cons)
    return (pc, kind, to, tuple((rel, e, 32) for rel, e in aw), ('C', asz), cons)

def merge_v1(s2, s1):
    """union v1 path records into a v2 summary (in place); records the counts"""
    if not s1: return s2
    sites = set(s2['sites']); calls = set(s2['calls'])
    n0, c0 = len(sites), len(calls)
    sites |= set(s1['sites']); calls |= {convert_v1_call(r) for r in s1['calls']}
    s2['sites'] = sorted(sites, key=lambda x: x[0]); s2['calls'] = sorted(calls, key=lambda x: x[0])
    s2['stats']['v1_merged_sites'] = len(sites) - n0; s2['stats']['v1_merged_calls'] = len(calls) - c0
    s2['stats']['v1_sites_covered'] = s1['stats'].get('n_sites_covered')
    return s2

SUMMARY_DIR = os.environ.get('SUMMARY_DIR') or SUMMARY_CACHE[:-4] + '.d'   # per-codehash pickles (lazy, memory-frugal)

class SummaryStore:
    def __init__(self, cap=1000, time_budget=None, max_loaded=80,
                 max_loaded_bytes=int(os.environ.get('SUMMARY_MAX_BYTES', '120000000'))):
        self.lazy = os.path.isdir(SUMMARY_DIR)
        self.cache = {} if self.lazy else (pickle.load(open(SUMMARY_CACHE, 'rb')) if os.path.exists(SUMMARY_CACHE) else {})
        self.kw = dict(ANALYZE_KW); self.kw['max_pc_visits'] = cap
        if time_budget is not None: self.kw['time_budget'] = time_budget
        self.dirty = 0; self.codes = {}; self.max_loaded = max_loaded; self.max_loaded_bytes = max_loaded_bytes
        self.loaded_bytes = 0; self.sizes = {}
    def _lazy_get(self, codehash):
        p = f"{SUMMARY_DIR}/{codehash}.pkl"
        if not os.path.exists(p): return None
        sz = os.path.getsize(p)
        while self.cache and (len(self.cache) >= self.max_loaded or self.loaded_bytes + sz > self.max_loaded_bytes):
            k = next(iter(self.cache)); del self.cache[k]; self.loaded_bytes -= self.sizes.pop(k, 0)
        self.sizes[codehash] = sz; self.loaded_bytes += sz
        s = pickle.load(open(p, 'rb'))
        if s.get('compact') == 2:   # grouped format: records grouped by key / call signature, constraint ids into a table
            tab = s['cons_table']
            tab_tier = [TIERS.tier(TIERS.expr_flags(e)) for e, _ in tab]      # constraint tier per table entry
            def _ctier(a): return max((tab_tier[i] for i in a), default=0)
            sg = {}
            for grp in s['site_groups']:
                key, pcs, alts = grp[0], grp[1], grp[2]
                tf = grp[3] if len(grp) > 3 else None          # stored tier field: (ktier, [ctier per alt])
                key_ids = frozenset(idx_ids(key)); ids = set(key_ids); cons_alts = []
                for a in alts:
                    cons = tuple(tab[i] for i in a); cons_alts.append(cons)
                    for e, _ in cons: idx_ids(e, ids)
                ktier = tf[0] if tf else TIERS.site_tier(key)
                ctiers = tuple(tf[1]) if tf else tuple(_ctier(a) for a in alts)
                sg[key] = (classify(key), ids, key_ids, cons_alts, ktier, ctiers)
            cg = {}
            for grp in s['call_groups']:
                sig, pcs, alts = grp[0], grp[1], grp[2]
                tf = grp[3] if len(grp) > 3 else None          # (ktier, ptier, [ctier per alt])
                kind, target, argwords, argsize = sig
                if argwords is None: kids = set()
                else:
                    kids = _all_ids([target, argsize if not isinstance(argsize, int) else None], ())
                    for rel, v, nb in argwords:
                        if isinstance(rel, int): idx_ids(v, kids)
                ids = set(kids); cons_alts = []
                for a in alts:
                    cons = tuple(tab[i] for i in a); cons_alts.append(cons)
                    for e, _ in cons: idx_ids(e, ids)
                if tf: ktier, ptier, ctiers = tf[0], tf[1], tuple(tf[2])
                else:
                    ktier = TIERS.tier(TIERS.expr_flags(argsize if isinstance(argsize, tuple) else None, TIERS.expr_flags(target)))
                    ptier = TIERS.call_tier(target, argwords, argsize)
                    ctiers = tuple(_ctier(a) for a in alts)
                cg[sig] = (ids, kids, cons_alts, ktier, ptier, ctiers)
            s['_meta'] = (sg, cg); s['sites'] = (); s['calls'] = ()
        elif s.get('compact'):   # constraint tuples stored as indices into a per-summary table
            tab = s['cons_table']
            s['sites'] = [(pc, op, key, tuple(tab[i] for i in ci)) for pc, op, key, ci in s['sites']]
            s['calls'] = [(pc, kind, to, aw, asz, tuple(tab[i] for i in ci)) for pc, kind, to, aw, asz, ci in s['calls']]
        self.cache[codehash] = s
        return s
    def code(self, codehash: str):
        c = self.codes.get(codehash)
        if c is None:
            p = f"{CODES}/{codehash}.hex"
            if not os.path.exists(p): return None
            c = bytes.fromhex(open(p).read())
            if len(self.codes) > 4000: self.codes.clear()
            self.codes[codehash] = c
        return c
    def designator(self, codehash: str):
        """EIP-7702: code == 0xef0100 || address  -> delegate address hex, else None"""
        c = self.code(codehash)
        if c is not None and len(c) == 23 and c[:3] == DESIGNATOR: return '0x' + c[3:].hex()
        return None
    def get(self, codehash: str):
        if codehash in self.cache: return self.cache[codehash]
        if self.lazy:
            s = self._lazy_get(codehash)
            if s is not None: return s
        code = self.code(codehash)
        if code is None: return None
        t = time.perf_counter()
        a = analyze(code, **self.kw)
        s = {'sites': sorted(a.sites, key=lambda x: x[0]), 'calls': sorted(a.calls, key=lambda x: x[0]),
             'stats': a.summary(), 'code_len': len(code), 'analysis_s': time.perf_counter() - t}
        if VERSION == 'v2': merge_v1(s, v1_summary(codehash))
        self.cache[codehash] = s; self.dirty += 1
        if self.lazy:   # per-file store: persist immediately (atomic rename; safe across shards)
            tmp = f"{SUMMARY_DIR}/{codehash}.pkl.tmp{os.getpid()}"; pickle.dump(s, open(tmp, 'wb')); os.replace(tmp, f"{SUMMARY_DIR}/{codehash}.pkl")
        elif self.dirty >= 20: self.flush()
        return s
    def flush(self):
        if self.lazy: return
        tmp = SUMMARY_CACHE + f'.tmp{os.getpid()}'; pickle.dump(self.cache, open(tmp, 'wb')); os.replace(tmp, SUMMARY_CACHE); self.dirty = 0

def hx(v: int, n=32): return '0x' + v.to_bytes(n, 'big').hex()

class Oracle:
    """storage / code oracle at a fixed block state (block-1 of the tx's block). Counts reads.
    File mode (env ORACLE_FILE=path.json, {"addr:keyhex": valuehex}): values served from the file; misses are appended to
    ORACLE_MISS (one 'addr keyhex' per line) and raise Unknown, so a later fetch pass can fill them.
    Dump mode (env ORACLE_DUMP set): every value served over RPC is recorded in Oracle.DUMP so that a later pass can run
    offline off the same state (keys match the file-mode format: 'addr:keyhex' and 'code:addr')."""
    FILE = None; MISS = None; DUMP = None
    def __init__(self, rpc, block_tag: str, addr2code: dict):
        if Oracle.DUMP is None and os.environ.get('ORACLE_DUMP'): Oracle.DUMP = {}
        self.rpc = rpc; self.tag = block_tag; self.addr2code = addr2code
        self.storage_cache = {}; self.code_cache = {}; self.reads = 0; self.rpc_s = 0.0
        if Oracle.FILE is None and os.environ.get('ORACLE_FILE'):
            Oracle.FILE = json.load(open(os.environ['ORACLE_FILE'])) if os.path.exists(os.environ['ORACLE_FILE']) else {}
            Oracle.MISS = open(os.environ.get('ORACLE_MISS', os.environ['ORACLE_FILE'] + f'.miss{os.getpid()}'), 'a')
    def sload(self, addr: str, key: int) -> int:
        k = (addr, key)
        if k not in self.storage_cache:
            if Oracle.FILE is not None:
                v = Oracle.FILE.get(f"{self.tag}:{addr}:{hx(key)}")
                if v is None:
                    Oracle.MISS.write(f"{self.tag} {addr} {hx(key)}\n"); raise Unknown('no-oracle')
                self.reads += 1; self.storage_cache[k] = int(v, 16); return self.storage_cache[k]
            if self.rpc is None: raise Unknown('no-oracle')
            self.reads += 1
            _t = time.perf_counter()
            self.storage_cache[k] = int(self.rpc("eth_getStorageAt", [addr, hx(key), self.tag]), 16)
            self.rpc_s += time.perf_counter() - _t
            if Oracle.DUMP is not None: Oracle.DUMP[f"{self.tag}:{addr}:{hx(key)}"] = hex(self.storage_cache[k])
        return self.storage_cache[k]
    def codehash(self, addr: str):
        addr = addr.lower()
        if addr in self.addr2code: return self.addr2code[addr]
        if addr not in self.code_cache:
            if self.rpc is None:
                if Oracle.FILE is not None:
                    v = Oracle.FILE.get(f"code:{addr}")
                    if v is None: Oracle.MISS.write(f"{self.tag} {addr} code\n"); return None
                    return v or None
                return None
            _t = time.perf_counter()
            code = self.rpc("eth_getCode", [addr, self.tag])
            self.rpc_s += time.perf_counter() - _t
            cb = bytes.fromhex(code[2:]) if code and code != '0x' else b''
            ch = keccak256(cb).hex() if cb else None
            if ch and not os.path.exists(f"{CODES}/{ch}.hex"):
                open(f"{CODES}/{ch}.hex", 'w').write(cb.hex())
            self.code_cache[addr] = ch
            if Oracle.DUMP is not None: Oracle.DUMP[f"code:{addr}"] = ch or ""
        return self.code_cache[addr]

def build_env(tx, blk, address: str, caller: str, calldata: bytes, value: int):
    return {'CALLER': int(caller, 16), 'ORIGIN': int(tx['from'], 16), 'ADDRESS': int(address, 16),
            'CALLVALUE': value, 'CALLDATASIZE': len(calldata), 'NUMBER': blk['number'],
            'TIMESTAMP': int(blk['timestamp'], 16), 'CHAINID': 1, 'COINBASE': int(blk.get('miner', '0x0'), 16),
            'GASLIMIT': int(blk.get('gasLimit', '0x0'), 16), 'BASEFEE': int(blk.get('baseFeePerGas', '0x0'), 16),
            'PREVRANDAO': int(blk.get('mixHash', '0x0'), 16), 'BLOBBASEFEE': 1, 'CODESIZE': 0}

def _all_ids(rec_exprs, cons):
    ids = set()
    for e in rec_exprs:
        if e is not None: idx_ids(e, ids)
    for e, _ in cons: idx_ids(e, ids)
    return ids

class Budget(Exception): pass

TX_TIME_BUDGET_S = float(os.environ.get('TX_TIME_BUDGET_S', '3'))
TX_MAX_FRAMES = 64
TX_MAX_FOLLOWED = 500
# Phase 14 improvement 1 (default off): a tx whose prediction enters a codehash listed in RELAX_CH_FILE (summaries
# rewritten by analyzer v2.11) gets the frame budget RELAX_MAX_FRAMES instead of TX_MAX_FRAMES from that frame on.
RELAX_CH = frozenset(open(os.environ['RELAX_CH_FILE']).read().split()) if os.environ.get('RELAX_CH_FILE') else frozenset()
RELAX_MAX_FRAMES = int(os.environ.get('RELAX_MAX_FRAMES', '128'))
# Phase 15 (diagnostics only, default off; prediction unchanged): SLICE_REF_DIR=<v2.10 store> marks every constraint
# alternative of the loaded (v2.12) summary that is not in the reference summary as 'sliced', labelled with the
# classes of the constraints it lacks relative to its smallest reference superset. A record admitted ONLY by sliced
# alternatives tags its slots -- and, for a call, every slot predicted below the followed frame -- with
# via '<via>/sl:<classes>' (PRED_TAGS=1 -> eval_blocks <out>.tags.json), for precision attribution by class.
SLICE_REF_DIR = os.environ.get('SLICE_REF_DIR')
_SLREF = {}
def _slice_marks(codehash, meta):
    """{id(alt): dropped classes} for the sliced alternatives of a v2.12 summary's grouped meta"""
    p = f'{SLICE_REF_DIR}/{codehash}.pkl'
    if not os.path.exists(p): return {}
    ref = pickle.load(open(p, 'rb'))
    if ref.get('compact') == 2:
        tab = ref['cons_table']
        rs = {g[0]: [frozenset(tab[i] for i in a) for a in g[2]] for g in ref['site_groups']}
        rc = {g[0]: [frozenset(tab[i] for i in a) for a in g[2]] for g in ref['call_groups']}
    else: return {}
    out = {}
    for groups, refg in ((meta[0], rs), (meta[1], rc)):
        for k, v in groups.items():
            alts = v[3] if groups is meta[0] else v[2]
            ra = refg.get(k, [])
            rset = set(ra)
            for a in alts:
                fa = frozenset(a)
                if fa in rset: continue
                sup = [b for b in ra if fa <= b]
                if not sup: out[id(a)] = 'new'; continue
                b = min(sup, key=len)
                out[id(a)] = '+'.join(sorted({Predictor._cons_class(e, w) for e, w in b - fa})) or 'none'
    return out

class Predictor:
    def __init__(self, store: SummaryStore, oracle, level: int, max_depth=None):
        self.store = store; self.oracle = oracle; self.level = level
        self.max_depth = MAX_DEPTH if max_depth is None else max_depth
        self.reasons = defaultdict(int)
        self.stats = defaultdict(int)
        self._deadline = None; self._info = None; self._last_holes = 0; self._cur_call = (0, 1, 0); self._sltag = ''

    def _check_budget(self):
        if time.perf_counter() > self._deadline: raise Budget('time')
        if self._info['frames'] > (RELAX_MAX_FRAMES if self._info.get('relaxed') else TX_MAX_FRAMES): raise Budget('frames')
        if self._info['calls_followed'] > TX_MAX_FOLLOWED: raise Budget('followed')

    def predict_tx(self, tx, blk):
        """-> (set of (addr, slot_hex), info dict)"""
        pred = set(); info = {'frames': 0, 'calls_seen': 0, 'calls_followed': 0, 'sload_rounds': 0, 'family_sites': 0, 'family_calls': 0}
        if not tx.get('to'): return pred, info
        calldata = bytes.fromhex((tx.get('input') or '0x')[2:])
        to = tx['to'].lower()
        codehash = self.oracle.codehash(to) if self.oracle else None
        if codehash is None: self.reasons['no-code'] += 1; return pred, info
        self._deadline = time.perf_counter() + TX_TIME_BUDGET_S; self._info = info; info['budget'] = ''
        try:
            self._frame(tx, blk, to, codehash, tx['from'].lower(), calldata, int(tx.get('value') or '0x0', 16), pred, info, 0, set(), None)
        except Budget as b:
            info['budget'] = str(b); self.reasons['budget:' + str(b)] += 1
        return pred, info

    # ------------------------------------------------------------------ frame
    def _frame(self, tx, blk, address, codehash, caller, calldata, value, pred, info, depth, seen, cd_unknown, via='entry'):
        """execute summary of `codehash` in the storage context of `address`.
        `via` (tags only): how the frame was reached -- 'entry' | 'call' | 'call-unk' (payload has unknown words)
        | 'call-hole' (payload has bytes no arg word covers) | 'call-unk-hole'."""
        deleg = self.store.designator(codehash)
        if deleg is not None:                       # EIP-7702 delegated EOA: run delegate's code on the EOA's storage
            ch2 = self.oracle.codehash(deleg)
            if ch2 is None or ch2 == codehash: self.reasons['7702-no-target'] += 1; return
            self.stats['7702'] += 1
            codehash = ch2
        key = (address, codehash, calldata)
        if key in seen: return
        seen.add(key)
        summ = self.store.get(codehash)
        if summ is None: self.reasons['no-summary'] += 1; return
        if RELAX_CH and codehash in RELAX_CH: info['relaxed'] = 1
        info['frames'] += 1; self._check_budget()
        env = build_env(tx, blk, address, caller, calldata, value)
        ctx = {'calldata': calldata, 'env': env, 'idx': None, 'cd_unknown': cd_unknown or None, '_evcache': {}}
        if VERSION == 'v2': ctx['code'] = self.store.code(codehash)
        if self.level >= 1 and self.oracle is not None and (CALLEE_L1 or depth == 0):
            ctx['sload'] = lambda k, a=address: self.oracle.sload(a, k)
        cap = min(MAX_FAMILY, len(calldata) // 32 + 34)

        meta = summ.get('_meta')
        if meta is None: meta = summ['_meta'] = self._build_meta(summ)
        site_groups, call_groups = meta
        tags = info.setdefault('tags', {}) if PRED_TAGS else None
        slm = None
        if SLICE_REF_DIR:
            slm = summ.get('_slmark')
            if slm is None: slm = summ['_slmark'] = _slice_marks(codehash, meta)
        def _tag(slot, ktier, ctier, fam, ifree, idxmax=-1, selfail=0, failcls='', sl=''):
            if tags is not None and slot not in tags:
                v = via
                if SLICE_REF_DIR and (sl or self._sltag): v = f'{via}/sl:{sl or self._sltag}'
                tags[slot] = (depth, ktier, ctier, fam, ifree, v, idxmax, selfail, failcls)
        def _failing(cons):
            """classes of the index-free constraints of `cons` that evaluate to the opposite of what the path wants"""
            out = set()
            for e, w in cons:
                if idx_ids(e): continue
                try: v = evaluate(e, ctx) != 0
                except Unknown: continue
                if v != w: out.add(self._cons_class(e, w))
            return out
        def _reject(fc): return bool(fc & FIC_CLASSES)
        for kexpr, (cls, ids, key_ids, cons_alts, ktier, ctiers) in site_groups.items():
            if cls == 'C': self.reasons['key-dyn'] += 1; continue
            if cls == 'B' and self.level < 1: self.reasons['key-needs-state'] += 1; continue
            if ktier > TIER_MAX: self.reasons[f'key-tier{ktier}'] += 1; continue
            if TIER_CONS and TIER_MAX < 2:
                keep = [(c, t) for c, t in zip(cons_alts, ctiers) if t <= TIER_MAX]
                if not keep: self.reasons['key-cons-tier'] += 1; continue
                cons_alts, ctiers = [c for c, _ in keep], tuple(t for _, t in keep)
            if not ids:
                if tags is None:
                    if not any(self._cons_ok(c, ctx) for c in cons_alts): continue
                    ct = 0
                else:
                    okc = [(c, t) for c, t in zip(cons_alts, ctiers) if self._cons_ok(c, ctx)]
                    if not okc: continue
                    ok = [t for _, t in okc]
                    ct = min(ok)
                    slc = slm[id(okc[0][0])] if slm and all(id(c) in slm for c, _ in okc) else ''
                try: k = evaluate(kexpr, ctx)
                except Unknown as u: self.reasons['key-unknown:' + str(u)[:20]] += 1; continue
                slot = (address, hx(k)); pred.add(slot); _tag(slot, ktier, ct, 0, 1, sl=(slc if tags is not None else ''))
            else:
                asgs = {}
                for cons, ct in zip(cons_alts, ctiers):
                    ifree = 1; sf = 0; fc = frozenset()
                    if FAMILY_IFREE_CONS or tags is not None:
                        fc = frozenset(_failing(cons)); ifree = int(not fc); sf = int('sel' in fc)
                        if fc and _reject(fc): self.reasons['family-ifree-cons'] += 1; continue
                    for asg in self._family_assignments(ids, cons, ctx, cap, bool(key_ids), key_ids):
                        a = tuple(sorted((i, asg[i]) for i in key_ids))
                        prev = asgs.get(a)
                        if prev is None or (ct, -ifree, sf) < prev[:3]: asgs[a] = (ct, -ifree, sf, fc)
                for asg, (ct, nifree, sf, fc) in asgs.items():
                    ctx['idx'] = dict(asg)
                    try: k = evaluate(kexpr, ctx)
                    except Unknown as u: self.reasons['key-unknown:' + str(u)[:20]] += 1; continue
                    slot = (address, hx(k)); pred.add(slot); info['family_sites'] += 1
                    _tag(slot, ktier, ct, 1, -nifree, max(v for _, v in asg) if asg else -1, sf, '+'.join(sorted(fc)))
                ctx['idx'] = None

        if self.level >= 2 and depth < self.max_depth:
            for (kind, target, argwords, argsize), (ids, kids, cons_alts, ktier, ptier, ctiers) in call_groups.items():
                self._check_budget()
                if ktier > TIER_MAX: self.reasons[f'call-tier{ktier}'] += 1; continue
                if TIER_PAYLOAD and ptier > TIER_MAX: self.reasons[f'call-payload-tier{ptier}'] += 1; continue
                if TIER_CONS and TIER_MAX < 2:
                    keep = [c for c, t in zip(cons_alts, ctiers) if t <= TIER_MAX]
                    if not keep: self.reasons['call-cons-tier'] += 1; continue
                    cons_alts = keep
                if argwords is None:
                    if CALL_IGNORE_CONS or any(self._cons_ok(cons, ctx) for cons in cons_alts):
                        self.reasons['call-dyn-args'] += 1; info['calls_seen'] += 1
                        if FOLLOW_UNKNOWN_ARGS:   # target derivable, payload not: enter the callee with all calldata unknown
                            self._follow(tx, blk, address, caller, value, kind, target, None, None, ctx, pred, info, depth, seen)
                    continue
                if not ids:
                    if not (CALL_IGNORE_CONS or any(self._cons_ok(cons, ctx) for cons in cons_alts)): continue
                    info['calls_seen'] += 1; self._cur_call = (0, 1, 0)
                    old = self._sltag
                    if slm and not old:
                        okc = [c for c in cons_alts if self._cons_ok(c, ctx)]
                        if okc and all(id(c) in slm for c in okc): self._sltag = slm[id(okc[0])]
                    try:
                        self._follow(tx, blk, address, caller, value, kind, target, argwords, argsize, ctx, pred, info, depth, seen)
                    finally:
                        self._sltag = old
                else:
                    asgs = {}
                    for cons in cons_alts:
                        ifree = 1; sf = 0
                        if FAMILY_IFREE_CONS or tags is not None:
                            fc = frozenset(_failing(cons)); ifree = int(not fc); sf = int('sel' in fc)
                            if fc and _reject(fc): self.reasons['family-ifree-cons'] += 1; continue
                        for asg in self._family_assignments(ids, cons, ctx, cap, True, kids):
                            a = tuple(sorted((i, asg[i]) for i in kids))
                            prev = asgs.get(a)
                            if prev is None or (-ifree, sf) < prev: asgs[a] = (-ifree, sf)
                    for n, asg in enumerate(sorted(asgs)):
                        if n >= MAX_FAMILY_CALLS: break
                        self._check_budget()
                        ctx['idx'] = dict(asg); info['calls_seen'] += 1; info['family_calls'] += 1
                        self._cur_call = (1, -asgs[asg][0], asgs[asg][1])
                        self._follow(tx, blk, address, caller, value, kind, target, argwords, argsize, ctx, pred, info, depth, seen)
                    ctx['idx'] = None

    @staticmethod
    def _build_meta(summ):
        """group records by key / call signature; each group keeps its alternative constraint sets"""
        site_groups = {}
        for pc, op, kexpr, cons in summ['sites']:
            g = site_groups.get(kexpr)
            if g is None:
                key_ids = frozenset(idx_ids(kexpr))
                g = site_groups[kexpr] = (classify(kexpr), _all_ids([kexpr], ()), key_ids, [], TIERS.site_tier(kexpr), [])
            ids = g[1]
            for e, _ in cons: idx_ids(e, ids)
            g[3].append(cons); g[5].append(TIERS.cons_tier(cons))
        call_groups = {}
        for pc, kind, target, argwords, argsize, cons in summ['calls']:
            sig = (kind, target, argwords, argsize)
            g = call_groups.get(sig)
            if g is None:
                if argwords is None: kids = set()
                else:
                    kids = _all_ids([target, argsize if not isinstance(argsize, int) else None], ())
                    if VERSION == 'v2':
                        for rel, v, nb in argwords:
                            if isinstance(rel, int): idx_ids(v, kids)
                ktier = TIERS.tier(TIERS.expr_flags(argsize if isinstance(argsize, tuple) else None, TIERS.expr_flags(target)))
                g = call_groups[sig] = (set(kids), kids, [], ktier, TIERS.call_tier(target, argwords, argsize), [])
            for e, _ in cons: idx_ids(e, g[0])
            g[2].append(cons); g[5].append(TIERS.cons_tier(cons))
        site_groups = {k: (v[0], v[1], v[2], v[3], v[4], tuple(v[5])) for k, v in site_groups.items()}
        call_groups = {k: (v[0], v[1], v[2], v[3], v[4], tuple(v[5])) for k, v in call_groups.items()}
        return site_groups, call_groups

    @staticmethod
    def _cons_class(e, want):
        """Class of an index-free path constraint (Phase 7 §3.7):
        sel     EQ(selector, const) wanted true                      (function dispatch, exact)
        selcmp  any other comparison on SHR(224, CD[0])              (binary-search dispatch)
        cv      mentions CALLVALUE                                    (payable check)
        cds     mentions CALLDATASIZE                                 (ABI length check)
        sl      reads storage (SLOAD)                                 (state-dependent branch)
        cd      only calldata / constants otherwise                   (argument value check)
        env     only block/tx environment otherwise                   (CALLER/ORIGIN/NUMBER ...)
        oth     anything else"""
        if want and ES.Analyzer._sel_tag(e, None) is not None: return 'sel'
        def has_sel(x, d=0):
            if d > 64 or not isinstance(x, tuple) or not x: return False
            if x[0] == 'OP' and x[1] == 'SHR' and x[2] == ('C', 224) and x[3] == ('CD', ('C', 0)): return True
            return any(has_sel(y, d + 1) for y in x)
        L = _leaves(e)
        if has_sel(e): return 'selcmp'
        if 'CALLVALUE' in L: return 'cv'
        if 'CALLDATASIZE' in L: return 'cds'
        if 'SLOAD' in L: return 'sl'
        envs = {l for l in L if l in ES.ENV_KNOWN or l in ES.ENV_DYN}
        rest = L - envs - {'CD', 'REGION:CD', 'IDX'}
        if rest: return 'oth'
        if envs: return 'env'
        return 'cd'

    def _cons_ok(self, cons, ctx):
        cache = ctx.get('_evcache') if ctx.get('idx') is None else None
        for e, want in cons:
            if cache is not None:
                v = cache.get(id(e))
                if v is None:
                    try: v = evaluate(e, ctx) != 0
                    except Unknown: v = 2
                    cache[id(e)] = v
                if v == 2: continue
                if v != want: return False
                continue
            try: v = evaluate(e, ctx)
            except Unknown: continue          # over-approximate
            if (v != 0) != want: return False
        return True

    def _family_assignments(self, ids, cons, ctx, cap, key_has_idx, key_ids=()):
        """enumerate loop-index assignments satisfying the path constraints.
        ids only mentioned in constraints (exited loops) are fixed to their minimal satisfying value;
        ids in the key/args are enumerated: bounded satisfying set -> all of it, unbounded -> minimal (post-loop record)."""
        key_ids = sorted(set(key_ids) & set(ids)); ids = sorted(ids)
        per_id = {i: [] for i in ids}; multi = []
        for e, want in cons:
            ii = idx_ids(e)
            if not ii: continue
            if len(ii) == 1: per_id[next(iter(ii))].append((e, want))
            else: multi.append((e, want))
        cache = ctx.setdefault('_famcache', {})
        def sat_set(i):
            k = (i, tuple(per_id[i]))
            r = cache.get(k)
            if r is None:
                r = []
                for v in range(cap):
                    ctx['idx'] = {i: v}
                    if self._cons_ok(per_id[i], ctx): r.append(v)
                cache[k] = r
            return r
        fixed = {}
        for i in ids:
            if i in key_ids: continue
            ss = sat_set(i)
            if not ss: ctx['idx'] = None; return []
            fixed[i] = ss[0]
        if len(key_ids) > 2: self.reasons['family-too-many-ids'] += 1; ctx['idx'] = None; return []
        out = []
        if not key_ids:
            out = [dict(fixed)]
        else:
            sets = {i: sat_set(i) for i in key_ids}
            for i in key_ids:
                if not sets[i]: ctx['idx'] = None; return []
            unbounded = any((cap - 1) in sets[i] for i in key_ids)
            if unbounded:
                self.stats['family-unbounded'] += 1
                out = [{**fixed, **{i: sets[i][0] for i in key_ids}}]
            else:
                self.stats['family-bounded'] += 1
                if len(key_ids) == 1:
                    out = [{**fixed, key_ids[0]: v} for v in sets[key_ids[0]]]
                else:
                    a, b = key_ids
                    out = [{**fixed, a: va, b: vb} for va in sets[a][:96] for vb in sets[b][:96]]
        if multi:
            kept = []
            for asg in out:
                ctx['idx'] = asg
                if self._cons_ok(multi, ctx): kept.append(asg)
            out = kept
        ctx['idx'] = None
        return out

    def _follow(self, tx, blk, address, caller, value, kind, target, argwords, argsize, ctx, pred, info, depth, seen):
        try:
            t = evaluate(target, ctx) & ((1 << 160) - 1)
        except Unknown as u:
            self.reasons['call-unknown:' + str(u)[:20]] += 1; return
        if t < 256: self.reasons['call-precompile-or-zero'] += 1; return
        holes = 0
        if argwords is None:          # unknown payload: every calldata read in the callee stays unresolved
            buf, unknown = b'', [(0, 1 << 32)]
            self.stats['follow-unknown-args'] += 1
        else:
            try:
                buf, unknown = self._callargs(argwords, argsize, ctx)
            except Unknown as u:
                self.reasons['call-unknown:' + str(u)[:20]] += 1; return
            holes = self._last_holes
            for lo, hi in unknown:
                if lo < 4: self.reasons['call-selector-unknown'] += 1; return
            if unknown and not DYN_ALLOW: self.reasons['call-dyn-argword-blocked'] += 1; return
        if holes: self.stats['follow-with-holes'] += 1; self.stats['hole-bytes'] += holes
        via = 'call' + ('-unk' if unknown else '') + ('-hole' if holes else '')
        taddr = hx(t, 20)
        info['calls_followed'] += 1
        info.setdefault('targets', set()).add((taddr, bytes(buf[:4]).hex()))
        if kind in ('DELEGATECALL', 'CALLCODE'):
            ch = self.oracle.codehash(taddr)
            if ch is None: self.reasons['no-code'] += 1; return
            self._frame(tx, blk, address, ch, caller, bytes(buf), value, pred, info, depth + 1, seen, unknown, via)
        else:
            ch = self.oracle.codehash(taddr)
            if ch is None: self.reasons['no-code'] += 1; return
            self._frame(tx, blk, taddr, ch, address, bytes(buf), 0, pred, info, depth + 1, seen, unknown, via)

    def _callargs(self, argwords, argsize, ctx):
        """-> (bytes, unknown_ranges). DYN words become unknown ranges (the callee's CD reads over them raise Unknown)."""
        if VERSION != 'v2':
            if argsize == -1:
                src = evaluate(argwords[1], ctx); n = evaluate(argwords[2], ctx)
                if n > 1 << 20: raise Unknown('fwd-size')
                return bytes(ctx['calldata'][src:src + n].ljust(n, b'\0')), []
            buf = bytearray(argsize)
            for rel, e in argwords:
                w = evaluate(e, ctx).to_bytes(32, 'big'); lo = max(rel, 0); hi = min(rel + 32, argsize)
                if lo < hi: buf[lo:hi] = w[lo - rel:hi - rel]
            return bytes(buf), []
        size = evaluate(argsize, ctx)
        if size > 1 << 16: raise Unknown('argsize')
        buf = bytearray(size); unk = bytearray(size)   # unk[i]=1 -> byte i could not be reconstructed
        cov = bytearray(size)                          # cov[i]=1 -> some arg word (known or not) covers byte i
        self._last_holes = 0
        # writes are applied in write order, so a later write CLEARS the unknown flag of the bytes it covers
        # (e.g. a proxy that restores mem[0] before calldatacopy(0,0,calldatasize) must not leave the
        #  selector marked unknown -- that used to abort the follow with 'call-selector-unknown').
        def place(rel, v, nb):
            if v[0] == 'REGION':
                try: data = eval_region(v, ctx, 0)
                except Unknown:
                    lo = max(rel, 0)
                    if lo < size: unk[lo:size] = b'\1' * (size - lo); cov[lo:size] = b'\1' * (size - lo)
                    return
                lo = max(rel, 0); hi = min(rel + len(data), size)
                if lo < hi: buf[lo:hi] = data[lo - rel:hi - rel]; unk[lo:hi] = bytes(hi - lo); cov[lo:hi] = b'\1' * (hi - lo)
                return
            n = 32 if nb is None else nb
            lo = max(rel, 0); hi = min(rel + n, size)
            if lo >= hi: return
            cov[lo:hi] = b'\1' * (hi - lo)
            try: w = evaluate(v, ctx).to_bytes(32, 'big')
            except Unknown:
                unk[lo:hi] = b'\1' * (hi - lo); return
            buf[lo:hi] = w[lo - rel:hi - rel]; unk[lo:hi] = bytes(hi - lo)
        for rel, v, nb in argwords:
            if isinstance(rel, int):
                place(rel, v, nb); continue
            # offset linear in a loop index: instantiate for every iteration that lands inside the buffer
            ids = sorted(idx_ids(rel) | idx_ids(v))
            bound = {i: ctx['idx'][i] for i in ids if ctx['idx'] and i in ctx['idx']}
            free = [i for i in ids if i not in bound]
            if len(free) != 1:
                if not free:
                    try: r = evaluate(rel, ctx)
                    except Unknown: continue
                    if r < 1 << 62: place(r, v, nb)
                continue
            saved = ctx['idx']
            for i in range(min(MAX_FAMILY, size // 32 + 2)):
                ctx["idx"] = {**bound, free[0]: i}
                try: r = evaluate(rel, ctx)
                except Unknown: break
                if r >= 1 << 62: r -= 1 << 256
                if r >= size or r < -32: break
                place(r, v, nb)
            ctx['idx'] = saved
        # bytes no arg word covers: the producing pass read them as zero (unwritten EVM memory). Whether that
        # transfers to this tx is exactly the transferability question -> count them; optionally mark unknown.
        self._last_holes = size - sum(cov) if size else 0
        if TIER_HOLE_UNKNOWN and self._last_holes:
            for i in range(size):
                if not cov[i]: unk[i] = 1
        unknown = []
        i = 0
        while i < size:
            if unk[i]:
                j = i
                while j < size and unk[j]: j += 1
                unknown.append((i, j)); i = j
            else: i += 1
        return bytes(buf), unknown

def ground_truth(tx):
    g = set(); g_entry = set()
    to = (tx.get('to') or '').lower()
    for a, v in tx['accounts'].items():
        for s in v['slots']:
            g.add((a.lower(), s))
            if a.lower() == to: g_entry.add((a.lower(), s))
    return g, g_entry
