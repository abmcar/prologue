"""Static (symbolic) extraction of storage-access summaries from EVM bytecode.

Summary = list of sites {pc, op, key: Expr, constraints: [(Expr, bool)], sel}
where Expr is a hashable nested tuple:
  ('C', int)                      constant
  ('CD', off_expr)                CALLDATALOAD(off)
  ('ENV', name)                   CALLER/ORIGIN/ADDRESS/CALLVALUE/CALLDATASIZE/NUMBER/TIMESTAMP/...
  ('OP', name, a, b, ...)         arithmetic / logic
  ('KEC', (w0, w1, ...))          keccak256 of concatenated 32-byte words
  ('SLOAD', key_expr)             value read from storage (state-dependent, "one hop")
  ('DYN', reason)                 not statically derivable (ext call result, dynamic memory, ...)
"""
from __future__ import annotations
import sys, time as _time
from collections import Counter, defaultdict
from Crypto.Hash import keccak

MASK = (1 << 256) - 1
SIGN = 1 << 255

def keccak256(b: bytes) -> bytes:
    h = keccak.new(digest_bits=256); h.update(b); return h.digest()

# ---------------------------------------------------------------- opcode table
# name -> (pops, pushes)
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
             'CHAINID','GASLIMIT','BASEFEE','PREVRANDAO','BLOBBASEFEE','CODESIZE'}
ENV_DYN = {'GASPRICE','GAS','MSIZE','PC','SELFBALANCE','RETURNDATASIZE'}

def disassemble(code: bytes):
    """-> dict pc -> (opname, pushvalue|None, next_pc)"""
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


def mset(mem, k, v):
    """write memory word k so that the dict's order is the order of the last writes (a rewritten word moves to
    the end); call records read the words in this order"""
    mem.pop(k, None); mem[k] = v

def is_c(e): return e[0] == 'C'
DYN_MEM = ('DYN','mem')

def leaves(e, acc=None):
    acc = set() if acc is None else acc
    t = e[0]
    if t == 'C': pass
    elif t == 'CD': acc.add('CD'); leaves(e[1], acc)
    elif t == 'ENV': acc.add(e[1])
    elif t == 'OP':
        for a in e[2:]: leaves(a, acc)
    elif t == 'KEC':
        for a in e[1]: leaves(a, acc)
    elif t == 'SLOAD': acc.add('SLOAD'); leaves(e[1], acc)
    elif t == 'DYN': acc.add('DYN:'+e[1])
    return acc

def classify(e):
    """A: fully known pre-execution from tx + block env; B: needs storage reads (k-hop); C: dynamic."""
    L = leaves(e)
    if any(l.startswith('DYN') for l in L): return 'C'
    if 'SLOAD' in L: return 'B'
    return 'A'

def to_signed(v): return v - (1<<256) if v & SIGN else v

MAX_SIZE = 48
_intern = {}
_size = {}
def intern(e):
    """canonicalize expression; cache node count by identity of the canonical object"""
    c = _intern.get(e)
    if c is not None: return c
    if len(_intern) > 500_000: _intern.clear(); _size.clear()
    _intern[e] = e
    t = e[0]
    if t in ('C','ENV','DYN'): n = 1
    elif t == 'CD': n = 1 + size(e[1])
    elif t == 'OP': n = 1 + sum(size(a) for a in e[2:])
    elif t == 'KEC': n = 1 + sum(size(a) for a in e[1])
    elif t == 'SLOAD': n = 1 + size(e[1])
    else: n = 1
    _size[id(e)] = n
    return e
def size(e):
    n = _size.get(id(e))
    if n is None:
        intern(e); n = _size.get(id(e), 1)
    return n

def fold(name, args):
    if all(is_c(a) for a in args):
        v = [a[1] for a in args]
        try:
            r = ARITH[name](*v)
            return C(r)
        except Exception:
            pass
    if sum(size(a) for a in args) >= MAX_SIZE: return ('DYN', 'big')
    return intern(('OP', name, *args))

def mk(e):
    e = intern(e)
    return ('DYN','big') if size(e) > MAX_SIZE else e

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

class Unknown(Exception): pass

def evaluate(e, ctx, depth=0):
    """Concretize expression. ctx: dict with calldata(bytes), env(dict name->int), sload(fn key->int)|None."""
    if depth > 200: raise Unknown('depth')
    t = e[0]
    if t == 'C': return e[1]
    if t == 'CD':
        off = evaluate(e[1], ctx, depth+1)
        if off > 1<<32: return 0
        d = ctx['calldata']; return int.from_bytes(d[off:off+32].ljust(32, b'\0'), 'big')
    if t == 'ENV':
        if e[1] in ctx['env']: return ctx['env'][e[1]]
        raise Unknown('env:'+e[1])
    if t == 'OP':
        return ARITH[e[1]](*[evaluate(a, ctx, depth+1) for a in e[2:]])
    if t == 'KEC':
        return int.from_bytes(keccak256(b''.join(evaluate(w, ctx, depth+1).to_bytes(32,'big') for w in e[1])), 'big')
    if t == 'SLOAD':
        f = ctx.get('sload')
        if f is None: raise Unknown('sload')
        k = evaluate(e[1], ctx, depth+1); return f(k)
    raise Unknown('dyn:'+e[1])

# ---------------------------------------------------------------- symbolic executor
class Budget(Exception): pass

class Analyzer:
    def __init__(self, code: bytes, max_steps=400_000, max_pc_visits=40, max_forks=20_000, max_stack=1024, time_budget=60.0):
        self.code = code; self.ins = disassemble(code)
        self.jumpdests = {pc for pc,(n,_,_) in self.ins.items() if n == 'JUMPDEST'}
        self.max_steps = max_steps; self.max_pc_visits = max_pc_visits; self.max_forks = max_forks
        self.sites = set()          # (pc, op, key_expr, constraints)
        self.calls = set()          # (pc, kind, target_expr, args_tuple|None, constraints)
        self.pc_visits = Counter(); self.steps = 0; self.forks = 0
        self._marks = []   # sas_det
        self.static_sites = {pc for pc,(n,_,_) in self.ins.items() if n in ('SLOAD','SSTORE')}
        self.static_calls = {pc for pc,(n,_,_) in self.ins.items() if n in ('CALL','STATICCALL','DELEGATECALL','CALLCODE')}
        self.covered_sites = set(); self.covered_calls = set(); self.truncated = False
        self.unresolved_jumps = 0
        import time as _t; self._t0 = _t.time(); self._time = _t.time; self.time_budget = time_budget

    def run(self):
        # state: (pc, stack(list), mem(dict), constraints(tuple), pathcount(Counter of pc))
        work = [(0, [], {0x40: C(0x80)}, (), Counter())]
        try:
            while work:
                pc, stack, mem, cons, loops = work.pop()
                self._exec_path(pc, stack, mem, cons, loops, work)
        except Budget:
            self.truncated = True
        return self

    def _known(self, e):
        L = leaves(e)
        return not any(l.startswith('DYN') or l == 'SLOAD' for l in L)

    def _exec_path(self, pc, stack, mem, cons, loops, work):
        ins = self.ins
        while True:
            if pc not in ins: return
            self.steps += 1
            if (self.steps & 0x3FFF) == 0: self._marks.append((self.steps, _time.process_time()))   # sas_det: CPU time at step milestones
            if self.steps > self.max_steps: raise Budget()
            if (self.steps & 1023) == 0 and self._time() - self._t0 > self.time_budget: raise Budget()
            self.pc_visits[pc] += 1
            if self.pc_visits[pc] > self.max_pc_visits: return
            name, pushval, nxt = ins[pc]
            base = OPS.get(self.code[pc], ('INVALID',0,0))
            npop = base[1]
            if len(stack) < npop: return  # stack underflow -> dead path
            if name.startswith('PUSH'):
                stack.append(C(pushval or 0)); pc = nxt; continue
            if name.startswith('DUP'):
                stack.append(stack[-int(name[3:])]); pc = nxt; continue
            if name.startswith('SWAP'):
                k = int(name[4:]); stack[-1], stack[-1-k] = stack[-1-k], stack[-1]; pc = nxt; continue
            if name == 'JUMPDEST' or name == 'PC' and False:
                pc = nxt; continue
            if name in ('STOP','RETURN','REVERT','INVALID','SELFDESTRUCT'): return
            if name == 'JUMP':
                t = stack.pop()
                if not is_c(t): self.unresolved_jumps += 1; return
                if t[1] not in self.jumpdests: return
                pc = t[1]
                if loops[pc] > 2: return
                loops = loops.copy(); loops[pc] += 1
                continue
            if name == 'JUMPI':
                t = stack.pop(); c = stack.pop()
                if is_c(c):
                    if c[1] == 0: pc = nxt; continue
                    if not is_c(t) or t[1] not in self.jumpdests: return
                    pc = t[1]
                    if loops[pc] > 2: return
                    loops = loops.copy(); loops[pc] += 1
                    continue
                self.forks += 1
                if self.forks > self.max_forks: raise Budget()
                record = self._known(c)
                # fall-through branch (condition false)
                cons_f = cons + ((c, False),) if record else cons
                work.append((nxt, list(stack), dict(mem), cons_f, loops))
                # taken branch
                if not is_c(t) or t[1] not in self.jumpdests: return
                if loops[t[1]] > 2: return
                loops = loops.copy(); loops[t[1]] += 1
                cons = cons + ((c, True),) if record else cons
                pc = t[1]; continue
            args = [stack.pop() for _ in range(npop)]  # args[0] = top of stack
            # ---- memory / storage / calls
            if name == 'MLOAD':
                off = args[0]
                stack.append(mem.get(off[1], DYN_MEM) if is_c(off) else ('DYN','mload-symoff'))
            elif name == 'MSTORE':
                off, val = args
                if is_c(off): mset(mem, off[1], val)
                else: mem = {k:v for k,v in mem.items() if k == 0x40 or k == 'cdcopy'}  # unknown write: forget scratch (keep free ptr guess)
            elif name == 'MSTORE8':
                off, val = args
                if is_c(off):
                    a = off[1] & ~31; mset(mem, a, ('DYN','mstore8'))
            elif name == 'CALLDATALOAD':
                stack.append(mk(('CD', args[0])))
            elif name == 'CALLDATACOPY':
                dst, src, size = args
                if is_c(dst) and is_c(src) and is_c(size) and size[1] <= 4096 and dst[1] % 32 == 0:
                    for i in range(0, size[1], 32):
                        mset(mem, dst[1]+i, ('CD', C(src[1]+i)))  # approximate tail word
                elif is_c(dst) and is_c(size) and size[1] <= 4096:
                    for i in range(0, size[1], 32): mset(mem, (dst[1]+i)&~31, ('CD', fold('ADD',[src, C(i)])))
                elif is_c(dst):
                    mset(mem, dst[1], ('DYN','calldatacopy'))
                    mem['cdcopy'] = (dst[1], src, size)   # symbolic-size copy region (proxy forwarding pattern)
            elif name in ('CODECOPY','EXTCODECOPY','RETURNDATACOPY','MCOPY'):
                dst = args[0] if name != 'EXTCODECOPY' else args[1]
                if name == 'MCOPY' and is_c(args[0]) and is_c(args[1]) and is_c(args[2]) and args[2][1] <= 4096:
                    for i in range(0, args[2][1], 32): mset(mem, args[0][1]+i, mem.get(args[1][1]+i, DYN_MEM))
                elif is_c(dst): mset(mem, dst[1], ('DYN', name.lower()))
            elif name == 'SHA3':
                off, size = args
                if is_c(off) and is_c(size) and size[1] % 32 == 0 and 0 < size[1] <= 32*8:
                    words = [mem.get(off[1]+i, DYN_MEM) for i in range(0, size[1], 32)]
                    stack.append(mk(('KEC', tuple(words))))
                elif is_c(size) and size[1] == 0:
                    stack.append(C(int.from_bytes(keccak256(b''),'big')))
                else:
                    stack.append(('DYN','sha3-dynamic'))
            elif name == 'SLOAD':
                key = args[0]
                self.sites.add((pc, 'SLOAD', key, cons)); self.covered_sites.add(pc)
                stack.append(mk(('SLOAD', key)))
            elif name == 'SSTORE':
                key, val = args
                self.sites.add((pc, 'SSTORE', key, cons)); self.covered_sites.add(pc)
            elif name in ('TLOAD',):
                stack.append(('DYN','tload'))
            elif name == 'TSTORE':
                pass
            elif name in ('CALL','CALLCODE','DELEGATECALL','STATICCALL'):
                if name in ('CALL','CALLCODE'):
                    gas, to, val, aoff, asz, roff, rsz = args
                else:
                    gas, to, aoff, asz, roff, rsz = args; val = C(0)
                argwords = None
                if is_c(aoff) and is_c(asz) and asz[1] <= 32*64:
                    a0, n = aoff[1], asz[1]
                    # every memory word overlapping [a0, a0+n) in write order (the dict's order: `mset` moves a rewritten
                    # word to the end), so that a later write wins on overlap. this was
                    # ascending offset, which let an earlier word win over a later overlapping one (a1513fb2: the free
                    # memory pointer word at 0x40, written first, cleared the last 4 bytes of the recipient at 0x24)
                    argwords = tuple((off - a0, mem[off]) for off in mem if isinstance(off, int) and a0 - 32 < off < a0 + n)
                    argsize = n
                elif is_c(aoff) and 'cdcopy' in mem and mem['cdcopy'][0] == aoff[1] and mem['cdcopy'][2] == asz:
                    argwords = ('FWD', mem['cdcopy'][1], asz); argsize = -1
                else:
                    argsize = None
                self.calls.add((pc, name, to, argwords, argsize, cons)); self.covered_calls.add(pc)
                if is_c(roff) and is_c(rsz):
                    for i in range(0, min(rsz[1], 4096), 32): mset(mem, roff[1]+i, ('DYN','returndata'))
                stack.append(('DYN','callresult'))
            elif name in ('CREATE','CREATE2'):
                stack.append(('DYN','create'))
            elif name in ('BALANCE','EXTCODESIZE','EXTCODEHASH','BLOCKHASH','BLOBHASH'):
                stack.append(('DYN', name.lower()))
            elif name in ENV_KNOWN:
                stack.append(('ENV', name))
            elif name in ENV_DYN:
                stack.append(('DYN', name.lower()))
            elif name == 'POP' or name.startswith('LOG'):
                pass
            elif name in ARITH:
                stack.append(fold(name, args))
            else:
                # unknown effect: push DYN for pushes
                for _ in range(base[2]): stack.append(('DYN', name.lower()))
            if len(stack) > 1024: return
            pc = nxt

    def summary(self):
        return {
            'n_sites_static': len(self.static_sites), 'n_sites_covered': len(self.covered_sites),
            'n_calls_static': len(self.static_calls), 'n_calls_covered': len(self.covered_calls),
            'steps': self.steps, 'forks': self.forks, 'truncated': self.truncated,
            'unresolved_jumps': self.unresolved_jumps, 'n_site_records': len(self.sites),
        }

def strip_metadata(code: bytes) -> bytes:
    """Solidity appends CBOR metadata; last 2 bytes are its length. Keep code as-is (disassembly tolerates it)."""
    return code

def analyze(code: bytes, **kw):
    a = Analyzer(code, **kw).run()
    return a

def site_class_table(a: Analyzer):
    """per static site pc -> best class (A<B<C) across recorded key exprs."""
    order = {'A':0,'B':1,'C':2}
    best = {}
    for pc, op, key, cons in a.sites:
        c = classify(key)
        if pc not in best or order[c] < order[best[pc][0]]: best[pc] = (c, op)
    return best

if __name__ == '__main__':
    import json
    code = bytes.fromhex(open(sys.argv[1]).read().strip().removeprefix('0x'))
    a = analyze(code)
    print(json.dumps(a.summary()))
    tab = site_class_table(a)
    print(Counter((op, c) for c, op in tab.values()))
