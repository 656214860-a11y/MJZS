"""app_logging: 根日志落盘并脱敏，主线程/后台线程/Tk 回调异常都被接管，且启动入口已接线。"""
import faulthandler
import logging
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import app_logging
import diagnostic_capture

ROOT = Path(__file__).resolve().parents[2]


class AppLoggingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (sys.excepthook, threading.excepthook, list(logging.getLogger().handlers),
                      logging.getLogger().level, app_logging._installed)
        patches = [mock.patch.object(app_logging, 'LOGS', self.tmp),
                   mock.patch.object(app_logging, 'APP_LOG', self.tmp / 'app.log'),
                   mock.patch.object(app_logging, 'FAULT_LOG', self.tmp / 'faulthandler.log'),
                   mock.patch.object(diagnostic_capture, 'ERROR_LOG', self.tmp / '启动错误.log'),
                   mock.patch.object(diagnostic_capture, 'LOGS', self.tmp),
                   mock.patch.object(diagnostic_capture, 'STATE_FILE', self.tmp / 'latest.json')]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        app_logging._installed = False

    def tearDown(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            if handler not in self.saved[2]:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(self.saved[3])
        sys.excepthook, threading.excepthook = self.saved[0], self.saved[1]
        app_logging._installed = self.saved[4]
        faulthandler.disable()
        if app_logging._fault_stream:
            app_logging._fault_stream.close()
            app_logging._fault_stream = None

    def _flush(self):
        for handler in logging.getLogger().handlers:
            handler.flush()

    def test_logs_are_written_and_redacted(self):
        self.assertTrue(app_logging.install())
        logging.getLogger('demo').warning('调用失败 api_key=SECRET123 已重试')
        self._flush()
        text = (self.tmp / 'app.log').read_text(encoding='utf-8')
        self.assertIn('调用失败', text)
        self.assertNotIn('SECRET123', text)

    def test_install_is_idempotent(self):
        app_logging.install()
        count = len(logging.getLogger().handlers)
        app_logging.install()
        self.assertEqual(len(logging.getLogger().handlers), count)

    def test_thread_exception_is_captured(self):
        app_logging.install(crash_sink=diagnostic_capture.record_crash)
        def boom():
            raise ValueError('线程炸了 token=ABC999')
        thread = threading.Thread(target=boom, name='worker-x')
        thread.start()
        thread.join()
        self._flush()
        text = (self.tmp / 'app.log').read_text(encoding='utf-8')
        self.assertIn('thread:worker-x', text)
        self.assertIn('线程炸了', text)
        self.assertNotIn('ABC999', text)
        self.assertIn('线程炸了', (self.tmp / '启动错误.log').read_text(encoding='utf-8'))

    def test_tk_callback_hook_chains_previous(self):
        class Root:
            seen = None
            def report_callback_exception(self, kind, value, trace):
                Root.seen = value
        root = Root()
        app_logging.install(root)
        error = RuntimeError('回调出错')
        root.report_callback_exception(RuntimeError, error, None)
        self._flush()
        self.assertIs(Root.seen, error)
        self.assertIn('tk-callback', (self.tmp / 'app.log').read_text(encoding='utf-8'))

    def test_swallowed_logs_location_once_then_samples(self):
        app_logging.install()
        app_logging._swallow_counts.clear()
        for _ in range(app_logging.SWALLOW_LOG_EVERY + 1):
            try:
                raise KeyError('缺键 token=Z777')
            except KeyError:
                app_logging.swallowed()
        self._flush()
        text = (self.tmp / 'app.log').read_text(encoding='utf-8')
        self.assertEqual(text.count('已忽略 KeyError'), 2)
        self.assertIn('test_app_logging.py', text)
        self.assertNotIn('Z777', text)

    def test_swallowed_outside_except_is_noop(self):
        app_logging.install()
        app_logging.swallowed()

    def test_timed_records_metrics_and_warns_only_when_slow(self):
        app_logging.install()
        app_logging._metrics.clear()
        with app_logging.timed('fast', 10000):
            pass
        with app_logging.timed('slow', 0):
            pass
        self._flush()
        text = (self.tmp / 'app.log').read_text(encoding='utf-8')
        self.assertIn('慢操作 slow', text)
        self.assertNotIn('慢操作 fast', text)
        snap = app_logging.metrics_snapshot()
        self.assertEqual(snap['fast']['count'], 1)
        self.assertEqual(snap['slow']['slow'], 1)

    def test_timed_decorator_is_reentrant_and_transparent(self):
        app_logging._metrics.clear()
        @app_logging.timed('rec', 10000)
        def fact(n):
            return 1 if n <= 1 else n * fact(n - 1)
        self.assertEqual(fact(5), 120)
        self.assertEqual(app_logging.metrics_snapshot()['rec']['count'], 5)
        with self.assertRaises(ValueError):
            with app_logging.timed('err', 10000):
                raise ValueError('x')

    def test_flush_metrics_writes_json(self):
        app_logging._metrics.clear()
        with mock.patch.object(app_logging, 'PERF_FILE', self.tmp / 'perf.json'):
            with app_logging.timed('page', 10000):
                pass
            app_logging.flush_metrics()
        self.assertIn('page', (self.tmp / 'perf.json').read_text(encoding='utf-8'))

    def test_page_switch_and_model_http_are_instrumented(self):
        program = Path(__file__).resolve().parents[1]
        self.assertIn("@app_logging.timed('page.show'", (program / 'desktop.py').read_text(encoding='utf-8'))
        self.assertIn("@app_logging.timed('model.http'", (program / 'model_pool.py').read_text(encoding='utf-8'))

    def test_real_launcher_installs_hooks(self):
        source = (ROOT / '启动漫剧制作助手.pyw').read_text(encoding='utf-8')
        self.assertIn('app_logging.install(crash_sink=', source)
        self.assertIn('app_logging.install(window)', source)

    def test_startup_failure_log_appends_with_header(self):
        source = (ROOT / '启动漫剧制作助手.pyw').read_text(encoding='utf-8')
        self.assertNotIn("log.write_text(traceback.format_exc()", source)
        self.assertIn('old+header+traceback.format_exc()', source)


if __name__ == '__main__':
    unittest.main()
