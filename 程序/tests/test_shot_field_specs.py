# -*- coding: utf-8 -*-
"""镜头字段单一事实源（轮 6C·D7）的契约断言。

镜头字段事实收敛在 ``contract.episode_contract``（SHOT_FIELD_SPECS 与取值常量），
``shot_batches.schema()``／``shot_batches.validate()``、``episode_contract.validate_episode()``、
``storyboard_contract.rules()`` 是它的呈现。断言检验「同一事实被各呈现共用」的行为，
不比对源码字符串；rules() 的逐字一致由 tests/fixtures/golden/storyboard_contract_rules.txt
黄金对照守卫（见 test_golden_outputs.py）。
"""
import re
import unittest

from contract import episode_contract, shot_batches, storyboard_contract


def _shot(**overrides):
    shot = {'id': 'SH001', 'title': '镜头', 'duration': 3, 'characters': [],
            'location': 'LOC_001', 'frame': 'frames/SH001.png',
            'frame_prompt': 'x', 'video_prompt': 'x' * 5, 'dialogue': []}
    shot.update(overrides)
    return shot


class FactTableTests(unittest.TestCase):
    def test_specs_cover_the_contract_shot_fields(self):
        names = [name for name, _note, _fragment in episode_contract.SHOT_FIELD_SPECS]
        for expected in ('id', 'title', 'duration', 'characters', 'location', 'props',
                         'frame', 'frame_prompt', 'video_prompt', 'dialogue',
                         'action_complexity', 'complexity_reason', 'ordinary_props',
                         'edit_duration', 'trim_in', 'trim_out'):
            self.assertIn(expected, names)

    def test_scalar_facts_have_expected_values(self):
        self.assertEqual(episode_contract.SHOT_ID_SAMPLE, 'SH001')
        self.assertEqual(episode_contract.SHOT_DURATION_RANGE, (2, 15))
        self.assertEqual(episode_contract.VIDEO_PROMPT_RANGE, (1, 1500))
        self.assertEqual(episode_contract.ACTION_COMPLEXITY, ('simple', 'medium', 'complex'))

    def test_id_pattern_accepts_contract_formats_only(self):
        pattern = episode_contract.SHOT_ID_PATTERN
        for good in ('SH001', 'SH123', 'EP001_SH001'):
            self.assertTrue(re.fullmatch(pattern, good), good)
        for bad in ('SH01', 'S01', 'X001', 'EP1_SH001', 'SH001x'):
            self.assertFalse(re.fullmatch(pattern, bad), bad)


class SchemaPresentationTests(unittest.TestCase):
    def test_shot_required_derives_from_batch_shot_fields(self):
        shot = shot_batches.schema()['properties']['shots']['items']
        self.assertEqual(shot['required'], [row[0] for row in shot_batches.SHOT_FIELDS])
        self.assertEqual(len(shot['required']), 9)

    def test_shot_properties_cover_every_spec_with_a_fragment(self):
        specs = {name: fragment for name, _note, fragment in episode_contract.SHOT_FIELD_SPECS
                 if fragment is not None}
        props = shot_batches.schema()['properties']['shots']['items']['properties']
        for name, fragment in specs.items():
            self.assertEqual(props.get(name), fragment, name)

    def test_batch_field_properties_derive_from_shot_fields_rows(self):
        props = shot_batches.schema()['properties']['shots']['items']['properties']
        for row in shot_batches.SHOT_FIELDS:
            name, _source, _note, fragment = row
            self.assertEqual(props.get(name), fragment, name)

    def test_duration_bounds_in_schema_match_the_shared_range(self):
        props = shot_batches.schema()['properties']['shots']['items']['properties']
        low, high = episode_contract.SHOT_DURATION_RANGE
        for key in ('duration', 'estimated_duration'):
            self.assertEqual(props[key]['minimum'], low, key)
            self.assertEqual(props[key]['maximum'], high, key)

    def test_action_complexity_enum_comes_from_the_shared_values(self):
        props = shot_batches.schema()['properties']['shots']['items']['properties']
        self.assertEqual(props['action_complexity']['enum'],
                         list(episode_contract.ACTION_COMPLEXITY))


class ValidatePresentationTests(unittest.TestCase):
    def test_episode_validator_uses_the_shared_duration_range(self):
        # duration 越界的报错文案由 SHOT_DURATION_RANGE 渲染；改区间两处同时变。
        episode = {'episode_id': 'EP001', 'title': 't', 'duration': 1, 'shots': [_shot(duration=1)]}
        with self.assertRaises(ValueError) as ctx:
            episode_contract.validate_episode(episode, __file__)
        self.assertIn('时长必须为2–15的整数秒', str(ctx.exception))

    def test_batch_validator_uses_the_shared_duration_range(self):
        shot = shot_batches.normalize(_shot(estimated_duration=16), 0)
        problems = shot_batches.validate(shot, 0)
        self.assertTrue(any('2–15' in text for text in problems), problems)

    def test_video_prompt_range_is_enforced_by_episode_validator(self):
        episode = {'episode_id': 'EP001', 'title': 't', 'duration': 3,
                   'shots': [_shot(video_prompt='x' * 1501)]}
        with self.assertRaises(ValueError) as ctx:
            episode_contract.validate_episode(episode, __file__)
        self.assertIn('video_prompt须为1–1500字符', str(ctx.exception))


class RulesPresentationTests(unittest.TestCase):
    def test_rules_renders_enum_segments_from_the_fact_table(self):
        text = storyboard_contract.rules()
        head = storyboard_contract._field_text('id', 'title', 'duration')
        tail = storyboard_contract._field_text('characters', 'location', 'props', 'frame',
                                             'frame_prompt', 'video_prompt', 'dialogue')
        self.assertIn('每镜必须有 ' + head + '、', text)
        self.assertIn(tail + '。', text)
        self.assertEqual(head, 'id（SH001 格式且不重复）、title、duration（2–15 的整数秒）')

    def test_rules_injects_shared_scalars(self):
        text = storyboard_contract.rules()
        low, high = episode_contract.VIDEO_PROMPT_RANGE
        self.assertIn('%d–%d 个字符' % (low, high), text)
        self.assertIn('超过%d秒' % episode_contract.SHOT_DURATION_RANGE[1], text)
        self.assertIn(episode_contract.SHOT_ID_SAMPLE, text)

    def test_field_text_rejects_names_outside_the_fact_table(self):
        with self.assertRaises(KeyError):
            storyboard_contract._field_text('not_a_shot_field')


if __name__ == '__main__':
    unittest.main()
