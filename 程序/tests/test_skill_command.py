"""R2893 轮 3：``/`` 命令解析、补全排序与阶段别名映射（无 Tk）。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import skill_command
from contract import pet_bus


def _skill(name, stage='storyboard'):
    return SimpleNamespace(name=name, stage=stage)


class ParseCommandTests(unittest.TestCase):
    def test_free_chat_returns_none(self):
        for text in ('', '你好', '写一段开场', ' /skill'):
            self.assertIsNone(skill_command.parse_command(text))

    def test_skill_name_exact_and_case_insensitive(self):
        skills = [_skill('sd-script-engine'), _skill('Storyboard-Helper')]
        hit = skill_command.parse_command('/sd-script-engine 把第三幕写细', skills=skills)
        self.assertEqual(hit['kind'], 'skill')
        self.assertEqual(hit['name'], 'sd-script-engine')
        self.assertEqual(hit['rest'], '把第三幕写细')
        hit = skill_command.parse_command('/storyboard-helper', skills=skills)
        self.assertEqual(hit['name'], 'Storyboard-Helper')

    def test_stage_alias_forms(self):
        for token, stage in (('/storyboard', 'storyboard'), ('/初步分镜', 'storyboard'),
                             ('/03', 'storyboard'), ('/03 初步分镜', 'storyboard'),
                             ('/剧本准备', 'script'), ('/delivery', 'delivery')):
            with self.subTest(token=token):
                hit = skill_command.parse_command(token)
                self.assertEqual(hit['kind'], 'stage')
                self.assertEqual(hit['stage'], stage)

    def test_ambiguous_stage_name_takes_first_in_order(self):
        # 「分镜」同时出现在初步分镜／分镜预演／分镜定稿：取阶段顺序第一条。
        hit = skill_command.parse_command('/分镜')
        self.assertEqual(hit['stage'], 'storyboard')

    def test_engine_name(self):
        engines = ('sd-script-engine', 'sd-storyboard-engine')
        hit = skill_command.parse_command('/sd-storyboard-engine 全部重做', engines=engines)
        self.assertEqual(hit['kind'], 'engine')
        self.assertEqual(hit['name'], 'sd-storyboard-engine')
        self.assertEqual(hit['rest'], '全部重做')

    def test_unknown_slash_is_not_a_command(self):
        self.assertIsNone(skill_command.parse_command('/不存在的东西'))
        self.assertIsNone(skill_command.parse_command('/'))

    def test_skill_wins_over_stage_alias(self):
        skills = [_skill('storyboard', stage='script')]
        hit = skill_command.parse_command('/storyboard', skills=skills)
        self.assertEqual(hit['kind'], 'skill')

    def test_sub_engine_names_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'skills' / '00全流程SKILL' / 'AIGC创作全流程'
            (base / 'sd-alpha-engine').mkdir(parents=True)
            (base / 'sd-alpha-engine' / 'SKILL.md').write_text('x', encoding='utf-8')
            (base / 'empty-dir').mkdir()
            (base / '.hidden').mkdir()
            names = skill_command.sub_engine_names(Path(tmp) / 'skills')
        self.assertEqual(names, ('sd-alpha-engine',))


class CompletionsTests(unittest.TestCase):
    def test_current_stage_skills_first(self):
        skills = [_skill('other-stage-skill', stage='assets'),
                  _skill('mine-a', stage='storyboard'), _skill('mine-b', stage='storyboard')]
        out = skill_command.completions('/', stage='storyboard', skills=skills, engines=())
        self.assertEqual(out[:2], ('/mine-a', '/mine-b'))
        self.assertIn('/other-stage-skill', out)

    def test_stage_aliases_and_engines_follow(self):
        out = skill_command.completions('/', skills=[], engines=('sd-script-engine',))
        joined = ' '.join(out)
        self.assertIn('/01', joined)
        self.assertIn('/storyboard', joined)
        self.assertIn('/sd-script-engine', joined)
        # 子引擎排在阶段别名之后。
        self.assertLess(joined.index('/storyboard'), joined.index('/sd-script-engine'))

    def test_prefix_filters(self):
        skills = [_skill('alpha-skill'), _skill('beta-skill')]
        out = skill_command.completions('/alpha', skills=skills, engines=())
        self.assertEqual(out, ('/alpha-skill',))
        self.assertEqual(skill_command.completions('abc', skills=skills), ())

    def test_command_token(self):
        self.assertEqual(skill_command.command_token('/sto rest'), '/sto')
        self.assertEqual(skill_command.command_token('/'), '/')
        self.assertEqual(skill_command.command_token('plain'), '')


if __name__ == '__main__':
    unittest.main()
