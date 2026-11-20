#!/usr/bin/env bash
# EXP-199 short comparison rounds (README section 6.4): copy of scripts/session_e.sh calling scripts/run_xl_f.py
# EXP-193: copy of EXP-192 scripts/session.sh, unchanged.
# EXP-192: copy of EXP-189 scripts/session.sh, unchanged.
# EXP-189: copy of EXP-184 scripts/session.sh, unchanged.
# EXP-184: copy of EXP-183 session.sh, unchanged.
# EXP-183: copy of EXP-182 session.sh, unchanged (EAP_SPLITLOG was added and removed again before the run, Master 10-26:
# its call timer would load only H-AS and H-APS and enter their comparison with H-A; the `eap split exit` lines stay).
# EXP-182: copy of EXP-181 session.sh, unchanged.
# EXP-181: copy of EXP-177 session.sh, unchanged.
# EXP-177: copy of EXP-176 session.sh, unchanged.
# EXP-176: copy of EXP-175 session.sh, unchanged.
# EXP-175: copy of the EXP-174 / EXP-172 script of the same name, unchanged.
# EXP-174: copy of EXP-172 session.sh, unchanged.
# EXP-172: copy of EXP-171 session.sh, unchanged.
# EXP-171: copy of EXP-169 session.sh, unchanged.
# EXP-169: copy of EXP-167 session.sh; the binary has no default (BIN required).
# EXP-167 (copy of EXP-159 session.sh, unchanged). EXP-159 (copy of EXP-157 session.sh, unchanged). EXP-157 (copy of EXP-152 session.sh, unchanged). EXP-152 (copy of EXP-148 session.sh; EAP_C2REC added). EXP-122: copy of EXP-120 scripts/session.sh; default binary changed; second segment adds EAP_KEYDIAG (EXP-105) to the node environment. EXP-094: copy of EXP-093 scripts/session.sh, unchanged.
# EXP-019 node session (after EXP-018 scripts/session.sh): wait for the exclusive timing lock, check that no other node
# runs, then run one labelled run of scripts/run_xl.py in a new node process under that lock.
# usage: [SEQ=...] [WARM=S] session.sh LABEL WARMUP MEASURED
set -u
cd "$(dirname "$0")/.."
D=$PWD
LABEL=$1 WARMUP=$2 MEASURED=$3
BIN=${BIN:?BIN required}
# EXP-199: the plan library can be set by the caller (PLANS_DIR); default the EXP-011 library as before
PLANS=${PLANS_DIR:-$PROLOGUE_REPO/experiments/EXP-011-residual-coverage/plans}
# Prologue server copy: scripts/server/apply_server.py: no lock here, prologue_run.sh holds the run lock for the whole run
echo "$(date +%T) load $(cat /proc/loadavg)"
# apply_v290.py (reth 2.9.0 binaries, Master 11-02): any process whose executable starts with "reth"
reth_running() { local q e; pgrep -x reth >/dev/null && return 0; for q in $(pgrep -f reth); do e=$(basename "$(readlink /proc/$q/exe 2>/dev/null)"); case "$e" in reth*) return 0;; esac; done; return 1; }
if reth_running; then echo "a reth process is running"; exit 3; fi
if (exec 3<>/dev/tcp/127.0.0.1/8545) 2>/dev/null; then echo "port 8545 is listening"; exit 3; fi
# 2026-10-18 host memory rule: at least 16 GB available before starting the node
t0=$(date +%s)
while (( $(free -g | awk '/^内存|^Mem/ {print $7}') < 16 )) && (( $(date +%s) - t0 < 1800 )); do sleep 15; done
echo "$(date +%T) available memory $(free -g | awk '/^内存|^Mem/ {print $7}') GB"
if (( $(free -g | awk '/^内存|^Mem/ {print $7}') < 16 )); then echo "less than 16 GB available"; exit 5; fi
t0=$(date +%s)
while [ "${PGATE:-0.25}" = 0 ] && awk '{exit !($1 > 4)}' /proc/loadavg && (( $(date +%s) - t0 < 1800 )); do sleep 30; done
echo "$(date +%T) load wait $(( $(date +%s) - t0 )) s; load $(cat /proc/loadavg)"
# apply_i4_254.py (EXP-254 / X-028): NODIAG=1 leaves EAP_DIAG and EAP_KEYDIAG out of the node environment, NOSLOW=1 the slow-block threshold out of its arguments
DIAGENV="EAP_DIAG=$D/raw/$LABEL.diag.jsonl EAP_KEYDIAG=$D/raw/$LABEL.keydiag.jsonl "; [ "${NODIAG:-0}" = 1 ] && DIAGENV=
SLOWARG="--engine.slow-block-threshold 0"; [ "${NOSLOW:-0}" = 1 ] && SLOWARG=
NODE_ENV="EAP_CTRL=$D/raw/$LABEL.ctrl EAP_PLANS=$PLANS ${DIAGENV}EAP_C2REC=${C2REC_DIR:-$PROLOGUE_REPO/experiments/EXP-145-proxy-derivation-static/raw/c2records}${NODE_ENV_ADD:+ $NODE_ENV_ADD}" EAP_CTRL_FILE=$D/raw/$LABEL.ctrl EAP_PLANS=$PLANS NODE_CPUS=${NODE_CPUS_RUN:-0-7} PGATE=${PGATE:-0.25} \
  python3 -u scripts/run_xl_f.py "$LABEL" "$BIN" "$MEASURED" "$D/blocks" "$D/raw" "$WARMUP" -- $SLOWARG --color never ${EXTRA_ARGS:-} > "raw/$LABEL.run.log" 2>&1
echo "$(date +%T) $LABEL rc=$?"; tail -2 "raw/$LABEL.run.log"
echo "$(date +%T) done"
