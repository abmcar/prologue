# copy of scripts/sas_wb/evm_static_v210.py. Change (knob AFFINE_MEM, default on): an MLOAD
# whose address is "base + loop-index terms" and that the base-keyed memory model reads as DYN('mem') falls back to
# (a) a word written in a widened iteration of another loop at the same base shape (index ids renamed), or (b) the
# nearest calldata-copy region below it on a base that is a prefix of the address, read as CD(src + offset) with the
# symbolic offset (see _affine_read). A second knob CONST_UNROLL (default 0 = off, not used by the earlier runs) lets loops
# whose stack changes only in constants unroll past max_loop. With AFFINE_MEM=0 and CONST_UNROLL=0 the analyser behaves as sas_wb.
# copy of scripts/sas_det/evm_static_v210.py (itself a copy of the StateAccessSummary analyser,
# see scripts/sas_det/README.md). Changes: the wall-clock budget check is removed; deterministic work counters
# (_CW, see 'work units' below) and a work cap (max_work) checked every 256 steps; marks every 4,096 steps.
"""Static (symbolic) extraction of storage-access summaries from EVM bytecode — v2.10.

v2.10 = v2 (evm_static_v2.py, frozen) + a symbolic free-memory pointer (Phase 13, knob FMP_SYM, default on):
  * a value stored to the free-memory-pointer slot 0x40 that the memory model cannot represent (it has a DYN
    leaf, e.g. p + size with an untracked size) is replaced by a fresh opaque base ('OPQ', 'fmp', pc, n);
    n counts fresh bases on the path, so two dynamic allocations on one path never share a base;
  * an MLOAD of slot 0x40 that would return DYN mints (and stores) such a base as well;
  * loop widening keeps slot 0x40 (and stack/memory values at a constant offset from it) as a fresh base
    instead of deleting the cell / turning the value into ('DYN','widen');
  => the buffer built after such an allocation stays keyed by (base, const off): the CALL argument buffer
     start, its length (end - start folds when both are offsets of the same base) and the selector bytes
     are recovered. The base itself never needs a value: offsets and lengths are differences.
  * SHA3 over "calldata copy region of symbolic length ++ k trailing words" (abi.encodePacked(string, x))
    becomes ('KECB', ((REGION, 0, None), (w0, 0, 32), ...)) instead of an opaque value (knob FMP_SHA3).
The predictor needs no change: an 'OPQ' leaf raises Unknown at prediction time exactly like before.

--- v2 docstring ---

Changes vs v1 (evm_static.py):
  * linear canonical form ('LIN', const, ((coef, term), ...)) for ADD/SUB/MUL-by-const/SHL-by-const,
    so pointer arithmetic folds (sub(add(p,0x44),p) -> 0x44) and any address splits into (base_expr, const_off)
  * base-pointer symbolic memory: mem[(base, off)] with byte-precise composition for unaligned writes
    (encodePacked, MSTORE8, partial CALLDATACOPY) -> ('BYTES', segs) / ('KECB', segs)
  * symbolic-size copy regions (calldatacopy/codecopy/returndatacopy with symbolic len) -> ('REGION', kind, src, len)
    so CALL argument buffers with `bytes` payloads are reconstructable
  * CALL args: any (base, off) range, constant or symbolic size, recorded in write order (seq)
  * loop widening: a back-edge traversed twice forks a widened path in which stride-changing values become
    v + d*('IDX', id) -> parameterized key families {key(i)}; the concrete unrolled sibling continues up to max_loop
  * per-selector pc-visit budgets, (src,dst)-edge loop counting, state dedup after state-dependent forks
  * RETURNDATASIZE==0 before first call, CODESIZE constant, constant CODECOPY reads own bytecode

Expr grammar (hashable nested tuples):
  ('C', int) | ('CD', off) | ('ENV', name) | ('OP', name, a, b, ...) | ('LIN', const, ((coef, term), ...))
  ('KEC', (w0, w1, ...)) | ('KECB', ((expr, lo, hi), ...)) | ('BYTES', ((expr, lo, hi), ...))
  ('SLOAD', key) | ('IDX', id) | ('DYN', reason)
"""
from __future__ import annotations
import sys, os, time as _time
from collections import Counter
from Crypto.Hash import keccak

MASK = (1 << 256) - 1
SIGN = 1 << 255

def keccak256(b: bytes) -> bytes:
    h = keccak.new(digest_bits=256); h.update(b); return h.digest()

# ---------------------------------------------------------------- opcode table
OPS = {
 0x00:('STOP',0,0),0x01:('ADD',2,1),0x02:('MUL',2,1),0x03:('SUB',2,1),0x04:('DIV',2,1),0x05:('SDIV',2,1),
 0x06:('MOD',2,1),0x07:('SMOD',2,1),0x08:('ADDMOD',3,1),0x09:('MULMOD',3,1),0x0a:('EXP',2,1),0x0b:('SIGNEXTEND',2,1),
 0x10:('LT',2,1),0x11:('GT',2,1),0x12:('SLT',2,1),0x13:('SGT',2,1),0x14:('EQ',2,1),0x15:('ISZERO',1,1),
 0x16:('AND',2,1),0x17:('OR',2,1),0x18:('XOR',2,1),0x19:('NOT',1,1),0x1a:('BYTE',2,1),0x1b:('SHL',2,1),
 0x1c:('SHR',2,1),0x1d:('SAR',2,1),0x20:('SHA3',2,1),
 0x30:('ADDRESS',0,1),0x31:('BALANCE',1,1),0x32:('ORIGIN',0,1),0x33:('CALLER',0,1),0x34:('CALLVALUE',0,1),
 0x35:('CALLDATALOAD',1,1),0x36:('CALLDATASIZE',0,1),0x37:('CALLDATACOPY',3,0),0x38:('CODESIZE',0,1),
 0x39:('CODECOPY',3,0),0x3a:('GASPRICE',0,1),0x3b:('EXTCODESIZE',1,1),0x3c:('EXTCODECOPY',4,0),
 0x3d:('RETURNDATASIZE',0,1),0x3e:('RETURNDATACOPY',3,0),0x3f:('EXTCODEHASH',1,1),
 0x40:('BLOCKHASH',1,1),0x41:('COINBASE',0,1),0x42:('TIMESTAMP',0,1),0x43:('NUMBER',0,1),0x44:('PREVRANDAO',0,1),
 0x45:('GASLIMIT',0,1),0x46:('CHAINID',0,1),0x47:('SELFBALANCE',0,1),0x48:('BASEFEE',0,1),0x49:('BLOBHASH',1,1),
 0x4a:('BLOBBASEFEE',0,1),
 0x50:('POP',1,0),0x51:('MLOAD',1,1),0x52:('MSTORE',2,0),0x53:('MSTORE8',2,0),0x54:('SLOAD',1,1),0x55:('SSTORE',2,0),
 0x56:('JUMP',1,0),0x57:('JUMPI',2,0),0x58:('PC',0,1),0x59:('MSIZE',0,1),0x5a:('GAS',0,1),0x5b:('JUMPDEST',0,0),
 0x5c:('TLOAD',1,1),0x5d:('TSTORE',2,0),0x5e:('MCOPY',3,0),0x5f:('PUSH0',0,1),
 0xf0:('CREATE',3,1),0xf1:('CALL',7,1),0xf2:('CALLCODE',7,1),0xf3:('RETURN',2,0),0xf4:('DELEGATECALL',6,1),
 0xf5:('CREATE2',4,1),0xfa:('STATICCALL',6,1),0xfd:('REVERT',2,0),0xfe:('INVALID',0,0),0xff:('SELFDESTRUCT',1,0),
}
for i in range(1,33): OPS[0x5f+i] = (f'PUSH{i}',0,1)
for i in range(1,17): OPS[0x7f+i] = (f'DUP{i}',i,i+1)
for i in range(1,17): OPS[0x8f+i] = (f'SWAP{i}',i+1,i+1)
for i in range(0,5): OPS[0xa0+i] = (f'LOG{i}',i+2,0)

ENV_KNOWN = {'CALLER','ORIGIN','ADDRESS','CALLVALUE','CALLDATASIZE','NUMBER','TIMESTAMP','COINBASE',
             'CHAINID','GASLIMIT','BASEFEE','PREVRANDAO','BLOBBASEFEE'}
ENV_DYN = {'GASPRICE','GAS','MSIZE','PC','SELFBALANCE'}

def disassemble(code: bytes):
    ins = {}; pc = 0; n = len(code)
    while pc < n:
        b = code[pc]
        if b in OPS:
            name = OPS[b][0]
            if 0x60 <= b <= 0x7f:
                k = b - 0x5f; val = int.from_bytes(code[pc+1:pc+1+k].ljust(k, b'\0'), 'big')
                ins[pc] = (name, val, pc+1+k); pc += 1+k; continue
            ins[pc] = (name, None, pc+1)
        else:
            ins[pc] = ('INVALID', None, pc+1)
        pc += 1
    return ins

# ---------------------------------------------------------------- expressions
def C(v): return ('C', v & MASK)
def is_c(e): return e[0] == 'C'
DYN_MEM = ('DYN','mem')
# Guided (concolic) mode only: a single memory base whose offsets are CONCRETE byte addresses obtained by
# evaluating the address expression under the guide. Aliasing is then exactly as precise as a real
# execution (this is what the symbolic base-pointer model loses on ABI encoders), while every stored
# VALUE stays symbolic and each cell remembers the symbolic address expression it was reached by, so a
# CALL record's word offsets can be emitted as symbolic differences instead of guide-specific integers.
CONC = ('CONC',)
_MISS = object()
# Guided passes replace these unknown-but-fixed scalars by opaque symbols ('OPQ', tag, pc) instead of
# ('DYN', tag). The stand-in values below are used ONLY to decide memory aliasing and guide branches;
# every recorded expression keeps the symbol, and offsets recorded as symbolic differences cancel it.
OPQ_STANDIN = {'rdsize': 32, 'callresult': 1, 'gas': 5_000_000, 'gasprice': 10**9, 'msize': 0x200,
               'selfbalance': 0, 'balance': 0, 'extcodesize': 1, 'extcodehash': 0, 'blockhash': 0,
               'blobhash': 0, 'tload': 0, 'sha3': 0, 'create': 0, 'retword': 0, 'returndata': 0,
               'fmp': 1 << 40}   # v2.10: above max_conc_addr -> a fresh fmp base stays a SYMBOLIC base under a guide
FMP_SYM = os.environ.get('FMP_SYM', '1') != '0'      # v2.10 symbolic free-memory pointer
FMP_SHA3 = os.environ.get('FMP_SHA3', '1') != '0'    # v2.10 keccak(region ++ trailing words)
FMP_SHA3_MAXW = 4
DBG_MLOAD = None     # debug hook (phase13_debug.py): Counter of (pc, dyn tag, base kind, off) for MLOADs returning DYN
def _dbg_b(b):
    return 'abs' if not isinstance(b, tuple) else ('CONC' if b is CONC else b[0] + (':' + b[1] + '@' + str(b[2]) if b[0] == 'OPQ' else ''))
ZERO = ('C', 0)
# Guided (CONC) memory only: a byte of a composed word that NO write on the path covered. It evaluates to 0
# exactly like unwritten EVM memory, but stays visible as a leaf so a record built from it can be flagged
# as depending on unwritten memory (transferability tier T2, scripts/tiers.py). Unguided paths keep ZERO.
HZ = ('HZ',)

def leaves(e, acc=None):
    acc = set() if acc is None else acc
    t = e[0]
    if t == 'C': pass
    elif t == 'CD': acc.add('CD'); leaves(e[1], acc)
    elif t == 'ENV': acc.add(e[1])
    elif t == 'OP':
        for a in e[2:]: leaves(a, acc)
    elif t == 'LIN':
        for _, a in e[2]: leaves(a, acc)
    elif t == 'KEC':
        for a in e[1]: leaves(a, acc)
    elif t in ('KECB', 'BYTES'):
        for a, _, _ in e[1]: leaves(a, acc)
    elif t == 'SLOAD': acc.add('SLOAD'); leaves(e[1], acc)
    elif t == 'IDX': acc.add('IDX')
    elif t == 'DYN': acc.add('DYN:'+str(e[1]))
    elif t == 'OPQ': acc.add('OPQ:'+e[1])
    elif t == 'HZ': acc.add('HOLE')
    elif t == 'REGION': acc.add('REGION:'+e[1]); leaves(e[2], acc); leaves(e[3], acc)
    return acc

def idx_ids(e, acc=None):
    acc = set() if acc is None else acc
    t = e[0]
    if t == 'IDX': acc.add(e[1])
    elif t == 'CD': idx_ids(e[1], acc)
    elif t == 'OP':
        for a in e[2:]: idx_ids(a, acc)
    elif t == 'LIN':
        for _, a in e[2]: idx_ids(a, acc)
    elif t == 'KEC':
        for a in e[1]: idx_ids(a, acc)
    elif t in ('KECB', 'BYTES'):
        for a, _, _ in e[1]: idx_ids(a, acc)
    elif t == 'SLOAD': idx_ids(e[1], acc)
    elif t == 'REGION': idx_ids(e[2], acc); idx_ids(e[3], acc)
    return acc

_IDX_CACHE = {}
# work units: 0 steps (unused, Analyzer.steps), 1 memory-state copies, 2 dedup keys, 3 records, 4 new expression
# nodes, 5 forks, 6 memory composition, 7 widening, 8 stack scans. Counted in element counts, independent of the machine.
_CW = [0] * 9
def idx_ids_c(e):
    """cached idx_ids keyed by object identity (summary records are long-lived objects)"""
    r = _IDX_CACHE.get(id(e))
    if r is not None and r[0] is e: return r[1]
    if len(_IDX_CACHE) > 2_000_000: _IDX_CACHE.clear()
    ids = frozenset(idx_ids(e)); _IDX_CACHE[id(e)] = (e, ids); return ids

def classify(e):
    """A: known pre-execution from tx + block env (IDX allowed); B: needs storage reads; C: dynamic."""
    L = leaves(e)
    if any(l.startswith(('DYN', 'OPQ')) for l in L): return 'C'
    if 'SLOAD' in L: return 'B'
    return 'A'

def to_signed(v): return v - (1<<256) if v & SIGN else v

MAX_SIZE = 64
_intern = {}
_size = {}
_order = {}
def intern(e):
    c = _intern.get(e)
    if c is not None: return c
    if len(_intern) > 200_000: _intern.clear(); _size.clear(); _order.clear()
    _intern[e] = e; _CW[4] += 1
    t = e[0]
    if t in ('C','ENV','DYN','IDX','OPQ','HZ'): n = 1
    elif t == 'CD': n = 1 + size(e[1])
    elif t == 'OP': n = 1 + sum(size(a) for a in e[2:])
    elif t == 'LIN': n = 1 + sum(size(a) for _, a in e[2])
    elif t == 'KEC': n = 1 + sum(size(a) for a in e[1])
    elif t in ('KECB', 'BYTES'): n = 1 + sum(size(a) for a, _, _ in e[1])
    elif t == 'SLOAD': n = 1 + size(e[1])
    elif t == 'REGION': n = 1 + size(e[2]) + size(e[3])
    else: n = 1
    _size[id(e)] = n; _order[id(e)] = len(_order)
    return e
def size(e):
    n = _size.get(id(e))
    if n is None:
        e = intern(e); n = _size.get(id(e), 1)
    return n
def order(e):
    o = _order.get(id(e))
    if o is None:
        e = intern(e); o = _order.get(id(e), 0)
    return o

def mk(e):
    e = intern(e)
    return ('DYN','big') if size(e) > MAX_SIZE else e

# ---- linear forms
def lin(e):
    """-> (const, {term: coef}) with coefs mod 2^256"""
    t = e[0]
    if t == 'C': return e[1], {}
    if t == 'LIN': return e[1], dict((a, c) for c, a in e[2])
    return 0, {e: 1}

def from_lin(k, terms):
    k &= MASK
    terms = {a: c & MASK for a, c in terms.items() if c & MASK}
    if not terms: return C(k)
    if k == 0 and len(terms) == 1:
        (a, c), = terms.items()
        if c == 1: return a
    items = tuple(sorted(((c, a) for a, c in terms.items()), key=lambda ca: order(ca[1])))
    return mk(('LIN', k, items))

def lin_add(a, b, sign=1):
    ka, ta = lin(a); kb, tb = lin(b)
    terms = dict(ta)
    for x, c in tb.items(): terms[x] = terms.get(x, 0) + sign * c
    return from_lin(ka + sign * kb, terms)

def lin_scale(a, m):
    ka, ta = lin(a)
    return from_lin(ka * m, {x: c * m for x, c in ta.items()})

def split_addr(e):
    """address expr -> (base, off) ; base is an interned expr or 0 for absolute; None if unknown"""
    t = e[0]
    if t == 'C': return 0, e[1]
    if t == 'DYN': return None, 0
    if t == 'LIN':
        k, items = e[1], e[2]
        if len(items) == 1 and items[0][0] == 1: base = items[0][1]
        else: base = mk(('LIN', 0, items))
        if k >= 1 << 255: k -= 1 << 256   # negative offsets (rare)
        if base[0] == 'DYN': return None, 0
        return base, k
    return e, 0

def _div(a,b): return a//b if b else 0
def _sdiv(a,b):
    if b == 0: return 0
    sa, sb = to_signed(a), to_signed(b); q = abs(sa)//abs(sb); return (q if (sa<0)==(sb<0) else -q) & MASK
def _mod(a,b): return a%b if b else 0
def _smod(a,b):
    if b == 0: return 0
    sa, sb = to_signed(a), to_signed(b); r = abs(sa)%abs(sb); return (-r if sa<0 else r) & MASK
def _exp(a,b): return pow(a,b,1<<256)
def _signext(b,x):
    if b >= 31: return x
    bit = b*8+7; mask = (1<<(bit+1))-1
    return (x | (MASK ^ mask)) if (x>>bit)&1 else (x & mask)
def _byte(i,x): return (x >> (8*(31-i))) & 0xff if i < 32 else 0
def _shl(s,x): return (x << s) & MASK if s < 256 else 0
def _shr(s,x): return x >> s if s < 256 else 0
def _sar(s,x):
    sx = to_signed(x)
    return (sx >> s) & MASK if s < 256 else (MASK if sx < 0 else 0)
ARITH = {
 'ADD': lambda a,b:(a+b)&MASK, 'MUL': lambda a,b:(a*b)&MASK, 'SUB': lambda a,b:(a-b)&MASK,
 'DIV': _div, 'SDIV': _sdiv, 'MOD': _mod, 'SMOD': _smod,
 'ADDMOD': lambda a,b,n:(a+b)%n if n else 0, 'MULMOD': lambda a,b,n:(a*b)%n if n else 0, 'EXP': _exp,
 'SIGNEXTEND': _signext, 'LT': lambda a,b:int(a<b), 'GT': lambda a,b:int(a>b),
 'SLT': lambda a,b:int(to_signed(a)<to_signed(b)), 'SGT': lambda a,b:int(to_signed(a)>to_signed(b)),
 'EQ': lambda a,b:int(a==b), 'ISZERO': lambda a:int(a==0), 'AND': lambda a,b:a&b, 'OR': lambda a,b:a|b,
 'XOR': lambda a,b:a^b, 'NOT': lambda a: a ^ MASK, 'BYTE': _byte, 'SHL': _shl, 'SHR': _shr, 'SAR': _sar,
}

def fold(name, args):
    if all(is_c(a) for a in args):
        try: return C(ARITH[name](*[a[1] for a in args]))
        except Exception: pass
    if any(a[0] == 'DYN' for a in args):
        return ('DYN', 'big') if any(a[1] == 'big' for a in args if a[0] == 'DYN') else ('DYN', 'arith')
    if name == 'ADD': return lin_add(args[0], args[1])
    if name == 'SUB': return lin_add(args[0], args[1], -1)
    if name == 'MUL':
        if is_c(args[0]): return lin_scale(args[1], args[0][1])
        if is_c(args[1]): return lin_scale(args[0], args[1][1])
    if name == 'SHL' and is_c(args[0]) and args[0][1] < 256:
        return lin_scale(args[1], 1 << args[0][1])
    if name == 'AND':
        # mask of an already-masked value / masking a LIN of a clean address is common; keep as OP
        pass
    if name == 'EQ' and args[0] == args[1]: return C(1)
    if sum(size(a) for a in args) >= MAX_SIZE: return ('DYN', 'big')
    return intern(('OP', name, *args))

# masked-pointer library calls as internal calls; off by default (output unchanged)
MASKED_CALL = os.environ.get('SAS_MASKED_CALL', '0') == '1'

class Unknown(Exception): pass

def _bytes32(v): return v.to_bytes(32, 'big')

def evaluate(e, ctx, depth=0):
    """Concretize. ctx: calldata(bytes), env(dict), sload(fn)|None, idx(dict id->int)|None, cd_unknown(list of (lo,hi))|None."""
    if depth > 200: raise Unknown('depth')
    t = e[0]
    if t == 'C': return e[1]
    if t == 'HZ': return 0
    if t == 'CD':
        off = evaluate(e[1], ctx, depth+1)
        if off > 1<<32: return 0
        unk = ctx.get('cd_unknown')
        if unk:
            for lo, hi in unk:
                if off < hi and off + 32 > lo: raise Unknown('cd-unknown')
        d = ctx['calldata']; return int.from_bytes(d[off:off+32].ljust(32, b'\0'), 'big')
    if t == 'ENV':
        v = ctx['env'].get(e[1])
        if v is None: raise Unknown('env:'+e[1])
        return v
    if t == 'LIN':
        v = e[1]
        for c, a in e[2]: v += c * evaluate(a, ctx, depth+1)
        return v & MASK
    if t == 'OP':
        return ARITH[e[1]](*[evaluate(a, ctx, depth+1) for a in e[2:]])
    if t == 'KEC':
        return int.from_bytes(keccak256(b''.join(_bytes32(evaluate(w, ctx, depth+1)) for w in e[1])), 'big')
    if t == 'KECB':
        return int.from_bytes(keccak256(eval_segments(e[1], ctx, depth+1)), 'big')
    if t == 'BYTES':
        return int.from_bytes(eval_segments(e[1], ctx, depth+1), 'big')
    if t == 'SLOAD':
        f = ctx.get('sload')
        if f is None: raise Unknown('sload')
        return f(evaluate(e[1], ctx, depth+1))
    if t == 'IDX':
        ix = ctx.get('idx')
        if ix is None or e[1] not in ix: raise Unknown('idx')
        return ix[e[1]]
    if t == 'OPQ':
        # only the guided analyzer supplies concrete stand-ins (for the aliasing/branch decision);
        # at prediction time this always raises, so a record that truly depends on one is dropped
        v = ctx.get('opq')
        if v is None: raise Unknown('opq:'+e[1])
        x = v.get(e)                 # exact symbol: a value the return-data oracle pinned down
        return x if x is not None else v.get(e[1], 0)
    raise Unknown('dyn:'+str(e[1]))

def eval_segments(segs, ctx, depth):
    out = bytearray()
    for a, lo, hi in segs:
        if a[0] == 'REGION':
            rb = eval_region(a, ctx, depth)
            out += rb[lo:hi].ljust(hi - lo, b'\0') if hi is not None else rb[lo:]
        else:
            out += _bytes32(evaluate(a, ctx, depth))[lo:hi]
    return bytes(out)

def eval_region(r, ctx, depth):
    """('REGION', kind, src, len) -> bytes"""
    kind, src, ln = r[1], r[2], r[3]
    n = evaluate(ln, ctx, depth)
    if n > 1 << 20: raise Unknown('region-size')
    s = evaluate(src, ctx, depth)
    if kind == 'CD':
        unk = ctx.get('cd_unknown')
        if unk:
            for lo, hi in unk:
                if s < hi and s + n > lo: raise Unknown('cd-unknown')
        return bytes(ctx['calldata'][s:s+n].ljust(n, b'\0'))
    if kind == 'CODE':
        code = ctx.get('code')
        if code is None: raise Unknown('code')
        return bytes(code[s:s+n].ljust(n, b'\0'))
    raise Unknown('region:'+kind)

# ---------------------------------------------------------------- memory model
# mem: dict (base, off) -> (seq, val, nbytes)      base: interned expr | 0 ; off: int ; nbytes 32 or 1 (MSTORE8) or k (partial)
# residues: dict base -> set(off % 32) plus 'P' if any partial write ; regions: list (base, off, kind, src, len, seq)

class MemState:
    __slots__ = ('w', 'res', 'regions', 'seq', 'h', 'sym', 'ncall', 'nfmp')
    def __init__(self, w=None, res=None, regions=None, seq=0, h=0, sym=None, ncall=0, nfmp=0):
        self.w = {} if w is None else w; self.res = {} if res is None else res
        self.regions = [] if regions is None else regions; self.seq = seq; self.h = h
        self.sym = {} if sym is None else sym      # concrete addr -> symbolic addr expr (guided mode only)
        self.ncall = ncall                          # calls executed on this path (guide alignment index)
        self.nfmp = nfmp                            # v2.10: fresh free-memory-pointer bases minted on this path
    def copy(self):
        _CW[1] += len(self.w) + len(self.res) + len(self.regions) + 1
        return MemState(dict(self.w), {b: set(r) for b, r in self.res.items()}, list(self.regions),
                        self.seq, self.h, dict(self.sym), self.ncall, self.nfmp)
    def rehash(self):
        self.h = 0; _CW[7] += len(self.w)
        for k, (seq, val, nb) in self.w.items(): self.h ^= hash((k, val, nb))

def mem_write(m: MemState, base, off, val, nbytes=32):
    m.seq += 1
    k = (base, off); old = m.w.get(k)
    if old is not None: m.h ^= hash((k, old[1], old[2]))
    m.h ^= hash((k, val, nbytes))
    m.w[k] = (m.seq, val, nbytes)
    r = m.res.get(base)
    if r is None: r = m.res[base] = set()
    r.add(off % 32)
    if nbytes != 32: r.add('P')

def mem_region(m: MemState, base, off, kind, src, ln):
    m.seq += 1
    m.regions.append((base, off, kind, src, ln, m.seq))
    if len(m.regions) > 8: m.regions.pop(0)
    r = m.res.get(base)
    if r is None: r = m.res[base] = set()
    r.add('R')

def _region_hit(m, base, off, need_seq=-1):
    """newest region on `base` covering byte `off` (len symbolic: assume covers off>=start, and off<start+len if len const)"""
    best = None
    for (b, o, kind, src, ln, seq) in m.regions:
        if b != base or o > off or seq <= need_seq: continue
        if is_c(ln) and off >= o + ln[1]: continue
        if best is None or seq > best[5]: best = (b, o, kind, src, ln, seq)
    return best

def region_word(reg, off):
    b, o, kind, src, ln, seq = reg
    d = off - o
    if kind == 'CD': return mk(('CD', lin_add(src, C(d))))
    if kind == 'CODE': return ('DYN', 'codecopy-sym')
    return ('DYN', kind.lower() + '-region')

AFFINE_MEM = os.environ.get('AFFINE_MEM', '1') != '0'
CONST_UNROLL = int(os.environ.get('CONST_UNROLL', '0'))   # 0 = off (sas_wb behaviour)


def _is_idx(x): return x[0] == 'IDX'


def _subst(e, mp):
    """e with the sub-expressions in mp replaced"""
    r = mp.get(e)
    if r is not None: return r
    if not isinstance(e, tuple): return e
    out = tuple(_subst(x, mp) if isinstance(x, tuple) else x for x in e)
    return intern(out) if out != e else e


def _affine_read(m: MemState, base, off):
    """value of the 32-byte word at symbolic address base + off that mem_read could not resolve (DYN_MEM),
    or None. (a) a word written at the same offset on a base that differs from `base` only in the ids of its loop-index
    terms (same coefficients, same other terms): written in a widened iteration of an earlier loop (an ABI decoder's
    copy loop) and read in a later one; its value is returned with the index ids renamed. (b) the nearest copy region
    (largest start <= off, newest on ties) on a base b_r whose linear terms all appear in `base` with the same
    coefficient (b_r = 0: absolute memory), when no later word write on b_r starts at or after the region start: a
    calldata region gives CD(src + (base - b_r) + off - start)."""
    if base == 0 or base is CONC: return None
    kB, tB = lin(base)
    if any(x[0] == 'DYN' for x in tB): return None
    _CW[6] += len(m.w) + len(m.regions)
    iB = {x: c for x, c in tB.items() if _is_idx(x)}
    oB = {x: c for x, c in tB.items() if not _is_idx(x)}
    best = None
    if iB:
        for (bb, oo), (seq, val, nb) in m.w.items():
            if oo != off or nb != 32 or bb == 0 or bb is CONC or bb == base: continue
            kb, tb = lin(bb)
            if kb != kB: continue
            ib = {x: c for x, c in tb.items() if _is_idx(x)}
            ob = {x: c for x, c in tb.items() if not _is_idx(x)}
            if ob != oB or len(ib) != len(iB) or not ib: continue
            mp = {}
            for xb, cb in ib.items():
                cand = [x for x, c in iB.items() if c == cb and x not in mp.values()]
                if len(cand) != 1: mp = None; break
                mp[xb] = cand[0]
            if mp is None: continue
            if best is None or seq > best[0]: best = (seq, val, mp)
        if best is not None:
            v = best[1]
            if v[0] == 'DYN': return None
            return _subst(v, best[2])
    reg = None
    for (b, o, kind, src, ln, seq) in m.regions:
        if o > off: continue
        if b == 0:
            extra = dict(tB); k0 = kB
        else:
            if b is CONC: continue
            kr, tr = lin(b)
            if any(tB.get(x) != c for x, c in tr.items()): continue
            extra = {x: c for x, c in tB.items() if x not in tr}; k0 = kB - kr
        if not extra: continue
        if reg is None or o > reg[0][1] or (o == reg[0][1] and seq > reg[0][5]): reg = ((b, o, kind, src, ln, seq), extra, k0)
    if reg is None: return None
    (b, o, kind, src, ln, seq), extra, k0 = reg
    if kind != 'CD': return None
    for (bb, oo), (wseq, val, nb) in m.w.items():
        if bb == b and wseq > seq and oo + nb > o: return None
    return mk(('CD', lin_add(src, from_lin(k0 + off - o, extra))))


def mem_read(m: MemState, base, off, nbytes=32):
    """read `nbytes` (<=32) at (base, off) as a 256-bit expr (right-aligned when nbytes<32 not needed: callers use 32)"""
    r = m.res.get(base)
    if r is None: return DYN_MEM
    ex = m.w.get((base, off))
    if base is CONC:
        segs = compose(m, base, off, nbytes)
        if segs is None: return DYN_MEM
        if len(segs) == 1 and segs[0][1] == 0 and segs[0][2] == 32 and segs[0][0][0] != 'REGION':
            return segs[0][0]
        return mk(('BYTES', tuple(segs)))
    if ex is not None and ex[2] == 32 and r <= {off % 32} :
        return ex[1]
    if 'R' not in r and 'P' not in r and r <= {off % 32}:
        return ex[1] if ex is not None else DYN_MEM
    # slow path: byte composition
    segs = compose(m, base, off, nbytes)
    if segs is None: return DYN_MEM
    if len(segs) == 1 and segs[0][1] == 0 and segs[0][2] == 32 and segs[0][0][0] != 'REGION': return segs[0][0]
    return mk(('BYTES', tuple(segs)))

def compose(m: MemState, base, off, n):
    """-> list of (expr, lo, hi) covering bytes [off, off+n) newest-write-wins; None if any byte is unknown-dynamic"""
    cover = [None] * n   # per byte: (seq, expr, byte_index_within_expr, kind)
    _CW[6] += (63 if base is CONC else len(m.w)) + len(m.regions)
    if base is CONC:
        # all writes are keyed by integer address, so only keys in [off-31, off+n) can cover the range
        src = (((base, off + d), m.w[(base, off + d)]) for d in range(-31, n) if (base, off + d) in m.w)
    else:
        src = m.w.items()
    for (b, o), (seq, val, nb) in src:
        if b != base: continue
        lo = max(o, off); hi = min(o + nb, off + n)
        if lo >= hi: continue
        for p in range(lo, hi):   # convention: a write of nb bytes stores the FIRST nb bytes of val
            c = cover[p - off]
            if c is None or seq > c[0]: cover[p - off] = (seq, val, p - o)
    for (b, o, kind, src, ln, seq) in m.regions:
        if b != base: continue
        lo = max(o, off); hi = off + n if not is_c(ln) else min(o + ln[1], off + n)
        if lo >= hi: continue
        reg = ('REGION', kind, src, ln)
        for p in range(lo, hi):
            c = cover[p - off]
            if c is None or seq > c[0]: cover[p - off] = (seq, reg, p - o)
    if all(c is None for c in cover): return None
    segs = []
    hole = HZ if base is CONC else ZERO      # guided passes keep unwritten bytes visible (see HZ)
    for i, c in enumerate(cover):
        if c is None:
            expr, bi = hole, i   # unwritten memory reads as zero
        else:
            expr, bi = c[1], c[2]
        if expr[0] == 'DYN': return None
        if segs and segs[-1][0] is expr and segs[-1][2] == bi:
            segs[-1][2] = bi + 1
        else:
            segs.append([expr, bi, bi + 1])
    out = []
    for expr, lo, hi in segs:
        if expr is ZERO or expr is HZ: lo, hi = 32 - (hi - lo), 32
        out.append((expr, lo, hi))
    return out

# ---------------------------------------------------------------- symbolic executor
class Budget(Exception): pass

WK_DEFAULT = (1, 0, 0, 0, 0, 0, 0, 0, 0)   # weights of the work units (steps only unless set)
def _rss_mb():   # diagnostics only (marks); never used in a decision
    try: return int(open('/proc/self/statm').read().split()[1]) * 4096 >> 20
    except OSError: return -1

WIDENED = 1 << 30

class Analyzer:
    def __init__(self, code: bytes, max_steps=400_000, max_pc_visits=40, max_forks=20_000, max_stack=1024,
                 time_budget=60.0, max_loop=3, widen=True, dedup=True,
                 max_loop_guided=32, guide_widen=False, max_arg_words=128, expr_max_size=0,
                 max_conc_addr=1 << 22, opq_decide=False,
                 opq_scalars=True, rd_strict=True):
        self.code = code; self.ins = disassemble(code)
        self.jumpdests = {pc for pc,(n,_,_) in self.ins.items() if n == 'JUMPDEST'}
        self.retblock = {pc for pc in self.jumpdests if self._is_return_block(pc)}
        # JUMP whose target was not pushed by the immediately preceding instruction: subroutine return / computed jump
        self.indirect_jump = set(); self.masked_call = set(); prev = None; prev2 = None
        for pc in sorted(self.ins):
            name = self.ins[pc][0]
            if name == 'JUMP' and not (prev or '').startswith('PUSH'): self.indirect_jump.add(pc)
            # a library call through a masked function pointer, `PUSH f; AND; JUMP`
            # (solc 0.5/0.6 internal calls of `using L for T` functions), is an internal call, not a subroutine return
            if MASKED_CALL and name == 'JUMP' and prev == 'AND' and (prev2 or '').startswith('PUSH'): self.masked_call.add(pc)
            prev2 = prev; prev = name
        self.max_steps = max_steps; self.max_pc_visits = max_pc_visits; self.max_forks = max_forks
        self.max_loop = max_loop; self.widen = widen; self.dedup = dedup; self.widen_budget = 500; self.max_widen = 2000
        self.sites = set(); self.calls = set()
        self.pc_visits = Counter(); self.steps = 0; self.forks = 0; self.n_widen = 0; self.n_dedup = 0
        self._marks = []   # sas_det
        self.static_sites = {pc for pc,(n,_,_) in self.ins.items() if n in ('SLOAD','SSTORE')}
        self.static_calls = {pc for pc,(n,_,_) in self.ins.items() if n in ('CALL','STATICCALL','DELEGATECALL','CALLCODE')}
        self.covered_sites = set(); self.covered_calls = set(); self.truncated = False
        self.unresolved_jumps = 0; self.idx_counter = 0; self.seen_states = set()
        self.cw = _CW; _CW[:] = [0] * len(_CW); self.max_work = float('inf'); self.w_chk = 0; self.wk = None; self._chks = []
        self.trace = None; self.guide = None
        # ---- guided (concolic) mode: a guide is a ctx dict {'calldata': bytes, 'env': {...}} used ONLY to
        # decide branches. No concrete value is ever substituted into a recorded expression, so every record
        # emitted under a guide is still symbolic in calldata and carries its own path-constraint set.
        self.max_loop_guided = max_loop_guided; self.guide_widen = guide_widen
        self.max_arg_words = max_arg_words; self.arg_skip = Counter(); self.arg_debug = None
        self.max_conc_addr = max_conc_addr; self.opq_decide = opq_decide
        self.opq_scalars = opq_scalars; self._gcache = {}
        self.n_conc = 0; self.n_conc_fail = 0; self.n_rel_sym = 0; self.n_rel_unknown = 0
        self.n_alias_assumed = 0; self.n_opq = 0; self.n_cons_opq = 0
        self.n_affine = 0; self.n_const_unroll = 0; self.n_zero_slot = 0; self.n_fmp_store = 0; self.n_fmp_load = 0; self.n_fmp_widen = 0; self.n_fmp_widen_rel = 0; self.n_sha3_tail = 0
        self.guide_rd = None; self.n_rd_bound = 0; self.n_rd_missing = 0
        self.n_rd_aligned = 0; self.n_rd_mismatch = 0; self.n_rd_unverified = 0
        self.rd_strict = rd_strict
        self._gctx = None
        self.expr_max_size = expr_max_size
        self.n_guides = 0; self.n_guided_dec = 0; self.n_guide_unknown = 0; self.guide_truncated = 0
        self.guide_gain = []; self.guided_sites = set(); self.guided_calls = set()
        self._t0 = _time.time(); self.time_budget = time_budget

    def run(self):
        m = MemState(); mem_write(m, 0, 0x40, C(0x80))
        # state: pc, stack, mem, cons, loops(dict edge->[count, stack_snap, mem_snap]), tag, called, dd(dedup pending)
        work = [(0, [], m, (), {}, None, False, 0, None, 0, ())]
        try:
            while work:
                st = work.pop()
                self._exec_path(*st, work)
        except Budget:
            self.truncated = True
        return self

    def run_guided(self, guides, time_budget_each=None):
        """Concolic passes on top of whatever `run()` already recorded.

        `guides` : list of ctx dicts {'calldata': bytes, 'env': {name: int}} (see `evaluate`).
        Invariants (relied on by predict.py, which is unchanged):
          * the guide is consulted ONLY at a JUMPI whose condition is fully known and index-free;
            the taken direction is appended to the path-constraint set exactly as in the unguided
            executor, so a record is still gated by the constraints of the path that produced it;
          * no concrete value is substituted into stack/memory/keys -- calldata stays the symbolic
            ('CD', off) leaf, so records generalize to any transaction whose constraints hold;
          * records accumulate into the same self.sites / self.calls sets, hence a guided summary is a
            SUPERSET of the unguided one (monotone in recall, never removes a record);
          * budgets (steps/forks/pc-visits/state dedup) are re-armed per guide so one guide cannot
            starve the next one.
        """
        base_cov = set(self.covered_sites); base_covc = set(self.covered_calls)
        base_n = (len(self.sites), len(self.calls))
        # ERC-4337-style contracts build the callee's argument buffer with an ABI encoder whose SIZE
        # expression is a deep nest of calldata reads; with the v2 node cap (MAX_SIZE=64) it collapses to
        # ('DYN','big') and the whole CALL record loses its payload. Guided passes may use a larger cap:
        # they explore few paths, so the O(size) hashing/traversal cost stays bounded.
        global MAX_SIZE
        _saved_max_size = MAX_SIZE
        if self.expr_max_size: MAX_SIZE = self.expr_max_size
        for g in guides:
            self.guide = g
            self.guide_rd = g.get('returndata')      # per-call return data from the guide oracle
            self._gctx = dict(g); self._gctx['opq'] = dict(OPQ_STANDIN)
            self.steps = 0; self.forks = 0
            self._gcache.clear()
            self.pc_visits.clear(); self.seen_states.clear()
            self._t0 = _time.time()
            if time_budget_each is not None: self.time_budget = time_budget_each
            n0s, n0c = len(self.sites), len(self.calls)
            m = MemState()
            fb, fo = self._split(C(0x40), m)
            mem_write(m, fb, fo, C(0x80))
            work = [(0, [], m, (), {}, None, False, 0, None, 0, ())]
            try:
                while work:
                    st = work.pop()
                    self._exec_path(*st, work)
            except Budget:
                self.guide_truncated += 1
            self.n_guides += 1
            self.guide_gain.append((len(self.sites) - n0s, len(self.calls) - n0c))
        self.guide = None
        MAX_SIZE = _saved_max_size
        self.guided_sites = self.covered_sites - base_cov      # site pcs first reached by a guided pass
        self.guided_calls = self.covered_calls - base_covc
        self.guided_records = (len(self.sites) - base_n[0], len(self.calls) - base_n[1])
        return self

    # ---------------------------------------------------------------- v2.10 free-memory pointer
    @staticmethod
    def _is_fmp(b, o):
        return o == 0x40 and (b is CONC or (b == 0 and not isinstance(b, tuple)))

    @staticmethod
    def _has_dyn(e):
        return any(l.startswith('DYN') for l in leaves(e))

    def _fmp_fresh(self, mem, pc):
        mem.nfmp += 1
        return mk(('OPQ', 'fmp', pc, mem.nfmp))

    def _sha3_tail(self, mem, b, o, reg, sz):
        """keccak over [calldata region of symbolic length L] ++ k words written right after it (sz = L + 32k)"""
        ln = reg[4]
        d = fold('SUB', [sz, ln])
        if not is_c(d) or d[1] % 32 or not 0 < d[1] <= 32 * FMP_SHA3_MAXW: return None
        if b is CONC:
            n = self._geval(ln)
            if n is None: return None
            b2, o2 = CONC, o + n
        else:
            start = C(o) if b == 0 and not isinstance(b, tuple) else lin_add(b, C(o))
            b2, o2 = split_addr(lin_add(start, ln))
            if b2 is None: return None
        words = []
        for j in range(d[1] // 32):
            if (b2, o2 + 32 * j) not in mem.w: return None
            w = mem_read(mem, b2, o2 + 32 * j)
            if w[0] == 'DYN' or self._has_dyn(w): return None
            words.append((w, 0, 32))
        # the region must still be the newest writer of its bytes: no later write may start inside it
        # (a trailing-word write at the region end is the expected one and lies outside the region)
        self.n_sha3_tail += 1
        return mk(('KECB', ((('REGION', 'CD', reg[3], ln), 0, None),) + tuple(words)))

    # ---------------------------------------------------------------- guided addressing
    def _geval(self, e):
        """value of `e` under the current guide, or None (memoized per guide pass)"""
        c = self._gcache.get(e, _MISS)
        if c is not _MISS: return c
        try:
            v = evaluate(e, self._gctx)
        except Unknown:
            v = None
        except Exception:
            v = None
        if len(self._gcache) < 200_000: self._gcache[e] = v
        return v

    def _opq(self, tag, *key):
        """unknown-but-fixed scalar: an opaque symbol under a guide, ('DYN', tag) otherwise.

        `key` identifies the symbol (a pc, or a (call index, word index) for return data). Values bound
        into `self._gctx['opq']` by the return-data oracle are used ONLY to decide memory layout and
        aliasing; the symbol itself is what lands in the record.
        """
        if self.guide is None or not self.opq_scalars: return ('DYN', tag)
        self.n_opq += 1
        return mk(('OPQ', tag, *key))

    def _bind_returndata(self, k, target=None):
        """bind the true size and words of the k-th call's return data (guide oracle), if we have it.

        `rd_strict` (default): bind only when the call TARGET evaluates under the guide and equals the
        target the traced execution called at that index. A guided pass explores paths the real
        transaction never took, so on a divergent path the k-th call is a different call and its
        recorded return data would be actively misleading -- there we fall back to the tag stand-in.
        """
        rd = self.guide_rd[k] if (self.guide_rd is not None and k < len(self.guide_rd)) else None
        if rd is None:
            self.n_rd_missing += 1
            return None
        if target is not None:
            tgt = self._geval(target)
            if tgt is not None and rd['to']:
                if tgt == rd['to']: self.n_rd_aligned += 1
                else:
                    self.n_rd_mismatch += 1
                    if self.rd_strict: return None
            elif self.rd_strict:
                self.n_rd_unverified += 1
                return None
        out = rd['bytes']
        opq = self._gctx['opq']
        changed = opq.get(('OPQ', 'rdsize', k)) != len(out)
        opq[('OPQ', 'rdsize', k)] = len(out)
        for i in range(0, min(len(out), 32 * 512), 32):
            opq[('OPQ', 'retword', k, i // 32)] = int.from_bytes(out[i:i + 32].ljust(32, b'\x00'), 'big')
        if changed: self._gcache.clear()    # a rebound symbol invalidates memoized address values
        self.n_rd_bound += 1
        return rd

    def _split(self, e, mem):
        """address expr -> (base, off) for the memory model.

        Unguided: exactly `split_addr(e)` (byte-identical behaviour).
        Guided: if the address evaluates under the guide, the cell is keyed by its CONCRETE address
        (base CONC) so aliasing matches a real execution, and the symbolic address expression is
        remembered for that address (first writer wins) so CALL word offsets stay symbolic.
        """
        if self.guide is None: return split_addr(e)
        a = self._geval(e)
        if a is None or a > self.max_conc_addr:
            self.n_conc_fail += 1
            return split_addr(e)
        self.n_conc += 1
        prev = mem.sym.get(a)
        if prev is None:
            if len(mem.sym) < 100_000: mem.sym[a] = e
        elif prev is not e and not (is_c(fold('SUB', [e, prev])) and fold('SUB', [e, prev])[1] == 0):
            self.n_alias_assumed += 1      # same concrete address, structurally different expression
        return CONC, a

    def _conc_rel(self, addr, aoff, mem):
        """word offset of concrete `addr` inside a buffer whose symbolic start is `aoff`.

        Returns an int when the symbolic difference folds to a constant (provably layout-independent),
        an expression when it stays symbolic and evaluable per transaction (predict._callargs evaluates
        symbolic rels), or None when the cell has no symbolic address or the difference is dynamic --
        never the guide-specific integer difference, which would bake this guide's layout into the record.
        """
        sa = mem.sym.get(addr)
        if sa is None: return None
        d = fold('SUB', [sa, aoff])
        if is_c(d):
            v = d[1]
            return v if v < (1 << 31) else None
        if any(l.startswith('DYN') or l == 'SLOAD' for l in leaves(d)): return None
        return d

    def _is_return_block(self, pc, limit=40):
        """straight-line block from JUMPDEST pc ending in a JUMP whose target comes from the stack (subroutine return)"""
        prev = None
        for _ in range(limit):
            if pc not in self.ins: return False
            name, val, nxt = self.ins[pc]
            if name == 'JUMP': return prev is not None and not prev.startswith('PUSH')
            if name in ('JUMPI', 'STOP', 'RETURN', 'REVERT', 'INVALID', 'SELFDESTRUCT') or (name == 'JUMPDEST' and prev is not None): return False
            prev = name; pc = nxt
        return False

    @staticmethod
    def _sel_tag(c, tag):
        if tag is None and c[0] == 'OP' and c[1] == 'EQ':
            a, b = c[2], c[3]
            if is_c(b): a, b = b, a
            if is_c(a) and b[0] == 'OP' and b[1] == 'SHR' and b[2] == ('C', 224) and b[3] == ('CD', ('C', 0)):
                return a[1]
        return tag

    def _known(self, e):
        L = leaves(e)
        if any(l.startswith('DYN') or l == 'SLOAD' or l.startswith('REGION') for l in L): return False
        # A condition over an opaque stand-in symbol counts as KNOWN by default, i.e. it is recorded as
        # a path constraint: predict's _cons_ok over-approximates (an unevaluable constraint is skipped,
        # not fatal), so recording costs nothing and the branch still forks both ways.
        return (not self.opq_decide) or not any(l.startswith('OPQ') for l in L)

    def _die(self, tag, pc, reason):
        if self.trace is not None: self.trace[(tag, reason, pc)] += 1
        return None

    # ---- loop handling on a jump edge; returns (loops, widened_state|None) or None to kill
    def _edge(self, edge, stack, mem, loops, work_extra, allow_widen=True):
        if edge[1] in self.retblock: return loops
        ent = loops.get(edge)
        if ent is None:
            loops = dict(loops); loops[edge] = [1, list(stack), dict(mem.w) if self.widen else None]
            loops.pop('_cool', None)          # new edge -> left the region being widened; re-arm
            return loops
        cnt = ent[0]
        if cnt >= WIDENED: return None
        # under a guide the trip count is decided by the concrete calldata, so the unroll bound can be
        # much larger than the unguided max_loop (paths terminate on their own instead of being cut).
        if cnt >= (self.max_loop_guided if self.guide is not None else self.max_loop):
            # a loop whose stack changed only in constants since the previous traversal (a counter
            # and pointers with concrete values, e.g. a word-by-word memory copy of a constant length) keeps unrolling up to
            # CONST_UNROLL traversals; its exit test is concrete, so the path ends by itself
            prev = ent[3] if len(ent) > 3 else None
            if not (CONST_UNROLL and self.guide is None and cnt < CONST_UNROLL and prev is not None and len(prev) == len(stack)
                    and all(a == b or (is_c(a) and is_c(b)) for a, b in zip(prev, stack))):
                return None
            self.n_const_unroll += 1
        loops = dict(loops)
        cool = loops.get('_cool')
        if cool == edge: loops.pop('_cool', None); cool = None
        if cnt == 1 and self.widen and allow_widen and cool is None and (self.guide is None or self.guide_widen):
            w = self._widen(edge, stack, mem, ent[1], ent[2])
            if w is not None:
                wl = {edge: [WIDENED, None, None]}
                work_extra.append((w[0], w[1], wl))
                loops['_cool'] = edge
        loops[edge] = [cnt + 1, None, None, list(stack) if CONST_UNROLL and self.guide is None else None]
        return loops

    def _widen(self, edge, stack, mem, pstack, pmem):
        if pstack is None or len(pstack) != len(stack): return None
        self.idx_counter += 1; idx = mk(('IDX', self.idx_counter))
        changed = 0
        nstack = []
        for a, b in zip(pstack, stack):
            if a == b: nstack.append(b); continue
            g = _generalize(b, a, idx)
            if g is None: nstack.append(('DYN', 'widen'))
            else: nstack.append(g); changed += 1
        nmem = mem.copy()
        # v2.10: a free-memory pointer that does not advance by a constant stride per iteration becomes a
        # fresh base; values at a constant offset from the pointer in BOTH iterations follow it.
        fk = (0, 0x40) if (0, 0x40) in mem.w else ((CONC, 0x40) if (CONC, 0x40) in mem.w else None)
        fsym = None
        if FMP_SYM and fk is not None and fk in pmem and pmem[fk][1] != mem.w[fk][1] \
                and _generalize(mem.w[fk][1], pmem[fk][1], idx) is None:
            pf, cf = pmem[fk][1], mem.w[fk][1]
            fsym = self._fmp_fresh(nmem, edge[1]); self.n_fmp_widen += 1
            def _rel(a, b):
                da = _const_diff(a, pf); db = _const_diff(b, cf)
                if da is None or da != db: return None
                self.n_fmp_widen_rel += 1
                return lin_add(fsym, C(da))
            for i, (a, b) in enumerate(zip(pstack, stack)):
                if nstack[i] == ('DYN', 'widen'):
                    r = _rel(a, b)
                    if r is not None: nstack[i] = r; changed += 1
        for k, (seq, val, nb) in mem.w.items():
            p = pmem.get(k)
            if p is None: continue
            if p[1] == val: continue
            g = _generalize(val, p[1], idx)
            if g is None and fsym is not None:
                g = fsym if k == fk else _rel(p[1], val)
            if g is None: del nmem.w[k]
            else: nmem.w[k] = (seq, g, nb); changed += 1
        nmem.rehash()
        if changed == 0 or self.n_widen >= self.max_widen: return None
        self.n_widen += 1
        return nstack, nmem

    def _wchk(self, work):
        """work W = steps * wk[0] + sum(wk[i] * cw[i]) at every 256th step; stop (truncate) when W > max_work.
        Records are stamped with the number of checks done (index into _chks), so the records of a run capped at K are
        exactly those whose check has W <= K, under any weights."""
        cw = self.cw; wk = self.wk or WK_DEFAULT
        W = self.steps * wk[0] + sum(k * c for k, c in zip(wk[1:], cw[1:]))
        self.w_chk = W; self._chks.append((self.steps,) + tuple(cw[1:]))
        if (self.steps & 0xFFF) == 0:
            self._marks.append((self.steps, _time.process_time(), W, tuple(cw), len(work), len(self.seen_states), len(_intern), _rss_mb()))
        if W > self.max_work: raise Budget()

    def _exec_path(self, pc, stack, mem, cons, loops, tag, called, dd, wb, wsteps, cs, work):
        ins = self.ins; code = self.code
        while True:
            if pc not in ins: return self._die(tag, pc, 'nopc')
            self.steps += 1
            if self.steps > self.max_steps: raise Budget()
            if (self.steps & 255) == 0: self._wchk(work)   # deterministic work cap, no wall-clock budget
            if wb is not None:
                wsteps -= 1
                if wsteps <= 0: return self._die(tag, pc, 'widen-unvalidated/W')
            key = (tag, pc)
            self.pc_visits[key] += 1
            if self.pc_visits[key] > self.max_pc_visits: return self._die(tag, pc, 'pcvisits' if wb is None else 'pcvisits/W')
            name, pushval, nxt = ins[pc]
            base = OPS.get(code[pc], ('INVALID',0,0))
            npop = base[1]
            if len(stack) < npop: return self._die(tag, pc, 'underflow')
            if name.startswith('PUSH'):
                stack.append(C(pushval or 0)); pc = nxt; continue
            if name.startswith('DUP'):
                stack.append(stack[-int(name[3:])]); pc = nxt; continue
            if name.startswith('SWAP'):
                k = int(name[4:]); stack[-1], stack[-1-k] = stack[-1-k], stack[-1]; pc = nxt; continue
            if name == 'JUMPDEST':
                if dd > 0 and self.dedup:
                    dd -= 1
                    sk = (tag, pc, tuple(stack), mem.h, len(mem.w), cons); self.cw[2] += len(stack) + len(cons) + 1
                    if sk in self.seen_states: self.n_dedup += 1; return self._die(tag, pc, 'dedup' if wb is None else 'dedup/W')
                    self.seen_states.add(sk)
                pc = nxt; continue
            if name in ('STOP','RETURN','REVERT','INVALID','SELFDESTRUCT'): return self._die(tag, pc, name if wb is None else name + '/W')
            if name == 'JUMP':
                t = stack.pop()
                if not is_c(t): self.unresolved_jumps += 1; return self._die(tag, pc, 'symjump')
                if t[1] not in self.jumpdests: return self._die(tag, pc, 'badjump')
                if pc in self.indirect_jump:          # subroutine return (or computed jump)
                    if cs and cs[-1] == t[1]: cs = cs[:-1]
                    elif pc in self.masked_call and ('C', nxt) in stack and len(cs) < 64: cs = cs + (nxt,)
                    pc = t[1]; continue
                self.cw[8] += len(stack)
                if ('C', nxt) in stack:               # internal call: return address (pc after JUMP) is on the stack
                    if len(cs) < 64: cs = cs + (nxt,)
                    pc = t[1]; continue
                extra = []
                loops = self._edge((pc, t[1], cs), stack, mem, loops, extra, wb is None)
                if loops is None: return self._die(tag, pc, 'loop' if wb is None else 'loop/W')
                if extra:
                    work.append((t[1], stack, mem, cons, loops, tag, called, dd, wb, wsteps, cs))
                    ws, wm, wl = extra[0]; stack, mem, loops, wb, wsteps = ws, wm, wl, [], self.widen_budget
                pc = t[1]; continue
            if name == 'JUMPI':
                t = stack.pop(); c = stack.pop()
                if is_c(c):
                    if c[1] == 0: pc = nxt; continue
                    if not is_c(t) or t[1] not in self.jumpdests: return self._die(tag, pc, 'badjumpi')
                    extra = []
                    loops = self._edge((pc, t[1], cs), stack, mem, loops, extra, wb is None)
                    if loops is None: return self._die(tag, pc, 'loopi' if wb is None else 'loopi/W')
                    if extra:
                        work.append((t[1], stack, mem, cons, loops, tag, called, dd, wb, wsteps, cs))
                        ws, wm, wl = extra[0]; stack, mem, loops, wb, wsteps = ws, wm, wl, [], self.widen_budget
                    pc = t[1]; continue
                record = self._known(c)
                # the stand-in values are NOT used to decide branches by default: pruning a branch on
                # `callresult == 1` or an assumed return size costs more recall than it saves time
                # (Phase 5 ablation opq_decide=True: -0.48 pp block-level recall at -15% time).
                if self.guide is not None and not idx_ids(c) and (record or self.opq_decide):
                    try:
                        gv = evaluate(c, self._gctx if self.opq_decide else self.guide) != 0
                    except Unknown:
                        gv = None; self.n_guide_unknown += 1
                    if gv is not None:
                        self.n_guided_dec += 1
                        if record: cons = cons + ((c, gv),)
                        else: self.n_cons_opq += 1   # decided by a stand-in value; not recordable
                        if not gv: pc = nxt; continue
                        if not is_c(t) or t[1] not in self.jumpdests: return self._die(tag, pc, 'badjumpi2')
                        extra = []
                        loops = self._edge((pc, t[1], cs), stack, mem, loops, extra, False)
                        if loops is None: return self._die(tag, pc, 'loopi2')
                        tag = self._sel_tag(c, tag)
                        pc = t[1]; continue
                self.forks += 1
                if self.forks > self.max_forks: raise Budget()
                if wb is not None and _is_loop_cond(c):
                    if not record: return self._die(tag, pc, 'widen-dynbound/W')
                    for rec in wb:
                        (self.sites if len(rec) == 4 else self.calls).add(rec)
                    wb = None
                ndd = dd if record else 4
                cons_f = cons + ((c, False),) if record else cons; self.cw[5] += len(stack) + len(cons) + 1
                work.append((nxt, list(stack), mem.copy(), cons_f, loops, tag, called, ndd, None if wb is None else list(wb), wsteps, cs))
                if not is_c(t) or t[1] not in self.jumpdests: return self._die(tag, pc, 'badjumpi2')
                extra = []
                loops = self._edge((pc, t[1], cs), stack, mem, loops, extra, wb is None)
                cons = cons + ((c, True),) if record else cons
                if record: tag = self._sel_tag(c, tag)
                dd = ndd
                if loops is None: return self._die(tag, pc, 'loopi2' if wb is None else 'loopi2/W')
                if extra:
                    work.append((t[1], stack, mem, cons, loops, tag, called, dd, wb, wsteps, cs))
                    ws, wm, wl = extra[0]; stack, mem, loops, wb, wsteps = ws, wm, wl, [], self.widen_budget
                pc = t[1]; continue
            args = [stack.pop() for _ in range(npop)]  # args[0] = top of stack
            # ---- memory
            if name == 'MLOAD':
                b, o = self._split(args[0], mem)
                v = ('DYN','mload-symoff') if b is None else mem_read(mem, b, o)
                if AFFINE_MEM and v is DYN_MEM and b is not None:
                    v2 = _affine_read(mem, b, o)
                    if v2 is not None and v2[0] != 'DYN': v = v2; self.n_affine += 1
                if FMP_SYM and v is DYN_MEM and o == 0x60 and (b is CONC or (b == 0 and not isinstance(b, tuple))) \
                        and not any(bb == b and oo < 0x80 and oo + nb > 0x60 for (bb, oo), (_, _, nb) in mem.w.items()):
                    v = ZERO; self.n_zero_slot += 1          # Solidity zero slot 0x60 (empty `bytes memory`) reads 0
                if FMP_SYM and b is not None and self._is_fmp(b, o) and self._has_dyn(v):
                    v = self._fmp_fresh(mem, pc); mem_write(mem, b, o, v); self.n_fmp_load += 1
                if DBG_MLOAD is not None and v[0] == 'DYN': DBG_MLOAD[(pc, v[1], 'base' if b is None else _dbg_b(b), o)] += 1
                stack.append(v)
            elif name == 'MSTORE':
                b, o = self._split(args[0], mem)
                if b is not None:
                    v = args[1]
                    if FMP_SYM and self._is_fmp(b, o) and self._has_dyn(v):
                        v = self._fmp_fresh(mem, pc); self.n_fmp_store += 1
                    mem_write(mem, b, o, v)
            elif name == 'MSTORE8':
                b, o = self._split(args[0], mem)
                if b is not None: mem_write(mem, b, o, fold('SHL', [C(248), args[1]]), 1)
            elif name == 'CALLDATALOAD':
                stack.append(mk(('CD', args[0])))
            elif name == 'CALLDATACOPY':
                dst, src, sz = args
                b, o = self._split(dst, mem)
                if b is not None:
                    if is_c(sz) and sz[1] <= 4096:
                        n = sz[1]
                        for i in range(0, n, 32):
                            mem_write(mem, b, o + i, mk(('CD', lin_add(src, C(i)))), min(32, n - i))
                    else:
                        mem_region(mem, b, o, 'CD', src, sz)
            elif name == 'CODECOPY':
                dst, src, sz = args
                b, o = self._split(dst, mem)
                if b is not None:
                    if is_c(sz) and is_c(src) and sz[1] <= 4096:
                        n = sz[1]; s0 = src[1]
                        for i in range(0, n, 32):
                            chunk = code[s0+i:s0+i+min(32, n-i)] if s0 + i < len(code) else b''
                            mem_write(mem, b, o + i, C(int.from_bytes(chunk.ljust(min(32, n-i), b'\0'), 'big') << (8 * (32 - min(32, n-i)))), min(32, n - i))
                    else:
                        mem_region(mem, b, o, 'CODE', src, sz)
            elif name in ('EXTCODECOPY','RETURNDATACOPY'):
                dst = args[0] if name == 'RETURNDATACOPY' else args[1]; sz = args[2] if name == 'RETURNDATACOPY' else args[3]
                b, o = self._split(dst, mem)
                if b is not None:
                    rdc = name == 'RETURNDATACOPY' and self.guide is not None
                    n = sz[1] if is_c(sz) else (self._geval(sz) if rdc else None)
                    soff = 0
                    if rdc and n is not None:
                        soff = self._geval(args[1])
                        if soff is None or soff % 32: n = None      # unaligned source: fall back
                    if n is not None and n <= 4096:
                        k = mem.ncall - 1
                        for i in range(0, n, 32):
                            mem_write(mem, b, o + i,
                                      self._opq('retword', k, (soff + i) // 32) if rdc
                                      else self._opq('retword', pc) if self.guide is not None
                                      else ('DYN', name.lower()),
                                      min(32, n - i) if rdc else 32)
                    else: mem_region(mem, b, o, 'RET', args[1], sz)
            elif name == 'MCOPY':
                dst, src, sz = args
                bd, od = self._split(dst, mem); bs, os_ = self._split(src, mem)
                if bd is not None:
                    if is_c(sz) and sz[1] <= 4096 and bs is not None:
                        vals = [mem_read(mem, bs, os_ + i) for i in range(0, sz[1], 32)]
                        for i, v in zip(range(0, sz[1], 32), vals): mem_write(mem, bd, od + i, v, min(32, sz[1] - i))
                    else: mem_region(mem, bd, od, 'MEM', src, sz)
            elif name == 'SHA3':
                off, sz = args
                b, o = self._split(off, mem)
                if is_c(sz) and sz[1] == 0:
                    stack.append(C(int.from_bytes(keccak256(b''),'big')))
                elif b is None or not is_c(sz) or sz[1] > 32 * 16:
                    if b is not None and not is_c(sz):
                        reg = _region_hit(mem, b, o)
                        if reg is not None and reg[1] == o and reg[4] == sz and reg[2] == 'CD':
                            stack.append(mk(('KECB', ((('REGION', 'CD', reg[3], sz), 0, None),)))); pc = nxt; continue
                        if FMP_SHA3 and reg is not None and reg[1] == o and reg[2] == 'CD':
                            k = self._sha3_tail(mem, b, o, reg, sz)
                            if k is not None: stack.append(k); pc = nxt; continue
                    stack.append(self._opq('sha3', pc))
                else:
                    n = sz[1]
                    if n % 32 == 0:
                        words = [mem_read(mem, b, o + i) for i in range(0, n, 32)]
                        if any(w[0] == 'DYN' for w in words): stack.append(self._opq('sha3', pc))
                        else: stack.append(mk(('KEC', tuple(words))))
                    else:
                        segs = compose(mem, b, o, n)
                        stack.append(self._opq('sha3', pc) if segs is None else mk(('KECB', tuple(segs))))
            # ---- storage
            elif name == 'SLOAD':
                key = args[0]
                (self.sites.add((pc, 'SLOAD', key, cons)) if wb is None else wb.append((pc, 'SLOAD', key, cons))); self.covered_sites.add(pc)
                stack.append(mk(('SLOAD', key)))
            elif name == 'SSTORE':
                key, val = args
                (self.sites.add((pc, 'SSTORE', key, cons)) if wb is None else wb.append((pc, 'SSTORE', key, cons))); self.covered_sites.add(pc)
            elif name == 'TLOAD':
                stack.append(self._opq('tload', pc))
            elif name == 'TSTORE':
                pass
            # ---- calls
            elif name in ('CALL','CALLCODE','DELEGATECALL','STATICCALL'):
                if name in ('CALL','CALLCODE'): gas, to, val, aoff, asz, roff, rsz = args
                else: gas, to, aoff, asz, roff, rsz = args; val = C(0)
                argwords = None; argsize = None
                b, o = self._split(aoff, mem)
                if self.arg_debug is not None and (b is None or asz[0] == 'DYN'):
                    self.arg_debug.append((pc, aoff, asz))
                if b is None: self.arg_skip[(pc, 'base')] += 1
                elif asz[0] == 'DYN': self.arg_skip[(pc, 'dyn-size:' + str(asz[1]))] += 1
                elif is_c(asz) and asz[1] > 32 * self.max_arg_words: self.arg_skip[(pc, 'too-big')] += 1
                if b is CONC and asz[0] != 'DYN':
                    # guided concrete addressing: the buffer extent comes from the guide, but every
                    # recorded word offset is a SYMBOLIC difference (or a provable constant), so the
                    # record generalizes to any tx satisfying `cons` rather than to this guide only.
                    nsz = self._geval(asz)
                    if nsz is None or nsz > 32 * self.max_arg_words:
                        self.arg_skip[(pc, 'conc-size-unknown' if nsz is None else 'too-big')] += 1
                    else:
                        hi = o + nsz
                        items = []
                        for (bb, oo), (seq, v, nb) in mem.w.items():
                            if bb is not CONC or oo + nb <= o or oo >= hi: continue
                            rel = self._conc_rel(oo, aoff, mem)
                            if rel is None: self.n_rel_unknown += 1; continue
                            if not isinstance(rel, int): self.n_rel_sym += 1
                            items.append((seq, rel, v, nb))
                        for (bb, oo, kind, src, ln, seq) in mem.regions:
                            if bb is not CONC or oo < o - 32 or oo >= hi: continue
                            rel = self._conc_rel(oo, aoff, mem)
                            if rel is None: self.n_rel_unknown += 1; continue
                            if not isinstance(rel, int): self.n_rel_sym += 1
                            items.append((seq, rel, ('REGION', kind, src, ln), None))
                        items.sort(key=lambda it: it[0])
                        argwords = tuple((rel, v, nb) for _, rel, v, nb in items)
                        argsize = asz
                elif b is not None and asz[0] != 'DYN' and not (is_c(asz) and asz[1] > 32 * self.max_arg_words):
                    hi = o + asz[1] if is_c(asz) else None
                    items = []
                    for (bb, oo), (seq, v, nb) in mem.w.items():
                        if bb == b:
                            if oo + nb <= o or (hi is not None and oo >= hi): continue
                            items.append((seq, oo - o, v, nb))
                        else:
                            rel = _idx_rel(bb, oo, b, o)      # entry written in a widened iteration: offset is linear in IDX
                            if rel is not None: items.append((seq, rel, v, nb))
                    for (bb, oo, kind, src, ln, seq) in mem.regions:
                        if bb == b:
                            if oo < o - 32 or (hi is not None and oo >= hi): continue
                            items.append((seq, oo - o, ('REGION', kind, src, ln), None))
                        else:
                            rel = _idx_rel(bb, oo, b, o)
                            if rel is not None: items.append((seq, rel, ('REGION', kind, src, ln), None))
                    items.sort(key=lambda it: it[0])
                    argwords = tuple((rel, v, nb) for _, rel, v, nb in items)
                    argsize = asz
                (self.calls.add((pc, name, to, argwords, argsize, cons)) if wb is None else wb.append((pc, name, to, argwords, argsize, cons))); self.covered_calls.add(pc)
                k = mem.ncall; mem.ncall = k + 1
                rd = self._bind_returndata(k, to) if self.guide is not None else None
                rb, ro = self._split(roff, mem)
                if rb is not None and is_c(rsz):
                    for i in range(0, min(rsz[1], 4096), 32):
                        mem_write(mem, rb, ro + i,
                                  self._opq('retword', k, i // 32) if self.guide is not None
                                  else ('DYN', 'returndata'))
                called = True
                stack.append(self._opq('callresult', pc))
            elif name in ('CREATE','CREATE2'):
                called = True
                stack.append(self._opq('create', pc))
            elif name == 'RETURNDATASIZE':
                if not called: stack.append(ZERO)
                elif self.guide is None: stack.append(('DYN', 'returndatasize'))
                else: stack.append(self._opq('rdsize', mem.ncall - 1))
            elif name == 'CODESIZE':
                stack.append(C(len(code)))
            elif name in ('BALANCE','EXTCODESIZE','EXTCODEHASH','BLOCKHASH','BLOBHASH'):
                stack.append(self._opq({'balance':'balance','extcodesize':'extcodesize',
                                        'extcodehash':'extcodehash','blockhash':'blockhash',
                                        'blobhash':'blobhash'}[name.lower()], pc))
            elif name in ENV_KNOWN:
                stack.append(('ENV', name))
            elif name in ENV_DYN:
                stack.append(self._opq(name.lower(), pc) if name != 'PC' else C(pc))
            elif name == 'POP' or name.startswith('LOG'):
                pass
            elif name in ARITH:
                stack.append(fold(name, args))
            else:
                for _ in range(base[2]): stack.append(('DYN', name.lower()))
            if len(stack) > 1024: return self._die(tag, pc, 'overflow')
            pc = nxt

    def summary(self):
        return {
            'n_sites_static': len(self.static_sites), 'n_sites_covered': len(self.covered_sites),
            'n_calls_static': len(self.static_calls), 'n_calls_covered': len(self.covered_calls),
            'steps': self.steps, 'forks': self.forks, 'truncated': self.truncated,
            'unresolved_jumps': self.unresolved_jumps, 'n_site_records': len(self.sites),
            'n_widen': self.n_widen, 'n_dedup': self.n_dedup,
            'n_family_sites': sum(1 for s in self.sites if 'IDX' in leaves(s[2])),
            'n_guides': self.n_guides, 'n_guided_dec': self.n_guided_dec,
            'n_conc_addr': self.n_conc, 'n_conc_addr_fail': self.n_conc_fail,
            'n_rel_symbolic': self.n_rel_sym, 'n_rel_unknown': self.n_rel_unknown,
            'n_alias_assumed': self.n_alias_assumed, 'n_opq_symbols': self.n_opq,
            'n_rd_bound': self.n_rd_bound, 'n_rd_missing': self.n_rd_missing,
            'n_rd_aligned': self.n_rd_aligned, 'n_rd_mismatch': self.n_rd_mismatch,
            'n_rd_unverified': self.n_rd_unverified,
            'n_cons_opq_dropped': self.n_cons_opq,
            'n_guide_unknown': self.n_guide_unknown, 'guide_truncated': self.guide_truncated,
            'n_sites_guided_new': len(self.guided_sites), 'n_calls_guided_new': len(self.guided_calls),
            'n_records_guided': getattr(self, 'guided_records', (0, 0)),
            'fmp_v210': (self.n_fmp_store, self.n_fmp_load, self.n_fmp_widen, self.n_fmp_widen_rel, self.n_sha3_tail, self.n_zero_slot),
        }

CMP = {'LT', 'GT', 'SLT', 'SGT'}
def _is_loop_cond(c):
    """comparison (possibly under ISZERO) whose operands contain a loop index"""
    while c[0] == 'OP' and c[1] == 'ISZERO': c = c[2]
    return c[0] == 'OP' and c[1] in CMP and bool(idx_ids(c))

def _generalize(b, a, idx, depth=0):
    """anti-unify iteration values a (earlier) and b (later): b + (b-a)*idx where they differ by constants"""
    if a == b: return b
    if depth > 12: return None
    d = _const_diff(b, a)
    if d is not None:
        # Re-widening the same loop through an alternate back edge must not mint a second index:
        # if the earlier value is already parameterized by an index with this stride, the widening is
        # idempotent and we keep that form (otherwise offsets accumulate one +d*IDX_k per widening,
        # which the concretizer then discards as `family-too-many-ids`).
        if d and a[0] == 'LIN' and any(x[0] == 'IDX' and c == (d & MASK) for c, x in a[2]): return a
        return lin_add(b, lin_scale(idx, d))
    if a[0] != b[0]: return None
    t = b[0]
    if t == 'CD':
        g = _generalize(b[1], a[1], idx, depth+1); return None if g is None else mk(('CD', g))
    if t == 'OP':
        if b[1] != a[1] or len(a) != len(b): return None
        gs = []
        for x, y in zip(b[2:], a[2:]):
            g = _generalize(x, y, idx, depth+1)
            if g is None: return None
            gs.append(g)
        return fold(b[1], gs)
    if t == 'LIN':
        if b[1] != a[1] or len(b[2]) != len(a[2]): return None
        terms = {}
        for (cb, xb), (ca, xa) in zip(b[2], a[2]):
            if cb != ca: return None
            g = _generalize(xb, xa, idx, depth+1)
            if g is None: return None
            terms[g] = terms.get(g, 0) + cb
        return from_lin(b[1], terms)
    if t == 'KEC':
        if len(a[1]) != len(b[1]): return None
        gs = []
        for x, y in zip(b[1], a[1]):
            g = _generalize(x, y, idx, depth+1)
            if g is None: return None
            gs.append(g)
        return mk(('KEC', tuple(gs)))
    if t in ('KECB', 'BYTES'):
        if len(a[1]) != len(b[1]): return None
        gs = []
        for (x, lo, hi), (y, lo2, hi2) in zip(b[1], a[1]):
            if lo != lo2 or hi != hi2: return None
            g = _generalize(x, y, idx, depth+1)
            if g is None: return None
            gs.append((g, lo, hi))
        return mk((t, tuple(gs)))
    if t == 'SLOAD':
        g = _generalize(b[1], a[1], idx, depth+1); return None if g is None else mk(('SLOAD', g))
    if t == 'REGION':
        if a[1] != b[1]: return None
        g1 = _generalize(b[2], a[2], idx, depth+1); g2 = _generalize(b[3], a[3], idx, depth+1)
        return None if g1 is None or g2 is None else ('REGION', b[1], g1, g2)
    return None

def _idx_rel(bb, oo, b, o):
    """if base bb == b + (terms in IDX only), return the relative offset expr (oo - o + idx terms); else None"""
    if bb == 0: return None
    kb, tb = lin(bb); k0, t0 = lin(b) if b != 0 else (0, {})
    diff = dict(tb)
    for x, c in t0.items(): diff[x] = diff.get(x, 0) - c
    diff = {x: c & MASK for x, c in diff.items() if c & MASK}
    if not diff or any(x[0] != 'IDX' for x in diff): return None
    return from_lin(kb - k0 + oo - o, diff)

def _const_diff(b, a):
    """b - a if it is a constant (both linearizable over the same terms), else None"""
    kb, tb = lin(b); ka, ta = lin(a)
    if tb.keys() != ta.keys(): return None
    for k in tb:
        if (tb[k] - ta[k]) & MASK: return None
    d = (kb - ka) & MASK
    if d >= 1 << 255: d -= 1 << 256
    if abs(d) > 1 << 64: return None
    return d

def analyze(code: bytes, **kw):
    return Analyzer(code, **kw).run()

def site_class_table(a: Analyzer):
    order_ = {'A':0,'B':1,'C':2}
    best = {}
    for pc, op, key, cons in a.sites:
        c = classify(key)
        if pc not in best or order_[c] < order_[best[pc][0]]: best[pc] = (c, op)
    return best

if __name__ == '__main__':
    import json
    code = bytes.fromhex(open(sys.argv[1]).read().strip().removeprefix('0x'))
    a = analyze(code, max_steps=3_000_000, max_forks=200_000, max_pc_visits=1000, time_budget=30)
    print(json.dumps(a.summary()))
    print(Counter((op, c) for c, op in site_class_table(a).values()))
