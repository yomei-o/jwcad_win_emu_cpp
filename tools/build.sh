#!/bin/sh
# Native build of jwemu.exe, at low priority, in parallel.
set -e
cd "$(dirname "$0")/.."
export PATH=/c/prog/w64devkit/bin:$PATH
JOBS=${JOBS:-$(( $(nproc) > 2 ? $(nproc) - 1 : 1 ))}
. tools/lowpri.sh
make -j"$JOBS" "$@"
# The real comctl32 (5.82) runs inside the emulator; it is Microsoft's, so it
# is copied from this machine rather than kept in the repository.
mkdir -p dlls
if [ ! -f dlls/comctl32.dll ] && [ -f /c/Windows/SysWOW64/comctl32.dll ]; then
    cp /c/Windows/SysWOW64/comctl32.dll dlls/
fi
