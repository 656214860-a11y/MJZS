"""C4 部分交付：项目设置的安全读取视图不能成为损坏文件的写入基础。"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from infra import project_settings


class ProjectSettingsValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.target = project_settings.file(self.project)

    def assert_rejected_unchanged(self, original, *, value=True, read_error=None):
        self.target.write_bytes(original)
        errors = []
        with mock.patch.object(project_settings, 'save', wraps=project_settings.save) as publisher:
            reader = (mock.patch.object(project_settings, 'read', side_effect=read_error)
                      if read_error is not None else mock.patch.object(
                          project_settings, 'read', wraps=project_settings.read))
            with reader:
                try:
                    project_settings.put(self.project, 'auto_review', value)
                except ValueError as exc:
                    errors.append(str(exc))
            self.assertEqual(self.target.read_bytes(), original)
            publisher.assert_not_called()
        self.assertEqual(len(errors), 1)
        self.assertIn('ui_settings.json', errors[0])
        self.assertIn('请', errors[0])
        self.assertNotIn('fixture_private_value', errors[0])
        self.assertNotIn(str(self.project), errors[0])

    def test_bad_json_rejects_without_publishing(self):
        self.assert_rejected_unchanged(b'{"unknown":"fixture_private_value",')

    def test_non_object_roots_reject_without_publishing(self):
        for original in (b'[]', b'null', b'"fixture_private_value"', b'42', b'false'):
            with self.subTest(original=original):
                self.assert_rejected_unchanged(original)

    def test_invalid_utf8_rejects_without_publishing(self):
        self.assert_rejected_unchanged(b'{"unknown":"\xfffixture_private_value"}')

    def test_permission_error_rejects_without_publishing(self):
        self.assert_rejected_unchanged(
            b'{"unknown":"fixture_private_value"}',
            read_error=PermissionError('fixture_private_value'))

    def test_other_oserror_rejects_without_publishing(self):
        self.assert_rejected_unchanged(
            b'{"unknown":"fixture_private_value"}',
            read_error=OSError('fixture_private_value'))

    def test_noop_value_still_requires_strict_read(self):
        self.assert_rejected_unchanged(b'{"unknown":"fixture_private_value",', value=None)

    def test_safe_off_view_does_not_allow_overwriting_later_corruption(self):
        self.target.write_bytes(b'{"unknown":"fixture_private_value",')
        self.assertEqual(project_settings.load(self.project), {})
        self.assertFalse(project_settings.auto_review(self.project))
        self.assert_rejected_unchanged(self.target.read_bytes())

    def test_missing_file_can_be_created(self):
        with mock.patch.object(project_settings, 'save', wraps=project_settings.save) as publisher:
            self.assertTrue(project_settings.put(self.project, 'auto_review', True))
            publisher.assert_called_once()
        self.assertEqual(json.loads(self.target.read_bytes()), {'auto_review': True})

    def test_unknown_fields_and_detached_read_view_survive(self):
        original = {'unknown': {'nested': ['keep']}, 'auto_adopt': True}
        self.target.write_bytes(json.dumps(original).encode('utf-8'))
        view = project_settings.load(self.project)
        view['unknown']['nested'].append('local-only')
        self.assertTrue(project_settings.put(self.project, 'auto_review', True))
        self.assertEqual(json.loads(self.target.read_bytes()), dict(original, auto_review=True))

    def test_strict_reread_occurs_inside_lock(self):
        self.target.write_bytes(b'{"unknown":true}')
        held = []
        class Lock:
            def __enter__(self):
                held.append(True)
            def __exit__(self, *args):
                held.pop()
        real_read = project_settings.read
        def checked_read(path):
            self.assertEqual(held, [True])
            return real_read(path)
        with mock.patch.object(project_settings, 'access', return_value=Lock()), \
                mock.patch.object(project_settings, 'read', side_effect=checked_read):
            self.assertTrue(project_settings.put(self.project, 'auto_review', True))

    def test_two_threads_preserve_distinct_keys(self):
        self.target.write_bytes(b'{"unknown":{"keep":true}}')
        barrier = threading.Barrier(2)
        errors = []
        def update(key):
            try:
                barrier.wait(timeout=5)
                project_settings.put(self.project, key, True)
            except Exception as exc:
                errors.append(type(exc).__name__)
        threads = [threading.Thread(target=update, args=(key,))
                   for key in ('auto_review', 'auto_adopt')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(json.loads(self.target.read_bytes()),
                         {'unknown': {'keep': True}, 'auto_review': True, 'auto_adopt': True})
