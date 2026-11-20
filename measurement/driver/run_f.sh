#!/usr/bin/env bash
# apply_x260.py (EXP-260 / X-028): PRECHECK_ALT from PRE_ALT
# EXP-199 (X-020, README section 6.4): a short comparison round. Copy of scripts/run_e.sh with: the label prefix LBL (one
# per round, e.g. f, g, h), the configurations CF (3-4; one pass per configuration, pass p rotates the list by p), the last
# measured block END (default 26,266,604: the first 3,000 blocks of the common segment), the driver copy scripts/run_xl_f.py
# through scripts/session_f.sh, the checkpoint log raw/<LBL>.ckpt and the forward step <LBL>fwd. The first pass also accepts
# the end of the previous experiment (PREV_END, default 26,268,604) and unwinds from it.
# usage: MIN_HEAD=<node head> BIN=<eap-x199c binary in reth/bin-eap> REQ_COMMIT=<eap-x199c commit, c3bbbb0 or later> NBNICE=10 NBGAS=5000000 \
#        LBL=f CF="D-RE ..." [END=26266604] [PASSES="0 1 ..."] run_f.sh   (labq node job)
set -u
# Prologue server copy: scripts/server/apply_server.py
source /prologue/machine.env || { echo "/prologue/machine.env missing"; echo "run_main rc=6"; exit 6; }
cd "$(dirname "$0")/.."; D=$PWD
# EXP-199 (Master 10-31, from round j on; EXP-218 README 6.3: the driver's python took 3-5% of the core time on the node's
# cores while the execution thread waited): this script, the driver and every process they start run on cores 8-15; the
# node is pinned to NODE_CPUS=0-7 by start_node.sh (pcores -c = taskset -c), so its threads stay on 0-7
# apply_w.py (Master 11-01, the 20-core round): DRIVER_CPUS (default 8-15) for the driver, NODE_CPUS_RUN (default 0-7)
# for the node; the defaults are the placement above
DRIVER_CPUS=${DRIVER_CPUS:-$PROLOGUE_DRIVER_CPUS}; export NODE_CPUS_RUN=${NODE_CPUS_RUN:-$PROLOGUE_NODE_CPUS}
taskset -cp "$DRIVER_CPUS" $$ > /dev/null || { echo "cannot move the driver to cores $DRIVER_CPUS"; echo "run_main rc=6"; exit 6; }
echo "driver on cores $DRIVER_CPUS, node on cores $NODE_CPUS_RUN"
MH=${MIN_HEAD:?MIN_HEAD required (the node head, checked exactly)}
BIN=${BIN:?BIN required}
REQ=${REQ_COMMIT:?REQ_COMMIT required (the eap-x199c commit the binary must contain)}
export NBNICE=${NBNICE:?NBNICE required: 10 as EXP-185 C-FA}
export NBGAS=${NBGAS:?NBGAS required: 5000000 as EXP-185 C-FA}
[ "$NBNICE" = 10 ] && [ "$NBGAS" = 5000000 ] || { echo "D-RE, D-WE, D-WEX need NBNICE=10 NBGAS=5000000"; echo "run_main rc=6"; exit 6; }
# apply_wu.py (the researcher 11-01, via Master): 300 warm-up blocks per pass from round m on (600 before); the measured
# blocks start at 26,263,605 as in every earlier round, so the warm-up starts at S = 26,263,605 - W and the passes unwind
# to S - 1 (26,263,304 with 300)
W=${WARMUP_BLOCKS:-300}; (( W >= ${WARMUP_MIN:-200} && W <= 600 )) || { echo "WARMUP_BLOCKS $W outside ${WARMUP_MIN:-200}-600"; echo "run_main rc=6"; exit 6; }
# apply_acc240.py (EXP-240 / X-028): MEAS_START, the first measured block (default 26,263,605 as before)
LBL=${LBL:?LBL required (the round label prefix)}; FWD0=${FWD0:-26261004}; MEAS_START=${MEAS_START:-26263605}; S=$((MEAS_START - W)); END=${END:-26266604}; NMEAS=$((END - S - W + 1)); PREV_END=${PREV_END:-26268604}
# apply_q10.py (EXP-240 / X-028): END_MAX (the highest END accepted; default 26,274,131 as before, q10 26,277,231; the block files
# end at 26,306,842)
END_MAX=${END_MAX:-26274131}; (( END_MAX >= 26274131 && END_MAX <= ${BLOCK_FILES_END:-26306842} )) || { echo "END_MAX $END_MAX outside 26274131-${BLOCK_FILES_END:-26306842}"; echo "run_main rc=6"; exit 6; }
(( END >= S + W + ${MIN_MEAS:-300} - 1 && END <= END_MAX )) || { echo "END $END outside the common segment (END_MAX $END_MAX)"; echo "run_main rc=6"; exit 6; }
(( MH == FWD0 || MH == S - 1 || MH == END || MH == PREV_END )) || { echo "head $MH is none of $FWD0 $((S - 1)) $END $PREV_END"; echo "run_main rc=6"; exit 6; }
read -r -a CF <<< "${CF:?CF required (3-4 configurations)}"   # Master 10-30 21:3x: D-WEG in place of D-WE, so that D-WEX / D-WEG isolates the plan-native order
NC=${#CF[@]}
# apply_s.py (Master 11-01, screening rounds): NPASS passes, default NC (the Latin square as before); NPASS=2 with 3 or more
# configurations: every block gets two of them, pass 1 derived from pass 0 by scripts/pairsched199.py (balanced pairs)
NPASS=${NPASS:-$NC}
# apply_sl.py (EXP-199 final runs, segments of 20 and 10): SEGLEN blocks per segment, fixed (no lengthened segment), schedules handed to the driver as files
SEGLEN=${SEGLEN:-3}; (( SEGLEN >= 3 && SEGLEN <= 40 )) || { echo "SEGLEN $SEGLEN outside 3-40"; echo "run_main rc=6"; exit 6; }
SEGOPT=(); (( SEGLEN != 3 )) && SEGOPT=(--seglen $SEGLEN --no-shift)
# apply_f4.py (final run, Master 11-02): SCHED4=1, four passes of scripts/sched4_199.py (two base rows on every block, one group of two rows each)
SCHED4=${SCHED4:-0}
if [ "$SCHED4" = 1 ]; then
  NPASS=4
  read -r -a S4B <<< "${SCHED4_BASE:?SCHED4_BASE required with SCHED4=1 (two configurations)}"
  S4G=${SCHED4_GROUPS:?SCHED4_GROUPS required with SCHED4=1 (groups of two, e.g. "AB4,AB6 AB2,AB3")}
  [ "$(printf '%s\n' "${S4B[@]}" ${S4G//,/ } | sort | tr '\n' ' ')" = "$(printf '%s\n' "${CF[@]}" | sort | tr '\n' ' ')" ] || \
    { echo "SCHED4: CF must hold the base rows and the groups' rows exactly"; echo "run_main rc=6"; exit 6; }
fi
(( SCHED4 == 1 || NPASS == NC || (NPASS == 2 && NC >= 3) )) || { echo "NPASS $NPASS: $NC (Latin square) or 2 with 3 or more configurations"; echo "run_main rc=6"; exit 6; }
# the version-3 plan library of EXP-201 (X-023): loop-indexed call records; storage keys equal to the version-1/2 libraries on all
# 1,734,567 frames of EXP-099; only configurations that follow call records (cttx, pwct) use them
export PLANS_DIR=${PLANS_DIR:-$PROLOGUE_REPO/experiments/EXP-112-caller-side-prefetch/plans}   # section 6.3: the first comparison's library (no configuration follows call records)   # version 3 (X-023; storage keys as the version-2 library on all 1,734,567 frames)
# a library with a MANIFEST (X-023's completed libraries, EXP-222 scripts/complete_lib222.sh) must match it: the number of
# plans and the sha256 of the sorted file list; a library without one must hold the 19,256 plans of the earlier libraries
if [ -f "$PLANS_DIR/MANIFEST" ]; then
  NP=$(awk '$1 == "files" { print $2 }' "$PLANS_DIR/MANIFEST"); HP=$(awk '$1 == "list_sha256" { print $2 }' "$PLANS_DIR/MANIFEST")
  [ -n "$NP" ] && [ "$(find "$PLANS_DIR" -maxdepth 1 -name '*.eapf' | wc -l)" = "$NP" ] && \
    [ "$(find "$PLANS_DIR" -maxdepth 1 -name '*.eapf' -printf '%f\n' | LC_ALL=C sort | sha256sum | cut -c1-64)" = "$HP" ] || \
    { echo "plan library $PLANS_DIR does not match its MANIFEST"; echo "run_main rc=6"; exit 6; }
  # content_sha256 (X-023, 11-01): the names alone do not tell X-023's corrected library from the x216 one
  HC=$(awk '$1 == "content_sha256" { print $2 }' "$PLANS_DIR/MANIFEST")
  if [ -n "$HC" ]; then
    GC=$(cd "$PLANS_DIR" && find . -maxdepth 1 -name '*.eapf' -printf '%f\n' | LC_ALL=C sort | xargs sha256sum | sha256sum | cut -c1-64)
    [ "$GC" = "$HC" ] || { echo "plan library $PLANS_DIR: content sha256 $GC, MANIFEST $HC"; echo "run_main rc=6"; exit 6; }
  fi
  echo "plan library $PLANS_DIR: $NP plans, list sha256 $HP, content sha256 ${HC:-none in MANIFEST} (MANIFEST, checked)" | { mkdir -p raw; tee raw/$LBL.plans; }
else
  [ "$(ls $PLANS_DIR | grep -c '\.eapf$')" = 19256 ] || { echo "plan library $PLANS_DIR does not hold 19256 plans"; echo "run_main rc=6"; exit 6; }
fi
export CLASSFILE=${CLASSFILE:-$PROLOGUE_REPO/experiments/EXP-193-eap-stepwise/results/blocks_class_zk_a1.csv}
python3 - "$CLASSFILE" $S $END <<'PY' || { echo "class file does not cover $S-$END"; echo "run_main rc=6"; exit 6; }
import csv, sys
c = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(sys.argv[1]))}
miss = [b for b in range(int(sys.argv[2]), int(sys.argv[3]) + 1) if c.get(b) not in ('mint', 'nomint')]
print(f'class file: {len(miss)} blocks of the segment without cls_mint')
raise SystemExit(1 if miss else 0)
PY
mkdir -p blocks raw results
[ -z "${NODE_ENV_ADD:-}" ] || echo "node environment added to the measured passes (NODE_ENV_ADD): $NODE_ENV_ADD"
# apply_af.py (EXP-232 accflt): the filter file named in NODE_ENV_ADD must describe the base the passes restore (S - 1)
AF=$(for kv in ${NODE_ENV_ADD:-}; do case "$kv" in EAP_ACCFILTER=*) echo "${kv#EAP_ACCFILTER=}";; esac; done)
if [ -n "$AF" ]; then
  python3 - "$AF" $((S - 1)) <<'PY' || { echo "filter file $AF does not describe block $((S - 1))"; echo "run_main rc=6"; exit 6; }
import struct, sys
h = open(sys.argv[1], 'rb').read(32)
ok = len(h) == 32 and h[:8] == b'EAPACCF1' and struct.unpack('<Q', h[24:32])[0] == int(sys.argv[2])
print(f'filter file {sys.argv[1]}: magic {h[:8]!r}, block {struct.unpack("<Q", h[24:32])[0] if len(h) == 32 else None}, {"ok" if ok else "WRONG"}')
raise SystemExit(0 if ok else 1)
PY
fi
(source "$PROLOGUE_NODE_HOME/engine-replay/node-common.sh" >/dev/null; link_blocks $((FWD0 + 1)) $END "$D/blocks")   # links to the pool on another disk, the range only
for b in $(seq $((FWD0 + 1)) $END); do [ -e blocks/$b.json ] || { echo "block file $b missing"; echo "run_main rc=6"; exit 6; }; done
[ -x $BIN ] || { echo "binary missing"; echo "run_main rc=4"; exit 4; }
# apply_settle5.py (Master 11-02): the longest wait after a block is SETTLE_MAX (default 5 s, was 2 s), so that a block never arrives during the 16-block persistence write
# apply_v290.py (reth 2.9.0 binaries, Master 11-02): the node's libraries (NODE_LD_LIBRARY_PATH, start_node.sh), the checkpoint reader (CKPT_BIN)
export NODE_LD_LIBRARY_PATH=${NODE_LD_LIBRARY_PATH-}
LD_LIBRARY_PATH=$NODE_LD_LIBRARY_PATH ldd $BIN | grep -q "not found" && { echo "ldd $BIN: libraries not found with LD_LIBRARY_PATH=$NODE_LD_LIBRARY_PATH"; echo "run_main rc=4"; exit 4; }
if [ -n "${CKPT_BIN:-}" ]; then
  [[ "$CKPT_BIN" = /* && -x "$CKPT_BIN" ]] || { echo "CKPT_BIN $CKPT_BIN: an absolute path to an executable"; echo "run_main rc=6"; exit 6; }
  [ "${RESTORE:-}" = reflink ] || { echo "CKPT_BIN requires RESTORE=reflink (the forward step and the unwind use the 2.5.1 tools)"; echo "run_main rc=6"; exit 6; }
  export CKPT_BIN; echo "checkpoints read by $CKPT_BIN ($($CKPT_BIN --version 2>/dev/null | sed -n 's/^Reth Version: *//p'))"
fi
BSHA=$($BIN --version 2>/dev/null | sed -n 's/^Commit SHA: *//p')
git -C "${REQ_REPO:-$PROLOGUE_RETH_REPO}" merge-base --is-ancestor "$REQ" "$BSHA" 2>/dev/null || { echo "binary commit $BSHA does not contain $REQ"; echo "run_main rc=4"; exit 4; }
# the schedules of all passes, and the check that every measured block gets every configuration once at the same position
if [ "$SCHED4" = 1 ]; then   # apply_f4.py: the four passes at once, with their check
  python3 scripts/sched4_199.py build $((S + W)) $END --base "${S4B[*]}" --groups "$S4G" --seed ${SCHED4_SEED:-199} --out raw/$LBL | tee raw/$LBL.sched4.check
  [ "${PIPESTATUS[0]}" = 0 ] || { echo "sched4 schedule check failed"; echo "run_main rc=6"; exit 6; }
  for (( p = 0; p < 4; p++ )); do echo "${CF[*]}" > raw/$LBL$p.cfgs; done
fi
for (( p = 0; p < NPASS && SCHED4 != 1; p++ )); do
  rot=(); for (( i = 0; i < NC; i++ )); do rot+=("${CF[$(( (i + p) % NC ))]}"); done
  if (( NPASS < NC && p == 1 )); then   # apply_s.py: pass 1 of the pair design, same segments as pass 0
    rot=("${CF[@]}"); echo "${rot[*]}" > raw/$LBL$p.cfgs
    python3 scripts/pairsched199.py derive raw/${LBL}0.schedule.csv "${CF[@]}" --out raw/$LBL$p.schedule.csv > raw/$LBL$p.schedule.check || { echo "schedule $p failed"; echo "run_main rc=6"; exit 6; }
    continue
  fi
  echo "${rot[*]}" > raw/$LBL$p.cfgs
  python3 $PROLOGUE_REPO/scripts/schedule_runs3.py $((S + W)) $END "${rot[@]}" "${SEGOPT[@]}" --out raw/$LBL$p.schedule.csv > raw/$LBL$p.schedule.check || { echo "schedule $p failed"; echo "run_main rc=6"; exit 6; }
done
if [ "$SCHED4" = 1 ]; then
  python3 scripts/sched4_199.py check raw/$LBL --base "${S4B[*]}" --groups "$S4G" > /dev/null || { echo "sched4 check of the written schedules failed"; echo "run_main rc=6"; exit 6; }
elif (( NPASS < NC )); then
  python3 scripts/pairsched199.py check $LBL "${CF[@]}" | tee raw/$LBL.pairs.check; [ "${PIPESTATUS[0]}" = 0 ] || { echo "pair design check failed"; echo "run_main rc=6"; exit 6; }
else
python3 - "$NC" "$LBL" <<'PY' || { echo "Latin square check failed"; echo "run_main rc=6"; exit 6; }
import csv, sys
n = int(sys.argv[1])
S = [{int(r['block']): (r['cfg'], r['pos']) for r in csv.DictReader(open(f'raw/{sys.argv[2]}{p}.schedule.csv'))} for p in range(n)]
bad = [b for b in S[0] if len({S[p][b][0] for p in range(n)}) != n or len({S[p][b][1] for p in range(n)}) != 1]
print(f'Latin square: {len(S[0])} blocks, {len(bad)} without all {n} configurations at one position')
raise SystemExit(1 if bad else 0)
PY
fi
reth_running() { local q e; pgrep -x reth >/dev/null && return 0; for q in $(pgrep -f reth); do e=$(basename "$(readlink /proc/$q/exe 2>/dev/null)"); case "$e" in reth*) return 0;; esac; done; return 1; }   # local q: the loop variable must not overwrite the pass number (EXP-198 25cb0df8)
# apply_ckpt290.py (Master 11-02): the reader's stderr goes to raw/<LBL>.ckpt.err (one header line per call)
CKERR=$D/raw/$LBL.ckpt.err
ckpt() { echo "$(date -Is) ckpt by ${CKPT_BIN:-./bin/reth}" >> "$CKERR"; (cd $PROLOGUE_NODE_HOME && ulimit -n "$(ulimit -Hn)" && "${CKPT_BIN:-./bin/reth}" db --datadir data --chain mainnet list StageCheckpoints --json 2>>"$CKERR" | sed -n '/^\[/,$p' | jq -c '[.[] | {(.[0]): .[1].block_number}] | add'); }
# with CKPT_BIN (2.9.0): Bodies, Execution, Finish in [END - 64, END], AccountHashing in [END - 94, END] (scripts/apply_ckpt290.py)
near290() { echo "$1" | jq -e --argjson h "$2" '([.Bodies, .Execution, .Finish] | all(. != null and . <= $h and . >= $h - 64)) and (.AccountHashing != null and .AccountHashing <= $h and .AccountHashing >= $h - 94)' >/dev/null; }
hist() { if [ -n "${CKPT_BIN:-}" ]; then (source $D/scripts/history_window.sh; check_history_window_bin "$CKPT_BIN"); else (source $PROLOGUE_NODE_HOME/engine-replay/node-common.sh >/dev/null; check_history_window); fi; }
at() { echo "$1" | jq -e --argjson h "$2" '[.AccountHashing, .Bodies, .Execution, .Finish] | all(. == $h)' >/dev/null; }
ulimit -n "$(ulimit -Hn)"
TOML=$PROLOGUE_NODE_HOME/data/reth.toml; sha0=$(sha256sum $TOML | cut -d' ' -f1)
# apply_rr.py (Master 11-01): RESTORE=reflink puts the database back from RESTORE_BASE before every pass
RESTORE=${RESTORE:-}; RESTORE_SH=${RESTORE_SH:-/prologue/scripts/restore_reflink.sh}
if [ -n "$RESTORE" ]; then
  [ "$RESTORE" = reflink ] || { echo "RESTORE $RESTORE: only reflink"; echo "run_main rc=6"; exit 6; }
  [ -d "${RESTORE_BASE:?RESTORE_BASE required with RESTORE=reflink}/db" ] || { echo "RESTORE_BASE $RESTORE_BASE has no db/"; echo "run_main rc=6"; exit 6; }
  [ -x "$RESTORE_SH" ] || { echo "restore script $RESTORE_SH missing"; echo "run_main rc=6"; exit 6; }
  echo "restore before every pass: $RESTORE_SH $RESTORE_BASE (the head must then be $((S - 1)))"
fi
rc=0
ALLP=$(seq -s ' ' 0 $((NPASS - 1)))
for p in ${PASSES:-$ALLP}; do
  L=$LBL$p
  if reth_running; then echo "a reth process is running before pass $p"; rc=3; break; fi
  c=$(ckpt); echo "$(date -Is) pass $p checkpoints before: $c" | tee -a raw/$LBL.ckpt
  if [ -n "$RESTORE" ]; then   # apply_rr.py: in place of the forward step and the unwind, whatever the head
    echo "$(date -Is) pass $p: restore from $RESTORE_BASE" | tee -a raw/$LBL.ckpt
    t0=$(date +%s)
    "$RESTORE_SH" "$RESTORE_BASE" > raw/$L.restore.log 2>&1 || { echo "pass $p: restore failed: $(tail -1 raw/$L.restore.log)"; rc=11; break; }
    c=$(ckpt); echo "$(date -Is) pass $p checkpoints after the restore ($(( $(date +%s) - t0 )) s): $c" | tee -a raw/$LBL.ckpt
    at "$c" $((S - 1)) || { echo "pass $p: restore did not give $((S - 1))"; rc=12; break; }
  elif at "$c" $FWD0; then
    # the forward step from the snapshot head to S - 1 with stock S0, advance only (EXP-197 run_r1.sh step 1); records of an
    # earlier attempt are kept aside
    [ -e raw/${LBL}fwd.jsonl ] || [ -e raw/${LBL}fwd.run.log ] && { fd=raw/old-${LBL}fwd-$(date +%m%d%H%M%S); mkdir -p $fd; mv raw/${LBL}fwd.* $fd/; }
    hist || { echo "pass $p: history check failed before the forward step"; rc=4; break; }
    echo "$(date -Is) pass $p: forward $((FWD0 + 1))-$((S - 1)) with S0, not measured" | tee -a raw/$LBL.ckpt
    NODE_ENV="EAP_CTRL=$D/raw/${LBL}fwd.ctrl EAP_PLANS=$PLANS_DIR" EAP_CTRL_FILE=$D/raw/${LBL}fwd.ctrl EAP_PLANS=$PLANS_DIR NODE_CPUS=$NODE_CPUS_RUN PGATE=0 \
      SEQ=S0 WARM=S0 MIN_HEAD=$FWD0 EXACT_HEAD=$FWD0 MAX_END=$((S - 1)) FFWD_TO=$S SETTLE_MIN=0 SETTLE_MAX=0 LEAD=0 \
      python3 -u scripts/run_xl_f.py ${LBL}fwd "$BIN" 0 "$D/blocks" "$D/raw" 0 -- --engine.slow-block-threshold 0 --color never --jit > raw/${LBL}fwd.run.log 2>&1
    frc=$?
    t0=$(date +%s); while reth_running && (( $(date +%s) - t0 < 600 )); do sleep 5; done
    reth_running && { echo "pass $p: reth still running after the forward step"; rc=9; break; }
    echo "forward rc=$frc"; tail -2 raw/${LBL}fwd.run.log
    (( frc == 0 )) || { echo "pass $p: forward step failed"; rc=13; break; }
    c=$(ckpt); echo "$(date -Is) pass $p checkpoints after the forward step: $c" | tee -a raw/$LBL.ckpt
    at "$c" $((S - 1)) || { echo "pass $p: forward step did not reach $((S - 1))"; rc=12; break; }
  elif ! at "$c" $((S - 1)); then
    at "$c" $END || at "$c" $PREV_END || { echo "pass $p: head none of $FWD0 $((S - 1)) $END $PREV_END"; rc=10; break; }
    echo "$(date -Is) pass $p: unwind to $((S - 1))" | tee -a raw/$LBL.ckpt
    scripts/unwind.sh to-block $((S - 1)) > raw/$L.unwind.log 2>&1 || { echo "pass $p: unwind failed"; rc=11; break; }
    c=$(ckpt); echo "$(date -Is) pass $p checkpoints after the unwind: $c" | tee -a raw/$LBL.ckpt
    at "$c" $((S - 1)) || { echo "pass $p: unwind did not reach $((S - 1))"; rc=12; break; }
  fi
  hist || { echo "pass $p: history check failed"; rc=4; break; }
  [ "$(sha256sum $TOML | cut -d' ' -f1)" = "$sha0" ] || { echo "pass $p: reth.toml changed"; rc=4; break; }
  python3 scripts/evict_cache.py > raw/$L.evict.log 2>&1 || { echo "pass $p: eviction refused"; rc=5; break; }
  cat raw/$L.evict.log
  # apply_mem248.py (EXP-248, Master 11-04): PREREAD_DATADIR reads the database file once, in order, inside this scope, so that
  # its page cache starts full before the node starts (off when unset)
  if [ -n "${PREREAD_DATADIR:-}" ]; then
    python3 scripts/preread248.py "$PREREAD_DATADIR" > raw/$L.preread.log 2>&1 || { echo "pass $p: pre-read failed: $(tail -1 raw/$L.preread.log)"; rc=5; break; }
    cat raw/$L.preread.log
  fi
  grep -E 'workingset_refault_file|allocstall|pgmajfault|pswpin|pswpout' /proc/vmstat > raw/$L.vmstat.before
  # apply_mem290.py (EXP-237, Master 11-02): NODE_MEM_MAX caps this labq job's scope (driver and node) for the pass
  if [ -n "${NODE_MEM_MAX:-}" ]; then
    [ -n "${LABQ_JOB_ID:-}" ] || { echo "pass $p: NODE_MEM_MAX needs a labq job (LABQ_JOB_ID unset)"; rc=6; break; }
    MSC=labq-$LABQ_JOB_ID.scope; MCG=/sys/fs/cgroup$(awk -F: '$1=="0"{print $3}' /proc/self/cgroup)
    case "$MCG" in */$MSC) ;; *) echo "pass $p: this script is in $MCG, not in $MSC"; rc=6; break;; esac
    systemctl --user set-property --runtime "$MSC" MemoryMax="$NODE_MEM_MAX" MemorySwapMax=0 || { echo "pass $p: cannot set MemoryMax on $MSC"; rc=6; break; }
    mwant=$(numfmt --from=iec "$NODE_MEM_MAX"); mgot=$(cat $MCG/memory.max)
    [ "$mgot" = "$mwant" ] && [ "$(cat $MCG/memory.swap.max)" = 0 ] || { echo "pass $p: memory.max $mgot, want $mwant (swap.max $(cat $MCG/memory.swap.max))"; rc=6; break; }
    echo "pass $p: memory.max $mgot on $MSC, swap 0"
    { cat $MCG/memory.events; grep -E '^(anon|file|workingset_refault_file|pgmajfault) ' $MCG/memory.stat; } > raw/$L.memcg.before
  fi
  /prologue/scripts/node_status.sh > raw/$L.labq.before 2>&1
  CFGS3="$(cat raw/$LBL$p.cfgs)"
  [ "$(echo $CFGS3 | wc -w)" = "$NC" ] && [ "$L" = "$LBL$p" ] || { echo "pass $p: configuration list \"$CFGS3\" or label $L wrong"; rc=6; break; }
  # apply_d290.py (EXP-239/241, Master 11-02): NODE_XARGS appended to the node arguments of the measured passes
  RUNS3_SCHEDULE=$( (( NPASS < NC || SEGLEN != 3 )) && echo $D/raw/$L.schedule.csv ) BIN=$BIN SEQ="$CFGS3" RUNS3=1 RUNS3_CFGS="$CFGS3" END_BLOCK=$END EXTRA_ARGS="--jit${NODE_XARGS:+ $NODE_XARGS}" MIN_HEAD=$((S - 1)) EXACT_HEAD=$((S - 1)) MAX_END=$END FFWD_TO=0 WARM=${WARM_CONFIG:-K-W} \
    JIT_SWITCH=0 FILLER= NFILL=0 SETTLE_MIN=${SETTLE_MIN:-1} SETTLE_MIN_MEASURED=${SETTLE_MIN_MEASURED:-${SETTLE_MIN:-1}} SETTLE_MAX=${SETTLE_MAX:-5} LEAD=0 PRECHECK=${PRECHECK:-100} PRECHECK_CFG=${PRE_CONFIG:-D-WEX1} PRECHECK_ALT=${PRE_ALT:-} PRECHECK_C2=0 \
    PRECHECK_ACCT=report PRECHECK_GATE=report CLASSFILE=$CLASSFILE \
    scripts/session_f.sh $L $W $NMEAS > raw/$L.session.log 2>&1
  grep -E 'workingset_refault_file|allocstall|pgmajfault|pswpin|pswpout' /proc/vmstat > raw/$L.vmstat.after
  if [ -n "${NODE_MEM_MAX:-}" ]; then   # apply_mem290.py (EXP-237, Master 11-02)
    { cat $MCG/memory.events; grep -E '^(anon|file|workingset_refault_file|pgmajfault) ' $MCG/memory.stat; } > raw/$L.memcg.after
    systemctl --user set-property --runtime "$MSC" MemoryMax=infinity MemorySwapMax=infinity || echo "pass $p: could not lift the cap on $MSC"
    echo "pass $p: memory.events after: $(tr '\n' ' ' < raw/$L.memcg.after)"
  fi
  /prologue/scripts/node_status.sh > raw/$L.labq.after 2>&1
  t0=$(date +%s); while reth_running && (( $(date +%s) - t0 < 600 )); do sleep 5; done
  reth_running && { echo "pass $p: reth still running after the driver ended"; rc=9; break; }
  if grep -q "below MIN_HEAD\|is not EXACT_HEAD\|MAX_END\|Traceback\|precheck failed\|reuse difference\|newPayload {\|nice check failed\|node panicked\|schedule_runs3 check failed\|undefined configurations" raw/$L.run.log 2>/dev/null || [ ! -s raw/$L.jsonl ]; then
    echo "pass $p: driver refused, failed or stopped: $(grep -m1 "below MIN_HEAD\|is not EXACT_HEAD\|MAX_END\|precheck failed\|reuse difference\|newPayload {\|nice check failed\|node panicked\|schedule_runs3 check failed\|undefined configurations\|Error" raw/$L.run.log)"
    rc=6; break
  fi
  # the driver's schedule must equal the pre-computed one (the rotation is what makes the passes a Latin square)
  python3 - "$L" <<'PY' || { echo "pass $p: driver schedule differs from raw/$L.schedule.csv"; rc=6; break; }
import csv, json, sys
L = sys.argv[1]
want = {int(r['block']): r['cfg'] for r in csv.DictReader(open(f'raw/{L}.schedule.csv'))}
got = {j['block']: j['cfg'] for j in (json.loads(x) for x in open(f'raw/{L}.jsonl')) if j.get('role') == 'measured'}
bad = [b for b, c in want.items() if got.get(b) != c]
print(f'{L}: measured {len(got)}, schedule mismatches {len(bad)}')
raise SystemExit(1 if bad or len(got) != len(want) else 0)
PY
  # apply_af.py: the filter was checked against the restored database and installed exactly once in this pass
  if [ -n "$AF" ]; then
    naf=$(grep -c "eap accflt loaded" raw/$L.node.log 2>/dev/null || true)
    echo "pass $p: eap accflt loaded lines $naf"
    [ "$naf" = 1 ] || { echo "pass $p: $naf 'eap accflt loaded' lines, 1 expected"; rc=6; break; }
  fi
  # apply_ckpt290.py (Master 11-02): wait for the node to exit, read up to 3 times, the node log must end at END, 2.9.0 may lag
  w=0; while reth_running && (( w < 120 )); do sleep 1; w=$((w + 1)); done
  if reth_running; then echo "pass $p: a reth process is still running 120 s after the run"; rc=10; break; fi
  c=""; for k in 1 2 3; do c=$(ckpt); [ -n "$c" ] && break; sleep 10; done
  echo "$(date -Is) pass $p checkpoints after the run: $c (waited $w s for reth to exit, $k reads)" | tee -a raw/$LBL.ckpt
  last=$(grep -v slow_block raw/$L.node.log | grep -oP 'Block added to canonical chain number=\K[0-9]+' | tail -1)
  [ "$last" = "$END" ] || { echo "pass $p: the node log's last added block is ${last:-none}, not $END"; rc=10; break; }
  if [ -z "${CKPT_BIN:-}" ]; then
    at "$c" $END || { echo "pass $p: head after the run is not $END"; rc=10; break; }
  elif [ -z "$c" ]; then
    echo "pass $p: checkpoints unreadable by $CKPT_BIN after the run (stderr: raw/$LBL.ckpt.err, last lines below)"; tail -5 "$CKERR" | cut -c1-300
    [ "${CKPT_UNREADABLE_OK:-0}" = 1 ] || { echo "pass $p: CKPT_UNREADABLE_OK is not 1"; rc=10; break; }
    echo "pass $p: accepted (CKPT_UNREADABLE_OK=1, the node log ends at $END, the next pass restores the base)"
  else
    near290 "$c" $END || { echo "pass $p: 2.9.0 checkpoints after the run outside [END - 64, END] (AccountHashing [END - 94, END])"; rc=10; break; }
    at "$c" $END || echo "pass $p: 2.9.0 checkpoints lag $END (accepted, apply_ckpt290.py): $c"
  fi
  python3 scripts/parse.py $L > raw/$L.parse.log 2>&1
done
echo "run_main rc=$rc"
exit $rc
