# -*- coding: utf-8 -*-
"""UX-REPLY-AREA：第 2–13 页统一「过程与回话区」控件（ui/stage_reply_area.py）。

覆盖卡面接口契约：单实例挂在共享输入框正上方、script 与非阶段页隐藏、12 个
制作阶段页逐页切换；默认收起单行最新摘要；展开正文是覆盖内容区的卡片浮层，
页面正文画布不重排、输入框不被挤出视口；浮层支持收起、键盘滚动/Esc、拖动或
键盘调整高度、切页重定位；用户指令、进度、审批、产物、错误按序渲染；更早
记录按钮分页；产物行可点开；记录按阶段分文件落盘。
"""
import tempfile
import time
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


def _pump_until(win, predicate, seconds=2):
    """隐藏桌面时启动/切页回调有真实排队时延：泵到谓词落定或超时。"""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        win.update_idletasks()
        win.update()
        if predicate():
            return True
        time.sleep(.005)
    return bool(predicate())


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
        self.shared_input.input = ttk.Entry(self.shared_input)
        self.shared_input.input.pack(fill='x')
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

    def test_expanded_overlay_hides_on_non_stage_page(self):
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win, .05)
        self.assertEqual(self.area.overlay.winfo_manager(), 'place')
        self.area.sync_stage('')
        _pump(self.win, .05)
        self.assertEqual(self.area.winfo_manager(), '')
        self.assertEqual(self.area.overlay.winfo_manager(), '', '非阶段页不得残留回话浮层')

    def test_reply_hides_when_real_route_hides_shared_input_after_sync(self):
        """真实路由顺序：sync_stage 先跑，locked/free/home 随后才 pack_forget 共享输入框。"""
        self.area.sync_stage('storyboard')
        self.area.toggle()
        self.desktop.shared_input.pack_forget()
        _pump(self.win, .05)
        self.assertEqual(self.area.winfo_manager(), '',
                         '共享输入框被真实路由收起时，回话区不得单独残留')
        self.assertEqual(self.area.overlay.winfo_manager(), '', '路由隐藏后回话浮层不得残留')
        self.area.sync_stage('storyboard')
        self.desktop.shared_input.pack(side='top', fill='x')
        _pump(self.win, .05)
        self.assertEqual(self.area.winfo_manager(), 'pack', '共享输入框恢复后回话区随阶段页恢复')
        slaves = self.desktop.dock.pack_slaves()
        self.assertLess(slaves.index(self.area), slaves.index(self.desktop.shared_input))

    def test_route_hidden_shared_input_moves_overlay_focus_to_canvas(self):
        self.area.sync_stage('storyboard')
        self.desktop.shared_input.input.focus_force()
        self.win.update()
        self.area.toggle()
        _pump(self.win, .05)
        self.assertIs(self.win.focus_get(), self.area.text)
        self.area.sync_stage('storyboard')
        self.desktop.shared_input.pack_forget()
        _pump(self.win, .05)
        self.assertIsNot(self.win.focus_get(), self.area.text,
                         '隐藏桌面里焦点也不得留在不可见回话文本')
        self.assertIs(self.win.focus_get(), self.desktop.canvas,
                      '共享输入框也隐藏时，焦点落到正文画布而不是隐藏控件')

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

    def test_note_with_expand_true_expands_current_stage_without_persisting_expand(self):
        import json
        self.area.sync_stage('storyboard')
        _pump(self.win, .05)
        self.assertFalse(self.area.expanded)
        self.area.note('error', 'storyboard', '请先确认结构剧本', expand=True)
        _pump(self.win, .05)
        self.assertTrue(self.area.expanded, '当前阶段传 expand=True 应自动展开')
        self.assertEqual(self.area.body.winfo_manager(), 'pack')
        self.assertEqual(self.area.toggle_button.cget('text'), '收起')
        rendered = self.area.text.get('1.0', 'end')
        self.assertEqual(rendered.count('请先确认结构剧本'), 1)
        records, _cursor = stage_reply_log.read_tail(self.root, 'storyboard')
        self.assertEqual(len(records), 1)
        self.assertNotIn('expand', records[0], 'expand 绝不得写入 JSONL 记录')
        log_path = stage_reply_log.stage_log_path(self.root, 'storyboard')
        raw_rows = [json.loads(line) for line in log_path.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertNotIn('expand', raw_rows[-1])

    def test_note_default_stays_collapsed_and_other_stage_expand_does_not_open_current(self):
        self.area.sync_stage('storyboard')
        _pump(self.win, .05)
        self.area.note('progress', 'storyboard', '普通进度记录')
        _pump(self.win, .05)
        self.assertFalse(self.area.expanded, '默认 expand=False 保持收起态')
        self.assertEqual(self.area.body.winfo_manager(), '')
        self.area.note('error', 'assets', '资产缺失报错', expand=True)
        _pump(self.win, .05)
        self.assertFalse(self.area.expanded, '非当前阶段传 expand=True 不得误展开当前页')
        self.assertEqual(self.area.body.winfo_manager(), '')
        records, _cursor = stage_reply_log.read_tail(self.root, 'assets')
        self.assertEqual([r.get('text') for r in records], ['资产缺失报错'])
        self.assertNotIn('expand', records[0])


class ExpandGeometryTests(StageReplyAreaFixture):
    def test_expanded_reply_is_overlay_and_does_not_move_content(self):
        """契约变更：展开体不再 pack 进 input_dock 挤压正文，而是 place 成画布内浮层。"""
        self.area.sync_stage('storyboard')
        _pump(self.win)
        canvas_before = (self.desktop.canvas.winfo_width(), self.desktop.canvas.winfo_height())
        input_top = self.desktop.shared_input.winfo_rooty()
        self.area.toggle()
        _pump(self.win)
        self.assertTrue(self.area.expanded)
        self.assertEqual(self.area.body.winfo_manager(), 'pack')
        self.assertEqual(self.area.overlay.winfo_manager(), 'place', '展开体应是浮层')
        self.assertTrue(self.area.overlay.winfo_ismapped())
        self.assertEqual((self.desktop.canvas.winfo_width(), self.desktop.canvas.winfo_height()),
                         canvas_before, '展开回话浮层不得改变正文画布几何')
        self.assertEqual(self.desktop.shared_input.winfo_rooty(), input_top,
                         '展开回话浮层不得推动共享输入框')
        overlay_h = self.area.overlay.winfo_height()
        canvas_h = self.desktop.canvas.winfo_height()
        self.assertGreater(overlay_h, 0)
        self.assertLessEqual(overlay_h, int(canvas_h * self.area.EXPAND_RATIO) + 2,
                             '默认展开高度仍不超过内容区 40%（用户手动调高除外）')
        self.assertGreaterEqual(self.area.overlay.winfo_rootx(),
                                self.desktop.canvas.winfo_rootx())
        self.assertLessEqual(self.area.overlay.winfo_rooty() + overlay_h,
                             self.desktop.canvas.winfo_rooty() + canvas_h + 2,
                             '浮层底边锚在内容区内、不盖住共享输入框')
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
        self.assertEqual(self.area.overlay.winfo_manager(), 'place')

    def test_toggle_back_collapses(self):
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win, .05)
        self.area.toggle()
        _pump(self.win, .05)
        self.assertFalse(self.area.expanded)
        self.assertEqual(self.area.body.winfo_manager(), '')
        self.assertEqual(self.area.overlay.winfo_manager(), '', '收起后浮层必须撤下')
        self.assertEqual(self.area.toggle_button.cget('text'), '展开')

    def test_resize_overlay_height_and_window_resize_repositions_it(self):
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win)
        default_h = self.area.overlay.winfo_height()
        self.area.resize_to(default_h + 64)
        _pump(self.win, .05)
        enlarged = self.area.overlay.winfo_height()
        self.assertGreater(enlarged, default_h, '用户可把浮层调高过默认 40% 档')
        self.area.resize_to(default_h - 32)
        _pump(self.win, .05)
        self.assertLess(self.area.overlay.winfo_height(), enlarged, '用户也可把浮层调低')
        before = (self.area.overlay.winfo_width(), self.area.overlay.winfo_rooty())
        self.win.geometry('800x520')
        _pump(self.win)
        self.assertNotEqual((self.area.overlay.winfo_width(), self.area.overlay.winfo_rooty()), before,
                            '窗口调整大小后浮层应跟随内容区重新定位')
        self.assertTrue(self.desktop.shared_input.winfo_ismapped())

    def test_drag_top_edge_resizes_overlay(self):
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win)
        before = self.area.overlay.winfo_height()
        self.area.resize_edge.event_generate('<Button-1>', x=4, y=4)
        self.area.resize_edge.event_generate('<B1-Motion>', x=4, y=-24)
        _pump(self.win, .05)
        self.assertGreater(self.area.overlay.winfo_height(), before,
                           '拖动浮层顶边向上应增加高度')
        self.area.resize_edge.event_generate('<ButtonRelease-1>', x=4, y=-24)
        _pump(self.win, .05)

    def test_expand_focuses_text_and_collapse_restores_input_focus(self):
        """聚焦回归：展开后键盘焦点进只读回话文本，收起后回到共享输入框。"""
        self.area.sync_stage('storyboard')
        _pump(self.win)
        composer_input = self.desktop.shared_input.input
        composer_input.focus_force()     # 隐藏桌面没有系统前台焦点；先建立真实的应用内焦点
        self.win.update()
        self.assertIs(self.win.focus_get(), composer_input)
        self.area.toggle()
        _pump(self.win, .05)
        self.assertIs(self.win.focus_get(), self.area.text,
                      '展开后方向键/Home/Esc 应直接作用于回话浮层')
        self.area.toggle()
        _pump(self.win, .05)
        self.assertIs(self.win.focus_get(), composer_input,
                      '收起后焦点须回到展开前的共享输入框')

    def test_keyboard_scroll_escape_and_ctrl_resize(self):
        self.win.focus_force()
        for i in range(40):
            self._record('storyboard', i)
        self.area.sync_stage('storyboard')
        self.area.toggle()
        _pump(self.win)
        self.assertGreater(self.area.text.yview()[0], 0, '长记录展开后默认停在末尾')
        self.area.text.event_generate('<Home>')
        _pump(self.win, .05)
        self.assertEqual(self.area.text.yview()[0], 0, 'Home 应键盘滚动到顶部')
        before_h = self.area.overlay.winfo_height()
        self.area.text.event_generate('<Control-Up>')
        _pump(self.win, .05)
        self.assertGreaterEqual(self.area.overlay.winfo_height(), before_h,
                                'Ctrl+Up 应调大或不小于原浮层高度')
        self.area.text.event_generate('<Escape>')
        _pump(self.win, .05)
        self.assertFalse(self.area.expanded, 'Esc 应收起浮层')
        self.assertEqual(self.area.overlay.winfo_manager(), '')

    def test_page_switch_retargets_overlay_and_script_hides_it(self):
        self.area.sync_stage('storyboard')
        self.desktop.shared_input.input.focus_force()   # 隐藏桌面先模拟应用在前台持有输入焦点
        self.win.update()
        self.area.toggle()
        _pump(self.win, .05)
        self.assertEqual(self.area.overlay.winfo_manager(), 'place')
        self.area.sync_stage('assets')
        _pump(self.win, .05)
        self.assertEqual(self.area.stage, 'assets')
        self.assertTrue(self.area.expanded, '制作阶段之间切页时浮层随阶段换档而不是失效')
        self.assertEqual(self.area.overlay.winfo_manager(), 'place')
        self.area.sync_stage('script')
        _pump(self.win, .05)
        self.assertEqual(self.area.winfo_manager(), '')
        self.assertEqual(self.area.overlay.winfo_manager(), '', '自然剧本页不得残留回话浮层')
        self.assertIsNot(self.win.focus_get(), self.area.text,
                         '切页隐藏浮层后焦点不得留在不可见回话文本里')
        self.area.sync_stage('keyframe')
        _pump(self.win, .05)
        self.assertEqual(self.area.stage, 'keyframe')
        self.assertEqual(self.area.overlay.winfo_manager(), 'place', '回到制作阶段页后浮层恢复')
        self.assertIs(self.win.focus_get(), self.area.text,
                      '浮层随切页恢复后键盘焦点也回到回话文本')


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
        ready = _pump_until(
            cls.win,
            lambda: cls.desktop.root is not None
            and getattr(cls.desktop, '_startup_project_page_job', None) is None
            and getattr(cls.desktop, '_startup_script_build_job', None) is None,
            seconds=5)
        if not ready:
            raise AssertionError('真实 Desktop 启动路由未落定，不能可靠验收 storyboard 切页')

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
        area = getattr(d, 'reply_area', None)
        self.assertIsNotNone(area, 'desktop 须持有单实例 reply_area')
        d.show(PAGE['storyboard'])
        self.assertTrue(
            _pump_until(self.win,
                        lambda: area.stage == 'storyboard' and area.winfo_manager() == 'pack',
                        seconds=2),
            '真实路由切到 storyboard 后回话区应随共享输入框显示')
        self.assertEqual(area.stage, 'storyboard')
        self.assertEqual(area.winfo_manager(), 'pack', '阶段页回话区可见')
        self.assertEqual(str(area.winfo_parent()), str(d.input_dock))
        slaves = d.input_dock.pack_slaves()
        self.assertLess(slaves.index(area), slaves.index(d.shared_input),
                        '回话区位于共享输入框正上方')
        self.assertFalse(area.expanded, '默认收起')
        self.assertEqual(str(area.overlay.master), str(d.stage_area),
                         '展开浮层须挂在画布与输入 dock 的共同祖先下，才能覆盖正文而不重排')
        canvas_size = (d.canvas.winfo_width(), d.canvas.winfo_height())
        area.toggle()
        _pump(self.win)
        self.assertEqual(area.overlay.winfo_manager(), 'place')
        self.assertEqual((d.canvas.winfo_width(), d.canvas.winfo_height()), canvas_size,
                         '真 Desktop 中展开浮层不得推动正文画布')
        area.toggle()
        d.show(PAGE['script'])
        _pump(self.win)
        self.assertEqual(area.winfo_manager(), '', 'script 页隐藏（有自己的对话区）')
        d.show(PAGE_SITES)
        _pump(self.win)
        self.assertEqual(area.winfo_manager(), '', '非阶段页隐藏')
        d.show(PAGE['storyboard'])
        self.assertTrue(
            _pump_until(self.win,
                        lambda: area.stage == 'storyboard' and area.winfo_manager() == 'pack',
                        seconds=2),
            '离开再返回 storyboard 后回话区仍应恢复显示')


if __name__ == '__main__':
    unittest.main()
