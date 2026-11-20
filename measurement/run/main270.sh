#!/bin/bash
# EXP-270 (written before the run, 11-13; from EXP-257 scripts/main257.sh and EXP-269 scripts/run269.sh): one node process
# of the final measurement on a Shanghai i5 or i4 (pc14h: node on logical cpus 0-27, driver on 28-31), from segment k's
# base (README 2: the original segments, SEG0 26305830; the unwind succeeded, 11-13 21:4x). Records off (NODIAG=1 NOSLOW=1, CTRL_ADD
# "srdiag=0 ctlcache=1") unless the mode says otherwise.
#   up <k>     the official build, row U8, one pass, no pre-check, no NODE_RTPRIO                     run e270<X>up-<k>
#   ur <k>     as up, with --engine.prewarm-reuse                                                      run e270<X>ur-<k>
#   un <k>     as up, with --engine.disable-prewarming                                                 run e270<X>un-<k>
#   pn <k>     the integration build, row F8 (frozen), pre-check F8chk (100 blocks)                   run e270<X>pn-<k>
#   pp <k>     the integration build, row P8 (Prologue without plans), pre-check P8chk                 run e270<X>pp-<k>
#   abl <k>    rows H0 H1 H2 H3 H4 H5 HX HC HXC, nine passes (Latin square)                            run e270<X>abl-<k>
#   rec <k>    rows H0n H0 H3 H4 H5, five passes, records ON (EAP_DIAG, CC_CACHETIME, slow-block
#              threshold 0) and logq=0 at the end of the control line (the per-block eap lines back)   run e270<X>rec-<k>
#   tchk <k>   the trial (README 11): rows H0 H3 H4 HXC, four passes over 400 measured blocks, logq=0 xbtl2=1 (switch
#              echoes), other records off                                                              run e270<X>tchk-<k>
#   st<c> <k>  storage tiers (README 5), TIER=local|pl1|pl0 required; <c> = up un pn pp (records off) or rec (rows H0n H0
#              H3 H4, four passes, records on, logq=0); DISK_DEV (per-block device counters) is the device under the
#              node's working database; local: the device under /data; pl1, pl0: the device under /essd, which must
#              not be the device under /data                                                         run e270<X>s<tier><c>-<k>
# <X> is XTAG (default empty): m16 / m32 / m64 for the memory machine sm (MEMT 16G / 32G / 64G), c for the processor
# machine; MEMT (default 32G) is the run scope's MemoryMax.
# Shared with EXP-257/269: lean mode fcu, 0.25-5 s after every block, NODE_RTPRIO=1 for the integration build when F8 has
# exrt=1, raw/rtprio.txt, raw/tier.txt; EXP-257's pre257.sh for the step-0 checks; the binary's commit
# contains EXP-269's 15 commits; the plan library PLANS (default /prologue/data/plans_269; route C plans_270).
# Environment: BIN_SHA; BIN and INT_COMMIT for the integration build; TIER, XTAG, MEMT, SEG0, PLANS, C2REC (default
# /prologue/data/c2rec_270, README 1). DRY=1: checks only.
# usage (in a scope under system.slice): systemd-run --scope --quiet -- env [DRY=1] BIN_SHA=... [BIN=... INT_COMMIT=...] [TIER=...] [XTAG=... MEMT=...] bash main270.sh <mode> <k>
set -u
MODE=${1:?mode}; export SEG=${2:?segment}; DRY=${DRY:-0}; export PLANS=${PLANS:-/prologue/data/plans_269}
export SEG0=${SEG0:-26305830}
[ "$SEG0" = 26305830 ] || { echo "SEG0 $SEG0: only the original segments (26305830; README 2, 13)"; exit 4; }
NCORES=${NCORES:-28}; case $NCORES in 28) NC=0-27 ;; 14) NC=0-13 ;; *) echo "NCORES $NCORES: 28 or 14 (README 18)"; exit 4 ;; esac
CTRL="srdiag=0 ctlcache=1"; LAUNCH="bash $(readlink -f "$0") $MODE $SEG"
XTAG=${XTAG:-}; MEMT=${MEMT:-32G}
[[ "$XTAG" =~ ^(|m16|m32|m64|c|h14)$ ]] || { echo "XTAG $XTAG: empty, m16, m32, m64, c or h14"; exit 4; }
[ "$NCORES" = 14 ] && [ "$XTAG" != h14 ] && { echo "NCORES 14 needs XTAG h14 (README 18)"; exit 4; }
[ "$XTAG" = h14 ] && [ "$NCORES" != 14 ] && { echo "XTAG h14 needs NCORES 14"; exit 4; }
case $MEMT in 16G|32G|64G) ;; *) echo "MEMT $MEMT: 16G, 32G or 64G"; exit 4 ;; esac
[[ "$XTAG" =~ ^m ]] && [ "${XTAG#m}G" != "$MEMT" ] && { echo "XTAG $XTAG does not match MEMT $MEMT"; exit 4; }
[[ "$XTAG" =~ ^m ]] || [ "$MEMT" = 32G ] || { echo "MEMT $MEMT needs XTAG m${MEMT%G}"; exit 4; }
case $MODE in
  up|ur|un|stup|stun) KIND=up; BIN=${BIN:-/prologue/bin/reth-2.9.0-upstream-c9a780f-jitflags-3e2aba9}; export UP_COMMIT=${UP_COMMIT:-3e2aba9} ;;
  pn|pp|abl|rec|tchk|stpn|stpp|strec) KIND=int; BIN=${BIN:?BIN required for the integration build} ;;
  *) echo "mode $MODE: up ur un pn pp abl rec tchk stup stun stpn stpp strec"; exit 4 ;;
esac
ENVTIER=${TIER:-}; TIER=""
case $MODE in
  st*) TIER=${ENVTIER:?TIER local, pl1 or pl0 required}
       case $TIER in
         local) ;;
         pl1|pl0) export BASE=${BASE:-/essd/base-$((SEG0 + 1000 * SEG))} AF=${AF:-/essd/accflt-$((SEG0 + 1000 * SEG)).bin} ;;
         *) echo "TIER $TIER: local, pl1 or pl0"; exit 4 ;;
       esac
       NAMES=e270${XTAG}s$TIER${MODE#st}-$SEG ;;
  tchk) NAMES=e270${XTAG}tchk-$SEG; export ME=$((SEG0 + 1000 * SEG + 700)) ;;
  *) NAMES=e270$XTAG$MODE-$SEG ;;
esac
export KIND BIN
source "${PRE257:-/prologue/engine-access-plan/experiments/EXP-257-main-measurement/scripts/pre257.sh}"
pre_checks
if [ "$KIND" = int ]; then
  for c in f8a46c5 5be9c20 b66f77a 0ed6aa6 6ccc6c5 39e16b5 13174f6 0fe3659 4c8b895 b4fe89a 18ddffe c49d7b2 ccde697 11ef23a f069cb0 2bd2e69 827cee0; do
    git -C "$PROLOGUE_RETH_REPO" merge-base --is-ancestor $c "$INT_COMMIT" 2>/dev/null || stop "INT_COMMIT $INT_COMMIT does not contain $c"
  done
fi
if [ "$KIND" = up ]; then   # README 15.5: the official build differs from c9a780f only by 2bd2e69's two files
  fl=$(git -C "$PROLOGUE_RETH_REPO" diff --name-only c9a780f "$UP_COMMIT" 2>/dev/null | sort | tr '\n' ' ')
  [ "$fl" = "crates/ethereum/node/src/node.rs crates/node/core/src/args/jit.rs " ] || stop "UP_COMMIT $UP_COMMIT differs from c9a780f in: ${fl:-?}"
fi
[ "$(grep -c '^# apply_drvgap.py (EXP-269 section 16)' "$PROLOGUE_DRIVER/run_xl_f.py")" = 1 ] || stop "the driver does not carry apply_drvgap.py (6ad623cb or later; README 1)"
# core layout (README 2): siblings adjacent, the driver's 28-31 share no physical core with the node's 0-27
python3 - <<'PY' || stop "cpu topology: the node's 0-27 and the driver's 28-31 share a physical core, or the machine has not 32 cpus"
import os
n = os.cpu_count(); assert n == 32, n
def sib(c):
    s = set()
    for p in open(f'/sys/devices/system/cpu/cpu{c}/topology/thread_siblings_list').read().strip().split(','):
        a, _, b = p.partition('-'); s.update(range(int(a), int(b or a) + 1))
    return s
for c in range(28, 32):
    assert sib(c) <= set(range(28, 32)), (c, sib(c))
print('cpu topology: 32 cpus; cpu 0 siblings', sorted(sib(0)), '; 28-31 share no core with 0-27')
PY
DRV=$PROLOGUE_DRIVER/run_xl_f.py
RT=$( (cd "$(dirname $DRV)" && NBNICE=10 NBGAS=5000000 python3 - "$DRV" <<'PY'
import os, sys
p = sys.argv[1]; src = open(p).read()
end = src.index("\nPRECHECK = int(os.environ.get('PRECHECK', '0'))")
ns = {'__file__': os.path.abspath(p), '__name__': 'main270'}
exec(compile(src[:end], p, 'exec'), ns)
C = ns['CONFIGS']
need = ('U8', 'F8', 'F8chk', 'F8w', 'P8', 'P8chk', 'P8w', 'H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'HX', 'HC', 'HXC', 'H0n', 'G3qxS', 'G4qaxepkS', 'G4qaxepkSR')
assert all(k in C for k in need), 'rows of apply_final270.py missing'
assert C['F8'] in (C['G4qaxepkS'], C['G4qaxepkSR']) and C['P8'] == C['G3qxS'], 'F8 / P8 not the integrated rows'
exrt = [t for t in C['F8'].split() if t.startswith('exrt=')]
print(1 if exrt and exrt[-1] != 'exrt=0' else '')
PY
) ) || stop "the driver's rows of apply_final270.py cannot be read or F8/P8 are not the integrated rows"
[ "$(grep -c '^# apply_final270.py (EXP-270 / final measurement)' "$DRV")" = 1 ] || stop "$DRV does not carry apply_final270.py once"
FROZEN=$(sed -n 's/^# apply_final270.py (EXP-270 \/ final measurement): F8 (frozen = \([A-Za-z0-9]*\)).*/\1/p' "$DRV")
[ "$(grep -c '^# apply_disk257.py (EXP-257): per-block' "$DRV")" = 1 ] || stop "$DRV does not carry apply_disk257.py once"
grep -q 'apply_disk257.py (EXP-257)' "$PROLOGUE_DRIVER/parse.py" || stop "parse.py does not carry apply_disk257.py"
# the device under the node's working database (every mode records it; disk counters for every process, as EXP-269)
src=$(findmnt -no SOURCE --target "$PROLOGUE_NODE_HOME/data" | sed 's/\[.*\]$//'); DEV=$(basename "$(readlink -f "$src")")
LDEV=$(basename "$(readlink -f "$(findmnt -no SOURCE --target /data | sed 's/\[.*\]$//')")")
if [ -n "$TIER" ] && [ "$TIER" != local ] && [ "${BASE_OK:-1}" = 0 ] && [ "$DRY" = 1 ]; then
  echo "BASE_OK=0 (DRY=1 only): the tier's device not checked (the disk is put in place between processes)"; DEV=""
elif [ -n "$TIER" ] && [ "$TIER" != local ]; then
  EDEV=$(basename "$(readlink -f "$(findmnt -no SOURCE --target /essd | sed 's/\[.*\]$//')")")
  [ "$(findmnt -no TARGET /essd)" = /essd ] || stop "/essd is not a mount point"
  [ "$DEV" = "$EDEV" ] && [ "${DEV%p[0-9]*}" != "${LDEV%p[0-9]*}" ] || stop "tier $TIER: the node's database is on $DEV, /essd on $EDEV, /data on $LDEV"
else
  [ "$DEV" = "$LDEV" ] || stop "the node's database $PROLOGUE_NODE_HOME/data is on $DEV, not on $LDEV (the device of /data)"
fi
if [ -n "$DEV" ]; then
  [ -r /sys/class/block/$DEV/stat ] || stop "/sys/class/block/$DEV/stat is not readable"
  if [ "${BASE_OK:-1}" = 0 ] && [ "$DRY" = 1 ]; then echo "BASE_OK=0 (DRY=1 only): base device not checked"
  else [ "$(stat -c %d "$BASE")" = "$(stat -c %d "$PROLOGUE_NODE_HOME/data")" ] || stop "base $BASE is not on the device of $PROLOGUE_NODE_HOME/data"; fi
fi
PK=$(lsblk -no PKNAME /dev/${DEV:-$LDEV} 2>/dev/null | head -1)
echo "tier ${TIER:-local}: node database on ${DEV:-?} (disk ${PK:-?}), /data on $LDEV, base $BASE; frozen row $FROZEN; plans $PLANS; MemoryMax $MEMT"
export MEM=$MEMT
# CREATE2 salt templates (README 1; decisions 11-08 19:3x, Master 11-13): EXP-263's records for every code of plans_final
# with CREATE2 plus the same analysis for the codes EXP-269 added (c2new270.py), one directory C2REC with a MANIFEST
# (files, content_sha256 over the sorted "name sha256" lines); the official build does not read it
C2REC=${C2REC:-/prologue/data/c2rec_270}
if [ "$KIND" = int ]; then
  python3 - "$C2REC" <<'PY' || stop "CREATE2 record directory $C2REC does not match its MANIFEST"
import hashlib, os, sys
d = sys.argv[1]; m = dict(l.split(None, 1) for l in open(f'{d}/MANIFEST').read().splitlines() if l.strip())
names = sorted(n for n in os.listdir(d) if n.endswith('.json'))
h = hashlib.sha256(''.join(f'{n} {hashlib.sha256(open(f"{d}/{n}", "rb").read()).hexdigest()}\n' for n in names).encode()).hexdigest()
assert int(m['files']) == len(names) and m['content_sha256'].strip() == h, (len(names), h)
print(f'CREATE2 records: {len(names)} files, content_sha256 {h[:16]}')
PY
fi
XARGS=(LEAN_MODE=fcu SETTLE_MIN=0.25 SETTLE_MIN_MEASURED=0.25 SETTLE_MAX=5)
# JIT (README 15): every column gets the same JIT setting; JITW is the number of JIT compilation workers
# (README 15.5: 8, or 16 if the check on f0 fails); the official build is c9a780f + 2bd2e69 (3e2aba9), which has the
# two extra flags; every process of every column gets the same set
JITW=${JITW:-8}; [[ "$JITW" =~ ^(8|16)$ ]] || stop "JITW $JITW: 8 (README 15.5) or 16 (its fallback)"
NX="--jit.timeout 60s --jit.worker-count $JITW --jit.max-pending-jobs 8192 --jit.log-compilations"   # README 15.5 (researcher 11-14)
OFF=(NODIAG=1 NOSLOW=1)
case $MODE in
  up|stup)  CF="U8"; WARM=U8; PRE=U8; PRECHK=0; RTP=""; XARGS+=("${OFF[@]}") ;;
  ur)       CF="U8"; WARM=U8; PRE=U8; PRECHK=0; RTP=""; XARGS+=("${OFF[@]}" "NODE_XARGS=$NX --engine.prewarm-reuse") ;;
  un|stun)  CF="U8"; WARM=U8; PRE=U8; PRECHK=0; RTP=""; XARGS+=("${OFF[@]}" "NODE_XARGS=$NX --engine.disable-prewarming") ;;
  pn|stpn)  CF="F8"; WARM=F8w; PRE=F8chk; PRECHK=100; RTP=$RT; XARGS+=("${OFF[@]}") ;;
  pp|stpp)  CF="P8"; WARM=P8w; PRE=F8chk; PRECHK=100; RTP=$RT; XARGS+=("${OFF[@]}") ;;
  abl)      CF="H0 H1 H2 H3 H4 H5 HX HC HXC"; WARM=F8w; PRE=F8chk; PRECHK=100; RTP=$RT; XARGS+=("${OFF[@]}") ;;
  tchk)     CF="H0 H3 H4 HXC"; WARM=F8w; PRE=F8chk; PRECHK=100; RTP=$RT; XARGS+=("${OFF[@]}"); CTRL="$CTRL logq=0 xbtl2=1" ;;
  rec)      CF="H0n H0 H3 H4 H5"; WARM=F8w; PRE=F8chk; PRECHK=100; RTP=$RT; CTRL="$CTRL logq=0" ;;
  strec)    CF="H0n H0 H3 H4"; WARM=F8w; PRE=F8chk; PRECHK=100; RTP=$RT; CTRL="$CTRL logq=0" ;;
esac
[ -n "$DEV" ] && XARGS+=(DISK_DEV=$DEV)
case $MODE in ur|un|stun) ;; *) XARGS+=("NODE_XARGS=$NX") ;; esac   # ur, un carry NX with their own flag
[ "$KIND" = int ] && XARGS+=(C2REC_DIR=$C2REC)
echo "EXP-270 $MODE segment $SEG (base $TO, measured $MS-$ME): rows $CF, warm-up $WARM, pre-check $PRE ($PRECHK blocks), NODE_RTPRIO ${RTP:-unset}, CTRL_ADD=$CTRL, MemoryMax $MEM, ${XARGS[*]}"
[ "$DRY" = 1 ] && { echo "DRY=1: checks done $(ts)"; exit 0; }
RUNDIR=/work/runs/$NAMES
(
  until [ -d $RUNDIR/raw ]; do sleep 2; done
  echo "setting NODE_RTPRIO=${RTP:-unset} ncores $NCORES node-cpus $NC jitw $JITW mode $MODE tier ${TIER:-local} dev ${DEV:-none} memt $MEMT frozen $FROZEN plans $PLANS seg0 $SEG0 ctrl $CTRL" > $RUNDIR/raw/rtprio.txt
  { echo "tier ${TIER:-local} dev ${DEV:-none} disk ${PK:-?} data-dev $LDEV"; findmnt --target "$PROLOGUE_NODE_HOME/data"; lsblk -o NAME,SIZE,TYPE,MODEL,SERIAL;
    for c in 0 27 28; do echo "cpu $c siblings $(cat /sys/devices/system/cpu/cpu$c/topology/thread_siblings_list)"; done; lscpu | grep -E 'Model name|MHz'; } > $RUNDIR/raw/tier.txt 2>&1
  seen=""
  while ! grep -q "run_main rc=" $RUNDIR/raw/run_main.log 2>/dev/null; do
    for x in /proc/[0-9]*; do
      [ "$(readlink $x/exe 2>/dev/null)" = "$B" ] || continue
      pid=${x#/proc/}; case " $seen " in *" $pid "*) continue ;; esac
      seen="$seen $pid"
      echo "pid $pid $(grep 'Max realtime priority' $x/limits 2>/dev/null | tr -s ' ')" >> $RUNDIR/raw/rtprio.txt
    done
    sleep 5
  done
) &
MON=$!
one_run $NAMES "$(tr -d - <<< "${NAMES#e270}")" "$CF" $WARM $PRE $PRECHK "$RTP" "${XARGS[@]}"
rc=$?
kill $MON 2>/dev/null; wait $MON 2>/dev/null
exit $rc
