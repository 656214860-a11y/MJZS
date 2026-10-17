"""REQ-S01-15：剧本准备阶段 SKILL 定义编剧／编辑／演员三角色把关。"""
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / 'skills' / '01 剧本准备SKILL' / 'pipeline-script-preparation.skill.md'


class ScriptPreparationRoleTests(unittest.TestCase):
    def setUp(self):
        text = SKILL.read_text(encoding='utf-8')
        self.assertIn('## 定向注入（00 包）', text)
        self.section = text.split('## 定向注入（00 包）', 1)[1].split('\n## ', 1)[0]

    def test_three_roles_declared(self):
        for role, duty in (('编剧角色', '五阶门控'), ('编辑角色', '情绪节拍'), ('演员角色', '台词七维诊断')):
            with self.subTest(role=role):
                self.assertIn(role, self.section)
                self.assertIn(duty, self.section)

    def test_roles_do_not_add_confirmation_step(self):
        self.assertIn('不另设确认阶段', self.section)


if __name__ == '__main__':
    unittest.main()
