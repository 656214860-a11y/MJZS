"""REQ-S12 测试锚定：后期剪辑（S12）尚无测试锚点的需求。

每条测试名与 docstring 都写明锚定的 ``REQ-S12-xx``，断言对应需求原文里可判定的那句行为；
只用 ``tempfile`` 临时项目与桩件，不联网、不开 Tk、不碰真实用户项目，也不依赖 ffmpeg。
已有 S12 测试文件由 docstring 认领其已覆盖的条目，本文件补上尚无锚点的部分。
"""
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import engine
import handoff_service
import stage_flow
import storage_maintenance
from agent.core import file_hash
from edit_export import normalize_edits


class _EncodeStudio:
    """``Studio._encode`` 只用到这几个接缝：项目根、输出规格、设置、发布与清单。"""

    def __init__(self, root, spec):
        self.root = Path(root)
        self.cfg = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
        self._spec = spec
        self.bundles = []
        self.lists = []

    def output_spec(self):
        return dict(self._spec)

    def edit_settings(self):
        return normalize_edits(None)

    def edit_inputs(self):
        return {'audio': [], 'subtitles': []}

    def publish_edit_bundle(self, out, master, report, chosen, edits=None, overlap=0.0):
        self.bundles.append((Path(out), Path(master), dict(report or {}), list(chosen)))

    def publish_edit_lists(self, out, chosen, spec):
        self.lists.append((Path(out), list(chosen), dict(spec)))
        return {'ok': True, 'reason': ''}

    def _join_shots(self, *args):
        return engine.Studio._join_shots(self, *args)


class _AssembleStudio:
    """``Studio.assemble`` 只用到这几个接缝：项目根、状态、分镜与编码入口。"""

    def __init__(self, root, shots_state, shots):
        self.root = Path(root)
        self._state = {'shots': shots_state}
        self.episode = {'shots': shots}

    def state(self):
        return self._state

    def lock(self):
        @contextmanager
        def held():
            yield
        return held()

    def _encode(self, chosen, out, coverage=None):
        return str(Path(out) / 'MASTER.mp4')


SPEC = {'aspect_ratio': '9:16', 'resolution': '1080x1920', 'width': 1080, 'height': 1920,
        'fps': 30, 'loudness': {'i': -16, 'tp': -1.5, 'lra': 11}}


class _ManifestAssembleStudio:
    """走真实 ``Studio.assemble``／``_encode``／``publish_edit_bundle``，只把 ffmpeg 与项目根换成夹具。"""

    def __init__(self, root, versions, shots, inputs):
        self.root = Path(root)
        self.cfg = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
        self._state = {'shots': versions}
        self.episode = {'shots': shots}
        self._inputs = inputs

    def state(self):
        return self._state

    def lock(self):
        @contextmanager
        def held():
            yield
        return held()

    def output_spec(self):
        return dict(SPEC)

    def edit_settings(self):
        return normalize_edits({'transition': {'kind': 'fade', 'seconds': 0.5}})

    def edit_inputs(self):
        return dict(self._inputs)

    def _encode(self, chosen, out, coverage=None):
        return engine.Studio._encode(self, chosen, out, coverage)

    def publish_edit_bundle(self, out, master, report, chosen, edits=None, overlap=0.0):
        return engine.Studio.publish_edit_bundle(self, out, master, report, chosen, edits, overlap)

    def publish_edit_lists(self, out, chosen, spec):
        return engine.Studio.publish_edit_lists(self, out, chosen, spec)

    def _join_shots(self, *args):
        return engine.Studio._join_shots(self, *args)


class _HandoffHost:
    """``MediaPagesMixin.handoff`` 只用到 root／studio／subtitles；用鸭子类型避开 Tk 窗口。"""

    def __init__(self, root, versions, shots, subtitle=b'1\n00:00:00,000 --> 00:00:01,000\n\xe4\xbd\xa0\xe5\xa5\xbd\n'):
        self.root = Path(root)
        self.studio = SimpleNamespace(state=lambda: {'shots': versions},
                                      episode={'shots': shots})
        self._subtitle = subtitle

    def subtitles(self):
        if self._subtitle is None:
            raise ValueError('无对白')
        return self._subtitle


def _approved_version(root, path, number, *, review='pass', pinned=False):
    """一条已下载、质检通过、默认已验收的版本记录；路径相对项目根，与 engine 口径一致。"""
    version = {'version': number, 'state': 'downloaded', 'qc_pass': True, 'review': review,
               'file': Path(path).relative_to(root).as_posix(), 'sha256': file_hash(path)}
    if pinned:
        version['pinned'] = True
    return version


class ReqS12AnchorTests(unittest.TestCase):
    def test_req_s12_10_reencode_each_shot_then_concat_copy_and_note_missing_audio(self):
        """REQ-S12-10：每镜先按 output_filter／响度滤镜重编码为 x264+aac 48k 立体声，
        再 ``concat -c copy`` 合成 MASTER.mp4；源视频没有音轨的镜头补静音、写 <镜头>_音轨说明.json。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / 'out'
            out.mkdir()
            clip_a = root / 'A.mp4'
            clip_a.write_bytes(b'a')
            clip_b = root / 'B.mp4'
            clip_b.write_bytes(b'b')
            studio = _EncodeStudio(root, SPEC)
            chosen = [({'id': 'S01', 'duration': 2}, {'version': 1, 'sha256': 'h1'}, clip_a),
                      ({'id': 'S02', 'duration': 2}, {'version': 1, 'sha256': 'h2'}, clip_b)]
            recorded = []

            def fake_command(args, cwd=None):
                recorded.append([str(item) for item in args])
                last = args[-1]
                if isinstance(last, Path):
                    last.write_bytes(b'encoded')

            def fake_probe(path, cfg):
                streams = [{'codec_type': 'video'}]
                if Path(path).name == 'A.mp4':
                    streams.append({'codec_type': 'audio'})
                return {'streams': streams}

            with patch('engine.command', side_effect=fake_command), \
                    patch('engine.check', return_value={'errors': []}), \
                    patch('agent.media.probe', side_effect=fake_probe):
                master = engine.Studio._encode(studio, chosen, out)

            self.assertEqual(Path(master), out / 'MASTER.mp4')
            encode_a = next(row for row in recorded if row[-1] == str(out / 'S01.mp4'))
            joined_a = ' '.join(encode_a)
            self.assertIn('scale=1080:1920:force_original_aspect_ratio=decrease', joined_a)
            self.assertIn('pad=1080:1920:(ow-iw)/2:(oh-ih)/2', joined_a)
            self.assertIn('-c:v libx264', joined_a)
            self.assertIn('-c:a aac', joined_a)
            self.assertIn('-ar 48000 -ac 2', joined_a)
            self.assertIn('loudnorm=I=-16:TP=-1.5:LRA=11', joined_a)
            encode_b = next(row for row in recorded if row[-1] == str(out / 'S02.mp4'))
            joined_b = ' '.join(encode_b)
            self.assertIn('anullsrc=channel_layout=stereo:sample_rate=48000', joined_b)
            self.assertNotIn('loudnorm', joined_b)
            self.assertTrue((out / 'S02_音轨说明.json').is_file())
            self.assertFalse((out / 'S01_音轨说明.json').exists())
            concat = next(row for row in recorded if 'concat' in row)
            self.assertIn('-c copy', ' '.join(concat))

    def test_req_s12_27_recovery_hint_points_to_manual_editing_and_reviewed_stills(self):
        """REQ-S12-27：无可用成片时 ``stage_flow.RECOVERY_HINTS['edit']`` 给出手动出路——
        改用剪辑软件人工剪辑；静帧替代镜头须明确审核，不当作 AI 视频成功。"""
        hint = stage_flow.RECOVERY_HINTS['edit']
        self.assertIn('剪辑软件', hint)
        self.assertIn('人工剪辑', hint)
        self.assertIn('静帧', hint)
        self.assertIn('审核', hint)
        self.assertIn('不当作', hint)
        self.assertIn('AI视频', hint)

    def test_req_s12_40_edit_stage_never_synthesizes_dialogue_subtitles_or_drafts(self):
        """REQ-S12-40：本阶段不生成／合成对白、配音、字幕，不生成剪映草稿，
        也不静默使用未验收版本（非目标）。"""
        with tempfile.TemporaryDirectory() as temporary:
            shot = {'id': 'SH001', 'duration': 2}
            studio = _AssembleStudio(Path(temporary), {'SH001': []}, [shot])
            with self.assertRaisesRegex(ValueError, 'SH001'):
                engine.Studio.assemble(studio, skip_unready=False)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            clip = root / 'clip.mp4'
            clip.write_bytes(b'clip')
            shot = {'id': 'SH001', 'duration': 3}
            from stage_execution_service import publish_handoff_bundle
            result = handoff_service.publish_bundle(
                root, [shot], [(shot, {'file': 'clip.mp4', 'review': 'pass'})],
                subtitle=None, publish=publish_handoff_bundle)
            self.assertTrue(result.ok, getattr(result, 'reason', ''))
            out = Path(result.data)
            names = [item.name for item in out.iterdir()]
            self.assertNotIn('对白.srt', names)
            manifest = json.loads((out / '交接包清单.json').read_text(encoding='utf-8'))
            self.assertFalse(manifest['subtitle'])
            self.assertIn('不是剪映草稿', handoff_service.MEDIA_PACKAGE_NOTE)
            self.assertFalse(any('草稿' in name for name in names))
            self.assertIn('不是剪映草稿', (out / '导入剪映说明.txt').read_text(encoding='utf-8'))

    def test_req_s12_15_handoff_uses_pinned_approved_version(self):
        """REQ-S12-15：交接包选版与成片同一口径——已验收版本中用户锁定（pinned）的优先，
        即便后面还有更新的已验收版；选中的必须就是 ``adopted_edit_version`` 返回的那一条。"""
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clips = root / 'data' / 'clips'
            clips.mkdir(parents=True)
            old = clips / 'SH001_v1.mp4'; old.write_bytes(b'old-take')
            new = clips / 'SH001_v2.mp4'; new.write_bytes(b'new-take')
            first = _approved_version(root, old, 1, pinned=True)
            second = _approved_version(root, new, 2)
            shot = {'id': 'SH001', 'duration': 2}
            host = _HandoffHost(root, {'SH001': [first, second]}, [shot])
            with patch('stage_execution_service.publish_stage_handoff_bundle',
                       return_value=root / 'bundle') as publish:
                out = Desktop.handoff(host)
            self.assertEqual(out, root / 'bundle')
            rows = publish.call_args.args[2]
            self.assertEqual([row[1]['version'] for row in rows], [1])
            self.assertIs(rows[0][1], engine.adopted_edit_version([first, second], root)[0])

    def test_req_s12_15_handoff_without_pin_uses_last_approved_version(self):
        """REQ-S12-15：没有 pinned 时仍取最后一条已验收版（旧行为回归保护），
        且与 ``adopted_edit_version`` 返回同一条。"""
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clips = root / 'data' / 'clips'
            clips.mkdir(parents=True)
            old = clips / 'SH001_v1.mp4'; old.write_bytes(b'old-take')
            new = clips / 'SH001_v2.mp4'; new.write_bytes(b'new-take')
            first = _approved_version(root, old, 1)
            second = _approved_version(root, new, 2)
            shot = {'id': 'SH001', 'duration': 2}
            host = _HandoffHost(root, {'SH001': [first, second]}, [shot])
            with patch('stage_execution_service.publish_stage_handoff_bundle',
                       return_value=root / 'bundle') as publish:
                Desktop.handoff(host)
            rows = publish.call_args.args[2]
            self.assertEqual([row[1]['version'] for row in rows], [2])
            self.assertIs(rows[0][1], engine.adopted_edit_version([first, second], root)[0])

    def test_req_s12_15_handoff_skips_shot_without_approved_version(self):
        """REQ-S12-15：只有未验收版本的镜头不进交接包（不退回最新未验收版），其余镜照常；
        因为不是全镜进包，按既有逻辑不附全片字幕。"""
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clips = root / 'data' / 'clips'
            clips.mkdir(parents=True)
            pending_file = clips / 'SH001_v1.mp4'; pending_file.write_bytes(b'pending-take')
            ready_file = clips / 'SH002_v1.mp4'; ready_file.write_bytes(b'ready-take')
            pending = _approved_version(root, pending_file, 1, review='pending')
            ready = _approved_version(root, ready_file, 1)
            shots = [{'id': 'SH001', 'duration': 2}, {'id': 'SH002', 'duration': 2}]
            host = _HandoffHost(root, {'SH001': [pending], 'SH002': [ready]}, shots)
            with patch('stage_execution_service.publish_stage_handoff_bundle',
                       return_value=root / 'bundle') as publish:
                Desktop.handoff(host)
            rows = publish.call_args.args[2]
            self.assertEqual([row[0]['id'] for row in rows], ['SH002'])
            self.assertIsNone(publish.call_args.args[3], '缺镜时不得附全片字幕')
            self.assertIsNone(engine.adopted_edit_version([pending], root)[0])
            self.assertEqual(engine.adopted_edit_version([pending], root)[1], engine.ADOPT_UNAPPROVED)

    def test_req_s12_15_handoff_skips_missing_or_replaced_adopted_file(self):
        """REQ-S12-15：采用版文件被替换（sha256 与验收摘要不符）或缺失时，该镜同样不进包；
        与成片口径一致，绝不把核不过的文件塞进交接包。"""
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clips = root / 'data' / 'clips'
            clips.mkdir(parents=True)
            replaced_file = clips / 'SH001_v1.mp4'; replaced_file.write_bytes(b'original-take')
            missing_file = clips / 'SH002_v1.mp4'; missing_file.write_bytes(b'missing-take')
            ready_file = clips / 'SH003_v1.mp4'; ready_file.write_bytes(b'ready-take')
            replaced = _approved_version(root, replaced_file, 1)
            missing = _approved_version(root, missing_file, 1)
            ready = _approved_version(root, ready_file, 1)
            replaced_file.write_bytes(b'replaced-take')
            missing_file.unlink()
            shots = [{'id': 'SH001', 'duration': 2}, {'id': 'SH002', 'duration': 2},
                     {'id': 'SH003', 'duration': 2}]
            host = _HandoffHost(root, {'SH001': [replaced], 'SH002': [missing], 'SH003': [ready]}, shots)
            with patch('stage_execution_service.publish_stage_handoff_bundle',
                       return_value=root / 'bundle') as publish:
                Desktop.handoff(host)
            rows = publish.call_args.args[2]
            self.assertEqual([row[0]['id'] for row in rows], ['SH003'])
            self.assertIsNotNone(engine.adopted_edit_version([ready], root)[0])
            self.assertEqual(engine.adopted_edit_version([replaced], root)[1], engine.ADOPT_REPLACED)
            self.assertEqual(engine.adopted_edit_version([missing], root)[1], engine.ADOPT_MISSING)

    def test_req_s12_34_assemble_manifest_records_timeline_sources_and_switch(self):
        """REQ-S12-34：一次真实 assemble 产出的 ``edit_manifest.json`` 每镜在原四字段外补
        时间码（与同次 EDL 同一 layout 与数值）、音轨、字幕、切换依据；无配音／字幕的镜头
        写空数组而不是缺键；有配音的镜头音轨 sha256 与实际文件一致。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio_folder = root / '11配音与字幕' / '音频'
            audio_folder.mkdir(parents=True)
            voice = audio_folder / 'SH001_对白.wav'
            voice.write_bytes(b'voice-bytes')
            subtitle_folder = root / '11配音与字幕' / '字幕'
            subtitle_folder.mkdir(parents=True)
            subtitle = subtitle_folder / 'SH001.srt'
            subtitle.write_bytes(b'subtitle-bytes')
            inputs = {'audio': [{'path': voice.relative_to(root).as_posix(), 'sha256': file_hash(voice)}],
                      'subtitles': [{'path': subtitle.relative_to(root).as_posix(),
                                     'sha256': file_hash(subtitle)}]}
            videos = root / 'episode' / 'videos'
            videos.mkdir(parents=True)
            versions = {}
            for number, sid, duration in ((1, 'SH001', 2), (2, 'SH002', 3)):
                source = videos / (sid + '.mp4')
                source.write_bytes(('source-' + sid).encode('utf-8'))
                versions[sid] = [{'version': number, 'state': 'downloaded', 'qc_pass': True,
                                  'review': 'pass', 'file': source.relative_to(root).as_posix(),
                                  'sha256': file_hash(source)}]
            shots = [{'id': 'SH001', 'duration': 2}, {'id': 'SH002', 'duration': 3}]
            studio = _ManifestAssembleStudio(root, versions, shots, inputs)
            recorded = []

            def fake_command(args, cwd=None):
                recorded.append([str(item) for item in args])
                if isinstance(args[-1], Path):
                    args[-1].write_bytes(b'encoded fixture')

            def fake_probe(path, cfg):
                return {'format': {'duration': 2.5}, 'streams': [{'codec_type': 'video'},
                                                                  {'codec_type': 'audio'}]}

            with patch('engine.command', side_effect=fake_command), \
                    patch('engine.check', return_value={'errors': []}), \
                    patch('engine.probe', side_effect=fake_probe), \
                    patch('agent.media.probe', side_effect=fake_probe):
                master = Path(engine.Studio.assemble(studio))

            out = master.parent
            self.assertEqual(master.name, 'MASTER.mp4')
            manifest = json.loads((out / engine.EDIT_MANIFEST_NAME).read_text(encoding='utf-8'))
            self.assertEqual(manifest['schema'], engine.EDIT_MANIFEST_SCHEMA)
            rows = manifest['manifest']
            self.assertEqual([row['shot'] for row in rows], ['SH001', 'SH002'])
            # 原四字段只增不改。
            self.assertEqual([(row['version'], row['sha256']) for row in rows], [(1, versions['SH001'][0]['sha256']),
                                                                               (2, versions['SH002'][0]['sha256'])])
            self.assertTrue(all(row['source'].endswith('.mp4') for row in rows))
            # 时间码与同次 EDL 同一口径（EDL 行尾两个时间码就是时间线入/出点）。
            edl_lines = [line.split() for line in (out / '剪辑清单.edl').read_text(encoding='utf-8').splitlines()
                         if line[:3].isdigit()]
            self.assertEqual(len(edl_lines), 2)
            for row, line in zip(rows, edl_lines):
                self.assertEqual((row['timecode']['in'], row['timecode']['out']), (line[6], line[7]))
                self.assertEqual(row['timecode']['fps'], 30)
            self.assertEqual((rows[0]['timecode']['in_seconds'], rows[0]['timecode']['out_seconds']), (0.0, 2.0))
            self.assertEqual((rows[1]['timecode']['in_seconds'], rows[1]['timecode']['out_seconds']), (2.0, 5.0))
            # 音轨／字幕：有对应来源的镜头记路径与摘要，没有的写空数组（键必须在）。
            expected_audio = [{'path': os.path.relpath(voice, out).replace('\\', '/'), 'sha256': file_hash(voice)}]
            expected_subtitle = [{'path': os.path.relpath(subtitle, out).replace('\\', '/'),
                                  'sha256': file_hash(subtitle)}]
            self.assertEqual(rows[0]['audio'], expected_audio)
            self.assertEqual(rows[0]['subtitles'], expected_subtitle)
            self.assertEqual(rows[1]['audio'], [])
            self.assertEqual(rows[1]['subtitles'], [])
            # 切换依据：首镜无前一镜，第二镜按真实转场设置淡入淡出 0.5 秒。
            self.assertEqual(rows[0]['transition']['kind'], 'cut')
            self.assertEqual(rows[1]['transition']['kind'], 'fade')
            self.assertEqual(rows[1]['transition']['seconds'], 0.5)
            self.assertIn('淡入淡出', rows[1]['transition']['reason'])
            # bundle 顶层同版本号，镜头行与索引一致，S13 从任一份都能判断新旧。
            bundle = json.loads((out / engine.EDIT_BUNDLE_NAME).read_text(encoding='utf-8'))
            self.assertEqual(bundle['schema'], engine.EDIT_MANIFEST_SCHEMA)
            self.assertEqual(bundle['manifest'], rows)

    def test_req_s12_34_legacy_manifest_is_still_accepted_by_all_readers(self):
        """REQ-S12-34：老格式（顶层数组、每镜只有四字段）仍被所有读取方接受——
        ``read_edit_bundle`` 退回 legacy，``storage_maintenance.edit_source_versions``
        照常读出被引用的版本与摘要；新格式（顶层 schema＋manifest）同样可读。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / '13质检交付' / '导出成片' / '旧成片'
            folder.mkdir(parents=True)
            legacy = [{'shot': 'SH001', 'version': 1, 'sha256': 'old-hash', 'source': '../SH001.mp4'}]
            (folder / engine.EDIT_MANIFEST_NAME).write_text(json.dumps(legacy, ensure_ascii=False),
                                                            encoding='utf-8')
            recovered = engine.read_edit_bundle(folder)
            self.assertTrue(recovered['legacy'])
            self.assertEqual(recovered['manifest'], legacy)
            pairs, digests = storage_maintenance.edit_source_versions(root)
            self.assertEqual(pairs, {('SH001', 1)})
            self.assertEqual(digests, {('SH001', 'old-hash')})
            current = {'schema': engine.EDIT_MANIFEST_SCHEMA, 'manifest': legacy}
            (folder / engine.EDIT_MANIFEST_NAME).write_text(json.dumps(current, ensure_ascii=False),
                                                            encoding='utf-8')
            self.assertEqual(engine.read_edit_bundle(folder)['manifest'], legacy)
            self.assertEqual(storage_maintenance.edit_source_versions(root), (pairs, digests))


if __name__ == '__main__':
    unittest.main()
