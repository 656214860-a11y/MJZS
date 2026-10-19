"""REQ-S12 测试锚定：后期剪辑（S12）尚无测试锚点的需求。

每条测试名与 docstring 都写明锚定的 ``REQ-S12-xx``，断言对应需求原文里可判定的那句行为；
只用 ``tempfile`` 临时项目与桩件，不联网、不开 Tk、不碰真实用户项目，也不依赖 ffmpeg。
已有 S12 测试文件由 docstring 认领其已覆盖的条目，本文件补上尚无锚点的部分。
"""
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import engine
import handoff_service
import stage_flow
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


if __name__ == '__main__':
    unittest.main()
