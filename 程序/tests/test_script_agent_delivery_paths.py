"""Agent 正式交付与下载保存共用路径，API 不注入本地交付段。"""
from tests.architecture._scan import parse_desktop
import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import idea_chat
from orchestrator import workflow_tasks
from project_context_factory import project_context
from stage_execution_service import publish_idea_creative


class AgentDeliveryPathsTests(unittest.TestCase):
    def test_agent_paths_equal_published_paths_for_every_kind(self):
        with tempfile.TemporaryDirectory() as td, patch(
                'workflow_settings.model_name', return_value='测试模型'), patch(
                'domain.idea_document_paths.storage_identity', return_value=('Provider', 'Model')):
            root = Path(td)
            at = 1791331200
            prompt = workflow_tasks.script_prompt(root, None, 'writing', creative_text='素材',
                                                  agent_delivery=True, delivery_at=at)
            followup = workflow_tasks.script_followup(None, 'writing', project=root,
                creative_text='素材', agent_delivery=True, delivery_at=at)
            self.assertIn('必须直接写入以下本机绝对路径（文件名不得自拟或改写）', prompt)
            self.assertIn('仅当产出该类内容时使用', prompt)
            for body in ('项目设定：角色阿明。', '故事大纲：阿明寻找真相。',
                         '第1集\n场景：夜 外街道\n阿明：我要找到真相。\n动作：阿明推开门。'):
                saved = idea_chat.save_reply(project_context(root), body, at=at,
                    provider='Provider', model='Model', publish=publish_idea_creative)
                relative = saved.relative_to(root).as_posix()
                self.assertIn(relative, prompt)
                self.assertIn(relative, followup)
                # 契约变更：01剧本准备已扁平化，直接落在 01剧本准备/<分类>/ 下，不再嵌套供应商/模型/创意_日期。
                self.assertEqual(saved.parents[1].name, '01剧本准备')
                self.assertNotIn('创意_', relative)
                self.assertNotIn('/Model/', relative)
            self.assertIn('项目大纲/', prompt)

    def test_api_default_does_not_emit_delivery_paths_or_compute_them(self):
        with tempfile.TemporaryDirectory() as td, patch(
                'domain.idea_document_paths.reply_path_parts', side_effect=AssertionError('API must not compute paths')):
            for text in (workflow_tasks.script_prompt(td, None, 'writing', creative_text='素材'),
                         workflow_tasks.script_followup(None, 'writing', project=td, creative_text='素材')):
                self.assertNotIn('以下本机绝对路径', text)
                self.assertNotIn('创意_', text)
                self.assertIn('script_raw.md', text)

    def test_path_helper_is_pure_and_classification_literals_not_reinvented(self):
        with tempfile.TemporaryDirectory() as td:
            before = tuple(Path(td).iterdir())
            parts = idea_chat.reply_path_parts(project_context(td), at=1791331200,
                                               provider='Provider', model='Model')
            self.assertEqual(parts[-2], '项目剧本')
            self.assertEqual(tuple(Path(td).iterdir()), before)
        tree = ast.parse(Path(workflow_tasks.__file__).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotEqual(node.value, '创意_')
                self.assertNotIn(node.value, ('项目设定', '项目大纲', '项目剧本'))

    def test_agent_completion_warns_only_for_internal_draft(self):
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ('script_raw.md', '正式剧本.md'):
                with self.subTest(name=name), patch(
                        'workflow_engines.cancel_stage_slot_requests'), patch(
                        'workflow_engines.forget_process'), patch(
                        'contract.script_contract.resolve_script_source', return_value=root / name):
                    app = SimpleNamespace(root=root, status=Mock(),
                        pet=SimpleNamespace(auto=SimpleNamespace(active='script'), report_done=Mock()),
                        flow_processes={(str(root), 'writing', 'codex', 'test'): Mock(poll=lambda: 0)})
                    Desktop.poll_flow_processes(app)
                    message = app.status.set.call_args.args[0]
                    self.assertEqual('Agent 未产出规范正式稿' in message, name == 'script_raw.md')
                    app.pet.report_done.assert_called_once_with('script', message)

    def test_desktop_agent_entry_explicitly_enables_delivery_paths(self):
        import desktop
        tree = parse_desktop()  # R1505：start_script_workflow 已迁到 ScriptPagesMixin
        entry = next(node for node in ast.walk(tree)
                     if isinstance(node, ast.FunctionDef) and node.name == 'start_script_workflow')
        calls = [node for node in ast.walk(entry) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id in ('script_prompt', 'script_followup')]
        self.assertEqual(len(calls), 2)
        for call in calls:
            options = {item.arg: item.value for item in call.keywords}
            self.assertIs(options['agent_delivery'].value, True)
            self.assertEqual(options['delivery_at'].id, 'delivery_at')


if __name__ == '__main__':
    unittest.main()
