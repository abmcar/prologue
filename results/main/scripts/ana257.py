#!python3
"""Analysis of the main comparison, the ablation and the recording processes: ratios of sums of block validation time
with intervals from 2,000 resamples of 10-block groups, the slowest 5% (chosen by the mean of the two rows compared),
per-segment ratios, processor time, the ablation steps and the recorded waits.
The command that produced results/ana270.txt is results/ana270.cmd (run in results/main)."""
import csv, json, os, re, sys
from collections import Counter
import numpy as np

CLASS = os.environ.get('CLASSFILE', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '..', 'measurement', 'block_classes.csv'))
cls = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(CLASS))}
RUP, RPN = os.environ.get('ROW_UP', 'U7'), os.environ.get('ROW_PN', 'F7')
ROWS_ABL = os.environ.get('ROWS_ABL', 'G0,G1,G2,G3,G4,G5,GX,GC,GXC').split(',')
ROWS_REC = os.environ.get('ROWS_REC', 'G0n,G0,G3,G4,G5').split(',')
NPA = int(os.environ.get('NPASS_ABL', '9')); NPR = int(os.environ.get('NPASS_REC', '5')); NPM = int(os.environ.get('NPASS_MAIN', '1')); NB = 2000; SHARE = 0.100
OLDDEV = {int(x) for x in os.environ.get('OLDDEV', '2,3').split(',') if x}   # (OLDDEV= for the lowest-two rule)
args = sys.argv[1:]
MAIN = [a.split(':') for i, a in enumerate(args) if i > 0 and args[i - 1] == '--main']
ABL = [a.split(':') for i, a in enumerate(args) if i > 0 and args[i - 1] == '--abl']
REC = [a.split(':') for i, a in enumerate(args) if i > 0 and args[i - 1] == '--rec']


def load(d, lab, npass, rows, pos2):
    out = {}
    for p in range(npass):
        for r in csv.DictReader(open(f'{d}/results/blocks_{lab}{p}.csv')):
            if r['role'] == 'measured' and r['cfg'] in rows and (not pos2 or int(float(r['pos'])) >= 2):
                out[(int(r['block']), r['cfg'])] = (float(r['new_payload_ms']), float(r['exec_ms']), float(r['gas_used']), float(r.get('proc_cpu_ms') or 'nan'),
                                                    float(r.get('state_root_ms') or 'nan'), np.nan_to_num(float(r.get('eap_join_us') or 0)) / 1e3)   # no readers: join 0
    return out


FB = re.compile(r' eap reusefb block=(\d+) reused=\d+ outcome=\w+ exec_us=\d+ root_us=\d+ at=(\w+)')


def fallbacks(d, lab, npass):
    """measured blocks with a whole-block fallback: {block: [(row, at), ...]}"""
    out = {}
    for p in range(npass):
        cfg = {int(r['block']): r['cfg'] for r in csv.DictReader(open(f'{d}/results/blocks_{lab}{p}.csv')) if r['role'] == 'measured'}
        for line in open(f'{d}/raw/{lab}{p}.node.log', errors='replace'):
            m = FB.search(line)
            if m and int(m.group(1)) in cfg:
                out.setdefault(int(m.group(1)), []).append((cfg[int(m.group(1))], m.group(2)))
    return out


def fbline(fb, S, a, b, sel_of):
    n = Counter(x for v in fb.values() for x in v)
    if not fb:
        return 'fallback (printed only): 0 measured blocks; nothing to leave out'
    keep = ~sel_of(set(fb))
    return (f'fallback (printed only): {len(fb)} measured blocks ({", ".join(f"{r} at={at} {c}" for (r, at), c in sorted(n.items()))}); '
            f'without them {a}/{b} newPayload {fr(S.ratio(a, b, 0, keep))}, execution {fr(S.ratio(a, b, 1, keep))}')


def ms_of(k):
    return int(os.environ.get("SEG0", "26305830")) + 1000 * k + 301   # SEG0: route C


rng = np.random.default_rng(20261106)


class Set:
    """blocks (k, block) with per-row arrays; resampling of 10-block groups within each segment"""
    def __init__(self, keys, vals, rows):
        self.keys = keys; self.rows = rows
        self.V = {r: np.array([vals[(k, b, r)] for k, b in keys]) for r in rows}   # columns N, E, G, C, root wait, join
        g = {}
        for i, (k, b) in enumerate(keys):
            g.setdefault((k, (b - ms_of(k)) // 10), []).append(i)
        byk = {}
        for s in g:
            byk.setdefault(s[0], []).append(s)
        self.draws = []
        for _ in range(NB):
            pick = []
            for k, ss in sorted(byk.items()):
                for j in rng.integers(0, len(ss), len(ss)):
                    pick.extend(g[ss[j]])
            self.draws.append(np.array(pick))
        self.reg = np.array([cls.get(b) == 'nomint' for _, b in keys]); self.mnt = ~self.reg

    def ratio(self, a, b, col, sel=None, f=None):
        sel = np.ones(len(self.keys), bool) if sel is None else sel
        f = f or (lambda x, y: x.sum() / y.sum())
        A, B = self.V[a][:, col], self.V[b][:, col]
        pt = f(A[sel], B[sel])
        bs = [f(A[ix][sel[ix]], B[ix][sel[ix]]) for ix in self.draws if sel[ix].any()]
        lo, hi = np.nanpercentile(bs, [2.5, 97.5])
        return pt, lo, hi

    def diff(self, a, b, col, sel):
        d = self.V[a][:, col] - self.V[b][:, col]
        bs = [d[ix][sel[ix]].mean() for ix in self.draws if sel[ix].any()]
        lo, hi = np.nanpercentile(bs, [2.5, 97.5])
        return d[sel].mean(), lo, hi


fr = lambda t: f'{t[0]:.3f} ({t[1]:.3f}-{t[2]:.3f})'   # noqa: E731
fd = lambda t: f'{t[0]:+.2f} ({t[1]:+.2f} to {t[2]:+.2f})'   # noqa: E731
vals = {}; keys = []; fbm = {}; order = {}
for spec in MAIN:
    k, du, lu, dr, lr, dn, ln, dp, lp = spec
    k = int(k)
    u, r, n_ = load(du, lu, NPM, {RUP}, False), load(dr, lr, NPM, {RUP}, False), load(dn, ln, NPM, {RUP}, False)
    p = load(dp, lp, NPM, {RPN}, False)
    fbm.update({(k, b): v for b, v in fallbacks(dp, lp, NPM).items()})
    bs = sorted({b for b, _ in u} & {b for b, _ in r} & {b for b, _ in n_} & {b for b, _ in p})
    for b in bs:
        vals[(k, b, 'UP')] = u[(b, RUP)]; vals[(k, b, 'UR')] = r[(b, RUP)]; vals[(k, b, 'UN')] = n_[(b, RUP)]; vals[(k, b, 'PN')] = p[(b, RPN)]
        keys.append((k, b))
    # each process's start (meta t_start) gives the order on its machine
    st = {c: json.load(open(f'{d}/raw/{l}0.meta.json')).get('t_start', 0) for c, d, l in (('UP', du, lu), ('UR', dr, lr), ('UN', dn, ln), ('PN', dp, lp))}
    order[k] = ' '.join(sorted(st, key=st.get))
M = Set(keys, vals, ['UP', 'UR', 'UN', 'PN'])
print(f'ana257: {len(MAIN)} segments, {len(keys)} blocks under all four processes (regular {M.reg.sum()}, batch-mint {M.mnt.sum()})')
pct = lambda q: (lambda x, y: np.percentile(x, q) / np.percentile(y, q))   # noqa: E731
segs = sorted({k for k, _ in keys})
segsel = {k: np.array([kk == k for kk, _ in keys]) for k in segs}
SD = {}


def pair(a, b, title, judged=True):
    print(f'\n######## {title}: {a} against {b}')
    aN, aE, aC = M.ratio(a, b, 0), M.ratio(a, b, 1), M.ratio(a, b, 3)
    sr = np.array([M.ratio(a, b, 0, segsel[k])[0] for k in segs]); sd = float(np.std(sr, ddof=1)) if len(sr) > 1 else float('nan')
    SD[(a, b)] = sd
    print(f'[1] all blocks: newPayload {fr(aN)}; execution {fr(aE)}')
    print('    per segment newPayload: ' + ', '.join(f'k{k} {v:.3f}' for k, v in zip(segs, sr)) + f'; sd {sd:.4f}; below 1: {int((sr < 1).sum())} of {len(sr)}')
    def keep8(seg_ratio):
        """ the blocks of the segments left after dropping the two with the lowest ratio
        (OLDDEV set: the segments not in OLDDEV)"""
        if OLDDEV:
            drop = OLDDEV
        else:
            drop = {k for _, k in sorted((v, k) for k, v in seg_ratio.items())[:2]}
        return np.array([k not in drop for k, _ in keys]), sorted(drop)
    uNsel, dN = keep8(dict(zip(segs, sr)))
    uEsel, dE = keep8({k: M.ratio(a, b, 1, segsel[k])[0] for k in segs})
    uN = M.ratio(a, b, 0, uNsel) if uNsel.any() else (np.nan,) * 3
    uE = M.ratio(a, b, 1, uEsel) if uEsel.any() else (np.nan,) * 3
    print(f'    without segments {dN} (newPayload) / {dE} (execution): newPayload {fr(uN)}; execution {fr(uE)}')
    if a == 'PN':
        print('    ' + fbline(fbm, M, a, b, lambda ks: np.array([kb in ks for kb in keys])))
    mean2 = (M.V[a][:, 0] + M.V[b][:, 0]) / 2; top = mean2 >= np.percentile(mean2, 95)
    tN = M.ratio(a, b, 0, top)
    print(f'[2] slowest 5% by the mean of both ({top.sum()} blocks): newPayload {fr(tN)}; p95 {fr(M.ratio(a, b, 0, f=pct(95)))}; p99 {fr(M.ratio(a, b, 0, f=pct(99)))}')
    rd = M.diff(a, b, 0, M.reg)
    w = lambda r: (1 - SHARE) * M.V[r][M.reg, 0].mean() + SHARE * M.V[r][M.mnt, 0].mean() if M.mnt.any() else M.V[r][M.reg, 0].mean()   # noqa: E731
    print(f'[3] regular blocks: newPayload {np.mean(M.V[b][M.reg, 0]):.2f} -> {np.mean(M.V[a][M.reg, 0]):.2f} ms, difference {fd(rd)}, ratio {fr(M.ratio(a, b, 0, M.reg))}')
    oa, ob = M.V[a][M.reg, 0] - M.V[a][M.reg, 1], M.V[b][M.reg, 0] - M.V[b][M.reg, 1]
    print(f'[3b] regular blocks, outside execution {ob.mean():.2f} -> {oa.mean():.2f} ms; state-root wait {np.nanmean(M.V[b][M.reg, 4]):.2f} -> {np.nanmean(M.V[a][M.reg, 4]):.2f} ms (printed only)')
    if M.mnt.any():
        print(f'    batch-mint blocks (a note): newPayload ratio {fr(M.ratio(a, b, 0, M.mnt))}; reweighted to a batch-mint share of {SHARE:.1%}: {w(a) / w(b):.3f}')
    print(f'[4] process cpu: {fr(aC)}')
    if not judged:
        print('[5] reported only, no conclusion')
        return
    print(f'[5] the three conditions for "{a} shortens against {b}"')
    for lab, t, ut in (('newPayload', aN, uN), ('execution', aE, uE), ('slowest 5%', tN, None)):
        if lab == 'newPayload':
            segok = int((sr < 1).sum())
        elif lab == 'execution':
            segok = sum(M.ratio(a, b, 1, segsel[k])[0] < 1 for k in segs)
        else:
            segok = sum(M.ratio(a, b, 0, top & segsel[k])[0] < 1 for k in segs if (top & segsel[k]).any())
            ts_, dT = keep8({k: M.ratio(a, b, 0, top & segsel[k])[0] for k in segs if (top & segsel[k]).any()})
            ut = M.ratio(a, b, 0, top & ts_) if (top & ts_).any() else (np.nan,) * 3
        c1, c2, c3 = t[2] < 1, segok >= 8, ut[2] < 1
        print(f'  {lab}: interval below 1 {c1} ({fr(t)}); segments below 1: {segok} (>= 8: {c2}); eight segments of condition 3 below 1 {c3} ({fr(ut)})'
              f' -> {"shortens" if c1 and c2 and c3 else "not established on these blocks"}')


pair('PN', 'UP', 'main result')
pair('PN', 'UR', 'Prologue against stock with reth\'s reuse')
pair('PN', 'UN', 'Prologue against stock without prewarming (reported)', judged=False)
pair('UR', 'UP', "reth's reuse alone (reported)", judged=False)
pair('UP', 'UN', "reth's prewarming alone (reported)", judged=False)
print('\n[1b] (printed only) each segment: the processes in the order they ran, newPayload PN/UP, PN/UR, PN/UN, UR/UP, UP/UN')
for k in segs:
    print(f'    k{k}: {order[k]}; ' + ' '.join(f'{M.ratio(a, b, 0, segsel[k])[0]:.3f}' for a, b in (('PN', 'UP'), ('PN', 'UR'), ('PN', 'UN'), ('UR', 'UP'), ('UP', 'UN'))))
sd = SD[('PN', 'UP')]
if ABL:
    av = {}; ak = []; fba = {}
    for k, d, lab in ABL:
        k = int(k); x = load(d, lab, NPA, set(ROWS_ABL), True)
        fba.update({(k, b): v for b, v in fallbacks(d, lab, NPA).items()})
        bs = sorted({b for b, r in x if all((b, rr) in x for rr in ROWS_ABL)})
        for b in bs:
            ak.append((k, b))
            for i, rr in enumerate(ROWS_ABL):
                av[(k, b, f'P{i}')] = x[(b, rr)]
    A = Set(ak, av, [f'P{i}' for i in range(len(ROWS_ABL))])
    print(f'\n[6] ablation: {len(ABL)} segments, {len(ak)} blocks under all {len(ROWS_ABL)} rows (position >= 2; regular {A.reg.sum()}, batch-mint {A.mnt.sum()})')
    print('    "on against off" (features: "off against full"); newPayload all | regular | batch-mint ; execution all | regular | batch-mint')
    allsel = np.ones(len(ak), bool)
    for a, b, lab in (('P1', 'P0', 'own pre-execution and reuse (G1/G0)'), ('P2', 'P1', 'scheduling (G2/G1)'), ('P3', 'P2', 'reading path (G3/G2)'),
                      ('P4', 'P3', 'plans and readers, on the rest (G4/G3)'), ('P5', 'P0', 'plans and readers, on stock (G5/G0)'),
                      ('P2', 'P0', 'pre-execution with scheduling (G2/G0)'), ('P3', 'P0', 'without plans (G3/G0)'), ('P4', 'P0', 'the whole (G4/G0)'),
                      ('P6', 'P4', 'extrapolation off (GX/G4)'), ('P7', 'P4', 'path conditions off (GC/G4)'), ('P8', 'P4', 'both off (GXC/G4)')):
        if a in A.V and b in A.V:
            t = A.ratio(a, b, 0)
            cells = [fr(A.ratio(a, b, c, s_)) for c in (0, 1) for s_ in (allsel, A.reg, A.mnt) if s_.any()]
            print(f'    {lab:42s} {" | ".join(cells[:3])} ; {" | ".join(cells[3:])}' + ('  (no significant difference, all blocks)' if t[1] <= 1 <= t[2] else ''))
    print('    ' + fbline({kb: v for kb, v in fba.items() if kb in set(ak)}, A, 'P4', 'P0', lambda ks: np.array([kb in ks for kb in ak])))
    P = A.V
    def inter_f(ix):
        s = lambda r: P[r][ix, 0].sum()   # noqa: E731
        return (s('P4') / s('P3')) / (s('P5') / s('P0'))
    if all(r in P for r in ('P0', 'P3', 'P4', 'P5')):
        pt = inter_f(np.arange(len(ak))); bs = [inter_f(ix) for ix in A.draws]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f'    2x2 interaction (G4/G3) / (G5/G0), newPayload: {pt:.3f} ({lo:.3f}-{hi:.3f}); interval includes 1: {lo <= 1 <= hi}')
        # [6b] does the plans-and-readers step still lengthen regular blocks end to end?
        r_ = A.reg
        print('[6b] G4 against G3, regular blocks (ms per block, G3 -> G4, difference with interval):')
        for col, nm in ((0, 'newPayload'), (1, 'execution'), (4, 'state-root wait'), (5, 'readers\' join')):
            print(f'    {nm:16s} {np.nanmean(P["P3"][r_, col]):.2f} -> {np.nanmean(P["P4"][r_, col]):.2f}; {fd(A.diff("P4", "P3", col, r_))}')
        oc = {r: P[r][:, 0] - P[r][:, 1] for r in ('P3', 'P4')}
        d = oc['P4'] - oc['P3']; bs = [d[ix][r_[ix]].mean() for ix in A.draws]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f'    outside execution {oc["P3"][r_].mean():.2f} -> {oc["P4"][r_].mean():.2f}; {d[r_].mean():+.2f} ({lo:+.2f} to {hi:+.2f})')
        g = A.ratio('P4', 'P3', 0, r_)
        print('    -> ' + ('plans and readers no longer lengthen regular blocks end to end' if g[2] <= 1 else
                          'plans and readers lengthen regular blocks end to end; the differences above say where' if g[1] > 1 else
                          'not resolved on these blocks'))
    print('\n[7] the ablation against the main comparison, on the ablation segments (newPayload, all blocks of these segments)')
    print('    (rows: P0-P5 are G0-G5, P6-P8 are GX GC GXC)')
    ks = {int(k) for k, _, _ in ABL}
    sel = np.array([k in ks for k, _ in keys])
    if sel.any() and 'P4' in A.V:
        mm = M.ratio('PN', 'UP', 0, sel); aa = A.ratio('P4', 'P0', 0)
        # P0 against UP on the same blocks (different processes, the integration build with Prologue off against the official build)
        common = [(k, b) for k, b in ak if (k, b, 'UP') in vals]
        p0up = sum(av[(k, b, 'P0')][0] for k, b in common) / sum(vals[(k, b, 'UP')][0] for k, b in common) if common else float('nan')
        gap = abs(aa[0] - mm[0])
        print(f'    PN/UP {fr(mm)}; G4/G0 {fr(aa)}; G0/UP {p0up:.3f} ({len(common)} blocks, position >= 2); |difference| {gap:.3f}, '
              f'twice the per-segment sd {2 * sd:.3f}')
        print('    -> ' + ('the ablation only decomposes the contributions; the overall level is the main comparison\'s' if gap > 2 * sd
                          else 'the ablation and the main comparison agree within the spread between machines'))

if REC:
    # [8] the recording process (records on; its times are not compared with the timing processes)
    W = ('slot_miss_ms', 'acct_miss_ms', 'code_miss_ms')
    wv = {}
    for k, d, lab in REC:
        for p in range(NPR):
            for r in csv.DictReader(open(f'{d}/results/blocks_{lab}{p}.csv')):
                if r['role'] == 'measured' and r['cfg'] in ROWS_REC and int(float(r['pos'])) >= 2:
                    wv[(int(k), int(r['block']), r['cfg'])] = [float(r.get(c) or 0) for c in W] + [float(r['exec_ms']), float(r['new_payload_ms'])]
    kb = sorted({(k, b) for k, b, _ in wv if all((k, b, rr) in wv for rr in ROWS_REC)})
    reg = np.array([cls.get(b) == 'nomint' for _, b in kb])
    print(f'\n[8] recording process: {len(REC)} segments, {len(kb)} blocks under all of {ROWS_REC} (position >= 2; regular {reg.sum()})')
    print('    ms per block: ' + ', '.join(W) + ', exec_ms, new_payload_ms; storage-wait share of execution')
    for rr in ROWS_REC:
        for sel, nm in ((np.ones(len(kb), bool), 'all'), (reg, 'regular'), (~reg, 'batch-mint')):
            if not sel.any():
                continue
            v = np.array([wv[(k, b, rr)] for (k, b), s_ in zip(kb, sel) if s_])
            m = v.mean(axis=0)
            print(f'      {rr:4s} {nm:10s}: ' + ' '.join(f'{x:.2f}' for x in m) + f'; share {m[:3].sum() / m[3]:.3f}')
