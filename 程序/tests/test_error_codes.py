import os
import tempfile
import unittest

from contract import error_codes
from contract.diagnostics import Severity
from contract.error_codes import (CODES, SEVERITIES, ErrorCode, analyze, code_data,
                                  code_of, classify, describe, from_http_result, lookup,
                                  TEXT_RULES)
from contract.infra_errors import StorageError
from contract.service_contract import ServiceResult, SystemError, UserError, success


class ErrorCodesTests(unittest.TestCase):
    def test_every_code_is_complete_and_well_formed(self):
        self.assertGreaterEqual(len(CODES), 10)
        self.assertLessEqual(len(CODES), 30)
        for key, item in CODES.items():
            self.assertRegex(key, r'^E-[A-Z]+(-[A-Z]+)*$')
            self.assertEqual(key, item.code)
            self.assertTrue(item.user_message and item.remedy, key)

    def test_unknown_code_falls_back_instead_of_raising(self):
        self.assertEqual(lookup('E-NOPE').code, 'E-UNKNOWN')
        self.assertEqual(lookup(None).code, 'E-UNKNOWN')
        self.assertIn('E-NET-TIMEOUT', describe('E-NET-TIMEOUT'))

    def test_network_codes_are_retryable_and_client_errors_are_not(self):
        self.assertTrue(lookup('E-NET-TIMEOUT').retryable)
        self.assertFalse(lookup('E-NET-CLIENT').retryable)

    def test_error_code_travels_in_data_without_changing_result_fields(self):
        self.assertEqual(tuple(ServiceResult.__dataclass_fields__), ('ok', 'reason', 'recoverable', 'data'))
        failed = UserError('缺图', data=code_data('E-ASSET-MISSING', shot=3))
        self.assertEqual(code_of(failed), 'E-ASSET-MISSING')
        self.assertEqual(failed.data['shot'], 3)
        self.assertEqual(code_of(success()), '')
        self.assertEqual(code_of(SystemError('x', data=code_data('E-BOGUS'))), 'E-UNKNOWN')


    def test_http_transport_results_map_to_codes(self):
        self.assertEqual(from_http_result({'ok': True}), '')
        self.assertEqual(from_http_result({'ok': False, 'status': 429, 'error_class': 'client'}), 'E-NET-RATE-LIMIT')
        self.assertEqual(from_http_result({'ok': False, 'status': 401, 'error_class': 'auth'}), 'E-AUTH-REJECTED')
        self.assertEqual(from_http_result({'ok': False, 'status': 503, 'error_class': 'server'}), 'E-NET-SERVER')
        self.assertEqual(from_http_result({'ok': False, 'status': 0, 'error_class': 'network',
                                           'error': 'TimeoutError：timed out'}), 'E-NET-TIMEOUT')
        self.assertEqual(from_http_result({'ok': False, 'status': 0, 'error_class': 'network', 'error': 'refused'}), 'E-NET-UNREACHABLE')
        self.assertEqual(from_http_result({'ok': False, 'error_class': 'bug'}), 'E-UNKNOWN')

    def test_every_code_declares_severity_in_the_closed_set(self):
        # K8：severity 闭集唯一权威是 contract.diagnostics.Severity 五值枚举，
        # SEVERITIES 由枚举派生、不再是字符串字面量闭集；旧 recoverable 已删。
        self.assertEqual(SEVERITIES, frozenset({'fatal', 'error', 'warn', 'degraded', 'info'}))
        for key, item in CODES.items():
            with self.subTest(code=key):
                self.assertIsInstance(item.severity, Severity)
                self.assertIn(item.severity.value, SEVERITIES)

    def test_severity_spot_values_reflect_user_impact(self):
        self.assertEqual(lookup('E-CANCELLED').severity, Severity.INFO)
        self.assertEqual(lookup('E-TOOL-MISSING').severity, Severity.DEGRADED)
        self.assertEqual(lookup('E-CONTRACT-VIOLATION').severity, Severity.DEGRADED)
        self.assertEqual(lookup('E-NET-TIMEOUT').severity, Severity.WARN)
        self.assertEqual(lookup('E-AUTH-MISSING').severity, Severity.WARN)

    def test_error_code_rejects_unregistered_severity(self):
        with self.assertRaises(ValueError):
            ErrorCode('E-TEST', 'bogus', False, 'msg', 'fix')

    def test_analyze_returns_first_non_none_hit(self):
        failure = RuntimeError('boom')
        first = lookup('E-NET-TIMEOUT')
        second = lookup('E-AUTH-MISSING')
        hit = analyze(failure, (lambda exc: first, lambda exc: second))
        self.assertIs(hit, first)

    def test_analyze_skips_none_and_falls_back_to_unknown(self):
        failure = RuntimeError('boom')
        self.assertEqual(analyze(failure, ()).code, 'E-UNKNOWN')
        self.assertEqual(analyze(failure, (lambda exc: None,)).code, 'E-UNKNOWN')
        hit = analyze(failure, (lambda exc: None, lambda exc: lookup('E-AUTH-REJECTED')))
        self.assertEqual(hit.code, 'E-AUTH-REJECTED')

    def test_analyze_swallows_analyzer_errors_without_masking_failure(self):
        failure = RuntimeError('original startup failure')

        def broken(exc):
            raise ValueError('analyzer bug')

        hit = analyze(failure, (broken, lambda exc: lookup('E-NET-SERVER')))
        self.assertEqual(hit.code, 'E-NET-SERVER')
        self.assertEqual(analyze(failure, (broken,)).code, 'E-UNKNOWN')
        # 原始失败对象不被吞掉：调用方仍持有它
        self.assertIsInstance(failure, RuntimeError)
        self.assertEqual(str(failure), 'original startup failure')


class ClassifyTextTests(unittest.TestCase):
    """轮 5A D6：``classify(text)`` 错误文本 → ``ErrorCode`` 分类器。

    关键词表 ``TEXT_RULES`` 自 ``ui.pet_agent_rules.PATTERNS`` 迁入（顺序即优先级）；
    轮 5B 起 PATTERNS 已删、「是否重试」以码的 ``retryable`` 为唯一权威（G10），
    ``pet_agent.retry_plan`` 的接线断言见 ``test_pet_agent_error_wiring.py``。
    """

    # 对照表逐行：(探测文本, 期望码, 期望 retryable)。params→E-NET-CLIENT 是
    # 唯一与现行 VERDICTS 不一致的行（现行 retry=True，接线后=False）。
    ROWS = (
        ('接口返回 401 Unauthorized', 'E-AUTH-REJECTED', False),
        ('余额不足，请充值', 'E-QUOTA-EXCEEDED', False),
        ('内容审核未通过', 'E-CONTENT-POLICY', False),
        ('参数不合法：size', 'E-NET-CLIENT', False),
        ('rate limit exceeded', 'E-NET-RATE-LIMIT', True),
        ('请求超时，请重试', 'E-NET-TIMEOUT', True),
        ('HTTP 503：服务不可用', 'E-NET-SERVER', True),
        ('完全没见过的故障', 'E-UNKNOWN', False),
    )

    def test_each_comparison_row_classifies_to_its_code(self):
        for text, code, retryable in self.ROWS:
            with self.subTest(text=text):
                item = classify(text)
                self.assertIsInstance(item, ErrorCode)
                self.assertEqual(item.code, code)
                self.assertEqual(item.retryable, retryable, code)
                self.assertIn(item.severity, SEVERITIES)

    def test_text_rules_categories_have_verdicts_and_registered_codes(self):
        """轮 5B：PATTERNS 已删，TEXT_RULES 是唯一关键词表——每个类目都要有
        VERDICTS 动作/文案兜底、每个码都在 CODES 登记、类目顺序与迁入时一致。"""
        from ui.pet_agent_rules import VERDICTS
        self.assertEqual([category for category, _code, _marks in TEXT_RULES],
                         ['auth', 'quota', 'content', 'params', 'rate_limit', 'timeout', 'server'])
        for category, code, _marks in TEXT_RULES:
            with self.subTest(category=category):
                self.assertIn(code, CODES)
                self.assertIn(category, VERDICTS)
        self.assertIn('unknown', VERDICTS)

    def test_numeric_marks_require_standalone_digits(self):
        """与 pet_agent._mark_hit 同口径：长数字里的 429 不算被限流。"""
        self.assertEqual(classify('ComfyUI 进程已退出（退出代码 4294967295）').code, 'E-UNKNOWN')
        self.assertEqual(classify('被限流').code, 'E-NET-RATE-LIMIT')

    def test_status_parameter_feeds_the_same_haystack(self):
        self.assertEqual(classify('', status=503).code, 'E-NET-SERVER')
        self.assertEqual(classify('请求失败', status='429').code, 'E-NET-RATE-LIMIT')
        self.assertEqual(classify('某个怪问题', status='not-a-number').code, 'E-UNKNOWN')
        self.assertEqual(classify('某个怪问题', status='').code, 'E-UNKNOWN')
        self.assertEqual(classify(None).code, 'E-UNKNOWN')

    def test_earlier_category_wins_on_overlap(self):
        # content（第 3 位）先于 server（第 7 位）；auth（第 1 位）先于 params（第 4 位）
        self.assertEqual(classify('内容审核未通过，HTTP 500').code, 'E-CONTENT-POLICY')
        self.assertEqual(classify('401 参数不合法').code, 'E-AUTH-REJECTED')

    def test_new_codes_carry_user_facing_remedy(self):
        for code in ('E-QUOTA-EXCEEDED', 'E-CONTENT-POLICY'):
            with self.subTest(code=code):
                item = error_codes.lookup(code)
                self.assertTrue(item.user_message and item.remedy)
                self.assertFalse(item.retryable)
                self.assertEqual(item.severity, Severity.WARN)

    def test_golden_table_code_severity_retryable(self):
        """K8-4 黄金样本：错误码表整份对照（码 → Severity, retryable）。"""
        expected = {
            'E-UNKNOWN': (Severity.WARN, False),
            'E-NET-TIMEOUT': (Severity.WARN, True),
            'E-NET-UNREACHABLE': (Severity.WARN, True),
            'E-NET-RATE-LIMIT': (Severity.WARN, True),
            'E-NET-SERVER': (Severity.WARN, True),
            'E-NET-CLIENT': (Severity.WARN, False),
            'E-QUOTA-EXCEEDED': (Severity.WARN, False),
            'E-CONTENT-POLICY': (Severity.WARN, False),
            'E-AUTH-MISSING': (Severity.WARN, False),
            'E-AUTH-REJECTED': (Severity.WARN, False),
            'E-ASSET-MISSING': (Severity.WARN, False),
            'E-FILE-NOT-FOUND': (Severity.WARN, False),
            'E-FILE-TOO-LARGE': (Severity.WARN, False),
            'E-PATH-UNSAFE': (Severity.WARN, False),
            'E-CONTRACT-VIOLATION': (Severity.DEGRADED, False),
            'E-STAGE-BLOCKED': (Severity.WARN, False),
            'E-CANCELLED': (Severity.INFO, False),
            'E-IO-WRITE': (Severity.WARN, True),
            'E-TOOL-MISSING': (Severity.DEGRADED, False),
            'E-IO-READ': (Severity.WARN, True),
            'E-IO-CORRUPT': (Severity.DEGRADED, False),
            'E-TOOL-FAILED': (Severity.DEGRADED, True),
            'E-TOOL-TIMEOUT': (Severity.DEGRADED, True),
            'E-CONFIG-INVALID': (Severity.WARN, False),
            'E-START-FAILED': (Severity.FATAL, False),
            'E-START-SELFCHECK': (Severity.FATAL, False),
        }
        self.assertEqual(set(CODES), set(expected))
        for code, (severity, retryable) in expected.items():
            with self.subTest(code=code):
                item = lookup(code)
                self.assertEqual(item.severity, severity)
                self.assertEqual(item.retryable, retryable)

    def test_recoverable_value_is_rejected(self):
        """K8-3：旧 recoverable 取值删除，重试与否只读 retryable。"""
        with self.assertRaises(ValueError):
            ErrorCode('E-X', 'recoverable', False, 'm', 'r')
        # 字符串入参仍归一到枚举（兼容构造口径）
        self.assertIs(ErrorCode('E-X', 'warn', True, 'm', 'r').severity, Severity.WARN)


class UserTextTests(unittest.TestCase):
    """EC-1：界面失败文字统一出口 ``user_text(error, *, fallback='E-UNKNOWN')``。

    规则按序命中：R1 带已登记 ``code`` 的异常走 ``describe``；R2 系统
    ``OSError``（errno 非 None）归码不给原文；R3 中文说明原样（并一行）；
    R4 其余回 ``fallback``。纯函数，任何输入不抛异常。
    """

    def test_infra_error_with_code_uses_describe(self):
        self.assertEqual(error_codes.user_text(StorageError('', code='E-IO-READ')),
                         describe('E-IO-READ'))

    def test_infra_error_appends_chinese_message(self):
        self.assertEqual(
            error_codes.user_text(StorageError('分镜文件读不出', code='E-IO-READ')),
            describe('E-IO-READ') + '：分镜文件读不出')

    def test_handwritten_chinese_passes_through_on_one_line(self):
        self.assertEqual(error_codes.user_text(ValueError('当前操作尚未结束，请稍后')),
                         '当前操作尚未结束，请稍后')
        self.assertEqual(error_codes.user_text(ValueError('  第一段\n\n   第二段  ')),
                         '第一段 第二段')

    def test_programmer_error_hides_original_text(self):
        text = error_codes.user_text(AttributeError("'NoneType' object has no attribute 'state'"))
        self.assertEqual(text, describe('E-UNKNOWN'))
        self.assertNotIn('NoneType', text)

    def test_real_os_error_maps_to_code_without_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                open(os.path.join(tmp, '不存在的文件.txt'), 'rb')
            except OSError as exc:
                err = exc
        text = error_codes.user_text(err)
        self.assertEqual(text, describe('E-FILE-NOT-FOUND'))
        self.assertNotIn(tmp, text)

    def test_other_real_os_error_uses_fallback(self):
        # errno 非 None 但不是 FileNotFoundError 的系统错误（本机打开目录
        # 抛 PermissionError）→ describe(fallback)，系统原文不给用户
        with tempfile.TemporaryDirectory() as tmp:
            try:
                open(tmp, 'rb')
            except OSError as exc:
                err = exc
        self.assertIsInstance(err, OSError)
        self.assertIsNotNone(err.errno)
        self.assertNotIsInstance(err, FileNotFoundError)
        text = error_codes.user_text(err)
        self.assertEqual(text, describe('E-UNKNOWN'))
        self.assertNotIn(tmp, text)

    def test_manually_raised_oserror_with_chinese_passes_through(self):
        # 手工构造的 OSError errno 为 None，不是系统报错——按 R3 原样返回
        self.assertEqual(error_codes.user_text(OSError('磁盘已满，请清理后重试')),
                         '磁盘已满，请清理后重试')

    def test_anything_else_falls_back_without_raising(self):
        class BadStr:
            def __str__(self):
                raise RuntimeError('str broken')

        for obj in (None, '', object(), BadStr()):
            with self.subTest(obj=type(obj).__name__):
                self.assertEqual(error_codes.user_text(obj), describe('E-UNKNOWN'))

    def test_fallback_code_is_used(self):
        self.assertEqual(error_codes.user_text(RuntimeError('boom'), fallback='E-START-FAILED'),
                         describe('E-START-FAILED'))
        self.assertEqual(error_codes.user_text(RuntimeError('boom'), fallback='E-BOGUS'),
                         describe('E-UNKNOWN'))


if __name__ == '__main__':
    unittest.main()
