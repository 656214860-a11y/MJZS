"""四角色请求去重、短审核与失败断点的本地回归，不访问远端模型。"""
import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

from agent.core import save_text
import hollmwood_roles as roles
from tests.test_hollmwood_roles import FakeAdapter


ANSWERS = ['计划', '编剧稿', 'APPROVED', '编辑稿', 'APPROVED', '演员稿', 'APPROVED']


class PerformanceTests(unittest.TestCase):
    def test_empty_audit_retry_requests_short_review_not_a_new_plan(self):
        adapter = FakeAdapter(['', 'APPROVED'])
        with tempfile.TemporaryDirectory() as folder:
            result = roles._ask(adapter, 'test', 'director_review_writer', '审核', '候选',
                                folder, 3, None, publish_log=save_text)
        self.assertEqual(result, 'APPROVED')
        self.assertEqual(len(adapter.prompts), 2)
        self.assertIn('REVISE:', adapter.prompts[1])
        self.assertNotIn('导演节奏计划', adapter.prompts[1])

    def test_saved_default_rules_are_not_injected_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(ANSWERS)
            roles.run(adapter, 'test', '创意', log_folder=folder, publish_log=save_text,
                      director_rules=roles.default_director_rules(),
                      role_rules={role: roles.default_role_rules(role) for role in roles.ROLE_ORDER})
        for index, rule in ((0, roles.DIRECTOR_PLAN_RULES), (1, roles.WRITER_RULES),
                            (3, roles.EDITOR_RULES), (5, roles.ACTOR_RULES),
                            (2, roles.DIRECTOR_REVIEW_RULES)):
            self.assertEqual(adapter.systems[index].count(rule), 1)
        self.assertNotIn(roles.DIRECTOR_PLAN_RULES, adapter.systems[2])

    def test_review_is_concise_without_removing_shared_constraints(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(ANSWERS)
            roles.run(adapter, 'test', '简报标记', log_folder=folder, publish_log=save_text,
                      skill_instructions='全部质量约束')
        for index in (2, 4, 6):
            self.assertIn('不复述剧本', adapter.systems[index])
            self.assertIn('全部质量约束', adapter.systems[index])
            self.assertIn('简报标记', adapter.prompts[index])

    def test_failed_editor_reuses_only_approved_prefix_and_success_starts_fresh(self):
        with tempfile.TemporaryDirectory() as folder:
            options = dict(log_folder=folder, publish_log=save_text, resume_identity='provider-config')
            first = FakeAdapter(['计划', '编剧稿', 'APPROVED', '编辑稿', 'REVISE: 动机',
                                 '编辑修订', 'REVISE: 动机仍不明'])
            with self.assertRaises(roles.RoleExecutionError):
                roles.run(first, 'test', '创意', **options)
            retry = FakeAdapter(['新编辑稿', 'APPROVED', '演员稿', 'APPROVED'])
            result = roles.run(retry, 'test', '创意', **options)
            self.assertEqual(result.data['script'], '演员稿')
            self.assertEqual(len(retry.prompts), 4)
            self.assertIn('编剧稿', retry.prompts[0])
            self.assertNotIn('编辑修订', retry.prompts[0])
            fresh = FakeAdapter(ANSWERS)
            roles.run(fresh, 'test', '创意', **options)
            self.assertEqual(len(fresh.prompts), 7)

    def test_changed_inputs_invalidate_checkpoint(self):
        for changed in ({'brief_complete': '改后的角色卡'}, {'model': 'other'},
                        {'resume_identity': 'new-config'}, {'skill_instructions': '新规则'},
                        {'director_rules': '新导演规则'}, {'role_rules': {'writer': '新编剧规则'}},
                        {'rhythm_template': '新节奏'}, {'output_contract': '新契约'}):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                options = dict(model='test', brief_complete='创意', log_folder=folder,
                               publish_log=save_text, resume_identity='provider-config')
                with self.assertRaises(roles.RoleExecutionError):
                    roles.run(FakeAdapter(['计划', '']), **options)
                options.update(changed)
                adapter = FakeAdapter(ANSWERS)
                roles.run(adapter, **options)
                self.assertEqual(len(adapter.prompts), 7)

    def test_failure_at_each_content_role_resumes_from_that_role(self):
        for prefix, remaining in ((['计划'], ANSWERS[1:]),
                                  (ANSWERS[:3], ANSWERS[3:]), (ANSWERS[:5], ANSWERS[5:])):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as folder:
                options = dict(log_folder=folder, publish_log=save_text, resume_identity='config')
                with self.assertRaises(roles.RoleExecutionError):
                    roles.run(FakeAdapter(prefix + ['']), 'test', '创意', **options)
                events = []
                retry = FakeAdapter(remaining)
                result = roles.run(retry, 'test', '创意', emit=lambda role, step: events.append((role, step)), **options)
                self.assertEqual(result.data['script'], '演员稿')
                self.assertEqual(len(retry.prompts), len(remaining))
                self.assertEqual(events[-1], ('director_review_actor', 7))

    def test_modified_cached_body_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            options = dict(log_folder=folder, publish_log=save_text, resume_identity='config')
            with self.assertRaises(roles.RoleExecutionError):
                roles.run(FakeAdapter(ANSWERS[:3] + ['']), 'test', '创意', **options)
            target = Path(folder) / 'hollmwood_resume.json'
            saved = json.loads(target.read_text(encoding='utf-8'))
            saved['outputs']['writer'] = '未经审核的修改'
            save_text(target, json.dumps(saved, ensure_ascii=False))
            retry = FakeAdapter(ANSWERS)
            roles.run(retry, 'test', '创意', **options)
            self.assertEqual(len(retry.prompts), 7)

    def test_cancelled_response_does_not_become_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter = FakeAdapter(['计划'])
            with self.assertRaises(roles.RoleCancelledError):
                roles.run(adapter, 'test', '创意', log_folder=folder, publish_log=save_text,
                          resume_identity='config', cancelled=lambda: bool(adapter.prompts))
            retry = FakeAdapter(ANSWERS)
            roles.run(retry, 'test', '创意', log_folder=folder, publish_log=save_text,
                      resume_identity='config')
            self.assertEqual(len(retry.prompts), 7)

    def test_corrupt_checkpoint_is_not_used(self):
        for content in ('{', '[]', json.dumps({'fingerprint': 'wrong'})):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as folder:
                save_text(Path(folder) / 'hollmwood_resume.json', content)
                adapter = FakeAdapter(ANSWERS)
                roles.run(adapter, 'test', '创意', log_folder=folder, publish_log=save_text,
                          resume_identity='config')
                self.assertEqual(len(adapter.prompts), 7)

    def test_api_passes_config_identity_without_persisting_credentials(self):
        import writing_api
        from service_contract import success
        with tempfile.TemporaryDirectory() as folder, \
                patch('writing_api.PoolAdapter'), \
                patch('stage_config.hollmwood_rules', return_value=('', '')), \
                patch('stage_config.hollmwood_role_rules', return_value={}), \
                patch('workflow_settings.skill_prompt', return_value=''), \
                patch('writing_api._write_script_raw', return_value=Path(folder) / 'script_raw.md'), \
                patch('hollmwood_roles.run', return_value=success({'script': '正文'})) as run:
            for endpoint in ('one', 'two'):
                writing_api._hollmwood_reply(folder, 'test', {'endpoint': endpoint, 'key': 'private'}, {}, {'idea': '创意'})
            identities = [call.kwargs['resume_identity'] for call in run.call_args_list]
        self.assertNotEqual(*identities)
        self.assertTrue(all(len(value) == 64 and 'private' not in value for value in identities))
