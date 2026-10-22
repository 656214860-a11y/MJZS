"""空格键勾选当前行：资产表与首帧表共用的 bind_space_toggle（R1777 审计第 35 项）。不起 Tk。"""
import unittest

from responsive_ui import bind_space_toggle


class FakeTree:
    def __init__(self, rows, focus='', selected=()):
        self.rows, self._focus, self._selected, self.handlers = set(rows), focus, tuple(selected), {}

    def bind(self, sequence, handler, add=None):
        self.handlers[sequence] = handler

    def focus(self):
        return self._focus

    def exists(self, row):
        return row in self.rows

    def selection(self):
        return self._selected

    def selection_set(self, row):
        self._selected = (row,)


class SpaceToggleTests(unittest.TestCase):
    def press(self, tree):
        toggled = []
        bind_space_toggle(tree, toggled.append)
        result = tree.handlers['<space>'](object())
        return toggled, result

    def test_toggles_the_focused_row_and_aligns_selection(self):
        tree = FakeTree({'a', 'b'}, focus='b', selected=('a',))
        toggled, result = self.press(tree)
        self.assertEqual(toggled, ['b'])
        self.assertEqual(tree.selection(), ('b',))
        self.assertEqual(result, 'break')

    def test_stale_focus_falls_back_to_the_selected_row(self):
        tree = FakeTree({'a'}, focus='gone', selected=('a',))
        toggled, _ = self.press(tree)
        self.assertEqual(toggled, ['a'])

    def test_nothing_to_toggle_still_swallows_the_key(self):
        toggled, result = self.press(FakeTree(set()))
        self.assertEqual(toggled, [])
        self.assertEqual(result, 'break')


if __name__ == '__main__':
    unittest.main()
