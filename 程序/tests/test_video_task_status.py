# -*- coding: utf-8 -*-
"""O28：本地/云端任务统一可恢复状态与错误分类（只读翻译，不改提交判据）。"""
import json
import tempfile
import unittest
from pathlib import Path

from video_progress import (task_status, status_label, status_next, status_detail,
                            error_kind, ERROR_LABELS)
from video_task_state import submission_block_reason, VIDEO_FAILURE_TO_CODE
from contract.error_codes import describe


class TaskStatusTests(unittest.TestCase):
    """一条版本只翻出一个统一状态码：八态＋失败/拒绝/缺文件。"""

    def test_raw_states_map_to_unified_vocabulary(self):
        self.assertEqual(task_status({}), '')
        self.assertEqual(task_status({'state': 'submitting'}), 'submitting')
        self.assertEqual(task_status({'state': 'unknown'}), 'unknown')
        self.assertEqual(task_status({'state': 'queued'}), 'queued')
        self.assertEqual(task_status({'state': 'running'}), 'running')
        self.assertEqual(task_status({'state': 'succeeded'}), 'downloading')
        self.assertEqual(task_status({'state': 'failed'}), 'failed')
        self.assertEqual(task_status({'state': 'rejected'}), 'rejected')

    def test_downloaded_version_splits_by_qc_and_review(self):
        self.assertEqual(task_status({'state': 'downloaded'}), 'missing_file')
        self.assertEqual(task_status({'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': False}), 'qc_failed')
        self.assertEqual(task_status({'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': True}), 'review_pending')
        self.assertEqual(task_status({'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': True, 'review': 'pass'}), 'adopted')

    def test_download_failure_is_its_own_state(self):
        self.assertEqual(task_status({'state': 'succeeded', 'download_error': 'x'}), 'download_failed')
        self.assertEqual(task_status({'state': 'succeeded'}), 'downloading')

    def test_status_names_match_o28_vocabulary(self):
        self.assertEqual(status_label({'state': 'submitting'}), '提交中')
        self.assertEqual(status_label({'state': 'unknown'}), '结果不确定')
        self.assertEqual(status_label({'state': 'queued'}), '排队中')
        self.assertEqual(status_label({'state': 'running'}), '生成中')
        self.assertEqual(status_label({'state': 'succeeded', 'download_error': 'x'}), '下载失败')
        self.assertEqual(status_label({'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': False}), '技术不合格')
        self.assertEqual(status_label({'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': True}), '待审核')
        self.assertEqual(status_label({'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': True, 'review': 'pass'}), '已采用')

    def test_every_state_has_a_label_and_a_next_step(self):
        samples = [
            {'state': 'submitting'}, {'state': 'unknown'}, {'state': 'queued'},
            {'state': 'running'}, {'state': 'succeeded'},
            {'state': 'succeeded', 'download_error': 'x'},
            {'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': False},
            {'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': True},
            {'state': 'downloaded', 'file': 'a.mp4', 'qc_pass': True, 'review': 'pass'},
            {'state': 'failed'}, {'state': 'rejected'}, {'state': 'downloaded'},
        ]
        for version in samples:
            self.assertTrue(status_label(version), version)
            self.assertTrue(status_next(version), version)

    def test_next_step_says_query_or_explicit_redo(self):
        self.assertIn('查询', status_next({'state': 'running'}))
        self.assertIn('不要重投', status_next({'state': 'unknown'}))
        self.assertIn('不会重新生成', status_next({'state': 'succeeded', 'download_error': 'x'}))
        self.assertIn('重做', status_next({'state': 'failed'}))

    def test_detail_adds_error_class_and_action(self):
        # EC-5B：错误分类经 VIDEO_FAILURE_TO_CODE→describe() 统一出口，动作指引保留原文。
        detail = status_detail({'state': 'failed', 'error': '401 invalid api key'})
        self.assertIn(describe(VIDEO_FAILURE_TO_CODE['auth']), detail)
        self.assertIn('[E-', detail)
        self.assertIn('（建议：', detail)
        self.assertIn('补配置', detail)
        detail = status_detail({'state': 'failed', 'error': '400 invalid_request_error'})
        self.assertIn(describe(VIDEO_FAILURE_TO_CODE['protocol']), detail)
        self.assertIn('重做', detail)
        self.assertIn(describe(VIDEO_FAILURE_TO_CODE['disk']),
                      status_detail({'state': 'failed', 'error': 'No space left on device'}))
        self.assertIn('不要重投', status_detail({'state': 'unknown'}))
        self.assertEqual(status_detail({}), '未开始；点击生成按钮才会提交')


class ErrorKindTests(unittest.TestCase):
    """错误只归到用户能行动的一类；认不出明确给「未分类」，不猜。"""

    def test_classifies_the_six_kinds_and_unknown(self):
        self.assertEqual(error_kind('401 invalid api key'), 'auth')
        self.assertEqual(error_kind('insufficient_quota'), 'quota')
        self.assertEqual(error_kind('429 rate limit'), 'quota')
        self.assertEqual(error_kind('400 invalid_request_error'), 'protocol')
        self.assertEqual(error_kind('内容审核未通过'), 'refused')
        self.assertEqual(error_kind('connection timed out'), 'network')
        self.assertEqual(error_kind('No space left on device'), 'disk')
        self.assertEqual(error_kind('something odd happened'), 'unknown')
        self.assertEqual(error_kind(''), '')

    def test_disk_wins_over_other_marks(self):
        # 「写盘失败」也要归本机磁盘，不能被后面的模型文案改判。
        self.assertEqual(error_kind('写入失败 quota'), 'disk')

    def test_every_kind_has_a_label(self):
        for kind in ('auth', 'quota', 'protocol', 'refused', 'network', 'disk', 'unknown'):
            self.assertTrue(ERROR_LABELS[kind])


class NoBlindResubmitTests(unittest.TestCase):
    """断网/超时/关窗重启/远端成功本机未落盘：状态拦住重投，只能查询或显式重做。"""

    def test_unfinished_or_uncertain_states_block_resubmission(self):
        for state in ('submitting', 'unknown', 'queued', 'running', 'succeeded'):
            reason = submission_block_reason([{'state': state}])
            self.assertTrue(reason, state)
            self.assertIn('不确定', reason)

    def test_only_failed_rejected_or_revise_can_resubmit(self):
        self.assertEqual(submission_block_reason([]), '')
        self.assertEqual(submission_block_reason([{'state': 'failed'}]), '')
        self.assertEqual(submission_block_reason([{'state': 'rejected'}]), '')
        self.assertEqual(submission_block_reason([{'state': 'downloaded', 'review': 'revise'}]), '')
        self.assertTrue(submission_block_reason([{'state': 'downloaded', 'review': 'pass'}]))

    def test_state_survives_restart(self):
        """关窗重启：状态在磁盘上，读回来仍拦住重投，且保留本地请求号。"""
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'data' / 'state.json'
            db.parent.mkdir(parents=True)
            db.write_text(json.dumps({'shots': {'SH001': [{'version': 1, 'state': 'unknown',
                            'local_request': 'abc', 'charged': True}]}}), encoding='utf-8')
            from agent.core import read
            versions = read(db)['shots']['SH001']
            self.assertTrue(submission_block_reason(versions))
            self.assertEqual(versions[-1]['local_request'], 'abc')
            self.assertTrue(versions[-1]['charged'])