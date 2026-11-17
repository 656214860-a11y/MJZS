"""P0 命名接线：调用真实生产函数，验证名称与载荷结构保持兼容。"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from contract import file_naming


class FileNamingProducerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_script_four_parts_preserve_project_underscore(self):
        from contract.script_contract import stage_file_name
        at = datetime(2026, 11, 17).timestamp()
        self.assertEqual(stage_file_name(self.root / '项目__20261117', '自然剧本', '初稿', at),
                         '项目__自然剧本_初稿_20261117.md')
        with patch.dict(file_naming.EXISTING_TEMPLATES,
                        stage_script='{project}_{file_type}_{content}_{date}_中心.md'):
            self.assertTrue(stage_file_name(self.root / '项目', '自然剧本', '初稿', at).endswith('_中心.md'))

    def test_working_storyboard_preserves_title_and_machine_id(self):
        from domain.storyboard_storage import canonical_name
        self.assertEqual(canonical_name({'episode_id': 'EP001', 'title': ' 雨夜__  街头. '}),
                         'EP001_雨夜__  街头_分镜.json')
        for title in ('../CON', 'NUL', 'CON.txt', 'a/b\\c', '...'):
            with self.subTest(title=title):
                name = canonical_name({'episode_id': 'EP001', 'title': title})
                self.assertTrue(name.startswith('EP001_'))
                self.assertTrue(name.endswith('_分镜.json'))
                self.assertEqual(Path(name).name, name)
                self.assertNotIn('\\', name)
                file_naming.validate(name)
        self.assertEqual(canonical_name({'episode_id': 'EP001', 'title': 'NUL'}),
                         'EP001__NUL_分镜.json')

    def test_keyframe_register_keeps_atomic_unique_png_name(self):
        import keyframe_import as service
        source = self.root / 'episode.json'
        source.write_text('{}', encoding='utf-8')
        image = self.root / 'input.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 4 + b'IHDR' + b'\0' * 20 + b'IEND' + b'\0' * 4)
        shot = {'id': 'SH001', 'frame': 'frames/missing.png'}
        item = {'shot_id': 'SH001', 'shot_signature': service.fingerprint(shot)}
        with patch.object(service, 'read', return_value={'episode_id': 'EP001', 'shots': [shot]}), \
                patch.object(service, 'media_root', return_value=self.root), \
                patch('domain.keyframe_evidence.make_evidence'), \
                patch.object(service, 'save_bytes_new') as exclusive, \
                patch.object(service, 'publish_frame_reference', side_effect=lambda _s, _b, _i, dest: dest), \
                patch.object(service.uuid, 'uuid4', return_value=SimpleNamespace(hex='abcdef123456')):
            dest = service.register(source, item, image)
        self.assertEqual(dest.name, 'EP001_SH001_abcdef12.png')
        exclusive.assert_called_once_with(dest, image.read_bytes())

    def test_audio_import_keeps_kind_prefix_and_source_spacing(self):
        from domain import audio_import_service as service
        source = self.root / ' 录音__  第一段.WAV'
        source.write_bytes(b'audio')
        publisher = Mock()
        with patch.object(service.uuid, 'uuid4', return_value=SimpleNamespace(hex='abcdef123456')):
            result = service.import_audio(self.root, source, publish=publisher, kind='bgm')
        self.assertTrue(result.ok)
        self.assertEqual(result.data.name, 'BGM_ 录音__  第一段_abcdef.wav')
        self.assertEqual(publisher.call_args.args, (result.data, source))
        with patch.object(service.uuid, 'uuid4', return_value=SimpleNamespace(hex='abcdef123456')):
            dialogue = service.import_audio(self.root, source, publish=publisher)
        self.assertTrue(dialogue.ok)
        self.assertEqual(dialogue.data.name, ' 录音__  第一段_abcdef.wav')

    def test_handoff_real_bundle_keeps_order_and_case(self):
        from domain import handoff_service as service
        shot = {'id': 'EP001_SH001', 'duration': 3}
        publisher = Mock(return_value='bundle')
        with patch.object(service.uuid, 'uuid4', return_value=SimpleNamespace(hex='abcdef123456')):
            result = service.publish_bundle(self.root, [shot], [(shot, {'file': 'clip.MP4'})], publish=publisher)
        self.assertTrue(result.ok)
        self.assertEqual(publisher.call_args.args[1], '剪映交接_abcdef12')
        self.assertEqual(publisher.call_args.args[2][0]['name'], '001_EP001_SH001.MP4')
        self.assertEqual(json.loads(publisher.call_args.args[2][1]['data'])[0]['shot'], 'EP001_SH001')

    def test_animatic_generate_keeps_artifact_relative_paths(self):
        from domain import animatic_service as service
        from orchestrator.project_context_factory import project_context
        source = self.root / 'storyboard.json'
        source.write_text(json.dumps({'shots': [{'id': 'SH001', 'prompt': '街头', 'duration': 2}]}), encoding='utf-8')
        reference, audio = self.root / 'reference.png', self.root / 'temporary.WAV'
        reference.write_bytes(b'reference')
        audio.write_bytes(b'audio')
        def render(workspace, *_args):
            target = workspace / 'image.PNG'
            target.write_bytes(b'image')
            return target
        def assemble(_images, _durations, _audio, target, **_kwargs):
            target.write_bytes(b'video')
            return target
        result = service.build_bundle(project_context(self.root), source, [reference], audio,
            {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}, 
            render=render, assemble=assemble, publish=lambda artifacts: artifacts,
            write_temporary=lambda path, data: path.write_bytes(data))
        self.assertTrue(result.ok)
        manifest = json.loads(result.data[service.MANIFEST])
        self.assertEqual(manifest['shots'][0]['image'], 'assets/shots/SH001.png')
        self.assertEqual(manifest['audio'], 'assets/temporary_audio.wav')
        self.assertTrue(service.validate_bundle(result.data))

    def test_final_real_publish_keeps_dated_folder(self):
        from tests.test_req_s07_anchors import _project
        from orchestrator import storyboard_final as service
        from domain.project_naming import dated_path
        from stage_execution_service import asset_plan_gateway
        project, episode, source = _project(self.root / 'project')
        at = datetime(2026, 11, 17).timestamp()
        with patch.object(service, 'dated_path', side_effect=lambda parent, prefix: dated_path(parent, prefix, at=at)):
            dest = service.finalize(project, episode, source, retire_working=lambda *_args: None,
                                    gateway=asset_plan_gateway())
        self.assertEqual(dest.name, 'EP001_分镜定稿_20261117')
        self.assertTrue((dest / 'episode.json').is_file())
        self.assertTrue((dest / 'assets.json').is_file())

    def test_direct_api_real_production_keeps_ep_id_and_title(self):
        from tests.test_storyboard_direct_api import FakeAdapter, good_episode
        from orchestrator import storyboard_direct_api as service
        from contract.stage_path_service import write_dir
        from agent.core import save
        script = self.root / 'EP001_雨夜.md'
        script.write_text('第1集 雨夜\n甲：你好。', encoding='utf-8')
        save(self.root / 'config.json', {'episode_dir': str(self.root / 'episode')})
        data = good_episode(title=' 雨夜__  街头 ')
        results = service.run_batch(self.root, {'engine': 'qwen', 'model': 'deepseek-v4-pro'}, 'SKILL',
            scripts=[script], adapter=FakeAdapter(json.dumps(data, ensure_ascii=False)), record={'name': 'm'})
        self.assertTrue(results[0]['ok'], results)
        target = Path(results[0]['path'])
        self.assertEqual(target.name, 'EP001_雨夜__  街头_分镜.json')
        self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['episode_id'], 'EP001')
        self.assertTrue(target.is_relative_to(write_dir(self.root, 'storyboard')))

    def test_suffix_validation_is_central_for_both_apis(self):
        for suffix in ('../png', '.png/evil', '.png\\evil', '.png.exe', '.png\0'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                file_naming.generate_existing('animatic_shot', shot_id='SH001', suffix=suffix)
            with self.subTest(generic=suffix), self.assertRaises(ValueError):
                file_naming.generate_name('资产', prefix='CHAR', index=1, slug='主角', suffix=suffix)


if __name__ == '__main__':
    unittest.main()
