# -*- coding: utf-8 -*-
"""O47：关键真实链路的集成测试（配置→请求快照→实际发送→响应保全→阶段采用→下游成果）。

四条链全部使用合成数据与注入的传输／发布器，不调用真实付费 API、不依赖 Tk 界面：

* 回收站安全语义（O38/O39）：写前计划→逐项移动→提交／回滚、恢复保全、保留口径与成片引用。
* 模型请求链：实际发送的 URL／请求头／请求体、响应保全白名单元数据、诊断不落任何正文。
* 导入→发布→完成证据（O02/O03）：导入不等于完成，导入非对白音轨不能顶替对白，人工确认才完成。
* 剧本→结构→分镜下游：结构稿由真实规则生成，可被编排器独立验证，来源保全。
* 视频返工与首帧门禁（O04/O05/O06）：需修改才允许重做新版本；未配置／已删除／越界／缺失／空文件／损坏 PNG 都不算「首帧都在」。

断言只依赖公开行为与不变量，不锚定易漂移的行号或私有实现细节。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import read, save
from contract.project_stages import exports
import infra.storage_maintenance as sm


NEWLINE = chr(10)
NATURAL_SCRIPT = NEWLINE.join((
    '# 第1集 雨夜',
    '',
    '林青：你终于来了。',
    '陈默：路上堵车。',
    '',
    '林青蹲在店门口，雨水顺着伞骨往下落。',
)) + NEWLINE


class RecycleChainTests(unittest.TestCase):
    """O38/O39：写前计划→逐项移动→提交／回滚，恢复保全与删除前引用检查。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def batches(self):
        base = sm.recycle_base(self.root)
        return sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []

    def test_recycle_then_restore_keeps_bytes_and_marks_committed(self):
        first = self.root / 'a.bin'
        first.write_bytes(b'alpha')
        second = self.root / 'nested' / 'b.bin'
        second.parent.mkdir()
        second.write_bytes(b'beta')
        moved = sm.recycle_paths(self.root, [first, second], '用户清理')
        self.assertEqual(len(moved), 2)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        batch = self.batches()
        self.assertEqual(len(batch), 1)
        info = sm.read_recycle_batch(self.root, batch[0])
        self.assertEqual(info['state'], 'committed')
        self.assertEqual(info['reason'], '用户清理')
        self.assertEqual(len(info['items']), 2)
        for item in info['items']:
            self.assertEqual(sorted(item), ['recycle_path', 'source'])
        restored = sm.restore_recycle_batch(self.root, batch[0])
        self.assertEqual(len(restored), 2)
        self.assertEqual(first.read_bytes(), b'alpha')
        self.assertEqual(second.read_bytes(), b'beta')

    def test_failed_move_rolls_back_the_whole_batch(self):
        first = self.root / 'a.bin'
        first.write_bytes(b'alpha')
        second = self.root / 'b.bin'
        second.write_bytes(b'beta')
        real = sm.move_planned
        calls = {'n': 0}

        def flaky(record, root, batch):
            calls['n'] += 1
            if calls['n'] == 2:
                raise OSError('目标被占用')
            return real(record, root, batch)

        with patch('storage_maintenance.move_planned', side_effect=flaky):
            with self.assertRaises(OSError):
                sm.recycle_paths(self.root, [first, second], '用户清理')
        self.assertEqual(first.read_bytes(), b'alpha')
        self.assertEqual(second.read_bytes(), b'beta')
        info = sm.read_recycle_batch(self.root, self.batches()[0])
        self.assertEqual(info['state'], 'rolled_back')
        self.assertEqual(len(info['items']), 2)

    def test_version_retention_reasons(self):
        now = 1000000000.0
        month = 40 * 24 * 3600
        base = {'state': 'downloaded', 'version': 1, 'created': now - month, 'sha256': 'abc'}
        for state in ('queued', 'running', 'unknown', ''):
            self.assertEqual(sm.version_retention(dict(base, state=state), 'SH1', 9, set(), set(), now),
                             sm.RETAIN_UNSETTLED)
        self.assertEqual(sm.version_retention(dict(base, locked=True), 'SH1', 9, set(), set(), now),
                         sm.RETAIN_LOCKED)
        self.assertEqual(sm.version_retention(dict(base, version=3), 'SH1', 9, {('SH1', 3)}, set(), now),
                         sm.RETAIN_EDIT_SOURCE)
        self.assertEqual(sm.version_retention(base, 'SH1', 9, set(), {('SH1', 'abc')}, now),
                         sm.RETAIN_EDIT_SOURCE)
        self.assertEqual(sm.version_retention(dict(base, review='pass'), 'SH1', 9, set(), set(), now),
                         sm.RETAIN_APPROVED)
        self.assertEqual(sm.version_retention(dict(base, version=9), 'SH1', 9, set(), set(), now),
                         sm.RETAIN_LATEST)
        self.assertEqual(sm.version_retention(dict(base, created=now - 60), 'SH1', 9, set(), set(), now),
                         sm.RETAIN_FRESH)
        self.assertEqual(sm.version_retention(base, 'SH1', 9, set(), set(), now), '')

    def test_edit_source_versions_reads_published_cut_manifest(self):
        folder = exports(self.root)
        folder.mkdir(parents=True)
        save(folder / 'edit_bundle.json', {'manifest': [
            {'shot': 'SH001', 'version': 1, 'sha256': 'aaa'},
            {'shot': 'SH002', 'version': 4, 'sha256': 'bbb'}]})
        pairs, digests = sm.edit_source_versions(self.root)
        self.assertEqual(pairs, {('SH001', 1), ('SH002', 4)})
        self.assertEqual(digests, {('SH001', 'aaa'), ('SH002', 'bbb')})

    def test_clean_project_only_recycles_registered_downloads_project(self):
        outside = self.root / 'proj'
        (outside / '历史版本').mkdir(parents=True)
        (outside / '历史版本' / 'old.txt').write_text('x', encoding='utf-8')
        self.assertEqual(sm.clean_project(outside), [])

        downloads = self.root / 'downloads'
        root = downloads / 'proj'
        (root / '历史版本').mkdir(parents=True)
        (root / '历史版本' / 'old.txt').write_text('x', encoding='utf-8')
        save(root / 'config.json', {})
        with patch('storage_maintenance.downloads_root', return_value=downloads):
            removed = sm.clean_project(root)
        self.assertEqual([path.as_posix() for path in removed], ['历史版本'])
        info = sm.read_recycle_batch(root, self._only_batch(root))
        self.assertEqual(info['state'], 'committed')
        self.assertEqual([item['source'] for item in info['items']], ['历史版本'])

    def _only_batch(self, root):
        base = sm.recycle_base(root)
        return sorted(p for p in base.iterdir() if p.is_dir())[0]


class ModelRequestChainTests(unittest.TestCase):
    """配置→请求快照→实际发送→响应保全：真实发送路径，注入传输，不碰真实付费 API。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.sent = {}

    def transport(self, url, payload, headers, timeout):
        self.sent.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {'ok': True, 'status': 200, 'error': '', 'data': {
            'id': 'resp-1',
            'usage': {'prompt_tokens': 10, 'completion_tokens': 4, 'prompt_cache_hit_tokens': 3},
            'choices': [{'finish_reason': 'stop',
                         'message': {'content': '正文结果', 'reasoning_content': '思考'}}]}}

    def adapter(self):
        from infra.model_router import GPTAdapter
        return GPTAdapter(program=self.root, transport=self.transport, key='sk-test')

    def test_chat_sends_frozen_snapshot_without_leaking_key(self):
        result = self.adapter().chat([{'role': 'user', 'content': '写一句'}],
                                     {'max_tokens': 128}, model='gpt-4o', system='系统前缀')
        self.assertTrue(result['ok'])
        self.assertEqual(self.sent['url'], 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(self.sent['headers']['Authorization'], 'Bearer sk-test')
        self.assertEqual(self.sent['payload']['model'], 'gpt-4o')
        self.assertEqual(self.sent['payload']['max_tokens'], 128)
        self.assertEqual(self.sent['payload']['messages'][0], {'role': 'system', 'content': '系统前缀'})
        self.assertEqual(self.sent['payload']['messages'][1], {'role': 'user', 'content': '写一句'})
        self.assertNotIn('sk-test', json.dumps(self.sent['payload'], ensure_ascii=False))
        self.assertEqual(result['text'], '正文结果')

    def test_response_meta_is_a_whitelist_of_shape_only(self):
        meta = self.adapter().chat([{'role': 'user', 'content': 'x'}], model='gpt-4o')['response_meta']
        self.assertEqual(meta['requested_model'], 'gpt-4o')
        self.assertEqual(meta['wire_api'], 'chat')
        self.assertEqual(meta['response_id'], 'resp-1')
        self.assertEqual(meta['finish_reason'], 'stop')
        self.assertEqual(meta['response_shape'], ['choices', 'id', 'usage'])
        self.assertEqual(meta['message_fields'], ['content', 'reasoning_content'])
        self.assertEqual(meta['reasoning_fields'], ['reasoning_content'])
        self.assertEqual(meta['reasoning_lengths'], {'reasoning_content': len('思考')})
        self.assertEqual(meta['content_length'], len('正文结果'))

    def test_usage_maps_cache_hit_and_ledger_ratios(self):
        from infra.pet_llm import Ledger, usage_of
        usage = usage_of({'data': {'usage': {'prompt_tokens': 10, 'completion_tokens': 4,
                                              'prompt_cache_hit_tokens': 3}}})
        self.assertEqual(usage, {'prompt_tokens': 10, 'completion_tokens': 4, 'cached_tokens': 3})
        ledger = Ledger()
        ledger.record('gpt-4o-mini', usage, tier='flash')
        ledger.record('gpt-4o', {'prompt_tokens': 10, 'completion_tokens': 0, 'cached_tokens': 0}, tier='pro')
        self.assertEqual(ledger.hit_rate(), round(3 / 20, 3))
        self.assertEqual(ledger.flash_share(), 0.5)

    def test_diagnostics_record_metadata_without_any_body(self):
        from infra import model_diagnostics
        result = self.adapter().chat([{'role': 'user', 'content': '机密提示词'}], model='gpt-4o')
        path = model_diagnostics.record(self.root, result, context={'task': '写作'})
        self.assertEqual(path.parent, self.root / 'model_diagnostics')
        saved = read(path)
        self.assertTrue(saved['ok'])
        self.assertEqual(saved['content_length'], len('正文结果'))
        self.assertEqual(saved['usage'], {'prompt_tokens': 10, 'completion_tokens': 4, 'cached_tokens': 3})
        blob = path.read_text(encoding='utf-8')
        self.assertNotIn('正文结果', blob)
        self.assertNotIn('机密提示词', blob)
        self.assertNotIn('思考', blob)

    def test_timeout_is_reported_not_raised(self):
        def boom(url, payload, headers, timeout):
            raise TimeoutError('slow')

        adapter = self.adapter()
        adapter.transport = boom
        result = adapter.chat([{'role': 'user', 'content': 'x'}], model='gpt-4o')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_class'], 'timeout')
        self.assertEqual(result['text'], '')
        self.assertEqual(result['status'], 0)


class ImportToCompletionChainTests(unittest.TestCase):
    """O02/O03：导入→发布→阶段采用→完成证据；导入不等于完成，人工确认不可跳过。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root / 'input.wav'
        self.source.write_bytes(b'audio bytes')
        save(self.root / 'config.json', {'ffprobe': 'test-probe'})
        story = self.root / 'storyboard' / 'episode.json'
        save(story, {'id': 'EP01', 'shots': [{'id': 'S01'}]})
        save(self.root / 'ui_settings.json',
             {'frame_json': str(story), 'adopted_storyboards': [str(story)]})

    def import_dialogue(self):
        from domain import audio_import_service

        def publish(target, source):
            target.write_bytes(source.read_bytes())

        with patch('domain.audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            return audio_import_service.import_audio(self.root, self.source, publish=publish)

    def test_import_publishes_then_requires_explicit_review(self):
        from stage_completion_service import (completion_evidence, confirm_media_completion,
                                              prepare_media_completion)
        result = self.import_dialogue()
        self.assertTrue(result.ok)
        target = result.data
        self.assertEqual(target, self.root / '11配音与字幕' / '音频' / 'input_abcdef.wav')
        self.assertTrue(self.source.is_file())
        self.assertFalse(completion_evidence(self.root, 'audio')[0])
        probe = {'format': {'duration': '2.5'}, 'streams': [{'codec_type': 'audio'}]}
        with patch('agent.media.probe', return_value=probe):
            prepared = prepare_media_completion(self.root, 'audio', [target])
        self.assertEqual(prepared['status'], 'pending_review')
        self.assertFalse(completion_evidence(self.root, 'audio')[0])
        confirm_media_completion(self.root, 'audio', prepared)
        self.assertEqual(completion_evidence(self.root, 'audio'), (True, ''))

    def test_non_dialogue_audio_cannot_complete_dialogue(self):
        from stage_completion_service import prepare_media_completion
        from domain import audio_import_service

        def publish(target, source):
            target.write_bytes(source.read_bytes())

        with patch('domain.audio_import_service.uuid.uuid4') as created:
            created.return_value.hex = 'abcdef123456'
            result = audio_import_service.import_audio(self.root, self.source, publish=publish, kind='bgm')
        probe = {'format': {'duration': '2.5'}, 'streams': [{'codec_type': 'audio'}]}
        with patch('agent.media.probe', return_value=probe):
            with self.assertRaisesRegex(ValueError, '对白'):
                prepare_media_completion(self.root, 'audio', [result.data])

    def test_delivery_import_publishes_under_the_delivery_stage(self):
        from stage_execution_service import import_delivery_master, project_context
        master = self.root / 'master.mp4'
        master.write_bytes(b'video')
        with patch('agent.media.validate_import', return_value={'decoded': True}):
            result = import_delivery_master(self.root, master)
        self.assertTrue(result.ok)
        self.assertEqual(result.data.parent, project_context(self.root).stage_resolver('delivery'))
        self.assertEqual(result.data.read_bytes(), b'video')
        self.assertTrue(master.is_file())


class ScriptToStoryboardChainTests(unittest.TestCase):
    """O04–O12：自然剧本→结构剧本→分镜采用；结构稿可被编排器独立验证，来源保全。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def test_natural_script_becomes_a_verifiable_structured_stage(self):
        from contract.stage_path_service import write_dir
        from orchestrator.skill_orchestrator import verified_stage_output
        from stage_completion_service import completion_evidence
        import script_contract
        writing = write_dir(self.root, 'script')
        writing.mkdir(parents=True)
        raw = writing / '项目剧本_第1集_20261012.md'
        raw.write_text(NATURAL_SCRIPT, encoding='utf-8')
        self.assertEqual(Path(script_contract.resolve_script_source(self.root)).resolve(), raw)
        target = script_contract.write_structured_script(self.root)
        self.assertTrue(target.is_file())
        self.assertEqual(target.parent, write_dir(self.root, 'structure') / '结构剧本')
        self.assertIn('结构剧本', target.name)
        self.assertTrue(script_contract.is_structured_script(target))
        self.assertTrue(verified_stage_output(self.root, 'script_structure'))
        self.assertTrue(completion_evidence(self.root, 'script_structure')[0])
        self.assertEqual(raw.read_text(encoding='utf-8'), NATURAL_SCRIPT)

    def test_storyboard_stage_requires_adopted_shots(self):
        from contract.stage_path_service import write_dir
        from stage_completion_service import completion_evidence
        storyboard_dir = write_dir(self.root, 'storyboard')
        storyboard_dir.mkdir(parents=True)
        empty = storyboard_dir / 'episode.json'
        save(empty, {'id': 'EP01', 'shots': []})
        save(self.root / 'ui_settings.json',
             {'frame_json': str(empty), 'adopted_storyboards': [str(empty)]})
        self.assertFalse(completion_evidence(self.root, 'storyboard')[0])
        ready = storyboard_dir / 'episode_v2.json'
        save(ready, {'episode_id': 'EP001', 'title': '第1集',
                     'shots': [{'id': 'SH001', 'location': 'LOC_001', 'title': '开场'}]})
        save(self.root / 'ui_settings.json',
             {'frame_json': str(ready), 'adopted_storyboards': [str(ready)]})
        self.assertTrue(completion_evidence(self.root, 'storyboard')[0])
class VideoReworkGateTests(unittest.TestCase):
    """O04：已下载视频必须显式标记需修改才能返工；未决任务禁止重复提交。"""

    def test_submission_gate_distinguishes_rework_from_first_submit(self):
        from video_task_state import submission_block_reason as block
        self.assertEqual(block([]), '')
        self.assertEqual(block([{'state': 'failed'}]), '')
        self.assertEqual(block([{'state': 'downloaded', 'review': 'revise'}]), '')
        first = block([{'state': 'downloaded'}])
        settled = block([{'state': 'downloaded', 'review': 'pass'}])
        self.assertIn('需修改', first)
        self.assertIn('需修改', settled)
        self.assertEqual(first, settled)
        for versions in ([{'state': 'unknown'}], [{'state': 'running'}],
                         [{'state': 'downloaded', 'review': 'pass'}, {'state': 'queued'}]):
            self.assertIn('未完成或结果不确定', block(versions))


class KeyframeGateTests(unittest.TestCase):
    """O05/O06：首帧门禁按镜头逐项给出未配置／已删除／越界／缺失／空文件／损坏原因。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        from contract.stage_path_service import write_dir
        self.base = write_dir(self.root, 'storyboard')
        (self.base / 'media').mkdir(parents=True)
        (self.base / 'media' / 'empty.png').write_bytes(b'')
        (self.base / 'media' / 'broken.png').write_bytes(b'not-a-png-but-nonempty')
        shots = [
            {'id': 'S01'},
            {'id': 'S02', 'frame': 'media/x.png', 'frame_deleted': True},
            {'id': 'S03', 'frame': '../../escape.png'},
            {'id': 'S04', 'frame': 'media/missing.png'},
            {'id': 'S05', 'frame': 'media/empty.png'},
            {'id': 'S06', 'frame': 'media/broken.png'}]
        episode = self.base / 'episode.json'
        save(episode, {'id': 'EP01', 'shots': shots})
        save(self.root / 'ui_settings.json',
             {'frame_json': str(episode), 'adopted_storyboards': [str(episode)]})

    def test_every_missing_kind_is_reported_and_never_passes(self):
        from stage_parallel import frames_ready
        result = frames_ready(self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(result['started'])
        self.assertEqual(len(result['problems']), 6)
        joined = ' '.join(result['problems'])
        for marker in ('未配置首帧路径', '已删除', '越界', '缺首帧', '空文件', 'PNG'):
            self.assertIn(marker, joined)



if __name__ == '__main__':
    unittest.main()
