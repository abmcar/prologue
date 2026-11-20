#!/bin/bash
# Per-transaction tables of the recording processes (segments k = 0, 4, 8; passes 0-4; rows H0 stock reth, H3 Prologue
# without plans, H4 Prologue, H5 stock reth plus plans), via extract247_e270.py, into paper/data/f270_tx/. Needs the
# per-read records rec<k><p>.diag.jsonl under results/main/raw/e270rec-<k>/raw, which are not in the repository; the
# tables themselves are, so restcost247_e270.py runs without this step.
# usage (repository root): bash paper/scripts/extract247_e270.sh
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
S=$ROOT/paper/scripts; E=$ROOT/results/main/raw; O=$ROOT/paper/data/f270_tx
for k in 0 4 8; do for p in 0 1 2 3 4; do
  [ -e "$O/tx_rec$k$p.csv.gz" ] && continue
  EXP247_REC=$E/e270rec-$k EXP247_OUT=$O EXP247_CLASS=$ROOT/measurement/block_classes.csv \
    python3 $S/extract247_e270.py rec$k $p H0 H3 H4 H5 || { echo "extract rec$k$p failed"; exit 1; }
done; done
echo "all 15 passes extracted"
