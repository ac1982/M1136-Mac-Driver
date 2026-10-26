#!/usr/bin/env python3
"""Bind successful local validation to exact source bytes and signed binary."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root)
    names = set(git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split(b'\0')) - {b''}
    files = {}
    for raw in sorted(names):
        name = os.fsdecode(raw)
        path = root / name
        if path.is_symlink():
            files[name] = {'symlink': os.readlink(path)}
        elif path.is_file():
            files[name] = {'sha256': digest(path), 'executable': bool(path.stat().st_mode & 0o111)}
        else:
            files[name] = {'missing': True}
    return {'git_commit': git('rev-parse', 'HEAD').decode().strip(),
            'git_dirty': bool(git('status', '--porcelain', '--untracked-files=normal')),
            'files': files}


def begin(root, build):
    build.mkdir(exist_ok=True)
    (build / 'validated-build.json').unlink(missing_ok=True)
    (build / 'source-start.json').write_text(json.dumps(snapshot(root), sort_keys=True))


def finish(root, build):
    source = json.loads((build / 'source-start.json').read_text())
    if snapshot(root) != source:
        raise ValueError('Source changed during build/tests; rebuild before packaging')
    manifest = {'schema': 1, 'source': source,
                'binary_sha256': digest(build / 'rastertom1136')}
    (build / 'validated-build.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


def verify(root, build):
    manifest = json.loads((build / 'validated-build.json').read_text())
    if manifest['schema'] != 1 or snapshot(root) != manifest['source']:
        raise ValueError('Source differs from validated build; run scripts/build-macos.sh again')
    if digest(build / 'rastertom1136') != manifest['binary_sha256']:
        raise ValueError('Binary differs from validated build; rebuild before packaging')
    return manifest


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    build = root / 'build-macos'
    try:
        {'begin': begin, 'finish': finish, 'verify': verify}[sys.argv[1]](root, build)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
