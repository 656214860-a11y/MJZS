"""轮 5B（R3304）：D6 重试判定接线 ＋ D8 ``self.errors`` 可见出口。

- ``pet_agent.retry_plan`` 的「是否重试」以 ``contract.error_codes.classify(text).retryable``
  为唯一权威（G10）；``tasks_round_3300_result.md`` §D6-0 对照表每行一条断言。
- ``ui.pet_agent_rules.VERDICTS`` 只留 ``(action, hint)``，``PATTERNS`` 已删
  （错误文本 → 类目的关键词表唯一权威在 L0 ``error_codes.TEXT_RULES``）。
- ``Pet.errors``／``Agent.errors`` 接可见出口：状态栏左区角标常驻计数＋每条新错误
  一次 ``【警告】`` 播报；同一 ``(名字, 原文)`` 不重复播报。
"""
import unittest
from types import SimpleNamespace

import pet_agent
from contract import error_codes
from test_pet_ui import PetTestCase
from ui import pet_agent_rules

# D6-0 对照表逐行：(探测文本, HTTP 状态, 期望码, 期望类目, 期望 retryable)。
# params 行是唯一行为变化点：现行 VERDICTS retry=True → 接线后 E-NET-CLIENT.retryable=False。
ROWS = (
    ('接口返回 401 Unauthorized', None, 'E-AUTH-REJECTED', 'auth', False),
    ('余额不足，请充值', 402, 'E-QUOTA-EXCEEDED', 'quota', False),
    ('内容审核未通过', None, 'E-CONTENT-POLICY', 'content', False),
    ('参数不合法：size', 400, 'E-NET-CLIENT', 'params', False),
    ('rate limit exceeded', 429, 'E-NET-RATE-LIMIT', 'rate_limit', True),
    ('请求超时，请重试', None, 'E-NET-TIMEOUT', 'timeout', True),
    ('HTTP 503：服务不可用', None, 'E-NET-SERVER', 'server', True),
    ('完全没见过的故障', None, 'E-UNKNOWN', 'unknown', False),
)


class RetryAuthorityTests(unittest.TestCase):
    """D6-d/D6-f：retry_plan 的重试判定与对照表逐行一致。"""

    def test_each_comparison_row_agrees_with_error_codes(self):
        for text, status, code, category, retryable in ROWS:
            with self.subTest(text=text):
                item = error_codes.classify(text, status)
                self.assertEqual(item.code, code)
                self.assertEqual(item.retryable, retryable)
                plan = pet_agent.classify(text, status)
                self.assertEqual(plan['category'], category)
                self.assertEqual(plan['retry'], retryable)
                self.assertEqual(pet_agent.retry_plan(0, text, status=status)['allow'], retryable)

    def test_retryable_rows_back_off_and_non_retryable_rows_stop(self):
        for text, status, _code, _category, retryable in ROWS:
            with self.subTest(text=text):
                plan = pet_agent.retry_plan(1, text, status=status)
                if retryable:
                    self.assertTrue(plan['allow'])
                    self.assertEqual(plan['next_attempt'], 2)
                    self.assertGreater(plan['delay'], 0)
                else:
                    self.assertFalse(plan['allow'])
                    self.assertIsNone(plan['delay'])
                    self.assertEqual(plan['next_attempt'], 1)

    def test_verdicts_carry_only_action_and_hint(self):
        """VERDICTS 瘦身：可重试布尔唯一权威在 error_codes，表里只留 (action, hint)。"""
        self.assertEqual(
            pet_agent_rules.VERDICTS,
            {'timeout': ('backoff', '超时：按 30/60/120 秒退避重试'),
             'rate_limit': ('backoff', '被限流：退避后重试，Pro 自动降级 Flash'),
             'server': ('backoff', '服务端故障：退避后重试'),
             'params': ('fix_params', '参数不合法：先归一尺寸/时长/模型名，再立即重试一次'),
             'content': ('prompt_fix', '命中内容审核：改写提示词后再提，别原样重试'),
             'quota': ('pause', '余额或配额不足：暂停该阶段并通知，不再消耗'),
             'auth': ('notify', '接口密钥无效或没配：到「模型管理」里检查密钥；用 .env 配置的，检查里面的 Key'),
             'unknown': ('notify', '没认出来：先按「重试失败项」，要细节看右键菜单里的「待确认项」')})
        for category, verdict in pet_agent_rules.VERDICTS.items():
            with self.subTest(category=category):
                action, hint = verdict
                self.assertTrue(action)
                self.assertTrue(hint)

    def test_patterns_table_is_gone_classification_lives_in_l0(self):
        self.assertFalse(hasattr(pet_agent_rules, 'PATTERNS'))
        self.assertFalse(hasattr(pet_agent, 'PATTERNS'))
        self.assertEqual([category for category, _code, _marks in error_codes.TEXT_RULES],
                         ['auth', 'quota', 'content', 'params', 'rate_limit', 'timeout', 'server'])


class _FakeStatusBus:
    """最小状态总线：只记 publish 进来的 Message。"""

    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class ErrorsOutletTests(PetTestCase):
    """D8-a：``self.errors`` 的可见出口——角标＋一次性【警告】＋去重。"""

    def _wire(self):
        """给假宿主接上状态栏三件套：总线、左区段、清段；并清空两份 ErrorLog。"""
        bus = _FakeStatusBus()
        segments = {}
        cleared = []
        self.fake.status_bus = bus
        self.fake.set_status_segment = lambda key, text, tooltip=None: segments.__setitem__(
            key, (text, tooltip))
        self.fake.status_bar = SimpleNamespace(clear_segment=lambda key: cleared.append(key))
        self.pet.errors.clear()
        self.pet.agent.errors.clear()
        return bus, segments, cleared

    def test_new_error_shows_badge_and_one_warning(self):
        bus, segments, _cleared = self._wire()
        self.pet.errors.append(('probe', '测试错误一'))
        self.pet.sync_errors()
        self.assertEqual(segments.get('pet_errors', ('',))[0], '异常 1')
        warnings = [message for message in bus.messages if message.level == 'warning']
        self.assertEqual(len(warnings), 1)
        self.assertIn('【警告】', warnings[0].text)
        self.assertIn('probe', warnings[0].text)
        self.assertIn('测试错误一', warnings[0].text)

    def test_same_error_is_not_broadcast_twice(self):
        bus, _segments, _cleared = self._wire()
        self.pet.errors.append(('probe', '重复错误'))
        self.pet.sync_errors()
        self.pet.errors.append(('probe', '重复错误'))
        self.pet.sync_errors()
        self.pet.errors.append(('other', '另一个错误'))
        self.pet.sync_errors()
        texts = [message.text for message in bus.messages]
        self.assertEqual(len(texts), 2)
        self.assertEqual(sum('重复错误' in text for text in texts), 1)
        self.assertTrue(any('另一个错误' in text for text in texts))

    def test_badge_counts_buffered_errors_and_clears_when_empty(self):
        _bus, segments, cleared = self._wire()
        self.pet.errors.append(('a', '甲'))
        self.pet.errors.append(('b', '乙'))
        self.pet.sync_errors()
        self.assertEqual(segments['pet_errors'][0], '异常 2')
        self.pet.errors.clear()
        self.pet.sync_errors()
        self.assertIn('pet_errors', cleared)

    def test_agent_errors_are_surfaced_too(self):
        bus, segments, _cleared = self._wire()
        self.pet.agent.errors.append(('journal', '写日志失败'))
        self.pet.sync_errors()
        self.assertEqual(segments['pet_errors'][0], '异常 1')
        self.assertTrue(any('journal' in message.text and '写日志失败' in message.text
                            for message in bus.messages))

    def test_missing_status_bar_degrades_silently(self):
        """假宿主没接状态栏三件套：不抛异常，记账照旧（可见出口缺位只影响展示）。"""
        self.pet.errors.append(('probe', '静默错误'))
        self.pet.sync_errors()
        self.assertTrue(self.pet.errors)

    def test_pump_drives_the_outlet(self):
        bus, segments, _cleared = self._wire()
        self.pet.errors.append(('pump', '心跳里的错误'))
        self.pet.pump()
        self.assertTrue(any('心跳里的错误' in message.text for message in bus.messages))
        self.assertEqual(segments['pet_errors'][0], '异常 1')


if __name__ == '__main__':
    unittest.main()
