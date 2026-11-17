import unittest

from contract.error_codes import (CODES, SEVERITIES, ErrorCode, analyze, code_data,
                                  code_of, describe, from_http_result, lookup)
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


if __name__ == '__main__':
    unittest.main()
