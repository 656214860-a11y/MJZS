"""REQ-S11 测试锚定：配音阶段默认技能、兼容层与媒体完成清单。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stage_config
import workflow_settings
from agent.core import file_hash, read, save
from project_stages import audio
from stage_completion_service import (completion_evidence, confirm_media_completion,
                                     media_manifest_path, media_scope, prepare_media_completion)


class _MediaProject:
    """S11-04 只用到的临时项目接缝：采用分镜、配置与音频成果目录；不联网、不碰用户项目。"""

    def __init__(self, temporary):
        self.root = Path(temporary).resolve()
        self.source = self.root / 'storyboard' / 'episode.json'
        save(self.source, {'id': 'EP01', 'shots': [{'id': 'S01'}]})
        save(self.root / 'ui_settings.json',
             {'frame_json': str(self.source), 'adopted_storyboards': [str(self.source)]})
        save(self.root / 'config.json', {'ffprobe': 'test-probe'})

    def media_file(self, name='dialogue.wav'):
        folder = audio(self.root) / '音频'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_bytes(b'fixture-audio')
        return path

    def prepare(self, path):
        """ffprobe 用桩返回有限正时长的 audio 流，沿用既有完成度测试的做法。"""
        probed = {'format': {'duration': '2.5'}, 'streams': [{'codec_type': 'audio'}]}
        with patch('agent.media.probe', return_value=probed):
            return prepare_media_completion(self.root, 'audio', [path])


class ReqS11AnchorTests(unittest.TestCase):
    def test_req_s11_32_legacy_audio_default_is_empty_and_stage_preset_is_authoritative(self):
        """REQ-S11-32：旧 FLOWS 的 audio 默认保持空串，阶段预设默认 pipeline-audio-subtitle。"""
        self.assertEqual(workflow_settings.DEFAULT_SKILLS['audio'], '')
        self.assertIn('pipeline-audio-subtitle', stage_config.default_entry('audio')['skills'])


class ReqS11MediaCompletionAnchorTests(unittest.TestCase):
    """REQ-S11-04：阶段完成只认人工确认的 ``成果确认/<hash>.json``，每条都验失败路径。"""

    def test_req_s11_04_subtitle_alone_does_not_complete_audio(self):
        """REQ-S11-04：只有字幕文件、没有成果确认清单时阶段不算完成；
        同一份对白音频校验并人工确认后才是完成，证明否定来自缺清单而非坏夹具。"""
        with tempfile.TemporaryDirectory() as temporary:
            project = _MediaProject(temporary)
            subtitles = audio(project.root) / '字幕'
            subtitles.mkdir(parents=True)
            (subtitles / '对白.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\n你好\n',
                                                encoding='utf-8')
            ok, detail = completion_evidence(project.root, 'audio')
            self.assertFalse(ok, '字幕不能替代媒体成果确认清单')
            self.assertIn('尚未确认', detail)
            path = project.media_file()
            manifest = confirm_media_completion(project.root, 'audio', project.prepare(path))
            self.assertTrue(manifest.is_file())
            self.assertEqual(completion_evidence(project.root, 'audio'), (True, ''))

    def test_req_s11_04_manifest_requires_complete_status_and_reviewed_true(self):
        """REQ-S11-04：清单存在但 ``status`` 不是 ``complete``，或 ``reviewed`` 不为真，
        都不算完成；恢复原清单后才重新有效。"""
        with tempfile.TemporaryDirectory() as temporary:
            project = _MediaProject(temporary)
            path = project.media_file()
            manifest = confirm_media_completion(project.root, 'audio', project.prepare(path))
            confirmed = read(manifest)
            self.assertEqual(completion_evidence(project.root, 'audio'), (True, ''))
            save(manifest, dict(confirmed, status='pending_review'))
            ok, detail = completion_evidence(project.root, 'audio')
            self.assertFalse(ok, 'status=pending_review 必须判为未完成')
            self.assertIn('仍待您确认', detail)
            save(manifest, dict(confirmed, reviewed=False))
            ok, detail = completion_evidence(project.root, 'audio')
            self.assertFalse(ok, 'reviewed=False 必须判为未完成')
            self.assertIn('仍待您确认', detail)
            save(manifest, confirmed)
            self.assertEqual(completion_evidence(project.root, 'audio'), (True, ''))

    def test_req_s11_04_storyboard_change_invalidates_old_confirmation(self):
        """REQ-S11-04：采用版分镜改动（sha256 变化）后旧清单失效，且不能再拿旧清单确认；
        切集同理，因为 scope 绑定的是当前采用分镜。"""
        with tempfile.TemporaryDirectory() as temporary:
            project = _MediaProject(temporary)
            path = project.media_file()
            prepared = project.prepare(path)
            confirm_media_completion(project.root, 'audio', prepared)
            self.assertEqual(completion_evidence(project.root, 'audio'), (True, ''))
            save(project.source, {'id': 'EP01', 'shots': [{'id': 'S02'}]})
            ok, detail = completion_evidence(project.root, 'audio')
            self.assertFalse(ok, '分镜改动后旧确认必须失效')
            self.assertIn('不一致', detail)
            with self.assertRaisesRegex(ValueError, '不一致'):
                confirm_media_completion(project.root, 'audio', prepared)

    def test_req_s11_04_replaced_audio_file_invalidates_old_confirmation(self):
        """REQ-S11-04：成果音频被替换（字节数／sha256 变化）后旧清单失效；
        恢复原字节后重新有效，证明判定看的是摘要而不是时间戳。"""
        with tempfile.TemporaryDirectory() as temporary:
            project = _MediaProject(temporary)
            path = project.media_file()
            confirm_media_completion(project.root, 'audio', project.prepare(path))
            original = path.read_bytes()
            path.write_bytes(b'X' * len(original))
            ok, detail = completion_evidence(project.root, 'audio')
            self.assertFalse(ok, '被替换的成果文件必须使旧确认失效')
            self.assertIn('替换或修改', detail)
            path.write_bytes(original)
            self.assertEqual(completion_evidence(project.root, 'audio'), (True, ''))

    def test_req_s11_04_non_dialogue_only_is_rejected_before_confirmation(self):
        """REQ-S11-04：所选音频没有一条对白音轨（只有 BGM／音效／旁白）时，
        ``prepare_media_completion`` 当场拒绝且不生成待审清单；对白文件才可进入待审。"""
        from tts_api import audio_kind
        with tempfile.TemporaryDirectory() as temporary:
            project = _MediaProject(temporary)
            bgm = project.media_file('BGM_theme.wav')
            self.assertEqual(audio_kind(bgm.name), 'bgm')
            with self.assertRaisesRegex(ValueError, '都不是对白音轨'):
                project.prepare(bgm)
            self.assertFalse(media_manifest_path(project.root, 'audio', media_scope(project.root)).exists())
            dialogue = project.media_file('dialogue.wav')
            prepared = project.prepare(dialogue)
            self.assertEqual(prepared['status'], 'pending_review')
            self.assertEqual(prepared['outputs'][0]['sha256'], file_hash(dialogue))


if __name__ == '__main__':
    unittest.main(verbosity=2)
