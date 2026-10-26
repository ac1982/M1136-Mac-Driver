#!/usr/bin/env python3
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_version import release_version
root=Path(__file__).resolve().parents[1]
assert release_version(root)==(root/'VERSION').read_text().strip()
with tempfile.TemporaryDirectory() as directory:
    d=Path(directory);(d/'ppd').mkdir()
    for version,ppd,accepted in [('1.0.0','1.0.0',True),('1.0.0','0.1',False),('invalid','invalid',False)]:
        (d/'VERSION').write_text(version)
        (d/'ppd/M1136.ppd').write_text(f'*FileVersion: "{ppd}"\n')
        try:release_version(d)
        except ValueError:assert not accepted
        else:assert accepted
print('release version and PPD consistency PASS')
