"""阶段制作锁、SKILL 路径引用和桌面四角色共用规则。"""
import tempfile
import unittest
from pathlib import Path

import hollmwood_roles
import hollmwood_rules
import idea_chat
import script_contract as contract
import workflow_engines
import workflow_settings
from workflow_tasks import script_prompt
from tests.test_idea_chat import idea_chat as injected_chat
from tests.test_ui_edges import make_minimal_project


STORY = '故事梗概：修表师寻找父亲\n故事题材：冒险\n故事角色：林青与阿禾\n故事集数：12集\n单集时间：90秒'


class StagePromptGovernanceTests(unittest.TestCase):
    def test_story_fields_and_stage_lock_contract(self):
        self.assertEqual(contract.INLINE_REQUIRED_LABELS,
                         ('故事梗概', '故事题材', '故事角色', '故事集数', '单集时间'))
        self.assertEqual(contract.stage_lock_requirements('writing'), ('delivery_format',))
        for stage in ('keyframe', 'frames', 'video', 'video_prompt', 'previs'):
            self.assertEqual(set(contract.stage_lock_requirements(stage)),
                             {'aspect_ratio', 'video_model_version', 'delivery_format'})
        for stage in ('assets', 'storyboard', 'audio', 'unknown', None):
            self.assertEqual(contract.stage_lock_requirements(stage), ())

    def test_inline_required_locks_follow_stage_and_aliases(self):
        self.assertEqual(idea_chat.inline_required_missing(None, STORY), ('交付形态',))
        draft = STORY + '\n交付形态：markdown'
        for stage in ('script', 'writing', 'audio', 'storyboard'):
            self.assertEqual(idea_chat.inline_required_missing(None, draft, stage=stage), ())
        for stage in ('frames', 'previs', 'video'):
            self.assertEqual(set(idea_chat.inline_required_missing(None, draft, stage=stage)), {'画幅', '视频模型版本'})
            self.assertEqual(idea_chat.inline_required_missing(None, draft, stage=stage,
                             attachment_fields={'故事画幅': '9:16', '视频模型': 'Seedance 2.5'}), ())
        self.assertEqual(idea_chat.inline_required_missing(None, STORY, stage='audio'), ())

    def test_custom_lock_labels_and_template_aliases(self):
        definitions = ({'key': 'delivery_format', 'label': '交付方式', 'aliases': ('交付形态',)},)
        self.assertEqual(idea_chat.inline_required_missing(None, STORY, lock_definitions=definitions), ('交付方式',))
        template = STORY + '\n交付方式：示例'
        draft = STORY + '\n交付形态：示例'
        self.assertIn('交付方式', idea_chat.inline_required_missing(template, draft, lock_definitions=definitions))
        self.assertEqual(idea_chat.inline_required_missing(None, draft.replace('示例', 'markdown'), lock_definitions=definitions), ())

    def test_receive_brief_requires_only_stage_locks_and_preserves_advisory(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            def receive(text, stage):
                return injected_chat.receive_brief(root, text, inline_text=text, stage=stage,
                    lock_definitions=contract.PRODUCTION_LOCK_DEFINITIONS)
            self.assertEqual(injected_chat.receive_brief(root, STORY, inline_text=STORY, stage='writing')['missing'], ('delivery_format',))
            missing = receive(STORY, 'script')
            self.assertEqual(missing['missing'], ('delivery_format',))
            self.assertIsNone(missing['complete_path'])
            self.assertIn('交付形态', missing['followup'])
            text = STORY + '\n交付形态：markdown'
            self.assertEqual(receive(text, 'script')['missing'], ())
            self.assertEqual(set(receive(text, 'frames')['missing']), {'aspect_ratio', 'video_model_version'})
            fields = receive(text + '\n故事画幅：9:16\n视频模型：Seedance 2.5', 'script')['fields']
            self.assertEqual(fields['production_locks']['aspect_ratio'], '9:16')
            self.assertEqual(fields['production_locks']['video_model_version'], 'Seedance 2.5')
            self.assertEqual(receive(STORY, 'audio')['missing'], ())

    def test_writing_references_skill_once_and_excludes_media_locks(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'SKILL.md'
            path.write_text('---\nname: chosen\n---\n独有的技能正文。', encoding='utf-8')
            config = {'engine': 'codex', 'stage': 'writing', 'stage_skills': [str(path)],
                      'skills': [str(path)], 'skill': str(path),
                      'workflow_lock': {'aspect_ratio': '9:16', 'video_model_version': 'Seedance', 'delivery_format': 'markdown'}}
            prompt = workflow_engines.prompt_with_settings(script_prompt(td, None, 'writing'), config)
            self.assertEqual(prompt.count(f'请使用 [$chosen]({path.as_posix()})'), 1)
            self.assertNotIn('独有的技能正文。', prompt)
            self.assertNotIn('已完整注入', prompt)
            self.assertIn('四阶段协作', prompt)
            self.assertIn('Gate 1~2', prompt)
            self.assertIn('Gate 3~5', prompt)
            self.assertIn('制作锁：delivery_format=markdown', prompt)
            for unwanted in ('ComfyUI', 'Blender', '制作锁：aspect_ratio=', '制作锁：video_model_version='):
                self.assertNotIn(unwanted, prompt)
            for rules in (hollmwood_rules.DIRECTOR_PLAN_RULES, hollmwood_rules.WRITER_RULES,
                          hollmwood_rules.EDITOR_RULES, hollmwood_rules.ACTOR_RULES,
                          hollmwood_rules.DIRECTOR_REVIEW_RULES):
                self.assertEqual(prompt.count(rules), 1)

    def test_selected_skills_are_path_references_for_all_engines_and_stages(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'SKILL.md'
            path.write_text('---\nname: chosen\n---\n独有的技能正文。\n'
                            '../references/screenplay-gate-engine.md', encoding='utf-8')
            for engine in ('codex', 'claude', 'qwen'):
                config = {'engine': engine, 'stage': 'frames',
                          'stage_skills': [str(path)], 'skills': [str(path)],
                          'workflow_lock': {'aspect_ratio': '9:16',
                                            'video_model_version': 'Seedance',
                                            'delivery_format': 'markdown'}}
                for stage in ('script', 'writing', 'storyboard', 'assets', 'frames',
                              'previs', 'video_prompt', 'audio'):
                    with self.subTest(engine=engine, stage=stage):
                        prompt = workflow_engines.prompt_with_settings('任务', config, stage=stage)
                        reference = (f'请使用 [$chosen]({path.as_posix()})' if engine == 'codex'
                                     else f'请先完整读取并遵循本地技能文件 {path}')
                        self.assertEqual(prompt.count(reference), 1)
                        self.assertNotIn('独有的技能正文。', prompt)
                        self.assertNotIn('../references/screenplay-gate-engine.md', prompt)
                        if stage in ('script', 'writing'):
                            self.assertIn('制作锁：delivery_format=markdown', prompt)
                            self.assertNotIn('制作锁：aspect_ratio=', prompt)
                            self.assertNotIn('制作锁：video_model_version=', prompt)

    def test_api_role_wrappers_share_exact_rules(self):
        for role in ('director_plan', 'writer', 'editor', 'actor', 'director_review'):
            self.assertEqual(getattr(hollmwood_roles, '_' + role + '_system')(),
                             getattr(hollmwood_rules, role.upper() + '_RULES'))

    def test_media_apps_and_header_for_other_stages(self):
        config = {'engine': 'codex', 'skill': '', 'workflow_lock': {'aspect_ratio': '9:16', 'delivery_format': 'markdown', 'custom': 'keep'}}
        for stage in ('assets', 'frames', 'previs', 'video_prompt'):
            prompt = workflow_engines.prompt_with_settings('任务', config, stage=stage)
            self.assertIn('ComfyUI', prompt)
            self.assertIn('Blender', prompt)
        for stage in ('storyboard', 'audio'):
            prompt = workflow_engines.prompt_with_settings('任务', config, stage=stage)
            self.assertNotIn('ComfyUI', prompt)
            self.assertIn('制作锁：custom=keep', prompt)
        self.assertNotIn('制作锁：custom=', workflow_settings.skill_prompt(config, stage='frames'))

    def test_coordinator_is_scoped_in_real_stage_config(self):
        import stage_config
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            stage_config.put_workflow(root, {'name': 'AIGC全流程'})
            config = workflow_settings.current(root, 'writing')
            self.assertIn('不全文加载统筹 SKILL', config['workflow_skill_prompt'])
            self.assertNotIn('完整读取', config['workflow_skill_prompt'])


if __name__ == '__main__':
    unittest.main()
