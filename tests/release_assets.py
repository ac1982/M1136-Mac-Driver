#!/usr/bin/env python3
"""Release publication must reject stale, unaccepted or altered artifacts."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
root=Path(__file__).resolve().parents[1]
version=(root/'VERSION').read_text().strip()
with tempfile.TemporaryDirectory() as directory:
    d=Path(directory)
    package=d/f'M1136-Mac-Driver-{version}-arm64.pkg';package.write_bytes(b'test package')
    source=d/'M1136-Mac-Driver-source.tar.gz'
    with tarfile.open(source,'w:gz') as tar:
        content=(version+'\n').encode();info=tarfile.TarInfo('M1136-Mac-Driver-source/VERSION')
        info.size=len(content);tar.addfile(info,io.BytesIO(content))
    report={'team_id':'89G3DBC6CS','build':{'version':version,'git_dirty':False,'git_commit':'a'*40,
            'signing':{'team_id':'89G3DBC6CS'}},'notarization':'Accepted','stapled':True,
            'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),
            'source_archive_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    env=os.environ.copy();env['GITHUB_SHA']='a'*40
    def check(r,good=False):
        (d/'M1136-Mac-Driver-release.json').write_text(json.dumps(r))
        p=subprocess.run([sys.executable,str(root/'scripts/verify-release.py'),str(d)],env=env,capture_output=True)
        assert (p.returncode==0)==good,p.stderr
    check(report,True)
    for field,value in [('notarization','Invalid'),('stapled',False),('package_sha256','bad'),('source_archive_sha256','bad')]:
        r=copy.deepcopy(report);r[field]=value;check(r)
    for field,value in [('git_dirty',True),('git_commit','b'*40),('version','0.0.0')]:
        r=copy.deepcopy(report);r['build'][field]=value;check(r)
    package.write_bytes(b'changed after notarization');check(report)
print('release asset gates: acceptance, stapling, clean commit, version and hashes PASS')
