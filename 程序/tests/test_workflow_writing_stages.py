"""Writing instructions preserve staged review and the canonical delivery boundary."""
import tempfile
import shutil
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from workflow_settings import stage_output_contract
from workflow_tasks import script_followup, script_prompt


class WritingStageInstructionsTests(unittest.TestCase):
    def test_all_routes_require_confirmation_and_keep_reference_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('workflow_tasks._agent_delivery_contract', return_value='规范路径清单'):
                texts = [stage_output_contract('writing')]
                for agent in (False, True):
                    texts.extend((
                        script_prompt(directory, None, 'writing', creative_text='素材', agent_delivery=agent),
                        script_followup(None, 'writing', project=directory,
                                        creative_text='修改人物', agent_delivery=agent),
                    ))
            for text in texts:
                with self.subTest(text=text[:50]):
                    for phrase in ('①项目设定', '②剧本大纲', '③角色卡', '④自然剧本',
                                   '故事大体环境', '小说/漫剧类型', '用户确认', '待确认',
                                   '不进入 02', '唯一来源', '内部工作稿',
                                   '项目设定和角色卡', '项目大纲', '项目剧本', '角色卡标明“人物设定”'):
                        self.assertIn(phrase, text)
                    self.assertNotIn('docs/', text)
                    self.assertNotIn('请直接完成一份', text)
            self.assertIn('本次只输出阶段①项目设定', texts[1])
            self.assertIn('根据对话历史', texts[2])
            self.assertIn('修改当前阶段', texts[2])
            self.assertIn('规范路径清单', texts[3])
            self.assertIn('规范路径清单', texts[4])
            self.assertNotIn('规范路径清单', texts[1])

    def test_role_card_heading_uses_existing_classifier(self):
        from idea_chat import _project_file_type
        self.assertEqual(_project_file_type('# 人物设定：角色卡\n姓名：林青'), '角色卡')
        self.assertEqual(_project_file_type('# 项目设定\n都市雨夜'), '项目设定')

    def test_skill_scopes_template_to_first_four_stages(self):
        program = Path(__file__).resolve().parents[1]
        skill = program / 'skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md'
        text = skill.read_text(encoding='utf-8')
        self.assertNotIn('jingju-skills', text)
        for heading in ('### 1. 项目设定', '### 2. 剧本大纲',
                        '### 3. 角色卡', '### 4. 自然剧本'):
            self.assertIn(heading, text)
        self.assertNotIn('### 5.', text)
        self.assertNotIn('角色参考图 image2 提示词', text)
        self.assertIn('output: [scriptRaw, creativeBrief, emotionCurve]', text)
        self.assertIn('先问清楚，再创作', text)
        self.assertIn('每个关键阶段都必须用户确认，不能自动跳到下一阶段', text)
        self.assertIn('内置阶段输出模板', text)
        self.assertIn('不进入 02', text)
        self.assertIn('character_manifest', text)
        self.assertNotIn('docs/', text)

    def _installed_skill(self, directory):
        source = Path(__file__).resolve().parents[1] / 'skills'
        root = Path(directory) / 'program' / 'skills'
        relative = Path('01 剧本准备SKILL/pipeline-script-preparation.skill.md')
        skill = root / relative
        skill.parent.mkdir(parents=True)
        shutil.copyfile(source / relative, skill)
        aigc = Path('00全流程SKILL/AIGC创作全流程')
        shutil.copytree(source / aigc, root / aigc)
        return root, skill

    def test_installed_api_skill_loads_without_jingju_and_keeps_aigc(self):
        import codex_skill_sync
        from workflow_settings import skill_prompt
        with tempfile.TemporaryDirectory() as directory:
            root, skill = self._installed_skill(directory)
            self.assertFalse((root / '00全流程SKILL/jingju-skills').exists())
            with patch('skill_registry.default_root', return_value=root):
                prompt = skill_prompt({'stage_skills': [str(skill)]}, inline=True)
            self.assertIn('### 4. 自然剧本', prompt)
            for name in ('screenplay-gate-engine.md', 'emotion-beat-curve.md',
                         'dialogue-doctor-7d.md', 'dialogue-speed-check.md'):
                self.assertIn('## 引用: ' + name, prompt)
            home = Path(directory) / 'codex-skills'
            result = codex_skill_sync.sync_codex_skills(root.parent, home)
            self.assertEqual(result['written'], ['pipeline-script-preparation'])
            body = (home / 'pipeline-script-preparation/SKILL.md').read_text(encoding='utf-8')
            self.assertIn('### 4. 自然剧本', body)
            self.assertNotIn('jingju-skills', body)

    def test_jingju_edits_do_not_change_api_or_synced_skill(self):
        import codex_skill_sync
        from workflow_settings import _inline_skill
        with tempfile.TemporaryDirectory() as directory:
            root, skill = self._installed_skill(directory)
            reference = root / '00全流程SKILL/jingju-skills/references/stage-output-contracts.md'
            reference.parent.mkdir(parents=True)
            reference.write_text('原始外部模板', encoding='utf-8')
            with patch('skill_registry.default_root', return_value=root):
                before = _inline_skill(skill)
                reference.write_text('被用户修改的外部模板', encoding='utf-8')
                self.assertEqual(_inline_skill(skill), before)
            home = Path(directory) / 'codex-skills'
            result = codex_skill_sync.sync_codex_skills(root.parent, home)
            self.assertEqual(result['written'], ['pipeline-script-preparation'])
            body = (home / 'pipeline-script-preparation/SKILL.md').read_text(encoding='utf-8')
            self.assertNotIn('jingju-skills', body)
            self.assertIn('### 4. 自然剧本', body)
            links = re.findall(r'\]\(([^)]+)\)', body)
            self.assertEqual(len(links), 4)
            for link in links:
                self.assertIn('/00全流程SKILL/AIGC创作全流程/', link)
                self.assertTrue(Path(link.split('#')[0]).is_file())


if __name__ == '__main__':
    unittest.main()
