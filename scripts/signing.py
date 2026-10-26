"""Pulse signing configuration; credentials remain in the user's keychain."""
import os
from pathlib import Path
import subprocess

TEAM = '89G3DBC6CS'
ORGANIZATION = 'Pulse (Chongqing) Artificial Intelligence Technology Co., Ltd'
APPLICATION = f'Developer ID Application: {ORGANIZATION} ({TEAM})'
INSTALLER = f'Developer ID Installer: {ORGANIZATION} ({TEAM})'
KEYCHAIN = Path(os.environ.get('M1136_SIGNING_KEYCHAIN',
    Path.home() / 'Library/Application Support/apple-signing' / TEAM / 'pulse-signing.keychain-db'))


def inspect(binary, require_pulse=False):
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(binary)], check=True)
    info = subprocess.run(['/usr/bin/codesign', '-d', '--verbose=4', str(binary)],
                          check=True, capture_output=True, text=True).stderr
    if 'Signature=adhoc' in info:
        if require_pulse:
            raise ValueError('Developer ID build required; run build-macos.sh --developer-id')
        return {'kind': 'ad-hoc', 'team_id': None}
    requirement = (f'anchor apple generic and certificate leaf[subject.OU] = "{TEAM}" '
                   f'and certificate leaf[subject.CN] = "{APPLICATION}"')
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', '-R', '=' + requirement, str(binary)], check=True)
    if '(runtime)' not in info or '\nTimestamp=' not in info:
        raise ValueError('Developer ID build requires hardened runtime and trusted timestamp')
    return {'kind': 'Developer ID Application', 'team_id': TEAM, 'authority': APPLICATION,
            'hardened_runtime': True, 'trusted_timestamp': True}
