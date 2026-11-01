"""``skill_config.json`` 的文件名只在路径权威 ``stage_layout`` 里写一次（J-配置）。"""
import ast
import unittest

from tests.architecture._scan import ROOT, parse, production_runtime_files

NAME = 'skill_config.json'
AUTHORITY = 'stage_layout.py'


class SkillConfigPathSingleEntryTests(unittest.TestCase):
    def test_only_the_path_authority_spells_the_file_name(self):
        offenders = []
        for path in production_runtime_files():
            if path.name == AUTHORITY:
                continue
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.Constant) and node.value == NAME:
                    offenders.append('%s:%d' % (path.relative_to(ROOT).as_posix(), node.lineno))
        self.assertEqual(offenders, [], '请用 stage_layout.skill_config_path()／SKILL_CONFIG_NAME，不要另拼文件名')


if __name__ == '__main__':
    unittest.main()
