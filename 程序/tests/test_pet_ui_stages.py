# -*- coding: utf-8 -*-
"""宠物贴片自检（阶段推进、一键执行、批量派发、对话落地与自动启动）：自原 test_pet_ui.py 按测试类拆分，断言与夹具原样保留。"""
import json
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if PROGRAM not in sys.path:
    sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

from pet_ui_test_support import (
    _Event,
    PetTestCase,
)
import pet_agent
import pet_bus
import stage_flow
from ui import pet_ask
from ui import pet_cloud
import ui.pet_ui_support as pet_ui_support
import ui.pet_ui as pet_ui
import selftest_sandbox

selftest_sandbox.isolate(pet_ui)

class OneClickTests(PetTestCase):
    """一键执行：只重试失败项与出日报，不碰任何会产生费用的按钮。"""

    def test_with_nothing_to_do_it_says_so(self):
        text = self.pet.one_click()
        self.assertIn('日报已生成', text)
        self.assertEqual(self.fake.kicks, [])

    def test_failures_are_retried_first(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        text = self.pet.one_click()
        self.assertIn('已重试失败项', text)
        self.assertNotIn('pet', self.fake.kicks)
        self.assertIn('keyframe', self.fake.advances)
        self.assertEqual(self.pet.agent.failures, [])

    def test_missing_first_frames_are_reported_without_generating(self):
        work = self.fake.root / 'storyboard' / '分镜拆分'
        work.mkdir(parents=True)
        (work / 'EP001_分镜.json').write_text(json.dumps(
            {'episode_id': 'EP001', 'shots': [{'id': 'SH001'}, {'id': 'SH002'}]},
            ensure_ascii=False), encoding='utf-8')
        text = self.pet.one_click()
        self.assertIn('首帧还差 2 个镜头', text)

    def test_the_daily_report_is_written(self):
        self.pet.one_click()
        self.assertTrue(self.pet.report_path.is_file())

    def test_the_notice_is_stored_for_the_bubble(self):
        text = self.pet.one_click()
        self.assertEqual(self.pet.notice, text)

    def test_it_is_reachable_from_the_one_click_intent(self):
        self.assertEqual(self.pet.click('oneclick'), self.pet.notice)

    def test_a_broken_ledger_does_not_stop_the_report_step(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.assertEqual(self.pet.click('oneclick'), self.pet.notice)
        self.assertTrue(self.pet.report_path.is_file())


class OneClickOfferTests(PetTestCase):
    """第 25 期第 3 条：三虎看着制作进度，到了该收尾的时候主动问一句，并把选择项摆出来。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.gaps = []
        self.pet.gaps = lambda at=None: tuple(self.gaps)
        self.asked = []
        self.pet.asker = lambda title, text: self.asked.append(title) or True

    def offer(self):
        return self.pet.offer_oneclick(at=self.now)

    def arm(self, parts=('首帧还差 6 个镜头',)):
        """先空对一次表（开机那一下盘上还没缺口），再让缺口出现并等过节流——真跑起来就是这条路。"""
        self.offer()
        self.now += pet_ui.OFFER_SECONDS + 1
        self.gaps = list(parts)
        return self.offer()

    def test_nothing_to_offer_means_silence(self):
        self.assertEqual(self.offer(), '', '盘上没有缺口就不打扰')
        self.assertFalse(self.pet.cloud_visible())

    def test_the_first_tick_only_takes_notes(self):
        self.gaps = ['3 份分镜 JSON 还没采用']
        self.assertEqual(self.offer(), '', '开机第一拍只对表，不许冒东西')
        self.assertFalse(self.pet.cloud_visible())
        self.assertEqual(self.pet.offer.sig, ('3 份分镜 JSON 还没采用',), '指纹先记下来')
        self.now += pet_ui.OFFER_REPEAT + 1
        self.assertTrue(self.offer(), '同一批缺口闷久了也要提一次')

    def test_a_new_gap_is_asked_about_after_the_throttle(self):
        text = self.arm()
        self.assertIn('一键执行', text)
        self.assertIn('首帧还差 6 个镜头', text)
        self.assertTrue(text.startswith('【阶段'))
        self.assertIn(pet_agent.PET_NAME + '：', text)
        self.assertTrue(self.pet.cloud_visible(), '问出来就得让用户看见')

    def test_the_same_gap_is_not_asked_twice_in_a_row(self):
        self.arm()
        self.now += pet_ui.OFFER_SECONDS + 1
        self.assertEqual(self.offer(), '', '同一批缺口不追着问')

    def test_question_uses_current_level_color(self):
        """待确认的问题采用当前自动化等级的颜色。"""
        self.arm()
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        self.assertEqual(cloud.edge(), pet_cloud.PET_PALETTE['level_' + self.pet.agent.level + '_outline'])

    def test_the_question_lists_the_choices(self):
        self.arm()
        self.assertIn('回「好」', self.pet.cloud().transcript(), '要写清楚怎么答')
        self.assertIn('先不用', self.pet.cloud().transcript())
        self.assertTrue(self.pet.offer.open, '问题挂着，用户才好回话')

    def test_pending_failures_count_as_a_reason_to_ask(self):
        self.offer()                                     # 先对表（这会儿还没有失败项）
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.now += pet_ui.OFFER_SECONDS + 1
        self.assertIn('待确认', self.offer())

    def test_saying_yes_runs_the_one_click_once(self):
        self.arm()
        result = self.pet.answer_offer('好')
        self.assertIsNotNone(result)
        self.assertTrue(result['decision']['run'])
        self.assertEqual(result['plan']['intent'], 'oneclick')
        self.assertTrue(result['plan']['params']['confirmed'], '气泡里点过头就不再弹第二次确认窗')
        self.assertFalse(self.pet.offer.open, '答过就不再挂着')
        self.pet.run_plan(result)
        self.assertEqual(self.asked, [], '已经答过「好」，不许再弹一个确认窗')
        self.assertIn('日报', self.pet.notice)
        self.assertTrue(self.pet.report_path.is_file())

    def test_saying_no_changes_nothing(self):
        self.arm()
        result = self.pet.answer_offer('先不用')
        self.assertIsNotNone(result)
        self.assertFalse(result['decision']['run'])
        self.assertEqual(result['plan'], {})
        self.assertIsNone(self.pet.report_path, '说不做就一件都不做（日报不落盘）')

    def test_an_unrelated_sentence_falls_through_to_the_rules(self):
        self.arm()
        self.assertIsNone(self.pet.answer_offer('帮我把首帧生成一下'), '没认出来就交给规则表')
        self.assertTrue(self.pet.offer.open, '这句话不算回答，问题还挂着')

    def test_a_stray_yes_is_not_an_answer_when_nothing_was_asked(self):
        self.assertIsNone(self.pet.answer_offer('好'), '没问过的时候，「好」不能当成开工')

    def test_the_cloud_hands_the_answer_back_to_the_pet(self):
        """真路径：云朵框把用户那句话交回宠物时，先经过 answer_offer（见 Cloud.ask）。"""
        self.arm()
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.ask('好')
        cloud.drain()
        self.assertIn('日报', self.pet.notice)
        self.assertEqual(self.asked, [])


class FirstFrameBatchTests(PetTestCase):
    """首帧缺口接进自动链路：宠物只说缺口，派发交给宿主，绝不碰付费通道。"""

    def test_without_the_seam_nothing_is_said(self):
        self.assertEqual(self.pet.firstframe_batch(), "")
        self.assertEqual(self.fake.kicks, [])

    def test_the_seam_is_called_from_the_one_click(self):
        calls = []
        self.fake.pet_frame_batch = lambda: calls.append(1) or "已按分镜顺序派发 2 镜首帧"
        text = self.pet.one_click()
        self.assertIn("已按分镜顺序派发 2 镜首帧", text)
        self.assertEqual(len(calls), 1)

    def test_an_empty_answer_adds_no_step(self):
        self.fake.pet_frame_batch = lambda: ""
        self.assertNotIn("首帧", self.pet.one_click())

    def test_a_broken_seam_is_recorded_not_raised(self):
        def boom():
            raise RuntimeError("派发坏了")
        self.fake.pet_frame_batch = boom
        self.assertIn("首帧批次未派发", self.pet.one_click())
        self.assertTrue(any(item[0] == "firstframe" for item in self.pet.errors))

    def test_the_one_click_stays_off_the_paid_channels(self):
        self.fake.pet_frame_batch = lambda: "已按分镜顺序派发 1 镜首帧（本地 ComfyUI 免费后端）"
        text = self.pet.one_click()
        for word in ("Seedream", "火山", "云端", "付费引擎"):
            self.assertNotIn(word, text, "一键执行不能碰会产生费用的通道")


class StoryboardBatchTests(PetTestCase):
    """第 62 期任务 2：三虎也能自己把分镜做起来——派发交给宿主，没有输入就退回「叫醒一轮」。"""

    def test_without_the_seam_it_falls_back_to_waking_the_poller(self):
        self.assertEqual(self.pet.storyboard_batch(), "")
        text = self.pet.generate("storyboard")
        self.assertIn("提前叫醒一轮", text)
        self.assertEqual(self.fake.advances, ["storyboard"])

    def test_the_seams_words_are_used_when_it_dispatches(self):
        self.fake.pet_storyboard_batch = lambda: "已经在准备分镜任务：2 份输入交给 Agent"
        text = self.pet.generate("storyboard")
        self.assertIn("已经在准备分镜任务", text)
        self.assertEqual(self.fake.advances, [], "派上了就不用再叫醒自动采用")

    def test_an_empty_answer_falls_back_instead_of_saying_nothing(self):
        self.fake.pet_storyboard_batch = lambda: ""
        text = self.pet.generate("storyboard")
        self.assertEqual(self.fake.advances, ["storyboard"])
        self.assertTrue(text)

    def test_a_broken_seam_is_recorded_not_raised(self):
        def boom():
            raise RuntimeError("派发坏了")
        self.fake.pet_storyboard_batch = boom
        text = self.pet.generate("storyboard")
        self.assertIn("分镜批次未派发", text)
        self.assertTrue(any(item[0] == "storyboard" for item in self.pet.errors))


class ChatCoordinationFailureTests(PetTestCase):
    """R1073：迁移前冻结 G3 的异常顺序，不借重构修行为。"""

    def test_schedule_failure_records_error_and_flips_immediately(self):
        from unittest.mock import patch
        with patch.object(self.win, 'after', side_effect=RuntimeError('schedule failed')), \
                patch.object(self.pet, 'open_chat', return_value='opened') as opened:
            self.assertEqual(self.pet.pet_click(), 'opened')
        opened.assert_called_once_with()
        self.assertIsNone(self.pet._click_at)
        self.assertIn(('click', 'schedule failed'), self.pet.errors)

    def test_cancel_tcl_failure_clears_pending_and_returns_job(self):
        from unittest.mock import patch
        job = self.pet.pet_click()
        with patch.object(self.win, 'after_cancel', side_effect=self.tk.TclError('gone')):
            self.assertEqual(self.pet.cancel_click(), job)
        self.assertIsNone(self.pet._click_at)
        self.win.after_cancel(job)

    def test_cancel_other_failure_propagates_after_clearing_pending(self):
        from unittest.mock import patch
        job = self.pet.pet_click()
        with patch.object(self.win, 'after_cancel', side_effect=ValueError('bad cancel')):
            with self.assertRaisesRegex(ValueError, 'bad cancel'):
                self.pet.cancel_click()
        self.assertIsNone(self.pet._click_at)
        self.win.after_cancel(job)

    def test_repeated_single_click_replaces_the_pending_job(self):
        first = self.pet.pet_click()
        second = self.pet.pet_click()
        self.assertNotEqual(first, second)
        self.assertEqual(self.pet._click_at, second)
        scheduled = self.win.tk.call('after', 'info')
        self.assertNotIn(first, scheduled)
        self.assertIn(second, scheduled)

    def test_child_destroy_does_not_close_or_cancel(self):
        self.pet.open_chat()
        job = self.pet.pet_click()
        self.pet.step()
        animation = self.pet._timer
        child = _Event(self.pet.canvas)
        self.assertIsNone(self.pet.stop(child))
        self.assertIsNone(self.pet.close_chat(child))
        self.assertTrue(self.pet.cloud().visible)
        self.assertIsNotNone(self.pet.chat)
        self.assertEqual(self.pet._click_at, job)
        self.assertEqual(self.pet._timer, animation)

    def test_stop_close_failure_preserves_animation_but_cancels_click(self):
        from unittest.mock import patch
        self.pet.open_chat()
        self.pet.pet_click()
        self.pet.step()
        animation = self.pet._timer
        with patch.object(self.pet.cloud(), 'close', side_effect=RuntimeError('close failed')):
            with self.assertRaisesRegex(RuntimeError, 'close failed'):
                self.pet.stop()
        self.assertIsNone(self.pet._click_at)
        self.assertEqual(self.pet._timer, animation)
        self.assertIn(animation, self.win.tk.call('after', 'info'))

    def test_late_callback_after_cancel_failure_keeps_legacy_behavior(self):
        from unittest.mock import patch
        callbacks = []
        def schedule(delay, callback):
            callbacks.append(callback)
            return 'pending'
        with patch.object(self.win, 'after', side_effect=schedule), \
                patch.object(self.win, 'after_cancel', side_effect=self.tk.TclError('gone')), \
                patch.object(self.pet, 'open_chat', return_value='opened') as opened:
            self.assertEqual(self.pet.pet_click(), 'pending')
            self.assertEqual(self.pet.cancel_click(), 'pending')
            self.assertEqual(callbacks[0](), 'opened')
        opened.assert_called_once_with()
        self.assertIsNone(self.pet._click_at)


class ConfirmTests(PetTestCase):
    """第 16 期：三虎要用户点头的事，以通知气泡显现（有按钮的那种优先）。"""

    class FakeToast:
        """假自绘气泡：只记「弹了什么」，不建真窗口。"""

        def __init__(self):
            self.shown = []

        def show(self, text, title=None):
            self.shown.append((title, text))
            return True

        def close(self):
            return True

    def test_a_confirmation_speaks_through_the_cloud(self):
        self.assertTrue(self.pet.confirm('这一步要花 3 元，确认吗？'))
        cloud = self.pet.cloud()
        self.assertTrue(cloud.visible, '要用户点头的事必须当场说出来')
        self.assertIn('要花 3 元', cloud.transcript())

    def test_a_confirmation_is_recorded_in_the_cloud_too(self):
        self.pet.confirm('这一步要花 3 元，确认吗？')
        self.assertIn('要花 3 元', self.pet.cloud().transcript())

    def test_snoozing_keeps_the_bubble_quiet_but_still_records(self):
        self.pet.snooze(600)
        self.pet.confirm('这一步要花 3 元，确认吗？')
        self.assertFalse(self.pet.cloud().visible, '安静时段不冒框')
        self.assertIn('要花 3 元', self.pet.cloud().transcript(), '但记录里要有')


class ProgressFeedbackTests(PetTestCase):
    """第 16 期：一键执行这类跑在页面之外的活儿，进度写进主界面状态栏，别让用户找不到。"""

    def test_the_one_click_writes_where_the_work_is_running(self):
        self.pet.one_click()
        self.assertIn('一键执行', self.fake.status.get())
        self.assertIn('一键执行', self.pet.notice)

    def test_a_progress_line_lands_on_the_status_bar(self):
        self.assertEqual(self.pet.show_progress('正在补首帧'), '正在补首帧')
        self.assertEqual(self.fake.status.get(), '正在补首帧')

    def test_without_a_status_bar_the_line_falls_back_to_the_cloud(self):
        self.fake.status = None
        self.pet.show_progress('正在补首帧')
        self.assertEqual(self.pet.notice, '正在补首帧')


class ConfirmStartTests(PetTestCase):
    """第 18 期：一键执行前先弹一块确认框，用户点「否」就什么都不做。"""

    def test_the_dialog_asks_before_the_automatic_run(self):
        seen = []

        def asker(title, text):
            seen.append((title, text))
            return True

        self.pet.asker = asker
        text = self.pet.one_click()
        self.assertEqual(seen[0][0], pet_ui.ONE_CLICK_TITLE)
        self.assertIn('自动制图', seen[0][1])
        self.assertIn('日报已生成', text, '点了「是」照常跑')

    def test_answering_no_does_nothing(self):
        self.pet.asker = lambda title, text: False
        text = self.pet.one_click()
        self.assertIn('已取消', text)
        self.assertEqual(self.fake.kicks, [])
        self.assertIsNone(self.pet.report_path, '点「否」就不该落盘')

    def test_a_broken_dialog_does_not_block_the_run(self):
        def boom(title, text, parent=None):
            raise RuntimeError('弹不出来')

        self.pet.asker = boom
        self.assertIn('日报已生成', self.pet.one_click())
        self.assertTrue(any(name == 'ask' for name, _text in self.pet.errors))


class ReplyBoxTests(PetTestCase):
    """第 35 期第 2 条：那颗「确认」按钮点了没反应——整颗删掉，聊天框这一行留给回复框。

    用户在这儿回一句（回车发送）就走原来那条路：三虎有待办就照待办办，没有就办「这一页该做
    的那件事」。第 29 期第 5 条那颗按钮的判据一条都没丢，换的只是入口。
    """

    def test_the_row_has_a_reply_box_and_no_confirm_button(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        self.assertIsNotNone(cloud.reply, '回复框要真的建出来')
        self.assertEqual(cloud.reply.winfo_class(), 'TEntry')
        self.assertTrue(cloud.reply.bind('<Return>'), '回车要真的挂上发送')
        self.assertFalse(hasattr(cloud, 'confirm_button'), '点了没反应的那颗按钮要整颗删掉')
        self.assertFalse(hasattr(pet_cloud, 'CONFIRM_TEXT'), '它的文案也不留')
        self.assertFalse(hasattr(pet_cloud, 'SEND_TEXT'), '「发送」那套文案也不留')

    def test_the_reply_box_sends_what_the_user_typed(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose('查一下进度')
        cloud.reply.insert(0, '  按你这句办  ')
        self.addCleanup(self.wait_for_the_reply, cloud)
        self.assertEqual(cloud.submit(), '按你这句办', '回复框里写的字就是发出去的那句')
        self.assertIn('您：按你这句办', cloud.transcript(), '说过的话要留在记录里')
        self.assertEqual(cloud.reply.get(), '', '发出去就清空，等着下一句')

    def test_an_empty_reply_box_falls_back_to_what_the_pet_asked(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose('查一下进度')
        self.addCleanup(self.wait_for_the_reply, cloud)
        self.assertEqual(cloud.submit(), '查一下进度', '空着回车＝原来按一下确认')

    def test_the_reply_box_is_locked_while_the_pet_is_thinking(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose('查一下进度')
        cloud.submit()
        self.assertTrue(cloud.busy)
        self.assertTrue(cloud.reply.instate(['disabled']), '回话期间不许再发一句')
        deadline = time.time() + 5.0            # 后台那句想完才落地：心跳到账就解锁
        while time.time() < deadline and cloud.busy:
            cloud.drain()
            time.sleep(0.01)
        self.assertFalse(cloud.busy, '5 秒内该回完')
        self.assertFalse(cloud.reply.instate(['disabled']), '回完就把回复框放开')

    def test_the_copy_button_and_its_helper_are_gone(self):
        """第 24 期第 3 条：聊天框里的「复制」整个删掉（按钮、方法、文案一起清）。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        self.assertFalse(hasattr(cloud, 'copy'), '实现要一起删干净')
        self.assertFalse(hasattr(pet_cloud, 'COPIED'), '文案也不留')
        labels = [child.cget('text') for child in cloud.chat_row.winfo_children()
                  if child.winfo_class() == 'TButton']
        self.assertNotIn('复制', labels)

    def test_the_reply_box_fills_the_row(self):
        """这一行只有回复框一个控件，铺满整行（原来那颗按钮也是铺满的）。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        self.win.update()
        row = cloud.chat_row
        children = row.winfo_children()
        self.assertIn(cloud.reply, children, '回复框铺满这一行')
        self.assertEqual([child for child in children if child is not cloud.reply], [cloud.hint],
                         '这一行只有回复框与那条滚动小字')
        self.assertLessEqual(cloud.reply.winfo_reqwidth(), row.winfo_width() + 1)
        self.assertGreaterEqual(row.winfo_width(), pet_cloud.ROW_H * 2)

    def test_the_style_paints_on_the_accent_colour(self):
        """另开一个 Tk 解释器上主题：样式表是分解释器的，这样不打扰别的用例。"""
        import ui_theme
        from tkinter import ttk
        other = self.tk.Tk()
        other.withdraw()
        try:
            ui_theme.apply(other)
            style = ttk.Style(other)
            self.assertEqual(str(style.configure('Send.TButton', 'fill')), ui_theme.ACCENT)
            self.assertEqual(other.winfo_rgb(str(style.configure('Send.TButton','foreground'))), other.winfo_rgb('white'))
        finally:
            other.destroy()


class ConfirmDoesTheTaskTests(PetTestCase):
    """第 31 期第 6 条留下的口径：空待办时按「这一页该做的事」办，用户这一下＝本人授权。

    第 35 期第 2 条把入口从「确认」按钮换成回复框（那颗按钮点了没反应，整颗删掉了）——
    判据一条没改：空着回车就现场问一次「这一页该做什么」。
    """

    def test_an_empty_confirm_runs_the_page_task(self):
        self.fake.page_index = 5
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose('')
        self.addCleanup(self.wait_for_the_reply, cloud)
        self.assertEqual(cloud.page_ask(), pet_ui.PAGE_ASKS[5][1], '问的是当前这一页')
        self.assertEqual(cloud.submit(), pet_ui.PAGE_ASKS[5][1])
        self.assertIn('您：' + pet_ui.PAGE_ASKS[5][1], cloud.transcript())

    def test_nothing_to_do_still_falls_back_to_the_old_line(self):
        """连这一页该做的事都问不出来，才退回第 29 期那句说明——回复框至少回一句人话。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose('')
        original = self.pet.chat_task
        self.pet.chat_task = lambda index=None: ('', '')
        self.addCleanup(setattr, self.pet, 'chat_task', original)
        self.assertEqual(cloud.submit(), '')
        self.assertEqual(cloud.status.cget('text'), pet_cloud.EMPTY)

    def test_the_cloud_sends_the_confirmation_flag(self):
        cloud = self.pet.cloud()
        agent = self.pet.agent
        seen = []
        original = agent.dispatch

        def spy(text, at=None, confirmed=False):
            seen.append(confirmed)
            return original(text, at=at, confirmed=confirmed)

        agent.dispatch = spy
        self.addCleanup(setattr, agent, 'dispatch', original)
        cloud.dispatch('执行选中')
        self.assertEqual(seen, [True], '按下确认发出去的那一句带 confirmed')

    def test_an_older_dispatch_without_the_flag_still_works(self):
        """认不出 confirmed 的实现（老接口、假宠物）照旧只吃一句话，不该炸。"""
        cloud = self.pet.cloud()
        agent = self.pet.agent
        original = agent.dispatch
        agent.dispatch = lambda text: {'plan': {'intent': 'progress'}, 'decision': {'run': True}}
        self.addCleanup(setattr, agent, 'dispatch', original)
        self.assertEqual(cloud.dispatch('查一下进度')['plan']['intent'], 'progress')

    def test_the_cloud_comes_back_on_top_when_it_pops_up(self):
        """云被别人压住时按钮点不到：每次冒出来都要重新压一遍置顶。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.win.attributes('-topmost', False)          # 假装被别的窗口压下去
        self.assertFalse(bool(cloud.win.attributes('-topmost')))
        cloud.show(pinned=True)
        self.assertTrue(cloud.win.attributes('-topmost'),
                        '每次冒出来都要重新压一遍置顶，否则按钮点不到')

    def test_the_pages_confirm_routes_to_the_pages_stage(self):
        """S-03：「视频生成」页空着回车，派发带上 'video'——不是状态机当下停着的那一步。"""
        self.fake.page_index = list(pet_bus.STAGES).index('video')
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose(pet_ui.PAGE_ASKS[self.fake.page_index][1], stage='video')
        seen = []
        original = self.pet.agent.dispatch

        def spy(text, at=None, confirmed=False, stage=None):
            seen.append(stage)
            return original(text, at=at, confirmed=confirmed, stage=stage)

        self.pet.agent.dispatch = spy
        self.addCleanup(setattr, self.pet.agent, 'dispatch', original)
        self.addCleanup(self.wait_for_the_reply, cloud)
        self.assertEqual(cloud.submit(), '执行选中')
        deadline = time.time() + 5
        while cloud.busy and time.time() < deadline:
            cloud.drain()
            time.sleep(0.01)
        self.assertEqual(seen, ['video'], '记下的问句带着页的阶段一路进 dispatch')
        self.assertEqual(self.pet.agent.decisions[-1]['stage'], 'video',
                         '路由按问句带来的阶段走，不按状态机')

    def test_a_typed_sentence_keeps_the_state_machine_stage(self):
        """S-03：手打的句子不带 stage——照旧按状态机当前阶段路由。"""
        self.fake.page_index = list(pet_bus.STAGES).index('video')
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose(pet_ui.PAGE_ASKS[self.fake.page_index][1], stage='video')
        seen = []
        original = self.pet.agent.dispatch

        def spy(text, at=None, confirmed=False, stage=None):
            seen.append(stage)
            return original(text, at=at, confirmed=confirmed, stage=stage)

        self.pet.agent.dispatch = spy
        self.addCleanup(setattr, self.pet.agent, 'dispatch', original)
        self.addCleanup(self.wait_for_the_reply, cloud)
        cloud.reply.insert(0, '现在到哪一步了')
        cloud.submit()
        deadline = time.time() + 5
        while cloud.busy and time.time() < deadline:
            cloud.drain()
            time.sleep(0.01)
        self.assertEqual(seen, [None], '手打句子不带 stage，照旧用状态机当前阶段')


class ChatLandsTests(PetTestCase):
    """第 23 期：对话不能只出一句结论——「听懂了」之后要真的做掉那一步。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def plan(self, text):
        """走一遍真实链路：问一句 → 拿到结论 → 在界面线程落地。"""
        result = self.pet.agent.dispatch(text)
        return result, self.pet.run_plan(result)

    def test_an_instruction_to_switch_pages_really_switches(self):
        self.pet.agent.set_level('semi')
        _result, done = self.plan('打开剪辑')
        self.assertEqual(self.fake.pages, ['edit'], '说了要切页就得真切')
        self.assertIn('已切到', done or self.pet.notice)

    def test_a_page_switch_needs_no_permission_at_all(self):
        """切页是「看一眼」：只提醒那档也得立刻生效，不然用户什么都做不了。"""
        self.pet.agent.set_level('hint')
        self.assertEqual(self.pet.agent.level, 'hint')
        self.plan('打开首帧管理')
        self.assertEqual(self.fake.pages, ['keyframe'])

    def test_a_read_only_question_is_answered_in_every_level(self):
        self.pet.agent.set_level('hint')
        result = self.pet.agent.dispatch('现在到哪一步了')
        self.assertTrue(result['decision']['run'], '查进度不该被等级挡住')
        self.assertEqual(result['decision']['reason'], '')
        self.assertNotIn('只提醒', result['reply'], '能做的事不拖一句等级后缀')

    def test_a_step_that_costs_money_still_waits_for_a_nod(self):
        """会产生费用的那几步照旧不代按：只提醒档下连结论都不放行。"""
        self.pet.agent.set_level('hint')
        result, _done = self.plan('批量生成全部视频')
        self.assertFalse(result['decision']['run'])
        self.assertEqual(self.fake.advances, [])
        self.assertIn('不自动执行', result['reply'])

    def test_saying_the_level_out_loud_switches_it(self):
        self.pet.agent.set_level('hint')
        self.plan('切到全自动')
        self.assertEqual(self.pet.agent.level, 'auto')
        self.assertIn('全自动', self.pet.notice)

    def test_half_auto_runs_the_free_firstframe_path(self):
        """半自动＝免费步骤自动跑：首帧走本机 ComfyUI，说一句就该真的派单。"""
        self.pet.agent.set_level('semi')
        seen = []
        self.fake.pet_frame_batch = lambda: seen.append('batch') or '已按分镜顺序派发 2 镜首帧'
        result, done = self.plan('批量生成全部首帧')
        self.assertTrue(result['decision']['run'])
        self.assertEqual(seen, ['batch'])
        self.assertIn('首帧', done or '')

    def test_an_intent_nobody_registered_touches_nothing(self):
        result = {'plan': {'intent': '和猫跳舞', 'stage': None, 'params': {}},
                  'decision': {'run': True, 'reason': ''}, 'reply': '好'}
        self.assertEqual(self.pet.run_plan(result), '')
        self.assertEqual(self.fake.pages, [])
        self.assertEqual(self.fake.advances, [])

    def test_a_refused_step_never_touches_anything(self):
        result = {'plan': {'intent': 'generate', 'stage': 'video', 'params': {}},
                  'decision': {'run': False, 'reason': '只提醒模式：不自动执行'}, 'reply': '开始批量生成视频。'}
        self.assertEqual(self.pet.run_plan(result), '')
        self.assertEqual(self.fake.pages, [], '没放行就不许动手')

    def test_a_broken_step_is_recorded_not_raised(self):
        def boom(stage):
            raise RuntimeError('翻页坏了')

        self.fake.pet_goto = boom
        result = {'plan': {'intent': 'goto', 'stage': 'edit', 'params': {}},
                  'decision': {'run': True, 'reason': ''}, 'reply': '好'}
        self.assertTrue(self.pet.run_plan(result), '翻不动也要回一句人话')
        self.assertTrue(any(name == 'goto' for name, _text in self.pet.errors))

    def test_an_unexpected_plan_failure_is_visible_and_recorded(self):
        def boom():
            raise RuntimeError('面板初始化失败')

        self.pet.show_panel = boom
        result = {'plan': {'intent': 'panel', 'stage': None, 'params': {}},
                  'decision': {'run': True, 'reason': ''}, 'reply': '好'}
        self.assertEqual(self.pet.run_plan(result), '操作未完成，请稍后重试。')
        self.assertEqual(self.pet.notice, '操作未完成，请稍后重试。')
        self.assertTrue(any(name == 'run_plan' for name, _text in self.pet.errors))

    def test_cloud_shows_a_fallback_when_a_host_run_plan_raises(self):
        cloud = self.pet.cloud()

        def boom(_result):
            raise RuntimeError('替换宿主执行失败')

        self.pet.run_plan = boom
        cloud.queue.put({'text': '打开面板', 'lines': ['三虎：好的'], 'result': {}})
        self.assertEqual(cloud.drain(), 1)
        self.assertIn('操作未完成，请稍后重试。', cloud.transcript())
        self.assertTrue(any(name == 'run' for name, _text in cloud.errors))

    def test_the_whole_chat_path_lands_the_step_and_says_so(self):
        """真链路：回复框 → 后台结论 → 心跳落地，记录里看得到「已经切过去了」。"""
        self.assertIsNotNone(self.pet.open_chat())
        cloud = self.pet.cloud()
        self.pet.agent.set_level('semi')
        cloud.propose('打开资产管理')
        self.assertEqual(cloud.submit(), '打开资产管理')
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if self.pet.chat_drain():
                break
            time.sleep(0.01)
        else:
            self.fail('云朵框没等到回复')
        self.assertEqual(self.fake.pages, ['assets'])
        self.assertIn('已切到', cloud.transcript())


class AdvanceTests(PetTestCase):
    """第 23 期：Agent.advance() 从「只有用例在调」变成真的接上心跳。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def up_to_script_structure(self):
        self.pet.machine.start('script')
        self.pet.machine.complete('script')

    def test_the_next_step_is_woken_up_when_the_level_allows(self):
        self.pet.agent.set_level('semi')
        self.up_to_script_structure()
        self.assertEqual(self.pet.tune_advance(at=self.now), '',
                         '开机第一拍只叫醒，不出声（第 44 期：默认半自动，别在开机那一下冒云）')
        self.assertEqual(self.fake.advances, ['script_structure'], '下一步必须先做剧本结构')
        text = self.pet.tune_advance(at=self.now + pet_ui.ADVANCE_SECONDS + 1)
        self.assertIn('剧本结构', text, '下一拍照旧把这一步念一遍')

    def test_hint_level_never_wakes_anything(self):
        # 第 44 期：开机默认是半自动了（附件关键决策第 5 条），这一条验的是「只提醒档不叫醒任何东西」，
        # 所以显式点名那一档；默认档叫不叫醒放在 DefaultLevelTests 里验。
        self.pet.agent.set_level('hint')
        self.assertEqual(self.pet.agent.level, 'hint')
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, [])

    def test_a_paused_or_silenced_pet_does_not_wake_anything(self):
        self.pet.agent.set_level('auto')
        self.pet.agent.pause('歇会儿')
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.pet.agent.resume()
        self.pet.snooze()
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, [])

    def test_an_open_dialog_does_not_wake_anything(self):
        self.pet.agent.set_level('auto')
        self.pet.cloud().show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, [])

    def test_the_wake_up_is_throttled_and_said_once(self):
        self.pet.agent.set_level('semi')
        self.up_to_script_structure()
        self.pet.tune_advance(at=self.now)          # 开机第一拍：只叫醒，不出声（第 44 期）
        said = self.now + pet_ui.ADVANCE_SECONDS + 1
        self.assertIn('剧本结构', self.pet.tune_advance(at=said))
        self.assertEqual(self.pet.tune_advance(at=said + 1), '', '节流窗口里不再问宿主一次')
        self.assertEqual(len(self.fake.advances), 2, '开机那一拍＋念的这一次')
        self.pet.cloud().close()                   # 上一句播报的云先收起来
        later = said + pet_ui.ADVANCE_SECONDS + 1
        self.assertEqual(self.pet.tune_advance(at=later), '', '同一句不重复念')
        self.assertEqual(len(self.fake.advances), 3, '该叫醒还是要叫醒，只是不再说一遍')

    def test_a_step_without_an_unattended_path_is_left_alone(self):
        self.pet.agent.set_level('semi')
        self.fake.deaf = ('script',)
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, [])

    def test_it_rides_the_existing_heartbeat(self):
        """推进挂在既有 150ms 心跳里，不额外开线程、不加新轮询。"""
        self.pet.agent.set_level('semi')
        self.pet.pump()
        self.assertEqual(self.fake.advances, ['script'], '心跳里就该顺手把下一步叫醒')


class PageAskTests(PetTestCase):
    """第 29 期第 5 条：三虎主动问「当前这一页该做的事」，问句与那件事一起给（第 35 期第 2 条起
    放在回复框上：空着回车就办它）。"""

    def test_every_production_page_has_its_own_question(self):
        import desktop
        self.assertEqual(len(pet_ui.PAGE_ASKS), len(desktop.PAGES) - 1,
                         '11 个制作阶段各一句；第 12 页参考网站走兜底那一句')
        asks = [ask for ask, _command in pet_ui.PAGE_ASKS]
        self.assertEqual(len(set(asks)), len(asks), '一页一句，不重样')
        for ask, command in pet_ui.PAGE_ASKS:
            with self.subTest(ask=ask):
                self.assertTrue(command, '每一句都要配一件照着做的事')
                self.assertTrue(ask.startswith('要不要'), '问句就一句问：%s' % ask)
                self.assertTrue(ask.endswith('？'), '是一句问句')

    def test_every_question_only_talks_about_the_work(self):
        """第 37 期第 5 条：不问自答「这是第几页」——只问用户要不要做这件事。"""
        for ask, _command in pet_ui.PAGE_ASKS + (pet_ui.FALLBACK_ASK,):
            with self.subTest(ask=ask):
                self.assertNotIn('这页', ask, '不许报页码：%s' % ask)
                self.assertNotIn('换到', ask, '不许说切到哪一页：%s' % ask)
                self.assertNotIn(pet_agent.PET_NAME, ask, '名字由说话那一路补，问句里不带')
                self.assertLessEqual(len(ask), 40, '一句话读得完：%s' % ask)

    def test_the_question_follows_the_current_page(self):
        self.fake.page_index = list(pet_bus.STAGES).index('keyframe')
        ask, command = self.pet.chat_task()
        self.assertIn('首帧', ask)
        self.assertEqual((ask, command), pet_ui.PAGE_ASKS[self.fake.page_index])

    def test_a_page_without_a_stage_falls_back(self):
        self.fake.page_index = len(pet_ui.PAGE_ASKS)
        self.assertEqual(self.pet.chat_task(), pet_ui.FALLBACK_ASK)

    def test_a_broken_page_index_still_asks_something(self):
        self.fake.page_index = '不是个页号'
        self.assertEqual(self.pet.chat_task(), pet_ui.PAGE_ASKS[0])

    def test_opening_the_chat_hands_the_task_to_the_reply_box(self):
        self.fake.page_index = list(pet_bus.STAGES).index('keyframe')
        cloud = self.pet.cloud()
        self.assertIsNotNone(self.pet.open_chat())
        self.assertIsNotNone(cloud.reply, '开对话框就有回复框')
        self.assertEqual(cloud.choice, pet_ui.PAGE_ASKS[self.fake.page_index][1], '空着回车发出去的就是这一页那件事')
        line = cloud.lines[-1]
        self.assertFalse(line.startswith('【阶段'), line)
        self.assertIn(pet_agent.PET_NAME + '：', line)
        self.assertIn('首帧', line)
        self.assertNotIn('这页', line, '不报页码（第 37 期第 5 条）')
        self.assertIn(line, cloud._body_text(), '问句要真的排进对话框里')

    def test_the_question_joins_the_record_instead_of_wiping_it(self):
        cloud = self.pet.cloud()
        self.pet.open_chat()
        before = list(cloud.lines)
        self.pet.open_chat()
        self.assertEqual(cloud.lines[:len(before)], before, '再开一次只往后接一句，不刷新记录')
        self.assertEqual(cloud.lines[0], pet_cloud.WELCOME)

    def test_every_page_question_knows_its_stage(self):
        """SANHU-FIX-2 S-03：PAGE_STAGES 与 PAGE_ASKS 一一等长对应——页表之外认不出为 None。"""
        self.assertEqual(len(pet_ui_support.PAGE_STAGES), len(pet_ui.PAGE_ASKS))
        for stage in pet_ui_support.PAGE_STAGES:
            self.assertIn(stage, pet_bus.STAGES)
        self.assertIsNone(pet_ui_support.page_stage_for(len(pet_ui.PAGE_ASKS)))
        self.assertIsNone(pet_ui_support.page_stage_for(-1))

    def test_opening_the_chat_hands_the_pages_stage_to_the_reply_box(self):
        """S-03：三虎问的那件事带着这一页的阶段——空着回车按它派发。"""
        self.fake.page_index = list(pet_bus.STAGES).index('video')
        cloud = self.pet.cloud()
        self.pet.open_chat()
        self.assertEqual(cloud.choice, pet_ui.PAGE_ASKS[self.fake.page_index][1])
        self.assertEqual(cloud.choice_stage, 'video')


class StageNoteTests(PetTestCase):
    """第 36 期第 6 条：用户换了阶段，三虎看一眼「这一步要不要我自动做」。

    第 45 期：换页本身不再等于「该说话了」——用户要「取消用户切换页面三虎就弹出对话框的规则，
    改为三虎自己判断用户是否需要对话操作」。所以这一组用例两头都盯：有事才开口、没事就安静。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def pending(self, stage="video"):
        """让这一阶段压上一条「失败待确认」：三虎为此才值得开口。"""
        self.pet.agent.fail(stage, "连不上云端", attempt=4)
        return self.pet.agent.failures[-1]

    def page_for(self, stage):
        """阶段插入或排序调整后，测试仍按业务阶段而不是旧页号验证。"""
        return list(pet_bus.STAGES).index(stage)

    def test_the_first_page_is_only_registered(self):
        self.assertEqual(self.pet.note_stage(page=4, at=self.now), "",
                         "开机落在哪一页不算「换阶段」：不打扰")
        self.assertEqual(self.pet._stage_page, 4)

    def test_a_plain_page_switch_stays_quiet(self):
        """第 45 期：手上没有非等用户点头的事，翻页就翻页——三虎一个字都不说。"""
        self.pet.note_stage(page=4, at=self.now)
        self.assertEqual(self.pet.note_stage(page=5, at=self.now + 1), "")
        self.assertFalse(self.pet.cloud_visible(), "不冒贴纸")
        self.assertEqual(self.pet._stage_page, 5, "页还是记下了：下一回按新的一页判断")

    def test_a_failure_waiting_on_this_page_makes_it_ask(self):
        self.pet.note_stage(page=4, at=self.now)
        self.pending("video")
        video_page = self.page_for("video")
        said = self.pet.note_stage(page=video_page, at=self.now + 1)
        self.assertIn(pet_agent.PET_NAME, said)
        self.assertNotIn(self.pet.page_name(video_page), said, "第 37 期第 5 条：不报「这是第几页」")
        self.assertNotIn("换到", said, "也不说切到哪一页")
        self.assertIn("要不要", said, "只问用户要不要做这件事")
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        # broadcast 的返回值带阶段标签；云朵正文只保留用户实际读到的问句。
        self.assertIn(said.split('】', 1)[-1], cloud.transcript())
        self.assertEqual(self.pet.note_stage(page=video_page, at=self.now + 2), "", "同一页不重复问")

    def test_a_failure_on_another_page_keeps_this_one_quiet(self):
        self.pet.note_stage(page=4, at=self.now)
        self.pending("video")
        self.assertEqual(self.pet.note_stage(page=2, at=self.now + 1), "",
                         "压着的是视频那一步的活：在资产页不插嘴")
        self.assertTrue(self.pet.note_stage(page=self.page_for("video"), at=self.now + 2), "切到它自己那一页再说")

    def test_a_paused_pet_does_not_pester(self):
        self.pet.note_stage(page=4, at=self.now)
        self.pending("video")
        self.pet.agent.pause("用户按了暂停")
        self.assertEqual(self.pet.note_stage(page=self.page_for("video"), at=self.now + 1), "",
                         "暂停期间问了也做不成：不打扰")

    def test_the_same_page_asks_again_after_the_throttle(self):
        self.pet.note_stage(page=4, at=self.now)
        self.pending("video")
        video_page = self.page_for("video")
        self.assertTrue(self.pet.note_stage(page=video_page, at=self.now + 1))
        asked_at = self.pet._stage_at
        self.pet.cloud()._hide_now()                 # 上一朵收干净：现在只看节流这一道闸
        self.assertEqual(self.pet.note_stage(page=video_page, at=self.now + 2), "",
                         "刚问过这一页：不重复问")
        self.assertEqual(self.pet._stage_at, asked_at, "被节流的那一次不动钟点")
        self.now += pet_ui.STAGE_ASK_SECONDS + 1
        self.pet.bstate.last_broadcast = ""                # 「同一句不连说两遍」是另一道闸：这里只看节流
        self.assertTrue(self.pet.note_stage(page=video_page, at=self.now), "过了节流窗口可以再问")

    def test_the_question_hands_the_task_to_the_reply_box(self):
        self.pet.note_stage(page=4, at=self.now)
        self.pending("video")
        video_page = self.page_for("video")
        self.pet.note_stage(page=video_page, at=self.now + 1)
        self.assertEqual(self.pet.cloud().choice, pet_ui.PAGE_ASKS[video_page][1],
                         "直接按回车就等于答应它")

    def test_a_quiet_pet_stays_quiet(self):
        self.pet.note_stage(page=4, at=self.now)
        self.pending("video")
        self.pet.mute(seconds=600, at=self.now)
        video_page = self.page_for("video")
        self.assertEqual(self.pet.note_stage(page=video_page, at=self.now + 1), "", "安静期里不问")
        self.pet._mute_until = 0
        self.pet.front = lambda: False
        self.assertEqual(self.pet.note_stage(page=video_page, at=self.now + 2), "", "人切走了不问")

    def test_it_does_not_stack_on_a_showing_sticker(self):
        self.pet.note_stage(page=4, at=self.now)
        self.pet.cloud().whisper("三虎：随口一句")          # 露着的是一句话贴纸，不是对话框
        self.pending("video")
        self.assertEqual(self.pet.note_stage(page=self.page_for("video"), at=self.now + 1), "",
                         "已经有贴纸露着就不叠一个")

    def test_an_open_dialog_follows_the_page(self):
        """第 37 期第 5／6 条：对话框开着时换页，问句排进同一个框，上一页那句让位。"""
        self.pet.open_chat()
        cloud = self.pet.cloud()
        keyframe_page = self.page_for("keyframe")
        video_page = self.page_for("video")
        self.pet._stage_page = keyframe_page
        self.pending("keyframe")
        self.pet.note_stage(page=keyframe_page, at=self.now)          # 先问首帧这一步
        was = cloud.lines[-1]
        self.assertTrue(self.pet.is_page_ask(was), "上一句是三虎问的这一页的事")
        self.pending("video")
        said = self.pet.note_stage(page=video_page, at=self.now + 1)
        self.assertTrue(said, "这一页压着待确认的事：问一句")
        self.assertEqual(cloud.lines[-1], said, "排进同一个框")
        self.assertNotIn(was, cloud.lines, "上一页那句让位：框里只留当前这一页的事")
        self.assertEqual(cloud.choice, pet_ui.PAGE_ASKS[video_page][1], "回车要办的事也换成这一页的")

    def test_the_dialog_does_not_pile_up(self):
        """第 37 期第 6 条：对话框不当地志——换页顺手清一清，攒不过几段。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        for index in range(20):
            cloud.append("第%d句" % index)
        self.pet._stage_page = self.page_for("keyframe")
        self.pending("video")
        self.pet.note_stage(page=self.page_for("video"), at=self.now + 1)
        self.assertLessEqual(len(cloud.lines), pet_cloud.CHAT_KEEP, "换页后只留最近几段")

    def test_a_broken_clock_never_raises(self):
        self.pet.clock = lambda: (_ for _ in ()).throw(RuntimeError("读不出时间"))
        self.assertEqual(self.pet.note_stage(page=5), "")
        self.assertTrue(any(name == "stage.clock" for name, _text in self.pet.errors))


class StageEntryTests(PetTestCase):
    """第 57 期第 12 条：进页状态、半自动确认与全自动模板入口。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.fake.page_index = 0
        self.spoken = []
        self.pet.broadcast = lambda text, **_kwargs: self.spoken.append(text) or text

    def pend_script_failure(self):
        """R1948：进页只在有待办时开口——这两条用例先在剧本阶段压一条失败待确认。"""
        self.pet.agent.failures.append({'stage': 'script', 'category': 'unknown', 'error': '待确认'})

    def test_hint_only_reports_the_current_script_progress(self):
        self.pet.agent.set_level('hint')
        self.pend_script_failure()
        self.pet.run_skill = lambda *_args, **_kwargs: self.fail('提示档不能启动 SKILL')
        said = self.pet.enter_stage(page=0, at=self.now)
        self.assertIn('【阶段 1/13】', said)
        self.assertIn('剧本', said)
        self.assertIn('当前进度', said)

    def test_semi_auto_combines_progress_with_existing_confirmation(self):
        self.pet.agent.set_level('semi')
        self.pend_script_failure()
        self.pet.run_skill = lambda *_args, **_kwargs: self.fail('确认前不能启动 SKILL')
        said = self.pet.enter_stage(page=0, at=self.now)
        self.assertIn('【阶段 1/13】', said)
        self.assertIn('要不要', said)
        self.assertIn(pet_agent.PET_NAME + '：', said)

    def test_auto_runs_the_stage_once_and_asks_to_confirm_script_result(self):
        self.pet.agent.set_level('auto')
        started, confirmations = [], []
        self.pet.run_skill = lambda plan, at=None: started.append((plan, at)) or '完成剧本'
        self.pet.confirm = lambda text: confirmations.append(text) or text
        self.assertEqual(self.pet.enter_stage(page=0, at=self.now), '完成剧本')
        self.assertIn('script', started[0][0]['stage'])
        self.assertEqual(started[0][0]['params']['template_confirmation'], '确认')
        # R1948 契约变更：已派发、又没有失败／阻塞待办时，再进这一页一个字都不说（原断言等于最近一句进度）。
        self.assertEqual(self.pet.enter_stage(page=0, at=self.now + 1), '')
        self.assertEqual(len(started), 1, '切页刷新不得重复派发同一阶段')
        self.assertIn('确认剧本信息', confirmations[0])

    def test_auto_storyboard_uses_artifact_batch_not_generic_skill(self):
        """初步分镜完成必须等待 JSON 生成并自动采用，不能只因 SKILL 已派发而完成。"""
        self.pet.agent.set_level('auto')
        storyboard_page = list(pet_bus.STAGES).index('storyboard')
        starts = []
        self.pet.run_skill = lambda *_args, **_kwargs: self.fail('分镜不能走通用 SKILL 完成通道')
        self.pet.start_stage = lambda stage, at=None: starts.append((stage, at)) or '已派发分镜任务，等待生成并采用'
        self.assertIn('等待生成并采用', self.pet.enter_stage(page=storyboard_page, at=self.now))
        self.assertEqual(starts, [('storyboard', self.now)])


class AutoStartTests(PetTestCase):
    """第 67 期任务 4／5：开机一律「只提醒」；自动档下三虎自己把每一步开起来。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.started = []
        self.fake.pet_start = self.start_it

    def start_it(self, stage):
        """宿主的 pet_start 接缝：打开无人值守开关＋立刻起跑（与 Desktop.pet_start 同口径）。"""
        self.started.append(stage)
        return '已自动开始「%s」' % pet_bus.STAGE_NAMES.get(stage, stage)

    def script_done(self):
        self.pet.machine.start('script')
        self.pet.machine.complete('script')

    def test_starting_the_app_always_goes_back_to_the_hint_level(self):
        """第 67 期任务 4：上次选的档不沿用——开机那一下就是「只提醒」。"""
        self.pet.agent.set_level('auto')
        self.assertEqual(self.pet.start_level(), pet_agent.DEFAULT_LEVEL)
        self.assertEqual(self.pet.agent.level, 'hint')
        self.assertFalse(self.pet.auto.armed, '只提醒档不带着自动推进那条链')

    def test_switching_to_an_automatic_level_arms_the_chain_from_the_project(self):
        """第 67 期任务 5：剧本早就做完的项目，切到自动档就该从下一步接手。"""
        self.script_done()
        self.pet.set_level('semi')
        self.assertTrue(self.pet.auto.armed, '切档那一下按项目现状武装起来')
        self.assertEqual(self.pet.auto.pending()[0], 'script_structure',
                         '剧本完成后必须先生成结构剧本，不能跳过第 02 阶段直接制作分镜')

    def test_structured_script_on_disk_starts_storyboard_when_auto_is_enabled(self):
        """结构剧本手动产出但状态机缺历史时，切自动档也要立即从分镜接手。"""
        structured = self.fake.root / 'writing' / 'script.md'
        structured.parent.mkdir(parents=True, exist_ok=True)
        structured.write_text('# 结构化剧本\n\n## 角色档案\n\n## 分场剧本\n\n### 镜头 001', encoding='utf-8')
        self.pet.set_mode('auto')
        self.assertTrue(self.pet.auto.armed)
        self.assertEqual(self.started, ['storyboard'], '切换自动档后应自动开始制作分镜')
        self.assertEqual(self.pet.auto.state()['active'], 'storyboard')
        from storyboard_files import selected_many
        self.assertIn(structured.resolve(), selected_many(self.fake.root, 'script'), '结构剧本已同步到分镜输入')

    def test_reselecting_auto_does_not_dispatch_the_active_stage_twice(self):
        """全自动已派发分镜时重复选择“全自动”不能清空 active 后再派一次。"""
        structured = self.fake.root / 'writing' / 'script.md'
        structured.parent.mkdir(parents=True, exist_ok=True)
        structured.write_text('# 结构化剧本\n\n## 角色档案\n\n## 分场剧本\n\n### 镜头 001', encoding='utf-8')
        self.pet.set_mode('auto')
        self.assertEqual(self.started, ['storyboard'])
        self.pet.set_mode('auto')
        self.assertEqual(self.started, ['storyboard'], '当前阶段仍在执行，重复切换模式不得重复派发')
        self.assertEqual(self.pet.auto.state()['active'], 'storyboard')

    def test_switching_back_to_the_hint_level_stops_the_chain(self):
        """第 67 期任务 4：退回只提醒，那条链立刻停手。"""
        self.script_done()
        self.pet.set_level('auto')
        self.assertTrue(self.pet.auto.armed)
        self.pet.set_level('hint')
        self.assertFalse(self.pet.auto.armed, '只提醒档不再替用户开阶段')

    def test_script_download_is_the_only_storyboard_prompt_time(self):
        """REQ-S01-76：模型回话不弹完成框；剧本自动存档（每份新剧本一次）后才问下一步。

        SANHU-FIX-2 S-10：问句改口——原来直接问「制作分镜」，现在先问「要不要把
        剧本原稿整理成结构化正稿」（与第 02 阶段 script_structure 对齐）。"""
        prompts = []
        self.pet.confirm = lambda text, **kwargs: prompts.append(text) or text
        self.pet.script_downloaded('剧本.md')
        self.assertEqual(prompts, ['【下一阶段】剧本已保存。要不要我把这份剧本原稿整理成结构化正稿？'])

    def test_the_script_download_offer_carries_the_structure_stage(self):
        """S-10：问句带 'script_structure'——空着回车派发按剧本结构路由。"""
        self.pet.confirm = lambda text, **kwargs: text
        self.pet.script_downloaded('剧本.md')
        cloud = self.pet.cloud()
        self.assertEqual(cloud.choice, '执行选中')
        self.assertEqual(cloud.choice_stage, 'script_structure')

    def test_the_fully_automatic_level_does_not_ask_after_saving_the_script(self):
        """S-10：全自动档不问——自动链自己往下走。"""
        prompts = []
        self.pet.confirm = lambda text, **kwargs: prompts.append(text) or text
        self.pet.agent.set_level('auto')
        self.pet.script_downloaded('剧本.md')
        self.assertEqual(prompts, [], '全自动不问：链自己往下走')

    def test_downloading_a_real_script_completes_the_automatic_script_stage(self):
        saved = self.fake.root / 'writing' / '创意_20260926' / '项目_EP001_20260926.md'
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text('# 第一集\n完整剧本正文', encoding='utf-8')
        emitted = []
        self.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        self.pet.confirm = lambda *_args, **_kwargs: ''
        self.pet.script_downloaded(saved)
        self.assertEqual([kind for kind, _payload in emitted],
                         ['script.completed', 'stage.completed'])

    def test_the_free_steps_are_started_by_themselves(self):
        """第 67 期任务 5：自动档不是「叫一声」，真的把这一步开起来；付费那步只叫醒。

        SANHU-FIX-2 S-05：半自动的付费步骤现在先问一句「现在做吗」——这里同步换成
        假回答（用户没点头）：断言照旧：不代跑、照旧退成「提前叫醒一轮」。
        """
        original = pet_ask.ask_yes
        pet_ask.ask_yes = lambda *args, **kwargs: False
        self.addCleanup(setattr, pet_ask, 'ask_yes', original)
        self.script_done()
        self.pet.set_level('semi')
        self.pet.start_stage('storyboard', at=self.now)
        self.assertEqual(self.started, ['storyboard'], '免费步骤自己起跑')
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(self.started, ['storyboard'], '半自动的付费步骤不代跑')
        self.assertIn('assets', self.fake.advances, '付费那一步退成「提前叫醒一轮」')

    def test_the_semi_paid_step_asks_once_before_running(self):
        """S-05：半自动付费步骤先问一句「现在做吗」——点头后授权并带 confirmed 派发。"""
        self.script_done()
        self.pet.set_level('semi')
        asks = []
        original = pet_ask.ask_yes
        pet_ask.ask_yes = lambda *args, **kwargs: asks.append(args[2] if len(args) > 2 else '') or True
        self.addCleanup(setattr, pet_ask, 'ask_yes', original)
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(len(asks), 1, '这一步只问一次')
        self.assertIn('资产管理', asks[0])
        self.assertIn('要花钱', asks[0])
        self.assertIn('assets', self.started, '点头后带 confirmed=True 重审派发')
        self.assertTrue(self.pet.should_auto_run('assets'), 'grant_paid 已把本阶段授权记上')

    def test_a_declined_paid_step_waits_and_stops_asking(self):
        """S-05：没点头 → 回「等您点头再开始」、记进被拒集合，本档不再自动追问。"""
        self.script_done()
        self.pet.set_level('semi')
        asks = []
        original = pet_ask.ask_yes
        pet_ask.ask_yes = lambda *args, **kwargs: asks.append(1) or False
        self.addCleanup(setattr, pet_ask, 'ask_yes', original)
        text = self.pet.start_stage('assets', at=self.now)
        self.assertEqual(text, '「资产管理」要花钱，等您点头再开始')
        self.assertNotIn('assets', self.started)
        self.assertEqual(asks, [1], '问了就一次')
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(asks, [1], '本档内被拒过的阶段不再自动追问')
        self.assertIn('assets', self.fake.advances, '照旧只把轮询提前叫醒一轮')

    def test_an_unanswered_paid_question_also_counts_as_a_decline(self):
        """S-05：没等到回答（超时）与「不」同路——记被拒、不再追问。"""
        self.script_done()
        self.pet.set_level('semi')
        asks = []
        original = pet_ask.ask_yes
        pet_ask.ask_yes = lambda *args, **kwargs: asks.append(1) or None
        self.addCleanup(setattr, pet_ask, 'ask_yes', original)
        text = self.pet.start_stage('assets', at=self.now)
        self.assertEqual(text, '「资产管理」要花钱，等您点头再开始')
        self.assertNotIn('assets', self.started)
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(asks, [1])

    def test_saying_continue_lets_the_paid_step_ask_again(self):
        """S-05：用户说「继续」＝被拒集合清空，这一阶段重新可问。"""
        self.script_done()
        self.pet.set_level('semi')
        asks = []
        original = pet_ask.ask_yes
        pet_ask.ask_yes = lambda *args, **kwargs: asks.append(1) or False
        self.addCleanup(setattr, pet_ask, 'ask_yes', original)
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(asks, [1])
        self.pet.run_plan({'plan': {'intent': 'resume'}, 'decision': {'run': True}}, at=self.now)
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(asks, [1, 1], '说过「继续」之后再被问到')

    def test_switching_the_level_clears_the_declined_step(self):
        """S-05：切档＝授权与被拒集合一起清，这一阶段回到可问状态。"""
        self.script_done()
        self.pet.set_level('semi')
        asks = []
        original = pet_ask.ask_yes
        pet_ask.ask_yes = lambda *args, **kwargs: asks.append(1) or False
        self.addCleanup(setattr, pet_ask, 'ask_yes', original)
        self.pet.start_stage('assets', at=self.now)
        self.pet.set_level('hint')
        self.pet.set_level('semi')
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(len(asks), 2, '切档之后这一阶段重新可问')

    def test_automatic_keyframe_dispatch_marks_its_trigger(self):
        calls = []
        self.fake.pet_start = lambda stage: calls.append(stage) or '已按分镜顺序派发 2 镜首帧'
        self.pet.mode = 'auto'
        self.pet.agent.set_level('auto')
        self.pet.start_stage('keyframe', at=self.now)
        self.assertEqual(calls, ['keyframe'])

    def test_batch_dispatch_error_finishes_the_active_stage_as_failed(self):
        """接缝异常不能只显示错误文字，必须收场自动链，避免永久执行中。"""
        def boom():
            raise RuntimeError('宿主批处理不可用')

        self.fake.pet_start = lambda _stage: boom()
        self.pet.mode = 'auto'
        self.pet.agent.set_level('auto')
        self.pet.auto = stage_flow.Auto(order=['script_structure', 'storyboard'])
        self.pet.auto.script_done('auto')
        self.assertEqual(self.pet.auto.next_stage(), 'script_structure')

        text = self.pet.start_stage('script_structure', at=self.now)
        self.assertIn('剧本结构未派发：宿主批处理不可用', text)
        self.pet.bus.pump()
        self.assertEqual(self.pet.machine.stages['script_structure']['state'], 'failed')
        self.assertEqual(self.pet.auto.state()['blocked'], 'script_structure')

    def test_automatic_stage_without_any_host_entry_finishes_as_failed(self):
        """没有轮询也没有批处理的阶段不能伪装成已经自动启动。"""
        self.fake.pet_start = None
        self.fake.deaf = ('continuity',)
        self.pet.mode = 'auto'
        self.pet.agent.set_level('auto')
        self.pet.auto = stage_flow.Auto(order=['continuity'])
        self.pet.auto.script_done('auto')
        self.assertEqual(self.pet.auto.next_stage(), 'continuity')
        text = self.pet.start_stage('continuity', at=self.now)
        self.assertIn('没有「连贯性清单」的自动执行入口', text)
        self.pet.bus.pump()
        self.assertEqual(self.pet.machine.stages['continuity']['state'], 'failed')
        self.assertEqual(self.pet.auto.state()['blocked'], 'continuity')

    def test_the_fully_automatic_level_starts_the_paid_steps_too(self):
        self.script_done()
        self.pet.set_level('auto')
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(self.started, ['assets'], '全自动档连会花钱的步骤也自己开')

    def test_a_stage_without_checked_skills_is_skipped_before_any_dispatch(self):
        """R2905：一个 SKILL 都没勾的阶段自动跳过并提示——先于付费审批与派发。"""
        import json as _json
        (self.fake.root / 'skill_config.json').write_text(_json.dumps(
            {'assets': {'model': 'auto', 'skills': []}}, ensure_ascii=False), encoding='utf-8')
        self.pet.set_level('semi')
        text = self.pet.start_stage('assets', at=self.now)
        self.assertIn('跳过', text)
        self.assertEqual(self.started, [], '未勾选的阶段不得进入 pet_start 派发')
        self.assertEqual(self.fake.advances, [], '跳过的阶段也不叫醒轮询')
        self.pet.bus.pump()
        self.assertEqual(self.pet.machine.stages['assets']['state'], 'skipped')

    def test_the_hint_level_starts_nothing_at_all(self):
        """第 67 期任务 4：只提醒档只看着，一个阶段都不替他开。"""
        self.script_done()
        self.assertEqual(self.pet.start_stage('storyboard', at=self.now), '')
        self.assertEqual(self.started, [])
        self.assertEqual(self.fake.advances, [])


if __name__ == '__main__':
    unittest.main()
