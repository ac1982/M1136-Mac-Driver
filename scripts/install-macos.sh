#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Explicit administrator installation only. Never called by build or CI.
set -eu
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || exit 1
[ "$(id -u)" = 0 ] || { echo 'Run with sudo after reviewing the package.' >&2; exit 1; }
[ "$#" = 1 ] || { echo 'Usage: sudo sh install-macos.sh "usb://..."' >&2; exit 1; }
uri=$1
case "$uri" in usb://*) ;; *) echo 'USB device URI required' >&2; exit 1;; esac
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dest=/Library/Printers/M1136MacDriver
queue=HP_M1136_Native_C
[ ! -e "$dest" ] && [ ! -L "$dest" ] || { echo 'Destination exists; refusing overwrite.' >&2; exit 1; }
if lpstat -p "$queue" >/dev/null 2>&1; then echo 'Queue exists; refusing overwrite.' >&2; exit 1; fi
stage=$(mktemp -d /Library/Printers/.M1136MacDriver.XXXXXX)
trap 'rm -rf "$stage"' EXIT
install -o root -g wheel -m 755 "$source_dir/rastertom1136" "$stage/rastertom1136"
install -o root -g wheel -m 644 "$source_dir/M1136.ppd" "$stage/M1136.ppd"
for file in rastertom1136 M1136.ppd; do
    expected=$(awk -v name="$file" '$2 == name {print $1}' "$source_dir/SHA256SUMS")
    actual=$(shasum -a 256 "$stage/$file" | awk '{print $1}')
    [ "$actual" = "$expected" ] || { echo "Checksum failed: $file" >&2; exit 1; }
done
lipo "$stage/rastertom1136" -verify_arch arm64
codesign --verify --strict "$stage/rastertom1136"
cupstestppd -I filters "$stage/M1136.ppd"
chmod 755 "$stage"
mv "$stage" "$dest"
trap - EXIT
if ! lpadmin -p "$queue" -E -v "$uri" -P "$dest/M1136.ppd" \
    -D 'HP M1136 Native C' -o printer-is-shared=false; then
    echo "Queue setup failed. Files remain at $dest; see rollback instructions." >&2
    exit 1
fi
printf 'Installed queue %s. Default printer unchanged. No test page sent.\n' "$queue"
