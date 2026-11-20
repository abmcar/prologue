#!/bin/bash
# EXP-270 (written before the run, 11-13; from EXP-257 scripts/seq257.sh): one machine's items in order (README 10),
# stopping at the first one that fails. Items:
#   need:<k>                between processes: ask for segment k's base (README 2, 10) and wait for it. Writes
#                           /work/need/base-<N> (N = SEG0 + 1000k) and waits, holding nothing, until the Aliyun session
#                           has put base-N and accflt-N.bin in /data/node from the Shanghai bucket (oss_get_base.sh: every
#                           piece's sha256 and the unpacked listing equal to MANIFEST) and written /work/have/base-<N>;
#                           then checks that both are there and that no reth process runs. No timing overlaps the copy:
#                           the sequence does nothing else while it waits.
#   drop:<k>                delete segment k's base and filter from /data/node (after its last process; frees the disk)
#   <mode>:<k>              a main270.sh node process (up ur un pn pp abl rec tchk; stup stun stpn stpp strec need TIER)
#   tier:<local|pl1|pl0>    set TIER for the storage items that follow
#   cores:<14|28>          README 18: the node's logical cpus 0-13 or 0-27 for the items that follow (XTAG h14 for 14)
#   mem:<16G|32G|64G>       set MEMT (and XTAG m16/m32/m64) for the items that follow (the memory machine sm)
#   essd:<pl1|pl0>/<k>      EXP-257 essd257.sh up (SEG0 as here; ESSD_NVME=1 on an i5): wait for the mounted disk, copy
#                           segment k's base onto it, bind-mount it under the node's working database
#   essdoff:<pl1|pl0>       EXP-257 essd257.sh down
#   fio:<local|pl1|pl0>     EXP-257 fio257.sh on the device under the node's working database (local runs it as nvme)
# XTAG0 (environment) is the machine's own tag: c on the processor machine, empty elsewhere.
# usage: systemd-run --scope --quiet -- env [JITW=8] BIN_UP=... BIN_SHA_UP=... BIN_SHA_INT=... BIN_INT=... INT_COMMIT=... [SEG0=...] [PLANS=...] [XTAG0=c] [ESSD_NVME=1] bash seq270.sh "need:0 up:0 ..."
set -u
S=$(dirname "$(readlink -f "$0")"); S257=$(cd "$S/../../EXP-257-main-measurement/scripts" && pwd)
export SEG0=${SEG0:-26305830}
TIER=""; MEMT=32G; XTAG=${XTAG0:-}
fail() { echo "$(date -Is) $1 failed; stop"; exit 4; }
for it in ${1:?sequence}; do
  m=${it%%:*}; a=${it#*:}
  case $m in
    need) N=$((SEG0 + 1000 * a)); mkdir -p /work/need /work/have; touch /work/need/base-$N
          echo "$(date -Is) need base-$N: waiting for /work/have/base-$N"
          until [ -e /work/have/base-$N ]; do sleep 30; done
          [ -d /data/node/base-$N/db ] && [ -e /data/node/accflt-$N.bin ] || fail "$it (have-marker without base-$N or accflt-$N.bin)"
          for p in /proc/[0-9]*; do case "$(basename "$(readlink $p/exe 2>/dev/null)")" in reth*) fail "$it (a reth process runs: $p)";; esac; done
          rm -f /work/need/base-$N ;;
    drop) N=$((SEG0 + 1000 * a)); rm -rf /data/node/base-$N /data/node/accflt-$N.* || fail "$it" ;;
    tier) TIER=$a ;;
    mem)  MEMT=$a; XTAG=m${a%G} ;;
    cores) export NCORES=$a; XTAG=$([ "$a" = 14 ] && echo h14 || echo "${XTAG0:-}") ;;   # README 18: node on logical cpus 0-13 (14) or 0-27 (28)
    essd) env ESSD_NVME="${ESSD_NVME:-0}" SEG0=$SEG0 bash "$S257/essd257.sh" up "${a%%/*}" "${a#*/}" || fail "$it" ;;
    essdoff) bash "$S257/essd257.sh" down "$a" || fail "$it" ;;
    fio)  bash "$S257/fio257.sh" "$([ "$a" = local ] && echo nvme || echo "$a")" || fail "$it" ;;
    up|ur|un|stup|stun)
          env TIER="$TIER" XTAG="$XTAG" MEMT="$MEMT" BIN="${BIN_UP:?}" BIN_SHA="${BIN_SHA_UP:?}" bash "$S/main270.sh" $m $a || fail "$it" ;;
    pn|pp|abl|rec|tchk|stpn|stpp|strec)
          env TIER="$TIER" XTAG="$XTAG" MEMT="$MEMT" BIN="${BIN_INT:?}" BIN_SHA="${BIN_SHA_INT:?}" INT_COMMIT="${INT_COMMIT:?}" bash "$S/main270.sh" $m $a || fail "$it" ;;
    *) echo "item $it?"; exit 4 ;;
  esac
  echo "$(date -Is) $it done"
done
echo "$(date -Is) sequence done"
