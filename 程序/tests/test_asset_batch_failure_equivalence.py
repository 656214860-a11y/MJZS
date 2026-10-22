"""压平 asset_batch_execution.run_batch：失败分支原样内嵌为旧实现，与抽出的 _record_failure
逐个异常类型、逐个台账初态对照，比较台账内容与 save_ledger 调用。"""
import copy
import unittest
from unittest import mock

import asset_batch_execution as abe
from asset_batch_execution import AssetSubmissionUncertain
from comfy_service import ComfyGenerationFailed, ComfySubmissionUncertain


def _legacy(project, state, aid, exc, publish_ledger, save_ledger):
    if aid in state:
        state[aid]['error'] = str(exc)
        if isinstance(exc, AssetSubmissionUncertain): pass
        elif isinstance(exc, ComfySubmissionUncertain):
            state[aid]['state'] = 'submitting'
            if getattr(exc, 'record', ''): state[aid]['record'] = str(exc.record)
        elif isinstance(exc, ComfyGenerationFailed) or state[aid].get('state') == 'submitting' and isinstance(exc, ValueError): state[aid]['state'] = 'failed'
        save_ledger(project, state, publish=publish_ledger)


def _uncertain(record):
    exc = ComfySubmissionUncertain.__new__(ComfySubmissionUncertain)
    Exception.__init__(exc, '不确定')
    if record is not None:
        exc.record = record
    return exc


def _exceptions():
    return [AssetSubmissionUncertain('资产不确定'), _uncertain('rec-1'), _uncertain(''), _uncertain(None),
            ComfyGenerationFailed('生成失败'), ValueError('值错误'), RuntimeError('运行错误'), KeyError('k')]


STATES = [{}, {'a': {'state': 'submitting'}}, {'a': {'state': 'queued', 'record': 'r0'}}, {'a': {}}, {'b': {'state': 'submitting'}}]


class RecordFailureEquivalenceTest(unittest.TestCase):
    def test_matches_legacy(self):
        publish = object()
        for initial in STATES:
            for index in range(len(_exceptions())):
                old_state, new_state = copy.deepcopy(initial), copy.deepcopy(initial)
                old_calls, new_calls = [], []
                _legacy('P', old_state, 'a', _exceptions()[index], publish,
                        lambda p, s, publish: old_calls.append((p, copy.deepcopy(s), publish)))
                with mock.patch.object(abe, 'save_ledger', lambda p, s, publish: new_calls.append((p, copy.deepcopy(s), publish))):
                    abe._record_failure('P', new_state, 'a', _exceptions()[index], publish)
                with self.subTest(initial=initial, exc=index):
                    self.assertEqual(new_state, old_state)
                    self.assertEqual(new_calls, old_calls)


if __name__ == '__main__':
    unittest.main()
