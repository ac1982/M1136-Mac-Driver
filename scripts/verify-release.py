#!/usr/bin/env python3
"""Check accepted release metadata and asset digests before publication."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]) if len(sys.argv)>1 else root / 'build-package'
version = (root / 'VERSION').read_text().strip()
report_name = 'M1136-Mac-Driver-release.json'
r = json.loads((out / report_name).read_text())
assert r['build']['version'] == version
assert r['build']['git_dirty'] is False, 'Release must come from a clean commit'
if os.environ.get('GITHUB_SHA'):
    assert r['build']['git_commit'] == os.environ['GITHUB_SHA'], 'Release commit mismatch'
assert r['team_id'] == '89G3DBC6CS'
assert r['build']['signing']['team_id'] == '89G3DBC6CS'
assert r['notarization'] == 'Accepted' and r['stapled'] is True
package_name = f'M1136-Mac-Driver-{version}-arm64.pkg'
source_name = 'M1136-Mac-Driver-source.tar.gz'
for name, expected in [(package_name, r['package_sha256']), (source_name, r['source_archive_sha256'])]:
    assert hashlib.sha256((out/name).read_bytes()).hexdigest() == expected, name
with tarfile.open(out/source_name) as tar:
    assert tar.extractfile('M1136-Mac-Driver-source/VERSION').read().decode().strip() == version
names = [package_name, source_name, report_name]
(out/'SHA256SUMS').write_text(''.join(hashlib.sha256((out/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in names))
print('Accepted clean-commit release and asset checksums PASS')
