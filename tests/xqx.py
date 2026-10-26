"""Read per-page XQX items independently of the C serializer."""
import struct


def page_items(data):
    pos = data.index(b',XQX') + 4
    pages = []
    while True:
        kind, count = struct.unpack_from('>II', data, pos)
        pos += 8
        assert 1 <= kind <= 7
        items = {}
        if kind == 7:
            pos += count
        else:
            for _ in range(count):
                key, length = struct.unpack_from('>II', data, pos)
                pos += 8
                assert pos + length <= len(data)
                if length == 4:
                    items[key] = struct.unpack_from('>I', data, pos)[0]
                pos += length
        assert pos <= len(data)
        if kind == 3:
            pages.append(items)
        if kind == 2:
            break
    assert data[pos:] == b'\x1b%-12345X@PJL EOJ\n\x1b%-12345X'
    return pages


def page_copies(data):
    return [page[0x20000005] for page in page_items(data)]
