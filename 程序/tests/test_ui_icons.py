import unittest
from unittest.mock import patch

import ui_icons
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
