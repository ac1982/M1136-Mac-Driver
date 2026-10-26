#!/usr/bin/env python3
"""Package an already validated local release build; never install anything."""
import hashlib
import json
import platform
import shutil
import subprocess
import tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if platform.system()!='Darwin' or platform.machine()!='arm64':
    raise SystemExit('Package on native Apple Silicon only')
binary=root/'build-macos/rastertom1136'
subprocess.run(['/usr/bin/codesign','--verify','--strict',str(binary)],check=True)
subprocess.run(['python3',str(root/'scripts/check-binary.py'),str(binary)],check=True)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
out=root/'build-package';out.mkdir(exist_ok=True)
stage=out/'M1136-Mac-Driver';stage.mkdir(exist_ok=True)
for source,name in [(binary,'rastertom1136'),(root/'ppd/M1136.ppd','M1136.ppd'),
                    (root/'scripts/install-macos.sh','install-macos.sh'),
                    (root/'docs/INSTALL.zh-CN.md','INSTALL.zh-CN.md'),(root/'COPYING','COPYING')]:
    shutil.copy2(source,stage/name)
(stage/'BUILD.json').write_text(json.dumps({'git_commit':revision,
    'build_host':subprocess.check_output(['/usr/bin/sw_vers'],text=True),
    'architecture':platform.machine(),'signing':'ad-hoc; not notarized',
    'hardware_printing_verified':False},indent=2)+'\n')
files=['rastertom1136','M1136.ppd','install-macos.sh','INSTALL.zh-CN.md','COPYING','BUILD.json']
(stage/'SHA256SUMS').write_text(''.join(hashlib.sha256((stage/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in files))
archive=out/'M1136-Mac-Driver-arm64.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for name in files+['SHA256SUMS']: tar.add(stage/name,arcname='M1136-Mac-Driver/'+name)
print(archive)
