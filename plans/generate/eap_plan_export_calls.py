#!/usr/bin/env python3
"""access-plan export, file version 2 = the earlier single-frame plan plus the summary's call records.

Everything of version 1 (site groups, nodes, constraint lists) is produced by the earlier converter unchanged; this script
appends one section:
  u32 n_cgroups, n_cgroups x [kind, target node, argsize node | NONE32, cside offset, n argwords, flags]
  u32 n_cside,   per argword [offset node, value node, byte count | NONE32]
  u32 n_calts,   n_calts x [group, has_sel, sel, list]   (sorted by (has_sel, sel) like the site alternatives)
  u32 n_family_calls (call groups skipped because they depend on a loop index)
and sets the header version to 2. Call-record expressions may contain SLOAD (node tag 10, child = key); site keys may not
(the converter's rule 2 in src/frame_plan/README.md still applies to them), so the storage prediction of a frame is
unchanged. Call groups of transferability tier 2 (return data, opaque values) are skipped as in the predictor
(TIER_POLICY=t0t1); an argument word that cannot be converted makes the payload unknown (target still exported).
usage: eap_plan_export_calls.py CODEHASH_LIST OUT_DIR STATS_CSV [--nproc N]
env: SUMMARY_DIRS / CODES_DIRS (colon lists; first match wins) or SUMMARY_DIR / CODES_DIR.
"""
import os, sys, struct, array, csv, time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SUMMARY_DIRS = [d for d in os.environ.get('SUMMARY_DIRS', os.environ.get('SUMMARY_DIR', '')).split(':') if d]
CODES_DIRS = [d for d in os.environ.get('CODES_DIRS', os.environ.get('CODES_DIR', '')).split(':') if d]
os.environ['SUMMARY_DIR'] = SUMMARY_DIRS[0] if SUMMARY_DIRS else '/nonexistent'
os.environ['CODES_DIR'] = CODES_DIRS[0] if CODES_DIRS else '/nonexistent'
import eap_plan_export as X
predict = X.predict
T_SLOAD = 10
KIND = {'CALL': 0, 'CALLCODE': 1, 'DELEGATECALL': 2, 'STATICCALL': 3}


class MultiStore(predict.SummaryStore):
    def __init__(self):
        super().__init__(); self.lazy = True
    def _lazy_get(self, codehash):
        for d in SUMMARY_DIRS:
            if os.path.exists(f'{d}/{codehash}.pkl'):
                saved = predict.SUMMARY_DIR; predict.SUMMARY_DIR = d
                try: return super()._lazy_get(codehash)
                finally: predict.SUMMARY_DIR = saved
        return None
    def get(self, codehash):
        s = self.cache.get(codehash)
        return s if s is not None else self._lazy_get(codehash)
    def code(self, codehash):
        c = self.codes.get(codehash)
        if c is None:
            for d in CODES_DIRS:
                p = f'{d}/{codehash}.hex'
                if os.path.exists(p):
                    c = bytes.fromhex(open(p).read().strip()); break
            if c is None: return None
            if len(self.codes) > 4000: self.codes.clear()
            self.codes[codehash] = c
        return c


class CallBuilder(X.Builder):
    """Builder whose SLOAD conversion is switchable; the version-1 part is built with it off."""
    allow_sload = False
    def __init__(self):
        super().__init__(); self.memo_sl = {}
    def _conv(self, e):
        if e[0] == 'SLOAD' and self.allow_sload:
            k = self.conv(e[1])
            return X.UNK if k == X.UNK else self.add(T_SLOAD, 0, k, 0, 0, self.dep(k))
        return super()._conv(e)
    def conv(self, e):
        # the memo is keyed by expression identity; SLOAD-containing subtrees converted with allow_sload off are UNK and
        # must not be reused with it on, so keep two memos
        memo = self.memo_sl if self.allow_sload else self.memo
        k = id(e); r = memo.get(k)
        if r is not None and r[0] is e: return r[1]
        j = self._conv(e); memo[k] = (e, j); return j


def build_calls(B, summ, lists, lst):
    meta = summ['_meta']
    call_groups = meta[1]
    st = {'cgroups_in': 0, 'c_skip_tier': 0, 'c_family': 0, 'c_target_unknown': 0, 'c_nopayload_rec': 0, 'c_argword_unknown': 0,
          'cgroups': 0, 'calts': 0, 'c_alts_dead': 0, 'c_sload_nodes': 0}
    B.allow_sload = True
    cg_out = []; ca_out = []; cside = array.array('I')
    for (kind, target, argwords, argsize), (ids, kids, cons_alts, ktier, ptier, ctiers) in call_groups.items():
        st['cgroups_in'] += 1
        if ktier > predict.TIER_MAX: st['c_skip_tier'] += 1; continue
        if ids: st['c_family'] += 1; continue
        tn = B.conv(target)
        if tn == X.UNK: st['c_target_unknown'] += 1; continue
        alts = []
        for cons in cons_alts:
            sel = None; items = []; dead = False
            for e, w in cons:
                s = X.sel_const(e, w)
                if s is not None and sel is None:
                    if s >= 1 << 32: dead = True
                    sel = s; continue
                j = B.conv(e)
                if j == X.UNK: continue
                if (B.nodes[j][0] & 0xff) == X.T_CONST:
                    if (B.consts[B.nodes[j][1]] != 0) == bool(w): continue
                    dead = True
                assert not B.dep(j)
                items.append(j | (int(bool(w)) << 31))
            if dead: st['c_alts_dead'] += 1; continue
            alts.append((sel, lst(items)))
        if not alts: continue
        off = len(cside); n = 0; size_node = X.NONE32
        if argwords is None:
            st['c_nopayload_rec'] += 1
        else:
            ok = True
            size_node = B.conv(('C', argsize)) if isinstance(argsize, int) else B.conv(argsize)
            if size_node == X.UNK: ok = False
            words = []
            for rel, v, nb in argwords:
                rn = B.conv(('C', rel if rel >= 0 else rel + (1 << 256))) if isinstance(rel, int) else B.conv(rel)
                vn = B.conv(v)
                if X.UNK in (rn, vn): ok = False; break
                words.append((rn, vn, X.NONE32 if nb is None else nb))
            if ok:
                for rn, vn, nb in words: cside.extend((rn, vn, nb)); n += 1
            else:
                st['c_argword_unknown'] += 1; size_node = X.NONE32; del cside[off:]; n = 0
        g = len(cg_out); cg_out.append((KIND[kind], tn, size_node, off, n, 0)); st['cgroups'] += 1
        for sel, li in alts: ca_out.append((g, 0 if sel is None else 1, 0 if sel is None else sel, li))
    ca_out.sort(key=lambda r: (r[1], r[2], r[0]))
    st['calts'] = len(ca_out)
    st['c_sload_nodes'] = sum(1 for nd in B.nodes if (nd[0] & 0xff) == T_SLOAD)
    B.allow_sload = False
    return cg_out, ca_out, cside, st


def serialize2(B, lists, sg, sa, fg, fa, side2, cg, ca, cside, n_family):
    blob = bytearray(X.serialize(B, lists, sg, sa, fg, fa, side2))
    struct.pack_into('<I', blob, 4, 2)   # version 2
    a = array.array('I'); [a.extend(r) for r in cg]; blob += struct.pack('<I', len(cg)) + a.tobytes()
    blob += X.u32s(cside)
    a = array.array('I'); [a.extend(r) for r in ca]; blob += struct.pack('<I', len(ca)) + a.tobytes()
    blob += struct.pack('<I', n_family)
    return bytes(blob)


def convert_one(args):
    ch, od = args
    store = MultiStore()
    p = f'{od}/{ch}.eapf'
    dl = store.designator(ch)
    if dl is not None:
        open(p, 'wb').write(b'EAPF' + struct.pack('<II', 1, 1) + bytes.fromhex(dl[2:]))
        return dict(codehash=ch, kind='delegate', bytes=os.path.getsize(p))
    s = store.get(ch)
    if s is None:
        open(p, 'wb').write(b'EAPF' + struct.pack('<II', 1, 2)); return dict(codehash=ch, kind='no_summary', bytes=os.path.getsize(p))
    t1 = time.perf_counter()
    # version-1 part through the earlier code, with our builder class substituted
    saved = X.Builder; X.Builder = CallBuilder
    try:
        B, lists, sg, sa, fg, fa, side2, st = X.build(s)
    finally:
        X.Builder = saved
    lix = {tuple(l): i for i, l in enumerate(lists)}
    def lst(items):
        k = tuple(items); i = lix.get(k)
        if i is None: i = lix[k] = len(lists); lists.append(k)
        return i
    cg, ca, cside, st2 = build_calls(B, s, lists, lst)
    blob = serialize2(B, lists, sg, sa, fg, fa, side2, cg, ca, cside, st2['c_family'])
    open(p, 'wb').write(blob)
    r = dict(codehash=ch, kind='plan', bytes=len(blob), convert_s=round(time.perf_counter() - t1, 4), **st); r.update(st2)
    return r


def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('list'); ap.add_argument('out'); ap.add_argument('csv'); ap.add_argument('--nproc', type=int, default=8)
    a = ap.parse_args()
    chs = open(a.list).read().split(); os.makedirs(a.out, exist_ok=True)
    rows = []; t0 = time.time()
    from multiprocessing import Pool
    with Pool(a.nproc, maxtasksperchild=200) as pool:
        for n, r in enumerate(pool.imap_unordered(convert_one, [(ch, a.out) for ch in chs], chunksize=4)):
            rows.append(r)
            if n % 1000 == 0: print(n, len(chs), round(time.time() - t0), flush=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(a.csv, 'w', newline='') as f:
        w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
    print('done', len(rows), round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
