"""Phase 18 engineering speed-ups for scripts/predict.py (applied as patches by scripts/phase18_eval.py; predict.py itself
is not modified). Every option keeps the prediction semantics: with the wall-clock budget disabled, the predicted slot
set of every transaction is identical to that of predict.py (checked by scripts/phase18_identity.py).

Options (P18_FAST, '+'-separated):
  ifree   index-free constraint check of family records (the `_failing` closure of Predictor._frame): the list of
          index-free constraints of a constraint alternative and the class of each constraint (Predictor._cons_class,
          a pure function of the expression) are computed once per loaded summary instead of once per frame, and the
          evaluation of an index-free constraint reuses the frame's evaluation cache (ctx['_evcache'], the cache that
          Predictor._cons_ok already uses; index-free expressions do not depend on the loop-index assignment).
  cache   in-process summary cache: least-recently-used eviction (predict.py evicts in load order), a byte cap of
          P18_CACHE_BYTES pickle bytes (default 1.5e9; predict.py uses SUMMARY_MAX_BYTES=4e7 and at most 80 summaries),
          the raw grouped records are dropped after the per-summary grouping has been built (it is the only form the
          predictor reads), and the loaded objects are moved out of the cyclic garbage collector's scan set (gc.freeze),
          so that full collections do not traverse the cached summaries.
"""
import os, gc, inspect, textwrap

OLD_FAILING = '''        def _failing(cons):
            """classes of the index-free constraints of `cons` that evaluate to the opposite of what the path wants"""
            out = set()
            for e, w in cons:
                if idx_ids(e): continue
                try: v = evaluate(e, ctx) != 0
                except Unknown: continue
                if v != w: out.add(self._cons_class(e, w))
            return out
'''
NEW_FAILING = '''        _p18 = summ.get('_p18')
        if _p18 is None: _p18 = summ['_p18'] = ({}, {})
        _p18_if, _p18_cl = _p18
        _p18_ev = ctx['_evcache']
        def _failing(cons):
            """classes of the index-free constraints of `cons` that evaluate to the opposite of what the path wants"""
            pre = _p18_if.get(id(cons))
            if pre is None: pre = _p18_if[id(cons)] = tuple((e, w) for e, w in cons if not idx_ids(e))
            out = set()
            usec = ctx.get('idx') is None
            for e, w in pre:
                v = _p18_ev.get(id(e)) if usec else None
                if v is None:
                    try: v = evaluate(e, ctx) != 0
                    except Unknown: v = 2
                    if usec: _p18_ev[id(e)] = v
                if v == 2: continue
                if v != w:
                    k = (id(e), w); c = _p18_cl.get(k)
                    if c is None: c = _p18_cl[k] = self._cons_class(e, w)
                    out.add(c)
            return out
'''


def _patch_frame(predict):
    src = textwrap.dedent(inspect.getsource(predict.Predictor._frame))
    # the method source is dedented by 4 spaces; the closure body sits at 4 spaces of indentation inside it
    o = textwrap.indent(textwrap.dedent(OLD_FAILING), '    ')
    n = textwrap.indent(textwrap.dedent(NEW_FAILING), '    ')
    assert src.count(o) == 1, 'predict.Predictor._frame changed: _failing block not found exactly once'
    src = src.replace(o, n)
    ns = {}
    exec(compile(src, '<predict_fast._frame>', 'exec'), predict.__dict__, ns)
    predict.Predictor._frame = ns['_frame']


def _patch_cache(predict):
    cap = int(float(os.environ.get('P18_CACHE_BYTES', '1.5e9')))
    S = predict.SummaryStore
    _init, _get, _lazy = S.__init__, S.get, S._lazy_get

    def __init__(self, *a, **k):
        _init(self, *a, **k)
        self.max_loaded_bytes = cap; self.max_loaded = 10 ** 6

    def get(self, codehash):
        s = self.cache.pop(codehash, None)
        if s is not None:               # hit: move to the most-recently-used end (dict order = eviction order)
            self.cache[codehash] = s; return s
        return _get(self, codehash)

    def _lazy_get(self, codehash):
        s = _lazy(self, codehash)
        if s is not None and s.get('compact') == 2:
            for k in ('site_groups', 'call_groups', 'cons_table'): s.pop(k, None)
            gc.freeze()
        return s
    S.__init__, S.get, S._lazy_get = __init__, get, _lazy_get


def apply(predict, opts):
    opts = set(o for o in opts.split('+') if o)
    assert opts <= {'ifree', 'cache'}, opts
    if 'ifree' in opts: _patch_frame(predict)
    if 'cache' in opts: _patch_cache(predict)
    return opts
