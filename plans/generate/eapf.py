#!/usr/bin/env python3
"""reader and writer of the .eapf access-plan files (src/frame_plan_v3 `Plan::parse` /
`Plan::to_bytes`, file versions 1-3) and structural canonical forms of nodes, condition lists and family call
alternatives (used to decide, from the expression structure alone, which family call groups give the same call)."""
import struct

T_CONST, T_CD, T_ENV, T_LIN, T_OP, T_KEC, T_KECB, T_BYTES, T_REGCD, T_IDX, T_SLOAD, T_UNK = range(12)
NONE32 = 0xFFFFFFFF


class Plan:
    pass


def load(path):
    with open(path, 'rb') as fh: return parse(fh.read())


def parse(b):
    assert b[:4] == b'EAPF', 'bad magic'
    p = Plan(); pos = [4]

    def u32():
        v = struct.unpack_from('<I', b, pos[0])[0]; pos[0] += 4; return v

    def u32s(n):
        v = list(struct.unpack_from(f'<{n}I', b, pos[0])); pos[0] += 4 * n; return v

    def arr(n, k):
        v = u32s(n * k); return [v[i * k:(i + 1) * k] for i in range(n)]

    p.version = u32(); p.kind = u32()
    if p.kind == 1:
        p.delegate = b[12:32]; pos[0] = 32; assert pos[0] == len(b); return p
    if p.kind == 2:
        assert pos[0] == len(b); return p
    nc = u32(); p.consts = [b[pos[0] + 32 * i:pos[0] + 32 * i + 32] for i in range(nc)]; pos[0] += 32 * nc
    p.nodes = arr(u32(), 4)
    p.side = u32s(u32())
    nl = u32(); p.list_off = u32s(nl + 1)
    p.list_data = u32s(u32())
    p.sgroups = u32s(u32())
    p.salts = arr(u32(), 4); p.fgroups = arr(u32(), 4); p.falts = arr(u32(), 9)
    p.side2 = u32s(u32()); p.n_idx = u32()
    p.cgroups, p.cside, p.calts, p.n_family_calls = [], [], [], 0
    p.fcgroups, p.fcalts, p.cside2 = [], [], []
    if p.version >= 2:
        p.cgroups = arr(u32(), 6); p.cside = u32s(u32()); p.calts = arr(u32(), 4); p.n_family_calls = u32()
    if p.version >= 3:
        p.fcgroups = arr(u32(), 8); p.fcalts = arr(u32(), 9); p.cside2 = u32s(u32())
    assert pos[0] == len(b), (pos[0], len(b))
    return p


def to_bytes(p):
    o = bytearray(b'EAPF')
    w = lambda x: o.extend(struct.pack('<I', x))
    ws = lambda v: o.extend(struct.pack(f'<{len(v)}I', *v))
    def wl(v): w(len(v)); ws(v)
    def wa(v):
        w(len(v))
        for r in v: ws(r)
    w(p.version); w(p.kind)
    if p.kind == 1: o.extend(p.delegate); return bytes(o)
    if p.kind == 2: return bytes(o)
    w(len(p.consts))
    for c in p.consts: o.extend(c)
    wa(p.nodes); wl(p.side)
    w(len(p.list_off) - 1); ws(p.list_off); wl(p.list_data)
    wl(p.sgroups); wa(p.salts); wa(p.fgroups); wa(p.falts); wl(p.side2); w(p.n_idx)
    if p.version >= 2: wa(p.cgroups); wl(p.cside); wa(p.calts); w(p.n_family_calls)
    if p.version >= 3: wa(p.fcgroups); wa(p.fcalts); wl(p.cside2)
    return bytes(o)


def tag(p, j): return p.nodes[j][0] & 0xff
def sub(p, j): return (p.nodes[j][0] >> 8) & 0xff
def dep(p, j): return (p.nodes[j][0] >> 16) & 1 == 1


def children(p, j):
    w0, a, b, n = p.nodes[j]; t = w0 & 0xff
    if t in (T_CD, T_SLOAD): return [a]
    if t == T_LIN: return [p.side[b + 2 * k + 1] for k in range(n)]
    if t in (T_OP, T_KEC): return [p.side[b + k] for k in range(n)]
    if t in (T_KECB, T_BYTES): return [p.side[b + 3 * k] for k in range(n)]
    if t == T_REGCD: return [a, b]
    return []


def lst(p, i): return p.list_data[p.list_off[i]:p.list_off[i + 1]]


def idx_ids(p, j, out=None):
    """loop index ids in the subtree of node j"""
    out = set() if out is None else out; st = [j]
    while st:
        x = st.pop()
        if not dep(p, x): continue
        if tag(p, x) == T_IDX: out.add(p.nodes[x][1]); continue
        st.extend(children(p, x))
    return out


class Canon:
    """structural canonical form of nodes, interned as integers: equal ids evaluate equally on every frame and binding,
    once the loop index ids are renamed by `ren` (id -> role); constants compared by value; every field the evaluator
    reads is part of the form"""
    def __init__(self, p):
        self.p = p; self.memo = {}; self.tab = {}

    def _id(self, key):
        v = self.tab.get(key)
        if v is None: v = self.tab[key] = len(self.tab)
        return v

    def node(self, j, ren=None):
        rk = None if ren is None else tuple(sorted(ren.items()))
        key = (j, rk) if dep(self.p, j) else (j, None)   # an index-free subtree does not depend on the renaming
        if key in self.memo: return self.memo[key]
        p = self.p; w0, a, b, n = p.nodes[j]; t = w0 & 0xff; s = (w0 >> 8) & 0xff; d = (w0 >> 16) & 1
        if t == T_CONST: r = ('C', p.consts[a])
        elif t == T_IDX: r = ('I', ren.get(a, ('raw', a)) if ren is not None else ('raw', a))
        elif t == T_ENV: r = ('E', s)
        elif t in (T_CD, T_SLOAD): r = (t, d, self.node(a, ren))
        elif t == T_LIN: r = ('L', d, p.consts[a], tuple((p.consts[p.side[b + 2 * k]], self.node(p.side[b + 2 * k + 1], ren)) for k in range(n)))
        elif t in (T_OP, T_KEC): r = (t, s, d, tuple(self.node(p.side[b + k], ren) for k in range(n)))
        elif t in (T_KECB, T_BYTES): r = (t, d, tuple((self.node(p.side[b + 3 * k], ren), p.side[b + 3 * k + 1], p.side[b + 3 * k + 2]) for k in range(n)))
        elif t == T_REGCD: r = ('R', d, self.node(a, ren), self.node(b, ren))
        elif t == T_UNK: r = ('U', s, a, b, n)
        else: raise ValueError(f'tag {t}')
        v = self.memo[key] = self._id(r)
        return v

    def items(self, li, ren=None):
        if li == NONE32: return None
        return tuple((it >> 31, self.node(it & 0x7FFFFFFF, ren)) for it in lst(self.p, li))

    def target(self, cg):
        """kind, target and payload of a call group (cgroups / fcgroups layout: kind, target, argsize, cside offset, n words)"""
        p = self.p; off, nw = cg[3], cg[4]
        words = tuple((self.node(p.cside[off + 3 * k]), self.node(p.cside[off + 3 * k + 1]), p.cside[off + 3 * k + 2]) for k in range(nw))
        return (cg[0], self.node(cg[1]), None if cg[2] == NONE32 else self.node(cg[2]), words if cg[2] != NONE32 else None)

    def call_nodes(self, cg):
        p = self.p; off, nw = cg[3], cg[4]
        ns = [cg[1]] + ([] if cg[2] == NONE32 else [cg[2]])
        if cg[2] != NONE32:
            for k in range(nw): ns += [p.cside[off + 3 * k], p.cside[off + 3 * k + 1]]
        return ns

    def falt(self, al):
        """family call alternative (fcalts layout) with its fixed indices renamed by position (bound per alternative) and
        the group's key indices renamed by role; for groups whose target and payload do not use the key indices"""
        p = self.p; g = al[0]; cg = p.fcgroups[g]
        off, nx, nfix = al[3], al[4], al[5]
        ren = {}
        for k in range(cg[5]): ren[cg[6 + k]] = ('K', k)
        fx = [(p.cside2[off + nx + 2 * k], p.cside2[off + nx + 2 * k + 1]) for k in range(nfix)]
        for k, (i, _) in enumerate(fx): ren.setdefault(i, ('F', k))
        sel = (al[1], al[2] if al[1] else None, tuple(p.cside2[off:off + nx]))
        return (sel, tuple((ren[i], self.items(li, ren)) for i, li in fx),
                tuple(self.items(al[6 + k], ren) for k in range(cg[5])), self.items(al[8], ren), cg[5])
