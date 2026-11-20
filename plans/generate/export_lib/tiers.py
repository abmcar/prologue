"""Phase 7: record transferability tiers.

A summary record is applied to transactions other than the one(s) that produced it. Whether that is sound
depends on what its expressions are built from:

  T0  only the transaction's own calldata, block/tx environment, constants, loop indices (IDX) and the
      contract's own bytecode (REGION:CODE)  -> transferable to any tx satisfying the record's constraints
  T1  additionally one-hop storage reads (SLOAD)                     -> transferable given a storage oracle
  T2  return data of a call, any other opaque scalar (gas, balances, extcodesize, ...), a dynamic value
      (DYN), or a read of memory the producing path never wrote (guided passes only, flag 'hole')
                                                                      -> not transferable

`expr_flags(e)` gives the set of leaf sources, `tier(flags)` maps them to 0/1/2.  Records carry the tier of
their key/target/payload (`ktier`) and, separately, of their path constraints (`ctier`), because a record
whose KEY is transferable may still be gated by a constraint nobody can evaluate before execution.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import evm_static_v2 as ES

RD_LEAVES = {'OPQ:retword', 'OPQ:rdsize'}
T2_FLAGS = frozenset({'rd', 'opq', 'dyn', 'hole', 'nopayload'})
HOLE = ES.HOLE if hasattr(ES, 'HOLE') else None

def _walk_hole(e, depth=0):
    """True if `e` contains a BYTES/KECB segment produced from unwritten memory (guided pass marker)."""
    if depth > 64 or not isinstance(e, tuple) or not e: return False
    t = e[0]
    if t in ('BYTES', 'KECB'):
        for a, lo, hi in e[1]:
            if a is HOLE or (isinstance(a, tuple) and a[0] == 'HZ'): return True
            if _walk_hole(a, depth + 1): return True
        return False
    if t == 'HZ': return True
    if t == 'CD': return _walk_hole(e[1], depth + 1)
    if t == 'OP': return any(_walk_hole(a, depth + 1) for a in e[2:])
    if t == 'LIN': return any(_walk_hole(a, depth + 1) for _, a in e[2])
    if t == 'KEC': return any(_walk_hole(a, depth + 1) for a in e[1])
    if t == 'SLOAD': return _walk_hole(e[1], depth + 1)
    if t == 'REGION': return _walk_hole(e[2], depth + 1) or _walk_hole(e[3], depth + 1)
    return False

def expr_flags(e, acc=None):
    acc = set() if acc is None else acc
    if e is None: return acc
    for l in ES.leaves(e):
        if l in RD_LEAVES: acc.add('rd')
        elif l.startswith('OPQ'): acc.add('opq')
        elif l.startswith('DYN'): acc.add('dyn')
        elif l == 'SLOAD': acc.add('sload')
        elif l == 'CD' or l == 'REGION:CD': acc.add('cd')
        elif l == 'IDX': acc.add('idx')
        elif l == 'REGION:CODE': acc.add('code')
        elif l.startswith('REGION:'): acc.add('dyn')
        else: acc.add('env')
    if _walk_hole(e): acc.add('hole')
    return acc

def tier(flags):
    if flags & T2_FLAGS: return 2
    if 'sload' in flags: return 1
    return 0

def site_flags(key):
    return expr_flags(key)

def call_flags(target, argwords, argsize):
    f = expr_flags(target)
    if argwords is None: f.add('nopayload'); return f
    if argsize is not None and not isinstance(argsize, int): expr_flags(argsize, f)
    for rel, v, nb in argwords:
        if isinstance(rel, tuple): expr_flags(rel, f)
        expr_flags(v, f)
    return f

def cons_flags(cons):
    f = set()
    for e, _ in cons: expr_flags(e, f)
    return f

def site_tier(key): return tier(site_flags(key))
def call_tier(target, argwords, argsize): return tier(call_flags(target, argwords, argsize))
def cons_tier(cons): return tier(cons_flags(cons))

def flags_str(f): return '+'.join(sorted(f))
