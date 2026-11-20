#!python3
"""Comparisons on one segment between processes run under different conditions (storage tier, memory limit, number
of cores, machine type): ratios with resampled intervals, differences of ratios, device counters, recorded waits.
The commands that produced results/cmp270_{sd,sm,mem,cpu}.txt are the .cmd files next to them (run in results/main)."""
import csv, os, re, sys
import numpy as np

CLASS = os.environ.get('CLASSFILE', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '..', 'measurement', 'block_classes.csv'))
cls = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(CLASS))}
K = int(os.environ['SEG']); MS = int(os.environ.get('SEG0', '26305830')) + 1000 * K + 301; NB = 2000
rng = np.random.default_rng(20261113)
args = sys.argv[1:]
opt = lambda name: [args[i + 1] for i, a in enumerate(args) if a == name and i + 1 < len(args)]   # noqa: E731
procs = {}
for i, a in enumerate(args):
    if '=' in a and (i == 0 or args[i - 1] not in ('--rec',)) and not a.startswith('--') and ':' in a.split('=', 1)[1]:
        n, v = a.split('=', 1); d, lab = v.split(':')[:2]; procs[n] = (d, lab)
RES = float(opt('--res')[0]) if opt('--res') else 0.0
F = ('new_payload_ms', 'exec_ms', 'disk_rd_ios', 'disk_rd_ticks', 'disk_io_ticks')


def load(d, lab, p=0, rows=None, pos2=False):
    out = {}
    for r in csv.DictReader(open(f'{d}/results/blocks_{lab}{p}.csv')):
        if r['role'] != 'measured' or (rows and r['cfg'] not in rows) or (pos2 and int(float(r['pos'])) < 2):
            continue
        out[(int(r['block']), r['cfg'])] = r
    return out


V = {}
for n, (d, lab) in procs.items():
    V[n] = {b: r for (b, _), r in load(d, lab).items()}
blocks = sorted(set.intersection(*[set(v) for v in V.values()]))
A = {(n, f): np.array([float(V[n][b].get(f) or 'nan') for b in blocks]) for n in V for f in F}
reg = np.array([cls.get(b) == 'nomint' for b in blocks]); mnt = ~reg
grp = {}
for i, b in enumerate(blocks):
    grp.setdefault((b - MS) // 10, []).append(i)
gl = list(grp.values())
draws = [np.concatenate([gl[j] for j in rng.integers(0, len(gl), len(gl))]) for _ in range(NB)]
stall = np.zeros(len(blocks), bool)
for n in V:
    stall |= (A[(n, 'new_payload_ms')] - A[(n, 'exec_ms')]) > 250
fr = lambda t: f'{t[0]:.3f} ({t[1]:.3f}-{t[2]:.3f})'   # noqa: E731


def ratio(a, b, f='new_payload_ms', sel=None):
    sel = np.ones(len(blocks), bool) if sel is None else sel
    x, y = A[(a, f)], A[(b, f)]
    pt = x[sel].sum() / y[sel].sum()
    bs = [x[ix][sel[ix]].sum() / y[ix][sel[ix]].sum() for ix in draws if sel[ix].any()]
    return (pt, *np.percentile(bs, [2.5, 97.5]))


def diff(a, b, c, d, sel=None):
    sel = np.ones(len(blocks), bool) if sel is None else sel
    x = lambda ix: (A[(a, 'new_payload_ms')][ix][sel[ix]].sum() / A[(b, 'new_payload_ms')][ix][sel[ix]].sum()   # noqa: E731
                    - A[(c, 'new_payload_ms')][ix][sel[ix]].sum() / A[(d, 'new_payload_ms')][ix][sel[ix]].sum())
    pt = x(np.arange(len(blocks))); bs = [x(ix) for ix in draws]
    return (pt, *np.percentile(bs, [2.5, 97.5]))


print(f'cmp270: segment {K}, {len(blocks)} blocks under all of {list(V)} (regular {reg.sum()}, batch-mint {mnt.sum()}); '
      f'stalled blocks (outside execution > 250 ms in any process) {stall.sum()}')
for n in V:
    o = A[(n, 'new_payload_ms')] - A[(n, 'exec_ms')]
    print(f'  {n}: newPayload {np.nanmean(A[(n, "new_payload_ms")]):.2f} ms, execution {np.nanmean(A[(n, "exec_ms")]):.2f} ms per block; '
          f'its own stalled blocks {(o > 250).sum()}')
sels = [('all', None)] + ([('without stalled', ~stall)] if '--stall' in args else [])
for s in opt('--ratio'):
    a, b = s.split('/')
    for nm, sel in sels:
        base = np.ones(len(blocks), bool) if sel is None else sel
        m2 = (A[(a, 'new_payload_ms')] + A[(b, 'new_payload_ms')]) / 2; top = base & (m2 >= np.percentile(m2[base], 95))
        print(f'[ratio] {a}/{b} ({nm}): newPayload {fr(ratio(a, b, sel=base))}; execution {fr(ratio(a, b, "exec_ms", base))}; '
              f'slowest 5% {fr(ratio(a, b, sel=top))}; regular {fr(ratio(a, b, sel=base & reg))}'
              + (f'; batch-mint {fr(ratio(a, b, sel=base & mnt))}' if (base & mnt).any() else ''))
for s in opt('--diff'):
    l, r = s.split('-'); a, b = l.split('/'); c, d = r.split('/')
    for nm, sel in sels:
        t = diff(a, b, c, d, sel)
        res = abs(t[0]) > RES
        verdict = ('wholly below 0' if t[2] < 0 and res else 'wholly above 0' if t[1] > 0 and res else 'not resolved')
        print(f'[diff] ({a}/{b}) - ({c}/{d}) ({nm}): {t[0]:+.3f} ({t[1]:+.3f} to {t[2]:+.3f})' + (f'; |point| vs resolution {RES:.3f}' if RES else '') + f' -> {verdict}')
for fp in opt('--fio'):
    print(f'[fio] {fp}: ' + ' | '.join(l.strip() for l in open(fp) if re.match(r'\s*(qd1|qd32)', l) or 'latency' in l)[:400])
for n in opt('--dev'):
    rd, rt, N = A[(n, 'disk_rd_ios')], A[(n, 'disk_rd_ticks')], A[(n, 'new_payload_ms')]
    print(f'[dev] {n}: {np.nanmean(rd):.0f} reads per block, {np.nansum(rd) / np.nansum(N) * 1e3:.0f} per s, {np.nansum(rt) / max(np.nansum(rd), 1):.3f} ms per read, '
          f'reads in flight while busy {np.nansum(rt) / max(np.nansum(A[(n, "disk_io_ticks")]), 1):.1f} (approximate)')
for n in opt('--mem'):
    d, lab = procs[n]
    def kvf(p):
        return dict(l.split()[:2] for l in open(p) if len(l.split()) >= 2) if os.path.exists(p) else {}
    b, a = kvf(f'{d}/raw/{lab}0.memcg.before'), kvf(f'{d}/raw/{lab}0.memcg.after')
    print(f'[mem] {n}: page cache before {int(b.get("file", 0)) / 2**30:.2f} GiB, anon {int(b.get("anon", 0)) / 2**30:.2f} GiB; after: max {a.get("max")}, '
          f'oom_kill {a.get("oom_kill")}, file {int(a.get("file", 0)) / 2**30:.2f} GiB; proc read MB per block {np.nanmean([float(V[n][x].get("proc_read_mb") or "nan") for x in blocks]):.2f}, '
          f'major faults per block {np.nanmean([float(V[n][x].get("proc_majflt") or "nan") for x in blocks]):.0f}')
for s in opt('--rec'):
    n, v = s.split('=', 1); d, lab, npass, rows = v.split(':'); rows = rows.split(',')
    x = {}
    for p in range(int(npass)):
        x.update(load(d, lab, p, set(rows), True))
    print(f'[rec] {n}: ms per block slot, account, code waits, execution; storage-wait share; ms per device read (position >= 2)')
    for row in rows:
        v_ = [x[(b, row)] for b in blocks if (b, row) in x]
        if not v_:
            continue
        w = [np.nanmean([float(y.get(c) or 0) for y in v_]) for c in ('slot_miss_ms', 'acct_miss_ms', 'code_miss_ms', 'exec_ms')]
        rd = np.nansum([float(y.get('disk_rd_ios') or 0) for y in v_]); rt = np.nansum([float(y.get('disk_rd_ticks') or 0) for y in v_])
        print(f'  {row:4s}: ' + ' '.join(f'{z:.2f}' for z in w) + f'; share {sum(w[:3]) / w[3]:.3f}; {rt / max(rd, 1):.3f} ms per read ({len(v_)} blocks)')
