# -*- coding: utf-8 -*-
"""短生命周期 Tk 首帧回归：启动不能再被嵌套 idle spin 卡住。"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import os
import sys
import tempfile
import time
import unittest
import json
from datetime import date
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
os.chdir(HERE)

import tkinter as tk

from desktop import Desktop, PAGES
import skill_registry
from performance_contract import (AUTO_RESUME_TO_SCRIPT_SECONDS,
                                  CHAT_FIRST_TEXT_SECONDS, FIRST_DAY_SELECTOR_SECONDS,
                                  FIRST_EVENT_LOOP_SECONDS, STARTUP_RECURSIVE_SCAN_COUNT)


class DesktopStartupPerfTests(unittest.TestCase):
    @staticmethod
    def _startup_app(temporary, *, remembered):
        """构造首日/同日两条真实启动分支所需的最小程序与项目登记。"""
        app = Path(temporary) / 'app'
        downloads = Path(temporary) / 'downloads'
        project = downloads / '项目' / '性能项目_20261002'
        (project / '01剧本准备' / '输入').mkdir(parents=True)
        (project / 'config.json').write_text('{}', encoding='utf-8')
        app.mkdir()
        (app / 'config.json').write_text(json.dumps({'downloads_root': str(downloads)}), encoding='utf-8')
        (app / 'projects.json').write_text(json.dumps({
            'active': str(project), 'projects': [{'name': '性能项目', 'path': str(project)}],
        }), encoding='utf-8')
        settings = {'comfy_url': 'http://127.0.0.1:8189', 'jianying': ''}
        if remembered:
            settings.update({'project_choice_day': date.today().isoformat(),
                             'project_choice_path': str(project)})
        (app / 'desktop_settings.json').write_text(json.dumps(settings), encoding='utf-8')
        return app, project

    @staticmethod
    def _pump_until(window, predicate, deadline):
        while time.perf_counter() < deadline:
            window.update()
            if predicate():
                return True
            time.sleep(.005)
        return False

    @staticmethod
    def _measure_after_callbacks(window):
        """包装 after，记录每个 UI 回调本身的耗时而非整轮 update 的耗时。"""
        measurements = []
        original_after = window.after
        def traced_after(delay, callback=None, *args):
            if callback is None:
                return original_after(delay)
            def timed():
                started = time.perf_counter()
                try:
                    return callback(*args)
                finally:
                    measurements.append((getattr(callback, '__name__', ''),
                                         time.perf_counter() - started))
            return original_after(delay, timed)
        window.after = traced_after
        return measurements

    def test_first_day_selector_never_leaves_a_child_widget_holding_grab(self):
        """R772：真实首日启动期间 grab 只能属于 Toplevel，不能是其子控件。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-grab-safety-') as temporary:
                app, _project = self._startup_app(temporary, remembered=False)
                desktop = Desktop(window, root=app)
                deadline = time.perf_counter() + 1.2
                saw_selector = False
                while time.perf_counter() < deadline:
                    window.update()
                    holder = window.grab_current()
                    self.assertTrue(holder is None or isinstance(holder, tk.Toplevel),
                                    '启动期间 grab 不得落到 Label／Frame／Button 等子控件')
                    saw_selector = saw_selector or any(
                        isinstance(child, tk.Toplevel) and child.winfo_viewable()
                        for child in window.winfo_children())
                    time.sleep(.005)
                self.assertTrue(saw_selector, '首日分支须实际打开项目选择弹窗')
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_empty_project_first_paint_is_bounded(self):
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-first-paint-') as temporary:
                started = time.perf_counter()
                desktop = Desktop(window, root=Path(temporary))
                # 空临时项目会按产品契约弹出“新建项目”流程；该交互不属于首帧，
                # 与启动探针一样在进入 Tk 事件循环前撤销它。
                desktop.startup_controller.cancel()
                window.update_idletasks()
                window.update()
                self.assertLessEqual(time.perf_counter() - started, 4.5)
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_empty_startup_cancel_finishes_loading_and_resumes_tick(self):
        """R1043：真实首帧→项目选择→取消新建不能停留在载入态。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-startup-cancel-') as temporary:
                app = Path(temporary) / 'app'
                app.mkdir()
                (app / 'config.json').write_text(json.dumps({
                    'downloads_root': str(Path(temporary) / 'downloads'),
                }), encoding='utf-8')
                (app / 'projects.json').write_text(json.dumps({
                    'active': None, 'projects': [],
                }), encoding='utf-8')
                cancelled = []
                deadline = time.perf_counter() + 2
                def cancel_new_dialog():
                    dialog = next((child for child in window.winfo_children()
                                   if isinstance(child, tk.Toplevel)
                                   and child.title() == '新建项目'), None)
                    if dialog is not None:
                        cancelled.append(desktop.status.get())
                        dialog.cancel()
                    elif time.perf_counter() < deadline:
                        window.after(10, cancel_new_dialog)
                desktop = Desktop(window, root=app)
                window.update_idletasks()
                window.after(10, cancel_new_dialog)
                self.assertTrue(self._pump_until(window, lambda: bool(cancelled), deadline))
                window.update()
                self.assertEqual(len(cancelled), 1)
                self.assertIn('正在打开今日项目', cancelled[0])
                self.assertNotIn('正在打开今日项目', desktop.status.get())
                self.assertFalse(desktop._startup_project_choice,
                                 '取消后状态：' + desktop.status.get())
                self.assertFalse(desktop._startup_tick_paused)
                self.assertFalse(window._desktop_loading_project)
                self.assertIsNone(desktop.root)
                self.assertEqual(desktop.projects.info['projects'], [])
                self.assertEqual(desktop.page_index, 0)
                self.assertIsNotNone(desktop._tick_id)
                # 后续手动取消不能重写状态或新建项目。
                desktop.status.set('保留当前操作结果')
                with mock.patch('desktop.simpledialog.askstring', return_value=None):
                    desktop.new()
                self.assertEqual(desktop.status.get(), '保留当前操作结果')
                self.assertEqual(desktop.projects.info['projects'], [])
                with mock.patch('desktop.simpledialog.askstring', return_value='取消后新建'):
                    desktop.new()
                self.assertIsNotNone(desktop.root)
                self.assertTrue(desktop.root.is_relative_to(Path(temporary)))
                self.assertFalse(desktop._startup_project_choice)
                selected = desktop.root
                desktop.status.set('保留已打开项目')
                with mock.patch('desktop.simpledialog.askstring', return_value=None):
                    desktop.new()
                self.assertEqual(desktop.root, selected)
                self.assertEqual(desktop.status.get(), '保留已打开项目')
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_empty_startup_cancel_during_shutdown_does_not_resume_tick(self):
        from types import SimpleNamespace
        desktop = SimpleNamespace(
            win=object(), root=None, _startup_project_choice=True,
            shutting_down=True, status=mock.Mock(),
            _request_tick_resume_after_first_paint=mock.Mock())
        with mock.patch('desktop.simpledialog.askstring', return_value=None):
            Desktop.new(desktop)
        self.assertFalse(desktop._startup_project_choice)
        desktop.status.set.assert_not_called()
        desktop._request_tick_resume_after_first_paint.assert_not_called()

    def test_first_event_loop_is_bounded(self):
        """R697 口径：窗口构建完成后首次事件循环不超过 2.6 秒。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-first-event-loop-') as temporary:
                app, _project = self._startup_app(temporary, remembered=False)
                started = time.perf_counter()
                desktop = Desktop(window, root=app)
                window.update_idletasks()
                window.update()
                self.assertLessEqual(time.perf_counter() - started, FIRST_EVENT_LOOP_SECONDS)
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_first_day_selector_is_visible_and_selection_enters_script_within_bound(self):
        """首日：选择框可见；用户确认选择后的项目页停留不应超过 1 秒。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-first-day-choice-') as temporary:
                app, project = self._startup_app(temporary, remembered=False)
                started = time.perf_counter()
                desktop = Desktop(window, root=app)
                popup = None
                def selector_is_visible():
                    nonlocal popup
                    popup = next((child for child in window.winfo_children()
                                  if isinstance(child, tk.Toplevel)), None)
                    return popup is not None and popup.winfo_viewable()
                self.assertTrue(self._pump_until(window, selector_is_visible,
                                                  started + FIRST_DAY_SELECTOR_SECONDS),
                                '首日项目选择框须在启动后 1 秒内可见')
                selected_at = time.perf_counter()
                self.assertTrue(desktop.open_project_or_cleanup(project))
                self.assertEqual(desktop.page_index, 0)
                self.assertEqual(desktop.title.cget('text'), PAGES[0])
                self.assertLessEqual(time.perf_counter() - selected_at, FIRST_DAY_SELECTOR_SECONDS)
                popup.destroy()
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_same_day_auto_resume_leaves_project_page_within_bound(self):
        """同日自动续开：从启动到剧本准备可见壳的项目页停留不超过 1 秒。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-same-day-choice-') as temporary:
                app, _project = self._startup_app(temporary, remembered=True)
                started = time.perf_counter()
                desktop = Desktop(window, root=app)
                self.assertTrue(self._pump_until(
                    window,
                    lambda: (desktop.page_index == 0
                             and desktop.title.cget('text') == PAGES[0]),
                    started + AUTO_RESUME_TO_SCRIPT_SECONDS),
                    '同日自动续开不得在“我的项目”停留超过 1 秒')
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_startup_path_does_not_recurse_directories(self):
        """窗口出现至剧本准备壳可见期间，启动路径不得递归扫描目录。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-startup-no-recurse-') as temporary:
                app, _project = self._startup_app(temporary, remembered=True)
                original_rglob = Path.rglob
                original_walk = os.walk
                recursive_glob = []
                recursive_walk = []
                def count_rglob(path, pattern):
                    recursive_glob.append((path, pattern))
                    return original_rglob(path, pattern)
                def count_walk(*args, **kwargs):
                    recursive_walk.append(traceback.format_stack(limit=12))
                    return original_walk(*args, **kwargs)
                with mock.patch.object(Path, 'rglob', new=count_rglob), \
                     mock.patch('os.walk', new=count_walk):
                    desktop = Desktop(window, root=app)
                    # 此探针只量“打开项目 → 剧本准备可见壳”。进入页面后由
                    # 宠物自动制作触发的分镜盘点是后台生产链，不属于启动路径。
                    desktop.pet_at_stage = lambda index, **kwargs: ''
                    self.assertTrue(self._pump_until(
                        window,
                        lambda: (desktop.page_index == 0
                                 and desktop.title.cget('text') == PAGES[0]),
                        time.perf_counter() + 1.5))
                self.assertEqual(len(recursive_glob), STARTUP_RECURSIVE_SCAN_COUNT)
                self.assertEqual(len(recursive_walk), STARTUP_RECURSIVE_SCAN_COUNT)
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_real_project_page_callback_is_interactive(self):
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-real-project-') as temporary:
                project = Path(temporary)
                # 模拟已有项目而非 root=None 的项目选择页；文件表仍走产品的
                # 异步发现入口，回调本身必须先交还输入区。
                (project / '01剧本准备' / '输入').mkdir(parents=True)
                (project / '01剧本准备' / '输入' / '故事创意_01.md').write_text('故事梗概：测试', encoding='utf-8')
                (project / 'config.json').write_text('{}', encoding='utf-8')
                desktop = Desktop(window, root=project)
                desktop.startup_controller.cancel()
                desktop.projects.info['projects'].append({'name': 'performance', 'path': str(project)})
                desktop.reload()
                # 自动续开必须先交还“剧本准备”的可见壳；完整页面及项目维护
                # 即使变慢，也不能把首屏困在“我的项目 / 正在载入今日项目”。
                original_recovery = desktop._complete_project_recovery
                desktop._complete_project_recovery = lambda target: time.sleep(.35)
                measurements = self._measure_after_callbacks(window)
                desktop.load(project, defer_page=True)
                time.sleep(.12)
                window.update()
                callback_times = [elapsed for name, elapsed in measurements
                                   if name == 'show_loaded_project']
                self.assertEqual(len(callback_times), 1)
                self.assertLessEqual(callback_times[0], .2)
                self.assertNotEqual(str(desktop.status.get()), '正在载入今日项目…',
                                    '项目页回调完成后不得把项目选择页伪装成仍在载入')
                self.assertIn(str(desktop.status.get()),
                              ('正在打开剧本准备…', str(project)))
                # update() 会因宿主机器的消息泵时机选择在本轮或下一轮执行 40ms
                # 回调；无论哪种时机，已由上面的回调耗时锁定“完整建页不在
                # show_loaded_project 内同步执行”。
                deadline=time.perf_counter()+1.5
                while (str(desktop.status.get()) != str(project)
                       and time.perf_counter() < deadline):
                    window.update()
                    time.sleep(.01)
                self.assertEqual(desktop.page_index, 0)
                self.assertEqual(str(desktop.status.get()), str(project))
                desktop._complete_project_recovery = original_recovery
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_startup_stage_entry_waits_for_greeting_but_manual_entry_does_not(self):
        """自动续开的真实 40ms 回调不能越过问候静默门禁。"""
        window = tk.Tk()
        window.withdraw()
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-startup-greeting-') as temporary:
                app, _project = self._startup_app(temporary, remembered=True)
                with mock.patch.object(Desktop, 'writing') as writing:
                    desktop = Desktop(window, root=app)
                    with mock.patch.object(desktop.pet, 'enter_stage', return_value='进页') as enter:
                        self.assertTrue(self._pump_until(
                            window, lambda: writing.called, time.perf_counter() + 2))
                        self.assertIsNotNone(desktop.pet._greet_id)
                        enter.assert_not_called()
                        # 未问候时主动切页仍立即响应。
                        self.assertEqual(desktop.pet_at_stage(0), '进页')
                        enter.assert_called_once_with(0)
                        enter.reset_mock()
                        desktop.pet.cancel_greet()
                        desktop.pet._quiet_until = desktop.pet.clock() + 10
                        self.assertEqual(desktop.pet_at_stage(0, automatic=True), '')
                        enter.assert_not_called()
                        desktop.pet._quiet_until = None
                        self.assertEqual(desktop.pet_at_stage(0, automatic=True), '进页')
                        enter.assert_called_once_with(0)
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            window.destroy()

    def test_startup_script_guard_does_not_leave_tick_paused_after_page_switch(self):
        """40ms 建页守卫失效后，创意历史结果仍须由恢复的 tick 消费。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-startup-tick-') as temporary:
                project = Path(temporary)
                (project / '01剧本准备' / '输入').mkdir(parents=True)
                (project / 'config.json').write_text('{}', encoding='utf-8')
                desktop = Desktop(window, root=project)
                desktop.startup_controller.cancel()
                desktop.projects.info['projects'].append({'name': 'startup-tick', 'path': str(project)})
                desktop.reload()
                # 此场景发生在首帧已呈现、自动续开再延迟 40ms 建页的窗口内。
                window._desktop_first_paint_complete = True
                delivered = []
                desktop.load(project, defer_page=True)
                window.update()
                desktop._brief_load_results.put((desktop._idea_brief_generation, desktop.root,
                                                 lambda path: delivered.append(path), project / 'brief.md', None))
                # 模拟自动续开后的 40ms 窗口内用户换页：延后建页守卫必须 return。
                desktop.page_index = 1
                deadline = time.perf_counter() + .5
                while time.perf_counter() < deadline:
                    window.update()
                    if not desktop._startup_tick_paused and delivered:
                        break
                    time.sleep(.01)
                self.assertFalse(desktop._startup_tick_paused)
                self.assertEqual(delivered, [project / 'brief.md'])
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_real_project_chat_shows_independent_content_before_model_key(self):
        """模型分区键慢时，软件示例仍须先出现，不能把聊天壳卡在空白。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-chat-visible-') as temporary:
                project = Path(temporary)
                (project / '01剧本准备' / '输入').mkdir(parents=True)
                (project / 'config.json').write_text('{}', encoding='utf-8')
                desktop = Desktop(window, root=project)
                desktop.startup_controller.cancel()
                desktop.projects.info['projects'].append({'name': 'chat-visible', 'path': str(project)})
                desktop.reload()
                desktop.load(project)
                window.update()
                desktop._idea_view_model_cache = None
                with mock.patch.object(desktop, 'idea_chat_model', side_effect=lambda: (time.sleep(.35), 'probe')[1]):
                    started = time.perf_counter()
                    desktop.show_conversation()
                while time.perf_counter() - started < CHAT_FIRST_TEXT_SECONDS:
                        window.update()
                        if str(desktop.idea_log.get('1.0', 'end-1c')).strip():
                            break
                        time.sleep(.01)
                self.assertTrue(str(desktop.idea_log.get('1.0', 'end-1c')).strip())
                self.assertLessEqual(time.perf_counter() - started, CHAT_FIRST_TEXT_SECONDS)
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_real_project_startup_does_not_repeat_registry_file_keys(self):
        """真实项目建页的注册表目录键调用须远低于旧查询风暴（2854+）。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-registry-count-') as temporary:
                project = Path(temporary)
                (project / '01剧本准备' / '输入').mkdir(parents=True)
                (project / 'config.json').write_text('{}', encoding='utf-8')
                registry = skill_registry.default_registry()
                registry.scan(force=True)
                calls = []
                original = registry._file_cache_key
                def counted():
                    calls.append(1)
                    return original()
                with mock.patch.object(registry, '_file_cache_key', side_effect=counted):
                    desktop = Desktop(window, root=project)
                    desktop.startup_controller.cancel()
                    desktop.projects.info['projects'].append({'name': 'registry-count', 'path': str(project)})
                    desktop.reload()
                    desktop.load(project)
                    window.update()
                self.assertLessEqual(len(calls), 50)
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass

    def test_idea_chat_model_cold_lookup_is_bounded(self):
        """模型分区键是首屏后台依赖；冷查在测试环境也不得超过 0.5 秒。"""
        try:
            window = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        desktop = None
        try:
            with tempfile.TemporaryDirectory(prefix='desktop-model-key-') as temporary:
                project = Path(temporary)
                (project / 'config.json').write_text('{}', encoding='utf-8')
                desktop = Desktop(window, root=project)
                desktop.startup_controller.cancel()
                started = time.perf_counter()
                desktop.idea_chat_model()
                self.assertLessEqual(time.perf_counter() - started, .5)
        finally:
            if desktop is not None:
                desktop.cancel_timers()
            try:
                window.destroy()
            except tk.TclError:
                pass
