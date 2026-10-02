"""视频提示词多份成果发布的回归。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import read, restore_bytes, save, save_bytes
import video_prompt_publication


class _Studio:
    def __init__(self, root):
        self.episode_path = root / 'episode.json'
        self.media_dir = root
        self.episode = read(self.episode_path)
        self.root = root

    def shot_folder(self, sid):
        return self.root / 'shots' / sid


class VideoPromptPublicationTests(unittest.TestCase):
    @staticmethod
    def _gateway():
        return {'publish_bundle': lambda artifacts, _validate, _index: [save_bytes(path, data)
                                                                           for path, data in artifacts.items()],
                'read_bytes': lambda path: Path(path).read_bytes(), 'publish_json': save,
                'publish_bytes': save_bytes, 'restore_bytes': restore_bytes,
                'remove_dir': lambda folder: folder.rmdir()}
    def _studio(self, root):
        path = root / 'episode.json'
        save(path, {'shots': [{'id': 'SH001', 'video_prompt': '旧提示词'}]})
        return _Studio(root)

    def test_publish_updates_all_visible_prompt_artifacts(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); studio = self._studio(root)
            record = video_prompt_publication.publish(
                studio, 'SH001', '新提示词', publish_bundle=self._gateway()['publish_bundle'])
            self.assertEqual(record['video_prompt'], '新提示词')
            self.assertEqual(read(root / 'episode.json')['shots'][0]['video_prompt'], '新提示词')
            self.assertEqual(read(root / 'video_prompts' / 'SH001.json')['video_prompt'], '新提示词')
            self.assertEqual((root / 'video_prompts' / 'SH001.txt').read_text(encoding='utf-8'), '新提示词')
            self.assertEqual((root / 'shots' / 'SH001' / '当前提示词.txt').read_text(encoding='utf-8'), '新提示词')

    def test_first_artifact_failure_restores_preexisting_episode(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); studio = self._studio(root)
            before = studio.episode_path.read_bytes()
            writes = []

            def fail_first_write(path, data):
                if not writes:
                    writes.append(path)
                    raise OSError('磁盘错误')
                return save_bytes(path, data)

            gateway = self._gateway(); gateway['publish_bundle'] = lambda artifacts, _validate, _index: [
                fail_first_write(path, data) for path, data in artifacts.items()]
            with self.assertRaisesRegex(OSError, '磁盘错误'):
                video_prompt_publication.publish(studio, 'SH001', '新提示词',
                                                 publish_bundle=gateway['publish_bundle'])
            self.assertEqual(studio.episode_path.read_bytes(), before)
            self.assertFalse((root / 'video_prompts' / 'SH001.json').exists())
            self.assertEqual(studio.episode['shots'][0]['video_prompt'], '旧提示词')

    def test_stage_import_stores_draft_without_changing_episode(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); studio = self._studio(root)
            record = video_prompt_publication.stage_import(studio, 'SH001', '导入提示词', gateway=self._gateway())
            self.assertEqual(record['provider'], 'import')
            self.assertEqual(read(root / 'video_prompts' / 'SH001.json')['video_prompt'], '导入提示词')
            self.assertEqual(read(root / 'episode.json')['shots'][0]['video_prompt'], '旧提示词')

    def test_stage_import_failure_keeps_previous_draft_and_cleans_backup(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); studio = self._studio(root)
            target = root / 'video_prompts' / 'SH001.json'
            save(target, {'video_prompt': '旧草稿'})
            before = target.read_bytes()
            gateway = self._gateway(); gateway['publish_json'] = lambda *_args: (_ for _ in ()).throw(OSError('磁盘错误'))
            with self.assertRaisesRegex(OSError, '磁盘错误'):
                video_prompt_publication.stage_import(studio, 'SH001', '导入提示词', gateway=gateway)
            self.assertEqual(target.read_bytes(), before)
            self.assertFalse((root / 'video_prompts' / '历史版本').exists())
