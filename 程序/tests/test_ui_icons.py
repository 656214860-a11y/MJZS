import unittest
from unittest.mock import patch

import ui_icons


class _Master:
    pass


class _Image:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.puts = []

    def put(self, colour, *, to):
        self.puts.append((colour, to))


class IconLoaderTests(unittest.TestCase):
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
