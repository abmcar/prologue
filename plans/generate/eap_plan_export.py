"""mechanical conversion of the predictor's per-code-hash summaries into single-frame plans.

The summary of each code hash is loaded with the predictor's own code (predict.SummaryStore._lazy_get, which builds the
grouped `_meta` for compact==2 stores, or predict.Predictor._build_meta otherwise), under the earlier frame-level
environment. Only what Predictor._frame at level 1 with PRED_TAGS=1, FAMILY_IFREE_CONS=sel, TIER_POLICY=t0t1 and a storage
oracle that always raises Unknown can use is written (src/frame_plan/README.md):
  * site groups whose key class is 'C' or whose key tier > 1 are skipped by the predictor -> not written
  * a key containing SLOAD / DYN / OPQ / REGION of kind != CD / an ENV name absent from predict.build_env always raises
    Unknown -> group not written (counted)
  * family groups with more than 2 key loop indices always yield nothing (_family_assignments) -> not written
  * a constraint that always raises Unknown (same node set) is skipped by _cons_ok -> not written
  * index-free constraints of family alternatives are only used for the 'sel'-class rejection (FIC_CLASSES={'sel'}):
    only their selector constants are written
  * the first selector-equality constraint (Analyzer._sel_tag form) of an alternative becomes its selector index key
Binary layout: see src/frame_plan/README.md. usage: python eap_plan_export.py CODEHASH_LIST OUT_DIR STATS_CSV
Environment: SUMMARY_DIR, CODES_DIR (set by the caller).
"""
import os, sys, struct, array, csv, time
for k, v in dict(EVM_STATIC='v2', SUMMARY_MAX_BYTES='40000000', MAX_FAMILY='512', MAX_DEPTH='4', DYN_ALLOW='1', PRED_TAGS='1',
                 TIER_CONS='0', TIER_POLICY='t0t1', TIER_HOLE_UNKNOWN='1', FAMILY_IFREE_CONS='sel', P18_FAST='ifree+cache').items():
    assert os.environ.get(k, v) == v, k
    os.environ[k] = v
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'export_lib'))
sys.dont_write_bytecode = True
import predict, predict_fast
predict_fast.apply(predict, 'ifree+cache')
ES = predict.ES
assert predict.TIER_MAX == 1 and predict.PRED_TAGS and predict.FIC_CLASSES == frozenset({'sel'}) and not predict.TIER_CONS

ENV_IDS = {n: i for i, n in enumerate(['CALLER', 'ORIGIN', 'ADDRESS', 'CALLVALUE', 'CALLDATASIZE', 'NUMBER', 'TIMESTAMP',
                                       'CHAINID', 'COINBASE', 'GASLIMIT', 'BASEFEE', 'PREVRANDAO', 'BLOBBASEFEE', 'CODESIZE'])}
OPS = ['ADD', 'MUL', 'SUB', 'DIV', 'SDIV', 'MOD', 'SMOD', 'ADDMOD', 'MULMOD', 'EXP', 'SIGNEXTEND', 'LT', 'GT', 'SLT', 'SGT',
       'EQ', 'ISZERO', 'AND', 'OR', 'XOR', 'NOT', 'BYTE', 'SHL', 'SHR', 'SAR']
assert set(OPS) == set(ES.ARITH), set(ES.ARITH) ^ set(OPS)
OP_IDS = {n: i for i, n in enumerate(OPS)}
T_CONST, T_CD, T_ENV, T_LIN, T_OP, T_KEC, T_KECB, T_BYTES, T_REGCD, T_IDX = range(10)
NONE32 = 0xFFFFFFFF
UNK = -1
FAR = 1 << 24
HI_NONE = 0x7FFFFFFF

class Builder:
    def __init__(self):
        self.consts = []; self.cix = {}; self.nodes = []; self.side = array.array('I'); self.nix = {}; self.memo = {}
        self.idx_map = {}; self.stat = {}
    def const(self, v):
        i = self.cix.get(v)
        if i is None: i = self.cix[v] = len(self.consts); self.consts.append(v)
        return i
    def idx(self, i):
        j = self.idx_map.get(i)
        if j is None: j = self.idx_map[i] = len(self.idx_map)
        return j
    def add(self, tag, sub, a, b, n, dep):
        key = (tag, sub, a, b, n, tuple(self.side[b:b + n * {T_LIN: 2, T_KECB: 3, T_BYTES: 3}.get(tag, 1)]) if tag in (T_LIN, T_OP, T_KEC, T_KECB, T_BYTES) else ())
        j = self.nix.get(key)
        if j is not None:
            if tag in (T_LIN, T_OP, T_KEC, T_KECB, T_BYTES): del self.side[b:]   # shared: drop the duplicate side entries
            return j
        j = self.nix[key] = len(self.nodes); self.nodes.append((tag | (sub << 8) | (dep << 16), a, b, n)); return j
    def dep(self, j): return (self.nodes[j][0] >> 16) & 1
    def conv(self, e):
        """expression -> node id, or UNK when its evaluation always raises Unknown"""
        k = id(e); r = self.memo.get(k)
        if r is not None and r[0] is e: return r[1]
        j = self._conv(e); self.memo[k] = (e, j); return j
    def _conv(self, e):
        t = e[0]
        if t == 'C': return self.add(T_CONST, 0, self.const(e[1]), 0, 0, 0)
        if t == 'HZ': return self.add(T_CONST, 0, self.const(0), 0, 0, 0)
        if t == 'CD':
            c = self.conv(e[1]); return UNK if c == UNK else self.add(T_CD, 0, c, 0, 0, self.dep(c))
        if t == 'ENV':
            return self.add(T_ENV, ENV_IDS[e[1]], 0, 0, 0, 0) if e[1] in ENV_IDS else UNK
        if t == 'IDX': return self.add(T_IDX, 0, self.idx(e[1]), 0, 0, 1)
        if t in ('DYN', 'OPQ', 'SLOAD'): return UNK
        if t == 'REGION':
            if e[1] != 'CD': return UNK
            ln = self.conv(e[3]); src = self.conv(e[2])
            if UNK in (ln, src): return UNK
            return self.add(T_REGCD, 0, src, ln, 0, self.dep(src) | self.dep(ln))
        if t == 'LIN':
            terms = [(c, self.conv(a)) for c, a in e[2]]
            if any(j == UNK for _, j in terms): return UNK
            b = len(self.side)
            for c, j in terms: self.side.append(self.const(c)); self.side.append(j)
            return self.add(T_LIN, 0, self.const(e[1]), b, len(terms), max([self.dep(j) for _, j in terms] + [0]))
        if t == 'OP':
            args = [self.conv(a) for a in e[2:]]
            if UNK in args: return UNK
            b = len(self.side); self.side.extend(args)
            return self.add(T_OP, OP_IDS[e[1]], 0, b, len(args), max(self.dep(j) for j in args))
        if t == 'KEC':
            args = [self.conv(a) for a in e[1]]
            if UNK in args: return UNK
            b = len(self.side); self.side.extend(args)
            return self.add(T_KEC, 0, 0, b, len(args), max([self.dep(j) for j in args] + [0]))
        if t in ('KECB', 'BYTES'):
            segs = []
            for a, lo, hi in e[1]:
                # Python slice semantics (negative bounds count from the end) are reproduced by the instantiator;
                # bounds are stored as two's-complement i32, hi=None as HI_NONE
                assert isinstance(lo, int) and (hi is None or isinstance(hi, int)), (lo, hi)
                j = self.conv(a)
                if j == UNK: return UNK
                if a[0] != 'REGION': assert (self.nodes[j][0] & 0xff) != T_REGCD
                if a[0] == 'REGION' and lo >= FAR:   # region bytes are at most 2^20 long: rb[lo:hi] is empty, padded to hi - lo
                    w = 0 if hi is None else max(hi - lo, 0); assert w < FAR, (lo, hi)
                    lo, hi = FAR, (None if hi is None else FAR + w); self.stat['far_seg'] = self.stat.get('far_seg', 0) + 1
                assert -FAR < lo < 2 * FAR and (hi is None or -FAR < hi < 2 * FAR), (lo, hi)
                if lo < 0 or (hi is not None and hi < 0): self.stat['neg_seg'] = self.stat.get('neg_seg', 0) + 1
                segs.append((j, lo & 0xFFFFFFFF, HI_NONE if hi is None else hi & 0xFFFFFFFF))
            b = len(self.side)
            for s in segs: self.side.extend(s)
            return self.add(T_KECB if t == 'KECB' else T_BYTES, 0, 0, b, len(segs), max([self.dep(j) for j, _, _ in segs] + [0]))
        raise ValueError(t)

def sel_const(e, want):
    if not want: return None
    return ES.Analyzer._sel_tag(e, None)

def build(summ):
    B = Builder(); st = {'groups_in': 0, 'skip_cls_c': 0, 'skip_tier': 0, 'key_unknown': 0, 'fam_too_many_keys': 0,
                        'simple_groups': 0, 'family_groups': 0, 'alts_in': 0, 'alts_dead': 0, 'cons_in': 0, 'cons_unknown': 0,
                        'cons_const_true': 0}
    meta = summ.get('_meta')
    if meta is None: meta = summ['_meta'] = predict.Predictor._build_meta(summ)
    site_groups = meta[0]
    lists = []; lix = {}
    def lst(items):
        k = tuple(items)
        i = lix.get(k)
        if i is None: i = lix[k] = len(lists); lists.append(k)
        return i
    sg_out = []; sa_out = []; fg_out = []; fa_out = []; side2 = array.array('I')
    for kexpr, (cls, ids, key_ids, cons_alts, ktier, ctiers) in site_groups.items():
        st['groups_in'] += 1
        if cls == 'C': st['skip_cls_c'] += 1; continue
        if ktier > predict.TIER_MAX: st['skip_tier'] += 1; continue
        kn = B.conv(kexpr)
        if kn == UNK: st['key_unknown'] += 1; continue
        if not ids:
            alts = []
            for cons in cons_alts:
                st['alts_in'] += 1; sel = None; items = []; dead = False
                for e, w in cons:
                    st['cons_in'] += 1
                    s = sel_const(e, w)
                    if s is not None and sel is None:
                        if s >= 1 << 32: dead = True
                        sel = s; continue
                    j = B.conv(e)
                    if j == UNK: st['cons_unknown'] += 1; continue
                    if (B.nodes[j][0] & 0xff) == T_CONST:
                        if (B.consts[B.nodes[j][1]] != 0) == bool(w): st['cons_const_true'] += 1; continue
                        dead = True
                    assert not B.dep(j)
                    items.append(j | (int(bool(w)) << 31))
                if dead: st['alts_dead'] += 1; continue
                alts.append((sel, lst(items)))
            if not alts: continue
            g = len(sg_out); sg_out.append(kn); st['simple_groups'] += 1
            for sel, li in alts: sa_out.append((g, 0 if sel is None else 1, 0 if sel is None else sel, li))
        else:
            kids = sorted(key_ids)
            if len(kids) > 2: st['fam_too_many_keys'] += 1; continue
            kmap = [B.idx(i) for i in kids]
            nonkey = [i for i in sorted(ids) if i not in key_ids]
            alts = []
            for cons in cons_alts:
                st['alts_in'] += 1; sels = []; per = {}; multi = []; dead = False
                for e, w in cons:
                    st['cons_in'] += 1
                    ii = predict.idx_ids(e)
                    if not ii:
                        s = sel_const(e, w)
                        if s is not None:
                            if s >= 1 << 32: dead = True
                            sels.append(s)
                        continue
                    j = B.conv(e)
                    if j == UNK: st['cons_unknown'] += 1; continue
                    it = j | (int(bool(w)) << 31)
                    if len(ii) == 1: per.setdefault(next(iter(ii)), []).append(it)
                    else: multi.append(it)
                if dead: st['alts_dead'] += 1; continue
                # per-id lists in Python's id order (sorted ids); ids with no constraint have the full range
                fixed = [(B.idx(i), lst(per[i])) for i in nonkey if i in per]
                keyl = [lst(per[i]) if i in per else NONE32 for i in kids]
                alts.append((sels, fixed, keyl, lst(multi) if multi else NONE32))
            if not alts: continue
            g = len(fg_out); st['family_groups'] += 1
            fg_out.append((kn, len(kids), kmap[0] if kids else 0, kmap[1] if len(kids) > 1 else 0))
            for sels, fixed, keyl, ml in alts:
                off = len(side2)
                side2.extend(sels[1:] if sels else [])
                for a, li in fixed: side2.append(a); side2.append(li)
                fa_out.append((g, 1 if sels else 0, sels[0] if sels else 0, off, max(len(sels) - 1, 0), len(fixed),
                               keyl[0] if len(keyl) > 0 else NONE32, keyl[1] if len(keyl) > 1 else NONE32, ml))
    # sort simple / family alternatives by (has_sel, sel) so that the loader can build selector ranges
    sa_out.sort(key=lambda r: (r[1], r[2], r[0])); fa_out.sort(key=lambda r: (r[1], r[2], r[0]))
    st.update(nodes=len(B.nodes), consts=len(B.consts), side=len(B.side), lists=len(lists), simple_alts=len(sa_out),
              family_alts=len(fa_out), idx_ids=len(B.idx_map), far_seg=B.stat.get('far_seg', 0), neg_seg=B.stat.get('neg_seg', 0))
    return B, lists, sg_out, sa_out, fg_out, fa_out, side2, st

def u32s(a): a = array.array('I', a); return struct.pack('<I', len(a)) + a.tobytes()

def serialize(B, lists, sg, sa, fg, fa, side2):
    out = [b'EAPF', struct.pack('<II', 1, 0)]
    out.append(struct.pack('<I', len(B.consts)) + b''.join(v.to_bytes(32, 'big') for v in B.consts))
    nd = array.array('I'); [nd.extend(n) for n in B.nodes]; out.append(struct.pack('<I', len(B.nodes)) + nd.tobytes())
    out.append(u32s(B.side))
    offs = array.array('I', [0]); data = array.array('I')
    for l in lists: data.extend(l); offs.append(len(data))
    out.append(struct.pack('<I', len(lists)) + offs.tobytes() + u32s(data))
    out.append(u32s(sg))
    a = array.array('I'); [a.extend(r) for r in sa]; out.append(struct.pack('<I', len(sa)) + a.tobytes())
    a = array.array('I'); [a.extend(r) for r in fg]; out.append(struct.pack('<I', len(fg)) + a.tobytes())
    a = array.array('I'); [a.extend(r) for r in fa]; out.append(struct.pack('<I', len(fa)) + a.tobytes())
    out.append(u32s(side2)); out.append(struct.pack('<I', len(B.idx_map)))
    return b''.join(out)

def main():
    chs = open(sys.argv[1]).read().split(); od = sys.argv[2]; os.makedirs(od, exist_ok=True)
    store = predict.SummaryStore(); rows = []; t0 = time.time()
    for n, ch in enumerate(chs):
        p = f'{od}/{ch}.eapf'
        dl = store.designator(ch)
        if dl is not None:
            open(p, 'wb').write(b'EAPF' + struct.pack('<II', 1, 1) + bytes.fromhex(dl[2:]))
            rows.append(dict(codehash=ch, kind='delegate', bytes=os.path.getsize(p))); continue
        s = store.get(ch)
        if s is None:
            open(p, 'wb').write(b'EAPF' + struct.pack('<II', 1, 2)); rows.append(dict(codehash=ch, kind='no_summary', bytes=os.path.getsize(p))); continue
        t1 = time.perf_counter()
        B, lists, sg, sa, fg, fa, side2, st = build(s)
        blob = serialize(B, lists, sg, sa, fg, fa, side2)
        open(p, 'wb').write(blob)
        rows.append(dict(codehash=ch, kind='plan', bytes=len(blob), convert_s=round(time.perf_counter() - t1, 4),
                         summary_pickle_bytes=store.sizes.get(ch, 0), **st))
        store.cache.clear()
        if n % 200 == 0: print(n, len(chs), round(time.time() - t0), flush=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(sys.argv[3], 'w', newline='') as f:
        w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)

if __name__ == '__main__':
    main()
