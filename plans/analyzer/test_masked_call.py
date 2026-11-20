#!/usr/bin/env python3
"""library calls through a masked function pointer (`PUSH4 ffffffff; PUSH2 f; AND; JUMP`,
solc 0.5/0.6 `using L for T`) are internal calls when SAS_MASKED_CALL=1. The program calls one internal function four
times this way; the function takes a branch on a constant (a counted loop edge, as SafeMath.mul's divisor check in a
Uniswap V2 pair, 0x5b83bdbc, pc 8702) and returns through the stack; after the fourth call it reads slot 9. Without the
switch the four calls share one call stack, the branch counts as one loop iterated four times and the path is cut at
max_loop (3), so slot 9 is never read; with it each call has its own return address on the call stack and slot 9 is
recorded. Both analyzers of the generator chain are checked (evm_static_v2, evm_static_v210), each in a fresh process.
usage: python3 test_masked_call.py   (exit 0: passed)"""
import os, subprocess, sys

H = os.path.dirname(os.path.abspath(__file__))


def program():
    out = bytearray()
    rets = []
    for i in range(4):                       # call site i: PUSH2 ret; PUSH1 5; PUSH4 ffffffff; PUSH2 F; AND; JUMP; ret: JUMPDEST
        st = len(out)
        out += bytes.fromhex('61') + b'\0\0' + bytes.fromhex('6005' '63ffffffff' '61') + b'\0\0' + bytes.fromhex('16' '56' '5b')
        rets.append((st, len(out) - 1))      # (start of the call site, its return JUMPDEST)
    out += bytes.fromhex('6009' '54' '00')   # PUSH1 9; SLOAD; STOP
    F = len(out)                             # F: JUMPDEST; DUP1; PUSH2 L; JUMPI; INVALID
    out += bytes.fromhex('5b' '80' '61') + b'\0\0' + bytes.fromhex('57' 'fe')
    L = len(out)                             # L: JUMPDEST; PUSH2 M; JUMP
    out += bytes.fromhex('5b' '61') + b'\0\0' + bytes.fromhex('56')
    M = len(out)                             # M: JUMPDEST; POP; JUMP   (return to the address below the argument)
    out += bytes.fromhex('5b' '50' '56')
    for st, ret in rets:
        out[st + 1:st + 3] = ret.to_bytes(2, 'big')
        out[st + 11:st + 13] = F.to_bytes(2, 'big')
    out[F + 3:F + 5] = L.to_bytes(2, 'big')
    out[L + 2:L + 4] = M.to_bytes(2, 'big')
    return bytes(out)


CHILD = '''
import sys
sys.path.insert(0, %r)
import importlib
ES = importlib.import_module(sys.argv[1])
a = ES.Analyzer(bytes.fromhex(sys.argv[2]), max_steps=100000, max_forks=1000, max_pc_visits=1000, time_budget=10)
a.run()
print(int(any(op == 'SLOAD' and key == ('C', 9) for pc, op, key, cons in a.sites)))
''' % H


def slot9(mod, on):
    env = dict(os.environ, SAS_MASKED_CALL='1' if on else '0', PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run([sys.executable, '-c', CHILD, mod, program().hex()], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip() == '1'


for mod in ('evm_static_v2', 'evm_static_v210'):
    off, on = slot9(mod, False), slot9(mod, True)
    assert not off, f'{mod}: slot 9 recorded without the switch (the test no longer shows the cut)'
    assert on, f'{mod}: slot 9 not recorded with SAS_MASKED_CALL=1'
    print('ok', mod, 'off', off, 'on', on)
