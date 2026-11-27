"""C08：性能用例并发红时串行单跑复核一次再判红。"""
import unittest

import selftest_perf_recheck as scheduling


def item(name, red):
    return (name, name, 1, ['boom'] if red else [], 'detail', 0.1, '')


class PerfRecheckTests(unittest.TestCase):
    def test_green_on_recheck_replaces_red(self):
        calls = []

        def runner(units):
            calls.append([u[0] for u in units])
            return [item(u[0], False) for u in units]

        got = [item('test_plain', False), item('test_perf_baseline', True)]
        out = scheduling.recheck_perf_reds(got, [('test_perf_baseline', 'x', None)], runner)
        self.assertEqual(calls, [['test_perf_baseline']])
        self.assertFalse(any(i[3] for i in out))

    def test_still_red_stays_red(self):
        got = [item('test_perf_baseline', True)]
        out = scheduling.recheck_perf_reds(
            got, [('test_perf_baseline', 'x', None)],
            lambda units: [item(u[0], True) for u in units])
        self.assertTrue(out[0][3])

    def test_non_perf_red_not_rechecked(self):
        def runner(units):
            raise AssertionError('不应复核')

        got = [item('test_plain', True), item('test_perf_baseline', False)]
        out = scheduling.recheck_perf_reds(got, [('test_perf_baseline', 'x', None)], runner)
        self.assertEqual(out, got)


if __name__ == '__main__':
    unittest.main()
