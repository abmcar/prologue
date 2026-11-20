#!/usr/bin/env python3
# EXP-193: copy of EXP-192 scripts/parse.py, unchanged.
# EXP-192: copy of EXP-189 scripts/parse.py, unchanged.
# EXP-189: copy of EXP-184 parse.py plus the `eap zk` fields (zk_*, the line of block N is written at block N+1's start)
# and the record field zk (the block carries the proof-verification entry).
# EXP-184: copy of EXP-183 parse.py, unchanged.
# EXP-182: copy of EXP-181 parse.py, unchanged.
# EXP-181: copy of EXP-177 parse.py, unchanged.
# EXP-177: copy of EXP-176 parse.py, unchanged.
# EXP-169: copy of EXP-167 parse.py, unchanged (EXP-169 counters are parsed from the node log by the analysis scripts).
"""EXP-159: copy of EXP-157 parse.py plus the dedicated-thread counters pw_heavy_* and the eap-x159 counters lx_fit_over,
lx_fit_budget_out, pw_after_end. EXP-122: copy of EXP-120 parse.py plus the non-blocking pass counters nb_*. EXP-101: copy of EXP-094 parse.py, unchanged. EXP-094: copy of EXP-093 parse.py, unchanged. EXP-080: adds the fresh-state counters fs_*. EXP-078: adds the counter sd_disarmed. EXP-023 (copy of EXP-019 parse.py, plus the EXP-023 counters sd_handover, pw_gated, pw_dedup). EXP-019: (copy of EXP-018 parse.py; adds the prewarm-worker call-start fields of eap-x19 and per-block figures from the
diagnostics file raw/<label>.diag.jsonl: storage misses in catch-up transactions, misses on keys a reader loaded too late
by source, and the not-in-cross-block-cache lookups used for the strata): merge the driver records (raw/<label>.jsonl) with the node log lines (`cc cache timing`, `eap block`) of
raw/<label>.node.log into results/blocks_<label>.csv, one row per measured (and warm-up) block.
usage: parse.py LABEL [LABEL ...]"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw')
RES = os.path.join(HERE, '..', 'results')
KV = re.compile(r'(\w+)=(-?[\w.]+)')


def kv(line):
    return {k: v for k, v in KV.findall(line)}


def num(d, k, default=0.0):
    try:
        v = d[k]
        if v in ('true', 'false'):
            return float(v == 'true')
        return float(v)
    except (KeyError, ValueError):
        return default


LOW, HIGH = 20.2, 26.2  # not-in-cross-block-cache slot lookups per Mgas (segment review 5.1)


def diag_block(d):
    """Per-block figures from one EAP_DIAG line (reth eap-x19)."""
    txs = {x[0]: x for x in d['tx']}

    def kind(i):
        x = txs.get(i)
        if x is None or x[1] not in (5, 6) or x[3] < 0:
            return 'not_prewarmed'
        if x[4] <= x[11]:
            return 'timely'
        return 'catchup' if x[3] <= x[11] else 'exec_first'
    lk = [0, 0, 0, 0]
    for x in d['tx']:
        for k in range(4):
            lk[k] += x[13 + k]
    for arr in (d['pre'], d['post']):
        for k in range(4):
            lk[k] += arr[k]
    g = d['gas'] / 1e6
    nc = (lk[0] + lk[1] + lk[3]) / g if g else 0.0
    m2 = d.get('miss2', [])
    cu = [m for m in m2 if m[0] >= 0 and kind(m[0]) == 'catchup']
    kinds = [kind(i) for i in txs]
    out = {'d_lk_pw': lk[0], 'd_lk_reader': lk[1], 'd_lk_old': lk[2], 'd_lk_miss': lk[3], 'd_not_cached_per_mgas': nc,
           'stratum': 'low' if nc < LOW else ('mid' if nc < HIGH else 'high'),
           'd_slot_miss': len(m2), 'd_slot_miss_ms': sum(m[7] for m in m2) / 1e6,
           'd_cu_miss': len(cu), 'd_cu_miss_ms': sum(m[7] for m in cu) / 1e6, 'd_cu_txs': kinds.count('catchup'),
           'd_timely_share': kinds.count('timely') / max(1, len(kinds)), 'd_traced': int(bool(d.get('frames')))}
    for src, name in ((2, 'tx'), (3, 'cs0'), (4, 'cs1'), (5, 'pw')):
        late = [m for m in m2 if m[2] == 2 and m[3] == src]
        out[f'd_late_{name}'] = len(late)
        out[f'd_late_{name}_ms'] = sum(m[7] for m in late) / 1e6
    out['d_late_prewarm'] = sum(1 for m in m2 if m[2] == 1)
    out['d_not_loaded'] = sum(1 for m in m2 if m[2] == 0)
    out['d_loaded_before'] = sum(1 for m in m2 if m[2] == 3)
    return out


def parse(label):
    cc, eap, zkl = {}, {}, {}
    for line in open(os.path.join(RAW, f'{label}.node.log')):
        if 'cc cache timing' in line:
            d = kv(line)
            cc[int(d['block'])] = d
        elif 'eap block' in line:
            d = kv(line)
            eap[int(d['block'])] = d
        elif 'eap zk' in line:
            d = kv(line)
            zkl[int(d['block'])] = d
    diag = {}
    dpath = os.path.join(RAW, f'{label}.diag.jsonl')
    if os.path.exists(dpath):
        for line in open(dpath):
            d = json.loads(line)
            diag[d['block']] = diag_block(d)
    rows = []
    for line in open(os.path.join(RAW, f'{label}.jsonl')):
        r = json.loads(line)
        n = r['block']
        m = r['metrics']
        C = cc.get(n, {})
        E = eap.get(n, {})
        exec_ms = m.get('reth_sync_execution_execution_histogram_sum', 0.0) * 1000
        row = {'label': label, 'block': n, 'role': r['role'], 'cfg': r['cfg'].split('+')[0], 'cfg_full': r['cfg'], 'cycle': r['cycle'], 'pos': r['pos'], 'txs': r['txs'], 'gas_used': r['gas_used'],
               'new_payload_ms': r['new_payload_ms'], 'exec_ms': exec_ms, 'exec_count': m.get('reth_sync_execution_execution_histogram_count', 0),
               'read_ms': sum(v for k, v in m.items() if 'fetch_latency_sum' in k and 'source="engine"' in k) * 1000,
               'state_root_ms': m.get('reth_sync_block_validation_state_root_histogram_sum', 0.0) * 1000,
               'engine_cpu_ms': r['engine']['cpu_ns'] / 1e6, 'engine_runq_ms': r['engine']['runq_ns'] / 1e6, 'engine_majflt': r['engine']['majflt'], 'engine_minflt': r['engine'].get('minflt', ''),   # apply_mem248.py (EXP-248): records only
               'engine_migr': r['engine'].get('migr', ''), 'engine_ivcsw': r['engine'].get('ivcsw', ''), 'engine_vcsw': r['engine'].get('vcsw', ''),   # apply_pc.py
               'proc_cpu_ms': r['proc']['utime_ms'] + r['proc']['stime_ms'], 'proc_utime_ms': r['proc']['utime_ms'], 'proc_stime_ms': r['proc']['stime_ms'],
               'proc_cpu_fcu_ms': r['proc_fcu']['utime_ms'] + r['proc_fcu']['stime_ms'],
               **{f'idle_s{s}_{w}': (sum(v for k, v in r['cpuidle'].items() if k.endswith(f's{s}{t}')) if r.get('cpuidle') else '')
                  for s in (2, 3) for w, t in (('n', 'u'), ('us', 't'))},   # apply_ci.py
               **({f'disk_{k}': v for k, v in r['disk'].items()} if r.get('disk') else {}),   # apply_disk257.py (EXP-257)
               **({f'irq_{k}': v for k, v in r['irq'].items()} if r.get('irq') else {}),   # apply_irq_block.py (X-028)
               'proc_majflt': r['proc']['majflt'], 'proc_minflt': r['proc'].get('minflt', ''), 'proc_read_mb': r['proc']['read_bytes'] / 1e6, 'load1': float(r['load'].split()[0]),
               'cc_exec_ms': num(C, 'exec_ns') / 1e6, 'cc_read_ms': num(C, 'read_ns') / 1e6}
        for kind in ('acct', 'slot', 'code'):
            for src in ('pw', 'old', 'eap', 'cs0', 'cs1'):
                row[f'{kind}_hit_{src}'] = num(C, f'{kind}_hit_{src}')
                row[f'{kind}_hit_{src}_ms'] = num(C, f'{kind}_hit_{src}_ns') / 1e6
            row[f'{kind}_miss'] = num(C, f'{kind}_miss')
            row[f'{kind}_miss_ms'] = num(C, f'{kind}_miss_ns') / 1e6
        for k in ('frames', 'frames_plan', 'cs_keys', 'cs_us', 'inst_us', 'txs_plan', 'tx_keys', 'reads', 'dup', 'read_us', 'busy_us', 'miss_unpred', 'miss_queued',
                  'miss_inflight', 'miss_done', 'join_wait_us', 'frames_d0', 'frames_plan_d0', 'frames_plan_d1', 'cs_keys_d0', 'cs_keys_d1', 'miss_late_tx',
                  'miss_late_cs0', 'miss_late_cs1', 'reads_tx', 'reads_cs0', 'reads_cs1', 'reader_cpu_us', 'wall_us', 'join_us', 'slots', 'code', 'txs', 'txmod', 'noread',
                  'miss_late_pw', 'reads_pw', 'pwcs', 'pw_frames', 'pw_jobs', 'pw_keys', 'pw_hook_us', 'pw_far', 'pw_stale', 'pw_sync_keys',
                  'sd_txs', 'sd_runs', 'sd_keys', 'sd_run_us', 'sd_wait_us', 'sd_timeouts', 'sd_handover', 'pw_gated', 'pw_dedup', 'sd_disarmed', 'fs_diffs', 'fs_cands', 'fs_runs', 'fs_txs', 'fs_keys', 'fs_jobs', 'fs_late', 'fs_run_us', 'claimed', 'sl_stale', 'miss_late_sd', 'reads_sd',
                  'nb_txs', 'nb_steps', 'nb_keys', 'nb_forced', 'nb_hist', 'nb_skipped', 'nb_ok', 'nb_us',
                  'ct_jobs', 'ct_calls', 'ct_plans', 'ct_keys', 'ct_keys_new', 'ct_us', 'miss_late_ct', 'reads_ct',
                  'lx_groups', 'lx_fit', 'lx_calls', 'lx_c2', 'lx_plans', 'lx_keys', 'lx_keys_new', 'lx_us', 'lx_fit_us',   # EXP-130
                  'lx_dropped', 'txdec_txs', 'txdec_keys_new', 'lx_fit_known', 'lx_dec_capped', 'lx_drop_calls', 'lx_drop_keys', 'c2_evals', 'c2_addrs', 'c2_fail',   # EXP-151
                  'join_threads_us', 'kt_us', 'busy_at_stop',   # EXP-150
                  'pw_heavy_txs', 'pw_heavy_run_us', 'pw_heavy_wait_us', 'pw_heavy_pool', 'lx_fit_over', 'lx_fit_budget_out', 'pw_after_end',   # EXP-159
                  'exrt', 'exrt_state', 'exrt_refused',   # apply_rt.py
                  'ewnear', 'ewnear_eff', 'ewnear_raised', 'ewnear_refused', 'ewnear_back', 'ewnear_us'):   # apply_nr.py
            row[f'eap_{k}'] = num(E, k) if E else float('nan')
        row.update(diag.get(n, {}))
        row['zk'] = r.get('zk', 0)
        Z = zkl.get(n)
        row['zk_line'] = int(Z is not None)
        for k in ('pre', 'learn', 'glv', 'glv_muls', 'da_muls', 'learned', 'learned_txs', 'triggered', 'skips', 'skip_us', 'skip_muls', 'submitted', 'dup', 'cached',
                  'computed', 'stored', 'failed', 'cpu_us', 'exec_hit_ahead', 'exec_hit_other', 'exec_miss_inflight', 'exec_miss_other', 'pw_hit_ahead', 'pw_hit_other', 'pw_miss'):
            row[f'zk_{k}'] = num(Z, k) if Z else 0.0
        # thread-name groups of live threads (CPU ms during newPayload)
        # EXP-120: lead wait, pool feeding and txpool snapshot counters
        row['lead_s'] = r.get('lead_s', 0.0)
        fd = r.get('feed') or {}
        for k in ('sent', 'skipped', 'accepted', 'rejected', 'ms'):
            row[f'feed_{k}'] = fd.get(k, '')
        row['feed_errors'] = json.dumps(fd.get('errors', {})) if fd else ''
        for k, v in (r.get('txpool_snapshot') or {}).items():
            row['tps_' + k.split('txpool_snapshot_')[-1]] = v
        for g, v in sorted(r['threads'].items()):
            if v > 0:
                row[f'thr_{g}_ms'] = v
        rows.append(row)
    keys = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    os.makedirs(RES, exist_ok=True)
    out = os.path.join(RES, f'blocks_{label}.csv')
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, '') for k in keys})
    print(out, len(rows), 'rows;', sum(r['role'] == 'measured' for r in rows), 'measured')


if __name__ == '__main__':
    for label in sys.argv[1:]:
        parse(label)
