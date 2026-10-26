#!/usr/bin/env python3
import os
from pathlib import Path
import random
import signal
import struct
import subprocess
import sys
import tempfile
import time
from xqx import page_items, page_copies

binary, fixture = map(str, map(Path, sys.argv[1:3]))
def run(data, copies='1', path=None, ok=False):
    cmd=[binary,'1','untrusted user','title @PJL EOJ',copies,'arbitrary options']
    if path is not None: cmd.append(str(path))
    p=subprocess.run(cmd,input=data,capture_output=True,timeout=30)
    assert (p.returncode==0)==ok, (cmd,p.returncode,p.stderr)
    assert b'AddressSanitizer' not in p.stderr and b'runtime error:' not in p.stderr,p.stderr
    assert b'untrusted' not in p.stdout and b'arbitrary' not in p.stdout
    return p

def page_count(data):
    return len(page_items(data))

valid=None
for case in ['valid','a4','letter','max','multi','limit']:
    data=subprocess.check_output([fixture,case],timeout=30)
    p=run(data,ok=True)
    assert page_count(p.stdout)==({'multi':3,'limit':500}.get(case,1))
    if case=='valid': valid=data
    print(case,'PASS')
for case in ['width','height','stride','color','duplex','tumble','dpi','paper','bits','truncated','overlimit']:
    data=subprocess.check_output([fixture,case],timeout=30)
    run(data)
    print(case,'rejected')
# Raster metadata is authoritative even when argv[4] still requests 3 copies.
for case, expected in [('collated',[1,1,1]), ('uncollated',[3]),
                       ('mixedcopies',[1,2,3]), ('copies99',[99])]:
    data=subprocess.check_output([fixture,case],timeout=30)
    p=run(data,copies='3',ok=True)
    assert page_copies(p.stdout)==expected,(case,page_copies(p.stdout))
    accounting=[line for line in p.stderr.decode().splitlines() if line.startswith('PAGE:')]
    assert accounting==[f'PAGE: {i} {n}' for i,n in enumerate(expected,1)],accounting
    print(case,'copies and accounting PASS',expected)
for case in ['copies0','copies100','copiesoverflow']:
    assert not run(subprocess.check_output([fixture,case])).stdout
for copies in ['0','100','-1','+1',' 1','1 ','1;touch /tmp/no','999999999999999999999999','']:
    assert not run(valid,copies).stdout
for copies in ['1','99']:
    assert page_count(run(valid,copies,ok=True).stdout)==1
for data in [b'',b'not raster',valid[:3],valid[:50],valid[:-1],valid+b'broken next header']:
    run(data)
# Both endian variants and legacy v1 framing must decode to the same stream.
v1=(0x52615374).to_bytes(4,sys.byteorder)+valid[4:424]+valid[1800:]
assert page_count(run(v1,ok=True).stdout)==1
swapped=bytearray(valid)
swapped[:4]=swapped[:4][::-1]
for offset in range(4+256,4+580,4): swapped[offset:offset+4]=swapped[offset:offset+4][::-1]
assert page_count(run(bytes(swapped),ok=True).stdout)==1
for offset in [372,376,392]:
    malformed=bytearray(valid)
    malformed[4+offset:8+offset]=(0xffffffff).to_bytes(4,sys.byteorder)
    assert not run(bytes(malformed)).stdout
# Compressed raster containers are deliberately outside this version's input contract.
run((0x52615332).to_bytes(4,sys.byteorder)+valid[4:])
with tempfile.TemporaryDirectory() as d:
    d=Path(d); path=d/'input.ras'; path.write_bytes(valid)
    run(None,path=path,ok=True)
    link=d/'link'; link.symlink_to(path); run(None,path=link)
    fifo=d/'fifo'; os.mkfifo(fifo); run(None,path=fifo)
    run(None,path=d); run(None,path=d/'missing')
    # Closed output pipe must be a handled nonzero exit, not SIGPIPE.
    read_fd,write_fd=os.pipe();os.close(read_fd)
    p=subprocess.run([binary,'1','u','t','1','',str(path)],stdout=write_fd,stderr=subprocess.PIPE,timeout=10)
    os.close(write_fd)
    assert p.returncode==1,p
    # Cancellation while blocked reading the remaining input.
    p=subprocess.Popen([binary,'1','u','t','1',''],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    p.stdin.write(valid[:100]);p.stdin.flush()
    time.sleep(.1);p.send_signal(signal.SIGTERM)
    p.wait(timeout=5)
    p.stdin.close()
    assert p.returncode==1,p.returncode
    p.stdout.close();p.stderr.close()
    # A live but non-draining output consumer must not prevent cancellation.
    read_fd,write_fd=os.pipe()
    import fcntl
    original_flags=fcntl.fcntl(write_fd,fcntl.F_GETFL)
    fcntl.fcntl(write_fd,fcntl.F_SETFL,original_flags|os.O_NONBLOCK)
    try:
        while True: os.write(write_fd,b'x'*4096)
    except BlockingIOError:
        pass
    fcntl.fcntl(write_fd,fcntl.F_SETFL,original_flags)
    original_flags=fcntl.fcntl(write_fd,fcntl.F_GETFL)
    p=subprocess.Popen([binary,'1','u','t','1','',str(path)],stdout=write_fd,stderr=subprocess.PIPE)
    try:
        time.sleep(.1);p.send_signal(signal.SIGTERM)
        p.wait(timeout=5)
        assert p.returncode==1,p.returncode
        assert fcntl.fcntl(write_fd,fcntl.F_GETFL)==original_flags
    finally:
        if p.poll() is None: p.kill();p.wait()
        os.close(read_fd);os.close(write_fd);p.stderr.close()
randomizer=random.Random(1136)
for _ in range(60):
    # Invalid magic: ensure fast rejection without trusting random size fields.
    data=b'BAD!'+randomizer.randbytes(randomizer.randrange(0,2048))
    run(data)
print('filter: argument, stream, file, cancellation, pipe and malformed-input tests PASS')
