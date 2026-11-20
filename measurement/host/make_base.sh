#!/usr/bin/env bash
# Prologue server: write the base /data/node/base-N from the node's working copy $PROLOGUE_NODE_HOME/data when its head
# is N (after forward.sh), and the base's account filter /data/node/accflt-N.bin, at the same time (both only read the
# working copy; the node is stopped).
# The base is an ordinary copy (cp --reflink=never), so it is contiguous and not a clone of a clone (boot_prepare.sh);
# it is written as base-N.part and gets its name, read-only, only after its listing checked out and the filter is there:
# a machine that copies from this one finds the filter whenever it finds the base.
# Checks before: root; the run lock; no reth process; every stage checkpoint is N; the database's header of N carries
# the block file's stateRoot and parentHash. After: the base's file listing (names and sizes) equals the working copy's;
# the filter's header names N (bytes 24-31, as EXP-240 prologue_pre.sh reads it) and its json the block hash of N.
# With NO_FILTER=1 only the base is written.
# usage: [NO_FILTER=1] make_base.sh N
set -euo pipefail
source "$(dirname "$(realpath "$0")")/root-common.sh"
N=${1:?block number}; [[ "$N" =~ ^[0-9]+$ ]] || { echo "N: a block number"; exit 2; }
H=$PROLOGUE_NODE_HOME; B=/data/node/base-$N; F=/data/node/accflt-$N; FILTER=$(( ${NO_FILTER:-0} != 1 ))
take_run_lock
r=$(asp reth_running) && { echo "a reth process is running (pid $r)"; exit 3; }
[ ! -e $B ] && [ ! -e $B.part ] || { echo "$B or $B.part exists"; exit 3; }
(( ! FILTER )) || [ ! -e $F.bin ] || { echo "$F.bin exists"; exit 3; }

c=$(asp "stage_checkpoints | jq -c '[.[]] | unique'")
[ "$c" = "[$N]" ] || { echo "stage checkpoints are $c, not all $N"; exit 4; }
want=$(asp block_file_header $PROLOGUE_BLOCKS_POOL/$N.json); got=$(asp db_header $N)
[ "$got" = "$want" ] || { echo "header of $N in the database ($got) differs from the block file ($want)"; exit 4; }
hash=$(python3 -c "import json, sys; print(json.load(open(sys.argv[1]))['payload']['block_hash'])" $PROLOGUE_BLOCKS_POOL/$N.json)
ts "head $N checked (stateRoot, parentHash); writing $B and $F.bin"

t0=$(date +%s)
if (( FILTER )); then
  asp "/usr/bin/time -v ./bin/reth db --datadir data --chain mainnet --log.file.directory engine-replay/logs eap-acc-filter --out $F.bin > $F.log 2> $F.time" & fpid=$!
fi
cp -a --reflink=never $H/data $B.part
ts "base copied in $(( $(date +%s) - t0 )) s"
if (( FILTER )); then
  wait $fpid || { echo "eap-acc-filter failed: $(tail -3 $F.log)"; exit 6; }
  ts "filter written in $(( $(date +%s) - t0 )) s"
fi
# what the filter build, open during the copy, left in the copy: its temporary directory and the lock file as it was then
# (base-26305830: 1,028,096 bytes against 0 after the tool ended); the lock file takes the working copy's state
rm -rf $B.part/rocksdb-secondary-tmp-*; cp --reflink=never $H/data/db/mdbx.lck $B.part/db/mdbx.lck
[ "$(asp listing_sha $H/data)" = "$(asp listing_sha $B.part)" ] || { echo "listing of $B.part differs from the working copy"; exit 5; }
if (( FILTER )); then
  python3 - $F.bin $N "$hash" <<'PY' || { echo "filter $F.bin does not describe $N"; exit 6; }
import json, struct, sys
f, n, h = sys.argv[1], int(sys.argv[2]), sys.argv[3]
hd = open(f, 'rb').read(32); j = json.load(open(f[:-4] + '.json'))
ok = hd[:8] == b'EAPACCF1' and struct.unpack('<Q', hd[24:32])[0] == n and j['block_number'] == n and j['block_hash'] == h
print(f'filter header {hd[:8]} block {struct.unpack("<Q", hd[24:32])[0]}, json block {j["block_number"]} hash {j["block_hash"]}, accounts {j["accounts"]}')
sys.exit(0 if ok else 1)
PY
fi
chown -R prologue:prologue $B.part; chmod -R a-w $B.part; mv $B.part $B
ts "base $B ready ($(du -sh --apparent-size $B | cut -f1)), $(( $(date +%s) - t0 )) s"
