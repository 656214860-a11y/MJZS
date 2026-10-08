# -*- coding: utf-8 -*-
"""HOLLMWOOD 四角色协作的纯本地自检。"""
import tempfile
import unittest
import json
from pathlib import Path

import hollmwood_roles as roles
from agent.core import save_text
from model_router import ModelAdapter


class FakeAdapter(ModelAdapter):
    def __init__(self, responses):
        super().__init__(program=Path(__file__).resolve().parent)
        self.responses = iter(responses)
        self.systems = []
        self.prompts = []

    def chat(self, messages, options=None, model='', system=''):
        self.systems.append(system)
        self.prompts.append(messages[0]['content'])
        return {'ok': True, 'text': next(self.responses), 'error': ''}


class RolesTests(unittest.TestCase):
    def test_content_roles_use_8192_and_empty_response_is_not_retried(self):
        """只有导演空正文可补发；创作角色必须保留一次请求的真实失败边界。"""
        class EmptyContentAdapter(ModelAdapter):
            def __init__(self):
                super().__init__(program=Path(__file__).resolve().parent)
                self.requests = []

            def chat(self, messages, options=None, model='', system=''):
                self.requests.append((messages, options, system))
                return {'ok': True, 'text': '', 'error': '', 'data': {
                    'choices': [{'finish_reason': 'length', 'message': {
                        'reasoning_content': 'private only', 'content': ''}}]}}

        for role in ('writer', 'editor', 'actor',
                     'writer_revision', 'editor_revision', 'actor_revision'):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as folder:
                adapter = EmptyContentAdapter()
                with self.assertRaisesRegex(roles.RoleExecutionError, '模型未返回可显示正文'):
                    roles._ask(adapter, 'test-model', role, '创作规则', '创作请求',
                               folder, 2, None, publish_log=save_text)
                self.assertEqual(len(adapter.requests), 1, '非导演角色不能无边界重试')
                self.assertEqual(adapter.requests[0][1]['max_tokens'],
                                 roles.CONTENT_ROLE_MAX_TOKENS)

    def test_director_retry_keeps_openai_chat_envelope(self):
        """重试只改变提示和额度，system 与 user 消息仍使用既有 Chat 契约。"""
        class RetryAdapter(ModelAdapter):
            def __init__(self):
                super().__init__(program=Path(__file__).resolve().parent)
                self.requests = []

            def chat(self, messages, options=None, model='', system=''):
                self.requests.append((messages, options, system))
                return ({'ok': True, 'text': '', 'error': '', 'data': {
                    'choices': [{'finish_reason': 'length', 'message': {'content': ''}}]}}
                        if len(self.requests) == 1 else
                        {'ok': True, 'text': '可见导演计划', 'error': '', 'data': {
                            'choices': [{'finish_reason': 'stop', 'message': {'content': '可见导演计划'}}]}})

        with tempfile.TemporaryDirectory() as folder:
            adapter = RetryAdapter()
            result = roles._ask(adapter, 'test-model', 'director', '导演规则', '初始任务',
                                folder, 1, None, publish_log=save_text)
        self.assertEqual(result, '可见导演计划')
        self.assertEqual(len(adapter.requests), 2)
        for messages, _options, system in adapter.requests:
            self.assertEqual(messages[0]['role'], 'user')
            self.assertEqual(system.splitlines()[0], '导演规则')
        self.assertEqual(adapter.requests[0][1]['max_tokens'], 4096)
        self.assertEqual(adapter.requests[1][1]['max_tokens'], roles.DIRECTOR_RETRY_MAX_TOKENS)

    def test_empty_director_plan_retries_once_and_returns_clear_status(self):
        class EmptyDirectorAdapter(ModelAdapter):
            def __init__(self):
                super().__init__(program=Path(__file__).resolve().parent)
                self.calls = 0
                self.requests = []

            def chat(self, messages, options=None, model='', system=''):
                self.calls += 1
                self.requests.append((messages, options, system))
                return {'ok': True, 'text': '', 'error': '', 'data': {
                    'choices': [{'finish_reason': 'stop', 'message': {
                        'reasoning_content': 'internal only', 'content': ''}}]}}

        with tempfile.TemporaryDirectory() as folder:
            adapter = EmptyDirectorAdapter()
            with self.assertRaisesRegex(roles.RoleExecutionError, '模型未生成导演正文'):
                roles._ask(adapter, 'test-model', 'director', '规划', '生成节奏计划', folder, 1, None,
                           publish_log=save_text)
            self.assertEqual(adapter.calls, 2, '空导演正文只允许补发一次')
            self.assertEqual(adapter.requests[1][1]['max_tokens'], roles.DIRECTOR_RETRY_MAX_TOKENS)
            self.assertIn('直接输出完整、可执行的导演节奏计划', adapter.requests[1][0][0]['content'])
            final_log = Path(folder) / 'hollmwood_step_1.log'
            self.assertIn('finish_reason', final_log.read_text(encoding='utf-8'))

    def test_empty_director_review_retries_once_and_returns_clear_status(self):
        class EmptyReviewAdapter(ModelAdapter):
            def __init__(self):
                super().__init__(program=Path(__file__).resolve().parent)
                self.calls = 0

            def chat(self, messages, options=None, model='', system=''):
                self.calls += 1
                return {'ok': True, 'text': '', 'error': '', 'data': {
                    'choices': [{'finish_reason': 'stop', 'message': {
                        'reasoning_content': 'internal only', 'content': ''}}]}}

        with tempfile.TemporaryDirectory() as folder:
            adapter = EmptyReviewAdapter()
            with self.assertRaisesRegex(roles.RoleExecutionError, '模型未生成审核正文'):
                roles._ask(adapter, 'test-model', 'director_review_writer', '审核', '审核候选剧本',
                           folder, 3, None, publish_log=save_text)
            self.assertEqual(adapter.calls, 2, '空审核正文只允许补发一次')
            final_log = Path(folder) / 'hollmwood_step_3.log'
            self.assertIn('reasoning_content', final_log.read_text(encoding='utf-8'))

    def test_four_roles_are_serial_and_each_step_is_logged(self):
        answers = ('节奏计划', '编剧稿', 'APPROVED 编剧通过', '编辑稿',
                   'APPROVED 编辑通过', '演员稿', 'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            result = roles.run(adapter, 'test-model', {'idea': '少年发现秘密'},
                               rhythm_template={'rules': 'hook'}, log_folder=folder, publish_log=save_text)
            self.assertTrue(result.ok)
            self.assertEqual(result.data['script'], '演员稿')
            files = sorted(Path(folder).glob('hollmwood_step_*.log'))
            self.assertEqual(len(files), 7)
            diagnostics = sorted((Path(folder) / 'model_diagnostics').glob('*.json'))
            self.assertEqual(len(diagnostics), 7)
            diagnostic = json.loads(diagnostics[0].read_text(encoding='utf-8'))
            self.assertIn('elapsed_ms', diagnostic['context'])
            self.assertIn('request_chars', diagnostic['context'])
            self.assertGreaterEqual(float(diagnostic['context']['elapsed_ms']), 0)
            self.assertIn('director_review_actor', files[-1].read_text(encoding='utf-8'))
            self.assertTrue(all('hook' in system for system in adapter.systems))
            self.assertNotIn('<rhythm_template>', adapter.prompts[0])
            self.assertTrue(all('<rhythm_template>' not in prompt for prompt in adapter.prompts))

    def test_all_roles_and_reviews_share_skill_but_writer_owns_output_contract(self):
        answers = ('节奏计划', '编剧稿', 'REVISE: 补足冲突', '编剧返工稿',
                   'APPROVED 编剧通过', '编辑稿', 'APPROVED 编辑通过',
                   '演员稿', 'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            roles.run(adapter, 'test-model', '创意', rhythm_template='全局节奏', log_folder=folder,
                      skill_instructions='共享 SKILL 标记', output_contract='仅编剧交付标记',
                      publish_log=save_text)
        for index, system in enumerate(adapter.systems):
            self.assertEqual(system.count('共享 SKILL 标记'), 1)
            self.assertEqual(system.count('仅编剧交付标记'), int(index in (1, 3)))
        self.assertTrue(all('全局节奏' in system for system in adapter.systems))

    def test_brief_and_plan_reach_every_review_and_revision(self):
        answers = ('独立导演计划标记', '编剧稿', 'REVISE: 编剧返工', '编剧修订',
                   'APPROVED 编剧通过', '编辑稿', 'REVISE: 编辑返工', '编辑修订',
                   'APPROVED 编辑通过', '演员稿', 'REVISE: 演员返工', '演员修订',
                   'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            result = roles.run(adapter, 'test-model', {'单集时间': '137秒', '确认事实': '独立简报标记'},
                               log_folder=folder, skill_instructions='共享规则标记', publish_log=save_text)
        self.assertEqual(len(adapter.prompts), 13)
        self.assertEqual(result.data['script'], '演员修订')
        for index, (system, prompt) in enumerate(zip(adapter.systems, adapter.prompts)):
            with self.subTest(request=index):
                self.assertEqual(system.count('共享规则标记'), 1)
                self.assertEqual(prompt.count('<brief_complete>'), 1)
                self.assertEqual(prompt.count('独立简报标记'), 1)
                self.assertIn('137秒', prompt)
                self.assertEqual(prompt.count('独立导演计划标记'), int(index > 0))
                self.assertNotIn('全局节奏模板', system)
        for index, candidate in ((2, '编剧稿'), (4, '编剧修订'), (6, '编辑稿'),
                                 (8, '编辑修订'), (10, '演员稿'), (12, '演员修订')):
            self.assertIn('<candidate>\n' + candidate + '\n</candidate>', adapter.prompts[index])
        for index, draft, review in ((3, '编剧稿', '编剧返工'), (7, '编辑稿', '编辑返工'),
                                     (11, '演员稿', '演员返工')):
            self.assertIn('<previous_script>\n' + draft, adapter.prompts[index])
            self.assertIn('<director_review>\nREVISE: ' + review, adapter.prompts[index])

    def test_empty_rhythm_is_skipped_and_custom_content_is_preserved(self):
        for template in ('', '  ', '# 只读说明', roles.load_rhythm_template(), {},
                         {'name': '占位', 'rules': {}, 'constraints': {}},
                         'name: 占位\nrules:\nconstraints: null # 空'):
            with self.subTest(template=template):
                self.assertEqual(roles.rhythm_prompt(template), '')
        for template in ('自定义节奏', 'rules:\n  name: 必须保留的自定义规则',
                         'rules: {custom: true}', 'other: 保留未知字段',
                         {'rules': {'custom': '保留规则'}}):
            with self.subTest(template=template):
                self.assertEqual(roles.rhythm_prompt(template),
                                 '\n\n全局节奏模板（每个角色都必须遵守）：\n' + roles._body(template))

    def test_context_budget_rejects_before_model_call_without_truncating_script(self):
        class NeverCalledAdapter(ModelAdapter):
            def __init__(self):
                super().__init__(program=Path(__file__).resolve().parent)
                self.calls = 0

            def chat(self, *args, **kwargs):
                self.calls += 1
                return {'ok': True, 'text': '不应调用', 'error': ''}

        with tempfile.TemporaryDirectory() as folder:
            adapter = NeverCalledAdapter()
            with self.assertRaisesRegex(roles.RoleExecutionError, '上下文过长'):
                roles._ask(adapter, 'test-model', 'writer', '规则',
                           '剧本' * (roles.REQUEST_CONTEXT_MAX_CHARS + 1),
                           folder, 2, None, publish_log=save_text)
            self.assertEqual(adapter.calls, 0)
            log = Path(folder) / 'hollmwood_step_2.log'
            self.assertIn('安全预算', log.read_text(encoding='utf-8'))

    def test_project_director_rules_are_injected_only_into_director_roles(self):
        answers = ('节奏计划', '编剧稿', 'APPROVED 编剧通过', '编辑稿',
                   'APPROVED 编辑通过', '演员稿', 'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            roles.run(adapter, 'test-model', '创意', rhythm_template='规则', log_folder=folder,
                      director_rules='导演必须保留雨伞这个关键道具', publish_log=save_text)
        self.assertIn('雨伞', adapter.systems[0])
        self.assertIn('雨伞', adapter.systems[2])
        self.assertNotIn('雨伞', adapter.systems[1])

    def test_director_rejects_after_revision_budget(self):
        answers = ('节奏计划', '编剧稿', 'REVISE: 缺少钩子', '重写稿', 'REVISE: 仍缺钩子')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(roles.RoleExecutionError):
                roles.run(FakeAdapter(answers), 'test-model', '创意', rhythm_template='规则',
                          log_folder=folder, max_revisions=1, publish_log=save_text)

    def test_contract_reference_points_to_project_template(self):
        self.assertEqual(roles.RHYTHM_TEMPLATE_PATH, 'skills/templates/rhythm_template.yaml')
        lines = [line for line in roles.load_rhythm_template().splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        self.assertEqual(lines, ['name: 漫剧节奏指令', 'template_id: "rhythm"',
                                 'version: 1', 'rules: {}', 'constraints: {}'])

    def test_cancel_stops_after_the_active_request_before_next_role(self):
        events = []
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(('节奏计划',))
            with self.assertRaises(roles.RoleCancelledError):
                roles.run(adapter, 'test-model', '创意', rhythm_template='规则', log_folder=folder,
                          emit=lambda role, step: events.append((role, step)),
                          cancelled=lambda: bool(events), publish_log=save_text)
        self.assertEqual(events, [('director', 1)])
        self.assertEqual(len(adapter.systems), 1, '取消后不再启动后续角色')


if __name__ == '__main__':
    unittest.main()
