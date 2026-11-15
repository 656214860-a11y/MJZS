import unittest
from unittest.mock import patch

import ui_icons
from desktop_page_registry import (ASSET_ROSTER_ICON, PAGE_NAV_ICONS,
                                   PROJECT_ACTION_ICONS, PROJECT_GROUP_ICONS)
from ui_tokens import COLORS


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
        with patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)) as made:
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
        with patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)) as made:
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
        with patch.object(ui_icons.tk, 'PhotoImage', side_effect=lambda **kw: _Image(**kw)) as made:
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
