#!/usr/bin/env bash
# Prologue server: fetch the engine_newPayload inputs of blocks FIRST..LAST into the block pool ($PROLOGUE_BLOCKS_POOL)
# with engine-replay/fetch.py (beacon API, default publicnode; BEACON_API overrides), skipping files already there, then
# check the whole range with verify_blocks.py. LAST defaults to the execution head of the public RPC minus 64 blocks.
# The start slot is computed from the first block's timestamp (slot = (timestamp - genesis) / 12), so fetch.py starts
# exactly at the block's slot. usage: fetch_blocks.sh FIRST [LAST] [WORKERS=8]
set -euo pipefail
source /prologue/machine.env
RPC=${RPC:-https://ethereum-rpc.publicnode.com}
rpc() { curl -s -m 30 -X POST -H 'content-type: application/json' --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$1\",\"params\":$2}" "$RPC" | jq -r "$3"; }
FIRST=${1:?first block}; LAST=${2:-$(( $(rpc eth_blockNumber '[]' .result) - 64 ))}
POOL=$PROLOGUE_BLOCKS_POOL; mkdir -p "$POOL"
n=$FIRST
while (( n <= LAST )); do   # the first block of each run of missing files
  while (( n <= LAST )) && [ -e "$POOL/$n.json" ]; do n=$((n + 1)); done
  (( n <= LAST )) || break
  m=$n; while (( m <= LAST )) && [ ! -e "$POOL/$m.json" ]; do m=$((m + 1)); done
  ts=$(rpc eth_getBlockByNumber "[\"$(printf '0x%x' $n)\", false]" .result.timestamp)
  slot=$(( (ts - 1606824023) / 12 ))
  echo "$(date -Is) fetch $n-$((m - 1)) from slot $slot"
  python3 -I "$PROLOGUE_NODE_HOME/engine-replay/fetch.py" --start-block $n --count $((m - n)) --start-slot $slot --out "$POOL" --workers ${WORKERS:-8} 2>&1 | tail -1
  n=$m
done
python3 -I "$(dirname "$(realpath "$0")")/verify_blocks.py" "$POOL" "$FIRST" "$LAST"
