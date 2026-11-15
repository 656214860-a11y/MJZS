"""语义提取是独立 Agent 请求，结果校验后回填，再进入原发送门禁。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import idea_chat
import idea_semantic_brief_service
from stage_execution_service import project_context
from tests.test_idea_chat import _Harness
from tests.ui_edges_support import make_minimal_project


SOURCE = '修表师林青追查父亲失踪之谜，与船长阿禾一起冒险。计划12集，每集120秒，9:16，MiniMax H3，交付 markdown 文档。'
VALUES = {'故事梗概': '修表师追查父亲失踪之谜', '故事题材': '冒险悬疑',
          '故事角色': '林青：修表师；阿禾：船长', '故事集数': '12集',
          '单集时间': '120秒', '故事画幅': '9:16', '视频模型': 'MiniMax H3',
          '交付形态': 'markdown 文档'}


def response(request, values=None):
    return {'request_id': request['request_id'], 'fields': {
        label: {'value': value, 'evidence': SOURCE} for label, value in (values or VALUES).items()}}


class SemanticBriefTests(unittest.TestCase):
    def test_cli_intake_and_script_reuse_the_same_process_slot(self):
        import hashlib
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            config = {'engine': 'codex', 'program': 'codex', 'model': ''}
            key = (str(root), 'writing', 'codex', hashlib.sha256(
                json.dumps(config, sort_keys=True).encode()).hexdigest())
            process = Mock(); process.poll.return_value = None
            desktop = SimpleNamespace(root=root, worker=False, status=Mock(), notifier=Mock(),
                projects=SimpleNamespace(info={'projects': []}), flow_processes={key: process},
                async_=lambda fn, done: done(fn()))
            with patch('codex_skill_sync.sync_codex_skills',
                       return_value={'errors': [], 'conflicts': []}), \
                    patch('agent_dispatch.claim', return_value={'duplicate': False}), \
                    patch('agent_dispatch.finish'), patch('agent_dispatch.outcome'), \
                    patch('workflow_engines.submit_existing', return_value={
                        'ok': True, 'reason': '已发送', 'send_dispatched': True}) as submit, \
                    patch('workflow_engines.request_stage_process_slot') as reserve:
                Desktop.open_flow_agent(desktop, 'writing', '提取', '只提取', _config=config, intake_only=True)
                submit.assert_called_once_with(process, '只提取', title=root.name + ' 提取')
                reserve.assert_not_called()

    def test_api_extraction_uses_configured_model_without_script_publication(self):
        import writing_api
        request = {'request_id': 'test', 'source': SOURCE, 'prompt': '只做提取'}
        with tempfile.TemporaryDirectory() as td, \
                patch('writing_api.selected_model', return_value=('chosen', {})), \
                patch('writing_api.PoolAdapter') as adapter, \
                patch('writing_api._auto_save_script_raw') as publish:
            adapter.return_value.chat.return_value = {'ok': True, 'text': json.dumps(response(request))}
            self.assertEqual(writing_api.extract_idea_brief(Path(td), request), VALUES)
            self.assertEqual(adapter.return_value.chat.call_args.kwargs['model'], 'chosen')
            publish.assert_not_called()

    def test_intake_dispatch_does_not_inject_script_skill_or_history(self):
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            built = []
            desktop = SimpleNamespace(root=root, worker=False, projects=SimpleNamespace(info={'projects': []}),
                                      async_=lambda fn, done: built.append(fn()))
            config = {'engine': 'codex', 'program': 'codex', 'model': ''}
            with patch('codex_skill_sync.sync_codex_skills',
                       return_value={'errors': [], 'conflicts': []}), \
                    patch('agent_dispatch.claim', return_value={'duplicate': False}), \
                    patch('agent_dispatch.finish'), \
                    patch('workflow_context.snapshot', side_effect=AssertionError('no history')), \
                    patch('workflow_engines.prompt_with_settings', side_effect=AssertionError('no script skill')):
                Desktop.open_flow_agent(desktop, 'writing', '提取', '只提取', _config=config, intake_only=True)
            self.assertEqual(built[0]['prompt'], '只提取')

    def test_unlabelled_prose_is_extracted_by_agent_not_keyword_parser(self):
        self.assertEqual(idea_chat.extract_brief_creation(SOURCE), {})
        values = idea_semantic_brief_service.semantic_brief_values(response({'request_id': 'test'}),
                                                                  'test', SOURCE)
        self.assertEqual(values, VALUES)

    def test_specific_requirements_need_verbatim_evidence(self):
        data = response({'request_id': 'test'})
        data['fields']['故事集数'] = {'value': '100集', 'evidence': SOURCE}
        data['fields']['交付形态']['evidence'] = ''
        values = idea_semantic_brief_service.semantic_brief_values(data, 'test', SOURCE)
        self.assertNotIn('故事集数', values)
        self.assertNotIn('交付形态', values)
        self.assertEqual(values['故事题材'], '冒险悬疑')

    def test_stale_or_malformed_result_is_rejected(self):
        for data in ({}, {'request_id': 'old', 'fields': {}},
                     {'request_id': 'test', 'fields': []}):
            with self.assertRaises(ValueError):
                idea_semantic_brief_service.semantic_brief_values(data, 'test', SOURCE)

    def test_inferred_value_cannot_inject_another_required_field(self):
        data = response({'request_id': 'test'})
        data['fields']['故事梗概']['value'] = '追查失踪之谜\n交付形态：臆造格式'
        del data['fields']['交付形态']
        values = idea_semantic_brief_service.semantic_brief_values(data, 'test', SOURCE)
        draft = '\n'.join(label + '：' + value for label, value in values.items())
        self.assertEqual(idea_chat.inline_required_missing(None, draft), ('交付形态',))

    def test_changed_attachment_rejects_result(self):
        from stage_execution_service import read_idea_semantic_brief
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            source = Path(td) / '素材.txt'
            source.write_text(SOURCE, encoding='utf-8')
            request = idea_semantic_brief_service.semantic_brief_request(
                project_context(root), '', {'paths': (source,), 'brief_texts': (SOURCE,)}, local_mode=False)
            request['path'].parent.mkdir(parents=True, exist_ok=True)
            request['path'].write_text(json.dumps(response(request)), encoding='utf-8')
            source.write_text(SOURCE + '已改动', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '已变化'):
                read_idea_semantic_brief(request)

    def test_prompt_only_authorizes_extraction_and_relative_result(self):
        with tempfile.TemporaryDirectory() as td:
            context = project_context(make_minimal_project(td))
            request = idea_semantic_brief_service.semantic_brief_request(
                context, '补充要求',
                {'paths': (), 'brief_texts': (SOURCE,), 'context': '【附档：输入/材料.md】'})
            self.assertIn('不生成剧本', request['prompt'])
            self.assertIn('不得猜测', request['prompt'])
            self.assertIn('故事题材', request['prompt'])
            self.assertNotIn(str(context.root), request['prompt'])
            self.assertNotIn(SOURCE, request['prompt'])


class SemanticBriefDesktopTests(_Harness):
    def start_explicit_extraction(self, desktop):
        # 兼容旧的显式提取接口；普通发送已不再启动独立提取任务。
        value = desktop.draft_text()
        prepared = desktop.idea_chat_controller.prepare_submission(desktop.root, value, is_example=False)
        desktop.start_idea_semantic_brief(value, prepared)

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_manual_values_and_empty_label_are_preserved_or_filled(self, _local):
        with tempfile.TemporaryDirectory() as td:
            d = self.setup_request(td)
            d.idea_input.insert('1.0', '故事题材：手填类型\n故事画幅：4:3\n故事角色：\n')
            with patch.object(d, 'open_flow_agent'), \
                    patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                self.start_explicit_extraction(d)
                pending = d._idea_semantic_pending
                pending['request']['path'].write_text(json.dumps(response(pending['request'])), encoding='utf-8')
                d.poll_idea_semantic_brief()
                launch.assert_called_once()
                submitted = launch.call_args.args[0]
                self.assertIn('故事题材：手填类型', submitted)
                self.assertIn('故事画幅：4:3', submitted)
                self.assertNotIn('故事画幅：9:16', submitted)
                notice.assert_not_called()

    def setup_request(self, td):
        from stage_execution_service import archive_idea_attachments
        root = make_minimal_project(td)
        source = Path(td) / '素材.txt'
        source.write_text(SOURCE, encoding='utf-8')
        with patch('stage_execution_service.idea_attachment_local_mode', return_value=True):
            paths = archive_idea_attachments(root, [source])
        d, win = self.desktop(root)
        d.show(0); self.settle_script_page(win)
        d.idea_attachment_paths = tuple(paths)
        return d

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_local_agent_result_autofills_and_resumes_send(self, _local):
        with tempfile.TemporaryDirectory() as td:
            d = self.setup_request(td)
            with patch.object(d, 'open_flow_agent') as extract, \
                    patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                self.start_explicit_extraction(d)
                extract.assert_called_once()
                launch.assert_not_called()
                notice.assert_not_called()
                pending = d._idea_semantic_pending
                pending['request']['path'].write_text(json.dumps(response(pending['request'])), encoding='utf-8')
                d.poll_idea_semantic_brief()
                launch.assert_called_once()
                self.assertIn('故事题材：冒险悬疑', launch.call_args.args[0])
                self.assertNotIn(SOURCE, launch.call_args.args[0])
                notice.assert_not_called()

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_unknown_requirements_remain_missing_after_autofill(self, _local):
        with tempfile.TemporaryDirectory() as td:
            d = self.setup_request(td)
            with patch.object(d, 'open_flow_agent'), patch.object(d, 'start_script_workflow') as launch, \
                    patch.object(d.notifier, 'info') as notice:
                self.start_explicit_extraction(d)
                pending = d._idea_semantic_pending
                fields = {key: value for key, value in VALUES.items() if key != '交付形态'}
                pending['request']['path'].write_text(json.dumps(response(pending['request'], fields)), encoding='utf-8')
                d.poll_idea_semantic_brief()
                launch.assert_not_called()
                self.assertEqual(tuple(d._idea_missing_dialog.brief_fields), ('交付形态',))
                notice.assert_not_called()
                self.assertIn('故事题材：冒险悬疑', d.draft_text())

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_user_edit_invalidates_late_result(self, _local):
        with tempfile.TemporaryDirectory() as td:
            d = self.setup_request(td)
            with patch.object(d, 'open_flow_agent'), patch.object(d, 'start_script_workflow') as launch:
                self.start_explicit_extraction(d)
                pending = d._idea_semantic_pending
                d.idea_input.insert('1.0', '新的手填内容')
                pending['request']['path'].write_text(json.dumps(response(pending['request'])), encoding='utf-8')
                d.poll_idea_semantic_brief()
                self.assertEqual(d.draft_text(), '新的手填内容')
                launch.assert_not_called()
