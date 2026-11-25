"""制作后段页的无 Tk 状态与决策（R1983 J3）：从 MediaPagesMixin 下沉后行为不变。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator import media_page_controller as media
import video_progress
from local_video import skip_summary


class _Studio:
    def __init__(self, path, shots, versions):
        self.episode_path = path
        self.episode = {'shots': shots}
        self._versions = versions

    def state(self):
        return {'shots': self._versions}


class SummaryTextTests(unittest.TestCase):
    def test_summary_text_reports_pass_or_todo(self):
        self.assertEqual(media.summary_text({'shots': 3, 'batches': 2, 'ok': True}), '镜头 3 个 · 批次 2 组 · 全部通过')
        self.assertEqual(media.summary_text({}), '镜头 0 个 · 批次 0 组 · 有待办')
        self.assertEqual(media.summary_text(None), '镜头 0 个 · 批次 0 组 · 有待办')


class EditReadySignatureTests(unittest.TestCase):
    def test_signature_changes_with_storyboard_file_and_review_state(self):
        shots = [{'id': 'SH001'}]
        versions = {'SH001': [{'version': 1, 'review': 'approved', 'qc_pass': True, 'state': 'done'}]}
        first = media.edit_ready_signature(_Studio('a.json', shots, versions))
        self.assertEqual(first, media.edit_ready_signature(_Studio('a.json', shots, versions)))
        self.assertNotEqual(first, media.edit_ready_signature(_Studio('b.json', shots, versions)))
        changed = {'SH001': [{'version': 1, 'review': 'pending', 'qc_pass': True, 'state': 'done'}]}
        self.assertNotEqual(first, media.edit_ready_signature(_Studio('a.json', shots, changed)))


class KeyframeBatchVerdictTests(unittest.TestCase):
    def verdict(self, busy=False, missing=(), blocked=(), check=False, error=None):
        def blockers():
            if error:
                raise error
            return list(blocked)
        return media.keyframe_batch_verdict(['S1', 'S2'], lambda: busy, lambda: list(missing), blockers, skip_summary, check)

    def test_busy_waits_quietly(self):
        self.assertEqual(self.verdict(busy=True), ('已有制作任务在跑，等这一轮结束再补', False))

    def test_missing_settings_only_checked_on_request(self):
        self.assertEqual(self.verdict(missing=['model']), ('', True))
        reason, warn = self.verdict(missing=['model', 'url'], check=True)
        self.assertIn('缺 model、url', reason)
        self.assertTrue(warn)

    def test_busy_short_circuits_before_settings_and_blockers(self):
        calls = []
        reason, warn = media.keyframe_batch_verdict(
            ['S1'], lambda: True, lambda: calls.append('settings'), lambda: calls.append('blockers'), skip_summary, True)
        self.assertEqual(calls, [])
        self.assertFalse(warn)

    def test_blocker_error_is_reported_as_reason(self):
        self.assertEqual(self.verdict(error=ValueError('分镜坏了')), ('分镜坏了', True))

    def test_only_a_fully_blocked_batch_is_refused(self):
        self.assertEqual(self.verdict(blocked=[('S1', '缺参考')]), ('', True))
        reason, warn = self.verdict(blocked=[('S1', '缺参考'), ('S2', '缺提示词')])
        self.assertTrue(reason.startswith('2 镜都无法生成：'))
        self.assertTrue(warn)


class ContinuityTests(unittest.TestCase):
    def test_build_ledger_survives_unreadable_inputs(self):
        def broken():
            raise ValueError('读不出')
        ledger = media.build_ledger(broken, broken)
        self.assertEqual(ledger['summary']['shots'], 0)

    def test_ledger_shots_requires_a_list(self):
        self.assertEqual(media.ledger_shots({'shots': [{'id': 'A'}]}), [{'id': 'A'}])
        self.assertEqual(media.ledger_shots({'shots': 'x'}), [])
        self.assertEqual(media.ledger_shots([1]), [])

    def test_batch_rows(self):
        ledger = {'batches': [{'batch_id': 'B1', 'shot_ids': ['S1', 'S2'], 'seconds': 8,
                               'frozen_anchors': [{'kind': 'character', 'id': 'C1', 'anchor': '黑发'}]},
                              {'batch_id': 'B2'}]}
        self.assertEqual(media.batch_rows(ledger), [('B1', 'S1、S2', 8, 'character C1：黑发'), ('B2', '—', 0, '—')])

    def test_check_rows_keep_section_order(self):
        ledger = {'drift': [{'id': 'D', 'ok': False, 'detail': 'd'}],
                  'triplets': [{'batch_id': 'B', 'ok': True, 'detail': 't'}],
                  'cross_batch': [{'kind': 'prop', 'ok': False}],
                  'conflicts': [{'shot_id': 'S', 'kind': 'k', 'resolution': 'r', 'reason': '因'}]}
        self.assertEqual([row[0] for row in media.check_rows(ledger)], ['三元组', '跨批次', '参考图裁决', '锚点漂移'])
        rows = media.check_rows(ledger)
        self.assertEqual(rows[1], ('跨批次', 'prop', '不一致', ''))
        self.assertEqual(rows[2][3], 'r；理由：因')
        self.assertEqual(rows[3][2], '漂移')

    def test_issue_rows_and_open_filter(self):
        issues = [{'id': 'I1', 'kind_label': '漂移', 'severity': 'high', 'state_label': '未处理',
                   'state': 'open', 'shots': ['S1'], 'assets': ['A1'], 'detail': '细节'},
                  {'id': 'I2', 'state': 'ignored'}]
        self.assertEqual(media.issue_table_rows(issues)[0], ('I1', '漂移', 'high', '未处理', 'S1、A1', '细节'))
        self.assertEqual(media.issue_table_rows(issues)[1][4], '—')
        self.assertEqual([row['id'] for row in media.open_issues(issues)], ['I1'])


class EditorCandidatesTests(unittest.TestCase):
    def test_saved_path_comes_first_and_drives_are_last(self):
        env = {'LOCALAPPDATA': 'L', 'ProgramFiles': 'P', 'ProgramFiles(x86)': 'Q'}
        found = media.editor_candidates('C:/saved/J.exe', env)
        self.assertEqual(found[0], Path('C:/saved/J.exe'))
        self.assertEqual(found[1], Path('L/JianyingPro/JianyingPro.exe'))
        self.assertEqual(found[-1], Path('G:/JianyingPro/JianyingPro.exe'))
        self.assertEqual(len(found), 1 + 4 + 5)

    def test_without_saved_path_nothing_is_prepended(self):
        self.assertEqual(media.editor_candidates('', {})[0], Path('JianyingPro/JianyingPro.exe'))


class SubtitleStatusTests(unittest.TestCase):
    def test_non_dict_reports(self):
        self.assertIn('估算', media.subtitle_status(True))
        self.assertIn('按分镜时间', media.subtitle_status(None))

    def test_calibration_report(self):
        self.assertIn('还有 2 句未按实际配音校准', media.subtitle_status({'uncalibrated': [1, 2], 'mode': 'length'}))
        self.assertIn('按句长估算', media.subtitle_status({'uncalibrated': [1], 'mode': 'length'}))
        self.assertIn('按镜头时长估算', media.subtitle_status({'uncalibrated': [1], 'mode': 'shot'}))
        self.assertIn('共 5 句', media.subtitle_status({'calibrated': 5}))

    def test_mixed_mode_reports_calibrated_and_pending(self):
        status = media.subtitle_status({'mode': 'mixed', 'audio': 2, 'calibrated': 2,
                                        'uncalibrated': [{'shot': 'SH001'}]})
        self.assertIn('已按实际配音校准 2 句', status)
        self.assertIn('还有 1 句未按实际配音校准', status)

    def test_audio_skip_reason_is_explained_and_short(self):
        status = media.subtitle_status({'mode': 'length', 'uncalibrated': [{}, {}],
                                        'audio_skip_reason': '未配置 FFprobe'})
        self.assertIn('按句长估算', status)
        self.assertIn('还有 2 句未按实际配音校准', status)
        self.assertIn('未配置 FFprobe', status)
        fixed = len([char for char in status if not char.isspace()])  # copy_rules 口径：非空白字数 ≤45
        self.assertLessEqual(fixed, 45)


class DialogueAvailabilityTests(unittest.TestCase):
    def test_three_outcomes(self):
        self.assertEqual(media.dialogue_availability(lambda: ([{'t': 1}], False)), (True, ''))
        self.assertEqual(media.dialogue_availability(lambda: ([], False)),
                         (False, '当前分镜没有对白，配音生成与字幕导出暂不可用。'))

        def broken():
            raise ValueError('坏了')
        has, reason = media.dialogue_availability(broken)
        self.assertFalse(has)
        self.assertTrue(reason.endswith('：坏了'))


class VideoWorkspaceTests(unittest.TestCase):
    def test_resolve_video_root_requires_config_inside_cloud_video(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            task = root / 'cloud_video' / 't1'
            task.mkdir(parents=True)
            prefs = {'cloud_video_workspace': 'cloud_video/t1'}
            self.assertEqual(media.resolve_video_root(root, 'cloud', prefs), root)
            (task / 'config.json').write_text('{}', encoding='utf-8')
            self.assertEqual(media.resolve_video_root(root, 'cloud', prefs), task)
            self.assertEqual(media.resolve_video_root(root, 'local', prefs), root)
            outside = {'cloud_video_workspace': '../x'}
            self.assertEqual(media.resolve_video_root(root, 'cloud', outside), root)

    def test_apply_video_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'cloud_video' / 't1').mkdir(parents=True)
            prefs = media.apply_video_workspace(root, {}, root / 'cloud_video' / 't1')
            self.assertEqual(prefs, {'cloud_video_workspace': 'cloud_video/t1'})
            self.assertEqual(media.apply_video_workspace(root, prefs, None), {})
            with self.assertRaisesRegex(ValueError, '不在当前项目内'):
                media.apply_video_workspace(root, {}, root / 'other')

    def test_frame_checks_key(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'a.json'
            self.assertEqual(media.frame_checks_key(False, 'k', source), str(source.resolve()))
            self.assertEqual(media.frame_checks_key(True, 'k', source), 'k')
            self.assertEqual(media.frame_checks_key(True, None, source), str(source.resolve()))


class HandoffAndDeliveryTests(unittest.TestCase):
    def test_handoff_rows_skip_shots_without_adopted_version(self):
        with tempfile.TemporaryDirectory() as folder:
            studio = _Studio('e.json', [{'id': 'S1', 'title': 'a'}], {'S1': [{'version': 1, 'review': 'pending'}]})
            self.assertEqual(media.handoff_rows(Path(folder), studio), [])

    def test_delivery_line_for_unsubmitted_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            studio = _Studio('e.json', [{'id': 'S1', 'title': '开场'}], {'S1': []})
            lines = media.delivery_lines(Path(folder), studio, video_progress.LABELS, video_progress.status_next)
            self.assertEqual(len(lines), 1)
            self.assertTrue(lines[0].startswith('S1  开场  | 状态 '))
            self.assertIn('采用 无', lines[0])


if __name__ == '__main__':
    unittest.main()
