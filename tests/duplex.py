#!/usr/bin/env python3
"""Decode actual JBIG pixels; verify sheet pairs, rotation, padding and pauses."""
import resource
import os
from pathlib import Path
import random
import select
import signal
import struct
import time
import subprocess
import sys
import tempfile
from xqx import page_items

binary, fixture, decoder = sys.argv[1:]

def run(data, mode='ShortEdge', copies='1', ok=True):
    p = subprocess.run([binary, '1', 'u', 't', copies,
                        'M1136ManualDuplex=' + mode], input=data,
                       capture_output=True, timeout=30)
    assert (p.returncode == 0) == ok, p.stderr
    if not ok:
        assert not p.stdout, 'Rejected duplex jobs must not partially print'
    return p

def images(data):
    pos = data.index(b',XQX') + 4
    result = []
    bie = bytearray()
    while True:
        kind, count = struct.unpack_from('>II', data, pos)
        pos += 8
        if kind == 7:
            bie += data[pos:pos+count]
            pos += count
        else:
            for _ in range(count):
                key, n = struct.unpack_from('>II', data, pos)
                pos += 8
                if key == 0x40000002:
                    bie += data[pos:pos+n]
                pos += n
        if kind == 4:
            decoded = subprocess.check_output([decoder], input=bie)
            shape, bits = decoded.split(b'\n', 1)
            w, h = map(int, shape.split())
            assert len(bits) == w//8*h
            result.append([[bool(bits[y*(w//8)+x//8] & (128 >> (x%8)))
                            for x in range(w)] for y in range(h)])
            bie.clear()
        if kind == 2:
            return result

for count in [1, 2, 3, 4, 199, 200]:
    data = subprocess.check_output([fixture, 'duplex'+str(count)])
    for mode in ['ShortEdge', 'LongEdge']:
        result = run(data, mode)
        items = page_items(result.stdout)
        total = count + count%2
        assert len(items) == total
        assert [p[0x20000012] for p in items] == [0]+[1]*(total//2-1)+[2]+[3]*(total//2-1)
        assert all(p[0x20000005] == 1 and p[0x80000000] == 192 for p in items)
        # Small asymmetric pages exercise visible width 129 vs JBIG width 256.
        if count <= 4:
            decoded = images(result.stdout)
            order = list(range(0,total,2)) + list(range(total-1,0,-2))
            bayer = [[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]]
            for page, index in zip(decoded,order):
                expected = [[index < count and (x+y+index)%256 < 8+16*bayer[y%4][x%4]
                             for x in range(129)] for y in range(32)]
                if mode == 'LongEdge' and index%2:
                    expected = [row[::-1] for row in expected[::-1]]
                assert page == [row+[False]*127 for row in expected], (count,mode,index)
        print(count,mode,'pairing/pause/pixels PASS')

for case in ['duplex201', 'uncollated', 'mixedpaper', 'mixedsize', 'truncated', 'duplex']:
    run(subprocess.check_output([fixture,case]),ok=False)
valid = subprocess.check_output([fixture,'multi'])
run(valid,copies='2',ok=False)
run(valid,mode='invalid',ok=False)
run(valid[:-1],ok=False)
run(valid+b'bad next header',ok=False)
print('Invalid duplex input rejected before output PASS')

# A full spool must fail before a single byte is sent to the device.
def no_disk():
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    signal.signal(signal.SIGXFSZ,signal.SIG_IGN)
p=subprocess.run([binary,'1','u','t','1','M1136ManualDuplex=LongEdge'],
    input=valid,capture_output=True,timeout=10,preexec_fn=no_disk)
assert p.returncode!=0 and not p.stdout,(p.returncode,p.stderr)
# Cancellation while waiting for the next raster page must close the private spool.
p=subprocess.Popen([binary,'1','u','t','1','M1136ManualDuplex=LongEdge'],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
    first=subprocess.check_output([fixture,'valid'])
    p.stdin.write(first)
    p.stdin.flush()
    time.sleep(.1)
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=5)
    assert p.returncode==1 and not p.stdout.read()
finally:
    if p.poll() is None: p.kill();p.wait()
    p.stdin.close();p.stdout.close();p.stderr.close()
print('Spool I/O failure and cancellation before output PASS')

# Exercise the real filter process after it has entered front/back replay.
# Enough noisy output remains to block the consumer pipe at either point.
header=bytearray(valid[:1800])
for offset,value in [(372,2049),(376,1024),(392,2049)]:
    struct.pack_into('=I',header,4+offset,value)
rng=random.Random(1136)
noise=header[:4]+b''.join(header[4:]+rng.randbytes(2049*1024) for _ in range(2))
baseline=run(noise,'LongEdge').stdout
positions=[]
pos=baseline.index(b',XQX')+4
while True:
    kind,count=struct.unpack_from('>II',baseline,pos)
    if kind==3: positions.append(pos)
    pos+=8
    if kind==7:
        pos+=count
    else:
        for _ in range(count):
            _,length=struct.unpack_from('>II',baseline,pos)
            pos+=8+length
    if kind==2: break
assert len(positions)==2
with tempfile.TemporaryDirectory(prefix='m1136-cancel-') as directory:
    d=Path(directory);source=d/'input.ras';source.write_bytes(noise)
    env=dict(os.environ,TMPDIR=directory)
    for side,offset in enumerate(positions,1):
        for action in ['SIGTERM','broken-pipe']:
            target=offset+4096
            assert len(baseline)-target>65536
            p=subprocess.Popen([binary,'1','u','t','1','M1136ManualDuplex=LongEdge',str(source)],
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
            try:
                # A visible page prefix proves preparation has finished; no timing guess.
                prefix=bytearray();deadline=time.monotonic()+10
                while len(prefix)<target:
                    left=deadline-time.monotonic()
                    assert left>0 and select.select([p.stdout],[],[],left)[0]
                    chunk=os.read(p.stdout.fileno(),min(65536,target-len(prefix)))
                    assert chunk,'Filter exited before the requested replay phase'
                    prefix+=chunk
                assert p.poll() is None
                start=time.monotonic()
                if action=='SIGTERM': p.send_signal(signal.SIGTERM)
                else: p.stdout.close()
                p.wait(timeout=5)
                elapsed=time.monotonic()-start
                assert p.returncode==1,(side,action,p.returncode,p.stderr.read())
                if action=='SIGTERM':
                    output=prefix+p.stdout.read()
                    assert b'@PJL EOJ' not in output
                errors=p.stderr.read()
                assert b'AddressSanitizer' not in errors and b'runtime error:' not in errors,errors
                assert set(d.iterdir())=={source},'Named temporary spool left behind'
                print('Replay side',side,action,'exit and cleanup PASS',round(elapsed,3),'seconds')
            finally:
                if p.poll() is None: p.kill();p.wait()
                p.stdout.close();p.stderr.close()
    recovered=subprocess.run([binary,'1','u','t','1','M1136ManualDuplex=LongEdge',str(source)],
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=30)
    assert recovered.returncode==0,recovered.stderr
    assert len(page_items(recovered.stdout))==2
    assert set(d.iterdir())=={source}
    print('Fresh filter job succeeds after cancellations; no named spool residue PASS')
