"""界面四个兜底入口的报错文字统一经 error_codes.user_text（EC-2；EC-B1、EC-B2、EC-B3）。

四个入口：Desktop.safe()、PageNavMixin.go()、App.safe()、AsyncTasksMixin._async_failed()。
未分类的程序原文不给用户看，中文提示原样，带错误代码的基础层异常显示码表说明；
Desktop.safe()、go() 与 App.safe() 把原始异常交给诊断记录，go() 与 App.safe() 先记录再提示，
记录自己出错不影响提示。
全部用假对象直接调未绑定的方法，不建窗口。
"""
import unittest
from types import SimpleNamespace
from unittest import mock

import app
import desktop
from contract import error_codes
from contract.infra_errors import StorageError
from ui.desktop_async_tasks import AsyncTasksMixin
from ui.desktop_page_nav import PageNavMixin
from ui.desktop_page_registry import ACCOUNT_TITLE, PAGE_ACCOUNT

RAW = "'NoneType' object has no attribute 'state'"
UNKNOWN = error_codes.describe('E-UNKNOWN')
RECORD = 'infra.diagnostic_capture.record_degradation'
PROJECT = 'P:/示例项目'


def _raising(error):
    def run():
        raise error
    return run


def _order_of(host, record):
    """让记录和提示各留一个记号，返回这张先后顺序表。"""
    order = []
    record.side_effect = lambda *args, **kwargs: order.append('record')
    host.notifier.error.side_effect = lambda *args, **kwargs: order.append('prompt')
    return order


def _desktop_host():
    return SimpleNamespace(worker=None, notifier=mock.Mock(), page_index=0, root='')


class DesktopSafeTests(unittest.TestCase):
    def test_unclassified_error_shows_the_code_and_records_the_original(self):
        host = _desktop_host()
        error = AttributeError(RAW)
        with mock.patch(RECORD) as record:
            desktop.Desktop.safe(host, _raising(error))
        host.notifier.error.assert_called_once_with(UNKNOWN)
        self.assertNotIn('NoneType', host.notifier.error.call_args.args[0])
        record.assert_called_once()
        self.assertIs(record.call_args.args[0], error)

    def test_chinese_message_is_shown_unchanged(self):
        host = _desktop_host()
        with mock.patch(RECORD):
            desktop.Desktop.safe(host, _raising(ValueError('当前操作尚未结束，请稍后')))
        host.notifier.error.assert_called_once_with('当前操作尚未结束，请稍后')

    def test_coded_infra_error_shows_the_code_description(self):
        host = _desktop_host()
        with mock.patch(RECORD):
            desktop.Desktop.safe(host, _raising(StorageError('', code='E-IO-READ')))
        host.notifier.error.assert_called_once_with(error_codes.describe('E-IO-READ'))


class GoTests(unittest.TestCase):
    def host(self, error):
        return SimpleNamespace(show=mock.Mock(side_effect=error), notifier=mock.Mock(),
                               page_index=0, root='')

    def test_page_failure_shows_the_code_keeps_the_title_and_records_the_original(self):
        error = AttributeError(RAW)
        host = self.host(error)
        with mock.patch(RECORD) as record:
            PageNavMixin.go(host, 3)
        host.show.assert_called_once_with(3, video_mode=None)
        host.notifier.error.assert_called_once_with(UNKNOWN, title='页面无法显示')
        record.assert_called_once()
        self.assertIs(record.call_args.args[0], error)

    def test_failing_record_does_not_block_the_prompt(self):
        host = self.host(AttributeError(RAW))
        with mock.patch(RECORD, side_effect=OSError('disk full')):
            PageNavMixin.go(host, 3)
        host.notifier.error.assert_called_once_with(UNKNOWN, title='页面无法显示')

    def test_record_happens_before_the_prompt(self):
        host = self.host(AttributeError(RAW))
        with mock.patch(RECORD) as record:
            order = _order_of(host, record)
            PageNavMixin.go(host, 3)
        self.assertEqual(order, ['record', 'prompt'])

    def test_account_page_is_recorded_by_its_title(self):
        """会员账户页不在 PAGES 里：记录要用 page_title 取名，不能按序号去 PAGES 里取。"""
        host = self.host(AttributeError(RAW))
        host.page_index, host.root, host._startup_project_choice = PAGE_ACCOUNT, PROJECT, True
        with mock.patch(RECORD) as record:
            PageNavMixin.go(host, PAGE_ACCOUNT)
        self.assertEqual(record.call_args.kwargs,
                         {'page': ACCOUNT_TITLE, 'project': PROJECT, 'automatic_daily_open': True})
        host.notifier.error.assert_called_once_with(UNKNOWN, title='页面无法显示')


def _app_host(**changes):
    return SimpleNamespace(**{'busy': False, 'notifier': mock.Mock(), 'root': PROJECT, **changes})


class AppSafeTests(unittest.TestCase):
    def test_unclassified_error_shows_the_code_and_records_the_original(self):
        host = _app_host()
        error = AttributeError(RAW)
        with mock.patch(RECORD) as record:
            app.App.safe(host, _raising(error))
        host.notifier.error.assert_called_once_with(UNKNOWN, title='提示')
        self.assertNotIn('NoneType', host.notifier.error.call_args.args[0])
        record.assert_called_once()
        self.assertIs(record.call_args.args[0], error)
        self.assertEqual(record.call_args.kwargs,
                         {'page': '视频生成', 'stage': 'app.safe', 'project': PROJECT})

    def test_record_happens_before_the_prompt(self):
        host = _app_host()
        with mock.patch(RECORD) as record:
            order = _order_of(host, record)
            app.App.safe(host, _raising(AttributeError(RAW)))
        self.assertEqual(order, ['record', 'prompt'])

    def test_failing_record_does_not_block_the_prompt(self):
        host = _app_host()
        with mock.patch(RECORD, side_effect=OSError('disk full')):
            app.App.safe(host, _raising(AttributeError(RAW)))
        host.notifier.error.assert_called_once_with(UNKNOWN, title='提示')

    def test_chinese_message_is_shown_unchanged(self):
        host = _app_host()
        with mock.patch(RECORD):
            app.App.safe(host, _raising(ValueError('请先选择镜头')))
        host.notifier.error.assert_called_once_with('请先选择镜头', title='提示')

    def test_busy_notice_is_shown_unchanged_and_the_action_does_not_run(self):
        host = _app_host(busy=True)
        action = mock.Mock()
        with mock.patch(RECORD):
            app.App.safe(host, action)
        action.assert_not_called()
        host.notifier.error.assert_called_once_with('正在执行操作，请稍后', title='提示')


class AsyncFailedTests(unittest.TestCase):
    def host(self):
        return SimpleNamespace(_idea_requesting=False, update_script_interrupt_button=mock.Mock(),
                               clear_thinking=mock.Mock(), notifier=mock.Mock())

    def test_raw_text_shows_the_code(self):
        host = self.host()
        AsyncTasksMixin._async_failed(host, RAW)
        host.notifier.error.assert_called_once_with(UNKNOWN, title='操作未完成')
        self.assertNotIn('NoneType', host.notifier.error.call_args.args[0])

    def test_exception_object_shows_the_code(self):
        host = self.host()
        AsyncTasksMixin._async_failed(host, AttributeError(RAW))
        host.notifier.error.assert_called_once_with(UNKNOWN, title='操作未完成')

    def test_chinese_text_is_shown_unchanged(self):
        host = self.host()
        AsyncTasksMixin._async_failed(host, '断线')
        host.notifier.error.assert_called_once_with('断线', title='操作未完成')


if __name__ == '__main__':
    unittest.main()
