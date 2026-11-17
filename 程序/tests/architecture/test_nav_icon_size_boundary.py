"""U2: every shipped Fluent navigation PNG uses the 24px icon.nav.size canvas.

No grandfathered files: the PNG IHDR is the authority for the dimensions, and
this gate runs without Pillow in the bundled runtime.
"""
import struct
import unittest
from pathlib import Path

from ui_tokens import NAV_ICON_SIZE
from tests.architecture._scan import ROOT

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
NAV_DIR = ROOT / 'assets' / 'nav'


def png_dimensions(data):
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b'IHDR':
        raise ValueError('invalid PNG header')
    return struct.unpack('>II', data[16:24])


class NavIconSizeBoundaryTests(unittest.TestCase):
    def test_all_nav_icons_use_fixed_canvas(self):
        paths = sorted(NAV_DIR.glob('*.png'))
        self.assertTrue(paths, 'missing assets/nav/*.png')
        dimensions = {path.name: png_dimensions(path.read_bytes()) for path in paths}
        wrong = {name: size for name, size in dimensions.items()
                 if size != (NAV_ICON_SIZE, NAV_ICON_SIZE)}
        self.assertEqual(wrong, {}, 'Fluent PNG must use fixed icon.nav.size canvas')

    def test_png_header_canary(self):
        sample = PNG_SIGNATURE + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 28, 26)
        self.assertEqual(png_dimensions(sample), (28, 26))
        self.assertNotEqual(png_dimensions(sample), (NAV_ICON_SIZE, NAV_ICON_SIZE))
        with self.assertRaises(ValueError):
            png_dimensions(b'not a PNG')


if __name__ == '__main__':
    unittest.main()
