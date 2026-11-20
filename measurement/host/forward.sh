#!/usr/bin/env bash
# Prologue server: advance the node database from FROM to TO, nothing measured (the forward step before a base is written).
# Server copy of master/scripts/forward_win.sh (Master 2026-10-31) with the changes X-028 wrote in EXP-240's
# server_bundle.md section 6: the binary is the measuring integration binary and the configuration AB1ng (every Prologue
# switch off; the stock row of the 2.9.0 runs), in place of 2.5.1 and S0; the driver is the server copy ($PROLOGUE_DRIVER)
# in a run directory /work/runs/NAME; paths, cores and helpers come from machine.env and the server's node-common.sh.
# Checks: no reth process; every block file there; head exactly FROM before; reth.toml unchanged; after the run the stage
# checkpoints must equal TO, and the header the database holds for TO must carry the block file's stateRoot and
# parentHash. A 2.9.0 node leaves storage that read-only tools cannot open until a read-write start heals it (short5,
# "cannot get a writer on a read-only environment"; run_f.sh accepts that with CKPT_UNREADABLE_OK): then the node is
# started once without blocks and stopped. If the head lags TO, the step is repeated from the head reached (3 rounds at
# most). Failures are reported with the reason (exit 12, 13, 15) and the database is left as it is.
# DRY=1 does every check up to the start of the node and stops there, in /work/runs/dry-NAME-<time>.
# Run as root: it holds the run lock and runs the driver as user prologue (same limits as a measured run, no memory cap).
# Afterwards it writes raw/fwd_per1000.txt: the time per 1,000 blocks from the driver's per-block records.
# FWD_ENV (X-031, EXP-269): extra NAME=VALUE pairs for the node environment, e.g. EAP_CODES_OUT=/work/codes.tsv (the code table).
# usage: [DRY=1] [BIN=...] [FWD_ENV=...] FROM=26299454 TO=26305830 forward.sh NAME
set -euo pipefail
source "$(dirname "$(realpath "$0")")/root-common.sh"
NAME=${1:?run name}; FROM=${FROM:?}; TO=${TO:?}
[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ && "$FROM" =~ ^[0-9]+$ && "$TO" =~ ^[0-9]+$ ]] && (( TO > FROM )) || { echo "NAME: letters, digits, . _ -; FROM < TO"; exit 2; }
BIN=$(realpath "${BIN:-$PROLOGUE_NODE_HOME/bin/reth}")
R=/work/runs/$NAME; [ "${DRY:-0}" = 1 ] && R=/work/runs/dry-$NAME-$(date +%m%d%H%M%S)
take_run_lock
[ ! -e "$R" ] || { echo "$R exists"; exit 3; }
mkdir -p "$R"/{blocks,raw}; cp -a "$PROLOGUE_DRIVER" "$R/scripts"; chown -R prologue:prologue "$R"
cat > "$R/fwd.sh" <<EOF
set -u
source /prologue/machine.env; source \$PROLOGUE_NODE_HOME/engine-replay/node-common.sh   # cd to the node home; helpers
export NBNICE=10 NBGAS=5000000 PLANS_DIR=/prologue/data/plans_final
ckpt() { stage_checkpoints $BIN; }
at() { echo "\$1" | jq -e --argjson h "\$2" '[.AccountHashing, .Bodies, .Execution, .Finish] | all(. == \$h)' >/dev/null; }
r=\$(reth_running) && { echo "a reth process is running (pid \$r)"; exit 3; }
link_blocks $((FROM + 1)) $TO $R/blocks
for b in \$(seq $((FROM + 1)) $TO); do [ -e $R/blocks/\$b.json ] || { echo "block file \$b missing"; exit 6; }; done
sha0=\$(sha256sum data/reth.toml | cut -d' ' -f1)
c=\$(ckpt); echo "\$(date -Is) checkpoints before: \$c" | tee -a $R/raw/fwd.ckpt
at "\$c" $FROM || { echo "head is not $FROM"; exit 12; }
echo "binary $BIN \$($BIN --version | sed -n 's/^Commit SHA: *//p')"
[ "${DRY:-0}" = 1 ] && { echo "DRY=1: checks passed, node not started"; exit 0; }
# the forward step from the head H to $TO; afterwards the node is started once more without blocks when the checkpoints
# cannot be read (a 2.9.0 node stopped with storage that only a read-write start heals: "cannot get a writer on a read-only
# environment"), and the step is repeated from the head it reached when that lags $TO; at most 3 rounds
# The node is started directly, not through start_node.sh, whose history-window check refuses a database whose checkpoints
# cannot be read; on start it heals the storage ("Healing static file inconsistencies": static files and history indices
# written past the committed checkpoints are unwound to them).
heal() {
  local pid log=$R/raw/heal.\$1.log
  taskset -c \$PROLOGUE_NODE_CPUS $BIN node --datadir data --chain mainnet --authrpc.addr 127.0.0.1 --authrpc.port 8551 \\
    --authrpc.jwtsecret data/jwt.hex --ipcdisable --disable-discovery --max-outbound-peers 0 --max-inbound-peers 0 \\
    --log.file.directory engine-replay/logs --color never > \$log 2>&1 &
  pid=\$!
  for _ in \$(seq 600); do grep -q "Status connected_peers" \$log && break; kill -0 \$pid 2>/dev/null || break; sleep 1; done
  kill -TERM \$pid 2>/dev/null; while kill -0 \$pid 2>/dev/null; do sleep 1; done
  grep -E "Healing|healing|unwinding" \$log | sed 's/^/  heal: /' | cut -c1-200
}
# 2.9.0 keeps up to 50 blocks in memory before it writes (2.5.1: 2) and writes what is left only on SIGTERM; a stop that
# times out in that write loses those blocks (fwd50, 11-04: 50 executed, none kept). The forward step is not measured, so
# the node writes after every 2 blocks.
PERSIST="--engine.persistence-threshold 2 --engine.memory-block-buffer-target 0 --engine.num-state-masking-blocks 0"
H=$FROM; frc=0
for round in 1 2 3; do
  echo "\$(date -Is) round \$round: forward \$((H + 1))-$TO with AB1ng, not measured" | tee -a $R/raw/fwd.ckpt
  cd $R
  NODE_ENV="EAP_CTRL=$R/raw/fwd.ctrl EAP_PLANS=\$PLANS_DIR${FWD_ENV:+ $FWD_ENV}" EAP_CTRL_FILE=$R/raw/fwd.ctrl EAP_PLANS=\$PLANS_DIR NODE_CPUS=\$PROLOGUE_NODE_CPUS PGATE=0 \\
    SEQ=AB1ng WARM=AB1ng MIN_HEAD=\$H EXACT_HEAD=\$H MAX_END=$TO FFWD_TO=$((TO + 1)) SETTLE_MIN=0 SETTLE_MAX=0 LEAD=0 \\
    python3 -u scripts/run_xl_f.py fwd\$round "$BIN" 0 "$R/blocks" "$R/raw" 0 -- --engine.slow-block-threshold 0 --color never --jit \$PERSIST > raw/fwd\$round.run.log 2>&1
  frc=\$?
  cd \$PROLOGUE_NODE_HOME
  t0=\$(date +%s); while reth_running >/dev/null && (( \$(date +%s) - t0 < 600 )); do sleep 5; done
  r=\$(reth_running) && { echo "reth (pid \$r) still running 600 s after the forward step"; exit 9; }
  echo "round \$round: driver rc=\$frc"; tail -2 $R/raw/fwd\$round.run.log
  (( frc == 0 )) || { echo "forward step failed (driver rc \$frc); the database is left as it is"; exit 13; }
  c=\$(ckpt)
  [ -n "\$c" ] || { echo "round \$round: checkpoints unreadable; one node start without blocks to heal the storage"; heal \$round; c=\$(ckpt); }
  echo "\$(date -Is) round \$round: checkpoints after: \$c" | tee -a $R/raw/fwd.ckpt
  [ -n "\$c" ] || { echo "checkpoints still unreadable after the healing start; the database is left as it is"; exit 15; }
  at "\$c" $TO && break
  H=\$(echo "\$c" | jq -r .Finish)
  [[ "\$H" =~ ^[0-9]+$ ]] && (( H < $TO )) && at "\$c" \$H || { echo "checkpoints neither $TO nor one consistent head below it: \$c"; exit 12; }
  echo "round \$round: the head is \$H, $TO not reached (2.9.0 persisted less than it executed); next round from \$H"
done
at "\$c" $TO || { echo "$TO not reached in 3 rounds (head \$H); the database is left as it is"; exit 12; }
[ "\$(sha256sum data/reth.toml | cut -d' ' -f1)" = "\$sha0" ] || { echo "reth.toml changed"; exit 8; }
want=\$(block_file_header $R/blocks/$TO.json); got=\$(db_header $TO $BIN)
echo "head $TO stateRoot and parentHash: database \$got, block file \$want"; [ "\$got" = "\$want" ] || { echo "head header differs from the block file"; exit 14; }
echo "forward rc=0"
EOF
set +e
# in a scope of its own under system.slice, like prologue_run.sh: user.slice (the ssh session) is held to the driver's cores
systemd-run --scope --quiet --unit "prologue-fwd-$(basename "$R")" prlimit --nofile=524288:524288 -- \
  setpriv --reuid=prologue --regid=prologue --init-groups -- \
  env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/home/prologue USER=prologue LANG=C.UTF-8 bash "$R/fwd.sh" 2>&1 | tee -p "$R/raw/forward_main.log"   # -p: the log goes on when the ssh session that started this ends (fwd-26305830)
rc=${PIPESTATUS[0]}
set -e
ls "$R"/raw/fwd[0-9].jsonl >/dev/null 2>&1 && python3 - "$R"/raw/fwd[0-9].jsonl > "$R/raw/fwd_per1000.txt" <<'PY'
import json, sys
rows = sorted((j['block'], j['t']) for f in sys.argv[1:] for j in (json.loads(l) for l in open(f)) if 'block' in j and 't' in j)
prev = rows[0][1] if rows else 0
by = {}
for b, t in rows:   # each block's share: the time since the previous block's record
    by.setdefault(b // 1000, []).append(t - prev); prev = t
for k in sorted(by): print(f'{k * 1000}-{k * 1000 + 999}: {len(by[k])} blocks, {sum(by[k]):.0f} s')
PY
exit $rc
