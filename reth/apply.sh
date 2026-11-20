#!/usr/bin/env bash
# Fetch reth v2.9.0 and evm2 at the commit reth v2.9.0 pins, apply the patches of this directory, and check that the
# resulting source trees are the ones measured in the paper (git tree hashes).
# usage: reth/apply.sh DEST            -> DEST/reth-2.9.0-prologue and DEST/evm2-x290 (the manifest refers to ../evm2-x290)
# Environment: RETH_URL, EVM2_URL (default: the upstream repositories on GitHub).
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd); D=$(realpath -m "${1:?usage: apply.sh DEST}"); mkdir -p "$D"
RETH_URL=${RETH_URL:-https://github.com/paradigmxyz/reth}; EVM2_URL=${EVM2_URL:-https://github.com/alloy-rs/evm2}
RETH_BASE=c9a780f4f23d6752ca299b104c93b7f099673c80      # tag v2.9.0
EVM2_BASE=f93318f120f6300599b21170d6c7bef81ed63d87      # the evm2 revision in reth v2.9.0's Cargo.toml
STOCK_TREE=215bd925357d21e713f8cfd36387b56c2a16ace7     # after patch 0001: the stock baseline (two compiler flags added)
PROLOGUE_TREE=178bf5a95d7be1939d5aae7766b3f71c70c43765  # after patch 0002: Prologue
EVM2_TREE=9dc7206301b972b8cf61b2f53a9da402c5e72bdf
am() { git -c user.name=prologue -c user.email=prologue@localhost -c commit.gpgsign=false am -q --whitespace=nowarn "$@"; }

git init -q "$D/reth-2.9.0-prologue"; cd "$D/reth-2.9.0-prologue"
git fetch -q --depth 1 "$RETH_URL" "$RETH_BASE"; git checkout -q -B prologue FETCH_HEAD
[ "$(git rev-parse HEAD)" = "$RETH_BASE" ] || { echo "reth base is not v2.9.0"; exit 1; }
am "$H"/patches/reth/0001-*.patch
[ "$(git rev-parse 'HEAD^{tree}')" = "$STOCK_TREE" ] || { echo "stock tree mismatch"; exit 1; }
git branch -f stock HEAD
am "$H"/patches/reth/0002-*.patch
[ "$(git rev-parse 'HEAD^{tree}')" = "$PROLOGUE_TREE" ] || { echo "Prologue tree mismatch"; exit 1; }

git init -q "$D/evm2-x290"; cd "$D/evm2-x290"
git fetch -q --depth 1 "$EVM2_URL" "$EVM2_BASE"; git checkout -q -B prologue FETCH_HEAD
am "$H"/patches/evm2/0001-*.patch
[ "$(git rev-parse 'HEAD^{tree}')" = "$EVM2_TREE" ] || { echo "evm2 tree mismatch"; exit 1; }
echo "ok: $D/reth-2.9.0-prologue (branches stock = $STOCK_TREE, prologue = $PROLOGUE_TREE), $D/evm2-x290 ($EVM2_TREE)"
