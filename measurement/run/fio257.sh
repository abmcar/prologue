#!/bin/bash
# EXP-257 README 5.3 (written before the run, 11-07): before a storage tier's node processes, measure the device under
# the node's working database with fio, outside any timed run (holds the run lock): 4 KiB random reads with O_DIRECT on
# a 16 GiB file in that directory, (a) one in flight for 60 s (mean and 99th percentile latency), (b) 32 in flight for
# 60 s (IOPS). The file is laid out first (written, not timed) and deleted afterwards, so the next restore sees the
# base only. Output: /work/fio257/<tier>.json and a summary line in /work/fio257/<tier>.txt.
# usage: bash fio257.sh <nvme|pl1|pl0>
set -uo pipefail
source /prologue/scripts/root-common.sh   # ts, take_run_lock, asp
T=${1:?tier}; [[ "$T" =~ ^(nvme|pl1|pl0)$ ]] || { echo "tier $T: nvme, pl1 or pl0"; exit 2; }
command -v fio >/dev/null || { echo "fio is not installed"; exit 3; }
O=/work/fio257; mkdir -p $O
take_run_lock
r=$(asp reth_running) && { ts "a reth process is running ($r)"; exit 3; }
W=$PROLOGUE_NODE_HOME/data; F=$W/fio257.dat
dev=$(basename "$(findmnt -no SOURCE --target "$W" | sed 's/\[.*\]$//')")
ts "fio on $W ($dev), tier $T" | tee -a $O/$T.txt
fio --name=lay --filename=$F --size=16g --rw=write --bs=1m --direct=1 --ioengine=libaio --iodepth=8 > /dev/null || { ts "layout failed"; rm -f $F; exit 5; }
fio --output-format=json --output=$O/$T.json --filename=$F --size=16g --direct=1 --ioengine=libaio --bs=4k --rw=randread \
  --time_based --runtime=60 --group_reporting \
  --name=qd1 --iodepth=1 --numjobs=1 \
  --name=qd32 --stonewall --iodepth=32 --numjobs=1 || { ts "fio failed"; rm -f $F; exit 5; }
rm -f $F
python3 - $O/$T.json <<'PY' | tee -a $O/$T.txt
import json, sys
d = json.load(open(sys.argv[1]))
for j in d['jobs']:
    r = j['read']; lat = r['clat_ns']
    p99 = lat.get('percentile', {}).get('99.000000', 0)
    print(f"{j['jobname']}: iops {r['iops']:.0f}, mean latency {lat['mean'] / 1000:.1f} us, p99 {p99 / 1000:.1f} us, bw {r['bw'] / 1024:.0f} MiB/s")
PY
