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
    pos=data.index(b',XQX')+4
    pages=0
    while True:
        kind,count=struct.unpack_from('>II',data,pos);pos+=8
        assert 1<=kind<=7
        if kind==7: pos+=count
        else:
            for _ in range(count):
                key,n=struct.unpack_from('>II',data,pos);pos+=8+n
        assert pos<=len(data)
        if kind==3: pages+=1
        if kind==2: break
    assert data[pos:]==b'\x1b%-12345X@PJL EOJ\n\x1b%-12345X'
    return pages

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
randomizer=random.Random(1136)
for _ in range(60):
    # Invalid magic: ensure fast rejection without trusting random size fields.
    data=b'BAD!'+randomizer.randbytes(randomizer.randrange(0,2048))
    run(data)
print('filter: argument, stream, file, cancellation, pipe and malformed-input tests PASS')
