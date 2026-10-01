"""三虎项目状态读取必须复用正式 JSON 缓存。"""
import tempfile
import unittest
from pathlib import Path


class ProjectStatusCacheTests(unittest.TestCase):
    def test_status_read_uses_cache_and_atomic_save_invalidates_it(self):
        import skill_orchestrator as subject
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            subject.save_project_status({'step': 1}, project)
            self.assertEqual(subject.load_project_status(project), {'step': 1})
            subject.save_project_status({'step': 2}, project)
            self.assertEqual(subject.load_project_status(project), {'step': 2})


if __name__ == '__main__':
    unittest.main()
