# -*- coding: utf-8 -*-
"""第 49 期：安装后那个图标——纯标准库算出 .ico（自带解释器没有 PIL）。运行：python test_app_icon.py

第 49 期第 2 条把图标整个重画了（方块画布、平涂的虎皮橙、粗墨轮廓、三道额纹、右上角一颗 ✦）：
用例盯住「画布是方的」、「剪影外是透的」、「耳朵顶出来」、「颜色鲜艳且平涂」、「极简／七笔」，
以及 .ico 目录里的宽高照旧各写各的。
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import app_icon

SMALL = (32, 32)                      # 用例里只用小尺寸：渲染一档要跑一遍超采样，省时间


def ihdr(blob):
    """读 PNG 的 (宽, 高)。"""
    return struct.unpack('>II', blob[16:24])


class PixelTests(unittest.TestCase):
    def test_pixels_are_as_wide_as_tall_as_asked(self):
        pixels = app_icon.cat_pixels((64, 64))
        self.assertEqual(len(pixels), 64, '行数＝高')
        for row in pixels:
            self.assertEqual(len(row), 64, '列数＝宽')
            for pixel in row:
                self.assertEqual(len(pixel), 4)
                self.assertTrue(all(0 <= value <= 255 for value in pixel))

    def test_the_canvas_is_square(self):
        """第 49 期第 2 条：桌面图标改成方块画布——宽图放上桌面会被缩成一条，白扔三分之一面积。"""
        self.assertEqual(app_icon.ASPECT, 1.0)
        for size in app_icon.SIZES:
            with self.subTest(size=size):
                self.assertEqual(len(size), 2)
                self.assertEqual(size[0], size[1], '每一档都是方的')

    def test_every_size_is_at_least_sixteen(self):
        for size in app_icon.SIZES:
            self.assertGreaterEqual(min(size), 16, str(size))
    def test_outside_the_silhouette_is_transparent(self):
        pixels = app_icon.cat_pixels(SMALL)
        self.assertEqual(pixels[0][0][3], 0, '左上角是空的（剪影贴着底边站）')
        self.assertEqual(pixels[0][-1][3], 0, '右上角也是空的')

    def test_the_ears_stick_up_above_the_face(self):
        width, height = SMALL
        pixels = app_icon.cat_pixels(SMALL)
        ear_row = int(height * 0.16)
        self.assertTrue([x for x in range(width) if pixels[ear_row][x][3] > 0], '耳朵尖要露出来')
        face_row = int(height * 0.55)
        body = [x for x in range(width) if pixels[face_row][x][3] > 0]
        self.assertTrue(body, '脸上要有肉')
        self.assertNotEqual(tuple(pixels[int(height * 0.55)][body[len(body) // 2]][:3]),
                            tuple(app_icon.CLEAR[:3]))

    def test_the_face_reads_as_a_cat_not_a_blob(self):
        """轮廓里得有墨（描边／眼睛／鼻子）——一整块纯色就不像猫了。"""
        pixels = app_icon.cat_pixels((96, 96))
        ink = sum(1 for row in pixels for pixel in row if tuple(pixel[:3]) == tuple(app_icon.INK[:3]))
        self.assertGreater(ink, 60, '深墨描边＋五官的总量')

    def test_every_shipped_size_can_be_rendered(self):
        for size in app_icon.SIZES[:3]:
            with self.subTest(size=size):
                width, height = size
                pixels = app_icon.cat_pixels(size)
                self.assertEqual((len(pixels[0]), len(pixels)), (width, height))

    def test_a_single_number_means_a_square_canvas(self):
        self.assertEqual(app_icon.pair(16), (16, 16))
        self.assertEqual(app_icon.pair((16, 10)), (16, 10))

    def test_a_zero_size_request_is_refused_not_crashed(self):
        for bad in (0, (0, 10), (10, 0), -4):
            with self.subTest(bad=bad):
                with self.assertRaises(Exception):
                    app_icon.cat_pixels(bad)


class TigerSymbolTests(unittest.TestCase):
    """第 49 期第 2 条：桌面图标重新设计成**三虎的符号**。

    用户点名的四件事就是这一组判据：清晰轮廓（一条粗墨线勾完整个剪影）、鲜艳色彩（平涂的虎皮
    橙 ＋ 奶白口鼻 ＋ 暖粉耳窝 ＋ 青色 ✦）、潮流元素（方块画布上贴一枚贴纸感的猫头，右上角
    一颗 ✦，与界面上那句「✦ 把灵感画成故事」是同一颗记号）、极简符号（一对耳朵、一张脸、三道
    额纹、两只菱形眼、一枚鼻子、一张嘴——七笔到底，不再有胡须、高光、渐变）。
    """

    @staticmethod
    def count(pixels, color):
        return sum(1 for row in pixels for pixel in row if tuple(pixel[:3]) == tuple(color[:3]))

    def test_the_outline_is_bold_enough_to_hold_a_symbol(self):
        self.assertGreaterEqual(app_icon.EDGE_W, 0.050, "极简的造型靠这条粗轮廓立住")
        pixels = app_icon.cat_pixels((128, 128))
        self.assertGreater(self.count(pixels, app_icon.INK), 300, "整张剪影一圈墨")

    def test_the_colours_are_vivid(self):
        """鲜艳：主色是暖橙（红 > 绿 > 蓝），色板上每一档的彩度都够看。"""
        for name in ("FUR", "EAR_IN", "MUZZLE", "ACCENT"):
            red, green, blue, alpha = getattr(app_icon, name)
            self.assertEqual(alpha, 255, "%s 要不透明" % name)
            self.assertGreater(max(red, green, blue) - min(red, green, blue), 25, "%s 太灰" % name)
        red, green, blue, _alpha = app_icon.FUR
        self.assertGreater(red, green, "虎皮橙：红多于绿")
        self.assertGreater(green, blue, "虎皮橙：绿多于蓝")

    def test_the_old_details_are_gone(self):
        """上一版的冷蓝、冰白高光、胡须墨随设计一起作废（不留没人用的常量）。"""
        for name in ("BODY", "OUTLINE", "LIGHT", "SOFT", "SHEEN", "WHISK_W"):
            self.assertFalse(hasattr(app_icon, name), name + " 是上一版的细节")

    def test_the_face_is_flat_orange_with_a_cream_muzzle(self):
        pixels = app_icon.cat_pixels((96, 96))
        opaque = sum(1 for row in pixels for pixel in row if pixel[3] > 0)
        self.assertGreater(self.count(pixels, app_icon.FUR), opaque * 0.30,
                           "脸是一整块平涂的虎皮橙（有渐变就凑不出这么多同色像素）")
        self.assertGreater(self.count(pixels, app_icon.MUZZLE), 60, "口鼻那块是奶白的")
        self.assertGreater(self.count(pixels, app_icon.EAR_IN), 8, "耳窝里那抹暖粉")

    def test_the_three_stripes_sit_on_the_forehead(self):
        """极简的「三」：沿脸的中线竖着数，额头那一段正好三道墨。"""
        size = 128
        pixels = app_icon.cat_pixels((size, size))
        column = [y for y in range(size)
                  if tuple(pixels[y][int(size * 0.5)][:3]) == tuple(app_icon.INK[:3])
                  and 0.28 * size <= y <= 0.49 * size]
        runs = 0
        for index, y in enumerate(column):
            if index == 0 or y != column[index - 1] + 1:
                runs += 1
        self.assertEqual(runs, 3, "额头三道纹，一道不少：%r" % column)

    def test_the_sparkle_is_in_the_top_right_corner(self):
        """潮流元素：右上角那颗 ✦。"""
        size = 128
        pixels = app_icon.cat_pixels((size, size))
        spots = [(x, y) for y in range(size) for x in range(size)
                 if tuple(pixels[y][x][:3]) == tuple(app_icon.ACCENT[:3])]
        self.assertTrue(spots, "那颗 ✦ 得画出来")
        self.assertGreater(min(x for x, _y in spots), size * 0.6, "它长在右半边")
        self.assertLess(max(y for _x, y in spots), size * 0.4, "而且在上半边")

    def test_the_ink_stays_on_the_upper_face(self):
        """鼻子往下就不再拖笔画了：下巴只剩下那一圈轮廓——缩到 32 像素也不糊成一团。"""
        size = 128
        pixels = app_icon.cat_pixels((size, size))
        ink = [(x, y) for y in range(size) for x in range(size)
               if tuple(pixels[y][x][:3]) == tuple(app_icon.INK[:3])]
        self.assertTrue(ink, "总得有墨")
        lower = [1 for _x, y in ink if y > size * 0.82]
        self.assertLess(len(lower), len(ink) * 0.35, "下半张脸只剩轮廓那一圈")

    def test_the_symbol_keeps_off_the_canvas_edge(self):
        """一条白边：剪影与那颗 ✦ 都不贴着画布边（缩到 16 像素也干净）。"""
        size = 128
        pixels = app_icon.cat_pixels((size, size))
        for x in (0, size - 1):
            for y in range(size):
                self.assertEqual(pixels[y][x][3], 0, '左右各留一条白边 (x=%d)' % x)
        for y in (0, size - 1):
            for x in range(size):
                self.assertEqual(pixels[y][x][3], 0, '上下也留白 (y=%d)' % y)


class IcoTests(unittest.TestCase):
    def test_the_container_header_is_well_formed(self):
        blob = app_icon.ico_bytes(((16, 10), (32, 20)))
        reserved, kind, count = struct.unpack('<HHH', blob[:6])
        self.assertEqual((reserved, kind, count), (0, 1, 2))
        offset = 6
        for expected in ((16, 10), (32, 20)):
            width, height, _colors, _res, planes, bits, length, start = struct.unpack(
                '<BBBBHHII', blob[offset:offset + 16])
            self.assertEqual((width, height), expected, '宽高各写各的')
            self.assertEqual((planes, bits), (1, 32))
            self.assertLessEqual(start + length, len(blob), '每一项都要在文件里')
            offset += 16
        self.assertGreater(len(blob), 400)

    def test_the_directory_is_ordered_like_the_request(self):
        blob = app_icon.ico_bytes(app_icon.SIZES)
        pairs = []
        for index in range(len(app_icon.SIZES)):
            width, height = struct.unpack('<BB', blob[6 + 16 * index:8 + 16 * index])
            pairs.append((width, height))
        self.assertEqual(pairs, [(0 if w >= 256 else w, 0 if h >= 256 else h)
                                 for w, h in app_icon.SIZES])

    def test_256_is_written_as_zero(self):
        blob = app_icon.ico_bytes(((256, 160),))
        self.assertEqual(blob[6], 0, '256 那一档按 ICO 规矩写 0')
        self.assertEqual(blob[7], 160, '高的那一头照常写')

    def test_the_dib_header_carries_both_sides(self):
        blob = app_icon.ico_bytes(((32, 20),))
        header = struct.unpack('<IiiHHIIiiII', blob[22:22 + 40])
        self.assertEqual(header[1], 32)
        self.assertEqual(header[2], 40, 'DIB 里的高是两倍（色彩位 ＋ 掩码）')


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_ensure_writes_the_file_then_reuses_it(self):
        target = self.base / 'sub' / 'x.ico'
        self.assertIsNotNone(app_icon.ensure(target, sizes=((16, 10),)))
        self.assertTrue(target.is_file())
        self.assertGreater(target.stat().st_size, 0)
        stamp = target.stat().st_mtime_ns
        self.assertEqual(app_icon.ensure(target, sizes=((16, 10),)), target, '已经有了就原样返回')
        self.assertEqual(target.stat().st_mtime_ns, stamp)

    def test_force_redraws_over_an_old_file(self):
        """第 25 期：图标重设计了，得能盖掉旧的那张（不然换了图桌面还是老样子）。"""
        target = self.base / 'x.ico'
        target.write_bytes(b'old')
        self.assertIsNotNone(app_icon.ensure(target, sizes=((16, 10),), force=True))
        self.assertNotEqual(target.read_bytes(), b'old')
        self.assertGreater(target.stat().st_size, 100)

    def test_ensure_is_quiet_when_it_cannot_write(self):
        target = self.base / 'x.ico'
        target.mkdir()
        self.assertIsNone(app_icon.ensure(target), '写不进去返回 None，绝不抛给界面线程')

    def test_the_preview_is_a_png_of_the_asked_size(self):
        target = self.base / 'p.png'
        app_icon.write_preview(target, size=(48, 30))
        blob = target.read_bytes()
        self.assertEqual(blob[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(ihdr(blob), (48, 30))

    def test_icon_path_points_into_the_program_folder(self):
        self.assertEqual(app_icon.icon_path().parent, app_icon.ASSETS)
        self.assertEqual(app_icon.icon_path().name, app_icon.ICON_NAME)


class WindowTests(unittest.TestCase):
    def test_apply_never_raises_on_a_window_without_iconbitmap(self):
        class FakeWindow:
            pass

        self.assertIsNone(app_icon.apply(FakeWindow()))

    def test_apply_hands_the_icon_to_a_real_window(self):
        try:
            import tkinter as tk
            win = tk.Tk()
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        win.withdraw()
        try:
            self.assertEqual(app_icon.apply(win), app_icon.icon_path())
        finally:
            win.destroy()


if __name__ == '__main__':
    unittest.main()