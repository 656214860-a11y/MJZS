"""界面四个兜底入口的报错文字统一经 error_codes.user_text（EC-2；EC-B1、EC-B2、EC-B3）。

四个入口：Desktop.safe()、PageNavMixin.go()、App.safe()、AsyncTasksMixin._async_failed()。
未分类的程序原文不给用户看，中文提示原样，带错误代码的基础层异常显示码表说明；
Desktop.safe() 与 go() 把原始异常交给诊断记录，记录自己出错不影响提示。
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

RAW = "'NoneType' object has no attribute 'state'"
UNKNOWN = error_codes.describe('E-UNKNOWN')
RECORD = 'infra.diagnostic_capture.record_degradation'


def _raising(error):
    def run():
        raise error
    return run


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


class AppSafeTests(unittest.TestCase):
    def test_unclassified_error_shows_the_code(self):
        host = SimpleNamespace(busy=False, notifier=mock.Mock())
        app.App.safe(host, _raising(AttributeError(RAW)))
        host.notifier.error.assert_called_once_with(UNKNOWN, title='提示')
        self.assertNotIn('NoneType', host.notifier.error.call_args.args[0])


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
