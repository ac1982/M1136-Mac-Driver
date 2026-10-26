#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || {
    echo 'Run on a native Apple Silicon Mac (not under Rosetta).' >&2; exit 1;
}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build="$root/build-macos"
cmake -S "$root" -B "$build" -DCMAKE_C_COMPILER=/usr/bin/clang \
    -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_BUILD_TYPE=Release
cmake --build "$build" --parallel 4
ctest --test-dir "$build" --output-on-failure
python3 "$root/scripts/check-binary.py" "$build/rastertom1136"
/usr/bin/lipo "$build/rastertom1136" -verify_arch arm64
/usr/bin/otool -L "$build/rastertom1136"
/usr/bin/codesign --force --sign - "$build/rastertom1136"
/usr/bin/codesign --verify --strict "$build/rastertom1136"
/usr/bin/cupstestppd -I filters "$root/ppd/M1136.ppd"
python3 "$root/tests/macos-pipeline.py" "$build/rastertom1136"
echo 'Build and software checks complete. Printer installation and physical printing are separate.'
