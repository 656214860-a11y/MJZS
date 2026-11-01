"""J22：「工作流任务」目录由路径权威 stage_layout 产出。"""
import unittest
from pathlib import Path

import stage_layout


class WorkflowDirAuthorityTests(unittest.TestCase):
    def test_workflow_dir_joins_parts_under_the_project(self):
        project = Path('项目')
        self.assertEqual(stage_layout.workflow_dir(project), project / '工作流任务')
        self.assertEqual(stage_layout.workflow_dir(str(project), '宠物', '通知.json'),
                         project / '工作流任务' / '宠物' / '通知.json')

    def test_constant_is_the_single_name(self):
        self.assertEqual(stage_layout.WORKFLOW_DIR, '工作流任务')


if __name__ == '__main__':
    unittest.main()
