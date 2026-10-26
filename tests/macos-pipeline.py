#!/usr/bin/env python3
"""Generate a non-sensitive PDF; exercise Apple's real PDF -> raster -> XQX path."""
import subprocess
import sys
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
# Minimal vector PDF with known dimensions and gray/black calibration shapes.
def pdf(width,height):
    content=b'0 g 24 24 120 120 re f\n0.5 g 180 24 120 120 re f\n0 G 1 w 24 200 m 500 200 l S\n'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
             b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << >> /Contents 4 0 R >>'.encode(),
             b'<< /Length '+str(len(content)).encode()+b' >>\nstream\n'+content+b'endstream']
    data=bytearray(b'%PDF-1.4\n'); offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data);data+=b'xref\n0 5\n0000000000 65535 f \n'
    for offset in offsets[1:]: data+=f'{offset:010d} 00000 n \n'.encode()
    data+=f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return data
with tempfile.TemporaryDirectory(prefix='m1136-pipeline-') as d:
    d=Path(d)
    for paper,w,h in [('A4',595,842),('Letter',612,792)]:
        source=d/'test.pdf';source.write_bytes(pdf(w,h))
        rendered=subprocess.run(['/usr/sbin/cupsfilter','-p',str(root/'ppd/M1136.ppd'),
            '-m','application/vnd.cups-raster','-o','PageSize='+paper,str(source)],capture_output=True,timeout=60)
        if rendered.returncode: raise SystemExit(rendered.stderr.decode(errors='replace'))
        result=subprocess.run([sys.argv[1],'1','test','calibration','1',''],input=rendered.stdout,capture_output=True,timeout=60)
        assert result.returncode==0,result.stderr
        assert b',XQX' in result.stdout and b'@PJL EOJ' in result.stdout
        print(paper,'Apple PDF -> raster -> XQX PASS',len(result.stdout),'bytes')
