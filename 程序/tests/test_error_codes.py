import unittest

from contract import error_codes
from contract.error_codes import (CODES, SEVERITIES, ErrorCode, analyze, code_data,
                                  code_of, classify, describe, from_http_result, lookup,
                                  TEXT_RULES)
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
        self.assertEqual(SEVERITIES, frozenset({'fatal', 'degraded', 'recoverable', 'info'}))
        for key, item in CODES.items():
            with self.subTest(code=key):
                self.assertIn(item.severity, SEVERITIES)

    def test_severity_spot_values_reflect_user_impact(self):
        self.assertEqual(lookup('E-CANCELLED').severity, 'info')
        self.assertEqual(lookup('E-TOOL-MISSING').severity, 'degraded')
        self.assertEqual(lookup('E-CONTRACT-VIOLATION').severity, 'degraded')
        self.assertEqual(lookup('E-NET-TIMEOUT').severity, 'recoverable')
        self.assertEqual(lookup('E-AUTH-MISSING').severity, 'recoverable')

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

    关键词表自 ``ui.pet_agent_rules.PATTERNS`` 迁入（顺序即优先级）；
    「是否重试」以码的 ``retryable`` 为唯一权威（G10），本类断言的正是
    结果文件对照表里「改后 retry」那一列。
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

    def test_text_rules_mirror_patterns_order_categories_and_marks(self):
        """迁入保真：类目顺序、类目名与每条关键词表与 PATTERNS 逐一相等。"""
        from ui.pet_agent_rules import PATTERNS
        self.assertEqual([(category, marks) for category, _code, marks in TEXT_RULES],
                         [(category, marks) for category, marks in PATTERNS])
        self.assertEqual([category for category, _code, _marks in TEXT_RULES],
                         [category for category, _marks in PATTERNS])

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
                self.assertEqual(item.severity, 'recoverable')


if __name__ == '__main__':
    unittest.main()
