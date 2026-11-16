"""剧本 API 不得反向依赖阶段配置编排，读阶段模型走 L1 协议、回退口令走 L2 启发式。"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WritingApiStageConfigBoundaryTests(unittest.TestCase):
    def test_writing_api_reads_stage_model_via_l1_protocol_not_l3_config(self):
        """P0-2：writing_api 读阶段模型须走 L1 stage_model_value，不得反向依赖 L3 stage_config。"""
        source = (ROOT / 'writing_api.py').read_text(encoding='utf-8')
        self.assertIn('import stage_model_value', source)
        self.assertNotIn('import stage_config', source)
        self.assertNotIn('stage_config.get', source)

    def test_restart_intent_uses_l2_heuristic_not_l3_workflow_tasks(self):
        """P0-2：回退口令判定下沉 L2 idea_script_heuristic，不得反向依赖 L3 workflow_tasks。"""
        source = (ROOT / 'writing_api.py').read_text(encoding='utf-8')
        self.assertIn('from domain.idea_script_heuristic import writing_restart_requested', source)
        self.assertNotIn('from workflow_tasks import writing_restart_requested', source)

    def test_l2_heuristic_is_pure_text_without_orchestration_deps(self):
        """下沉的回退口令判定须保持纯文本：不读阶段配置、不碰编排层。"""
        source = (ROOT / 'domain/idea_script_heuristic.py').read_text(encoding='utf-8')
        self.assertIn('def writing_restart_requested(text):', source)
        self.assertNotIn('import stage_config', source)
        self.assertNotIn('import workflow_tasks', source)

    def test_workflow_tasks_re_exports_heuristic_for_existing_callers(self):
        """workflow_tasks.writing_restart_requested 按名转发 L2 实现，保持既有调用与测试锚点。"""
        source = (ROOT / 'workflow_tasks.py').read_text(encoding='utf-8')
        self.assertIn('def writing_restart_requested(text):', source)
        self.assertIn('from domain.idea_script_heuristic import writing_restart_requested', source)


if __name__ == '__main__':
    unittest.main()
