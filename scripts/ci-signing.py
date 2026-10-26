#!/usr/bin/env python3
"""Prepare/clean an isolated Actions signing keychain. Never log credentials."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys
import urllib.request


def run(command, label):
    result = subprocess.run(command, capture_output=True)
    if result.returncode:
        # CalledProcessError would expose password-bearing command arguments.
        raise RuntimeError(f'{label} failed (exit {result.returncode})')
    print(label + ' OK', flush=True)
    return result.stdout


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('This helper is for isolated GitHub Actions runners only')
    directory = Path(os.environ['RUNNER_TEMP']) / 'm1136-signing'
    keychain = directory / 'release.keychain-db'
    if sys.argv[1] == 'cleanup':
        saved_search = directory / 'original-search-list.json'
        if saved_search.exists():
            run(['security', 'list-keychains', '-d', 'user', '-s',
                 *json.loads(saved_search.read_text())], 'Restore runner keychain search list')
        if keychain.exists():
            run(['security', 'delete-keychain', str(keychain)], 'Delete temporary keychain')
        if directory.exists():
            shutil.rmtree(directory)
        return
    if sys.argv[1] != 'prepare':
        raise ValueError('Expected prepare or cleanup')
    required = ['APPLE_APPLICATION_P12_BASE64', 'APPLE_INSTALLER_P12_BASE64',
                'APPLE_P12_PASSWORD', 'APPLE_NOTARY_KEY_BASE64',
                'APPLE_NOTARY_KEY_ID', 'APPLE_NOTARY_ISSUER_ID']
    for name in required:
        if not os.environ.get(name):
            raise ValueError('Missing Actions secret: ' + name)
    directory.mkdir(mode=0o700)
    with open(os.environ['GITHUB_ENV'], 'a') as env:
        env.write(f'M1136_SIGNING_KEYCHAIN={keychain}\nM1136_NOTARY_PROFILE=pulse-notary\n')
    original_search = shlex.split(subprocess.check_output(['security', 'list-keychains', '-d', 'user'], text=True))
    (directory / 'original-search-list.json').write_text(json.dumps(original_search))
    password = secrets.token_urlsafe(40)
    run(['security', 'create-keychain', '-p', password, str(keychain)], 'Create temporary keychain')
    run(['security', 'unlock-keychain', '-p', password, str(keychain)], 'Unlock temporary keychain')
    run(['security', 'set-keychain-settings', '-lut', '7200', str(keychain)], 'Set keychain lifetime')
    # codesign's chain discovery also uses the user search list on fresh runners.
    # This is runner-local, and cleanup restores the exact previous list.
    run(['security', 'list-keychains', '-d', 'user', '-s', str(keychain), *original_search],
        'Add temporary keychain to runner search list')
    # These P12 backups contain leaf certificates only. Fresh runners need
    # the matching Apple intermediate; importing it does not override trust.
    certificate = directory / 'DeveloperIDCA.cer'
    with urllib.request.urlopen('https://www.apple.com/certificateauthority/DeveloperIDCA.cer', timeout=30) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != '7afc9d01a62f03a2de9637936d4afe68090d2de18d03f29c88cfb0b1ba63587f':
        raise ValueError('Unexpected Apple Developer ID G1 intermediate certificate')
    certificate.write_bytes(data)
    run(['security', 'import', str(certificate), '-k', str(keychain), '-t', 'cert'], 'Import pinned Apple intermediate')
    for name, secret in [('application.p12' , 'APPLE_APPLICATION_P12_BASE64'),
                         ('installer.p12', 'APPLE_INSTALLER_P12_BASE64'),
                         ('notary.p8', 'APPLE_NOTARY_KEY_BASE64')]:
        path = directory / name
        with path.open('xb') as stream:
            path.chmod(0o600)
            stream.write(base64.b64decode(os.environ[secret], validate=True))
    for name in ['application.p12', 'installer.p12']:
        run(['security', 'import', str(directory / name), '-k', str(keychain),
             '-P', os.environ['APPLE_P12_PASSWORD'], '-T', '/usr/bin/codesign',
             '-T', '/usr/bin/pkgbuild', '-T', '/usr/bin/productsign'], 'Import ' + name)
    run(['security', 'set-key-partition-list', '-S', 'apple-tool:,apple:', '-s', '-k',
         password, str(keychain)], 'Configure Apple signing tools')
    identities = run(['security', 'find-identity', '-v', str(keychain)], 'Validate signing identities')
    for fingerprint in [b'DFDB23B57B981768E409295A450B830831AC8117', b'527D671237915C637E479669553F95E48A21F984']:
        if fingerprint not in identities:
            raise ValueError('Expected Pulse signing identity is not valid in the temporary keychain')
    code_identities = run(['security', 'find-identity', '-v', '-p', 'codesigning', str(keychain)], 'Validate code-signing policy')
    if b'DFDB23B57B981768E409295A450B830831AC8117' not in code_identities:
        raise ValueError('Pulse Application identity does not satisfy code-signing policy')
    probe = directory / 'signing-probe'
    (directory / 'probe.c').write_text('int main(void) { return 0; }\n')
    run(['/usr/bin/clang', str(directory / 'probe.c'), '-o', str(probe)], 'Compile signing probe')
    run(['/usr/bin/codesign', '--force', '--sign', 'DFDB23B57B981768E409295A450B830831AC8117',
         '--keychain', str(keychain), '--options', 'runtime', '--timestamp', str(probe)], 'Sign probe on clean runner')
    run(['/usr/bin/codesign', '--verify', '--strict', str(probe)], 'Verify signing probe')
    probe.unlink()
    (directory / 'probe.c').unlink()
    run(['xcrun', 'notarytool', 'store-credentials'  , 'pulse-notary', '--keychain', str(keychain),
         '--key', str(directory / 'notary.p8'), '--key-id', os.environ['APPLE_NOTARY_KEY_ID'],
         '--issuer', os.environ['APPLE_NOTARY_ISSUER_ID']], 'Validate notary credentials')
    for name in ['application.p12', 'installer.p12', 'notary.p8']:
        (directory / name).unlink()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        raise SystemExit(str(error))
