"""阶段制作锁、SKILL 路径引用和项目级编剧风格。"""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import idea_chat
import script_contract as contract
import workflow_engines
import workflow_settings
from workflow_tasks import script_prompt
from tests.test_idea_chat import idea_chat as injected_chat
from tests.test_ui_edges import make_minimal_project


STORY = '故事梗概：修表师寻找父亲\n故事题材：冒险\n故事角色：林青与阿禾\n故事集数：12集\n单集时间：90秒'


class InlineSkillTests(unittest.TestCase):
    def test_manifest_survives_history_without_exposing_configuration(self):
        with tempfile.TemporaryDirectory() as td:
            project = make_minimal_project(td)
            manifest = {'engine': 'qwen', 'model': 'sample', 'selected': ['/skill'],
                        'loaded': [{'name': '写作规则', 'path': '/skill', 'sha256': 'abc', 'chars': 10}]}
            injected_chat.append(project, 'user', '本轮请求', skill_injection=manifest)
            manifest['loaded'][0]['name'] = '后来改名'
            row = injected_chat.load(project)[0]
            self.assertIn('已勾选 1 项，本次已加载 1 项（写作规则）', idea_chat.skill_injection_summary(row))
            self.assertEqual(row['skill_injection']['loaded'][0]['sha256'], 'abc')
            self.assertEqual(idea_chat.skill_injection_summary({'text': '旧记录'}), '')

    def test_frozen_request_keeps_content_and_route(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root / 'SKILL.md'
            skill.write_text('冻结时的规则', encoding='utf-8')
            config = {'engine': 'qwen', 'model': 'first', 'stage': 'writing',
                      'skills': [str(skill)], 'stage_skills': [str(skill)]}
            with patch('skill_registry.default_root', return_value=root):
                frozen = workflow_settings.freeze_skills(config)
            config['model'] = 'second'
            skill.write_text('发送后的规则', encoding='utf-8')
            self.assertEqual(frozen['model'], 'first')
            for inline in (True, False):
                prompt = workflow_settings.skill_prompt(frozen, inline=inline)
                self.assertEqual(prompt.count('冻结时的规则'), 1)
                self.assertNotIn('发送后的规则', prompt)
            self.assertEqual(len(frozen['skill_injection']['loaded']), 1)

    def test_direct_references_only_and_desktop_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'skills'
            root.mkdir()
            skill = root / 'SKILL.md'
            skill.write_text('---\nname: sample\n---\n技能正文\n[一](one.md#section)\n'
                             '[重复](one.md)\n[二](two.txt)\n[越界](../outside.md)\n'
                             '[网址](https://example.com/file.md)', encoding='utf-8-sig')
            (root / 'one.md').write_text('直接正文一 [递归](nested.md)', encoding='utf-8')
            (root / 'two.txt').write_text('直接正文二', encoding='utf-8')
            (root / 'nested.md').write_text('禁止递归正文', encoding='utf-8')
            (root.parent / 'outside.md').write_text('禁止越界正文', encoding='utf-8')
            config = {'engine': 'qwen', 'stage_skills': [str(skill)], 'skills': [str(skill)]}
            before = workflow_settings.skill_prompt(config)
            with patch('skill_registry.default_root', return_value=root):
                result = workflow_settings.skill_prompt(config, inline=True)
                self.assertEqual(result, workflow_settings.skill_prompt(config, inline=True))
            self.assertTrue(result.startswith('<skill name="sample">\n<!-- 来源:'))
            self.assertTrue(result.endswith('</skill>'))
            self.assertEqual(result.count('技能正文'), 1)
            self.assertEqual(result.count('直接正文一'), 1)
            self.assertIn('直接正文二', result)
            self.assertNotIn('禁止递归正文', result)
            self.assertNotIn('禁止越界正文', result)
            self.assertNotIn('请先完整读取并遵循本地技能文件', result)
            self.assertEqual(before, workflow_settings.skill_prompt(config, inline=False))

    def test_cap_and_fresh_self_contained_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root / 'SKILL.md'
            skill.write_text('正文 [引用](large.md)', encoding='utf-8')
            (root / 'large.md').write_text('长' * 30000, encoding='utf-8')
            with patch('skill_registry.default_root', return_value=root):
                with self.assertRaisesRegex(ValueError, '已阻止发送'):
                    workflow_settings._inline_skill(skill, cap=20000)
            skill.write_text('更新后的独立正文', encoding='utf-8')
            result = workflow_settings._inline_skill(skill)
            self.assertIn('更新后的独立正文', result)
            self.assertIn(f'<skill name="{root.name}">', result)
            self.assertNotIn('长', result)

    def test_missing_reference_and_total_budget_block_freeze(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skill = root / 'SKILL.md'
            config = {'engine': 'qwen', 'skills': [str(skill)]}
            skill.write_text('规则 [依据](missing.md)', encoding='utf-8')
            with patch('skill_registry.default_root', return_value=root):
                with self.assertRaisesRegex(ValueError, '引用未加载'):
                    workflow_settings.freeze_skills(config)
            # R1434：长度跟随硬上限常量，两份各约一半，合计必超（断言未动）。
            half = workflow_settings.REQUEST_CONTEXT_MAX_CHARS // 4 + 1
            skill.write_text('规则' * half, encoding='utf-8')
            other = root / 'other' / 'SKILL.md'
            other.parent.mkdir()
            other.write_text('依据' * half, encoding='utf-8')
            config['skills'].append(str(other))
            with self.assertRaisesRegex(ValueError, 'SKILL请求上下文超过'):
                workflow_settings.freeze_skills(config)


class StagePromptGovernanceTests(unittest.TestCase):
    def test_writer_style_prompt_is_project_scoped_and_optional(self):
        self.assertEqual(workflow_settings.writer_style_prompt({'stage': 'writing'}), '')
        self.assertEqual(workflow_settings.writer_style_prompt({'stage': 'writing', 'writer_style': '  '}), '')
        config = {'stage': 'writing', 'writer_style': '参考好莱坞编剧，三幕结构清晰'}
        prompt = workflow_settings.writer_style_prompt(config)
        self.assertEqual(prompt.count('参考好莱坞编剧，三幕结构清晰'), 1)
        self.assertIn('编剧角色', prompt)
        self.assertEqual(workflow_settings.writer_style_prompt(config, 'storyboard'), '')
        self.assertEqual(workflow_settings.writer_style_summary({'stage': 'writing'}), '')
        self.assertIn('编剧风格', workflow_settings.writer_style_summary(config))
        self.assertNotIn('参考好莱坞', workflow_settings.writer_style_summary(config))

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
                      'writer_style': '参考好莱坞编剧',
                      'workflow_lock': {'aspect_ratio': '9:16', 'video_model_version': 'Seedance', 'delivery_format': 'markdown'}}
            prompt = workflow_engines.prompt_with_settings(script_prompt(td, None, 'writing'), config)
            self.assertEqual(prompt.count(f'请使用 [$chosen]({path.as_posix()})'), 1)
            self.assertNotIn('独有的技能正文。', prompt)
            self.assertNotIn('已完整注入', prompt)
            self.assertEqual(prompt.count('参考好莱坞编剧'), 1)
            for obsolete in ('HOLLMWOOD', '四阶段协作', '节奏指令'):
                self.assertNotIn(obsolete, prompt)
            self.assertIn('制作锁：delivery_format=markdown', prompt)
            for unwanted in ('ComfyUI', 'Blender', '制作锁：aspect_ratio=', '制作锁：video_model_version='):
                self.assertNotIn(unwanted, prompt)

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
            self.assertIn('不全文加载总控 SKILL', config['workflow_skill_prompt'])
            self.assertNotIn('完整读取', config['workflow_skill_prompt'])


if __name__ == '__main__':
    unittest.main()


class UnsupportedVideoModelLockTests(unittest.TestCase):
    def test_manual_unknown_model_falls_back_to_skill_default_format(self):
        import workflow_settings
        prompt = workflow_settings.skill_prompt({'workflow_lock': {'video_model_version': '可灵 2.1'}}, stage='video')
        self.assertIn('制作锁：video_model_version=可灵 2.1（总控 SKILL 未适配该模型', prompt)
        self.assertIn('七段式', prompt)
        for listed in ('Seedance 2.5', 'seedance2.5', 'MiniMax H3'):
            prompt = workflow_settings.skill_prompt({'workflow_lock': {'video_model_version': listed}}, stage='video')
            self.assertNotIn('未适配', prompt)
