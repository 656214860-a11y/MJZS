import unittest

from error_codes import CODES, code_data, code_of, describe, from_http_result, lookup
from service_contract import ServiceResult, SystemError, UserError, success


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


if __name__ == '__main__':
    unittest.main()
