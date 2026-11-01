# -*- coding: utf-8 -*-
"""R1694：剧本准备页的「采风」入口真的在页脚上（真窗口构建，不是只查方法存在）。

行为侧（请求读写、后台排队、结果汇报）由 `tests/test_recon_service.py` 覆盖；
这里钉两件事：这个按钮在真实页面上存在、可点、文案对；只在素材来源适用时显示。
"""
import json
import os
import sys
import tempfile
import time
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


def _workflow(source):
    return {'name': 'AIGC全流程', 'lock': {'AIGC全流程': {'material_source': source}}}


class WritingReconButtonTests(unittest.TestCase):
    def open_page(self, td, source):
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
        root = Path(td)
        (root / 'skill_config.json').write_text(json.dumps(
            {'workflow': _workflow(source)}, ensure_ascii=False), encoding='utf-8')
        page = Desktop(win, root=PROGRAM)
        page.root = root
        page.show(pet_state.PAGE_OF['script'])
        # 采风显隐由建页 250 ms 后的延后刷新补上，等它跑过再看。
        deadline = time.monotonic() + 0.8
        while time.monotonic() < deadline:
            win.update()
            time.sleep(0.05)
        win.update()
        return page, win

    def test_the_recon_button_is_on_the_writing_page(self):
        """REQ-S01-46：素材来源是「对标爆款」时，采风在页脚上可见、可点。"""
        with tempfile.TemporaryDirectory() as td:
            page, _win = self.open_page(td, '对标爆款')
            button = getattr(page, 'recon_button', None)
            self.assertIsNotNone(button, '剧本准备页脚必须有「采风」入口')
            self.assertEqual(str(button.cget('text')), '采风')
            self.assertNotEqual(str(button.cget('state')), 'disabled', '采风入口不能是禁用态')
            foot = button.master
            self.assertNotIn(button, foot.hidden_children)
            self.assertEqual(button.winfo_manager(), 'place', '适用的素材来源下采风要显示出来')
            labels = [child.cget('text') for child in foot.winfo_children() if 'text' in child.keys()]
            self.assertIn('采风', labels)
            self.assertIn('质检报告', labels, '采风与质检那组应在同一页脚')
            self.assertTrue(callable(getattr(page, 'collect_recon', None)))
            self.assertTrue(callable(getattr(page, 'recon_done', None)))

    def test_recon_button_hides_for_other_sources_until_source_applies(self):
        """REQ-S01-46：素材来源不是「对标爆款」「热点速成」时采风隐藏不占位；改成适用来源后显示。"""
        import stage_config
        with tempfile.TemporaryDirectory() as td:
            page, win = self.open_page(td, '原创')
            button = page.recon_button
            self.assertIn(button, button.master.hidden_children)
            self.assertEqual(button.winfo_manager(), '', '不适用时采风不占动作栏位置')
            stage_config.put_workflow(Path(td), _workflow('热点速成'))
            page.update_recon_button()
            win.update()
            self.assertNotIn(button, button.master.hidden_children)
            self.assertEqual(button.winfo_manager(), 'place')


if __name__ == '__main__':
    unittest.main()
