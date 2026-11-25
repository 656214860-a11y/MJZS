# -*- coding: utf-8 -*-
"""UX-REPLY-AREA：第 2–13 页统一「过程与回话区」控件（ui/stage_reply_area.py）。

覆盖卡面接口契约：单实例挂在共享输入框正上方、script 与非阶段页隐藏、12 个
制作阶段页逐页切换；默认收起单行最新摘要；展开高度 ≤ 可用内容区 40% 且矮窗
钳制不把输入框挤出视口；用户指令、进度、审批、产物、错误按序渲染；更早
记录按钮分页；产物行可点开；记录按阶段分文件落盘。
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import tk_test_support
from agent.core import save_text
from contract import pet_bus
from domain import message_parts, stage_reply_log
from ui import stage_reply_area as reply_area_module


def _pump(win, seconds=.2):
    tk_test_support.pump(win, seconds)


class _Desktop:
    """StageReplyArea 的最小宿主：dock＋画布（可用内容区）＋共享输入框占位。"""

    def __init__(self, win, root):
        self.win = win
        self.root = root
        self.page_index = 0
        self.status = tk.StringVar(master=win, value='')
        self.canvas = tk.Canvas(win, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.dock = ttk.Frame(win)
        self.dock.pack(side='bottom', fill='x')
        self.shared_input = ttk.Frame(self.dock)
        ttk.Label(self.shared_input, text='输入框').pack()
        self.shared_input.pack(side='top', fill='x')
        self.opened = []

    def safe(self, fn):
        return fn()

    def open_target(self, target):
        self.opened.append(str(target))


class StageReplyAreaFixture(unittest.TestCase):
    def setUp(self):
        self.win = tk_test_support.make_root()
        self.win.geometry('960x720')
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.desktop = _Desktop(self.win, self.root)
        self.area = reply_area_module.StageReplyArea(self.desktop.dock, self.desktop)
        _pump(self.win)

    def _record(self, stage, i, kind='progress'):
        return stage_reply_log.append_record(
            self.root, stage, {'kind': kind, 'text': '第%d条' % i}, publish=save_text)


class StageVisibilityTests(StageReplyAreaFixture):
    def test_hidden_on_script_and_non_stage(self):
        self.area.sync_stage('script')
        self.assertEqual(self.area.winfo_manager(), '', 'script 页不显示回话区')
        self.area.sync_stage('')
        self.assertEqual(self.area.winfo_manager(), '', '非阶段页不显示回话区')
        self.assertEqual(self.area.stage, '')

    def test_every_production_stage_maps_above_shared_input(self):
        for stage in pet_bus.STAGES:
            if stage == 'script':
                continue
            with self.subTest(stage=stage):
                self.area.sync_stage(stage)
                _pump(self.win, .05)
                self.assertEqual(self.area.stage, stage)
                self.assertEqual(self.area.winfo_manager(), 'pack')
                slaves = self.desktop.dock.pack_slaves()
                self.assertLess(slaves.index(self.area), slaves.index(self.desktop.shared_input),
                                '回话区须位于共享输入框正上方')

    def test_switch_back_to_script_hides_again(self):
        self.area.sync_stage('storyboard')
        self.assertEqual(self.area.winfo_manager(), 'pack')
        self.area.sync_stage('script')
        self.assertEqual(self.area.winfo_manager(), '')
        self.area.sync_stage('keyframe')
        self.assertEqual(self.area.winfo_manager(), 'pack')


class CollapsedSummaryTests(StageReplyAreaFixture):
    def test_collapsed_by_default_one_line_summary(self):
        self.area.sync_stage('storyboard')
        _pump(self.win)
        self.assertFalse(self.area.expanded)
        self.assertEqual(self.area.body.winfo_manager(), '', '收起态不映射正文区')
        self.assertIn('暂无', self.area.summary.cget('text'))
        self.assertNotIn('\n', self.area.summary.cget('text'), '摘要只显示一行')

    def test_latest_record_shows_in_summary(self):
        self._record('storyboard', 0)
        self._record('storyboard', 1)
        self.area.sync_stage('storyboard')
        self.assertIn('第1条', self.area.summary.cget('text'))
        self.assertNotIn('第0条', self.area.summary.cget('text'), '收起态只显示最新一条')

    def test_note_appends_record_and_refreshes_summary(self):
        self.area.sync_stage('storyboard')
        self.area.note('user', 'storyboard', '整理为结构化剧本')
        self.assertIn('整理为结构化剧本', self.area.summary.cget('text'))
        records, _cursor = stage_reply_log.read_tail(self.root, 'storyboard')
        self.assertEqual([r.get('text') for r in records], ['整理为结构化剧本'])
        self.assertEqual(records[0].get('kind'), 'user')

    def test_note_for_other_stage_writes_its_own_file(self):
        self.area.sync_stage('storyboard')
        self.area.note('user', 'assets', '补齐角色图')
        records, _cursor = stage_reply_log.read_tail(self.root, 'assets')
        self.assertEqual([r.get('text') for r in records], ['补齐角色图'])
        self.assertNotIn('补齐角色图', self.area.summary.cget('text'),
                         '别的阶段记录不串进当前页摘要')


class ExpandGeometryTests(StageReplyAreaFixture):
    def test_expand_caps_at_forty_percent_of_content_area(self):
        self.area.sync_stage('storyboard')
        _pump(self.win)
        self.area.toggle()
        _pump(self.win)
        body = self.area.body.winfo_height()
        canvas = self.desktop.canvas.winfo_height()
        self.assertTrue(self.area.expanded)
        self.assertGreater(body, 0)
        self.assertLessEqual(body, int((canvas + body) * self.area.EXPAND_RATIO) + 2,
                             '展开体高 ≤ 可用内容区 40%')
        self.assertTrue(self.desktop.shared_input.winfo_ismapped())
        self.assertEqual(self.area.toggle_button.cget('text'), '收起')

    def test_short_window_keeps_input_inside_viewport(self):
        self.win.geometry('960x420')
        _pump(self.win)
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win)
        shared = self.desktop.shared_input
        bottom = shared.winfo_rooty() + shared.winfo_height()
        self.assertLessEqual(bottom, self.win.winfo_rooty() + self.win.winfo_height() + 2,
                             '矮窗时输入框不得被挤出视口')
        self.assertTrue(shared.winfo_ismapped())

    def test_toggle_back_collapses(self):
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win, .05)
        self.area.toggle()
        _pump(self.win, .05)
        self.assertFalse(self.area.expanded)
        self.assertEqual(self.area.body.winfo_manager(), '')
        self.assertEqual(self.area.toggle_button.cget('text'), '展开')


class SequenceAndRenderTests(StageReplyAreaFixture):
    def test_user_progress_artifact_error_render_in_order(self):
        self.area.sync_stage('storyboard')
        self.area.note('user', 'storyboard', '出分镜')
        self.area.note('progress', 'storyboard', '正在直连模型')
        self.area.note('artifact', 'storyboard', '第01集.json',
                       path=str(self.root / '01剧本准备' / '第01集.json'))
        self.area.note('error', 'storyboard', '输出失败：超时')
        _pump(self.win)
        self.area.toggle()
        _pump(self.win)
        content = self.area.text.get('1.0', 'end')
        positions = [content.index(mark) for mark in
                     ('出分镜', '正在直连模型', '第01集.json', '输出失败：超时')]
        self.assertEqual(positions, sorted(positions), '指令、进度、产物、错误须按序出现')
        self.assertIn('📄', content, '产物渲染为可点开的一行')

    def test_artifact_row_opens_target_via_host(self):
        self.area.sync_stage('storyboard')
        target = self.root / '03初步分镜' / 'shot.json'
        target.parent.mkdir(parents=True)
        target.write_text('{}', encoding='utf-8')
        self.area.note('artifact', 'storyboard', 'shot.json', path=str(target))
        artifact = message_parts.Artifact(
            kind='json', identifier=str(target), title='shot.json', meta={'path': str(target)})
        self.area.open_artifact(artifact)
        self.assertEqual(self.desktop.opened, [str(target)])

    def test_reasoning_part_stays_collapsible(self):
        self.area.sync_stage('storyboard')
        self.area.note('reply', 'storyboard', '',
                       parts=[message_parts.reasoning_part('先想这一步')])
        self.area.toggle()
        _pump(self.win)
        self.assertIn('思考过程', self.area.text.get('1.0', 'end'))

    def test_approval_kind_roundtrip(self):
        """审批记录种类已在 schema 预留：写入、加载、渲染全通（生产写入方另行接线）。"""
        self.area.note('approval', 'storyboard', '采用第 3 版分镜？')
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win)
        self.assertIn('采用第 3 版分镜？', self.area.text.get('1.0', 'end'))


class EarlierPaginationTests(StageReplyAreaFixture):
    def test_tail_200_then_load_earlier(self):
        total = stage_reply_log.TAIL_LIMIT + 30
        for i in range(total):
            self._record('storyboard', i)
        self.area.sync_stage('storyboard')
        self.assertEqual(len(self.area.records), stage_reply_log.TAIL_LIMIT)
        self.assertTrue(self.area.has_more)
        self.assertTrue(self.area.earlier_button.winfo_manager(), '有更早记录时出现「更早」钮')
        self.area.load_earlier()
        self.assertEqual(len(self.area.records), total)
        self.assertFalse(self.area.has_more)
        self.assertEqual(self.area.records[0].get('text'), '第0条')

    def test_load_earlier_prepends_before_existing(self):
        for i in range(5):
            self._record('storyboard', i)
        self.area.sync_stage('storyboard')
        first = self.area.records[0].get('text')
        self.assertEqual(first, '第0条')


class StreamTests(StageReplyAreaFixture):
    def test_streaming_appends_segments_then_persists(self):
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win, .05)
        self.area.begin_stream()
        self.area.push_stream('先给结论。')
        self.area.push_stream('再分点。')
        self.area.end_stream()
        records, _cursor = stage_reply_log.read_tail(self.root, 'storyboard')
        self.assertEqual([r.get('text') for r in records], ['先给结论。再分点。'])
        self.assertEqual(records[0].get('kind'), 'reply')
        self.assertIn('先给结论。再分点。', self.area.text.get('1.0', 'end'))


class DesktopReplyAreaIntegrationTests(unittest.TestCase):
    """真 Desktop：回话区挂在 input_dock 内输入框正上方，_sync_shared_input 联动切页。"""

    @classmethod
    def setUpClass(cls):
        import test_desktop_startup_perf as startup_fixtures
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory(prefix='reply-area-')
        app, cls.project = startup_fixtures.DesktopStartupPerfTests._startup_app(
            cls.temp.name, remembered=True)
        from desktop import Desktop
        cls.desktop = Desktop(cls.win, root=app)
        _pump(cls.win, 1.5)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.desktop.cancel_timers()
        except Exception:
            pass
        cls.win.destroy()
        cls.temp.cleanup()

    def test_stage_switch_visibility_and_position(self):
        from desktop import PAGE, PAGE_SITES
        d = self.desktop
        d.show(PAGE['storyboard'])
        _pump(self.win)
        area = getattr(d, 'reply_area', None)
        self.assertIsNotNone(area, 'desktop 须持有单实例 reply_area')
        self.assertEqual(area.stage, 'storyboard')
        self.assertEqual(area.winfo_manager(), 'pack', '阶段页回话区可见')
        self.assertEqual(str(area.winfo_parent()), str(d.input_dock))
        slaves = d.input_dock.pack_slaves()
        self.assertLess(slaves.index(area), slaves.index(d.shared_input),
                        '回话区位于共享输入框正上方')
        self.assertFalse(area.expanded, '默认收起')
        d.show(PAGE['script'])
        _pump(self.win)
        self.assertEqual(area.winfo_manager(), '', 'script 页隐藏（有自己的对话区）')
        d.show(PAGE_SITES)
        _pump(self.win)
        self.assertEqual(area.winfo_manager(), '', '非阶段页隐藏')
        d.show(PAGE['storyboard'])
        _pump(self.win)


if __name__ == '__main__':
    unittest.main()
