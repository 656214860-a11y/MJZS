"""任务书 I22 预测性预加载验收：三道闸门＋io 池低优先级＋暖缓存行为。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contract.infra_errors import QuotaError
from infra import file_cache, prefetch


def _mem(total=1000, available=500):
    return {'memory': {'total': total, 'available': available,
                       'used': total - available, 'percent': 50.0}}


class ScheduleGateTests(unittest.TestCase):
    """I22-2：开关／内存／活跃三闸，任一门不过即不调度。"""

    def test_disable_flag_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            flag = Path(td) / 'autotune_disable_prefetch.flag'
            flag.write_text('off', encoding='utf-8')
            with mock.patch.object(prefetch, 'DISABLE_FLAG', flag), \
                 mock.patch.object(prefetch.executors, 'submit') as submit:
                self.assertFalse(prefetch.schedule(lambda: None,
                                                   snapshot=_mem()))
        submit.assert_not_called()

    def test_memory_below_threshold_blocks(self):
        with mock.patch.object(prefetch.executors, 'submit') as submit:
            self.assertFalse(prefetch.schedule(
                lambda: None, snapshot=_mem(total=1000, available=99)))
        submit.assert_not_called()

    def test_memory_unavailable_does_not_block(self):
        with mock.patch.object(prefetch.executors, 'submit') as submit:
            self.assertTrue(prefetch.schedule(
                lambda: None, snapshot={'memory': 'unavailable'}))
        submit.assert_called_once()

    def test_active_user_blocks(self):
        with mock.patch.object(prefetch.executors, 'submit') as submit:
            self.assertFalse(prefetch.schedule(
                lambda: None, snapshot=_mem(), active=lambda: True))
        submit.assert_not_called()

    def test_quota_error_returns_false(self):
        with mock.patch.object(prefetch.executors, 'submit',
                               side_effect=QuotaError('执行器已关闭：io')):
            self.assertFalse(prefetch.schedule(lambda: None, snapshot=_mem()))

    def test_schedule_submits_to_io_pool(self):
        fn = lambda: None
        with mock.patch.object(prefetch.executors, 'submit') as submit:
            self.assertTrue(prefetch.schedule(fn, snapshot=_mem(),
                                              label='t.probe'))
        args, kwargs = submit.call_args
        self.assertEqual(args[0], 'io')
        self.assertIs(args[1], fn)
        self.assertEqual(kwargs.get('label'), 't.probe')


class WarmFilesTests(unittest.TestCase):
    """I22-1／I22-3：显式清单、不递归；读过的文件进 file_cache 层。"""

    def test_counts_success_and_skips_missing(self):
        with tempfile.TemporaryDirectory() as td:
            ok = Path(td) / 'a.txt'
            ok.write_text('x', encoding='utf-8')
            missing = Path(td) / 'gone.txt'
            self.assertEqual(prefetch.warm_files([ok, missing]), 1)

    def test_json_file_warmed_into_cache(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'b.json'
            path.write_text(json.dumps({'k': 1}), encoding='utf-8')
            self.assertEqual(prefetch.warm_files([path]), 1)
            real_read = Path.read_bytes
            with mock.patch.object(Path, 'read_bytes',
                                   wraps=real_read) as spy:
                self.assertEqual(file_cache.read_json(path), {'k': 1})
            spy.assert_not_called()          # 第二次读命中暖层，零磁盘读

    def test_reader_injection_for_stage_files(self):
        seen = []
        prefetch.warm_files(['p1', 'p2'], reader=seen.append)
        self.assertEqual(seen, ['p1', 'p2'])   # 下一阶段模板/SKILL 文件同机制


if __name__ == '__main__':
    unittest.main()
