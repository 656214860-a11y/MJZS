import unittest


class ServiceContractTests(unittest.TestCase):
    def test_result_has_the_four_stable_fields(self):
        from service_contract import ServiceResult, success
        result = success({'published': True})
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, '')
        self.assertFalse(result.recoverable)
        self.assertEqual(result.data, {'published': True})
        self.assertEqual(tuple(ServiceResult.__dataclass_fields__),
                         ('ok', 'reason', 'recoverable', 'data'))

    def test_cancelled_is_not_a_failure(self):
        from service_contract import Cancelled, SystemError, UserError, is_failure
        self.assertFalse(is_failure(Cancelled()))
        self.assertTrue(is_failure(UserError('请补充文件')))
        self.assertTrue(is_failure(SystemError('磁盘不可用')))
