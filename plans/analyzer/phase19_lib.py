"""Phase 19 shared definitions: new records of a summary relative to its base summary, and their build-time type.

A *record* at the level the predictor consumes is an alternative of a group in the compacted (compact==2) summary:
a site record is (key expression, constraint set), a call record is (call signature, constraint set), the constraint
set being a frozenset of (expression, wanted truth value). A record of the v2.10 summary is *new* when the same
(key or signature, constraint set) pair is not an alternative of the base (v2.8) summary of the same code hash.
Base alternatives that the v2.10 compaction dropped (subsumption pruning or the 32-alternative cap) are *shadowed*;
removing the new records and re-compacting restores them.

Record type (rule family b), from the record alone:
  kind   site | call
  grp    newgroup (the key / signature is absent from the base summary) | newalt (an existing group gained an alternative)
  idx    the key (site) or target + payload words + payload size (call) contains a loop index (IDX leaf)
  cd     ... contains a calldata read (CD leaf)
  sl     ... contains a storage read (SLOAD leaf)
type string: f"{kind}/{grp}/idx{0|1}/cd{0|1}/sl{0|1}" (32 types).
"""
import os, sys, pickle
sys.path.insert(0, os.path.dirname(__file__))
import evm_static_v210 as E10


def groups(s):
    """compacted summary -> ({key: [frozenset(cons), ...]}, {sig: [frozenset(cons), ...]}) in stored order"""
    if s.get('compact') == 2:
        tab = s['cons_table']
        sg = {key: [frozenset(tab[i] for i in a) for a in alts] for key, pcs, alts, *_ in s['site_groups']}
        cg = {sig: [frozenset(tab[i] for i in a) for a in alts] for sig, pcs, alts, *_ in s['call_groups']}
        return sg, cg
    from build_guided_summaries import expand      # uncompacted summary (e.g. written lazily by the predictor)
    sites, calls = expand(s); sg = {}; cg = {}
    for pc, op, key, cons in sites:
        l = sg.setdefault(key, []); c = frozenset(cons)
        if c not in l: l.append(c)
    for pc, kind, to, aw, asz, cons in calls:
        l = cg.setdefault((kind, to, aw, asz), []); c = frozenset(cons)
        if c not in l: l.append(c)
    return sg, cg


def _leaves_of(kind, ks):
    acc = set()
    if kind == 'site':
        E10.leaves(ks, acc)
    else:
        k, target, argwords, argsize = ks
        E10.leaves(target, acc)
        if isinstance(argsize, tuple): E10.leaves(argsize, acc)
        for rel, v, nb in (argwords or ()):
            if isinstance(rel, tuple): E10.leaves(rel, acc)
            if isinstance(v, tuple): E10.leaves(v, acc)
    return acc


def rtype(kind, ks, groupnew):
    lv = _leaves_of(kind, ks)
    return f"{kind}/{'newgroup' if groupnew else 'newalt'}/idx{int('IDX' in lv)}/cd{int('CD' in lv)}/sl{int('SLOAD' in lv)}"


def diff(s_new, s_base):
    """-> dict with
         new_sites {key: {cons: type}}, new_calls {sig: {cons: type}},
         shadow_sites {key: [cons]}, shadow_calls {sig: [cons]}  (base alternatives absent from the new summary),
         n_new, n_base (records = alternatives)"""
    a_s, a_c = groups(s_new)
    if s_base is None: b_s, b_c = {}, {}
    else: b_s, b_c = groups(s_base)
    out = {'new_sites': {}, 'new_calls': {}, 'shadow_sites': {}, 'shadow_calls': {}}
    for kind, A, B, nk, sk in (('site', a_s, b_s, 'new_sites', 'shadow_sites'), ('call', a_c, b_c, 'new_calls', 'shadow_calls')):
        for ks, alts in A.items():
            old = B.get(ks)
            oset = set(old) if old else set()
            nw = {c: None for c in alts if c not in oset}
            if nw:
                t = rtype(kind, ks, old is None)
                out[nk][ks] = {c: t for c in nw}
            if old:
                aset = set(alts); sh = [c for c in old if c not in aset]
                if sh: out[sk][ks] = sh
    out['n_new'] = sum(len(v) for v in out['new_sites'].values()) + sum(len(v) for v in out['new_calls'].values())
    out['n_base'] = sum(len(v) for v in b_s.values()) + sum(len(v) for v in b_c.values())
    return out


def load_pair(ch, store, base):
    """-> (s_new, s_base) or (None, None) if the store file is the base file (symlink to the same resolved path)"""
    p = f'{store}/{ch}.pkl'; q = f'{base}/{ch}.pkl'
    if not os.path.exists(p): return None, None
    if os.path.exists(q) and os.path.realpath(p) == os.path.realpath(q): return None, None
    s_new = pickle.load(open(p, 'rb'))
    s_base = pickle.load(open(q, 'rb')) if os.path.exists(q) else None
    if s_base is None and s_new.get('compact') != 2:
        return None, None   # a v2 summary the predictor wrote lazily: the base run analyses the same code identically
    return s_new, s_base
