# Prologue server version of node-common.sh (development host, 2026-10-08), sourced by the
# driver copy (start_node.sh, unwind.sh, run_f.sh, run_xl_f.py, history_window.sh) and by boot_prepare.sh through
# $PROLOGUE_NODE_HOME/engine-replay/node-common.sh. Differences:
#   - the node home is $PROLOGUE_NODE_HOME (from /prologue/machine.env);
#   - no prune arguments on the command line: the snapshot's own data/reth.toml holds the prune settings that match the
#     downloaded data (distance 10,064 for account and storage history and bodies, 64 for receipts, sender recovery and
#     transaction lookup full), and reth would write command-line settings back into it;
#   - the history check only checks that the prune checkpoints are readable (every pass restores the base, so no unwind
#     depends on the retained history); same return codes as the development host's (3 unreadable, 4 inconsistent storage).
[ -n "${PROLOGUE_NODE_HOME:-}" ] || source /prologue/machine.env
cd "$PROLOGUE_NODE_HOME"
ulimit -n "$(ulimit -Hn)"
PRUNE_ARGS=()
check_history_window_bin() {
  local msg
  if ! msg=$("${1:?reth binary}" db --datadir data --chain mainnet list PruneCheckpoints --json 2>&1 >/dev/null); then
    case $msg in *"inconsistent state"*) echo "storage was left inconsistent by an interrupted shutdown; a node start heals it" >&2; return 4;; esac
    echo "refusing to start: cannot read prune checkpoints" >&2; return 3
  fi
}
check_history_window() { check_history_window_bin ./bin/reth; }
# the stage checkpoints as {"Stage": block, ...} (nothing when the database cannot be read); BIN default ./bin/reth
stage_checkpoints() {
  "${1:-./bin/reth}" db --datadir data --chain mainnet list StageCheckpoints --json 2>/dev/null | sed -n '/^\[/,$p' | jq -c '[.[] | {(.[0]): .[1].block_number}] | add'
}
# the Finish stage checkpoint (the head), as the node directory/engine-replay/sync-chain.sh's finish_checkpoint
finish_checkpoint() { stage_checkpoints "$@" | jq -r '.Finish // empty'; }
# "stateRoot parentHash" of block N: from the database (db_header N [BIN]; the header does not carry its own hash) and
# from the block file (block_file_header FILE)
db_header() {
  "${2:-./bin/reth}" db --datadir data --chain mainnet get static-file headers "$1" --color never 2>/dev/null | sed -n '/^{/,/^}/p' | jq -r '.stateRoot + " " + .parentHash'
}
block_file_header() { python3 -c "import json, sys; p = json.load(open(sys.argv[1]))['payload']; print(p['state_root'], p['parent_hash'])" "$1"; }
# sha256 of a directory's file listing (relative names and sizes): bases and their copies are compared by it. Leaves out
# rocksdb-secondary-tmp-<pid>/, which a read-only reth tool (eap-acc-filter, db list) makes in data/ while it runs
listing_sha() { (cd "$1" && find . -path ./rocksdb-secondary-tmp-\* -prune -o -type f -printf '%P\t%s\n' | LC_ALL=C sort | sha256sum | cut -c1-64); }
# any process whose executable name starts with reth (reth, reth-2.9.0-*, the official downloader), as the driver and
# restore_reflink.sh count a running node; never pgrep -f, which also matches the shell that started it
reth_running() { local p e; for p in /proc/[0-9]*; do e=$(readlink "$p/exe" 2>/dev/null) || continue; case "$(basename "$e")" in reth*) echo "${p#/proc/}"; return 0;; esac; done; return 1; }
# symbolic links DIR/<n>.json -> the block pool for FIRST..LAST (the pool is on another disk, so no hard links)
link_blocks() { seq -f "$PROLOGUE_BLOCKS_POOL/%.0f.json" "$1" "$2" | xargs ln -sfn -t "$3"; }
