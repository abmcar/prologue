#!/usr/bin/env bash
# Prologue server: one node run of the server driver copy (scripts/server/apply_server.py) in place of a labq node job.
# As root it
#   - holds the run lock $PROLOGUE_RUN_LOCK for the whole run (build290.sh and forward.sh refuse while it is held);
#   - makes the run directory /work/runs/NAME with a fresh copy of $PROLOGUE_DRIVER and blocks/ raw/ results/;
#   - starts run_f.sh in a systemd scope prologue-run-NAME.scope with MemoryMax=MEM (default 45G) and MemorySwapMax=0, so
#     the driver, the node and the page cache they fault in stay under the cap (the development host's node memory);
#   - drops to user prologue (RLIMIT_NICE and RTPRIO 0 as on the development host; nofile 524288), so a configuration that
#     asks for SCHED_FIFO or a lower nice value gets exactly what it gets there (root would bypass both limits);
#   - checks that run_f.sh is in that scope (stops the run otherwise) and sets NODE_CG_CHECK=1, so the driver stops when a
#     node is not in the driver's control group (apply_mem248.py); a run may pass NODE_CG_CHECK=0 to turn that off;
#   - records memory.max of the scope in raw/scope.txt and, every 5 s, memory.current, memory.peak, anon, file and
#     memory.events in raw/scope.log (the scope disappears with its last process).
# This script stays on the driver's cores. The run's variables are passed as NAME=VALUE arguments, the same as run_f.sh
# takes on the development host.
# usage: [MEM=45G] prologue_run.sh NAME VAR=VALUE ...   (e.g. LBL=t1 CF="AB1ng AB5ng" BIN=... MIN_HEAD=... END=...)
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 2; }
NAME=${1:?run name}; shift
[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "name: letters, digits, . _ -"; exit 2; }
source /prologue/machine.env
taskset -cp "$PROLOGUE_DRIVER_CPUS" $$ > /dev/null
R=/work/runs/$NAME; U=prologue-run-$NAME; MEM=${MEM:-45G}
exec 8>"$PROLOGUE_RUN_LOCK"; flock -n 8 || { echo "another run or build holds $PROLOGUE_RUN_LOCK"; exit 3; }
[ ! -e "$R" ] || { echo "$R exists"; exit 3; }
mkdir -p "$R"/{blocks,raw,results}; cp -a "$PROLOGUE_DRIVER" "$R/scripts"; chown -R prologue:prologue "$R"
echo "$(date -Is) run $NAME in $R, scope $U.scope, MemoryMax $MEM, node cpus $PROLOGUE_NODE_CPUS, driver cpus $PROLOGUE_DRIVER_CPUS"
systemd-run --scope --quiet --unit "$U" -p MemoryMax="$MEM" -p MemorySwapMax=0 \
  prlimit --nofile=524288:524288 -- \
  setpriv --reuid=prologue --regid=prologue --init-groups -- \
  env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/home/prologue USER=prologue LANG=C.UTF-8 NODE_CG_CHECK=1 "$@" \
  bash "$R/scripts/run_f.sh" > "$R/raw/run_main.log" 2>&1 &
pid=$!
CG=/sys/fs/cgroup/system.slice/$U.scope
# the scope appears before systemd-run has moved itself into it: wait up to 5 s for both
for _ in $(seq 50); do [ -e $CG/memory.max ] && [ "$(</proc/$pid/cgroup)" = "0::/system.slice/$U.scope" ] && break; sleep 0.1; done
echo "memory.max $(<$CG/memory.max) memory.swap.max $(<$CG/memory.swap.max); run_f.sh $(</proc/$pid/cgroup)" > "$R/raw/scope.txt"
if [ "$(</proc/$pid/cgroup)" != "0::/system.slice/$U.scope" ]; then
  echo "run_f.sh is not in $U.scope after 5 s: $(</proc/$pid/cgroup)"; kill -TERM $pid; wait $pid || true; exit 4
fi
while kill -0 $pid 2>/dev/null; do
  [ -e $CG/memory.current ] && echo "$(date +%s) current $(<$CG/memory.current) peak $(<$CG/memory.peak) $(grep -E '^(anon|file) ' $CG/memory.stat | tr '\n' ' ')$(tr '\n' ' ' < $CG/memory.events)" >> "$R/raw/scope.log"
  sleep 5
done
rc=0; wait $pid || rc=$?
echo "$(date -Is) run $NAME rc=$rc; $(tail -1 "$R/raw/run_main.log")"
exit $rc
