# -*- coding: utf-8 -*-
"""R1694：剧本准备页的「采风」入口真的在页脚上（真窗口构建，不是只查方法存在）。

行为侧（请求读写、后台排队、结果汇报）由 `tests/test_recon_service.py` 覆盖；
这里只钉一件事：这个按钮在真实页面上存在、可点、文案对。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(1, HERE)
os.chdir(PROGRAM)

from skip_reasons import PLATFORM_TKINTER

try:
    import tkinter as tk
except ImportError:                     # pragma: no cover - 平台缺件
    tk = None


class WritingReconButtonTests(unittest.TestCase):
    def test_the_recon_button_is_on_the_writing_page(self):
        if tk is None:
            self.skipTest(PLATFORM_TKINTER)
        try:
            win = tk.Tk()
        except tk.TclError:
            self.skipTest(PLATFORM_TKINTER)
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        win.geometry('1100x760+40+40')
        import desktop as desktop_module
        import pet_state
        from desktop import Desktop
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, 'choose_project', original)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'skill_config.json').write_text(json.dumps(
                {'workflow': {'name': 'AIGC全流程',
                              'lock': {'AIGC全流程': {'material_source': '对标爆款'}}}},
                ensure_ascii=False), encoding='utf-8')
            page = Desktop(win, root=PROGRAM)
            page.root = root
            page.show(pet_state.PAGE_OF['script'])
            win.update()
            button = getattr(page, 'recon_button', None)
            self.assertIsNotNone(button, '剧本准备页脚必须有「采风」入口')
            self.assertEqual(str(button.cget('text')), '采风')
            self.assertNotEqual(str(button.cget('state')), 'disabled', '采风入口不能是禁用态')
            foot = button.master
            labels = [child.cget('text') for child in foot.winfo_children() if 'text' in child.keys()]
            self.assertIn('采风', labels)
            self.assertIn('查看质检报告', labels, '采风与质检那组应在同一页脚')
            self.assertTrue(callable(getattr(page, 'collect_recon', None)))
            self.assertTrue(callable(getattr(page, 'recon_done', None)))


if __name__ == '__main__':
    unittest.main()
