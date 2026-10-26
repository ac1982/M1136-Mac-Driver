#!/usr/bin/env python3
"""Prepare/clean an isolated Actions signing keychain. Never log credentials."""
import base64
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys


def run(command, label):
    result = subprocess.run(command, capture_output=True)
    if result.returncode:
        # CalledProcessError would expose password-bearing command arguments.
        raise RuntimeError(f'{label} failed (exit {result.returncode})')
    print(label + ' OK', flush=True)


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('This helper is for isolated GitHub Actions runners only')
    directory = Path(os.environ['RUNNER_TEMP']) / 'm1136-signing'
    keychain = directory / 'release.keychain-db'
    if sys.argv[1] == 'cleanup':
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
    password = secrets.token_urlsafe(40)
    run(['security', 'create-keychain', '-p', password, str(keychain)], 'Create temporary keychain')
    run(['security', 'unlock-keychain', '-p', password, str(keychain)], 'Unlock temporary keychain')
    run(['security', 'set-keychain-settings', '-lut', '7200', str(keychain)], 'Set keychain lifetime')
    for name, secret in [('application.p12', 'APPLE_APPLICATION_P12_BASE64'),
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
    run(['xcrun', 'notarytool', 'store-credentials', 'pulse-notary', '--keychain', str(keychain),
         '--key', str(directory / 'notary.p8'), '--key-id', os.environ['APPLE_NOTARY_KEY_ID'],
         '--issuer', os.environ['APPLE_NOTARY_ISSUER_ID']], 'Validate notary credentials')
    for name in ['application.p12', 'installer.p12', 'notary.p8']:
        (directory / name).unlink()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        raise SystemExit(str(error))
