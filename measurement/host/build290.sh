#!/usr/bin/env bash
# Build reth 2.9.0 (stock, or the Prologue tree) on a measurement server.
# The toolchain is in /opt/conda, the cargo home in /prologue/cargo-home (system disk), the build directory in
# /work/target/<name> (local disk); the binary goes to /prologue/bin. The build holds the run lock $PROLOGUE_RUN_LOCK
# throughout, so it never overlaps a node run. Run as user prologue.
#
# usage: build290.sh <source tree> <commit> <name> [MODE=build|test+build]
#   stock:  build290.sh /prologue/src/reth-2.9.0 c9a780f reth-2.9.0-upstream-c9a780f      (MODE defaults to build, -p reth)
# Environment: JOBS (default 16), TEST_THREADS (default 16), PKGS (packages whose tests run), FORCE=1 replaces an existing
# binary, SKIP_TESTS="name ..." (passed as --skip to each package's tests; only for tests that fail on the base as well),
# BUILD_LOCK=<file>: build under this lock instead of the run lock, at nice 19 and idle I/O priority, only while no
# timing run is on the machine.
# Settings: VERGEN_GIT_SHA=<full commit>, VERGEN_GIT_DIRTY=false, CARGO_PROFILE_RELEASE_STRIP=none,
# JEMALLOC_SYS_WITH_LG_VADDR=48 (48-bit virtual addresses), no RUSTFLAGS (no target-cpu=native),
# cargo build --release --locked, rust 1.98.1 (conda reth-build), LLVM 23.1.4 (conda llvm23-build, for evm2-jit's
# llvm-sys 231), offline (dependencies fetched beforehand with cargo fetch).
set -euo pipefail
[ $# -eq 3 ] || { sed -n '2,12p' "$0"; exit 2; }
WT=$(realpath "$1"); EXPECT=$2; NAME=$3
MODE=${MODE:-build}; JOBS=${JOBS:-16}; TEST_THREADS=${TEST_THREADS:-16}
PKGS=${PKGS:-reth-execution-cache reth-engine-tree reth-storage-overlay reth-trie-parallel}
source /prologue/machine.env; OUT=/prologue/bin; LOCK=${BUILD_LOCK:-$PROLOGUE_RUN_LOCK}
mkdir -p $OUT /work/target /work/build-logs

for m in ${MODE//+/ }; do case $m in build|test) ;; *) echo "unknown mode $m"; exit 2 ;; esac; done
# No build during a node run and no node run during a build: the build holds the run lock throughout
exec 8>"$LOCK"; flock -n 8 || { echo "a node run or another build holds $LOCK; not building"; exit 75; }

H=$(git -C "$WT" rev-parse HEAD); SH=${H:0:7}
[[ "$H" == "$EXPECT"* ]] || { echo "tree is at $H, not $EXPECT"; exit 2; }
[ -z "$(git -C "$WT" status --porcelain --untracked-files=no)" ] || { git -C "$WT" status --short | head; echo "modified tracked files"; exit 2; }
B=$OUT/$NAME
[[ "+$MODE+" == *+build+* ]] && [ -e "$B" ] && [ "${FORCE:-0}" != 1 ] && { echo "binary exists: $B"; exit 3; }
if [ "$H" = c9a780f4f23d6752ca299b104c93b7f099673c80 ]; then DESCRIBE=v2.9.0; PSEL=(-p reth); else
  [[ "$NAME" =~ ^reth-2\.9\.0-([A-Za-z0-9._-]+)-([0-9a-f]{7,})$ ]] || { echo "name must be reth-2.9.0-<tag>-<hash>"; exit 2; }
  [[ "$H" == "${BASH_REMATCH[2]}"* ]] || { echo "name hash is not the commit"; exit 2; }
  DESCRIBE=v2.9.0-${BASH_REMATCH[1]}-g$SH; PSEL=(); fi
T=/work/target/$NAME

E=/opt/conda/envs; LB=/prologue/toolchain/llvmbin
mkdir -p $LB; ln -sf $E/llvm23-build/bin/llvm-config $LB/llvm-config; ln -sf $E/llvm23-build/bin/ld.lld $LB/ld.lld
export VERGEN_GIT_SHA=$H VERGEN_GIT_DIRTY=false VERGEN_GIT_DESCRIBE=$DESCRIBE
export PATH=$LB:$E/reth-build/bin:/usr/bin:/bin CARGO_HOME=/prologue/cargo-home LLVM_SYS_231_PREFIX=$E/llvm23-build
export CARGO_TARGET_DIR=$T CARGO_PROFILE_RELEASE_STRIP=none JEMALLOC_SYS_WITH_LG_VADDR=48 CARGO_NET_OFFLINE=true
export RUSTC=$E/reth-build/bin/rustc; C=$E/reth-build/bin/cargo
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS
cd "$WT"
V=$(llvm-config --version); [[ "$V" == 23.* ]] || { echo "llvm-config is $V, not LLVM 23"; exit 2; }
echo "tree $WT $H; mode $MODE; jobs $JOBS; target $T; describe $DESCRIBE"
echo "$($RUSTC -V); $($C -V); llvm-config $V; $(ld.lld --version | cut -c1-12); $(cc --version | head -1)"
L0=$(sha256sum Cargo.lock)
touch crates/node/core/build.rs
LOGD=/work/build-logs/$NAME.$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$LOGD"; echo "logs $LOGD"

for M in ${MODE//+/ }; do
  case $M in
    test)
      FLAKY=persistence::tests::test_read_only_consistency_across_reorg
      for pkg in $PKGS reth-provider; do
        args=(--test-threads="$TEST_THREADS")
        [ "$pkg" = reth-provider ] && args+=(acc_filter)
        [ "$pkg" = reth-engine-tree ] && args+=(--skip "$FLAKY")
        for k in ${SKIP_TESTS:-}; do args+=(--skip "$k"); done   # SKIP_TESTS: tests that also fail on the base commit (named by the requester)
        t=$(date +%s); trc=0
        nice -n 19 $C test --release --locked -p "$pkg" --lib -j "$JOBS" -- "${args[@]}" > "$LOGD/test.$pkg.log" 2>&1 || trc=$?
        grep -E "^test result|^error" "$LOGD/test.$pkg.log" || tail -30 "$LOGD/test.$pkg.log"
        sed -n 's/^test \(.*\) \.\.\. FAILED$/FAILED \1/p' "$LOGD/test.$pkg.log"
        echo "test $pkg (${args[*]}) rc $trc, $(( $(date +%s) - t )) s"; [ $trc -eq 0 ] || exit 6
      done
      if [[ " $PKGS " == *" reth-engine-tree "* ]]; then
        for k in 1 2 3; do
          if nice -n 19 $C test --release --locked -p reth-engine-tree --lib -j "$JOBS" -- "$FLAKY" > "$LOGD/test.flaky.$k.log" 2>&1; then
            echo "flaky test passed on try $k"; break; fi
          echo "flaky test failed on try $k"
        done
      fi ;;
    build)
      t=$(date +%s)
      nice -n 19 $C build --release --locked "${PSEL[@]}" --bin reth -j "$JOBS" > "$LOGD/build.log" 2>&1 || { tail -40 "$LOGD/build.log"; exit 6; }
      echo "build wall $(( $(date +%s) - t )) s"
      [ "$(sha256sum Cargo.lock)" = "$L0" ] || { echo "Cargo.lock changed during the build"; exit 7; }
      cp "$T/release/reth" "$B.part" && mv "$B.part" "$B"
      echo "built $B sha256 $(sha256sum "$B" | cut -d' ' -f1)"
      echo "ldd: $(ldd "$B" | grep -c 'not found' || true) libraries not found"
      VOUT=$("$B" --version); sed -n '1,5p' <<< "$VOUT"
      grep -q "^Commit SHA: $H" <<< "$VOUT" && echo "version commit ok" || { echo "VERSION COMMIT MISMATCH"; exit 5; } ;;
  esac
done
echo "done $(date -u +%FT%TZ)"
