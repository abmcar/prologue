#!/usr/bin/env python3
# EXP-199 short comparison rounds (README section 6.4): copy of scripts/run_xl_e.py (frozen for the second comparison while
# it runs) plus the candidate configurations of the next rounds.
# EXP-199 second development run (README section 6.2, written before the run): copy of scripts/run_xl.py of the first run at
# commit be8747ac (frozen for the first run while it runs) plus the configurations D-WEXAnR, D-WEXAnC, D-WEXAnN.
# EXP-199 (X-020, README section 6, written before the run): copy of EXP-198 scripts/run_xl.py plus the configurations D-*
# (EAP's own prewarm mechanism on eap-x199, every one with iqc=1) and the pre-check of the mechanism (precheck_ew).
# EXP-194 (README section 2, written before the run): copy of EXP-193 scripts/run_xl.py with the configurations T-U, T-UR, T-F,
# T-FR (stock and EXP-185 C-FA, both with glv=1 as EXP-193's A00 and A10, without and with the txpool snapshot tpw=1) and the
# pre-check configuration T-FR1 (T-FR in the reuse check mode); FEED_ALL=0 feeds the realistic plan only to tpw=1 blocks, as
# EXP-148 (every block still waits FEED_T + FEED_T2); PRECHECK_TPW=guaranteed stops the txpool pre-check only when the
# snapshot line is missing or nothing fed was accepted (the shares are reported); the zk learning check at the first
# measured block only when the warm-up configuration learns (zklearn=1).
# EXP-193 (README section 2, written before the run): copy of EXP-192 scripts/run_xl.py with the stepwise configurations
# A00-A11 (Master 2026-10-27 15:52, the researcher's ablation): stock plus glv, then one group of switches added per step,
# A10 = EXP-185 C-FA plus glv (Z-F), A11 = A10 plus the BN254 multiplications computed ahead (Z-FZ4). Nothing else changed.
# EXP-192 (README sections 2-4, written before the run): copy of EXP-189 scripts/run_xl.py with the three configurations
# of the confirmation run (Master 2026-10-27 12:0x): Z-S (stock K-U plus glv=1, srdiag=1), Z-F (the C-FA control line of
# EXP-185, verbatim, plus glv=1), Z-FZ4 (Z-F plus zklearn=1 zkpre=4) and the pre-check configuration Z-FZ41 (Z-FZ4 in the
# reuse check mode, as EXP-185 C-FA1); no node-level code settings (bigra, ccv, sysn) on any side. Z-FZ41 is also added to
# the reported F family of the reuse pre-check (reported only; the stop rule is unchanged). Nothing else changed.
# EXP-189 (README sections 3-5, written before the run): copy of EXP-184 scripts/run_xl.py with the configurations of the
# BN254 multiplications computed ahead (Z-*, K-WZ, Z-AZ81), the rotation stratified by whether a block carries a
# transaction to the proof-verification entry (ZKCLASS, SEQ_ZK), the record fields `zk` and the stratum's cycle, the
# pre-check precheck_zk189 (the `eap zk` line of every pre-check block with the control line's switches; quantities
# reported) and the learning check at the end of the warm-up. z2 (README section 10): RUNS3=1 hands the measured range to
# the standard rotation scripts/schedule_runs3.py (segments of 3 blocks per configuration, RUNS3_CFGS, the entry blocks
# as targets), records seg and pos (position in the segment) and cycle = seg // (2 x configurations); configurations
# Z-AZ41 (pre-check with zkpre=4). Header of the EXP-184 copy follows.
# EXP-184: copy of EXP-183 scripts/run_xl.py; changes: the EXP-184 configurations (C-U, C-A, C-AC, C-AS, C-ACS, the
# pre-check configuration C-ACS1 and the warm-up configuration K-WC, block after the H-* configurations), the calldata-address
# pre-check precheck_cd184 (stop only on conditions the code guarantees with cdaddr/cdst on; quantities reported), and C-ACS1 /
# K-WC counted in the method / stock families of the reuse pre-check; for c2 (README section 11) C-AL, C-AL1 and K-WL
# (learning from the execution thread's misses, cdlearn=1) and the cdlearn switch in precheck_cd184.
# EXP-130 m1 (eap-x150, merge of eap-x130 and eap-x141b): copy of EXP-141 scripts/run_xl.py with EXP-130's configurations
# (PxmTL ... PxmTLD+kd) and the merged-branch arms PxmTLB+kd / PxmTLDH+kd added (search "EXP-130").
"""EXP-183 (Master 10-26, after X-018 found that with --jit the speculative passes run compiled contracts without the
inspector's step hook, EXP-180 section 7.11): H-Ai = H-A plus pwnbinterp=1 (eap-x180b 3e65fe0: the speculative passes and the
post-block history pass run every frame in the interpreter). The pre-check alternates H-APSi1 (H-APS1 plus pwnbinterp=1,
even pre-check blocks) and H-APS1 (PRECHECK_ALT, odd pre-check blocks); precheck_interp183 asks only what the code guarantees:
the `eap block` line shows the switch as set and the site table grows over the pre-check (nb_sites, a process-wide table
size). Reported only: the step hook per speculative pass (nb_steps / nb_txs) per half and its factor (a stop condition
"strictly larger" stopped h1's first attempt at its 100th pre-check block with 0.86 although the switch acted; Master 10-26:
a functional pre-check uses only conditions the code guarantees, expected quantities are reported), nb_val_site /
nb_val_reads and nb_val_aborted per half (Master 10-26; nb_val_site counts the hook's slot reads that found a
site value, nb_val_reads the reads answered with a prediction, so the quotient is not a share and can exceed 1). The reuse pre-check counts H-APSi1 as the method family too.
EXP-183 (copy of EXP-182 run_xl.py; README section 6, written before the run): configurations on G-FA of EXP-182 -
H-U stock, H-A (= G-FA), H-Ab0 (H-A with pwnbbh=0: no post-block history pass of the speculative helpers), H-AP (H-A plus
rdpool=1: block readers on persistent threads), H-AS (H-A plus pwsplit=4 pwsplitv=2 pwsplitmin=20: X-017's split of batch
entries with at least 20 elements), H-APS (both), pre-check configuration H-APS1 (H-APS in the reuse check mode). Pre-checks
added: precheck_rdpool (every line rdpool=true, pool threads 8-64 at the end, overflow and nice_unpooled reported) and
precheck_split183 (X-017's rule: split_threads 0 or 4, 4 exactly in the blocks with a split dispatch, 4 exit lines each; the
EXP-169 split pre-check, which needs sysn, is not used). The reuse pre-check counts H-APS1 as the method family.
EXP-182 (copy of EXP-181 run_xl.py; README section 5, written before the run): the merged binary eap-x182 on a general
development segment. Configurations (all with the state-root diagnostics srdiag=1): G-U stock; G-F the full method of the
confirmation run (EXP-177 K-FRD: extrapolation, entry decoding, dedicated heavy threads, account prefetch, the extra readers
behind the account gate, reuse); G-FL (G-F plus pwlxnoself=1), G-FH (G-F plus heavy-first dispatch pwheavyfirst=4, X-017),
G-FV (G-F plus the speculative passes of X-018, EXP-180 _K_V, helpers at nice NBNICE), G-FA (all three), G-FAT (G-FA plus
X-017's dispatch-time proof targets srtx=1, Master 10-26), G-FATJ (G-FAT plus rdjoinlate=1: the readers are joined at the
next block's start, Master 10-26); the pre-check configuration G-FATJ1 (G-FATJ in the reuse check mode). Pre-checks: the dedicated threads (precheck_heavy), heavy-first picks
(precheck_heavyfirst, EXP-179), the speculative passes, abort and helper nice values (precheck_val, EXP-180), the account
handout in report mode and the account gate in report mode (general segment: the gate may stay closed, PRECHECK_GATE as
EXP-180), pwlxnoself on every line, the readers' block-end join (EXP-181), an `eap sr` line for every pre-check block
(precheck_sr) and the dispatch-time proof targets in it (precheck_srtx); the helper nice check of the first measured blocks
of G-FV, G-FA and G-FAT (EXP-180); the srtx flag of the `eap sr` line of the first measured block of every configuration
(true only for G-FAT); the reuse pre-check counts G-FA1 and G-FAT1 as the method family.
EXP-181 (copy of EXP-177 run_xl.py; README section 7): configurations K-FDN (K-FD plus pwlxnoself=1: an extrapolation
job hands every key to the readers instead of reading each call's first key itself), K-FNR (K-F plus pwlxnoself=1 and
pwrdpf=8: every reader takes up to 8 waiting slots and accounts and walks their pages together with asynchronous reads), the
pre-check configuration K-FNPR (both walks; the pre-check also asks the same of rd_pf_* for pwrdpf), K-FNP (K-F plus pwlxnoself=1 and
pwlxpf=64: the job's reader then walks the job's libmdbx pages and asks for the missing ones asynchronously, 64 lookups in
progress; 8 readers, no extra ones) and K-FN (K-F plus pwlxnoself=1, the fallback third configuration); with a pre-check
configuration that sets pwlxnoself / pwlxpf the pre-check also asks that every pre-check block line carries
pwlxnoself=true (and pwlxpf=W), that at least half of the pre-check blocks of class mint with an extrapolation fit walked
pages (lx_pf_jobs > 0 and lx_pf_items > 0), and that walks ended by a page that did not parse are at most 1% of the
lookups walked (lx_pf_bad <= 0.01 lx_pf_items).
EXP-177 (copy of EXP-176 run_xl.py): configurations K-FD and K-FRD (K-F and K-FR plus eight extra readers behind the
eap-x177 account gate, pwlxrd=8 pwlxrdacct=16) and the pre-check configuration K-FRD1 (K-FD in the reuse check mode); with a
pre-check configuration that sets pwlxrdacct, the pre-check also asks that the gate follows the account count (README
section 4): every pre-check block with lx_acct >= N logs lx_rd_woken = pwlxrd and lx_rd_open_us > 0, every block with
lx_acct < N logs lx_rd_woken = 0 and lx_rd_open_us = 0, the block lines carry pwlxrdacct=N, and at least one block opens.
EXP-176 (copy of EXP-175 run_xl.py): the metric filter also records fresh execution-cache creations
(reth_sync_caching_execution_cache_creation_duration_seconds_count: the next block could not take the saved cache) and the
cache-saving gauge. EXP-175 (copy of EXP-174 run_xl.py): the confirmation-run configurations K-* on eap-x174 9862556 (see CONFIGS; README
section 2), the warm-up configurations K-FR1 / K-W in the reuse check mode (the reuse pre-check counts them as the method and
stock families), and the account-handout pre-check by pre-execution class (PRECHECK_ACCT=mint: among the pre-check blocks of
class cls_mint = mint in CLASSFILE with an extrapolation fit, at least half hand out accounts; PRECHECK_ACCT=report: counts only).
EXP-174 (copy of EXP-172 run_xl.py): functional-check configurations of the merged binary eap-x174 (see CONFIGS):
F-A, F-lr, F-S2, U-N next to F, F-R1f, F-Rf and S0.
EXP-172 (copy of EXP-171 run_xl.py): configurations X-LDH-A (X-LDH plus pwlxacct=1: the extrapolation hands the
predicted callees' and callers' accounts to the readers), X-LDH-AB (X-LDH-A with the per-block key budget 4,000) and
X-LDH-AR (X-LDH-A with 16 readers); with PRECHECK_CFG=X-LDH-A the pre-check also asks that the account handout works
(pwlxacct=true in the block lines, lx_acct and lx_acct_read > 0 over the pre-check blocks, and lx_acct > 0 in at least
half of the pre-check blocks with an extrapolation fit). The EXP-171 reuse pre-check and reuse stop rule run only when a
configuration of the run uses reuse (after n1's first submission stopped on them).
EXP-171 (copy of EXP-169 run_xl.py): configurations U-R, F-R (reuse of the prewarm results, reuse=2, every 16th
transaction checked instead, reusechk=16) and the check-mode warm-up W-R1 / pre-check F-R1 (reuse=1); after the warm-up the
reuse pre-check (README section 7): every warm-up block's `eap reuse` line present, no difference, valid results and checked
transactions on both configuration families; during the run the driver stops after any block whose `eap reuse` line reports
a difference or the trip flag (besides the existing stop on a newPayload or forkchoiceUpdated status other than VALID).
EXP-169 (copy of EXP-167 run_xl.py): configurations U-S, F-S (pwsplit=4) and the -y cells (the block's system-call slots
were read at the end of the previous block: the driver adds sysn=1 to the control line of the block before every -y block,
from a schedule computed before the first block), pre-check PC (split helpers and next-block slots). EXP-167 (copy of EXP-159 run_xl.py): configurations F-nl, F-rn (see CONFIGS). EXP-159 (copy of EXP-157 run_xl.py): configurations F, F-h0, F-s0, F-t0 (second segment, see CONFIGS); configuration X-LDH-nk (X-LDH without the per-key diagnostics pwtrace=1); with PERF=1 a
flat profile of the node process (perf record -k CLOCK_MONOTONIC -e cpu-clock -F 499, no call graph, child threads followed; sample
times comparable with the records' mono field; Master 2026-10-24 03:03: every major fault with its data address, -e major-faults/period=1/ -d,
in the same session, for X-009) runs over the measured and filler blocks, written to <out>/<label>.perf.data, stopped after the last block or before the node is stopped.
EXP-157 (copy of EXP-152 run_xl.py): the plan gates relaxed on general blocks - configurations X-LDH-k0 (pwk=0) and X-LDH-k0m0
(pwk=0 pwmin=0) next to X-LDH and U-S0; warm-up configuration Scnt (stock plus call counting: cnt=1 pwmin=32, so that the
fast-forward and warm-up blocks count calls for pwmin; eap.rs 545-553 counts only when pwmin > 0); the pre-check also asks that the
k0 configuration was never gated (pw_gated == 0) and issued plan jobs (pw_jobs > 0).
EXP-152 (copy of EXP-148 run_xl.py): the 14 configurations of the second unified run on eap-x150 7c3d3e2; the realistic
feeding is done for every block (only the R configurations, tpw=1, prewarm from the txpool); the pre-check also asks for salt-template
evaluations (c2_evals) and known-sequence fits (lx_fit_known) over the pre-check blocks.
EXP-148 (copy of EXP-130 run_xl.py with the EXP-127 realistic txpool feeding and the EXP-146 filler count): configurations
S0+k, S0R+k (stock plus txpool prewarm fed realistically), PxmTLDH+k (full method of eap-x150) and PxmTLDHR+k (full method plus
txpool prewarm); FEED_PLAN csv (block, tx, delay_ms): only transactions the public mempool saw, batch 1 (lead >= FEED_T) then a
wait of FEED_T, batch 2 (lead in [FEED_T2, FEED_T)) then a wait of FEED_T2; every other block waits FEED_T + FEED_T2 as well;
NFILL filler blocks after each cycle; pre-check (PRECHECK_CFG with pwheavy and tpw): dedicated threads busy, the txpool
snapshot used, feeding accepted.
EXP-129 (copy of EXP-122 run_xl.py; adds the configurations PxmTNSH/PxmTNS2 and the history-pass pre-check). EXP-122 (copy of EXP-120 run_xl.py; adds the configurations PxmTN/PxmTN0). EXP-120 (copy of EXP-101 run_xl.py; additions: configurations S0M/PxmTM with tpw=1, txpool feeding of the next block's raw transactions LEAD s before its newPayload for tpw=1 blocks, the same LEAD wait for every other measured/warm-up/filler block; feed counts in the per-block record).
EXP-101 (copy of EXP-094 run_xl.py; uj3/ui3 additions: FILLER, SETTLE_MIN/SETTLE_MAX, signal-proof stop_node; block pacing changed before the run: an adaptive wait after each block instead of the
fixed SETTLE (adaptive_settle: at least 50 ms, then every 20 ms until the node used less than one clock tick of CPU time in
the last 50 ms and /proc/meminfo Writeback < 1 MB, at most 1 s; recorded as settle_s), core-busy samples 0.05 s before a
block (was 1 s) and in the record (was 0.5 s); the gate PGATE is unchanged). Interpreter segment only (after the JIT
segment had run): the core-busy fraction excludes the CPU time of the node process tree (pcore_busy(dt, pid)). EXP-094 (copy of EXP-093 run_xl.py): configuration A0 (A without the counting inspector) and MIN_HEAD added.
EXP-082 (copy of EXP-081 run_xl.py; configurations A, K, PxmK added). EXP-069 (copy of EXP-067 scripts/run_x67.py, unchanged configurations). EXP-067: (copy of EXP-063 scripts/run_x63.py; every configuration gets cnt=1). EXP-063: (copy of EXP-033 scripts/run_x33.py, unchanged). EXP-033: (copy of EXP-026 scripts/run_x26.py, unchanged configurations). EXP-026: (copy of EXP-023 scripts/run_x23.py with configuration Pxm added). EXP-023: (copy of EXP-019 scripts/run_x19.py, configurations replaced; EXP-019 was a copy of EXP-018 scripts/run_r27.py); changes: the configurations below
(all with prewarming on; a name ending in "+r" adds per-frame recording, trace19=1), warm-up configuration and
sequence from the environment (WARM, SEQ). Everything else (records, node start, checks, load gate) unchanged. The
node writes the per-block diagnostics (EAP_DIAG, reth branch eap-x19) itself.
Run under `an exclusive lock` (node use).
EXP-081 (copy of EXP-080 run_xl.py, unchanged configurations). EXP-080 (copy of EXP-078 run_xl.py; configuration PxmF added). EXP-078 (copy of EXP-076 run_xl.py; configurations PSDxmN and PSDxmG instead of PxmC). EXP-076 (copy of EXP-074 run_xl.py):
adds MEASURE=indicator (see below), configuration PxmC, and a try/finally that stops the node after any exception once it
has started.
usage: [MEASURE=indicator] EAP_CTRL_FILE=F EAP_PLANS=D [NODE_CPUS=0-7] [SEQ=...] [WARM=S] [SETTLE=2] [LOADGATE=4 | PGATE=0.25] run_x19.py LABEL BINARY N_MEASURED BLOCKS_DIR OUT_DIR WARMUP [-- extra reth node args]
Blocks start at the node head + 1; WARMUP warm-up blocks run with configuration WARM, then N_MEASURED measured blocks."""
import collections, csv, hashlib, json, os, signal, subprocess, sys, time, urllib.request, re

ER = os.path.join(os.environ['PROLOGUE_NODE_HOME'], 'engine-replay')   # Prologue server copy: scripts/server/apply_server.py
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ER)
import replay as R  # noqa: E402

TICK = os.sysconf('SC_CLK_TCK')
TOML = os.path.join(os.environ['PROLOGUE_NODE_HOME'], 'data', 'reth.toml')
METRIC_KEYS = re.compile(r'^(reth_sync_execution_execution_histogram_(sum|count)|reth_sync_block_validation_(state_root_histogram|total_duration)_sum|'
                         r'reth_sync_state_provider_total_\w+_fetch_latency_sum|reth_revmc_jit_\w+|'
                         r'reth_sync_caching_execution_cache_creation_duration_seconds_count|reth_sync_prewarm_cache_saving_duration|reth_sync_prewarm_reuse_\w+)')   # apply_r290.py (EXP-243/244, Master 11-03)   # EXP-176

# Per-block configurations written to the node's EAP_CTRL file (eap.rs Mode::parse; reth eap-x19 from 419b7b1). prewarm=1 everywhere.
CONFIGS = {
    'S': 'prewarm=1 insp=0 cs=0 tx=0 code=0',
    'SDg': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 sd=1000000 sdr=6',
    'SDn': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 sds=24 sdr=6 sdp2=1',
    'SDn1': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 sds=24 sdr=6',
    'P': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1',
    'Pd': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1',
    'Pk': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8',
    'PSDg': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 sd=1000000 sdr=6',
    'PSDn': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 sds=24 sdr=6 sdp2=1',
    'PdSDn': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 sds=24 sdr=6 sdp2=1',
    'PkSDn': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 sds=24 sdr=6 sdp2=1',
    'PdSDg': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 sd=1000000 sdr=6',
    # EXP-023 frozen configurations (README 5.2)
    'SDx': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 sds=24 sdr=6 sdp2=1',
    'Px': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8',
    'PSDx': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 sds=24 sdr=6 sdp2=1',
    'PSDxm': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 sds=24 sdr=6 sdp2=1 pwmin=32',
    # EXP-026: Px with plans generated with compilation (used after 32 calls), no storage discovery
    'Pxm': 'prewarm=1 insp=0 cs=0 tx=0 code=0 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 pwmin=32',
}
# EXP-033 development run after the confirmation (eap-x19 7d68e08): execution-thread claims of queued slots, 16 readers
CONFIGS['PSDxC'] = CONFIGS['PSDx'] + ' claim=1'
CONFIGS['PSDxC16'] = CONFIGS['PSDx'].replace('readers=8', 'readers=16') + ' claim=1'
# second development run (eap-x19 4c7d9be): handed-out slots of passed transactions dropped, with claims
CONFIGS['PSDxL'] = CONFIGS['PSDx'] + ' claim=1 slstale=1'
# third development run (eap-x19 a05d8f9): discovery keys behind plan keys on the same readers
CONFIGS['PSDxP'] = CONFIGS['PSDx'] + ' sdlow=1'
# EXP-067: calls counted on the prewarm workers in every block (cnt=1) for all configurations, so that pwmin sees all blocks
CONFIGS['Pxm'] = CONFIGS['Px'] + ' pwmin=32'
CONFIGS['S0'] = CONFIGS['S']  # stock reth: no inspector on the prewarm workers, no counting
# EXP-078: compile-condition plans with storage discovery (PSDxm, as EXP-067), plans also inside discovery runs
# (pwnodisc=0), and discovery only for prewarm transactions without a plan job (sdgap=1, eap-x19 cc24946)
CONFIGS['PSDxmN'] = CONFIGS['PSDxm'].replace(' pwnodisc=1', ' pwnodisc=0')
CONFIGS['PSDxmG'] = CONFIGS['PSDxm'] + ' sdgap=1'
# EXP-080: Pxm plus fresh-state speculative runs for transactions whose prewarm run issued >= 16 plan jobs (eap-x19 bece77a)
CONFIGS['PxmF'] = CONFIGS['Pxm'] + ' fs=16'
for _k in ('S', 'SDx', 'Pxm', 'PSDx', 'PSDxm', 'PSDxmN', 'PSDxmG', 'PxmF'):
    CONFIGS[_k] = CONFIGS[_k] + ' cnt=1'
for _k in list(CONFIGS):
    CONFIGS[_k + '+r'] = CONFIGS[_k] + ' trace19=1'
# EXP-082 (copy of EXP-081 run_xl.py): the previous EAP (three parts, call-start prediction on the execution thread), its
# account and code prefetch alone, and Pxm with that prefetch added, next to stock reth and Pxm on the same blocks.
CONFIGS['A'] = 'prewarm=1 insp=1 cs=1 tx=1 code=1 readers=8 cnt=1'
CONFIGS['K'] = 'prewarm=1 insp=0 cs=0 tx=1 code=1 slots=0 readers=8 cnt=1'
CONFIGS['PxmK'] = CONFIGS['Pxm'].replace('tx=0 code=0', 'tx=1 code=1 slots=0')
# EXP-085: the new EAP plus the previous EAP's transaction-arrival stage on the readers (sender and target accounts, target
# code, the target's plan slots); no inspector and no call-start instantiation on the execution thread
CONFIGS['PxmT'] = CONFIGS['Pxm'].replace('tx=0 code=0', 'tx=1 code=1')
# EXP-093: the arrival stage alone, accounts and code only (K) or with its plan slots (T, the previous EAP's arrival part),
# without the counting inspector on the prewarm workers (no plans in these blocks, so no counting needed)
CONFIGS['K'] = 'prewarm=1 insp=0 cs=0 tx=1 code=1 slots=0 readers=8'
CONFIGS['T'] = 'prewarm=1 insp=0 cs=0 tx=1 code=1 readers=8'
# EXP-094: the previous EAP without the counting inspector on the prewarm workers (cnt=1 is A's only reason for that
# inspector: eap.rs pw_inspector returns None when pwcs=0, trace=0 and cnt=0, eap-x19 bece77a line 1570)
CONFIGS['A0'] = CONFIGS['A'].replace(' cnt=1', '')
assert 'cnt' not in CONFIGS['A0'] and 'cnt=1' in CONFIGS['A']
# EXP-120: txpool-stage prewarming (reth --engine.txpool-prewarming, node-side flag tpw=1 lets the block use the snapshot)
CONFIGS['S0M'] = CONFIGS['S0'] + ' tpw=1'
CONFIGS['PxmTM'] = CONFIGS['PxmT'] + ' tpw=1'
# EXP-122: non-blocking prewarm pass on the prewarm workers for transactions with gas limit >= 1,000,000 (pwnbgas),
# tainted branches predicted from the direction history of earlier passes (pwnbhist=1)
CONFIGS['PxmTN'] = CONFIGS['PxmT'] + ' pwnb=1 pwnbgas=1000000 pwnbhist=1'
CONFIGS['PxmTN0'] = CONFIGS['PxmT'] + ' pwnb=1 pwnbgas=1000000 pwnbhist=0'
# EXP-122 second segment: the non-blocking pass on a separate thread (pwnbsep=1), and per-key diagnostics (+k: pwtrace=1,
# key times to EAP_KEYDIAG, EXP-105) on every configuration of the segment
CONFIGS['PxmTNS'] = CONFIGS['PxmTN'] + ' pwnbsep=1'
# EXP-129: the two corrections: branch history from the post-block history pass (pwnbbh=1) and a bounded wait of
# 20 us for handed-out slots (pwnbwait=20); PxmTNSH has only the history correction
CONFIGS['PxmTNSH'] = CONFIGS['PxmTNS'] + ' pwnbbh=1 pwnbwait=0'
CONFIGS['PxmTNS2'] = CONFIGS['PxmTNS'] + ' pwnbbh=1 pwnbwait=20'
# EXP-129 second segment: early start of the pass on 4 helper threads (pwnbearly=4); PxmTNS3P also hands its slots to the readers'
# slot channel (pwnbprio=1)
CONFIGS['PxmTNS3'] = CONFIGS['PxmTNS2'] + ' pwnbearly=4'
CONFIGS['PxmTNS3P'] = CONFIGS['PxmTNS3'] + ' pwnbprio=1'
# EXP-129 third segment: level-by-level runahead (up to 6 passes per transaction, 8 ms budget, 1 ms wait per level)
CONFIGS['PxmTNS4'] = CONFIGS['PxmTNS3P'] + ' pwnblevels=6 pwnbbudget=8000 pwnblvlwait=1000'
# EXP-129 fourth segment: reads with a tainted key are not handed to the readers (the offline model's rule)
CONFIGS['PxmTNS5'] = CONFIGS['PxmTNS4'] + ' pwnbtaintkey=1'
# EXP-129 fifth segment (diagnostic): the pass's reads of every level are dumped (pwnbdump=1)
CONFIGS['PxmTNS5D'] = CONFIGS['PxmTNS5'] + ' pwnbdump=1'
# EXP-141: heavy transactions (gas limit >= 1e6) prewarmed first on 4 dedicated threads
CONFIGS['PxmTH'] = CONFIGS['PxmT'] + ' pwheavy=4 pwheavygas=1000000'
# EXP-141 second segment: dedicated threads only when idle, else the pool
CONFIGS['PxmTH2'] = CONFIGS['PxmTH'] + ' pwheavyidle=1'
# EXP-141 third segment: recovered transactions reach the prewarm dispatch as soon as each is recovered
CONFIGS['PxmTH3'] = CONFIGS['PxmTH2'] + ' pwearlydisp=1'
for _k in ('PxmT', 'PxmTN', 'PxmTNS', 'PxmTNSH', 'PxmTNS2', 'PxmTNS3', 'PxmTNS3P', 'PxmTNS4', 'PxmTNS5', 'PxmTNS5D', 'PxmTH', 'PxmTH2', 'PxmTH3'):
    CONFIGS[_k + '+k'] = CONFIGS[_k] + ' pwtrace=1'
# EXP-130: loop-call extrapolation on the prewarm workers (predicted callees resolved on the readers, proxies followed one level)
CONFIGS['PxmTL'] = CONFIGS['PxmT'] + ' pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 ctd=2'
CONFIGS['PxmTLr'] = CONFIGS['PxmTL'] + ' ctr=4'
# EXP-130 second segment (Master 2026-10-22): per-key diagnostics on all three configurations (as EXP-122 +k), the per-fit
# log (pwlxdbg, prewarm-worker side only) on PxmTL alone
CONFIGS['S0+k'] = CONFIGS['S0'] + ' pwtrace=1'
CONFIGS['PxmTL+kd'] = CONFIGS['PxmTL'] + ' pwtrace=1 pwlxdbg=1'
# EXP-130 third segment: the prewarm workers in the interpreter (pwjit=0), so the step hook sees the salt preimages
CONFIGS['PxmTLi+kd'] = CONFIGS['PxmTL'] + ' pwjit=0 pwtrace=1 pwlxdbg=1'
# EXP-130 d1: PxmTL plus the structure decoder at arrival and the per-block key budget
CONFIGS['PxmTLD+kd'] = CONFIGS['PxmTL'] + ' txdec=1 pwlxbudget=1500 pwtrace=1 pwlxdbg=1'
# EXP-130 m1: extrapolation without the structure decoder (gate and budget kept), and the full method with the dedicated
# heavy-transaction threads of EXP-141 (final configuration pwheavy=4 pwheavygas=1000000 pwheavyidle=1)
CONFIGS['PxmTLB+kd'] = CONFIGS['PxmTL'] + ' pwlxbudget=1500 pwtrace=1 pwlxdbg=1'
CONFIGS['PxmTLDH+kd'] = CONFIGS['PxmTLD+kd'] + ' pwheavy=4 pwheavygas=1000000 pwheavyidle=1'
# EXP-148: the full method of eap-x150 without the per-fit log, per-key diagnostics on every configuration, txpool prewarm (tpw=1)
CONFIGS['PxmTLDH+k'] = CONFIGS['PxmTL'] + ' txdec=1 pwlxbudget=1500 pwheavy=4 pwheavygas=1000000 pwheavyidle=1 pwtrace=1'
CONFIGS['S0R+k'] = CONFIGS['S0+k'] + ' tpw=1'
CONFIGS['PxmTLDHR+k'] = CONFIGS['PxmTLDH+k'] + ' tpw=1'
# EXP-152 (Master 2026-10-23): every configuration with readers has rdstop=1 except X-LDH-rdstop0; per-key diagnostics on
# every non-stock configuration; the one-off arms remove one part from the full method X-LDH
_X_LD = CONFIGS['PxmTL'] + ' txdec=1 pwlxbudget=1500 rdstop=1 pwlxcnt=1 pwlxbin=1 c2rec=1'
_X_H = ' pwheavy=4 pwheavygas=1000000 pwheavyidle=1'
CONFIGS['U-S0'] = CONFIGS['S0']
CONFIGS['S0R'] = CONFIGS['S0'] + ' tpw=1'
CONFIGS['X-T'] = CONFIGS['PxmT'].replace(' pwcs=1', ' pwcs=0') + ' rdstop=1 pwtrace=1'
CONFIGS['X-PxmT'] = CONFIGS['PxmT'] + ' rdstop=1 pwtrace=1'
CONFIGS['X-LD'] = _X_LD + ' pwtrace=1'
CONFIGS['X-LDH'] = _X_LD + _X_H + ' pwtrace=1'
CONFIGS['X-LDHR'] = _X_LD + _X_H + ' tpw=1 pwtrace=1'
CONFIGS['X-LDH-s0'] = _X_LD + _X_H + ' pwlxslots=0 pwtrace=1'
CONFIGS['X-LDH-dec0'] = _X_LD.replace(' txdec=1', ' txdec=0') + _X_H + ' pwtrace=1'
CONFIGS['X-LDH-v0'] = _X_LD + _X_H + ' pwlxv=0 pwtrace=1'
CONFIGS['X-LDH-bin0'] = _X_LD.replace(' pwlxbin=1', ' pwlxbin=0') + _X_H + ' pwtrace=1'
CONFIGS['X-LDH-cnt0'] = _X_LD.replace(' pwlxcnt=1', ' pwlxcnt=0') + _X_H + ' pwtrace=1'
CONFIGS['X-LDH-c2r0'] = _X_LD.replace(' c2rec=1', ' c2rec=0') + _X_H + ' pwtrace=1'
CONFIGS['X-LDH-rdstop0'] = _X_LD.replace(' rdstop=1', ' rdstop=0') + _X_H + ' pwtrace=1'
# EXP-157 (Master 2026-10-24): the two plan gates relaxed on the full method; warm-up / fast-forward configuration with call counting
CONFIGS['X-LDH-k0'] = CONFIGS['X-LDH'].replace(' pwk=8', ' pwk=0')
CONFIGS['X-LDH-k0m0'] = CONFIGS['X-LDH-k0'].replace(' pwmin=32', ' pwmin=0')
CONFIGS['Scnt'] = CONFIGS['S0'] + ' cnt=1 pwmin=32'
assert ' pwk=8' in CONFIGS['X-LDH'] and ' pwmin=32' in CONFIGS['X-LDH'] and ' pwk=0' in CONFIGS['X-LDH-k0'] and ' pwmin=0' in CONFIGS['X-LDH-k0m0']
assert ' pwk=8' not in CONFIGS['X-LDH-k0'] and ' pwmin=32' in CONFIGS['X-LDH-k0'] and 'pwcs' not in CONFIGS['Scnt']

# EXP-159 (Master 2026-10-24): the full method without the per-key diagnostics (gated calls are then not instantiated, no key trace)
CONFIGS['X-LDH-nk'] = CONFIGS['X-LDH'].replace(' pwtrace=1', '')
assert ' pwtrace=1' in CONFIGS['X-LDH'] and 'pwtrace' not in CONFIGS['X-LDH-nk'] and CONFIGS['X-LDH-nk'] + ' pwtrace=1' == CONFIGS['X-LDH']
# EXP-159 second segment (binary eap-x159 with the bounded fit): F is the full method without per-key diagnostics; one
# reduction each: no dedicated heavy-transaction threads (F-h0), transaction arrival without the entry plan's slots
# (F-s0: sender and target accounts, target code and the entry calldata decoder only), no transaction-arrival stage (F-t0)
CONFIGS['F'] = CONFIGS['X-LDH-nk']
CONFIGS['F-h0'] = CONFIGS['F'].replace(' pwheavy=4 pwheavygas=1000000 pwheavyidle=1', '')
CONFIGS['F-s0'] = CONFIGS['F'] + ' slots=0'
CONFIGS['F-t0'] = CONFIGS['F'].replace(' tx=1 code=1', ' tx=0 code=0')
assert 'pwheavy' not in CONFIGS['F-h0'] and ' tx=0 code=0' in CONFIGS['F-t0'] and 'pwtrace' not in CONFIGS['F'] and CONFIGS['F-h0'] != CONFIGS['F']
# EXP-167 (eap-x170 functional check): the node-level storage switches of EXP-158 (bigra=1 ccv=1) and the EXP-160 priority
# switches (rdnice=10 hvnice=10) on the full method F; S (stock plus cnt=1, pwmin=0) separates method blocks to check that
# pwmin=0 blocks count calls (EXP-160 fix), against S0 (no counting)
CONFIGS['F-nl'] = CONFIGS['F'] + ' bigra=1 ccv=1'
CONFIGS['F-rn'] = CONFIGS['F'] + ' rdnice=10 hvnice=10'
assert ' cnt=1' in CONFIGS['S'] and 'pwmin' not in CONFIGS['S'] and 'cnt' not in CONFIGS['S0'] and 'pwcs' not in CONFIGS['S']
# EXP-169 (eap-x169): batch entries split into elements for 4 helper threads (pwsplit=4) on the stock configuration U and the
# full method F; every configuration also as a -y cell: the same control line, and the block before it carries sysn=1 (its
# end reads this block's system-call slots into the saved execution cache). PC: pre-check (split helpers, sysn every block).
CONFIGS['U'] = CONFIGS['S0']
CONFIGS['U-S'] = CONFIGS['U'] + ' pwsplit=4'
CONFIGS['F-S'] = CONFIGS['F'] + ' pwsplit=4'
for _k in ('U', 'U-S', 'F', 'F-S'):
    CONFIGS[_k + '-y'] = CONFIGS[_k]
CONFIGS['PC'] = CONFIGS['F-S'] + ' sysn=1'
# EXP-171 (eap-x171): reuse of the prewarm results on stock reth (U-R) and on the full method (F-R); warm-up in check mode
CONFIGS['W-R1'] = CONFIGS['Scnt'] + ' reuse=1'
CONFIGS['F-R1'] = CONFIGS['F'] + ' reuse=1'
CONFIGS['U-R'] = CONFIGS['U'] + ' reuse=2 reusechk=16'
CONFIGS['F-R'] = CONFIGS['F'] + ' reuse=2 reusechk=16'
# EXP-171 r3 (eap-x171 1c72cdc): the read-set check restricted to the keys written so far in the block (reusefast=1); the
# check-mode warm-up compares the restricted and the full check on every transaction (fast_diff must stay 0)
CONFIGS['F-Rf'] = CONFIGS['F-R'] + ' reusefast=1'
CONFIGS['F-R1f'] = CONFIGS['F-R1'] + ' reusefast=1'
CONFIGS['W-R1f'] = CONFIGS['W-R1'] + ' reusefast=1'
assert 'reuse' not in CONFIGS['U'] and 'reuse' not in CONFIGS['F'] and CONFIGS['U-R'].startswith(CONFIGS['U'] + ' ') and CONFIGS['F-R'].startswith(CONFIGS['F'] + ' ')
assert 'pwsplit' not in CONFIGS['F'] and 'pwsplit' not in CONFIGS['U'] and 'sysn' not in CONFIGS['F-S-y'] and 'pwtrace' not in CONFIGS['F']
# EXP-172 (eap-x172): prefetch of the predicted callees' and callers' accounts, alone and with a larger key budget or more readers
CONFIGS['X-LDH-A'] = CONFIGS['X-LDH'] + ' pwlxacct=1'
CONFIGS['X-LDH-AB'] = CONFIGS['X-LDH-A'].replace(' pwlxbudget=1500', ' pwlxbudget=4000')
CONFIGS['X-LDH-AR'] = CONFIGS['X-LDH-A'].replace(' readers=8', ' readers=16')
assert ' pwlxbudget=1500' in CONFIGS['X-LDH'] and ' readers=8' in CONFIGS['X-LDH'] and ' pwtrace=1' in CONFIGS['X-LDH']
assert ' pwlxbudget=4000' in CONFIGS['X-LDH-AB'] and ' readers=16' in CONFIGS['X-LDH-AR'] and 'pwlxacct' not in CONFIGS['X-LDH']
# EXP-174 (eap-x174): every new switch on its own on top of the full method F (all new switches off = eap-x170's F)
CONFIGS['F-A'] = CONFIGS['F'] + ' pwlxacct=1'
CONFIGS['F-lr'] = CONFIGS['F-A'] + ' pwlxrd=4'
CONFIGS['F-S2'] = CONFIGS['F'] + ' pwsplit=4 pwsplitv=2'
CONFIGS['U-N'] = CONFIGS['S0'] + ' bigra=1 ccv=1 sysn=1'
assert 'pwtrace' not in CONFIGS['F'] and 'pwlxacct' not in CONFIGS['F'] and 'reuse' not in CONFIGS['F'] and 'pwsplit' not in CONFIGS['F']
# EXP-175 (eap-x174 9862556): the confirmation run (README section 2). K-F is the full method (EXP-174 F plus the account
# prefetch, no per-key trace); reuse is not part of K-F until the researcher decides (then K-F takes the K-FR line and K-FR goes)
_K_REUSE = ' reuse=2 reusechk=16 reusefast=1'
_K_N = ' bigra=1 ccv=1 sysn=1'
_K_S = ' pwsplit=4 pwsplitv=2'
CONFIGS['K-U'] = CONFIGS['S0']
CONFIGS['K-US'] = CONFIGS['S0'] + _K_S
CONFIGS['K-UN'] = CONFIGS['S0'] + _K_N
CONFIGS['K-UR'] = CONFIGS['S0'] + _K_REUSE
CONFIGS['K-B'] = CONFIGS['PxmT'] + ' rdstop=1'
CONFIGS['K-F'] = CONFIGS['F'] + ' pwlxacct=1'
CONFIGS['K-FN'] = CONFIGS['K-F'] + _K_N
CONFIGS['K-FS2'] = CONFIGS['K-F'] + _K_S
CONFIGS['K-Fx'] = CONFIGS['K-F'].replace(' pwlx=1 ', ' pwlx=0 ').replace(' txdec=1 ', ' txdec=0 ')
CONFIGS['K-Fs'] = CONFIGS['K-F'] + ' pwlxslots=0'
CONFIGS['K-Fa0'] = CONFIGS['F']
CONFIGS['K-FR'] = CONFIGS['K-F'] + _K_REUSE
# warm-up in the reuse check mode (EXP-171 pre-check): the method family K-FR1 (pre-check blocks) and the stock family K-W
CONFIGS['K-FR1'] = CONFIGS['K-F'] + ' reuse=1 reusefast=1'
CONFIGS['K-W'] = CONFIGS['Scnt'] + ' reuse=1 reusefast=1'
assert ' pwlx=0 ' in CONFIGS['K-Fx'] and ' txdec=0 ' in CONFIGS['K-Fx'] and 'pwtrace' not in CONFIGS['K-F'] and 'reuse' not in CONFIGS['K-F']
assert ' rdstop=1' in CONFIGS['K-B'] and 'pwlx' not in CONFIGS['K-B'] and 'pwheavy' not in CONFIGS['K-B'] and 'pwlxacct' not in CONFIGS['K-Fa0']
# EXP-175 option (b): the main-table configurations also in interpreted execution, block by block in the same process; a name
# ending in "@i" switches the node's compiled-code lookup off (`reth_jit disable`, EXP-032) before the block, every other
# block switches it on; the control line is the configuration's own
# EXP-177 (eap-x177 8e780cf): eight extra readers that start once the block has handed out 16 predicted accounts
_K_D = ' pwlxrd=8 pwlxrdacct=16'
CONFIGS['K-FD'] = CONFIGS['K-F'] + _K_D
CONFIGS['K-FRD'] = CONFIGS['K-FR'] + _K_D
CONFIGS['K-FRD1'] = CONFIGS['K-FD'] + ' reuse=1 reusefast=1'
# EXP-181 (eap-x181): the extrapolation job hands out every key (pwlxnoself=1); asynchronous page walk of the job (pwlxpf=W)
CONFIGS['K-FDN'] = CONFIGS['K-FD'] + ' pwlxnoself=1'
CONFIGS['K-FNP'] = CONFIGS['K-F'] + ' pwlxnoself=1 pwlxpf=64'
CONFIGS['K-FN'] = CONFIGS['K-F'] + ' pwlxnoself=1'
# EXP-181 after the small test t1: every reader walks up to 8 waiting slots and accounts together (pwrdpf=8); the pre-check
# configuration K-FNPR switches on both page walks
CONFIGS['K-FNR'] = CONFIGS['K-F'] + ' pwlxnoself=1 pwrdpf=8'
CONFIGS['K-FNPR'] = CONFIGS['K-F'] + ' pwlxnoself=1 pwlxpf=64 pwrdpf=8'
assert 'pwlxrd=8 pwlxrdacct=16' in CONFIGS['K-FDN'] and 'pwlxrd' not in CONFIGS['K-FNP'] and 'pwtrace' not in CONFIGS['K-FNP']
assert CONFIGS['K-FRD'] == CONFIGS['K-F'] + _K_REUSE + _K_D and 'pwlxacct=1' in CONFIGS['K-FD'] and 'pwlxrd' not in CONFIGS['K-FR']
for _k in ('K-U', 'K-F', 'K-FR', 'K-UR'):
    CONFIGS[_k + '@i'] = CONFIGS[_k]
# EXP-182 (eap-x182, README section 5.2): the speculative passes of X-018 (EXP-180 _K_V, unchanged) with the helpers' nice value
# NBNICE (0: not set; fixed before the run after X-018's result and written in README section 5.2); srdiag=1 everywhere
# Master 10-26: the helpers' nice value and the gas threshold of the speculative passes (pwnbgas) are chosen by X-018's v1
# segment and given as NBNICE / NBGAS (README section 5.2); EXP-180 used pwnbgas=1000000
NBNICE = os.environ.get('NBNICE', '')
if NBNICE not in ('', '0', '10'):
    raise SystemExit(f'NBNICE must be 0 or 10, not {NBNICE}')
NBGAS = os.environ.get('NBGAS', '1000000')
if not NBGAS.isdigit():
    raise SystemExit(f'NBGAS must be a gas amount, not {NBGAS}')
_K_V = f' pwnb=1 pwnbval=1 pwnbgas={NBGAS} pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000'
_K_VN = _K_V + (f' pwnbnice={NBNICE}' if NBNICE not in ('', '0') else '')
_G_SR = ' srdiag=1'
CONFIGS['G-U'] = CONFIGS['K-U'] + _G_SR
CONFIGS['G-F'] = CONFIGS['K-FRD'] + _G_SR
CONFIGS['G-FL'] = CONFIGS['K-FRD'] + ' pwlxnoself=1' + _G_SR
CONFIGS['G-FH'] = CONFIGS['K-FRD'] + ' pwheavyfirst=4' + _G_SR
CONFIGS['G-FV'] = CONFIGS['K-FRD'] + _K_VN + _G_SR
CONFIGS['G-FA'] = CONFIGS['K-FRD'] + ' pwlxnoself=1 pwheavyfirst=4' + _K_VN + _G_SR
CONFIGS['G-FA1'] = CONFIGS['K-FRD1'] + ' pwlxnoself=1 pwheavyfirst=4' + _K_VN + _G_SR
# Master 10-26: X-017's dispatch-time proof targets (eap-x182 016e3b9, srtx=1: senders, recipients and access lists handed to
# the state-root task as proof targets at dispatch)
CONFIGS['G-FAT'] = CONFIGS['K-FRD'] + ' pwlxnoself=1 pwheavyfirst=4' + _K_VN + ' srtx=1' + _G_SR
CONFIGS['G-FAT1'] = CONFIGS['K-FRD1'] + ' pwlxnoself=1 pwheavyfirst=4' + _K_VN + ' srtx=1' + _G_SR
# Master 10-26 (EXP-182 section 9): the readers' block-end join moved to the next block's start (eap-x181 da1c679 -> x182 7a1146d)
CONFIGS['G-FATJ'] = CONFIGS['K-FRD'] + ' pwlxnoself=1 pwheavyfirst=4' + _K_VN + ' srtx=1 rdjoinlate=1' + _G_SR
CONFIGS['G-FATJ1'] = CONFIGS['K-FRD1'] + ' pwlxnoself=1 pwheavyfirst=4' + _K_VN + ' srtx=1 rdjoinlate=1' + _G_SR
assert CONFIGS['G-FATJ'] == CONFIGS['G-FAT'].replace(_G_SR, ' rdjoinlate=1' + _G_SR) and all('rdjoinlate' not in CONFIGS[k] for k in ('G-U', 'G-F', 'G-FL', 'G-FH', 'G-FV', 'G-FA', 'G-FAT', 'K-W', 'S0'))
# EXP-183 (README section 6): on G-FA
_H_SPLIT = ' pwsplit=4 pwsplitv=2 pwsplitmin=20'
CONFIGS['H-U'] = CONFIGS['K-U'] + _G_SR
CONFIGS['H-A'] = CONFIGS['G-FA']
CONFIGS['H-Ab0'] = CONFIGS['G-FA'].replace(' pwnbbh=1 ', ' pwnbbh=0 ')
CONFIGS['H-AP'] = CONFIGS['G-FA'].replace(_G_SR, ' rdpool=1' + _G_SR)
CONFIGS['H-AS'] = CONFIGS['G-FA'].replace(_G_SR, _H_SPLIT + _G_SR)
CONFIGS['H-APS'] = CONFIGS['G-FA'].replace(_G_SR, ' rdpool=1' + _H_SPLIT + _G_SR)
CONFIGS['H-APS1'] = CONFIGS['G-FA1'].replace(_G_SR, ' rdpool=1' + _H_SPLIT + _G_SR)
CONFIGS['H-Ai'] = CONFIGS['G-FA'].replace(_G_SR, ' pwnbinterp=1' + _G_SR)   # Master 10-26 (EXP-180 section 7.11)
CONFIGS['H-APSi1'] = CONFIGS['H-APS1'].replace(_G_SR, ' pwnbinterp=1' + _G_SR)
assert all('pwnbinterp' not in CONFIGS[k] for k in ('H-U', 'H-A', 'H-Ab0', 'H-AP', 'H-AS', 'H-APS', 'H-APS1')) and ' pwnbbh=1 ' in CONFIGS['H-Ai']
assert ' pwnbbh=0 ' in CONFIGS['H-Ab0'] and ' pwnbbh=1 ' in CONFIGS['H-A'] and CONFIGS['H-Ab0'].count('pwnbbh') == 1
assert all(CONFIGS[k].endswith(_G_SR) for k in ('H-U', 'H-A', 'H-Ab0', 'H-AP', 'H-AS', 'H-APS', 'H-APS1', 'H-Ai', 'H-APSi1'))
assert 'reuse=1' in CONFIGS['H-APS1'] and 'reuse=2' in CONFIGS['H-APS'] and 'rdpool' not in CONFIGS['H-A'] and 'pwsplit' not in CONFIGS['H-A']
assert all('rdjoinlate' not in CONFIGS[k] and 'srtx' not in CONFIGS[k] for k in ('H-U', 'H-A', 'H-Ab0', 'H-AP', 'H-AS', 'H-APS', 'H-APS1', 'H-Ai', 'H-APSi1'))
# EXP-184 (README section 5): on G-FA with the node-level code settings; stock with them as the first reference; the
# pre-check configuration in the reuse check mode (G-FA1); the warm-up K-W learning the calldata positions (cdaddr only)
_C_N = ' bigra=1 ccv=1 sysn=1'
_C_CD = ' cdaddr=512 cdrate=10 cdmin=1 cdratio=4'
CONFIGS['C-U'] = CONFIGS['K-U'] + _C_N + _G_SR
CONFIGS['C-A'] = CONFIGS['G-FA'].replace(_G_SR, _C_N + _G_SR)
CONFIGS['C-AC'] = CONFIGS['G-FA'].replace(_G_SR, _C_N + _C_CD + _G_SR)
CONFIGS['C-AS'] = CONFIGS['G-FA'].replace(_G_SR, _C_N + ' cdst=1' + _G_SR)
CONFIGS['C-ACS'] = CONFIGS['G-FA'].replace(_G_SR, _C_N + _C_CD + ' cdst=1' + _G_SR)
CONFIGS['C-ACS1'] = CONFIGS['G-FA1'].replace(_G_SR, _C_N + _C_CD + ' cdst=1' + _G_SR)
CONFIGS['K-WC'] = CONFIGS['K-W'] + _C_CD
# EXP-184 c2 (README section 11): learning from the execution thread's misses (cdlearn=1), no cdst
_C_CDL = _C_CD + ' cdlearn=1'
CONFIGS['C-AL'] = CONFIGS['G-FA'].replace(_G_SR, _C_N + _C_CDL + _G_SR)
CONFIGS['C-AL1'] = CONFIGS['G-FA1'].replace(_G_SR, _C_N + _C_CDL + _G_SR)
CONFIGS['K-WL'] = CONFIGS['K-W'] + _C_CDL
assert 'cdst' not in CONFIGS['C-AL'] + CONFIGS['C-AL1'] + CONFIGS['K-WL'] and CONFIGS['C-AL'] == CONFIGS['C-AC'].replace(_G_SR, ' cdlearn=1' + _G_SR)
assert all(CONFIGS[k].endswith(_C_N + _G_SR) or CONFIGS[k].endswith(_C_N + _C_CD + _G_SR) or CONFIGS[k].endswith(' cdst=1' + _G_SR) for k in ('C-U', 'C-A', 'C-AC', 'C-AS', 'C-ACS', 'C-ACS1'))
assert 'cdaddr' not in CONFIGS['C-A'] + CONFIGS['C-AS'] + CONFIGS['C-U'] and 'cdst' not in CONFIGS['C-A'] + CONFIGS['C-AC'] + CONFIGS['C-U'] + CONFIGS['K-WC']
assert 'reuse=1' in CONFIGS['C-ACS1'] and 'reuse=2' in CONFIGS['C-ACS'] and all(CONFIGS['C-' + k].startswith(CONFIGS['G-FA'][:-len(_G_SR)]) for k in ('A', 'AC', 'AS', 'ACS'))
assert all('rdjoinlate' not in CONFIGS[k] and 'srtx' not in CONFIGS[k] and 'rdpool' not in CONFIGS[k] and 'pwsplit' not in CONFIGS[k] for k in ('C-U', 'C-A', 'C-AC', 'C-AS', 'C-ACS', 'C-ACS1', 'K-WC'))
assert CONFIGS['G-FAT'] == CONFIGS['G-FA'].replace(_G_SR, ' srtx=1' + _G_SR) and all('srtx' not in CONFIGS[k] for k in ('G-U', 'G-F', 'G-FL', 'G-FH', 'G-FV', 'G-FA', 'G-FA1'))
assert all('reuse=2' in CONFIGS[k] and _K_D in CONFIGS[k] and 'pwlxacct=1' in CONFIGS[k] and 'pwheavy=4' in CONFIGS[k] for k in ('G-F', 'G-FL', 'G-FH', 'G-FV', 'G-FA'))
assert 'reuse=1' in CONFIGS['G-FA1'] and 'reuse=2' not in CONFIGS['G-FA1'] and 'pwnb=' not in CONFIGS['G-F'] and 'pwnb=' not in CONFIGS['G-U']
assert all(CONFIGS[k].endswith(' srdiag=1') and 'pwtrace' not in CONFIGS[k] and 'srpf' not in CONFIGS[k] for k in ('G-U', 'G-F', 'G-FL', 'G-FH', 'G-FV', 'G-FA', 'G-FA1'))
# EXP-189 (README section 3): GLV on both sides (node level), the multiplications computed ahead with 4 and 8 threads, stock
# without GLV for GLV's own effect; the warm-up K-WZ learns the heavy entries (stock, counting and reuse check mode as K-W);
# the pre-check configuration Z-AZ81 is Z-AZ8 in the reuse check mode (G-FA1)
_Z_G = ' glv=1'
CONFIGS['Z-U0'] = CONFIGS['C-U']
CONFIGS['Z-U'] = CONFIGS['C-U'].replace(_G_SR, _Z_G + _G_SR)
CONFIGS['Z-A'] = CONFIGS['C-A'].replace(_G_SR, _Z_G + _G_SR)
CONFIGS['Z-AZ4'] = CONFIGS['C-A'].replace(_G_SR, _Z_G + ' zkpre=4' + _G_SR)
CONFIGS['Z-AZ8'] = CONFIGS['C-A'].replace(_G_SR, _Z_G + ' zkpre=8' + _G_SR)
CONFIGS['Z-AZ81'] = CONFIGS['G-FA1'].replace(_G_SR, _C_N + _Z_G + ' zkpre=8' + _G_SR)
CONFIGS['K-WZ'] = CONFIGS['K-W'] + ' zklearn=1'
assert CONFIGS['Z-U0'] == CONFIGS['K-U'] + _C_N + _G_SR and 'glv' not in CONFIGS['Z-U0'] and 'zk' not in CONFIGS['Z-U0']
assert all(CONFIGS[k].endswith(_C_N + _Z_G + _G_SR) for k in ('Z-U', 'Z-A')) and CONFIGS['Z-U'].startswith(CONFIGS['K-U'])
assert CONFIGS['Z-A'].startswith(CONFIGS['G-FA'][:-len(_G_SR)]) and all(CONFIGS[k].startswith(CONFIGS['Z-A'][:-len(_G_SR)]) for k in ('Z-AZ4', 'Z-AZ8'))
assert ' zkpre=4' in CONFIGS['Z-AZ4'] and ' zkpre=8' in CONFIGS['Z-AZ8'] and 'zkpre' not in CONFIGS['Z-A'] + CONFIGS['Z-U'] + CONFIGS['K-WZ']
assert 'reuse=1' in CONFIGS['Z-AZ81'] and 'reuse=2' in CONFIGS['Z-AZ8'] and all('cdaddr' not in CONFIGS[k] and 'cdst' not in CONFIGS[k] for k in ('Z-U0', 'Z-U', 'Z-A', 'Z-AZ4', 'Z-AZ8', 'Z-AZ81', 'K-WZ'))
assert all('rdjoinlate' not in CONFIGS[k] and 'srtx' not in CONFIGS[k] and 'rdpool' not in CONFIGS[k] and 'pwsplit' not in CONFIGS[k] for k in ('Z-U0', 'Z-U', 'Z-A', 'Z-AZ4', 'Z-AZ8', 'Z-AZ81', 'K-WZ'))
# EXP-189: blocks carrying a transaction to the entry (file with columns block, cls_zk in {zk, other}) rotate in their own
# cycle SEQ_ZK; the others in SEQ with the fillers
ZKCLASS = os.environ.get('ZKCLASS', '')
ZK_SET = set()
if ZKCLASS:
    import csv as _csv
    ZK_SET = {int(r['block']) for r in _csv.DictReader(open(ZKCLASS)) if r['cls_zk'] == 'zk'}
SEQ_ZK = os.environ.get('SEQ_ZK', '').split()
# EXP-189 z2 (README section 10): the standard rotation in runs of 3 (scripts/schedule_runs3.py)
RUNS3 = os.environ.get('RUNS3', '0') == '1'
RUNS3_CFGS = os.environ.get('RUNS3_CFGS', '').split()
RUNS3_INFO = {}   # block -> (seg, position in the segment, cycle)
CONFIGS['Z-AZ41'] = CONFIGS['G-FA1'].replace(_G_SR, _C_N + _Z_G + ' zkpre=4' + _G_SR)
assert 'reuse=1' in CONFIGS['Z-AZ41'] and ' zkpre=4' in CONFIGS['Z-AZ41'] and CONFIGS['Z-AZ41'] == CONFIGS['Z-AZ81'].replace(' zkpre=8', ' zkpre=4')
# EXP-192 (README section 2): the control lines of the confirmation run. _C_FA185 is EXP-185's C-FA, copied verbatim
# (experiments/EXP-185-confirm-general2/scripts/run_xl.py, CONFIGS['C-FA'] with NBNICE=10 NBGAS=5000000)
_C_FA185 = ('prewarm=1 insp=0 cs=0 tx=1 code=1 readers=8 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 pwmin=32 cnt=1 pwlx=1 pwlxn=4 '
            'pwlxmax=512 pwlxc2=1 ctd=2 txdec=1 pwlxbudget=1500 rdstop=1 pwlxcnt=1 pwlxbin=1 c2rec=1 pwheavy=4 pwheavygas=1000000 pwheavyidle=1 '
            'pwlxacct=1 pwlxrd=8 pwlxrdacct=16 reuse=2 reusechk=16 reusefast=1 pwlxnoself=1 pwheavyfirst=4 pwnb=1 pwnbval=1 pwnbgas=5000000 '
            'pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 srdiag=1')
CONFIGS['Z-S'] = CONFIGS['K-U'] + _Z_G + _G_SR
CONFIGS['Z-F'] = _C_FA185.replace(_G_SR, _Z_G + _G_SR)
CONFIGS['Z-FZ4'] = CONFIGS['Z-F'].replace(_G_SR, ' zklearn=1 zkpre=4' + _G_SR)
CONFIGS['Z-FZ41'] = CONFIGS['Z-FZ4'].replace(' reuse=2 reusechk=16 reusefast=1', ' reuse=1 reusefast=1')
assert CONFIGS['Z-S'] == 'prewarm=1 insp=0 cs=0 tx=0 code=0 glv=1 srdiag=1'
assert sorted(CONFIGS['Z-F'].split()) == sorted(_C_FA185.split() + ['glv=1'])
assert sorted(CONFIGS['Z-FZ4'].split()) == sorted(CONFIGS['Z-F'].split() + ['zklearn=1', 'zkpre=4'])
assert sorted(CONFIGS['Z-FZ41'].split()) == sorted([t for t in CONFIGS['Z-FZ4'].split() if t not in ('reuse=2', 'reusechk=16')] + ['reuse=1'])
assert all(k not in CONFIGS[c] for c in ('Z-S', 'Z-F', 'Z-FZ4', 'Z-FZ41') for k in ('bigra', 'ccv', 'sysn', 'cdaddr', 'cdst', 'srtx', 'rdjoinlate', 'pwsplit', 'pwjit'))
if NBNICE == '10' and NBGAS == '5000000':   # the run's setting: Z-F is G-FA (as the EXP-189 runs) plus glv, without node-level settings
    assert sorted(CONFIGS['Z-F'].split()) == sorted(CONFIGS['G-FA'].split() + ['glv=1'])
# EXP-192: end of the configurations
# EXP-193 (README section 2): each step adds one group of switches to the previous step (a key already present is replaced,
# srdiag=1 stays last). Order: the parts that use no access plan, then the plans at transaction arrival and at call start,
# the speculative pass (it needs pwcs: eap.rs `m.active && m.pwnb && m.pwcs > 0`), the extrapolation and its three parts.
_A_STEPS = [
    ('A01', ' pwheavy=4 pwheavygas=1000000 pwheavyidle=1'),                       # dedicated threads for heavy transactions
    ('A02', ' pwheavyfirst=4'),                                                    # heavy transactions recovered and dispatched first
    ('A03', _K_REUSE),                                                             # reuse of the prewarm results
    ('A04', ' tx=1 code=1 readers=8 rdstop=1 cnt=1 pwmin=32'),                     # plans at transaction arrival, account and code reads
    ('A05', ' pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2'),        # plans at call start
    ('A06', _K_VN),                                                                # speculative pass of heavy transactions
    ('A07', ' pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1'),   # extrapolation: storage slots
    ('A08', ' pwlxacct=1'),                                                        # extrapolation: account reads
    ('A09', ' pwlxnoself=1'),                                                      # extrapolation: keys issued without the job's own reads
    ('A10', ' pwlxrd=8 pwlxrdacct=16'),                                            # extrapolation: readers added on demand
    ('A11', ' zklearn=1 zkpre=4'),                                                 # BN254 multiplications computed ahead
]


def _a_add(base, add):
    keys = {t.split('=')[0] for t in add.split()}
    return ' '.join([t for t in base.split() if t.split('=')[0] not in keys and t != 'srdiag=1'] + add.split() + ['srdiag=1'])


assert 'A00' not in CONFIGS and all(k not in CONFIGS for k, _ in _A_STEPS)
CONFIGS['A00'] = CONFIGS['Z-S']
_prev = 'A00'
for _k, _add in _A_STEPS:
    CONFIGS[_k] = _a_add(CONFIGS[_prev], _add)
    assert set(CONFIGS[_k].split()) - set(CONFIGS[_prev].split()) == set(_add.split()), _k
    _prev = _k
A_CFGS = ['A00'] + [k for k, _ in _A_STEPS]
assert sorted(CONFIGS['A10'].split()) == sorted(CONFIGS['Z-F'].split()), 'A10 must be EXP-185 C-FA plus glv'
assert sorted(CONFIGS['A11'].split()) == sorted(CONFIGS['Z-FZ4'].split()), 'A11 must be Z-FZ4'
# EXP-194 (README section 2): the txpool-prewarm increment of the current EAP
assert not any(k.startswith('T-') for k in CONFIGS)
CONFIGS['T-U'] = CONFIGS['A00']
CONFIGS['T-UR'] = CONFIGS['A00'] + ' tpw=1'
CONFIGS['T-F'] = CONFIGS['A10']
CONFIGS['T-FR'] = CONFIGS['A10'] + ' tpw=1'
CONFIGS['T-FR1'] = CONFIGS['T-FR'].replace(' reuse=2 reusechk=16 reusefast=1', ' reuse=1 reusefast=1')
assert CONFIGS['T-U'] == 'prewarm=1 insp=0 cs=0 tx=0 code=0 glv=1 srdiag=1'
assert sorted(CONFIGS['T-F'].split()) == sorted(_C_FA185.split() + ['glv=1'])
assert all(' glv=1' in CONFIGS[k] and 'zkpre' not in CONFIGS[k] and 'zklearn' not in CONFIGS[k] for k in ('T-U', 'T-UR', 'T-F', 'T-FR', 'T-FR1'))
# EXP-195 (Master 10-29): the block interval. T-UL / T-FL are T-U / T-F with a longer wait before newPayload, set per
# configuration by LEAD_BY_CFG (e.g. "T-UL=12 T-FL=12"; every other block waits LEAD); T-F1 is T-F in the reuse check
# mode for the pre-check (T-FR1 without tpw)
CONFIGS['T-UL'] = CONFIGS['T-U']
CONFIGS['T-FL'] = CONFIGS['T-F']
CONFIGS['T-UM'] = CONFIGS['T-U']
CONFIGS['T-FM'] = CONFIGS['T-F']
CONFIGS['T-F1'] = CONFIGS['T-F'].replace(' reuse=2 reusechk=16 reusefast=1', ' reuse=1 reusefast=1')
assert ' reuse=1 ' in CONFIGS['T-F1'] + ' ' and 'reusechk' not in CONFIGS['T-F1'] and 'tpw' not in CONFIGS['T-F1']
assert 'tpw' not in CONFIGS['T-U'] + CONFIGS['T-F'] and ' reuse=1 ' in CONFIGS['T-FR1'] + ' ' and 'reusechk' not in CONFIGS['T-FR1']
assert all(' glv=1' in CONFIGS[k] for k in A_CFGS)
# EXP-193: end of the configurations
PERF = os.environ.get('PERF', '0') == '1'
JIT_SWITCH = os.environ.get('JIT_SWITCH', '0') == '1'   # EXP-175 option (b)
PERF_PROC = []


def perf_start(pid, out_dir, label):
    """EXP-159: flat cpu-clock profile of the node process (threads it creates later are followed), on an efficiency core."""
    if PERF and not PERF_PROC:
        err = open(os.path.join(out_dir, f'{label}.perf.log'), 'w')
        PERF_PROC.append(subprocess.Popen(['taskset', '-c', '15', 'perf', 'record', '-k', 'CLOCK_MONOTONIC', '-e', 'cpu-clock', '-F', '499', '-e', 'major-faults/period=1/', '-d', '-p', str(pid),
                                           '-o', os.path.join(out_dir, f'{label}.perf.data')], stdout=err, stderr=err))


def perf_stop():
    while PERF_PROC:
        p = PERF_PROC.pop()
        try:
            p.send_signal(signal.SIGINT); p.wait(timeout=120)
        except Exception:
            p.kill()
FEED_T = float(os.environ.get('FEED_T', '2.0')); FEED_T2 = float(os.environ.get('FEED_T2', '0.5'))
FEED_ALL = os.environ.get('FEED_ALL', '1') == '1'   # EXP-194: 0 = only tpw=1 blocks are fed (EXP-148); 1 = every block (EXP-152)
FEED_PLAN = {}
if os.environ.get('FEED_PLAN'):
    import csv as _csv
    for _r in _csv.DictReader(open(os.environ['FEED_PLAN'])):
        FEED_PLAN.setdefault(int(_r['block']), []).append((int(_r['tx']), int(_r['delay_ms'])))
# EXP-199 (X-020, README section 6): EAP's own prewarm mechanism (eap-x199). Every configuration adds iqc=1: the execution
# thread records the storage keys it looks up (one locked insert per lookup, the same in every configuration) and the
# readers' block-end issue counts are logged.
_D_IQ = ' iqc=1'
_D_EW = ' ew=12 ewded=4 ewgas=1000000'
CONFIGS['D-N0'] = 'prewarm=0 insp=0 cs=0 tx=0 code=0 glv=1' + _D_IQ + ' srdiag=1'                      # no prefetch
# plans only, no EVM: transaction-arrival plans and their call records on the readers (version-2 library, depth 2; ctsl=1:
# storage reads in call targets, e.g. proxy implementation slots, read back by the readers); without prewarm threads the
# call counts do not grow, so pwmin=0 (plans of every contract usable)
CONFIGS['D-NP'] = 'prewarm=0 insp=0 cs=0 glv=1 tx=1 code=1 readers=8 rdstop=1 txdec=1 cttx=1 ctd=2 ctsl=1 pwmin=0' + _D_IQ + ' srdiag=1'
CONFIGS['D-R'] = CONFIGS['A00'].replace(' srdiag=1', _D_IQ + ' srdiag=1')                             # reth prewarm
CONFIGS['D-RE'] = CONFIGS['A10'].replace(' srdiag=1', _D_IQ + ' srdiag=1')                            # reth prewarm + full EAP
# own prewarm only (round 1): the mechanism with its parts that need no access plan (block-write layer, core reservation,
# in-flight reads joined by the execution thread)
_D_NAT = ' ewov=1 ewcore=1 ewinf=1'
CONFIGS['D-W'] = CONFIGS['A00'].replace(' srdiag=1', _D_EW + ' pwheavyfirst=4' + _K_REUSE + _D_NAT + _D_IQ + ' srdiag=1')
CONFIGS['D-WE'] = CONFIGS['D-RE'].replace(' pwheavy=4 pwheavygas=1000000 pwheavyidle=1', _D_EW)        # own prewarm + full EAP
CONFIGS['D-WEG'] = CONFIGS['D-WE'].replace(' srdiag=1', _D_NAT + ' srdiag=1')                  # + the plan-free native parts (generic)
CONFIGS['D-WEX'] = CONFIGS['D-WEG'].replace(' srdiag=1', ' ewprio=4 srdiag=1')                  # + the plan-predicted order (plan-native)
CONFIGS['D-WEX1'] = CONFIGS['D-WEX'].replace(_K_REUSE, ' reuse=1 reusefast=1')                       # pre-check: reuse check mode
assert sorted(CONFIGS['D-RE'].split()) == sorted((CONFIGS['A10'] + _D_IQ).split())
assert 'pwheavy=' not in CONFIGS['D-WE'] and ' ew=12 ' in CONFIGS['D-WE'] and ' pwheavyfirst=4 ' in CONFIGS['D-WE']
assert set(CONFIGS['D-WE'].split()) - set(CONFIGS['D-RE'].split()) == set(_D_EW.split())
assert set(CONFIGS['D-WEX'].split()) - set(CONFIGS['D-WE'].split()) == {'ewov=1', 'ewcore=1', 'ewinf=1', 'ewprio=4'}
assert set(CONFIGS['D-WEX'].split()) - set(CONFIGS['D-WEG'].split()) == {'ewprio=4'}
assert set(_D_NAT.split()) <= set(CONFIGS['D-W'].split()) and 'ewprio' not in CONFIGS['D-W'] and ' tx=0 ' in CONFIGS['D-W']
assert ' reuse=1 ' in CONFIGS['D-WEX1'] and 'reusechk' not in CONFIGS['D-WEX1']
# upstream-style controls for a second development run (Master 10-30, X-022 docs/related_work_20261030.md): the value-
# speculative pass replaced by Nethermind-style storage discovery (constant placeholder 1, then every byte 0x01; hand-over
# after 24 backend slot reads or a gas limit above 10,000,000; at most 6 rounds); the pass with the zero answer instead of
# the read site's recent value; heavy transactions by gas limit (geth PR #35404)
_D_ND = ' sd=10000000 sdr=6 sds=24 sdp2=1'
CONFIGS['D-WEN'] = CONFIGS['D-WE'].replace(_K_VN, '').replace(' srdiag=1', _D_ND + ' srdiag=1')
CONFIGS['D-WE0'] = CONFIGS['D-WE'].replace(' pwnbval=1 ', ' pwnbval=0 ')
CONFIGS['D-WES'] = CONFIGS['D-WE'].replace(' srdiag=1', ' ewsort=1 srdiag=1')
assert _K_VN in CONFIGS['D-WE'] and 'pwnb' not in CONFIGS['D-WEN'] and set(_D_ND.split()) <= set(CONFIGS['D-WEN'].split())
assert set(CONFIGS['D-WE0'].split()) ^ set(CONFIGS['D-WE'].split()) == {'pwnbval=0', 'pwnbval=1'}
assert set(CONFIGS['D-WES'].split()) - set(CONFIGS['D-WE'].split()) == {'ewsort=1'}
assert all(CONFIGS[k].endswith(' srdiag=1') and _D_IQ + ' ' in CONFIGS[k] and ' glv=1' in CONFIGS[k] for k in ('D-N0', 'D-NP', 'D-R', 'D-RE', 'D-W', 'D-WE', 'D-WEX'))
# EXP-199 rounds 2-3 (README section 6, candidates of the second development run, binary eap-x199c, library plans_v3x):
# detect-then-redo; call records with loop indices, followed as EXP-201 B1b plus the spread over the readers; plans at the
# speculative pass's inner call starts; and the same plan parts on reth's prewarm (D-REA), so that "ours + EAP" and
# "reth + EAP" carry the same EAP
_D_CT = ' pwct=1 ctr=4 cttx=1 ctsl=1 ctpay=1 ctfan=16 ctbudget=3000 ctspread=16'
CONFIGS['D-WEXR'] = CONFIGS['D-WEX'].replace(' srdiag=1', ' ewredo=1 srdiag=1')
CONFIGS['D-WEXC'] = CONFIGS['D-WEX'].replace(' srdiag=1', _D_CT + ' srdiag=1')
CONFIGS['D-WEXN'] = CONFIGS['D-WEX'].replace(' srdiag=1', ' nbpl=1 srdiag=1')
CONFIGS['D-WEXA'] = CONFIGS['D-WEX'].replace(' srdiag=1', ' ewredo=1' + _D_CT + ' nbpl=1 srdiag=1')
CONFIGS['D-REA'] = CONFIGS['D-RE'].replace(' srdiag=1', _D_CT + ' nbpl=1 srdiag=1')
CONFIGS['D-WEXA1'] = CONFIGS['D-WEXA'].replace(_K_REUSE, ' reuse=1 reusefast=1')                    # pre-check: reuse check mode
# EXP-199 round 3 (README section 10): the fixed thresholds replaced by plan and runtime quantities (all eight ewbud bits);
# the replaced parameters stay in the line, the code no longer uses them under ewbud
CONFIGS['D-WEXB'] = CONFIGS['D-WEXA'].replace(' srdiag=1', ' ewbud=255 srdiag=1')
CONFIGS['D-WEXB1'] = CONFIGS['D-WEXB'].replace(_K_REUSE, ' reuse=1 reusefast=1')                    # pre-check: reuse check mode
assert set(CONFIGS['D-WEXB'].split()) - set(CONFIGS['D-WEXA'].split()) == {'ewbud=255'}
# the kept parameter without a recorded basis (README section 10.2, Master 10-30): ctr=0, the follow jobs on the block's readers
CONFIGS['D-WEXB0'] = CONFIGS['D-WEXB'].replace(' ctr=4 ', ' ctr=0 ')
assert set(CONFIGS['D-WEXB0'].split()) ^ set(CONFIGS['D-WEXB'].split()) == {'ctr=0', 'ctr=4'}
# second development run (README section 6.2): D-WEXA without one of its three new parts (leave one out)
CONFIGS['D-WEXAnR'] = CONFIGS['D-WEXA'].replace(' ewredo=1', '')                     # without detect-then-redo
CONFIGS['D-WEXAnC'] = CONFIGS['D-WEXA'].replace(_D_CT, '')                            # without following call records (version-3 library)
CONFIGS['D-WEXAnN'] = CONFIGS['D-WEXA'].replace(' nbpl=1', '')                        # without plans at the speculative pass's call starts
assert set(CONFIGS['D-WEXA'].split()) - set(CONFIGS['D-WEXAnR'].split()) == {'ewredo=1'} and set(CONFIGS['D-WEXAnR'].split()) <= set(CONFIGS['D-WEXA'].split())
assert set(CONFIGS['D-WEXA'].split()) - set(CONFIGS['D-WEXAnC'].split()) == set(_D_CT.split()) and set(CONFIGS['D-WEXAnC'].split()) <= set(CONFIGS['D-WEXA'].split())
assert set(CONFIGS['D-WEXA'].split()) - set(CONFIGS['D-WEXAnN'].split()) == {'nbpl=1'} and set(CONFIGS['D-WEXAnN'].split()) <= set(CONFIGS['D-WEXA'].split())
# README section 10.4: D-WEXB with the remaining parameters derived (ewbud bits 256, 1024, 2048: workers from the cores,
# redo until arrival, call records while a level issues new keys; bit 512, idle-class helpers, left out after the review
# of c3bbbb0) and set to their derived values (ctr=0: follow jobs on the block's readers; pwlxn=3: two observations fit a
# stride, the third verifies it)
CONFIGS['D-WEXBD'] = CONFIGS['D-WEXB'].replace(' ewbud=255 ', ' ewbud=3583 ').replace(' ctr=4 ', ' ctr=0 ').replace(' pwlxn=4 ', ' pwlxn=3 ')
assert 3583 == 4095 & ~512
assert set(CONFIGS['D-WEXBD'].split()) ^ set(CONFIGS['D-WEXB'].split()) == {'ewbud=3583', 'ewbud=255', 'ctr=0', 'ctr=4', 'pwlxn=3', 'pwlxn=4'}
# README section 6.3 (after the first comparison, Master 10-31): why D-WEG loses to D-RE, one change each, against D-RE in
# the same run; and a fair pair of prewarms alone (D-RW = A03: reth's prewarm with the dedicated threads, the heavy-first
# recovery and the reuse that D-W also has)
CONFIGS['D-WEGc0'] = CONFIGS['D-WEG'].replace(' ewcore=1', '')                        # the core left to the executor: off
CONFIGS['D-WEGsp'] = CONFIGS['D-WEG'].replace(' srdiag=1', ' ewsplit=1 srdiag=1')    # reth's division of the workers
CONFIGS['D-WEGsl'] = CONFIGS['D-WEG'].replace(' srdiag=1', ' ewbud=1 srdiag=1')      # slack order (ewbud bit 1)
CONFIGS['D-RW'] = CONFIGS['A03'].replace(' srdiag=1', _D_IQ + ' srdiag=1')           # reth prewarm + dedicated threads + heavy-first + reuse
assert set(CONFIGS['D-WEG'].split()) - set(CONFIGS['D-WEGc0'].split()) == {'ewcore=1'} and set(CONFIGS['D-WEGc0'].split()) <= set(CONFIGS['D-WEG'].split())
assert set(CONFIGS['D-WEGsp'].split()) - set(CONFIGS['D-WEG'].split()) == {'ewsplit=1'}
assert set(CONFIGS['D-WEGsl'].split()) - set(CONFIGS['D-WEG'].split()) == {'ewbud=1'}
assert all(k in CONFIGS['D-RW'] for k in (' pwheavy=4 ', ' pwheavyfirst=4 ', ' reuse=2 ', ' iqc=1 ')) and ' ew=' not in CONFIGS['D-RW'] and ' tx=0 ' in CONFIGS['D-RW']
assert set(CONFIGS['D-W'].split()) - set(CONFIGS['D-RW'].split()) == {'ew=12', 'ewded=4', 'ewgas=1000000', 'ewov=1', 'ewcore=1', 'ewinf=1'}
# README section 6.4: candidates of the short rounds after the second comparison (each one or two changes on D-WEG)
CONFIGS['D-WEGc0sp'] = CONFIGS['D-WEGc0'].replace(' srdiag=1', ' ewsplit=1 srdiag=1')   # no core left to the executor + reth's division
CONFIGS['D-WEGc0sl'] = CONFIGS['D-WEGc0'].replace(' srdiag=1', ' ewbud=1 srdiag=1')     # no core left + slack order
CONFIGS['D-WEGc0t'] = CONFIGS['D-WEGc0'].replace(' srdiag=1', ' ewbud=256 srdiag=1')    # no core left + workers = cores - 1
CONFIGS['D-WEGnov'] = CONFIGS['D-WEG'].replace(' ewov=1', '')                           # without the block write overlay
CONFIGS['D-WEGninf'] = CONFIGS['D-WEG'].replace(' ewinf=1', '')                         # without the in-flight join
assert set(CONFIGS['D-WEGc0sp'].split()) ^ set(CONFIGS['D-WEG'].split()) == {'ewcore=1', 'ewsplit=1'}
assert set(CONFIGS['D-WEGc0sl'].split()) ^ set(CONFIGS['D-WEG'].split()) == {'ewcore=1', 'ewbud=1'}
assert set(CONFIGS['D-WEGc0t'].split()) ^ set(CONFIGS['D-WEG'].split()) == {'ewcore=1', 'ewbud=256'}
assert set(CONFIGS['D-WEG'].split()) - set(CONFIGS['D-WEGnov'].split()) == {'ewov=1'} and set(CONFIGS['D-WEG'].split()) - set(CONFIGS['D-WEGninf'].split()) == {'ewinf=1'}
assert all(k not in CONFIGS['D-WEX'] for k in ('pwct', 'cttx', 'ctr=', 'ctsl', 'ctspread', 'nbpl', 'ewredo')) and ' pwnb=1 ' in CONFIGS['D-WEX'] + ' ' and ' pwnb=1 ' in CONFIGS['D-RE'] + ' '
assert set(CONFIGS['D-WEXA'].split()) - set(CONFIGS['D-WEX'].split()) == set((' ewredo=1' + _D_CT + ' nbpl=1').split())
assert set(CONFIGS['D-REA'].split()) - set(CONFIGS['D-RE'].split()) == set((_D_CT + ' nbpl=1').split())
assert set(CONFIGS['D-WEXA'].split()) - set(CONFIGS['D-REA'].split()) == set(CONFIGS['D-WEX'].split()) - set(CONFIGS['D-RE'].split()) | {'ewredo=1'}
# README section 6.4, round g (Master 10-31: D-RE, the best of round f, one change): the block write overlay and the
# in-flight join both left out (the non-read time of the prewarm threads, README 6.4), and the prewarm on compiled code
# (pwjitreal: the inspected workers run compiled frames when the node runs with --jit and pwjit=1, the default;
# pwjitpeek: their lookups do not change what gets compiled; pwjitkec: KECCAK256 inputs of compiled frames reach the
# extrapolation). reusebal is off under pwjitreal (eap.rs set_mode), so the two are not combined.
CONFIGS['D-WEGnn'] = CONFIGS['D-WEGnov'].replace(' ewinf=1', '')
CONFIGS['D-WEGc0nn'] = CONFIGS['D-WEGc0'].replace(' ewov=1', '').replace(' ewinf=1', '')
_D_JIT = ' pwjitreal=1 pwjitpeek=1 pwjitkec=1'
CONFIGS['D-WEGjit'] = CONFIGS['D-WEG'].replace(' srdiag=1', _D_JIT + ' srdiag=1')
CONFIGS['D-WEGc0jit'] = CONFIGS['D-WEGc0'].replace(' srdiag=1', _D_JIT + ' srdiag=1')
assert set(CONFIGS['D-WEG'].split()) - set(CONFIGS['D-WEGnn'].split()) == {'ewov=1', 'ewinf=1'} and set(CONFIGS['D-WEGnn'].split()) <= set(CONFIGS['D-WEG'].split())
assert set(CONFIGS['D-WEGc0'].split()) - set(CONFIGS['D-WEGc0nn'].split()) == {'ewov=1', 'ewinf=1'} and set(CONFIGS['D-WEGc0nn'].split()) <= set(CONFIGS['D-WEGc0'].split())
assert set(CONFIGS['D-WEGjit'].split()) - set(CONFIGS['D-WEG'].split()) == set(_D_JIT.split()) and set(CONFIGS['D-WEG'].split()) <= set(CONFIGS['D-WEGjit'].split())
assert set(CONFIGS['D-WEGc0jit'].split()) - set(CONFIGS['D-WEGc0'].split()) == set(_D_JIT.split()) and set(CONFIGS['D-WEGc0'].split()) <= set(CONFIGS['D-WEGc0jit'].split())
assert all(' pwjit=0' not in CONFIGS[k] and ' pwlx=1' in CONFIGS[k] and ' pwlxc2=1' in CONFIGS[k] for k in ('D-WEGjit', 'D-WEGc0jit'))
# README section 6.4, later rounds: following the version-3 call records (X-023's EXP-212; PLANS_DIR = EXP-201 plans_v3x
# for every configuration of that round) and the persistent threads (ewpool, from the build after eap-x199c 1da4235)
for _b in ('D-WEG', 'D-WEGc0'):
    # EXP-201 B1's call-record following exactly (EXP-201 scripts/run_xl.py line 550: pwct=1 ctr=4 cttx=1 ctsl=1; ctd=2 is
    # in the base), Master 10-31; the round-3 variant with ctpay, ctfan, ctbudget and ctspread kept as *ctx
    CONFIGS[_b + 'ct'] = CONFIGS[_b].replace(' srdiag=1', ' pwct=1 ctr=4 cttx=1 ctsl=1 srdiag=1')
    CONFIGS[_b + 'ctx'] = CONFIGS[_b].replace(' srdiag=1', _D_CT + ' srdiag=1')
    CONFIGS[_b + 'pool'] = CONFIGS[_b].replace(' srdiag=1', ' ewpool=1 srdiag=1')
    assert set(CONFIGS[_b + 'ct'].split()) ^ set(CONFIGS[_b].split()) == {'pwct=1', 'ctr=4', 'cttx=1', 'ctsl=1'} and ' ctd=2 ' in CONFIGS[_b] + ' '
    assert set(CONFIGS[_b + 'ctx'].split()) - set(CONFIGS[_b].split()) == set(_D_CT.split()) and set(CONFIGS[_b].split()) <= set(CONFIGS[_b + 'ctx'].split())
    assert set(CONFIGS[_b + 'pool'].split()) ^ set(CONFIGS[_b].split()) == {'ewpool=1'}
# EXP-210's lock-free replacements (ewlf bits 1 block writes, 2 in-flight table, 16 mode snapshot; from the build with
# eap-x210 bab7d1c): all three, and the block writes alone; bit 1 needs ewov and bit 2 ewinf, both in D-WEG
for _b in ('D-WEG', 'D-WEGc0'):
    CONFIGS[_b + 'lf'] = CONFIGS[_b].replace(' srdiag=1', ' ewlf=19 srdiag=1')
    CONFIGS[_b + 'lf1'] = CONFIGS[_b].replace(' srdiag=1', ' ewlf=1 srdiag=1')
    assert ' ewov=1' in CONFIGS[_b] and ' ewinf=1' in CONFIGS[_b]
    assert set(CONFIGS[_b + 'lf'].split()) ^ set(CONFIGS[_b].split()) == {'ewlf=19'}
# EXP-218 (from eap-x199c a9a7266): prewarm threads in SCHED_BATCH (pwbatch=1), the execution thread's time slice 100 us
# (exslice=100, EXP-218 README line 69); and reth's prewarm with EAP plus SCHED_BATCH
for _b in ('D-WEG', 'D-WEGc0'):
    CONFIGS[_b + 'b'] = CONFIGS[_b].replace(' srdiag=1', ' pwbatch=1 srdiag=1')
    CONFIGS[_b + 'xs'] = CONFIGS[_b].replace(' srdiag=1', ' exslice=100 srdiag=1')
    assert set(CONFIGS[_b + 'b'].split()) ^ set(CONFIGS[_b].split()) == {'pwbatch=1'}
    assert set(CONFIGS[_b + 'xs'].split()) ^ set(CONFIGS[_b].split()) == {'exslice=100'}
CONFIGS['D-REb'] = CONFIGS['D-RE'].replace(' srdiag=1', ' pwbatch=1 srdiag=1')
assert set(CONFIGS['D-REb'].split()) ^ set(CONFIGS['D-RE'].split()) == {'pwbatch=1'}
# README section 6.4, round i (after round h): pwbatch kept, the execution thread's time slice on top
CONFIGS['D-WEGbxs'] = CONFIGS['D-WEGb'].replace(' srdiag=1', ' exslice=100 srdiag=1')
assert set(CONFIGS['D-WEGbxs'].split()) ^ set(CONFIGS['D-WEGb'].split()) == {'exslice=100'}
# README section 6.4, round j (Master 10-31, the researcher asked for it): the prewarm on compiled code, on X = D-WEG or
# D-WEGb (pwjitreal: compiled frames on the inspected workers; pwjitpeek: their lookups do not change what is compiled;
# pwjitkec: KECCAK256 inputs of compiled frames reach the extrapolation)
_D_J = ' pwjitreal=1 pwjitpeek=1 pwjitkec=1'
CONFIGS['D-WEGj'] = CONFIGS['D-WEG'].replace(' srdiag=1', _D_J + ' srdiag=1')
CONFIGS['D-WEGbj'] = CONFIGS['D-WEGb'].replace(' srdiag=1', _D_J + ' srdiag=1')
assert CONFIGS['D-WEGj'] == CONFIGS['D-WEGjit']
assert set(CONFIGS['D-WEGbj'].split()) ^ set(CONFIGS['D-WEGb'].split()) == set(_D_J.split())
# round j if ewlf is kept in round i (Master 10-31): the compiled-code prewarm on X = D-WEGlf
CONFIGS['D-WEGlfj'] = CONFIGS['D-WEGlf'].replace(' srdiag=1', _D_J + ' srdiag=1')
assert set(CONFIGS['D-WEGlfj'].split()) ^ set(CONFIGS['D-WEGlf'].split()) == set(_D_J.split())
# after round j (Master 10-31): SCHED_BATCH for the EVM threads only, the readers stay SCHED_OTHER (pwbatch=2, from 60f8a93)
CONFIGS['D-WEGb2'] = CONFIGS['D-WEG'].replace(' srdiag=1', ' pwbatch=2 srdiag=1')
assert set(CONFIGS['D-WEGb2'].split()) ^ set(CONFIGS['D-WEG'].split()) == {'pwbatch=2'}
# round k (Master 10-31): the execution thread's time slice alone (exslice=100) on X = the best of rounds i and j
for _b in ('D-WEGlf', 'D-WEGj', 'D-WEGlfj'):
    CONFIGS[_b + 'xs'] = CONFIGS[_b].replace(' srdiag=1', ' exslice=100 srdiag=1')
    assert set(CONFIGS[_b + 'xs'].split()) ^ set(CONFIGS[_b].split()) == {'exslice=100'}
# round k (Master 10-31): EXP-201 B1's call-record following on X = the best of rounds i and j (PLANS_DIR = plans_v3x for the
# whole round)
for _b in ('D-WEGlf', 'D-WEGj', 'D-WEGlfj'):
    CONFIGS[_b + 'ct'] = CONFIGS[_b].replace(' srdiag=1', ' pwct=1 ctr=4 cttx=1 ctsl=1 srdiag=1')
    assert set(CONFIGS[_b + 'ct'].split()) ^ set(CONFIGS[_b].split()) == {'pwct=1', 'ctr=4', 'cttx=1', 'ctsl=1'}
# the deployment round (Master 10-31): plans for all code that ran (pwmin=0) on X, with the completed library plans_full
for _b in ('D-WEG', 'D-WEGlf', 'D-WEGj', 'D-WEGlfj'):
    assert ' pwmin=32 ' in CONFIGS[_b] + ' '
    CONFIGS[_b + 'p0'] = (CONFIGS[_b] + ' ').replace(' pwmin=32 ', ' pwmin=0 ').rstrip()
    assert set(CONFIGS[_b + 'p0'].split()) ^ set(CONFIGS[_b].split()) == {'pwmin=32', 'pwmin=0'}
# the core for the execution thread alone (excore=1, from eap-x199c 7823a2f on), on both sides (Master 11-01)
for _b in ('D-RE', 'D-WEG', 'D-WEGlf', 'D-WEGj', 'D-WEGlfj'):
    CONFIGS[_b + 'ec'] = CONFIGS[_b].replace(' srdiag=1', ' excore=1 srdiag=1')
    assert set(CONFIGS[_b + 'ec'].split()) ^ set(CONFIGS[_b].split()) == {'excore=1'}
# the bundle of small changes (Master 11-01, round m): persistent threads, the node-level
# changes (system-call slots for the next block, large-value read-ahead, victim code cache; the researcher 01:56: ours, they
# count in the method), and with interpreted prewarm the balance-only reuse (reusebal is off under pwjitreal, eap.rs set_mode)
for _b in ('D-WEG', 'D-WEGlf', 'D-WEGj', 'D-WEGlfj', 'D-WEGec', 'D-WEGlfec', 'D-WEGjec', 'D-WEGlfjec'):
    _add = ' ewpool=1 sysn=1 bigra=1 ccv=1 rdpeek=1 exslice=100 fpimp=1' + ('' if ' pwjitreal=1' in CONFIGS[_b] else ' reusebal=1')   # rdpeek, exslice, fpimp: round m
    CONFIGS[_b + 'pk'] = CONFIGS[_b].replace(' srdiag=1', _add + ' srdiag=1')
    assert set(CONFIGS[_b + 'pk'].split()) ^ set(CONFIGS[_b].split()) == set(_add.split())
    assert ' reuse=2 ' in CONFIGS[_b] + ' '
# round m (Master 11-01, after rdpeek): the readers' cache filter is in every pk above; D-REpk = D-RE with the parts that
# apply to both sides (sysn, bigra, ccv, rdpeek), so that D-WEGpk / D-REpk compares the prewarms with these on both sides
assert ' srdiag=1' in CONFIGS['D-RE'] and not any(t in CONFIGS['D-RE'].split() for t in ('sysn=1', 'bigra=1', 'ccv=1', 'rdpeek=1', 'ewpool=1'))
# exslice=100 too (Master 11-01 after round k: D-WEGxs/D-WEG 0.983, interval without 1, below the 0.98 reference; a
# scheduling parameter for both sides, merged into the bundle with its one parameter, the 100 us slice)
# fpimp=1 too (Master 11-01 after EXP-227: the plan solver's EXP-005 improvement, every instantiation on both sides)
CONFIGS['D-REpk'] = CONFIGS['D-RE'].replace(' srdiag=1', ' sysn=1 bigra=1 ccv=1 rdpeek=1 exslice=100 fpimp=1 srdiag=1')
assert set(CONFIGS['D-REpk'].split()) ^ set(CONFIGS['D-RE'].split()) == {'sysn=1', 'bigra=1', 'ccv=1', 'rdpeek=1', 'exslice=100', 'fpimp=1'}
CONFIGS['D-REjpk'] = CONFIGS['D-REpk'].replace(' srdiag=1', _D_J + ' srdiag=1')   # D-REpk + compiled-code prewarm (apply_fp.py)
assert set(CONFIGS['D-REjpk'].split()) ^ set(CONFIGS['D-REpk'].split()) == set(_D_J.split()) == {'pwjitreal=1', 'pwjitpeek=1', 'pwjitkec=1'}
assert 'rdpeek=1' in CONFIGS['D-WEGpk'].split() and set(CONFIGS['D-WEGpk'].split()) ^ set(CONFIGS['D-WEG'].split()) == {'ewpool=1', 'sysn=1', 'bigra=1', 'ccv=1', 'rdpeek=1', 'exslice=100', 'fpimp=1', 'reusebal=1'}
# the access plans fully on (Master 11-01, round o; EXP-222 sec 6: the plan side's bound 7.58-8.70%, the switches alone
# 6.90-8.18%): pwmin=0 and the call-record following of B1 (pwct=1 ctr=4 cttx=1 ctsl=1) four levels deep (ctd=4, the
# parser's cap, eap.rs Mode::parse)
for _b in ('D-WEG', 'D-WEGlf', 'D-WEGj', 'D-WEGlfj', 'D-WEGec', 'D-WEGlfec', 'D-WEGjec', 'D-WEGlfjec'):
    assert ' pwmin=32 ' in CONFIGS[_b] + ' ' and ' ctd=2 ' in CONFIGS[_b] + ' '
    _c = (CONFIGS[_b] + ' ').replace(' pwmin=32 ', ' pwmin=0 ').replace(' ctd=2 ', ' ctd=4 ').rstrip()
    CONFIGS[_b + 'pa'] = _c.replace(' srdiag=1', ' pwct=1 ctr=4 cttx=1 ctsl=1 srdiag=1')
    assert set(CONFIGS[_b + 'pa'].split()) ^ set(CONFIGS[_b].split()) == {'pwmin=32', 'pwmin=0', 'ctd=2', 'ctd=4', 'pwct=1', 'ctr=4', 'cttx=1', 'ctsl=1'}
# round o (Master 11-01; X-021 EXP-221 section 10: on top of the plans fully on, pwk=0 adds at least 1.84 points to the
# merged bound): pa with the call-start gate off
for _b in ('D-WEG', 'D-WEGlf', 'D-WEGj', 'D-WEGlfj', 'D-WEGec', 'D-WEGlfec', 'D-WEGjec', 'D-WEGlfjec'):
    assert ' pwk=8 ' in CONFIGS[_b + 'pa'] + ' '
    CONFIGS[_b + 'pa0'] = (CONFIGS[_b + 'pa'] + ' ').replace(' pwk=8 ', ' pwk=0 ').rstrip()
    assert set(CONFIGS[_b + 'pa0'].split()) ^ set(CONFIGS[_b + 'pa'].split()) == {'pwk=8', 'pwk=0'}
# round k (Master 11-01): the execution thread's time slice (exslice=100) on the plans fully on, with and without the
# call-start gate
for _b in ('D-WEGpa', 'D-WEGpa0', 'D-WEGlfpa', 'D-WEGlfpa0', 'D-WEGjpa', 'D-WEGjpa0', 'D-WEGlfjpa', 'D-WEGlfjpa0'):
    CONFIGS[_b + 'xs'] = CONFIGS[_b].replace(' srdiag=1', ' exslice=100 srdiag=1')
    assert set(CONFIGS[_b + 'xs'].split()) ^ set(CONFIGS[_b].split()) == {'exslice=100'}
# round q (Master 11-01, after X-023 EXP-226): the access plans with a frame's repeated calls followed once (ctdedup=1) and the
# following kept at depth 2, on X = D-WEG
assert ' pwmin=32 ' in CONFIGS['D-WEG'] + ' ' and ' ctd=2 ' in CONFIGS['D-WEG'] + ' '
CONFIGS['D-WEGpd'] = (CONFIGS['D-WEG'] + ' ').replace(' pwmin=32 ', ' pwmin=0 ').rstrip().replace(
    ' srdiag=1', ' pwct=1 ctr=4 cttx=1 ctsl=1 ctdedup=1 srdiag=1')
assert set(CONFIGS['D-WEGpd'].split()) ^ set(CONFIGS['D-WEG'].split()) == {'pwmin=32', 'pwmin=0', 'pwct=1', 'ctr=4', 'cttx=1', 'ctsl=1', 'ctdedup=1'}
assert set(CONFIGS['D-WEGpd'].split()) ^ set(CONFIGS['D-WEGpa'].split()) == {'ctd=4', 'ctd=2', 'ctdedup=1'}
# round p (Master 11-01): <name>c0 = the pk configuration without the execution thread's reserved core (ewcore=1); before the
# bud loop below, so <name>c0bud exists too
for _k in [k for k in CONFIGS if k.endswith('pk') and 'ewcore=1' in CONFIGS[k].split()]:
    CONFIGS[_k + 'c0'] = ' '.join(t for t in CONFIGS[_k].split() if t != 'ewcore=1')
    assert set(CONFIGS[_k].split()) - set(CONFIGS[_k + 'c0'].split()) == {'ewcore=1'} and len(CONFIGS[_k + 'c0'].split()) == len(CONFIGS[_k].split()) - 1
# rounds p and w (Master 11-01): ewbud=256 on every configuration with the own prewarm's workers: <name>bud (workers = the execution
# thread's available cores less one, read every block)
for _k in [k for k in CONFIGS if not k.endswith('bud') and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())
           and not any(t.startswith('ewbud=') for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'bud'] = ' '.join(_t[:_i] + ['ewbud=256'] + _t[_i:])
    assert set(CONFIGS[_k + 'bud'].split()) ^ set(CONFIGS[_k].split()) == {'ewbud=256'}
# round rt (Master 11-01, after round p): <name>rt = a pk configuration with the execution thread at SCHED_FIFO priority 1
# (exrt=1; needs NODE_RTPRIO=1 for the node and a binary from eap-x199c with exrt)
for _k in [k for k in CONFIGS if k.endswith('pk')]:
    _t = CONFIGS[_k].split()
    assert not any(t.startswith('exrt=') for t in _t) and _k + 'rt' not in CONFIGS, _k
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'rt'] = ' '.join(_t[:_i] + ['exrt=1'] + _t[_i:])
    assert set(CONFIGS[_k + 'rt'].split()) ^ set(_t) == {'exrt=1'}
# round w (Master 11-01, 15:42): <name>pa = a pk configuration of the own prewarm with the access plans fully on and k
_PA_W = ['pwct=1', 'ctr=4', 'cttx=1', 'ctsl=1', 'ctdedup=1', 'satcls=1']
for _k in [k for k in CONFIGS if k.endswith('pk') and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    assert 'pwmin=32' in _t and 'ctd=2' in _t and not any(t.split('=')[0] in ('pwct', 'ctr', 'cttx', 'ctsl', 'ctdedup', 'satcls') for t in _t), _k
    assert _k + 'pa' not in CONFIGS, _k + 'pa'
    _t = ['pwmin=0' if t == 'pwmin=32' else t for t in _t]
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'pa'] = ' '.join(_t[:_i] + _PA_W + _t[_i:])
    assert set(CONFIGS[_k + 'pa'].split()) ^ set(CONFIGS[_k].split()) == set(_PA_W) | {'pwmin=0', 'pwmin=32'}
# round w after round t (Master 11-01 21:4x): <name>rtpa = an rt configuration of the own prewarm with the access plans fully on and k
for _k in [k for k in CONFIGS if k.endswith('pkrt') and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    assert 'pwmin=32' in _t and _k + 'pa' not in CONFIGS, _k
    _t = ['pwmin=0' if t == 'pwmin=32' else t for t in _t]
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'pa'] = ' '.join(_t[:_i] + _PA_W + _t[_i:])
    assert set(CONFIGS[_k + 'pa'].split()) ^ set(CONFIGS[_k[:-2] + 'pa'].split()) == {'exrt=1'}, _k
# round after w (Master 11-01 21:5x): <name>sr = an rt configuration with the state-root threads at SCHED_FIFO priority 1 from the end of execution to the root
for _k in [k for k in CONFIGS if k.endswith('pkrt') or k.endswith('pkrtpa')]:
    _t = CONFIGS[_k].split()
    assert not any(t.startswith('srboost=') for t in _t) and _k + 'sr' not in CONFIGS, _k
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'sr'] = ' '.join(_t[:_i] + ['srboost=1'] + _t[_i:])
    assert set(CONFIGS[_k + 'sr'].split()) ^ set(_t) == {'srboost=1'}, _k
# round v (Master 11-02): <name>cs = an rt configuration of the own prewarm with the call-start handover on the execution path (cs=1 cslag=1)
for _k in [k for k in CONFIGS if k.endswith('pkrt') and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    assert 'cs=0' in _t and not any(t.startswith('cslag=') for t in _t) and _k + 'cs' not in CONFIGS, _k
    _t = ['cs=1' if t == 'cs=0' else t for t in _t]
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'cs'] = ' '.join(_t[:_i] + ['cslag=1'] + _t[_i:])
    assert set(CONFIGS[_k + 'cs'].split()) ^ set(CONFIGS[_k].split()) == {'cs=0', 'cs=1', 'cslag=1'}, _k
# round after v (Master 11-02, X-026): <name>chk, <name>redo = an rt configuration of the own prewarm with the background reuse checks / detect then redo
for _k in [k for k in CONFIGS if k.endswith('pkrt') and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    assert {'reuse=2', 'ewov=1'} <= set(_t) and any(t.startswith('reusechk=') for t in _t), _k
    assert not any(t.startswith(('reusechkbg', 'ewredo')) for t in _t) and _k + 'chk' not in CONFIGS and _k + 'redo' not in CONFIGS, _k
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    for _s, _tok in (('chk', 'reusechkbg=1'), ('redo', 'ewredo=2')):
        CONFIGS[_k + _s] = ' '.join(_t[:_i] + [_tok] + _t[_i:])
        assert set(CONFIGS[_k + _s].split()) ^ set(_t) == {_tok}, _k
# round of ewnear (Master 11-02): <name>nr = an rt configuration of the own prewarm with the near workers at SCHED_FIFO 1 (ewnear=1)
for _k in [k for k in CONFIGS if k.endswith('pkrt') and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    assert not any(t.startswith('ewnear') for t in _t) and _k + 'nr' not in CONFIGS and _k + 'bal' not in CONFIGS, _k
    assert 'reuse=2' in _t, _k
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    # <name>bal only where reusebal is off: the interpreted pk configurations have it already, the compiled (j) ones left
    # it out because it was off under pwjitreal before EXP-233
    for _s, _tok in (('nr', 'ewnear=1'),) + ((('bal', 'reusebal=1'),) if 'reusebal=1' not in _t else ()):
        CONFIGS[_k + _s] = ' '.join(_t[:_i] + [_tok] + _t[_i:])
        assert set(CONFIGS[_k + _s].split()) ^ set(_t) == {_tok}, _k
# base after round x (Master 11-02): <name>nb = an rt configuration of the own prewarm with ewnear=1 and reusebal=1 (round x adopted both)
for _k in [k for k in CONFIGS if k.endswith('pkrt') and k + 'nr' in CONFIGS and k + 'bal' in CONFIGS]:
    _t = CONFIGS[_k].split()
    assert not any(t.startswith(('ewnear', 'reusebal')) for t in _t) and _k + 'nb' not in CONFIGS, _k
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'nb'] = ' '.join(_t[:_i] + ['ewnear=1', 'reusebal=1'] + _t[_i:])
    _n = set(CONFIGS[_k + 'nb'].split())
    assert _n ^ set(_t) == {'ewnear=1', 'reusebal=1'}, _k
    assert _n ^ set(CONFIGS[_k + 'nr'].split()) == {'reusebal=1'} and _n ^ set(CONFIGS[_k + 'bal'].split()) == {'ewnear=1'}, _k
# round of cdscan (Master 11-02, EXP-232): <name>sc63, <name>sc16 = an rt configuration of the own prewarm with the calldata-address prefetch
for _k in [k for k in CONFIGS if 'pkrt' in k and not k.endswith(('sc63', 'sc16')) and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    assert not any(t.startswith(('cdscan', 'cdaddr', 'cdst')) for t in _t) and any(t.startswith('readers=') and t != 'readers=0' for t in _t), _k
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    for _s, _tok in (('sc63', ['cdscan=63']), ('sc16', ['cdscan=63', 'cdscanmin=16'])):
        assert _k + _s not in CONFIGS, _k
        CONFIGS[_k + _s] = ' '.join(_t[:_i] + _tok + _t[_i:])
        assert set(CONFIGS[_k + _s].split()) ^ set(_t) == set(_tok), _k
# round of accflt (Master 11-02, EXP-232): <name>af = an rt configuration of the own prewarm with the filter of existing accounts
for _k in [k for k in CONFIGS if 'pkrt' in k and not k.endswith('af') and any(t.startswith('ew=') and t != 'ew=0' for t in CONFIGS[k].split())]:
    _t = CONFIGS[_k].split()
    assert not any(t.startswith('accflt') for t in _t) and _k + 'af' not in CONFIGS, _k
    _i = _t.index('srdiag=1') if 'srdiag=1' in _t else len(_t)
    CONFIGS[_k + 'af'] = ' '.join(_t[:_i] + ['accflt=1', 'accfltchk=1000'] + _t[_i:])
    assert set(CONFIGS[_k + 'af'].split()) ^ set(_t) == {'accflt=1', 'accfltchk=1000'}, _k
# final ablation trial (Master 11-02): AB1-AB8 (rows of the final ablation; groups from scripts/abl199_table.py)
_AB_GROUPS = {'base': ['prewarm=1', 'insp=0', 'cs=0', 'glv=1'], 'diag_off': ['iqc=1', 'cnt=1'], 'diag_keep': ['srdiag=1'], 'plan': ['tx=1', 'code=1', 'readers=8', 'rdstop=1', 'pwmin=32', 'pwcs=1', 'pwsync=1', 'pwstale=1', 'pwdedup=1', 'pwnodisc=1', 'pwk=8', 'ctd=2', 'pwnb=1', 'pwnbval=1', 'pwnbgas=5000000', 'pwnbhist=0', 'pwnbsep=1', 'pwnbbh=1', 'pwnbwait=0', 'pwnbearly=4', 'pwnbprio=1', 'pwnblevels=6', 'pwnbbudget=30000', 'pwnblvlwait=1000', 'pwnbnice=10', 'pwlx=1', 'pwlxn=4', 'pwlxmax=512', 'pwlxc2=1', 'txdec=1', 'pwlxbudget=1500', 'pwlxcnt=1', 'pwlxbin=1', 'c2rec=1', 'pwlxacct=1', 'pwlxnoself=1', 'pwlxrd=8', 'pwlxrdacct=16', 'pwjitkec=1', 'fpimp=1'], 'prewarm': ['ew=12', 'ewded=4', 'ewgas=1000000', 'pwheavyfirst=4', 'ewov=1', 'reuse=2', 'reusechk=16', 'reusefast=1', 'reusebal=1', 'pwjitreal=1', 'pwjitpeek=1'], 'sched': ['ewcore=1', 'ewpool=1', 'exslice=100', 'exrt=1', 'ewnear=1'], 'read': ['rdpeek=1', 'bigra=1', 'ccv=1', 'sysn=1', 'ewinf=1', 'accflt=1', 'accfltchk=1000']}
_AB_MODS = {'AB1': [], 'AB2': ['prewarm'], 'AB3': ['prewarm', 'sched'], 'AB4': ['prewarm', 'read', 'sched'], 'AB5': ['plan', 'prewarm', 'read', 'sched'], 'AB6': ['plan'], 'AB7': ['plan', 'prewarm', 'read'], 'AB8': ['plan', 'prewarm', 'sched']}
_AB_ROWS = {'AB1': 'prewarm=1 insp=0 cs=0 glv=1 tx=0 code=0 srdiag=1', 'AB2': 'prewarm=1 insp=0 cs=0 glv=1 tx=0 code=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=16 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 srdiag=1', 'AB3': 'prewarm=1 insp=0 cs=0 glv=1 tx=0 code=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=16 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=1 srdiag=1', 'AB4': 'prewarm=1 insp=0 cs=0 glv=1 tx=0 code=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=16 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=1 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 srdiag=1', 'AB5': 'prewarm=1 insp=0 cs=0 glv=1 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=16 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=1 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1', 'AB6': 'prewarm=1 insp=0 cs=0 glv=1 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 fpimp=1 srdiag=1', 'AB7': 'prewarm=1 insp=0 cs=0 glv=1 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=16 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1', 'AB8': 'prewarm=1 insp=0 cs=0 glv=1 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=16 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=1 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1'}
_AB_BASE = set(_AB_GROUPS['base'] + _AB_GROUPS['diag_keep'])
for _n, _line in _AB_ROWS.items():
    assert _n not in CONFIGS, _n
    CONFIGS[_n] = _line
    _want = set(_AB_BASE) | (set() if 'plan' in _AB_MODS[_n] else {'tx=0', 'code=0'})
    for _m in _AB_MODS[_n]:
        _want |= {t for t in _AB_GROUPS[_m] if not (t == 'pwjitkec=1' and 'prewarm' not in _AB_MODS[_n])}
    assert set(_line.split()) == _want, (_n, sorted(set(_line.split()) ^ _want))
assert set(CONFIGS['AB5'].split()) == set(CONFIGS['D-WEGjpkrtnbaf'].split()) - {'iqc=1', 'cnt=1'}
assert set(CONFIGS['AB1'].split()) == set(CONFIGS['D-R'].split()) - {'iqc=1'}
# final runs without GLV (researcher 11-02 12:26): ABkng = the ablation row ABk without glv=1
for _n in [f'AB{i}' for i in range(1, 9)]:
    _t = CONFIGS[_n].split()
    assert 'glv=1' in _t and _n + 'ng' not in CONFIGS, _n
    CONFIGS[_n + 'ng'] = ' '.join(t for t in _t if t != 'glv=1')
    assert set(CONFIGS[_n + 'ng'].split()) ^ set(_t) == {'glv=1'}, _n
    _AB_MODS[_n + 'ng'] = _AB_MODS[_n]
# apply_v290.py (reth 2.9.0 binaries, Master 11-02): the pre-check of 2.9.0 runs (PRE_CONFIG): AB5ng checking every reused transaction (reusechk=1)
CONFIGS['AB5ngchk'] = CONFIGS['AB5ng'].replace(' reusechk=16 ', ' reusechk=1 ')
assert set(CONFIGS['AB5ngchk'].split()) ^ set(CONFIGS['AB5ng'].split()) == {'reusechk=1', 'reusechk=16'}
# apply_threads250.py (EXP-250 / X-028): AB5ngT, AB5ng with Prologue's own thread counts doubled for the server's 28 logical cpus
_T250 = {'ew=12': 'ew=24', 'ewded=4': 'ewded=8', 'pwheavyfirst=4': 'pwheavyfirst=8', 'readers=8': 'readers=16', 'pwnbearly=4': 'pwnbearly=8'}
assert 'AB5ngT' not in CONFIGS and all(CONFIGS['AB5ng'].split().count(k) == 1 for k in _T250)
CONFIGS['AB5ngT'] = ' '.join(_T250.get(t, t) for t in CONFIGS['AB5ng'].split())
assert set(CONFIGS['AB5ngT'].split()) ^ set(CONFIGS['AB5ng'].split()) == set(_T250) | set(_T250.values())
# apply_ab0.py (main result, researcher 11-02 15:30): AB0ng = AB1ng with reth's transaction prewarming off (prewarm=0); no Prologue module
assert 'AB0ng' not in CONFIGS and 'AB0ng' not in _AB_MODS and CONFIGS['AB1ng'].split().count('prewarm=1') == 1
CONFIGS['AB0ng'] = ' '.join('prewarm=0' if t == 'prewarm=1' else t for t in CONFIGS['AB1ng'].split())
assert set(CONFIGS['AB0ng'].split()) ^ set(CONFIGS['AB1ng'].split()) == {'prewarm=0', 'prewarm=1'}
_AB_MODS['AB0ng'] = []
# apply_acc240.py (EXP-240 / X-028): AB5ngNF, AB5ngW, AB5ngP, AB5ngNI, AB5ngNC, AB5ngRS
assert not {'AB5ngNF', 'AB5ngW', 'AB5ngP', 'AB5ngNI', 'AB5ngNC', 'AB5ngRS'} & set(CONFIGS)
_t = CONFIGS['AB5ng'].split()
assert _t.count('accflt=1') == 1 and _t.count('accfltchk=1000') == 1 and not any(t.startswith('accwarm') for t in _t)
assert not any(t.startswith('srpf') for t in _t)
assert _t.count('ewinf=1') == 1 and not any(t.startswith('ewinf') and t != 'ewinf=1' for t in _t)
assert not any(t.startswith(('ewnice=', 'rdnice=')) for t in _t) and _t.count('ewded=4') == 1 and _t.count('ewpool=1') == 1
assert not any(t.startswith('rdspawn') for t in _t) and _t.count('readers=8') == 1
CONFIGS['AB5ngNF'] = ' '.join({'accflt=1': 'accflt=0', 'accfltchk=1000': 'accfltchk=0'}.get(t, t) for t in _t)
CONFIGS['AB5ngW'] = CONFIGS['AB5ng'] + ' accwarm=1'
CONFIGS['AB5ngP'] = CONFIGS['AB5ng'] + ' srpf=8'
CONFIGS['AB5ngNI'] = ' '.join('ewinf=0' if t == 'ewinf=1' else t for t in _t)
CONFIGS['AB5ngNC'] = CONFIGS['AB5ng'] + ' ewnice=10 rdnice=10'
CONFIGS['AB5ngRS'] = CONFIGS['AB5ng'] + ' rdspawn=1'
assert set(CONFIGS['AB5ngNF'].split()) ^ set(_t) == {'accflt=1', 'accfltchk=1000', 'accflt=0', 'accfltchk=0'}
assert set(CONFIGS['AB5ngW'].split()) ^ set(_t) == {'accwarm=1'}
assert set(CONFIGS['AB5ngP'].split()) ^ set(_t) == {'srpf=8'}
assert set(CONFIGS['AB5ngNI'].split()) ^ set(_t) == {'ewinf=1', 'ewinf=0'}
assert set(CONFIGS['AB5ngNC'].split()) ^ set(_t) == {'ewnice=10', 'rdnice=10'}
assert set(CONFIGS['AB5ngRS'].split()) ^ set(_t) == {'rdspawn=1'}
# apply_acc240q.py (EXP-240 / X-028): AB5ngPM, AB5ngWF
assert 'AB5ngPM' not in CONFIGS and not any(t.startswith('srpf') for t in CONFIGS['AB5ng'].split())
CONFIGS['AB5ngPM'] = CONFIGS['AB5ng'] + ' srpf=8 srpfmk=1'
assert set(CONFIGS['AB5ngPM'].split()) ^ set(CONFIGS['AB5ng'].split()) == {'srpf=8', 'srpfmk=1'}
assert set(CONFIGS['AB5ngPM'].split()) ^ set(CONFIGS['AB5ngP'].split()) == {'srpfmk=1'}
assert 'AB5ngWF' not in CONFIGS and CONFIGS['AB5ng'].split().count('accflt=1') == 1
CONFIGS['AB5ngWF'] = CONFIGS['AB5ng'] + ' accwarm=1'
assert CONFIGS['AB5ngWF'] == CONFIGS['AB5ngW']
# apply_e2e240.py (EXP-240 / X-028): AB5ngH, AB5ngB0
assert not {'AB5ngH', 'AB5ngB0'} & set(CONFIGS)
assert 'pwnbbhroot=1' not in CONFIGS['AB5ng'].split() and CONFIGS['AB5ng'].split().count('pwnbbh=1') == 1
CONFIGS['AB5ngH'] = CONFIGS['AB5ng'] + ' pwnbbhroot=1'
CONFIGS['AB5ngB0'] = ' '.join('pwnbbh=0' if t == 'pwnbbh=1' else t for t in CONFIGS['AB5ng'].split())
# apply_acc240m.py (EXP-240 / X-028): AB5ngB
_t = CONFIGS['AB5ng'].split()
assert 'AB5ngB' not in CONFIGS and not any(t.split('=')[0] in ('srpf', 'pwnbbhroot', 'satcls') for t in _t) and 'pwnbbh=1' in _t
CONFIGS['AB5ngB'] = CONFIGS['AB5ng'] + ' srpf=8 pwnbbhroot=1'
assert set(CONFIGS['AB5ngB'].split()) ^ set(_t) == {'srpf=8', 'pwnbbhroot=1'}
assert set(CONFIGS['AB5ngB'].split()) ^ set(CONFIGS['AB5ngP'].split()) == {'pwnbbhroot=1'}
assert set(CONFIGS['AB5ngB'].split()) ^ set(CONFIGS['AB5ngH'].split()) == {'srpf=8'}
# apply_acc240m.py (EXP-240 / X-028): AB5ngBX
assert 'AB5ngBX' not in CONFIGS and not any(t.split('=')[0] in ['ewnearkeep'] for t in CONFIGS['AB5ngB'].split())
CONFIGS['AB5ngBX'] = CONFIGS['AB5ngB'] + ' ewnearkeep=1'
assert set(CONFIGS['AB5ngBX'].split()) ^ set(CONFIGS['AB5ngB'].split()) == {'ewnearkeep=1'}
# apply_r290.py (EXP-243/244, Master 11-03): AB5ngnr
assert 'AB5ngnr' not in CONFIGS
_nr = {'reuse=2', 'reusechk=16', 'reusefast=1', 'reusebal=1'}
assert _nr <= set(CONFIGS['AB5ng'].split()) and 'pwcs=1' in CONFIGS['AB5ng'].split()
assert not [t for t in CONFIGS['AB5ng'].split() if t.startswith('reuse') and t not in _nr]
CONFIGS['AB5ngnr'] = ' '.join(t for t in CONFIGS['AB5ng'].split() if t not in _nr)
assert set(CONFIGS['AB5ngnr'].split()) ^ set(CONFIGS['AB5ng'].split()) == _nr
# apply_d290.py (EXP-239/241, Master 11-02): AB1ngup, AB4ngsp
assert not {'AB1ngup', 'AB4ngsp'} & set(CONFIGS)
CONFIGS['AB1ngup'] = CONFIGS['AB1ng'] + ' upreuse=1'
_sp = ('pwcs=1 pwk=4294967295 readers=8 rdstop=1 pwstale=1 pwnb=1 pwnbval=1 pwnbgas=0 pwnbhist=0 pwnbsep=1 pwnbbh=1 '
       'pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10').split()
_t4 = CONFIGS['AB4ng'].split()
assert 'tx=0' in _t4 and 'code=0' in _t4 and not any(t.split('=')[0] in {x.split('=')[0] for x in _sp} for t in _t4) and 'ewbud' not in CONFIGS['AB4ng']
_t5 = set(CONFIGS['AB5ng'].split())
assert {t for t in _sp if t.startswith('pwnb') and t != 'pwnbgas=0'} <= _t5 and 'pwnbgas=5000000' in _t5   # AB5's pass, all transactions
_i = _t4.index('srdiag=1') if 'srdiag=1' in _t4 else len(_t4)
CONFIGS['AB4ngsp'] = ' '.join(_t4[:_i] + _sp + _t4[_i:])
assert set(CONFIGS['AB4ngsp'].split()) ^ set(_t4) == set(_sp)
# apply_supp290.py (EXP-235/236, Master 11-02): AB1ngrec, AB1ngpl, AB5ngpl, AB5ngcs
assert not {'AB1ngrec', 'AB1ngpl', 'AB5ngpl', 'AB5ngcs'} & set(CONFIGS)
CONFIGS['AB1ngrec'] = CONFIGS['AB1ng'] + ' plrec=1'
CONFIGS['AB1ngpl'] = CONFIGS['AB1ng'] + ' pl=1'
CONFIGS['AB5ngpl'] = CONFIGS['AB5ng'] + ' pl=1'
_cs_drop = {'pwcs=1', 'pwnb=1', 'pwlx=1', 'c2rec=1', 'txdec=1'}
assert _cs_drop <= set(CONFIGS['AB5ng'].split()) and 'cs=0' in CONFIGS['AB5ng'].split() and 'tx=1' in CONFIGS['AB5ng'].split()
CONFIGS['AB5ngcs'] = ' '.join(['cs=1' if t == 'cs=0' else t for t in CONFIGS['AB5ng'].split() if t not in _cs_drop] + ['slots=0'])
assert set(CONFIGS['AB5ngcs'].split()) ^ set(CONFIGS['AB5ng'].split()) == _cs_drop | {'cs=0', 'cs=1', 'slots=0'}
# apply_x029w.py (EXP-247 8.35): AB5ngf1 = AB5ng + ewfeed=1, targeted wake-ups alone (bit 1 without bit 8)
assert 'AB5ngf1' not in CONFIGS and 'AB5ngf1' not in _AB_MODS and 'ewfeed' not in CONFIGS['AB5ng']
assert 'ewsplit' not in CONFIGS['AB5ng']   # bit 1 has effect only without ewsplit
CONFIGS['AB5ngf1'] = CONFIGS['AB5ng'] + ' ewfeed=1'
_AB_MODS['AB5ngf1'] = _AB_MODS['AB5ng']
assert set(CONFIGS['AB5ngf1'].split()) ^ set(CONFIGS['AB5ng'].split()) == {'ewfeed=1'}
# apply_bf240.py (EXP-240 26 / X-028): AB5ngBF = AB5ng + e240m's B (srpf=8 pwnbbhroot=1) + X-029's f1 (ewfeed=1)
assert 'AB5ngBF' not in CONFIGS and 'AB5ngBF' not in _AB_MODS
assert not any(t.split('=')[0] in ('srpf', 'pwnbbhroot', 'ewfeed', 'ewsplit') for t in CONFIGS['AB5ng'].split())
assert CONFIGS['AB5ng'].split().count('pwnbbh=1') == 1   # pwnbbhroot holds the pass that pwnbbh=1 turns on
CONFIGS['AB5ngBF'] = CONFIGS['AB5ng'] + ' srpf=8 pwnbbhroot=1 ewfeed=1'
_AB_MODS['AB5ngBF'] = _AB_MODS['AB5ng']
assert set(CONFIGS['AB5ngBF'].split()) ^ set(CONFIGS['AB5ng'].split()) == {'srpf=8', 'pwnbbhroot=1', 'ewfeed=1'}
# apply_hr240.py (EXP-240 27.4 / X-028): AB5ngHR = AB5ng + hashpre=2000 (aaa44b6) + rdpool=1 (2a7ee27)
assert 'AB5ngHR' not in CONFIGS and 'AB5ngHR' not in _AB_MODS
assert not any(t.split('=')[0] in ('hashpre', 'rdpool') for t in CONFIGS['AB5ng'].split())
assert CONFIGS['AB5ng'].split().count('ewcore=1') == 1 and CONFIGS['AB5ng'].split().count('readers=8') == 1
CONFIGS['AB5ngHR'] = CONFIGS['AB5ng'] + ' hashpre=2000 rdpool=1'
_AB_MODS['AB5ngHR'] = _AB_MODS['AB5ng']
assert set(CONFIGS['AB5ngHR'].split()) ^ set(CONFIGS['AB5ng'].split()) == {'hashpre=2000', 'rdpool=1'}
# apply_rp240.py (EXP-240 27.6 / X-028): AB5ngRP = AB5ng + rdpool=1 (2a7ee27)
assert 'AB5ngRP' not in CONFIGS and 'AB5ngRP' not in _AB_MODS
assert not any(t.split('=')[0] in ('hashpre', 'rdpool') for t in CONFIGS['AB5ng'].split())
assert CONFIGS['AB5ng'].split().count('ewcore=1') == 1 and CONFIGS['AB5ng'].split().count('readers=8') == 1
CONFIGS['AB5ngRP'] = CONFIGS['AB5ng'] + ' rdpool=1'
_AB_MODS['AB5ngRP'] = _AB_MODS['AB5ng']
assert set(CONFIGS['AB5ngRP'].split()) ^ set(CONFIGS['AB5ng'].split()) == {'rdpool=1'}
# apply_rpm240.py (EXP-240 27.10 / X-028): AB5ngM = AB5ng + exrt=0 ewnear=0 ewredo=4 (the main configuration since 11-05 05:11), AB5ngMRP = AB5ngM + rdpool=1
assert not {'AB5ngM', 'AB5ngMRP'} & (set(CONFIGS) | set(_AB_MODS))
_t = CONFIGS['AB5ng'].split()
assert _t.count('exrt=1') == 1 and _t.count('ewnear=1') == 1 and not any(x.split('=')[0] in ('ewredo', 'rdpool', 'excore') for x in _t)
CONFIGS['AB5ngM'] = ' '.join({'exrt=1': 'exrt=0', 'ewnear=1': 'ewnear=0'}.get(x, x) for x in _t) + ' ewredo=4'
CONFIGS['AB5ngMRP'] = CONFIGS['AB5ngM'] + ' rdpool=1'
_AB_MODS['AB5ngM'] = _AB_MODS['AB5ng']
_AB_MODS['AB5ngMRP'] = _AB_MODS['AB5ng']
assert set(CONFIGS['AB5ngM'].split()) ^ set(_t) == {'exrt=1', 'exrt=0', 'ewnear=1', 'ewnear=0', 'ewredo=4'}
assert set(CONFIGS['AB5ngMRP'].split()) ^ set(CONFIGS['AB5ngM'].split()) == {'rdpool=1'}
# apply_final251.py (EXP-251 / X-028): rows of the final measurement from main_config.txt (base AB5ng set ewnear=0 set reusechk=0 add ewredo=4 add reusefb=1 add exio=1)
assert not {'PFchk', 'P1', 'P0', 'UP', 'P5', 'P2', 'P3', 'PF', 'P4'} & (set(CONFIGS) | set(_AB_MODS))
CONFIGS['UP'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1'
_AB_MODS['UP'] = _AB_MODS['AB1ng' if 'UP' in ('UP', 'P0') else 'AB5ng']
CONFIGS['PF'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1'
_AB_MODS['PF'] = _AB_MODS['AB1ng' if 'PF' in ('UP', 'P0') else 'AB5ng']
CONFIGS['PFchk'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=1 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1'
_AB_MODS['PFchk'] = _AB_MODS['AB1ng' if 'PFchk' in ('UP', 'P0') else 'AB5ng']
CONFIGS['P0'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1'
_AB_MODS['P0'] = _AB_MODS['AB1ng' if 'P0' in ('UP', 'P0') else 'AB5ng']
CONFIGS['P1'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4'
_AB_MODS['P1'] = _AB_MODS['AB1ng' if 'P1' in ('UP', 'P0') else 'AB5ng']
CONFIGS['P2'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 exio=1'
_AB_MODS['P2'] = _AB_MODS['AB1ng' if 'P2' in ('UP', 'P0') else 'AB5ng']
CONFIGS['P3'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 exio=1 accflt=1 accfltchk=1000 bigra=1 ccv=1 ewinf=1 rdpeek=1 sysn=1'
_AB_MODS['P3'] = _AB_MODS['AB1ng' if 'P3' in ('UP', 'P0') else 'AB5ng']
CONFIGS['P4'] = 'prewarm=1 insp=0 cs=0 tx=1 code=1 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 exio=1 accflt=1 accfltchk=1000 bigra=1 ccv=1 ewinf=1 rdpeek=1 sysn=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1'
_AB_MODS['P4'] = _AB_MODS['AB1ng' if 'P4' in ('UP', 'P0') else 'AB5ng']
CONFIGS['P5'] = 'prewarm=1 insp=0 cs=0 tx=1 code=1 srdiag=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1'
_AB_MODS['P5'] = _AB_MODS['AB1ng' if 'P5' in ('UP', 'P0') else 'AB5ng']
assert CONFIGS['UP'] == CONFIGS['AB1ng'] == CONFIGS['P0']
assert {t for t in CONFIGS['PF'].split() if not t.startswith('srdiag=')} == {t for t in CONFIGS['P4'].split() if not t.startswith('srdiag=')}
# apply_final252.py (EXP-252 / X-028): rows of the final measurement from main_config.txt (base AB5ng set ewnear=0 set reusechk=0 add ewredo=4 add reusefb=1 add exio=1 add srrt=1 add reusebalsend=1 add ixpf=256 add ixpfw=1)
assert not {'Q1', 'N2chk', 'Q2', 'QS', 'QC', 'U2', 'Q4', 'Q0n', 'QN', 'Q5', 'QX', 'Q0', 'Q3', 'N2'} & (set(CONFIGS) | set(_AB_MODS))
CONFIGS['U2'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1'
_AB_MODS['U2'] = _AB_MODS['AB1ng' if 'U2' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['N2'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1'
_AB_MODS['N2'] = _AB_MODS['AB1ng' if 'N2' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['N2chk'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=1 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1'
_AB_MODS['N2chk'] = _AB_MODS['AB1ng' if 'N2chk' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['Q0'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1'
_AB_MODS['Q0'] = _AB_MODS['AB1ng' if 'Q0' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['Q1'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 reusebalsend=1 ixpf=256 ixpfw=1'
_AB_MODS['Q1'] = _AB_MODS['AB1ng' if 'Q1' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['Q2'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 reusebalsend=1 ixpf=256 ixpfw=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 exio=1 srrt=1'
_AB_MODS['Q2'] = _AB_MODS['AB1ng' if 'Q2' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['Q3'] = 'prewarm=1 insp=0 cs=0 tx=0 code=0 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 reusebalsend=1 ixpf=256 ixpfw=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 exio=1 srrt=1 accflt=1 accfltchk=1000 bigra=1 ccv=1 ewinf=1 rdpeek=1 sysn=1'
_AB_MODS['Q3'] = _AB_MODS['AB1ng' if 'Q3' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['Q4'] = 'prewarm=1 insp=0 cs=0 tx=1 code=1 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 reusebalsend=1 ixpf=256 ixpfw=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 exio=1 srrt=1 accflt=1 accfltchk=1000 bigra=1 ccv=1 ewinf=1 rdpeek=1 sysn=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1'
_AB_MODS['Q4'] = _AB_MODS['AB1ng' if 'Q4' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['Q5'] = 'prewarm=1 insp=0 cs=0 tx=1 code=1 srdiag=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1'
_AB_MODS['Q5'] = _AB_MODS['AB1ng' if 'Q5' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['QX'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=0 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1'
_AB_MODS['QX'] = _AB_MODS['AB1ng' if 'QX' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['QS'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=0 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1'
_AB_MODS['QS'] = _AB_MODS['AB1ng' if 'QS' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['QC'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=1 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1 nocons=1'
_AB_MODS['QC'] = _AB_MODS['AB1ng' if 'QC' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['QN'] = 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=0 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=0 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=1 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1 nocons=1'
_AB_MODS['QN'] = _AB_MODS['AB1ng' if 'QN' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
CONFIGS['Q0n'] = 'prewarm=0 insp=0 cs=0 tx=0 code=0 srdiag=1'
_AB_MODS['Q0n'] = _AB_MODS['AB1ng' if 'Q0n' in ('U2', 'Q0', 'Q0n') else 'AB5ng']
assert CONFIGS['U2'] == CONFIGS['AB1ng'] == CONFIGS['Q0']
assert set(CONFIGS['Q0n'].split()) ^ set(CONFIGS['Q0'].split()) == {'prewarm=0', 'prewarm=1'}
assert {t for t in CONFIGS['N2'].split() if not t.startswith('srdiag=')} == {t for t in CONFIGS['Q4'].split() if not t.startswith('srdiag=')}
assert set(CONFIGS['QX'].split()) ^ set(CONFIGS['N2'].split()) == {'pwlx=0', 'pwlx=1'}
assert set(CONFIGS['QS'].split()) ^ set(CONFIGS['N2'].split()) == {'pwnb=0', 'pwnb=1'}
assert set(CONFIGS['QC'].split()) ^ set(CONFIGS['N2'].split()) == {'nocons=1'}
assert set(CONFIGS['QN'].split()) ^ set(CONFIGS['N2'].split()) == {'pwlx=0', 'pwnb=1', 'nocons=1', 'pwnb=0', 'pwlx=1'}
# apply_i4_254.py (EXP-254 / X-028): N2nr = N2 without reuse, N2j = N2 + rdjoinlate=1
_nr = CONFIGS['N2'].split()
for _a, _b in (('reuse=2', 'reuse=0'), ('reusefast=1', 'reusefast=0'), ('reusebal=1', 'reusebal=0'), ('reusebalsend=1', 'reusebalsend=0'), ('reusefb=1', 'reusefb=0')):
    assert _nr.count(_a) == 1, _a
    _nr[_nr.index(_a)] = _b
CONFIGS['N2nr'] = ' '.join(_nr)
assert 'reusechk=0' in _nr and set(CONFIGS['N2'].split()) - set(_nr) == {'reuse=2', 'reusefast=1', 'reusebal=1', 'reusebalsend=1', 'reusefb=1'}
assert 'rdjoinlate' not in CONFIGS['N2']
CONFIGS['N2j'] = CONFIGS['N2'] + ' rdjoinlate=1'
assert set(CONFIGS['N2j'].split()) - set(CONFIGS['N2'].split()) == {'rdjoinlate=1'}
# apply_lead254.py (EXP-254 / X-028): N2L, N2rp0, N2rp300, N2rp850 (the lead floor, reth prologue-leadfloor), N2rpj
_n2 = CONFIGS['N2'].split()
assert 'ewcore=1' in _n2 and _n2.count('pwnb=1') == 1 and not any(k.split('=')[0] in ('rdpool', 'exlead', 'exleadus', 'leadlog', 'excore', 'rdjoinlate') for k in _n2)
# the final configuration's base (researcher 21:3x): N2 without speculation
_n2s = ' '.join('pwnb=0' if k == 'pwnb=1' else k for k in _n2)
CONFIGS['N2L'] = _n2s + ' leadlog=1'
for _l in (0, 300, 850):
    CONFIGS[f'N2rp{_l}'] = _n2s + f' rdpool=1 exlead=1 exleadus={_l}'
CONFIGS['N2rpj'] = _n2s + ' rdpool=1 rdjoinlate=1 leadlog=1'
for _k, _own in (('N2L', {'leadlog=1'}), ('N2rp0', {'rdpool=1', 'exlead=1', 'exleadus=0'}), ('N2rp300', {'rdpool=1', 'exlead=1', 'exleadus=300'}),
                 ('N2rp850', {'rdpool=1', 'exlead=1', 'exleadus=850'}), ('N2rpj', {'rdpool=1', 'rdjoinlate=1', 'leadlog=1'})):
    assert set(CONFIGS[_k].split()) - set(_n2) == _own | {'pwnb=0'} and set(_n2) - set(CONFIGS[_k].split()) == {'pwnb=1'}, _k
# apply_off254.py (EXP-254 / X-028): N2off (Prologue without prewarming)
_off = CONFIGS['N2'].split()
_offmap = {'pwnb=1': 'pwnb=0', 'prewarm=1': 'prewarm=0', 'ew=12': 'ew=0', 'cs=0': 'cs=1', 'insp=0': 'insp=1', 'reuse=2': 'reuse=0',
           'reusefast=1': 'reusefast=0', 'reusebal=1': 'reusebal=0', 'reusebalsend=1': 'reusebalsend=0', 'reusefb=1': 'reusefb=0'}
for _a, _b in _offmap.items():
    assert _off.count(_a) == 1, _a
    _off[_off.index(_a)] = _b
CONFIGS['N2off'] = ' '.join(_off)
assert set(CONFIGS['N2'].split()) - set(_off) == set(_offmap) and set(_off) - set(CONFIGS['N2'].split()) == set(_offmap.values())
assert all(k in _off for k in ('tx=1', 'code=1', 'readers=8')) and 'Q0n' in CONFIGS and 'prewarm=0' in CONFIGS['Q0n'].split()
# apply_v256.py (EXP-256 / X-028): V0 (N2s + leadlog), V1 (+ rdpool rdjoinlate), V2 (+ exlead, no extra wait), V3 (+ exphys)
_v = CONFIGS['N2'].split()
assert 'ewcore=1' in _v and _v.count('pwnb=1') == 1 and not any(k.split('=')[0] in ('rdpool', 'rdjoinlate', 'exlead', 'exleadus', 'leadlog', 'excore', 'exphys') for k in _v)
_vs = ' '.join('pwnb=0' if k == 'pwnb=1' else k for k in _v)
_steps = (('V0', ['leadlog=1']), ('V1', ['rdpool=1', 'rdjoinlate=1']), ('V2', ['exlead=1', 'exleadus=0']), ('V3', ['exphys=1']))
_prev, _acc = None, []
for _k, _own in _steps:
    _acc = _acc + _own
    CONFIGS[_k] = _vs + ' ' + ' '.join(_acc)
    assert set(CONFIGS[_k].split()) - set(_v) == set(_acc) | {'pwnb=0'} and set(_v) - set(CONFIGS[_k].split()) == {'pwnb=1'}, _k
    if _prev:
        assert set(CONFIGS[_k].split()) - set(CONFIGS[_prev].split()) == set(_own) and not set(CONFIGS[_prev].split()) - set(CONFIGS[_k].split()), _k
    _prev = _k
_nr = CONFIGS['V2'].split()
for _a, _b in (('reuse=2', 'reuse=0'), ('reusefast=1', 'reusefast=0'), ('reusebal=1', 'reusebal=0'), ('reusebalsend=1', 'reusebalsend=0'), ('reusefb=1', 'reusefb=0')):
    assert _nr.count(_a) == 1, _a
    _nr[_nr.index(_a)] = _b
CONFIGS['V2nr'] = ' '.join(_nr)
assert set(CONFIGS['V2'].split()) - set(_nr) == {'reuse=2', 'reusefast=1', 'reusebal=1', 'reusebalsend=1', 'reusefb=1'}
# apply_final257.py (EXP-257 / main measurement): F7 (frozen), F7chk, U7, G0-G5, GX, GC, GXC, G0n
assert not {'F7', 'F7chk', 'U7', 'G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'GX', 'GC', 'GXC', 'G0n'} & set(CONFIGS)
def _sub(row, a, b):
    _t = row.split()
    assert _t.count(a) == 1, (a, row)
    _t[_t.index(a)] = b
    return ' '.join(_t)
def _keys(row):
    return {x.split('=')[0] for x in row.split()}
_FROZEN_ADD = 'rdpool=1 rdjoinlate=1'
assert not _keys(CONFIGS['N2']) & {'rdpool', 'rdjoinlate', 'nocons', 'leadlog', 'exlead', 'exphys'}
CONFIGS['F7'] = _sub(CONFIGS['N2'], 'pwnb=1', 'pwnb=0') + ' ' + _FROZEN_ADD
assert set(CONFIGS['F7'].split()) == set(CONFIGS['V1'].split()) - {'leadlog=1'}, 'F7 must equal V1 without leadlog'
CONFIGS['F7chk'] = _sub(CONFIGS['F7'], 'reusechk=0', 'reusechk=1')
CONFIGS['U7'] = CONFIGS['U2']
assert CONFIGS['U7'] == CONFIGS['AB1ng'] == CONFIGS['Q0']
for _i in range(4):
    assert not _keys(CONFIGS[f'Q{_i}']) & {'pwnb', 'rdpool', 'rdjoinlate', 'nocons'}, _i
    CONFIGS[f'G{_i}'] = CONFIGS[f'Q{_i}']
CONFIGS['G4'] = _sub(CONFIGS['Q4'], 'pwnb=1', 'pwnb=0') + ' ' + _FROZEN_ADD
_nosr = lambda r: {x for x in r.split() if not x.startswith('srdiag=')}
assert _nosr(CONFIGS['G4']) == _nosr(CONFIGS['F7']), 'G4 must equal F7'
CONFIGS['G5'] = _sub(CONFIGS['Q5'], 'pwnb=1', 'pwnb=0') + ' ' + _FROZEN_ADD
assert set(CONFIGS['G5'].split()) - set(CONFIGS['Q5'].split()) == {'pwnb=0', 'rdpool=1', 'rdjoinlate=1'}
CONFIGS['GX'] = _sub(CONFIGS['F7'], 'pwlx=1', 'pwlx=0')
CONFIGS['GC'] = CONFIGS['F7'] + ' nocons=1'
CONFIGS['GXC'] = _sub(CONFIGS['F7'], 'pwlx=1', 'pwlx=0') + ' nocons=1'
for _k, _d in (('GX', {'pwlx=0', 'pwlx=1'}), ('GC', {'nocons=1'}), ('GXC', {'pwlx=0', 'pwlx=1', 'nocons=1'})):
    assert set(CONFIGS[_k].split()) ^ set(CONFIGS['F7'].split()) == _d, _k
CONFIGS['G0n'] = CONFIGS['Q0n']
assert set(CONFIGS['G0n'].split()) ^ set(CONFIGS['G0'].split()) == {'prewarm=0', 'prewarm=1'}
# each step adds its own group only: G1-G0 pre-execution, G2-G1 scheduling, G3-G2 reading path, G4-G3 plans and readers
for _a, _b in (('G0', 'G1'), ('G1', 'G2'), ('G2', 'G3'), ('G3', 'G4')):
    assert not _keys(CONFIGS[_a]) - _keys(CONFIGS[_b]), (_a, _b)
assert {'rdpool=1', 'rdjoinlate=1', 'pwnb=0'} <= set(CONFIGS['G4'].split()) - set(CONFIGS['G3'].split())
# apply_x258.py (EXP-258 / X-028): G4R = G4 + rdasync=1 rddefer=1; G4S = G4 with pwsync=0; G4B = G4 + srbatch=16
_g4 = CONFIGS['G4'].split()
assert {x for x in _g4 if not x.startswith('srdiag=')} == {x for x in CONFIGS['F7'].split() if not x.startswith('srdiag=')} and 'rdpool=1' in _g4 and not any(k.split('=')[0] in ('rdasync', 'rddefer') for k in _g4)
CONFIGS['G4R'] = CONFIGS['G4'] + ' rdasync=1 rddefer=1'
assert set(CONFIGS['G4R'].split()) - set(_g4) == {'rdasync=1', 'rddefer=1'} and set(_g4) <= set(CONFIGS['G4R'].split())
assert _g4.count('pwsync=1') == 1
CONFIGS['G4S'] = ' '.join('pwsync=0' if k == 'pwsync=1' else k for k in _g4)
assert set(_g4) - set(CONFIGS['G4S'].split()) == {'pwsync=1'} and set(CONFIGS['G4S'].split()) - set(_g4) == {'pwsync=0'}
assert not any(k.split('=')[0] == 'srbatch' for k in _g4)
CONFIGS['G4B'] = CONFIGS['G4'] + ' srbatch=16'
assert set(CONFIGS['G4B'].split()) - set(_g4) == {'srbatch=16'} and set(_g4) <= set(CONFIGS['G4B'].split())
# apply_x260.py (EXP-260 / X-028): Current = F7 with srdiag=0 and the explicit switches of 19cbaea; Candidate = Current with srleafselect=1;
# CurChk / CandChk = the two with reusechk=1 srhintdiag=1 (pre-check only, the srleafselect echo)
def _x260_sub(row, a, b):
    _t = row.split()
    assert _t.count(a) == 1, (a, row)
    _t[_t.index(a)] = b
    return ' '.join(_t)
assert not {'Current', 'Candidate', 'CurChk', 'CandChk'} & set(CONFIGS)
assert not any(k.split('=')[0] in ['srdirty', 'srworkdiag', 'srphase', 'srverify', 'srhintdedup', 'srhintdiag', 'srleafselect'] for k in CONFIGS['F7'].split())
CONFIGS['Current'] = _x260_sub(CONFIGS['F7'], 'srdiag=1', 'srdiag=0') + ' srdirty=0 srworkdiag=0 srphase=0 srverify=0 srhintdedup=0 srhintdiag=0 srleafselect=0'
CONFIGS['Candidate'] = _x260_sub(CONFIGS['Current'], 'srleafselect=0', 'srleafselect=1')
assert CONFIGS['Current'] == 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=0 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=0 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1 rdpool=1 rdjoinlate=1 srdirty=0 srworkdiag=0 srphase=0 srverify=0 srhintdedup=0 srhintdiag=0 srleafselect=0', 'Current is not configs.json Current'
assert CONFIGS['Candidate'] == 'prewarm=1 insp=0 cs=0 ew=12 ewded=4 ewgas=1000000 pwheavyfirst=4 ewov=1 reuse=2 reusechk=0 reusefast=1 reusebal=1 pwjitreal=1 pwjitpeek=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 rdpeek=1 bigra=1 ccv=1 sysn=1 ewinf=1 accflt=1 accfltchk=1000 tx=1 code=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=0 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 srdiag=0 ewredo=4 reusefb=1 exio=1 srrt=1 reusebalsend=1 ixpf=256 ixpfw=1 rdpool=1 rdjoinlate=1 srdirty=0 srworkdiag=0 srphase=0 srverify=0 srhintdedup=0 srhintdiag=0 srleafselect=1', 'Candidate is not configs.json Candidate'
assert set(CONFIGS['Candidate'].split()) ^ set(CONFIGS['Current'].split()) == {'srleafselect=0', 'srleafselect=1'}
CONFIGS['CurChk'] = _x260_sub(_x260_sub(CONFIGS['Current'], 'reusechk=0', 'reusechk=1'), 'srhintdiag=0', 'srhintdiag=1')
CONFIGS['CandChk'] = _x260_sub(_x260_sub(CONFIGS['Candidate'], 'reusechk=0', 'reusechk=1'), 'srhintdiag=0', 'srhintdiag=1')
assert set(CONFIGS['CandChk'].split()) ^ set(CONFIGS['CurChk'].split()) == {'srleafselect=0', 'srleafselect=1'}
# apply_bp240.py (EXP-240 28.5 / X-028): PFBP = PF + busypromote=500 (PF: the main configuration, apply_final251.py)
assert 'PFBP' not in set(CONFIGS) | set(_AB_MODS) and 'PF' in CONFIGS
assert not any(x.split('=')[0] == 'busypromote' for x in CONFIGS['PF'].split())
CONFIGS['PFBP'] = CONFIGS['PF'] + ' busypromote=500'
_AB_MODS['PFBP'] = _AB_MODS['PF']
assert set(CONFIGS['PFBP'].split()) ^ set(CONFIGS['PF'].split()) == {'busypromote=500'}
# apply_dr240.py (EXP-240 28.14 / X-028): PFD = PF + drainnopre=1, PFR = PF + srrt=1, PFDR = PF + both (PF: apply_final251.py)
assert not {'PFD', 'PFR', 'PFDR'} & (set(CONFIGS) | set(_AB_MODS)) and 'PF' in CONFIGS
assert not any(x.split('=')[0] in ('drainnopre', 'srrt') for x in CONFIGS['PF'].split())
CONFIGS['PFD'] = CONFIGS['PF'] + ' drainnopre=1'
CONFIGS['PFR'] = CONFIGS['PF'] + ' srrt=1'
CONFIGS['PFDR'] = CONFIGS['PF'] + ' drainnopre=1 srrt=1'
for _r in ('PFD', 'PFR', 'PFDR'):
    _AB_MODS[_r] = _AB_MODS['PF']
assert set(CONFIGS['PFD'].split()) ^ set(CONFIGS['PF'].split()) == {'drainnopre=1'}
assert set(CONFIGS['PFR'].split()) ^ set(CONFIGS['PF'].split()) == {'srrt=1'}
assert set(CONFIGS['PFDR'].split()) ^ set(CONFIGS['PF'].split()) == {'drainnopre=1', 'srrt=1'}
# apply_x031.py (EXP-264 / X-031): G3q G4q G4qa G3qx G4qax
_x031_keys = ('logq', 'rdasync', 'excore', 'exsmt', 'exphys')
assert {x for x in CONFIGS['G4'].split() if not x.startswith('srdiag=')} == {x for x in CONFIGS['F7'].split() if not x.startswith('srdiag=')}
assert not any(k.split('=')[0] in _x031_keys for r in ('G3', 'G4') for k in CONFIGS[r].split()), 'G3 or G4 sets an X-031 key'
_x031_x = ' excore=1 exsmt=1 exphys=1'
CONFIGS['G3q'] = CONFIGS['G3'] + ' logq=1'
CONFIGS['G4q'] = CONFIGS['G4'] + ' logq=1'
CONFIGS['G4qa'] = CONFIGS['G4q'] + ' rdasync=1'
CONFIGS['G3qx'] = CONFIGS['G3q'] + _x031_x
CONFIGS['G4qax'] = CONFIGS['G4qa'] + _x031_x
for _r, _b, _add in (('G3q', 'G3', {'logq=1'}), ('G4q', 'G4', {'logq=1'}), ('G4qa', 'G4q', {'rdasync=1'}),
                     ('G3qx', 'G3q', {'excore=1', 'exsmt=1', 'exphys=1'}), ('G4qax', 'G4qa', {'excore=1', 'exsmt=1', 'exphys=1'})):
    assert set(CONFIGS[_r].split()) - set(CONFIGS[_b].split()) == _add and set(CONFIGS[_b].split()) <= set(CONFIGS[_r].split()), _r
# apply_x031e.py (EXP-265 / X-031): G4qaxe
assert not any(k.split('=')[0] == 'exclean' for r in ('G3qx', 'G4qax') for k in CONFIGS[r].split()), 'G3qx or G4qax sets exclean'
CONFIGS['G4qaxe'] = CONFIGS['G4qax'] + ' exclean=1'
assert set(CONFIGS['G4qaxe'].split()) - set(CONFIGS['G4qax'].split()) == {'exclean=1'} and set(CONFIGS['G4qax'].split()) <= set(CONFIGS['G4qaxe'].split()), 'G4qaxe'
# apply_x031pk.py (EXP-266 / X-031): G4qaxep G4qaxepk
assert not any(k.split('=')[0] in ('rddefer', 'prep', 'rdkick') for k in CONFIGS['G4qaxe'].split()), 'G4qaxe sets rddefer, prep or rdkick'
CONFIGS['G4qaxep'] = CONFIGS['G4qaxe'] + ' rddefer=1 prep=1'
CONFIGS['G4qaxepk'] = CONFIGS['G4qaxep'] + ' rdkick=1'
for _r, _b, _add in (('G4qaxep', 'G4qaxe', {'rddefer=1', 'prep=1'}), ('G4qaxepk', 'G4qaxep', {'rdkick=1'})):
    assert set(CONFIGS[_r].split()) - set(CONFIGS[_b].split()) == _add and set(CONFIGS[_b].split()) <= set(CONFIGS[_r].split()), _r
# apply_x031int.py (EXP-269 / X-031 integration): G3qxS G4qaxepkS G4qaxepkSR
assert not any(k.split('=')[0] in ('srleafselect', 'rdscratch') for r in ('G3qx', 'G4qaxepk') for k in CONFIGS[r].split()), 'a base sets srleafselect or rdscratch'
CONFIGS['G3qxS'] = CONFIGS['G3qx'] + ' srleafselect=1 rdscratch=1'
CONFIGS['G4qaxepkS'] = CONFIGS['G4qaxepk'] + ' srleafselect=1 rdscratch=1'
CONFIGS['G4qaxepkSR'] = CONFIGS['G4qaxepkS'] + ' pwsync=0 rdsplit=4'
for _r, _b in (('G3qxS', 'G3qx'), ('G4qaxepkS', 'G4qaxepk')):
    assert set(CONFIGS[_r].split()) - set(CONFIGS[_b].split()) == {'srleafselect=1', 'rdscratch=1'} and set(CONFIGS[_b].split()) <= set(CONFIGS[_r].split()), _r
assert 'pwsync=1' in CONFIGS['G4qaxepkS'].split() and not any(k.startswith('rdsplit=') for k in CONFIGS['G4qaxepkS'].split()), 'G4qaxepkS'
assert set(CONFIGS['G4qaxepkSR'].split()) - set(CONFIGS['G4qaxepkS'].split()) == {'pwsync=0', 'rdsplit=4'} and CONFIGS['G4qaxepkSR'].split()[-2:] == ['pwsync=0', 'rdsplit=4'], 'G4qaxepkSR'
# apply_x031late.py (EXP-269 section 10): G4qaxepkSL G4qaxepkSRL
for _r, _b in (('G4qaxepkSL', 'G4qaxepkS'), ('G4qaxepkSRL', 'G4qaxepkSR')):
    assert not any(k.startswith('rdlate=') for k in CONFIGS[_b].split()), _b
    CONFIGS[_r] = CONFIGS[_b] + ' rdlate=500'
    assert set(CONFIGS[_r].split()) - set(CONFIGS[_b].split()) == {'rdlate=500'}, _r
# apply_x031pl.py (EXP-269 section 11): G4qaxepkSP
assert not any(k.startswith('prlite=') for k in CONFIGS['G4qaxepkS'].split()), 'G4qaxepkS'
CONFIGS['G4qaxepkSP'] = CONFIGS['G4qaxepkS'] + ' prlite=1'
assert set(CONFIGS['G4qaxepkSP'].split()) - set(CONFIGS['G4qaxepkS'].split()) == {'prlite=1'}, 'G4qaxepkSP'
# apply_x031dg.py (EXP-269 section 13): G4qaxepkSN G3qxSP G3qxSQ
for _r, _b, _add in (('G4qaxepkSN', 'G4qaxepkS', 'rdnop=1'), ('G3qxSP', 'G3qxS', 'spin=8 spinus=2250 spinwin=18000'), ('G3qxSQ', 'G3qxS', 'spin=8 spinus=3200 spinwin=25000')):
    assert not any(k.split('=')[0] in ('rdnop', 'spin', 'spinus', 'spinwin') for k in CONFIGS[_b].split()), _b
    CONFIGS[_r] = CONFIGS[_b] + ' ' + _add
    assert set(CONFIGS[_r].split()) - set(CONFIGS[_b].split()) == set(_add.split()), _r
# apply_x031ji.py (EXP-269 section 14): G4qaxepkSI
assert not any(k.split('=')[0] in ('rdidle', 'prlite') for k in CONFIGS['G4qaxepkS'].split()), 'G4qaxepkS'
CONFIGS['G4qaxepkSI'] = CONFIGS['G4qaxepkS'] + ' pwsync=0 rdidle=1 prlite=1'
assert set(CONFIGS['G4qaxepkSI'].split()) - set(CONFIGS['G4qaxepkS'].split()) == {'pwsync=0', 'rdidle=1', 'prlite=1'}, 'G4qaxepkSI'
# apply_x031iw.py (EXP-269 section 15): G4qaxepkSW
assert not any(k.startswith('infwait=') for k in CONFIGS['G4qaxepkSI'].split()), 'G4qaxepkSI'
CONFIGS['G4qaxepkSW'] = CONFIGS['G4qaxepkSI'] + ' infwait=0'
assert set(CONFIGS['G4qaxepkSW'].split()) - set(CONFIGS['G4qaxepkS'].split()) == {'pwsync=0', 'rdidle=1', 'prlite=1', 'infwait=0'}, 'G4qaxepkSW'
# apply_x031io.py (EXP-269 section 19): G4qaxepkSIB, G4qaxepkSWB
for _b in ('G4qaxepkSI', 'G4qaxepkSW'):
    assert not any(k.startswith('rdidleio=') for k in CONFIGS[_b].split()), _b
    CONFIGS[_b + 'B'] = CONFIGS[_b] + ' rdidleio=1'
    assert set(CONFIGS[_b + 'B'].split()) - set(CONFIGS[_b].split()) == {'rdidleio=1'}, _b + 'B'
# apply_final270.py (EXP-270 / final measurement): F8 (frozen = G4qaxepkS), F8chk, F8w, P8, P8chk, P8w, U8, H0-H5, HX, HC, HXC, H0n
_NEW270 = {'F8', 'F8chk', 'F8w', 'P8w', 'P8', 'P8chk', 'U8', 'H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'HX', 'HC', 'HXC', 'H0n'}
assert not _NEW270 & set(CONFIGS), _NEW270 & set(CONFIGS)
def _m270(row):
    _d = {}
    for _x in row.split():
        _k, _, _v = _x.partition('=')
        _d.pop(_k, None); _d[_k] = _v
    return _d
def _s270(d):
    return ' '.join(f'{k}={v}' for k, v in d.items())
def _add270(row, add):
    _d = _m270(row)
    for _k, _v in _m270(add).items():
        _d.pop(_k, None); _d[_k] = _v
    _sd = _d.pop('srdiag', None)
    if _sd is not None:
        _d['srdiag'] = _sd
    return _s270(_d)
def _nosr270(row):
    return {k: v for k, v in _m270(row).items() if k != 'srdiag'}
def _diff270(a, b):
    _ma, _mb = _m270(a), _m270(b)
    return {k: v for k, v in _mb.items() if _ma.get(k) != v}
CONFIGS['F8'] = CONFIGS['G4qaxepkS']
assert CONFIGS['F8'] == 'prewarm=1 insp=0 cs=0 tx=1 code=1 srdiag=1 ew=12 ewded=4 ewgas=1000000 ewov=1 pwheavyfirst=4 pwjitpeek=1 pwjitreal=1 reuse=2 reusebal=1 reusechk=0 reusefast=1 reusefb=1 ewredo=4 reusebalsend=1 ixpf=256 ixpfw=1 ewcore=1 ewpool=1 exslice=100 exrt=1 ewnear=0 exio=1 srrt=1 accflt=1 accfltchk=1000 bigra=1 ccv=1 ewinf=1 rdpeek=1 sysn=1 readers=8 rdstop=1 pwmin=32 pwcs=1 pwsync=1 pwstale=1 pwdedup=1 pwnodisc=1 pwk=8 ctd=2 pwnb=0 pwnbval=1 pwnbgas=5000000 pwnbhist=0 pwnbsep=1 pwnbbh=1 pwnbwait=0 pwnbearly=4 pwnbprio=1 pwnblevels=6 pwnbbudget=30000 pwnblvlwait=1000 pwnbnice=10 pwlx=1 pwlxn=4 pwlxmax=512 pwlxc2=1 txdec=1 pwlxbudget=1500 pwlxcnt=1 pwlxbin=1 c2rec=1 pwlxacct=1 pwlxnoself=1 pwlxrd=8 pwlxrdacct=16 pwjitkec=1 fpimp=1 rdpool=1 rdjoinlate=1 logq=1 rdasync=1 excore=1 exsmt=1 exphys=1 exclean=1 rddefer=1 prep=1 rdkick=1 srleafselect=1 rdscratch=1', 'F8 is not the freeze list line (EXP-269 README section 20)'
CONFIGS['F8chk'] = _add270(CONFIGS['F8'], 'reusechk=1 logq=0')   # the driver's pre-check reads the eap block/ew lines, which logq=1 does not write (e270pn-0 stopped there, 11-14 20:13); warm-up only
CONFIGS['F8w'] = _add270(CONFIGS['F8'], 'logq=0')   # warm-up row: the driver's reuse pre-check reads the eap reuse lines of the whole warm-up (e270pn-0 second stop, 11-14 20:2x); as EXP-269's warm-up F7, which has no logq
CONFIGS['P8'] = CONFIGS['G3qxS']
CONFIGS['P8w'] = _add270(CONFIGS['P8'], 'logq=0')
CONFIGS['P8chk'] = _add270(CONFIGS['P8'], 'reusechk=1 logq=0')
assert _m270(CONFIGS['F8'])['reusechk'] == '0' and _m270(CONFIGS['P8'])['reusechk'] == '0'
CONFIGS['U8'] = CONFIGS['U7']
assert CONFIGS['U8'] == CONFIGS['AB1ng'] == CONFIGS['G0']
_G1 = _diff270(CONFIGS['G0'], CONFIGS['G1']); _G2 = _diff270(CONFIGS['G1'], CONFIGS['G2']); _G3 = _diff270(CONFIGS['G2'], CONFIGS['G3'])
_SCHED_X = {'excore': '1', 'exsmt': '1', 'exphys': '1'}; _READ_X = {'srleafselect': '1'}
CONFIGS['H0'] = _add270(CONFIGS['G0'], 'logq=1')
CONFIGS['H1'] = _add270(CONFIGS['H0'], _s270(_G1))
CONFIGS['H2'] = _add270(CONFIGS['H1'], _s270({**_G2, **_SCHED_X}))
CONFIGS['H3'] = _add270(CONFIGS['H2'], _s270({**_G3, **_READ_X}))
_p8 = _nosr270(CONFIGS['P8']); assert _p8.pop('rdscratch') == '1'   # G3qxS carries rdscratch=1, inert without readers (eap.rs 605-606)
assert _nosr270(CONFIGS['H3']) == _p8, ('H3 != P8 without rdscratch', set(_nosr270(CONFIGS['H3']).items()) ^ set(_p8.items()))
_PLANS270 = _diff270(CONFIGS['H3'], CONFIGS['F8'])
assert not {k for k in _m270(CONFIGS['H3']) if k not in _m270(CONFIGS['F8'])}, 'F8 lacks a key of H3'
CONFIGS['H4'] = _add270(CONFIGS['H3'], _s270(_PLANS270))
assert _nosr270(CONFIGS['H4']) == _nosr270(CONFIGS['F8']), 'H4 != F8'
CONFIGS['H5'] = _add270(CONFIGS['H0'], _s270(_PLANS270))
for _k in ('readers', 'tx', 'code', 'pwlx', 'rdpool', 'rdjoinlate', 'rdasync', 'exclean', 'rddefer', 'prep', 'rdkick', 'rdscratch'):
    assert _m270(CONFIGS['H5']).get(_k) == _m270(CONFIGS['F8'])[_k] != '0', ('H5', _k)
for _k in ('excore', 'exsmt', 'exphys', 'ewcore', 'srleafselect'):
    assert _k not in _m270(CONFIGS['H5']), ('H5 must not carry', _k)
CONFIGS['HX'] = _add270(CONFIGS['F8'], 'pwlx=0')
CONFIGS['HC'] = _add270(CONFIGS['F8'], 'nocons=1')
CONFIGS['HXC'] = _add270(CONFIGS['F8'], 'pwlx=0 nocons=1')
assert _m270(CONFIGS['F8'])['pwlx'] == '1' and 'nocons' not in _m270(CONFIGS['F8'])
for _r, _d in (('HX', {'pwlx': '0'}), ('HC', {'nocons': '1'}), ('HXC', {'pwlx': '0', 'nocons': '1'})):
    assert _diff270(CONFIGS['F8'], CONFIGS[_r]) == _d and set(_m270(CONFIGS[_r])) - set(_m270(CONFIGS['F8'])) <= set(_d), _r
CONFIGS['H0n'] = _add270(CONFIGS['H0'], 'prewarm=0')
assert _diff270(CONFIGS['H0'], CONFIGS['H0n']) == {'prewarm': '0'}
# each step adds its own group only, and no step removes a key
for _a, _b, _g in (('H0', 'H1', _G1), ('H1', 'H2', {**_G2, **_SCHED_X}), ('H2', 'H3', {**_G3, **_READ_X}), ('H3', 'H4', _PLANS270)):
    assert _diff270(CONFIGS[_a], CONFIGS[_b]) == _g and set(_m270(CONFIGS[_a])) <= set(_m270(CONFIGS[_b])), (_a, _b)
assert not set(_G1) & set(_G2) and not set(_G2) & set(_G3) and not set(_G1) & set(_G3)
assert {'excore', 'exsmt', 'exphys', 'srleafselect', 'logq'}.isdisjoint(_PLANS270)
assert {'rdasync', 'exclean', 'rddefer', 'prep', 'rdkick', 'rdscratch', 'rdpool', 'rdjoinlate'} <= set(_PLANS270)
PRECHECK = int(os.environ.get('PRECHECK', '0')); PRECHECK_CFG = os.environ.get('PRECHECK_CFG', 'S0M')   # EXP-120
WARM_REUSE_CHECK = int(os.environ.get('WARM_REUSE_CHECK', '1'))   # apply_ckpt290.py (Master 11-02): 0 skips the reuse pre-check at the warm-up's end
PRECHECK_ALT = os.environ.get('PRECHECK_ALT', '')   # EXP-183: configuration of the odd pre-check blocks (empty = none)
LEAD = float(os.environ.get('LEAD', '1.0'))
LEAD_BY_CFG = {k: float(v) for k, v in (x.split('=') for x in os.environ.get('LEAD_BY_CFG', '').split())}   # EXP-195   # EXP-120: seconds between feeding the transactions (or the control file) and newPayload
_missing = [c for c in os.environ.get('SEQ', '').split() + os.environ.get('RUNS3_CFGS', '').split() + list(LEAD_BY_CFG) if c not in CONFIGS]   # EXP-195: every rotated configuration defined before the node starts
if _missing:
    raise SystemExit(f'undefined configurations: {_missing}')
WARM = os.environ.get('WARM', 'S')
# uj3/ui3 (after the ui segment showed slow blocks every third block aligned with the 12-block cycle): filler block after
# every cycle (FILLER: its configuration, empty = none) and the wait after each block at least SETTLE_MIN, at most SETTLE_MAX s
FILLER = os.environ.get('FILLER', '')
SETTLE_MIN = float(os.environ.get('SETTLE_MIN', '0'))
# EXP-199 (Master 10-31, as EXP-204): the minimum wait after a measured block (default SETTLE_MIN); warm-up and pre-check
# blocks keep SETTLE_MIN
SETTLE_MIN_MEASURED = float(os.environ.get('SETTLE_MIN_MEASURED', str(SETTLE_MIN)))
SETTLE_MAX = float(os.environ.get('SETTLE_MAX', '1'))
# EXP-199 (Master 10-31): switches added to every control line of the run (warm-up, pre-check and measured blocks), the
# same for every configuration, e.g. EXP-210's counting-only diagnostics `pwru=1 lkprof=1` (empty: none)
CTRL_ADD = os.environ.get('CTRL_ADD', '').strip()
# apply_srdiag_off.py (EXP-240 / X-028): srdiag as the node takes it from the line it is sent (the configuration plus CTRL_ADD; eap.rs 1041)
def _srdiag_on(line):
    v = [t.split('=', 1)[1] for t in (line + ' ' + CTRL_ADD).split() if t.startswith('srdiag=')]
    try:
        return bool(v) and int(v[-1]) != 0
    except ValueError:
        return False
# EXP-076: with MEASURE=indicator, a block after the warm-up is measured only if one of its raw transactions contains a
# batch-transaction marker (EXP-033 section 11, as in EXP-073 scripts/scan_windows.py); other blocks run with WARM as
# role 'between' (no gate, no settle). The rotation advances over measured blocks only.
MEASURE = os.environ.get('MEASURE', 'all')
MARK = ['06450dee7fd2fb8e39061434babcfc05599a6fb8', '0de8bf93da2f7eecb3d9169422413a9bef4ef628', '931a644c8049babdd91fac0f5e394179569c13f5',
        '845074654f5412915f5c0d76c017c39c800d96a5', 'c2580804', 'cc5cf7cd', 'c6e68c19', '1c560305']


def has_marker(path):
    return any(any(m in t.lower() for m in MARK) for t in json.load(open(path))['payload']['transactions'])
LOADGATE = float(os.environ.get('LOADGATE', '4'))
LOADGATE_MAX = float(os.environ.get('LOADGATE_MAX', '300'))
DEFAULT_SEQ = 'S+r S'


def metrics():
    txt = urllib.request.urlopen('http://127.0.0.1:9001/metrics', timeout=60).read().decode()
    out = {}
    for line in txt.splitlines():
        if line.startswith('#') or not METRIC_KEYS.match(line):
            continue
        k, v = line.rsplit(' ', 1)
        out[k] = float(v)
    return out


PGATE = float(os.environ.get('PGATE', '0'))


def _cpu_times(cpus):
    out = {}
    for line in open('/proc/stat'):
        f = line.split()
        if f[0].startswith('cpu') and f[0][3:].isdigit() and int(f[0][3:]) in cpus:
            v = [int(x) for x in f[1:]]
            out[int(f[0][3:])] = (sum(v), v[3] + v[4])  # total, idle + iowait
    return out


def _tree_ticks(pid):
    """utime+stime (clock ticks) of a process and all its live descendants (EXP-101: the node and, under --jit, its
    compiler child processes)"""
    total = 0; todo = [pid]; seen = set()
    while todo:
        p = todo.pop()
        if p in seen: continue
        seen.add(p)
        try:
            f = stat_fields(f'/proc/{p}/stat'); total += int(f[11]) + int(f[12])
            for t in os.listdir(f'/proc/{p}/task'):
                try:
                    todo.extend(int(c) for c in open(f'/proc/{p}/task/{t}/children').read().split())
                except OSError:
                    pass
        except (OSError, ValueError):
            pass
    return total


# apply_prologue_lean.py (Prologue server, 11-04): modes and the cheaper per-block samples (see the patch's docstring)
LEAN_MODES = [m for m in os.environ.get('LEAN_ROTATE', os.environ.get('LEAN_MODE', 'old')).split(',') if m]
assert LEAN_MODES and all(m in ('old', 'nopre', 'fcu') for m in LEAN_MODES), f'LEAN_MODE/LEAN_ROTATE: {LEAN_MODES}'
LEAN_ROTLEN = int(os.environ.get('LEAN_ROTLEN', '10'))
LEAN_ORIGIN = int(os.environ.get('LEAN_ORIGIN', '0'))   # windows counted from this block (e.g. MEAS_START, to line up with the rows' segments)
LEAN_MCHK = os.environ.get('LEAN_MCHK', '0') == '1'
LEAN_TT_EVERY = int(os.environ.get('LEAN_TT_EVERY', '50'))
_LEAN = {'mode': 'old', 'tt_n': 0, 'tt_pids': None, 'comm': {}, 'last': None}


def lean_mode(n):
    return LEAN_MODES[((n - LEAN_ORIGIN) // LEAN_ROTLEN) % len(LEAN_MODES)]


def _tree_pids(pid):
    # the process and its live descendants, the walk of the original _tree_ticks
    out = []; todo = [pid]; seen = set()
    while todo:
        q = todo.pop()
        if q in seen: continue
        seen.add(q)
        try:
            for th in os.listdir(f'/proc/{q}/task'):
                try:
                    todo.extend(int(c) for c in open(f'/proc/{q}/task/{th}/children').read().split())
                except OSError:
                    pass
            out.append(q)
        except OSError:
            pass
    return out


_tree_ticks_full = _tree_ticks


def _tree_ticks(pid):
    if _LEAN['mode'] == 'old':
        return _tree_ticks_full(pid)
    if _LEAN['tt_pids'] is None or _LEAN['tt_n'] >= LEAN_TT_EVERY or _LEAN['tt_pids'][0] != pid:
        _LEAN['tt_pids'] = _tree_pids(pid) or [pid]; _LEAN['tt_n'] = 0
    _LEAN['tt_n'] += 1
    total = 0
    for q in _LEAN['tt_pids']:
        try:
            f = stat_fields(f'/proc/{q}/stat'); total += int(f[11]) + int(f[12])
        except (OSError, ValueError):
            pass
    return total


def parse_cpus(spec):
    """Prologue server copy: a cpu list as taskset takes it (0-7, 0-15, 0-7,16-23)."""
    out = set()
    for part in spec.split(','):
        a, _, b = part.partition('-')
        out.update(range(int(a), int(b or a) + 1))
    return out


def pcore_busy(dt=1.0, pid=None):
    """Mean busy fraction of the node's cores over dt seconds (EXP-019 gate: other sessions' work is pinned to the
    efficiency cores, so the 1-minute load average no longer says whether the node's cores are free). EXP-101: with pid,
    the CPU time of the node and its descendants in the same window is subtracted, so only other programs count (under
    --jit the node's compiler child processes kept the cores about 125% busy and the gate slept 2 s before every block)."""
    spec = os.environ.get('PGATE_CPUS') or os.environ.get('NODE_CPUS', '0-7')   # apply_w.py: PGATE_CPUS, the gate's set
    cpus = parse_cpus(spec)
    n0 = _tree_ticks(pid) if pid else 0
    t0 = _cpu_times(cpus)
    time.sleep(dt)
    t1 = _cpu_times(cpus)
    n1 = _tree_ticks(pid) if pid else 0
    tot = sum(t1[c][0] - t0[c][0] for c in cpus)
    idle = sum(t1[c][1] - t0[c][1] for c in cpus)
    return max(0.0, (tot - idle) - (n1 - n0)) / tot if tot else 0.0


def loadavg():
    return open('/proc/loadavg').read().strip()


def stat_fields(path):
    s = open(path).read()
    return s[s.rindex(')') + 2:].split()


def io_read_bytes(path):
    try:
        for line in open(path):
            if line.startswith('read_bytes:'):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def thread_sample(pid, tid):
    run_ns, wait_ns, _ = (int(x) for x in open(f'/proc/{pid}/task/{tid}/schedstat').read().split())
    f = stat_fields(f'/proc/{pid}/task/{tid}/stat')
    out = {'cpu_ns': run_ns, 'runq_ns': wait_ns, 'majflt': int(f[9]), 'read_bytes': io_read_bytes(f'/proc/{pid}/task/{tid}/io'),
           'minflt': int(f[7])}   # apply_mem248.py (EXP-248): minor faults, records only
    # apply_pc.py (round p on): migrations and context switches of the thread (/proc/<pid>/task/<tid>/sched)
    try:
        for line in open(f'/proc/{pid}/task/{tid}/sched'):
            k, _, v = line.partition(':')
            k = k.strip()
            if k in ('se.nr_migrations', 'nr_involuntary_switches', 'nr_voluntary_switches'):
                out[{'se.nr_migrations': 'migr', 'nr_involuntary_switches': 'ivcsw', 'nr_voluntary_switches': 'vcsw'}[k]] = int(float(v))
    except OSError:
        pass
    return out


def cpuidle_sample():
    """apply_ci.py (round v on): deep idle entries and residency (us) of the node's cores (NODE_CPUS; 0-7 before the server copy), states 2 and 3 (sysfs, no root)."""
    out = {}
    for c in sorted(parse_cpus(os.environ.get('NODE_CPUS', '0-7'))):
        for s in (2, 3):
            for f, t in (('usage', 'u'), ('time', 't')):
                try:
                    out[f'c{c}s{s}{t}'] = int(open(f'/sys/devices/system/cpu/cpu{c}/cpuidle/state{s}/{f}').read())
                except (OSError, ValueError):
                    pass
    return out


def proc_sample(pid):
    f = stat_fields(f'/proc/{pid}/stat')
    # utime/stime (fields 14/15) include exited threads (reader threads are joined at block end)
    return {'utime_ms': int(f[11]) * 1000 / TICK, 'stime_ms': int(f[12]) * 1000 / TICK, 'majflt': int(f[9]),
            'minflt': int(f[7]),   # apply_mem248.py (EXP-248): minor faults, records only
            'read_bytes': io_read_bytes(f'/proc/{pid}/io'), 'threads': int(f[17])}


def threads_by_name(pid):
    """CPU time (ms, utime+stime) of live threads grouped by thread name with trailing digits removed."""
    out = {}
    tids = os.listdir(f'/proc/{pid}/task')   # apply_prologue_lean.py
    if _LEAN['mode'] != 'old':   # keep only the ids listed now: an exited thread's id taken by a new thread starts afresh
        live = set(tids); _LEAN['comm'] = {k: v for k, v in _LEAN['comm'].items() if k in live}
    for tid in tids:
        try:
            c = _LEAN['comm'].get(tid) if _LEAN['mode'] != 'old' else None   # apply_prologue_lean.py
            if c and c[1] >= 2:
                comm = c[0]
            else:
                comm = open(f'/proc/{pid}/task/{tid}/comm').read().strip()
                if _LEAN['mode'] != 'old':
                    _LEAN['comm'][tid] = (comm, c[1] + 1 if c and c[0] == comm else 1)
            f = stat_fields(f'/proc/{pid}/task/{tid}/stat')
        except OSError:
            continue
        g = re.sub(r'[-_]?\d+$', '', comm) or comm
        out[g] = out.get(g, 0.0) + (int(f[11]) + int(f[12])) * 1000 / TICK
    return out


def find_tid(pid, name):
    for tid in os.listdir(f'/proc/{pid}/task'):
        try:
            if open(f'/proc/{pid}/task/{tid}/comm').read().strip() == name:
                return tid
        except OSError:
            pass
    return None


def write_ctrl(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(text + (' ' + CTRL_ADD if CTRL_ADD else '') + '\n')
    os.replace(tmp, path)


# apply_irq_block.py (X-028): per-block interrupt counts, off unless IRQ_CPUS is set
def _irq_cpus(spec):
    out = set()
    for item in spec.split(','):
        if item.strip():
            lo, _, hi = item.strip().partition('-')
            out.update(range(int(lo), int(hi or lo) + 1))
    return sorted(out)


IRQ_CPUS = _irq_cpus(os.environ.get('IRQ_CPUS', ''))
IRQ_SET = _irq_cpus(os.environ.get('IRQ_SET', os.environ.get('NODE_CPUS', '0-7'))) if IRQ_CPUS else []
_IRQ_NVME = re.compile(r'\b(nvme\d+)q\d+')
_IRQ_NET = re.compile(r'\b(eth|ens|enp|mlx|ena)')


def _irq_kind(irq, desc):
    d = desc.lower()
    m = _IRQ_NVME.search(d)
    if m:
        return m.group(1)
    if 'nvme' in d:
        return 'nvme'
    if 'virtio' in d and ('input' in d or 'output' in d):
        return 'net'
    if _IRQ_NET.search(d):
        return 'net'
    if 'virtio' in d and 'req' in d:
        return 'vblk'
    if irq in ('LOC', 'RES', 'CAL', 'TLB'):
        return irq
    return None


def irq_sample():
    """apply_irq_block.py (X-028): one read of /proc/interrupts summed by kind, per CPU of IRQ_CPUS and over IRQ_SET; {} when off."""
    if not IRQ_CPUS:
        return {}
    try:
        lines = open('/proc/interrupts').read().splitlines()
    except OSError:
        return {}
    ncpu = len(lines[0].split())
    out = {}
    for l in lines[1:]:
        irq, sep, rest = l.partition(':')
        if not sep:
            continue
        toks = rest.split()
        if len(toks) < ncpu or not all(t.isdigit() for t in toks[:ncpu]):
            continue
        nums = [int(t) for t in toks[:ncpu]]
        irq = irq.strip()
        for k in ('all', _irq_kind(irq, ' '.join(toks[ncpu:]))):
            if k is None:
                continue
            for c in IRQ_CPUS:
                if c < ncpu:
                    out[f'{k}_c{c}'] = out.get(f'{k}_c{c}', 0) + nums[c]
            out[f'{k}_set'] = out.get(f'{k}_set', 0) + sum(nums[c] for c in IRQ_SET if c < ncpu)
    return out


# apply_disk257.py (EXP-257): per-block block-device counters, off unless DISK_DEV is set
DISK_DEV = os.environ.get('DISK_DEV', '').strip()
_DISK_FIELDS = ('rd_ios', 'rd_merges', 'rd_sectors', 'rd_ticks', 'wr_ios', 'wr_merges', 'wr_sectors', 'wr_ticks',
                'in_flight', 'io_ticks', 'time_in_queue')


def disk_sample():
    """apply_disk257.py (EXP-257): one read of /sys/class/block/DISK_DEV/stat; {} when off or unreadable."""
    if not DISK_DEV:
        return {}
    try:
        v = [int(x) for x in open(f'/sys/class/block/{DISK_DEV}/stat').read().split()]
    except (OSError, ValueError):
        return {}
    return dict(zip(_DISK_FIELDS, v))


def delta(a, b):
    return {k: b[k] - a.get(k, 0.0) for k in b}


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def history_check():
    if os.environ.get('CKPT_BIN'):   # apply_v290.py (reth 2.9.0 binaries, Master 11-02): the binary that reads the prune checkpoints
        return subprocess.run(['bash', '-c', 'source ' + os.path.join(HERE, 'history_window.sh') + '; check_history_window_bin "$CKPT_BIN"'],
                              capture_output=True, text=True)
    return subprocess.run(['bash', '-c', 'source "$PROLOGUE_NODE_HOME/engine-replay/node-common.sh"; check_history_window'],
                          capture_output=True, text=True)


def main():
    label, binary, n_measured, blocks, out_dir, warmup = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5], int(sys.argv[6])
    extra = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    seq = os.environ.get('SEQ', DEFAULT_SEQ).split()
    settle = float(os.environ.get('SETTLE', '1'))   # EXP-101: 1 s (was 2 s)
    os.makedirs(out_dir, exist_ok=True)
    eap_ctrl = os.environ['EAP_CTRL_FILE']
    write_ctrl(eap_ctrl, 'tag=0 ' + CONFIGS[WARM])
    meta = {'label': label, 'binary': binary, 'binary_sha256': sha(binary), 'warmup': warmup, 'n_measured': n_measured, 'seq': seq,
            'configs': CONFIGS, 'extra_args': extra, 'load_before': loadavg(), 't_start': time.time(), 'toml_sha_before': sha(TOML),
            'node_env': os.environ.get('NODE_ENV', ''), 'node_cpus': os.environ.get('NODE_CPUS', '0-7'), 'pgate_cpus': os.environ.get('PGATE_CPUS', ''), 'ctrl_add': CTRL_ADD, 'driver_cpus': sorted(os.sched_getaffinity(0))}
    node_log = os.path.abspath(os.path.join(out_dir, f'{label}.node.log'))
    meta['node_log'] = node_log
    env = dict(os.environ, NODE_LOG=node_log)
    r = subprocess.run([os.path.join(HERE, 'start_node.sh'), binary, *extra], env=env, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'start_node.sh rc={r.returncode}: {r.stderr}')
    pid = int(r.stdout.split()[-1])
    meta['pid'] = pid
    # uj3/ui3: SIGTERM ends the run like SIGINT (KeyboardInterrupt), so the finally below always stops the node
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if os.environ.get('NODE_CG_CHECK') == '1':   # apply_mem248.py (EXP-248): the node in the run's scope, as the driver
            cg_self, cg_node = open('/proc/self/cgroup').read().strip(), open(f'/proc/{pid}/cgroup').read().strip()
            meta['node_cgroup'] = cg_node
            if cg_node != cg_self:
                sys.exit(f'NODE_CG_CHECK: the node is in {cg_node}, the driver in {cg_self}')
        started(label, blocks, out_dir, warmup, n_measured, seq, settle, eap_ctrl, meta, pid, node_log)
    finally:
        # 2026-10-18 board rule: stop the node before any exit, also after an exception
        stop_node(pid, meta, out_dir, label)


def started(label, blocks, out_dir, warmup, n_measured, seq, settle, eap_ctrl, meta, pid, node_log):
    http = R.Rpc('http://127.0.0.1:8545')
    for _ in range(600):
        try:
            head = int(http.call('eth_blockNumber', [])[0], 16)
            break
        except Exception:
            if not os.path.exists(f'/proc/{pid}'):
                sys.exit('node exited during start; see ' + node_log)
            time.sleep(1)
    else:
        sys.exit('node did not come up')
    time.sleep(5)
    tid = find_tid(pid, 'engine')
    head = int(http.call('eth_blockNumber', [])[0], 16)
    start = head + 1
    # EXP-094: do not run into the blocks of an earlier experiment that stopped early (MIN_HEAD: its last block)
    if head < int(os.environ.get('MIN_HEAD', '0')):
        sys.exit(f"node head {head} below MIN_HEAD {os.environ['MIN_HEAD']}")
    # EXP-120: the segment starts right after a block fixed by the Master (EXACT_HEAD): refuse to run from any other head
    if os.environ.get('EXACT_HEAD') and head != int(os.environ['EXACT_HEAD']):
        sys.exit(f"node head {head} is not EXACT_HEAD {os.environ['EXACT_HEAD']}")
    # FFWD_TO (EXP-033 second confirmation): blocks below it are executed first with the warm-up configuration and
    # recorded with role 'ffwd' (advance only, not measured), then the warm-up and measured blocks follow
    ffwd = max(0, int(os.environ.get('FFWD_TO', '0')) - start)
    meta['ffwd_blocks'] = ffwd
    warmup += ffwd
    n_fill = (n_measured // len(seq)) * int(os.environ.get('NFILL', '1')) if FILLER else 0   # uj3/ui3: NFILL filler blocks after every full rotation cycle (EXP-146)
    meta['n_filler'] = n_fill
    end = start + warmup + n_measured + n_fill - 1
    # EXP-189: with the stratified rotation the segment's last block is fixed (END_BLOCK); the counts follow from the schedule
    if os.environ.get('END_BLOCK'):
        end = int(os.environ['END_BLOCK'])
    # EXP-122 second segment (Master 2026-10-21): refuse to run into another experiment's range (no block is sent)
    if os.environ.get('MAX_END') and end > int(os.environ['MAX_END']):
        sys.exit(f"segment would end at {end}, above MAX_END {os.environ['MAX_END']}: refusing to run (head {head})")
    meta.update(engine_tid=tid, head_at_start=head, start=start, end=end, affinity=sorted(os.sched_getaffinity(pid)))
    missing = [n for n in range(start, end + 1) if not os.path.exists(os.path.join(blocks, f'{n}.json'))]
    if missing:
        sys.exit(f'missing block files, e.g. {missing[:3]}')
    secret = bytes.fromhex(open(os.path.join(os.environ['PROLOGUE_NODE_HOME'], 'data', 'jwt.hex')).read().strip().removeprefix('0x'))
    engine = R.Rpc('http://127.0.0.1:8551', secret)
    hashes = {head: http.call('eth_getBlockByNumber', [hex(head), False])[0]['hash']}
    print(json.dumps({k: v for k, v in meta.items() if k != 'configs'}), flush=True)
    run_blocks(label, out_dir, blocks, start, end, ffwd, warmup, seq, eap_ctrl, engine, http, hashes, head, meta, pid, tid, settle)


def feed_txpool(http_url, txs):
    """EXP-120: send the block's raw transactions to the node's pool in one JSON-RPC batch (block order; blob
    transactions skipped: they need sidecars). Returns (sent, accepted, rejected, {error: count})."""
    reqs = []; skipped = 0
    for i, t in enumerate(txs):
        if t.startswith('0x03'):
            skipped += 1; continue
        reqs.append({'jsonrpc': '2.0', 'id': i, 'method': 'eth_sendRawTransaction', 'params': [t]})
    if not reqs:
        return {'sent': 0, 'skipped': skipped, 'accepted': 0, 'rejected': 0, 'errors': {}, 'ms': 0.0}
    t0 = time.monotonic()
    req = urllib.request.Request(http_url, data=json.dumps(reqs).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.load(r)
    errors = {}; acc = 0
    for x in body:
        if 'error' in x:
            m = re.sub(r'0x[0-9a-fA-F]+|\d+', '#', str(x['error'].get('message', x['error'])))[:80]
            errors[m] = errors.get(m, 0) + 1
        else:
            acc += 1
    return {'sent': len(reqs), 'skipped': skipped, 'accepted': acc, 'rejected': len(reqs) - acc, 'errors': errors, 'ms': (time.monotonic() - t0) * 1e3}


def precheck_heavy(node_log, k, blocks=None):
    """EXP-141: the last k 'eap block' lines must show heavy transactions prewarmed on the dedicated threads (pw_heavy_txs >= 1 in
    at least k // 2 blocks) and no panic."""
    lines = []
    for _ in range(6):
        all_lines = [l for l in open(node_log, errors='replace') if ' eap block ' in l]
        panic = any('panicked' in l for l in open(node_log, errors='replace'))
        lines = [l for l in all_lines if blocks is None or any(f' tag={b} ' in l for b in blocks)][-k:]
        if len(lines) >= k: break
        time.sleep(0.5)
    if panic: return False, 'panic in node log'
    if len(lines) < k - 1: return False, f'only {len(lines)} eap block lines'   # EXP-183: the last line may be unflushed
    def f(l, key):
        m = re.search(r'\b' + key + r'=(\d+)', l)
        return int(m.group(1)) if m else 0
    hv = [f(l, 'pw_heavy_txs') for l in lines]; wait = [f(l, 'pw_heavy_wait_us') for l in lines]
    # EXP-183 (Master 10-26): the share of blocks with heavy transactions depends on the blocks: reported only
    why = (f'heavy busy blocks={sum(1 for x in hv if x >= 1)}/{len(lines)} (reported, expected >= {k // 2 + 1}); '
           f'pw_heavy_txs={hv} pw_heavy_wait_us={wait}')
    return True, why


def precheck_split(node_log, k, blocks):
    """EXP-169: in the k pre-check blocks (PC: pwsplit=4 sysn=1), no panic; split helpers ran element runs (an 'eap split
    exit' line with runs >= 1) in at least k // 6 blocks; every block that dispatched elements has its helpers' exit lines; an
    'eap sysn' line with 5 slots (inserted + cached) in at least k - 2 blocks."""
    def f(l, key):
        m = re.search(r'\b' + key + r'=(\d+)', l)
        return int(m.group(1)) if m else 0
    bs = set(blocks)
    for _ in range(8):   # the helpers' exit lines can follow the block's other lines
        lines = list(open(node_log, errors='replace'))
        panic = any('panicked' in l for l in lines)
        disp = {f(l, 'block'): f(l, 'elements') for l in lines if 'eap split dispatch' in l and f(l, 'block') in bs}
        runs = {}
        for l in lines:
            if 'eap split exit' in l and f(l, 'block') in bs:
                runs.setdefault(f(l, 'block'), []).append(f(l, 'runs'))
        sysn = {f(l, 'block'): f(l, 'inserted') + f(l, 'cached') for l in lines if 'eap sysn' in l and f(l, 'block') in bs}
        if len(disp) >= k - 1 and all(len(runs.get(b, [])) == 4 for b in disp):
            break
        time.sleep(0.5)
    with_runs = sum(1 for b, r in runs.items() if sum(r) >= 1)
    why = (f'split_dispatch_blocks={len(disp)} elements={sum(disp.values())} blocks_with_runs={with_runs} '
           f'exit_lines={sum(len(r) for r in runs.values())} sysn_blocks={sum(1 for v in sysn.values() if v == 5)}')
    if panic: return False, 'panic in node log; ' + why
    if with_runs < k // 6: return False, 'too few blocks with element runs: ' + why
    if any(len(runs.get(b, [])) != 4 for b, e in disp.items()): return False, 'missing split helper exit lines: ' + why
    if sum(1 for v in sysn.values() if v == 5) < k - 2: return False, 'next-block slots not read: ' + why
    return True, why


def precheck_nb(node_log, k, blocks=None):
    """EXP-122: the last k "eap block" lines of the node log for the non-blocking pass. Stops on a panic in the log or
    fewer than k lines; the quantities (history passes, second-level passes, blocks with passes, blocks with passes and no
    new keys, share of successful passes, time per block) are reported only (EXP-199, Master 10-31: pre-checks stop only
    on conditions the code guarantees)."""
    lines = []
    for _ in range(6):   # the line of the last block may not be flushed yet
        try:
            all_lines = [l for l in open(node_log, errors='replace') if ' eap block ' in l]
            panic = any('panicked' in l for l in open(node_log, errors='replace'))
        except OSError as e:
            return False, f'cannot read node log: {e}'
        lines = [l for l in all_lines if blocks is None or any(f' tag={b} ' in l for b in blocks)][-k:]
        if len(lines) >= k:
            break
        time.sleep(0.5)
    if panic:
        return False, 'panic in node log'
    if len(lines) < k:
        return False, f'only {len(lines)} eap block lines'
    def f(l, key):
        m = re.search(r'\b' + key + r'=(\d+)', l)
        return int(m.group(1)) if m else 0
    txs = [f(l, 'nb_txs') for l in lines]; keys = [f(l, 'nb_keys') for l in lines]; oks = [f(l, 'nb_ok') for l in lines]; us = [f(l, 'nb_us') for l in lines]
    with_pass = [i for i in range(k) if txs[i] >= 1]
    bh = [f(l, 'nb_bh_runs') for l in lines]; sites = [f(l, 'nb_bh_sites') for l in lines]; waits = [f(l, 'nb_wait_hit') for l in lines]
    why = f'nb_txs={txs} nb_keys={keys} nb_ok={oks} nb_us={us} nb_bh_runs={bh} nb_bh_sites={sites} nb_wait_hit={waits}'
    # EXP-199 (Master 10-31): every item below is a quantity, not a condition the code guarantees, so it is reported only;
    # the run stops above on a panic or on missing 'eap block' lines (the other pre-checks keep their guaranteed items)
    rep = []
    # EXP-129: the history pass runs after the block's stats line, so its counters are cumulative (nb_bh_runs = passes so far,
    # nb_bh_sites = size of the history table at the time of the line)
    if 'pwnbbh=1' in CONFIGS.get(PRECHECK_CFG, ''):
        rep.append(f'history_runs_last={bh[-1]} (expected >= {max(1, k - 2)}) sites_last={sites[-1]}')
    # EXP-129 third segment: passes beyond the first level
    lv = [f(l, 'nb_levels') for l in lines]
    if 'pwnblevels=' in CONFIGS.get(PRECHECK_CFG, ''):
        rep.append(f'blocks_with_second_level={sum(1 for i in with_pass if lv[i] >= 1)}/{len(with_pass)} (expected >= {len(with_pass) // 2 + 1})')
    rep.append(f'blocks_with_passes={len(with_pass)}/{k} (expected >= {k // 2})')
    # under EAP's own prewarm mechanism a pass issues only slots not yet cached; when the workers or the plans' readers have
    # read every slot it reaches, or the pass is skipped because the execution thread has passed the transaction, none
    rep.append(f'blocks_with_passes_no_new_keys={sum(1 for i in with_pass if keys[i] == 0)}/{len(with_pass)}')
    rep.append(f'passes_ok={sum(oks)}/{sum(txs)} (expected >= 1/3)')
    rep.append(f'max_nb_us={max(us)} (expected <= 200000)')
    return True, why + ' (reported: ' + ', '.join(rep) + ')'

def helper_nices(node_log, block):
    """EXP-180: nice values of the speculative-pass helper threads of `block` (`eap nb helper` lines of eap-x180)."""
    out = []
    try:
        for l in open(node_log, errors='replace'):
            if 'eap nb helper' in l and re.search(r'\bblock=' + str(block) + r'\b', l):
                mt = re.search(r'\bnice=(-?\d+)', l)
                if mt:
                    out.append(int(mt.group(1)))
    except OSError:
        pass
    return out


def precheck_val(node_log, k, blocks):
    """EXP-180 (README 7.2), copied unchanged: the speculative passes of the pre-check configuration work: no panic; passes in
    at least k // 2 blocks; predicted reads (nb_val_reads > 0) in at least half of the blocks with passes; keys handed out in
    every block with predicted reads (nb_val_reads > 0 => nb_keys > 0; EXP-180 4bb536b8 after the 08:02 pre-check of v1, which
    stopped on three blocks whose passes read only cached keys and so had nothing to hand out); at least one pass cut short (nb_val_aborted > 0, the in-pass abort works); the history pass runs
    and the site table is filled by the last block (nb_bh_runs >= k - 2, nb_sites > 0); the helpers' nice values equal
    pwnbnice of the configuration in every pre-check block that has `eap nb helper` lines, and such lines exist in at least
    k // 2 blocks."""
    lines = []
    for _ in range(6):
        try:
            all_lines = [l for l in open(node_log, errors='replace') if ' eap block ' in l]
            panic = any('panicked' in l for l in open(node_log, errors='replace'))
        except OSError as e:
            return False, f'cannot read node log: {e}'
        lines = [l for l in all_lines if any(f' tag={b} ' in l for b in blocks)][-k:]
        if len(lines) >= k:
            break
        time.sleep(0.5)
    if panic:
        return False, 'panic in node log'
    if len(lines) < k - 1:   # EXP-183: the last line may be unflushed
        return False, f'only {len(lines)} eap block lines'
    def f(l, key):
        m = re.search(r'\b' + key + r'=(\d+)', l)
        return int(m.group(1)) if m else 0
    txs = [f(l, 'nb_txs') for l in lines]; keys = [f(l, 'nb_keys') for l in lines]; val = [f(l, 'nb_val_reads') for l in lines]
    ab = [f(l, 'nb_val_aborted') for l in lines]; us = [f(l, 'nb_us') for l in lines]; bh = [f(l, 'nb_bh_runs') for l in lines]
    sites = [f(l, 'nb_sites') for l in lines]
    with_pass = [i for i in range(len(lines)) if txs[i] >= 1]
    want = int(re.search(r'pwnbnice=(\d+)', CONFIGS[PRECHECK_CFG]).group(1)) if 'pwnbnice=' in CONFIGS[PRECHECK_CFG] else 0
    nices = {b: helper_nices(node_log, b) for b in blocks}
    with_nice = [b for b, v in nices.items() if v]
    bad_nice = {b: v for b, v in nices.items() if any(x != want for x in v)}
    why = (f'blocks with passes {len(with_pass)}/{k}; nb_val_reads>0 in {sum(1 for i in with_pass if val[i] > 0)}; aborted {sum(ab)}; '
           f'max nb_us {max(us)}; nb_bh_runs last {bh[-1]}; nb_sites last {sites[-1]}; helper nice lines in {len(with_nice)} blocks, wrong {len(bad_nice)} (want {want})')
    # EXP-183 (Master 10-26): only the helpers' nice value is guaranteed by the code (every helper line of a block carries
    # pwnbnice); the rest depends on the blocks and the passes and is reported, with the condition EXP-180 used
    rep_ = [f'passes in >= {k // 2} blocks: {len(with_pass) >= k // 2}',
            f'predicted reads in >= half of the blocks with passes: {sum(1 for i in with_pass if val[i] > 0) >= len(with_pass) // 2 + 1}',
            f'every block with predicted reads handed out keys: {not any(keys[i] == 0 for i in with_pass if val[i] > 0)}',
            f'a pass cut short: {sum(ab) > 0}', f'history passes >= {max(1, k - 2)} and site table filled: {bh[-1] >= max(1, k - 2) and sites[-1] > 0}',
            f'helper lines in >= {k // 2} blocks: {len(with_nice) >= k // 2}', f'max nb_us <= 400 ms: {max(us) <= 400_000}']
    why += ' (reported: ' + ', '.join(rep_) + ')'
    if bad_nice:
        return False, 'helper nice check failed: ' + why + f' {dict(list(bad_nice.items())[:3])}'
    return True, why


def precheck_heavyfirst(node_log, k, blocks):
    """EXP-179, copied unchanged: the last k pre-check blocks must have an 'eap heavyfirst' line with at least one picked
    transaction in at least k // 2 + 1 blocks (blocks with fewer than 30 transactions or no transaction of 1M gas limit pick
    none), and no panic."""
    time.sleep(0.5)
    lines = [l for l in open(node_log, errors='replace') if 'eap heavyfirst tag=' in l and any(f'tag={b} ' in l for b in blocks)]
    panic = any('panicked' in l for l in open(node_log, errors='replace'))
    if panic: return False, 'panic in node log'
    picked = [l.split('picked=')[1].split()[0] for l in lines]
    have = sum(1 for p in picked if p and not p.startswith('first_us='))
    # EXP-183 (Master 10-26): picks depend on the blocks (fewer than 30 transactions or none of 1M gas limit pick none): reported
    why = f'heavyfirst lines={len(lines)} with picks={have} (reported, expected >= {k // 2 + 1})'
    return True, why


def precheck_sr(node_log, k, blocks):
    """EXP-182: an `eap sr` line (srdiag=1, eap-x181 sr_root_done) for at least k - 1 pre-check blocks (the last block's line
    may still be unflushed), with the state-root task's times (finished_marker_us, root_us not both 0) and proof worker
    threads found (proof_threads > 0) in at least k - 2 blocks."""
    time.sleep(0.5)
    bs = set(blocks); sr = {}
    for l in open(node_log, errors='replace'):
        if 'eap sr' in l and 'finish_us=' in l and (mb := re.search(r'\bblock=(\d+)', l)) and int(mb.group(1)) in bs:
            sr[int(mb.group(1))] = dict(re.findall(r'\b(\w+)=(-?\d+)', l))
    timed = sum(1 for v in sr.values() if v.get('finished_marker_us', '0') != '0' or v.get('root_us', '0') != '0')
    thr = sum(1 for v in sr.values() if int(v.get('proof_threads', 0)) > 0)
    why = f'sr lines={len(sr)}/{k} with task times={timed} with proof threads={thr}'
    return (len(sr) >= k - 1 and timed >= k - 2 and thr >= k - 2), why


def sr_line(node_log, block):
    """EXP-182: the fields of the `eap sr` line of `block` ({} when there is none)."""
    out = {}
    try:
        for l in open(node_log, errors='replace'):
            if 'eap sr' in l and 'finish_us=' in l and re.search(r'\bblock=' + str(block) + r'\b', l):
                out = dict(re.findall(r'\b(\w+)=([\w.\-]+)', l))
    except OSError:
        pass
    return out


def precheck_srtx(node_log, k, blocks, ntx):
    """EXP-182 (X-017's rule for srtx=1, Master 10-26: conditions on every block only where they must hold): every `eap sr`
    line found (at least k - 1, see precheck_sr) has srtx=true; in every block srtx_msgs <= ceil(srtx_txs / 32) (aa758af: the
    last batch is not sent when the dispatch was told to stop) and srtx_txs is at most the block's transaction count; at least
    90% of the blocks with 10 or more transactions hand out at least one transaction and one account (srtx_txs >= 1,
    srtx_accts >= 1; a block whose transactions the execution thread passed before the prewarm dispatched them hands out
    none, so this cannot be required of every block). Reports the blocks with srtx_msgs < ceil(srtx_txs / 32)."""
    bs = set(blocks); sr = {}
    for l in open(node_log, errors='replace'):
        if 'eap sr' in l and 'finish_us=' in l and (mb := re.search(r'\bblock=(\d+)', l)) and int(mb.group(1)) in bs:
            sr[int(mb.group(1))] = dict(re.findall(r'\b(\w+)=([\w.\-]+)', l))
    g = lambda d, key: int(d.get(key, '0')) if d.get(key, '0').isdigit() else -1   # noqa: E731
    on = sum(1 for v in sr.values() if v.get('srtx') == 'true')
    bad = [b for b in sr if not (0 <= g(sr[b], 'srtx_msgs') <= -(-g(sr[b], 'srtx_txs') // 32) and 0 <= g(sr[b], 'srtx_txs') <= ntx.get(b, 0))]
    withtx = [b for b in sr if ntx.get(b, 0) >= 10]
    covered = [b for b in withtx if g(sr[b], 'srtx_txs') >= 1 and g(sr[b], 'srtx_accts') >= 1]
    short = sum(1 for b in sr if b not in bad and g(sr[b], 'srtx_msgs') < -(-g(sr[b], 'srtx_txs') // 32))
    why = (f'srtx lines={len(sr)}/{k} srtx_true={on} blocks_with_10_txs={len(withtx)} handing_out={len(covered)} bad={len(bad)} last_batch_dropped={short} '
           f'srtx_txs={sum(g(v, "srtx_txs") for v in sr.values())} srtx_accts={sum(g(v, "srtx_accts") for v in sr.values())} '
           f'srtx_slots={sum(g(v, "srtx_slots") for v in sr.values())} srtx_msgs={sum(g(v, "srtx_msgs") for v in sr.values())}'
           + (f' first bad {bad[:3]} {[sr[b] for b in bad[:1]]}' if bad else ''))
    return (len(sr) >= k - 1 and on == len(sr) and not bad and len(covered) >= 0.9 * len(withtx)), why


GUARD_POS = [0]
GUARD = {}   # block -> stale_fills of its `eap cache guard` line (fills dropped since the previous block's writes were applied)


def guard_check(node_log, sched, n):
    """EXP-182 (Master 10-26, rules (a)-(c) of README section 5.3): a block's `eap cache guard` stale_fills counts the cache
    fills dropped because they came after the previous block's writes (threads of the previous block or earlier that ran
    past its cache save). (a) When the previous block's configuration joins its readers (no rdjoinlate=1), stale_fills > 0
    means a cache-filling thread was not joined before the save: the run stops. (b) After a block with rdjoinlate=1 the
    count is expected (its readers' last reads end after the save and are dropped) and only recorded."""
    try:
        with open(node_log, errors='replace') as f:
            f.seek(GUARD_POS[0])
            data = f.read()
            GUARD_POS[0] = f.tell()
    except OSError:
        return
    for l in data.splitlines():
        if 'eap cache guard' not in l:
            continue
        mb = re.search(r'\bblock=(\d+)', l); ms = re.search(r'\bstale_fills=(\d+)', l)
        if not (mb and ms):
            continue
        b, k = int(mb.group(1)), int(ms.group(1))
        GUARD[b] = k
        prev = sched.get(b - 1)
        late = prev is not None and 'rdjoinlate=1' in CONFIGS.get(prev[1], '')
        if k > 0 and not late:
            raise SystemExit(f'stale fills without rdjoinlate: block {b} stale_fills={k} after block {b - 1} ({prev[1] if prev else "?"}; checked after block {n})')


def precheck_late(node_log, blocks):
    """EXP-182 (Master 10-26): with rdjoinlate=1 every pre-check block's readers are joined at the next block's start: an
    `eap late readers` line for every pre-check block but the last (its line comes with the first block after the pre-check;
    one more may still be unflushed when the check runs);
    reports the threads still running then and the late joins' time, and the stale fills of the blocks after them (rule (b),
    recorded only)."""
    lines = {}
    for l in open(node_log, errors='replace'):
        if 'eap late readers' in l and (mb := re.search(r'\bblock=(\d+)', l)):
            lines[int(mb.group(1))] = dict(re.findall(r'\b(\w+)=(\d+)', l))
    want = blocks[:-1]
    have = [b for b in want if b in lines]
    run = [int(lines[b].get('running', 0)) for b in have]; js = sorted(int(lines[b].get('join_us', 0)) for b in have)
    st = [GUARD.get(b + 1, 0) for b in have]
    why = (f'late join lines={len(have)}/{len(want)} running_sum={sum(run)} running_max={max(run) if run else -1} '
           f'late_join_us_median={js[len(js) // 2] if js else -1} late_join_us_max={js[-1] if js else -1} '
           f'stale_fills_after(sum/max)={sum(st)}/{max(st) if st else -1}')
    return len(have) >= len(want) - 1, why


def precheck_rdpool(node_log, k, blocks):
    """EXP-183: with rdpool=1 every pre-check block's `eap block` line has rdpool=true (at least k - 1 lines: the last may be
    unflushed), and at the last line the pool has 8 to 64 threads; overflow and nice_unpooled are reported."""
    bs = set(blocks); lines = {}
    for l in open(node_log, errors='replace'):
        if ' eap block ' in l and (mt := re.search(r' tag=(\d+) ', l)) and int(mt.group(1)) in bs:
            lines[int(mt.group(1))] = dict(re.findall(r'\b(\w+)=([\w.\-]+)', l))
    on = sum(1 for v in lines.values() if v.get('rdpool') == 'true')
    last = lines[max(lines)] if lines else {}
    th = int(last.get('rdpool_threads', 0) or 0)
    why = (f'rdpool lines={len(lines)}/{k} rdpool_true={on} pool_threads={th} busy_peak={last.get("rdpool_busy_peak")} '
           f'overflow={last.get("rdpool_overflow")} nice_unpooled={last.get("rdpool_nice_unpooled")}')
    # EXP-183 (Master 10-26): at most RDPOOL_MAX = 64 threads and at least one are guaranteed; 8 or more is expected (8 readers
    # submitted at each block start) and reported
    why += f' (reported: pool_threads >= 8: {th >= 8})'
    return (len(lines) >= k - 1 and on == len(lines) and 1 <= th <= 64), why


def precheck_split183(node_log, k, blocks):
    """EXP-183 (rewritten after h1's second attempt, Master 10-26): with pwsplit and pwsplitmin the dispatch writes an
    `eap split dispatch` line in every block (txs = the entries selected, at least pwsplitmin elements each) and starts its
    pwsplit helper threads at the first selected entry only (eap-x183 prewarm.rs; test helpers_start_at_first_selected_entry_and_join).
    Guaranteed and required: an `eap prewarm join` line for at least k - 1 pre-check blocks; in a block whose dispatch line has
    txs > 0, split_threads = 4 and 4 `eap split exit` lines; in a block whose dispatch line has txs = 0, split_threads = 0 and no
    exit line; no panic. Reported: the blocks with a selected entry (may be 0 in 100 blocks). (The first version took every
    block with a dispatch line as one with a selected entry and stopped h1 with 99 mismatches.)"""
    bs = set(blocks)
    def f(l, key):
        m = re.search(r'\b' + key + r'=(\d+)', l)
        return int(m.group(1)) if m else 0
    for _ in range(8):   # the helpers' exit lines can follow the block's other lines
        lines = list(open(node_log, errors='replace'))
        join = {f(l, 'block'): f(l, 'split_threads') for l in lines if 'eap prewarm join' in l and f(l, 'block') in bs}
        disp = {f(l, 'block'): f(l, 'txs') for l in lines if 'eap split dispatch' in l and f(l, 'block') in bs}
        exits = collections.Counter(f(l, 'block') for l in lines if 'eap split exit' in l and f(l, 'block') in bs)
        if all(exits.get(b, 0) == 4 for b, t in disp.items() if t > 0):
            break
        time.sleep(0.5)
    panic = any('panicked' in l for l in lines)
    sel = {b for b, t in disp.items() if t > 0}
    bad_val = [b for b, v in join.items() if v not in (0, 4)]
    bad_match = [b for b, v in join.items() if b in disp and (v == 4) != (b in sel)]
    bad_exit = [b for b in disp if exits.get(b, 0) != (4 if b in sel else 0)]
    why = (f'split join lines={len(join)}/{k} dispatch lines={len(disp)} blocks with a selected entry={len(sel)} (reported) '
           f'split_threads_not_0_or_4={len(bad_val)} threads_vs_selection_mismatch={len(bad_match)} exit_lines_mismatch={len(bad_exit)}')
    return (not panic and len(join) >= k - 1 and not bad_val and not bad_match and not bad_exit), why


def precheck_interp183(node_log, k, blocks, sched):
    """EXP-183 (Master 10-26): the pre-check alternates the configuration with pwnbinterp=1 (PRECHECK_CFG) and without it
    (PRECHECK_ALT). Asks: at least k - 1 `eap block` lines, each showing pwnbinterp=true in the blocks of PRECHECK_CFG and
    false in the others; nb_sites at the last line larger than at the first. Reported only (Master 10-26, after h1's first
    attempt): nb_steps / nb_txs per half and its factor, nb_val_site / nb_val_reads per half; per block in each half nb_val_reads,
    nb_val_site, nb_val_aborted, nb_steps, nb_txs, nb_us."""
    bs = set(blocks); lines = {}
    for _ in range(6):
        for l in open(node_log, errors='replace'):
            if ' eap block ' in l and (mt := re.search(r' tag=(\d+) ', l)) and int(mt.group(1)) in bs:
                lines[int(mt.group(1))] = dict(re.findall(r'\b(\w+)=([\w.\-]+)', l))
        if len(lines) >= k:
            break
        time.sleep(0.5)
    on = [b for b in sorted(lines) if sched[b][1] == PRECHECK_CFG]; off = [b for b in sorted(lines) if sched[b][1] == PRECHECK_ALT]
    g = lambda b, key: int(lines[b].get(key, 0) or 0)   # noqa: E731
    bad_flag = [b for b in on if lines[b].get('pwnbinterp') != 'true'] + [b for b in off if lines[b].get('pwnbinterp') != 'false']
    srt = sorted(lines)
    grow = g(srt[-1], 'nb_sites') - g(srt[0], 'nb_sites') if srt else 0
    tot = lambda bl, key: sum(g(b, key) for b in bl)   # noqa: E731
    q_on = tot(on, 'nb_val_site') / tot(on, 'nb_val_reads') if tot(on, 'nb_val_reads') else float('nan')
    q_off = tot(off, 'nb_val_site') / tot(off, 'nb_val_reads') if tot(off, 'nb_val_reads') else float('nan')
    per = lambda bl, key: tot(bl, key) / len(bl) if bl else float('nan')   # noqa: E731
    st_on = tot(on, 'nb_steps') / tot(on, 'nb_txs') if tot(on, 'nb_txs') else float('nan')
    st_off = tot(off, 'nb_steps') / tot(off, 'nb_txs') if tot(off, 'nb_txs') else float('nan')
    why = (f'interp lines={len(lines)}/{k} on={len(on)} off={len(off)} flag_wrong={len(bad_flag)} nb_sites_growth={grow} '
           f'steps/pass on={st_on:.0f} off={st_off:.0f} factor={st_on / st_off if st_off else float("nan"):.2f} (reported); site/val_reads on={q_on:.3f} off={q_off:.3f} (reported); per block on/off: val_reads {per(on, "nb_val_reads"):.1f}/{per(off, "nb_val_reads"):.1f} '
           f'val_site {per(on, "nb_val_site"):.1f}/{per(off, "nb_val_site"):.1f} steps {per(on, "nb_steps"):.0f}/{per(off, "nb_steps"):.0f} aborted {per(on, "nb_val_aborted"):.2f}/{per(off, "nb_val_aborted"):.2f} '
           f'nb_txs {per(on, "nb_txs"):.2f}/{per(off, "nb_txs"):.2f} nb_us {per(on, "nb_us"):.0f}/{per(off, "nb_us"):.0f}')
    ok = len(lines) >= k - 1 and on and off and not bad_flag and grow > 0
    return bool(ok), why


def precheck_cd184(node_log, k, blocks, ntx):
    """EXP-184 (README section 7; Master 10-26: stop only on conditions the code guarantees with the feature on, report
    every quantity): the `eap cdaddr` lines of the pre-check blocks (configuration with cdaddr and cdst on). Stops when a
    pre-check block has no line (BlockPrefetch exists whenever cdaddr or cdst is on, and its drop writes the line), when a
    line's switches differ from the configuration's, when a block with transactions issued no sender or recipient (cdst
    issues at least the first transaction's sender in a fresh record), when done + unfinished differs from the issued
    count (the summary counts each issued address once), when a line reports complete=false (the execution of a valid
    block completes), or when the learning table shrinks from one pre-check block to the next (it only grows). Reported:
    candidates, readable candidates, issued, limited, reads from the backend, used and in time, wrong reads, end_us."""
    cfg = CONFIGS[PRECHECK_CFG]
    want = {k2: v for k2, v in (t.split('=') for t in cfg.split()) if k2 in ('cdaddr', 'cdrate', 'cdmin', 'cdratio')}
    want_st = ' cdst=1' in cfg
    want_learn = ' cdlearn=1' in cfg   # c2
    lines = {}
    for l in open(node_log, errors='replace'):
        if 'eap cdaddr' not in l:
            continue
        d = dict(re.findall(r'\b(\w+)=(\w+)', l))
        if d.get('block', '').isdigit() and int(d['block']) in blocks:
            lines[int(d['block'])] = d
    bad = []
    missing = [b for b in blocks if b not in lines]
    if missing:
        bad.append(f'no eap cdaddr line in {len(missing)} blocks (first {missing[:3]})')
    tot = collections.Counter(); prev_table = -1; ends = []
    for b in sorted(lines):
        d = lines[b]
        if any(d.get(k2) != v for k2, v in want.items()) or (d.get('cdst') == 'true') != want_st or (d.get('cdlearn', 'false') == 'true') != want_learn:
            bad.append(f'switches differ in block {b}: ' + ' '.join(f'{k2}={d.get(k2)}' for k2 in ('cdaddr', 'cdrate', 'cdmin', 'cdratio', 'cdst', 'cdlearn')))
        g = lambda k2: int(d.get(k2, '0')) if d.get(k2, '0').isdigit() else 0
        if want_st and ntx.get(b, 0) > 0 and g('issued_st') == 0:
            bad.append(f'block {b} with {ntx.get(b)} transactions issued no sender or recipient')
        if g('done') + g('unfinished') != g('issued_cd') + g('issued_st'):
            bad.append(f'block {b}: done + unfinished != issued')
        if d.get('complete') != 'true':
            bad.append(f'block {b}: complete={d.get("complete")}')
        if g('table') < prev_table:
            bad.append(f'learning table shrank at block {b} ({prev_table} -> {g("table")})')
        prev_table = g('table')
        for k2 in ('cand', 'cand_readable', 'issued_cd', 'issued_st', 'capped', 'done', 'unfinished', 'acct_fill', 'code_fill', 'used_cd', 'used_cd_in_time',
                   'used_st', 'fill_used', 'fill_unused', 'fill_used_in_time'):
            tot[k2] += g(k2)
        ends.append(g('end_us'))
    why = (f'cdaddr lines={len(lines)}/{len(blocks)} table_end={prev_table} ' + ' '.join(f'{k2}={v}' for k2, v in tot.items()) +
           (f' end_us_mean={sum(ends) / len(ends):.0f} end_us_max={max(ends)}' if ends else ''))
    if bad:
        why += ' STOP: ' + '; '.join(bad[:5])
    return not bad, why


def zk_lines(node_log):
    """EXP-189: the `eap zk` lines of the node log by block (each written at the next block's start)."""
    d = {}
    try:
        with open(node_log, errors='replace') as f:
            for l in f:
                if 'eap zk' in l:
                    kv = dict(re.findall(r'(\w+)=(\S+)', l))
                    if 'block' in kv:
                        d[int(kv['block'])] = kv
    except FileNotFoundError:
        pass
    return d


def zk_tagged(cfg, txs=None):
    """EXP-199 (Master 10-31): whether a block of this configuration writes an `eap zk` line under its own number. The line is
    written at the next block's start (eap.rs refresh -> eap_zk::block_start) with the number set by `eap_zk::set_block`,
    which only the prewarm paths call (prewarm.rs: reth's pool path and EAP's own mechanism `ew`); a configuration with
    prewarm=0 and no `ew` (D-N0, D-NP) leaves the previous number, so its line carries another block's number. The prewarm
    path is also skipped for a block with fewer than SMALL_BLOCK_TX_THRESHOLD = 5 transactions (payload_processor/mod.rs
    488, every configuration; d0 of 10-31: block 26,263,039 with 4 transactions under D-WEX1)."""
    c = ' ' + CONFIGS[cfg] + ' '
    path = ' prewarm=0 ' not in c or re.search(r' ew=[1-9]', c) is not None
    return path and (txs is None or txs >= 5)


ZK_TXS = {}   # EXP-199: transactions per executed block, for zk_tagged


def zk_want(cfg):
    """EXP-189: the `eap zk` fields a block of this configuration must show (None: no line, all three switches off)."""
    c = CONFIGS[cfg]
    m = re.search(r' zkpre=(\d+)', c)
    pre = m.group(1) if m else '0'
    glv = 'true' if ' glv=1' in c else 'false'
    learn = 'true' if (' zklearn=1' in c or pre != '0') else 'false'
    return None if (pre == '0' and glv == 'false' and learn == 'false') else {'pre': pre, 'glv': glv, 'learn': learn}


def precheck_zk189(node_log, k, blocks):
    """EXP-189 (README section 4): in the pre-check blocks (Z-AZ81: glv=1, zkpre=8; z2: Z-AZ41, zkpre=4) every block but
    the last (its line is written at the next block's start) has its `eap zk` line with the pre-check configuration's
    zkpre, learn=true, glv=true, and from the second block
    on no double-and-add multiplication (GLV_MUL is on throughout the window, so every multiplication started in it takes
    GLV; the first block may count multiplications that started before the window). Learned entries, triggered
    transactions, skip passes, inputs computed and stored and the execution thread's hits are reported."""
    time.sleep(0.3)
    L = zk_lines(node_log)
    need = blocks[:-1]
    miss = [b for b in need if b not in L]
    want_pre = re.search(r' zkpre=(\d+)', CONFIGS[PRECHECK_CFG]).group(1)   # z1: 8 (Z-AZ81), z2: 4 (Z-AZ41)
    bad = [b for b in need if b in L and not (L[b].get('pre') == want_pre and L[b].get('learn') == 'true' and L[b].get('glv') == 'true')]
    da = [b for b in need[1:] if b in L and L[b].get('da_muls', '0') != '0']
    tot = lambda key: sum(int(L[b].get(key, 0)) for b in need if b in L)   # noqa: E731
    ok = not miss and not bad and not da
    last = L.get(need[-1], {}) if need else {}
    why = (f"zk lines {len(need) - len(miss)}/{len(need)} (missing {miss[:5]}); switch mismatches {bad[:5]}; double-and-add in glv blocks {da[:5]}; "
           f"(reported: learned at the last {last.get('learned')}, learned_txs {tot('learned_txs')}, triggered {tot('triggered')}, skips {tot('skips')}, "
           f"skip_muls {tot('skip_muls')}, submitted {tot('submitted')}, computed {tot('computed')}, stored {tot('stored')}, failed {tot('failed')}, "
           f"glv_muls {tot('glv_muls')}, exec_hit_ahead {tot('exec_hit_ahead')}, exec_miss_inflight {tot('exec_miss_inflight')}, exec_miss_other {tot('exec_miss_other')}, "
           f"pw_hit_ahead {tot('pw_hit_ahead')})")
    return ok, why


def precheck_ew(node_log, k, blocks):
    """EXP-199: in the k pre-check blocks (PRECHECK_CFG with ew=N): stops on a panic, on no 'eap ew block' line, on a line
    whose threads differ from N, or (iqc=1) on no 'eap iqc' line; the code writes one 'eap ew block' line per block with at
    least five transactions and one 'eap iqc' line per block with readers. Counts are reported."""
    want = int(re.search(r' ew=(\d+)', CONFIGS[PRECHECK_CFG]).group(1))
    bset = set(blocks)
    ew, iqc, exits = {}, {}, 0
    for _ in range(6):
        lines = list(open(node_log, errors='replace'))
        panic = any('panicked' in l for l in lines)
        ew, iqc, exits = {}, {}, 0
        for l in lines:
            m = re.search(r'\bblock=(\d+)', l)
            if not m or int(m.group(1)) not in bset:
                continue
            kv = dict(re.findall(r'\b(\w+)=(\d+)', l))
            if 'eap ew block' in l:
                ew[int(m.group(1))] = kv
            elif 'eap iqc' in l:
                iqc[int(m.group(1))] = kv
            elif 'eap ew exit' in l:
                exits += 1
            elif 'eap ew native' in l or 'eap inflight' in l:
                for k2 in ('found', 'joined', 'timeouts', 'pred_txs', 'pred_promoted'):
                    iqc.setdefault('_native', {}).setdefault(k2, 0)
                    iqc['_native'][k2] += int(kv.get(k2, 0))
        if len(ew) >= k - 1:
            break
        time.sleep(0.5)
    if panic:
        return False, 'panic in node log'
    why = (f'ew lines={len(ew)}/{k} exit lines={exits} heavy={sum(int(v.get("heavy", 0)) for v in ew.values())} '
           f'queued={sum(int(v.get("queued", 0)) for v in ew.values())} skipped={sum(int(v.get("skipped", 0)) for v in ew.values())} '
           f'ov_slot_reads={sum(int(v.get("ov_slot_reads", 0)) for v in ew.values())} ov_txs={sum(int(v.get("ov_txs", 0)) for v in ew.values())} '
           f'iqc lines={len([k for k in iqc if k != "_native"])} native={iqc.get("_native", {})}')
    if not ew:
        return False, 'no eap ew block line: ' + why
    if any(int(v.get('threads', -1)) != want for v in ew.values()):
        return False, f'eap ew block threads differ from {want}: ' + why
    if ' iqc=1' in CONFIGS[PRECHECK_CFG] and ' tx=1' in CONFIGS[PRECHECK_CFG] and not [k for k in iqc if k != '_native']:
        return False, 'no eap iqc line: ' + why
    return True, why


def run_prechecks(node_log, n, sched, out_dir, label):
    """EXP-183 (Master 10-26, after h1 stopped twice at its 100th pre-check block on conditions that were expected, not
    guaranteed): the pre-check items of the PRECHECK blocks ending at block n, moved here from run_blocks so that
    scripts/replay_precheck183.py runs the same code on a recorded node log. Every item is evaluated (no item is skipped
    after an earlier one failed), and an item stops the run only on conditions the code guarantees when the feature is on;
    expected quantities are reported in `why`. Returns (ok, why)."""
    if 'pwsplit=' in CONFIGS.get(PRECHECK_CFG, '') and 'pwsplitmin=' not in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-169 (needs sysn)
        ok, why = precheck_split(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        hv_ok, hv_why = precheck_heavy(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and hv_ok, why + '; ' + hv_why
    else:
        ok, why = (precheck_heavy if 'pwheavy=' in CONFIGS.get(PRECHECK_CFG, '') else precheck_nb)(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
    if ' ew=' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-199: EAP's own prewarm mechanism
        e_ok, e_why = precheck_ew(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and e_ok, why + '; ' + e_why
    if 'pwheavyfirst=' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-179
        hf_ok, hf_why = precheck_heavyfirst(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and hf_ok, why + '; ' + hf_why
    if 'pwnbval=' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-180: the speculative passes, the abort and the helpers' nice value
        v_ok, v_why = precheck_val(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and v_ok, why + '; ' + v_why
    if PRECHECK_ALT and 'pwnbinterp=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-183: the speculative passes in the interpreter
        i_ok, i_why = precheck_interp183(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)), sched)
        ok, why = ok and i_ok, why + '; ' + i_why
    if 'rdpool=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-183: the readers on the persistent pool
        p_ok, p_why = precheck_rdpool(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and p_ok, why + '; ' + p_why
    if 'pwsplitmin=' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-183: X-017's split of the larger entries only
        s_ok, s_why = precheck_split183(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and s_ok, why + '; ' + s_why
    if _srdiag_on(CONFIGS.get(PRECHECK_CFG, '')):   # EXP-182: the state-root diagnostics line of every block (apply_srdiag_off.py: with CTRL_ADD)
        s_ok, s_why = precheck_sr(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and s_ok, why + '; ' + s_why
    if ' zkpre=' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-189: the `eap zk` lines, switches and multiplication counts
        z_ok, z_why = precheck_zk189(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and z_ok, why + '; ' + z_why
    if 'rdjoinlate=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-182: the late joins of the readers
        time.sleep(0.3)
        guard_check(node_log, sched, n)
        l_ok, l_why = precheck_late(node_log, list(range(n - PRECHECK + 1, n + 1)))
        ok, why = ok and l_ok, why + '; ' + l_why
    if ' cdaddr=' in CONFIGS.get(PRECHECK_CFG, '') or ' cdst=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-184: the calldata-address lines
        ntx = {r['block']: r['txs'] for r in (json.loads(x) for x in open(os.path.join(out_dir, f'{label}.jsonl')))} if os.path.exists(os.path.join(out_dir, f'{label}.jsonl')) else {}
        c_ok, c_why = precheck_cd184(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)), ntx)
        ok, why = ok and c_ok, why + '; ' + c_why
    if ' srtx=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-182: X-017's dispatch-time proof targets
        ntx = {r['block']: r['txs'] for r in (json.loads(x) for x in open(os.path.join(out_dir, f'{label}.jsonl')))}
        t_ok, t_why = precheck_srtx(node_log, PRECHECK, list(range(n - PRECHECK + 1, n + 1)), ntx)
        ok, why = ok and t_ok, why + '; ' + t_why
    if 'tpw=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-148: the txpool snapshot is used and the feeding accepted
        tl_lines = [l for l in open(node_log, errors='replace') if 'txpool snapshot for this block' in l]
        used = sum(1 for l in tl_lines if 'used=true' in l)
        fr = [json.loads(l) for l in open(os.path.join(out_dir, f'{label}.jsonl'))][-PRECHECK:]
        sent = sum((r.get('feed') or {}).get('sent', 0) for r in fr); acc = sum((r.get('feed') or {}).get('accepted', 0) for r in fr)
        why += f' txpool_snapshot_lines={len(tl_lines)} txpool_snapshot_used={used} fed_sent={sent} fed_accepted={acc}'
        if os.environ.get('PRECHECK_TPW', '') == 'guaranteed':   # EXP-194: one line per block whatever tpw (log filter), and the feeding works
            if len(tl_lines) < PRECHECK or sent == 0 or acc == 0:
                ok = False
        elif used < PRECHECK // 2 + 1 or sent == 0 or acc < 0.8 * sent:
            ok = False
    if 'c2rec=1' in CONFIGS.get(PRECHECK_CFG, '') and os.environ.get('PRECHECK_C2', '1') != '0':   # EXP-152: salt templates evaluated and known-sequence fits made (PRECHECK_C2=0: not checked, segment without template entries)
        blocks_pc = set(range(n - PRECHECK + 1, n + 1))
        c2e = fk = 0
        for l in open(node_log, errors='replace'):
            if ' eap block ' not in l: continue
            mt = re.search(r' tag=(\d+) ', l)
            if mt and int(mt.group(1)) in blocks_pc:
                m1 = re.search(r'\bc2_evals=(\d+)', l); m2 = re.search(r'\blx_fit_known=(\d+)', l)
                c2e += int(m1.group(1)) if m1 else 0; fk += int(m2.group(1)) if m2 else 0
        why += f' c2_evals={c2e} lx_fit_known={fk}'
        if c2e == 0 or fk == 0:
            ok = False
    if ' pwk=0' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-157: the relaxed configuration was never gated and issued plan jobs
        blocks_pc = set(range(n - PRECHECK + 1, n + 1))
        gated = jobs = 0
        for l in open(node_log, errors='replace'):
            if ' eap block ' not in l: continue
            mt = re.search(r' tag=(\d+) ', l)
            if mt and int(mt.group(1)) in blocks_pc:
                m1 = re.search(r'\bpw_gated=(\d+)', l); m2 = re.search(r'\bpw_jobs=(\d+)', l)
                gated += int(m1.group(1)) if m1 else 0; jobs += int(m2.group(1)) if m2 else 0
        why += f' pw_gated={gated} pw_jobs={jobs}'
        if gated != 0 or jobs == 0:
            ok = False
    if 'pwlxacct=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-172: the account handout works; EXP-175: by class
        blocks_pc = set(range(n - PRECHECK + 1, n + 1))
        mode_acct = os.environ.get('PRECHECK_ACCT', 'fit')   # fit (EXP-172), mint (EXP-175 batch-mint segment), report
        mint = set()
        if mode_acct == 'mint':
            mint = {int(r['block']) for r in csv.DictReader(open(os.environ['CLASSFILE'])) if r['cls_mint'] == 'mint'}
        la = lr = fit_blocks = acct_blocks = on = 0
        for l in open(node_log, errors='replace'):
            if ' eap block ' not in l: continue
            mt = re.search(r' tag=(\d+) ', l)
            if mt and int(mt.group(1)) in blocks_pc:
                g = lambda k: int(m.group(1)) if (m := re.search(r'\b' + k + r'=(\d+)', l)) else 0
                la += g('lx_acct'); lr += g('lx_acct_read'); on += 'pwlxacct=true' in l
                if g('lx_fit') > 0 and (mode_acct != 'mint' or int(mt.group(1)) in mint):
                    fit_blocks += 1; acct_blocks += g('lx_acct') > 0
        why += f' acct_mode={mode_acct} pwlxacct_lines={on} lx_acct={la} lx_acct_read={lr} fit_blocks={fit_blocks} fit_blocks_with_acct={acct_blocks}'
        if on == 0 or (mode_acct != 'report' and (la == 0 or lr == 0 or fit_blocks == 0 or acct_blocks * 2 < fit_blocks)):
            ok = False
    if 'pwlxrdacct=' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-177: the extra readers follow the account count
        blocks_pc = set(range(n - PRECHECK + 1, n + 1))
        nrd = int(re.search(r'pwlxrd=(\d+)', CONFIGS[PRECHECK_CFG]).group(1)); nacc = int(re.search(r'pwlxrdacct=(\d+)', CONFIGS[PRECHECK_CFG]).group(1))
        opened = closed = bad = lines = 0
        for l in open(node_log, errors='replace'):
            if ' eap block ' not in l: continue
            mt = re.search(r' tag=(\d+) ', l)
            if mt and int(mt.group(1)) in blocks_pc:
                g = lambda k: int(m.group(1)) if (m := re.search(r'\b' + k + r'=(\d+)', l)) else -1
                lines += g('pwlxrdacct') == nacc
                if g('lx_acct') >= nacc:
                    opened += 1; bad += not (g('lx_rd_woken') == nrd and g('lx_rd_open_us') > 0)
                else:
                    closed += 1; bad += not (g('lx_rd_woken') == 0 and g('lx_rd_open_us') == 0)
        # EXP-182 (as EXP-180 PRECHECK_GATE): on a general segment the gate may stay closed in every pre-check block
        gate_mode = os.environ.get('PRECHECK_GATE', 'require')
        why += f' gate_mode={gate_mode} gate_lines={lines} gate_open_blocks={opened} gate_closed_blocks={closed} gate_bad={bad}'
        # EXP-182 (Master 10-26): with the lazy gate (eap-x182 9bbe16b) a gate that opens only after the block stopped
        # spawns no extra reader, so lx_acct >= pwlxrdacct with lx_rd_woken = 0 is possible in a few blocks
        # EXP-183 (Master 10-26): blocks whose gate opened after the block stopped are possible (lazy gate): gate_bad reported
        if lines < PRECHECK - 1 or (gate_mode == 'require' and opened == 0):
            ok = False
    if 'pwlxnoself=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-181: the job hands out every key; the page walk works
        blocks_pc = set(range(n - PRECHECK + 1, n + 1))
        wpf = int(m.group(1)) if (m := re.search(r'pwlxpf=(\d+)', CONFIGS[PRECHECK_CFG])) else 0
        mint = {int(r['block']) for r in csv.DictReader(open(os.environ['CLASSFILE'])) if r['cls_mint'] == 'mint'}
        lines = lines_pf = fit_mint = walked = items = bad_pf = 0
        for l in open(node_log, errors='replace'):
            if ' eap block ' not in l: continue
            mt = re.search(r' tag=(\d+) ', l)
            if mt and int(mt.group(1)) in blocks_pc:
                g = lambda k: int(m.group(1)) if (m := re.search(r'\b' + k + r'=(\d+)', l)) else 0
                lines += 'pwlxnoself=true' in l
                lines_pf += bool(re.search(r'\bpwlxpf=' + str(wpf) + r'\b', l))
                items += g('lx_pf_items'); bad_pf += g('lx_pf_bad')
                if g('lx_fit') > 0 and int(mt.group(1)) in mint:
                    fit_mint += 1; walked += g('lx_pf_jobs') > 0 and g('lx_pf_items') > 0
        why += f' noself_lines={lines} pwlxpf_lines={lines_pf} mint_fit_blocks={fit_mint} walked_blocks={walked} lx_pf_items={items} lx_pf_bad={bad_pf}'
        # EXP-182: one line may still be unflushed when the check runs (the last pre-check block's)
        if lines < PRECHECK - 1 or (wpf > 0 and (lines_pf < PRECHECK - 1 or fit_mint == 0 or walked * 2 < fit_mint or bad_pf > 0.01 * items)):
            ok = False
    if 'pwrdpf=' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-181: the readers' batch walk works
        blocks_pc = set(range(n - PRECHECK + 1, n + 1))
        wrd = int(re.search(r'pwrdpf=(\d+)', CONFIGS[PRECHECK_CFG]).group(1))
        mint = {int(r['block']) for r in csv.DictReader(open(os.environ['CLASSFILE'])) if r['cls_mint'] == 'mint'}
        lines = fit_mint = walked = items = bad_pf = 0
        for l in open(node_log, errors='replace'):
            if ' eap block ' not in l: continue
            mt = re.search(r' tag=(\d+) ', l)
            if mt and int(mt.group(1)) in blocks_pc:
                g = lambda k: int(m.group(1)) if (m := re.search(r'\b' + k + r'=(\d+)', l)) else 0
                lines += bool(re.search(r'\bpwrdpf=' + str(wrd) + r'\b', l))
                items += g('rd_pf_items'); bad_pf += g('rd_pf_bad')
                if g('lx_fit') > 0 and int(mt.group(1)) in mint:
                    fit_mint += 1; walked += g('rd_pf_batches') > 0 and g('rd_pf_items') > 0
        why += f' pwrdpf_lines={lines} rd_mint_fit_blocks={fit_mint} rd_walked_blocks={walked} rd_pf_items={items} rd_pf_bad={bad_pf}'
        if lines != PRECHECK or fit_mint == 0 or walked * 2 < fit_mint or bad_pf > 0.01 * items:
            ok = False
    if 'pwlxnoself=1' in CONFIGS.get(PRECHECK_CFG, ''):   # EXP-181 (Master, X-018 review): the block-end join of the readers
        # stays short: median join_us of the pre-check blocks at most 1,472 us (twice K-FD's median 736 us in EXP-177 n1)
        # and no block above 20,000 us (K-FD's maximum there 5,649 us)
        blocks_pc = set(range(n - PRECHECK + 1, n + 1))
        joins = []
        for l in open(node_log, errors='replace'):
            if ' eap block ' not in l: continue
            mt = re.search(r' tag=(\d+) ', l)
            if mt and int(mt.group(1)) in blocks_pc and (mj := re.search(r'\bjoin_us=(\d+)', l)):
                joins.append(int(mj.group(1)))
        joins.sort()
        jmed = joins[len(joins) // 2] if joins else -1; jmax = joins[-1] if joins else -1
        why += f' join_blocks={len(joins)} join_us_median={jmed} join_us_max={jmax}'
        # EXP-183 (Master 10-26): the join times are expected magnitudes: reported only
        why += f' (reported: join median <= 1472 us {jmed <= 1472}, max <= 20000 us {jmax <= 20000})'
        if len(joins) < PRECHECK - 1:
            ok = False
    return ok, why

PANIC_POS = [0]


def panic_check(node_log, n):
    """EXP-182 (Master 10-26, after EXP-180 v1's reader panic): stops the run at the first block after which the node log has
    a `panicked` line (a reader thread's panic does not stop the node; the pre-check would only see it after 100 blocks)."""
    try:
        with open(node_log, errors='replace') as f:
            f.seek(PANIC_POS[0])
            data = f.read()
            PANIC_POS[0] = f.tell()
    except OSError:
        return
    for l in data.splitlines():
        if 'panicked' in l:
            raise SystemExit(f'node panicked (checked after block {n}): {l.strip()[:300]}')


REUSE_POS = [0]
REUSE = {}
REUSE_ON_TAIL = int(os.environ.get('REUSE_ON_TAIL', '0'))   # EXP-171: the last N warm-up blocks alternate U-R / F-R
REUSE_ON_TAIL_CFGS = os.environ.get('REUSE_ON_TAIL_CFGS', 'U-R F-R').split()   # r3: F-Rf only


def reuse_lines(node_log):
    """EXP-171: new `eap reuse` lines of the node log since the last call, by block: {block: {field: int}}."""
    try:
        with open(node_log, errors='replace') as f:
            f.seek(REUSE_POS[0])
            data = f.read()
            REUSE_POS[0] = f.tell()
    except OSError:
        return REUSE
    for l in data.splitlines():
        if 'eap reuse' not in l or 'mismatch' not in l:
            continue
        kv = dict(re.findall(r'\b(\w+)=(\w+)', l))
        if 'block' not in kv:
            continue
        b = int(kv['block'])
        if 'eap reuse mismatch' in l:   # the warning written at a difference, before the block's summary line
            REUSE.setdefault(b, {})['mismatch_warn'] = 1
            continue
        d = {k: (int(v) if v.isdigit() else (1 if v == 'true' else 0 if v == 'false' else v)) for k, v in kv.items()}
        d['mismatch_warn'] = REUSE.get(b, {}).get('mismatch_warn', 0)
        REUSE[b] = d
    return REUSE


def reuse_stop_check(node_log, n):
    """EXP-171: stops the run when any block so far reported a difference or the trip flag."""
    lines = reuse_lines(node_log)
    bad = {b: v for b, v in lines.items() if v.get('mismatch', 0) or v.get('tripped', 0) or v.get('mismatch_warn', 0) or v.get('fast_diff', 0)}
    if bad:
        raise SystemExit(f'reuse difference at block(s) {sorted(bad)[:5]} (checked up to {n}): {list(bad.values())[0]}')


def schedule(start, end, ffwd, warmup, seq, blocks):
    """EXP-169: (role, configuration, measured index) of every block, computed before the first block (the rules of the
    EXP-167 loop), so that the control line of a block can depend on the configuration of the next one."""
    sched = {}; k_meas = 0; fill_due = 0; k_zk = 0
    if RUNS3:   # EXP-189 z2: warm-up as before, the measured range from the standard rotation
        sys.path.insert(0, os.path.join(os.environ['PROLOGUE_REPO'], 'scripts'))
        from schedule_runs3 import build, check
        m0 = start + warmup
        for n in range(start, m0):
            cfg = WARM
            if n - start - ffwd < PRECHECK:
                cfg = PRECHECK_ALT if (PRECHECK_ALT and (n - start - ffwd) % 2 == 1) else PRECHECK_CFG
            sched[n] = ('warmup' if n >= start + ffwd else 'ffwd', cfg if n >= start + ffwd else WARM, 0)
        if os.environ.get('RUNS3_SCHEDULE'):   # apply_s.py: the pass's schedule from its CSV (pass 1 of the pair design)
            rows = [dict(r, block=int(r['block']), seg=int(r['seg']), pos=int(r['pos']), seglen=int(r['seglen']), target=int(r['target']))
                    for r in csv.DictReader(open(os.environ['RUNS3_SCHEDULE']))]
            if [r['block'] for r in rows] != list(range(m0, end + 1)):
                raise SystemExit(f"RUNS3_SCHEDULE {os.environ['RUNS3_SCHEDULE']} does not cover {m0}-{end}")
        else:
            rows = build(m0, end, RUNS3_CFGS, targets={b for b in ZK_SET if m0 <= b <= end})
        ok, lines = check(rows, RUNS3_CFGS)
        print('schedule_runs3 check:\n' + '\n'.join(lines), flush=True)
        if not ok:
            raise SystemExit('schedule_runs3 check failed')
        per = 2 * len(RUNS3_CFGS)
        for r in rows:
            sched[r['block']] = ('measured', r['cfg'], r['seg'])
            RUNS3_INFO[r['block']] = (r['seg'], r['pos'], r['seg'] // per)
        return sched
    for n in range(start, end + 1):
        role = 'ffwd' if n < start + ffwd else ('warmup' if n < start + warmup else 'measured')
        # EXP-189: a measured block carrying the entry takes the next configuration of its own cycle (no filler)
        if role == 'measured' and SEQ_ZK and n in ZK_SET:
            sched[n] = (role, SEQ_ZK[k_zk % len(SEQ_ZK)], k_zk)
            k_zk += 1
            continue
        if role == 'measured' and fill_due:   # uj3/ui3: filler block (FILLER configuration), not measured, shifts the phase
            role = 'filler'; fill_due -= 1   # EXP-146: NFILL filler blocks after each cycle
        if role == 'measured' and MEASURE == 'indicator' and not has_marker(os.path.join(blocks, f'{n}.json')):
            role = 'between'
        i = k_meas
        if role == 'measured':
            k_meas += 1
            fill_due = int(os.environ.get('NFILL', '1')) if (bool(FILLER) and k_meas % len(seq) == 0) else 0
        cfg = seq[i % len(seq)] if role == 'measured' else (FILLER if role == 'filler' else WARM)
        if role == 'warmup' and n - start - ffwd < PRECHECK:   # EXP-120: the first warm-up blocks run the fed configuration as a pre-check
            cfg = PRECHECK_ALT if (PRECHECK_ALT and (n - start - ffwd) % 2 == 1) else PRECHECK_CFG   # EXP-183: alternating
        if role == 'warmup' and REUSE_ON_TAIL and n >= start + ffwd + warmup - REUSE_ON_TAIL:   # EXP-171: reuse on before measuring
            cfg = REUSE_ON_TAIL_CFGS[(n - start) % len(REUSE_ON_TAIL_CFGS)]
        sched[n] = (role, cfg, i)
    return sched


# apply_drvgap.py (EXP-269 section 16): the marks of the current gap between blocks
_GAP = {}


def run_blocks(label, out_dir, blocks, start, end, ffwd, warmup, seq, eap_ctrl, engine, http, hashes, head, meta, pid, tid, settle):
    reuse_run = any('reuse=' in CONFIGS.get(c, '') for c in set(seq) | {WARM, PRECHECK_CFG, FILLER} | (set(REUSE_ON_TAIL_CFGS) if REUSE_ON_TAIL else set()))   # EXP-172
    nice_checked = set()   # EXP-180: value configurations whose helper nice value was checked
    srtx_checked = set()   # EXP-182: configurations whose srtx flag in the `eap sr` line was checked
    meta['nbnice'] = NBNICE
    meta['nbgas'] = NBGAS
    meta['stale_fills'] = GUARD
    meta['reuse_checks'] = reuse_run
    sched = schedule(start, end, ffwd, warmup, seq, blocks)
    with open(os.path.join(out_dir, f'{label}.jsonl'), 'w') as out:
        for n in range(start, end + 1):
            role, cfg, i = sched[n]
            # EXP-169: this block's end reads the next block's system-call slots when the next block is a -y cell
            nxt = sched.get(n + 1)
            sysn = bool(nxt) and nxt[1].endswith('-y') and ' sysn=1' not in CONFIGS[cfg]
            if role == 'measured':
                perf_start(pid, out_dir, label)   # EXP-159
            gate_s = 0.0
            _LEAN['mode'] = lean_mode(n)   # apply_prologue_lean.py: before the gate (pcore_busy uses _tree_ticks)
            if role in ('ffwd', 'between'):  # advance-only blocks: no gate
                pass
            elif PGATE > 0:  # wait while the node's cores (NODE_CPUS, default 0-7) are busy with other work
                tg = time.time()
                while pcore_busy(0.05, pid) > PGATE and time.time() - tg < LOADGATE_MAX:   # EXP-101: 0.05 s sample (was 1 s), node tree excluded
                    time.sleep(2)
                gate_s = time.time() - tg
            elif LOADGATE > 0:  # wait while the 1-minute load is above LOADGATE
                tg = time.time()
                while float(loadavg().split()[0]) > LOADGATE and time.time() - tg < LOADGATE_MAX:
                    time.sleep(5)
                gate_s = time.time() - tg
            if JIT_SWITCH:   # EXP-175 (b): compiled code off for "@i" blocks, on otherwise (EXP-032; 0.5 s for the switch)
                want = 'disable' if cfg.endswith('@i') else 'enable'
                if want != meta.get('_jit_state'):
                    http.call('reth_jit', [want])
                    meta['_jit_state'] = want
                    time.sleep(0.5)
            _GAP['gate'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            write_ctrl(eap_ctrl, f'tag={n} {CONFIGS[cfg]}' + (' sysn=1' if sysn else ''))
            b = R.load_block(os.path.join(blocks, f'{n}.json'), 10)
            _GAP['loaded'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            p = b['payload']
            # EXP-120: for tpw=1 blocks feed the block's transactions to the pool, then wait LEAD s (every block that is
            # not advance-only waits the same LEAD, fed or not); the node's txpool prewarm thread runs during this wait
            feed = None; lead_s = 0.0
            if role not in ('ffwd', 'between'):
                tl = time.monotonic()
                if FEED_PLAN and (FEED_ALL or 'tpw=1' in CONFIGS[cfg]):   # EXP-152: the realistic feeding on every block; only tpw=1 configurations prewarm from the txpool (EXP-194: FEED_ALL=0, only tpw=1 blocks)
                    # EXP-127: realistic feeding in two batches by public lead time; the same total wait T + T2 for every block
                    plan = FEED_PLAN.get(n, []); txs = p['transactions']
                    b1 = [txs[i] for i, d in plan if d >= FEED_T * 1000 and i < len(txs)]
                    b2 = [txs[i] for i, d in plan if FEED_T2 * 1000 <= d < FEED_T * 1000 and i < len(txs)]
                    feed = {'n_txs': len(txs), 'n_public': len(plan), 'n_b1': len(b1), 'n_b2': len(b2), 'n_late': len(plan) - len(b1) - len(b2)}
                    for key, batch, wait in (('b1', b1, FEED_T), ('b2', b2, FEED_T2)):
                        tb = time.monotonic()
                        try:
                            feed[key] = feed_txpool('http://127.0.0.1:8545', batch) if batch else {'sent': 0, 'skipped': 0, 'accepted': 0, 'rejected': 0, 'errors': {}, 'ms': 0.0}
                        except Exception as e:  # noqa: BLE001
                            feed[key] = {'error': str(e)[:200]}
                        rem = wait - (time.monotonic() - tb)
                        if rem > 0:
                            time.sleep(rem)
                    for k in ('sent', 'skipped', 'accepted', 'rejected', 'ms'):
                        feed[k] = sum(feed[x].get(k, 0) for x in ('b1', 'b2'))
                    feed['errors'] = {}
                    for x in ('b1', 'b2'):
                        for m, c in feed[x].get('errors', {}).items():
                            feed['errors'][m] = feed['errors'].get(m, 0) + c
                elif 'tpw=1' in CONFIGS[cfg]:
                    try:
                        feed = feed_txpool('http://127.0.0.1:8545', p['transactions'])
                    except Exception as e:  # noqa: BLE001
                        feed = {'error': str(e)[:200]}
                rem = (FEED_T + FEED_T2 if FEED_PLAN else LEAD_BY_CFG.get(cfg, LEAD)) - (time.monotonic() - tl)   # EXP-195: per-configuration wait
                if rem > 0:
                    time.sleep(rem)
                lead_s = time.monotonic() - tl
            _GAP['lead'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            params = [R.payload_v3(p), [R.versioned_hash(c) for c in b['blob_kzg_commitments']], b['parent_root'], R.execution_requests(b['execution_requests'])]
            load = loadavg()
            lm = _LEAN['mode']; last = _LEAN['last']   # apply_prologue_lean.py
            mpre = mnp = mfcu = None
            want = {'nopre': 'np', 'fcu': 'fcu'}.get(lm)
            if LEAN_MCHK or not (want and last and last[0] == want and last[2] == n - 1):
                mpre = metrics()
            if want and last and last[0] == want and last[2] == n - 1:
                m0, m0_src = last[1], 'prev_' + want
            else:
                m0, m0_src = mpre, 'pre'
            t0, q0, g0 = thread_sample(pid, tid), proc_sample(pid), threads_by_name(pid)
            ci0 = cpuidle_sample()   # apply_ci.py
            irq0 = irq_sample()   # apply_irq_block.py (X-028)
            dsk0 = disk_sample()   # apply_disk257.py (EXP-257)
            _GAP['sampled'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            mono0 = time.monotonic()
            res, np_ns = engine.call('engine_newPayloadV4', params)
            mono1 = time.monotonic()
            ci1 = cpuidle_sample()   # apply_ci.py
            irq1 = irq_sample()   # apply_irq_block.py (X-028)
            dsk1 = disk_sample()   # apply_disk257.py (EXP-257)
            if lm in ('old', 'nopre') or LEAN_MCHK:   # apply_prologue_lean.py
                mnp = metrics()
            t1, q1, g1 = thread_sample(pid, tid), proc_sample(pid), threads_by_name(pid)
            m1 = mnp if lm != 'fcu' else None
            if res['status'] != 'VALID':
                meta['invalid'] = {'block': n, 'res': res}
                print(f'block {n}: newPayload {res}', flush=True)
                break
            hashes[n] = p['block_hash']
            fin = hashes.get(max(n - 64, head), hashes[head])
            fcu, fcu_ns = engine.call('engine_forkchoiceUpdatedV3', [{'headBlockHash': p['block_hash'], 'safeBlockHash': fin, 'finalizedBlockHash': fin}, None])
            _GAP['fcu'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            if fcu['payloadStatus']['status'] != 'VALID':
                meta['invalid'] = {'block': n, 'fcu': fcu}
                print(f'block {n}: forkchoiceUpdated {fcu}', flush=True)
                break
            q2 = proc_sample(pid)
            if lm == 'fcu' or LEAN_MCHK:   # apply_prologue_lean.py: synchronous, done before the idle check starts
                mfcu = metrics()
            if lm == 'fcu':
                m1 = mfcu
            _LEAN['last'] = ('fcu', mfcu, n) if lm == 'fcu' else ('np', mnp, n)
            _GAP['settle0'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            settle_s = adaptive_settle(pid, minimum=(SETTLE_MIN_MEASURED if role == 'measured' else SETTLE_MIN), longest=SETTLE_MAX) if role not in ('ffwd', 'between') else 0.0   # EXP-101; EXP-199 / EXP-204 measured-block minimum
            _GAP['settle1'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            zk = int((bool(SEQ_ZK) or RUNS3) and n in ZK_SET and role == 'measured')   # EXP-189: the entry stratum and its own cycle
            sl = len(SEQ_ZK) if (zk and SEQ_ZK) else len(seq)
            if RUNS3 and n in RUNS3_INFO:   # z2: the segment, the position in it and the cycle of segments
                seg_i, cyc, posv = RUNS3_INFO[n][0], RUNS3_INFO[n][2], RUNS3_INFO[n][1]
            else:
                seg_i, cyc, posv = -1, (i // sl if role == 'measured' else -1), (i % sl if role == 'measured' else -1)
            rec = {'block': n, 'role': role, 'cfg': cfg, 'zk': zk, 'seg': seg_i, 'sysn_after': sysn, 'cycle': cyc, 'pos': posv,
                   'txs': len(p['transactions']), 'gas_used': int(p['gas_used']), 'new_payload_ms': np_ns / 1e6, 'fcu_ms': fcu_ns / 1e6,
                   'engine': delta(t0, t1), 'cpuidle': delta(ci0, ci1), 'proc': delta(q0, q1), 'proc_fcu': delta(q1, q2), 'proc_abs_before': q0, 'proc_abs_after_fcu': q2,
                   'threads': {k: g1.get(k, 0.0) - g0.get(k, 0.0) for k in set(g0) | set(g1)},
                   'metrics': delta(m0, m1), 'gate_s': gate_s, 'settle_s': settle_s, 'lead_s': lead_s, 'feed': feed, 'txpool_snapshot': {k: v for k, v in m1.items() if 'txpool_snapshot' in k}, 'pcore_busy': (pcore_busy(0.05, pid) if lm == 'old' else -2) if (PGATE > 0 and role not in ('ffwd', 'between')) else -1, 'lean': {'mode': lm, 'm0': m0_src, 'm1': 'fcu' if lm == 'fcu' else 'np', 'tree': len(_LEAN['tt_pids'] or [])}, 'mchk': ({'pre': mpre, 'np': mnp, 'fcu': mfcu} if LEAN_MCHK else None), 't': time.time(), 'mono': [mono0, mono1], 'load': load}
            if IRQ_CPUS:   # apply_irq_block.py (X-028)
                rec['irq'] = {k: irq1[k] - irq0.get(k, 0) for k in irq1}
            if DISK_DEV and dsk0 and dsk1:   # apply_disk257.py (EXP-257)
                rec['disk'] = {k: (dsk1[k] if k == 'in_flight' else dsk1[k] - dsk0[k]) for k in dsk1 if k in dsk0}
            _w = _GAP.get('written')   # apply_drvgap.py (EXP-269 section 16)
            rec['gap'] = {**{k: round((_GAP[k] - _w) * 1e3, 3) for k in ('checks', 'gate', 'loaded', 'lead', 'sampled') if _w and k in _GAP},
                          **{k: round((_GAP[k] - mono1) * 1e3, 3) for k in ('fcu', 'settle0', 'settle1') if k in _GAP}}
            out.write(json.dumps(rec) + '\n')
            out.flush()
            _GAP.clear(); _GAP['written'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            ZK_TXS[n] = rec['txs']
            panic_check(meta.get('node_log', ''), n)   # EXP-182: after every block, before any other check
            guard_check(meta.get('node_log', ''), sched, n)   # EXP-182: rules (a)-(b) for stale cache fills
            # EXP-189: the previous block's `eap zk` line (written at this block's start): at the first measured block, the
            # last warm-up block's line must show learned entries (README section 4: the warm-up carries 14 blocks with the
            # entry by the pool scan; a run whose zkpre blocks cannot trigger answers nothing); for the first measured block
            # of each configuration the line's switches must match its control line, and no line for Z-U0 (all off)
            if (SEQ_ZK or RUNS3) and role == 'measured' and n - 1 in sched:
                prole, pcfg, _ = sched[n - 1]
                need_line = (prole == 'warmup' and ' zklearn=1' in CONFIGS.get(WARM, '')) or (prole == 'measured' and pcfg not in meta.setdefault('zk_checked', {}))   # EXP-194: learning check only after a learning warm-up
                if need_line:
                    time.sleep(0.2)
                    L = zk_lines(meta.get('node_log', ''))
                    d = L.get(n - 1)
                    if prole == 'warmup':
                        if not d or d.get('learned', '0') == '0':
                            raise SystemExit(f'zk learning check failed: block {n - 1} line {d}')
                        meta['zk_learned_at_start'] = d.get('learned')
                        print(f"zk learning check: block {n - 1} learned {d.get('learned')}", flush=True)
                    elif not zk_tagged(pcfg, ZK_TXS.get(n - 1)):
                        # EXP-199: no line under this block's number by construction (no prewarm path, or a block of fewer
                        # than 5 transactions); recorded only, and the configuration is checked at its next measured block
                        meta.setdefault('zk_skipped', []).append({'block': n - 1, 'cfg': pcfg, 'txs': ZK_TXS.get(n - 1), 'line': d})
                        if not zk_tagged(pcfg):
                            meta.setdefault('zk_checked', {})[pcfg] = {'block': n - 1, 'line': d, 'skipped': 'no prewarm path, no tagged line'}
                        print(f'zk switch check: block {n - 1} {pcfg} skipped (txs {ZK_TXS.get(n - 1)}; line {d})', flush=True)
                    else:
                        want = zk_want(pcfg)
                        if want is None:
                            if d is not None:
                                raise SystemExit(f'zk switch check failed: block {n - 1} {pcfg} has a line {d}')
                        elif d is None or any(d.get(k) != v for k, v in want.items()):
                            raise SystemExit(f'zk switch check failed: block {n - 1} {pcfg} line {d} want {want}')
                        meta['zk_checked'][pcfg] = {'block': n - 1, 'line': d}
                        print(f'zk switch check: block {n - 1} {pcfg} {want}', flush=True)
            # EXP-180: the first measured blocks of each value configuration that start helper threads must show their nice value
            if role == 'measured' and 'pwnbval=' in CONFIGS[cfg] and [x for x in CONFIGS[cfg].split() if x.startswith('pwnb=')][-1:] == ['pwnb=1'] and cfg not in nice_checked:   # apply_drvgap.py (EXP-269 section 16): only with helpers
                time.sleep(0.2)
                nv = helper_nices(meta.get('node_log', ''), n)
                want = int(re.search(r'pwnbnice=(\d+)', CONFIGS[cfg]).group(1)) if 'pwnbnice=' in CONFIGS[cfg] else 0
                if nv:
                    if any(x != want for x in nv):
                        raise SystemExit(f'helper nice check failed: block {n} {cfg} nice {nv} want {want}')
                    nice_checked.add(cfg)
                    meta.setdefault('nice_check', {})[cfg] = {'block': n, 'nice': nv}
                    print(f'helper nice check: block {n} {cfg} nice {nv}', flush=True)
            # EXP-182: the first measured block of every configuration shows srtx=true in its `eap sr` line exactly when the
            # configuration sets srtx=1 (the line is written before newPayload returns)
            if role == 'measured' and _srdiag_on(CONFIGS[cfg]) and cfg not in srtx_checked:   # apply_srdiag_off.py: with CTRL_ADD
                d = sr_line(meta.get('node_log', ''), n)
                if not d:
                    time.sleep(0.3); d = sr_line(meta.get('node_log', ''), n)
                want = 'true' if ' srtx=1' in CONFIGS[cfg] else 'false'
                if d and d.get('srtx') != want:
                    raise SystemExit(f'srtx check failed: block {n} {cfg} srtx {d.get("srtx")} want {want}')
                if d:   # no line yet (unflushed): checked again at the next block of this configuration
                    srtx_checked.add(cfg)
                meta.setdefault('srtx_check', {})[cfg] = {'block': n, 'srtx': d.get('srtx'), 'srtx_txs': d.get('srtx_txs')}
                print(f'srtx check: block {n} {cfg} srtx {d.get("srtx")} srtx_txs {d.get("srtx_txs")}', flush=True)
            # EXP-172: the reuse stop rule and the reuse pre-check of EXP-171 run only when some configuration of this run
            # uses reuse (n1 of 10-25 01:03 stopped at the end of the warm-up on the unconditional pre-check: eap-x172 has no reuse)
            if reuse_run and ('reuse=' in CONFIGS[cfg] or role == 'measured'):   # EXP-171: the previous blocks' reuse lines are in the log by now
                reuse_stop_check(meta.get('node_log', ''), n)
            if reuse_run and WARM_REUSE_CHECK and role == 'warmup' and n == start + ffwd + warmup - 1:   # EXP-171: reuse pre-check over the whole warm-up
                time.sleep(1.0)
                lines = reuse_lines(meta.get('node_log', ''))
                wb = list(range(start + ffwd, n + 1))
                have = [b for b in wb if b in lines]
                fam = {'F': [b for b in have if sched[b][1] in ('F-R1', 'F-R1f', 'K-FR1', 'K-FRD1', 'G-FA1', 'G-FAT1', 'G-FATJ1', 'H-APS1', 'H-APSi1', 'C-ACS1', 'C-AL1', 'Z-AZ81', 'Z-FZ41')], 'U': [b for b in have if sched[b][1] in ('W-R1', 'W-R1f', 'K-W', 'K-WC', 'K-WL', 'K-WZ')]}   # EXP-189: Z-AZ81, K-WZ   # EXP-184: C-ACS1, K-WC; c2: C-AL1, K-WL   # EXP-175: K-FR1, K-W; EXP-177: K-FRD1
                on = {c: [b for b in have if sched[b][1] == c] for c in REUSE_ON_TAIL_CFGS}
                tot = lambda bs, k: sum(lines[b].get(k, 0) for b in bs)   # noqa: E731
                why = (f"reuse lines {len(have)}/{len(wb)}; mismatch {tot(have, 'mismatch')}; fast_diff {tot(have, 'fast_diff')}; "
                       + '; '.join(f"{k}: blocks {len(v)} txs {tot(v, 'txs')} valid {tot(v, 'valid')} checked {tot(v, 'checked')}" for k, v in fam.items())
                       + '; ' + '; '.join(f"{k}: blocks {len(v)} reused {tot(v, 'reused')} checked {tot(v, 'checked')}" for k, v in on.items()))
                # EXP-183 (Master 10-26): no difference is guaranteed by the code; valid and checked reuse per family is reported
                why += f"; (reported: valid and checked reuse in both families: {all(tot(v, 'valid') > 0 and tot(v, 'checked') > 0 for v in fam.values())})"
                ok = len(have) >= len(wb) - 1 and tot(have, 'mismatch') == 0 and tot(have, 'fast_diff') == 0
                ok = ok and (not REUSE_ON_TAIL or all(len(v) > 0 and tot(v, 'reused') > 0 for v in on.values()))
                meta['reuse_precheck'] = {'ok': ok, 'why': why}
                print(f'reuse precheck: {why}', flush=True)
                if not ok:
                    raise SystemExit('reuse precheck failed: ' + why)
            if PRECHECK and role == 'warmup' and n - start - ffwd == PRECHECK - 1:   # EXP-122: pre-check of the non-blocking pass
                ok, why = run_prechecks(meta.get('node_log', ''), n, sched, out_dir, label)
                meta['precheck'] = {'ok': ok, 'why': why}
                print(f'precheck: {why}', flush=True)
                if not ok:
                    raise SystemExit('precheck failed: ' + why)
            _GAP['checks'] = time.monotonic()   # apply_drvgap.py (EXP-269 section 16)
            ex = rec['metrics'].get('reth_sync_execution_execution_histogram_sum', 0) * 1000
            print(f"{label} {n} {role} {cfg} np={rec['new_payload_ms']:.1f}ms exec={ex:.1f}ms gas={rec['gas_used'] / 1e6:.1f}M txs={rec['txs']} load={load.split()[0]}", flush=True)


def _proc_ticks(pid):
    f = stat_fields(f'/proc/{pid}/stat')
    return int(f[11]) + int(f[12])


def _writeback_kb():
    for line in open('/proc/meminfo'):
        if line.startswith('Writeback:'):
            return int(line.split()[1])
    return 0


def adaptive_settle(pid, first=0.05, step=0.02, window=0.05, longest=1.0, minimum=0.0):
    """EXP-101: wait after a block until the node is idle: at least `first` s, then every `step` s check that the node's
    utime+stime grew by no clock tick (< 10 ms at 100 Hz; the coordinator's 5 ms threshold is below the tick resolution)
    over the last `window` s and Writeback < 1 MB; at most `longest` s. uj3/ui3: and at least `minimum` s (the longer of
    the two). Returns the wait in seconds."""
    t0 = time.monotonic()
    samples = [(t0, _proc_ticks(pid))]
    time.sleep(max(first, 0.0))
    while True:
        now = time.monotonic(); c = _proc_ticks(pid); samples.append((now, c))
        old = [x for x in samples if now - x[0] >= window]
        if now - t0 >= minimum and old and c - old[-1][1] == 0 and _writeback_kb() < 1024:
            break
        if now - t0 >= longest:
            break
        time.sleep(step)
    return time.monotonic() - t0


def stop_node(pid, meta, out_dir, label):
    # uj3/ui3: ignore further SIGINT/SIGTERM while stopping, so a second interrupt cannot leave the node running (uj2)
    signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN)
    perf_stop()   # EXP-159: the profile ends with the last block, before the node is stopped
    # EXP-199 (EXP-218): the node's threads with their scheduling class and nice value at the run's end, before the stop
    # (with pwbatch only the prewarm threads may be in SCHED_BATCH, class B)
    try:
        with open(os.path.join(out_dir, f'{label}.threads.txt'), 'w') as f:
            subprocess.run(['ps', '-L', '-o', 'tid,cls,ni,comm', '-p', str(pid)], stdout=f, stderr=subprocess.STDOUT, timeout=30)
            # EXP-199 (excore, Master 11-01): every thread's allowed CPUs (with excore only the execution thread may have the
            # execution core)
            f.seek(0, os.SEEK_END)
            f.write('\nTID COMMAND CPUS_ALLOWED\n')
            for tid in sorted(os.listdir(f'/proc/{pid}/task'), key=int):
                try:
                    comm = open(f'/proc/{pid}/task/{tid}/comm').read().strip()
                    cpus = re.search(r'^Cpus_allowed_list:\s*(\S+)', open(f'/proc/{pid}/task/{tid}/status').read(), re.M)
                    f.write(f'{tid} {comm} {cpus.group(1) if cpus else "?"}\n')
                except OSError:
                    pass
    except Exception as e:   # noqa: BLE001 (a failed listing must not keep the node running)
        meta['threads_dump_error'] = str(e)
    # EXP-199 (Master 10-31, round k): the node's resident memory and its peak at the run's end (plans_v3x adds about 2.7 GB)
    try:
        st = open(f'/proc/{pid}/status').read()
        for k in ('VmRSS', 'VmHWM'):
            m = re.search(rf'^{k}:\s+(\d+) kB', st, re.M)
            meta[k.lower() + '_kb'] = int(m.group(1)) if m else -1
    except Exception as e:   # noqa: BLE001
        meta['vm_error'] = str(e)
    time.sleep(5)
    meta['load_after'] = loadavg()
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        meta['node_gone_before_stop'] = True
    t_stop = time.time()
    while os.path.exists(f'/proc/{pid}') and time.time() - t_stop < 600:
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        time.sleep(0.5)
    meta['stop_s'] = time.time() - t_stop
    hc = history_check()
    meta.update(history_check_rc=hc.returncode, history_check_err=hc.stderr[-500:], toml_sha_after=sha(TOML), t_end=time.time())
    json.dump(meta, open(os.path.join(out_dir, f'{label}.meta.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != 'configs'}), flush=True)


if __name__ == '__main__':
    main()
