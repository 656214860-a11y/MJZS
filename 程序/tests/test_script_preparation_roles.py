"""REQ-S01-15：剧本准备阶段质检提示词定义编剧／编辑／演员三角色把关。"""
import unittest

import domain.writing_quality as writing_quality


class ScriptPreparationRoleTests(unittest.TestCase):
    def setUp(self):
        self.section = writing_quality.prompt()

    def test_three_roles_declared(self):
        for role, duty in (('编剧角色', '五阶门控'), ('编辑角色', '情绪节拍'), ('演员角色', '台词七维诊断')):
            with self.subTest(role=role):
                self.assertIn(role, self.section)
                self.assertIn(duty, self.section)

    def test_roles_do_not_add_confirmation_step(self):
        self.assertNotIn('APPROVED', self.section)
        self.assertNotIn('HOLLMWOOD', self.section)


if __name__ == '__main__':
    unittest.main()
