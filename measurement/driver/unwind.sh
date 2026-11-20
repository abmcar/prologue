#!/usr/bin/env bash
# EXP-198: copy of EXP-194 scripts/unwind.sh, unchanged. EXP-194: copy of EXP-187 scripts/unwind.sh, unchanged.
# EXP-187: copy of EXP-175 scripts/unwind.sh, unchanged.
# EXP-175: copy of the EXP-174 / EXP-172 script of the same name, unchanged.
# EXP-172: copy of EXP-170 scripts/unwind.sh, unchanged. EXP-170: copy of EXP-169 scripts/unwind.sh (itself a copy of EXP-114 scripts/unwind.sh with the running-reth check by executable), unchanged.
# EXP-114: unwind the node directory with the stock
# reth 2.5.1 `stage unwind` and check before/after: no reth running, history window intact (node-common.sh
# check_history_window), reth.toml unchanged (restored from the backup if the command rewrote it), Finish checkpoint.
# usage: unwind.sh num-blocks N | to-block B     (run as a labq node job)
set -u
cd "$(dirname "$0")/.."; D=$PWD
# Prologue server copy: scripts/server/apply_server.py
source "$PROLOGUE_NODE_HOME/engine-replay/node-common.sh"   # cds to the node directory
LOG=$D/raw/unwind-$(date +%Y%m%d-%H%M%S).log; exec > >(tee -a "$LOG") 2>&1
fin() { ./bin/reth db --datadir data --chain mainnet list StageCheckpoints --json 2>/dev/null | sed -n '/^\[/,$p' | jq -c '[.[] | {(.[0]): .[1].block_number}] | add'; }
# EXP-169: a process counts as reth when its executable is a reth binary (pgrep -f 'reth-2.5.1' also matched a review
# session whose prompt mentions the string, 2026-10-24 12:05)
reth_running() { pgrep -x reth >/dev/null && return 0; for p in $(pgrep -f 'reth-2.5.1'); do case "$(basename "$(readlink /proc/$p/exe 2>/dev/null)")" in reth*) return 0;; esac; done; return 1; }
if reth_running; then echo "a reth process is running"; exit 3; fi
cp -p data/reth.toml "$D/raw/reth.toml.before"; sha0=$(sha256sum data/reth.toml | cut -d' ' -f1)
check_history_window || { echo "history check failed before unwind"; exit 4; }
echo "$(date -Is) checkpoints before: $(fin)"
t0=$(date +%s)
./bin/reth stage unwind --datadir data --chain mainnet ${OFFLINE:-} "$@"; rc=$?
echo "$(date -Is) unwind rc=$rc in $(( $(date +%s) - t0 )) s"
echo "$(date -Is) checkpoints after: $(fin)"
sha1=$(sha256sum data/reth.toml | cut -d' ' -f1)
if [ "$sha0" != "$sha1" ]; then echo "reth.toml changed by the command; restoring the backup"; diff "$D/raw/reth.toml.before" data/reth.toml | head -20; cp -p "$D/raw/reth.toml.before" data/reth.toml; fi
check_history_window; hc=$?; echo "history check after: rc=$hc"
echo "unwind.sh rc=$rc"; exit $(( rc != 0 ? rc : hc ))
