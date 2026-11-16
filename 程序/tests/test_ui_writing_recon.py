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
        """R2923：「采风」页脚按钮已随动作栏删除；行为方法 collect_recon/recon_done 保留。"""
        with tempfile.TemporaryDirectory() as td:
            page, _win = self.open_page(td, '对标爆款')
            self.assertIsNone(getattr(page, 'recon_button', None), '「采风」页脚按钮已删除')
            self.assertTrue(callable(getattr(page, 'collect_recon', None)))
            self.assertTrue(callable(getattr(page, 'recon_done', None)))

    def test_recon_button_hides_for_other_sources_until_source_applies(self):
        """R2923：采风按钮删除后不再随素材来源显隐——所有来源下均无该按钮。"""
        import stage_config
        with tempfile.TemporaryDirectory() as td:
            page, win = self.open_page(td, '原创')
            self.assertIsNone(getattr(page, 'recon_button', None), '原创来源下也无采风按钮')
            stage_config.put_workflow(Path(td), _workflow('热点速成'))
            page.update_recon_button()
            win.update()
            self.assertIsNone(getattr(page, 'recon_button', None), '改适用来源后仍无采风按钮')


if __name__ == '__main__':
    unittest.main()
