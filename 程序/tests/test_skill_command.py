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

    def test_sub_engine_names_from_registered_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            items = [SimpleNamespace(name='sd-alpha-engine', layer='user',
                                     path=base / 'alpha' / 'SKILL.md'),
                     SimpleNamespace(name='sd-alpha-engine', layer='project',
                                     path=base / 'override' / 'SKILL.md'),
                     SimpleNamespace(name='flat', layer='user', path=base / 'flat.skill.md'),
                     SimpleNamespace(name='builtin', layer='builtin', path=base / 'SKILL.md'),
                     SimpleNamespace(name='../unsafe', layer='user', path=base / 'README.md'),
                     SimpleNamespace(name='broken', layer='user', path=None)]
            names = skill_command.sub_engine_names(items)
        self.assertEqual(names, ('sd-alpha-engine',))
        parsed = skill_command.parse_command('/sd-alpha-engine 继续', skills=items)
        self.assertEqual(parsed['kind'], 'engine')
        completions = skill_command.completion_entries('sd-alpha', skills=items)
        self.assertEqual([(row['name'], row['kind']) for row in completions],
                         [('sd-alpha-engine', 'engine')])
        self.assertEqual(skill_command.parse_command('/flat', skills=items)['kind'], 'skill')

    def test_empty_registered_engines_need_no_filesystem(self):
        from unittest.mock import patch
        with patch.object(Path, 'iterdir', side_effect=AssertionError('must not scan')):
            self.assertEqual(skill_command.sub_engine_names(), ())
            self.assertIsNone(skill_command.parse_command('/未知引擎'))
            self.assertEqual(skill_command.KINDS, ('skill', 'stage', 'engine'))


class CompletionEntriesTests(unittest.TestCase):
    """R2980：``completion_entries`` 结构化候选——当前阶段 skill → 其余 → 阶段别名 → 子引擎。"""

    def test_current_stage_skills_first(self):
        skills = [_skill('other-stage-skill', stage='assets'),
                  _skill('mine-a', stage='storyboard'), _skill('mine-b', stage='storyboard')]
        out = skill_command.completion_entries('', stage='storyboard', skills=skills, engines=())
        self.assertEqual([e['name'] for e in out[:2]], ['mine-a', 'mine-b'])
        self.assertEqual([e['kind'] for e in out[:2]], ['skill', 'skill'])
        names = [e['name'] for e in out]
        self.assertIn('other-stage-skill', names)
        self.assertLess(names.index('mine-a'), names.index('other-stage-skill'))

    def test_stage_aliases_and_engines_follow(self):
        out = skill_command.completion_entries('', skills=[], engines=('sd-script-engine',))
        kinds = [e['kind'] for e in out]
        # 阶段别名排在子引擎之前。
        self.assertLess(kinds.index('stage'), kinds.index('engine'))
        names = [e['name'] for e in out]
        self.assertIn('storyboard', names)
        self.assertIn('sd-script-engine', names)
        self.assertEqual(out[-1]['insert'], '/sd-script-engine ')

    def test_prefix_filters(self):
        skills = [_skill('alpha-skill'), _skill('beta-skill')]
        out = skill_command.completion_entries('alpha', skills=skills, engines=())
        self.assertEqual([e['name'] for e in out], ['alpha-skill'])
        self.assertEqual(skill_command.completion_entries('zzz', skills=skills, engines=()), ())

    def test_insert_and_label_shape(self):
        out = skill_command.completion_entries('plot', skills=[_skill('plot')], engines=())
        self.assertEqual(len(out), 1)
        entry = out[0]
        self.assertEqual(entry['kind'], 'skill')
        self.assertEqual(entry['label'], '/plot')
        self.assertEqual(entry['insert'], '/plot ')

    def test_dict_and_plain_string_items(self):
        skills = [{'name': 'dict-skill', 'stage': 'assets'}, 'plain-skill']
        out = skill_command.completion_entries('', stage='storyboard', skills=skills, engines=())
        names = [e['name'] for e in out]
        # 字符串视为当前阶段排前；字典按 stage 键归入其余。
        self.assertLess(names.index('plain-skill'), names.index('dict-skill'))


class TriggerTokenTests(unittest.TestCase):
    """R2980：``trigger_token`` 光标处 ``/``／``@`` 触发边界与 token 范围。"""

    def test_line_start_and_after_space(self):
        for text in ('/pl', '帮我 /分镜 一下', 'a\n/b'):
            with self.subTest(text=text):
                token = skill_command.trigger_token(text, len(text))
                self.assertIsNotNone(token)
                self.assertEqual(token['kind'], 'command')

    def test_no_trigger_inside_word_url_or_fraction(self):
        for text in ('a/b', 'https://example.com', '3/4', 'a@b.com'):
            with self.subTest(text=text):
                self.assertIsNone(skill_command.trigger_token(text, len(text)))

    def test_query_and_bounds(self):
        token = skill_command.trigger_token('帮我 /分镜一下', len('帮我 /分镜一下'))
        self.assertEqual(token['kind'], 'command')
        self.assertEqual(token['query'], '分镜一下')
        self.assertEqual(token['start'], 3)
        # 光标落在 token 中间：end 仍覆盖到词尾。
        token = skill_command.trigger_token('/story rest', 3)
        self.assertEqual((token['start'], token['end']), (0, 6))

    def test_mention_kind(self):
        text = '看 @人物'
        token = skill_command.trigger_token(text, len(text))
        self.assertEqual(token['kind'], 'mention')
        self.assertEqual(token['query'], '人物')

    def test_punctuation_terminates_end(self):
        token = skill_command.trigger_token('/name，后文', 5)
        self.assertEqual(token['end'], 5, '光标在标点前时 token 不得吞掉标点')

    def test_nearest_trigger_wins(self):
        token = skill_command.trigger_token('/a @b', len('/a @b'))
        self.assertEqual(token['kind'], 'mention')
        self.assertEqual(token['query'], 'b')

    def test_full_width_space_counts_as_boundary(self):
        token = skill_command.trigger_token('帮我　/分镜', len('帮我　/分镜'))
        self.assertIsNotNone(token, '全角空格同样是合法触发边界')


if __name__ == '__main__':
    unittest.main()
