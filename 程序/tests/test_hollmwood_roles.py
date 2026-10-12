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
    def test_deepseek_v4_has_room_for_reasoning_and_visible_output(self):
        class Capture(FakeAdapter):
            def chat(self, messages, options=None, model='', system=''):
                self.limit = options['max_tokens']
                return super().chat(messages, options, model, system)

        for role in ('director', 'writer_revision', 'director_review_writer', 'actor'):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as folder:
                adapter = Capture(['完整正文'])
                roles._ask(adapter, 'deepseek-v4-flash', role, '', '', folder, 1, None,
                           publish_log=save_text)
                self.assertEqual(adapter.limit, 32768)

    def test_truncated_visible_output_is_never_accepted_or_retried(self):
        class Truncated(FakeAdapter):
            def chat(self, *args, **kwargs):
                self.prompts.append('called')
                return {'ok': True, 'text': 'APPROVED 半截正文',
                        'response_meta': {'finish_reason': 'length'},
                        'usage': {'completion_tokens': 8192}}

        for role in ('director', 'writer_revision', 'director_review_writer', 'actor'):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as folder:
                adapter = Truncated([])
                with self.assertRaisesRegex(roles.RoleExecutionError, '输出额度耗尽.*length'):
                    roles._ask(adapter, 'test-model', role, '', '', folder, 1, None,
                               publish_log=save_text)
                self.assertEqual(len(adapter.prompts), 1)
                self.assertIn(role + '_failed', (Path(folder) / 'hollmwood_step_1.log').read_text('utf-8'))

    def test_other_models_keep_8192_and_empty_response_has_budget_diagnostics(self):
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
                with self.assertRaisesRegex(roles.RoleExecutionError, '模型未返回可显示正文') as caught:
                    roles._ask(adapter, 'test-model', role, '创作规则', '创作请求',
                               folder, 2, None, publish_log=save_text)
                self.assertEqual(len(adapter.requests), 1, '非导演角色不能无边界重试')
                self.assertEqual(adapter.requests[0][1]['max_tokens'],
                                 roles.CONTENT_ROLE_MAX_TOKENS)
                self.assertIn('finish_reason=length', str(caught.exception))
                self.assertIn('max_tokens=8192', str(caught.exception))
                self.assertIn('"retried_once": false', str(caught.exception))
                self.assertNotIn('private only', str(caught.exception))

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

    def test_all_roles_and_reviews_share_skill_and_output_contract(self):
        answers = ('节奏计划', '编剧稿', 'REVISE: 补足冲突', '编剧返工稿',
                   'APPROVED 编剧通过', '编辑稿', 'APPROVED 编辑通过',
                   '演员稿', 'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            roles.run(adapter, 'test-model', '创意', rhythm_template='全局节奏', log_folder=folder,
                      skill_instructions='共享 SKILL 标记', output_contract='自然剧本交付标记',
                      publish_log=save_text)
        for index, system in enumerate(adapter.systems):
            self.assertEqual(system.count('共享 SKILL 标记'), 1)
            self.assertEqual(system.count('自然剧本交付标记'), 1)
            self.assertIn('不以镜号、逐镜时间码或字幕逐行排版作为本阶段通过条件', system)
        self.assertTrue(all('全局节奏' in system for system in adapter.systems))

    def test_brief_and_plan_reach_every_review_and_revision(self):
        answers = ('独立导演计划标记', '编剧稿', 'REVISE: 编剧返工', '编剧修订',
                   'APPROVED 编剧通过', '编辑稿', 'REVISE: 编辑返工', '编辑修订',
                   'APPROVED 编辑通过', '演员稿', 'REVISE: 演员返工', '演员修订',
                   'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            result = roles.run(adapter, 'test-model', {'单集时间': '137秒', '确认事实': '独立简报标记'},
                               log_folder=folder, skill_instructions='共享规则标记',
                               output_contract='本轮自然剧本契约', publish_log=save_text)
        self.assertEqual(len(adapter.prompts), 13)
        self.assertEqual(result.data['script'], '演员修订')
        for index, (system, prompt) in enumerate(zip(adapter.systems, adapter.prompts)):
            with self.subTest(request=index):
                self.assertEqual(system.count('共享规则标记'), 1)
                self.assertEqual(system.count('本轮自然剧本契约'), 1)
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

    def test_editor_rejection_identifies_failed_role_without_starting_actor(self):
        answers = ('节奏计划', '编剧稿', 'APPROVED', '编辑稿',
                   'REVISE: 人物动机不连贯', '编辑返工稿', 'REVISE: 仍不连贯')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            with self.assertRaisesRegex(roles.RoleExecutionError, '导演未通过 editor') as caught:
                roles.run(adapter, 'test-model', '创意', log_folder=folder, publish_log=save_text)
            self.assertEqual(caught.exception.review_failed_role, 'editor')
            self.assertEqual(len(adapter.prompts), 7)

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


class ReviewTraceabilityTests(unittest.TestCase):
    """O16：审核结论要能追到冻结输入，返工只针对明确问题。"""

    PASS_ANSWERS = ('节奏计划', '编剧稿', 'APPROVED 编剧通过', '编辑稿',
                    'APPROVED 编辑通过', '演员稿', 'APPROVED 演员通过')

    def test_same_frozen_inputs_share_one_review_basis(self):
        snapshots = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as folder:
                adapter = FakeAdapter(self.PASS_ANSWERS)
                result = roles.run(adapter, 'test-model', {'单集时间': '90秒', '确认事实': '简报标记'},
                                   rhythm_template='全局节奏标记', log_folder=folder,
                                   skill_instructions='SKILL 标记', output_contract='契约标记',
                                   publish_log=save_text)
                snapshots.append(result.data['review_audit']['basis'])
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(set(snapshots[0]), {'brief_sha256', 'skill_sha256',
                                             'rhythm_sha256', 'review_system_sha256'})
        self.assertTrue(all(len(value) == 64 for value in snapshots[0].values()))

    def test_review_records_keep_rule_compliance_apart_from_creative_signoff(self):
        answers = ('节奏计划', '编剧稿',
                   'REVISE: 第3场动机断裂，违反人物连贯规则；补一句过渡；通过条件：动机可解释',
                   '编剧修订稿', 'APPROVED 规则合格', '编辑稿', 'APPROVED 编辑通过',
                   '演员稿', 'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            result = roles.run(adapter, 'test-model', '创意', rhythm_template='节奏',
                               log_folder=folder, publish_log=save_text)
        audit = result.data['review_audit']
        self.assertEqual(audit['scope'], roles.REVIEW_SCOPE)
        self.assertEqual([record['role'] for record in audit['records']],
                         ['writer', 'writer', 'editor', 'actor'])
        writer_records = [record for record in audit['records'] if record['role'] == 'writer']
        self.assertEqual([record['verdict'] for record in writer_records], ['revise', 'approved'])
        self.assertEqual([record['rule_compliant'] for record in writer_records], [False, True])
        self.assertEqual([record['attempt'] for record in writer_records], [0, 1])
        self.assertTrue(all(record['creative_signoff'] == 'pending_user_confirmation'
                            for record in audit['records']))
        self.assertIn('通过条件', writer_records[0]['review_text'])

    def test_revision_only_targets_listed_issues_without_reinjecting_rhythm(self):
        answers = ('节奏计划', '编剧稿', 'REVISE: 第2场节奏拖沓', '编剧修订稿', 'APPROVED 规则合格',
                   '编辑稿', 'APPROVED 编辑通过', '演员稿', 'APPROVED 演员通过')
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(answers)
            roles.run(adapter, 'test-model', '创意', rhythm_template='全局节奏标记',
                      log_folder=folder, publish_log=save_text)
        revision_index = 3
        self.assertIn('只修改', adapter.prompts[revision_index])
        self.assertIn('<director_review>\nREVISE: 第2场节奏拖沓', adapter.prompts[revision_index])
        self.assertNotIn('全局节奏标记', adapter.prompts[revision_index])
        self.assertEqual(adapter.systems[revision_index].count('全局节奏标记'), 1)

    def test_rejected_review_carries_basis_and_records(self):
        answers = ('节奏计划', '编剧稿', 'REVISE: 缺钩子', '重写稿', 'REVISE: 仍缺钩子')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(roles.RoleExecutionError) as caught:
                roles.run(FakeAdapter(answers), 'test-model', '创意', rhythm_template='节奏',
                          log_folder=folder, max_revisions=1, publish_log=save_text)
        error = caught.exception
        self.assertEqual(error.review_failed_role, 'writer')
        self.assertEqual(set(error.review_basis),
                         {'brief_sha256', 'skill_sha256', 'rhythm_sha256', 'review_system_sha256'})
        self.assertEqual([record['verdict'] for record in error.review_records], ['revise', 'revise'])
        self.assertIn('仍缺钩子', error.review_records[-1]['review_text'])

    def test_resumed_prefix_is_recorded_as_previously_approved(self):
        with tempfile.TemporaryDirectory() as folder:
            options = dict(model='test-model', brief_complete='创意', log_folder=folder,
                           publish_log=save_text, resume_identity='config')
            with self.assertRaises(roles.RoleExecutionError):
                roles.run(FakeAdapter(['节奏计划', '编剧稿', 'APPROVED', '编辑稿',
                                       'REVISE: 动机', '编辑修订', 'REVISE: 仍不连贯']), **options)
            adapter = FakeAdapter(['编辑修订稿', 'APPROVED', '演员稿', 'APPROVED'])
            result = roles.run(adapter, **options)
        records = result.data['review_audit']['records']
        self.assertEqual([(record['role'], record['verdict'], record['resumed']) for record in records],
                         [('writer', 'approved', True), ('editor', 'approved', False),
                          ('actor', 'approved', False)])


if __name__ == '__main__':
    unittest.main()
