#!/usr/bin/env python3
"""Regression cases for stale, dirty and modified validated builds."""
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from provenance import begin, finish, verify


def rejected(fn):
    try:
        fn()
    except (ValueError, FileNotFoundError):
        return
    raise AssertionError('Expected unvalidated/stale build rejection')


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    def git(*args):
        subprocess.run(['git', *args], cwd=root, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)
    git('init')
    git('config', 'user.name', 'Provenance Test')
    git('config', 'user.email', 'test@example.invalid')
    (root / '.gitignore').write_text('build-macos/\n')
    source = root / 'source.c'
    source.write_text('original')
    git('add', '.')
    git('commit', '-m', 'initial')
    build = root / 'build-macos'
    build.mkdir()
    binary = build / 'rastertom1136'
    binary.write_bytes(b'original binary')
    rejected(lambda: verify(root, build))
    begin(root, build); finish(root, build)
    assert not verify(root, build)['source']['git_dirty']
    source.write_text('modified')
    rejected(lambda: verify(root, build))
    # Starting another build invalidates the previous validation immediately.
    begin(root, build)
    rejected(lambda: verify(root, build))
    source.write_text('changed during tests')
    rejected(lambda: finish(root, build))
    begin(root, build); finish(root, build)
    assert verify(root, build)['source']['git_dirty']
    binary.write_bytes(b'tampered binary')
    rejected(lambda: verify(root, build))
    binary.write_bytes(b'original binary')
    git('add', 'source.c'); git('commit', '-m', 'new source commit')
    rejected(lambda: verify(root, build))
    begin(root, build); finish(root, build)
    (root / 'new-header.h').write_text('untracked build input')
    rejected(lambda: verify(root, build))
    (root / 'new-header.h').unlink()
    source.unlink()
    rejected(lambda: verify(root, build))
print('build provenance: stale commit, dirty source, mid-build edits, binary changes, missing validation PASS')
