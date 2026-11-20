#!/usr/bin/env python3
# Copied from scripts/eap_plan_export_calls_v3.py for
# Changes: more per-plan statistics (fc_nopayload_rec, fc_offexpr_words, fc_nkey0/1/2, fc_target_dep,
# fc_sload_nodes, fc_target_nokey); family groups without argument words whose target depends on a loop index are skipped
# (fc_target_nokey: the target never evaluates, see build_family_calls). The byte layout is unchanged (checked by
# src/frame_plan_v3 Plan::parse / Plan::to_bytes round trip over the whole library).
# option --calls-from DIR[:DIR...]: the call sections (index-free and family call groups) of a code hash come from
# the summary found in these directories (first match; same pickle formats as the summary store), the storage sections
# from the original summary as before (stat calls_src = alt / orig). A code hash without an original summary but with
# such a summary gets a plan with empty storage sections (calls_src = alt_only); its storage prediction stays empty.
# option --calls-union DIR[:DIR...]: the call sections are built from the union of the original summary's call
# groups and those of the summary found in these directories: same signature (kind, target, argument words, size) -> the
# alternative constraint sets are merged (duplicates dropped, original first); groups of one source only are kept
# (calls_src = union / union_alt_only; stats cu_*). Exclusive with --calls-from.
# option --unkval: an argument word whose offset converts but whose value does not (DYN, OPQ, unknown ENV, a
# REGION of another kind) is kept with a T_UNK value node (tag 11; sub 1 for a REGION: unknown from its offset to the end
# of the buffer) instead of dropping the whole payload (stats c_argword_unkval / fc_argword_unkval). src/frame_plan_v3
# then follows predict._callargs: such bytes are unknown unless a later word overwrites them, and a word outside the
# buffer is ignored. Needs src/frame_plan_v3 with T_UNK support. Without --unkval the output is byte-identical to the
# plans_v3s export.
"""access-plan export, file version 3 = version 2 plus the call groups that depend on a loop index
("family" call records: a call site inside a loop whose target or argument words vary with the loop index, e.g. a batch
transfer looping over a calldata array). Version 2 skipped them (`if ids: continue`).

Appended after the version-2 sections (header version set to 3):
  u32 n_fcgroups, n_fcgroups x [kind, target node, argsize node | NONE32, cside offset, n argwords, nkey, key id 0, key id 1]
  u32 n_fcalts,   n_fcalts x [group, has_sel, sel, cside2 offset, n_extra_sel, n_fixed, key list 0, key list 1, multi list]
                  (the family site alternative layout of version 1; sorted by (has_sel, sel) like the others)
  u32 n_cside2,   extra selectors and (index, list) pairs of the fixed (non-key) indices, as side2 for family sites
Argument words of a family call group are appended to the shared cside array; their offset and value nodes may depend on
the key indices (bound at instantiation). Groups whose key indices exceed 2, or whose target/argsize cannot be converted,
are skipped and counted (st: fc_too_many_keys, fc_target_unknown). Everything else is produced by the earlier script.
usage: eap_plan_export_calls_v3.py CODEHASH_LIST OUT_DIR STATS_CSV [--nproc N] [--calls-from DIR[:DIR...] | --calls-union DIR[:DIR...]] [--unkval]
env: SUMMARY_DIRS / CODES_DIRS (colon lists).
"""
import os, sys, struct, array, csv, time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eap_plan_export_calls as V2
X = V2.X; predict = V2.predict
NONE32 = X.NONE32
T_UNK = 11
UNKVAL = False   # set by main (--unkval)


def unk_node(B, v):
    return B.add(T_UNK, 1 if v[0] == 'REGION' else 0, 0, 0, 0, 0)


def build_calls(B, summ, lists, lst):
    """eap_plan_export_calls.build_calls (copied; identical when UNKVAL is off) plus the --unkval rule"""
    if not UNKVAL: return V2.build_calls(B, summ, lists, lst)
    meta = summ['_meta']
    call_groups = meta[1]
    st = {'cgroups_in': 0, 'c_skip_tier': 0, 'c_family': 0, 'c_target_unknown': 0, 'c_nopayload_rec': 0, 'c_argword_unknown': 0,
          'cgroups': 0, 'calts': 0, 'c_alts_dead': 0, 'c_sload_nodes': 0, 'c_argword_unkval': 0}
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
                s_ = X.sel_const(e, w)
                if s_ is not None and sel is None:
                    if s_ >= 1 << 32: dead = True
                    sel = s_; continue
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
            words = []; nu = 0
            for rel, v, nb in argwords:
                rn = B.conv(('C', rel if rel >= 0 else rel + (1 << 256))) if isinstance(rel, int) else B.conv(rel)
                vn = B.conv(v)
                if rn != X.UNK and vn == X.UNK: vn = unk_node(B, v); nu += 1
                if X.UNK in (rn, vn): ok = False; break
                words.append((rn, vn, X.NONE32 if nb is None else nb))
            if ok:
                for rn, vn, nb in words: cside.extend((rn, vn, nb)); n += 1
                st['c_argword_unkval'] += nu
            else:
                st['c_argword_unknown'] += 1; size_node = X.NONE32; del cside[off:]; n = 0
        g = len(cg_out); cg_out.append((V2.KIND[kind], tn, size_node, off, n, 0)); st['cgroups'] += 1
        for sel, li in alts: ca_out.append((g, 0 if sel is None else 1, 0 if sel is None else sel, li))
    ca_out.sort(key=lambda r: (r[1], r[2], r[0]))
    st['calts'] = len(ca_out)
    st['c_sload_nodes'] = sum(1 for nd in B.nodes if (nd[0] & 0xff) == V2.T_SLOAD)
    B.allow_sload = False
    return cg_out, ca_out, cside, st


_V1DROP = None


def v1_drop(ch, cg):
    """env V1_DROP = a pickle {code hash: set of call-group signatures}. The
    original summary's call groups with these signatures are dropped before the union: they are the v1 analyzer's records
    with argument words in ascending offset order where the order changes the payload (fixed in sas_x23 evm_static.py
    926d7078); the regenerated stage-1 summary of --calls-union supplies the write-order versions. Unset: unchanged."""
    global _V1DROP
    path = os.environ.get('V1_DROP')
    if not path: return cg, 0
    if _V1DROP is None:
        import pickle
        _V1DROP = pickle.load(open(path, 'rb'))
    bad = _V1DROP.get(ch.lower().removeprefix('0x'))
    if not bad: return cg, 0
    out = {k: v for k, v in cg.items() if k not in bad}
    return out, len(cg) - len(out)


def union_calls(cg1, cg2):
    """--calls-union: call groups of two summaries (predict's grouped form sig -> (ids, kids, cons_alts, ktier, ptier,
    ctiers)); same signature -> alternatives merged (original first, duplicates dropped), ids united"""
    out = dict(cg1); st = {'cu_groups_orig': len(cg1), 'cu_groups_alt': len(cg2), 'cu_merged': 0, 'cu_new': 0, 'cu_alts_added': 0}
    for sig, g2 in cg2.items():
        g1 = out.get(sig)
        if g1 is None: out[sig] = g2; st['cu_new'] += 1; continue
        st['cu_merged'] += 1
        seen = set(g1[2]); alts = list(g1[2]); ct = list(g1[5])
        for c, t in zip(g2[2], g2[5]):
            if c in seen: continue
            seen.add(c); alts.append(c); ct.append(t); st['cu_alts_added'] += 1
        out[sig] = (set(g1[0]) | set(g2[0]), g1[1], alts, max(g1[3], g2[3]), max(g1[4], g2[4]), tuple(ct))
    return out, st


def build_family_calls(B, summ, lists, lst, cside):
    meta = summ['_meta']; call_groups = meta[1]
    st = {'fc_in': 0, 'fc_too_many_keys': 0, 'fc_target_unknown': 0, 'fc_skip_tier': 0, 'fc_alts_dead': 0, 'fc_argword_unknown': 0,
          'fcgroups': 0, 'fcalts': 0, 'fc_nopayload_rec': 0, 'fc_offexpr_words': 0, 'fc_nkey0': 0, 'fc_nkey1': 0, 'fc_nkey2': 0,
          'fc_target_dep': 0, 'fc_target_nokey': 0}
    n_sl0 = sum(1 for nd in B.nodes if (nd[0] & 0xff) == V2.T_SLOAD)
    B.allow_sload = True
    fcg = []; fca = []; cside2 = array.array('I')
    for (kind, target, argwords, argsize), (ids, kids, cons_alts, ktier, ptier, ctiers) in call_groups.items():
        if not ids: continue
        st['fc_in'] += 1
        if ktier > predict.TIER_MAX: st['fc_skip_tier'] += 1; continue
        kids_s = sorted(kids)
        if len(kids_s) > 2: st['fc_too_many_keys'] += 1; continue
        kmap = [B.idx(i) for i in kids_s]
        nonkey = [i for i in sorted(ids) if i not in kids]
        # without argument words the predictor's key indices are empty (predict.SummaryStore._lazy_get), so a target
        # that depends on a loop index never evaluates (IDX unbound); predict.py does not follow such groups either.
        # Checked before converting the target so that the skipped group adds no nodes.
        if argwords is None and predict.idx_ids(target): st['fc_target_nokey'] += 1; continue
        tn = B.conv(target)
        if tn == X.UNK: st['fc_target_unknown'] += 1; continue
        alts = []
        for cons in cons_alts:
            sels = []; per = {}; multi = []; dead = False
            for e, w in cons:
                ii = predict.idx_ids(e)
                if not ii:
                    s = X.sel_const(e, w)
                    if s is not None:
                        if s >= 1 << 32: dead = True
                        sels.append(s)
                    continue
                j = B.conv(e)
                if j == X.UNK: continue
                it = j | (int(bool(w)) << 31)
                if len(ii) == 1: per.setdefault(next(iter(ii)), []).append(it)
                else: multi.append(it)
            if dead: st['fc_alts_dead'] += 1; continue
            fixed = [(B.idx(i), lst(per[i])) for i in nonkey if i in per]
            keyl = [lst(per[i]) if i in per else NONE32 for i in kids_s]
            alts.append((sels, fixed, keyl, lst(multi) if multi else NONE32))
        if not alts: continue
        off = len(cside); n = 0; size_node = NONE32
        if argwords is None: st['fc_nopayload_rec'] += 1
        if argwords is not None:
            ok = True
            size_node = B.conv(('C', argsize)) if isinstance(argsize, int) else B.conv(argsize)
            if size_node == X.UNK: ok = False
            words = []
            nu = 0
            for rel, v, nb in (argwords if ok else []):
                rn = B.conv(('C', rel if rel >= 0 else rel + (1 << 256))) if isinstance(rel, int) else B.conv(rel)
                vn = B.conv(v)
                if UNKVAL and rn != X.UNK and vn == X.UNK: vn = unk_node(B, v); nu += 1
                if X.UNK in (rn, vn): ok = False; break
                words.append((rn, vn, NONE32 if nb is None else nb))
            if ok:
                for rn, vn, nb in words: cside.extend((rn, vn, nb)); n += 1
                if UNKVAL: st['fc_argword_unkval'] = st.get('fc_argword_unkval', 0) + nu
                st['fc_offexpr_words'] += sum(1 for rn, _, _ in words if (B.nodes[rn][0] & 0xff) != X.T_CONST)
            else:
                st['fc_argword_unknown'] += 1; size_node = NONE32; del cside[off:]; n = 0
        g = len(fcg); st['fcgroups'] += 1; st[f'fc_nkey{len(kids_s)}'] += 1; st['fc_target_dep'] += B.dep(tn)
        fcg.append((V2.KIND[kind], tn, size_node, off, n, len(kids_s), kmap[0] if kids_s else 0, kmap[1] if len(kids_s) > 1 else 0))
        for sels, fixed, keyl, ml in alts:
            o2 = len(cside2)
            cside2.extend(sels[1:] if sels else [])
            for a, li in fixed: cside2.append(a); cside2.append(li)
            fca.append((g, 1 if sels else 0, sels[0] if sels else 0, o2, max(len(sels) - 1, 0), len(fixed),
                        keyl[0] if len(keyl) > 0 else NONE32, keyl[1] if len(keyl) > 1 else NONE32, ml))
    fca.sort(key=lambda r: (r[1], r[2], r[0]))
    st['fcalts'] = len(fca)
    st['fc_sload_nodes'] = sum(1 for nd in B.nodes if (nd[0] & 0xff) == V2.T_SLOAD) - n_sl0
    B.allow_sload = False
    return fcg, fca, cside2, st


class DirStore(V2.MultiStore):
    """summaries of the call sections (--calls-from): first match in `dirs`, loaded by the predictor's store code"""
    def __init__(self, dirs):
        super().__init__(); self.dirs = dirs
    def _lazy_get(self, codehash):
        for d in self.dirs:
            if os.path.exists(f'{d}/{codehash}.pkl'):
                saved = predict.SUMMARY_DIR; predict.SUMMARY_DIR = d
                try: return predict.SummaryStore._lazy_get(self, codehash)
                finally: predict.SUMMARY_DIR = saved
        return None


def call_meta(s2):
    m = s2.get('_meta')
    if m is None: m = s2['_meta'] = predict.Predictor._build_meta(s2)
    return m[1]


def serialize3(B, lists, sg, sa, fg, fa, side2, cg, ca, cside, n_family, fcg, fca, cside2):
    blob = bytearray(V2.serialize2(B, lists, sg, sa, fg, fa, side2, cg, ca, cside, n_family))
    struct.pack_into('<I', blob, 4, 3)   # version 3
    a = array.array('I'); [a.extend(r) for r in fcg]; blob += struct.pack('<I', len(fcg)) + a.tobytes()
    a = array.array('I'); [a.extend(r) for r in fca]; blob += struct.pack('<I', len(fca)) + a.tobytes()
    blob += X.u32s(cside2)
    return bytes(blob)


def convert_one(args, unkval=None):
    """args = (code hash, out dir[, call-summary dirs[, 'from' | 'union']]); unkval: True / False override the module
    switch UNKVAL (set by --unkval) for this plan, None keeps it (scripts/plan_worker_x23.py passes unkval=True)"""
    global UNKVAL
    if unkval is not None and unkval != UNKVAL:
        saved = UNKVAL; UNKVAL = unkval
        try: return convert_one(args)
        finally: UNKVAL = saved
    ch, od = args[0], args[1]
    cdirs = args[2] if len(args) > 2 else []
    cmode = args[3] if len(args) > 3 else 'from'
    store = V2.MultiStore()
    p = f'{od}/{ch}.eapf'
    dl = store.designator(ch)
    if dl is not None:
        open(p, 'wb').write(b'EAPF' + struct.pack('<II', 1, 1) + bytes.fromhex(dl[2:]))
        return dict(codehash=ch, kind='delegate', bytes=os.path.getsize(p))
    s = store.get(ch)
    s2 = DirStore(cdirs).get(ch) if cdirs else None
    calls_src = 'orig'
    if s is None:
        if s2 is None:
            open(p, 'wb').write(b'EAPF' + struct.pack('<II', 1, 2)); return dict(codehash=ch, kind='no_summary', bytes=os.path.getsize(p))
        s = {'_meta': ({}, {})}; calls_src = 'alt_only' if cmode == 'from' else 'union_alt_only'
    t1 = time.perf_counter()
    saved = X.Builder; X.Builder = V2.CallBuilder
    try:
        B, lists, sg, sa, fg, fa, side2, st = X.build(s)
    finally:
        X.Builder = saved
    lix = {tuple(l): i for i, l in enumerate(lists)}
    def lst(items):
        k = tuple(items); i = lix.get(k)
        if i is None: i = lix[k] = len(lists); lists.append(k)
        return i
    cs = s; stu = {}
    if s2 is not None:
        if cmode == 'from':
            cs = {'_meta': (s['_meta'][0], call_meta(s2))}
            if calls_src == 'orig': calls_src = 'alt'
        else:
            g1, ndrop = v1_drop(ch, s['_meta'][1])
            cu, stu = union_calls(g1, call_meta(s2))
            if ndrop: stu['v1_dropped'] = ndrop
            cs = {'_meta': (s['_meta'][0], cu)}
            if calls_src == 'orig': calls_src = 'union'
    cg, ca, cside, st2 = build_calls(B, cs, lists, lst)
    fcg, fca, cside2, st3 = build_family_calls(B, cs, lists, lst, cside)
    # the version-1 part was serialized before build_calls extended B; keep the earlier convention (nodes appended after)
    blob = serialize3(B, lists, sg, sa, fg, fa, side2, cg, ca, cside, st2['c_family'], fcg, fca, cside2)
    open(p, 'wb').write(blob)
    r = dict(codehash=ch, kind='plan', bytes=len(blob), convert_s=round(time.perf_counter() - t1, 4), calls_src=calls_src, **st)
    r.update(st2); r.update(st3); r.update(stu)
    return r


def main():
    import argparse
    from multiprocessing import Pool
    ap = argparse.ArgumentParser(); ap.add_argument('list'); ap.add_argument('out'); ap.add_argument('csv'); ap.add_argument('--nproc', type=int, default=1)
    ap.add_argument('--calls-from', default='', help='DIR[:DIR...]: summaries for the call sections (first match)')
    ap.add_argument('--calls-union', default='', help='DIR[:DIR...]: call sections = union with these summaries (first match)')
    ap.add_argument('--unkval', action='store_true', help='keep argument words with unconvertible values as T_UNK nodes')
    A = ap.parse_args()
    assert not (A.calls_from and A.calls_union), '--calls-from and --calls-union are exclusive'
    global UNKVAL; UNKVAL = A.unkval
    cmode = 'union' if A.calls_union else 'from'
    cdirs = [d for d in (A.calls_union or A.calls_from).split(':') if d]
    chs = [l.strip() for l in open(A.list) if l.strip()]
    os.makedirs(A.out, exist_ok=True)
    jobs = [(ch, A.out, cdirs, cmode) for ch in chs]
    if A.nproc > 1: rows = list(Pool(A.nproc).imap_unordered(convert_one, jobs, chunksize=4))
    else:
        import gc
        rows = []
        for n, j in enumerate(jobs):
            rows.append(convert_one(j))
            # predict_fast's cache patch calls gc.freeze() after each summary load, which exempts everything loaded so far
            # from the cyclic collector; release it periodically (output unchanged)
            if n % 20 == 19: gc.unfreeze(); gc.collect()
    keys = sorted({k for r in rows for k in r})
    with open(A.csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    n = sum(1 for r in rows if r.get('fcgroups', 0)); print('plans', len(rows), 'with family call groups', n,
          'family alts', sum(r.get('fcalts', 0) for r in rows), 'skipped (too many keys)', sum(r.get('fc_too_many_keys', 0) for r in rows))


if __name__ == '__main__':
    main()
