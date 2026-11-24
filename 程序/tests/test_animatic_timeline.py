"""离线验证预演合成命令与媒体核验，不调用外部进程。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from contract.stage_path_service import write_dir
from domain.edit_service import assemble_image_timeline


class AnimaticTimelineTests(unittest.TestCase):
    def render(self, root, info):
        self.commands = []
        def execute(command, **options):
            self.commands.append(command)
            self.assertTrue(options['check'])
            self.assertTrue(options['capture_output'])
            self.assertGreater(options['timeout'], 0)
            return SimpleNamespace(stdout=json.dumps(info))
        return assemble_image_timeline([root / '镜头.png'], [2], root / '临时.wav',
            root / 'animatic.mp4', ffmpeg='ffmpeg', ffprobe='ffprobe',
            write_temporary=lambda path, raw: path.write_bytes(raw), run=execute)

    def test_timeline_maps_audio_and_decodes_before_success(self):
        """REQ-S04-25：拼接后叠加声音、含视频与音频流、总时长匹配且完整解码后才算通过。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.render(root, {'streams': [{'codec_type': 'video'}, {'codec_type': 'audio'}],
                                       'format': {'duration': '2'}})
            self.assertEqual(result, root / 'animatic.mp4')
            self.assertEqual(len(self.commands), 4)
            self.assertIn('1:a:0', self.commands[1])
            self.assertIn('-xerror', self.commands[-1])
            self.assertEqual((root / 'animatic_concat.txt').read_text(), "file 'segment_0000.mp4'\n")

    def test_missing_audio_and_wrong_duration_are_rejected(self):
        """REQ-S04-25：缺音频流或总时长与各镜之和相差超过 1 秒即不发布。"""
        for streams, duration in [([{'codec_type': 'video'}], '2'),
                                  ([{'codec_type': 'video'}, {'codec_type': 'audio'}], '20')]:
            with self.subTest(streams=streams, duration=duration), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(ValueError, '核验失败'):
                    self.render(Path(temporary), {'streams': streams, 'format': {'duration': duration}})

    def test_invalid_duration_never_starts_process(self):
        """REQ-S04-25：每镜时长必须有限且在 0–600 秒内，无效输入不得启动编码进程。"""
        def forbidden(*args, **kwargs):
            self.fail('无效输入不应启动进程')
        with self.assertRaises(ValueError):
            assemble_image_timeline(['image.png'], [float('nan')], 'audio.wav', 'out.mp4',
                ffmpeg='ffmpeg', ffprobe='ffprobe', write_temporary=forbidden, run=forbidden)


class MixedAudioRenderTests(unittest.TestCase):
    def test_req_s04_74_76_mixed_audio_runs_injected_command_in_scratch_area(self):
        """REQ-S04-74/76：混音命令由 L3 注入后原样执行，edit_service 不 import animatic_audio。"""
        from domain.edit_service import render_mixed_audio
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'mixed.wav'
            commands = []
            def execute(command, **options):
                commands.append(command)
                self.assertTrue(options['check'])
                self.assertTrue(options['capture_output'])
                return SimpleNamespace(stdout='')
            built = []
            def mix(path, total, **kwargs):
                built.append((path, total, kwargs))
                return ['ffmpeg', '-i', 'voice.wav', '-t', str(total), str(path)]
            result = render_mixed_audio(output, 4.5, ffmpeg='ffmpeg', run=execute,
                full_track='track.mp3', dialogue_clips=({'path': 'd1.mp3', 'start_ms': 500},),
                music='bgm.mp3', mix_command=mix)
            self.assertEqual(result, output)
            self.assertEqual(built, [(output, 4.5, {'full_track': 'track.mp3',
                'dialogue_clips': ({'path': 'd1.mp3', 'start_ms': 500},),
                'music': 'bgm.mp3', 'ffmpeg': 'ffmpeg'})])
            self.assertEqual(commands, [['ffmpeg', '-i', 'voice.wav', '-t', '4.5', str(output)]])

    def test_req_s04_76_mixed_audio_requires_l3_injected_command(self):
        """REQ-S04-76：未注入混音命令时拒绝编造 ffmpeg 参数。"""
        from domain.edit_service import render_mixed_audio
        with self.assertRaises(TypeError):
            render_mixed_audio('out.wav', 1.0, ffmpeg='ffmpeg')


class TimelineModelTests(unittest.TestCase):
    """REQ-S04-80…85：domain.animatic_timeline 纯模型——build/set_*/版本命名/回写计划。"""

    def test_req_s04_80_build_creates_stamped_timeline_with_board_defaults(self):
        from domain import animatic_timeline as timeline_model
        import contract.artifact_schema as artifact_schema
        board = {'shots': [{'id': 'SH001', 'duration': 3}, {'id': 'SH002', 'duration': 5}]}
        timeline, rebuilt = timeline_model.build(board, '03初步分镜/分镜拆分/ep1.json', 'sha-x')
        self.assertFalse(rebuilt)
        self.assertEqual(timeline['kind'], 'animatic_timeline')
        self.assertEqual(timeline['schema_version'], 1)
        self.assertEqual(timeline['source'], '03初步分镜/分镜拆分/ep1.json')
        self.assertEqual(timeline['source_sha256'], 'sha-x')
        self.assertEqual([row['id'] for row in timeline['shots']], ['SH001', 'SH002'])
        row = timeline['shots'][0]
        self.assertEqual(row['seconds'], 3)
        self.assertEqual(row['image_version'], 0)
        self.assertEqual(row['source'], 'generated')
        self.assertEqual(row['references'], [])
        self.assertIsNone(row['dialogue_audio'])
        self.assertEqual(row['note'], '')
        self.assertEqual(artifact_schema.validate('animatic_timeline', timeline), [])

    def test_req_s04_81_set_duration_accepts_only_int_seconds_2_to_15(self):
        from domain import animatic_timeline as timeline_model
        timeline, _ = timeline_model.build({'shots': [{'id': 'SH001', 'duration': 3}]}, 'a.json', 'x')
        updated = timeline_model.set_duration(timeline, 'SH001', 12)
        self.assertEqual(updated['shots'][0]['seconds'], 12)
        self.assertEqual(timeline['shots'][0]['seconds'], 3, '必须返回新副本而不改原时间线')
        for bad in (1, 16, 3.5, True, '5', 0, -2, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                timeline_model.set_duration(timeline, 'SH001', bad)
        with self.assertRaises(ValueError):
            timeline_model.set_duration(timeline, 'SH999', 5)

    def test_req_s04_82_84_version_counters_never_reuse_existing_names(self):
        from domain import animatic_timeline as timeline_model
        self.assertEqual(timeline_model.next_version([]), 1)
        self.assertEqual(timeline_model.next_version(['v1.png', 'v2.jpg', 'note.txt']), 3)
        self.assertEqual(timeline_model.next_version(['镜头/SH001/v9.png']), 10)
        self.assertEqual(timeline_model.next_video_name([]), '版本/animatic_v001.mp4')
        self.assertEqual(
            timeline_model.next_video_name(['animatic_v001.mp4', 'animatic_v007.mp4', 'x.txt']),
            '版本/animatic_v008.mp4')

    def test_req_s04_85_rebuild_keeps_same_ids_drops_removed_and_defaults_new(self):
        from domain import animatic_timeline as timeline_model
        board = {'shots': [{'id': 'SH001', 'duration': 3},
                           {'id': 'SH002', 'duration': 4}, {'id': 'SH003', 'duration': 6}]}
        timeline, _ = timeline_model.build(board, 'ep1.json', 'old-sha')
        timeline = timeline_model.set_duration(timeline, 'SH001', 12)
        timeline = timeline_model.set_version(timeline, 'SH003', 2, source='imported')
        timeline = timeline_model.set_note(timeline, 'SH001', '慢镜头')
        new_board = {'shots': [{'id': 'SH001', 'duration': 3},
                               {'id': 'SH003', 'duration': 6}, {'id': 'SH004', 'duration': 7}]}
        rebuilt, flag = timeline_model.build(new_board, 'ep1.json', 'new-sha', previous=timeline)
        self.assertTrue(flag)
        rows = {row['id']: row for row in rebuilt['shots']}
        self.assertEqual(list(rows), ['SH001', 'SH003', 'SH004'])
        self.assertNotIn('SH002', rows)
        self.assertEqual((rows['SH001']['seconds'], rows['SH001']['note']), (12, '慢镜头'))
        self.assertEqual((rows['SH003']['image_version'], rows['SH003']['source']), (2, 'imported'))
        self.assertEqual((rows['SH004']['seconds'], rows['SH004']['image_version']), (7, 0))
        self.assertEqual(rebuilt['source_sha256'], 'new-sha')

    def test_req_s04_90_writeback_plan_changes_only_duration_fields(self):
        from domain import animatic_timeline as timeline_model
        board = {'duration': 8, 'episode_id': 'EP001', 'shots': [
            {'id': 'SH001', 'duration': 3, 'video_prompt': '甲'},
            {'id': 'SH002', 'duration': 5, 'video_prompt': '乙',
             'trim_in': 1, 'trim_out': 5, 'edit_duration': 4}]}
        timeline, _ = timeline_model.build(board, 'ep1.json', 'x')
        timeline = timeline_model.set_duration(timeline, 'SH001', 10)
        timeline = timeline_model.set_duration(timeline, 'SH002', 4)
        plan, changed = timeline_model.writeback_plan(board, timeline)
        self.assertTrue(changed)
        self.assertEqual(plan['shots'][0]['duration'], 10)
        second = plan['shots'][1]
        self.assertEqual((second['duration'], second['trim_in'], second['trim_out'],
                          second['edit_duration']), (4, 1, 4, 3),
                         'trim_out 夹紧到新时长并重算 edit_duration')
        self.assertEqual(plan['duration'], 14, '顶层时长等于各镜之和')
        self.assertEqual(plan['shots'][0]['video_prompt'], '甲', '只改时长，不动提示词与对白')
        self.assertEqual(board['shots'][0]['duration'], 3, '返回深拷贝，不改原分镜')
        _, unchanged = timeline_model.writeback_plan(
            board, timeline_model.build(board, 'ep1.json', 'x')[0])
        self.assertFalse(unchanged)

    def test_req_s04_90_trim_in_beyond_clamped_out_is_reset(self):
        from domain import animatic_timeline as timeline_model
        board = {'shots': [{'id': 'SH001', 'duration': 5,
                            'trim_in': 4, 'trim_out': 5, 'edit_duration': 1}]}
        timeline, _ = timeline_model.build(board, 'ep1.json', 'x')
        timeline = timeline_model.set_duration(timeline, 'SH001', 3)
        plan, changed = timeline_model.writeback_plan(board, timeline)
        self.assertTrue(changed)
        shot = plan['shots'][0]
        self.assertEqual((shot['duration'], shot['trim_in'], shot['trim_out'],
                          shot['edit_duration']), (3, 0, 3, 3),
                         'trim_in >= 新 trim_out 时归零')


class TimelineGatewayTests(unittest.TestCase):
    """REQ-S04-80…85 的 L3 组装：timeline.json 持久化、单镜重做／替换、版本化合成。"""

    def _adopted(self, root, shots):
        board = {'episode_id': 'EP001', 'title': '集', 'duration': sum(s['duration'] for s in shots),
                 'shots': [dict(shot, title='镜', video_prompt='提示词' + shot['id'],
                                characters=[], location='LOC_01',
                                frame='frames/%s.png' % shot['id'], dialogue=[]) for shot in shots]}
        path = root / '03初步分镜' / '分镜拆分' / 'ep1.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
        (root / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': [path.relative_to(root).as_posix()]}),
            encoding='utf-8')
        return path

    def test_req_s04_80_85_timeline_persists_and_rebuilds_on_source_change(self):
        from stage_execution_service import load_or_sync_animatic_timeline, update_animatic_shot
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._adopted(root, [{'id': 'SH001', 'duration': 3},
                                          {'id': 'SH002', 'duration': 4}])
            timeline = load_or_sync_animatic_timeline(root)
            tpath = write_dir(root, 'animatic') / 'timeline.json'
            self.assertTrue(tpath.is_file())
            self.assertEqual(timeline['kind'], 'animatic_timeline')
            self.assertEqual(timeline['schema_version'], 1)
            self.assertEqual([row['id'] for row in timeline['shots']], ['SH001', 'SH002'])
            self.assertEqual(timeline['shots'][0]['seconds'], 3)
            timeline = update_animatic_shot(root, 'SH001', seconds=12, note='慢')
            self.assertEqual(json.loads(tpath.read_text(encoding='utf-8'))['shots'][0]['seconds'], 12)
            board = json.loads(source.read_text(encoding='utf-8'))
            board['shots'] = [board['shots'][0],
                              dict(board['shots'][0], id='SH003', video_prompt='新提示')]
            source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
            timeline = load_or_sync_animatic_timeline(root)
            rows = {row['id']: row for row in timeline['shots']}
            self.assertEqual(list(rows), ['SH001', 'SH003'], '删除镜移出、新增镜补入')
            self.assertEqual((rows['SH001']['seconds'], rows['SH001']['note']), (12, '慢'),
                             '同 ID 保留调整后的时长与批注')
            self.assertEqual(json.loads(tpath.read_text(encoding='utf-8'))['shots'][1]['id'], 'SH003')

    def test_req_s04_81_gateway_duration_edit_validates_bounds(self):
        from stage_execution_service import load_or_sync_animatic_timeline, update_animatic_shot
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 3}])
            load_or_sync_animatic_timeline(root)
            for bad in (1, 16, 2.5, True):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    update_animatic_shot(root, 'SH001', seconds=bad)
            timeline = update_animatic_shot(root, 'SH001', seconds=15)
            self.assertEqual(timeline['shots'][0]['seconds'], 15)

    def test_req_s04_82_83_regenerate_and_replace_write_new_image_versions(self):
        from domain import animatic_sketch_backends as backends
        from stage_execution_service import (load_or_sync_animatic_timeline,
            regenerate_animatic_shot, replace_animatic_shot_image)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 3}, {'id': 'SH002', 'duration': 4}])
            load_or_sync_animatic_timeline(root)
            folder = write_dir(root, 'animatic')
            shot_dir = folder / '镜头' / 'SH001'
            shot_dir.mkdir(parents=True)
            (shot_dir / 'v1.png').write_bytes(b'v1')
            calls = []

            def factory(workspace, shot, references, settings):
                calls.append(shot['id'])
                target = workspace / 'new.png'
                target.write_bytes(b'new-image')
                return target

            backends.register('unit_stub', factory)
            self.addCleanup(backends.unregister, 'unit_stub')
            timeline = regenerate_animatic_shot(
                root, 'SH001', settings={'animatic_sketch_backend': 'unit_stub'})
            self.assertEqual(calls, ['SH001'], '只重做单镜')
            self.assertTrue((shot_dir / 'v2.png').is_file())
            row = next(row for row in timeline['shots'] if row['id'] == 'SH001')
            self.assertEqual((row['image_version'], row['source']), (2, 'generated'))
            replacement = root / 'replace.png'
            replacement.write_bytes(b'rep')
            timeline = replace_animatic_shot_image(root, 'SH001', replacement)
            self.assertTrue((shot_dir / 'v3.png').is_file())
            row = next(row for row in timeline['shots'] if row['id'] == 'SH001')
            self.assertEqual((row['image_version'], row['source']), (3, 'imported'))
            self.assertEqual((shot_dir / 'v1.png').read_bytes(), b'v1', '旧版本保留不覆盖')

    def test_req_s04_83_84_run_renders_only_missing_and_versions_video(self):
        """缺图才生成：SH001/SH002 已有当前版本图，仅 SH003 出图；视频进 版本/ 递增。"""
        from domain import animatic_sketch_backends as backends
        from stage_execution_service import run_animatic_timeline
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 2},
                                 {'id': 'SH002', 'duration': 3}, {'id': 'SH003', 'duration': 4}])
            folder = write_dir(root, 'animatic')
            for sid in ('SH001', 'SH002'):
                shot_dir = folder / '镜头' / sid
                shot_dir.mkdir(parents=True)
                (shot_dir / 'v1.png').write_bytes(b'img-' + sid.encode())
            from stage_execution_service import load_or_sync_animatic_timeline, update_animatic_shot
            timeline = load_or_sync_animatic_timeline(root)
            for sid in ('SH001', 'SH002'):
                timeline = update_animatic_shot(root, sid, image_version=1)
            rendered = []

            def factory(workspace, shot, references, settings):
                rendered.append(shot['id'])
                target = workspace / 'image.png'
                target.write_bytes(b'img-' + shot['id'].encode())
                return target

            backends.register('unit_stub', factory)
            self.addCleanup(backends.unregister, 'unit_stub')

            def assemble(images, durations, sound, target, **_kwargs):
                self.assertEqual(durations, [2, 3, 4])
                target.write_bytes(b'video')
                return target

            def run(command, **_kwargs):
                Path(command[-1]).write_bytes(b'mixed')
                return SimpleNamespace(stdout='')

            settings = {'animatic_sketch_backend': 'unit_stub', 'ffmpeg': 'stub',
                        'ffprobe': 'stub', 'run': run}
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble):
                video = run_animatic_timeline(root, settings=settings)
            self.assertEqual(rendered, ['SH003'], '缺图才生成，已有当前版本直接复用')
            self.assertEqual(video, folder / '版本' / 'animatic_v001.mp4')
            self.assertTrue(video.is_file())
            manifest = json.loads((folder / 'animatic_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['video'], '版本/animatic_v001.mp4')
            rows = {row['id']: row for row in manifest['shots']}
            self.assertEqual(rows['SH001']['image'], '镜头/SH001/v1.png')
            self.assertEqual(rows['SH001']['image_version'], 1)
            self.assertEqual(rows['SH003']['image'], '镜头/SH003/v1.png')
            self.assertEqual(manifest['confirmed'], {'rhythm': False, 'duration': False,
                                                     'dialogue_sync': False})
            timeline = json.loads((folder / 'timeline.json').read_text(encoding='utf-8'))
            row = next(row for row in timeline['shots'] if row['id'] == 'SH003')
            self.assertEqual((row['image_version'], row['source']), (1, 'generated'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
