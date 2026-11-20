#!/usr/bin/env bash
# EXP-193: copy of EXP-192 scripts/start_node.sh, unchanged.
# EXP-192: copy of EXP-189 scripts/start_node.sh, unchanged.
# EXP-189: copy of EXP-184 scripts/start_node.sh, unchanged.
# EXP-184: copy of EXP-183 start_node.sh, unchanged.
# EXP-182: copy of EXP-181 start_node.sh, unchanged.
# EXP-181: copy of EXP-177 start_node.sh, unchanged.
# EXP-177: copy of EXP-176 start_node.sh, unchanged.
# EXP-176: copy of EXP-175 start_node.sh, unchanged.
# EXP-175: copy of the EXP-174 / EXP-172 script of the same name, unchanged.
# EXP-174: copy of EXP-172 start_node.sh, unchanged.
# EXP-171: copy of EXP-169 start_node.sh, unchanged.
# EXP-169: copy of EXP-167 start_node.sh, unchanged.
# EXP-167: copy of EXP-159 scripts/start_node.sh, unchanged. EXP-159: copy of EXP-157 scripts/start_node.sh, unchanged. EXP-157: copy of EXP-152 scripts/start_node.sh, unchanged. EXP-019: copy of EXP-018 scripts/start_node.sh (itself a copy of EXP-016), unchanged.
# Start the shared reth-full node with a given reth binary as a direct child process (the Science sandbox has no
# systemd user bus, so the transient unit of the development host cannot be used).
# Same node arguments as that script (CC_CACHETIME=1, LLVM 22 runtime libraries), pinned to the performance cores with
# a pinning helper (sched_setaffinity is refused in the sandbox). Prints the node PID on stdout; node stdout/stderr go
# to NODE_LOG. The caller stops the node with SIGTERM and waits for it.
# --ipcdisable: the sandbox cannot create the IPC socket in /tmp (Operation not permitted).
# usage: [NODE_ENV='K=V ...'] [NODE_CPUS=0-7] [NODE_LOG=file] start_node.sh BINARY [extra reth node args]
set -euo pipefail
BIN=$1
shift
# Prologue server copy: scripts/server/apply_server.py
source "$PROLOGUE_NODE_HOME/engine-replay/node-common.sh"   # cd the node directory; ulimit -n; PRUNE_ARGS; check_history_window
heal=0
# apply_v290.py (reth 2.9.0 binaries, Master 11-02): CKPT_BIN reads the prune checkpoints when set
if [ -n "${CKPT_BIN:-}" ]; then source "$(dirname "$(realpath "$0")")/history_window.sh"; check_history_window_bin "$CKPT_BIN" || heal=$?; else check_history_window || heal=$?; fi
if (( heal != 0 && heal != 4 )); then
  exit "${heal}"
fi
for kv in ${NODE_ENV:-}; do export "$kv"; done
# apply_rt.py (EXP-199 exrt, Master 11-01): NODE_RTPRIO=<n> raises this script's RLIMIT_RTPRIO to n (soft and hard) before the
# node starts; the node inherits it, so a thread may raise itself to a real-time policy at a priority up to n. sudo prlimit
# on this shell rather than cap_sys_nice on the binary, which would make the loader ignore LD_LIBRARY_PATH (set below).
if [ -n "${NODE_RTPRIO:-}" ]; then
  if ! [[ "$NODE_RTPRIO" =~ ^[1-9][0-9]?$ ]] || (( NODE_RTPRIO > 49 )); then echo "NODE_RTPRIO $NODE_RTPRIO: 1 to 49" >&2; exit 7; fi
  sudo -n /usr/local/sbin/prologue-rtprio $$ "$NODE_RTPRIO" || { echo "NODE_RTPRIO: sudo prlimit failed" >&2; exit 7; }
  [ "$(ulimit -r)" = "$NODE_RTPRIO" ] && [ "$(ulimit -H -r)" = "$NODE_RTPRIO" ] || { echo "NODE_RTPRIO: ulimit -r is $(ulimit -r)/$(ulimit -H -r)" >&2; exit 7; }
  echo "RLIMIT_RTPRIO $NODE_RTPRIO" >&2
fi
[ "${NODIAG:-0}" = 1 ] || export CC_CACHETIME=1   # apply_i4_254.py (EXP-254 / X-028): NODIAG=1 leaves the cache-time tags off
export LD_LIBRARY_PATH=${NODE_LD_LIBRARY_PATH-}   # apply_v290.py (reth 2.9.0 binaries, Master 11-02)
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy; export NO_PROXY='*' no_proxy='*'
taskset -c "${NODE_CPUS:-$PROLOGUE_NODE_CPUS}" "${BIN}" node --datadir data --chain mainnet \
  --authrpc.addr 127.0.0.1 --authrpc.port 8551 --authrpc.jwtsecret data/jwt.hex \
  --http --http.addr 127.0.0.1 --http.api eth,net,debug,reth --ipcdisable \
  --metrics 127.0.0.1:9001 \
  --disable-discovery --max-outbound-peers 0 --max-inbound-peers 0 \
  --log.file.directory engine-replay/logs "${PRUNE_ARGS[@]}" "$@" > "${NODE_LOG:-/dev/null}" 2>&1 &
echo $!
