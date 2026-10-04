import ast
import json
import os
import unittest
from pathlib import Path

from tests.architecture._layers import LAYERS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tree(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as handle:
        return ast.parse(handle.read())


class ProjectContextBoundaryTests(unittest.TestCase):
    def test_context_contract_is_l0_and_constructed_only_by_l3(self):
        self.assertEqual(LAYERS['project_context'], 0)
        delivery = _tree('delivery_import_service.py')
        calls = [node for node in ast.walk(delivery) if isinstance(node, ast.Call)
                 and getattr(node.func, 'id', '') == 'ProjectContext']
        self.assertEqual(calls, [], 'L2 只可消费 ProjectContext，不得自行构造')
        self.assertEqual(LAYERS['project_context_factory'], 3)
        orchestrator = _tree('project_context_factory.py')
        constructors = [node for node in ast.walk(orchestrator) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'snapshot'
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'ProjectContext']
        self.assertEqual(len(constructors), 1, '项目上下文必须由 L3 统一构造')

    def test_context_factory_is_shared_without_orchestrator_back_dependency(self):
        from project_context_factory import project_context
        from stage_execution_service import project_context as compatibility_entry
        import file_cache
        self.assertIs(project_context, compatibility_entry)
        settings = {'model': 'fixture'}
        context = project_context(Path('fixture'), settings_snapshot=settings)
        settings['model'] = 'changed'
        self.assertEqual(context.settings_snapshot['model'], 'fixture')
        self.assertIs(context.cache, file_cache)
        self.assertEqual(context.stage_resolver('script'), Path('fixture') / '01剧本准备')
        with self.assertRaises(TypeError):
            context.settings_snapshot['model'] = 'changed'
        for name in ('stage_parallel.py', 'storyboard_selection.py', 'writing_api.py', 'white_model.py', 'workflow_tasks.py'):
            source = Path(ROOT, name).read_text(encoding='utf-8')
            self.assertNotIn('from stage_execution_service import', source, name)

    def test_l2_uses_injected_stage_resolver_without_project_path_join(self):
        delivery = _tree('delivery_import_service.py')
        source = Path(ROOT, 'delivery_import_service.py').read_text(encoding='utf-8')
        self.assertIn("context.stage_resolver('delivery')", source)
        self.assertNotIn('project_stages', source)
        self.assertNotIn('os.path.join', source)

    def test_previs_page_and_finalization_inject_context_at_l3(self):
        page = _tree('local_previs.py')
        show = next(node for node in page.body if isinstance(node, ast.FunctionDef) and node.name == 'show')
        calls = [node for node in ast.walk(show) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr == 'shot_directory'
                             for node in calls), '页面不得把裸路径直接传给 L2 白模目录服务')
        self.assertEqual(sum(isinstance(node.func, ast.Name) and node.func.id == 'white_model_shot_directory'
                             for node in calls), 4)
        finalize = _tree('storyboard_final.py')
        sync = next(node for node in ast.walk(finalize) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == '_sync_plan')
        context = next(keyword.value for keyword in sync.keywords if keyword.arg == 'context')
        self.assertIsInstance(context, ast.Call)
        self.assertEqual(context.func.id, 'project_context')

    def test_asset_domain_services_consume_but_do_not_construct_context(self):
        for name in ('asset_context.py', 'asset_batch_lifecycle.py',
                     'asset_batch_state_service.py', 'asset_batch_service.py',
                     'asset_detail_service.py', 'asset_generated_import_service.py'):
            tree = _tree(name)
            constructors = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                            and getattr(node.func, 'id', '') == 'ProjectContext']
            self.assertEqual(constructors, [], name + ' 不得自行构造 ProjectContext')
            source = Path(ROOT, name).read_text(encoding='utf-8')
            self.assertIn('ProjectContext', source)

    def test_confirmation_service_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'confirm_gates.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn("context.stage_resolver('continuity')", source)
        tree = _tree('confirm_gates.py')
        constructors = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and getattr(node.func, 'id', '') == 'ProjectContext']
        self.assertEqual(constructors, [])
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def run_stage_confirmation_gate(', orchestrator)
        self.assertIn('context=project_context(project)', orchestrator)

    def test_local_video_settings_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'local_video_settings_service.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        tree = _tree('local_video_settings_service.py')
        constructors = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and getattr(node.func, 'id', '') == 'ProjectContext']
        self.assertEqual(constructors, [])
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('save_local_video_settings(project_context(project)', orchestrator)

    def test_idea_attachments_consume_context_and_l3_injects_it(self):
        source = Path(ROOT, 'idea_attachments.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn("context.stage_resolver('script')", source)
        tree = _tree('idea_attachments.py')
        constructors = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and getattr(node.func, 'id', '') == 'ProjectContext']
        self.assertEqual(constructors, [])
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('store(project_context(project)', orchestrator)
        self.assertIn('def stage_idea_attachment_reference(', orchestrator)

    def test_pet_performance_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'pet_performance_service.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('context.root.joinpath', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn("poll_startup_check(session, project_context(session['project'])", orchestrator)

    def test_pet_test_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'pet_test_service.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('context.root.joinpath', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('poll_incremental(session, project_context(project)', orchestrator)

    def test_cloud_video_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'cloud_video_service.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn("context.root/'cloud_video'", source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('session_folder(project_context(project)', orchestrator)
        self.assertIn('saved_provider_key(project_context(project)', orchestrator)

    def test_idea_chat_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'idea_chat.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('def _context(value)', source)
        self.assertIn('writing(_context(context).root)', source)
        self.assertNotIn('ProjectContext(', source)
        desktop = Path(ROOT, 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('def idea_chat_context(self)', desktop)
        self.assertIn('idea_chat.load(self.idea_chat_context()', desktop)

    def test_keyframe_batch_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'keyframe_batch.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('isinstance(context, ProjectContext)', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def keyframe_image_prompt(', orchestrator)
        self.assertIn('image_prompt(source, project_context(project)', orchestrator)

    def test_previs_routing_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'previs_routing.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('def _context(value)', source)
        self.assertIn('isinstance(value, ProjectContext)', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('set_override(project_context(project)', orchestrator)
        self.assertIn('dispatch(project_context(project)', orchestrator)
        self.assertIn('def previs_entries(', orchestrator)

    def test_storyboard_catalog_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'storyboard_catalog_service.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('def _context(value)', source)
        self.assertIn('isinstance(value, ProjectContext)', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def storyboard_catalog(', orchestrator)
        self.assertIn('catalog(project_context(project)', orchestrator)

    def test_tts_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'tts_api.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('def _context(value)', source)
        self.assertIn('audio(_context(context).root)', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def reusable_tts_full_track(', orchestrator)
        self.assertIn('publish_full_track(project_context(project)', orchestrator)
        self.assertIn('reusable_full_track(project_context(project)', orchestrator)

    def test_storyboard_lifecycle_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'storyboard_lifecycle.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('def _context(value)', source)
        self.assertIn('_context(context).root', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def storyboard_working_source(', orchestrator)
        self.assertIn('def retire_storyboard(', orchestrator)
        self.assertIn('def refresh_storyboard_studios(', orchestrator)

    def test_white_model_service_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'white_model_service.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn('def _context(value)', source)
        self.assertIn('_context(context).root', source)
        self.assertNotIn('ProjectContext(', source)
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def white_model_shot_directory(', orchestrator)
        self.assertIn('shot_directory(project_context(project)', orchestrator)

    def test_storyboard_path_only_services_are_explicit_context_exemptions(self):
        for name in ('keyframe_lifecycle_service.py', 'previs_progress_service.py', 'storyboard_edit_service.py',
                     'storyboard_source_service.py'):
            source = Path(ROOT, name).read_text(encoding='utf-8')
            self.assertNotIn('ProjectContext', source)
        ledger = json.loads(Path(ROOT, '维护记录', '架构统一基数.json').read_text(encoding='utf-8'))
        reasons = ledger['第二项']['exempt_reasons']
        self.assertIn('storyboard_edit_service', reasons)
        self.assertIn('storyboard_source_service', reasons)
        self.assertIn('keyframe_lifecycle_service', reasons)
        self.assertIn('previs_progress_service', reasons)

    def test_second_roadmap_scope_is_a_complete_migration_ratchet(self):
        ledger = json.loads(Path(ROOT, '维护记录', '架构统一基数.json').read_text(encoding='utf-8'))
        item = ledger['第二项']
        adopters = set(item['adopters'])
        pending = set(item['pending'])
        exempt = set(item['exempt_items'])
        historical = set(item['historical_name_audit_pending'])
        self.assertFalse((adopters & pending) | (adopters & exempt) | (adopters & historical))
        self.assertFalse((pending & exempt) | (pending & historical) | (exempt & historical))
        self.assertEqual(len(adopters | pending | exempt | historical), 37)
        self.assertEqual(item['exempt_count'], len(exempt))
        reasons = item['exempt_reasons']
        self.assertEqual(set(reasons), exempt)
        for name, reason in reasons.items():
            self.assertRegex(reason, r'^R\d+：')
            source = Path(ROOT, name + '.py').read_text(encoding='utf-8')
            self.assertNotIn('ProjectContext', source,
                             name + ' 是经审计的纯计算服务，不应伪造上下文消费')
        missing = {name for name in historical
                   if not (Path(ROOT, name + '.py').is_file()
                           or Path(ROOT, name, '__init__.py').is_file())}
        self.assertEqual(missing, historical,
                         '历史名称必须单独追溯，不得伪装成已迁移或现行待办')
