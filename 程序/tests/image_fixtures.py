"""Small real PNG fixtures using only the shipped standard library."""
import struct
import zlib


def png(size=(16, 9), color='red'):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    width, height = size
    rgb = b'\xff\x00\x00' if color == 'red' else b'\x00\x00\xff'
    data = (b'\x00' + rgb * width) * height
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(data)) + chunk(b'IEND', b''))
