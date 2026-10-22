#!/bin/sh
# Runs Jw_win.exe headless from orig/ and writes the screen to tmp/.
#   sh tools/run.sh [seconds] [extra jwemu options...]
cd "$(dirname "$0")/.."
mkdir -p tmp
secs=${1:-15}; [ $# -gt 0 ] && shift
cd orig
JWEMU_REGISTRY=../tmp/reg.txt ../jwemu.exe --headless --time $((secs * 1000)) --shot ../tmp/shot.png "$@" Jw_win.exe
