#!/usr/bin/env bash
# Prologue server: prepare a machine started from the system-disk image (or the first machine) up to the point where the
# node data can be put on it. Idempotent; run as root after every boot of a new machine (the image keeps /prologue,
# /opt/conda, the user and the limits; the local disks start empty on a new machine and may be empty after a host move).
#   1. local disks: every virtio disk without partitions or a file system other than the system disk, in name order,
#      gets one GPT partition and XFS (reflink=1, rmapbt=1) and is mounted by UUID with noatime,nofail:
#        1 disk: /data; 2: /data /work; 3: /data /data2 /work; 4 or more: /data /data2 /work /spare ...
#      without /data2 the block pool and the second base go to /data; without /work, /work is a directory on /data
#   2. user prologue (RLIMIT_NICE and RTPRIO 0 as on the development host, nofile 524288; one password-less sudo rule, for
#      prologue-rtprio, which the driver's NODE_RTPRIO uses in place of the development host's `sudo prlimit`)
#   2b. analysis tools: bpftrace and libbpf-tools when missing (perf, iostat, pidstat come with the image)
#   3. /prologue/machine.env: paths, locks and the core split read from sysfs (physical cores = sibling groups), as the
#      EAP Master set it on 2026-11-04 (layout pc14h on a 16-core machine, the one the final measurement uses):
#        node: both threads of every physical core but the last DRIVER_PHYS (default: all but 2);
#        driver: both threads of the last DRIVER_PHYS physical cores (default 2);
#      no core is left for offline work: builds and offline work never run during a node run (prologue_run.sh's lock)
#      override with NODE_PHYS=.. DRIVER_PHYS=.. machine_setup.sh (other layouts: set NODE_CPUS_RUN, DRIVER_CPUS per run)
#   3b. user.slice, init.scope, every running service and the cloud security agent on the driver's cores
#   4. the node home $PROLOGUE_NODE_HOME (data/ comes from boot_prepare.sh), the server driver copy (apply_server.py,
#      regenerated when the commit of its inputs changed), /work/runs
# usage: machine_setup.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 2; }
SYS=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")

# --- 1. local disks -----------------------------------------------------------------------------------------------------
mapfile -t DISKS < <(lsblk -dno NAME,TYPE | awk '$2 == "disk" {print $1}' | grep -v "^$SYS$" | sort)
case ${#DISKS[@]} in
  0) echo "no local data disk"; exit 3 ;;
  1) MP=(/data) ;; 2) MP=(/data /work) ;;
  *) MP=(/data /data2 /work); for ((i = 3; i < ${#DISKS[@]}; i++)); do MP+=(/spare$((i - 2))); done ;;
esac
for i in "${!DISKS[@]}"; do
  d=/dev/${DISKS[$i]}; m=${MP[$i]}; p=${d}1
  [[ "$d" =~ [0-9]$ ]] && p=${d}p1   # NVMe (i4, i5: /dev/nvme0n1) names its partitions nvme0n1p1
  # probe the devices themselves (blkid -p), not the udev cache: right after boot lsblk can report nothing for a disk that
  # holds data. Only a disk with no signature at all is partitioned, only an empty partition is formatted.
  udevadm settle
  if [ ! -b "$p" ]; then
    blkid -p "$d" >/dev/null 2>&1 && { echo "$d carries a signature but has no partition 1: $(blkid -p "$d"); not touching it"; exit 3; }
    parted -s "$d" mklabel gpt mkpart primary xfs 1MiB 100%; udevadm settle
  fi
  fs=$(blkid -p -o value -s TYPE "$p" 2>/dev/null || true)
  case $fs in
    xfs) ;;
    '') # blkid -p always reports the partition entry (PART_ENTRY_*); a superblock of any kind sets USAGE
        use=$(blkid -p -o value -s USAGE "$p" 2>/dev/null || true)
        [ -z "$use" ] || { echo "$p carries a $use signature that is not XFS: $(blkid -p "$p"); not touching it"; exit 3; }
        mkfs.xfs -q -m reflink=1,rmapbt=1 -L "$(basename "$m")" "$p" ;;
    *) echo "$p holds $fs, not XFS; not touching it"; exit 3 ;;
  esac
  u=$(blkid -s UUID -o value "$p"); mkdir -p "$m"
  grep -q "UUID=$u " /etc/fstab || { sed -i "\| $m xfs |d" /etc/fstab; echo "UUID=$u $m xfs defaults,noatime,nofail,x-systemd.device-timeout=10s 0 2" >> /etc/fstab; }
  mountpoint -q "$m" || mount "$m"
  echo "disk $d -> $m ($(df -h --output=size "$m" | tail -1 | tr -d ' '))"
done
systemctl daemon-reload
if ! mountpoint -q /work; then mkdir -p /data/work /work; mount --bind /data/work /work; fi   # one or two disks: /work lives on /data
POOL=/data/blocks_pool; mountpoint -q /data2 && POOL=/data2/blocks_pool

# --- 2. user and limits -------------------------------------------------------------------------------------------------
id prologue >/dev/null 2>&1 || useradd -m -s /bin/bash -U prologue
printf 'prologue soft nofile 524288\nprologue hard nofile 524288\n' > /etc/security/limits.d/prologue.conf
# the one command prologue may run with sudo: prologue-rtprio raises RLIMIT_RTPRIO of one of prologue's processes (the
# driver's NODE_RTPRIO); not prlimit itself, which runs commands and would hand out a root shell
install -o root -g root -m 755 "$(dirname "$(realpath "$0")")/prologue-rtprio" /usr/local/sbin/prologue-rtprio
rm -f /etc/sudoers.d/prologue-prlimit
echo 'prologue ALL=(root) NOPASSWD: /usr/local/sbin/prologue-rtprio' > /etc/sudoers.d/prologue-rtprio; chmod 440 /etc/sudoers.d/prologue-rtprio
visudo -cq

# --- 2b. analysis tools (EAP Master 11-04 22:0x; README, analysis tools) ----------------------------------------------------------
# perf (linux-tools of the running kernel), iostat and pidstat (sysstat) come with the image; bpftrace and libbpf-tools (the
# bcc tools built against BTF: offcputime-libbpf, profile-libbpf, biolatency-libbpf, runqlat-libbpf ...) are installed here
# from the region's internal mirror when missing (15 s). Not bpfcc-tools: its Python tools fail to compile against kernel
# 7.0's headers. Never during a run: push_repo.sh, which runs this script, refuses while the run lock is held.
pk=(bpftrace libbpf-tools sysstat "linux-tools-$(uname -r)")
dpkg -s "${pk[@]}" >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends "${pk[@]}" | tail -1

# --- 3. machine.env -----------------------------------------------------------------------------------------------------
mapfile -t PHYS < <(cat /sys/devices/system/cpu/cpu[0-9]*/topology/thread_siblings_list | sort -n -u)   # one line per physical core
P=${#PHYS[@]}; DP=${DRIVER_PHYS:-2}; NP=${NODE_PHYS:-$((P - DP))}
(( NP >= 1 && DP >= 1 && NP + DP <= P )) || { echo "core split node $NP + driver $DP does not fit $P physical cores"; exit 3; }
join() { local IFS=,; echo "$*"; }
NODE=$(join "${PHYS[@]:0:NP}"); DRV=$(join "${PHYS[@]:P-DP}")
cat > /prologue/machine.env <<EOF
# written by scripts/server/machine_setup.sh $(date -Is) on $(hostname): $P physical cores, ${#DISKS[@]} local disks
export PROLOGUE_REPO=/prologue/engine-access-plan PROLOGUE_RETH_REPO=/prologue/src/reth-2.9.0
export PROLOGUE_NODE_HOME=/data/node/home PROLOGUE_BLOCKS_POOL=$POOL PROLOGUE_DRIVER=/prologue/driver/scripts
export PROLOGUE_RUN_LOCK=/run/lock/prologue-run.lock PROLOGUE_NODE_CPUS=$NODE PROLOGUE_DRIVER_CPUS=$DRV
# defaults for run_f.sh, kept when a run sets them. BLOCK_FILES_END: no upper bound beyond the driver's own check that
# every block file FWD0+1..END is there; CLASSFILE: the class file of the server segments (X-028,
# scripts/server/prologue_classify.py, 26,299,455-26,340,032)
: \${BLOCK_FILES_END:=99999999}; export BLOCK_FILES_END
: \${NODE_LD_LIBRARY_PATH=}; export NODE_LD_LIBRARY_PATH   # 2.9.0 binaries need no extra libraries
: \${CLASSFILE:=\$PROLOGUE_REPO/experiments/EXP-240-e2e-after-exec/results/prologue_class_26299455_26340032.csv}; export CLASSFILE
# the standard settings for new runs (EAP Master 11-05 01:0x; a run that sets a variable keeps its own value):
#   post-block wait at least 0.25 s, warm-up and measured blocks (run_f.sh's default was 1 s; the idle check is unchanged;
#   prologue_run.sh starts run_f.sh with env -i and the run's own variables, and run_f.sh sources this file after them);
#   driver mode fcu (scripts/server/apply_prologue_lean.py: one /metrics per block, after forkchoiceUpdated);
#   srdiag=0 added to CTRL_ADD unless the run's CTRL_ADD names srdiag itself (the node takes the last token)
: \${SETTLE_MIN:=0.25}; : \${SETTLE_MIN_MEASURED:=\$SETTLE_MIN}; export SETTLE_MIN SETTLE_MIN_MEASURED   # measured follows SETTLE_MIN, as in run_f.sh
: \${LEAN_MODE:=fcu}; export LEAN_MODE
case " \${CTRL_ADD:-} " in *" srdiag="*) ;; *) CTRL_ADD="\${CTRL_ADD:+\$CTRL_ADD }srdiag=0" ;; esac; export CTRL_ADD
EOF
cat /prologue/machine.env

# --- 3b. other processes on the driver's cores ---------------------------------------------------------------------------
# (EAP Master 11-04, X-028's core comparison 20.2): user sessions, init, every running service and the cloud security
# agent stay off the node's cores. system.slice itself is left alone: the run scopes of prologue_run.sh and forward.sh live under it.
# AllowedCPUs is persistent (/etc/systemd/system.control); the cloud security agent's own cgroups are set at every boot.
# every running service (system.slice's .service units; the run scopes are .scope units and stay unrestricted)
for u in user.slice init.scope $(systemctl list-units --type=service --state=running --no-legend --plain | awk '{print $1}'); do
  systemctl set-property "$u" AllowedCPUs="${DRV//,/ }" || echo "warning: AllowedCPUs not set on $u"
done
grep -qw cpuset /sys/fs/cgroup/cgroup.subtree_control || echo +cpuset > /sys/fs/cgroup/cgroup.subtree_control
for g in /sys/fs/cgroup/aegis /sys/fs/cgroup/aegisMonitor; do [ -e $g/cpuset.cpus ] && echo "$DRV" > $g/cpuset.cpus; done
echo "other processes on cores $DRV: $(systemctl show user.slice -p AllowedCPUs --value) (user.slice)"

# --- 4. node home, driver copy, run directories -------------------------------------------------------------------------
source /prologue/machine.env
[ -L /prologue/scripts ] || { rm -rf /prologue/scripts; ln -s $PROLOGUE_REPO/scripts/server /prologue/scripts; }
ln -sfn $PROLOGUE_REPO/scripts/server/README.md /prologue/README.md
H=$PROLOGUE_NODE_HOME
mkdir -p $H/bin $H/engine-replay/logs "$POOL" /work/runs /work/build-logs /work/target
touch $PROLOGUE_RUN_LOCK; chmod 666 $PROLOGUE_RUN_LOCK   # /run is emptied at boot; root and prologue both take it
ln -sfn /prologue/bin/reth-2.9.0-eap-int-a8eee90 $H/bin/reth
cp $PROLOGUE_REPO/scripts/server/node-common.sh $H/engine-replay/node-common.sh
cp /prologue/engine-replay/replay.py /prologue/engine-replay/fetch.py $H/engine-replay/
# the driver copy is regenerated whenever an input changed in the repository since it was made (apply_server.py's stamp)
want=$(su prologue -c "python3 $PROLOGUE_REPO/scripts/server/apply_server.py --inputs-commit")
have=$(cat $PROLOGUE_DRIVER/.generated_from 2>/dev/null || echo none)
if [ "$have" != "$want" ]; then
  echo "driver copy made from $have, inputs now at $want: regenerating $PROLOGUE_DRIVER"
  rm -rf $PROLOGUE_DRIVER
  python3 $PROLOGUE_REPO/scripts/server/apply_server.py $PROLOGUE_REPO/experiments/EXP-199-eap-own-prewarm/scripts $PROLOGUE_DRIVER
else
  echo "driver copy $PROLOGUE_DRIVER is current (inputs at $want)"
fi
chown -R prologue:prologue /data/node "$POOL" /work /prologue
echo "machine_setup done $(date -Is)"
