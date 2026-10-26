"""Single release version, with a guard against stale PPD metadata."""
from pathlib import Path
import re


def release_version(root):
    version = (Path(root) / 'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('VERSION must contain major.minor.patch')
    ppd = (Path(root) / 'ppd/M1136.ppd').read_text()
    if f'*FileVersion: "{version}"' not in ppd.splitlines():
        raise ValueError('PPD FileVersion must match VERSION')
    return version
