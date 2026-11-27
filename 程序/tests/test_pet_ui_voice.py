# -*- coding: utf-8 -*-
"""宠物贴片自检（播报、通知、免打扰、停滞与失败语音提醒）：自原 test_pet_ui.py 按测试类拆分，断言与夹具原样保留。"""
import datetime
import os
import sys
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
from ui import pet_cloud
import ui.pet_context_facts as pet_context_facts
import ui.pet_ui_support as pet_ui_support
import ui.pet_ui as pet_ui
import selftest_sandbox

selftest_sandbox.isolate(pet_ui)

class NotificationTests(PetTestCase):
    """第 22 期：自绘气泡删了，通知只剩云朵框这一条出口（同一批失败只说一次）。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def fail_once(self, stage="keyframe", error="超时"):
        self.pet.agent.fail(stage, error, attempt=4)

    def test_the_notice_goes_into_the_cloud_record(self):
        self.fail_once()
        self.assertTrue(self.pet.announce_failures())
        self.assertIn("首帧管理", self.pet.cloud().transcript())
        self.assertEqual(self.pet.announce_failures(), "", "同一句话不许说两遍")

    def test_announcing_really_shows_the_cloud(self):
        self.fail_once()
        self.pet.announce_failures()
        self.assertTrue(self.pet.cloud().visible, "说给用户听就得真的冒出来")

    def test_snoozing_silences_the_cloud_too(self):
        self.pet.snooze(600)
        self.fail_once()
        self.assertEqual(self.pet.announce_failures(), "")
        self.assertNotIn("超时", self.pet.cloud().transcript())

    def test_the_buttons_reach_the_same_implementations(self):
        self.fail_once()
        self.pet.tap_safe("skip")
        self.assertIn("已跳过当前阻塞项", self.pet.notice)
        self.assertEqual(self.pet.agent.failures, [], "跳过就是把那条摘掉")
        self.pet.tap_safe("model")
        self.assertEqual(self.pet.tier, "deepseek-v4-flash")
        self.assertIn("已切换到", self.pet.notice)

    def test_an_empty_intent_is_ignored(self):
        self.assertFalse(self.pet.tap_safe(""))
        self.assertFalse(self.pet.tap_safe(None))
        self.assertFalse(any(name == "click" for name, _text in self.pet.errors),
                         '空 intent 不该被当成出错')

    def test_the_intent_lands_in_the_journal(self):
        self.fail_once()
        self.pet.tap_safe("skip")
        pet_ui.pump(self.fake)
        item = [event for event in self.pet.bus.history if event["kind"] == "intent.command"][-1]
        self.assertEqual(item["text"], "skip")

    # ── 跳过这张 ────────────────────────────────────────────────────────────
    def test_skip_takes_the_oldest_pending_item(self):
        self.fail_once("keyframe", "超时")
        self.fail_once("video", "被限流")
        self.pet.tap_safe("skip")
        self.assertEqual([item["stage"] for item in self.pet.agent.failures], ["video"])


class DetailsTests(PetTestCase):
    """「待确认项」：只在三虎旁的提示框展示，绝不创建只读文本窗。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def fail_once(self, stage="keyframe", error="超时"):
        self.pet.agent.fail(stage, error, attempt=4)

    # ── 待确认项 ────────────────────────────────────────────────────────────
    def test_details_are_shown_in_the_pet_bubble_not_a_host_window(self):
        calls = []
        self.fake.pet_show_text = lambda title, text, receipt="": calls.append((title, text, receipt))
        self.fail_once("keyframe", "请求超时")
        self.pet.click("details")
        self.assertEqual(calls, [], '待确认项不再调用宿主的弹窗入口')
        cloud = self.pet.cloud()
        self.assertTrue(cloud.visible, "待确认项应在三虎旁提示")
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_ROUND)
        self.assertEqual(self.pet.notice, self.pet.details_text())
        self.assertIn('待确认 1 项', cloud.transcript())

    def test_details_text_lists_every_pending_item(self):
        self.assertEqual(self.pet.details_text(), "现在没有待确认的项。")
        self.fail_once("keyframe", "请求超时")
        self.fail_once("video", "被限流")
        text = self.pet.details_text()
        self.assertIn("待确认 2 项", text)
        self.assertIn("1. 首帧管理 · 超时", text)
        self.assertIn("2. 视频生成 · 被限流", text)
        self.assertIn("原因：请求超时", text)
        self.assertIn("建议：", text)

    def test_details_never_calls_a_broken_host_window(self):
        def boom(title, text, receipt=""):
            raise RuntimeError("窗口开不出来")

        self.fake.pet_show_text = boom
        self.fail_once()
        self.assertTrue(self.pet.show_details())
        self.assertTrue(self.pet.cloud().visible, "待确认项直接走三虎提示框")
        self.assertFalse(any(name == "details.window" for name, _text in self.pet.errors))


class BroadcastTests(PetTestCase):
    """第 14 期：播报频率与缺口提醒（未采用的分镜 JSON、缺首帧的镜头）。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.counts = {'storyboards': 0, 'adopted': 0, 'shots': 0, 'frames': 0}
        self.pet.counts = lambda: dict(self.counts)

    def test_unadopted_storyboards_are_reported_with_the_next_step(self):
        self.counts['storyboards'] = 3
        parts = self.pet.gaps(force=True)
        self.assertEqual(len(parts), 1)
        self.assertIn('3 份分镜 JSON 还没采用', parts[0])
        self.assertIn('03 初步分镜', parts[0])

    def test_missing_first_frames_are_reported(self):
        self.counts.update(shots=10, frames=4)
        parts = self.pet.gaps(force=True)
        self.assertIn('首帧还差 6 个镜头', parts[0])
        self.assertIn('08 首帧管理', parts[0])

    def test_no_gap_means_nothing_to_say(self):
        self.assertEqual(self.pet.gaps(force=True), [])
        self.assertEqual(self.pet.tick_broadcast(), '')

    def test_a_new_gap_is_broadcast_at_once(self):
        self.assertEqual(self.pet.tick_broadcast(), '', '开局没缺口就不说话')
        self.counts['storyboards'] = 3
        self.now += pet_ui.GAP_SECONDS + 1   # 只过了「重算缺口」的节流，还没到播报间隔
        self.assertIn('3 份分镜 JSON 还没采用', self.pet.tick_broadcast())
        self.assertEqual(self.pet.tick_broadcast(), '', '同一批缺口不重复播')
        self.assertIn('3 份分镜 JSON 还没采用', self.pet.cloud().transcript())

    def test_the_gap_is_recounted_only_every_gap_seconds(self):
        reads = []
        self.pet.counts = lambda: reads.append(1) or {'storyboards': 0, 'adopted': 0, 'shots': 0, 'frames': 0}
        self.pet.gaps()
        self.pet.gaps()
        self.assertEqual(len(reads), 1, '读盘很贵，缺口按 GAP_SECONDS 缓存')
        self.now += pet_ui.GAP_SECONDS + 1
        self.pet.gaps()
        self.assertEqual(len(reads), 2)

    def test_the_idle_pet_reports_once_a_minute(self):
        self.pet.tick_broadcast()                      # 第一次只对表，不播
        self.now += pet_ui.BROADCAST_BUSY + 1
        self.assertEqual(self.pet.tick_broadcast(), '', '闲着的时候不该按忙时的频率报')
        self.now += pet_ui.BROADCAST_IDLE
        self.assertTrue(self.pet.tick_broadcast(), '闲着也要隔一会儿报一次进度')

    def test_the_busy_pet_reports_more_often(self):
        self.pet.machine.start('script')
        self.pet.tick_broadcast()
        self.now += pet_ui.BROADCAST_BUSY + 1
        self.assertTrue(self.pet.tick_broadcast(), '有阶段在跑：到 BROADCAST_BUSY 就报')

    def test_switching_the_level_says_which_one_is_active(self):
        self.pet.click('level')
        level = self.pet.agent.level
        self.assertEqual(self.pet.notice, pet_ui.LEVEL_SWITCH_NOTES[level])
        self.assertTrue(pet_ui.LEVEL_SWITCH_NOTES[level].startswith(pet_agent.LEVEL_NAMES[level] + '：'))
        transcript = self.pet.cloud().transcript()
        self.assertEqual(transcript.count('已切换到' + pet_agent.LEVEL_NAMES[level] + '模式'), 1)

    def test_pausing_and_resuming_say_so(self):
        self.pet.click('pause')
        self.assertIn('已暂停自动执行', self.pet.notice)
        self.pet.click('resume')
        self.assertIn('已继续自动执行', self.pet.notice)
        self.assertIn(self.pet.notice, self.pet.cloud().transcript())


class NoChatterTests(PetTestCase):
    """第 29 期第 5 条：删掉闲聊——三虎只谈制作流程，不再随口说可爱的话。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def change_pose(self):
        """让猫样真的换一次动作：从前话痨只在这一拍开口，现在这一拍也不许开口。"""
        self.pet.cat.next(self.pet.frame + 10 ** 6, force=True)

    def test_the_small_talk_is_gone(self):
        self.assertFalse(hasattr(self.pet, 'chatter'), '自言自语那个方法整个删掉')
        self.assertFalse(hasattr(pet_ui, 'CHATTER_LINES'), '那些可爱话的文案也不留')
        self.assertFalse(hasattr(pet_ui, 'CHATTER_SECONDS'), '连「隔多久说一句」的节流也不留')
        self.assertFalse(hasattr(pet_ui, 'CHAT_HELLO_LINES'), '猜意图的那五句「哈喽~」也不留')

    def test_the_heartbeat_never_says_a_cute_line(self):
        said = []
        original = self.pet.whisper
        self.pet.whisper = lambda text, at=None: said.append(text) or original(text, at=at)
        self.addCleanup(setattr, self.pet, 'whisper', original)
        self.pet.pump(at=self.now)
        self.change_pose()
        self.now += 3600.0                    # 隔了整整一小时，从前这个间隔早该冒一句了
        self.pet.pump(at=self.now)
        self.assertEqual(said, [], '换动作那一拍也不再说可爱的话')


class CloudVoiceTests(PetTestCase):
    """第 18 期：开机招呼、随口一句、标签框，以及开机清记录／云跟着主界面走。

    第 25 期起招呼与随口一句都用云朵框（用户要的「可爱话统一用云朵框」），圆气泡留给进度。
    """

    def main_window_showing(self, value=True):
        """自检里主窗口是 withdraw 的：招呼只在主窗口露着时才冒，这里按用例需要钉住它。"""
        self.pet.window_visible = lambda: value

    def test_the_greeting_uses_a_puff_with_the_creators_line(self):
        self.main_window_showing()
        self.assertEqual(self.pet.greet(), self.pet._prefix_output(pet_cloud.GREETING))
        cloud = self.pet.cloud()
        self.assertTrue(cloud.visible)
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF, '打招呼是云朵框')
        self.assertFalse(cloud.pinned, '招呼只有一句话，不带输入行')
        greeting_text = ' '.join(pet_cloud.GREETING.split())
        self.assertIn(greeting_text, cloud.transcript(),
                      '云朵正文去掉进度前缀，前缀仍由进度日志保留')
        self.assertIsNotNone(cloud._hold, '到点自己收')

    def test_the_greeting_line_is_the_one_the_user_asked_for(self):
        """第 27 期第 5 条：用户给的那一句，字要一个不差（第 28 期第 2 条重申）。

        第 36 期第 13 条：末尾那串「~~~~~~~」也删了（“启动软件时三虎弹出的打招呼内容，删除文字最后的~~”）。
        第 37 期第 3 条：改成一／二两句换行——先叫人，再说自己是谁、来干什么。
        """
        self.assertEqual(pet_cloud.GREETING,
                         '哈喽~创造者!\n我是宠物agent, 三虎! 协助您完成漫剧制作.')
        self.assertFalse(pet_cloud.GREETING.endswith('~'), '末尾不再拖一串波浪号')
        self.assertEqual(len(pet_cloud.GREETING.splitlines()), 2, '两句之间换行')

    def test_the_greeting_waits_until_the_main_window_is_showing(self):
        cloud = self.pet.cloud()
        self.main_window_showing(False)
        self.assertEqual(self.pet.greet(), '', '主窗口没露出来就不冒（贴片没有真实坐标）')
        self.assertFalse(cloud.visible)

    def test_the_scheduled_greeting_waits_for_the_startup_page_to_settle(self):
        """开机招呼等启动页建完（版面计算占主线程），不撞进揭开后的第一秒；等满上限也要冒。"""
        self.main_window_showing()
        cloud = self.pet.cloud()
        jobs = []
        original = self.pet.win.after
        self.pet.win.after = lambda ms, fn=None, *a: jobs.append((ms, fn)) or 'job'
        self.addCleanup(setattr, self.pet.win, 'after', original)
        self.pet.win._desktop_startup_settled = False
        self.pet.schedule_greet()
        self.assertEqual(self.pet.greet(), '', '启动页没建完：不冒')
        self.assertFalse(cloud.visible)
        self.assertIsNotNone(self.pet._greet_id, '改期而不是作废')
        self.pet.win._desktop_startup_settled = True
        self.assertTrue(self.pet.greet(), '启动页就绪后冒')
        self.assertTrue(cloud.visible)

    def test_the_scheduled_greeting_stops_waiting_after_the_poll_limit(self):
        self.main_window_showing()
        original = self.pet.win.after
        self.pet.win.after = lambda ms, fn=None, *a: 'job'
        self.addCleanup(setattr, self.pet.win, 'after', original)
        self.pet.win._desktop_startup_settled = False
        self.pet.schedule_greet()
        for _ in range(pet_ui_support.GREET_SETTLE_POLLS):
            self.assertEqual(self.pet.greet(), '')
        self.assertTrue(self.pet.greet(), '页面迟迟不就绪也不能让招呼永远不来')

    def test_nothing_else_pops_right_after_the_greeting(self):
        """第 68 期任务 11：用户要「打招呼的聊天框关闭后，再慢慢弹出其他信息」。

        招呼的云才收，自动那几路（进度播报／进度气泡／主动问一句／自动推进／失败提醒）先不出声。
        """
        self.main_window_showing()
        now = [0.0]
        self.pet.clock = lambda: now[0]
        self.pet.agent.failures = [{'stage': 'assets', 'category': 'a', 'error': '出图失败'}]
        self.assertEqual(self.pet.greet(), self.pet._prefix_output(pet_cloud.GREETING))
        now[0] = 1.0
        self.assertTrue(self.pet.quiet(at=1.0), '招呼之后有一段安静期')
        self.assertEqual(self.pet.tune_advance(at=1.0), '', '自动推进先不出声')
        self.assertEqual(self.pet.tick_broadcast(at=1.0), '', '进度播报先不出声')
        self.assertEqual(self.pet.progress_voice(at=1.0, force=True), '', '进度气泡先不冒')
        self.assertEqual(self.pet.offer_oneclick(at=1.0), '', '先不问「要不要一键执行」')
        self.assertEqual(self.pet.announce_failures(), '', '失败提醒也先缓着')
        now[0] = pet_ui.GREET_QUIET_SECONDS + 1
        self.assertIn('出图失败', self.pet.announce_failures(), '安静期过了照旧报')

    def test_greeting_quiet_window_releases_at_five_seconds(self):
        self.main_window_showing()
        self.pet.clock = lambda: 100.0
        self.pet.greet()
        self.assertTrue(self.pet.quiet(at=104.9))
        self.assertFalse(self.pet.quiet(at=105.0))
        self.assertIsNone(self.pet._quiet_until)

    def test_quiet_period_defers_disk_counts_until_it_ends(self):
        from unittest import mock
        self.pet._greet_id = None
        self.pet._quiet_until = 105.0
        with mock.patch.object(self.pet, 'counts', return_value={}) as counts:
            self.assertTrue(self.pet.quiet(at=104.0))
            counts.assert_not_called()
            self.assertFalse(self.pet.quiet(at=105.0))
            counts.assert_called_once()

    def test_the_quiet_window_only_holds_back_the_pet_itself(self):
        """安静期只压住三虎自己找话说：用户刚按出来的那一句照常冒（换档位是用户点出来的）。"""
        self.main_window_showing()
        now = [0.0]
        self.pet.clock = lambda: now[0]
        self.pet.greet()
        now[0] = 1.0
        self.assertIn(pet_ui.LEVEL_SWITCH_NOTES['hint'], self.pet.announce(pet_ui.LEVEL_SWITCH_NOTES['hint']),
                      '用户点出来的话不排在安静期后面')
        self.assertTrue(self.pet.cloud().visible)

    def test_the_quiet_window_ends_and_the_throttles_start_over(self):
        """安静期里说不上话，那几路的节流起算点就跟着往后挪；到点安静期自己结束。"""
        self.main_window_showing()
        now = [1.0]
        self.pet.clock = lambda: now[0]
        self.pet.greet()
        now[0] = 5.0
        self.pet.progress_voice()
        self.pet.tune_advance()
        self.assertEqual(self.pet._progress_at, 5.0, '进度气泡的节流从安静期里重新起算')
        self.assertEqual(self.pet.bstate.advance_at, 5.0, '自动推进的节流一样往后挪')
        now[0] = pet_ui.GREET_QUIET_SECONDS + 1
        self.assertFalse(self.pet.quiet(), '过了这一段就不再安静')
        self.assertIsNone(self.pet._quiet_until)

    def test_a_restart_starts_from_a_clean_record(self):
        self.main_window_showing()
        cloud = self.pet.cloud()
        cloud.append('上一轮的旧话')
        self.pet.reset_cloud()
        self.assertEqual(cloud.lines, [pet_cloud.WELCOME], '每次重开都从干净的一条开始')
        self.pet.greet()
        self.assertEqual(cloud.lines, [' '.join(pet_cloud.GREETING.split())],
                         '云朵记录保存可读正文，不重复显示进度前缀')
        self.assertNotIn('上一轮的旧话', cloud.transcript())

    def test_the_start_seam_clears_the_record_and_greets_later(self):
        self.main_window_showing()
        cloud = self.pet.cloud()
        cloud.append('上一轮的旧话')
        jobs = []
        original = self.pet.win.after
        self.pet.win.after = lambda ms, fn=None, *a: jobs.append((ms, fn)) or 'job'
        self.addCleanup(setattr, self.pet.win, 'after', original)
        self.assertEqual(pet_ui.start(self.fake), 'job')
        self.assertEqual(cloud.lines, [pet_cloud.WELCOME], 'start 先把记录清干净')
        self.assertEqual(jobs[0][0], pet_ui.GREET_DELAY_MS, '招呼推迟到主循环里再冒')
        self.assertEqual(jobs[0][1].__func__, self.pet.greet.__func__, '到点就打招呼')
        self.assertIs(jobs[0][1].__self__, self.pet)

    def test_startup_automatic_message_waits_for_the_greeting(self):
        self.main_window_showing()
        now = [0.0]
        self.pet.clock = lambda: now[0]
        pet_ui.start(self.fake, delay_ms=5000)
        self.pet.agent.failures = [
            {'stage': 'assets', 'category': 'a', 'error': '出图失败'}]
        now[0] = 1.0
        self.assertEqual(self.pet.announce_failures(), '',
                         '招呼尚未出现时，自动对话不能抢先弹出')
        self.pet.cancel_greet()
        self.pet.greet()
        self.assertEqual(self.pet.cloud().shape, pet_cloud.SHAPE_PUFF)
        self.assertEqual(self.pet.announce_failures(), '')
        now[0] += pet_ui.GREET_QUIET_SECONDS + 1
        self.assertIn('出图失败', self.pet.announce_failures())

    def test_pending_greeting_does_not_block_manual_messages(self):
        self.main_window_showing()
        pet_ui.start(self.fake, delay_ms=5000)
        self.assertTrue(self.pet.quiet())
        self.assertEqual(self.pet.announce('用户主动操作'),
                         self.pet._prefix_output('用户主动操作'))

    def test_cancelled_greeting_does_not_leave_automatic_messages_blocked(self):
        pet_ui.start(self.fake, delay_ms=5000)
        self.assertTrue(self.pet.quiet())
        self.pet.cancel_greet()
        self.assertFalse(self.pet.quiet())

    def test_a_whisper_is_a_puff_bubble(self):
        """第 25 期第 2 条：与工作无关的可爱话统一用云朵框（圆气泡留给进度）。"""
        text = '%s：尾巴甩一甩' % pet_agent.PET_NAME
        self.assertEqual(self.pet.whisper(text), self.pet._prefix_output(text))
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        self.assertFalse(cloud.long, '随口一句是「一句话」贴纸，不是进度明细')
        self.assertIn(text, cloud.transcript())
        self.assertFalse(cloud.pinned)
        self.assertEqual(self.pet.whisper(''), '')

    def test_a_banner_is_a_fresh_tag(self):
        text = '%s：今日日报已备好' % pet_agent.PET_NAME
        self.assertEqual(self.pet.banner(text), self.pet._prefix_output(text))
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_TAG)
        self.assertIn(text, cloud.transcript())
        self.assertEqual(self.pet.banner(''), '')

    def test_an_unknown_shape_name_falls_back_to_the_cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape='不存在')
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)

    def test_the_cloud_follows_the_main_window(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        seen = []
        original = cloud._place_window
        cloud._place_window = lambda: seen.append(1)
        self.addCleanup(setattr, cloud, '_place_window', original)
        cloud.follow(_Event(widget=self.win))
        self.assertEqual(seen, [1], '主窗口一动，云就重新摆位')
        cloud.follow(_Event(widget=cloud.canvas))
        self.assertEqual(seen, [1], '子控件冒泡上来的不认领')

    def test_the_main_window_carries_the_follow_binding(self):
        self.pet.cloud()
        self.assertTrue(self.win.bind('<Configure>'), '主窗口的 <Configure> 上要挂着跟位')


class SnoozeTests(PetTestCase):
    """「稍后再说」：安静一段时间，到点后同一批失败会再提醒一次；云朵框自己收起不算表态。

    第 22 期：自绘气泡删了、子菜单也收掉了——「暂停」与「稍后再说」都直接摆在一级功能栏上，
    通知只剩云朵框这一条出口。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def pause_items(self):
        """一级功能栏上的命令文字（「暂停」「稍后再说」就在其中）。"""
        menu = self.pet.menu
        return [menu.entrycget(index, "label")
                for index in range(menu.index("end") + 1)
                if menu.type(index) == "command"]

    def test_it_starts_awake(self):
        self.assertFalse(self.pet.snoozing())
        self.assertEqual(self.pet.snooze_left(), 0.0)
        self.assertIn("免打扰", self.pet.snooze_label())      # 第 44 期：这一项按附件叫「免打扰」

    def test_the_label_counts_down_the_minutes(self):
        self.pet.snooze(600)
        self.assertIn("10 分钟", self.pet.snooze_label())
        self.now += 240
        self.assertIn("6 分钟", self.pet.snooze_label())

    def test_snoozing_silences_the_notification(self):
        self.pet.snooze(600)
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertEqual(self.pet.announce_failures(), "")
        self.assertNotIn("超时", self.pet.cloud().transcript())

    def test_the_notification_comes_back_when_the_snooze_expires(self):
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertTrue(self.pet.announce_failures())
        spoken = len(self.pet.cloud().lines)
        self.pet.snooze(600)
        self.pet.agent.fail("video", "被限流", attempt=4)
        self.assertEqual(self.pet.announce_failures(), "")
        self.assertEqual(len(self.pet.cloud().lines), spoken, "安静期间一条都不许说")
        self.now += 601
        self.assertTrue(self.pet.announce_failures(), "到点后同一批要再提醒一次")
        self.assertEqual(len(self.pet.cloud().lines), spoken + 1)

    def test_the_same_batch_is_allowed_through_again(self):
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertTrue(self.pet.announce_failures())
        spoken = len(self.pet.cloud().lines)
        self.pet.snooze(60)
        self.now += 61
        self.assertTrue(self.pet.announce_failures(), "「稍后」不能变成「再也不提」")
        self.assertEqual(len(self.pet.cloud().lines), spoken + 1, "同一批要能再说一遍")

    def test_a_timeout_does_not_snooze_by_itself(self):
        self.assertFalse(self.pet.snoozing(), "气泡到点消失不是用户的表态")
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertTrue(self.pet.announce_failures())

    def test_unsnooze_restores_it_at_once(self):
        self.pet.snooze(600)
        self.pet.unsnooze()
        self.assertFalse(self.pet.snoozing())
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertTrue(self.pet.announce_failures())

    def test_toggle_flips_both_ways(self):
        self.assertGreater(self.pet.toggle_snooze(), 0)
        self.assertTrue(self.pet.snoozing())
        self.assertEqual(self.pet.toggle_snooze(), 0.0)
        self.assertFalse(self.pet.snoozing())

    def test_snooze_click_goes_quiet_and_says_for_how_long(self):
        self.assertEqual(self.pet.click('snooze'), 'snooze')
        self.assertTrue(self.pet.snoozing())
        self.assertIn('安静 %d 分钟' % (pet_ui.SNOOZE_SECONDS // 60), self.pet.notice)

    def test_the_top_level_menu_offers_pause_and_snooze(self):
        """第 22 期：「暂停」改名后与「稍后再说」一起直接摆在一级栏上，不用再点进子菜单。"""
        self.assertIn(self.pet.pause_label(), self.pause_items())
        self.assertIn(self.pet.snooze_label(), self.pause_items())

    def test_the_menu_entry_can_snooze(self):
        self.pet.menu.invoke(self.pet.menu_index['snooze'])
        self.assertTrue(self.pet.snoozing())

    def snooze_text(self):
        """功能栏上「免打扰」那一行的文字（按 menu_index 认，不靠在那排里的位置）。"""
        return self.pet.menu.entrycget(self.pet.menu_index['snooze'], 'label')

    def test_the_menu_label_follows_the_countdown(self):
        self.pet.snooze(600)
        self.assertIn("10 分钟", self.snooze_text())

    def test_the_heartbeat_keeps_the_label_fresh(self):
        self.pet.snooze(600)
        self.now += 300
        pet_ui.pump(self.fake)
        self.assertIn("5 分钟", self.snooze_text())

    def test_a_broken_clock_is_not_snoozing(self):
        self.pet.snooze_until = "坏"
        self.assertFalse(self.pet.snoozing())
        self.assertEqual(self.pet.snooze_left(), 0.0)

    def test_a_broken_cloud_is_recorded_not_raised(self):
        class Boom:
            def broadcast(self, text, hold=None):
                raise RuntimeError("浮窗画不出来")

        self.pet._cloud = Boom()
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertTrue(self.pet.announce_failures(), "说不出去也要留一句人话")
        self.assertTrue(any(name == "cloud" for name, _text in self.pet.errors))


class BusySnoozeTests(PetTestCase):
    """第 60 期第 1 条：用户正忙着按个不停时，三虎自己进免打扰（安静 15 分钟）。

    判据只是「窗口内攒够多少下用户动作」，不看前台也不看焦点——用户自己按的就是他自己在忙。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def burst(self, count, step=1.0):
        """连着按 count 下页面按钮（每下隔 step 秒），返回按完之后静没静。"""
        for _ in range(count):
            self.pet.tap('下一步')
            self.now += step
        return self.pet.snoozing()

    def test_a_burst_of_presses_puts_the_pet_to_sleep(self):
        self.assertFalse(self.burst(pet_ui.BUSY_TAPS - 1), '差一下还不到')
        self.pet.tap('下一步')
        self.assertTrue(self.pet.snoozing(), '攒满了就该自己安静')
        self.assertAlmostEqual(self.pet.snooze_left(), pet_ui.SNOOZE_SECONDS, places=3)
        self.assertIn('您在忙', self.pet.notice)

    def test_it_says_one_line_before_going_quiet(self):
        said = len(self.pet.cloud().lines)
        self.burst(pet_ui.BUSY_TAPS)
        self.assertEqual(len(self.pet.cloud().lines), said + 1, '安静前只留一句')

    def test_a_slow_trickle_never_sleeps(self):
        self.assertFalse(self.burst(pet_ui.BUSY_TAPS, step=pet_ui.BUSY_WINDOW), '按得慢就不算忙')

    def test_a_menu_click_is_counted_once(self):
        """一次点击只算一笔：act → tap_safe → click 这条链子上记两遍，阈值就等于砍了一半。"""
        for _ in range(pet_ui.BUSY_TAPS - 1):
            self.pet.act('pause')
            self.now += 1.0
        self.assertEqual(len(self.pet._busy_taps), pet_ui.BUSY_TAPS - 1, '一次点击只记一笔')
        self.pet.act(self.pet.pause_action)          # 菜单里传方法名的那一路也要记
        self.assertTrue(self.pet.snoozing(), '第 12 下照样算数')

    def test_while_snoozing_the_presses_are_not_counted(self):
        self.burst(pet_ui.BUSY_TAPS)                 # 已经安静了
        self.assertTrue(self.pet.snoozing())
        for _ in range(pet_ui.BUSY_TAPS * 2):
            self.pet.tap('下一步')
            self.now += 1.0
        self.assertEqual(self.pet._busy_taps, [], '安静期间不攒账：那不算新的一轮忙')

    def test_waking_up_clears_the_old_count(self):
        for _ in range(pet_ui.BUSY_TAPS - 1):
            self.pet.tap('下一步')
            self.now += 1.0
        self.pet.unsnooze()
        self.assertEqual(self.pet._busy_taps, [], '刚恢复别拿旧账立刻又把自己按静')

    def test_a_broken_clock_is_not_a_reason_to_sleep(self):
        self.pet.clock = lambda: '坏'
        self.assertFalse(self.pet.note_work(), '时钟读不出来就别乱静')
        self.assertFalse(self.pet.snoozing())


class ReportHintTests(PetTestCase):
    """第 36 期第 5 条：关软件前的日报／周报弹框删掉，改由三虎看工作强度自己递上来。

    原来这件事挂在「关软件那一下」（exit_banner），现在改在心跳里：下午两点之后、距上一次看见
    制作动静满 REPORT_QUIET_SECONDS（这一波活干完了）、这一天还没递过，就把报表递到眼前。
    """

    def stamp(self, month=9, day=22, hour=16):
        return datetime.datetime(2026, month, day, hour, 0).timestamp()

    def setUp(self):
        super().setUp()
        self.now = self.stamp()                      # 2026-09-22 是周二：走日报那一档
        self.pet.clock = lambda: self.now
        self.pet._work_at = None                     # 盘上没有新动静＝这一波活干完了

    def test_report_waits_for_startup_greeting_and_its_quiet_period(self):
        self.pet.schedule_greet(delay_ms=60000)
        self.assertEqual(self.pet.report_hint(at=self.now), '')
        self.assertIsNone(self.pet.report_path)
        self.pet.cancel_greet()
        self.pet.window_visible = lambda: True
        self.assertTrue(self.pet.greet(at=self.now))
        self.assertEqual(' '.join(pet_cloud.GREETING.split()), self.pet.cloud().transcript())
        self.pet.cloud_visible = lambda: False
        self.assertEqual(self.pet.report_hint(at=self.now + 1), '')
        self.assertIn('日报', self.pet.report_hint(
            at=self.now + pet_ui.GREET_QUIET_SECONDS + 1))

    def test_background_start_keeps_greeting_ahead_of_reports(self):
        self.pet._greet_id = 'expired-startup-callback'
        self.pet.window_visible = lambda: False
        self.assertEqual(self.pet.greet(at=self.now), '')
        self.assertIsNotNone(self.pet._greet_id)
        self.pet.window_visible = lambda: True
        self.assertEqual(self.pet.report_hint(at=self.now), '')
        self.pet.cancel_greet()
        self.assertTrue(self.pet.greet(at=self.now))

    def test_reminder_survives_a_fresh_pet_instance(self):
        self.assertIn('日报', self.pet.report_hint(at=self.now))
        restarted = pet_ui.Pet(self.fake, clock=lambda: self.now)
        self.addCleanup(restarted.stop)
        restarted.cloud_visible = lambda: False
        self.assertEqual(restarted.report_hint(at=self.now), '')

    def test_weekly_reminder_is_once_per_week(self):
        self.pet.cloud_visible = lambda: False
        self.assertIn('周报', self.pet.report_hint(at=self.stamp(day=25)))
        self.pet._report_key = None
        self.assertEqual(self.pet.report_hint(at=self.stamp(day=26)), '')
        self.assertEqual(self.pet.report_hint(at=self.stamp(day=27)), '')
        self.assertIn('周报', self.pet.report_hint(at=self.stamp(month=10, day=2)))

    def test_new_day_can_remind_again(self):
        self.pet.cloud_visible = lambda: False
        self.assertIn('日报', self.pet.report_hint(at=self.now))
        self.assertIn('日报', self.pet.report_hint(at=self.stamp(day=23)))

    def test_unsuccessful_banner_does_not_consume_reminder(self):
        original = self.pet.banner
        self.pet.banner = lambda text: ''
        self.assertEqual(self.pet.report_hint(at=self.now), '')
        self.pet.banner = original
        self.assertIn('日报', self.pet.report_hint(at=self.now))

    def test_the_morning_stays_quiet(self):
        self.assertEqual(self.pet.report_hint(at=self.stamp(hour=9)), '',
                         '一天才开头，报表也没什么可写')

    def test_the_afternoon_hands_over_the_daily_report(self):
        text = self.pet.report_hint(at=self.stamp())
        self.assertIn(pet_agent.PET_NAME, text)
        self.assertIn('日报', text)
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_TAG, '递报表那一眼是清新标签框')
        self.assertIn(text.split('】', 1)[-1], cloud.transcript())
        self.assertIsNotNone(self.pet.report_path, '递的同时把报表生成好')
        self.assertTrue(self.pet.report_path.is_file())

    def test_the_same_day_is_only_announced_once(self):
        self.assertTrue(self.pet.report_hint(at=self.stamp()))
        self.assertEqual(self.pet.report_hint(at=self.stamp(hour=17)), '', '当天递过就不再递')

    def test_friday_afternoon_hands_over_the_weekly(self):
        text = self.pet.report_hint(at=self.stamp(month=9, day=25))   # 2026-09-25 是周五
        self.assertIn('周报', text)
        self.assertIsNotNone(self.pet.weekly_path)

    def test_a_busy_hand_defers_the_report(self):
        self.pet._work_at = self.stamp() - pet_ui.REPORT_QUIET_SECONDS + 1
        self.assertEqual(self.pet.report_hint(at=self.stamp()), '',
                         '手上还有动静：不拿报表打断')

    def test_the_hint_carries_the_numbers_from_the_ledger(self):
        self.pet.counts = lambda: {'shots': 7, 'frames': 3}
        text = self.pet.report_hint(at=self.stamp())
        self.assertIn('7 个镜头', text)
        self.assertIn('3 张首帧', text)

    def test_quiet_when_a_dialog_is_showing(self):
        self.pet.cloud().show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        self.assertEqual(self.pet.report_hint(at=self.stamp()), '', '已经有框露着就不叠一个')

    def test_quiet_when_muted_or_not_attending(self):
        self.pet.mute(seconds=600, at=self.now)
        self.assertEqual(self.pet.report_hint(at=self.stamp()), '', '刚点掉云朵的安静期里不递')
        self.pet._mute_until = 0
        self.pet.front = lambda: False
        self.assertEqual(self.pet.report_hint(at=self.stamp()), '', '人切去其他应用了就不递')

    def test_a_broken_clock_never_raises(self):
        self.pet.clock = lambda: (_ for _ in ()).throw(RuntimeError('读不出时间'))
        self.assertEqual(self.pet.report_hint(), '')
        self.assertTrue(any(name == 'report_hint' for name, _text in self.pet.errors))


class StartupQuietTests(PetTestCase):
    """第 22 期第 9 条后半：开机第一拍只对表，不冒云（原来开机会闪一下云朵框）。

    第 43 期补：这两条走的是整条心跳（pump），不钉时钟就得跟着真实时刻红绿——第 36 期的
    日报／周报只在下午两点之后递，下午跑就会多出一朵「今日日报已备好」，量到的已经不是开机
    那一拍。钉在上午九点，这里剩下的判据就只有开机那一拍的播报。
    """

    def setUp(self):
        super().setUp()
        self.now = datetime.datetime(2026, 9, 22, 9, 0).timestamp()   # 周二上午九点
        self.pet.clock = lambda: self.now

    def test_the_first_heartbeat_only_takes_notes(self):
        self.pet.gaps = lambda at=None: ('缺 3 张首帧',)      # 假装一开机就有缺口
        self.pet.pump()
        self.assertFalse(self.pet.cloud_visible(), '开机第一拍不许冒云')
        self.assertEqual(self.pet._gap_sig, ('缺 3 张首帧',), '但指纹要记下来，后面才比得出「刚变化」')

    def test_the_same_gap_is_not_shouted_about_afterwards(self):
        self.pet.gaps = lambda at=None: ('缺 3 张首帧',)
        self.pet.pump()
        self.pet.pump()
        self.assertFalse(self.pet.cloud_visible(), '缺口没变化就不急报，等下一次按频率播报')


class ProgressBubbleTests(PetTestCase):
    """第 19 期：原来那块进度面板改成圆形气泡，冒不冒由三虎自己挑。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def test_the_bubble_is_written_into_a_long_round_shape(self):
        text = self.pet.progress_bubble('镜头：36/36')
        self.assertEqual(text, '镜头：36/36')
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_ROUND)
        self.assertTrue(cloud.long, '进度圆气泡要把整段明细写进去，不是随口一句')
        self.assertIn('镜头：36/36', cloud.transcript())

    def test_the_voice_waits_for_the_interval(self):
        self.assertEqual(self.pet.progress_voice(at=self.now), '', '第一次心跳只对表')
        self.now += pet_ui.PROGRESS_SECONDS - 1
        self.assertEqual(self.pet.progress_voice(at=self.now), '')
        self.now += 2
        self.assertTrue(self.pet.progress_voice(at=self.now))
        self.assertEqual(self.pet.cloud().shape, pet_cloud.SHAPE_ROUND)

    def test_a_sticker_keeps_the_progress_bubble_quiet(self):
        self.pet.cloud().greet()
        self.assertTrue(self.pet.cloud_visible(sticker_only=True), '云朵框露着的时候只留一个对话框')
        self.assertEqual(self.pet.progress_voice(at=self.now, force=True), '')

    def test_the_mute_after_closing_the_cloud_keeps_it_quiet(self):
        self.pet.mute(seconds=pet_ui.CHAT_MUTE_SECONDS, at=self.now)
        self.assertTrue(self.pet.muted(at=self.now))
        self.assertEqual(self.pet.progress_voice(at=self.now, force=True), '')
        self.assertFalse(self.pet.muted(at=self.now + pet_ui.CHAT_MUTE_SECONDS + 1))

    def test_the_bubble_leaves_out_what_says_nothing(self):
        """第 49 期第 3 条：气泡里不再有「顺手收了 N 个事件」这种什么也没说的话。"""
        self.pet.progress_voice(at=self.now)                 # 只对表
        self.now += pet_ui.PROGRESS_SECONDS + 1
        text = self.pet.progress_voice(at=self.now)
        self.assertTrue(text)
        self.assertEqual(self.pet.notice, text)
        self.assertNotIn('顺手收了', text)
        rows = [row for row in text.split('\n') if row.strip()]
        self.assertLessEqual(len(rows), pet_ui.PROGRESS_GAPS + 2, '圆里只留有用的几句')

    def test_an_unchanged_progress_keeps_quiet(self):
        """第 49 期第 3 条：与上一条一字不差的进度不再冒（用户要的「不许提示无用内容」）。"""
        self.pet.progress_voice(at=self.now)
        self.now += pet_ui.PROGRESS_SECONDS + 1
        first = self.pet.progress_voice(at=self.now)
        self.assertTrue(first)
        self.pet.cloud().close()
        self.now += pet_ui.PROGRESS_SECONDS + 1
        self.assertEqual(self.pet.progress_voice(at=self.now), '', '一样的话不再占一次')
        self.pet.gaps = lambda at=None, force=False: ['首帧还差 36 个镜头（08 首帧管理 → 手动制作首帧）']
        self.pet.cloud().close()
        self.assertTrue(self.pet.progress_voice(at=self.now), '进度真变了就不算重复，照样说')

    def test_the_progress_interval_is_ten_minutes(self):
        """第 49 期第 3 条：提示频率降低——进度气泡十分钟一次、播报忙时两分钟／闲时十分钟。"""
        self.assertGreaterEqual(pet_ui.PROGRESS_SECONDS, 600.0)
        self.assertGreaterEqual(pet_ui.BROADCAST_BUSY, 120.0)
        self.assertGreaterEqual(pet_ui.BROADCAST_IDLE, 600.0)


class DuplicateVoiceTests(PetTestCase):
    """第 57 期第 2 条：进度那条消息有两条入口（心跳播报与进度圆气泡），同一件事只说一遍。

    底下这些用例盯的就是那本「刚说过什么」的短账（_spoken）：另一条入口说过的进度／缺口
    在窗口内不再重复；缺口真变了是急事，照样立刻说。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.counts = {"storyboards": 0, "adopted": 0, "shots": 0, "frames": 0}
        self.pet.counts = lambda: dict(self.counts)

    def test_the_broadcast_does_not_repeat_what_the_bubble_said(self):
        self.pet.progress_voice(at=self.now)              # 第一拍只对表
        self.pet.tick_broadcast(at=self.now)              # 播报也第一拍只对表
        self.now += pet_ui.PROGRESS_SECONDS + 1
        self.assertTrue(self.pet.progress_voice(at=self.now), "圆气泡先说了这一句进度")
        self.pet.cloud().close()
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.assertEqual(self.pet.tick_broadcast(), "",
                         "同一句进度刚由圆气泡说过，播报不再重复一遍")

    def test_the_bubble_does_not_repeat_what_the_broadcast_said(self):
        self.pet.progress_voice(at=self.now)              # 只对表
        self.pet.tick_broadcast(at=self.now)              # 只对表
        self.now += pet_ui.BROADCAST_IDLE + 1
        said = self.pet.tick_broadcast()
        self.assertTrue(said, "播报先说了这一句进度")
        self.pet.cloud().close()
        self.now += pet_ui.PROGRESS_SECONDS + 1
        self.assertEqual(self.pet.progress_voice(at=self.now), "",
                         "刚由播报说过的那一句，圆气泡不再说第二遍")

    def test_the_same_thing_is_said_again_after_the_window(self):
        self.pet.progress_voice(at=self.now)
        self.pet.tick_broadcast(at=self.now)
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.assertTrue(self.pet.tick_broadcast())
        self.pet.cloud().close()
        self.now += pet_ui.SPEAK_GAP_SECONDS + 1
        self.assertTrue(self.pet.progress_voice(at=self.now),
                        "过了窗口就该轮到另一条入口说话，不是永远不说")

    def test_a_changed_gap_is_still_news(self):
        self.pet.tick_broadcast(at=self.now)              # 第一拍只对表
        self.pet.progress_voice(at=self.now)
        self.now += pet_ui.PROGRESS_SECONDS + 1
        self.assertTrue(self.pet.progress_voice(at=self.now))
        self.pet.cloud().close()
        self.counts["storyboards"] = 3                    # 缺口真变了：这是新消息
        self.now += pet_ui.GAP_SECONDS + 1
        self.assertIn("分镜 JSON", self.pet.tick_broadcast(),
                      "缺口一变就是急事，这道闸不拦它")

    def test_a_broken_clock_keeps_talking(self):
        self.pet.clock = lambda: "坏钟"
        self.assertFalse(self.pet.seen_recently(("progress", "x")))
        self.assertIsNone(self.pet.mark_spoken(("progress", "x")))
        self.pet.clock = lambda: self.now
        self.assertFalse(self.pet.seen_recently(("progress", "x")), "记不下来就当没说过")


class PanelQuietTests(PetTestCase):
    """用户主动查看进度后，自动播报按固定频率让路。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.seen = []
        self.fake.pet_show_text = lambda title, text, receipt=None: self.seen.append((title, text))

    def test_the_user_opening_the_panel_keeps_the_bubble_quiet(self):
        self.pet.show_panel()
        self.assertEqual(self.seen, [], '进度面板不再交给只读文本窗')
        self.assertTrue(self.pet.cloud().visible, '进度面板应在三虎提示框展示')
        self.assertTrue(self.pet.panel_quiet(at=self.now), '记下了「用户自己打开过面板」')
        # 他正看着明细这一拍里：连强制冒的那一次也得让路（force 绕不过这道闸）。
        self.assertEqual(self.pet.progress_voice(at=self.now + pet_ui.PROGRESS_SECONDS - 1, force=True), '',
                         '他正看着明细，不许再弹气泡')
        self.assertTrue(self.pet.cloud().visible, '用户主动打开的进度提示框应保持展示')

    def test_the_fixed_frequency_resumes_after_the_quiet_window(self):
        self.pet.show_panel()
        self.now += pet_ui.PROGRESS_SECONDS + 1
        self.assertFalse(self.pet.panel_quiet(at=self.now))
        self.pet.cloud().close()                   # 测试时钟不驱动 Tk 的自动收起，手动模拟提示框已读完
        self.pet.progress_voice(at=self.now)                 # 只对表
        self.now += pet_ui.PROGRESS_SECONDS + 1
        self.assertTrue(self.pet.progress_voice(at=self.now), '过了安静期就照固定频率继续提示')
        self.assertEqual(self.pet.cloud().shape, pet_cloud.SHAPE_ROUND)


class RecordScopeTests(PetTestCase):
    """第 24 期第 5 条：云朵记录只有三虎的播报与用户的聊天，操作步骤不进记录。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def panel_text(self):
        return '\n'.join('%s：%s' % (name, value) for name, value in self.pet.rows())

    def test_the_status_bar_steps_stay_out_of_the_cloud_record(self):
        self.pet.pump(at=self.now)                       # 第一次心跳只对表
        self.pet.say('正在导出交付包…')
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.pet.pump(at=self.now)
        self.assertIn('正在导出交付包', self.pet.last_status, '状态栏照旧写着这一步')
        self.assertIn('正在导出交付包', self.panel_text(), '进度面板里也要有')
        self.assertNotIn('正在导出交付包', self.pet.cloud().transcript(),
                         '云朵记录里不该有用户的操作步骤')

    def test_a_step_on_its_own_does_not_open_the_bubble(self):
        self.pet.pump(at=self.now)
        self.pet.say('已切换到资产管理页')
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.pet.pump(at=self.now)
        self.assertNotIn('已切换到资产管理页', self.pet.cloud().transcript())

    def test_the_pets_own_words_are_still_recorded(self):
        self.pet.pump(at=self.now)
        self.pet.announce('今天该做的都做完了')
        self.pet.cloud().close()
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.pet.pump(at=self.now)
        self.assertIn('今天该做的都做完了', self.pet.cloud().transcript(), '三虎自己说的话要留下')

    def test_the_confirmed_task_is_still_recorded(self):
        cloud = self.pet.cloud()
        self.pet.open_chat()
        cloud.propose('查一下进度')
        self.addCleanup(self.wait_for_the_reply, cloud)
        cloud.submit()
        self.assertTrue(any(line.startswith('您：') for line in cloud.lines), '聊天记录要留下')


class LevelNotesTests(PetTestCase):
    """第 24 期第 4 条：切到某一档时，圆形气泡里要带一句「这一档怎么干活」。"""

    def test_every_note_explains_the_level(self):
        for level in pet_agent.LEVELS:
            with self.subTest(level=level):
                note = pet_ui.LEVEL_SWITCH_NOTES[level]
                self.assertTrue(note.startswith(pet_agent.LEVEL_NAMES[level] + '：'), note)
                self.assertIn('：', note, '光说「已切换」不够，后面要跟一句说明')

    def test_the_hint_note_says_the_pet_will_not_touch_anything(self):
        self.assertIn('不自动制作', pet_ui.LEVEL_SWITCH_NOTES['hint'])

    def test_the_auto_note_says_paid_steps_still_need_a_nod(self):
        note = pet_ui.LEVEL_SWITCH_NOTES['auto']
        self.assertIn('付费', note)
        self.assertIn('阻塞', note)

    def test_the_notes_are_short_enough_for_a_round_bubble(self):
        for level, note in pet_ui.LEVEL_SWITCH_NOTES.items():
            self.assertLessEqual(len(note), 60, level + ' 太长，圆气泡里读不完')


class FailureVoiceTests(PetTestCase):
    """第 71 期任务 1：认不出类目的错误要把原因原文说出来。

    原来任何失败都只念 VERDICTS['unknown'] 那句模板（「没见过的错误：停下等您确认」），
    真正的原因被盖在下面——用户看到的就只有一句「没见过的错误」，不知道该修什么。
    """

    def test_an_unknown_failure_says_the_real_reason(self):
        self.pet.agent.fail("previs", "自动制作中断：ComfyUI 进程已退出（退出代码 4294967295）")
        text = self.pet.announce_failures()
        self.assertIn("ComfyUI 进程已退出", text, "原因原文要看得见")
        self.assertIn("白模预演", text, "还得说清是哪个阶段")

    def test_a_known_failure_still_says_what_to_do(self):
        """认得出类目的错误：原因照说，建议（退避／降级那一条）跟在后面。"""
        item = pet_agent.verdict("timeout", "请求超时，请重试")
        item["stage"] = "keyframe"
        self.pet.agent.failures.append(item)
        text = self.pet.announce_failures()
        self.assertIn("首帧管理", text, "还得说清是哪个阶段")
        self.assertIn("请求超时", text, "原因原文照说")
        self.assertIn("退避", text, "分得出类目的错误照旧给建议")

    def test_an_exhausted_retry_still_tells_the_reason(self):
        """重试用尽也不再只留一句「交给您确认」——原因照旧看得见。"""
        self.pet.agent.fail("keyframe", "请求超时，请重试", attempt=4)
        text = self.pet.announce_failures()
        self.assertIn("请求超时", text, "原因原文要看得见")
        self.assertIn("交给您确认", text, "用尽了也要说清在等您")

    def test_the_details_page_lists_the_reason_first(self):
        self.pet.agent.fail("previs", "自动制作中断：ComfyUI 进程已退出")
        text = self.pet.details_text()
        self.assertIn("原因：自动制作中断", text)
        self.assertIn("建议：", text)


class StallWatchTests(unittest.TestCase):
    """SANHU-PROACTIVE-STATS：阶段显示在跑、子进度满 10 分钟没动 → 一句停滞提醒，同一波只报一次。"""

    def stages(self, state='running', detail={'done': 3, 'total': 40}):
        return {'storyboard': {'state': state, 'detail': detail}}

    def test_stall_watch_fires_after_ten_quiet_minutes(self):
        ticks = [1000.0]
        watch = pet_context_facts.StallWatch(clock=lambda: ticks[0])
        stages = self.stages()
        self.assertIsNone(watch.sample(stages))          # 第一眼起表，不报
        ticks[0] += 599
        self.assertIsNone(watch.sample(stages), '差一秒不到点：还不报')
        ticks[0] += 1
        hit = watch.sample(stages)
        self.assertIsNotNone(hit)
        self.assertEqual((hit[0], hit[2], hit[3]), ('storyboard', 3, 40))
        self.assertEqual(hit[1], 10, '返回值里带着停了几分钟')

    def test_stall_watch_same_stall_fires_only_once(self):
        ticks = [0.0]
        watch = pet_context_facts.StallWatch(clock=lambda: ticks[0])
        stages = self.stages()
        watch.sample(stages)
        ticks[0] += 660
        self.assertIsNotNone(watch.sample(stages))
        ticks[0] += 120
        self.assertIsNone(watch.sample(stages), '同一波停滞不重报')

    def test_stall_watch_progress_resets_the_clock(self):
        ticks = [0.0]
        watch = pet_context_facts.StallWatch(clock=lambda: ticks[0])
        stages = self.stages()
        watch.sample(stages)
        ticks[0] += 500
        stages['storyboard']['detail'] = {'done': 4, 'total': 40}
        self.assertIsNone(watch.sample(stages), 'done 动过：计时清零')
        ticks[0] += 599
        self.assertIsNone(watch.sample(stages))
        ticks[0] += 1
        hit = watch.sample(stages)
        self.assertIsNotNone(hit)
        self.assertEqual((hit[2], hit[3]), (4, 40))

    def test_stall_watch_running_without_detail_is_not_counted(self):
        ticks = [0.0]
        watch = pet_context_facts.StallWatch(clock=lambda: ticks[0])
        stages = self.stages(detail=None)
        watch.sample(stages)
        ticks[0] += 1200
        self.assertIsNone(watch.sample(stages), '刚启动还没报子进度：不计时不报')

    def test_stall_watch_ignores_settled_and_failed_states(self):
        ticks = [0.0]
        watch = pet_context_facts.StallWatch(clock=lambda: ticks[0])
        for state in ('failed', 'success', 'pending', 'skipped'):
            with self.subTest(state=state):
                stages = self.stages(state=state)
                watch.sample(stages)
                ticks[0] += 1200
                self.assertIsNone(watch.sample(stages), '%s 不该报' % state)

    def test_stall_watch_retrying_counts_as_running(self):
        ticks = [0.0]
        watch = pet_context_facts.StallWatch(clock=lambda: ticks[0])
        stages = self.stages(state='retrying')
        watch.sample(stages)
        ticks[0] += 600
        self.assertIsNotNone(watch.sample(stages))

    def test_stall_watch_note_text(self):
        text = pet_context_facts.format_stall_note('storyboard', 12, 3, 40)
        self.assertIn('03 初步分镜', text)
        self.assertIn('12 分钟', text)
        self.assertIn('3/40', text)


class StallVoiceTests(PetTestCase):
    """停滞提醒的三虎侧接线：文案、免打扰只记账、心跳每 200 拍问一次。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.pet.counts = lambda: {}

    def _stalled(self, stage='storyboard', done=3, total=40):
        self.pet.machine.start(stage)
        self.pet.machine.detail(stage, done, total)
        self.pet.stall_note(at=self.now)                 # 第一眼起表
        self.now += 660                                  # 子进度 11 分钟没动

    def test_stall_watch_note_names_stage_minutes_and_done(self):
        self._stalled()
        note = self.pet.stall_note(at=self.now)
        self.assertIn('初步分镜', note)
        self.assertIn('11 分钟', note)
        self.assertIn('3/40', note)

    def test_stall_watch_snooze_only_books_the_stall(self):
        """免打扰里不播：这一波留着记账，安静期一过补说一句。"""
        self._stalled()
        self.pet.snooze(600)
        self.assertEqual(self.pet.stall_note(at=self.now), '', '免打扰里不播')
        self.assertNotIn('停滞', self.pet.cloud().transcript())
        self.now += 601
        self.assertIn('停滞', self.pet.stall_note(at=self.now), '出期补报同一波')

    def test_stall_watch_note_records_without_popping_when_away(self):
        """人不在助手界面：播报出口只记账不冒框。"""
        self.pet.front = lambda: False
        self._stalled()
        self.pet.announce(self.pet.stall_note(at=self.now))
        self.assertIn('停滞', self.pet.cloud().transcript())
        self.assertFalse(self.pet.cloud().visible)

    def test_stall_watch_pump_asks_once_every_two_hundred_ticks(self):
        calls = []
        self.pet.stall_note = lambda at=None: calls.append(at) or ''
        for _ in range(199):
            self.pet.pump()
        self.assertEqual(len(calls), 0, '前 199 拍不问')
        self.pet.pump()
        self.assertEqual(len(calls), 1, '第 200 拍问一次')
        for _ in range(200):
            self.pet.pump()
        self.assertEqual(len(calls), 2)

    def test_stall_watch_pump_announces_through_the_failure_exit(self):
        """非空就走失败播报同一个出口（announce）。"""
        heard = []
        self.pet.announce = lambda text, **kw: heard.append(text)
        note = '【阶段停滞】「03 初步分镜」已经在跑 11 分钟没有新进度（完成 3/40），要我看看吗？'
        self.pet.stall_note = lambda at=None: note
        for _ in range(200):
            self.pet.pump()
        self.assertEqual(heard, [note])

    def test_stall_watch_pump_speaks_a_real_stall_once(self):
        """全链路：machine 卡 11 分钟 → 第 200 拍说一句；再 200 拍不重播。"""
        self._stalled()
        for _ in range(200):
            self.pet.pump(at=self.now)
        self.assertIn('停滞', self.pet.cloud().transcript())
        said = self.pet.cloud().transcript().count('停滞')
        for _ in range(200):
            self.pet.pump(at=self.now)
        self.assertEqual(self.pet.cloud().transcript().count('停滞'), said, '同一波不重播')


if __name__ == '__main__':
    unittest.main()
