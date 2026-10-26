#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1] / 'vendor/jbigkit'
manifest = json.loads((root / 'SOURCE.json').read_text())
for name, expected in manifest['files'].items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
        raise SystemExit('JBIG-KIT source mismatch: ' + name)
print('JBIG-KIT ' + manifest['version'] + ': pinned source hashes verified')
