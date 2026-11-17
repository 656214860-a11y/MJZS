"""三虎运行状态的正式 JSON 必须走缓存读与原子写。"""
import unittest

from tests.architecture._scan import entity_file


class SkillOrchestratorJsonBoundaryTests(unittest.TestCase):
    def test_project_status_uses_cache_for_read_and_core_for_write(self):
        path = entity_file('skill_orchestrator')
        with open(path, encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn('from infra.file_cache import read_json', source)
        self.assertIn('data = read_json(path)', source)
        self.assertIn('from agent.core import save_text', source)
        self.assertIn('save_text(path, json.dumps(', source)
        self.assertNotIn('json.loads(path.read_text(', source)


if __name__ == '__main__':
    unittest.main()
