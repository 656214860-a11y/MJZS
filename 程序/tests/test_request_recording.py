"""逐笔用量落请求台账：视频下载成功、配音逐句合成；记账失败不影响制作。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine
import infra.pet_llm as pet_llm
import stage_execution_service as ses
from contract import platform_tools
from domain import tts_api


def rows(project):
    return pet_llm.RequestLedger(project).load().report()['kinds']


class RecordRequestTests(unittest.TestCase):
    def test_tts_batch_quote_blocks_before_first_request_without_writes(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'cost_profile.json').write_text(json.dumps({'budget_amount': '0.3', 'price_table': {
                'currency': 'CNY', 'version': 'v1', 'model_rates': {'m': {'characters': '0.1'}}}}), encoding='utf-8')
            lines = [{'shot_id': str(i), 'text': '你好', 'speed': 1.0, 'model': 'm'} for i in range(2)]
            generate = Mock(return_value=b'audio')
            before = set(root.rglob('*'))
            with self.assertRaises(ValueError):
                ses.run_tts_lines(lines, root / 'audio', generate, project=root)
            generate.assert_not_called()
            self.assertEqual(set(root.rglob('*')), before)

    def test_tts_quote_excludes_unknown_and_completed_and_tracks_changed_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lines = [{'shot_id': '1', 'text': '你好', 'speed': 1.0, 'model': 'm'}]
            out = root / 'audio'
            ses.run_tts_lines(lines, out, lambda *a, **k: b'audio', project=root)
            quote = tts_api.batch_cost_preview(root, lines, out)
            self.assertEqual((quote['pending'], quote['characters'], quote['unknown']), ([], 0, 0))
            manifest = [{**lines[0], 'state': 'uncertain', 'file': '', 'request_id': 'unknown'}]
            (out / '时间轴.json').write_text(json.dumps(manifest), encoding='utf-8')
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            quote = tts_api.batch_cost_preview(root, lines, out)
            self.assertEqual((quote['pending'], quote['characters'], quote['unknown']), ([], 0, 1))
            self.assertEqual({p: p.read_bytes() for p in root.rglob('*') if p.is_file()}, before)
            changed = [{**lines[0], 'text': '新的台词'}]
            quote = tts_api.batch_cost_preview(root, changed, out)
            self.assertEqual((quote['pending'], quote['characters'], quote['unknown']), ([1], 4, 0))

    def test_records_are_idempotent_per_id_and_kind(self):
        with tempfile.TemporaryDirectory() as folder:
            pet_llm.record_request(folder, 'r1', 'videos', 1)
            pet_llm.record_request(folder, 'r1', 'videos', 1)           # 重复调用只覆盖
            pet_llm.record_request(folder, 'r1', 'seconds', 5.0, mode='estimated')
            kinds = rows(folder)
            self.assertEqual((kinds['videos']['count'], kinds['videos']['settled']), (1, 1))
            self.assertEqual((kinds['seconds']['count'], kinds['seconds']['settled']), (1, 5.0))

    def test_failure_never_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            blocker = Path(folder) / 'file'
            blocker.write_text('x', encoding='utf-8')
            self.assertIsNone(pet_llm.record_request(blocker, 'r1', 'videos', 1))   # 项目路径其实是文件
            self.assertIsNone(pet_llm.record_request(folder, 'r2', 'videos', 'abc'))


class VideoRecordingTests(unittest.TestCase):
    def test_downloaded_video_records_count_and_estimated_seconds(self):
        with tempfile.TemporaryDirectory() as folder:
            class Fake:
                root = Path(folder)
                shot = engine.Studio.shot
                episode = {'shots': [{'id': 'SH001', 'duration': 6}]}
                record_video_usage = engine.Studio.record_video_usage
            studio = Fake()
            studio.record_video_usage('SH001', {'version': 2})
            studio.record_video_usage('SH001', {'version': 2})
            kinds = rows(folder)
            self.assertEqual(kinds['videos']['settled'], 1)
            self.assertEqual(kinds['seconds']['settled'], 6)
            studio.record_video_usage('NOPE', {'version': 1})   # 镜头不存在：只记次数
            self.assertEqual(rows(folder)['videos']['count'], 2)
            self.assertEqual(rows(folder)['seconds']['count'], 1)


SETTINGS = {'model': 'm', 'voice': 'v', 'base_url': 'http://tts.invalid', 'voices': [], 'speeds': []}


@patch.object(tts_api, 'read_settings', return_value=SETTINGS)
class TtsRecordingTests(unittest.TestCase):
    def test_only_synthesized_lines_are_recorded_and_reused_lines_are_not(self, _settings):
        with tempfile.TemporaryDirectory() as folder:
            project, out = Path(folder), Path(folder) / 'audio'
            lines = [{'shot_id': 'S1', 'text': '你好', 'speed': 1.0}, {'shot_id': 'S2', 'text': '再见', 'speed': 1.0}]
            counter = {'n': 0}

            def generate(text, speed=1.0, voice=None):
                counter['n'] += 1
                return b'audio-%d-' % counter['n'] + text.encode()
            first = ses.run_tts_lines(lines, out, generate, episode='E1', project=project)
            self.assertEqual(first, (2, 0, 0))
            self.assertEqual(rows(project)['requests']['count'], 2)
            again = ses.run_tts_lines(lines, out, generate, episode='E1', project=project)
            self.assertEqual(again, (2, 2, 0))
            self.assertEqual(rows(project)['requests']['count'], 2)         # 沿用不重复记
            ses.run_tts_lines(lines[:1], out / 'other', generate, episode='E1')   # 不传 project：不记账
            self.assertEqual(rows(project)['requests']['count'], 2)

    def test_tts_budget_blocks_then_timeout_survives_resume(self, _settings):
        from unittest.mock import Mock
        from infra.pet_llm import RequestLedger
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = {'budget_amount': '0', 'price_table': {'currency': 'CNY', 'version': 'test',
                      'model_rates': {'m': {'characters': '0.1'}}}}
            policy = root / 'cost_profile.json'
            policy.write_text(json.dumps(config), encoding='utf-8')
            lines = [{'shot_id': 'S1', 'text': '你好', 'speed': 1.0}]
            generate = Mock(side_effect=TimeoutError('test'))
            out = root / 'audio'
            with self.assertRaises(ValueError):
                ses.run_tts_lines(lines, out, generate, project=root)
            self.assertFalse(out.exists())
            generate.assert_not_called()
            config['budget_amount'] = '0.2'
            policy.write_text(json.dumps(config), encoding='utf-8')
            self.assertEqual(ses.run_tts_lines(lines, out, generate, project=root), (0, 0, 1))
            self.assertEqual(ses.run_tts_lines(lines, out, generate, project=root), (0, 0, 1))
            self.assertEqual(generate.call_count, 1)
            entry = json.loads((out / '时间轴.json').read_text(encoding='utf-8'))[0]
            self.assertEqual(entry['state'], 'uncertain')
            row = RequestLedger(root).load()._find(entry['request_id'])
            self.assertEqual(row['budget_cost'], '0.2')
            self.assertEqual(row['money_state'], 'unknown')

    def test_successful_tts_charges_characters_once_and_shares_image_budget(self, _settings):
        from infra.pet_llm import RequestLedger, BudgetRejected
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'cost_profile.json').write_text(json.dumps({'budget_amount': '0.2', 'price_table': {
                'currency': 'CNY', 'version': 'test', 'model_rates': {
                    'm': {'characters': '0.1'}, 'image': {'images': '0.1'}}}}), encoding='utf-8')
            lines = [{'shot_id': 'S1', 'text': '你好', 'speed': 1.0}]
            for expected in [(1, 0, 0), (1, 1, 0)]:
                self.assertEqual(ses.run_tts_lines(lines, root / 'audio', lambda *a, **k: b'audio', project=root), expected)
            ledger = RequestLedger(root).load()
            self.assertEqual(len(ledger.entries), 1)
            self.assertEqual(ledger.entries[0]['quantities'], {'characters': '2'})
            self.assertEqual(ledger.entries[0]['budget_cost'], '0.2')
            with self.assertRaises(BudgetRejected):
                with ledger.metered_units('image1', 'image', 'assets', 'images', 1):
                    self.fail('must not send')

    def test_direct_tts_budget_checked_before_opening_connection(self, _settings):
        from infra.pet_llm import BudgetRejected, RequestLedger
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'cost_profile.json').write_text(json.dumps({'budget_amount': '0', 'price_table': {
                'currency': 'CNY', 'version': 'test', 'model_rates': {'m': {'characters': '0.1'}}}}), encoding='utf-8')
            # R3320：出站统一走 infra.http_client → RequestsJsonOpener；预算拒绝时不得打开连接。
            with patch.object(tts_api, 'load_key', return_value='test'), \
                 patch.object(platform_tools.RequestsJsonOpener, 'open') as open_:
                with self.assertRaises(BudgetRejected):
                    tts_api.synthesize('你好', project=root)
                open_.assert_not_called()
            self.assertEqual(RequestLedger(root).load().entries, [])

    def test_direct_tts_stable_id_prevents_resend_after_timeout(self, _settings):
        from infra.pet_llm import BudgetRejected, RequestLedger
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'cost_profile.json').write_text(json.dumps({'budget_amount': '1', 'price_table': {
                'currency': 'CNY', 'version': 'test', 'model_rates': {'m': {'characters': '0.1'}}}}), encoding='utf-8')
            # R3320：默认传输是 RequestsJsonOpener；open 抛 TimeoutError → E-NET-TIMEOUT → synthesize 抛 TimeoutError。
            with patch.object(tts_api, 'load_key', return_value='test'), \
                 patch.object(platform_tools.RequestsJsonOpener, 'open', side_effect=TimeoutError('test')) as opener:
                with self.assertRaises(TimeoutError):
                    tts_api.synthesize('你好', project=root, request_id='tts-full:test')
                with self.assertRaises(BudgetRejected):
                    tts_api.synthesize('你好', project=root, request_id='tts-full:test')
                self.assertEqual(opener.call_count, 1)
            row = RequestLedger(root).load()._find('tts-full:test')
            self.assertEqual(row['money_state'], 'unknown')
            self.assertEqual(row['budget_cost'], '0.2')

    def test_on_line_hook_is_optional_in_tts_api(self, _settings):
        with tempfile.TemporaryDirectory() as folder:
            seen = []
            tts_api.run_lines([{'shot_id': 'S1', 'text': 'a', 'speed': 1.0}], folder,
                              lambda text, speed=1.0, voice=None: b'x', gateway=ses.tts_gateway(),
                              on_line=lambda index, line, entry: seen.append((index, entry['state'])))
            self.assertEqual(seen, [(1, 'ok')])

    def test_quote_and_release_cover_unsaved_via_l3(self, _settings):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lines = [{'shot_id': 'S1', 'text': '你好世界请放开重发', 'speed': 1.0}]
            out = root / 'audio'
            out.mkdir(parents=True)
            (out / '时间轴.json').write_text(json.dumps([
                {**lines[0], 'state': 'unsaved', 'file': '', 'request_id': 'rid-1',
                 'error': '已付费未保存：disk'}]), encoding='utf-8')
            quote = tts_api.batch_cost_preview(root, lines, out)
            self.assertEqual((quote['pending'], quote['unknown']), ([], 1))
            tip = tts_api.unknown_release_prompt(lines, out)
            self.assertEqual(tip['indexes'], [1])
            # FIX-S11-E1B（N137）：unsaved 句按状态分句，如实说明已付费、重发会再付一次。
            self.assertIn('这些句子上次已付费但没有保存成功，重新发送会再付一次', tip['text'])
            self.assertNotIn('这些请求没有扣费', tip['text'])
            self.assertIn('S1', tip['text'])
            self.assertIn('rid-1', tip['text'])
            self.assertEqual(ses.release_tts_unknown(out, tip['indexes']), [1])
            quote = tts_api.batch_cost_preview(root, lines, out)
            self.assertEqual(quote['pending'], [1])
            self.assertEqual(quote['unknown'], 0)


class WholeTrackRetryTests(unittest.TestCase):
    """FIX-S11-E2：整段配音请求号＝指纹＋尝试序号；上次结果未知先确认；成品丢失可重做。"""

    @staticmethod
    def _settings(tag):
        return {'model': 'm', 'voice': 'v',
                'base_url': 'http://tts-e2-%s.invalid' % tag, 'voices': [], 'speeds': []}

    @staticmethod
    def _ok_audio():
        import io

        class _Resp:
            status = 200
            headers = {}

            def __init__(self):
                self._body = io.BytesIO(b'audio-bytes')

            def read(self, n=-1):
                return self._body.read(n)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _Resp()

    def test_rejected_attempt_retries_with_next_request_id(self):
        """卡面边界：第一次 HTTP 401 → 第二次能发出，请求号与第一次不同；标记存相对路径。"""
        import io
        import urllib.error
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calls = []

            def opener(request, timeout=None):
                calls.append(request)
                if len(calls) == 1:
                    raise urllib.error.HTTPError(request.full_url, 401, 'unauthorized', {},
                                                 io.BytesIO(b'{"error":"bad key"}'))
                return self._ok_audio()
            with patch.object(tts_api, 'load_key', return_value='k'), \
                 patch.object(platform_tools.RequestsJsonOpener, 'open', side_effect=opener):
                rid1 = ses.reserve_tts_full_track(root, 'sig-e2a')
                self.assertTrue(rid1.endswith(':1'))
                with self.assertRaises(tts_api.TTSRejected):
                    ses.synthesize_tts_full_track(root, '台词', 'sig-e2a', rid1,
                                                  settings=self._settings('a'))
                rid2 = ses.reserve_tts_full_track(root, 'sig-e2a')
                self.assertIsNotNone(rid2)
                self.assertNotEqual(rid1, rid2)
                raw = ses.synthesize_tts_full_track(root, '台词', 'sig-e2a', rid2,
                                                    settings=self._settings('a'))
                self.assertEqual(raw, b'audio-bytes')
                path = ses.publish_tts_full_track(root, 'sig-e2a', raw)
            self.assertEqual(len(calls), 2)
            marker = json.loads((path.parent / '整段配音.json').read_text(encoding='utf-8'))
            self.assertFalse(Path(marker['file']).is_absolute())
            self.assertEqual(ses.reusable_tts_full_track(root, 'sig-e2a'), path)

    def test_unknown_whole_track_result_requires_confirm(self):
        """卡面边界：第一次超时 → 不确认就不发；确认后发出且请求号不同。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calls = []

            def opener(request, timeout=None):
                calls.append(request)
                raise TimeoutError('timed out')
            with patch.object(tts_api, 'load_key', return_value='k'), \
                 patch.object(platform_tools.RequestsJsonOpener, 'open', side_effect=opener):
                rid1 = ses.reserve_tts_full_track(root, 'sig-e2t')
                with self.assertRaises(TimeoutError):
                    ses.synthesize_tts_full_track(root, '台词', 'sig-e2t', rid1,
                                                  settings=self._settings('t'))
                self.assertIsNone(ses.reserve_tts_full_track(root, 'sig-e2t'))
                self.assertEqual(len(calls), 1)                       # 未确认不发
                rid2 = ses.reserve_tts_full_track(root, 'sig-e2t', confirmed=True)
                self.assertIsNotNone(rid2)
                self.assertNotEqual(rid1, rid2)
                with self.assertRaises(TimeoutError):
                    ses.synthesize_tts_full_track(root, '台词', 'sig-e2t', rid2,
                                                  settings=self._settings('t'))
                self.assertIsNone(ses.reserve_tts_full_track(root, 'sig-e2t'))
                self.assertEqual(len(calls), 2)

    def test_deleted_whole_track_audio_rebuilds_with_new_request_id(self):
        """卡面边界：成品文件被删后再点 → 重新合成（新请求号，不需要确认）。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(tts_api, 'synthesize', return_value=b'audio'):
                rid1 = ses.reserve_tts_full_track(root, 'sig-e2d')
                raw = ses.synthesize_tts_full_track(root, '台词', 'sig-e2d', rid1)
                path = ses.publish_tts_full_track(root, 'sig-e2d', raw)
            self.assertIsNotNone(ses.reusable_tts_full_track(root, 'sig-e2d'))
            path.unlink()
            self.assertIsNone(ses.reusable_tts_full_track(root, 'sig-e2d'))
            rid2 = ses.reserve_tts_full_track(root, 'sig-e2d')
            self.assertIsNotNone(rid2)
            self.assertNotEqual(rid1, rid2)

    def test_moved_project_reuses_audio_via_relative_marker(self):
        """卡面边界：项目目录改名后旧成品按相对路径仍能找到；新标记不存绝对路径。"""
        from contract.project_context import ProjectContext
        from contract.project_stages import audio
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            proj = base / 'project-a'
            proj.mkdir()
            ctx = ProjectContext.snapshot(proj, lambda _stage: proj)
            path = tts_api.publish_full_track(ctx, 'sig-e2m', b'audio', gateway=ses.tts_gateway())
            marker = json.loads((audio(proj) / '整段配音.json').read_text(encoding='utf-8'))
            self.assertFalse(Path(marker['file']).is_absolute())
            proj.rename(base / 'project-b')
            moved = ProjectContext.snapshot(base / 'project-b', lambda _stage: base / 'project-b')
            found = tts_api.reusable_full_track(moved, 'sig-e2m')
            self.assertIsNotNone(found)
            self.assertEqual(found.read_bytes(), b'audio')
            self.assertEqual(found, audio(base / 'project-b') / path.name)

    def test_legacy_absolute_marker_reuse_and_basename_fallback(self):
        """旧格式绝对路径：文件在就沿用；绝对路径失效但同名文件在音频目录也找回。"""
        from contract.project_context import ProjectContext
        from contract.project_stages import audio
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = audio(root)
            folder.mkdir(parents=True)
            keep = folder / '配音_keep00.mp3'
            keep.write_bytes(b'audio')
            marker = folder / '整段配音.json'
            ctx = ProjectContext.snapshot(root, lambda _stage: root)
            marker.write_text(json.dumps({'signature': 'sig-old', 'file': str(keep)}),
                              encoding='utf-8')
            self.assertEqual(tts_api.reusable_full_track(ctx, 'sig-old'), keep)
            ghost = folder.parent / 'old' / keep.name          # 项目搬走后的旧绝对路径，不存在
            marker.write_text(json.dumps({'signature': 'sig-old2', 'file': str(ghost)}),
                              encoding='utf-8')
            self.assertEqual(tts_api.reusable_full_track(ctx, 'sig-old2'), keep)


if __name__ == '__main__':
    unittest.main()
