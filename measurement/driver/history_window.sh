# Prologue server copy (scripts/server/apply_server.py) of history_window.sh: the server's minimal snapshot prunes
# history by distance and every pass restores the base, so the history check only checks that the prune checkpoints are
# readable; check_history_window_bin comes from the server's node-common.sh.
source "$PROLOGUE_NODE_HOME/engine-replay/node-common.sh"
