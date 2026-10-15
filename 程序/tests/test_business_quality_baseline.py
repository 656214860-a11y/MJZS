"""基准工具的记分规则；合成字节仅用于单测，不是产品质量样本。"""
import copy
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / '维护记录/基准脚本/business_quality_baseline.py'
SPEC = importlib.util.spec_from_file_location('business_quality_baseline', SCRIPT)
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


class BusinessQualityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        raw = b'\x89PNG\r\n\x1a\nunit-test-only'
        (self.base / 'sample.png').write_bytes(raw)
        self.data = baseline.template()
        self.data.update(application_commit='test-only', reviewers=['one', 'two'])
        for story in self.data['stories']:
            for shot in story['shots']:
                shot.update(status='generated', request_id=shot['id'], model='test-only',
                            artifact='sample.png', sha256=hashlib.sha256(raw).hexdigest(),
                            reviews=[{'reviewer': name, 'ratings': dict.fromkeys(baseline.AXES, 2),
                                      'reason': 'test-only'} for name in ('one', 'two')])

    def result(self):
        return baseline.evaluate(self.data, self.base)

    def test_empty_template_is_pending_not_free_or_passed(self):
        result = baseline.evaluate(baseline.template(), self.base)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['unknown_cost_items'], 80)
        self.assertTrue(all(s['pending'] == 10 for s in result['stories']))

    def test_failure_counts_in_denominator_and_seventy_percent_threshold(self):
        for shot in self.data['stories'][0]['shots'][:3]:
            shot['status'] = 'failed'
        self.assertEqual(self.result()['status'], 'pass')
        self.assertEqual(self.result()['stories'][0]['rate'], .7)
        self.data['stories'][0]['shots'][3]['status'] = 'not_returned'
        self.assertEqual(self.result()['status'], 'fail')

    def test_hash_changed_or_file_missing_never_passes(self):
        (self.base / 'sample.png').write_bytes(b'changed')
        self.assertEqual(self.result()['status'], 'pending')

    def test_disagreement_requires_distinct_reviewer_and_reason(self):
        shot = self.data['stories'][0]['shots'][0]
        shot['reviews'][0]['ratings'][baseline.AXES[0]] = 1
        self.assertEqual(self.result()['status'], 'pending')
        shot['adjudication'] = dict(reviewer='one', ratings=dict.fromkeys(baseline.AXES, 2), reason='why')
        self.assertEqual(self.result()['status'], 'pending')
        shot['adjudication']['reviewer'] = 'third'
        self.assertEqual(self.result()['status'], 'pass')

    def test_retry_and_removed_shots_cannot_improve_first_round(self):
        original = copy.deepcopy(self.data)
        self.data['stories'][0]['shots'][0]['attempt'] = 2
        with self.assertRaises(ValueError):
            self.result()
        self.data = original
        self.data['stories'][0]['shots'].pop()
        with self.assertRaises(ValueError):
            self.result()

    def test_holdout_is_required_and_reported_separately(self):
        self.data['stories'][-1]['shots'][0]['status'] = 'not_run'
        self.assertEqual(self.result()['status'], 'pending')
        self.assertEqual(self.result()['stories'][-1]['role'], 'holdout')

    def test_invalid_cost_or_duplicate_requests_rejected(self):
        shot = self.data['stories'][0]['shots'][0]
        shot['cost'] = float('nan')
        with self.assertRaises(ValueError):
            self.result()
        shot['cost'] = None
        shot['request_id'] = self.data['stories'][0]['shots'][1]['request_id']
        with self.assertRaises(ValueError):
            self.result()
