#!/usr/bin/env python3
"""Prepare a signed PKG; optionally notarize/staple it. Never install or print."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from provenance import verify, digest
from signing import KEYCHAIN, INSTALLER, TEAM, inspect
from release_version import release_version

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--notarize', action='store_true', help='Upload the driver PKG to Apple and wait for acceptance')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
version = release_version(root)
manifest = verify(root, root / 'build-macos')
inspect(root / 'build-macos/rastertom1136', require_pulse=True)
subprocess.run([sys.executable, str(root / 'scripts/package-macos.py')], check=True)
out = root / 'build-package'
stage = out / 'M1136-Mac-Driver'
package = out / f'M1136-Mac-Driver-{version}-arm64.pkg'
report_path = out / 'M1136-Mac-Driver-release.json'
checksum_path = out / f'M1136-Mac-Driver-{version}-arm64.pkg.sha256'
# Invalidate prior acceptance/checksum before replacing a release.
report_path.unlink(missing_ok=True)
checksum_path.unlink(missing_ok=True)
with tempfile.TemporaryDirectory(prefix='m1136-payload-') as directory:
    payload = Path(directory)
    payload.chmod(0o755)
    for name, mode in [('rastertom1136', 0o755), ('M1136.ppd', 0o644)]:
        shutil.copy2(stage / name, payload / name)
        (payload / name).chmod(mode)
        expected = (manifest['binary_sha256'] if name == 'rastertom1136' else
                    manifest['source']['files']['ppd/M1136.ppd']['sha256'])
        if digest(payload / name) != expected:
            raise SystemExit('Payload differs from validated source/build: ' + name)
    subprocess.run(['/usr/bin/pkgbuild', '--root', str(payload),
        '--identifier', 'com.pulse.m1136.driver', '--version', version,
        '--install-location', '/Library/Printers/M1136MacDriver',
        '--ownership', 'recommended', '--sign', INSTALLER, '--keychain', str(KEYCHAIN),
        '--timestamp', str(package)], check=True)
subprocess.run(['/usr/sbin/pkgutil', '--check-signature', str(package)], check=True)
# Supply the exact source snapshot, including local changes, with this GPL build.
source_archive = out / 'M1136-Mac-Driver-source.tar.gz'
verify(root, root / 'build-macos')
with tarfile.open(source_archive, 'w:gz') as tar:
    for name, entry in manifest['source']['files'].items():
        if not entry.get('missing'):
            tar.add(root / name, arcname='M1136-Mac-Driver-source/' + name, recursive=False)
verify(root, root / 'build-macos')
report = {'team_id': TEAM, 'build': json.loads((stage / 'BUILD.json').read_text()),
          'notarization': 'not submitted', 'source_archive_sha256': digest(source_archive)}
if args.notarize:
    profile = os.environ.get('M1136_NOTARY_PROFILE', 'pulse-notary')
    auth = ['--keychain-profile', profile, '--keychain', str(KEYCHAIN)]
    submitted = json.loads(subprocess.check_output(['xcrun', 'notarytool', 'submit', str(package),
                            *auth, '--output-format', 'json']))
    submission = submitted['id']
    report['submission_id'] = submission
    report['notarization'] = 'submitted'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('Notary submission:', submission, flush=True)
    subprocess.run(['xcrun', 'notarytool', 'wait', submission, *auth], check=True)
    status = json.loads(subprocess.check_output(['xcrun', 'notarytool', 'info', submission,
                        *auth, '--output-format', 'json']))
    report['notarization'] = status['status']
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    if status['status'] != 'Accepted':
        raise SystemExit('Apple did not accept this package; inspect the notary submission log')
    subprocess.run(['xcrun', 'stapler', 'staple', str(package)], check=True)
    subprocess.run(['xcrun', 'stapler', 'validate', str(package)], check=True)
    subprocess.run(['/usr/sbin/spctl', '--assess', '--type', 'install', '--verbose=2', str(package)], check=True)
    report['stapled'] = True
report['package_sha256'] = digest(package)
report_path.write_text(json.dumps(report, indent=2) + '\n')
checksum_path.write_text(report['package_sha256'] + '  ' + package.name + '\n')
print(package)
