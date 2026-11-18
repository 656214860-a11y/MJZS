"""R3274: synthetic request-freeze budgets; no production skills/model pool."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workflow_settings as settings
from orchestrator.skill_inline import _skill_inline_budget
from contract.workflow_context_budget import estimate_tokens, skill_inline_token_budget


class SkillContextBudgetPrestageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.roots = patch.object(settings.skill_registry, 'skill_roots', return_value=[self.root])
        self.roots.start()
        self.addCleanup(self.roots.stop)

    def skill(self, name, body):
        path = self.root / name / 'SKILL.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'---\nname: {name}\n---\n{body}', encoding='utf-8')
        return path

    def config(self, *paths, model='mystery-x', engine='qwen'):
        return dict(stage='writing', engine=engine, model=model,
                    invocation_mode='api', skills=list(map(str, paths)))

    def freeze(self, config, record):
        with patch('infra.model_pool.pool', side_effect=AssertionError('snapshot must not query pool')):
            return settings.freeze_skills(config, model_snapshot=record)

    def test_unknown_api_rejects_and_explicit_snapshot_keeps_budget(self):
        with patch('infra.model_pool.pool', side_effect=AssertionError('provided record')):
            with self.assertRaisesRegex(ValueError, 'context_window_unknown.*context_length'):
                _skill_inline_budget({'model': 'deepseek-v4.1-flash-1017', 'engine': 'api'}, record={})
            explicit = _skill_inline_budget({'model': 'deepseek-v4.1-flash-1017'}, record={'context_length': 32000})
        self.assertEqual(explicit['remaining'], skill_inline_token_budget(32000))

    def test_legacy_preset_snapshot_is_not_a_confirmed_api_window(self):
        config = {'model': 'deepseek-v4.1-flash-1017', 'engine': 'api',
                  'skill_budget': {'model': 'deepseek-v4.1-flash-1017',
                                   'context_length': 128000, 'source': 'preset'}}
        with patch('infra.model_pool.pool', side_effect=AssertionError('frozen snapshot')):
            with self.assertRaisesRegex(ValueError, 'context_window_unknown'):
                _skill_inline_budget(config)

    def test_default_pool_root_is_owned_by_model_pool(self):
        with patch('infra.model_pool.pool', return_value={'mystery-x': {'context_length': 32000}}) as pool:
            self.assertGreater(_skill_inline_budget({'model': 'mystery-x'})['remaining'], 0)
        self.assertEqual(pool.call_args.kwargs, {})

    def test_unknown_api_refuses_with_model_name(self):
        path = self.skill('unknown', '完整正文')
        with self.assertRaisesRegex(ValueError, '未填写上下文窗口.*mystery-x'):
            self.freeze(self.config(path), {})

    def test_cli_without_window_keeps_freeze(self):
        path = self.skill('cli', '完整正文')
        cfg = self.config(path, engine='codex')
        cfg.pop('invocation_mode')
        frozen = self.freeze(cfg, {})
        self.assertIn('完整正文', frozen['frozen_skill_prompt'])

    def test_all_bodies_before_references_and_shared_reference_once(self):
        one = self.skill('one', '甲正文' * 180 + '\n[共享](../shared.md)')
        two = self.skill('two', '乙正文' * 180 + '\n[共享](../shared.md)')
        (self.root / 'shared.md').write_text('大引用' * 1600, encoding='utf-8')
        cfg = self.config(one, two, one)
        frozen = self.freeze(cfg, {'context_length': 14000})
        text = frozen['frozen_skill_prompt']
        self.assertIn('甲正文' * 180, text)
        self.assertIn('乙正文' * 180, text)
        self.assertEqual(len(frozen['skill_injection']['loaded']), 2)
        self.assertEqual(sum(r['status'] == 'skipped' for r in frozen['skill_injection']['references']), 1)
        self.assertEqual(text.count('API 无法读取此本地文件'), 1)
        self.assertLessEqual(estimate_tokens(text), skill_inline_token_budget(14000))
        self.assertIn('本地路径', text)
        self.assertNotIn('请按路径读取', text)
        self.assertTrue(frozen['skill_injection']['degraded'])

    def test_distinct_sections_in_shared_file_both_survive(self):
        one = self.skill('one', '甲正文 [A](../shared.md#a)')
        two = self.skill('two', '乙正文 [B](../shared.md#b)')
        (self.root / 'shared.md').write_text('# A\n唯一甲节\n# B\n唯一乙节\n', encoding='utf-8')
        frozen = self.freeze(self.config(one, two), {'context_length': 128000})
        self.assertIn('唯一甲节', frozen['frozen_skill_prompt'])
        self.assertIn('唯一乙节', frozen['frozen_skill_prompt'])

    def test_skipped_large_section_does_not_hide_small_section(self):
        one = self.skill('one', '甲正文 [A](../shared.md#a)')
        two = self.skill('two', '乙正文 [B](../shared.md#b)')
        (self.root / 'shared.md').write_text('# A\n' + '巨大甲节' * 2000 + '\n# B\n唯一小节\n', encoding='utf-8')
        frozen = self.freeze(self.config(one, two), {'context_length': 14000})
        self.assertIn('唯一小节', frozen['frozen_skill_prompt'])
        self.assertNotIn('巨大甲节' * 2000, frozen['frozen_skill_prompt'])
        self.assertEqual(len(frozen['skill_injection']['skipped']), 1)

    def test_skipped_parent_does_not_reserve_or_read_descendants(self):
        path = self.skill('frontier', '正文' * 14000 + '\n[父](parent.md)')
        parent = path.parent / 'parent.md'
        parent.write_text('父引用' * 18000 + '\n' + '\n'.join(
            f'[子{i}]({"child" * 12}{i}.md)' for i in range(600)), encoding='utf-8')
        for i in range(600):
            (path.parent / ('child' * 12 + str(i) + '.md')).write_text('子正文', encoding='utf-8')
        # 父节点跳过后后代不可达，不应读取或为它们预留提示。
        frozen = self.freeze(self.config(path), {'context_length': 128000})
        self.assertIn('正文' * 14000, frozen['frozen_skill_prompt'])
        self.assertEqual(len(frozen['skill_injection']['skipped']), 1)
        self.assertLessEqual(estimate_tokens(frozen['frozen_skill_prompt']), skill_inline_token_budget(128000))

    def test_quality_marker_in_unsent_section_does_not_activate_rules(self):
        path = self.skill('quality', '正文 [安全](ref.md#safe)')
        (path.parent / 'ref.md').write_text('# Safe\n安全正文\n# Other\nscreenplay-gate-engine.md emotion-beat-curve.md dialogue-doctor-7d.md dialogue-speed-check.md\n', encoding='utf-8')
        frozen = self.freeze(self.config(path), {'context_length': 128000})
        self.assertNotIn('【四项辅助质检交付】', frozen['frozen_skill_prompt'])

    def test_plain_body_near_budget_does_not_reserve_unused_quality(self):
        path = self.skill('near-limit', '正文' * 1000)
        frozen = self.freeze(self.config(path), {'context_length': 14000})
        self.assertNotIn('【四项辅助质检交付】', frozen['frozen_skill_prompt'])
        self.assertLessEqual(estimate_tokens(frozen['frozen_skill_prompt']), skill_inline_token_budget(14000))

    def test_huge_body_refuses_with_real_breakdown(self):
        path = self.skill('huge', '巨大正文' * 5000)
        with self.assertRaisesRegex(ValueError, '正文合计.*huge.*包装') as raised:
            self.freeze(self.config(path), {'context_length': 9000})
        message = str(raised.exception)
        self.assertLessEqual(len(message.splitlines()), 3)
        self.assertIn('预算', message)
        self.assertIn('已阻止发送', message)
        detail = raised.exception.detail
        self.assertEqual(detail['body_tokens'], estimate_tokens('巨大正文' * 5000))
        self.assertEqual(detail['fixed_tokens'], detail['body_tokens'] + detail['wrapper_tokens'])
        self.assertGreater(detail['wrapper_tokens'], 0)
        self.assertEqual(detail['hint_tokens'], 0)
        self.assertEqual(detail['budget_tokens'], skill_inline_token_budget(9000))

    def test_wrappers_locks_and_long_skipped_hints_stay_within_budget(self):
        path = self.skill('wrapper', '正文\n' + '\n'.join(f'[引用{i}]({"x" * 100}{i}.md)' for i in range(12)))
        for i in range(12):
            (path.parent / ('x' * 100 + str(i) + '.md')).write_text('引用' * 2000, encoding='utf-8')
        cfg = self.config(path)
        cfg['workflow_lock'] = {'genre': '悬疑' * 40}
        try:
            frozen = self.freeze(cfg, {'context_length': 9500})
        except ValueError as exc:
            self.assertIn('包装', str(exc))
        else:
            self.assertLessEqual(estimate_tokens(frozen['frozen_skill_prompt']), skill_inline_token_budget(9500))

    def test_snapshot_read_once_idempotent_and_config_unchanged(self):
        one = self.skill('one', '[共享](../shared.md)\n甲正文')
        two = self.skill('two', '[共享](../shared.md)\n乙正文')
        shared = self.root / 'shared.md'
        shared.write_text('共享正文', encoding='utf-8')
        cfg = self.config(one, two)
        original = copy.deepcopy(cfg)
        counts = {}
        read = Path.read_text
        def once(path, *args, **kwargs):
            counts[path] = counts.get(path, 0) + 1
            return read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', once):
            frozen = self.freeze(cfg, {'context_length': 128000, 'api_key': 'DO-NOT-FREEZE'})
            again = settings.freeze_skills(frozen)
        self.assertEqual(cfg, original)
        self.assertEqual(again, frozen)
        self.assertEqual(counts, {one: 1, two: 1, shared: 1})
        self.assertEqual(frozen['frozen_skill_prompt'].count('共享正文'), 1)
        self.assertNotIn('DO-NOT-FREEZE', repr(frozen))

    def test_resolve_for_send_passes_captured_record(self):
        path = self.skill('snapshot', '完整正文')
        cfg = self.config(path)
        with patch('infra.model_pool.pool', side_effect=AssertionError('pool queried')):
            frozen = settings.resolve_for_send(self.root, 'writing', config=cfg,
                                               direct_api=True, model_snapshot={'context_length': 128000})
        self.assertIn('完整正文', frozen['frozen_skill_prompt'])

    def test_current_and_resolve_reuse_captured_record_without_pool_lookup(self):
        path = self.skill('current', '当前快照正文')
        from contextlib import ExitStack
        import orchestrator.stage_config as stage_config
        cfg = {'engine': 'qwen', 'profiles': {'qwen': {'program': '', 'model': 'mystery-x',
                                                     'skills': [str(path)], 'instructions': ''}}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(settings, 'load', return_value=cfg))
            stack.enter_context(patch.object(settings, 'validate_selected_skills'))
            stack.enter_context(patch.object(settings, 'stage_model', return_value=('mystery-x', '')))
            stack.enter_context(patch.object(stage_config, 'get', return_value={'skills': []}))
            stack.enter_context(patch.object(settings, '_local_engine_for_selected_model', return_value=('', '')))
            stack.enter_context(patch.object(stage_config, 'workflow_lock', return_value={}))
            stack.enter_context(patch.object(stage_config, 'project_created_at', return_value=''))
            stack.enter_context(patch.object(stage_config, 'writer_style', return_value=''))
            stack.enter_context(patch.object(settings.edit_habits, 'config_fields', return_value={}))
            stack.enter_context(patch.object(settings.skill_registry, 'default_registry'))
            pool = stack.enter_context(patch('infra.model_pool.pool', side_effect=AssertionError('pool queried')))
            current = settings.current(self.root, 'writing', model_snapshot=('mystery-x', {'context_length': 128000}))
            frozen = settings.resolve_for_send(self.root, 'writing', config=current)
        pool.assert_not_called()
        self.assertEqual(frozen['skill_budget']['context_length'], 128000)
        self.assertIn('当前快照正文', frozen['frozen_skill_prompt'])

    def test_shared_resource_hint_is_sent_once_and_closure_preserved(self):
        """REQ-S01-31：多技能共享资源不重复挤占已预留预算。"""
        resource = self.root / 'LICENSE'
        one = self.skill('resource-a', '第一份正文 [许可](../LICENSE)')
        two = self.skill('resource-b', '第二份正文 [许可](../LICENSE)')
        frozen = self.freeze(self.config(one, two), {'context_length': 128000})
        text = frozen['frozen_skill_prompt']
        self.assertEqual(text.count(f'本请求不发送该资源，本地路径：{resource}'), 1)
        rows = frozen['skill_injection']['references']
        self.assertEqual(sum(row['status'] == 'resource' for row in rows), 2)
        self.assertLessEqual(estimate_tokens(text), frozen['skill_injection']['inline_budget'])

    def test_already_sent_resource_does_not_reserve_again_in_later_child(self):
        """REQ-S01-31：后出现的父引用不为已发送资源制造幽灵预留。"""
        from orchestrator.skill_inline import _append_hint, _charge_reference, _ReferenceContext
        resource = self.root / 'LICENSE'
        source = self.root / 'child.md'
        hint = f'\n\n<!-- 本请求不发送该资源，本地路径：{resource} -->'
        body = '[许可](LICENSE)'
        block = f'\n\n## 引用: child.md\n{body}'
        budget = {'remaining': estimate_tokens(block),
                  'pending': {('resource', str(resource)): estimate_tokens(hint)}}
        blocks = []
        _append_hint(blocks, resource, hint, budget)
        context = _ReferenceContext([self.root], {}, set(), set(), lambda path: 'unused')
        self.assertTrue(_charge_reference(budget, source, '', block, body, context))
        self.assertEqual(budget['remaining'], 0)
        self.assertEqual(budget['pending'], {})

    def test_one_skill_unknown_window_is_valueerror_not_typeerror(self):
        path = self.skill('one', '正文 [引用](ref.md)')
        (path.parent / 'ref.md').write_text('引用正文', encoding='utf-8')
        with patch('infra.model_pool.pool', return_value={}):
            with self.assertRaisesRegex(ValueError, '未填写上下文窗口'):
                settings._one_skill_prompt(self.config(path), path, inline=True)


if __name__ == '__main__':
    unittest.main()
