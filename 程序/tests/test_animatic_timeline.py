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

    def test_req_s04_104_segment_filter_five_motions_and_zero_regression(self):
        """REQ-S04-104：segment_filter 支持 5 种运镜；未传 shot_motions 时命令与既有完全一致。"""
        from contract.script_contract import preview_spec
        from domain.edit_service import preview_filter, segment_filter
        spec = preview_spec()
        base = preview_filter(spec)
        self.assertEqual(segment_filter(spec, seconds=4, motion='static'), base)
        self.assertEqual(segment_filter(spec, seconds=0, motion='zoom_in'), base)
        self.assertEqual(segment_filter(spec, seconds=-2, motion='pan_left'), base)
        self.assertEqual(segment_filter(spec, seconds=float('nan'), motion='zoom_out'), base)
        motion_filters = {}
        for motion in ('zoom_in', 'zoom_out', 'pan_left', 'pan_right'):
            vf = segment_filter(spec, seconds=4, motion=motion)
            self.assertTrue(vf.startswith(base + ',zoompan='), (motion, vf))
            self.assertIn('d=96', vf)
            self.assertIn('s=1280x720', vf)
            self.assertIn('fps=24', vf)
            motion_filters[motion] = vf
        self.assertEqual(len(set(motion_filters.values())), 4)
        portrait = {'width': 720, 'height': 1280, 'fps': 24}
        self.assertIn('s=720x1280', segment_filter(portrait, seconds=3, motion='zoom_in'))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info = {'streams': [{'codec_type': 'video'}, {'codec_type': 'audio'}],
                    'format': {'duration': '5'}}
            cmds_plain = []
            def exec_plain(command, **_opts):
                cmds_plain.append(command)
                return SimpleNamespace(stdout=json.dumps(info))
            assemble_image_timeline(
                [root / 'a.png', root / 'b.png'], [2, 3], root / 'a.wav', root / 'out1.mp4',
                ffmpeg='ffmpeg', ffprobe='ffprobe',
                write_temporary=lambda path, raw: path.write_bytes(raw),
                run=exec_plain, spec=spec)
            self.assertEqual(cmds_plain[0][cmds_plain[0].index('-vf') + 1], base)
            self.assertEqual(cmds_plain[1][cmds_plain[1].index('-vf') + 1], base)

            cmds_motion = []
            def exec_motion(command, **_opts):
                cmds_motion.append(command)
                return SimpleNamespace(stdout=json.dumps(info))
            assemble_image_timeline(
                [root / 'a.png', root / 'b.png'], [2, 3], root / 'a.wav', root / 'out2.mp4',
                ffmpeg='ffmpeg', ffprobe='ffprobe',
                write_temporary=lambda path, raw: path.write_bytes(raw),
                run=exec_motion, spec=dict(spec, shot_motions=['zoom_in', 'static']))
            self.assertEqual(cmds_motion[0][cmds_motion[0].index('-vf') + 1],
                             segment_filter(spec, seconds=2, motion='zoom_in'))
            self.assertEqual(cmds_motion[1][cmds_motion[1].index('-vf') + 1], base)


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

    def test_req_s04_105_112_rebuild_preserves_dialogue_seconds_and_legacy_rows(self):
        """REQ-S04-105/112：重建时间线保留 dialogue_seconds，并兼容缺该字段的旧时间线。"""
        from domain import animatic_timeline as timeline_model
        board = {'shots': [{'id': 'SH001', 'duration': 4}, {'id': 'SH002', 'duration': 5}]}
        timeline, _ = timeline_model.build(board, 'ep1.json', 'sha-1')
        self.assertIsNone(timeline['shots'][0]['dialogue_seconds'])
        timeline['shots'][0]['dialogue_seconds'] = 2.75
        del timeline['shots'][1]['dialogue_seconds']
        rebuilt, flag = timeline_model.build(board, 'ep1.json', 'sha-2', previous=timeline)
        self.assertTrue(flag)
        rows = {row['id']: row for row in rebuilt['shots']}
        self.assertEqual(rows['SH001']['dialogue_seconds'], 2.75)
        self.assertIsNone(rows['SH002']['dialogue_seconds'])

    def test_req_s04_115_review_status_lifecycle_legacy_compat_and_rebuild(self):
        """REQ-S04-115：单镜审核状态枚举校验、旧时间线兼容、待修改列表与重建保留。"""
        from domain import animatic_timeline as timeline_model
        self.assertEqual(timeline_model.REVIEW_STATES, ('pending', 'approved', 'needs_revision'))
        board = {'shots': [{'id': 'SH001', 'duration': 3}, {'id': 'SH002', 'duration': 4}]}
        timeline, _ = timeline_model.build(board, 'ep1.json', 'sha-1')
        self.assertEqual(timeline['shots'][0]['review_status'], 'pending')
        self.assertEqual(timeline_model.review_status_of({'id': 'SH001'}), 'pending')
        self.assertEqual(timeline_model.review_status_of({'review_status': 'bogus'}), 'pending')
        self.assertEqual(timeline_model.review_status_of({'review_status': 'approved'}), 'approved')
        updated = timeline_model.set_review_status(timeline, 'SH002', 'needs_revision')
        self.assertEqual(timeline['shots'][1]['review_status'], 'pending', '返回新副本不改原对象')
        self.assertEqual(updated['shots'][1]['review_status'], 'needs_revision')
        updated = timeline_model.set_review_status(updated, 'SH001', 'approved')
        self.assertEqual(timeline_model.needs_revision_ids(updated), ('SH002',))
        with self.assertRaises(ValueError):
            timeline_model.set_review_status(updated, 'SH001', 'invalid')
        legacy = {'kind': 'animatic_timeline', 'source': 'ep1.json', 'source_sha256': 'old',
                  'shots': [{'id': 'SH001', 'seconds': 3, 'review_status': 'approved'},
                            {'id': 'SH002', 'seconds': 4, 'review_status': 'needs_revision'}]}
        rebuilt, flag = timeline_model.build(
            {'shots': [{'id': 'SH001', 'duration': 3},
                       {'id': 'SH002', 'duration': 4}, {'id': 'SH003', 'duration': 5}]},
            'ep1.json', 'sha-2', previous=legacy)
        self.assertTrue(flag)
        rows = {row['id']: row for row in rebuilt['shots']}
        self.assertEqual(rows['SH001']['review_status'], 'approved')
        self.assertEqual(rows['SH002']['review_status'], 'needs_revision')
        self.assertEqual(rows['SH003']['review_status'], 'pending')

    def test_req_s04_115_filter_shots_by_scene_and_status(self):
        """REQ-S04-115：按场次与状态（all/needs_revision/overlong/missing_image）筛选镜头。"""
        from domain import animatic_timeline as timeline_model
        board = {'shots': [
            {'id': 'SH001', 'duration': 3, 'scene_id': 'SC01', 'location': '茶馆'},
            {'id': 'SH002', 'duration': 4, 'scene': 'SC01', 'location': '茶馆'},
            {'id': 'SH003', 'duration': 3, 'scene_id': 'SC02', 'location': '雨夜街道'},
        ]}
        timeline, _ = timeline_model.build(board, 'ep1.json', 'sha-1')
        timeline = timeline_model.set_version(timeline, 'SH001', 1)
        timeline = timeline_model.set_version(timeline, 'SH003', 2)
        timeline = timeline_model.set_review_status(timeline, 'SH002', 'needs_revision')
        timeline['shots'][0]['dialogue_seconds'] = 3.5
        timeline['shots'][2]['dialogue_seconds'] = 3.05
        ids = lambda rows: [row['id'] for row in rows]
        self.assertEqual(ids(timeline_model.filter_shots(timeline, board)), ['SH001', 'SH002', 'SH003'])
        self.assertEqual(ids(timeline_model.filter_shots(timeline, board, status='all')),
                         ['SH001', 'SH002', 'SH003'])
        self.assertEqual(ids(timeline_model.filter_shots(timeline, board, scene='SC01')),
                         ['SH001', 'SH002'])
        self.assertEqual(ids(timeline_model.filter_shots(timeline, board, scene='雨夜街道')),
                         ['SH003'])
        self.assertEqual(ids(timeline_model.filter_shots(timeline, board, status='needs_revision')),
                         ['SH002'])
        self.assertEqual(ids(timeline_model.filter_shots(timeline, board, status='overlong')),
                         ['SH001'])
        self.assertEqual(ids(timeline_model.filter_shots(timeline, board, status='missing_image')),
                         ['SH002'])
        self.assertEqual(ids(timeline_model.filter_shots(
            timeline, board, scene='SC01', status='needs_revision')), ['SH002'])


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

    def test_run_animatic_timeline_skips_comfy_probe_when_all_shots_have_images(self):
        """全镜已有图时，即使默认 comfy_local 无桩也绝不调 wait_comfy/open_comfy。"""
        from stage_execution_service import (
            load_or_sync_animatic_timeline, run_animatic_timeline, update_animatic_shot)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 2}, {'id': 'SH002', 'duration': 3}])
            folder = write_dir(root, 'animatic')
            for sid in ('SH001', 'SH002'):
                shot_dir = folder / '镜头' / sid
                shot_dir.mkdir(parents=True)
                (shot_dir / 'v1.png').write_bytes(b'img-' + sid.encode())
            load_or_sync_animatic_timeline(root)
            for sid in ('SH001', 'SH002'):
                update_animatic_shot(root, sid, image_version=1)

            def assemble(_images, _durations, _sound, target, **_kwargs):
                target.write_bytes(b'video')
                return target

            def run(command, **_kwargs):
                Path(command[-1]).write_bytes(b'mixed')
                return SimpleNamespace(stdout='')

            settings = {'ffmpeg': 'stub', 'ffprobe': 'stub', 'run': run}
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble), \
                    patch('infra.comfy_runtime.wait_comfy') as wait_mock, \
                    patch('infra.comfy_runtime.open_comfy') as open_mock:
                video = run_animatic_timeline(root, settings=settings)
            self.assertTrue(video.is_file())
            wait_mock.assert_not_called()
            open_mock.assert_not_called()

    def test_run_animatic_timeline_probes_and_opens_comfy_when_missing_images(self):
        """缺图且默认 comfy_local 无桩时，先 wait_comfy 探测，未就绪则 open_comfy 再 wait_comfy。"""
        from stage_execution_service import run_animatic_timeline
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 2}])
            events = []

            def fake_wait(url, timeout=5):
                events.append(('wait', url, timeout))
                if len(events) == 1:
                    raise ValueError('ComfyUI 未启动')

            def fake_open():
                events.append(('open',))

            def fake_sketch(workspace, shot, _refs, _settings):
                target = Path(workspace) / (shot['id'] + '.png')
                target.write_bytes(b'img')
                return target

            def assemble(_images, _durations, _sound, target, **_kwargs):
                target.write_bytes(b'video')
                return target

            def run(command, **_kwargs):
                Path(command[-1]).write_bytes(b'mixed')
                return SimpleNamespace(stdout='')

            settings = {'animatic_sketch_backend': 'comfy_local',
                        'ffmpeg': 'stub', 'ffprobe': 'stub', 'run': run,
                        'url': 'http://127.0.0.1:8199', 'probe_timeout': 3,
                        'readiness_timeout': 12}
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble), \
                    patch('domain.animatic_service.local_sketch', fake_sketch), \
                    patch('infra.comfy_runtime.wait_comfy', side_effect=fake_wait), \
                    patch('infra.comfy_runtime.open_comfy', side_effect=fake_open):
                video = run_animatic_timeline(root, settings=settings)
            self.assertTrue(video.is_file())
            self.assertEqual(events, [
                ('wait', 'http://127.0.0.1:8199', 3),
                ('open',),
                ('wait', 'http://127.0.0.1:8199', 12),
            ])

    def test_run_animatic_timeline_skips_comfy_probe_when_client_injected(self):
        """缺图但已注入 comfy_client 桩时跳过 wait_comfy/open_comfy。"""
        from stage_execution_service import run_animatic_timeline
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 2}])

            class StubClient:
                def reference_config(self):
                    return {}

                def reference_graph(self, _prompt, _refs, _cfg):
                    return {}

                def submit_graph(self, workspace, _kind, _prompt, _graph):
                    target = Path(workspace) / 'stub.png'
                    target.write_bytes(b'img')
                    return target

                def collect(self, _workspace, record):
                    return [record]

            def assemble(_images, _durations, _sound, target, **_kwargs):
                target.write_bytes(b'video')
                return target

            def run(command, **_kwargs):
                Path(command[-1]).write_bytes(b'mixed')
                return SimpleNamespace(stdout='')

            settings = {'animatic_sketch_backend': 'comfy_local',
                        'ffmpeg': 'stub', 'ffprobe': 'stub', 'run': run,
                        'comfy_client': StubClient()}
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble), \
                    patch('infra.comfy_runtime.wait_comfy') as wait_mock, \
                    patch('infra.comfy_runtime.open_comfy') as open_mock:
                video = run_animatic_timeline(root, settings=settings)
            self.assertTrue(video.is_file())
            wait_mock.assert_not_called()
            open_mock.assert_not_called()

    def test_req_s04_105_run_animatic_timeline_records_dialogue_seconds_and_motion(self):
        """REQ-S04-103/104/105：逐镜 TTS 合成后 timeline.json 写 dialogue_seconds，无对白为 None。"""
        from stage_execution_service import run_animatic_timeline
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._adopted(root, [
                {'id': 'SH001', 'duration': 4, 'camera_movement': '缓慢推进'},
                {'id': 'SH002', 'duration': 3, 'camera_movement': '固定镜头'},
            ])
            board = json.loads(source.read_text(encoding='utf-8'))
            board['shots'][0]['dialogue'] = ['第一句临时对白']
            board['shots'][1]['dialogue'] = []
            source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
            folder = write_dir(root, 'animatic')
            captured_spec = {}

            def assemble(images, durations, _sound, target, **kwargs):
                captured_spec.update(kwargs.get('spec') or {})
                self.assertEqual(len(images), 2)
                self.assertEqual(durations, [4, 3])
                target.write_bytes(b'video')
                return target

            def run(command, **_kwargs):
                Path(command[-1]).write_bytes(b'mixed')
                return SimpleNamespace(stdout='')

            settings = {
                'animatic_sketch_backend': 'text_card',
                'ffmpeg': 'stub',
                'ffprobe': 'stub',
                'run': run,
                'tts_settings': {'model': 'm', 'voice': 'v'},
                'synthesize': lambda text, **_kw: b'fake-mp3-' + text.encode('utf-8'),
                'signature_fn': lambda text, _cfg: 'sig01',
                'probe_duration': lambda _path: 2.35,
            }
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble):
                video = run_animatic_timeline(root, settings=settings)
            self.assertTrue(video.is_file())
            self.assertEqual(captured_spec.get('shot_motions'), ['zoom_in', 'static'])
            timeline = json.loads((folder / 'timeline.json').read_text(encoding='utf-8'))
            rows = {row['id']: row for row in timeline['shots']}
            self.assertEqual(rows['SH001']['dialogue_seconds'], 2.35)
            self.assertIsNotNone(rows['SH001']['dialogue_audio'])
            self.assertIsNone(rows['SH002']['dialogue_seconds'])
            self.assertIsNone(rows['SH002']['dialogue_audio'])

            captured_static = {}
            def assemble_static(_images, _durations, _sound, target, **kwargs):
                captured_static.update(kwargs.get('spec') or {})
                target.write_bytes(b'video2')
                return target

            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble_static):
                run_animatic_timeline(root, settings=dict(settings, animatic_ken_burns=False))
            self.assertNotIn('shot_motions', captured_static)

    def test_req_s04_83_regenerate_animatic_shot_reuses_ensure_comfy_ready(self):
        """REQ-S04-83：单镜重做在默认 comfy_local 且无客户端时探测/拉起 ComfyUI；非 Comfy 后端跳过。"""
        from stage_execution_service import load_or_sync_animatic_timeline, regenerate_animatic_shot
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 3}])
            load_or_sync_animatic_timeline(root)
            events = []

            def fake_wait(url, timeout=5):
                events.append(('wait', url, timeout))
                if len(events) == 1:
                    raise ValueError('ComfyUI 未启动')

            def fake_open():
                events.append(('open',))

            def fake_sketch(workspace, shot, _refs, _settings):
                target = Path(workspace) / (shot['id'] + '.png')
                target.write_bytes(b'img')
                return target

            with patch('domain.animatic_service.local_sketch', fake_sketch), \
                    patch('infra.comfy_runtime.wait_comfy', side_effect=fake_wait), \
                    patch('infra.comfy_runtime.open_comfy', side_effect=fake_open):
                regenerate_animatic_shot(
                    root, 'SH001',
                    settings={'animatic_sketch_backend': 'comfy_local',
                              'url': 'http://127.0.0.1:8199', 'probe_timeout': 2,
                              'readiness_timeout': 10})
            self.assertEqual(events, [
                ('wait', 'http://127.0.0.1:8199', 2),
                ('open',),
                ('wait', 'http://127.0.0.1:8199', 10),
            ])

            with patch('infra.comfy_runtime.wait_comfy') as wait_mock, \
                    patch('infra.comfy_runtime.open_comfy') as open_mock:
                updated = regenerate_animatic_shot(
                    root, 'SH001', settings={'animatic_sketch_backend': 'text_card'})
            wait_mock.assert_not_called()
            open_mock.assert_not_called()
            self.assertEqual(updated['shots'][0]['image_version'], 2)

    def test_req_s04_114_default_text_card_silent_and_tts_failure_hint(self):
        """REQ-S04-114：默认不探测 ComfyUI、animatic_use_tts=False 静音出片、TTS 失败给出中文提示。"""
        from stage_execution_service import run_animatic_timeline
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._adopted(root, [{'id': 'SH001', 'duration': 3}])
            board = json.loads(source.read_text(encoding='utf-8'))
            board['shots'][0]['dialogue'] = ['开场对白']
            source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')

            def assemble(_images, _durations, _sound, target, **_kwargs):
                target.write_bytes(b'video')
                return target

            def run(command, **_kwargs):
                Path(command[-1]).write_bytes(b'mixed')
                return SimpleNamespace(stdout='')

            def broken_tts(*_a, **_kw):
                raise RuntimeError('missing api key')

            settings = {'ffmpeg': 'stub', 'ffprobe': 'stub', 'run': run,
                        'animatic_use_tts': False, 'synthesize': broken_tts,
                        'tts_settings': {}}
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble), \
                    patch('infra.comfy_runtime.wait_comfy') as wait_mock:
                video = run_animatic_timeline(root, settings=settings)
            self.assertTrue(video.is_file())
            wait_mock.assert_not_called()

            settings_tts = {'ffmpeg': 'stub', 'ffprobe': 'stub', 'run': run,
                            'animatic_use_tts': True, 'synthesize': broken_tts,
                            'tts_settings': {'model': 'm', 'voice': 'v'},
                            'signature_fn': lambda _t, _s: 'sig'}
            with patch('stage_parallel.evaluate', return_value={'ok': True}), \
                    patch('domain.edit_service.assemble_image_timeline', assemble):
                with self.assertRaisesRegex(ValueError, '关闭逐镜 TTS'):
                    run_animatic_timeline(root, settings=settings_tts)

    def test_req_s04_114_remove_animatic_audio_recycles_and_validates_track(self):
        """REQ-S04-114：remove_animatic_audio 经回收站移出整轨或音乐，非法 track 抛错。"""
        from stage_execution_service import remove_animatic_audio
        from infra.storage_maintenance import restore_latest_recycled_path
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = write_dir(root, 'animatic')
            track_file = folder / '声音' / '整轨' / 'full.mp3'
            music_file = folder / '声音' / '音乐' / 'bgm.mp3'
            track_file.parent.mkdir(parents=True, exist_ok=True)
            music_file.parent.mkdir(parents=True, exist_ok=True)
            track_file.write_bytes(b'track-bytes')
            music_file.write_bytes(b'bgm-bytes')
            with self.assertRaises(ValueError):
                remove_animatic_audio(root, 'dialogue')
            removed = remove_animatic_audio(root, 'track')
            self.assertEqual([Path(p).resolve() for p in removed], [track_file.resolve()])
            self.assertFalse(track_file.exists())
            self.assertTrue(music_file.is_file(), '移除整轨不得误删音乐')
            restore_latest_recycled_path(root, track_file)
            self.assertEqual(track_file.read_bytes(), b'track-bytes', '移除的音频应可从项目回收站恢复')
            removed_bgm = remove_animatic_audio(root, 'music')
            self.assertEqual([Path(p).resolve() for p in removed_bgm], [music_file.resolve()])
            self.assertFalse(music_file.exists())
            self.assertEqual(remove_animatic_audio(root, 'music'), ())

    def test_req_s04_115_regenerate_revision_shots_resets_status_and_rejects_empty(self):
        """REQ-S04-115：批量重做只跑需修改镜头、成功后重置为 pending，无待改镜头报错。"""
        from domain import animatic_sketch_backends as backends
        from stage_execution_service import (
            load_or_sync_animatic_timeline, regenerate_revision_shots, update_animatic_shot)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._adopted(root, [{'id': 'SH001', 'duration': 3},
                                 {'id': 'SH002', 'duration': 4},
                                 {'id': 'SH003', 'duration': 3}])
            load_or_sync_animatic_timeline(root)
            with self.assertRaisesRegex(ValueError, '当前没有标记「需修改」的镜头'):
                regenerate_revision_shots(root)
            update_animatic_shot(root, 'SH001', review_status='approved')
            update_animatic_shot(root, 'SH002', review_status='needs_revision')
            update_animatic_shot(root, 'SH003', review_status='needs_revision')
            calls = []

            def factory(workspace, shot, _refs, _settings):
                calls.append(shot['id'])
                target = workspace / (shot['id'] + '.png')
                target.write_bytes(b'redo-' + shot['id'].encode())
                return target

            backends.register('unit_rev_stub', factory)
            self.addCleanup(backends.unregister, 'unit_rev_stub')
            updated = regenerate_revision_shots(
                root, settings={'animatic_sketch_backend': 'unit_rev_stub'})
            self.assertEqual(calls, ['SH002', 'SH003'])
            rows = {row['id']: row for row in updated['shots']}
            self.assertEqual(rows['SH001']['review_status'], 'approved')
            self.assertEqual(rows['SH002']['review_status'], 'pending')
            self.assertEqual(rows['SH003']['review_status'], 'pending')
            self.assertEqual(rows['SH002']['image_version'], 1)
            self.assertEqual(rows['SH003']['image_version'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
