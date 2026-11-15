# -*- coding: utf-8 -*-
"""REQ-S01 测试锚定：剧本准备里没有现成行为用例可挂的两条需求。

其余十二条需求（S01 段的 01、02、03、04、10、11、12、13、14、20、21、30）由 ``tests/``
下既有的行为用例锚定，见各测试 docstring；本文件只补下面两条没有现成锚点的需求。

- REQ-S01-22：阶段完成＝能解析到被采用的剧本源；模型文字／界面提示不算证据。
- REQ-S01-31：SKILL 内容超预算或缺失时阻止发送，不截断、不静默省略。

断言只调用真实函数（``stage_completion_service``／``script_contract``／
``workflow_context_budget``／``workflow_settings``／``stage_path_service``），不 mock
被测事实、不检查源码字符串；需要落盘时一律在 ``tempfile.TemporaryDirectory()`` 隔离目录内。

本文件另有一条真 Tk 锚点（``IdeaBubbleAnchorTests``）：REQ-S01-01 的「气泡式界面」此前只由
持久化往返用例间接覆盖，这里补一条真 Tk 几何用例，按气泡渲染代码的实际契约断言容器、底色／对齐、
宽度与重启重建。
"""
import tempfile
import tkinter
import unittest
from pathlib import Path

import desktop_idea_chat
import script_contract
import stage_completion_service
import stage_config
import workflow_context_budget
import workflow_settings
from agent.core import save
from stage_path_service import write_dir
from tests.test_idea_chat import _Harness, idea_chat
from tests.ui_edges_support import make_minimal_project

RAW = (
    '第 1 集\n'
    '场景 1：夜，旧书店内\n'
    '林小满：把旧怀表交给我。\n'
    '陆时：先离开这里。\n'
    '道具：旧怀表\n'
)


class S01AnchorTests(unittest.TestCase):
    def test_req_s01_22_completion_evidence_is_the_adopted_script_source(self):
        """REQ-S01-22：阶段完成＝能解析到被采用的剧本源；模型文字不算证据。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # 没有可解析的剧本源时不算完成；模型自称“写完了”也不发完成事件。
            self.assertFalse(stage_completion_service.completion_evidence(root, 'script')[0])
            events = []

            def emit(*args, **kwargs):
                events.append((args, kwargs))
                return {'ok': True}

            ok, _detail, payload = stage_completion_service.emit_verified_completion(
                root, 'script', '模型说写完了', emit)
            self.assertFalse(ok)
            self.assertIsNone(payload)
            self.assertEqual(events, [])
            # 出现被采用的剧本源后才有证据，事件才发出。
            folder = write_dir(root, 'script')
            folder.mkdir(parents=True, exist_ok=True)
            source = folder / '我的剧本_自然剧本_20260101.md'
            source.write_text(RAW, encoding='utf-8')
            self.assertEqual(script_contract.resolve_script_source(root), source)
            self.assertTrue(stage_completion_service.completion_evidence(root, 'script')[0])
            ok, _detail, payload = stage_completion_service.emit_verified_completion(
                root, 'script', '完成', emit)
            self.assertTrue(ok)
            self.assertEqual([args[0] for args, _kwargs in events], ['stage.completed'])
            self.assertEqual(events[0][1]['stage'], 'script')

    def test_req_s01_31_oversized_or_missing_skill_blocks_send_without_truncation(self):
        """REQ-S01-31：SKILL 缺失或超预算时阻止发送，且不截断、不静默省略。"""
        # 缺失：已勾选但未加载的 SKILL 直接阻止发送。
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            save(stage_config.path(project),
                 {'script': {'model': 'gpt-4o', 'skills': ['deleted-skill']}})
            with self.assertRaisesRegex(ValueError, '已勾选的 SKILL 未加载'):
                workflow_settings.validate_selected_skills(project, 'writing')
        # 超预算：冻结 SKILL 正文时走同一硬保护，抛错而不是截断或省略。
        oversized = '技' * (workflow_context_budget.REQUEST_CONTEXT_MAX_CHARS + 1)
        with self.assertRaises(ValueError) as caught:
            workflow_context_budget.ensure_request_context(oversized, 'SKILL')
        self.assertIn('超过', str(caught.exception))
        # 预算内的 SKILL 原样返回，不截断、不静默省略。
        text, _budget = workflow_context_budget.prepare_request_context('技能正文', 'SKILL', report=True)
        self.assertEqual(text, '技能正文')


class IdeaBubbleAnchorTests(_Harness):
    """REQ-S01-01：创意对话的消息在真 Tk 下渲染成独立气泡，重建后仍按原顺序出现。"""

    USER = '想法：夜班照相馆收到会显影未来的旧底片'
    MODEL = '收到，先把这条设定记进第一集。'

    def settle_bubbles(self, d, win):
        """让首帧、模型键解析与分片插入都落地，再按真实宽度重摆一次气泡。"""
        win.deiconify()
        self.settle_script_page(win)
        d.show_conversation()
        self.settle_script_page(win)
        d.refit_bubbles()
        win.update_idletasks()

    @staticmethod
    def bbox_x(box, index):
        """文字首像素的横坐标；不可见时返回 None（不掩盖失败，由断言点出来）。"""
        try:
            found = box.bbox(index)
        except tkinter.TclError:
            return None
        return None if found is None else int(found[0])

    def assert_rendered_bubbles(self, box):
        """两条消息＝两只独立气泡；按代码实际契约分别断言容器、底色／对齐和宽度。"""
        spans = {}
        for name in ('bubble_0', 'bubble_1'):
            # 契约：add_bubble 给每条消息建一个 bubble_<序号> 标签（desktop_idea_chat.py:600），
            # 正文单独插在该标签下（:635）——标签范围就是这条消息自己的气泡容器。
            ranges = box.tag_ranges(name)
            self.assertEqual(len(ranges), 2, name + ' 应为一段独立的气泡正文')
            spans[name] = ranges
        self.assertLessEqual(box.index(spans['bubble_0'][1]), box.index(spans['bubble_1'][0]),
                             '两只气泡的正文容器互不重叠')
        # 文字完整：预览即全文（desktop_idea_chat.py:633-635）。
        self.assertEqual(str(box.get(*spans['bubble_0'])).strip(), self.USER)
        self.assertEqual(str(box.get(*spans['bubble_1'])).strip(), self.MODEL)
        # 契约（参考 DeepSeek 对话）：正文铺浅灰底框，用户靠右、模型靠左分列仍保留；不画描边线。
        self.assertEqual(str(box.tag_cget('bubble_0', 'background')), desktop_idea_chat.BUBBLE_FILL)
        self.assertEqual(str(box.tag_cget('bubble_1', 'background')), desktop_idea_chat.BUBBLE_FILL)
        self.assertIn(str(box.tag_cget('bubble_0', 'relief')), ('', 'flat'),
                      '正文只铺淡底，不设 relief 描边（多行会出横线）')
        self.assertGreater(int(box.tag_cget('bubble_0', 'lmargin1')), int(box.tag_cget('bubble_1', 'lmargin1')),
                           '用户消息必须比模型消息更靠右')
        # 契约：用户贴右（左边距更大），模型贴左（一个 BUBBLE_GAP 再加正文外框的 BUBBLE_PAD 内边距）。
        user_left = int(float(box.tag_cget('bubble_0', 'lmargin1')))
        model_left = int(float(box.tag_cget('bubble_1', 'lmargin1')))
        self.assertEqual(model_left, desktop_idea_chat.BUBBLE_GAP + desktop_idea_chat.BUBBLE_PAD)
        self.assertGreater(user_left, model_left, '用户气泡贴在右侧')
        # 真几何：气泡正文宽度＝对话区实际宽度 − 左右边距，不超过对话区宽度且非空。
        width = int(box.winfo_width())
        self.assertGreater(width, 1, '对话区应有真实宽度')
        for name in ('bubble_0', 'bubble_1'):
            left = int(float(box.tag_cget(name, 'lmargin1')))
            right = int(float(box.tag_cget(name, 'rmargin')))
            body = width - left - right
            self.assertGreater(body, 0, name + ' 的气泡正文宽度必须为正')
            self.assertLessEqual(body, width, name + ' 的气泡不得宽过对话区')
        # 真几何：用户气泡正文首像素落在模型气泡右侧。
        user_x = self.bbox_x(box, 'bubble_0.first')
        model_x = self.bbox_x(box, 'bubble_1.first')
        self.assertIsNotNone(user_x, '用户气泡应落在可视区内')
        self.assertIsNotNone(model_x, '模型气泡应落在可视区内')
        self.assertGreater(user_x, model_x, '用户气泡排在模型气泡右侧')
        # 契约（REQ-S01-65）：左右分列只由边距决定，正文与署名一律左对齐，符合阅读习惯。
        for name in ('bubble_0', 'bubble_1'):
            self.assertEqual(str(box.tag_cget(name, 'justify')), 'left', name + ' 的正文左对齐')
        self.assertEqual(str(box.tag_cget('bubble_0_meta', 'justify')), 'left', '用户气泡署名左对齐')
        # 选区优先级：淡底气泡 tag 不得盖住 sel——重绘后 sel 必须仍在气泡 tag 之上。
        # Tk 的 tag_names() 越靠后优先级越高；tag_raise('sel') 后 sel 应在列表末尾（最高）。
        names = box.tag_names()
        sel_at = names.index('sel') if 'sel' in names else -1
        bubble_at = next((i for i, n in enumerate(names) if n == 'bubble_1'), -1)
        self.assertGreaterEqual(sel_at, 0, 'sel 是内置 tag，必然存在')
        self.assertGreater(sel_at, bubble_at, 'sel 优先级须高于气泡淡底 tag，选区高亮不被底色盖住')

    def test_req_s01_01_idea_messages_render_as_bubbles_and_survive_restart(self):
        """REQ-S01-01：创意对话按气泡渲染；销毁界面、用同一目录重建后仍按原顺序出现。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            # 数据只走现有持久化接口，落在临时项目里。
            idea_chat.append(proj, 'user', self.USER)
            idea_chat.append(proj, 'assistant', self.MODEL)
            d, win = self.desktop(proj)
            d.show(0)
            self.settle_bubbles(d, win)
            self.assert_rendered_bubbles(d.idea_log)
            # 模拟重启：销毁界面，用同一目录重建，两只气泡按原顺序回来。
            win.destroy()
            d2, win2 = self.desktop(proj)
            d2.show(0)
            self.settle_bubbles(d2, win2)
            self.assert_rendered_bubbles(d2.idea_log)


if __name__ == '__main__':
    unittest.main()
