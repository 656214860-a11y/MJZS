# -*- coding: utf-8 -*-
"""模型调用错误的 kind 分类：传输层归类、pet_llm／model_router 透传、桌面文案分支。

只覆盖本轮新增的受控错误类别，不重复既有重试/降级用例。
"""
import ast
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import model_pool
import model_router
import pet_llm


class _Opener:
    """只负责在 open() 时抛出指定异常，模拟网络栈。"""

    def __init__(self, exc):
        self.exc = exc

    def open(self, request, timeout=None):
        raise self.exc


def _transport_failure(exc):
    with patch.object(model_pool, '_http_opener', lambda: _Opener(exc)):
        return model_pool.http_transport('https://provider.invalid/v1/chat/completions',
                                         {'input': 'x'}, {'Authorization': 'Bearer x'}, 3)


def _http_error(status, body=b'{"error":"boom"}'):
    return urllib.error.HTTPError('https://provider.invalid/v1', status, 'err', {}, io.BytesIO(body))


def _env_dir(td, key='sk-test-123456'):
    (Path(td) / '.env').write_text('DEEPSEEK_API_KEY=' + key + '\n', encoding='utf-8')
    return Path(td)


class _Fake:
    """假传输：按顺序回放结果，并记下发出去的请求。"""

    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.calls = []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append(url)
        if self.replies:
            return self.replies.pop(0)
        return {'ok': True, 'status': 200, 'data': {'usage': {'prompt_tokens': 10, 'completion_tokens': 2,
                                                              'prompt_cache_hit_tokens': 8}}}


class HttpTransportKindTests(unittest.TestCase):
    """问题一：http_transport 捕获处新增 kind，不改 error／status。"""

    def test_auth_status_is_auth_kind(self):
        for status in (401, 403):
            with self.subTest(status=status):
                result = _transport_failure(_http_error(status))
                self.assertEqual(result['kind'], 'auth')
                self.assertEqual(result['status'], status)
                self.assertIn('HTTP ' + str(status), result['error'])

    def test_server_status_is_server_kind(self):
        result = _transport_failure(_http_error(503))
        self.assertEqual(result['kind'], 'server')
        self.assertEqual(result['status'], 503)

    def test_other_http_status_is_client_kind(self):
        for status in (400, 404, 422):
            with self.subTest(status=status):
                self.assertEqual(_transport_failure(_http_error(status))['kind'], 'client')

    def test_url_error_is_network_kind(self):
        result = _transport_failure(urllib.error.URLError('unreachable'))
        self.assertEqual(result['kind'], 'network')
        self.assertEqual(result['status'], 0)
        self.assertIn('URLError', result['error'])

    def test_plain_exception_is_bug_kind(self):
        result = _transport_failure(RuntimeError('kaboom'))
        self.assertEqual(result['kind'], 'bug')
        self.assertIn('RuntimeError', result['error'])

    def test_error_and_status_fields_are_unchanged(self):
        result = _transport_failure(_http_error(500, b'{"detail":"x"}'))
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 500)
        self.assertEqual(result['error'], 'HTTP 500：{"detail":"x"}')


class PetLlmKindTests(unittest.TestCase):
    """问题二：pet_llm.ask 的预算早退／reply／外层异常都带 kind。"""

    def test_budget_early_exit_carries_budget_kind(self):
        with tempfile.TemporaryDirectory() as td:
            fake = _Fake()
            client = pet_llm.Client(program=_env_dir(td), transport=fake,
                                    config={'budget': {'tokens_per_day': 1}})
            client.ledger.record('deepseek-v4-flash',
                                 {'prompt_tokens': 5, 'completion_tokens': 5, 'cached_tokens': 0},
                                 at=pet_llm.time.time())
            result = client.ask('intent.route', '继续')
            self.assertEqual(result['kind'], 'budget')
            self.assertTrue(result['budget'])
            self.assertEqual(fake.calls, [])

    def test_transport_kind_is_passed_through(self):
        with tempfile.TemporaryDirectory() as td:
            fake = _Fake([{'ok': False, 'status': 503, 'kind': 'server', 'error': 'HTTP 503：服务不可用'}])
            result = pet_llm.Client(program=_env_dir(td), transport=fake).ask('intent.route', '继续')
            self.assertFalse(result['ok'])
            self.assertEqual(result['kind'], 'server')

    def test_unexpected_exception_is_logged_and_marked_bug(self):
        def boom(url, payload, headers, timeout):
            raise RuntimeError('kaboom')
        with tempfile.TemporaryDirectory() as td:
            client = pet_llm.Client(program=_env_dir(td), transport=boom)
            with self.assertLogs('pet_llm', level='ERROR') as captured:
                result = client.ask('intent.route', '继续')
            self.assertEqual(result['kind'], 'bug')
            self.assertIn('RuntimeError', result['error'])
            self.assertTrue(any('kaboom' in line for line in captured.output))


class RouterKindPassthroughTests(unittest.TestCase):
    """补齐链路：model_router 适配器不丢传输层的 kind。"""

    class _Adapter(model_router.ModelAdapter):
        provider = 'Test'
        key_env = 'TEST_KEY'
        base_url = 'https://example.invalid/v1'
        models = {'test-model': {}}

    def test_transport_kind_reaches_the_adapter_result(self):
        def transport(url, payload, headers, timeout):
            return {'ok': False, 'status': 503, 'kind': 'server', 'error': 'HTTP 503：boom'}
        result = self._Adapter(transport=transport, key='sk-test').chat(
            [{'role': 'user', 'content': 'hi'}], {'max_tokens': 5}, model='test-model')
        self.assertFalse(result['ok'])
        self.assertEqual(result['kind'], 'server')
        self.assertEqual(result['error'], 'HTTP 503：boom')

    def test_adapter_exception_is_bug_kind(self):
        def transport(url, payload, headers, timeout):
            raise RuntimeError('kaboom')
        result = self._Adapter(transport=transport, key='sk-test').chat(
            [{'role': 'user', 'content': 'hi'}], {'max_tokens': 5}, model='test-model')
        self.assertEqual(result['kind'], 'bug')


class DesktopMessageBranchTests(unittest.TestCase):
    """问题三：桌面按 kind 分支展示，缺失（旧记录）落内部错误文案。"""

    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / 'desktop.py'
        # R1490：model_error_display 已迁到 desktop_idea_chat（desktop 重新导入），按全部 Desktop 源码查找
        from tests.architecture._scan import desktop_text
        tree = ast.parse(desktop_text())
        funcs = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == 'model_error_display']
        assert len(funcs) == 1, '桌面文案映射函数应只定义一次'
        cls.namespace = {}
        exec(compile(ast.Module(body=funcs, type_ignores=[]), str(source), 'exec'), cls.namespace)

    def display(self, payload):
        return self.namespace['model_error_display'](payload)

    def test_network_and_server_show_retry_text(self):
        for kind in ('network', 'server'):
            with self.subTest(kind=kind):
                text, log_only = self.display({'kind': kind, 'error': 'HTTP 503：内部细节'})
                self.assertEqual(text, '模型暂时无法响应，请稍后重试')
                self.assertTrue(log_only)

    def test_auth_budget_client_keep_the_raw_text(self):
        for kind in ('auth', 'budget', 'client'):
            with self.subTest(kind=kind):
                text, log_only = self.display({'kind': kind, 'error': '原始提示'})
                self.assertEqual(text, '原始提示')
                self.assertFalse(log_only)

    def test_bug_and_missing_kind_show_internal_text(self):
        for payload in ({'kind': 'bug', 'error': 'x'}, {'error': '旧记录'}):
            with self.subTest(payload=payload):
                text, log_only = self.display(payload)
                self.assertEqual(text, '系统内部错误，已记录日志')
                self.assertTrue(log_only)


class IdeaApiReceivedTests(unittest.TestCase):
    """直连 API 回复落地：失败文案与弹窗标题、空回复、剧本已保存后的刷新与播报。"""

    def receive(self, result):
        from unittest import mock
        import desktop_idea_chat
        host = mock.Mock()
        host.idea_chat_controller.finish_request.return_value = True
        host.idea_send.winfo_exists.return_value = True
        host.pet.auto.active = None
        with (patch('idea_chat.append'),
              patch('writing_api.preparation_reply_message', return_value='')):
            desktop_idea_chat.IdeaChatMixin._idea_api_received(
                host, 'T', 'M', {'settings': {'skill_injection': None}}, result)
        return host

    def test_failures_pick_text_and_dialog_title_by_kind(self):
        with self.assertLogs('desktop_idea_chat', level='WARNING'):
            host = self.receive({'ok': False, 'error': 'e', 'kind': 'network'})
        host.status.set.assert_called_once_with('模型暂时无法响应，请稍后重试')
        host.notifier.error.assert_called_once_with('模型暂时无法响应，请稍后重试', title='模型调用失败')
        with self.assertLogs('desktop_idea_chat', level='WARNING'):
            host = self.receive({'ok': False, 'error': '超过模型上下文', 'kind': 'weird'})
        host.notifier.error.assert_called_once_with('系统内部错误，已记录日志', title='请求校验未通过')

    def test_empty_reply_explains_why(self):
        import idea_chat
        host = self.receive({'ok': True, 'text': '  '})
        message = idea_chat.why_empty({'ok': True, 'text': '  '})
        host.notifier.error.assert_called_once_with(message, title='模型调用失败')
        host.status.set.assert_called_once_with(message)

    def test_saved_script_refreshes_list_reports_and_shows_quality(self):
        host = self.receive({'ok': True, 'text': 'x', 'script_raw_path': 'r',
                             'natural_script_path': 'n', 'quality_summary': 'q'})
        host.refresh_script_list.assert_called_once_with()
        self.assertEqual('script', host.pet_report.call_args.args[0])
        self.assertEqual(2, host.show_script_quality.call_count)
        host.status.set.assert_not_called()
        host = self.receive({'ok': True, 'text': 'x', 'script_raw_path': 'r', 'quality_passed': False})
        host.pet_report.assert_not_called()
        host = self.receive({'ok': True, 'text': 'x', 'natural_script_path': 'n'})
        host.status.set.assert_called_once_with('自然剧本已自动保存：n')


if __name__ == '__main__':
    unittest.main()
