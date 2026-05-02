#!/bin/bash
# Usage: daemon_launch.sh <logfile> <command...>
# Daemonises the command so it survives terminal/parent disconnects.
# Uses double-fork + new process group via Python, since macOS lacks setsid(1).
set -euo pipefail
LOG="$1"; shift
exec python3 -c '
import os, sys, subprocess
# double-fork
if os.fork() != 0: os._exit(0)
os.setsid()
if os.fork() != 0: os._exit(0)
log = sys.argv[1]
cmd = sys.argv[2:]
with open(log, "ab", buffering=0) as f:
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(f.fileno(), 1)
    os.dup2(f.fileno(), 2)
os.execvp(cmd[0], cmd)
' "$LOG" "$@"
