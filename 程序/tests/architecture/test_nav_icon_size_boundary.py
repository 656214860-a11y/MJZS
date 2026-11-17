"""U2: main navigation PNGs use the 24px icon.nav.size canvas.

M3 stage-file composites intentionally keep their cropped canvas. The icon
registry defines the main-navigation set; PNG IHDR is the dimension authority.
"""
import struct
import unittest
from pathlib import Path

from ui_tokens import NAV_ICON_SIZE
from scripts.build_nav_icons import ICONS, STAGE_FILE_BASES
from tests.architecture._scan import ROOT

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
NAV_DIR = ROOT / 'assets' / 'nav'


def png_dimensions(data):
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b'IHDR':
        raise ValueError('invalid PNG header')
    return struct.unpack('>II', data[16:24])


class NavIconSizeBoundaryTests(unittest.TestCase):
    def test_main_nav_icons_use_fixed_canvas(self):
        expected = {f'{key}.png' for key in ICONS}
        composites = {f'{key}_files.png' for key in STAGE_FILE_BASES}
        paths = sorted(NAV_DIR.glob('*.png'))
        names = {path.name for path in paths}
        self.assertEqual(names, expected | composites, 'unregistered navigation PNG')
        dimensions = {path.name: png_dimensions(path.read_bytes()) for path in paths}
        wrong = {name: dimensions[name] for name in expected
                 if dimensions[name] != (NAV_ICON_SIZE, NAV_ICON_SIZE)}
        self.assertEqual(wrong, {}, 'main Fluent PNG must use fixed icon.nav.size canvas')

    def test_png_header_canary(self):
        sample = PNG_SIGNATURE + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 28, 26)
        self.assertEqual(png_dimensions(sample), (28, 26))
        self.assertNotEqual(png_dimensions(sample), (NAV_ICON_SIZE, NAV_ICON_SIZE))
        with self.assertRaises(ValueError):
            png_dimensions(b'not a PNG')


if __name__ == '__main__':
    unittest.main()
