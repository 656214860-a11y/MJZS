# -*- coding: utf-8 -*-
"""L4-U6：空项目下 08 首帧、09 白模、12 剪辑、13 交付四页能打开并显示引导。

先红后绿：改前四页在真实侧栏回调里分别抛 ValueError／AttributeError，被 ``go()``
兜成状态栏错误文案；本模块用隐藏桌面、临时样例项目复现，要求四页改走引导分支：
页面里有一段说明和一颗跳到补齐前置那一步的主按钮，状态栏不出现错误级消息。
"""
import json
import os
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(HERE / 'scripts'))
os.chdir(HERE)

import selftest_env  # noqa: F401,E402  自检环境必须先于 tkinter 生效

import tk_test_support
from contract import pet_bus, project_stages
from desktop import Desktop
from ui.desktop_page_registry import PAGE, PAGES
from ui.desktop_status_bridge import status_kind
from ui_widgets import DescriptionBlock, PrimaryButton
import test_desktop_startup_perf as startup_fixtures

# 四页 → 补齐前置那一步的页序号（08/09 缺分镜 JSON，去初步分镜；12/13 缺视频，去视频生成）。
GUIDE_TARGETS = {
    PAGE['keyframe']: PAGE['storyboard'],
    PAGE['previs']: PAGE['storyboard'],
    PAGE['edit']: PAGE['video'],
    PAGE['delivery']: PAGE['video'],
}

ALL_PAGES = list(range(len(PAGES) + 1))  # 01–13 阶段页、14 参考网站、00 会员账户


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def guides(page):
    """当前内容框里的说明文字与主按钮（引导页就是「一段说明＋一颗主按钮」）。"""
    blocks = [w for w in walk(page.content) if isinstance(w, DescriptionBlock)]
    buttons = [w for w in walk(page.content) if isinstance(w, PrimaryButton)]
    return blocks, buttons


class _DesktopCase(unittest.TestCase):
    """一套临时程序目录与样例项目；``with_storyboard`` 决定要不要补上分镜前置。"""

    with_storyboard = False

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(prefix='l4u6-')
        self.addCleanup(self._temp.cleanup)
        import asset_thumbs
        self._asset_thumbs = asset_thumbs
        self._cache_root = asset_thumbs.CACHE_ROOT
        asset_thumbs.reset_worker()
        asset_thumbs.forget()
        asset_thumbs.CACHE_ROOT = Path(self._temp.name) / 'thumbs'
        self.addCleanup(self._restore_thumbs)
        self.app, self.project = startup_fixtures.DesktopStartupPerfTests._startup_app(
            self._temp.name, remembered=True)
        script_dir = project_stages.writing(self.project) / '项目剧本'
        script_dir.mkdir(parents=True, exist_ok=True)
        (script_dir / '样例剧本.md').write_text('正文', encoding='utf8')
        if self.with_storyboard:
            self._write_storyboard()
        self.win = tk_test_support.make_root()
        self.win.geometry('1280x800+0+0')
        self.addCleanup(self.win.destroy)
        self.exceptions = []
        self.win.report_callback_exception = self._report_exception
        self.desktop = Desktop(self.win, root=self.app)
        self.addCleanup(self._close_desktop)
        tk_test_support.pump(self.win, 2, idle_first=False)

    def _report_exception(self, exc_type, exc, tb):
        self.exceptions.append(''.join(traceback.format_exception(exc_type, exc, tb))[-800:])

    def _restore_thumbs(self):
        self._asset_thumbs.reset_worker()
        self._asset_thumbs.forget()
        self._asset_thumbs.CACHE_ROOT = self._cache_root

    def _close_desktop(self):
        try:
            self.desktop.cancel_timers()
        except Exception:
            pass

    def _write_storyboard(self):
        shot = {'id': 'SH001', 'title': '镜头', 'duration': 5, 'characters': [],
                'location': 'LOC_001', 'frame': 'frames/SH001.png',
                'video_prompt': '一个角色站在窗边，镜头缓慢推近，光线柔和。', 'dialogue': []}
        episode = {'episode_id': 'EP001', 'title': '测试', 'shots': [shot]}
        folder = project_stages.storyboard(self.project) / '分镜拆分'
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / 'EP001_测试_分镜.json'
        source.write_text(json.dumps(episode, ensure_ascii=False), encoding='utf-8')
        relative = source.relative_to(self.project).as_posix()
        (self.project / 'ui_settings.json').write_text(json.dumps(
            {'adopted_storyboards': [relative], 'frame_json': relative},
            ensure_ascii=False), encoding='utf-8')

    def open_page(self, index):
        self.exceptions.clear()
        self.desktop.go(index)
        tk_test_support.pump(self.win, .8)
        return list(self.exceptions)


class EmptyProjectPagesTests(_DesktopCase):
    def test_all_pages_open_without_error(self):
        """T1：15 个页面逐个打开，页码到位、无 Tk 回调异常；四页不落进错误提示。"""
        errors = []
        original = self.desktop.notifier.error

        def spy(message, **kwargs):
            errors.append(str(message))
            return original(message, **kwargs)

        self.desktop.notifier.error = spy
        self.addCleanup(setattr, self.desktop.notifier, 'error', original)
        for index in ALL_PAGES:
            with self.subTest(page=index):
                errors.clear()
                thrown = self.open_page(index)
                self.assertEqual([], thrown)
                self.assertEqual(index, self.desktop.page_index)
                if index in GUIDE_TARGETS:
                    self.assertEqual([], errors, '第%02d页落到错误提示' % index)
                    for status in (self.desktop.status.get(),
                                   getattr(self.desktop.status_bar, 'message', '')):
                        self.assertNotEqual('error', status_kind(status),
                                            '第%02d页状态栏：%s' % (index, status))

    def test_guide_and_jump_button(self):
        """T2：四页各有一段说明和一颗主按钮；按钮跳到补齐前置那一步。"""
        for index, target in GUIDE_TARGETS.items():
            with self.subTest(page=index):
                thrown = self.open_page(index)
                self.assertEqual([], thrown)
                blocks, buttons = guides(self.desktop)
                texts = [str(block.cget('text')) for block in blocks if str(block.cget('text')).strip()]
                self.assertTrue(texts, '第%02d页没有说明文字' % index)
                self.assertTrue(any(pet_bus.stage_step(
                    'storyboard' if target == PAGE['storyboard'] else 'video') in text
                    for text in texts), '第%02d页说明没有指向补齐步骤：%s' % (index, texts))
                self.assertEqual(1, len(buttons), '第%02d页主按钮数：%s' % (index, len(buttons)))
                buttons[0].invoke()
                tk_test_support.pump(self.win, .8)
                self.assertEqual(target, self.desktop.page_index)


class FilledProjectPagesTests(_DesktopCase):
    with_storyboard = True

    def test_four_pages_show_no_guide_after_prerequisite(self):
        """T3：补上分镜前置后，四页不再显示引导（沿用原有布局与按钮）。"""
        self.assertTrue(self.desktop.align_studio())
        for index in GUIDE_TARGETS:
            with self.subTest(page=index):
                thrown = self.open_page(index)
                self.assertEqual([], thrown)
                self.assertEqual(index, self.desktop.page_index)
                blocks, _buttons = guides(self.desktop)
                self.assertEqual([], [str(block.cget('text')) for block in blocks
                                      if pet_bus.stage_step('storyboard') in str(block.cget('text'))])


if __name__ == '__main__':
    unittest.main()
