# -*- coding: utf-8 -*-
"""「选择分镜」下拉框的范围偏好写入：统一走 save_prefs（W6B-FIX-P1）。"""
import json, os, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import storyboard_source_selector


class FakeCombo:
    """select_box 替身：不建 Tk 控件，只记下绑定与当前序号。"""
    def __init__(self):
        self.index = -1
        self.binds = {}

    def pack(self, **kw):
        pass

    def current(self, index=None):
        if index is None:
            return self.index
        self.index = index

    def bind(self, sequence, handler):
        self.binds[sequence] = handler

    def winfo_exists(self):
        return True


def _app(root, errors, shown, current):
    def safe(fn):
        try:
            fn()
        except ValueError as exc:
            errors.append(exc)
    return types.SimpleNamespace(
        root=root,
        content=object(),
        asset_scope=lambda: 'current',
        current_frame_json=lambda: current,
        safe=safe,
        show=lambda index: shown.append(index),
        win=types.SimpleNamespace(
            tk=types.SimpleNamespace(call=lambda *a: None),
            after_idle=lambda fn: fn()))


def _select(app, combo, first, second):
    options = (['全部分镜', '甲', '乙'], [None, first, second], 1)
    with mock.patch.object(storyboard_source_selector, 'adopted',
                           return_value=[first, second]), \
         mock.patch.object(storyboard_source_selector, 'focus') as focus, \
         mock.patch('domain.storyboard_source_service.source_options',
                   return_value=options), \
         mock.patch('tkinter.ttk.Frame'), \
         mock.patch('tkinter.ttk.Label'):
        storyboard_source_selector.source_selector(
            app, 4, select_box=lambda parent, **kw: combo)
        combo.current(2)
        combo.binds['<<ComboboxSelected>>']()
    return focus


class SourceSelectorSavePrefsTests(unittest.TestCase):
    def test_writes_scope_when_project_exists(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'
            proj.mkdir()
            first, second = Path(td) / '甲.json', Path(td) / '乙.json'
            (proj / 'ui_settings.json').write_text(
                json.dumps({'other': 1}, ensure_ascii=False), encoding='utf-8')
            errors, shown, combo = [], [], FakeCombo()
            app = _app(proj, errors, shown, first)
            focus = _select(app, combo, first, second)
            prefs = json.loads((proj / 'ui_settings.json').read_text(encoding='utf-8'))
        self.assertEqual(prefs.get('asset_scope'), 'current')
        self.assertEqual(prefs.get('other'), 1)
        focus.assert_called_once_with(proj, second)
        self.assertEqual(errors, [])
        self.assertEqual(shown, [4])

    def test_missing_project_records_error_and_does_not_recreate(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'
            first, second = Path(td) / '甲.json', Path(td) / '乙.json'
            errors, shown, combo = [], [], FakeCombo()
            app = _app(proj, errors, shown, first)
            focus = _select(app, combo, first, second)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ValueError)
            self.assertIn('项目目录不存在或已被移动', str(errors[0]))
            self.assertFalse(proj.exists())
            focus.assert_not_called()
            self.assertEqual(shown, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
