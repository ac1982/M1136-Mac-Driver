#!/usr/bin/env python3
"""Package an already validated local release build; never install anything."""
import hashlib
import json
import platform
import shutil
import subprocess
import tarfile
from pathlib import Path
from provenance import verify, digest
from signing import inspect
from release_version import release_version
root=Path(__file__).resolve().parents[1]
version=release_version(root)
if platform.system()!='Darwin' or platform.machine()!='arm64':
    raise SystemExit('Package on native Apple Silicon only')
try:
    manifest=verify(root,root/'build-macos')
except (OSError, ValueError, KeyError) as error:
    raise SystemExit(f'Cannot package unvalidated build: {error}')
binary=root/'build-macos/rastertom1136'
signing=inspect(binary)
subprocess.run(['python3',str(root/'scripts/check-binary.py'),str(binary)],check=True)
revision=manifest['source']['git_commit']
out=root/'build-package';out.mkdir(exist_ok=True)
stage=out/'M1136-Mac-Driver';stage.mkdir(exist_ok=True)
for source,name in [(binary,'rastertom1136'),(root/'ppd/M1136.ppd','M1136.ppd'),
                    (root/'scripts/install-macos.sh','install-macos.sh'),
                    (root/'docs/INSTALL.zh-CN.md','INSTALL.zh-CN.md'),(root/'COPYING','COPYING')]:
    shutil.copy2(source,stage/name)
    expected = (manifest['binary_sha256'] if source == binary else
                manifest['source']['files'][source.relative_to(root).as_posix()]['sha256'])
    if digest(stage/name) != expected:
        raise SystemExit('Package input changed after validation: ' + name)
(stage/'BUILD.json').write_text(json.dumps({'version':version,'git_commit':revision,
    'git_dirty':manifest['source']['git_dirty'],
    'binary_sha256':manifest['binary_sha256'],
    'source_sha256':hashlib.sha256(json.dumps(manifest['source'],sort_keys=True).encode()).hexdigest(),
    'build_host':subprocess.check_output(['/usr/bin/sw_vers'],text=True),
    'architecture':platform.machine(),'signing':signing,
    'notarization':'Not asserted for this archive; see signed PKG release report',
    'hardware_printing_verified':False},indent=2)+'\n')
files=['rastertom1136','M1136.ppd','install-macos.sh','INSTALL.zh-CN.md','COPYING','BUILD.json']
(stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in files))
archive=out/'M1136-Mac-Driver-arm64.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for name in files+['SHA256SUMS']: tar.add(stage/name,arcname='M1136-Mac-Driver/'+name)
print(archive)
