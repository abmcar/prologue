# EXP-257 (written before the run, 11-07; copied from EXP-252 scripts/final2_pre.sh): settings and step-0 checks of one
# node process of the main measurement. Sourced by scripts/main257.sh as root on a Prologue server, after SEG, KIND (up:
# the official build; int: the integration build prologue-int-1107), BIN, BIN_SHA, INT_COMMIT (int only), NC, NAMES and
# CTRL are set. Changes from EXP-252:
#   - SEG is any segment number 0-99 (README 2: k = 14-23 for new bases, or 0-9); segment k: base base-(26,305,830 +
#     1000k), warm-up 300 blocks, measured 26,306,131 + 1000k to 26,307,130 + 1000k;
#   - BASE and AF may name a base on another file system (the storage tiers, README 5.2); the node's working database
#     must then be on that file system too (restore_reflink.sh checks it);
#   - for int, the binary's commit must also contain cff5517, 814f5b8 and b847c9a (prologue-int-1107, as EXP-256);
#     NOCONS_COMMIT defaults to 562432d; the driver must carry apply_final257.py once, and apply_i4_254.py (NODIAG,
#     NOSLOW) in session_f.sh and start_node.sh.
source /prologue/machine.env || { echo "no /prologue/machine.env"; exit 4; }
SEG=${SEG:?SEG (0-99) required}; [[ "$SEG" =~ ^[0-9]{1,2}$ ]] || { echo "SEG $SEG: 0-99"; exit 4; }
TO=$((${SEG0:-26305830} + 1000 * SEG));   # SEG0: EXP-270 route C (26325037); default the original segments
 MS=$((TO + 301)); ME=${ME:-$((TO + 1300))}; W=300; DC=28-31
# KIND up: the official build c9a780f (README 2), no Prologue commits; KIND int: the integration build, containing the
# commits of the main configuration's switches (a8eee90, reusefb's 42c3f88, exio's f20d7d3; researcher 11-05 10:02)
B=${BIN:?BIN required}; BSHA_WANT=${BIN_SHA:?BIN_SHA required}
case ${KIND:?KIND up or int} in
  up)  INT_COMMIT=${UP_COMMIT:-c9a780f}; REQ=c9a780f; REQS=$([ "${UP_COMMIT:-c9a780f}" = c9a780f ] || echo c9a780f) ;;   # EXP-270: c9a780f + 2bd2e69 (UP_COMMIT 3e2aba9)
  int) INT_COMMIT=${INT_COMMIT:?INT_COMMIT required for the integration build}; REQ=c069aab
       REQS="c069aab b615e7b a8eee90 42c3f88 f20d7d3 cf597d8 5401534 926ce62 ${NOCONS_COMMIT:-562432d} cff5517 814f5b8 b847c9a" ;;
  *)   echo "KIND $KIND: up or int"; exit 4 ;;
esac
BASE=${BASE:-/data/node/base-$TO}; AF=${AF:-/data/node/accflt-$TO.bin}
PLANS=${PLANS:-/prologue/data/plans_final}   # X-031 (EXP-269): a completed library can be given
CLASSF=$PROLOGUE_REPO/experiments/EXP-240-e2e-after-exec/results/prologue_class_26299455_26340032.csv
CLASS_SHA=ebc515a4a6f1417527a2018cd0c98fd61ae3c9ef960ded5a1ea6c4c577e6fba9
ENVADD="EAP_CODE_VICTIM_ENTRIES=1048576 EAP_ACCFILTER=$AF EAP_PLAN_CACHE_MB=5120"   # q10's node environment, this base's filter
# the official build reads none of these; without EAP_ACCFILTER run_f.sh also skips its check that the filter was loaded
# once per pass (run_f.sh 84-85, 240-244; e251tr-0 stopped there with rc=6, 11-05 08:15)
[ "$KIND" = up ] && ENVADD=""
ts() { TZ=Asia/Shanghai date '+%m-%d %H:%M'; }
stop() { echo "$*; stop $(ts)"; exit 4; }
SRD_MARK='# apply_srdiag_off.py (EXP-240 / X-028)'

pre_checks() {
  [ "$(id -u)" = 0 ] || stop "run as root (prologue_run.sh drops to user prologue)"
  # Master 11-04 18:3x (the deployment session's trial on t1): user.slice is bound to cpus 28-31, so a process of an ssh
  # session cannot be moved onto the node's cpus (taskset: Invalid argument); start the script in a scope under system.slice
  local cg; cg=$(awk -F: '$1 == "0" { print $3 }' /proc/self/cgroup)
  [[ "$cg" =~ ^/system\.slice/[^/]+\.scope$ ]] || stop "this script runs in $cg, not in a scope under system.slice; start it as
  systemd-run --scope --quiet -- env [DRY=1 ...] ${LAUNCH:-bash $0}"
  taskset -c "$NC" true && taskset -c $DC true || stop "taskset refuses $NC or $DC"
  python3 - "$NC" <<'PY' || stop "node cpus $NC not inside 0-27"
import sys
s = set()
for p in sys.argv[1].split(','):
    a, _, b = p.partition('-'); s.update(range(int(a), int(b or a) + 1))
sys.exit(0 if s and s <= set(range(28)) else 1)
PY
  [ -x "$B" ] || stop "binary $B missing"
  [ "$(sha256sum "$B" | cut -c1-64)" = "$BSHA_WANT" ] || stop "binary $B is not sha256 $BSHA_WANT"
  v=$("$B" --version 2>/dev/null | sed -n 's/^Commit SHA: *//p')
  case "$v" in "$INT_COMMIT"*) ;; *) stop "binary $B commit '$v' is not $INT_COMMIT";; esac
  for r in $REQS; do git -C "$PROLOGUE_RETH_REPO" merge-base --is-ancestor $r "$v" 2>/dev/null || stop "binary commit $v does not contain $r"; done
  if [ "${BASE_OK:-1}" = 1 ] || [ "${DRY:-0}" != 1 ]; then
    [ -d "$BASE/db" ] || stop "base $BASE has no db/"
    python3 - "$AF" "$TO" <<'PY' || stop "filter file $AF does not describe $TO"
import struct, sys
h = open(sys.argv[1], 'rb').read(32)
sys.exit(0 if len(h) == 32 and h[:8] == b'EAPACCF1' and struct.unpack('<Q', h[24:32])[0] == int(sys.argv[2]) else 1)
PY
  else
    echo "BASE_OK=0 (DRY=1 only): base and filter checks skipped"
  fi
  [ "$(sha256sum "$CLASSF" | cut -d' ' -f1)" = "$CLASS_SHA" ] || stop "class file $CLASSF is not the committed one"
  if [ "${BASE_OK:-1}" = 0 ] && [ "${DRY:-0}" = 1 ]; then echo "BASE_OK=0 (DRY=1 only): block-file coverage not checked (the blocks come with the base, pull_base257.sh)"; else
  python3 - "$PROLOGUE_BLOCKS_POOL" "$CLASSF" $((TO + 1)) $MS "$ME" <<'PY' || stop "block files or the class file do not cover the run"
import csv, os, sys
pool, cls, lo, ms, me = sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:])
miss = [b for b in range(lo, me + 1) if not os.path.exists(f'{pool}/{b}.json')]
c = {int(r['block']): r['cls_mint'] for r in csv.DictReader(open(cls))}
nocls = [b for b in range(lo, me + 1) if b not in c]
mint = sum(c.get(b) == 'mint' for b in range(ms, me + 1))
print(f'blocks {lo}-{me}: {len(miss)} block files missing, {len(nocls)} without a class; measured {ms}-{me}: '
      f'batch-mint {mint} ({100 * mint / (me - ms + 1):.2f}%)')
sys.exit(1 if miss or nocls else 0)
PY
  fi
  # run_f.sh lines 30-37 with these values (W 200-600; END_MAX within 26274131-BLOCK_FILES_END; END >= S + W + 299 and
  # <= END_MAX; MIN_HEAD one of FWD0, S - 1, END, PREV_END)
  local S=$((MS - W))
  (( W >= 200 && W <= 600 )) || stop "warm-up $W outside 200-600"
  (( ME >= 26274131 && ME <= BLOCK_FILES_END )) || stop "END_MAX $ME outside 26274131-$BLOCK_FILES_END"
  (( ME >= S + W + 299 )) || stop "END $ME below $((S + W + 299))"
  (( TO == S - 1 )) || stop "MIN_HEAD $TO is not the warm-up start minus one ($((S - 1)))"
  local NP HP
  NP=$(awk '$1 == "files" { print $2 }' $PLANS/MANIFEST); HP=$(awk '$1 == "list_sha256" { print $2 }' $PLANS/MANIFEST)
  [ -n "$NP" ] && [ "$(find $PLANS -maxdepth 1 -name '*.eapf' | wc -l)" = "$NP" ] && \
    [ "$(find $PLANS -maxdepth 1 -name '*.eapf' -printf '%f\n' | LC_ALL=C sort | sha256sum | cut -c1-64)" = "$HP" ] || stop "plan library $PLANS does not match its MANIFEST"
  local p e
  for p in /proc/[0-9]*; do e=$(readlink $p/exe 2>/dev/null) || continue; case "$(basename "$e")" in reth*) stop "a reth process is running ($p)";; esac; done
  exec 9>"$PROLOGUE_RUN_LOCK"; flock -n 9 || stop "the run lock $PROLOGUE_RUN_LOCK is held"; exec 9>&-
  for n in $NAMES; do [ ! -e /work/runs/$n ] || stop "/work/runs/$n exists"; done
  echo "driver range and plan library checks passed: measured $MS-$ME ($((ME - MS + 1)) blocks), warm-up from $S, head $TO, $NP plans"
  local sd; sd=$(tr ' ' '\n' <<< "${CTRL:-}" | grep '^srdiag=' | tail -1)
  [ "$sd" = srdiag=0 ] || stop "CTRL '${CTRL:-}' does not end its srdiag tokens with srdiag=0 (README 23)"
  [ "$(grep -cF "$SRD_MARK" "$PROLOGUE_DRIVER/run_xl_f.py")" = 1 ] || stop "$PROLOGUE_DRIVER/run_xl_f.py does not carry apply_srdiag_off.py once (the deployment session adds it through apply_server.py)"
  echo "every control line gets CTRL_ADD=\"$CTRL\"; the driver carries apply_srdiag_off.py"
  [ "$(grep -c '^# apply_final252.py (EXP-252 / X-028)' "$PROLOGUE_DRIVER/run_xl_f.py")" = 1 ] || stop "$PROLOGUE_DRIVER/run_xl_f.py does not carry apply_final252.py once"
  [ "$(grep -c '^# apply_final257.py (EXP-257 / main measurement)' "$PROLOGUE_DRIVER/run_xl_f.py")" = 1 ] || stop "$PROLOGUE_DRIVER/run_xl_f.py does not carry apply_final257.py once"
  grep -q 'apply_i4_254.py (EXP-254 / X-028): NODIAG=1' "$PROLOGUE_DRIVER/session_f.sh" || stop "session_f.sh does not carry apply_i4_254.py (NODIAG)"
  grep -q 'apply_i4_254.py (EXP-254 / X-028): NODIAG=1' "$PROLOGUE_DRIVER/start_node.sh" || stop "start_node.sh does not carry apply_i4_254.py (NODIAG)"
  [ "$(grep -c '^# apply_prologue_lean.py (Prologue server, 11-04)' "$PROLOGUE_DRIVER/run_xl_f.py")" -ge 1 ] || stop "the driver does not carry apply_prologue_lean.py (LEAN_MODE)"
  echo "node cpus $NC, driver $DC; binary $B ($v, sha256 $(sha256sum "$B" | cut -c1-16)); base $BASE; filter $AF; runs $NAMES"
}

# one run_f.sh run through prologue_run.sh (EXP-251, unchanged in EXP-252 and EXP-257): rows CF, warm-up row WARM, pre-check row PRE with PRECHECK blocks
# (0: none, for the official build), NODE_RTPRIO only when RTPRIO is set (README 3.8); segments of 10 blocks, every pass
# restored from the segment's base (README 3.7). Extra NAME=VALUE arguments go to run_f.sh.
# usage: one_run NAME LBL "CF" WARM PRE PRECHECK RTPRIO [VAR=VALUE ...]   (RTPRIO empty: not set)
one_run() {
  local name=$1 lbl=$2 cf=$3 warm=$4 pre=$5 prechk=$6 rt=$7; shift 7
  local a; for a in "$@"; do [[ "$a" == CTRL_ADD=* ]] && stop "one_run: CTRL_ADD comes from CTRL, not from an argument ($a)"; done
  local rtarg=(); [ -n "$rt" ] && rtarg=(NODE_RTPRIO="$rt")
  echo "$(ts) run $name (LBL $lbl): CF=$cf WARM=$warm PRE=$pre PRECHECK=$prechk RTPRIO=${rt:-unset} $*"
  bash /prologue/scripts/prologue_run.sh "$name" \
    NODE_CPUS_RUN="$NC" NODE_CPUS="$NC" PGATE_CPUS="$NC" DRIVER_CPUS=$DC CLASSFILE="$CLASSF" \
    CKPT_UNREADABLE_OK=1 FWD0=$TO MIN_HEAD=$TO RESTORE=reflink RESTORE_BASE="$BASE" "${rtarg[@]}" NBNICE=10 NBGAS=5000000 PLANS_DIR=$PLANS \
    BIN="$B" CKPT_BIN="$B" REQ_COMMIT=$REQ REQ_REPO="$PROLOGUE_RETH_REPO" \
    LBL="$lbl" CF="$cf" MEAS_START=$MS END="$ME" END_MAX="$ME" SEGLEN=10 WARM_CONFIG="$warm" PRE_CONFIG="$pre" PRECHECK="$prechk" \
    NODE_ENV_ADD="$ENVADD" "CTRL_ADD=$CTRL" "$@"
  local rc=$?
  (( rc == 0 )) && ! grep -q "run_main rc=0" /work/runs/$name/raw/run_main.log 2>/dev/null && rc=5   # the driver's own end line
  echo "$(ts) run $name rc=$rc; copy /work/runs/$name/{raw,results} back to the development host"
  return $rc
}
