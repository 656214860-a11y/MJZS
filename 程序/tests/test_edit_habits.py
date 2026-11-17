"""修改习惯：记录用户修改 → 归纳候选规则 → 用户确认 → 写进剧本准备提示词。"""
import json
import tempfile
import unittest
from pathlib import Path

from orchestrator import edit_habits
from workflow_engines import prompt_with_settings


class EditHabitsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root, self.program = base / '项目甲', base / 'program'
        self.root.mkdir()

    def record_three(self):
        for index in range(3):
            edit_habits.record_edit(self.root, 'script', '场景\n他说：我真的非常非常生气了你知道吗%d\n结尾' % index,
                                    '场景\n他说：我很生气%d\n结尾' % index, 'a.md', self.program)

    def test_record_keeps_only_changed_lines_and_skips_whitespace(self):
        """REQ-S01-58：只记改动片段；只改空白不记；非学习阶段不记。"""
        record = edit_habits.record_edit(self.root, 'script', '甲\n乙\n丙', '甲\n乙改\n丙', '自然剧本.md', self.program)
        self.assertEqual(record['hunks'], [{'before': '乙', 'after': '乙改'}])
        self.assertIsNone(edit_habits.record_edit(self.root, 'script', '甲 乙', '甲乙  ', program=self.program))
        self.assertIsNone(edit_habits.record_edit(self.root, 'storyboard', '甲', '乙', program=self.program))
        saved = json.loads(edit_habits.records_path(self.root, self.program).read_text(encoding='utf-8'))
        self.assertEqual(saved['schema_version'], 1)
        self.assertEqual(len(saved['records']), 1)
        self.assertEqual(saved['records'][0]['source'], '自然剧本.md', self.program)

    def test_records_are_capped_and_hunks_clipped(self):
        """REQ-S01-58：每段最多 600 字，最多保留 200 条。"""
        long = '长' * 2000
        edit_habits.record_edit(self.root, 'script', '', long, program=self.program)
        hunk = edit_habits.load_records(self.root, self.program)[0]['hunks'][0]
        self.assertEqual(len(hunk['after']), edit_habits.MAX_HUNK_CHARS + 1)
        for index in range(edit_habits.MAX_RECORDS + 5):
            edit_habits.record_edit(self.root, 'script', 'x', 'y%d' % index, program=self.program)
        records = edit_habits.load_records(self.root, self.program)
        self.assertEqual(len(records), edit_habits.MAX_RECORDS)
        self.assertEqual(records[-1]['hunks'][0]['after'], 'y%d' % (edit_habits.MAX_RECORDS + 4))

    def test_summarize_needs_three_records_before_calling_model(self):
        """REQ-S01-59：未归纳记录不足 3 条不调用模型。"""
        calls = []
        edit_habits.record_edit(self.root, 'script', '甲', '乙', program=self.program)
        result = edit_habits.summarize(self.root, program=self.program, summarizer=calls.append)
        self.assertFalse(result['ok'])
        self.assertEqual(calls, [])

    def test_summarize_saves_candidates_and_marks_records_learned(self):
        """REQ-S01-59/60：校验通过才存为待确认，记录标为已归纳，同文规则不重复。"""
        self.record_three()
        seen = []

        def model(hunks):
            seen.append(hunks)
            return '```json\n[{"rule": "对白压短，每句不超过 10 字", "evidence": 99, "before": "长句", "after": "短句"}]\n```'
        result = edit_habits.summarize(self.root, program=self.program, summarizer=model)
        self.assertTrue(result['ok'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(len(seen[0]), 3)
        rules = edit_habits.load_rules(self.program)
        self.assertEqual([(r['status'], r['evidence'], r['source_project']) for r in rules], [('candidate', 3, '项目甲')])
        self.assertEqual(edit_habits.pending(self.root, program=self.program), [])
        self.record_three()
        again = edit_habits.summarize(self.root, program=self.program, summarizer=model)
        self.assertEqual(again['count'], 0)
        self.assertEqual(len(edit_habits.load_rules(self.program)), 1)

    def test_bad_model_output_keeps_records_pending(self):
        """REQ-S01-59：返回格式不对时如实提示，记录保持未归纳。"""
        self.record_three()
        for reply in ('不是 JSON', '[{"rule": ""}]', '[{"rule": "%s"}]' % ('长' * 200)):
            with self.subTest(reply=reply):
                result = edit_habits.summarize(self.root, program=self.program, summarizer=lambda _h, r=reply: r)
                self.assertFalse(result['ok'])
                self.assertIn('记录已保留', result['message'])
                self.assertEqual(len(edit_habits.pending(self.root, program=self.program)), 3)
        self.assertEqual(edit_habits.load_rules(self.program), [])

    def test_only_adopted_rules_reach_the_writing_prompt(self):
        """REQ-S01-60/61：待确认不生效；采用后写进剧本准备任务书，停用后移除。"""
        self.record_three()
        edit_habits.summarize(self.root, program=self.program,
                              summarizer=lambda _h: '[{"rule": "对白压短", "evidence": 3}]')
        rule = edit_habits.load_rules(self.program)[0]
        self.assertEqual(edit_habits.config_fields('writing', self.program), {})
        edit_habits.decide(rule['id'], 'adopt', program=self.program)
        config = {'engine': 'codex', **edit_habits.config_fields('writing', self.program)}
        prompt = prompt_with_settings('任务', config, stage='writing')
        self.assertEqual(prompt.count('1. 对白压短'), 1)
        self.assertIn('以编剧风格为准', prompt)
        self.assertNotIn('对白压短', prompt_with_settings('任务', config, stage='storyboard'))
        self.assertEqual(edit_habits.config_fields('storyboard', self.program), {})
        edit_habits.decide(rule['id'], 'disable', program=self.program)
        self.assertEqual(edit_habits.config_fields('writing', self.program), {})

    def test_prompt_caps_rules_and_orders_by_evidence(self):
        """REQ-S01-61：按出现次数排序，最多 10 条、合计不超过 800 字。"""
        items = [{'rule': '规则%02d' % index, 'evidence': index, 'before': '', 'after': ''} for index in range(1, 15)]
        edit_habits.add_candidates('script', items, program=self.program)
        for rule in edit_habits.load_rules(self.program):
            edit_habits.decide(rule['id'], 'adopt', program=self.program)
        lines = [line for line in edit_habits.rules_prompt('script', self.program).splitlines() if line[0].isdigit()]
        self.assertEqual(len(lines), edit_habits.MAX_PROMPT_RULES)
        self.assertEqual(lines[0], '1. 规则14')
        long = [{'rule': '甲' * 70 + str(index), 'evidence': 1, 'before': '', 'after': ''} for index in range(20)]
        other = self.program / 'other'
        edit_habits.add_candidates('script', long, program=other)
        for rule in edit_habits.load_rules(other):
            edit_habits.decide(rule['id'], 'adopt', program=other)
        text = edit_habits.rules_prompt('script', other)
        self.assertLessEqual(sum(len(line.split('. ', 1)[1]) for line in text.splitlines() if line[0].isdigit()),
                             edit_habits.MAX_PROMPT_CHARS)

    def test_rewrite_and_delete(self):
        """REQ-S01-60：改写校验长度，删除后不再出现。"""
        edit_habits.add_candidates('script', [{'rule': '旧', 'evidence': 1, 'before': '', 'after': ''}],
                                   program=self.program)
        rule_id = edit_habits.load_rules(self.program)[0]['id']
        with self.assertRaises(ValueError):
            edit_habits.decide(rule_id, 'rewrite', '长' * 81, self.program)
        edit_habits.decide(rule_id, 'rewrite', '  新  规则 ', self.program)
        self.assertEqual(edit_habits.load_rules(self.program)[0]['text'], '新 规则')
        edit_habits.decide(rule_id, 'delete', program=self.program)
        self.assertEqual(edit_habits.load_rules(self.program), [])
        with self.assertRaises(ValueError):
            edit_habits.decide(rule_id, 'adopt', program=self.program)

    def test_corrupt_rules_file_does_not_block_tasks(self):
        """REQ-S01-61：规则文件损坏时不附加规则，不阻断任务。"""
        path = edit_habits.rules_path(self.program)
        path.parent.mkdir(parents=True)
        path.write_text('{坏', encoding='utf-8')
        self.assertEqual(edit_habits.config_fields('writing', self.program), {})


if __name__ == '__main__':
    unittest.main()
