#!/usr/bin/env python3
"""Check the release filter's direct linked symbols; not a whole-system audit."""
import re
import subprocess
import sys
from pathlib import Path
binary = str(Path(sys.argv[1]).resolve())
symbols = subprocess.check_output(['nm', binary], text=True)
for name in ['jbg_dec', 'jbg_newlen', 'system', 'popen', 'execve', 'socket', 'tmpfile']:
    pattern = r'\b_?' + re.escape(name) + (r'\w*\b' if name.startswith('jbg_') else r'\b')
    if re.search(pattern, symbols):
        raise SystemExit('Forbidden linked symbol: ' + name)
print('Release filter: decoder/process/network/tempfile symbols absent')
