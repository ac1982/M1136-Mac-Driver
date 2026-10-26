#!/usr/bin/env python3
"""Exercise Apple's PDF renderer, including its expansion of collated copies."""
import hashlib
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from xqx import page_copies, page_items

root = Path(__file__).resolve().parents[1]


def pdf(width, height, pages=1):
    kids = ' '.join(f'{3 + 2*i} 0 R' for i in range(pages))
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               f'<< /Type /Pages /Kids [{kids}] /Count {pages} >>'.encode()]
    for i in range(pages):
        content = (f'0 g {24 + 30*i} 24 120 120 re f\n'
                   '0.5 g 180 24 120 120 re f\n'
                   '0 G 1 w 24 200 m 500 200 l S\n').encode()
        objects.extend([
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << >> /Contents {4 + 2*i} 0 R >>'.encode(),
            b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'endstream'])
    data = bytearray(b'%PDF-1.4\n')
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(data)
    data += f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    for offset in offsets:
        data += f'{offset:010d} 00000 n \n'.encode()
    data += f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return data


def raster_pages(data):
    # Uncompressed CUPS wire headers, independent of the production parser.
    endian, size = {b'3SaR': ('<', 1796), b'RaS3': ('>', 1796),
                    b'tSaR': ('<', 420), b'RaSt': ('>', 420)}[data[:4]]
    pos = 4
    pages = []
    while pos < len(data):
        assert pos + size <= len(data)
        copies = struct.unpack_from(endian + 'I', data, pos + 340)[0]
        height = struct.unpack_from(endian + 'I', data, pos + 376)[0]
        stride = struct.unpack_from(endian + 'I', data, pos + 392)[0]
        pos += size
        end = pos + height * stride
        assert pos < end <= len(data)
        pages.append((copies, hashlib.sha256(data[pos:end]).digest()))
        pos = end
    return pages


with tempfile.TemporaryDirectory(prefix='m1136-pipeline-') as directory:
    source = Path(directory) / 'test.pdf'
    for paper, width, height in [('A4', 595, 842), ('Letter', 612, 792)]:
        for pages, copies, collate in [(1, 1, False), (1, 3, True),
                                       (2, 3, True), (1, 3, False), (2, 3, False)]:
            label = f'{paper} pages={pages} copies={copies} Collate={collate}'
            source.write_bytes(pdf(width, height, pages))
            rendered = subprocess.run([
                '/usr/sbin/cupsfilter', '-p', str(root / 'ppd/M1136.ppd'),
                '-m', 'application/vnd.cups-raster', '-n', str(copies),
                '-o', 'PageSize=' + paper, '-o', 'Collate=' + str(collate), str(source)
            ], capture_output=True, timeout=60)
            assert rendered.returncode == 0, (label, rendered.stderr)
            metadata = raster_pages(rendered.stdout)
            expected = [n for n, _ in metadata]
            assert sum(expected) == pages * copies, (label, expected)
            if collate:
                assert expected == [1] * (pages * copies), (label, expected)
                hashes = [digest for _, digest in metadata]
                assert hashes == hashes[:pages] * copies, label
                if pages > 1:
                    assert hashes[0] != hashes[1], 'Test pages must differ'
            result = subprocess.run([
                sys.argv[1], '1', 'test', 'calibration', str(copies), ''
            ], input=rendered.stdout, capture_output=True, timeout=60)
            assert result.returncode == 0, (label, result.stderr)
            actual = page_copies(result.stdout)
            assert actual == expected, (label, expected, actual)
            accounting = [line for line in result.stderr.decode().splitlines() if line.startswith('PAGE:')]
            assert accounting == [f'PAGE: {i} {n}' for i, n in enumerate(expected, 1)], (label, accounting)
            print(label, 'Apple PDF -> raster -> XQX PASS', actual, 'sheets:', sum(actual))

    for paper, width, height in [('A4',595,842),('Letter',612,792)]:
        for pages in [3,4]:
            source.write_bytes(pdf(width,height,pages))
            for mode in ['LongEdge','ShortEdge']:
                option='M1136ManualDuplex='+mode
                rendered=subprocess.run([
                    '/usr/sbin/cupsfilter','-p',str(root/'ppd/M1136.ppd'),
                    '-m','application/vnd.cups-raster','-o','PageSize='+paper,
                    '-o',option,str(source)],capture_output=True,timeout=60)
                assert rendered.returncode==0,rendered.stderr
                assert len(raster_pages(rendered.stdout))==pages
                result=subprocess.run([sys.argv[1],'1','test','manual duplex','1',option],
                    input=rendered.stdout,capture_output=True,timeout=60)
                assert result.returncode==0,result.stderr
                items=page_items(result.stdout)
                assert len(items)==4
                assert [p[0x20000012] for p in items]==[0,1,2,3]
                assert page_copies(result.stdout)==[1,1,1,1]
                print(paper,pages,mode,'Apple PDF -> manual duplex PASS')
