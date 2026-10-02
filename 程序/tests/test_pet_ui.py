# -*- coding: utf-8 -*-
"""宠物贴片自检：右上角几何与随窗移动、动画帧与帧率、气泡一键操作、面板数字与状态机一致，
以及三个接缝（自动任务队列 / 状态栏 / 页面按钮）只上报不改原逻辑。
第 6 期再加：日报／周报的数据与落盘、独立窗开关与常驻、开机自启（假注册表，不碰真注册表）。运行：python test_pet_ui.py"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import datetime, json, os, re, sys, tempfile, time, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

import model_pool
import model_secrets
import pet_models_ui
import pet_agent, pet_bus, pet_cloud, pet_report, pet_ui, stage_flow

# 第 45 期：这些用例读的（并会写的）是全局配置目录里那一份三虎设置。原来 program 指向本机真
# 安装目录，于是「出厂默认档是半自动」这类断言会被用户机上那份配置左右（那里存过 hint 就红）。
# 指到沙盒目录：读不到真配置，也写不脏真安装目录（见 selftest_sandbox 的说明）。
import selftest_sandbox
selftest_sandbox.isolate(pet_ui)


def make_project(td):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    (proj / "episode" / "episode.json").write_text(json.dumps({"episode_id": "EP001", "title": "T", "shots": []},
                                                               ensure_ascii=False), encoding="utf-8")
    return proj


class _Event:
    """最小事件替身：只带一个 widget，用来验证别认领子组件冒泡上来的事件。"""

    def __init__(self, widget):
        self.widget = widget


class _Point:
    """只带 x 的点击替身：猫爪按钮按 x 落在第几只爪上来选档。"""

    def __init__(self, x):
        self.x = x


class _Wheel:
    """最小滚轮事件替身：只带一个 delta（往下滚是负）。"""

    def __init__(self, delta):
        self.delta = delta


class SequenceRand:
    """按给定序列出数的假随机源：用例要的是可复现，不是真随机（第 17 期猫样用）。"""

    def __init__(self, values=(0.0,)):
        self.values = [float(value) for value in values] or [0.0]
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class _Registry:
    """最小项目登记表替身：只有一个 .info（与 projects.Projects 那一份同形）。"""

    def __init__(self, active, projects):
        self.info = {'active': active, 'projects': list(projects)}


class FakeDesktop:
    """最小宿主：只提供贴片真正用到的几个容器与开关，避免为了画宠物去建整个应用。"""

    def __init__(self, tk, ttk, win):
        self.win = win
        self.root = None
        self.shutting_down = False
        self.kicks = []
        self.pages = []          # pet_goto 切过哪几步
        self.advances = []       # pet_advance 叫醒过哪几步
        self.deaf = ()           # 放进这里的阶段：pet_advance 一律说「没有这条路」
        self.title_row = ttk.Frame(win)
        self.title_row.pack(fill="x")
        self.body = ttk.Frame(win)
        self.body.pack(fill="both", expand=True)
        self.header_status = ttk.Label(self.title_row, text="就绪")
        self.header_status.pack(side="right")
        self.header_model = ttk.Label(self.title_row, text="模型")
        self.header_model.pack(side="right")
        self.status = tk.StringVar(master=win, value="就绪")

    def kick_unattended(self, source):
        self.kicks.append(source)

    def pet_goto(self, stage):
        """第 23 期接缝：切页。记下切到哪一步，回一句页面名。"""
        self.pages.append(stage)
        return pet_bus.STAGE_NAMES.get(stage, '')

    def pet_advance(self, stage):
        """第 23 期接缝：把某一步提前叫醒一轮；deaf 里的阶段一律答「没有这条路」。"""
        if stage in self.deaf:
            return ''
        self.advances.append(stage)
        return '已把「%s」这一步提前叫醒一轮' % pet_bus.STAGE_NAMES.get(stage, stage)

    def asset_base(self):
        return self.root / "episode"


class PetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = FakeDesktop(self.tk, self.ttk, self.win)
        self.fake.root = make_project(self.tmp.name)
        # window／tray／toast=False：这些都默认开（第 16 期起），自检一律显式关掉，
        # 免得用例去碰真托盘图标、真浮窗，跑起来还得看本机配置。
        self.pet = pet_ui.attach(self.fake, autostart=False)
        # 一键执行前会弹确认框：用例里换成「一律点头」的假函数，不弹真窗也不卡住用例。
        self.pet.asker = lambda title, text: True
        # 第 43 期：模型池／三虎设置都落在这个临时目录里，自检绝不碰真安装目录的配置。
        self.pet.program = Path(self.tmp.name)
        # 真实退出先由宿主停止宠物、再销毁 Tk 根窗；用例也保持相同顺序，
        # 否则根窗抢先清 Tcl 命令会把仍在队列里的定位重试误报成 Tcl 生命周期错误。
        self.addCleanup(self.pet.stop)
        self.addCleanup(self.win.destroy)

    def pad_of(self, widget):
        return [int(float(item)) for item in re.findall(r"-?\d+\.?\d*", str(widget.cget("padding")))]


class GeometryTests(PetTestCase):
    def test_pet_sits_at_the_top_right_of_the_title_row(self):
        info = self.pet.canvas.place_info()
        self.assertEqual(float(info["relx"]), 1.0)
        self.assertEqual(float(info["rely"]), 0.0)
        self.assertEqual(info["anchor"], "ne")
        self.assertEqual(int(self.pet.canvas.cget("width")), pet_ui.SIZE)
        self.assertEqual(int(self.pet.canvas.cget("height")), pet_ui.SIZE)
        # 第 18 期：贴片往左挪了一个身位（原来贴着窗口右边，猫脸被控件压住）。
        self.assertEqual(int(info["x"]), pet_ui.PATCH_X)
        self.assertLessEqual(pet_ui.PATCH_X, -pet_ui.SIZE)

    def test_pet_lives_inside_the_title_row(self):
        self.assertEqual(str(self.pet.canvas.winfo_parent()), str(self.fake.title_row))
        self.assertIs(self.pet.canvas.winfo_toplevel(), self.win)

    def test_header_text_leaves_room_for_the_pet(self):
        for widget in (self.fake.header_status, self.fake.header_model):
            self.assertGreaterEqual(self.pad_of(widget)[2], pet_ui.SIZE)


class MainWindowRestoreTests(PetTestCase):
    """任务栏最小化不能被 winfo_viewable 的 Windows 语义误判为可见。"""

    def test_iconic_window_is_not_treated_as_visible(self):
        original_state = self.win.state
        original_viewable = self.win.winfo_viewable
        self.win.state = lambda *args: 'iconic' if not args else None
        self.win.winfo_viewable = lambda: True
        self.addCleanup(setattr, self.win, 'state', original_state)
        self.addCleanup(setattr, self.win, 'winfo_viewable', original_viewable)
        self.assertFalse(self.pet.window_visible())

    def test_show_main_restores_iconic_window_before_showing_it(self):
        calls = []
        original_state = self.win.state
        original_viewable = self.win.winfo_viewable
        original_deiconify = self.win.deiconify
        original_update = self.win.update_idletasks
        original_lift = self.win.lift
        original_focus = self.win.focus_force
        original_attributes = self.win.attributes
        original_after_idle = self.win.after_idle
        self.win.state = lambda *args: calls.append(('state', args)) or ('iconic' if not args else None)
        self.win.winfo_viewable = lambda: True
        self.win.deiconify = lambda: calls.append(('deiconify',))
        self.win.update_idletasks = lambda: calls.append(('update_idletasks',))
        self.win.lift = lambda: calls.append(('lift',))
        self.win.focus_force = lambda: calls.append(('focus_force',))
        self.win.attributes = lambda *args: calls.append(('attributes', args))
        self.win.after_idle = lambda callback: calls.append(('after_idle',)) or callback()
        self.addCleanup(setattr, self.win, 'state', original_state)
        self.addCleanup(setattr, self.win, 'winfo_viewable', original_viewable)
        self.addCleanup(setattr, self.win, 'deiconify', original_deiconify)
        self.addCleanup(setattr, self.win, 'update_idletasks', original_update)
        self.addCleanup(setattr, self.win, 'lift', original_lift)
        self.addCleanup(setattr, self.win, 'focus_force', original_focus)
        self.addCleanup(setattr, self.win, 'attributes', original_attributes)
        self.addCleanup(setattr, self.win, 'after_idle', original_after_idle)
        self.assertTrue(self.pet.show_main())
        self.assertEqual(calls[:3], [('state', ()), ('deiconify',), ('state', ('normal',))])
        self.assertIn(('state', ('normal',)), calls)
        self.assertIn(('attributes', ('-topmost', True)), calls)
        self.assertIn(('attributes', ('-topmost', False)), calls)
        self.assertEqual(calls[-1], ('focus_force',))

    def test_show_main_keeps_restore_successful_when_focus_is_rejected(self):
        original_focus = self.win.focus_force
        self.win.focus_force = lambda: (_ for _ in ()).throw(RuntimeError('focus denied'))
        self.addCleanup(setattr, self.win, 'focus_force', original_focus)
        self.assertTrue(self.pet.show_main())
        self.assertTrue(any(name == 'show_main.focus' for name, _ in self.pet.errors))


class AnimationTests(PetTestCase):
    def test_frames_draw_eyes_and_blink(self):
        self.pet.draw(0)
        self.assertEqual(len(self.pet.canvas.find_withtag('eye-dot')), 2)
        self.pet.draw(3)
        self.assertEqual(len(self.pet.canvas.find_withtag('eye-line')), 2)
        self.assertEqual(len(self.pet.canvas.find_withtag('eye-dot')), 0)

    def test_step_advances_the_frame_and_keeps_a_timer(self):
        start = self.pet.frame
        self.pet.step()
        self.assertEqual(self.pet.frame, start + 1)
        self.assertIsNotNone(self.pet._timer)

    def test_rate_is_slow_when_idle_and_fast_while_working(self):
        for stage in pet_bus.STAGES:
            self.pet.machine.skip(stage)
        self.assertEqual(self.pet.mood(), 'idle')
        self.assertEqual(self.pet.interval(), pet_ui.IDLE_MS)
        self.pet.machine.start('script')
        self.assertEqual(self.pet.mood(), 'busy')
        self.assertEqual(self.pet.interval(), pet_ui.ACTIVE_MS)

    def test_paused_and_worried_moods(self):
        self.pet.agent.pause('配额用完')
        self.assertEqual(self.pet.mood(), 'paused')
        self.pet.agent.resume()
        self.pet.agent.fail('keyframe', '命中内容审核', attempt=4)
        self.assertEqual(self.pet.mood(), 'worry')

    def test_stop_cancels_the_timer(self):
        self.pet.step()
        self.pet.stop()
        self.assertIsNone(self.pet._timer)

    def test_step_never_stacks_two_timers(self):
        """build() 已经排了一个定时器，再手动 step()（自测与调试里都在用）不能叠出第二个。

        叠了就是双倍频，而且关窗时只取消得掉最后一个——剩下那个到期报 invalid command name "…step"。
        """
        win = self.tk.Tk()
        win.withdraw()
        try:
            fake = FakeDesktop(self.tk, self.ttk, win)
            fake.root = Path(self.tmp.name)
            pet = pet_ui.attach(fake, autostart=False)
            pet.step()
            pet.step()
            jobs = [str(job) for job in win.tk.call('after', 'info')]
            self.assertEqual(len([item for item in jobs if 'step' in item]), 1, '宠物定时器叠了第二个')
            win.destroy()
            left = [str(job) for job in win.tk.call('after', 'info')]
            self.assertEqual([item for item in left if 'step' in item], [], '窗口销毁后还留着宠物定时器')
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass


class SeamTests(PetTestCase):
    def test_stage_queue_reports_the_drain_and_forwards_it(self):
        seen = []
        box = pet_ui.StageQueue("keyframe", lambda stage, item: seen.append((stage, item)))
        item = (True, "自动补首帧完成：3 张")
        box.put(item)
        self.assertEqual(box.get_nowait(), item)
        self.assertEqual(seen, [("keyframe", item)])

    def test_stage_queue_forwards_the_rest_of_the_api(self):
        box = pet_ui.StageQueue("video")
        box.put((False, "失败"))
        self.assertFalse(box.empty())
        self.assertEqual(box.get(timeout=1), (False, "失败"))
        self.assertTrue(box.empty())
        self.assertEqual(box.qsize(), 0)

    def test_broken_sink_never_breaks_the_drain(self):
        def boom(stage, item):
            raise RuntimeError("sink 自己炸了")
        box = pet_ui.StageQueue("assets", boom)
        box.put((True, "自动补资产完成"))
        self.assertEqual(box.get_nowait(), (True, "自动补资产完成"))
        self.assertEqual(box.errors, [('sink', 'sink 自己炸了')],
                         '通知支线失败可降级，但必须留下可核原因')

    def test_status_var_keeps_the_original_text(self):
        var = pet_ui.watch_status(self.fake, self.pet)
        self.assertIs(var, self.fake.status)
        self.assertTrue(getattr(var, "_petWatched", False))
        var.set("已自动生成定稿。")
        self.assertEqual(var.get(), "已自动生成定稿。")
        self.assertEqual(self.pet.last_status, "已自动生成定稿。")
        var.set("已自动生成定稿。")
        self.assertEqual(len(self.pet.agent.notifier.pending), 1)

    def test_status_var_wraps_the_existing_variable_exactly_once(self):
        var = pet_ui.watch_status(self.fake, self.pet)
        self.assertIs(var, self.fake.status)
        self.assertIs(pet_ui.watch_status(self.fake, self.pet), var)
        var.set("只记一笔")
        var.set("只记一笔")
        self.assertEqual(len(self.pet.agent.notifier.pending), 1)

    def test_watch_status_without_a_status_var_is_a_noop(self):
        class Bare:
            pass
        self.assertIsNone(pet_ui.watch_status(Bare(), self.pet))

    def test_drain_success_without_an_artifact_stays_paused(self):
        self.pet.drain("keyframe", (True, "自动补首帧完成：3 张"))
        pet_ui.pump(self.fake)
        kinds = [(item["kind"], item["stage"]) for item in self.pet.bus.history]
        self.assertIn(("stage.paused", "keyframe"), kinds)
        self.assertNotIn(("stage.completed", "keyframe"), kinds)

    def test_report_done_without_an_artifact_cannot_complete_a_stage(self):
        self.pet.report_done("video", "自动补视频完成：1 个镜头")
        pet_ui.pump(self.fake)
        kinds = [(item["kind"], item["stage"]) for item in self.pet.bus.history]
        self.assertIn(("stage.paused", "video"), kinds)
        self.assertNotIn(("stage.completed", "video"), kinds)

    def test_drain_failure_goes_through_the_classifier(self):
        first = self.pet.drain("video", (False, "自动补视频未完成：HTTP 503 服务不可用"))
        self.assertEqual(first["category"], "server")
        self.assertTrue(first["allow"])
        self.assertEqual(self.pet.attempts["video"], 1)
        # 第 63 期任务 2.1～2.11：视频生成的重试上限是 2 次（与用户设的上限取小），
        # 第三次失败就等您确认，不再自动重来。
        second = self.pet.drain("video", (False, "自动补视频未完成：HTTP 503 服务不可用"))
        self.assertTrue(second["allow"])
        self.assertEqual(self.pet.attempts["video"], 2)
        last = self.pet.drain("video", (False, "自动补视频未完成：HTTP 503 服务不可用"))
        self.assertFalse(last["allow"])
        self.assertEqual(self.pet.attempts["video"], 0)
        self.assertEqual(len(self.pet.agent.failures), 1)
        self.assertEqual(self.pet.agent.failures[0]["policy"], "manual")   # 视频用尽后是「待您处理」
        self.pet.drain("video", (True, "自动补视频完成：1 个镜头"))
        self.assertEqual(self.pet.attempts["video"], 0)

    def test_tap_reports_after_the_original_action(self):
        order = []

        def action():
            order.append("action")
            return "结果"

        self.assertEqual(pet_ui.tap(self.fake, "导出交付", action), "结果")
        self.assertEqual(order, ["action"])
        pet_ui.pump(self.fake)
        item = [event for event in self.pet.bus.history if event["kind"] == "intent.command"][-1]
        self.assertEqual((item["text"], item["source"]), ("导出交付", "button"))

    def test_tap_keeps_the_error_for_the_caller(self):
        def boom():
            raise ValueError("按钮自己报错")
        with self.assertRaises(ValueError):
            pet_ui.tap(self.fake, "导出交付", boom)

    def test_pump_on_a_desktop_without_pet_is_a_noop(self):
        class Bare:
            pass
        self.assertEqual(pet_ui.pump(Bare()), 0)


class FakeWinreg:
    """假注册表：只实现 Autostart 用到的那几个名字与函数，真注册表一行都不碰。"""

    HKEY_CURRENT_USER = 'HKCU'
    KEY_READ, KEY_SET_VALUE, REG_SZ = 1, 2, 3

    def __init__(self, fail_read=False, fail_write=False):
        self.values = {}
        self.fail_read = fail_read
        self.fail_write = fail_write

    def OpenKey(self, root, key, reserved, access):
        if self.fail_read:
            raise OSError('读不回来')
        return _Handle(self)

    def CreateKeyEx(self, root, key, reserved, access):
        if self.fail_write:
            raise OSError('写不进去')
        return _Handle(self)

    def QueryValueEx(self, handle, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, handle, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, handle, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        self.values.pop(name)


class _Handle:
    """注册表句柄：Autostart 用 with 打开，这里只负责进出。"""

    def __init__(self, api):
        self.api = api

    def __enter__(self):
        return self.api

    def __exit__(self, *exc):
        return False


class ReportTests(PetTestCase):
    """第 6 期：日报／周报的数据来源、落盘位置与菜单接线。"""

    def menu_items(self):
        """菜单上**点得动**的那几项（第 60 期第 2 条起栏里多了几行灰色小标题：它们也是
        type='command'，但 state='disabled'，不是给用户按的）。"""
        items = []
        for index in range(self.pet.menu.index('end') + 1):
            if self.pet.menu.type(index) != 'command':
                continue
            if str(self.pet.menu.entrycget(index, 'state')) == 'disabled':
                continue
            items.append((index, self.pet.menu.entrycget(index, 'label')))
        return items

    def index_of(self, label):
        for index, text in self.menu_items():
            if text == label:
                return index
        raise AssertionError('菜单里没有这一项：' + label)

    def record(self, prompt, cached, tier='flash'):
        self.pet.agent.client.ledger.record('deepseek-v4-' + tier,
                                            {'prompt_tokens': prompt, 'completion_tokens': 10,
                                             'cached_tokens': cached}, tier=tier)

    def test_the_menu_carries_only_the_entries_that_are_left(self):
        """第 19 期精简：日报／周报、显示主窗口、收集事件都从功能栏搬走或删掉了。

        第 44 期：用户附件把「退出」摆回功能栏最后一行，所以它不再算「搬走的那一项」。
        """
        labels = [text for _index, text in self.menu_items()]
        for label in ('向三虎提问', '一键执行（重试＋补首帧＋日报）', pet_ui.QUIT_LABEL):
            self.assertIn(label, labels)
        for gone in ('生成今日日报', '生成本周周报', '显示主窗口（从常驻切回主界面）',
                     '收集事件', '系统托盘（未开启）'):
            self.assertNotIn(gone, labels, gone + ' 已经搬走／删掉')
        self.assertEqual([text for text in labels if text.startswith('开机自启')], [],
                         '开机自启默认开着，不再占一行')

    def test_report_numbers_come_from_the_ledger(self):
        self.record(100, 80, 'flash')
        self.record(100, 0, 'pro')
        tokens = self.pet.report()['tokens']
        self.assertEqual((tokens['prompt'], tokens['completion'], tokens['cached']), (200, 20, 80))
        self.assertEqual((tokens['entries'], tokens['flash_entries']), (2, 1))
        self.assertEqual(tokens['hit_rate'], 0.4)
        self.assertEqual(tokens['flash_share'], 0.5)
        self.assertEqual(tokens['budget'], 2000000)

    def test_report_progress_matches_the_state_machine(self):
        self.pet.machine.start('script')
        self.pet.machine.detail('script', 3, 6)
        data = self.pet.report()
        self.assertEqual(data['percent'], round(100.0 * 0.5 / len(pet_bus.STAGES), 1))
        self.assertEqual((data['stage'], data['done_stages']), ('script', 0))
        self.assertEqual(data['total_stages'], len(pet_bus.STAGES))
        # gather() 把阶段表归一成 {阶段: 状态字符串}，日报正文也是这么用的。
        self.assertEqual(data['stages']['script'], 'running')
        self.assertEqual(data['project'], self.fake.root.name)

    def test_daily_report_writes_today_and_merges_the_summary(self):
        data, path = self.pet.daily_report()
        self.assertEqual(path, pet_report.report_path(self.fake.root, pet_report.day_key()))
        self.assertTrue(path.is_file())
        self.assertEqual(self.pet.report_path, path)
        self.assertIn('# 制作日报', path.read_text(encoding='utf-8'))
        self.assertEqual([row['day'] for row in pet_report.load_rows(self.fake.root)], [data['day']])

    def test_daily_report_without_a_project_is_a_noop(self):
        self.pet.desktop.root = None
        self.pet.core()
        self.assertEqual(self.pet.daily_report(), (None, None))
        self.assertIsNone(self.pet.report_path)

    def test_weekly_report_reads_the_daily_summary(self):
        self.pet.daily_report()
        path, totals = self.pet.weekly_report()
        self.assertEqual(path, pet_report.weekly_path(self.fake.root, pet_report.day_key()))
        self.assertEqual(self.pet.weekly_path, path)
        self.assertEqual(totals['days'], 1)
        self.assertIn('# 制作周报', path.read_text(encoding='utf-8'))

    def test_the_daily_report_still_works_without_a_menu_entry(self):
        """按钮搬走了，功能留着：一键执行与关软件那一眼照旧会出日报。"""
        with self.assertRaises(AssertionError):
            self.index_of('生成今日日报')
        self.assertIsNotNone(self.pet.daily_report()[0])
        self.assertTrue(self.pet.report_path.is_file())


class RemovedFeaturesTests(PetTestCase):
    """第 22 期：用户要的「删除独立小窗／自绘气泡」——两个功能连同它们的对象一起没有。"""

    def test_the_objects_and_the_methods_are_gone(self):
        for name in ('window', '_window', 'toast'):
            self.assertFalse(hasattr(self.pet, name), name + ' 还留在宠物身上')
        for name in ('open_window', 'close_window', 'toggle_window', 'open_toast',
                     'close_toast', 'toggle_toast', 'toast_action', 'notify'):
            self.assertFalse(hasattr(pet_ui.Pet, name), name + ' 还挂在宠物类上')
        # 第 44 期：quit_app 按用户附件回到功能栏最后一行（附件里那一项就是「退出」），
        # 所以它不再进这张「删过的清单」——它现在的判据在 MenuFeedbackTests／QuitTests 里。
        self.assertTrue(hasattr(pet_ui.Pet, 'quit_app'))

    def test_the_menu_has_no_entry_for_them(self):
        for name in ('window', 'toast'):
            self.assertNotIn(name, self.pet.menu_index, name + ' 还挂在功能栏上')

    def test_attach_no_longer_takes_the_two_switches(self):
        import inspect
        params = inspect.signature(pet_ui.attach).parameters
        self.assertNotIn('window', params)
        self.assertNotIn('toast', params)

    def test_closing_the_main_window_just_closes(self):
        """常驻模式没了：桌面问「要不要收进宠物窗」时一律答「不收」，关窗就是关程序。"""
        self.assertFalse(self.pet.hide_to_pet())


class AutostartTests(unittest.TestCase):
    """开机自启：只用假注册表，真注册表一行都不写。"""

    def test_command_points_at_the_launcher_next_to_the_program(self):
        command = pet_ui.autostart_command(PROGRAM)
        self.assertIn('启动漫剧制作助手.pyw', command)
        self.assertTrue(command.startswith('"'))

    def test_toggle_writes_then_removes_the_run_entry(self):
        api = FakeWinreg()
        control = pet_ui.Autostart(api=api)
        self.assertTrue(control.available)
        self.assertEqual(control.get(), '')
        self.assertFalse(control.enabled())
        self.assertTrue(control.toggle(PROGRAM))
        self.assertIn('启动漫剧制作助手.pyw', api.values[pet_ui.AUTOSTART_NAME])
        self.assertTrue(control.enabled())
        self.assertFalse(control.toggle(PROGRAM))
        self.assertEqual(api.values, {})

    def test_clear_is_idempotent(self):
        self.assertTrue(pet_ui.Autostart(api=FakeWinreg()).clear())

    def test_without_winreg_everything_degrades(self):
        control = pet_ui.Autostart(api=None)
        self.assertFalse(control.available)
        self.assertIsNone(control.get())
        self.assertFalse(control.set('x'))
        self.assertFalse(control.clear())
        self.assertFalse(control.toggle(PROGRAM))

    def test_broken_registry_is_reported_not_raised(self):
        self.assertIsNone(pet_ui.Autostart(api=FakeWinreg(fail_read=True)).get())
        self.assertFalse(pet_ui.Autostart(api=FakeWinreg(fail_write=True)).set('x'))


class AutostartMenuTests(PetTestCase):
    """第 19 期：开机自启默认开着，功能栏里不再占一行（标签仍跟着注册表走）。"""

    def test_label_follows_the_registry(self):
        self.pet._autostart = pet_ui.Autostart(api=FakeWinreg())
        self.assertEqual(self.pet.autostart_label(), '开机自启（未开启）')
        self.assertTrue(self.pet.toggle_autostart())
        self.assertEqual(self.pet.autostart_label(), '开机自启（已开启）')
        self.assertFalse(self.pet.toggle_autostart())
        self.assertEqual(self.pet.autostart_label(), '开机自启（未开启）')

    def test_label_without_a_registry_says_unsupported(self):
        self.pet._autostart = pet_ui.Autostart(api=None)
        self.assertEqual(self.pet.autostart_label(), '开机自启（本机不支持）')
        self.assertFalse(self.pet.toggle_autostart())

    def test_the_run_entry_is_written_by_default(self):
        """attach 不传 autostart 就把 Run 项补上；传 False 则一个字节都不动注册表。"""
        api = FakeWinreg()
        self.pet._autostart = pet_ui.Autostart(api=api)
        self.assertTrue(self.pet.autostart_default())
        self.assertIn('启动漫剧制作助手.pyw', api.values[pet_ui.AUTOSTART_NAME])
        api2 = FakeWinreg()
        quiet = pet_ui.attach(self.fake, autostart=False)
        self.assertIsInstance(quiet, pet_ui.Pet)

    def test_an_unsupported_registry_is_not_an_error(self):
        self.pet._autostart = pet_ui.Autostart(api=None)
        self.assertFalse(self.pet.autostart_default())
        self.assertEqual(self.pet.errors, [])


class ShotStatsTests(unittest.TestCase):
    """shot_stats：只数 JSON 里记着的路径、且文件真的在盘上——首帧名带哈希后缀，按名字猜必然数错。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / '星空项目'
        self.work = self.project / 'storyboard' / '分镜拆分'
        self.work.mkdir(parents=True)
        self.frames = self.project / 'storyboard' / 'frames'
        self.frames.mkdir(parents=True)

    def write(self, shots, name='EP001_分镜.json'):
        path = self.work / name
        path.write_text(json.dumps({'episode_id': 'EP001', 'shots': shots}, ensure_ascii=False),
                        encoding='utf-8')
        return path

    def png(self, name):
        (self.frames / name).write_bytes(b'\x89PNG\r\n\x1a\n')

    def test_counts_shots_and_the_frames_that_really_exist(self):
        self.png('EP001_SH001_aaaa.png')
        path = self.write([{'id': 'SH001', 'frame': 'frames/EP001_SH001_aaaa.png'},
                           {'id': 'SH002', 'frame': 'frames/EP001_SH002_bbbb.png'},
                           {'id': 'SH003'}])
        self.assertEqual(pet_ui.shot_stats([path]), (3, 1))

    def test_deleted_frames_are_not_counted(self):
        self.png('EP001_SH001_aaaa.png')
        path = self.write([{'id': 'SH001', 'frame': 'frames/EP001_SH001_aaaa.png', 'frame_deleted': True}])
        self.assertEqual(pet_ui.shot_stats([path]), (1, 0))

    def test_frames_pointing_outside_the_storyboard_folder_are_not_counted(self):
        (self.project / 'outside.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        path = self.write([{'id': 'SH001', 'frame': '../outside.png'}])
        self.assertEqual(pet_ui.shot_stats([path]), (1, 0))

    def test_junk_shots_are_ignored_but_the_rest_still_count(self):
        path = self.write(['乱写的', {'frame': 'frames/x.png'}, {'id': 'SH001'}])
        self.assertEqual(pet_ui.shot_stats([path]), (1, 0))

    def test_broken_json_and_missing_files_give_zero(self):
        bad = self.work / '坏.json'
        bad.write_text('{不是 JSON', encoding='utf-8')
        self.assertEqual(pet_ui.shot_stats([bad, self.work / '没有这个文件.json']), (0, 0))

    def test_shots_that_are_not_a_list_give_zero(self):
        path = self.work / '怪.json'
        path.write_text(json.dumps({'shots': {'SH001': {}}}), encoding='utf-8')
        self.assertEqual(pet_ui.shot_stats([path]), (0, 0))

    def test_no_paths_is_zero(self):
        self.assertEqual(pet_ui.shot_stats([]), (0, 0))
        self.assertEqual(pet_ui.shot_stats(None), (0, 0))


class AssetCountTests(unittest.TestCase):
    """asset_counts：登记的资产数＋真的有图的个数，口径与无人值守判断一致。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / '资产'
        self.base.mkdir()

    def test_counts_registered_and_ready_assets(self):
        (self.base / 'a.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        (self.base / 'assets.json').write_text(json.dumps(
            {'ast_01': {'image': 'a.png'}, 'ast_02': {'image': 'b.png'}, 'ast_03': {}}), encoding='utf-8')
        self.assertEqual(pet_ui.asset_counts(self.base), (3, 1))

    def test_missing_library_is_zero(self):
        self.assertEqual(pet_ui.asset_counts(self.base / '不存在'), (0, 0))

    def test_broken_registry_is_zero(self):
        (self.base / 'assets.json').write_text('[1, 2]', encoding='utf-8')
        self.assertEqual(pet_ui.asset_counts(self.base), (0, 0))


class CountsTests(PetTestCase):
    """Pet.counts：日报里的真实计数全部来自盘上，读不出来的项写 0，绝不编。"""

    def test_empty_project_counts_everything_as_zero(self):
        counts = self.pet.counts()
        self.assertEqual(sorted(counts), sorted(pet_report.COUNT_KEYS))
        self.assertEqual(set(counts.values()), {0})

    def test_real_storyboard_frames_and_scripts_are_counted(self):
        work = self.fake.root / 'storyboard' / '分镜拆分'
        work.mkdir(parents=True)
        frames = self.fake.root / 'storyboard' / 'frames'
        frames.mkdir(parents=True)
        (frames / 'EP001_SH001_aaaa.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        (work / 'EP001_分镜.json').write_text(json.dumps(
            {'episode_id': 'EP001', 'shots': [{'id': 'SH001', 'frame': 'frames/EP001_SH001_aaaa.png'},
                                              {'id': 'SH002'}]}, ensure_ascii=False), encoding='utf-8')
        writing = self.fake.root / 'writing'
        writing.mkdir(parents=True, exist_ok=True)
        (writing / '第1集剧本.md').write_text('# 剧本', encoding='utf-8')
        counts = self.pet.counts()
        self.assertEqual(counts['storyboards'], 1)
        self.assertEqual(counts['shots'], 2)
        self.assertEqual(counts['frames'], 1)
        self.assertEqual(counts['scripts'], 1)

    def test_a_broken_asset_library_is_reported_as_zero_not_raised(self):
        (self.fake.root / 'episode' / 'assets.json').write_text('[坏]', encoding='utf-8')
        self.assertEqual((self.pet.counts()['assets'], self.pet.counts()['ready_assets']), (0, 0))

    def test_report_data_carries_the_counts(self):
        data = self.pet.report()
        self.assertEqual(sorted(data['counts']), sorted(pet_report.COUNT_KEYS))


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
        self.assertEqual(self.fake.kicks, ['pet'])
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
        self.assertEqual(self.pet._offer_sig, ('3 份分镜 JSON 还没采用',), '指纹先记下来')
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

    def test_the_question_comes_in_the_green_chat_box(self):
        """第 26 期第 5 条：问用户「要不要办」用绿色对话框——长句子也放得下、一眼分得开。"""
        self.arm()
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        self.assertEqual(cloud.fill(), pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_CLOUD][0])

    def test_the_question_lists_the_choices(self):
        self.arm()
        self.assertIn('回「好」', self.pet.cloud().transcript(), '要写清楚怎么答')
        self.assertIn('先不用', self.pet.cloud().transcript())
        self.assertTrue(self.pet._offer_open, '问题挂着，用户才好回话')

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
        self.assertFalse(self.pet._offer_open, '答过就不再挂着')
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
        self.assertTrue(self.pet._offer_open, '这句话不算回答，问题还挂着')

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


class DesktopSeamTests(unittest.TestCase):
    """真接缝：Desktop 上确实挂上了宠物，且 _tick_once 的收尾真的分发事件。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def test_desktop_carries_the_pet_and_wrapped_seams(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Tk(); win.withdraw()
        try:
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            self.assertTrue(hasattr(d, "pet"))
            for name in ("auto_final_queue", "auto_edit_queue", "auto_keyframe_queue",
                         "auto_asset_queue", "auto_video_queue", "auto_handoff_queue"):
                with self.subTest(name=name):
                    box = getattr(d, name)
                    self.assertIsInstance(box, pet_ui.StageQueue)
                    if name in ("auto_keyframe_queue", "auto_asset_queue"):
                        # 这两类任务必须由界面线程复核真实产物后才允许发送完成事件。
                        self.assertIsNone(box.sink)
                    else:
                        self.assertIs(box.sink.__self__, d.pet)
                        self.assertEqual(box.sink.__name__, "drain")
            self.assertIsInstance(d.status, self.tk.StringVar)
            self.assertTrue(getattr(d.status, "_petWatched", False))
            d.status.set("接缝自检：状态栏照旧")
            self.assertEqual(d.status.get(), "接缝自检：状态栏照旧")
            self.assertTrue(getattr(self.tk.Variable, "_dramaGuarded", False))
            self.assertIsNotNone(d.pet.canvas)
            self.assertEqual(str(d.pet.canvas.winfo_parent()), str(d.title_row))
            stubs = [(box.stage, box) for box in (d.auto_final_queue, d.auto_edit_queue, d.auto_keyframe_queue,
                                                  d.auto_asset_queue, d.auto_video_queue, d.auto_handoff_queue)]
            self.assertEqual(sorted(stage for stage, _ in stubs),
                             sorted(["final", "edit", "keyframe", "assets", "video", "delivery"]))
        finally:
            win.destroy()

    def test_tk_gc_guard_skips_worker_threads(self):
        """非主线程回收 Tk 对象时不再调 Tcl——无人值守收尾阶段卡死的来源。

        tkinter 里只有 Variable、Image（PhotoImage）、font.Font 三个类型会在 __del__ 里调 Tcl；
        实机日志显示复选框图标（PhotoImage）被 worker 线程回收时刷出 32 条
        RuntimeError: main thread is not in main loop，这才是卡死链条上真正频繁的那一环。
        """
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import threading
        from tkinter import font as tkfont
        import desktop as desktop_module
        desktop_module.protect_tk_gc()
        win = self.tk.Tk(); win.withdraw()
        try:
            var = self.tk.StringVar(master=win, value="非主线程回收")
            image = self.tk.PhotoImage(master=win, width=1, height=1)
            lettering = tkfont.Font(root=win, family="TkDefaultFont", size=10)
            calls = [(self.tk.Variable.__del__, var), (self.tk.Image.__del__, image),
                     (tkfont.Font.__del__, lettering)]
            errors = []

            def worker():
                for function, target in calls:
                    try:
                        function(target)
                    except Exception as exc:
                        errors.append(repr(exc))

            thread = threading.Thread(target=worker)
            thread.start(); thread.join(20)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            # 守卫直接放弃回收，Tcl 侧的东西仍然有效——证明这几次 __del__ 都没跨线程调 Tcl
            self.assertEqual(var.get(), "非主线程回收")
            self.assertEqual(image.width(), 1)
            for cls in (self.tk.Variable, self.tk.Image, tkfont.Font):
                self.assertTrue(getattr(cls, "_dramaGuarded", False))
            # 三个对象都被拦下来排队，等主线程释放：就地释放会把 Tkapp 一起在 worker 里析构
            self.assertEqual(len(desktop_module._PENDING_TK_GC), len(calls))
            desktop_module.drain_tk_gc()
            self.assertEqual(desktop_module._PENDING_TK_GC, [])
        finally:
            win.destroy()

    def test_tick_once_drains_into_the_bus(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Tk(); win.withdraw()
        try:
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            d.auto_handoff_queue.put((True, "自动交接包已整理：exports/MASTER.mp4", "sig"))
            d._tick_once()
            kinds = [(item["kind"], item.get("stage")) for item in d.pet.bus.history]
            self.assertIn(("stage.completed", "delivery"), kinds)
            self.assertIn("自动交接包已整理：exports/MASTER.mp4", d.pet.last_status)
        finally:
            win.destroy()

    def test_button_seam_reports_the_label(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        win = self.tk.Tk(); win.withdraw()
        try:
            from desktop import Desktop
            d = Desktop(win, root=PROGRAM)
            button = d.button(d.content, "导出交付", lambda: "ok")
            button.invoke()
            pet_ui.pump(d)
            item = [event for event in d.pet.bus.history if event["kind"] == "intent.command"][-1]
            self.assertEqual(item["text"], "导出交付")
        finally:
            win.destroy()


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


class TimingRowTests(PetTestCase):
    """面板与日报的耗时数字：全部来自状态机，没有产出单位就写「信息不足」。"""

    def measure(self, stage="keyframe", units=20, seconds=600.0):
        machine = self.pet.machine
        machine.start(stage)
        machine.detail(stage, units, units)
        machine.complete(stage)
        machine.elapsed[stage] = seconds
        return machine

    def test_the_panel_lists_the_two_new_rows(self):
        rows = dict(self.pet.rows())
        self.assertIn("阶段停留", rows)
        self.assertIn("平均单镜耗时", rows)

    def test_empty_measurements_say_so(self):
        rows = dict(self.pet.rows())
        self.assertEqual(rows["阶段停留"], "信息不足")
        self.assertEqual(rows["平均单镜耗时"], "信息不足")

    def test_the_panel_numbers_follow_the_machine(self):
        self.measure()
        rows = dict(self.pet.rows())
        self.assertEqual(rows["阶段停留"], "首帧管理 10:00")
        self.assertEqual(rows["平均单镜耗时"], "首帧管理 0:30/镜")

    def test_the_rows_are_named_pairs_of_label_and_value(self):
        rows = self.pet.rows()
        self.assertTrue(rows)
        for label, value in rows:
            self.assertTrue(str(label).strip(), "每一行都要有名字")
            self.assertIsInstance(value, str)

    def test_the_timings_payload_is_normalized(self):
        self.measure("assets", units=4, seconds=120.0)
        payload = self.pet.timings()
        self.assertEqual(payload["stages"]["assets"], 120.0)
        self.assertEqual(sorted(payload["units"]), sorted(pet_bus.STAGES))
        self.assertEqual(payload["rates"], {"assets": 30.0})

    def test_the_report_carries_the_timings(self):
        self.measure()
        data = self.pet.report()
        self.assertEqual(data["timings"]["rates"], {"keyframe": 30.0})
        self.assertEqual(data["timings"]["stages"]["keyframe"], 600.0)

    def test_the_daily_report_writes_the_two_lines(self):
        self.measure()
        _data, path = self.pet.daily_report()
        text = path.read_text(encoding="utf-8")
        self.assertIn("阶段停留：首帧管理 10:00", text)
        self.assertIn("平均耗时：首帧管理 0:30/镜", text)


class FrameBatchSeamTests(unittest.TestCase):
    """真接缝：Desktop.pet_frame_batch 的每条出口都给人话，且从不碰付费通道。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from desktop import Desktop
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.d = Desktop(self.win, root=PROGRAM)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "p"

    def project_with_a_gap(self):
        work = self.base / "storyboard" / "分镜拆分"
        work.mkdir(parents=True, exist_ok=True)
        source = work / "EP001_分镜.json"
        source.write_text(json.dumps({"episode_id": "EP001", "shots": [
            {"id": "SH001", "frame": "frames/SH001.png"},
            {"id": "SH002", "frame": "frames/SH002.png"}]}, ensure_ascii=False), encoding="utf-8")
        (self.base / "ui_settings.json").write_text(json.dumps(
            {"frame_json": "storyboard/分镜拆分/EP001_分镜.json"}, ensure_ascii=False), encoding="utf-8")
        self.d.root = self.base
        self.d.studio = object()
        return source

    def test_it_says_nothing_without_a_project(self):
        self.assertEqual(self.d.pet_frame_batch(), "")
        self.assertEqual(self.d.pet.firstframe_batch(), "")

    def test_auto_keyframe_without_a_storyboard_finishes_as_failed(self):
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_frame_batch(trigger='auto')
        self.assertIn('未找到可用分镜', text)
        self.assertEqual(emitted, [('stage.failed', {'stage': 'keyframe', 'error': text})])

    def test_it_says_nothing_when_there_is_no_gap(self):
        self.project_with_a_gap()
        frames = self.base / "storyboard" / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        for name in ("SH001.png", "SH002.png"):
            (frames / name).write_bytes(b"\x89PNG\r\n\x1a\n")
        self.assertEqual(self.d.pet_frame_batch(), "", "没有缺口就一个字都不说")

    def test_auto_keyframe_with_no_gap_finishes_as_completed(self):
        self.project_with_a_gap()
        frames = self.base / "storyboard" / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        for name in ("SH001.png", "SH002.png"):
            (frames / name).write_bytes(b"\x89PNG\r\n\x1a\n")
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_frame_batch(trigger='auto')
        self.assertEqual(text, '首帧已齐全，无需制作')
        self.assertEqual(emitted, [('stage.completed', {'stage': 'keyframe', 'text': text})])

    def test_a_missing_asset_registry_is_reported_not_raised(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: []
        self.assertIn("找不到资产清单", self.d.pet_frame_batch())
        self.assertFalse(self.d.auto_keyframe_busy)

    def test_it_names_the_missing_local_settings(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: ["model"]
        text = self.d.pet_frame_batch()
        self.assertIn("还没配好", text)
        self.assertIn("model", text)
        self.assertFalse(self.d.auto_keyframe_busy)

    def test_it_names_the_blocked_shots(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: []
        self.d.batch_blockers = lambda source, pending: [(shot["id"], "缺参考图") for shot in pending]
        text = self.d.pet_frame_batch()
        self.assertIn("2 镜都无法生成", text)
        self.assertIn("缺参考图", text)              # 原因与引擎逐镜跳过时同一句话
        self.assertFalse(self.d.auto_keyframe_busy)

    def test_the_unattended_path_skips_a_batch_it_already_handled(self):
        """无人值守先判重再派发：同一批（同一份分镜、同样缺几张参考图）只跑一次。

        批次还在跑的那几十秒里清单没变，判重必须发生在派发之前，否则同一批会被重复下单；
        用户按下的按钮不受这份记忆影响，显式操作永远照做。
        """
        self.project_with_a_gap()
        import project_settings
        project_settings.set_auto_keyframe(self.base, True)
        self.d.keyframe_settings = lambda: []
        self.d.batch_blockers = lambda source, pending: []
        self.d.keyframe_signature = lambda source, pending: ("签名", len(pending))
        self.d.auto_keyframe_signature = ("签名", 2)
        import keyframe_comfy
        original = keyframe_comfy.auto_batch
        started = []
        keyframe_comfy.auto_batch = lambda source, log, stop=None: started.append(1) or "批次结束"
        try:
            self.d.poll_auto_keyframe()
            self.assertEqual(started, [], "这一批已经在跑了，不能再下一单")
            self.assertFalse(self.d.auto_keyframe_busy)
            text = self.d.pet_frame_batch()          # 显式按下：同一批照样派发
            self.assertIn("已按分镜顺序派发 2 镜首帧", text)
            self.assertTrue(self.d.auto_keyframe_busy)
        finally:
            keyframe_comfy.auto_batch = original
            self.d.auto_keyframe_busy = False
            while not self.d.auto_keyframe_queue.empty():
                self.d.auto_keyframe_queue.get_nowait()

    def test_it_says_nothing_while_another_batch_runs(self):
        self.project_with_a_gap()
        self.d.auto_keyframe_busy = True
        try:
            self.assertIn("已有制作任务在跑", self.d.pet_frame_batch())
        finally:
            self.d.auto_keyframe_busy = False

    def test_auto_keyframe_while_busy_finishes_as_failed(self):
        self.project_with_a_gap()
        self.d.auto_keyframe_busy = True
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        try:
            text = self.d.pet_frame_batch(trigger='auto')
        finally:
            self.d.auto_keyframe_busy = False
        self.assertIn('已有制作任务在跑', text)
        self.assertEqual(emitted, [('stage.failed', {'stage': 'keyframe', 'error': text})])

    def test_it_dispatches_the_free_local_batch(self):
        self.project_with_a_gap()
        self.d.keyframe_settings = lambda: []
        self.d.batch_blockers = lambda source, pending: []
        self.d.keyframe_signature = lambda source, pending: ("签名", len(pending))
        import keyframe_comfy
        original = keyframe_comfy.auto_batch
        keyframe_comfy.auto_batch = lambda source, log, stop=None: "无人值守首帧批次结束：处理 2 镜"
        try:
            text = self.d.pet_frame_batch()
            self.assertIn("已按分镜顺序派发 2 镜首帧", text)
            self.assertTrue(self.d.auto_keyframe_busy)
            ok, value, signature = self.d.auto_keyframe_queue.get(timeout=20)
            self.assertTrue(ok)
            self.assertIn("处理 2 镜", value)
            self.assertEqual(signature, ("签名", 2))
        finally:
            keyframe_comfy.auto_batch = original
            self.d.auto_keyframe_busy = False
            while not self.d.auto_keyframe_queue.empty():
                self.d.auto_keyframe_queue.get_nowait()

    def test_the_shared_signature_contains_the_missing_references(self):
        """无人值守与一键执行共用同一份指纹：两条路派发的批次不会互相再触发一次。"""
        source = self.project_with_a_gap()
        pending = [{"id": "SH001"}, {"id": "SH002"}]
        self.assertEqual(self.d.keyframe_signature(source, pending),
                         (str(source), (("SH001", 0), ("SH002", 0))))


class PetTextSeamTests(unittest.TestCase):
    """真接缝：宿主把宠物的「查看详情」接到全程序唯一的只读文本窗口上（不另造窗口）。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        # 这一条只看「宠物的详情窗口」，与项目无关：把打开项目那一步挡住。
        # 不挡的话，win.update() 会真的去开本机项目、把无人值守资产那一批跑起来，
        # 状态栏就不再是这一个用例说了算（与本仓库另外 140 处同一条隔离）。
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        from desktop import Desktop
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.d = Desktop(self.win, root=PROGRAM)
        self.addCleanup(self.d.cancel_timers)

    def popup(self):
        return [w for w in self.win.winfo_children() if isinstance(w, self.tk.Toplevel)][0]

    def buttons_of(self, win):
        from tkinter import ttk
        return [w for w in win.winfo_children() if isinstance(w, ttk.Button)]

    def test_the_text_window_shows_what_it_was_given(self):
        self.d.pet_show_text("待确认详情", "第一行\n第二行", "已复制")
        self.win.update()
        popup = self.popup()
        boxes = [w for w in popup.winfo_children() if isinstance(w, self.tk.Text)]
        self.assertEqual(boxes[0].get("1.0", "end-1c"), "第一行\n第二行")
        self.assertEqual([str(button.cget("text")) for button in self.buttons_of(popup)], ["复制详情"])

    def test_the_copy_button_still_goes_through_the_shared_window(self):
        """复制仍然只有一处实现（prompt_window.copy_text）：按钮名字换了，行为没换。"""
        self.d.pet_show_text("待确认详情", "哨兵文字", "已复制")
        self.win.update()
        popup = self.popup()
        import clipboard_lock                                     # # 第 65 期第 12 条：剪贴板是全机器共用的一块，几路并行要排队用
        with clipboard_lock.hold():
            self.buttons_of(popup)[0].invoke()
            self.win.update()
            self.assertEqual(self.win.clipboard_get(), "哨兵文字")
        self.assertFalse(popup.winfo_exists(), "复制成功后仍然关窗")
        self.assertEqual(self.d.status.get(), "已复制")


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
        self.assertIn("已跳过一条待确认", self.pet.notice)
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


class CloudTests(PetTestCase):
    """第 14／16 期：贴着三虎脑袋、朝左上铺开的漫画对话框浮窗——既播报也能对话。"""

    def cloud(self):
        widget = self.pet.open_chat()
        self.assertIsNotNone(widget, '云朵框应当能开出来')
        return self.pet.cloud()

    def answer(self, cloud, text, timeout=5.0):
        """走完整链路：回复框 → 后台线程 → 队列 → 心跳把回复贴回云里。

        第 35 期第 2 条起这一行是回复框：三虎问什么、空着回车就发什么——这里用 propose 把那句话摆好。
        """
        cloud.propose(text)
        self.assertEqual(cloud.submit(), text)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.pet.chat_drain():
                return cloud.transcript()
            time.sleep(0.01)
        self.fail('云朵框 %.0f 秒内没有收到回复' % timeout)

    def test_the_cloud_is_a_floating_bubble_of_its_own(self):
        """第 16 期：云朵要伸到界面外，所以它自带一扇无边框置顶浮窗，而不是界面里的浮层。"""
        cloud = self.cloud()
        self.assertIsNotNone(cloud.win, '云朵框该有自己的浮窗')
        self.assertIs(cloud.win.winfo_toplevel(), cloud.win)
        self.assertTrue(cloud.win.overrideredirect(), '无边框：它就是一朵云')
        self.assertTrue(cloud.win.attributes('-topmost'), '置顶：不然会被主界面盖住')
        self.assertTrue(getattr(cloud.win, '_positioned_once', False),
                        '建窗后立刻标 _positioned_once：别让 ui_theme 按对话框接管')

    def test_the_cloud_never_keeps_the_keyboard_grab(self):
        self.cloud()
        self.win.update()
        self.assertIsNone(self.win.grab_current(), '云朵框抓了键盘，主窗口就点不动了')

    def test_a_destroyed_window_takes_the_pending_timer_with_it(self):
        """父窗口被销毁时，待触发的播报定时器必须一起收回。

        不收的话 Tcl 到点会打一句「invalid command name ..._expire」，因为 after 的 Tcl 命令
        已经随控件被删了（第 14 期跑全量自检时真的见过这条 stderr）。
        """
        win = self.tk.Tk()
        win.withdraw()
        try:
            fake = FakeDesktop(self.tk, self.ttk, win)
            fake.root = self.fake.root
            pet = pet_ui.attach(fake, autostart=False)
            cloud = pet.cloud()
            cloud.show(pinned=False, hold=200)
            self.assertIsNotNone(cloud._hold, '播报形态该有一个到点自收的定时器')
            win.destroy()
            self.assertIsNone(cloud._hold)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    def placed_cloud(self, anchor=(1200.0, 320.0), bottom=384.0):
        """按给定的锚点（三虎嘴边）／下沿摆一朵云：几何用例都从这里出发。

        第 22 期：整朵云与尾巴共用一个锚点（_anchor），钉住它就等于钉住了「贴片在屏幕上的哪」。
        """
        cloud = self.cloud()
        cloud._anchor = lambda: anchor
        cloud._bottom = lambda: bottom
        cloud._render()
        return cloud

    def test_the_cloud_stands_left_of_the_pet_with_its_bottom_lined_up(self):
        """第 18 期：云身整个站在三虎左边，浮窗下沿与贴片下沿对齐；第 22 期尾巴尖指向嘴边。"""
        mouth = (1200.0, 320.0)
        cloud = self.placed_cloud(anchor=mouth, bottom=384.0)
        left, top = cloud._origin()
        self.assertEqual(left + cloud.total_width(), mouth[0] + pet_cloud.TIP_IN,
                         '整朵云站在三虎左边（尾巴尖往云身里缩 TIP_IN）')
        self.assertEqual(top + cloud._body + pet_cloud.TAIL, 384.0,
                         '下沿与三虎对齐（用户要的「底部和三虎对齐」）')
        tip_x, tip_y = cloud._tip()
        self.assertEqual(tip_x, int(mouth[0] - left), '尾巴尖落在嘴边那一列')
        self.assertGreaterEqual(tip_y, 8)
        self.assertLessEqual(tip_y, cloud._body + pet_cloud.TAIL)

    def test_the_cloud_never_runs_off_the_screen(self):
        """第 18 期：三虎贴着屏幕右边时，云身整个让回屏幕里（原来会顶出去一半）。"""
        cloud = self.cloud()
        cloud._anchor = lambda: (1900.0, 320.0)
        cloud._bottom = lambda: 384.0
        cloud._work_right = lambda: 1920
        cloud._render()
        left, _top = cloud._origin()
        self.assertGreaterEqual(left, pet_cloud.MARGIN)
        self.assertLessEqual(left + cloud.total_width(), 1920 - pet_cloud.MARGIN)

    def test_the_cloud_flips_below_when_there_is_no_room_above(self):
        """第 18 期：全屏时三虎贴着屏幕顶，上方放不下就翻到它下面（这就是「全屏显示不正常」）。

        第 29 期第 3 条：翻下去之后，尾巴带改挂在云身**上方**，带子的尖头正落在脸颊上——
        从前尾巴还在画布下边，尖头顶多顶到画布上沿，离脸差一整条云身（用户报的「箭头没碰到脸」）。
        """
        cloud = self.cloud()
        cloud._anchor = lambda: (1200.0, 120.0)
        cloud._bottom = lambda: 84.0
        cloud._screen_height = lambda: 1080
        cloud._patch_rect = lambda: (1100.0, 0.0, 64.0, 84.0)     # 三虎就贴在屏幕顶
        cloud._render()
        self.assertTrue(cloud._flipped(), '上方连最小云身都放不下，就该翻下去')
        _left, top = cloud._origin()
        tip_x, tip_y = cloud._tip()
        self.assertGreaterEqual(top, 84.0, '翻下去：云身整个在三虎下沿之外，不许压住猫')
        self.assertLess(tip_y, pet_cloud.TAIL, '带子在上：尖头落在画布最上面那一条带子里')
        self.assertAlmostEqual(top + tip_y, 120.0, delta=2, msg='尖头要顶在脸颊上')
        kind, points = cloud._tail_polygon()
        self.assertEqual(kind, 'poly')
        self.assertAlmostEqual(min(spot[1] for spot in points), float(tip_y), delta=2,
                               msg='多边形的上端就是那个尖头')

    def test_the_tail_is_a_curved_spike_pointing_at_the_cheek(self):
        """第 24 期第 2 条：尖角的两条边带弧度，尖头指三虎的脸颊（不再是嘴边）。"""
        cloud = self.placed_cloud()
        kind, points = cloud._tail_polygon()
        self.assertEqual(kind, 'poly')
        self.assertGreater(len(points), 3, '两条边是折线拟合出来的弧，不再是三点的直三角')
        tip_x, tip_y = cloud._tip()
        nearest = min(points, key=lambda spot: (spot[0] - tip_x) ** 2 + (spot[1] - tip_y) ** 2)
        self.assertAlmostEqual(nearest[0], tip_x, delta=2, msg='尖角指向三虎的脸颊')
        self.assertAlmostEqual(nearest[1], tip_y, delta=2)
        self.assertLess(points[0][0], nearest[0], '底边留在云身这一侧，尖角朝三虎指')

        def off_line(spot, start, end):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = max(1e-6, (dx * dx + dy * dy) ** 0.5)
            return abs((spot[0] - start[0]) * dy - (spot[1] - start[1]) * dx) / length

        self.assertGreater(off_line(points[3], points[0], nearest), 1.5,
                           '边往外鼓——「尖锐有弧度」看的就是这个')
        for x, y in points:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x, cloud.total_width())
            self.assertLessEqual(y, cloud._body + pet_cloud.TAIL)

    def test_the_tail_base_hides_inside_the_body(self):
        """第 21 期：底边长在云身里（被云身盖住），接缝才看不出来——四种形状都得成立。

        第 31 期：这条原先在「没摆放」的云上算几何——尾巴朝上还是朝下由当时的屏幕空间
        （_flipped）决定，同一份代码会随机红。这里用 placed_cloud 把锚点钉住，再把朝向也钉死，
        两种朝向各测一遍。

        尾巴多边形用的是画布坐标（翻转时云身整体下移一条尾巴带，见 _shift），而 inside_shape
        量的是云身自己的局部坐标——所以先减掉那一条偏移，两者的口径才对得上。
        """
        cloud = self.placed_cloud()
        for shape in pet_cloud.SHAPES:
            for up in (False, True):
                with self.subTest(shape=shape, up=up):
                    cloud.shape = shape
                    cloud._flipped = lambda up=up: up
                    cloud._render()
                    _kind, points = cloud._tail_polygon()
                    shift = cloud._shift()
                    for x, y in (points[0], points[-1]):
                        self.assertTrue(pet_cloud.inside_shape(shape, cloud.width(), cloud._body, x, y - shift),
                                        '底边两点都要落在云身里：%s (%.1f, %.1f)' % (shape, x, y))

    def test_the_record_is_numbered_one_line_at_a_time(self):
        """第 24 期第 7 条：编号和正文写在同一行，条与条之间不空行（每行放满再自动换行）。"""
        cloud = self.cloud()
        cloud.append(pet_cloud.SPEAKER + '：二号')
        body = cloud._body_text()
        lines = body.split('\n')
        self.assertEqual(len(lines), len(cloud.lines), '一条记录一行')
        gap = pet_cloud.NUMBER_GAP
        self.assertTrue(lines[0].startswith('1.' + gap + pet_cloud.WELCOME))
        self.assertIn('二号', lines[-1])
        for index, line in enumerate(lines, 1):
            self.assertTrue(line.startswith('%d.' % index + gap), '编号与正文同一行：' + line)
        self.assertNotIn('\n\n', body, '不再空行间隔，地方都要用来放字')

    def test_the_newest_line_is_always_in_view(self):
        """操作对话框只露最近五步，长记录不再把页面操作区挡住。"""
        cloud = self.cloud()
        for index in range(30):
            cloud.append(pet_cloud.SPEAKER + '：第 %d 行' % index)
        rows = cloud._body_text().split('\n')
        self.assertEqual(len(rows), pet_cloud.CHAT_VISIBLE_STEPS)
        self.assertIn('第 29 行', rows[-1], '最新步骤必须保留')
        self.assertNotIn('第 0 行', cloud._body_text(), '过期步骤不显示')
        self.assertEqual(cloud._scroll, cloud._scroll_limit(), '有单步长文本时默认仍停在最新位置')

    def test_the_wheel_does_not_scroll_the_main_page(self):
        """云框仍接住滚轮；五步上限下不会改变主界面或云框位置。"""
        cloud = self.cloud()
        for index in range(30):
            cloud.append(pet_cloud.SPEAKER + '：第 %d 行' % index)
        bottom = cloud._scroll
        self.assertEqual(cloud.wheel(_Wheel(120)), 'break', '云朵框先接住滚轮')
        self.assertLessEqual(cloud._scroll, bottom, '滚轮不应展开旧步骤或带动主界面')

    def test_the_bubble_emerges_with_a_fade(self):
        """第 16 期：交互时云朵框以浮出的形式出现（淡入），收起时把定时器一起收回来。"""
        cloud = self.cloud()
        self.assertIsNotNone(cloud._fade, '露面的那一下该有一段淡入')
        self.assertLess(float(cloud.win.attributes('-alpha')), pet_cloud.ALPHA)
        cloud.close()
        self.assertFalse(cloud.visible, '收起＝立刻不再算「露着」')
        self.assertIsNotNone(cloud._fade, '淡入那串定时器换成渐隐那一串（同一个槽位）')
        self.assertLess(float(cloud.win.attributes('-alpha')), pet_cloud.ALPHA, '收场先淡下去')

    def test_a_reply_that_needs_a_nod_rings_the_notification_bubble(self):
        """第 16 期：三虎要用户点头时，除了写进记录，还要弹一块通知气泡。"""
        cloud = self.cloud()
        seen = []
        original = self.pet.confirm
        self.pet.confirm = lambda text, title=None: seen.append((text, title))
        self.addCleanup(setattr, self.pet, 'confirm', original)
        cloud.queue.put({'text': '开始批量生成',
                         'lines': [pet_cloud.SPEAKER + '：开始批量生成。',
                                   pet_cloud.SPEAKER + '：' + pet_cloud.CONFIRM_PREFIX + '半自动：付费步骤需你确认'],
                         'result': None})
        self.assertEqual(cloud.drain(), 1)
        self.assertEqual(len(seen), 1, '要用户点头的事不能悄没声息')
        self.assertIn('付费步骤需你确认', seen[0][0])

    def test_every_line_in_the_record_is_signed_by_the_pet_name(self):
        """第 15 期：猫咪叫三虎——记录里每句话都挂在它名下，名字只有一处定义。"""
        self.assertEqual(pet_cloud.SPEAKER, pet_agent.PET_NAME)
        self.assertEqual(pet_cloud.SPEAKER, '三虎')
        self.assertTrue(pet_cloud.WELCOME.startswith(pet_agent.PET_NAME + '：'))
        for line in pet_cloud.reply_lines({'reply': '开始批量生成。', 'decision': {'run': True}}):
            self.assertTrue(line.startswith(pet_agent.PET_NAME + '：'), line)

    def test_double_clicking_the_pet_opens_the_chat(self):
        """第 19 期：双击＝直接和三虎说话（开关交给单击）。"""
        self.assertTrue(self.pet.canvas.bind('<Double-Button-1>'), '双击贴片应当接了入口')
        self.assertIsNotNone(self.pet.double_click())
        cloud = self.pet.cloud()
        self.assertTrue(cloud.visible)
        self.assertTrue(cloud.pinned, '双击是对话形态：带输入行')

    def test_a_line_gets_an_answer_back_in_the_record(self):
        cloud = self.cloud()
        self.pet.agent.set_level('semi')      # 第 22 期默认档是「只提醒」，说「我来做」要走半自动
        text = self.answer(cloud, '查一下进度')
        self.assertIn('您：查一下进度', text)
        self.assertIn(pet_cloud.SPEAKER + '：好，把进度面板打开。', text)
        self.assertIn(pet_cloud.SPEAKER + '：', text)

    def test_the_question_is_recorded_as_a_cloud_command(self):
        cloud = self.cloud()
        self.answer(cloud, '查一下进度')
        self.pet.pump()
        self.assertIn(('intent.command', 'cloud'),
                      [(item['kind'], item.get('source')) for item in self.pet.bus.history])

    def test_a_confirm_without_a_pending_task_does_the_page_task(self):
        """第 31 期第 6 条：提示框上那颗「确认」按下去不能没反应（用户报的哑键）。

        第 29 期遇到「只是播报、没有待办」时只把状态写成 EMPTY 那句小字——字太小，
        用户看到的就是一颗死键。现在的口径：按钮就照「这一页该做的事」办。
        """
        cloud = self.cloud()
        cloud.propose('')                     # 这一趟只是播报，没有要用户点的事
        lines = cloud.transcript().split('\n')
        self.assertEqual(lines[0], pet_cloud.WELCOME, '记录还是从开场那一句起')
        self.assertIn(pet_cloud.SPEAKER + '：', lines[-1],
                        '第 29 期第 5 条：一打开三虎先问这一页该做的事')
        self.assertIn(pet_ui.PAGE_ASKS[0][0], lines[-1])
        command = pet_ui.PAGE_ASKS[0][1]
        self.assertEqual(cloud.page_ask(), command, '现场问出这一页该做的事')
        self.assertEqual(cloud.submit(), command)
        self.assertIn('您：' + command, cloud.transcript(), '确认这件事要记进记录')
        self.assertNotEqual(cloud.status.cget('text'), pet_cloud.EMPTY)

    def test_a_busy_cloud_does_not_start_a_second_question(self):
        cloud = self.cloud()
        cloud.busy = True
        cloud.propose('查一下进度')
        self.assertEqual(cloud.submit(), '查一下进度')
        self.assertEqual(cloud.status.cget('text'), pet_cloud.BUSY)
        self.assertNotIn('您：查一下进度', cloud.transcript(), '上一问还没回来，不该又发一问')

    def test_a_broken_answer_still_says_something(self):
        cloud = self.cloud()
        agent = self.pet.agent

        def boom(text, at=None):
            raise RuntimeError('台账坏了')

        original = agent.dispatch
        agent.dispatch = boom
        self.addCleanup(setattr, agent, 'dispatch', original)
        lines = cloud.ask('查一下进度')
        self.assertEqual(len(lines), 1)
        self.assertIn('台账坏了', lines[0])

    def test_a_broadcast_opens_the_cloud_by_itself_and_then_hides_it(self):
        """第 15 期：宠物一说话，云朵框自己冒出来（不用用户手动打开），到点自己收。"""
        self.assertEqual(self.pet.broadcast('播报一句'), self.pet._prefix_output('播报一句'))
        cloud = self.pet.cloud()
        self.assertTrue(cloud.visible, '说话就该看见云，不必先双击贴片')
        self.assertTrue(cloud.pinned, '自动冒出来的云带输入行，用户可以马上接一句')
        self.assertIsNotNone(cloud._hold, '冒出来的时候就定好了什么时候收')
        self.assertIn('播报一句', cloud.transcript())
        self.assertTrue(cloud._expire(), '到点应当自己收起来')
        self.assertFalse(cloud.visible)

    def test_an_open_cloud_is_kept_by_a_broadcast_and_the_timer_moves_back(self):
        cloud = self.cloud()
        cloud._pointer_inside = lambda: False
        cloud.show(pinned=True, hold=50)
        self.pet.broadcast('插播一句')
        self.assertTrue(cloud.visible, '开着的时候插一句话不该把云收掉')
        self.assertTrue(cloud.pinned)
        self.assertIn('插播一句', cloud.transcript())
        cloud.busy = True
        self.assertFalse(cloud._expire(), '还在等回复时先别收，答案回来要有地方贴')
        cloud.busy = False
        self.assertTrue(cloud._expire(), '交互结束了就到点自己收')

    def test_the_cloud_stays_open_while_the_pointer_rests_on_it(self):
        """第 27 期第 2 条：用户正把鼠标停在云里读，到点也不许收——挪开之后下一次到点才收。"""
        cloud = self.cloud()
        cloud._pointer_inside = lambda: True
        self.assertFalse(cloud._expire(), '指针还在云上就别收')
        self.assertTrue(cloud.visible, '云还开着')
        self.assertIsNotNone(cloud._hold, '每隔 WATCH_RECHECK_MS 回头看一次指针走了没')
        cloud._pointer_inside = lambda: False
        self.assertTrue(cloud._expire(), '指针挪开了，下一次到点就真收')
        self.assertFalse(cloud.visible)

    def test_the_pointer_check_asks_the_window_for_real_coordinates(self):
        """指针在不在云上直接按窗口的屏幕坐标算——<Enter>／<Leave> 会被子控件吃掉。"""
        cloud = self.cloud()
        self.win.update_idletasks()
        x, y = cloud.win.winfo_rootx(), cloud.win.winfo_rooty()
        cloud.win.winfo_pointerxy = lambda: (x + 5, y + 5)
        self.assertTrue(cloud._pointer_inside(), '落在窗里就是在看这一条')
        cloud.win.winfo_pointerxy = lambda: (x - 40, y - 40)
        self.assertFalse(cloud._pointer_inside(), '飘到窗外就不算')
        self.assertEqual(cloud.win.bind('<Enter>'), '', '第 27 期第 2 条：不再靠 <Enter> 判断')

    def test_the_record_text_uses_the_shared_font(self):
        # 三虎对话框正文必须从设计系统取字体；Tk 的最终字号可能受系统 DPI 缩放影响。
        from tkinter import font as tkfont
        from ui_tokens import FONTS
        cloud = self.cloud()
        cloud.show(pinned=True)
        spec = tkfont.Font(root=self.win, font=cloud.label.cget('font'))
        self.assertEqual(pet_cloud.FONT, FONTS['body'], '正文只从设计系统 body token 取值')
        self.assertGreater(spec.cget('size'), 0, 'Tk 控件必须收到有效正文尺寸')
        self.assertEqual(pet_cloud.STICKER_FONTS[0], 13, '贴纸框也从 13 号起试')

    def test_the_cloud_does_not_steal_the_keyboard_when_it_opens_itself(self):
        self.pet.broadcast('播报一句')
        self.win.update()
        self.assertIsNone(self.win.grab_current(), '自动冒出来的云不抓键盘')
        self.assertEqual(self.pet.cloud().pinned, True)

    def test_typing_and_answering_push_the_auto_close_back(self):
        """交互没结束就不收：发出问题、答案贴回来，两处都把「什么时候收」往后推。"""
        cloud = self.cloud()
        first = cloud._hold
        self.assertIsNotNone(first)
        # 连「这一页该做的事」都问不出来＝这一下真的没有可办的事，才不该重排定时。
        original_task = self.pet.chat_task
        self.pet.chat_task = lambda index=None: ('', '')
        self.addCleanup(setattr, self.pet, 'chat_task', original_task)
        cloud.propose('')
        cloud.submit()
        self.assertEqual(cloud._hold, first)
        cloud.queue.put({'text': '查一下进度',
                         'lines': [pet_cloud.SPEAKER + '：好，把进度面板打开。'], 'result': None})
        cloud.busy = True
        self.assertEqual(cloud.drain(), 1)
        self.assertNotEqual(cloud._hold, first, '答案贴回来之后重新计时，留一段读完的时间再收')
        self.assertFalse(cloud.busy)
        second = cloud._hold
        cloud.propose('查一下进度')
        self.assertTrue(cloud.submit().startswith('查一下进度'))
        self.assertNotEqual(cloud._hold, second, '问题发出去之后也要重新计时')

    def test_the_same_sentence_is_not_said_twice_in_a_row(self):
        expected = self.pet._prefix_output('同一句')
        self.assertEqual(self.pet.broadcast('同一句'), expected)
        self.assertEqual(self.pet.broadcast('同一句'), '', '同一句话不该连着说两遍')
        self.assertEqual(self.pet.cloud().lines.count('同一句'), 1)

    def test_the_record_survives_closing_and_reopening(self):
        cloud = self.cloud()
        self.answer(cloud, '查一下进度')
        self.assertIsNone(self.pet.toggle_chat(), '开着的时候再点一次应当收起')
        self.assertIsNotNone(self.pet.toggle_chat())
        self.assertIs(self.pet.cloud(), cloud, '云朵框实例只建一次，记录才留得住')
        self.assertIn('您：查一下进度', cloud.transcript())

    def test_closing_is_idempotent(self):
        cloud = self.cloud()
        self.assertIsNone(cloud.close())
        self.assertIsNone(cloud.close())
        self.assertFalse(cloud.visible)
        self.assertEqual(cloud.errors, [])

    def test_the_record_keeps_only_the_last_lines(self):
        cloud = pet_cloud.Cloud(self.pet, self.win)
        for index in range(pet_cloud.LINE_LIMIT + 20):
            cloud.append('第 %d 行' % index)
        self.assertEqual(len(cloud.lines), pet_cloud.LINE_LIMIT)
        self.assertEqual(cloud.lines[-1], '第 %d 行' % (pet_cloud.LINE_LIMIT + 19))

    def test_a_long_record_does_not_make_the_cloud_grow_forever(self):
        cloud = self.cloud()
        for index in range(60):
            cloud.append('第 %d 行' % index)
        cloud._render()
        self.assertLessEqual(int(cloud.canvas.cget('height')), pet_cloud.TAIL + pet_cloud.MAX_BODY)

    def test_reply_lines_says_why_the_pet_will_not_act(self):
        lines = pet_cloud.reply_lines({'reply': '开始批量生成。',
                                       'decision': {'run': False, 'reason': '半自动：付费步骤需你点一下确认'}})
        self.assertEqual(lines[0], pet_cloud.SPEAKER + '：开始批量生成。')
        self.assertIn('暂时不动手——半自动', lines[1])

    def test_reply_lines_never_comes_back_empty(self):
        lines = pet_cloud.reply_lines(None)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith(pet_cloud.SPEAKER + '：'))
        # 第 23 期：放行的那一条不再补「我可以接着做」这类空话——真的做了什么由
        # Pet.run_plan 的结果跟在后面说（见 CloudTests 里那条「说了就真的做」）。
        self.assertEqual(len(pet_cloud.reply_lines({'decision': {'run': True}})), 1)
        lines = pet_cloud.reply_lines({'reply': '开始批量生成首帧。', 'decision': {'run': False,
                                                                        'reason': '只提醒模式：不自动执行'}})
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith(pet_cloud.SPEAKER + '：' + pet_cloud.CONFIRM_PREFIX))

    def test_a_cloud_that_cannot_build_is_recorded_not_raised(self):
        original = pet_cloud.Cloud.build

        def boom(self):
            raise RuntimeError('画不出来')

        pet_cloud.Cloud.build = boom
        self.addCleanup(setattr, pet_cloud.Cloud, 'build', original)
        self.pet._cloud = None                     # 别用上一条用例建好的云：这里要的是「建不出来」
        self.assertIsNone(self.pet.open_chat(), '建不出来就别交出半个控件')
        names = [name for name, _text in self.pet.errors]
        self.assertTrue(any(name.startswith('chat') for name in names), '建不起来要留记录')
        self.assertTrue(self.pet.notice, '点了「和宠物说话」必须说一句，不能没反应')

    def test_closing_the_main_window_takes_the_cloud_with_it(self):
        win = self.tk.Tk()
        win.withdraw()
        try:
            fake = FakeDesktop(self.tk, self.ttk, win)
            fake.root = self.fake.root
            pet = pet_ui.attach(fake, autostart=False)
            self.assertIsNotNone(pet.open_chat())
            win.destroy()
            self.assertIsNone(pet.chat)
        finally:
            try:
                win.destroy()
            except Exception:
                pass

    def test_the_bubble_points_at_the_cloud(self):
        self.assertIn(pet_ui.CHAT_HINT, self.pet.text())
        self.assertIn('云朵框', pet_ui.CHAT_HINT)


class LevelColorTests(PetTestCase):
    """第 15 期：头像颜色＝自动化等级（全自动红／半自动蓝／只提示黄）。"""

    def test_the_three_levels_have_three_distinct_colours(self):
        self.assertEqual(sorted(pet_ui.LEVEL_COLORS), sorted(pet_agent.LEVELS))
        self.assertEqual(len({pet_ui.LEVEL_COLORS[level][0] for level in pet_agent.LEVELS}), 3)

    def test_the_paw_and_the_cat_share_one_colour_per_level(self):
        """第 20 期用户报「自动化级别显示错误」：同一档不许蓝爪配黄猫——配色只留一份。"""
        for level in pet_agent.LEVELS:
            with self.subTest(level=level):
                self.assertEqual(pet_ui.PAW_COLORS[level], pet_ui.LEVEL_COLORS[level][:2])
                self.assertEqual(pet_ui.palette('idle', level)[0], pet_ui.PAW_COLORS[level][0])

    def test_the_palette_prefers_the_level_over_the_mood(self):
        self.assertEqual(pet_ui.palette('worry'), pet_ui.MOODS['worry'])
        self.assertEqual(pet_ui.palette('worry', 'auto'), pet_ui.LEVEL_COLORS['auto'])
        self.assertEqual(pet_ui.palette('busy', '不存在'), pet_ui.MOODS['busy'])

    def test_switching_the_level_keeps_the_avatar_identity_colour(self):
        self.pet.agent.set_level('semi')
        self.pet.draw()
        self.assertEqual(self.pet.agent.level, 'semi')
        self.pet.click('level')                      # 半自动 → 全自动
        self.assertEqual(self.pet.agent.level, 'auto')
        self.assertEqual(self.body_colour(), pet_ui.SANHU_FUR,
                         '等级由猫爪与文字表达，三虎头像保持固定虎皮橙')
        self.pet.click('level')                      # 全自动 → 只提示
        self.assertEqual(self.pet.agent.level, 'hint')
        self.assertEqual(self.body_colour(), pet_ui.SANHU_FUR)

    def body_colour(self):
        fur = self.pet.canvas.find_withtag('fur')
        return self.pet.canvas.itemcget(fur[2], 'fill')

    def test_the_level_comes_from_the_snapshot(self):
        self.assertEqual(self.pet.level({'level': 'auto'}), 'auto')
        self.assertIn(self.pet.level({'level': '不存在'}), pet_agent.LEVELS)

    def test_a_broken_agent_falls_back_to_the_default_level(self):
        class Broken:
            @property
            def level(self):
                raise RuntimeError('读不到')
        original = pet_ui.Pet.agent
        pet_ui.Pet.agent = property(lambda self: Broken())
        self.addCleanup(setattr, pet_ui.Pet, 'agent', original)
        self.assertEqual(self.pet.level({}), pet_agent.DEFAULT_LEVEL)


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
        self.assertIn('02 初步分镜', parts[0])

    def test_missing_first_frames_are_reported(self):
        self.counts.update(shots=10, frames=4)
        parts = self.pet.gaps(force=True)
        self.assertIn('首帧还差 6 个镜头', parts[0])
        self.assertIn('06 首帧管理', parts[0])

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
        self.assertIn(self.pet.notice, self.pet.cloud().transcript(), '这句话必须真的播报出去')

    def test_pausing_and_resuming_say_so(self):
        self.pet.click('pause')
        self.assertIn('已暂停自动执行', self.pet.notice)
        self.pet.click('resume')
        self.assertIn('已继续自动执行', self.pet.notice)
        self.assertIn(self.pet.notice, self.pet.cloud().transcript())


class MenuFeedbackTests(PetTestCase):
    """第 13／19 期：右键菜单的每一项都必须说一句，不再有「点了没提示」的项。"""

    # 自己就是「看得见的开关」的项单列用例，不进「逐项都要说话」那条循环。
    EXCLUDED = ('向三虎提问',)

    def menu_items(self):
        """菜单上**点得动**的那几项（第 60 期第 2 条起栏里多了几行灰色小标题：它们也是
        type='command'，但 state='disabled'，不是给用户按的）。"""
        items = []
        for index in range(self.pet.menu.index('end') + 1):
            if self.pet.menu.type(index) != 'command':
                continue
            if str(self.pet.menu.entrycget(index, 'state')) == 'disabled':
                continue
            items.append((index, self.pet.menu.entrycget(index, 'label')))
        return items

    def index_of(self, label):
        for index, text in self.menu_items():
            if text == label:
                return index
        raise AssertionError('菜单里没有这一项：' + label)

    def test_the_menu_keeps_only_the_daily_entries(self):
        labels = [text for _index, text in self.menu_items()]
        self.assertIn('向三虎提问', labels)
        self.assertIn(pet_ui.PANEL_MENU_LABEL, labels)      # 第 44 期：附件里的说法「打开三虎面板」
        for gone in ('独立小窗（桌面常驻贴片）', '和宠物说话（云朵框）',
                     '显示主窗口（从常驻切回主界面）'):
            self.assertNotIn(gone, labels, gone + ' 已经搬走／删掉')
        for name in ('level', 'roam', 'tray', 'autostart', 'showmain', 'toast', 'window'):
            self.assertNotIn(name, self.pet.menu_index, name + ' 还挂在菜单上')
        # 第 44 期：'quit' 按附件摆回来了（最后一行），所以这几项里不再点名它。
        self.assertIn('quit', self.pet.menu_index)
        # 第 22 期：「暂停」与「稍后再说」回到一级栏，进度面板也回到功能栏。
        for name in ('pause', 'snooze', 'panel'):
            self.assertIn(name, self.pet.menu_index, name + ' 应当在一级功能栏上')

    def groups(self):
        """菜单按分隔线切成几块（逐块给出条目名）。"""
        blocks, current = [], []
        for index in range(self.pet.menu.index('end') + 1):
            if self.pet.menu.type(index) == 'separator':
                blocks.append(current)
                current = []
                continue
            current.append(str(self.pet.menu.entrycget(index, 'label')))
        blocks.append(current)
        return blocks

    def test_the_menu_is_split_into_five_blocks(self):
        """第 50 期第 3 条：右键栏按用途分成五块，块间拉开——原来只有两条分隔线，
        十一项连成一大片（用户报「右键界面列表有点乱」）。块内次序照旧是「越靠上越常按」。
        """
        blocks = self.groups()
        self.assertEqual(blocks[0], ['向三虎提问', '一键执行（重试＋补首帧＋日报）'],
                         '① 和三虎说话（一眼就懂，不加小标题）')
        self.assertEqual(blocks[1], ['【进度与待确认】', pet_ui.PANEL_MENU_LABEL, '重试失败项',
                                     pet_ui.DETAIL_MENU_LABEL, '跳过这张'],
                         '② 进度与待确认')
        self.assertEqual(blocks[2], ['【设置与模型】', pet_ui.SETTINGS_LABEL, self.pet.model_label()],
                         '③ 设置与模型')
        self.assertEqual(blocks[3], ['【运行状态】', self.pet.pause_label(), self.pet.snooze_label()],
                         '④ 运行状态')
        self.assertEqual(blocks[4], [pet_ui.QUIT_LABEL],
                         '⑤ 退出程序单独一块，别跟免打扰挤在一起')
        self.assertEqual(len(blocks), 5, '再多就又成一大片了')

    def test_the_section_headings_are_readable_but_not_clickable(self):
        """第 60 期第 2 条：中间那三块各带一行灰色小标题——用户扫一眼就知道该去哪块找。"""
        headings = [(index, str(self.pet.menu.entrycget(index, 'label')))
                    for index in range(self.pet.menu.index('end') + 1)
                    if self.pet.menu.type(index) == 'command'
                    and str(self.pet.menu.entrycget(index, 'state')) == 'disabled']
        self.assertEqual([text for _index, text in headings],
                         ['【进度与待确认】', '【设置与模型】', '【运行状态】'])
        for index, _text in headings:
            self.assertEqual(self.pet.menu.invoke(index), '', '标题按不动')

    def test_every_item_says_something_after_it_runs(self):
        self.pet._autostart = pet_ui.Autostart(api=FakeWinreg())
        cloud = self.pet.cloud()
        for index, label in self.menu_items():
            if label in self.EXCLUDED:
                continue
            self.pet.notice = ''
            self.pet._last_broadcast = ''
            del cloud.lines[:]
            self.pet.menu.invoke(index)
            self.assertTrue(self.pet.notice, label + ' 没有留下提示')
            expected = ' '.join(self.pet.notice.split())
            if label in (pet_ui.PANEL_MENU_LABEL, pet_ui.DETAIL_MENU_LABEL):
                self.assertIn(self.pet.notice.splitlines()[0], cloud.transcript(),
                              label + ' 没有在三虎提示框展示内容')
            else:
                self.assertTrue(any(expected in line for line in cloud.lines),
                                label + ' 没有播报出去（云朵可保留完成／警告前缀）')

    def test_the_progress_entry_is_gone_but_the_voice_stays(self):
        """进度面板从功能栏搬走，改成三虎自己挑时机的圆形气泡。"""
        for gone in ('进度面板（主窗口右上角浮层）', '收集事件'):
            with self.assertRaises(AssertionError):
                self.index_of(gone)
        self.assertTrue(self.pet.progress_voice(force=True))
        self.assertEqual(self.pet.cloud().shape, pet_cloud.SHAPE_ROUND)

    def test_a_shown_menu_keeps_the_cloud_shut_and_says_it_afterwards(self):
        """第 47 期第 4 条：右键下拉栏显示期间三虎不冒云朵框；栏一收起，那句话补上。"""
        seen = []

        def fake_popup(x, y):
            seen.append(self.pet._menu_open)
            self.assertEqual(self.pet.broadcast('栏里冒出来的话'), '', '栏开着时先压住')
            self.assertFalse(self.pet.cloud_visible(), '栏开着时不冒云朵框')

        original = self.pet.menu.tk_popup
        self.pet.menu.tk_popup = fake_popup
        self.addCleanup(setattr, self.pet.menu, 'tk_popup', original)
        self.pet.popup_at(10, 20)
        self.assertEqual(seen, [True], '弹栏期间标记要是开着的')
        self.assertFalse(self.pet._menu_open, '栏收起后标记清掉')
        self.assertFalse(self.pet._held_broadcast, '压住的那句话已经补说出去')
        self.assertTrue(self.pet.cloud_visible(), '收起后补上那句话')
        self.assertIn('栏里冒出来的话', self.pet.cloud().transcript())

    def test_the_menu_entries_own_windows_are_not_blocked(self):
        """栏里那几项自己要开的东西照旧：栏开着时「向三虎提问」照样把对话打开。"""
        original = self.pet.menu.tk_popup
        self.pet.menu.tk_popup = lambda x, y: self.pet.menu.invoke(self.index_of('向三虎提问'))
        self.addCleanup(setattr, self.pet.menu, 'tk_popup', original)
        self.pet.popup_at(10, 20)
        self.assertTrue(self.pet.cloud().visible)
        self.assertEqual(self.pet.cloud().shape, pet_cloud.SHAPE_CLOUD, '开的是对话框，不是随手一句')

    def test_the_chat_entry_opens_the_cloud_and_says_so(self):
        self.pet.menu.invoke(self.index_of('向三虎提问'))
        self.assertIsNotNone(self.pet.chat)
        self.assertTrue(self.pet.cloud().visible)
        self.assertIn('云朵框已打开', self.pet.notice)

    def test_retrying_the_failures_says_what_happened(self):
        self.pet.menu.invoke(self.index_of('重试失败项'))
        self.assertIn('没有待确认的项', self.pet.notice)
        self.assertIn('没有待确认的项', self.pet.cloud().transcript())
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.menu.invoke(self.index_of('重试失败项'))
        self.assertIn('已重试失败项：1 项', self.pet.notice)
        self.assertEqual(self.fake.kicks, ['pet', 'pet'])

    def test_collecting_the_events_says_how_many(self):
        """收集事件并进了进度气泡：时机由三虎自己挑。

        第 49 期第 3 条：一个事件都没抽到时就一个字都不说——「已收集 0 个事件」什么也没说。
        """
        self.assertEqual(self.pet.collect_events(), 0)
        self.assertNotIn('已收集', self.pet.notice, '抽到 0 个就别报数')
        self.pet.pump = lambda *args, **kwargs: 3
        self.pet.collect_events()
        self.assertIn('已收集 3 个事件', self.pet.notice, '真抽到了才报')

    def test_an_action_that_blows_up_is_recorded_and_still_speaks(self):
        def boom():
            raise RuntimeError('动作坏了')

        self.assertIsNone(self.pet.act(boom))
        self.assertTrue(any(name == 'act' for name, _text in self.pet.errors))
        self.assertTrue(self.pet.cloud().visible, '动作出错也要让用户看见')

class PetClickTests(PetTestCase):
    """第 16 期：单击三虎＝收起云朵框＋唤出功能下拉栏；等级／模型在子菜单里一次点到位。"""

    def test_clicking_the_pet_flips_the_cloud_both_ways(self):
        """第 19 期：单击直接开／关云朵框（原来借道下拉栏，才有「再点一下关不掉」）。"""
        self.assertIsNotNone(self.pet.open_chat())
        self.assertTrue(self.pet.cloud().visible)
        self.pet.flip_chat()
        self.assertFalse(self.pet.cloud().visible, '再点一下就是收起来')
        self.assertIsNone(self.pet.chat)
        self.assertTrue(self.pet.muted(), '刚点掉的云朵框要安静一会儿，别被自动播报顶回来')
        self.pet.flip_chat()
        self.assertTrue(self.pet.cloud().visible, '再点一下又打开')

    def test_a_single_click_waits_for_the_double_click(self):
        self.pet.pet_click(_Event(widget=self.pet.canvas))
        self.assertIsNotNone(self.pet._click_at, '单击等第二下：双击要接管')

    def test_a_double_click_cancels_the_pending_menu(self):
        self.pet.pet_click(_Event(widget=self.pet.canvas))
        self.assertIsNotNone(self.pet._click_at)
        self.pet.double_click()
        self.assertIsNone(self.pet._click_at, '双击＝和三虎说话，待唤出的菜单要撤掉')
        self.assertTrue(self.pet.cloud().visible)

    def test_the_menu_is_ordered_by_how_often_it_is_used(self):
        labels = [self.pet.menu.entrycget(index, 'label')
                  for index in range(self.pet.menu.index('end') + 1)
                  if self.pet.menu.type(index) == 'command']
        self.assertEqual(labels[0], '向三虎提问')
        self.assertLess(labels.index('一键执行（重试＋补首帧＋日报）'), labels.index('重试失败项'))
        self.assertLess(labels.index('重试失败项'), labels.index(pet_ui.DETAIL_MENU_LABEL))
        self.assertNotIn('生成今日日报', labels, '日报周报搬走，功能照旧')
        self.assertEqual(labels[-1], pet_ui.QUIT_LABEL, '第 44 期：附件里的「退出」落在最后一行')

    def test_the_paws_set_the_level_directly(self):
        """等级从菜单搬到三虎身旁的猫爪上：点哪一爪就是哪一档，一次点到位。"""
        self.assertNotIn('level', self.pet.menu_index, '菜单里不再重复一栏等级')
        step = pet_ui.PAW_SIZE + pet_ui.PAW_GAP
        self.pet.paw_click(_Point(step))
        self.assertEqual(self.pet.agent.level, pet_agent.LEVELS[1])
        self.assertEqual(self.pet.notice, pet_ui.LEVEL_SWITCH_NOTES[pet_agent.LEVELS[1]])
        self.pet.paw_click(_Point(0))
        self.assertEqual(self.pet.agent.level, pet_agent.LEVELS[0])
        self.assertIsNone(self.pet.paw_click(_Point(10 * step)), '超出范围的点击不认领')

    def test_the_model_submenu_sets_the_model_directly(self):
        """第 43 期：子菜单不再写死三档，条目来自模型池；点哪一条就是哪一条。"""
        index = self.pet.menu_index['model']
        self.assertEqual(self.pet.menu.type(index), 'cascade')
        sub = self.pet.menu.nametowidget(self.pet.menu.entrycget(index, 'menu'))
        self.assertEqual(sub.entrycget(0, 'label'), '✓ 自动')
        sub.invoke(2)
        self.assertEqual(self.pet.tier, 'deepseek-v4-pro')
        self.assertIn('已切换到 DeepSeek V4 Pro', self.pet.notice)

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


class OverlayTests(PetTestCase):
    """第 19 期：贴片、猫爪、等级小字永远在最上层，否则被内容框压住，点了等于没点。"""

    class Raiser:
        """假控件：只记 Tcl 调用（Canvas 的 lift 被覆写成了 tag_raise，见 lift_patch 的注释）。"""

        def __init__(self, name):
            self._w = '.' + name
            self.calls = []
            self.tk = self

        def call(self, *args):
            self.calls.append(args)
            return ''

    def test_the_patch_the_paws_and_the_caption_are_raised(self):
        raisers = [self.Raiser(name) for name in ('canvas', 'paws', 'caption')]
        self.pet.canvas, self.pet.paws, self.pet.caption = raisers
        self.assertIs(self.pet.lift_patch(), raisers[0])
        for raiser in raisers:
            self.assertEqual(raiser.calls, [('raise', raiser._w)])

    def test_the_real_widgets_are_raised_without_errors(self):
        self.pet.lift_patch()
        self.assertEqual([item for item in self.pet.errors if item[0] == 'lift'], [])

    def test_a_widget_that_cannot_raise_is_recorded_not_raised(self):
        class Boom:
            def __init__(self):
                self.tk = self
                self._w = '.boom'

            def call(self, *args):
                raise RuntimeError('抬不动')

        self.pet.paws = Boom()
        self.assertIs(self.pet.lift_patch(), self.pet.canvas)
        self.assertTrue(any(name == 'lift' for name, _text in self.pet.errors))


class PoseTests(PetTestCase):
    """第 17 期：猫样——右上角那只猫会自己换动作（爬行／舔爪／打哈欠／摇尾巴／撒娇）。"""

    def paint_pose(self, pose, step=1):
        self.pet.canvas.delete("all")
        pet_ui.paint(self.pet.canvas, step, "idle", 0.0, None, pose)
        return self.pet.canvas

    def test_every_pose_has_its_own_marks_and_only_its_own(self):
        for pose in pet_ui.POSES:
            canvas = self.paint_pose(pose)
            if pose == "sit":
                self.assertEqual(len(canvas.find_withtag("pose-sit")), 0,
                                 "端坐就是那套基础画法，不该另加图元")
                continue
            self.assertTrue(canvas.find_withtag("pose-%s" % pose), "%s 要有自己的图元" % pose)
            for other in pet_ui.POSES:
                if other == pose or other == "sit":
                    continue
                self.assertEqual(len(canvas.find_withtag("pose-%s" % other)), 0,
                                 "%s 这一帧不该画出 %s 的东西" % (pose, other))

    def test_the_yawn_blushes_instead_of_gaping(self):
        """第 24 期第 6 条：打哈欠不再在脸上开一个黑洞（用户嫌丑），改成脸颊泛红。"""
        canvas = self.paint_pose("yawn")
        self.assertEqual(len(canvas.find_withtag("mouth-open")), 0, "脸上不再有那张张开的嘴")
        blushes = canvas.find_withtag("blush")
        self.assertTrue(blushes, "困意靠腮红说")
        for item in blushes:
            self.assertEqual(canvas.itemcget(item, "fill"), pet_ui.SANHU_BLUSH,
                             "基础腮红与打哈欠腮红共用三虎头像配色")
        self.assertTrue(canvas.find_withtag("pose-yawn"), "这一帧仍要认得出是打哈欠")

    def test_the_drawn_frame_follows_the_current_pose(self):
        self.pet.cat.pose = "yawn"
        self.pet.draw()
        self.assertTrue(self.pet.canvas.find_withtag("pose-yawn"))
        self.pet.cat.pose = "wag"
        self.pet.draw()
        self.assertEqual(len(self.pet.canvas.find_withtag("pose-yawn")), 0)
        self.assertTrue(self.pet.canvas.find_withtag("pose-wag"))

    def test_the_cat_changes_its_pose_on_its_own(self):
        start = self.pet.frame
        for _ in range(80):
            self.pet.step()
        self.assertGreater(self.pet.cat.changes, 1, "闲着的时候也该自己换动作")
        self.assertIn(self.pet.cat.pose, pet_ui.POSES)
        self.assertEqual(self.pet.frame, start + 80)

    def test_the_cat_never_repeats_the_same_pose_twice_in_a_row(self):
        cat = pet_ui.Cat(rand=SequenceRand([0.0]))
        seen = [cat.next(frame, force=True) for frame in range(len(pet_ui.POSES) * 3)]
        for before, after in zip(seen, seen[1:]):
            self.assertNotEqual(before, after, "连着两次同一个动作等于没换，看着像卡住了")

    def test_a_pose_lasts_between_the_configured_span(self):
        cat = pet_ui.Cat(rand=SequenceRand([0.0]))
        cat.next(0, force=True)
        self.assertGreaterEqual(cat.until, pet_ui.POSE_MIN)
        self.assertLessEqual(cat.until, pet_ui.POSE_MAX)

    def test_a_broken_random_source_never_raises(self):
        def boom():
            raise RuntimeError("随机源坏了")

        for bad in (boom, lambda: float("nan"), lambda: -1.0, lambda: 9.0, lambda: "不是数"):
            cat = pet_ui.Cat(rand=bad)
            for frame in range(30):
                self.assertIn(cat.next(frame), pet_ui.POSES)
            self.assertIn(cat.describe()["name"], pet_ui.POSE_NAMES.values())

    def test_the_blink_stays_on_the_frame_rhythm(self):
        """动作再换，眨眼仍只按帧走：用例与眼睛相关的断言才稳。"""
        for pose in pet_ui.POSES:
            self.pet.cat.pose = pose
            self.pet.draw(0)
            self.assertEqual(len(self.pet.canvas.find_withtag("eye-dot")), 2, pose)
            self.pet.draw(3)
            self.assertEqual(len(self.pet.canvas.find_withtag("eye-line")), 2, pose)


class CaptionTests(PetTestCase):
    """第 18 期：贴片左边那行小字写着现在是哪一档（用户报「正常／半自动／全自动不显示了」）。"""

    def test_the_caption_sits_to_the_right_of_the_patch(self):
        """第 21 期：小字挪到三虎右边（用户要的「文字移动到三虎右侧」）。"""
        caption = self.pet.caption
        self.assertIsNotNone(caption, '三虎右边该有一行等级小字')
        info = caption.place_info()
        self.assertEqual(float(info['relx']), 1.0)
        self.assertEqual(info['anchor'], 'ne')
        patch = int(self.pet.canvas.place_info()['x'])
        self.assertEqual(patch, pet_ui.PATCH_X, '贴片往左挪了一个身位')
        self.assertEqual(int(info['x']), -pet_ui.CAPTION_RIGHT, '小字贴着窗口右边往内 CAPTION_RIGHT')
        self.assertGreater(int(info['x']), patch, '小字落在贴片右边（-8 比 -68 更靠右）')

    def test_the_caption_clears_the_patch(self):
        """小字落在贴片右边那条空档里：不出窗口、也不压到猫脸上；标题栏文字还要让开。"""
        caption = self.pet.caption
        info = caption.place_info()
        self.assertLessEqual(-int(info['x']), -pet_ui.PATCH_X, '小字的右沿不许越过贴片的右沿')
        left_edge = -int(info['x']) - caption.winfo_reqwidth()
        self.assertGreaterEqual(left_edge, pet_ui.PATCH_X,
                                '小字的左沿要在贴片右沿以右，别压到猫脸')
        self.assertGreaterEqual(pet_ui.CAPTION_ROOM, caption.winfo_reqwidth() + 6,
                                'CAPTION_ROOM 要够这三个字用')
        self.assertGreaterEqual(pet_ui.HEAD_PAD,
                                -pet_ui.PATCH_X + pet_ui.CAPTION_RIGHT + pet_ui.CAPTION_ROOM,
                                '标题栏文字让出的宽度要装下小字＋贴片')

    def test_the_caption_is_black_ink(self):
        """第 21 期：三档小字一律黑色（用户要的「文字全部用黑色」）。"""
        self.assertEqual(pet_ui.CAPTION_INK, '#000000')
        for level in pet_agent.LEVELS:
            with self.subTest(level=level):
                self.pet.agent.set_level(level)
                self.pet.draw()
                self.assertEqual(str(self.pet.caption.cget('foreground')), pet_ui.CAPTION_INK)

    def test_the_caption_follows_the_level(self):
        for level in pet_agent.LEVELS:
            with self.subTest(level=level):
                self.pet.agent.set_level(level)
                self.pet.draw()
                self.assertEqual(self.pet.caption.cget('text'), pet_ui.LEVEL_CAPTIONS[level])

    def test_the_paused_caption_stays_black(self):
        """第 22 期：用户要「已暂停也显示黑色」——小字一律 CAPTION_INK，不跟猫一起变灰。"""
        self.pet.agent.pause('用例')
        self.pet.draw()
        self.assertEqual(self.pet.caption_text(), pet_ui.PAUSED_CAPTION)
        self.assertEqual(str(self.pet.caption.cget('foreground')), pet_ui.CAPTION_INK,
                         '暂停时小字仍是黑的')
        self.pet.agent.resume()

    def test_the_caption_says_the_users_words_for_the_hint_level(self):
        self.assertEqual(pet_ui.LEVEL_CAPTIONS['hint'], '只提醒')
        self.assertEqual(pet_ui.LEVEL_CAPTIONS['semi'], '半自动')
        self.assertEqual(pet_ui.LEVEL_CAPTIONS['auto'], '全自动')

    def test_pausing_writes_a_paused_caption_and_greys_the_cat(self):
        self.pet.agent.pause('用例')
        self.pet.draw()
        self.assertEqual(self.pet.caption.cget('text'), pet_ui.PAUSED_CAPTION)
        self.assertEqual(self.body_colour(), pet_ui.MOODS['paused'][0], '暂停时整只置灰')
        self.pet.agent.resume()
        self.pet.draw()
        self.assertNotEqual(self.pet.caption.cget('text'), pet_ui.PAUSED_CAPTION)

    def body_colour(self):
        fur = self.pet.canvas.find_withtag('fur')
        return self.pet.canvas.itemcget(fur[2], 'fill')


class ShapeTests(PetTestCase):
    """第 18 期：四种对话框形状——各自的图元、配色与写字框。

    第 57 期第 1 条：四种外形统一成方框（用户要的「全部改成方形框，保留颜色的区分」），
    这组用例改成验「外形是同一份方框几何 ＋ 颜色各不相同 ＋ 写字框够宽」。
    """

    def test_every_shape_has_parts_colours_and_a_width(self):
        for shape in pet_cloud.SHAPES:
            with self.subTest(shape=shape):
                parts = pet_cloud.shape_parts(shape, 400, 200)
                self.assertTrue(parts, '每个形状都得画得出来')
                for part in parts:
                    self.assertIn(part[0], ('oval', 'ellipse', 'rect', 'poly'))
                self.assertGreater(pet_cloud.shape_width(shape), 0)
                self.assertEqual(len(pet_cloud.shape_colors(shape)), 2)
                self.assertGreater(pet_cloud.shape_min_body(shape), 0)
                self.assertEqual(len(pet_cloud.text_box(shape, 400, 200)), 4)

    def test_an_unknown_shape_falls_back_to_the_cloud(self):
        self.assertEqual(pet_cloud.shape_parts('不存在', 400, 200),
                         pet_cloud.shape_parts(pet_cloud.SHAPE_CLOUD, 400, 200))

    def test_the_progress_bubble_is_a_square_frame(self):
        """第 57 期第 1 条：进度提示框（原来是宽椭圆）也改成方框，只留「提示蓝」这一档。"""
        width = pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_ROUND]
        height = pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_ROUND]
        parts = pet_cloud.shape_parts(pet_cloud.SHAPE_ROUND, width, height)
        self.assertEqual({part[0] for part in parts}, {'rect', 'oval'}, '只有框身与四个圆角')
        widest = max(part[3] - part[1] for part in parts if part[0] == 'rect')
        self.assertGreaterEqual(widest, width * 0.9, '框身要占满整条宽度')
        from ui_tokens import COLORS
        self.assertEqual(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_ROUND],
                         (COLORS['primary_subtle'], COLORS['primary']), '颜色来自提示蓝令牌')

        box = pet_cloud.text_box(pet_cloud.SHAPE_ROUND, width, height)
        self.assertGreaterEqual(box[2], 190, '写字框够宽，一行多放得下几个字')

    def test_the_puff_is_a_square_frame_in_red(self):
        """第 57 期第 1 条：可爱话那一档（原来是一圈鼓包叠出来的云）也是方框，颜色照旧偏红。"""
        width = pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF]
        height = pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_PUFF]
        parts = pet_cloud.shape_parts(pet_cloud.SHAPE_PUFF, width, height)
        kinds = [part[0] for part in parts]
        self.assertEqual(set(kinds), {'rect', 'oval'}, '只有框身与四个圆角')
        self.assertEqual(parts, pet_cloud.shape_parts(pet_cloud.SHAPE_CLOUD, width, height),
                         '四种框的外形一模一样')
        self.assertNotEqual(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_PUFF],
                            pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_CLOUD], '颜色仍分得开')

    def test_the_puff_stays_inside_its_body(self):
        """框身与四角的圆不许顶出云身画布（顶出去会被浮窗裁掉，框就成了切边的）。"""
        for width, height in ((300, 216), (300, 150), (240, 132)):
            with self.subTest(size=(width, height)):
                parts = pet_cloud.shape_parts(pet_cloud.SHAPE_PUFF, width, height)
                for part in parts:
                    if part[0] == 'oval':
                        self.assertGreaterEqual(part[1] - part[3], -0.5)
                        self.assertLessEqual(part[1] + part[3], width + 0.5)
                        self.assertGreaterEqual(part[2] - part[3], -0.5)
                        self.assertLessEqual(part[2] + part[3], height + 0.5)
                    else:
                        self.assertGreaterEqual(part[1], -0.5)
                        self.assertLessEqual(part[3], width + 0.5)
                        self.assertGreaterEqual(part[2], -0.5)
                        self.assertLessEqual(part[4], height + 0.5)

    def test_the_tail_grows_out_of_the_shape(self):
        """尾巴根要落在形状自己身上，不能飘在云身外面（看着像三点贴错了地方）。"""
        for shape in pet_cloud.SHAPES:
            with self.subTest(shape=shape):
                width = pet_cloud.shape_width(shape)
                height = pet_cloud.shape_min_body(shape)
                x, y = pet_cloud.shape_root(shape, width, height)
                self.assertGreaterEqual(x, width * 0.5)
                self.assertLess(x, width)
                self.assertLess(y, height)
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)

    def test_the_tag_is_a_rounded_rectangle(self):
        kinds = {part[0] for part in pet_cloud.shape_parts(pet_cloud.SHAPE_TAG, 360, 120)}
        self.assertEqual(kinds, {'rect', 'oval'})

    def test_the_chat_box_is_a_squared_frame(self):
        """第 24 期第 2 条：云朵对话框改成方框（用户要的「正方形」），不再是「一堆圆叠出来的云」。"""
        width, body = pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_CLOUD], 200
        parts = pet_cloud.shape_parts(pet_cloud.SHAPE_CLOUD, width, body)
        self.assertEqual({part[0] for part in parts}, {'rect', 'oval'}, '只有框身与四个圆角')
        widest = max(part[3] - part[1] for part in parts if part[0] == 'rect')
        self.assertGreaterEqual(widest, width * 0.9, '框身要占满整条宽度')
        self.assertLessEqual(max(part[3] for part in parts if part[0] == 'oval'), width * 0.2,
                             '四角的圆不许大得像云朵的圆弧')

    def test_the_four_frames_share_one_shape_and_keep_their_colours(self):
        """第 57 期第 1 条：四种聊天框的外形完全一样（都是方框），分得开的只剩颜色。"""
        for width, height in ((300, 150), (300, 216), (240, 132)):
            with self.subTest(size=(width, height)):
                boxes = [pet_cloud.shape_parts(shape, width, height) for shape in pet_cloud.SHAPES]
                for parts in boxes[1:]:
                    self.assertEqual(parts, boxes[0], '四种框是同一份方框几何')
        colours = [pet_cloud.SHAPE_COLORS[shape] for shape in pet_cloud.SHAPES]
        self.assertEqual(len(set(colours)), len(colours), '四种颜色各不相同')

    def test_switching_the_shape_repaints_the_bubble(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_PUFF)
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        self.assertTrue(cloud.canvas.find_withtag('cloud'), '换了形状也要重新画出来')
        self.assertEqual(cloud.fill(), pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_PUFF][0])
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_CLOUD)      # 换回云朵走的是同一扇窗
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        self.assertEqual(cloud.fill(), pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_CLOUD][0])


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
        now = [0.0]
        self.pet.clock = lambda: now[0]
        self.pet.greet()
        now[0] = 5.0
        self.pet.progress_voice()
        self.pet.tune_advance()
        self.assertEqual(self.pet._progress_at, 5.0, '进度气泡的节流从安静期里重新起算')
        self.assertEqual(self.pet._advance_at, 5.0, '自动推进的节流一样往后挪')
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


class ModelPoolTests(PetTestCase):
    """第 43 期：模型设置＝模型池（规格《三虎模型设置》）——右键两栏 ＋ 两扇窗 ＋ 即时生效。"""

    def _walk(self, widget, kind):
        found = []
        if isinstance(widget, kind):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self._walk(child, kind))
        return found

    def model_menu(self):
        index = self.pet.menu_index['model']
        return self.pet.menu.nametowidget(self.pet.menu.entrycget(index, 'menu'))

    def menu_labels(self, menu):
        return ['---' if menu.type(index) == 'separator' else menu.entrycget(index, 'label')
                for index in range(menu.index('end') + 1)]

    def test_the_shipped_pool_and_auto_are_the_only_menu_entries(self):
        labels = self.menu_labels(self.model_menu())
        self.assertEqual(labels[0], '✓ 自动')
        self.assertIn('DeepSeek V4 Flash', labels)
        self.assertIn('DeepSeek V4 Pro', labels)
        self.assertIn('GPT-4o', labels)
        self.assertIn('Qwen-Max', labels)
        self.assertEqual(labels[-1], '+ 新增模型…')

    def test_the_probe_message_reports_how_long_it_took(self):
        """规格：成功那句写「连接成功，延迟 xxx ms」，失败写清原因（HTTP 码 ＋ 错误）。"""
        original = model_secrets.PROTECTOR
        def protector(data, decrypt=False, label=''):
            payload = bytes(data)
            if decrypt:
                if not payload.startswith(b'test:'):
                    raise ValueError('bad test secret')
                return payload[5:][::-1]
            return b'test:' + payload[::-1]
        model_secrets.PROTECTOR = protector
        self.addCleanup(setattr, model_secrets, 'PROTECTOR', original)
        record = model_pool.save_local_key({'model': 'm', 'base_url': 'https://x.test/v1'},
                                           'sk-test-1234', self.pet.program)
        self.pet.probe_transport = lambda url, body, head, timeout: {'ok': True, 'status': 200, 'data': {}}
        said = pet_models_ui.probe_line(record, self.pet)
        self.assertIn('连接成功，延迟', said)
        self.assertIn('ms', said)
        self.pet.probe_transport = lambda url, body, head, timeout: {'ok': False, 'status': 401,
                                                                     'error': 'HTTP 401：unauthorized'}
        self.assertIn('HTTP 401', pet_models_ui.probe_line(record, self.pet))

    def test_api_configuration_lists_desktop_agents_in_the_model_pool(self):
        """桌面 Agent 是阶段配置可选模型，不是模型管理底部的启动按钮。"""
        records = model_pool.pool(program=self.pet.program)
        self.assertIn('chatgpt-desktop', records)
        self.assertIn('claude-desktop', records)
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.assertFalse(hasattr(win, '_pet_open_claude'))

    def test_the_settings_cascade_opens_the_model_page(self):
        self.assertIn('settings', self.pet.menu_index)
        index = self.pet.menu_index['settings']
        self.assertEqual(self.pet.menu.type(index), 'cascade')

    def test_the_settings_cascade_offers_the_same_pages_as_the_gear(self):
        """第 44 期：附件那几格（SKILL 管理不做）；

        第 59 期第 10 条：与齿轮那扇窗的分页**同步**——名字一模一样（原来这里自己
        写了一份「模型配置…」，齿轮那边早改名「三虎模型配置」了）。
        """
        import pet_settings_ui
        index = self.pet.menu_index['settings']
        sub = self.pet.menu.nametowidget(self.pet.menu.entrycget(index, 'menu'))
        labels = self.menu_labels(sub)
        self.assertEqual(self.pet.menu.entrycget(index, 'label'), pet_ui.SETTINGS_LABEL)
        self.assertEqual(labels, [title for _key, title in pet_settings_ui.TABS])
        self.assertEqual(pet_ui.SETTINGS_ENTRIES, tuple(pet_settings_ui.TABS),
                         '两边只认同一份表，以后改名不会再各改各的')
        self.assertNotIn('SKILL 管理', labels, '用户这一轮说 SKILL 管理不用做')

    def test_switching_a_model_persists_and_ticks_it(self):
        self.assertEqual(self.pet.set_tier('deepseek-v4-pro'), 'deepseek-v4-pro')
        self.assertIn('已切换到 DeepSeek V4 Pro', self.pet.notice)
        self.assertEqual(self.pet.agent.client.config['pro_model'], 'deepseek-v4-pro')
        self.assertEqual(self.pet.agent.client.config['flash_model'], 'deepseek-v4-pro')
        self.assertIn('✓ DeepSeek V4 Pro', self.menu_labels(self.model_menu()))
        tasks = model_pool.agent_models(program=self.pet.program)
        self.assertEqual(tasks['default'], 'deepseek-v4-pro', '写盘读回来还是这一档')

    def test_unknown_model_is_refused(self):
        self.assertEqual(self.pet.set_tier('不存在'), self.pet.tier)

    def test_deleting_the_current_model_falls_back_to_auto(self):
        self.pet.set_tier('deepseek-v4-pro')
        self.pet.delete_pool_model('deepseek-v4-pro')
        self.assertEqual(self.pet.tier, model_pool.AUTO)

    def test_the_fallback_rides_along_in_the_client_config(self):
        self.pet.set_tier('deepseek-v4-pro')
        fallback = self.pet.agent.client.config['fallback']
        self.assertEqual(fallback['pro_model'], 'deepseek-v4-flash')

    def test_an_external_tier_can_still_be_plugged_in(self):
        before = dict(pet_ui.TIER_MODELS)

        def restore():
            pet_ui.TIER_MODELS.clear()
            pet_ui.TIER_MODELS.update(before)
            pet_ui.TIER_CYCLE = tuple(pet_ui.TIER_MODELS)
            pet_ui.TIER_NAMES = {key: value[0] for key, value in pet_ui.TIER_MODELS.items()}

        self.addCleanup(restore)
        options = self.pet.register_model('local', '本地 Llama', {'force_tier': 'local'})
        self.assertEqual(options['local'], '本地 Llama')
        self.assertIn('本地 Llama', self.menu_labels(self.model_menu()))
        self.assertEqual(self.pet.set_tier('local'), 'local')
        self.assertEqual(self.pet.agent.client.config['force_tier'], 'local')
        self.assertIn('本地 Llama', self.pet.model_label())

    def test_the_settings_window_lists_the_four_dimensions(self):
        win = self.pet.open_model_settings()
        self.addCleanup(win.destroy)
        combos = self._walk(win, self.ttk.Combobox)
        self.assertEqual(len(combos), 4)
        self.assertEqual(combos[0].get(), model_pool.AUTO_LABEL, '默认模型开局是「自动」')
        self.assertEqual(combos[1].get(), 'DeepSeek V4 Pro')
        self.assertEqual(combos[2].get(), 'DeepSeek V4 Pro')
        self.assertEqual(combos[3].get(), 'DeepSeek V4 Flash')

    def test_the_manager_adds_and_deletes_a_model(self):
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.pet.save_pool({'label': '本地 Llama', 'model': 'llama-3-8b',
                            'base_url': 'http://127.0.0.1:8000/v1', 'key_env': '', 'wire_api': 'chat'})
        self.assertIn('本地 Llama', self.menu_labels(self.model_menu()))
        self.pet.delete_pool_model('llama-3-8b')
        self.assertNotIn('本地 Llama', self.menu_labels(self.model_menu()))

    def test_manager_delete_uses_the_currently_selected_row_and_persists_it(self):
        """列表刷新后，删除按钮也只能删除当前高亮的模型，重读配置不得复活。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.pet.asker = lambda _title, _text: True
        self.pet.save_pool({'label': '删除目标', 'model': 'delete-target',
                            'base_url': 'http://127.0.0.1:8000/v1', 'key_env': '', 'wire_api': 'chat'})
        win._pet_reload()
        win._pet_tree.selection_set('delete-target')
        self.assertEqual(win._pet_delete_one(), 'delete-target')
        self.assertNotIn('delete-target', self.pet.agent_model_records())
        self.assertNotIn('delete-target', model_pool.pool(program=self.pet.program))

    def test_the_manager_refills_a_custom_provider_name(self):
        """自定义厂商保存后重新选中，输入框必须仍显示用户填写的名字。"""
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        self.pet.save_pool({'label': '自定义 GPT', 'model': 'custom-gpt',
                            'provider': '我的厂商', 'base_url': 'https://example.invalid/v1'})
        win._pet_reload()
        win._pet_tree.selection_set('custom-gpt')
        win._pet_tree.event_generate('<<TreeviewSelect>>')
        self.win.update_idletasks()
        self.assertEqual(win._pet_provider.get(), '我的厂商')

    def test_the_manager_stores_a_typed_key_encrypted_and_shows_only_four_characters(self):
        """规格里的第二种放法：密钥直接输进来 → 系统加密存本机，界面只露前 4 位 ＋ ****。"""
        original = model_secrets.PROTECTOR
        def protector(data, decrypt=False, label=''):
            payload = bytes(data)
            if decrypt:
                if not payload.startswith(b'test:'):
                    raise ValueError('bad test secret')
                return payload[5:][::-1]
            return b'test:' + payload[::-1]
        model_secrets.PROTECTOR = protector
        self.addCleanup(setattr, model_secrets, 'PROTECTOR', original)
        win = self.pet.open_model_manager()
        self.addCleanup(win.destroy)
        entries = win._pet_entries
        entries['label'].insert(0, '我的本地模型')
        entries['model'].insert(0, 'llama-3-8b')
        entries['base_url'].insert(0, 'http://127.0.0.1:8000/v1')
        win._pet_key_entry.insert(0, 'sk-local-abcdef')
        item = win._pet_save_key()
        self.assertIsNotNone(item, win._pet_hint.get())
        records = self.pet.agent_model_records()
        self.assertIn('llama-3-8b', records, '存密钥时顺手把这条也写进池子')
        self.assertEqual(records['llama-3-8b']['key_env'], 'MODEL_LLAMA_3_8B_KEY')
        self.assertEqual(model_pool.local_key_of(records['llama-3-8b'], self.pet.program),
                         'sk-local-abcdef')
        self.assertEqual(model_pool.status(records['llama-3-8b'], self.pet.program), (True, '可用'))
        shown = win._pet_key_state()
        self.assertIn('sk-l****', shown)
        self.assertNotIn('sk-local-abcdef', shown, '整把密钥不许摆到界面上')
        self.assertEqual(win._pet_key_entry.get(), '', '存完把输入框清掉，不回显整把密钥')
        self.assertIn('我的本地模型', self.menu_labels(self.model_menu()))
        self.assertTrue(win._pet_clear_key())
        self.assertEqual(model_pool.local_key_of(records['llama-3-8b'], self.pet.program), '')


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
        self.assertEqual(cloud.submit(), '按你这句办', '回复框里写的字就是发出去的那句')
        self.assertIn('您：按你这句办', cloud.transcript(), '说过的话要留在记录里')
        self.assertEqual(cloud.reply.get(), '', '发出去就清空，等着下一句')

    def test_an_empty_reply_box_falls_back_to_what_the_pet_asked(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.propose('查一下进度')
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
            self.assertEqual(str(style.configure('Send.TButton', 'background')), ui_theme.ACCENT)
            self.assertEqual(str(style.configure('Send.TButton', 'foreground')), 'white')
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


class DefaultLevelTests(PetTestCase):
    """第 44 期：出厂默认档＝半自动（用户附件《模型管理》关键决策第 5 条）。

    这一档「免费步骤自己跑、花钱的先问一句」，所以默认状态下三虎真的在干活；等级仍可随时
    由那排猫爪／设置页改，改完写进配置，下次开机照用户选的来。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def test_a_fresh_pet_starts_in_hint_mode(self):
        self.assertEqual(pet_agent.DEFAULT_LEVEL, 'hint')
        self.assertEqual(self.pet.agent.level, 'hint')

    def test_the_hint_level_does_not_wake_the_next_step(self):
        """第 64 期任务 7：默认档＝只提醒——只看着、不替用户推进下一步。"""
        self.assertEqual(self.pet.agent.level, 'hint')
        self.pet.machine.start('script')
        self.pet.machine.complete('script')
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, [])

    def test_the_automatic_levels_wake_the_next_step(self):
        """半自动／全自动档：下一步会被叫醒（开机第一拍只叫醒、不出声）。"""
        self.pet.agent.set_level('semi')
        self.pet.machine.start('script')
        self.pet.machine.complete('script')
        self.assertEqual(self.pet.tune_advance(at=self.now), '')
        self.assertEqual(self.fake.advances, ['script_structure'],
                         '剧本完成后先进入正式的结构剧本阶段')

    def test_the_default_level_never_runs_paid_steps(self):
        """第 64 期任务 7：默认「只提醒」档连免费步骤都不代跑，更不会自己花钱。"""
        decision = self.pet.agent.approve('video.generate')
        self.assertFalse(decision['run'], '会花钱的按钮不代按')
        self.assertFalse(decision['confirm'], '只提醒档只提示，不弹确认框')

    def test_the_chosen_level_is_what_the_next_start_uses(self):
        self.pet.set_level('hint')
        saved = pet_agent.load_settings(program=self.pet.program)
        self.assertEqual(saved['level'], 'hint', '用户选过的档盖过出厂那一档')


class DesktopPetSeamTests(unittest.TestCase):
    """第 23 期真接缝：Desktop.pet_goto（切页）与 Desktop.pet_advance（提前叫醒下一步）。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from desktop import Desktop
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.d = Desktop(self.win, root=PROGRAM)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / "p"
        (self.base / "episode").mkdir(parents=True, exist_ok=True)
        (self.base / "episode" / "assets.json").write_text("{}", encoding="utf-8")

    # ── 切页 ────────────────────────────────────────────────────────────────
    def test_it_says_nothing_without_a_project(self):
        self.assertEqual(self.d.pet_goto("edit"), "")
        self.assertEqual(self.d.pet_advance("video"), "")
        self.assertEqual(self.d.pet_goto("不存在的步骤"), "")

    def test_it_hands_the_page_index_to_show(self):
        """页序号只认 pet_state.PAGE_OF 那一份，且真的落到 show() 上。"""
        from desktop import PAGES
        import pet_state
        self.d.root = self.base
        seen = []
        self.d.show = lambda index, video_mode=None: seen.append(index) or PAGES[index]
        self.assertEqual(self.d.pet_goto("edit"), PAGES[pet_state.PAGE_OF["edit"]])
        self.assertEqual(seen, [pet_state.PAGE_OF["edit"]])

    def test_a_broken_page_is_reported_not_raised(self):
        self.d.root = self.base
        self.d.studio = object()

        def boom(index, video_mode=None):
            raise RuntimeError("页面坏了")

        self.d.show = boom
        self.assertEqual(self.d.pet_goto("edit"), "")
        self.assertIn("切页失败", self.d.status.get())

    # ── 提前叫醒下一步 ──────────────────────────────────────────────────────
    def test_it_moves_only_the_due_time(self):
        self.d.root = self.base
        self.d.auto_video_due = 0
        self.assertIn("视频生成", self.d.pet_advance("video"))
        self.assertEqual(self.d.auto_video_due, 0)
        self.d.auto_video_due = time.monotonic() + 60      # 正常节流里还没到点的那一步
        self.assertIn("视频生成", self.d.pet_advance("video"))
        self.assertEqual(self.d.auto_video_due, 0, "把这一步的下一次轮询提前到现在")

    def test_a_step_in_backoff_is_left_alone(self):
        """失败后的 5 分钟退避不能被一次推进打乱（与 kick_unattended 同一条规矩）。"""
        from desktop import UNATTENDED_BACKOFF_FLOOR
        self.d.root = self.base
        far = time.monotonic() + UNATTENDED_BACKOFF_FLOOR + 60
        self.d.auto_keyframe_due = far
        self.assertEqual(self.d.pet_advance("keyframe"), "")
        self.assertEqual(self.d.auto_keyframe_due, far)

    def test_a_busy_step_is_left_alone(self):
        self.d.root = self.base
        self.d.auto_asset_busy = True
        self.assertEqual(self.d.pet_advance("assets"), "")
        self.d.auto_asset_busy = False

    def test_a_step_without_an_unattended_poll_says_nothing(self):
        self.d.root = self.base
        self.assertEqual(self.d.pet_advance("script"), "", "剧本没有无人值守轮询")
        self.assertEqual(self.d.pet_advance("audio"), "", "配音没有无人值守轮询")

    def test_the_desktop_hands_over_the_foreground_judge(self):
        """第 30 期第 3 条：真宿主把「前台窗口是不是本进程」挂到宠物上，假宿主不挂（＝不拦）。"""
        self.assertIs(self.d.pet.front, pet_ui.our_process_in_front)

    def test_the_table_covers_exactly_the_steps_that_have_a_poll(self):
        from desktop import PET_STAGE_POLL
        import pet_bus
        for stage, name in PET_STAGE_POLL.items():
            self.assertIn(stage, pet_bus.STAGES)
            self.assertTrue(hasattr(self.d, name + "_due"), name + " 必须真的有这一步的轮询")

    # ── 自动开始某一步（第 67 期任务 5）─────────────────────────────────────
    def test_it_opens_the_unattended_switch_then_starts_the_step(self):
        import project_settings
        self.d.root = self.base
        self.d.auto_asset_due = 0
        self.assertIn("资产管理", self.d.pet_start("assets"))
        self.assertTrue(project_settings.auto_asset(self.base), "无人值守开关替用户打开")
        self.assertEqual(self.d.auto_asset_due, 0, "顺手把这一步提前叫醒一轮")

    def test_a_step_without_an_unattended_poll_starts_nothing(self):
        self.d.root = self.base
        self.assertEqual(self.d.pet_start("script"), "", "剧本没有无人值守轮询")
        self.assertEqual(self.d.pet_start("audio"), "", "配音没有无人值守轮询")

    def test_auto_structure_without_source_emits_a_failure_instead_of_sticking_active(self):
        """自动链派到结构剧本却没有原稿时，必须收场为失败而非静默卡住。"""
        self.d.root = self.base
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_script_structure_batch(trigger='auto')
        self.assertIn('未找到剧本准备阶段的剧本', text)
        self.assertEqual(emitted, [('stage.failed', {
            'stage': 'script_structure', 'error': text})])

    def test_stage_event_delivery_failure_is_not_silently_swallowed(self):
        """阶段权威通知坏了必须上抛，不能假装自动链已经收场。"""
        self.d.root = self.base

        def broken_emit(*_args, **_kwargs):
            raise RuntimeError('阶段事件总线不可用')

        self.d.pet._emit = broken_emit
        with self.assertRaisesRegex(RuntimeError, '阶段事件总线不可用'):
            self.d.pet_script_structure_batch(trigger='auto')

    def test_auto_structure_while_another_worker_is_busy_is_queued_once(self):
        """后台占用是暂态：自动链保留 active，收尾后会经 L3 重新派发。"""
        self.d.root = self.base
        self.d.worker = True
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))

        text = self.d.pet_script_structure_batch(trigger='auto')
        self.assertIn('当前后台任务完成后将自动制作结构剧本', text)
        self.assertTrue(self.d._auto_structure_retry)
        self.assertEqual(emitted, [])

    def test_auto_structure_sync_failure_stays_in_that_stage(self):
        """正稿没同步进分镜输入时，不能伪装结构阶段已完成后才让下游失败。"""
        import script_contract
        import stage_exec
        import storyboard_selection

        self.d.root = self.base
        source = self.base / 'writing' / 'script_raw.md'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('# 自然剧本', encoding='utf-8')
        output = script_contract.canonical_structured_script_path(self.base)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('# 结构化剧本', encoding='utf-8')
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        self.d.async_ = lambda work, received, **_kwargs: received(work())
        old_run, old_sync = stage_exec.run, storyboard_selection.sync_structured_script
        stage_exec.run = lambda *_args, **_kwargs: {'ok': True}
        storyboard_selection.sync_structured_script = lambda _project: []
        self.addCleanup(setattr, stage_exec, 'run', old_run)
        self.addCleanup(setattr, storyboard_selection, 'sync_structured_script', old_sync)

        self.assertIn('已自动开始', self.d.pet_script_structure_batch(trigger='auto'))
        self.assertEqual(emitted[0][0], 'stage.executing')
        self.assertEqual(emitted[1][0], 'stage.failed')
        self.assertEqual(emitted[1][1]['stage'], 'script_structure')
        self.assertIn('同步初步分镜失败', emitted[1][1]['error'])

    def test_auto_structure_bad_selection_settings_stays_in_that_stage(self):
        """损坏的分镜选择配置也必须收敛为当前阶段失败，而非漏出后台回调。"""
        import script_contract
        import stage_exec
        import storyboard_selection

        self.d.root = self.base
        source = self.base / 'writing' / 'script_raw.md'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('# 自然剧本', encoding='utf-8')
        output = script_contract.canonical_structured_script_path(self.base)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('# 结构化剧本', encoding='utf-8')
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        self.d.async_ = lambda work, received, **_kwargs: received(work())
        old_run, old_sync = stage_exec.run, storyboard_selection.sync_structured_script
        stage_exec.run = lambda *_args, **_kwargs: {'ok': True}
        storyboard_selection.sync_structured_script = lambda _project: (_ for _ in ()).throw(AttributeError('选择配置格式错误'))
        self.addCleanup(setattr, stage_exec, 'run', old_run)
        self.addCleanup(setattr, storyboard_selection, 'sync_structured_script', old_sync)

        self.d.pet_script_structure_batch(trigger='auto')
        self.assertEqual(emitted[-1][0], 'stage.failed')
        self.assertEqual(emitted[-1][1]['stage'], 'script_structure')
        self.assertIn('选择配置格式错误', emitted[-1][1]['error'])

    def test_auto_storyboard_without_input_emits_a_failure_instead_of_sticking_active(self):
        """自动链派到分镜却没有结构剧本输入时，必须收场为失败。"""
        self.d.root = self.base
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_storyboard_batch(trigger='auto')
        self.assertIn('未选择结构剧本', text)
        self.assertEqual(emitted, [('stage.failed', {
            'stage': 'storyboard', 'error': text})])

    def test_auto_storyboard_bad_selection_state_emits_a_failure(self):
        """读取已选结构剧本异常也要收场，不能把自动链留在执行中。"""
        import storyboard_selection

        self.d.root = self.base
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        old_selected = storyboard_selection.selected_many
        storyboard_selection.selected_many = lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('选择配置已损坏'))
        self.addCleanup(setattr, storyboard_selection, 'selected_many', old_selected)

        text = self.d.pet_storyboard_batch(trigger='auto')
        self.assertIn('读取结构剧本输入失败：选择配置已损坏', text)
        self.assertEqual(emitted, [('stage.failed', {
            'stage': 'storyboard', 'error': text})])

    def test_auto_storyboard_with_an_adopted_result_completes_instead_of_waiting_forever(self):
        """已生成且已采用的分镜是自动链的正常终态，不应再空转 auto_adopt。"""
        self.d.root = self.base
        script = self.base / 'writing' / '第01集.md'
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text('# 第01集', encoding='utf-8')
        board = self.base / 'storyboard' / '分镜拆分' / 'EP001_分镜.json'
        board.parent.mkdir(parents=True, exist_ok=True)
        board.write_text(json.dumps({'episode_id':'EP001','title':'测试','source_script':'writing/第01集.md',
                                     'shots':[{'id':'SH001'}]}, ensure_ascii=False), encoding='utf-8')
        (self.base / 'ui_settings.json').write_text(json.dumps({
            'storyboard_scripts':['writing/第01集.md'],
            'adopted_storyboards':['storyboard/分镜拆分/EP001_分镜.json']}, ensure_ascii=False), encoding='utf-8')
        self.d.pet.auto.active = 'storyboard'
        emitted = []
        self.d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
        text = self.d.pet_storyboard_batch(trigger='auto')
        self.assertIn('均已生成并采用', text)
        self.assertEqual(emitted, [('stage.completed', {'stage':'storyboard','text':text})])

    def test_the_switch_table_covers_exactly_the_steps_with_a_poll(self):
        from desktop import PET_STAGE_POLL, UNATTENDED_SWITCH
        import project_settings
        self.assertEqual(sorted(UNATTENDED_SWITCH), sorted(PET_STAGE_POLL.values()),
                         "每一个无人值守轮询都要配一把能打开它的开关")
        for name in UNATTENDED_SWITCH.values():
            self.assertTrue(callable(getattr(project_settings, name, None)), name + " 必须真的存在")


class PawHoverTests(PetTestCase):
    """第 23 期：鼠标扫过那排猫爪就把那一只提亮——点哪一档变得可预期。"""

    def fill_of(self, index):
        canvas = self.pet.paws
        parts = canvas.find_withtag('paw-' + pet_ui.PAW_LEVELS[index])
        self.assertTrue(parts, '这一只爪应当画出来了')
        return canvas.itemcget(parts[0], 'fill')

    def at(self, index):
        return _Point(index * (pet_ui.PAW_SIZE + pet_ui.PAW_GAP))

    def test_hovering_a_paw_brightens_it(self):
        self.pet.set_level('hint')              # 第 44 期：默认档已是半自动，先退到别的档再验悬停
        self.pet.paw_hover(self.at(1))
        self.assertEqual(self.pet._paw_hover, 1)
        self.assertEqual(self.fill_of(1), pet_ui.PAW_HOVER[0])

    def test_leaving_the_row_puts_it_back(self):
        self.pet.set_level('hint')
        self.pet.paw_hover(self.at(1))          # 第 0 只是当前档，提亮只发生在没选中的爪上
        self.assertEqual(self.fill_of(1), pet_ui.PAW_HOVER[0])
        self.pet.paw_leave()
        self.assertIsNone(self.pet._paw_hover)
        self.assertEqual(self.fill_of(1), pet_ui.PAW_IDLE[0])

    def test_the_selected_paw_keeps_its_level_colour_under_the_cursor(self):
        level = self.pet.agent.level
        index = pet_ui.PAW_LEVELS.index(level)
        self.pet.paw_hover(self.at(index))
        self.assertEqual(self.fill_of(index), pet_ui.PAW_COLORS[level][0], '当前档的颜色不被悬停盖掉')

    def test_off_the_row_is_not_a_paw(self):
        self.assertIsNone(self.pet.paw_at(10 * (pet_ui.PAW_SIZE + pet_ui.PAW_GAP)))
        self.assertIsNone(self.pet.paw_at(None))
        self.assertIsNone(self.pet.paw_hover(_Event(widget=self.pet.paws)))   # 这个替身没有 x
        self.assertIsNone(self.pet._paw_hover)

    def test_the_hover_bindings_are_wired(self):
        self.assertTrue(self.pet.paws.bind('<Motion>'), '扫过去要有反应')
        self.assertTrue(self.pet.paws.bind('<Leave>'), '扫出去要恢复')

    def test_the_click_and_the_hover_share_one_hit_test(self):
        self.pet.paw_hover(self.at(2))
        self.pet.paw_click(self.at(2))
        self.assertEqual(self.pet.agent.level, pet_ui.PAW_LEVELS[2], '扫到哪只就能点到哪只')


class CaptionPendingTests(PetTestCase):
    """第 23 期：小字带上「待确认 N」——不开窗口就知道有没有事等着自己。"""

    def test_no_pending_keeps_the_plain_level(self):
        level = self.pet.agent.level
        self.assertEqual(self.pet.caption_text(), pet_ui.LEVEL_CAPTIONS[level])

    def test_pending_items_are_counted_on_the_caption(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.agent.fail('video', '超时', attempt=4)
        self.assertIn('待确认 2', self.pet.caption_text())
        self.pet.pump()
        self.assertIn('待确认 2', self.pet.caption.cget('text'), '心跳里就该写到小字上')

    def test_a_cleared_list_takes_the_count_away(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.assertIn('待确认 1', self.pet.caption_text())
        self.pet.agent.clear_failures()
        self.assertNotIn('待确认', self.pet.caption_text())

    def test_paused_still_wins(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.agent.pause('歇会儿')
        self.assertEqual(self.pet.caption_text(), pet_ui.PAUSED_CAPTION)

    def test_wider_pending_text_folds_down_instead_of_over_the_cat(self):
        """第 23 期补：小字是从右沿往左长的——加了「待确认 N」只能往下一行折，不许压到猫脸。"""
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.draw()
        self.win.update_idletasks()
        caption = self.pet.caption
        self.assertEqual(int(caption.cget('wraplength')), pet_ui.CAPTION_ROOM, '宽度得钉死')
        self.assertLessEqual(caption.winfo_reqwidth(), pet_ui.CAPTION_ROOM, '小字最多占 CAPTION_ROOM 宽')
        self.assertIn('待确认', caption.cget('text'))

    def test_the_caption_stays_black_in_every_case(self):
        self.pet.agent.fail('keyframe', '超时', attempt=4)
        self.pet.pump()
        self.assertEqual(str(self.pet.caption.cget('foreground')), pet_ui.CAPTION_INK)


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


class PawTests(PetTestCase):
    """第 19 期：自动化等级外置成一排猫爪，点哪一爪就切到哪一档。"""

    def test_a_paw_is_a_pad_and_four_toes(self):
        parts = pet_ui.paw_parts(0, 0)
        self.assertEqual(len(parts), 5)
        self.assertTrue(all(part[0] == 'oval' for part in parts))
        self.assertGreater(parts[0][3], max(part[3] for part in parts[1:]), '掌垫比脚趾大')

    def test_the_paws_sit_below_the_patch(self):
        """第 20 期用户要的：「3 个猫爪型按钮移动到三虎下方」。"""
        info = self.pet.paws.place_info()
        self.assertEqual(float(info['relx']), 1.0)
        self.assertEqual(int(float(info['x'])), pet_ui.PAW_ROW_X)
        self.assertEqual(pet_ui.PAW_ROW_X, pet_ui.PATCH_X, '猫爪排右沿＝贴片右沿')
        self.assertEqual(int(float(info['y'])), pet_ui.PAW_Y)
        self.assertGreaterEqual(pet_ui.PAW_Y, pet_ui.SIZE + pet_ui.PAW_GAP_Y, '猫爪排在三虎下方')
        self.assertEqual(int(float(self.pet.caption.place_info()['x'])), -pet_ui.CAPTION_RIGHT)

    def test_the_paws_and_the_patch_never_overlap(self):
        """第 20 期用户报「三虎的头像被遮挡一半」「猫爪被遮挡」：两个画布的矩形不许相交。

        改之前：猫爪排的右沿只比贴片右沿往里 8 像素，而它自己还有 PAW_WIDTH 宽——整排压在
        猫脸上（挡住耳朵），猫脸下半张还被只有约 40 像素高的标题行裁掉。
        """
        patch = self.pet.canvas.place_info()
        paws = self.pet.paws.place_info()
        self.assertEqual(int(float(paws['x'])), int(float(patch['x'])), '贴片与猫爪排同一右沿')
        self.assertEqual(int(float(paws['y'])),
                         int(float(patch['y'])) + pet_ui.SIZE + pet_ui.PAW_GAP_Y,
                         '猫爪排从贴片底边再往下一条缝，矩形不相交')
        self.assertEqual(int(self.pet.canvas.cget('height')), pet_ui.SIZE)
        self.assertEqual(int(self.pet.paws.cget('height')),
                         pet_ui.PAW_SIZE + pet_ui.PAW_ARC, '弯弧也要占画布高度')
        caption = int(float(self.pet.caption.place_info()['x']))
        self.assertGreater(caption, int(float(patch['x'])),
                           '等级小字落在贴片右边（第 21 期），不再占左边那一格')
        # 标题行：按贴片＋猫爪的总高度定死，不再由两个标签撑到约 40 像素（那会把猫脸裁掉一半）
        row = self.fake.title_row
        self.assertEqual(int(row.cget('height')), pet_ui.PATCH_ROOM)
        self.assertFalse(bool(row.pack_propagate()), '标题行不再随标签收缩')
        self.assertGreaterEqual(pet_ui.PATCH_ROOM, pet_ui.SIZE + pet_ui.PAW_SIZE, '贴片＋猫爪都要装得下')

    def test_the_selected_paw_is_filled_with_the_level_colour(self):
        self.pet.draw_paws('auto', force=True)
        self.assertEqual(len(self.pet.paws.find_withtag('paw')), 5 * len(pet_ui.PAW_LEVELS))
        marked = self.pet.paws.find_withtag('paw-auto')
        self.assertTrue(marked, '当前档那只爪要认得出来')
        self.assertEqual(self.pet.paws.itemcget(marked[0], 'fill'), pet_ui.PAW_COLORS['auto'][0])

    def test_switching_the_level_repaints_the_paws(self):
        self.pet.set_level('hint')
        chosen = self.pet.paws.find_withtag('paw-hint')
        self.assertEqual(self.pet.paws.itemcget(chosen[0], 'fill'), pet_ui.PAW_COLORS['hint'][0])
        other = self.pet.paws.find_withtag('paw-auto')
        self.assertEqual(self.pet.paws.itemcget(other[0], 'fill'), pet_ui.PAW_IDLE[0],
                         '没选中的爪是淡灰，旧档的填色要一起换掉')

    def test_the_paws_are_strung_along_a_downward_arc(self):
        """第 36 期第 9 条：三只爪按向下的弧形摆放（中间那只最低，两边各抬）。"""
        self.assertGreater(pet_ui.PAW_ARC, 0)
        self.assertEqual([pet_ui.paw_dy(index) for index in range(3)],
                         [0, pet_ui.PAW_ARC, 0], '中间那只最低')
        self.assertEqual(pet_ui.paw_dy(9), 0, '越界不挪')
        self.assertEqual(pet_ui.paw_dy('不是个号'), 0)
        self.pet.draw_paws('auto', force=True)
        boxes = [self.pet.paws.bbox(item) for item in self.pet.paws.find_withtag('paw')]
        step = pet_ui.PAW_SIZE + pet_ui.PAW_GAP

        def lowest(index):
            left = index * step
            return max(box[3] for box in boxes
                       if left <= (box[0] + box[2]) / 2.0 < left + pet_ui.PAW_SIZE)

        self.assertGreater(lowest(1), lowest(0), '中间那只落得比左边低')
        self.assertGreater(lowest(1), lowest(2), '中间那只落得比右边低')

    def test_the_click_picks_the_paw_under_the_cursor(self):
        step = pet_ui.PAW_SIZE + pet_ui.PAW_GAP
        self.pet.paw_click(_Point(2 * step))
        self.assertEqual(self.pet.agent.level, pet_ui.PAW_LEVELS[2])
        self.pet.paw_click(_Point(0))
        self.assertEqual(self.pet.agent.level, pet_ui.PAW_LEVELS[0])
        self.assertIsNone(self.pet.paw_click(_Point(9 * step)), '超出范围的点击不认领')


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
        self.pet.gaps = lambda at=None, force=False: ['首帧还差 36 个镜头（06 首帧管理 → 手动制作首帧）']
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


class PuffTailTests(unittest.TestCase):
    """第 25 期第 2 条：可爱话那一档的尾巴从右下角挑出来，根要落在框身里（不然接缝会露出来）。

    第 57 期第 1 条：外形统一成方框之后，「根落在里面」的判据照旧，只是框身换成了方框。
    """

    def test_the_tail_root_sits_inside_the_puff_body(self):
        for width, height in ((300, 150), (300, 216), (240, 132)):
            with self.subTest(size=(width, height)):
                x, y = pet_cloud.shape_root(pet_cloud.SHAPE_PUFF, width, height)
                self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_PUFF, width, height, x, y),
                                '尾巴根露在云身外头了：接缝会被看见')
                self.assertGreater(x, width * 0.55, '根落在靠右那半边')
                self.assertGreater(y, height * 0.55, '根落在靠下那半边')

    def test_the_other_shapes_keep_their_own_root(self):
        for shape in (pet_cloud.SHAPE_CLOUD, pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND, pet_cloud.SHAPE_TAG):
            with self.subTest(shape=shape):
                width = pet_cloud.shape_width(shape)
                height = pet_cloud.shape_min_body(shape)
                x, _y = pet_cloud.shape_root(shape, width, height)
                self.assertGreater(x, width / 2.0)


class RingTests(PetTestCase):
    """第 21 期：用户要的「删除三虎头像背后的弧线」。"""

    def test_no_arc_stands_behind_the_cat(self):
        canvas = self.pet.canvas
        for pose in pet_ui.POSES:
            with self.subTest(pose=pose):
                self.pet.cat.pose = pose
                self.pet.draw(0)
                self.assertEqual(canvas.find_withtag('ring'), (), '脸上不再挂那条进度弧线')

    def test_paint_ignores_the_percent_instead_of_drawing_a_ring(self):
        canvas = self.pet.canvas
        for percent in (0.0, 25.0, 100.0):
            with self.subTest(percent=percent):
                pet_ui.paint(canvas, step=0, percent=percent)
                self.assertEqual(canvas.find_withtag('ring'), ())
        self.assertTrue(canvas.find_withtag('fur'), '猫还在')


class AnchorTests(PetTestCase):
    """第 21 期：云朵框往下挪一条尾巴带，底部对齐左侧那行标题文字（＝贴片下沿）。"""

    def test_the_body_bottom_lands_on_the_patch_bottom(self):
        cloud = self.pet.cloud()
        # 贴片摆在界面右上角（真实位置）：第 24 期起云身落点还要过一道「不许压住三虎」的闸，
        # 摆在屏幕正中的假贴片会被那道闸挪走，量到的就不是对齐关系了。
        cloud._patch_rect = lambda: (1200.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._work_right = lambda: 1920
        self.assertEqual(pet_cloud.ANCHOR_DROP, pet_cloud.TAIL, '下移的就是那一条尾巴带')
        self.assertEqual(cloud._bottom(), 200.0 + pet_ui.SIZE + pet_cloud.ANCHOR_DROP)
        cloud._render()
        _left, top = cloud._origin()
        self.assertEqual(top + cloud._body, 200.0 + pet_ui.SIZE,
                         '云身下沿落在贴片下沿上——比原来低了一条尾巴带（用户要的「还要往下移」）')


class GrowTests(PetTestCase):
    """第 19 期：圆气泡从三虎耳朵那头一档一档长出来，不重叠、字不会被盖。"""

    def test_the_grow_starts_near_the_ear_and_lands_on_target(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        seen = []
        cloud.win.geometry = lambda geo: seen.append(geo)
        final = (400, 300)
        cloud._grow_to(final, pet_cloud.GROW_STEPS[0])
        cloud._grow_to(final, 1.0)

        def point(geo):
            parts = geo.lstrip('+').split('+')
            return int(parts[0]), int(parts[1])

        first, last = point(seen[0]), point(seen[-1])
        self.assertEqual(last, final, '走到最后一拍就是该在的地方')
        ear_x, ear_y = cloud._ear()
        self.assertLess(abs(first[0] - ear_x), abs(last[0] - ear_x), '起步时更靠近耳朵')
        self.assertLess(abs(first[1] - ear_y), abs(last[1] - ear_y))

    def test_the_label_is_placed_only_after_the_grow(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        place = []
        cloud._place_label = lambda: place.append(1)
        cloud._grow_to((10, 10), 1.0)
        self.assertEqual(place, [], '长的那几拍先不摆字')


class RoundBubbleTests(PetTestCase):
    """第 21 期：圆气泡瘦身——只带最近一条、不编号，字落在圆的内接方框里居中。"""

    def round_cloud(self, text, long=True):
        cloud = self.pet.cloud()
        cloud.long = long
        cloud.append(text)
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        return cloud

    def test_only_the_newest_line_shows(self):
        cloud = self.round_cloud('三虎：第一句')
        cloud.append('三虎：第二句')
        body = cloud._body_text()
        self.assertIn('第二句', body)
        self.assertNotIn('第一句', body, '圆里只留最近那一条，不再把前几条一起搬进来')

    def test_the_round_bubble_numbers_its_line_too(self):
        cloud = self.round_cloud('进度：剧本准备 20%')
        self.assertIn('剧本准备 20%', cloud._body_text())
        self.assertRegex(cloud._body_text(), r'^\d+\.\s', '第 22 期起贴纸也编号')

    def test_the_number_keeps_its_sentence_on_the_first_line(self):
        """第 24 期第 7 条：窄框里编号要和正文挤在同一行——原来用普通空格，头一行只剩一个编号。"""
        cloud = self.round_cloud('我把镜头号重排了一遍，你瞅瞅？')
        wrap = int(float(cloud.label.cget('wraplength')))
        self.assertGreater(wrap, 0, '圆里的字也得有个换行宽度')
        text = cloud._body_text()
        font = cloud.label.cget('font')
        # 第 27 期第 3 条把椭圆加宽之后，这句话在原来的宽度下一行就放得下，两种空格
        # 看不出差别了；把换行宽度收到「编号＋头半句刚好放得下」那一档，NBSP 的作用照样验得出来。
        wrap = min(wrap, 140)
        tight = self.tk.Label(self.win, text=text, wraplength=wrap,
                              justify='left', anchor='nw', font=font)
        loose = self.tk.Label(self.win, text=text.replace(pet_cloud.NUMBER_GAP, ' '), wraplength=wrap,
                              justify='left', anchor='nw', font=font)
        self.addCleanup(tight.destroy)
        self.addCleanup(loose.destroy)
        self.win.update_idletasks()
        self.assertLess(tight.winfo_reqheight(), loose.winfo_reqheight(),
                        '编号那行要真的带上正文，不能只剩一个编号')

    def test_the_text_box_is_inscribed_in_the_circle_and_centred(self):
        cloud = self.round_cloud('进度：剧本准备 20%')
        width, height = cloud.width(), cloud._body
        x, y, w, h = pet_cloud.text_box(pet_cloud.SHAPE_ROUND, width, height)
        self.assertAlmostEqual(x + w / 2.0, width / 2.0, delta=2, msg='框在圆里横向居中')
        self.assertAlmostEqual(y + h / 2.0, height / 2.0, delta=2, msg='纵向也居中')
        for cx, cy in ((x, y), (x + w, y + h), (x, y + h), (x + w, y)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_ROUND, width, height, cx, cy),
                            '四角都在圆里（字不压弧线）: (%.1f, %.1f)' % (cx, cy))
        self.assertGreaterEqual(w, 100, '框太小就写不下字')

    def test_the_progress_text_is_a_few_short_lines(self):
        text = self.pet.progress_text()
        lines = [line for line in text.split('\n') if line.strip()]
        self.assertLessEqual(len(lines), pet_ui.PROGRESS_GAPS + 3, '圆里就写几行，明细留给状态栏')
        self.assertNotIn('\n\n', text, '不留空行：圆里地方小')

    def test_the_bubble_grows_only_as_far_as_the_text_needs(self):
        small = self.round_cloud('进度：20%')
        floor = small._body
        big = self.round_cloud('进度：剧本准备 20%\n预计剩余 12 分钟\n'
                               '首帧还差 36 个镜头（06 首帧管理 → 手动制作首帧）')
        self.assertGreaterEqual(big._body, floor, '字多就大一点')
        self.assertLessEqual(big._body, pet_cloud.MAX_BODY, '再长也不许撑破上限')

    def test_the_shapes_are_smaller_than_they_were(self):
        self.assertLess(pet_cloud.WIDTH, 420)
        self.assertLess(pet_cloud.MAX_BODY, 300)
        # 第 27 期第 3 条：椭圆气泡按 ROUND_WIDTH 定宽（比原来那个方框宽一截），
        # 高度还是瘦身之后那一档。
        self.assertEqual(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_ROUND], pet_cloud.ROUND_WIDTH)
        self.assertGreater(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_ROUND],
                           pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_ROUND], '宽要真的比高大，才像椭圆')
        self.assertLessEqual(pet_cloud.SHAPE_MIN_BODY[pet_cloud.SHAPE_ROUND], 200)
        # 第 28 期第 1 条：字号提到 15 号之后，云朵框跟着加宽到 400（仍然只是个说话的气泡，不过度）
        self.assertLessEqual(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF], 420)

    def test_the_frame_is_wide_enough_for_a_longer_line(self):
        """第 57 期第 1 条：方框的写字框占满框身大半，同一行多放得下几个字。"""
        cloud = self.round_cloud('进度：剧本准备 20%')
        x, y, w, h = pet_cloud.text_box(pet_cloud.SHAPE_ROUND, cloud.width(), cloud._body)
        self.assertGreaterEqual(w, 190, '比原来那个正方形（约 112 宽）宽出一大截')
        self.assertGreaterEqual(w, 0.85 * cloud.width(), '写字框占满框身')
        for cx, cy in ((x, y), (x + w, y + h), (x, y + h), (x + w, y)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_ROUND, cloud.width(), cloud._body, cx, cy),
                            '四角还是落在框身里: (%.1f, %.1f)' % (cx, cy))


class StickerFitTests(PetTestCase):
    """第 21 期：贴纸要装得下那几个字——写字框装不下的高度，形状就得跟着长大。

    原来只按「字高＋内边距」定云身高度，而心／标签的写字框是按比例内缩出来的（只有云身的
    四成上下），字比那个框高时就直接顶到形状外面去了（开机那句话当初就是这么挤出框外的）。
    """

    def framed(self, shape_hint=None):
        cloud = self.pet.cloud()
        cloud._bottom = lambda: 600.0                 # 钉住落点：别让「上方还剩多少」影响云身高度
        cloud._screen_height = lambda: 1080
        return cloud

    def test_the_puff_grows_to_hold_the_greeting(self):
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        x, y, w, h = cloud._text_box()
        self.assertGreaterEqual(h, cloud._content_height(), '云朵框的写字框要装得下这一句话')
        for cx, cy in ((x + 4, y + 4), (x + w - 4, y + 4), (x + 4, y + h - 4), (x + w - 4, y + h - 4)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_PUFF, cloud.width(), cloud._body, cx, cy),
                            '写字框要在云身里：角 (%.1f, %.1f)' % (cx, cy))

    def test_the_puff_text_box_fills_the_bubble(self):
        """第 25 期第 5 条：打招呼那几句话要写满到框边——写字框太窄就会一行两三个字地往下掉。"""
        cloud = self.framed()
        cloud.greet()
        x, y, w, h = cloud._text_box()
        self.assertGreaterEqual(w, 160, '写字框太窄了：%.0f 像素' % w)
        self.assertGreaterEqual(w, 0.55 * cloud.width(), '宽度要占云身大半')
        self.assertGreaterEqual(x, 0, '框要落在云身里')
        self.assertLessEqual(x + w, cloud.width())

    def test_the_tag_holds_its_sentence_as_well(self):
        cloud = self.framed()
        cloud.banner('三虎：今日日报已备好——36 个镜头、12 张首帧入账。明天见，台账我都记着呢。')
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_TAG)
        x, y, w, h = cloud._text_box()
        self.assertGreaterEqual(h, cloud._content_height(), '标签框要装得下这一句')
        self.assertGreaterEqual(w, 120, '框太窄就一句一断，读起来费劲')
        for cx, cy in ((x + 4, y + 4), (x + w - 4, y + h - 4)):
            self.assertTrue(pet_cloud.inside_shape(pet_cloud.SHAPE_TAG, cloud.width(), cloud._body, cx, cy))

    def test_the_greeting_sticker_has_no_number(self):
        """第 26 期第 6 条：打招呼与随口一句的可爱话不带排序数字（原来贴纸也编号）。"""
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud._body_text(), pet_cloud.GREETING, '招呼就是那一句话，前面不挂编号')
        self.assertNotIn(pet_cloud.NUMBER_GAP, cloud._body_text())
        cloud.whisper('三虎：尾巴甩一甩，等你下一条指令。')
        self.assertEqual(cloud._body_text(), '三虎：尾巴甩一甩，等你下一条指令。')

    def test_the_progress_bubble_numbers_every_line(self):
        """第 26 期第 4 条：提示框一段有好几行，每一行都得带号（原来只有头一行带）。"""
        cloud = self.framed()
        cloud.progress('进度：脚本准备 20%\n预计剩余 12 分钟\n首帧还差 36 个镜头')
        rows = cloud._body_text().split('\n')
        self.assertEqual(len(rows), 3)
        for index, row in enumerate(rows, start=1):
            self.assertTrue(row.startswith('%d.%s' % (index, pet_cloud.NUMBER_GAP)),
                            '第 %d 行没带号：%r' % (index, row))

    def test_the_text_is_a_little_smaller_but_still_readable(self):
        """第 49 期第 3 条：用户要「聊天框文字适当缩小」——正文 13 号（比第 28 期的 15 号小一档，
        仍比最初那版 11 号大），贴纸从 13 号试起、6 号兜底。"""
        from ui_tokens import FONTS
        self.assertEqual(pet_cloud.FONT, FONTS['body'])
        self.assertEqual(int(pet_cloud.STICKER_FONTS[0]), 13, '贴纸也从 13 号试起')
        self.assertEqual(int(pet_cloud.STICKER_FONTS[-1]), 6, '兜底那一档留着，不然话会被裁掉')
        self.assertLess(int(pet_cloud.STICKER_FONTS[-1]), int(pet_cloud.STICKER_FONTS[0]),
                        '仍然是从大到小一档一档试下去')
        cloud = self.framed()
        cloud.greet()   # 先把窗搭起来，确认行才在
        self.assertFalse(hasattr(cloud, 'entry'),
                         '第 29 期第 5 条：输入框整个拿掉，字号这条只剩正文与贴纸要看')

    def test_the_greeting_keeps_the_biggest_font(self):
        """第 28 期第 1 条：打招呼那句话不该被收到小号字——云朵框加宽到 400 之后，最大那档字号下三行正好装得下。"""
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        size = int(str(cloud.label.cget('font')).split()[-1])
        self.assertEqual(size, int(pet_cloud.STICKER_FONTS[0]),
                         '呼吸框里的话要用最大那档字号：%s' % str(cloud.label.cget('font')))
        self.assertLessEqual(cloud._content_height(), cloud._room(), '支撑在框里，不许裁字')
        self.assertGreaterEqual(pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF], 400,
                                '框窄了这句话就要收到 13 号（用户就是这么看不清的）')

    def test_a_sticker_shrinks_its_font_when_the_room_is_short(self):
        """第 26 期第 7 条：云身长不高时把字号收一档，别让话说到一半被裁掉。"""
        cloud = self.pet.cloud()
        cloud._bottom = lambda: 210.0          # 三虎上方只剩这么高，云身顶到上限
        cloud._screen_height = lambda: 1080
        cloud.whisper('三虎：' + '这句可爱话挺长的，要看看云朵框装不装得下这么多字。' * 3)
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        self.assertLessEqual(cloud._content_height(), cloud._room(),
                             '正文要完整待在框里：%d > %d' % (cloud._content_height(), cloud._room()))

    @staticmethod
    def hugged(cloud):
        """第 58 期第 5 条：框身该有的高度＝max(最小高度, 内容 ＋ 内边距 ＋ 顶上那条「关闭」 ＋ 余量)。"""
        return max(pet_cloud.shape_min_body(cloud.shape),
                   cloud._content_height() + 2 * pet_cloud.PAD + cloud._close_strip() + 8)

    def test_the_greeting_bubble_hugs_the_two_lines(self):
        """第 58 期第 5 条：开机招呼那朵框按内容定高（用户报的「没有根据内容自动调整框的大小」）。

        原来量到的是 374×230、里面只写两行字——底数还留着「一圈鼓包／椭圆」时代那几档
        （PUFF 200／ROUND 188／TAG 110），第 57 期外形统一成方框之后它们就只是白留一片空白。
        """
        cloud = self.framed()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF)
        self.assertEqual(cloud._body, self.hugged(cloud), '框身贴着这一句话长')
        self.assertLess(cloud._body, 200, '不再是原来那档 200 的底数')
        self.assertGreaterEqual(cloud._room(), cloud._content_height(),
                                '顶上那条「关闭」也算进去了，正文完整待在框里')
        self.assertEqual(int(cloud.canvas.cget('height')), cloud._body + pet_cloud.TAIL,
                         '浮窗跟着框身一起收')
        self.assertLess(cloud.width(), pet_cloud.SHAPE_WIDTH[pet_cloud.SHAPE_PUFF],
                        '宽度也照着这句话收，不再拉满')

    def test_the_other_stickers_hug_their_line_too(self):
        """第 58 期第 5 条：可爱话／提示／标签三档贴纸同样按内容定高，不留一大片空白。

        这一条与上面那条分工不同：上面盯的是招呼那句（内容短、正好被底数压住），这里盯的是
        「内容比最小高度还高」的时候——框身必须就停在「内容 ＋ 内边距 ＋ 顶上那条关闭」上，
        不能再多留一截空白（原来 PUFF 200／ROUND 188／TAG 110 三档底数就是这么白的）。
        """
        said = '进度：剧本准备 20%，预计剩余 12 分钟，首帧还差 36 个镜头（06 首帧管理 → 手动制作首帧）。'
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND, pet_cloud.SHAPE_TAG):
            with self.subTest(shape=shape):
                cloud = self.framed()
                cloud.append(said)
                cloud.show(pinned=False, shape=shape)
                self.assertEqual(cloud.shape, shape)
                self.assertEqual(cloud._body, self.hugged(cloud), '框身＝这一条内容的高度')
                self.assertLessEqual(cloud._body,
                                     cloud._content_height() + 2 * pet_cloud.PAD + cloud._close_strip() + 8,
                                     '比内容高的那一截只能是内边距与「关闭」那一条')
                self.assertGreaterEqual(cloud._room(), cloud._content_height(), '正文不裁')


class BubbleColorTests(PetTestCase):
    """第 26 期第 5 条：云朵框红、提示框蓝、对话框绿——三种框按用途分色。"""

    @staticmethod
    def channel(color):
        return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))

    def test_the_cloud_is_red(self):
        red, green, blue = self.channel(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_PUFF][1])
        self.assertGreater(red, green, '云朵框要偏红')
        self.assertGreater(red, blue)

    def test_the_progress_bubble_is_blue(self):
        red, green, blue = self.channel(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_ROUND][1])
        self.assertGreater(blue, red, '提示框要偏蓝')
        self.assertGreater(blue, green)

    def test_the_chat_box_is_green(self):
        red, green, blue = self.channel(pet_cloud.SHAPE_COLORS[pet_cloud.SHAPE_CLOUD][1])
        self.assertGreater(green, red, '对话框要偏绿')
        self.assertGreater(green, blue)

    def test_confirming_asks_in_the_green_chat_box(self):
        self.pet.confirm('要按一次 Seedream 首帧吗？')
        cloud = self.pet.cloud()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD)
        self.assertIn('要按一次 Seedream 首帧吗', cloud.transcript())


class PanelTextTests(PetTestCase):
    """第 26 期第 4 条：进度面板按节排版、逐行编号。"""

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now

    def test_the_panel_opens_with_the_progress_title(self):
        """第 36 期第 10 条：面板正文开头就是「当前进度：」。"""
        text = self.pet.panel_text()
        self.assertTrue(text.startswith(pet_ui.PANEL_HEAD), text[:40])
        self.assertEqual(pet_ui.PANEL_HEAD, '当前进度：')

    def test_the_panel_is_split_into_sections(self):
        text = self.pet.panel_text()
        self.assertIn('【现在在做什么】', text)
        self.assertIn('【速度与命中】', text)
        self.assertIn('【配额与设置】', text)
        self.assertNotIn('\n\n', text, '不空行：一节里一条一行')

    def test_the_panel_fallback_bubble_keeps_its_own_numbering(self):
        """没有只读文本窗时进度面板退回圆气泡：那份正文自带节名与编号，不许再套一层。"""
        cloud = self.pet.cloud()
        text = self.pet.panel_text()
        cloud.progress(text)
        self.assertEqual(cloud._body_text(), text)
        plain = self.pet.cloud()
        plain.progress('1. 正在做：第 05 步首帧')
        self.assertIn(pet_cloud.NUMBER_GAP, plain._body_text())

    def test_every_panel_row_is_numbered_and_keeps_its_value(self):
        rows = dict(self.pet.rows())
        text = self.pet.panel_text()
        lines = [line for line in text.split('\n') if line[:1].isdigit()]
        self.assertEqual(len(lines), len(rows), '面板每一条都在，且各占一行')
        for index, line in enumerate(lines, start=1):
            self.assertTrue(line.startswith('%d.%s' % (index, pet_cloud.NUMBER_GAP)), line)
        for name, value in rows.items():
            self.assertIn('%s%s%s' % (name, pet_ui.PANEL_DIVIDER, value), text,
                          '「%s」那一行的值不许丢' % name)


class _PatchCanvas:
    """贴片替身：只带那一把几何接口，坐标想怎么报就怎么报。"""

    def __init__(self, left=1076, top=191, width=64, height=64, mapped=1):
        self.geometry = {'left': left, 'top': top, 'width': width, 'height': height, 'mapped': mapped}

    def winfo_width(self):
        return self.geometry['width']

    def winfo_height(self):
        return self.geometry['height']

    def winfo_rootx(self):
        return self.geometry['left']

    def winfo_rooty(self):
        return self.geometry['top']

    def winfo_ismapped(self):
        return self.geometry['mapped']

    def cget(self, name):
        # 真 Tk 里贴片还没映射出来时 winfo_width 报 0／1，cget('width') 仍是配好的那个寄寸
        return pet_cloud.PET_SIZE if name in ('width', 'height') else 0

    def bind(self, *args, **kwargs):
        return None


class PatchRectTrustTests(PetTestCase):
    """第 49 期第 1 条：主窗口最小化／收起那一拍量出来的贴片坐标是假的，不许拿它算落点。"""

    def cloud_with(self, **geometry):
        self.pet.canvas = _PatchCanvas(**geometry)
        return self.pet.cloud()

    def test_a_good_reading_is_kept(self):
        cloud = self.cloud_with()
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0))

    def test_an_unmapped_patch_falls_back_to_the_last_good_reading(self):
        cloud = self.cloud_with()
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0))
        self.pet.canvas.geometry.update({'left': 768, 'top': 1004, 'mapped': 0})   # 最小化那一拍
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0),
                         '贴片没映射：这一次的量值一个字节都不许用')

    def test_a_patch_with_no_size_is_not_trusted(self):
        """贴片报 0×0：退回配置的那个尺寸，绝不拿 0 去算落点。"""
        cloud = self.cloud_with(width=0, height=0)
        self.assertEqual(cloud._patch_rect(),
                         (1076.0, 191.0, float(pet_cloud.PET_SIZE), float(pet_cloud.PET_SIZE)),
                         '量成 0 的贴片不能当真：用配好的那个寄寸')

    def test_a_one_pixel_patch_is_not_trusted(self):
        """真机上没映射的贴片报 1×1（实测）：这种量值也不许拿去算落点。"""
        cloud = self.cloud_with()
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0))
        self.pet.canvas.geometry.update({'width': 1, 'height': 1})
        self.assertEqual(cloud._patch_rect(), (1076.0, 191.0, 64.0, 64.0),
                         '量成 1 像素的贴片不能当真，还用上一次量准的')

    def test_a_configure_while_minimised_leaves_the_cloud_where_it_was(self):
        cloud = self.cloud_with()
        cloud.show(pinned=False)
        spot = cloud._origin()
        self.pet.canvas.geometry.update({'left': 768, 'top': 1004, 'mapped': 0})
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertEqual(cloud._origin(), spot, '最小化那一拍不许挪窝：一挪就是「从右边跳到左边」')



class SingleDialogTests(PetTestCase):
    """第 21 期：用户要的「每次三虎只能启动一个聊天框」——同一时刻只留一个框。"""

    def test_the_progress_bubble_waits_until_the_chat_closes(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        self.assertTrue(self.pet.cloud_visible(), '云朵框正开着')
        self.assertFalse(self.pet.cloud_visible(sticker_only=True),
                         '云朵这一形态不算贴纸——只按贴纸判就会漏掉这一类，又冒一个框出来')
        self.assertEqual(self.pet.progress_voice(force=True), '', '已经有一个框了，就不再冒新的')
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_CLOUD, '还是那一个框，没被顶掉')
        cloud.close()
        self.assertFalse(self.pet.cloud_visible())

    def test_opening_the_chat_twice_keeps_the_same_window(self):
        cloud = self.pet.cloud()
        self.assertIs(cloud, self.pet.cloud(), '云朵框只建一次')
        self.pet.open_chat()
        self.assertIs(self.pet.chat, cloud)
        self.pet.open_chat()
        self.assertIs(self.pet.chat, cloud, '再打开还是同一朵云，不会冒出第二个框')


class FollowTests(PetTestCase):
    """第 21 期：助手界面一动（挪位、缩放），云朵框跟着重新摆位。"""

    def test_the_patch_and_the_paws_are_watched(self):
        watched = self.pet.cloud()._watchers()
        self.assertIn(self.pet.canvas, watched, '三虎动了云就要跟着动')
        self.assertIn(self.pet.paws, watched)

    def test_a_configure_of_the_patch_moves_the_cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        moved = []
        cloud._place_window = lambda: moved.append('moved') or (0, 0)
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertEqual(moved, ['moved'], '贴片自己动一下也要重摆')
        cloud.follow(_Event(widget=self.fake.header_status))
        self.assertEqual(moved, ['moved'], '别的控件冒泡上来的不认领')

    def test_nothing_is_moved_while_the_cloud_is_hidden(self):
        cloud = self.pet.cloud()
        moved = []
        cloud._place_window = lambda: moved.append('moved') or (0, 0)
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertEqual(moved, [], '收着的时候不用摆')

    def test_the_drawn_tail_follows_the_pet_when_the_ui_shrinks(self):
        """第 25 期第 7 条：界面一缩（贴片跟着挪），尾巴要当场重画着指回三虎。

        只把浮窗挪个位置是不够的——那根尖角画在画布上，不重画就停在旧坐标上了。
        所以这里量的是**画布上真画出来的那个尖角**（最后一个多边形图元），不是算式里的 _tip()。
        """
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        spot = [1200.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE)]
        cloud._patch_rect = lambda: tuple(spot)
        cloud._work_right = lambda: 1920
        cloud._screen_height = lambda: 1080
        cloud._bottom = lambda: spot[1] + spot[3] + pet_cloud.ANCHOR_DROP

        def drawn_tip():
            coords = cloud.canvas.coords(cloud.canvas.find_withtag('cloud')[-1])
            return list(zip(coords[0::2], coords[1::2]))

        def tip_offset():
            cheek = cloud._cheek()
            left, top = cloud._origin()
            points = drawn_tip()
            return min(((x + left - cheek[0]) ** 2 + (y + top - cheek[1]) ** 2) ** 0.5
                       for x, y in points)

        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertLess(tip_offset(), 2.0, '尾巴要指在脸颊上')
        spot[0], spot[1] = 640.0, 320.0                  # 主界面缩小／贴片挪位
        cloud.follow(_Event(widget=self.pet.canvas))
        self.assertLess(tip_offset(), 2.0, '界面一动，画出来的尾巴就要当场跟上')


class ViewportTests(PetTestCase):
    """第 22 期第 5b 条：文字外面套一层取景框——记录再长也滚不到输入行与「发送」上面。"""

    def cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.canvas.update_idletasks()
        return cloud

    def fill(self, cloud, count=14):
        for index in range(count):
            cloud.append('三虎：第 %d 条记录，用来把这一朵云撑得比取景框还高。' % index)
        cloud.canvas.update_idletasks()
        return cloud

    def test_the_label_hangs_inside_a_viewport(self):
        cloud = self.cloud()
        self.assertIsNotNone(cloud.clip, '文字外面要有取景框')
        self.assertEqual(str(cloud.label.winfo_parent()), str(cloud.clip), '标签得挂在框里才裁得住')

    def test_the_viewport_stops_above_the_input_row(self):
        cloud = self.fill(self.cloud())
        room = float(cloud.clip.winfo_height())
        self.assertGreater(room, 20, '取景框要有真实高度，这条才盯得住')
        top = float(cloud.clip.place_info()['y'])
        row_y = float(cloud.chat_row.place_info()['y'])
        self.assertLessEqual(top + room, row_y, '取景框下沿不能压到输入行')

    def test_a_long_record_scrolls_instead_of_overflowing(self):
        cloud = self.fill(self.cloud())
        limit = cloud._scroll_limit()
        self.assertGreater(limit, 0, '记录比取景框高就该能滚')
        cloud.scroll_by(10 ** 6)
        self.assertEqual(cloud._scroll, limit)
        self.assertEqual(float(cloud.label.place_info()['y']), float(-limit), '滚到底＝整条标签往上挪出框')


class InsideWindowTests(PetTestCase):
    """第 22 期第 9 条：整朵云在屏幕外摆不下时，自动挪进助手界面里。"""

    def cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        cloud._window_rect = lambda: (100, 100, 900, 700)      # 助手界面在屏幕上的位置（固定，不随本机变）
        cloud._work_right = lambda: 1920
        cloud._screen_height = lambda: 1080
        return cloud

    def test_a_cloud_that_fits_is_left_alone(self):
        cloud = self.cloud()
        self.assertIsNone(cloud._inside_window(200, 200), '摆得下就照原来的落点，界面上看不出变化')

    def test_a_cloud_past_the_right_edge_is_pulled_back(self):
        cloud = self.cloud()
        spot = cloud._inside_window(1900, 200)
        self.assertIsNotNone(spot, '顶出屏幕右边就该挪回界面里')
        self.assertLessEqual(spot[0] + cloud.total_width(), 1920)
        self.assertGreaterEqual(spot[0], 0)

    def test_a_cloud_above_the_screen_comes_down(self):
        cloud = self.cloud()
        spot = cloud._inside_window(200, -40)
        self.assertIsNotNone(spot, '顶出屏幕上边就该挪回界面里')
        self.assertGreaterEqual(spot[1], 0)


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


class FadeAndReadTests(PetTestCase):
    """第 24 期第 8 条：四种对话框都留够读完的时间，然后延时淡出去。"""

    def test_every_shape_fades_out_instead_of_vanishing(self):
        cloud = self.pet.cloud()
        for shape in pet_cloud.SHAPES:
            with self.subTest(shape=shape):
                cloud.show(pinned=False, hold=1, shape=shape)
                cloud.close()
                self.assertFalse(cloud.visible, shape)
                self.assertIsNotNone(cloud._fade, shape + '：收场该有一段渐隐')
                self.assertLess(float(cloud.win.attributes('-alpha')), pet_cloud.ALPHA)

    def test_the_fade_out_walks_all_the_way_to_hidden(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, hold=1)
        queued = []
        original = cloud.win.after          # 浮窗是自己一个 Toplevel，定时器排在它身上
        cloud.win.after = lambda ms, fn=None, *a: queued.append(fn) or 'job'
        self.addCleanup(setattr, cloud.win, 'after', original)
        cloud.close()
        self.assertTrue(queued, '渐隐要一档一档排下去')
        for _tick in range(len(pet_cloud.FADE_OUT_STEPS) + 2):
            if not queued:
                break
            queued.pop(0)()                   # 走一档：下一档又排进 queued 里
        self.assertIsNone(cloud._fade, '走到最后一档要收干净，别留定时器')
        self.assertFalse(cloud.visible)

    def test_a_longer_line_stays_longer(self):
        cloud = self.pet.cloud()
        short = cloud.read_hold('三虎：好。')
        long = cloud.read_hold('三虎：' + '这句话很长，' * 40)
        self.assertEqual(short, pet_cloud.HOLD_MS, '短句子有底线保底')
        self.assertGreater(long, short, '话越长停得越久')
        self.assertLessEqual(long, pet_cloud.READ_MAX_MS, '再长也不超过上限')

    def test_the_armed_hold_matches_the_reading_time(self):
        cloud = self.pet.cloud()
        text = '三虎：' + '把今天该做的都做完了，镜头、首帧、资产一项都不缺。' * 3
        seen = []
        original = self.win.after
        self.win.after = lambda ms, fn=None, *a: seen.append((ms, fn)) or 'job'
        self.addCleanup(setattr, self.win, 'after', original)
        cloud.broadcast(text)
        self.assertTrue(seen, '说完要排一个「什么时候收」的定时器')
        self.assertEqual(seen[-1][0], cloud.read_hold(text), '排的毫秒数＝读完这句要多久')
        self.assertGreaterEqual(seen[-1][0], pet_cloud.HOLD_MS)


class CheekAndTailTests(PetTestCase):
    """第 24 期第 2／9 条：尾巴尖钉在三虎的脸颊上，云身怎么变都只是让尾巴变长变短。"""

    def placed(self, anchor=(1200.0, 320.0), bottom=384.0):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        rect = (anchor[0] - pet_ui.SIZE * pet_cloud.CHEEK_X,
                anchor[1] - pet_ui.SIZE * pet_cloud.CHEEK_Y, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._anchor = lambda: anchor
        cloud._patch_rect = lambda: rect
        cloud._bottom = lambda: bottom
        cloud._work_right = lambda: 1920
        cloud._render()
        return cloud

    def test_the_pet_has_a_cheek_to_point_at(self):
        left, top, width, height = 100.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE)
        cloud = self.pet.cloud()
        cloud._patch_rect = lambda: (left, top, width, height)
        self.assertEqual(cloud._cheek(), (left + width * pet_cloud.CHEEK_X,
                                          top + height * pet_cloud.CHEEK_Y))
        self.assertEqual(cloud._anchor(), cloud._cheek(), '云身与尾巴共用一个锚点')

    def test_the_tip_lands_on_the_cheek_of_the_pet(self):
        anchor = (1200.0, 320.0)
        cloud = self.placed(anchor=anchor)
        left, top = cloud._origin()
        tip_x, tip_y = cloud._tip()
        self.assertAlmostEqual(left + tip_x, anchor[0], delta=1, msg='尖角指着脸颊那一列')
        self.assertAlmostEqual(top + tip_y, anchor[1], delta=1)

    def test_the_tip_keeps_its_place_when_the_body_resizes(self):
        """界面缩放：云身长高或压矮，尖角仍钉在脸颊那一点上（用户要的「尾巴始终在原位」）。"""
        anchor = (1200.0, 320.0)
        spots = []
        for body in (pet_cloud.MIN_BODY, 160, pet_cloud.MAX_BODY):
            cloud = self.placed(anchor=anchor)
            cloud._fit_body = lambda wanted, body=body: int(body)
            cloud._render()
            left, top = cloud._origin()
            tip_x, tip_y = cloud._tip()
            spots.append((left + tip_x, top + tip_y, cloud._body))
        self.assertEqual([spot[2] for spot in spots], [pet_cloud.MIN_BODY, 160, pet_cloud.MAX_BODY],
                         '云身真的换过高度，这条才盯得住')
        for spot in spots:
            self.assertAlmostEqual(spot[0], anchor[0], delta=1)
            self.assertAlmostEqual(spot[1], anchor[1], delta=1)


class AvoidPetTests(PetTestCase):
    """第 24 期第 9 条：云身可以压住界面里的文字，但不许压住三虎，而且别移太远。"""

    def cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        cloud._patch_rect = lambda: (1000.0, 200.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        return cloud

    def covers_the_pet(self, cloud, spot):
        left, top = spot
        # 只量云身那一块方框：尾巴是按用户要求「指着脸颊」的指针，本来就碰到三虎
        # （见 pet_cloud.Cloud._avoid_pet 的说明）。
        width, height = cloud.width(), cloud._body
        rect = cloud._patch_rect()
        return not (left + width <= rect[0] - pet_cloud.PET_GAP
                    or left >= rect[0] + rect[2] + pet_cloud.PET_GAP
                    or top + height <= rect[1] - pet_cloud.PET_GAP
                    or top >= rect[1] + rect[3] + pet_cloud.PET_GAP)

    def test_a_spot_that_does_not_touch_the_pet_is_left_alone(self):
        cloud = self.cloud()
        spot = (100, 100)
        self.assertEqual(cloud._avoid_pet(*spot), spot, '没压着就一个像素都不动')

    def test_a_spot_on_the_pet_moves_only_just_enough(self):
        cloud = self.cloud()
        spot = (int(cloud._patch_rect()[0]) - 40, 200)      # 右边压在猫脸上
        moved = cloud._avoid_pet(*spot)
        self.assertFalse(self.covers_the_pet(cloud, moved), '让开之后不许再压着三虎')
        self.assertLessEqual(moved[0], spot[0], '往左让')
        self.assertLess(spot[0] - moved[0], cloud.total_width(), '只挪到刚好不压着，别移太远')

    def test_the_real_layout_never_covers_the_pet(self):
        """真实落点：云身站在三虎左边，一条缝都不压（第 24 期起落点还要过这道闸）。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        cloud._patch_rect = lambda: (1500.0, 100.0, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._bottom = lambda: 100.0 + pet_ui.SIZE + pet_cloud.ANCHOR_DROP
        cloud._work_right = lambda: 1920
        cloud._render()
        self.assertFalse(self.covers_the_pet(cloud, cloud._origin()))


class MaxGapTests(PetTestCase):
    """第 25 期第 4 条：云身离三虎最多 MAX_GAP 那么远（被屏幕边／界面推得太开就拉回来）。"""

    def cloud(self, left=1500.0, top=100.0):
        cloud = self.pet.cloud()
        cloud.show(pinned=False)
        spot = (left, top, float(pet_ui.SIZE), float(pet_ui.SIZE))
        cloud._patch_rect = lambda: spot
        cloud._bottom = lambda: spot[1] + spot[3] + pet_cloud.ANCHOR_DROP
        cloud._work_right = lambda: 3000
        cloud._screen_height = lambda: 1080
        return cloud

    def gap(self, cloud):
        left, _top = cloud._origin()
        return cloud._patch_rect()[0] - (left + cloud.width())

    def test_a_cloud_pushed_far_away_is_pulled_back(self):
        cloud = self.cloud()
        cloud._inside_window = lambda left, top: (60.0, top)     # 屏幕挤得只能摆在界面最左边
        self.assertGreater(cloud._patch_rect()[0] - (60.0 + cloud.width()), pet_cloud.MAX_GAP,
                           '这条用例得真把它推远，才盯得住')
        self.assertLessEqual(self.gap(cloud), pet_cloud.MAX_GAP, '拉回来之后就不该再那么远')
        self.assertGreater(self.gap(cloud), 0, '拉回来也不许压到三虎身上')

    def test_a_cloud_that_is_already_close_is_left_alone(self):
        cloud = self.cloud()
        left, top = cloud._origin()
        self.assertLessEqual(self.gap(cloud), pet_cloud.MAX_GAP)
        self.assertEqual(cloud._near_pet(left, top), (int(left), int(top)), '已经在近处：一个像素都不动')

    def test_it_is_not_pulled_out_of_the_screen(self):
        cloud = self.cloud()
        cloud._inside_window = lambda left, top: (60.0, top)
        cloud._work_right = lambda: 380          # 屏幕只剩这么宽：拉回来就出界了
        left, _top = cloud._origin()
        self.assertEqual(int(left), 60, '宁远离，不越界')

    def test_the_tail_still_lands_on_the_cheek_after_being_pulled(self):
        cloud = self.cloud()
        cloud._inside_window = lambda left, top: (60.0, top)
        left, top = cloud._origin()
        tip_x, tip_y = cloud._tip()
        cheek_x, cheek_y = cloud._cheek()
        self.assertAlmostEqual(left + tip_x, cheek_x, delta=1, msg='拉近了也要指着脸颊')
        self.assertAlmostEqual(top + tip_y, cheek_y, delta=1)


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
        cloud.submit()
        self.assertTrue(any(line.startswith('您：') for line in cloud.lines), '聊天记录要留下')


class ForegroundTests(PetTestCase):
    """第 30 期第 3 条：用户切到别的应用上时，三虎不再把聊天框／气泡顶出来。

    「切到别的应用」＝前台窗口不是本进程的窗口（pet_ui.our_process_in_front）。只拦三虎自己
    冒出来的那几路（心跳播报、进度气泡、主动询问、失败提醒），用户自己点开的对话框一条都不拦。
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.pet.clock = lambda: self.now
        self.counts = {"storyboards": 3, "adopted": 0, "shots": 0, "frames": 0}
        self.pet.counts = lambda: dict(self.counts)

    def away(self):
        self.pet.front = lambda: False

    def here(self):
        self.pet.front = lambda: True

    def lines(self):
        return self.pet.cloud().transcript()

    # ── 判据本身 ────────────────────────────────────────────────────────────
    def test_without_a_judge_nothing_is_blocked(self):
        self.assertIsNone(self.pet.front, "自检与假宿主走的就是「不设这道闸」")
        self.assertTrue(self.pet.attending())

    def test_attach_carries_the_judge(self):
        handle = lambda: True
        quiet = pet_ui.attach(self.fake, autostart=False, front=handle)
        self.assertIs(quiet.front, handle)

    def test_a_broken_judge_keeps_talking_and_records_it(self):
        def boom():
            raise RuntimeError("问不到前台窗口")

        self.pet.front = boom
        self.assertTrue(self.pet.attending(), "拦错一边就是把播报全吞了，宁可多说一句")
        self.assertTrue(any(name == "front" for name, _text in self.pet.errors))

    def test_the_windows_api_answers_a_yes_or_no(self):
        self.assertIn(pet_ui.our_process_in_front(), (True, False), "问不出来一律当 True，绝不抛")

    # ── 自动播报 ────────────────────────────────────────────────────────────
    def test_the_heartbeat_keeps_quiet_in_another_app(self):
        self.pet.tick_broadcast()                     # 第一拍只对表
        self.away()
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.assertEqual(self.pet.tick_broadcast(), "", "用户在别的应用里：这一拍不许冒泡")
        self.assertNotIn("分镜 JSON", self.lines())
        self.assertFalse(self.pet.cloud().visible)

    def test_coming_back_hears_the_news(self):
        self.pet.tick_broadcast()
        self.away()
        self.now += pet_ui.BROADCAST_IDLE + 1
        self.assertEqual(self.pet.tick_broadcast(), "")
        self.here()
        self.assertIn("分镜 JSON", self.pet.tick_broadcast(), "回到软件里再说不迟")

    def test_the_progress_bubble_waits_too(self):
        self.away()
        self.assertEqual(self.pet.progress_voice(force=True), "", "进度气泡也不许冒")
        self.assertNotIn("进度", self.lines())

    def test_a_line_said_while_away_goes_into_the_record_only(self):
        """第 49 期第 1 条：人切到别的应用时，这句话只进云朵记录、不把框顶出来。

        原来照顶——那一刻贴片量出来的坐标是假的（主窗口没映射），框就落到屏幕另一头，
        正是用户报的「从右边跳到左边」。
        """
        self.away()
        self.assertEqual(self.pet.broadcast('这一句只说给记录听'),
                         self.pet._prefix_output('这一句只说给记录听'))
        cloud = self.pet.cloud()
        self.assertFalse(cloud.visible, '人在别的应用里，不弹框')
        self.assertIn('这一句只说给记录听', cloud.transcript(), '话不许丢：记在记录里')
        self.here()
        self.pet.broadcast('回来了就冒')
        self.assertTrue(cloud.visible, '人在界面里：照常冒')


    def test_the_oneclick_offer_waits_too(self):
        self.away()
        self.pet.offer_oneclick()                     # 第一拍只对表
        self.now += pet_ui.OFFER_SECONDS + 1
        self.assertEqual(self.pet.offer_oneclick(), "")
        self.assertNotIn("一键执行", self.lines())

    def test_the_failure_notice_waits_too(self):
        self.away()
        self.pet.agent.fail("keyframe", "超时", attempt=4)
        self.assertEqual(self.pet.announce_failures(), "", "失败提醒先记着，不弹")
        self.assertNotIn("超时", self.lines())
        self.here()
        self.assertTrue(self.pet.announce_failures(), "回来之后再提醒")

    def test_the_users_own_chat_still_opens(self):
        """自己点开的对话框不是「打扰」：切到别的应用时也不拦。"""
        self.away()
        self.assertIsNotNone(self.pet.open_chat())
        self.assertTrue(self.pet.cloud().visible)

    # ── 第 60 期第 4 条：对话框只能在助手界面上面，不许穿到别的应用上 ─────────
    def showing(self, value=True):
        """自检里主窗口是 withdraw 的：招呼只在主窗口露着时才冒，这里按用例需要钉住它。"""
        self.pet.window_visible = lambda: value

    def test_the_cloud_is_not_topmost_while_the_user_is_away(self):
        self.pet.open_chat()
        cloud = self.pet.cloud()
        self.assertTrue(cloud.win.attributes('-topmost'), '人在界面里：照旧置顶')
        self.away()
        self.assertFalse(cloud.sync_topmost(), '人切走了：不许再压着别的应用')
        self.assertFalse(bool(cloud.win.attributes('-topmost')))

    def test_a_cloud_left_open_is_put_away_when_the_user_leaves(self):
        self.pet.open_chat()
        cloud = self.pet.cloud()
        self.away()
        self.assertTrue(self.pet.guard_cloud_away(), '这一拍真的收了一朵')
        self.assertFalse(cloud.visible)
        self.assertIsNone(self.pet.chat)

    def test_the_heartbeat_keeps_the_cloud_off_other_apps(self):
        self.pet.open_chat()
        self.away()
        self.pet.pump()
        self.assertFalse(self.pet.cloud_visible(), '心跳一到就把露着的云收起来')

    def test_while_here_the_cloud_stays(self):
        self.pet.open_chat()
        self.assertFalse(self.pet.guard_cloud_away())
        self.assertTrue(self.pet.cloud_visible(), '人在界面里就别动它')

    def test_the_greeting_and_the_whisper_wait_for_the_user(self):
        self.showing()
        self.away()
        self.assertEqual(self.pet.greet(), '', '招呼不许穿到别的应用上')
        self.assertEqual(self.pet.whisper('随口一句'), '')
        self.assertEqual(self.pet.banner('一张便签'), '')
        self.assertFalse(self.pet.cloud_visible(), '一句都没冒出去')

    def test_the_greeting_still_comes_while_here(self):
        self.showing()
        self.here()
        self.assertEqual(self.pet.greet(), self.pet._prefix_output(pet_cloud.GREETING))

    # ── 第 35 期第 1 条：切出去＝三虎进入暂停状态（不再只是「各自闭嘴」） ───────
    def test_leaving_the_window_pauses_the_pet_after_a_grace(self):
        self.assertTrue(self.pet.watch_focus(), "第一拍人还在界面里")
        self.away()
        self.assertFalse(self.pet.watch_focus(), "人不在界面里：这一拍起算离开时间")
        self.now += pet_ui.AWAY_PAUSE_SECONDS - 1
        self.assertFalse(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused, "刚切出去那一下不暂停：alt-tab 一闪不折腾")
        self.now += 1
        self.assertFalse(self.pet.watch_focus())
        self.assertTrue(self.pet.agent.paused, "离开界面满 AWAY_PAUSE_SECONDS 就真的停下来")
        self.assertIn('您切去了别的应用', self.pet.agent.paused_reason)

    def test_an_alt_tab_and_back_never_pauses(self):
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS - 2
        self.pet.watch_focus()
        self.here()
        self.pet.watch_focus()
        self.assertFalse(self.pet.agent.paused, "闪一下就回来：一次都没暂停过")
        self.assertEqual(self.pet.notice, '')

    def test_coming_back_resumes_without_a_word(self):
        """第 37 期第 6 条：切回助手界面时不用弹聊天框——只把自动执行接上，一个字都不说。"""
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.pet.watch_focus()
        self.assertTrue(self.pet.agent.paused)
        self.here()
        before = self.lines()
        self.assertTrue(self.pet.watch_focus(), "人回来了")
        self.assertFalse(self.pet.agent.paused, "回来就自动接着跑")
        self.assertNotIn('已回到助手界面', self.pet.notice)
        self.assertEqual(self.lines(), before, "回来说一个字都不冒")
        self.assertFalse(self.pet.cloud_visible(), "也没冒一朵框")

    def test_a_manual_pause_is_left_alone(self):
        self.pet.agent.pause('你自己按的暂停')
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.pet.watch_focus()
        self.here()
        self.pet.watch_focus()
        self.assertTrue(self.pet.agent.paused, "手动按的暂停不替我恢复")
        self.assertEqual(self.pet.agent.paused_reason, '你自己按的暂停')
        self.assertNotIn('已回到助手界面', self.pet.notice)

    def test_a_resume_while_away_is_not_announced(self):
        self.pet.watch_focus()
        self.away()
        self.pet.watch_focus()
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.pet.watch_focus()
        self.pet.click('resume')                       # 人不在界面里，自己从菜单按了「继续」
        self.here()
        self.assertTrue(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused)
        self.assertNotIn('已回到助手界面', self.pet.notice, "不是我的暂停，就别替我说话")

    def test_without_a_judge_nothing_is_paused(self):
        self.pet.front = None
        self.now += pet_ui.AWAY_PAUSE_SECONDS + 1
        self.assertTrue(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused, "没有判据的假宿主什么都不做")

    def test_a_broken_judge_is_recorded_and_keeps_the_pet_running(self):
        def boom():
            raise RuntimeError('问不到前台窗口')

        self.pet.front = boom
        self.assertTrue(self.pet.watch_focus())
        self.assertFalse(self.pet.agent.paused, "问不出来宁可什么都不做，也不能替用户停")
        self.assertTrue(any(name == 'front' for name, _text in self.pet.errors),
                        "判据出错照旧记一笔（attending 那道闸自己收的）")


class ChatSizeTests(PetTestCase):
    """第 30 期第 4 条：聊天框尺寸收一档，文字尺寸一动不动。"""

    def test_the_chat_box_is_narrower_than_round_28(self):
        self.assertLess(pet_cloud.WIDTH, 372, "第 28 期那一档是 372，这一轮要更窄")
        self.assertLessEqual(pet_cloud.MAX_BODY, 236, "框身整体也收一档")
        self.assertGreaterEqual(pet_cloud.WIDTH, 300, "别收成一条缝：正文还要排得开")

    def test_the_text_size_is_only_one_step_smaller(self):
        """第 49 期第 3 条：这一期只收字号，一档一档连着（15 → 13），别的地方一动不动。"""
        from ui_tokens import FONTS
        self.assertEqual(pet_cloud.FONT, FONTS['body'], "正文使用设计系统 body 令牌")
        self.assertEqual(tuple(pet_cloud.STICKER_FONTS), (13, 12, 11, 10, 9, 8, 7, 6),
                         "贴纸那几档跟着收，仍然连成一串")

    def test_the_chat_still_holds_a_line(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.canvas.update_idletasks()
        box = pet_cloud.text_box(pet_cloud.SHAPE_CLOUD, cloud.width(), cloud._body)
        self.assertGreaterEqual(box[2], 240, "写字框还放得下一行十来个字")


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
        self.pet._last_broadcast = ""                # 「同一句不连说两遍」是另一道闸：这里只看节流
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

    def test_hint_only_reports_the_current_script_progress(self):
        self.pet.agent.set_level('hint')
        self.pet.run_skill = lambda *_args, **_kwargs: self.fail('提示档不能启动 SKILL')
        said = self.pet.enter_stage(page=0, at=self.now)
        self.assertIn('【阶段 1/12】', said)
        self.assertIn('剧本', said)
        self.assertIn('当前进度', said)

    def test_semi_auto_combines_progress_with_existing_confirmation(self):
        self.pet.agent.set_level('semi')
        self.pet.run_skill = lambda *_args, **_kwargs: self.fail('确认前不能启动 SKILL')
        said = self.pet.enter_stage(page=0, at=self.now)
        self.assertIn('【阶段 1/12】', said)
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
        self.assertEqual(self.pet.enter_stage(page=0, at=self.now + 1), self.spoken[-1])
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


class CloudFitTests(PetTestCase):
    """第 36 期第 11／12 条：回复框摆出三虎听得懂的指令；云朵框跟着文字收窄。

    第 7 条在这里一并盯住：主界面贴着屏幕上沿时，这一条内容上方放不下就整朵往下挪。
    """

    def test_the_commands_roll_inside_the_reply_box(self):
        """第 37 期第 4 条：基本指令放进回复框里、小字、自己往右滚，不再写「三虎听得懂：」。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        self.assertIn(cloud.hint, cloud.chat_row.winfo_children(), '小字就挂在回复框这一行里')
        # 第 39 期第 1 条：贴着左沿、从最左侧起步，底色跟输入框（不再是云身色那块贴片）。
        self.assertEqual(float(cloud.hint.place_info().get('relx')), 0.0, '贴着回复框左沿')
        self.assertEqual(cloud.hint.place_info().get('anchor'), 'w', '左对齐：小字往右长')
        self.assertEqual(str(cloud.hint.cget('bg')), cloud.field_bg(), '底色跟着 ttk.Entry 走')
        self.assertNotEqual(str(cloud.hint.cget('bg')), cloud.fill(), '不再刷云身色')
        self.assertGreaterEqual(pet_cloud.HINT_MS, 400, '慢慢挪')
        self.assertLess(pet_cloud.HINT_FONT[1], pet_cloud.REPLY_FONT[1], '小字比回复框的字小一档')
        self.assertIn(str(pet_cloud.HINT_FONT[1]), str(cloud.hint.cget('font')), '真的挂在这一档上')
        self.assertTrue(str(cloud.hint.cget('text')).strip(), '开着就露着一条')
        self.assertNotIn('三虎听得懂', pet_cloud.REPLY_HINTS, '那半句前缀删掉了')
        for word in ('右键功能', '进度面板', '设置模型', '自动化等级', '暂停', '重试失败项', '退出程序'):
            self.assertIn(word, pet_cloud.REPLY_HINTS)
        self.assertEqual(cloud.status.cget('text'), '', '这三句不再占提示行')

    def test_the_rolling_line_starts_at_the_left_and_marches_right(self):
        """整句从左往右移动，离场后才重新从左侧开始，不在中段循环拼接。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        first = str(cloud.hint.cget('text'))
        first_x = int(cloud.hint.place_info().get('x'))
        self.assertEqual(first, pet_cloud.REPLY_HINTS, '整句不截断')
        self.assertEqual(first_x, pet_cloud.HINT_X, '一露脸就在最左侧')
        cloud._hint_tick()
        second = str(cloud.hint.cget('text'))
        second_x = int(cloud.hint.place_info().get('x'))
        self.assertEqual(second, first, '移动时正文不从中间截断')
        self.assertEqual(second_x, first_x + pet_cloud.HINT_STEP_PX, '向右移动')
        cloud._hint_stop()
        self.assertEqual(cloud.hint.cget('text'), '', '收起后把字清干净')

    def test_clicking_the_hint_yields_to_the_reply_cursor(self):
        """点到提示层也必须进入输入框，不能把光标挡在灰字后面。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        cloud._focus_reply()
        self.assertEqual(cloud.reply.focus_get(), cloud.reply, '提示层点击后焦点回到输入框')
        self.assertEqual(cloud.hint.cget('text'), '', '用户开始输入时提示让位')
        cloud._restore_hint_after_reply()
        self.assertEqual(cloud.hint.cget('text'), pet_cloud.REPLY_HINTS, '离开空框后恢复说明')

    def test_the_entry_colour_falls_back_when_the_theme_has_none(self):
        """量不到输入框底色时退回常量：写一个空字符串回去，标签会被画成一块默认色。"""
        import tkinter.ttk as ttk_module
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        real = ttk_module.Style.lookup
        ttk_module.Style.lookup = lambda self, *args, **kwargs: ''
        self.addCleanup(setattr, ttk_module.Style, 'lookup', real)
        self.assertEqual(cloud.field_bg(), pet_cloud.HINT_BG)

    def test_every_chat_window_gets_the_rolling_line(self):
        """第 39 期第 1 条：回复框一露出来就有这条小字，不用等提示行那一拍。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud._hint_stop()
        self.assertEqual(cloud.hint.cget('text'), '')
        cloud.pin()                       # 点一下云：转成对话形态
        cloud._render()
        self.assertTrue(str(cloud.hint.cget('text')).strip(), '回复框露出来就滚起来')
        self.assertEqual(cloud._hint_x, pet_cloud.HINT_X, '还是从最左侧起步')
        cloud._hint_stop()

    def test_the_rolling_line_gives_way_to_what_the_user_types(self):
        """别遮挡：框里一有字就把这条小字藏起来，清空了再露。"""
        cloud = self.pet.cloud()
        self.pet.open_chat()
        cloud.reply.insert(0, '查一下进度')
        self.assertEqual(cloud._sync_hint(), '', '有字就藏')
        cloud.reply.delete(0, 'end')
        self.assertTrue(str(cloud._sync_hint()).strip(), '清空了再露出来')
        status = cloud.status.cget('text')
        cloud.set_status(pet_cloud.BUSY)
        self.assertEqual(cloud.hint.cget('text'), '', '三虎在忙着想：小字让位')
        self.assertEqual(cloud.status.cget('text'), pet_cloud.BUSY)
        cloud.set_status(status)

    def test_a_short_line_gets_a_narrow_cloud(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        cloud.lines = ['好']
        cloud._render()
        narrow = cloud.width()
        self.assertGreaterEqual(narrow, pet_cloud.MIN_WIDTH, '再短也有个下限')
        cloud.lines = ['这一句长得多，长到得换一行才排得下，看看框身会不会跟着宽一点。']
        cloud._render()
        self.assertGreater(cloud.width(), narrow, '字多了框就宽一档')
        self.assertLessEqual(cloud.width(), pet_cloud.shape_width(pet_cloud.SHAPE_CLOUD),
                             '再长也封顶在原来的宽度')

    def test_a_docked_top_window_sends_the_cloud_down(self):
        """第 36 期第 7 条：全屏／上移到屏幕边缘时，上方放不下就整朵往下挪。"""
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        room = pet_cloud.shape_min_body(pet_cloud.SHAPE_CLOUD) + 10
        cloud._room_above = lambda: room
        cloud._room_below = lambda: 520
        cloud._docked_top = lambda: True
        self.assertTrue(cloud._wants_down(room + 60), '贴着屏幕上沿、这条内容放不下：往下挪')
        cloud._docked_top = lambda: False
        self.assertFalse(cloud._wants_down(room + 60), '界面不在屏幕顶：落点照旧')
        cloud._docked_top = lambda: True
        self.assertFalse(cloud._wants_down(10), '这一条上方放得下：不动')
        cloud._room_below = lambda: 10
        self.assertFalse(cloud._wants_down(room + 60), '下面更窄：也不挪')

    def test_the_body_decides_the_side_before_measuring(self):
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        cloud._room_above = lambda: 60
        cloud._room_below = lambda: 520
        cloud._docked_top = lambda: True
        cloud._fit_body(300)
        self.assertTrue(cloud._down, '量之前先把朝向定下来')
        self.assertTrue(cloud._flipped(), '_down 之后就算翻到下面了')

    def test_the_old_flip_rule_still_works(self):
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        cloud._down = False
        cloud._room_above = lambda: 10
        cloud._room_below = lambda: 400
        cloud._docked_top = lambda: False
        self.assertTrue(cloud._flipped(), '上方连最小云身都放不下：照旧翻下去')


    def test_a_window_flush_with_the_screen_top_counts_as_docked(self):
        """第 42 期第 2 条：窗体上沿（含标题栏）贴到屏幕上沿就算「贴着顶」。

        原来按客户区上沿（winfo_rooty）判，窗口拖到屏幕最上面时客户区还在标题栏下面二三十像素，
        判据整个不生效——用户看到的「聊天框只显示一行」就是这么来的。
        """
        cloud = self.pet.cloud()
        win = self.win
        win.deiconify(); win.geometry('520x360+0+0'); win.update()
        self.addCleanup(win.withdraw)
        self.assertTrue(cloud._docked_top(), '拖到屏幕最上面＝贴着顶（客户区还差一条标题栏）')
        win.geometry('520x360+0+260'); win.update()
        self.assertFalse(cloud._docked_top(), '离屏幕顶还有一段：照旧不算')

    def test_the_box_grows_past_the_normal_ceiling_only_when_docked(self):
        """第 42 期第 2 条：贴着顶、整朵翻到三虎下面时上限放宽；内容短还是原来那么小。"""
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_CLOUD
        cloud._room_above = lambda: 60
        cloud._room_below = lambda: 700
        cloud._docked_top = lambda: True
        self.assertEqual(cloud._body_ceiling(), pet_cloud.MAX_BODY_DOWN)
        body = cloud._fit_body(400)
        self.assertTrue(cloud._flipped(), '贴着顶：整朵往下挪')
        self.assertGreater(body, pet_cloud.MAX_BODY, '下面那一整屏是空的：允许长过原来那一档')
        self.assertLessEqual(body, pet_cloud.MAX_BODY_DOWN)
        self.assertLessEqual(cloud._fit_body(120), 120, '内容短就还是原来那么小')
        # 界面不在屏幕顶（哪怕翻下去过）照旧收在 MAX_BODY
        cloud._docked_top = lambda: False
        cloud._room_above = lambda: 10
        self.assertEqual(cloud._body_ceiling(), pet_cloud.MAX_BODY)
        self.assertLessEqual(cloud._fit_body(400), pet_cloud.MAX_BODY)

    def test_a_sticker_never_grows_a_reply_box(self):
        """第 40 期第 1 条：贴纸点一下只把话多留一会儿，不长出回复框。

        用户报「三虎打招呼的云朵框里有个回复框」——点一下那朵云，它原来会顺手转成带输入行的
        样子（pin 一视同仁）。现在只有方框对话框带回复框，三种贴纸都不带。
        """
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND, pet_cloud.SHAPE_TAG):
            with self.subTest(shape=shape):
                cloud = self.pet.cloud()
                cloud.show(pinned=False, shape=shape)
                cloud.pin()                                  # 点一下这朵贴纸
                self.assertFalse(cloud.pinned, '贴纸不转对话形态')
                self.assertFalse(cloud._replies())
                self.assertEqual(cloud.chat_row.place_info(), {}, '回复框那一行不摆出来')
                self.assertEqual(cloud.status.place_info(), {}, '提示行也不占位')
                self.assertEqual(cloud.hint.place_info(), {}, '滚动小字跟着那一行一起收')
        cloud = self.pet.cloud()
        cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        cloud.pin()
        self.assertTrue(cloud._replies() and cloud.chat_row.place_info(), '方框对话框照旧带回复框')

    def test_the_greeting_bubble_has_no_reply_row(self):
        """第 40 期第 1 条：开机招呼那一屏没有回复框，点开也长不出来。"""
        cloud = self.pet.cloud()
        cloud.greet()
        self.assertEqual(cloud.shape, pet_cloud.SHAPE_PUFF, '招呼还是云朵框')
        for name, widget in (('回复框', cloud.reply), ('提示行', cloud.status), ('滚动小字', cloud.hint)):
            self.assertEqual(widget.place_info(), {}, '%s 不该在招呼那一屏里' % name)
        cloud.pin()
        self.assertEqual(cloud.reply.place_info(), {}, '点一下招呼那朵云也不长回复框')
        self.assertEqual(str(cloud.reply.get()), '', '回复框是空的那个（压根没摆出来）')

    def test_the_puff_follows_the_line(self):
        """第 40 期第 3 条：云朵框也跟文字多少收放——短话收窄，长话封顶在原来的宽度。"""
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_PUFF)
        cloud.lines = ['喵']
        cloud._render()
        narrow = cloud.width()
        self.assertGreaterEqual(narrow, pet_cloud.PUFF_MIN_WIDTH, '再短也有个下限')
        self.assertLess(narrow, pet_cloud.shape_width(pet_cloud.SHAPE_PUFF), '短话不占满一整条')
        cloud.lines = ['三虎：' + '这一句长得多，长到得换一行才排得下。' * 3]
        cloud._render()
        self.assertEqual(cloud.width(), pet_cloud.shape_width(pet_cloud.SHAPE_PUFF), '长话封顶')
        self.assertGreater(cloud.width(), narrow, '字多了框就宽一档')

    def test_the_progress_frame_follows_the_line(self):
        """第 40 期第 3 条：进度那个框也跟文字多少收放（原来钉在 ROUND_WIDTH）。"""
        cloud = self.pet.cloud()
        cloud.lines = ['进度：20%']
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_ROUND)
        short = cloud.width()
        self.assertGreaterEqual(short, pet_cloud.ROUND_MIN_WIDTH, '再短也有个下限')
        self.assertLess(short, pet_cloud.shape_width(pet_cloud.SHAPE_ROUND), '一句短话不占满整条')
        x, y, w, h = cloud._text_box()
        self.assertGreater(w, 0, '收窄之后写字框仍有地方落字')
        cloud.lines = ['进度：剧本准备 20%\n首帧还差 36 个镜头（06 首帧管理 → 手动制作首帧）']
        cloud._render()
        self.assertGreater(cloud.width(), short, '字多了椭圆就宽一档')
        self.assertLessEqual(cloud.width(), pet_cloud.shape_width(pet_cloud.SHAPE_ROUND), '封顶')


class ProjectMemoryTests(PetTestCase):
    """第 37 期第 1 条：三虎要「记住所有项目」——登记表整本记下来，名字、状态、走到哪一步都答得出。"""

    def setUp(self):
        super().setUp()
        self.other = Path(self.tmp.name) / 'q'
        (self.other / '工作流任务' / '宠物').mkdir(parents=True)
        self.fake.projects = _Registry(str(self.fake.root), [
            {'name': '甲', 'path': str(self.fake.root)},
            {'name': '乙', 'path': str(self.other), 'status': 'completed'}])

    def test_every_project_is_remembered(self):
        rows = self.pet.projects_snapshot(force=True)
        self.assertEqual([row['name'] for row in rows], ['甲', '乙'])
        self.assertTrue(rows[0]['active'], '当前项目排最前')
        self.assertEqual(rows[1]['status'], '已完成')
        self.assertEqual(rows[0]['status'], '在制作')
        self.assertTrue(rows[0]['stage'], '每个项目都记住走到哪一步了')

    def test_the_list_is_cached_until_it_is_forced(self):
        first = self.pet.projects_snapshot(force=True)
        self.fake.projects.info['projects'].append({'name': '丙', 'path': str(self.other)})
        self.assertEqual(len(self.pet.projects_snapshot()), len(first), 'TTL 之内用缓存')
        self.assertEqual(len(self.pet.projects_snapshot(force=True)), len(first) + 1, '强制重读看得见新项目')

    def test_the_pet_reads_the_list_out_loud(self):
        text = self.pet.projects_text(force=True)
        self.assertIn('甲', text)
        self.assertIn('乙', text)
        self.assertIn('已完成', text)
        self.assertIn('2 个项目', text)

    def test_asking_about_projects_is_answered(self):
        result = self.pet.agent.dispatch('有哪些项目')
        self.assertEqual(result['plan']['intent'], 'projects')
        self.assertTrue(result['decision']['run'], '看一眼的事哪一档都放行')
        said = self.pet.run_plan(result)
        self.assertIn('甲', said)

    def test_the_model_also_sees_the_projects(self):
        context = self.pet.agent.context()
        self.assertIn('projects', context)
        self.assertIn('甲', ' '.join(context['projects']))
        self.assertIn('当前', ' '.join(context['projects']), '哪个是当前项目要说清')

    def test_no_projects_yet_says_so(self):
        self.fake.projects.info = {'active': None, 'projects': []}
        self.assertEqual(self.pet.projects_snapshot(force=True), [])
        self.assertIn('还没建过项目', self.pet.projects_text(force=True))

    def test_a_broken_registry_never_raises(self):
        self.fake.projects.info = {'active': None, 'projects': [{'name': '没路径'}, '不是对象']}
        self.assertEqual(self.pet.projects_snapshot(force=True), [])
        self.assertTrue(self.pet.projects_text(force=True))
        self.assertFalse(self.pet.errors, '坏数据只丢一行，不记成错误')


class CloudHygieneTests(PetTestCase):
    """第 37 期第 5／6 条：记录里不留空行；对话框收起时及时清理；名字不再被小字抢位。"""

    def test_the_record_has_no_blank_lines(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=True)
        cloud.append('第一句\n\n   \n第二句  ')
        self.assertEqual(cloud.lines[-1], '第一句\n第二句')
        cloud.lines = ['三虎：上一条', '   ', '三虎：下一条']
        body = cloud._body_text()
        self.assertNotIn('\n\n', body, '每行之间不许有空行')
        self.assertNotIn('   ', body, '行内空白也收干净')

    def test_the_sticker_has_no_blank_lines_either(self):
        cloud = self.pet.cloud()
        cloud.show(pinned=False, shape=pet_cloud.SHAPE_PUFF)
        cloud.lines = ['三虎：一句\n\n带空行的话']
        self.assertEqual(cloud._body_text(), '三虎：一句\n带空行的话')

    def test_the_number_gap_survives(self):
        cloud = self.pet.cloud()
        cloud.shape = pet_cloud.SHAPE_ROUND
        gap = pet_cloud.NUMBER_GAP
        cloud.lines = ['当前阶段\n\n进度']       # 空行会被丢掉，两行各带一个号
        self.assertEqual(cloud._body_text(), '1.' + gap + '当前阶段\n2.' + gap + '进度')
        cloud.lines = ['甲' + gap + '乙']          # 行里本来就有的不换行空格一个都不动
        self.assertEqual(cloud._body_text(), '1.' + gap + '甲' + gap + '乙',
                         '不换行空格是「编号与正文粘在一起」的关键，一个都不能少')

    def test_trim_keeps_the_newest(self):
        cloud = self.pet.cloud()
        cloud.lines = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        self.assertEqual(cloud.trim(3), ['f', 'g', 'h'])

    def test_closing_the_dialog_trims_the_record(self):
        cloud = self.pet.cloud()
        self.pet.open_chat()
        for index in range(pet_cloud.CHAT_KEEP + 6):
            cloud.append('第%d句' % index)
        cloud.close()
        self.assertLessEqual(len(cloud.lines), pet_cloud.CHAT_KEEP)
        self.assertEqual(cloud.lines[-1], '第%d句' % (pet_cloud.CHAT_KEEP + 5), '留的是最新的')


class CloudCloseTests(PetTestCase):
    """第 45 期：三虎的对话框右上角多一颗看得见、点得到的「关闭」。"""

    def dialog(self, shape=None, pinned=True):
        cloud = self.pet.cloud()
        cloud.show(pinned=pinned, shape=shape or pet_cloud.SHAPE_CLOUD)
        cloud.canvas.update_idletasks()
        return cloud

    def test_the_dialog_grows_a_close_button_up_on_the_right(self):
        cloud = self.dialog()
        button = cloud.close_button
        self.assertIsNotNone(button, "对话框右上角要有一颗点得到的关闭")
        self.assertEqual(str(button.cget("text")), pet_cloud.CLOSE_MARK)
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = button.place_info()
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE, "贴着云身右上角")
        self.assertEqual(float(spot["y"]), box_y + 2)
        self.assertEqual((float(spot["width"]), float(spot["height"])),
                         (float(pet_cloud.CLOSE_SIZE), float(pet_cloud.CLOSE_SIZE)))

    def test_the_cloud_wears_no_zoom_buttons_in_its_corner(self):
        """第 8 轮（收口）：弹窗那两颗「最小化／最大化」全程序都删了（见 ui_theme），
        这一朵云自然也没有——第 67 期任务 1 当年是单独把它从这朵云上摘掉的，现在整份接线
        都不在了，弹窗与云朵框都只剩自己那颗 ×。
        """
        import ui_theme
        cloud = self.dialog()
        self.assertIsNone(getattr(cloud.win, "_drama_buttons", None), "云朵框不带那两颗按钮")
        self.assertFalse(hasattr(ui_theme, "window_buttons"), "第 8 轮起没有画键的函数了")

    def test_the_records_start_below_the_close_button(self):
        cloud = self.dialog()
        info = cloud.clip.place_info()
        self.assertEqual(float(info["y"]), cloud._text_box()[1] + pet_cloud.CLOSE_H,
                         "正文从「关闭」那条下面起步，别压在字上")
        self.assertLessEqual(float(info["y"]) + float(info["height"]),
                             float(cloud.chat_row.place_info()["y"]),
                             "记录仍然压不到输入行")

    def test_the_cross_is_placed_again_on_every_render(self):
        cloud = self.dialog()
        cloud.close_button.place_forget()
        cloud._render()
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = cloud.close_button.place_info()
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE)
        self.assertEqual(float(spot["y"]), box_y + 2)

    def test_clicking_the_cross_shuts_the_dialog(self):
        cloud = self.dialog()
        calls = []
        original = cloud.close
        cloud.close = lambda event=None: calls.append(event)
        self.addCleanup(setattr, cloud, "close", original)
        self.assertEqual(cloud._hit_close(), "break", "点一下就是收起，事件不再往下传")
        self.assertEqual(len(calls), 1)

    def test_the_escape_key_still_works_beside_the_cross(self):
        cloud = self.dialog()
        bound = cloud.win.bind()
        self.assertTrue(any("Escape" in item for item in bound),
                        "看得见的那颗只是多一条路，Esc 照旧要能用：%r" % (bound,))

    def test_the_cross_turns_red_under_the_mouse(self):
        cloud = self.dialog()
        button = cloud.close_button
        self.assertEqual(str(button.cget("bg")), pet_cloud.CLOSE_BG)
        button.event_generate("<Enter>")
        self.assertEqual(str(button.cget("bg")), pet_cloud.CLOSE_HOVER)
        button.event_generate("<Leave>")
        self.assertEqual(str(button.cget("bg")), pet_cloud.CLOSE_BG)

    def test_the_cross_shouts_where_to_close(self):
        """第 59 期第 9 条：关闭按钮要显著提示用户——红底白×的实心块，
        而不是原来一个不抢眼的灰×。"""
        cloud = self.dialog()
        button = cloud.close_button
        self.assertEqual(str(button.cget("bg")), pet_cloud.CLOSE_BG, "平时就是红的实心块")
        self.assertEqual(str(button.cget("fg")), pet_cloud.CLOSE_FG, "× 画成白的，红底上看得清")
        from ui_tokens import COLORS
        self.assertEqual(pet_cloud.CLOSE_FG, COLORS['background_card'])
        self.assertGreaterEqual(pet_cloud.CLOSE_SIZE, 20, "按钮足大，不用提着气去点")
        self.assertGreaterEqual(pet_cloud.CLOSE_H, pet_cloud.CLOSE_SIZE, "云身顶上那一条装得下这颗按钮")
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = button.place_info()
        self.assertEqual((float(spot["width"]), float(spot["height"])),
                         (float(pet_cloud.CLOSE_SIZE), float(pet_cloud.CLOSE_SIZE)))
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE, "还在云身右上角")

    def test_a_sticker_wears_a_close_button_too(self):
        """第 46 期第 4 条：云朵框与圆形框右上角也来一颗「关闭」。

        贴纸原来只靠到点自己收（用户要的「右上角增加关闭按钮」当时只做给了对话框）。
        """
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND):
            with self.subTest(shape=shape):
                cloud = self.dialog(shape=shape, pinned=False)
                self.assertFalse(cloud._replies(), "贴纸本来就没有输入行")
                self.assertTrue(cloud._closable(), "云朵框／圆形框要能随手关掉")
                button = cloud.close_button
                self.assertIsNotNone(button)
                box_x, box_y, box_w, _box_h = cloud._text_box()
                spot = button.place_info()
                self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE)
                self.assertEqual(float(spot["y"]), box_y + 2)
                self.assertEqual(str(button.cget("text")), pet_cloud.CLOSE_MARK)

    def test_the_sticker_text_starts_below_the_cross(self):
        """顶上那条「关闭」是从框身里量出来的：正文整块往下挪 CLOSE_H，字不压在×上。"""
        for shape in (pet_cloud.SHAPE_PUFF, pet_cloud.SHAPE_ROUND):
            with self.subTest(shape=shape):
                cloud = self.dialog(shape=shape, pinned=False)
                info = cloud.clip.place_info()
                self.assertEqual(float(info["y"]), cloud._text_box()[1] + pet_cloud.CLOSE_H)
                self.assertLessEqual(float(info["y"]) + float(info["height"]),
                                     cloud._text_box()[1] + cloud._text_box()[3],
                                     "正文仍然装在能写字的那块框里")

    def test_clicking_the_sticker_cross_puts_it_away(self):
        cloud = self.dialog(shape=pet_cloud.SHAPE_ROUND, pinned=False)
        calls = []
        original = cloud.close
        cloud.close = lambda event=None: calls.append(event)
        self.addCleanup(setattr, cloud, "close", original)
        self.assertEqual(cloud._hit_close(), "break")
        self.assertEqual(len(calls), 1)

    def test_the_report_tag_wears_a_close_button(self):
        """日报／周报标签框也要有可见且可点击的关闭入口。"""
        cloud = self.dialog(shape=pet_cloud.SHAPE_TAG, pinned=False)
        cloud._render(skip_sync=True)
        self.assertTrue(cloud._closable())
        self.assertIsNotNone(cloud.close_button)
        box_x, box_y, box_w, _box_h = cloud._text_box()
        spot = cloud.close_button.place_info()
        self.assertEqual(float(spot["x"]), box_x + box_w - pet_cloud.CLOSE_SIZE)
        self.assertEqual(float(spot["y"]), box_y + 2)
        self.assertEqual(str(cloud.close_button.cget("text")), pet_cloud.CLOSE_MARK)


class ChatUnderModalTests(PetTestCase):
    """第 59 期第 8 条：弹窗抽着指针时，三虎的聊天框不能留在那儿点不动。

    Tk 的本地 grab 把整个应用的指针事件都送进抓着的那屋窗，聊天框连右上角那颗
    「关闭」都点不动（用户报的就是这个）。所以：一发现有弹窗抓着，聊天框自己先收；
    要说的那一句话压住，弹窗一关心跳再补说。
    """

    def modal(self):
        """造一屋「正抽着指针」的弹窗（真 Toplevel，只把 grab_current 换成它）。"""
        holder = self.tk.Toplevel(self.win)
        self.addCleanup(holder.destroy)
        original = self.win.grab_current
        self.win.grab_current = lambda: holder
        self.addCleanup(setattr, self.win, "grab_current", original)
        return holder

    def test_a_modal_dialog_puts_the_chat_away(self):
        self.pet.open_chat()
        self.assertTrue(self.pet.cloud_visible())
        self.modal()
        self.assertTrue(self.pet.modal_grabbed(), "有弹窗抽着指针")
        self.assertTrue(self.pet.guard_chat_grab(), "这一拍真的收了一朵")
        self.assertFalse(self.pet.cloud_visible(), "关不掉的框不该留着")
        self.assertIsNone(self.pet.chat)

    def test_without_a_modal_the_chat_stays(self):
        self.pet.open_chat()
        self.assertFalse(self.pet.modal_grabbed())
        self.assertFalse(self.pet.guard_chat_grab())
        self.assertTrue(self.pet.cloud_visible(), "没弹窗就别动它")

    def test_the_held_line_is_said_once_the_dialog_closes(self):
        self.pet.open_chat()
        self.modal()
        self.pet.broadcast("弹窗期间的一句话")
        self.assertEqual(self.pet._held_broadcast, "弹窗期间的一句话", "弹窗期间先压着")
        self.assertTrue(self.pet.guard_chat_grab(), "心跳发现有弹窗：聊天框先自己收起来")
        self.assertFalse(self.pet.cloud_visible(), "关不掉的框不该留着")
        self.assertEqual(self.pet._held_broadcast, "弹窗期间的一句话", "压着的话不能丢")
        self.win.grab_current = lambda: None   # 弹窗关了
        self.pet.pump()                        # 下一个心跳把它补说
        self.assertFalse(self.pet._held_broadcast, "压不住太久：弹窗关了这一句就该说出去")
        self.assertIn("弹窗期间的一句话", self.pet.cloud().transcript(),
                      "弹窗一关，那句话还得说出去")


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
        """模型回话不弹完成框；用户下载剧本后才问要不要制作分镜。"""
        prompts = []
        self.pet.confirm = lambda text, **kwargs: prompts.append(text) or text
        self.pet.script_downloaded('剧本.md')
        self.assertEqual(prompts, ['【下一阶段】剧本已下载。现在制作分镜吗？'])

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
        """第 67 期任务 5：自动档不是「叫一声」，真的把这一步开起来；付费那步只叫醒。"""
        self.script_done()
        self.pet.set_level('semi')
        self.pet.start_stage('storyboard', at=self.now)
        self.assertEqual(self.started, ['storyboard'], '免费步骤自己起跑')
        self.pet.start_stage('assets', at=self.now)
        self.assertEqual(self.started, ['storyboard'], '半自动的付费步骤不代跑')
        self.assertIn('assets', self.fake.advances, '付费那一步退成「提前叫醒一轮」')

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

    def test_the_hint_level_starts_nothing_at_all(self):
        """第 67 期任务 4：只提醒档只看着，一个阶段都不替他开。"""
        self.script_done()
        self.assertEqual(self.pet.start_stage('storyboard', at=self.now), '')
        self.assertEqual(self.started, [])
        self.assertEqual(self.fake.advances, [])


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


if __name__ == "__main__":
    unittest.main(verbosity=1)
