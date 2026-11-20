# Source: copied verbatim from the state-access-summary analyzer phase20_lib.py (2026-10-12).
"""Phase 20 shared code (docs/phase20_P.md): reading the provenance files of scripts/phase20_eval.py, per-family kill
sets of source chains, and the causal calibration simulation.

Kill-set families (P.1; the extra families H and T are only used by the improvement branch P.8):
  A  key = code hash   chain killed when it has a new step in a frame whose code hash is disabled
  B  key = combo       chain killed when it has a new step in a frame whose combo is disabled
  C  key = combo       chain killed when it has any frame whose combo is disabled
  H  key = code hash   chain killed when it has any frame whose code hash is disabled
  T  key = record type chain killed when it has a new step all of whose records have the disabled type
A slot is deleted when every chain is killed; it is attributed to (owned by) key k when D = {k} deletes it.
"""
import gzip, json, os, collections, time
FAMS = ('A', 'B', 'C', 'H', 'T')


class Ids:
    def __init__(self): self.ch = {}; self.combo = {}; self.type = {}; self.combo_ch = []; self.chname = []; self.comboname = []
    def chid(self, h):
        i = self.ch.get(h)
        if i is None: i = self.ch[h] = len(self.chname); self.chname.append(h)
        return i
    def coid(self, h, sel):
        k = (h, sel); i = self.combo.get(k)
        if i is None: i = self.combo[k] = len(self.comboname); self.comboname.append(k); self.combo_ch.append(self.chid(h))
        return i
    def tyid(self, t):
        i = self.type.get(t)
        if i is None: i = self.type[t] = len(self.type)
        return i


def first_seen_set(ids, traces='data/traces', lo=25882410, hi=25883409):
    """code-hash ids (in `ids`) seen in the original corpus traces -> returns the set of code-hash strings"""
    seen = set()
    for n in range(lo, hi + 1):
        p = f'{traces}/block-{n}.json.gz'
        if not os.path.exists(p): continue
        for t in json.load(gzip.open(p, 'rt'))['txs']:
            for a, v in t['accounts'].items():
                if v.get('codeHash'): seen.add(v['codeHash'].lower().removeprefix('0x'))
    return seen


def read_blocks(files, ids, seen_ch, want_tx=False, old_only=False):
    """files: provenance files in block order (one process each). Yields one dict per block:
       old_only=True keeps only chains without new steps and drops slots left without a chain (description of the
       old analyser by post-hoc deletion of every new record).
       n, ng, npred, nhit, slots: list of (hit, fs_end, ksets) with ksets = {fam: tuple of frozensets (one per distinct
       chain kill set) or None if some chain has an empty kill set (slot never deleted in that family)},
       tx (if want_tx): list of (txhash, [(tx hit, ksets)])"""
    for f in files:
        CT = []; RT = []; ET = []; CH = []; CK = []   # per-file tables; CK: chain -> (kill sets per family, end fs flag)
        empty = frozenset()
        for line in gzip.open(f, 'rt'):
            r = json.loads(line)
            for h, sel in r['combos']: CT.append(ids.coid(h, sel))
            for h, t in r['rids']: RT.append(ids.tyid(t))
            for c, st in r['els']:
                g = CT[c]; chn = ids.combo_ch[g]
                types = None
                if st:
                    ts = {RT[x] for x in st}; types = next(iter(ts)) if len(ts) == 1 else None
                ET.append((g, chn, bool(st), types))
            for c in r['chains']:
                A = set(); B = set(); C = set(); H = set(); T = set()
                for e in c:
                    g, chn, nw, ty = ET[e]
                    C.add(g); H.add(chn)
                    if nw:
                        A.add(chn); B.add(g)
                        if ty is not None: T.add(ty)
                endch = ids.chname[ET[c[-1]][1]]
                CK.append(((frozenset(A), frozenset(B), frozenset(C), frozenset(H), frozenset(T)), endch not in seen_ch))
                CH.append(None)
            V = r['vocab']; bh = r['bhit']
            blk = [set() for _ in V]
            for h, lst in r['tx']:
                for vi, th, cids in lst: blk[vi].update(cids)
            def ks(cids):
                out = {}
                kk = [CK[c][0] for c in cids]
                if old_only: kk = [k for k in kk if not k[0]]     # chains without new steps (old-analyser approximation)
                for i, fm in enumerate(FAMS):
                    sets = {k[i] for k in kk}
                    out[fm] = None if (empty in sets or not sets) else tuple(sets)
                return out
            slots = []
            for vi, cids in enumerate(blk):
                if old_only:
                    cids = [c for c in cids if not CK[c][0][0]]
                    if not cids: continue
                fs = bool(cids) and all(CK[c][1] for c in cids)
                slots.append((bh[vi], fs, ks(cids)))
            d = {'n': r['block'], 'ng': r['ng'], 'npred': len(slots), 'nhit': sum(x[0] for x in slots), 'slots': slots}
            if want_tx:
                d['tx'] = [(h, [(th, ks(cids)) for vi, th, cids in lst]) for h, lst in r['tx']]
            yield d


def owners(kt):
    """kill-set tuple -> owner keys (intersection)"""
    if kt is None: return ()
    it = iter(kt); o = set(next(it))
    for s in it:
        o &= s
        if not o: break
    return o


def prep(blocks, fams=FAMS):
    """per block and family: increments [(key, hit)], removable slots [(slot idx, kill tuple)]"""
    out = []
    for d in blocks:
        inc = {f: [] for f in fams}; rem = {f: [] for f in fams}
        for i, (hit, fs, ks) in enumerate(d['slots']):
            for f in fams:
                kt = ks[f]
                if kt is None: continue
                rem[f].append((i, kt))
                for k in owners(kt): inc[f].append((k, hit))
        out.append(dict(d, inc=inc, rem=rem))
    return out


class Rule:
    """causal per-key rule. cold: 'opt' | 'cons'. window: None (cumulative) or int (last `window` shadow slots)."""
    def __init__(self, n, tau, cold='opt', window=None, init=None):
        self.n = n; self.tau = tau; self.cold = cold; self.window = window
        self.m = collections.Counter(); self.h = collections.Counter(); self.q = {}
        if init is not None:
            self.m.update(init.m); self.h.update(init.h)
            if window: self.q = {k: collections.deque(v, maxlen=window) for k, v in init.q.items()}
    def disabled(self, k):
        m = self.m.get(k, 0)
        if m >= self.n:
            bad = self.h.get(k, 0) < self.tau * m
            return bad
        return self.cold == 'cons'
    def update(self, incs):
        if self.window:
            for k, hit in incs:
                q = self.q.get(k)
                if q is None: q = self.q[k] = collections.deque(maxlen=self.window)
                if len(q) == self.window:
                    self.m[k] -= 1; self.h[k] -= q[0]
                q.append(hit); self.m[k] += 1; self.h[k] += hit
        else:
            for k, hit in incs: self.m[k] += 1; self.h[k] += hit


def killed_slot(kt, dis):
    for s in kt:
        if not any(dis(k) for k in s): return False
    return True


def simulate(pb, fam, rule, track=False):
    """pb: prep() output in block order. Returns per-block rows [(n, ng, pred, hit, removed, removed_hits)] and,
    with track=True, the per-block removed slot index sets and the disabled-set history {key: [blocks disabled]}."""
    rows = []; rmsets = [] if track else None
    dis_cache = {}
    for d in pb:
        dis_cache.clear()
        def dis(k):
            v = dis_cache.get(k)
            if v is None: v = dis_cache[k] = rule.disabled(k)
            return v
        rm = [i for i, kt in d['rem'][fam] if killed_slot(kt, dis)]
        rh = sum(d['slots'][i][0] for i in rm)
        rows.append((d['n'], d['ng'], d['npred'] - len(rm), d['nhit'] - rh, len(rm), rh))
        if track: rmsets.append((set(rm), {k for k, v in dis_cache.items() if v}))
        rule.update(d['inc'][fam])
    return rows, rmsets


def summarize(rows):
    ng = sum(r[1] for r in rows); p = sum(r[2] for r in rows); h = sum(r[3] for r in rows)
    return dict(blocks=len(rows), gt=ng, pred=p, hit=h, recall=h / ng if ng else float('nan'),
                precision=h / p if p else float('nan'), removed=sum(r[4] for r in rows), removed_hits=sum(r[5] for r in rows))
