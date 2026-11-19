import ast
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.architecture._scan import entity_file


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ServiceReturnContractBoundaryTests(unittest.TestCase):
    def _tree_contents(self, root):
        return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                for path in root.rglob('*')}

    def test_audited_readonly_scope_has_reasons_and_fixed_entrypoints(self):
        expected = {
            'video_source_evidence': {'submitted_sources'},
            'project_naming': {'dated_path'},
            'script_preview_service': {'should_load_async', 'read_preview', 'preview_chunks'},
            'storyboard_rows_service': {'shot_stats', 'frame_rows', 'rows_from_sources'},
            'video_task_state': {'generation_active', 'prompt_locked', 'assert_prompt_editable', 'poll_delay', 'elapsed_text', 'submission_block_reason', 'provider_failure_reason', 'shot_count_error'},
            'storyboard_adoption_contract': {'prefs', 'paths', 'resolve_source', 'adopted', 'problem_text'},
        }
        root = Path(ROOT)
        ledger = json.loads((root / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))['第一项']
        audit = ledger['readonly_scope_audit']
        self.assertEqual(set(expected), set(audit))
        self.assertTrue(set(audit) <= set(ledger['exempt_items']))
        for module, names in expected.items():
            self.assertRegex(audit[module], r'^R\d+：')
            tree = ast.parse(entity_file(module).read_text(encoding='utf-8'))
            self.assertEqual(names, {node.name for node in tree.body
                                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                                    and not node.name.startswith('_')}, module)

    def test_submission_decision_preserves_input_and_project_files(self):
        from video_task_state import submission_block_reason, provider_failure_reason
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = [{'state': 'downloaded', 'review': 'revise'}]
            before = json.dumps(state)
            files = self._tree_contents(root)
            self.assertEqual(submission_block_reason(state), '')
            self.assertIn('原因未知', provider_failure_reason(state[0]))
            self.assertEqual(json.dumps(state), before)
            self.assertEqual(self._tree_contents(root), files)

    def test_naming_and_preview_do_not_publish_project_data(self):
        from project_naming import dated_path
        from script_preview_service import read_preview, should_load_async, preview_chunks, READ_ERROR
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = dated_path(root, 'script', at=0)
            first.write_text('剧本文本', encoding='utf-8')
            bad = root / 'bad.txt'
            bad.write_bytes(b'\xff')
            before = self._tree_contents(root)
            second = dated_path(root, 'script', at=0)
            self.assertNotEqual(first, second)
            self.assertFalse(second.exists())
            self.assertEqual('剧本文本', read_preview(first))
            self.assertEqual('空', read_preview(second, '空'))
            self.assertEqual(READ_ERROR, read_preview(bad))
            self.assertTrue(should_load_async(first, threshold=1))
            self.assertEqual(['剧本', '文本'], list(preview_chunks('剧本文本', 2)))
            self.assertEqual(before, self._tree_contents(root))

    def test_adoption_queries_read_alias_without_mutating_files(self):
        from storyboard_adoption_contract import adopted, paths, prefs, resolve_source, problem_text
        from storyboard_storage import ALIAS_FILE, working_roots
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            self.assertEqual([], adopted(root))
            self.assertEqual({}, self._tree_contents(root))
            target = root / 'board.json'
            target.write_text('{}', encoding='utf-8')
            alias_dir = working_roots(root)[0]
            alias_dir.mkdir(parents=True)
            (alias_dir / ALIAS_FILE).write_text(json.dumps({'old.json': 'board.json'}), encoding='utf-8')
            settings = {'adopted_storyboards': ['old.json', 'board.json']}
            (root / 'ui_settings.json').write_text(json.dumps(settings), encoding='utf-8')
            before = self._tree_contents(root)
            self.assertEqual(settings, prefs(root))
            self.assertEqual(target, resolve_source(root, 'old.json'))
            self.assertEqual([target], adopted(root))
            with self.assertRaises(ValueError):
                paths(root, ['missing.json'])
            with self.assertRaises(ValueError):
                paths(root, ['../outside.json'])
            self.assertEqual('one；two', problem_text(ValueError('one\ntwo')))
            self.assertEqual(before, self._tree_contents(root))

    def test_every_registered_l2_module_has_a_scope_record(self):
        """未审计模块不能因旧清单遗漏而被误判为已经完成迁移。"""
        from tests.architecture._layers import LAYERS
        root = Path(ROOT)
        ledger = json.loads((root / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))['第一项']
        groups = [ledger[key] for key in ('adopters', 'exempt_items', 'scope_audit_pending')]
        names = [name for group in groups for name in group]
        self.assertEqual(len(names), len(set(names)), '范围记录不得重复或跨组重叠')
        self.assertEqual(set(names), {name for name, layer in LAYERS.items() if layer == 2})
        # 限定身份只解析自身源码，不用同 stem 门面掩盖缺失，也不误列历史逻辑名。
        locations = {name: root.joinpath(*name.split('.')) for name in names}
        missing = {name for name, path in locations.items() if not path.with_suffix('.py').is_file()
                   and not (path / '__init__.py').is_file()}
        historical = ledger['historical_name_audit_pending']
        self.assertEqual(len(historical), len(set(historical)))
        audited = ledger['historical_name_audited']
        self.assertEqual(len(audited), len(set(audited)))
        self.assertFalse(set(historical) & set(audited))
        self.assertEqual(missing, set(historical) | set(audited),
                         '旧逻辑名须保留追溯记录，不能直接算已迁移')
        audit = json.loads((root / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))['historical_name_audit']
        self.assertEqual(audit['classification'], 'unmaterialized_registry_names')
        self.assertEqual(set(audit['entrypoints']), set(audited))
        self.assertTrue(audit['evidence'])
        for name, entries in audit['entrypoints'].items():
            self.assertTrue(entries, name)
            for module, symbols in entries.items():
                self.assertNotIn(module, missing)
                source = ast.parse(entity_file(module).read_text(encoding='utf-8-sig'))
                actual = {node.name for node in source.body
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                self.assertTrue(symbols, module)
                self.assertTrue(set(symbols) <= actual, (name, module, symbols))

    def test_only_approved_l2_adopters_import_service_contract(self):
        """解冻后的每批迁移仍必须显式更新采用方棘轮。"""
        from tests.architecture._layers import LAYERS
        from tests.architecture._scan import module_name, module_scan_files
        entities = {module_name(path): path for path in module_scan_files()}
        adopters = set()
        for module, layer in LAYERS.items():
            if layer != 2:
                continue
            path = entities.get(module)
            if path is None:
                continue  # 历史兼容逻辑名仍可登记为 L2，但不是可扫描源码模块。
            tree = ast.parse(path.read_text(encoding='utf-8'))
            if any(isinstance(node, ast.ImportFrom)
                   and node.module in {'service_contract', 'contract.service_contract'}
                   for node in ast.walk(tree)):
                adopters.add(module)
        self.assertEqual(adopters, {'account_client', 'animatic_service', 'asset_batch_settings_service', 'asset_detail_service', 'asset_resume', 'asset_plan', 'storyboard_storage', 'idea_attachments', 'audio_import_service', 'delivery_import_service', 'desktop_settings_service', 'keyframe_lifecycle_service', 'projects',
                                    'cloud_video_service', 'edit_service', 'handoff_service', 'legacy_adoption_service', 'recon_service', 'recycle_recovery_service', 'script_workspace_service', 'stage_workspace_service', 'storyboard_edit_service', 'subtitle_export_service', 'video_lifecycle_service', 'video_prompt_publication', 'voice_ai', 'workflow_context', 'writing', 'writing_tools', 'writing_quality'})
        ledger = json.loads((Path(ROOT) / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))['第一项']
        self.assertEqual(adopters, set(ledger['adopters']))
        self.assertFalse(adopters & set(ledger['exempt_items']))
        self.assertEqual(ledger['exempt_count'], len(ledger['exempt_items']))

    def test_delivery_import_is_registered_l2_and_uses_result_contract(self):
        from tests.architecture._layers import LAYERS
        self.assertEqual(LAYERS['delivery_import_service'], 2)
        tree = ast.parse((Path(ROOT) / 'domain/delivery_import_service.py').read_text(encoding='utf-8'))
        imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module in {'service_contract', 'contract.service_contract'} for name in node.names}
        self.assertEqual(imports, {'SystemError', 'UserError', 'success'})

    def test_keyframe_lifecycle_is_registered_l2_and_uses_result_contract(self):
        from tests.architecture._layers import LAYERS
        self.assertEqual(LAYERS['keyframe_lifecycle_service'], 2)
        tree = ast.parse(entity_file('keyframe_lifecycle_service').read_text(encoding='utf-8'))
        imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module in {'service_contract', 'contract.service_contract'} for name in node.names}
        self.assertEqual(imports, {'SystemError', 'UserError', 'success'})
        lifecycle = {'delete_keyframe', 'restore_keyframe', 'replace_keyframe'}
        decorators = {
            node.name: {item.id for item in node.decorator_list if isinstance(item, ast.Name)}
            for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in lifecycle
        }
        self.assertEqual(set(decorators), lifecycle)
        self.assertTrue(all('_lifecycle_result' in values for values in decorators.values()))

    def test_service_result_contract_is_l0(self):
        from tests.architecture._layers import LAYERS
        self.assertEqual(LAYERS['service_contract'], 0)


class L2IdentityScopeTests(unittest.TestCase):
    """精确 L2 身份与范围登记原子闭环，沿用真实分层及服务范围消费者。"""

    selected = {'domain': 2, 'domain.hitl': 2}

    def test_exact_l2_identities_preserve_all_other_strict_refusals(self):
        from tests.architecture import test_layers as layers
        paths = layers.module_scan_files(qualified=True)
        after = layers._module_classifications(paths)
        legacy = {name: layer for name, layer in layers.LAYERS.items() if name not in self.selected}
        with patch.dict(layers.LAYERS, legacy, clear=True):
            before = layers._module_classifications(paths)
        self.assertEqual({name for name in before if before[name] != after[name]}, set(self.selected))
        for name, layer in self.selected.items():
            with self.subTest(name=name):
                self.assertEqual(before[name]['status'], 'unregistered')
                self.assertEqual((after[name]['status'], after[name]['registration'], after[name]['layer']),
                                 ('registered', name, layer))
        remaining = {name: row['status'] for name, row in after.items()
                     if row['status'] not in ('registered', 'legacy-unique', 'tool')}
        guard = layers.LayerDirectionTests('test_higher_layers_may_depend_only_on_same_or_lower_layers')
        if remaining:
            with self.assertRaises(AssertionError) as refusal:
                guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
            self.assertEqual(str(refusal.exception),
                             f'Unclassified local modules: {dict(sorted(remaining.items()))}')
        selected_paths = tuple(path for path in paths
                               if layers.module_name(path, qualified=True) in self.selected)
        with patch.object(layers, 'module_scan_files', return_value=selected_paths):
            guard.test_higher_layers_may_depend_only_on_same_or_lower_layers(qualified=True)
        ServiceReturnContractBoundaryTests().test_every_registered_l2_module_has_a_scope_record()

    def test_removing_l2_scope_record_trips_actual_scope_guard(self):
        data = json.loads((Path(ROOT) / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))
        pending = data['第一项']['scope_audit_pending']
        self.assertTrue(set(self.selected) <= set(pending))
        guard = ServiceReturnContractBoundaryTests()
        for name in self.selected:
            with self.subTest(name=name):
                pending.remove(name)
                try:
                    with patch(__name__ + '.json.loads', return_value=data):
                        with self.assertRaisesRegex(AssertionError, name.replace('.', r'\.')):
                            guard.test_every_registered_l2_module_has_a_scope_record()
                finally:
                    pending.append(name)

    def test_missing_exact_source_is_not_hidden_by_a_same_stem_file(self):
        original = Path.is_file
        for name, source in (('domain', 'domain/__init__.py'), ('domain.hitl', 'domain/hitl.py')):
            missing = Path(ROOT) / source
            same_stem = Path(ROOT) / 'hitl.py'

            def is_file(path):
                return False if path == missing else path == same_stem or original(path)

            with self.subTest(name=name), patch.object(Path, 'is_file', is_file):
                # 实际缺失的包初始化仍报错；限定子模块不回退至 hitl.py。
                with self.assertRaisesRegex(AssertionError, name.replace('.', r'\.')):
                    ServiceReturnContractBoundaryTests().test_every_registered_l2_module_has_a_scope_record()

    def test_exact_l2_entries_preserve_legacy_dependency_semantics(self):
        from tests.architecture import test_layers as layers
        current = (layers._upward_pairs(), layers._dynamic_upward_pairs())
        legacy = {name: layer for name, layer in layers.LAYERS.items() if name not in self.selected}
        with patch.dict(layers.LAYERS, legacy, clear=True):
            self.assertEqual(current, (layers._upward_pairs(), layers._dynamic_upward_pairs()))
