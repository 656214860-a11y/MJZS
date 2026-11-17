import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from domain import tts_api
from agent.core import save
from domain.audio_import_service import import_audio
from stage_completion_service import media_output_folders, prepare_media_completion
from contract.service_contract import UserError


def _gateway():
    from agent.core import save_bytes
    return {"publish_json": save, "publish_bytes": save_bytes}


def line(index, speaker="CHAR_001"):
    return {"shot_id": "SH%03d" % index, "speaker": speaker, "name": "角色", "text": "第%d句" % index,
            "start": float(index), "end": float(index) + 1, "voice": "voice_a", "speed": 1.0}


class VoiceMappingTests(unittest.TestCase):
    def test_id_takes_precedence_over_renamed_display_name(self):
        """REQ-S11-13：稳定角色 ID 优先于显示名，程序只负责绑定与回退。"""
        voices = {"CHAR_001": "voice_a"}
        self.assertEqual(tts_api.voice_for(voices, "CHAR_001", "改名前"), "voice_a")

    def test_name_fallback_and_empty(self):
        """REQ-S11-13：显示名次之，缺失时回退默认空音色；一角一音色仍由人工判断。"""
        self.assertEqual(tts_api.voice_for({"小明": "voice_b"}, "CHAR_009", "小明"), "voice_b")
        self.assertEqual(tts_api.voice_for({}, "CHAR_001"), "")

    def test_rename_keeps_mapping(self):
        voices = {"CHAR_001": "voice_a"}
        before = tts_api.voice_for(voices, "CHAR_001", "阿明")
        after = tts_api.voice_for(voices, "CHAR_001", "阿明（改名）")
        self.assertEqual(before, after)

    def test_missing_voices_lists_only_unconfigured_speakers(self):
        entries = [("SH001", "CHAR_001", "你好", 0.0, 1.0),
                   ("SH001", "CHAR_002", "再见", 1.0, 2.0),
                   ("SH002", "", "旁白", 0.0, 1.0)]
        assets = {"CHAR_001": {"name": "阿明"}}
        missing = tts_api.missing_voices(entries, assets, {"CHAR_001": "voice_a"})
        self.assertEqual(missing, [{"speaker": "CHAR_002", "name": "CHAR_002"}])

    def test_silent_lines_flags_blank_text(self):
        entries = [("SH001", "CHAR_001", "  ", 0.0, 1.0), ("SH001", "CHAR_002", "有词", 1.0, 2.0)]
        self.assertEqual(tts_api.silent_lines(entries),
                         [{"shot": "SH001", "speaker": "CHAR_001"}])

    def test_voice_snapshot_reports_version_and_speeds(self):
        snapshot = tts_api.voice_snapshot({"voice_version": 3, "voices": {"CHAR_001": "voice_a"},
                                           "speeds": {"CHAR_001": 1.5}})
        self.assertEqual(snapshot["version"], 3)
        self.assertEqual(snapshot["voices"]["CHAR_001"], {"voice": "voice_a", "speed": 1.5})

    def test_save_key_bumps_version_only_on_change(self):
        store = {}
        with patch.object(tts_api, "read_settings", side_effect=lambda: dict(store)), \
             patch.object(tts_api, "write_settings", side_effect=lambda data, gateway=None: store.update(data)), \
             patch("model_pool.save_named_key", return_value=None):
            tts_api.save_key("https://api.example.com/v1", "tts-1", "alloy", "sk-x", voices={"CHAR_001": "v1"})
            self.assertEqual(store["voice_version"], 1)
            tts_api.save_key("https://api.example.com/v1", "tts-1", "alloy", "sk-x", voices={"CHAR_001": "v1"})
            self.assertEqual(store["voice_version"], 1)
            tts_api.save_key("https://api.example.com/v1", "tts-1", "alloy", "sk-x", voices={"CHAR_001": "v2"})
            self.assertEqual(store["voice_version"], 2)


class AudioKindTests(unittest.TestCase):
    def test_dialogue_keeps_plain_name(self):
        self.assertEqual(tts_api.marked_audio_name("input", "dialogue"), "input")
        self.assertEqual(tts_api.audio_kind("input.wav"), "dialogue")

    def test_non_dialogue_is_prefixed_and_roundtrips(self):
        for kind in ("narration", "bgm", "sfx", "full"):
            name = tts_api.marked_audio_name("track", kind) + ".mp3"
            self.assertEqual(tts_api.audio_kind(name), kind)

    def test_unknown_kind_defaults_to_dialogue(self):
        self.assertEqual(tts_api.audio_kind("whatever.mp3"), "dialogue")
        self.assertEqual(tts_api.marked_audio_name("x", "nonsense"), "x")


class EpisodeBindingTests(unittest.TestCase):
    def setUp(self):
        self.lines = [line(1), line(2)]

    def test_batch_signature_default_matches_legacy(self):
        expected = hashlib.sha256(json.dumps(self.lines, ensure_ascii=False,
                                             sort_keys=True).encode("utf-8")).hexdigest()
        self.assertEqual(tts_api.batch_signature(self.lines), expected)

    def test_episode_changes_signature(self):
        self.assertNotEqual(tts_api.batch_signature(self.lines, "EP01"),
                            tts_api.batch_signature(self.lines, "EP02"))

    def test_two_episodes_do_not_share_resume_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first, second = root / "first", root / "second"
            for folder, episode in ((first, "EP01"), (second, "EP02")):
                tts_api.run_lines(self.lines, folder, generate=lambda *a, **k: b"audio",
                                  gateway=_gateway(), episode=episode)
            self.assertEqual(tts_api.resume_folder(root, self.lines, "EP01"), first)
            self.assertEqual(tts_api.resume_folder(root, self.lines, "EP02"), second)
            self.assertIsNone(tts_api.resume_folder(root, self.lines, "EP03"))
            self.assertIsNone(tts_api.resume_folder(root, self.lines))


class AudioImportKindTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "song.mp3"
        self.source.write_bytes(b"audio bytes")

    def publish(self, target, source):
        target.write_bytes(source.read_bytes())

    def test_bgm_import_is_marked(self):
        with patch("domain.audio_import_service.uuid.uuid4") as created:
            created.return_value.hex = "abcdef123456"
            result = import_audio(self.root, self.source, publish=self.publish, kind="bgm")
        self.assertTrue(result.ok)
        self.assertEqual(result.data.name, "BGM_song_abcdef.mp3")
        self.assertEqual(tts_api.audio_kind(result.data.name), "bgm")

    def test_dialogue_import_keeps_plain_name(self):
        with patch("domain.audio_import_service.uuid.uuid4") as created:
            created.return_value.hex = "abcdef123456"
            result = import_audio(self.root, self.source, publish=self.publish)
        self.assertEqual(result.data.name, "song_abcdef.mp3")

    def test_rejects_unknown_kind(self):
        with self.assertRaises(ValueError):
            import_audio(self.root, self.source, publish=self.publish, kind="nope")


class AudioCompletionKindTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "storyboard" / "episode.json"
        save(self.source, {"id": "EP01", "shots": [{"id": "S01"}]})
        save(self.root / "ui_settings.json",
             {"frame_json": str(self.source), "adopted_storyboards": [str(self.source)]})
        save(self.root / "config.json", {"ffprobe": "test-probe"})

    def artifact(self, name):
        folder = media_output_folders(self.root, "audio")[0][0]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_bytes(b"fixture-media")
        return path

    def prepare(self, path):
        result = {"format": {"duration": "2.5"}, "streams": [{"codec_type": "audio"}]}
        with patch("agent.media.probe", return_value=result):
            return prepare_media_completion(self.root, "audio", [path])

    def test_bgm_only_cannot_complete_dialogue(self):
        with self.assertRaisesRegex(ValueError, "对白音轨"):
            self.prepare(self.artifact("BGM_theme.wav"))

    def test_dialogue_track_is_accepted(self):
        prepared = self.prepare(self.artifact("line.wav"))
        self.assertEqual(prepared["status"], "pending_review")


if __name__ == "__main__":
    unittest.main(verbosity=2)
