import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from agent.core import read, save
from storyboard_edit_service import save_edited_json
from contract.service_contract import ServiceResult, SystemError, UserError


class StoryboardEditServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'episode.json'
        save(self.path, {'title': '旧内容'})

    def test_valid_json_is_published_atomically(self):
        result = save_edited_json(self.path, {'title': '新内容'}, publish=save)
        self.assertIsInstance(result, ServiceResult)
        self.assertTrue(result.ok)
        self.assertFalse(result.recoverable)
        self.assertEqual(result.data, self.path.resolve())
        self.assertEqual(read(self.path), {'title': '新内容'})

    def test_save_failure_keeps_existing_document(self):
        def unavailable(_path, _data):
            raise OSError('磁盘不可用')
        with self.assertLogs('storyboard_edit_service', level='ERROR'):
            result = save_edited_json(self.path, {'title': '不应写入'}, publish=unavailable)
        self.assertIsInstance(result, SystemError)
        self.assertFalse(result.ok)
        self.assertTrue(result.recoverable)
        self.assertIsNone(result.data)
        self.assertNotIn('磁盘不可用', result.reason)
        self.assertEqual(read(self.path), {'title': '旧内容'})

    def test_non_json_path_is_rejected_before_write(self):
        publish = Mock()
        result = save_edited_json(self.path.with_suffix('.txt'), {'title': '无效'}, publish=publish)
        self.assertIsInstance(result, UserError)
        self.assertFalse(result.ok)
        self.assertIn('JSON', result.reason)
        publish.assert_not_called()

    def test_programming_error_is_not_disguised_as_operational_failure(self):
        with self.assertRaisesRegex(TypeError, 'bad publisher'):
            save_edited_json(self.path, {}, publish=Mock(side_effect=TypeError('bad publisher')))
        self.assertEqual(read(self.path), {'title': '旧内容'})

    def test_missing_publisher_is_rejected_before_write(self):
        with self.assertRaisesRegex(TypeError, '必须由 L3 注入'):
            save_edited_json(self.path, {'title': '不应写入'})
