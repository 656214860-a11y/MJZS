"""REQ-S04 测试锚定：分镜预演（S04）的输入、参考图、草图、合成、发布与确认。

只使用 ``tempfile`` 临时项目与桩件，不联网、不开 Tk。每条测试名与 docstring 都写明锚定的
``REQ-S04-xx``，断言对应需求原文里可判定的那句行为；已有 S04 测试文件由 docstring 认领其
已覆盖的条目，本文件补上尚无锚点的部分。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from domain import animatic_service as service
import script_contract
from contract import script_output_spec
import stage_parallel
from domain.animatic_service import CONFIRMATIONS, MANIFEST, build_bundle, local_sketch, prepare_reference, validate_bundle
from project_context_factory import project_context
from stage_completion_service import completion_evidence
from stage_execution_service import (
    animatic_reference_paths,
    animatic_video,
    confirm_animatic,
    import_animatic_references,
    publish_animatic_bundle,
    run_animatic,
)
from contract.stage_path_service import shared_reference_dir, write_dir


def _source(root, shots=None):
    path = root / 'storyboard_draft.json'
    path.write_text(json.dumps({'shots': shots if shots is not None else [
        {'id': 's1', 'prompt': '门边的人', 'duration': 2}]}, ensure_ascii=False), encoding='utf-8')
    return path


class ReqS04AnchorTests(unittest.TestCase):
    # --- 输入与本地依赖 -------------------------------------------------
    def test_req_s04_02_requires_adopted_source_reference_and_temporary_sound(self):
        """REQ-S04-02：输入三样——已采用分镜、至少一张非空参考图、导入音频或 TTS 文本。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = _source(root)
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            context = project_context(root)
            with self.assertRaisesRegex(ValueError, '共享参考图'):
                build_bundle(context, source, [], None, {'tts_text': '你好'},
                             publish=Mock(), write_temporary=Mock())
            empty = root / 'empty.png'
            empty.write_bytes(b'')
            with self.assertRaisesRegex(ValueError, '共享参考图'):
                build_bundle(context, source, [empty], None, {'tts_text': '你好'},
                             publish=Mock(), write_temporary=Mock())
            with self.assertRaisesRegex(ValueError, '临时音频或填写临时 TTS'):
                build_bundle(context, source, [reference], None, {},
                             publish=Mock(), write_temporary=Mock())
            with patch('stage_parallel.evaluate', return_value={'ok': True}):
                with self.assertRaisesRegex(ValueError, '请选择已采用的本项目分镜初稿'):
                    run_animatic(root, source, [reference], reference,
                                 {'ffmpeg': 'stub', 'ffprobe': 'stub'})

    def test_req_s04_06_local_tools_and_comfy_readiness_gate_before_generating(self):
        """REQ-S04-06：ffmpeg／ffprobe 可解析、本地 ComfyUI 就绪，缺一项直接报错且不留半成品。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = _source(root)
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            audio = root / 'temporary.wav'
            audio.write_bytes(b'audio')
            with patch('contract.platform_tools.tool_path', return_value=''):
                with self.assertRaisesRegex(ValueError, 'ffmpeg'):
                    run_animatic(root, source, [reference], audio, {})
            self.assertFalse((write_dir(root, 'animatic') / MANIFEST).exists())
            ready = Mock(side_effect=RuntimeError('comfy not ready'))
            with patch('contract.platform_tools.tool_path', return_value='stub'), \
                    patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('storyboard_selection.adopted', return_value=(str(source),)), \
                    patch('comfy_runtime.wait_comfy', ready):
                with self.assertRaisesRegex(RuntimeError, 'comfy not ready'):
                    run_animatic(root, source, [reference], audio, {})
            ready.assert_called_once()
            self.assertFalse((write_dir(root, 'animatic') / MANIFEST).exists())

    # --- 共享参考图 -----------------------------------------------------
    def test_req_s04_10_reference_import_is_validated_and_content_addressed(self):
        """REQ-S04-10：导入仅 PNG/JPEG/WebP 且 ≤20 MB，按内容摘要命名去重，发布到共享目录。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            good = root / 'a.png'
            good.write_bytes(b'png-bytes')
            target = shared_reference_dir(root) / (service.digest(b'png-bytes') + '.png')
            self.assertEqual(tuple(import_animatic_references(root, [good])), (target,))
            self.assertEqual(target.read_bytes(), b'png-bytes')
            self.assertTrue(target.is_relative_to(shared_reference_dir(root)))
            twin = root / 'b.png'
            twin.write_bytes(b'png-bytes')
            self.assertEqual(import_animatic_references(root, [twin])[0], target, '同内容按摘要命名并复用')
            bad = root / 'a.gif'
            bad.write_bytes(b'x')
            with self.assertRaises(ValueError):
                import_animatic_references(root, [bad])
            big = root / 'big.png'
            with big.open('wb') as stream:
                stream.seek(20 * 1024 * 1024)
                stream.write(b'x')
            with self.assertRaises(ValueError):
                import_animatic_references(root, [big])
            with self.assertRaises(ValueError):
                prepare_reference(root, '', 'model', {}, publish=lambda paths: paths)
            with self.assertRaises(ValueError):
                prepare_reference(root, '描述', '  ', {}, publish=lambda paths: paths)

    def test_req_s04_11_reads_new_and_old_reference_dirs_without_duplicates(self):
        """REQ-S04-11：读取覆盖新旧共享参考图目录，按路径去重。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = shared_reference_dir(root)
            current.mkdir(parents=True)
            (current / 'n.png').write_bytes(b'n')
            legacy = root / '04资产管理' / '参考图'
            legacy.mkdir(parents=True)
            (legacy / 'o.jpg').write_bytes(b'o')
            (current / 'note.txt').write_text('x', encoding='utf-8')
            paths = animatic_reference_paths(root)
            self.assertIn(current / 'n.png', paths)
            self.assertIn(legacy / 'o.jpg', paths)
            self.assertNotIn(current / 'note.txt', paths)
            self.assertEqual(len(paths), len(set(paths)))

    # --- 草图与合成 -----------------------------------------------------
    def test_req_s04_20_sketch_uses_prompt_all_references_and_fixed_seed(self):
        """REQ-S04-20：草图用分镜提示词、全部共享参考图和固定种子（默认 1）生成，提示词带声明。"""
        class FakeComfy:
            def __init__(self):
                self.calls = {}
            def reference_config(self):
                return {'marker': 1}
            def reference_graph(self, prompt, images, cfg):
                self.calls['prompt'] = prompt
                self.calls['images'] = list(images)
                graph = {'1': {'class_type': 'KSampler', 'inputs': {'seed': 7, 'noise_seed': 8, 'steps': 20}},
                         '2': {'class_type': 'CheckpointLoader', 'inputs': {}}}
                self.calls['graph'] = graph
                return graph
            def submit_graph(self, root, kind, prompt, graph):
                self.calls['submit'] = (kind, prompt)
                return Path(root) / 'receipt.json'
            def collect(self, root, record):
                return [str(self.calls['image'])]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / 'ws'
            workspace.mkdir()
            image = root / 'shot.png'
            image.write_bytes(b'image')
            for settings, expected_seed in (({}, 1), ({'seed': 42}, 42)):
                client = FakeComfy()
                client.calls['image'] = image
                shot = {'id': 's1', 'prompt': '角色站在门边', 'seconds': 2}
                references = [root / 'r1.png', root / 'r2.png']
                self.assertEqual(local_sketch(workspace, shot, references, settings, client=client), image)
                self.assertTrue(client.calls['prompt'].startswith('只生成分镜预演草图，不是正式资产或首帧'))
                self.assertIn('角色站在门边', client.calls['prompt'])
                self.assertEqual(client.calls['images'], references)
                self.assertEqual(client.calls['submit'][0], 'scenes')
                self.assertEqual(client.calls['graph']['1']['inputs']['seed'], expected_seed)
                self.assertEqual(client.calls['graph']['1']['inputs']['noise_seed'], expected_seed)

    def test_req_s04_23_uncertain_submission_is_not_resubmitted_and_keeps_run_workspace(self):
        """REQ-S04-23：排队／超时不自动重投，报错请人工核查；回执留在持久工作区 run-*。"""
        class StalledComfy:
            def __init__(self):
                self.submits = 0
            def reference_config(self):
                return {}
            def reference_graph(self, prompt, images, cfg):
                return {'1': {'inputs': {'seed': 1}}}
            def submit_graph(self, *args, **kwargs):
                self.submits += 1
                return Path('receipt')
            def collect(self, *args, **kwargs):
                return []

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = StalledComfy()
            with self.assertRaisesRegex(ValueError, '不自动重复提交'):
                local_sketch(root, {'id': 's1', 'prompt': 'p', 'seconds': 1}, [root / 'r.png'],
                             {'timeout': 0}, client=client)
            self.assertEqual(client.submits, 1, '超时不得自动重投')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = _source(root, shots=[])
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            audio = root / 'temporary.wav'
            audio.write_bytes(b'audio')
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('storyboard_selection.adopted', return_value=(str(source),)), \
                    patch('comfy_runtime.wait_comfy'):
                with self.assertRaises(ValueError):
                    run_animatic(root, source, [reference], audio, {'ffmpeg': 'stub', 'ffprobe': 'stub'})
            work = write_dir(root, 'animatic') / '.work'
            self.assertTrue(any(item.is_dir() and item.name.startswith('run-') for item in work.iterdir()))

    # --- 发布与确认 -----------------------------------------------------
    def _ready_bundle(self, root):
        source = _source(root)
        reference = root / 'reference.png'
        reference.write_bytes(b'reference')
        audio = root / 'temporary.wav'
        audio.write_bytes(b'audio')

        def render(workspace, *_args):
            target = workspace / 'image.png'
            target.write_bytes(b'image')
            return target

        def assemble(images, durations, sound, target, **_kwargs):
            target.write_bytes(b'video')
            return target

        result = build_bundle(project_context(root), source, [reference], audio,
                              {'ffmpeg': 'stub', 'ffprobe': 'stub'},
                              publish=lambda artifacts: publish_animatic_bundle(
                                  root, artifacts, validate=lambda _: True),
                              write_temporary=lambda path, raw: path.write_bytes(raw),
                              render=render, assemble=assemble)
        self.assertTrue(result.ok, result.reason)
        return source

    def test_req_s04_30_publishes_all_artifacts_into_the_stage_folder(self):
        """REQ-S04-30：成果写入 04分镜预演/（清单、视频、临时声音、每镜图、发布器索引）。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._ready_bundle(root)
            folder = write_dir(root, 'animatic')
            for name in (MANIFEST, 'assets/animatic.mp4', 'assets/temporary_audio.wav',
                         'assets/shots/s1.png', 'animatic_index.json'):
                self.assertTrue((folder / name).is_file(), name)
            index = json.loads((folder / 'animatic_index.json').read_text(encoding='utf-8'))
            self.assertEqual(index['manifest'], MANIFEST)
            self.assertIn(MANIFEST, index['files'])

    def test_req_s04_31_bundle_validation_checks_files_mapping_and_unsigned(self):
        """REQ-S04-31：整包校验——files 一一对应、媒体在 files 内非空、confirmed 全 false、索引保留名。"""
        media = {'assets/animatic.mp4': b'v', 'assets/temporary_audio.wav': b'a',
                 'assets/shots/s1.png': b'i'}
        manifest = {'version': 1, 'kind': 'animatic', 'video': 'assets/animatic.mp4',
                    'audio': 'assets/temporary_audio.wav', 'shots': [{'id': 's1', 'image': 'assets/shots/s1.png'}],
                    'files': {name: service.digest(raw) for name, raw in media.items()},
                    'confirmed': {key: False for key in CONFIRMATIONS}}

        def bundle(row, rows=None):
            return dict(rows if rows is not None else media,
                        **{MANIFEST: json.dumps(row).encode('utf-8')})

        self.assertTrue(validate_bundle(bundle(manifest)))
        self.assertFalse(validate_bundle(bundle(manifest, dict(media, **{'assets/extra.png': b'x'}))),
                         'files 与媒体文件必须一一对应')
        self.assertFalse(validate_bundle(bundle(dict(manifest, confirmed={key: True for key in CONFIRMATIONS}))),
                         '生成器不得替用户签字')
        self.assertFalse(validate_bundle(bundle(dict(manifest, video='assets/missing.mp4'))))
        self.assertFalse(validate_bundle(bundle(dict(manifest, kind='storyboard'))))
        self.assertFalse(validate_bundle(bundle(manifest, dict(media, **{'assets/shots/s1.png': b''}))))
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                publish_animatic_bundle(Path(temporary), {MANIFEST: b'{}', 'animatic_index.json': b'x'},
                                        validate=lambda _: True)

    def test_req_s04_32_source_change_during_generation_blocks_publication(self):
        """REQ-S04-32：清单记来源相对路径与 SHA-256；生成期间来源被改动则本次不发布。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = _source(root)
            reference = root / 'reference.png'
            reference.write_bytes(b'reference')
            audio = root / 'temporary.wav'
            audio.write_bytes(b'audio')
            publisher = Mock()

            def render(workspace, *_args):
                target = workspace / 'image.png'
                target.write_bytes(b'image')
                return target

            def assemble(images, durations, sound, target, **_kwargs):
                target.write_bytes(b'video')
                source.write_text('{}', encoding='utf-8')
                return target

            with self.assertRaisesRegex(ValueError, '生成期间分镜已变化'):
                build_bundle(project_context(root), source, [reference], audio,
                             {'ffmpeg': 'stub', 'ffprobe': 'stub'}, publish=publisher,
                             write_temporary=lambda path, raw: path.write_bytes(raw),
                             render=render, assemble=assemble)
            publisher.assert_not_called()

    def test_req_s04_33_video_path_available_for_complete_unconfirmed_bundle(self):
        """REQ-S04-33：成果完整（无需已确认）即可拿到 animatic_video 路径，否则报原因。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._ready_bundle(root)
            self.assertEqual(animatic_video(root),
                             write_dir(root, 'animatic') / 'assets' / 'animatic.mp4')
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                animatic_video(Path(temporary))

    def test_req_s04_40_confirmation_needs_all_three_and_regeneration_resets(self):
        """REQ-S04-40：三项须一次全勾选才能确认；成果不完整不能确认；重新生成重置为未确认。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._ready_bundle(root)
            with self.assertRaisesRegex(ValueError, '全部确认'):
                confirm_animatic(root, rhythm=True, duration=True, dialogue_sync=False)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                confirm_animatic(Path(temporary), rhythm=True, duration=True, dialogue_sync=True)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._ready_bundle(root)
            confirm_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            manifest = json.loads((write_dir(root, 'animatic') / MANIFEST).read_text(encoding='utf-8'))
            self.assertTrue(all(manifest['confirmed'].values()))
            self.assertTrue(service.evidence(root)[0])
            self._ready_bundle(root)
            manifest = json.loads((write_dir(root, 'animatic') / MANIFEST).read_text(encoding='utf-8'))
            self.assertEqual(manifest['confirmed'], dict.fromkeys(CONFIRMATIONS, False))
            self.assertFalse(service.evidence(root)[0])

    def test_req_s04_42_sg_b_reuses_the_same_completion_verification(self):
        """REQ-S04-42：SG-B 与阶段完成核验共用 animatic_service.evidence，不另立判定。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('domain.animatic_service.evidence', return_value=(False, '同一核验')) as shared:
                self.assertFalse(stage_parallel.animatic_ready(root)['ok'])
                self.assertEqual(stage_parallel.animatic_ready(root)['detail'], '同一核验')
                self.assertEqual(completion_evidence(root, 'animatic'), (False, '同一核验'))
            self.assertTrue(shared.call_count >= 2)

    def test_req_s04_52_skill_only_promises_the_locks_the_stage_reads(self):
        """REQ-S04-52：SKILL 只声明本阶段实际读取的画幅／预览规格，不再承诺配置缺口门禁。"""
        text = (Path(__file__).resolve().parents[1] / 'skills' /
                '04 分镜预演SKILL' / 'pipeline-animatic.skill.md').read_text(encoding='utf-8')
        self.assertNotIn('配置缺口', text)
        self.assertNotIn('返回准备阶段', text)
        self.assertIn('画幅', text)
        self.assertNotIn('animatic', script_contract.STAGE_LOCK_REQUIREMENTS,
                         '代码事实：本阶段没有必填制作锁')
        self.assertEqual(script_output_spec.preview_spec({'aspect_ratio': '9:16'})['aspect_ratio'],
                         '9:16', '代码事实：预览规格继续读取项目画幅')

    # --- 时间线与锁定（REQ-S04-80…91）------------------------------------
    def _locked_project(self, root, shot_durations):
        """已采用分镜＋版本化成果清单＋timeline.json 的锁定就绪项目。"""
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
        manifest = {'version': 1, 'kind': 'animatic',
                    'source': source.relative_to(root).as_posix(),
                    'source_sha256': service.digest(source.read_bytes()),
                    'shots': [{'id': row['id'], 'image': '镜头/%s/v1.png' % row['id'],
                               'seconds': row['seconds'], 'image_version': 1}
                              for row in timeline['shots']],
                    'video': '版本/animatic_v001.mp4', 'audio': 'assets/temporary_audio.wav',
                    'files': {name: service.digest(raw) for name, raw in files.items()},
                    'confirmed': dict.fromkeys(CONFIRMATIONS, False)}
        (folder / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False),
                                      encoding='utf-8')
        return source, folder

    def test_req_s04_90_lock_without_bundle_is_rejected(self):
        """REQ-S04-90：没有可用清单与时间线时锁定直接拒绝，不落任何文件。"""
        from stage_execution_service import lock_animatic
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                lock_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            folder = write_dir(root, 'animatic')
            self.assertFalse((folder / 'timeline.json').exists())
            self.assertFalse((folder / MANIFEST).exists())

    def test_req_s04_91_sg_b_flips_back_to_unconfirmed_after_source_edit(self):
        """REQ-S04-91：锁定使 SG-B 通过；S03 再被改动，同一核验自动回到未确认。"""
        from stage_execution_service import lock_animatic
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, _folder = self._locked_project(root, [('SH001', 3), ('SH002', 4)])
            lock_animatic(root, rhythm=True, duration=True, dialogue_sync=True)
            self.assertTrue(stage_parallel.animatic_ready(root)['ok'])
            board = json.loads(source.read_text(encoding='utf-8'))
            board['shots'][0]['duration'] = 9
            source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
            self.assertFalse(stage_parallel.animatic_ready(root)['ok'])
            self.assertFalse(completion_evidence(root, 'animatic')[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
