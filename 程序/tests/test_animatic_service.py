"""Animatic 的路径、发布与人工确认契约；仅使用临时项目。"""
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from domain import animatic_service as service
import stage_layout
from pet_bus import STAGES
from contract.stage_path_service import read_dirs, write_dir
from stage_execution_service import publish_animatic_bundle
from project_context_factory import project_context


class AnimaticTests(unittest.TestCase):
    def test_existing_storyboard_prompt_contract_is_supported(self):
        shots = service.shots_of({'shots': [{'id': 'SH001', 'duration': 10, 'video_prompt': '门边的人'}]})
        self.assertEqual(shots[0]['prompt'], '门边的人')
        self.assertEqual(shots[0]['seconds'], 10)

    def test_formal_assets_require_confirmation_and_online_model(self):
        """REQ-S04-26：预演不改资产；正式资产仍走线上 API 生成。"""
        from stage_execution_service import require_formal_asset_generation
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                require_formal_asset_generation(temporary, online_model=True)
            with patch('stage_parallel.evaluate', return_value={'ok': True}):
                with self.assertRaisesRegex(ValueError, '线上 API'):
                    require_formal_asset_generation(temporary, online_model=False)
                require_formal_asset_generation(temporary, online_model=True)

    def test_animatic_skill_tools_open_the_correct_stage(self):
        import skill_tools
        for tool in ('animatic.generate', 'animatic.validate'):
            self.assertEqual(skill_tools.PAGES[tool][0], STAGES.index('animatic'))
            self.assertEqual(skill_tools.status_of(tool), 'page')
        self.assertEqual(skill_tools.PAGES['asset.plan'][0], STAGES.index('assets'))

    def test_generated_bundle_requires_confirmation_and_detects_source_changes(self):
        """REQ-S04-30/32/40：整包发布进阶段目录、清单记来源摘要且产源变化即失效、确认只改 confirmed。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard_draft.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '门边的人', 'duration': 2}]}), encoding='utf-8')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            audio = root / 'temporary.wav'
            audio.write_bytes(b'audio')
            def render(workspace, *_args):
                target = workspace / 'image.png'
                target.write_bytes(b'image')
                return target
            def assemble(images, durations, sound, target, **_kwargs):
                self.assertEqual(durations, [2])
                self.assertEqual(sound, audio)
                self.assertEqual(len(images), 1)
                target.write_bytes(b'video')
                return target
            def publish(artifacts):
                self.assertTrue(service.validate_bundle(artifacts))
                manifest = json.loads(artifacts[service.MANIFEST])
                manifest['confirmed'] = dict.fromkeys(service.CONFIRMATIONS, True)
                forged = dict(artifacts, **{service.MANIFEST: json.dumps(manifest).encode('utf-8')})
                self.assertFalse(service.validate_bundle(forged))
                return publish_animatic_bundle(root, artifacts, validate=lambda _: True)
            result = service.build_bundle(project_context(root), source, [reference], audio,
                {'ffmpeg': 'stub', 'ffprobe': 'stub'}, publish=publish,
                write_temporary=lambda path, raw: path.write_bytes(raw), render=render, assemble=assemble)
            self.assertTrue(result.ok)
            self.assertFalse(service.evidence(root)[0])
            self.assertTrue(service.evidence(root, require_confirmation=False)[0])
            from stage_execution_service import confirm_animatic
            confirm_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            self.assertTrue(service.evidence(root)[0])
            source.write_text('{}', encoding='utf-8')
            self.assertFalse(service.evidence(root)[0])

    def test_persistent_previs_reuses_tts_after_later_render_failure(self):
        """REQ-S04-24：临时 TTS 文件名含脚本签名，已存在且非空即复用，出图失败重跑仍复用。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'storyboard.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': 'door', 'duration': 2}]}), encoding='utf-8')
            reference = root / 'reference.png'; reference.write_bytes(b'image')
            scratch = root / 'scratch'; scratch.mkdir()
            settings = {'model': 'm', 'voice': 'v', 'base_url': 'https://example.invalid'}
            with patch('domain.tts_api.read_settings', return_value=settings), patch('domain.tts_api.synthesize', return_value=b'audio') as synth:
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError, 'render failed'):
                        service.build_bundle(project_context(root), source, [reference], None,
                            {'tts_text': 'hello'}, publish=lambda _: None, workspace=scratch,
                            write_temporary=lambda path, raw: path.write_bytes(raw),
                            render=Mock(side_effect=RuntimeError('render failed')))
                self.assertEqual(synth.call_count, 1)
                self.assertEqual(synth.call_args.kwargs['project'], root)
                self.assertTrue(synth.call_args.kwargs['request_id'].startswith('tts-previs:'))

    def test_evidence_streams_large_media_without_reading_bytes(self):
        """REQ-S04-43：大媒体校验走流式摘要（file_cache.file_digest），mp4／临时音频／镜头图都不整份读进内存。"""
        import infra.file_cache as file_cache
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard_draft.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '门边的人', 'duration': 2}]}), encoding='utf-8')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            audio = root / 'temporary.wav'
            audio.write_bytes(b'audio')
            def render(workspace, *_args):
                target = workspace / 'image.png'
                target.write_bytes(b'image')
                return target
            def assemble(images, durations, sound, target, **_kwargs):
                target.write_bytes(b'video' * 65536)
                return target
            result = service.build_bundle(project_context(root), source, [reference], audio,
                {'ffmpeg': 'stub', 'ffprobe': 'stub'},
                publish=lambda artifacts: publish_animatic_bundle(root, artifacts, validate=lambda _: True),
                write_temporary=lambda path, raw: path.write_bytes(raw), render=render, assemble=assemble)
            self.assertTrue(result.ok)
            from stage_execution_service import confirm_animatic
            confirm_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            real = Path.read_bytes
            def guarded(self, *args, **kwargs):
                if self.suffix.lower() in {'.mp4', '.wav', '.png'}:
                    raise AssertionError('校验阶段不得整份读取媒体字节：' + str(self))
                return real(self, *args, **kwargs)
            file_cache.clear()
            with patch.object(Path, 'read_bytes', guarded):
                self.assertTrue(service.evidence(root)[0], '媒体改走流式摘要后仍必须校验通过')

    def test_render_failure_never_publishes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard_draft.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '草图', 'duration': 1}]}), encoding='utf-8')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            publisher = Mock()
            with self.assertRaisesRegex(RuntimeError, 'unknown submission'):
                service.build_bundle(project_context(root), source, [reference], reference, {},
                    publish=publisher, write_temporary=Mock(),
                    render=Mock(side_effect=RuntimeError('unknown submission')), assemble=Mock())
            publisher.assert_not_called()

    def test_only_known_generation_failures_are_retried(self):
        from comfy_service import ComfyGenerationFailed, ComfySubmissionUncertain
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'storyboard_draft.json'
            source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '草图', 'duration': 1}]}), encoding='utf-8')
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            for error, count in [(ComfyGenerationFailed('failed'), 3), (ComfySubmissionUncertain('unknown'), 1)]:
                render = Mock(side_effect=error)
                with self.assertRaises((ValueError, ComfySubmissionUncertain)):
                    service.build_bundle(project_context(root), source, [reference], reference,
                        {'retry_attempts': 2}, publish=Mock(), write_temporary=Mock(), render=render, assemble=Mock())
                self.assertEqual(render.call_count, count)

    def test_stage_order_and_layout(self):
        self.assertEqual(STAGES[STAGES.index('storyboard') + 1], 'animatic')
        self.assertEqual(STAGES[STAGES.index('animatic') + 1], 'assets')
        self.assertTrue(stage_layout.validate_stage_contract())

    def test_old_directory_is_only_a_read_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(write_dir(root, 'assets'), root / '05资产管理')
            self.assertIn(root / '04资产管理', read_dirs(root, 'assets'))
            self.assertFalse((root / '04资产管理').exists())

    def test_shots_require_prompt_duration_and_unique_id(self):
        shot = {'id': 's1', 'prompt': '角色站在门边', 'duration': 2}
        self.assertEqual(service.shots_of({'shots': [shot]})[0]['seconds'], 2)
        for rows in ([], [shot, shot], [dict(shot, duration=0)], [dict(shot, id='../escape')]):
            with self.assertRaises(ValueError):
                service.shots_of({'shots': rows})

    def test_publication_rejects_escape_and_rolls_back_index_failure(self):
        """REQ-S04-30：成果路径越界即拒绝，索引更新失败整包回滚、不留半包。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = write_dir(root, 'animatic')
            folder.mkdir()
            manifest = folder / service.MANIFEST
            manifest.write_bytes(b'old')
            with self.assertRaises(ValueError):
                publish_animatic_bundle(root, {service.MANIFEST: b'{}', '../escape': b'x'}, validate=lambda _: True)
            def fail():
                raise RuntimeError('index failure')
            with self.assertRaises(RuntimeError):
                publish_animatic_bundle(root, {service.MANIFEST: b'new'}, validate=lambda _: True, update_index=fail)
            self.assertEqual(manifest.read_bytes(), b'old')
            self.assertFalse((folder / 'animatic_index.json').exists())

    def test_confirmation_cannot_replace_missing_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = write_dir(root, 'animatic')
            folder.mkdir()
            (folder / service.MANIFEST).write_text(json.dumps({'kind': 'animatic', 'confirmed':
                dict.fromkeys(service.CONFIRMATIONS, True)}), encoding='utf-8')
            self.assertFalse(service.evidence(root)[0])

    # --- REQ-S04-90/91：锁定＝三项确认＋时长回写原子事务 -------------------
    def _locked_setup(self, root, shot_durations):
        """建已采用分镜＋版本化成果清单＋timeline.json，返回 (source, folder, board_durations)。"""
        from stage_execution_service import load_or_sync_animatic_timeline
        shots = [{'id': sid, 'duration': duration} for sid, duration in shot_durations]
        board = {'episode_id': 'EP001', 'title': '集',
                 'duration': sum(s['duration'] for s in shots),
                 'shots': [dict(shot, title='镜', video_prompt='提示词' + shot['id'],
                                characters=[], location='LOC_01',
                                frame='frames/%s.png' % shot['id'], dialogue=[]) for shot in shots]}
        source = root / '03初步分镜' / '分镜拆分' / 'ep1.json'
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
        (root / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': [source.relative_to(root).as_posix()]}),
            encoding='utf-8')
        timeline = load_or_sync_animatic_timeline(root)
        folder = write_dir(root, 'animatic')
        files = {}
        for row in timeline['shots']:
            image = '镜头/%s/v1.png' % row['id']
            target = folder / image
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'image-' + row['id'].encode())
            files[image] = target.read_bytes()
        (folder / '版本').mkdir(parents=True)
        (folder / '版本' / 'animatic_v001.mp4').write_bytes(b'video')
        (folder / 'assets').mkdir(parents=True, exist_ok=True)
        (folder / 'assets' / 'temporary_audio.wav').write_bytes(b'audio')
        files['版本/animatic_v001.mp4'] = b'video'
        files['assets/temporary_audio.wav'] = b'audio'
        self._write_manifest(root, folder, source, files, timeline)
        return source, folder

    def _write_manifest(self, root, folder, source, files, timeline):
        manifest = {'version': 1, 'kind': 'animatic',
                    'source': source.relative_to(root).as_posix(),
                    'source_sha256': service.digest(source.read_bytes()),
                    'shots': [{'id': row['id'], 'image': '镜头/%s/v1.png' % row['id'],
                               'seconds': row['seconds'], 'image_version': 1}
                              for row in timeline['shots']],
                    'video': '版本/animatic_v001.mp4', 'audio': 'assets/temporary_audio.wav',
                    'files': {name: service.digest(raw) for name, raw in files.items()},
                    'confirmed': dict.fromkeys(service.CONFIRMATIONS, False)}
        (folder / service.MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False),
                                              encoding='utf-8')

    def _recompose_manifest(self, root, folder, source, seconds):
        """模拟「重新合成」：清单逐镜时长换成时间线新值、确认重置为全 False。"""
        import infra.file_cache as file_cache
        timeline = file_cache.read_json(folder / 'timeline.json')
        manifest = json.loads((folder / service.MANIFEST).read_text(encoding='utf-8'))
        manifest['shots'] = [dict(row, seconds=seconds[row['id']]) for row in manifest['shots']]
        manifest['confirmed'] = dict.fromkeys(service.CONFIRMATIONS, False)
        (folder / service.MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False),
                                              encoding='utf-8')
        file_cache.published(folder / service.MANIFEST)

    def test_req_s04_90_lock_needs_three_confirmations_and_fresh_composition(self):
        """REQ-S04-90：三项不全拒绝；时间线时长与最新合成清单不一致时拒绝锁定且不改 S03。"""
        from stage_execution_service import lock_animatic, update_animatic_shot
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, folder = self._locked_setup(root, [('SH001', 3), ('SH002', 4)])
            with self.assertRaisesRegex(ValueError, '全部确认'):
                lock_animatic(root, rhythm=True, duration=False, dialogue_sync=True)
            update_animatic_shot(root, 'SH001', seconds=10)
            with self.assertRaisesRegex(ValueError, '时间线改过，请先重新合成'):
                lock_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            board = json.loads(source.read_text(encoding='utf-8'))
            self.assertEqual(board['shots'][0]['duration'], 3, '拒绝锁定不得回写 S03')
            manifest = json.loads((folder / service.MANIFEST).read_text(encoding='utf-8'))
            self.assertEqual(manifest['confirmed'], dict.fromkeys(service.CONFIRMATIONS, False))

    def test_req_s04_90_lock_writes_archive_durations_new_sha_and_confirmation(self):
        """REQ-S04-90/91：历史版本存档→原文件只改时长→清单新摘要＋三项确认；S03 再改即失效。"""
        from stage_execution_service import lock_animatic, update_animatic_shot
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, folder = self._locked_setup(root, [('SH001', 3), ('SH002', 4)])
            update_animatic_shot(root, 'SH001', seconds=10)
            self._recompose_manifest(root, folder, source, {'SH001': 10, 'SH002': 4})
            lock_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            board = json.loads(source.read_text(encoding='utf-8'))
            self.assertEqual(board['shots'][0]['duration'], 10)
            self.assertEqual(board['shots'][0]['video_prompt'], '提示词SH001')
            self.assertEqual(board['duration'], 14, '顶层时长等于各镜之和')
            archives = list((source.parent / '历史版本').glob('ep1_*.json'))
            self.assertEqual(len(archives), 1, '回写前 S03 原样进同目录历史版本')
            manifest = json.loads((folder / service.MANIFEST).read_text(encoding='utf-8'))
            self.assertEqual(manifest['source_sha256'], service.digest(source.read_bytes()))
            self.assertEqual(manifest['confirmed'], dict.fromkeys(service.CONFIRMATIONS, True))
            self.assertTrue(service.evidence(root)[0])
            board['shots'][0]['duration'] = 9
            source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
            self.assertFalse(service.evidence(root)[0], 'REQ-S04-91：锁定后 S03 再改自动回未确认')

    def test_req_s04_90_rollback_restores_source_and_unconfirmed_manifest(self):
        """REQ-S04-90：任一步失败全回滚——S03 原字节恢复、无存档残留、清单仍全 False。"""
        from stage_execution_service import lock_animatic, update_animatic_shot
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, folder = self._locked_setup(root, [('SH001', 3), ('SH002', 4)])
            update_animatic_shot(root, 'SH001', seconds=10)
            self._recompose_manifest(root, folder, source, {'SH001': 10, 'SH002': 4})
            original = source.read_bytes()
            manifest_before = (folder / service.MANIFEST).read_bytes()
            with patch('orchestrator.storyboard_selection.adopt',
                       side_effect=RuntimeError('adopt broke')):
                with self.assertRaises(RuntimeError):
                    lock_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            self.assertEqual(source.read_bytes(), original, '失败必须恢复 S03 原文件字节')
            self.assertEqual((folder / service.MANIFEST).read_bytes(), manifest_before)
            history = source.parent / '历史版本'
            self.assertFalse(history.exists() and list(history.glob('*.json')),
                             '失败不留存档垃圾')
            manifest = json.loads(manifest_before)
            self.assertEqual(manifest['confirmed'], dict.fromkeys(service.CONFIRMATIONS, False))

    def test_req_s04_90_identical_durations_confirm_without_writeback(self):
        """REQ-S04-90：时间线时长与 S03 一致时不回写——无历史版本、原文件不动、只写确认。"""
        from stage_execution_service import lock_animatic
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, folder = self._locked_setup(root, [('SH001', 3), ('SH002', 4)])
            original = source.read_bytes()
            lock_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((source.parent / '历史版本').exists())
            manifest = json.loads((folder / service.MANIFEST).read_text(encoding='utf-8'))
            self.assertEqual(manifest['confirmed'], dict.fromkeys(service.CONFIRMATIONS, True))
            self.assertTrue(service.evidence(root)[0])


if __name__ == '__main__':
    unittest.main()
