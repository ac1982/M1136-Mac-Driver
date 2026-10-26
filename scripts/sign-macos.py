#!/usr/bin/env python3
"""Sign a release filter with the existing Pulse Developer ID identity."""
import os
import subprocess
import sys
from signing import KEYCHAIN, inspect

# Pin the reviewed Pulse certificate; override explicitly when renewing it.
identity = os.environ.get('M1136_APPLICATION_IDENTITY', 'DFDB23B57B981768E409295A450B830831AC8117')
subprocess.run(['/usr/bin/codesign', '--force', '--sign', identity,
                '--keychain', str(KEYCHAIN), '--options', 'runtime', '--timestamp',
                '--identifier', 'com.pulse.m1136.rastertom1136', sys.argv[1]], check=True)
inspect(sys.argv[1], require_pulse=True)
