#!/bin/bash
# Prologue server version of restore_reflink.sh (development host, Master 2026-11-01):
# put the node database back to a base state in seconds with XFS reflink. Changes: the working database is
# $PROLOGUE_NODE_HOME/data (a plain directory on /data, not a bind mount); BASE must be on the same file system.
# Same checks otherwise: no reth process; after the copy the file listing (names and sizes) equals BASE's; copy-on-write
# extent size 4 KB, so a 4 KB database page write unshares 4 KB, not XFS's default 128 KB.
# usage: restore_reflink.sh BASE
set -euo pipefail
source /prologue/machine.env; source "$PROLOGUE_NODE_HOME/engine-replay/node-common.sh"   # reth_running
BASE=${1:?BASE directory}
WORK=$PROLOGUE_NODE_HOME/data
r=$(reth_running) && { echo "reth running (pid $r)"; exit 1; }
[ -d "$BASE/db" ] || { echo "$BASE has no db/"; exit 1; }
[ "$(stat -f -c %T "$WORK")" = xfs ] || { echo "$WORK is not on XFS"; exit 1; }
[ "$(stat -c %d "$BASE")" = "$(stat -c %d "$WORK")" ] || { echo "BASE and $WORK are on different file systems"; exit 1; }
t0=$(date +%s.%N)
find "$WORK" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
xfs_io -c 'cowextsize 4k' "$WORK"
cp -a --reflink=always "$BASE"/. "$WORK"/
[ "$(xfs_io -r -c cowextsize "$WORK/db/mdbx.dat" | sed 's/^\[\([0-9]*\)\].*/\1/')" = 4096 ] || { echo "copy-on-write extent size of mdbx.dat is not 4 KB"; exit 3; }
chmod -R u+w "$WORK"
t1=$(date +%s.%N)
[ "$(listing_sha "$BASE")" = "$(listing_sha "$WORK")" ] || { echo "listing of the working copy differs from $BASE"; exit 2; }
echo "restore_reflink: $BASE -> $WORK in $(printf '%.1f' "$(echo "$t1 - $t0" | bc)") s, $(cd "$WORK" && find . -type f | wc -l) files"
