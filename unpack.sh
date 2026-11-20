#!/usr/bin/env bash
# Unpack the per-block tables of the measurement (results/main/raw, 220 MB) and of the 10,000-block recording run.
set -euo pipefail
cd "$(dirname "$0")"
tar -C results/main --zstd -xf results/main/runs.tar.zst
zstd -dqf results/blockreads/recorded_10k_blocks.csv.zst
echo "unpacked results/main/raw ($(ls results/main/raw | wc -l) runs) and results/blockreads/recorded_10k_blocks.csv"
