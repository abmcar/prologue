# Prologue server: helpers of the scripts run as root (first_start.sh, forward.sh, make_base.sh, boot_prepare.sh,
# fleet_prepare.sh). Sourcing it stops a caller that is not root and reads /prologue/machine.env.
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 2; }
source /prologue/machine.env
ts() { echo "$(date -Is) $*"; }
# the run lock on fd 8 for the rest of the caller (prologue_run.sh, build290.sh and these scripts exclude each other)
take_run_lock() { exec 8>"$PROLOGUE_RUN_LOCK"; flock -n 8 || { echo "another run or build holds $PROLOGUE_RUN_LOCK"; exit 3; }; }
# a command as user prologue in the node home, with node-common.sh's helpers
# as user prologue, in the caller's cgroup: not `su -`, which opens a login session and so moves the command into
# user.slice, onto the driver's 4 cores (11-04: a build started through su ran on cores 28-31 only)
asp() { setpriv --reuid=prologue --regid=prologue --init-groups env -i HOME=/home/prologue USER=prologue LOGNAME=prologue \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin bash -c "source $PROLOGUE_NODE_HOME/engine-replay/node-common.sh; $*"; }
# ssh to another machine of the same image (root, key /root/.ssh/id_prologue); fast cipher for bulk copies
SSH_PROLOGUE=(ssh -i /root/.ssh/id_prologue -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=20 -c aes128-gcm@openssh.com)
