import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.core import read, save
from storyboard_edit_service import save_edited_json


class StoryboardEditServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'episode.json'
        save(self.path, {'title': '旧内容'})

    def test_valid_json_is_published_atomically(self):
        result = save_edited_json(self.path, {'title': '新内容'})
        self.assertEqual(result, self.path.resolve())
        self.assertEqual(read(self.path), {'title': '新内容'})

    def test_save_failure_keeps_existing_document(self):
        with patch('storyboard_edit_service.save', side_effect=OSError('磁盘不可用')):
            with self.assertRaisesRegex(OSError, '磁盘不可用'):
                save_edited_json(self.path, {'title': '不应写入'})
        self.assertEqual(read(self.path), {'title': '旧内容'})

    def test_non_json_path_is_rejected_before_write(self):
        with self.assertRaisesRegex(ValueError, 'JSON'):
            save_edited_json(self.path.with_suffix('.txt'), {'title': '无效'})
