"""Writing instructions preserve staged review and the canonical delivery boundary."""
import tempfile
import shutil
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from workflow_settings import stage_output_contract
from orchestrator.workflow_tasks import script_followup, script_prompt


class WritingStageInstructionsTests(unittest.TestCase):
    def test_all_routes_require_confirmation_and_keep_reference_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='规范路径清单'):
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

    def test_req_s01_16_17_natural_script_carries_beat_table_without_shot_layer(self):
        """REQ-S01-16/17：④自然剧本每集带节拍表；镜头层（情境 ID／80-15-5／雷区）不进本阶段。"""
        program = Path(__file__).resolve().parents[1]
        text = (program / 'skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md').read_text(encoding='utf-8')
        template = text.split('### 4. 自然剧本', 1)[1].split('### 节拍表', 1)[0]
        self.assertIn('## 本集节拍表', template)
        self.assertIn('| 场次 | 节拍＃ | 情绪关键词 | 服务的剧本动作 | 权重 | 强度 |', template)
        rules = text.split('### 节拍表', 1)[1].split('## 定向注入', 1)[0]
        for phrase in ('每场 3–5 个节拍', '禁止“复杂”“微妙”', '每场至多 1 个', '4 个同类节拍等于戏没推进',
                       '不写情境 ID、镜头组合、机位、构图雷区', '留给 03／07'):
            self.assertIn(phrase, rules + text)
        # 同一份自然剧本文件内交付，不另立文件。
        self.assertNotIn('beat_sheet.json', text)
        clause = '每集在正文前附本集节拍表'
        with tempfile.TemporaryDirectory() as directory:
            with patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='规范路径清单'):
                prompts = [stage_output_contract('writing'),
                           script_prompt(directory, None, 'writing', creative_text='素材'),
                           script_followup(None, 'writing', project=directory, creative_text='修改人物')]
        for prompt in prompts:
            self.assertIn(clause, prompt)
            self.assertIn('不含机位、情境 ID 等镜头层内容', prompt)

    def _installed_skill(self, directory):
        source = Path(__file__).resolve().parents[1] / 'skills'
        root = Path(directory) / 'program' / 'skills'
        relative = Path('01 剧本准备SKILL/pipeline-script-preparation.skill.md')
        skill = root / relative
        skill.parent.mkdir(parents=True)
        shutil.copyfile(source / relative, skill)
        return root, skill

    def test_installed_api_skill_loads_without_builtin_control(self):
        from orchestrator import codex_skill_sync
        from workflow_settings import skill_prompt
        with tempfile.TemporaryDirectory() as directory:
            root, skill = self._installed_skill(directory)
            self.assertFalse((root / '00全流程SKILL').exists())
            with patch('skill_registry.default_root', return_value=root):
                prompt = skill_prompt({'stage_skills': [str(skill)]}, inline=True)
            self.assertIn('### 4. 自然剧本', prompt)
            for phrase in ('Premise：明确主角', '标准三分钟短剧', '台词七维', '语速五步'):
                self.assertIn(phrase, prompt)
            self.assertIn('台词七维：角色辨识度', prompt)
            self.assertIn('语速五步：拆句', prompt)
            home = Path(directory) / 'codex-skills'
            result = codex_skill_sync.sync_codex_skills(root.parent, home)
            self.assertEqual(result['written'], ['pipeline-script-preparation'])
            body = (home / 'pipeline-script-preparation/SKILL.md').read_text(encoding='utf-8')
            self.assertIn('### 4. 自然剧本', body)
            self.assertNotIn('jingju-skills', body)

    def test_unregistered_package_edits_do_not_change_api_or_synced_skill(self):
        from orchestrator import codex_skill_sync
        from workflow_settings import _inline_skill
        with tempfile.TemporaryDirectory() as directory:
            root, skill = self._installed_skill(directory)
            reference = root / 'unregistered-package/references/stage-output-contracts.md'
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
    def test_installed_codex_skill_rewrites_generic_references(self):
        from orchestrator import codex_skill_sync
        with tempfile.TemporaryDirectory() as directory:
            root, skill = self._installed_skill(directory)
            reference = root / 'shared-reference' / 'rules.md'
            reference.parent.mkdir()
            reference.write_text('# Rules\n规则', encoding='utf-8')
            with skill.open('a', encoding='utf-8') as stream:
                stream.write('\n[规则](../shared-reference/rules.md#rules)\n')
            home = Path(directory) / 'codex-skills'
            report = codex_skill_sync.sync_codex_skills(root.parent, home)
            self.assertEqual(report['errors'], [])
            body = (home / 'pipeline-script-preparation/SKILL.md').read_text(encoding='utf-8')
            links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', body)
            self.assertEqual(links, [reference.resolve().as_posix() + '#rules'])
            self.assertTrue(Path(links[0].split('#')[0]).is_file())


if __name__ == '__main__':
    unittest.main()
