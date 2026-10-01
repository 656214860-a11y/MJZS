"""独立批量首帧工具的成果文件写入回归。"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / '附加工具' / 'ComfyUI_批量首帧_Klein4B' / 'batch_frames.py'
SPEC = importlib.util.spec_from_file_location('extra_batch_frames', TOOL)
batch_frames = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch_frames)


class ExtraBatchFramesWriteTests(unittest.TestCase):
    def test_json_save_is_valid_atomic_destination_without_temp_residue(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'records' / 'job.json'
            payload = {'title': '首帧任务', 'shots': ['SH001']}
            batch_frames.save(destination, payload)
            self.assertEqual(json.loads(destination.read_text(encoding='utf-8')), payload)
            self.assertEqual(list(destination.parent.glob('*.tmp')), [])

    def test_binary_backup_save_replaces_destination_without_temp_residue(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'backup.json'
            batch_frames.save_bytes(destination, b'{"version": 1}')
            self.assertEqual(destination.read_bytes(), b'{"version": 1}')
            self.assertEqual(list(destination.parent.glob('*.tmp')), [])

    def test_new_frame_publish_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'frames' / 'SH001.png'
            destination.parent.mkdir()
            destination.write_bytes(b'old-frame')
            with self.assertRaises(FileExistsError):
                batch_frames.save_bytes_new(destination, b'new-frame')
            self.assertEqual(destination.read_bytes(), b'old-frame')
