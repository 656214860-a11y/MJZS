import unittest
from collections import Counter
from unittest.mock import patch

import ui_icons
from contract.pet_bus import STAGES
from desktop_page_registry import (ASSET_ROSTER_ICON, PAGE_NAV_ICONS,
                                   PROJECT_ACTION_ICONS, PROJECT_GROUP_ICONS)
from ui_tokens import COLORS, NAV_ICON_SIZE

MIN_BADGE_OVERLAP_SHARE = 0.4    # 角标外框至少四成面积压在阶段图形的画布范围内
MIN_BADGE_CONTRAST = 4.5         # 角标主色与图标列背景的对比度下限


class _Master:
    pass


class _Image:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.puts = []

    def put(self, colour, *, to):
        self.puts.append((colour, to))


class IconLoaderTests(unittest.TestCase):
    def test_return_arrow_color_is_rendered_and_part_of_cache_key(self):
        master = _Master()
        with patch.object(ui_icons, '_tinted_png', return_value=None), \
                patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)) as made:
            white = ui_icons.IconLoader.return_arrow(master)
            themed = ui_icons.IconLoader.return_arrow(master, color=COLORS['primary'])
            again = ui_icons.IconLoader.return_arrow(master, color=COLORS['primary'])
            scaled = ui_icons.IconLoader.return_arrow(master, width=24, height=16,
                                                       color=COLORS['primary'])
        self.assertIsNot(white, themed)
        self.assertIs(themed, again)
        self.assertIsNot(themed, scaled)
        self.assertEqual(made.call_count, 3)
        self.assertEqual({color for color, _ in white.puts}, {COLORS['background_card']})
        self.assertEqual({color for color, _ in themed.puts}, {COLORS['primary']})
        self.assertEqual([area for _, area in white.puts],
                         [area for _, area in themed.puts])

    def test_return_arrow_is_cached_per_master_and_size(self):
        master = _Master()
        with patch.object(ui_icons, '_tinted_png', return_value=None), \
                patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)) as made:
            first = ui_icons.IconLoader.return_arrow(master)
            again = ui_icons.IconLoader.return_arrow(master)
            scaled = ui_icons.IconLoader.return_arrow(master, width=24, height=16)
        self.assertIs(first, again)
        self.assertIsNot(first, scaled)
        self.assertEqual(made.call_count, 2)
        self.assertTrue(first.puts)

    def test_return_arrow_cache_is_not_shared_between_tk_hosts(self):
        with patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)):
            first = ui_icons.IconLoader.return_arrow(_Master())
            second = ui_icons.IconLoader.return_arrow(_Master())
        self.assertIsNot(first, second)


class NavIconTests(unittest.TestCase):
    """R2897：侧栏图标轨的语义名必须都能解析到已入库的 PNG。"""

    def test_every_sidebar_semantic_name_has_a_png(self):
        names = set(PAGE_NAV_ICONS.values()) | {ASSET_ROSTER_ICON}
        names |= set(PROJECT_GROUP_ICONS.values()) | set(PROJECT_ACTION_ICONS.values())
        self.assertEqual(len(names), 20, '阶段 13 + 参考网站 + 账户 + 资产清单 + 项目区 4 枚')
        for name in names:
            with self.subTest(icon=name):
                self.assertTrue((ui_icons._NAV_DIR / f'{name}.png').is_file(),
                                f'assets/nav/{name}.png 缺失：跑 scripts/build_nav_icons.py 重新生成')

    def test_nav_icon_loads_file_and_caches_per_name(self):
        master = _Master()
        with patch.object(ui_icons, '_tinted_png', return_value=None), \
                patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)) as made:
            first = ui_icons.IconLoader.nav_icon(master, 'video')
            again = ui_icons.IconLoader.nav_icon(master, 'video')
            other = ui_icons.IconLoader.nav_icon(master, 'audio')
        self.assertIs(first, again)
        self.assertIsNot(first, other)
        self.assertEqual(made.call_count, 2)
        self.assertTrue(made.call_args_list[0].kwargs['file'].endswith('video.png'))
        self.assertTrue(made.call_args_list[1].kwargs['file'].endswith('audio.png'))

    def test_nav_icon_missing_name_or_file_returns_none(self):
        master = _Master()
        self.assertIsNone(ui_icons.IconLoader.nav_icon(master, None))
        self.assertIsNone(ui_icons.IconLoader.nav_icon(master, ''))
        self.assertIsNone(ui_icons.IconLoader.nav_icon(master, 'no_such_icon'))

    def test_nav_icon_scales_and_caches_per_size(self):
        import base64
        import io
        from PIL import Image
        master = _Master()
        with patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)) as made:
            big = ui_icons.IconLoader.nav_icon(master, 'video', size=30)
            big_again = ui_icons.IconLoader.nav_icon(master, 'video', size=30)
            small = ui_icons.IconLoader.nav_icon(master, 'video', size=18)
        self.assertIs(big, big_again)
        self.assertIsNot(big, small)
        self.assertEqual(made.call_count, 2)
        big_img = Image.open(io.BytesIO(base64.b64decode(big.kwargs['data'])))
        small_img = Image.open(io.BytesIO(base64.b64decode(small.kwargs['data'])))
        self.assertEqual(big_img.size, (30, 30))
        self.assertEqual(small_img.size, (18, 18))
        # retint_nav_icons 对无 configure 方法的替身应安全跳过而不抛出 AttributeError。
        ui_icons.retint_nav_icons()

    def test_files_panel_dock_action_icons_have_pngs(self):
        """UX-C1：停靠面板四个动作钮与侧栏同套 PNG（素材库／设置／回收站／清空）。"""
        names = ('library', 'library_settings', 'recycle', 'recycle_purge')
        for name in names:
            with self.subTest(icon=name):
                self.assertTrue((ui_icons._NAV_DIR / f'{name}.png').is_file(),
                                f'assets/nav/{name}.png 缺失：跑 scripts/build_nav_icons.py 重新生成')

    def test_settings_hub_eight_icons_have_pngs_and_zero_main_nav_reuse(self):
        """UX-SETTINGS-MODELS：设置左栏 8 枚专属图标全部落盘且与主导航 0 复用。"""
        import pet_settings_ui
        main_names = (set(PAGE_NAV_ICONS.values()) | {ASSET_ROSTER_ICON, 'settings', 'lock', 'back',
                                                      'library', 'library_settings', 'recycle', 'recycle_purge'}
                      | set(PROJECT_GROUP_ICONS.values()) | set(PROJECT_ACTION_ICONS.values()))
        settings_names = set(pet_settings_ui.TAB_ICONS.values())
        self.assertEqual(len(settings_names), 8)
        self.assertTrue(settings_names.isdisjoint(main_names))
        for name in sorted(settings_names):
            with self.subTest(icon=name):
                self.assertTrue((ui_icons._NAV_DIR / f'{name}.png').is_file(),
                                f'assets/nav/{name}.png 缺失：跑 scripts/build_nav_icons.py 重新生成')


def _rgb(hex_color):
    value = hex_color.lstrip('#')
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _luminance(rgb):
    channels = []
    for channel in rgb:
        channel = channel / 255
        channels.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class StageFileBadgeTests(unittest.TestCase):
    """REQ-S01-93：阶段文件图标的文件角标压在阶段图形右下角之上、主题色实心、四周浅色描边。

    断言针对 ``assets/nav/<stage>_files.png`` 的像素本身；角标位置取合成图与对应导航图的
    逐像素差异外接矩形，与 ``tests/test_files_panel_stages.py::StageFileIconTests`` 同一口径。
    """

    @classmethod
    def setUpClass(cls):
        from PIL import Image
        from ui.desktop_page_registry import NAV_STAGE_ICONS
        cls.pairs = []
        for stage in STAGES:
            with Image.open(ui_icons._NAV_DIR / f'{stage}_files.png') as image:
                comp = image.convert('RGBA')
            with Image.open(ui_icons._NAV_DIR / f'{NAV_STAGE_ICONS[stage]}.png') as image:
                nav = image.convert('RGBA')
            cls.pairs.append((stage, comp, nav))

    @staticmethod
    def _nav_pixel(nav, x, y):
        if 0 <= x < nav.width and 0 <= y < nav.height:
            return nav.getpixel((x, y))
        return (0, 0, 0, 0)

    def _badge_box(self, comp, nav):
        points = [(x, y) for y in range(comp.height) for x in range(comp.width)
                  if comp.getpixel((x, y)) != self._nav_pixel(nav, x, y)]
        self.assertTrue(points, '合成图与导航图没有差异，文件角标缺失')
        xs = [x for x, _y in points]
        ys = [y for _x, y in points]
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1

    def test_badge_sits_on_top_of_stage_glyph(self):
        """角标外框至少四成面积落在阶段图形的画布范围内：是压在图形上，不是挂在外面。"""
        for stage, comp, nav in self.pairs:
            left, top, right, bottom = self._badge_box(comp, nav)
            over_w = max(0, min(right, NAV_ICON_SIZE) - left)
            over_h = max(0, min(bottom, NAV_ICON_SIZE) - top)
            share = over_w * over_h / float((right - left) * (bottom - top))
            self.assertGreaterEqual(
                share, MIN_BADGE_OVERLAP_SHARE,
                f'{stage}: 角标只有 {share:.0%} 压在阶段图形上，外框 {(left, top, right, bottom)}')

    def test_badge_main_color_stands_out_from_rail_background(self):
        """角标里出现最多的颜色不透明，且与图标列背景的对比度不低于下限。"""
        background = _rgb(COLORS['background_primary'])
        for stage, comp, nav in self.pairs:
            left, top, right, bottom = self._badge_box(comp, nav)
            colors = Counter(comp.getpixel((x, y))
                             for y in range(top, bottom) for x in range(left, right))
            main = colors.most_common(1)[0][0]
            self.assertEqual(main[3], 255, f'{stage}: 角标主色不是不透明色 {main}')
            ratio = _contrast(main[:3], background)
            self.assertGreaterEqual(
                ratio, MIN_BADGE_CONTRAST,
                f'{stage}: 角标主色 {main[:3]} 与背景对比度只有 {ratio:.2f}')

    def test_badge_has_one_pixel_light_ring(self):
        """角标外框最外一圈像素全是不透明的图标列背景色：把角标和它压住的阶段图形分开。"""
        ring = _rgb(COLORS['background_primary']) + (255,)
        for stage, comp, nav in self.pairs:
            left, top, right, bottom = self._badge_box(comp, nav)
            edge = [(x, y) for y in range(top, bottom) for x in range(left, right)
                    if x in (left, right - 1) or y in (top, bottom - 1)]
            wrong = [(x, y) for x, y in edge if comp.getpixel((x, y)) != ring]
            self.assertEqual(
                wrong, [], f'{stage}: 外圈有 {len(wrong)} 个像素不是描边色，首个 {wrong[:1]}')

    def test_tinted_stage_file_icon_preserves_gray_folder_badge(self):
        """染色后阶段文件角标保持灰色文件夹（text_secondary）与背景隔断环，不压成黑块。"""
        from PIL import Image
        bg_rgb = _rgb(COLORS['background_primary'])
        folder_rgb = _rgb(COLORS['text_secondary'])
        primary_rgb = _rgb(COLORS['text_primary'])
        self.assertNotEqual(folder_rgb, primary_rgb)
        for stage, comp, nav in self.pairs[:3]:
            left, top, right, bottom = self._badge_box(comp, nav)
            tinted = ui_icons._tint_stage_file_image(comp)
            badge_colors = {tinted.getpixel((x, y))[:3]
                            for y in range(top, bottom) for x in range(left, right)
                            if tinted.getpixel((x, y))[3] == 255}
            self.assertIn(folder_rgb, badge_colors, f'{stage}: 染色后右下角文件夹应保持灰色 text_secondary')
            self.assertIn(bg_rgb, badge_colors, f'{stage}: 染色后应保留背景色隔断环')
            self.assertNotIn(primary_rgb, badge_colors, f'{stage}: 角标区不得被压成纯深色 text_primary')
