#!/usr/bin/env bash
# Prologue server: stands in for `labq status` in the driver copy (run_f.sh records it before and after every pass).
# Prints the load, memory and the ten processes with the most CPU time.
echo "load $(cat /proc/loadavg)"
free -g | sed -n 1,2p
ps -eo pid,user,psr,pcpu,rss,comm --sort=-pcpu | head -11
