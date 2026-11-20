#!/usr/bin/env bash
# Prologue server: start the node once on $PROLOGUE_NODE_HOME/data without blocks and stop it when the start-up pipeline has
# finished. A database from `reth download --minimal` leaves the history index and transaction lookup stages at block 0;
# this start builds them (base-26335332: 17 s) before the database becomes a base or is advanced by forward.sh.
# The node runs as user prologue in a scope of its own under system.slice: user.slice (the ssh session) is held to the
# driver's cores, so a node started from there cannot be pinned to the node's cores ("taskset: failed to set pid's
# affinity: Invalid argument", 11-04). It is stopped by its pid; afterwards no process whose executable starts with reth
# may remain, and the stage checkpoints are printed.
# Run as root; holds the run lock. usage: first_start.sh [LOG]   (default engine-replay/logs/first_start-<time>.out)
set -euo pipefail
source "$(dirname "$(realpath "$0")")/root-common.sh"; H=$PROLOGUE_NODE_HOME
LOG=${1:-$H/engine-replay/logs/first_start-$(date +%m%d%H%M%S).out}
take_run_lock
r=$(asp reth_running) && { echo "a reth process is running (pid $r); not starting the node"; exit 3; }
[ -e $H/data/jwt.hex ] || { openssl rand -hex 32 > $H/data/jwt.hex; chown prologue:prologue $H/data/jwt.hex; chmod 600 $H/data/jwt.hex; }
t0=$(date +%s)
pid=$(systemd-run --scope --quiet --unit "prologue-first-start-$t0" prlimit --nofile=524288:524288 -- \
  setpriv --reuid=prologue --regid=prologue --init-groups -- \
  env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/home/prologue USER=prologue LANG=C.UTF-8 \
  NODE_LOG="$LOG" bash -c 'source /prologue/machine.env; exec bash "$PROLOGUE_DRIVER/start_node.sh" "$PROLOGUE_NODE_HOME/bin/reth" --color never')
[[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null || { echo "node did not start: $(tail -3 "$LOG")"; exit 4; }
echo "$(date -Is) node pid $pid, log $LOG"
DONE='Finished stage pipeline_stages=14/14 stage=Finish'
for _ in $(seq 3600); do grep -q "$DONE" "$LOG" && break; kill -0 "$pid" 2>/dev/null || break; sleep 1; done
ok=0; grep -q "$DONE" "$LOG" && ok=1
echo "$(date -Is) pipeline finished: $ok, after $(( $(date +%s) - t0 )) s"
kill -TERM "$pid" 2>/dev/null || true; while kill -0 "$pid" 2>/dev/null; do sleep 1; done
r=$(asp reth_running) && { echo "a reth process is still running (pid $r)"; exit 4; }
(( ok )) || { echo "pipeline did not finish: $(grep -E 'ERROR' "$LOG" | tail -3)"; exit 4; }
grep -E "Finished stage|Executed stage" "$LOG" | sed 's/\x1b\[[0-9;]*m//g' | cut -c1-200 | tail -16
echo "checkpoints: $(asp stage_checkpoints)"
