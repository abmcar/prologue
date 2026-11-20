#!/usr/bin/env python3
"""CREATE2 salt-template records from the analyzer copy (scripts/evm_static_c2.py), in the restricted form
the node can evaluate at transaction arrival. One record per (code, selector, pc, site kind); the unrolled loop
iterations of one site are merged into one record whose varying segments become index segments.

  record = {sel, site: 'CREATE2'|'C2CALC', pc, creator: SEG|null (null: the frame's ADDRESS),
            salt: {form: 'kec'|'raw', segs: [SEG...]}, init: {hash} | {segs: [SEG...]} | {hash_val: VAL} | null,
            n_sites, dims: number of index segments}
  SEG    = {kind:'const', hex}
         | {kind:'val', val: VAL, lo, hi}                                   bytes lo..hi of the 32-byte word VAL
         | {kind:'index', from: VAL|null, base, bound: VAL|null, lo, hi}    word = from + base + k, k = 0.. while word < bound
         | {kind:'cdarr', off_word, first, stride, len: VAL|null, lo, hi}   word = CD[first + CD(off_word) + stride*k], k < len
  VAL    = {kind:'const', hex} | {kind:'cd', off} | {kind:'cdat', add, off_word}  (= CD[add + CD(off_word)])
         | {kind:'address'|'caller'|'origin'} | {kind:'sload', key: VAL} | {kind:'kec', words: [VAL...]}
         | {kind:'lin', base, val: VAL}
The salt is keccak over the segments ('kec') or the 32 bytes themselves ('raw'). Sites outside the grammar are listed
with a reason. Reads raw/codes/<address>.hex, writes raw/c2records/<codehash>.json and results/c2records.csv."""
import sys, os, json, csv, time, collections
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import evm_static_c2 as E
OUT = os.environ.get('C2REC_OUT', 'c2records')   # used only when this file runs as a script
SHIFT96 = 1 << 96
ENVS = {'ADDRESS': 'address', 'CALLER': 'caller', 'ORIGIN': 'origin'}
class Unsupported(Exception): pass
def pretty(e):
    try: return E.pretty(e)[:90]
    except Exception: return str(e)[:90]

def strip(e):
    """masks and no-op arithmetic that do not change a value's low bytes"""
    while True:
        t = e[0]
        if t == 'OP' and e[1] == 'AND' and (e[2][0] == 'C' or e[3][0] == 'C'):
            e = e[3] if e[2][0] == 'C' else e[2]; continue
        if t == 'OP' and e[1] == 'DIV' and e[3] == ('C', 1): e = e[2]; continue
        if t == 'LIN' and e[1] == 0 and len(e[2]) == 1 and e[2][0][0] == 1: e = e[2][0][1]; continue
        return e

def idx_ids(e):
    if isinstance(e, tuple):
        if e and e[0] == 'IDX': return {e[1]}
        return set().union(*(idx_ids(x) for x in e)) if e else set()
    return set()

def val_of(e):
    """a word known at arrival or by storage reads"""
    e = strip(e); t = e[0]
    if t == 'C': return {'kind': 'const', 'hex': '%064x' % e[1]}
    if t == 'KEC': return {'kind': 'kec', 'words': [val_of(w) for w in e[1]]}
    if t == 'CD':
        o = strip(e[1])
        if o[0] == 'C': return {'kind': 'cd', 'off': o[1]}
        if o[0] == 'LIN' and len(o[2]) == 1 and o[2][0][0] == 1 and strip(o[2][0][1])[0] == 'CD' and strip(o[2][0][1])[1][0] == 'C':
            return {'kind': 'cdat', 'add': o[1], 'off_word': strip(o[2][0][1])[1][1]}
    if t == 'ENV' and e[1] in ENVS: return {'kind': ENVS[e[1]]}
    if t == 'SLOAD': return {'kind': 'sload', 'key': val_of(e[1])}
    if t == 'LIN' and len(e[2]) == 1 and e[2][0][0] == 1: return {'kind': 'lin', 'base': e[1], 'val': val_of(e[2][0][1])}
    if t == 'OP' and e[1] == 'SHR' and e[2][0] == 'C': return {'kind': 'shr', 'by': e[2][1], 'val': val_of(e[3])}
    raise Unsupported('val:' + pretty(e))

def seg_of(expr, lo, hi):
    """one byte segment [lo, hi) of a 32-byte word expression (hidden fields _ids/_c for merging)"""
    e = strip(expr); t = e[0]
    if t == 'C': return {'kind': 'const', 'hex': e[1].to_bytes(32, 'big')[lo:hi].hex()}
    if t == 'LIN' and e[1] == 0 and len(e[2]) == 1 and e[2][0][0] == SHIFT96 and hi <= 20:
        return seg_of(e[2][0][1], lo + 12, hi + 12)         # a 20-byte value shifted into the high bytes
    ids = idx_ids(e)
    if t == 'CD' and ids:
        # a calldata array element: CD[c + CD(off) + stride*i]
        o = strip(e[1])
        if o[0] == 'LIN':
            terms = {strip(x)[0]: (c, strip(x)) for c, x in o[2]}
            if set(terms) == {'CD', 'IDX'} and terms['CD'][0] == 1 and terms['CD'][1][1][0] == 'C':
                return {'kind': 'cdarr', 'off_word': terms['CD'][1][1][1], 'first': o[1], 'stride': terms['IDX'][0], 'len': None, 'lo': lo, 'hi': hi, '_ids': ids, '_c': o[1]}
        raise Unsupported('cd index:' + pretty(e))
    if ids:
        if t == 'IDX': return {'kind': 'index', 'from': None, 'base': 0, 'bound': None, 'lo': lo, 'hi': hi, '_ids': ids, '_c': 0}
        if t == 'LIN':
            rest = [(c, x) for c, x in e[2] if not idx_ids(x)]; ix = [(c, x) for c, x in e[2] if idx_ids(x)]
            if len(ix) != 1 or ix[0][0] != 1 or strip(ix[0][1])[0] != 'IDX' or len(rest) > 1 or (rest and rest[0][0] != 1): raise Unsupported('lin:' + pretty(e))
            return {'kind': 'index', 'from': val_of(rest[0][1]) if rest else None, 'base': e[1], 'bound': None, 'lo': lo, 'hi': hi, '_ids': ids, '_c': e[1]}
        raise Unsupported('idx:' + pretty(e))
    return {'kind': 'val', 'val': val_of(e), 'lo': lo, 'hi': hi}

def segs_of(parts): return [seg_of(e, lo, hi) for e, lo, hi in parts]

def split_bytes(parts, bounds):
    pos = 0; out = [[] for _ in range(len(bounds) - 1)]; j = 0
    for e, lo, hi in parts:
        ln = hi - lo
        while ln > 0:
            take = min(bounds[j + 1] - pos, ln)
            if take < ln and e[0] != 'C': raise Unsupported('segment crosses a boundary')
            out[j].append((e, lo, lo + take)); lo += take; ln -= take; pos += take
            if pos == bounds[j + 1]: j += 1
    if pos != bounds[-1]: raise Unsupported('length %d' % pos)
    return out

def salt_of(salt):
    if salt is None: raise Unsupported('create-nonce')
    if salt[0] == 'KEC': return {'form': 'kec', 'segs': segs_of([(w, 0, 32) for w in salt[1]])}
    if salt[0] == 'KECB': return {'form': 'kec', 'segs': segs_of(list(salt[1]))}
    return {'form': 'raw', 'segs': [seg_of(salt, 0, 32)]}

def init_of(init):
    if init is None: return None
    if init[0] == 'RAW': raise Unsupported('init raw: off=%s size=%s region=%s' % (pretty(init[1]), pretty(init[2]), str(init[3])[:60]))
    if init[0] != 'BYTES': raise Unsupported('init')
    if all(e[0] == 'C' for e, _, _ in init[1]):
        b = b''.join(e[1].to_bytes(32, 'big')[lo:hi] for e, lo, hi in init[1])
        return {'hash': '0x' + E.keccak256(b).hex(), 'len': len(b)}
    return {'segs': segs_of(list(init[1]))}

def hash_seg_of(parts):
    if len(parts) == 1 and (parts[0][1], parts[0][2]) == (0, 32):
        e = parts[0][0]
        if e[0] == 'C': return {'hash': '0x%064x' % e[1]}
        if e[0] == 'KECB': return init_of(('BYTES', e[1]))
        if e[0] == 'KEC': return init_of(('BYTES', tuple((w, 0, 32) for w in e[1])))
        return {'hash_val': val_of(e)}
    raise Unsupported('init hash')

SELW = ('OP', 'SHR', ('C', 224), ('CD', ('C', 0)))
def sel_of(cons):
    for c, flag in cons:
        if flag and c[0] == 'OP' and c[1] == 'EQ':
            if c[2][0] == 'C' and c[3] == SELW: return '%08x' % c[2][1]
            if c[3][0] == 'C' and c[2] == SELW: return '%08x' % c[3][1]
    return None

def bound_of(cons, ids, any_idx=False):
    """the loop condition on an index: word (c + i) < B -> (c, B); None when not found. With `any_idx`, a condition
    on some other loop variable (the loop counter when the salt word counts from a storage value)"""
    for c, flag in cons:
        e = c
        if not flag and e[0] == 'OP' and e[1] == 'ISZERO': e, flag = e[2], True
        if not flag or e[0] != 'OP' or e[1] not in ('LT', 'GT', 'SLT', 'SGT'): continue
        a, b = (e[2], e[3]) if e[1] in ('LT', 'SLT') else (e[3], e[2])
        if (idx_ids(a) & ids or any_idx and idx_ids(a) and not idx_ids(a) & ids) and not idx_ids(b):
            a = strip(a); k = a[1] if a[0] == 'LIN' else 0
            try: return k, val_of(b)
            except Unsupported: return None
    return None

def site_record(pc, name, salt, init, cons):
    if name == 'C2CALC':
        p0 = salt[1][0]
        if not (p0[0][0] == 'C' and p0[0][1].to_bytes(32, 'big')[p0[1]] == 0xff): raise Unsupported('no 0xff')
        pre, creator, saltp, hashp = split_bytes(list(salt[1]), [0, 1, 21, 53, 85])
        cr = segs_of(creator)
        if len(cr) == 1 and cr[0]['kind'] == 'val' and cr[0]['val'] == {'kind': 'address'} and (cr[0]['lo'], cr[0]['hi']) == (12, 32): cr = None
        if len(saltp) == 1 and saltp[0][0][0] in ('KEC', 'KECB') and (saltp[0][1], saltp[0][2]) == (0, 32): s = salt_of(saltp[0][0])
        else: s = {'form': 'raw', 'segs': segs_of(saltp)}
        r = {'sel': sel_of(cons), 'site': name, 'pc': pc, 'creator': cr, 'salt': s, 'init': hash_seg_of(hashp)}
    else:
        r = {'sel': sel_of(cons), 'site': name, 'pc': pc, 'creator': None, 'salt': salt_of(salt), 'init': init_of(init)}
    for s in r['salt']['segs']:
        if '_ids' in s:
            b = bound_of(cons, s['_ids'])
            if b:
                k, B = b
                if s['kind'] == 'index': s['bound'] = B if k == s['_c'] else {'kind': 'lin', 'base': s['_c'] - k, 'val': B}
                else: s['len'] = B                     # element index i < len
            elif s['kind'] == 'index' and (b := bound_of(cons, s['_ids'], any_idx=True)):
                # the loop counter is another variable (k + c' < B): the number of iterations
                k, B = b
                s['count'] = B if k == 0 else {'kind': 'lin', 'base': -k, 'val': B}
    return r

def plain(s):
    return {k: v for k, v in s.items() if not k.startswith('_')}

def merge(recs):
    """records of one (sel, site, pc): the varying segments become index segments with the smallest start"""
    n = len(recs[0]['salt']['segs'])
    if any(len(r['salt']['segs']) != n for r in recs): raise Unsupported('segment counts differ')
    if any(r['init'] != recs[0]['init'] for r in recs) or any(r['creator'] != recs[0]['creator'] for r in recs): raise Unsupported('init/creator differ')
    out = json.loads(json.dumps(recs[0], default=list)); dims = 0
    for i in range(n):
        vs = [r['salt']['segs'][i] for r in recs]
        kinds = {v['kind'] for v in vs}
        if kinds == {'val'} or kinds == {'const'}:
            if all(v == vs[0] for v in vs): out['salt']['segs'][i] = plain(vs[0]); continue
            if kinds == {'const'}:
                vals = sorted(int(v['hex'], 16) for v in vs); lo, hi = 0, 32
                out['salt']['segs'][i] = {'kind': 'index', 'from': None, 'base': vals[0], 'bound': None, 'lo': lo, 'hi': hi}; dims += 1; continue
            # calldata words at increasing dynamic offsets: a calldata array without the loop index visible
            if all(v['val']['kind'] == 'cdat' and v['val']['off_word'] == vs[0]['val']['off_word'] for v in vs):
                adds = sorted(v['val']['add'] for v in vs)
                out['salt']['segs'][i] = {'kind': 'cdarr', 'off_word': vs[0]['val']['off_word'], 'first': adds[0], 'stride': 32, 'len': {'kind': 'cdat', 'add': adds[0] - 32, 'off_word': vs[0]['val']['off_word']}, 'lo': vs[0]['lo'], 'hi': vs[0]['hi']}; dims += 1; continue
            # X, X+1, X+2 ... of the unrolled iterations with no loop index visible: an index from X
            srcs = [v['val']['val'] if v['val']['kind'] == 'lin' else v['val'] for v in vs]
            if all(json.dumps(x, sort_keys=True) == json.dumps(srcs[0], sort_keys=True) for x in srcs):
                starts = [v['val']['base'] if v['val']['kind'] == 'lin' else 0 for v in vs]
                out['salt']['segs'][i] = {'kind': 'index', 'from': srcs[0], 'base': min(starts), 'bound': None, 'lo': vs[0]['lo'], 'hi': vs[0]['hi']}; dims += 1; continue
            raise Unsupported('varying values: ' + ','.join(sorted({v['val']['kind'] for v in vs})))
        lo, hi = next(v for v in vs if 'lo' in v)['lo'], next(v for v in vs if 'lo' in v)['hi']
        if kinds <= {'index', 'const', 'val'}:
            ix = [v for v in vs if v['kind'] == 'index']
            froms = {json.dumps(v['from'], sort_keys=True) for v in ix}
            if len(froms) != 1: raise Unsupported('index sources differ')
            frm = ix[0]['from']
            starts = [int(v['hex'], 16) for v in vs if v['kind'] == 'const']
            if frm is None: starts += [v['base'] for v in ix]
            else:
                # plain (from + c) words of the earlier iterations: must be lin over the same source
                for v in vs:
                    if v['kind'] == 'val':
                        if v['val'] == frm: starts.append(0)
                        elif v['val'].get('kind') == 'lin' and v['val']['val'] == frm: starts.append(v['val']['base'])
                        else: raise Unsupported('index start')
                starts += [v['base'] for v in ix]
            bounds = [v['bound'] for v in ix if v.get('bound')]; counts = [v['count'] for v in ix if v.get('count')]
            out['salt']['segs'][i] = {'kind': 'index', 'from': frm, 'base': min(starts), 'bound': bounds[0] if bounds else None, 'count': counts[0] if counts else None, 'lo': lo, 'hi': hi}; dims += 1; continue
        if kinds <= {'cdarr', 'val'}:
            ca = [v for v in vs if v['kind'] == 'cdarr']
            ow = {v['off_word'] for v in ca} | {v['val']['off_word'] for v in vs if v['kind'] == 'val' and v['val']['kind'] == 'cdat'}
            if len(ow) != 1 or any(v['kind'] == 'val' and v['val']['kind'] != 'cdat' for v in vs): raise Unsupported('array sources differ')
            firsts = [v['first'] for v in ca] + [v['val']['add'] for v in vs if v['kind'] == 'val']
            lens = [v['len'] for v in ca if v.get('len')]
            first = min(firsts)
            out['salt']['segs'][i] = {'kind': 'cdarr', 'off_word': ow.pop(), 'first': first, 'stride': ca[0]['stride'], 'len': lens[0] if lens else {'kind': 'cdat', 'add': first - 32, 'off_word': ca[0]['off_word']}, 'lo': lo, 'hi': hi}; dims += 1; continue
        raise Unsupported('varying segment kinds: ' + ','.join(sorted(kinds)))
    out['n_sites'] = len(recs); out['dims'] = dims
    return out

def infer_counts(records):
    """An address computation that re-derives the proxies of a batch given in calldata has no visible bound on the
    batch-internal index; the creation site of the same code counts that index from a storage counter keyed by the
    batch value (index from S[KEC[batch, c]]): the number of proxies of a batch is that counter's value, so the
    computation's index gets count = S[KEC[<the batch segment's value>, c]]."""
    creates = [r for r in records if r['site'] == 'CREATE2']
    for r in records:
        if r['site'] != 'C2CALC': continue
        segs = r['salt']['segs']
        for p, s in enumerate(segs):
            if s['kind'] != 'index' or s.get('bound') or s.get('count'): continue
            for c in creates:
                cs = c['salt']['segs']
                if len(cs) != len(segs) or cs[p]['kind'] != 'index' or not cs[p].get('from') or cs[p]['from']['kind'] != 'sload': continue
                key = cs[p]['from']['key']
                if key['kind'] != 'kec' or len(key['words']) != 2: continue
                # the batch word of the creation template is another segment's value; in the computation that
                # segment is the calldata array element
                for q, cq in enumerate(cs):
                    if q != p and cq['kind'] == 'val' and cq['val'] == key['words'][0] and segs[q]['kind'] == 'cdarr':
                        s['count'] = {'kind': 'sload', 'key': {'kind': 'kec', 'words': [{'kind': 'segref', 'i': q}, key['words'][1]]}}
                        s['count_inferred'] = True
                        break
                if s.get('count'): break

def sload_keys(obj, out):
    """storage keys (canonical VAL json) read by a record's segments, including keys nested in other keys"""
    if isinstance(obj, dict):
        if obj.get('kind') == 'sload' and 'key' in obj: out.add(json.dumps(obj['key'], sort_keys=True))
        for v in obj.values(): sload_keys(v, out)
    elif isinstance(obj, list):
        for v in obj: sload_keys(v, out)
    return out

def updates_for(an, records):
    """counter updates of the storage keys the records read, per selector: a write S[K] = S[K] + delta (delta a VAL),
    per call, or per item when the write sits in the loop (its path condition or value carries a loop index)"""
    by_sel = collections.defaultdict(dict)
    for pc, key, val, cons in getattr(an, 'sstores', []):
        sel = sel_of(cons)
        try: kj = json.dumps(val_of(key), sort_keys=True)
        except Unsupported: continue
        v = strip(val)
        if v[0] != 'LIN': continue
        rest = []; self_term = False
        for c, x in v[2]:
            xs = strip(x)
            if c == 1 and xs[0] == 'SLOAD':
                try:
                    if json.dumps(val_of(xs[1]), sort_keys=True) == kj and not self_term: self_term = True; continue
                except Unsupported: pass
            rest.append((c, x))
        if not self_term: continue
        in_loop = bool(idx_ids(cons)) or bool(idx_ids(val))
        if rest:
            if len(rest) != 1 or rest[0][0] != 1: continue
            try: d = val_of(rest[0][1])
            except Unsupported: continue
            if v[1]: d = {'kind': 'lin', 'base': v[1], 'val': d}
        else:
            d = {'kind': 'const', 'hex': '%064x' % (v[1] % (1 << 256))}
        ent = by_sel[sel].setdefault(kj, {'key': json.loads(kj), 'deltas': set(), 'per': set()})
        ent['deltas'].add(json.dumps(d, sort_keys=True)); ent['per'].add('item' if in_loop else 'call')
    for r in records:
        keys = sload_keys(r['salt'], set())
        ups = []
        for kj in sorted(keys):
            e = by_sel.get(r['sel'], {}).get(kj)
            if not e: continue
            if len(e['deltas']) == 1:
                ups.append({'key': e['key'], 'delta': json.loads(next(iter(e['deltas']))), 'per': 'item' if 'item' in e['per'] else 'call'})
            else:
                # several constants at one key (an unrolled loop: +1, +2, ...): one per item
                ups.append({'key': e['key'], 'delta': {'kind': 'const', 'hex': '%064x' % 1}, 'per': 'item', 'note': 'several deltas'})
        r['updates'] = ups

def hexify(obj):
    """the node parses the records with plain JSON numbers (64-bit): loop-index bases (possibly 256-bit, possibly
    negative) are written as 0x-hex strings modulo 2^256 under the same key"""
    if isinstance(obj, dict):
        return {k: (('0x%x' % (v % (1 << 256))) if k == 'base' and isinstance(v, int) else hexify(v)) for k, v in obj.items()}
    if isinstance(obj, list): return [hexify(v) for v in obj]
    return obj

def short_seg(s):
    if s['kind'] == 'const': return 'C(%s)' % (s['hex'][:16] + ('..' if len(s['hex']) > 16 else ''))
    if s['kind'] == 'val': return '%s[%d:%d]' % (short_val(s['val']), s['lo'], s['hi'])
    if s['kind'] == 'index': return 'IDX(%s+%d .. <%s)[%d:%d]' % (short_val(s['from']) if s['from'] else '0', s['base'], short_val(s['bound']) if s.get('bound') else ('n=' + short_val(s['count'])) if s.get('count') else '?', s['lo'], s['hi'])
    if s['kind'] == 'cdarr': return 'CDARR(CD[%d+CD(%d)+%d*k], k<%s)[%d:%d]' % (s['first'], s['off_word'], s['stride'], short_val(s['len']) if s['len'] else '?', s['lo'], s['hi'])
    return str(s)
def short_val(v):
    k = v['kind']
    if k == 'const': x = int(v['hex'], 16); return '%x' % x if x < 1 << 64 else '..%x' % (x & 0xffff)
    if k == 'cd': return 'CD(%d)' % v['off']
    if k == 'cdat': return 'CD[%d+CD(%d)]' % (v['add'], v['off_word'])
    if k == 'sload': return 'S[%s]' % short_val(v['key'])
    if k == 'kec': return 'KEC[%s]' % ','.join(short_val(w) for w in v['words'])
    if k == 'lin': return '(%d+%s)' % (v['base'], short_val(v['val']))
    if k == 'shr': return '(%s>>%d)' % (short_val(v['val']), v['by'])
    if k == 'segref': return 'seg%d' % v['i']
    return k.upper()

if __name__ == '__main__':
    rows = []
    for f in sorted(os.listdir(os.path.join(H, '..', 'raw', 'codes'))):
        a = f[:-4]; code = bytes.fromhex(open(os.path.join(H, '..', 'raw', 'codes', f)).read().strip().removeprefix('0x'))
        if not code: continue
        h = '0x' + E.keccak256(code).hex()
        t0 = time.time(); an = E.analyze(code, max_steps=3_000_000, max_forks=200_000, max_pc_visits=1000, time_budget=60); dt = time.time() - t0
        groups = collections.defaultdict(list); reasons = collections.Counter(); seen = set()
        def signature(r):
            sig = []
            for sg in r['salt']['segs']:
                if sg['kind'] == 'const' or sg['kind'] == 'index' and sg['from'] is None: sig.append('ix0')
                elif sg['kind'] == 'index': sig.append(('ix', json.dumps(sg['from'], sort_keys=True)))
                elif sg['kind'] == 'cdarr': sig.append(('arr', sg['off_word']))
                else:
                    v = sg['val']
                    if v['kind'] == 'lin': v = v['val']
                    sig.append(('arr', v['off_word']) if v['kind'] == 'cdat' else ('v', json.dumps(v, sort_keys=True)))
            return tuple(sig)
        for pc, name, salt, init, cons in getattr(an, 'c2sites', []):
            k = (pc, name, repr(salt), repr(init), sel_of(cons))
            if k in seen: continue
            seen.add(k)
            try:
                r = site_record(pc, name, salt, init, cons); groups[(r['sel'], name, pc, signature(r))].append(r)
            except Unsupported as ex: reasons[(pc, name, sel_of(cons), str(ex)[:70])] += 1
        records = []
        for key, recs in sorted(groups.items(), key=lambda kv: (kv[0][2], kv[0][1], kv[0][0] or '')):
            try: records.append(merge(recs))
            except Unsupported as ex: reasons[(key[2], key[1], key[0], 'merge:' + str(ex)[:60])] += len(recs)
        # several signatures under one selector and site (different code paths): keep each, flagged
        by_sel = collections.Counter((r['sel'], r['site'], r['pc']) for r in records)
        for r in records: r['variants'] = by_sel[(r['sel'], r['site'], r['pc'])]
        infer_counts(records)
        updates_for(an, records)
        out = {'codehash': h, 'address': a, 'secs': round(dt, 2), 'records': [hexify(r) for r in records], 'not_converted': [{'pc': k[0], 'site': k[1], 'sel': k[2], 'why': k[3], 'n': v} for k, v in reasons.items()]}
        os.makedirs(OUT, exist_ok=True); json.dump(out, open(os.path.join(OUT, h + '.json'), 'w'), indent=1)
        rows.append([a, h, len(code), round(dt, 2), len(records), sum(reasons.values())])
        print(a[:10], h[:10], 'records', len(records), 'not converted', sorted({(k[0], k[1], k[2], k[3][:40]) for k in reasons}) if reasons else '')
        for r in records:
            init = r['init'] or {}
            print('   sel', r['sel'], r['site'], 'pc', r['pc'], r['salt']['form'], 'dims', r['dims'], 'sites', r['n_sites'], 'init', (init.get('hash') or '')[:12] or ('segs:' + ' '.join(short_seg(s) for s in init['segs']) if 'segs' in init else init), 'creator', [short_seg(s) for s in r['creator']] if r['creator'] else '-')
            print('       salt:', ' | '.join(short_seg(s) for s in r['salt']['segs']))
            for u in r.get('updates', []): print('       update: S[%s] += %s per %s' % (short_val(u['key']), short_val(u['delta']), u['per']))
    w = csv.writer(open(os.path.join(H, '..', 'results', 'c2records.csv'), 'w', newline='')); w.writerow(['address', 'codehash', 'bytes', 'secs', 'records', 'not_converted']); w.writerows(rows)
