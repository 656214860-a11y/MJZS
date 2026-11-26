"""源码文本契约锁（REQ-ARCH-SRC）：这些约束只能从源码文本判断，统一放在架构门禁里。

原先散落在功能测试里的 `inspect.getsource` 断言迁到此处，断言内容未动：
测试执行器的超时回收／心跳／跳过汇总写法，切页不强制 Tk 空闲队列，
书写页不得恢复滚动动画，项目回收文案不得声称"永久清除"。
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))


class SelftestRunnerContracts(unittest.TestCase):
    def test_serial_runner_has_recoverable_timeout(self):
        import run_selftests
        source = inspect.getsource(run_selftests.run_serial)
        self.assertIn('result_reader.poll(timeout)', source)
        self.assertIn('process.terminate()', source)

    def test_serial_runner_drains_result_before_waiting_for_child_exit(self):
        import run_selftests
        source = inspect.getsource(run_selftests.run_serial)
        self.assertLess(source.index('result_reader.poll(timeout)'), source.index('process.join(10)'))

    def test_parallel_runner_reports_heartbeat_while_waiting(self):
        import run_selftests
        source = inspect.getsource(run_selftests.run_units)
        self.assertIn('futures.wait(', source)
        self.assertIn('HEARTBEAT_SECONDS', source)
        self.assertIn('并行回归仍在执行', source)

    def test_parallel_runner_recovers_after_no_progress_timeout(self):
        import run_selftests
        source = inspect.getsource(run_selftests.run_units)
        self.assertIn('SAFE_UNIT_TIMEOUT', source)
        self.assertIn('process.terminate()', source)
        self.assertIn('并行池连续', source)

    def test_skip_report_is_printed_in_the_summary(self):
        import run_selftests
        source = inspect.getsource(run_selftests.main)
        self.assertIn('skip_summary(got)', source)
        self.assertIn('实际跳过', source)

    def test_incremental_flag_is_an_explicit_cli_option(self):
        import run_selftests
        source = inspect.getsource(run_selftests.main)
        self.assertIn("arg == '--incremental'", source)


class DesktopSourceContracts(unittest.TestCase):
    def test_page_switch_does_not_force_the_tk_idle_loop(self):
        """切页只排合并布局，不能在主线程强制跑完整个 Tk 空闲队列。"""
        from desktop import Desktop
        source = inspect.getsource(Desktop.show)
        self.assertNotIn('update_idletasks', source, '切页不得同步执行完整 Tk 空闲队列')
        self.assertIn('self.fit_content()', source, '切页后必须安排既有的合并空闲布局')

    def test_script_page_measurement_stays_in_the_idle_layout_batch(self):
        """剧本准备页面的固定高度测量留在合并的空闲布局批次。"""
        from desktop import Desktop
        import desktop_writing_page
        source = ''.join(inspect.getsource(cls) for cls in Desktop.__mro__ if cls is not object)
        source += inspect.getsource(desktop_writing_page._WritingPage)
        self.assertIn('def measure_page_fixed', source, '固定高度应在空闲布局批次测量')
        start = source.index('def measure_page_fixed')
        measured = source[start:source.index('def fit_talk', start)]
        self.assertNotIn('update_idletasks', measured, '剧本准备固定高度测量不得同步耗尽 Tk 空闲队列')

    def test_page_shortcut_is_bound_on_the_main_window(self):
        import desktop
        source = inspect.getsource(desktop)
        self.assertIn("self.page_shortcut", source)
        self.assertIn("<Control-Prior>", source)

    def test_writing_input_hint_does_not_return_to_scroll_animation(self):
        import desktop as desktop_module
        writing_source = inspect.getsource(desktop_module.Desktop.writing)
        self.assertNotIn('scroll_input_hint', writing_source, "输入提示不得恢复滚动实现")
        self.assertNotIn('after(35', writing_source, "输入提示不得持续投递动画回调")

    def test_recycle_copy_is_recoverable_and_separate_from_permanent(self):
        import desktop
        confirm_source = inspect.getsource(desktop.Desktop._choose_project_dialog)
        self.assertIn('不是永久清除', confirm_source)
        self.assertIn('回收不等于释放空间', confirm_source)
        home_source = inspect.getsource(desktop.Desktop.project_home)
        self.assertIn('重建项目索引', home_source)
        self.assertIn('不是永久清除', home_source)

    def test_missing_directory_notice_does_not_claim_files_were_deleted(self):
        import desktop
        source = inspect.getsource(desktop.Desktop._choose_project_dialog)
        self.assertNotIn('剧本已被删除', source)
        self.assertNotIn('清理残留文件夹', source)
        self.assertIn('只清除登记，不动磁盘', source)


if __name__ == '__main__':
    unittest.main()
