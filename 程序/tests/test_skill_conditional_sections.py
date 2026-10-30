# -*- coding: utf-8 -*-
"""REQ-S01-73：SKILL 引用按制作锁跳过不适用的引擎、带锚点的引用只内联该节；门禁核验不跳过。"""
import tempfile
import unittest
from pathlib import Path

import workflow_settings

SKILL = ('---\nname: sample\n---\n'
         '- 先读 [决策](engine.md#四工作流程)。\n'
         '- 仅 `track` 为海外剧时追加 [海外](overseas.md#执行规则)；'
         '仅 `track` 为解说叙事类时追加 [旁白](voice.md)。\n'
         '- 仅 `material_source` 为对标爆款／热点速成时追加 [采风](recon.md)，证据随简报交接。\n'
         '- 再读 [缺锚](engine.md#不存在的节)。\n')
ENGINE = ('# 引擎\n开头说明\n'
          '## 三、准备\n准备正文\n'
          '## 四、工作流程\n流程正文\n```\n# 代码里的井号不是标题\n```\n'
          '### 4.1 细则\n细则正文\n'
          '## 五、交付\n交付正文\n')


class SkillSlimTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / 'skills'
        root.mkdir()
        self.skill = root / 'SKILL.md'
        self.skill.write_text(SKILL, encoding='utf-8')
        (root / 'engine.md').write_text(ENGINE, encoding='utf-8')
        (root / 'overseas.md').write_text('# 海外\n## 执行规则\n海外规则正文\n## 其他\n海外其他正文\n', encoding='utf-8')
        (root / 'voice.md').write_text('旁白全文', encoding='utf-8')
        (root / 'recon.md').write_text('采风全文', encoding='utf-8')

    def report(self, locks):
        body, closure = workflow_settings._inline_skill_report(self.skill, strict=True, locks=locks)
        return body, [(row['target'], row['status']) for row in closure if row['depth'] == 1]

    def test_req_s01_73_unmet_lock_conditions_are_not_inlined(self):
        body, rows = self.report({'track': '国内剧', 'material_source': '原创'})
        self.assertNotIn('海外规则正文', body)
        self.assertNotIn('旁白全文', body)
        self.assertNotIn('采风全文', body)
        self.assertEqual(rows[1:4], [('overseas.md#执行规则', 'conditional'), ('voice.md', 'conditional'),
                                     ('recon.md', 'conditional')])

    def test_req_s01_73_met_or_empty_lock_conditions_are_inlined(self):
        body, rows = self.report({'track': '海外剧', 'material_source': '热点速成（给方向先找选题）'})
        self.assertIn('海外规则正文', body)
        self.assertNotIn('海外其他正文', body)
        self.assertNotIn('旁白全文', body)
        self.assertIn('采风全文', body)
        body, _rows = self.report({})
        for text in ('海外规则正文', '旁白全文', '采风全文'):
            self.assertIn(text, body)

    def test_req_s01_73_anchor_inlines_only_that_section_and_missing_anchor_falls_back(self):
        body, rows = self.report({'track': '国内剧', 'material_source': '原创'})
        self.assertEqual(rows[0], ('engine.md#四工作流程', 'section'))
        section = body.split('## 引用: engine.md#四工作流程（节选）\n', 1)[1].split('\n\n## 引用:', 1)[0]
        self.assertIn('流程正文', section)
        self.assertIn('# 代码里的井号不是标题', section)
        self.assertIn('细则正文', section)
        self.assertNotIn('准备正文', section)
        self.assertNotIn('交付正文', section)
        # 锚点找不到：整份内联，与改动前一致。
        self.assertEqual(rows[4], ('engine.md#不存在的节', 'inlined'))
        self.assertIn('## 引用: engine.md\n' + ENGINE, body)

    def test_req_s01_73_master_gate_validation_skips_nothing(self):
        _text, _meta, _blocks, closure = workflow_settings._skill_blocks(self.skill, strict=True)
        self.assertNotIn('conditional', [row['status'] for row in closure])
        (self.skill.parent / 'voice.md').unlink()
        with self.assertRaises(ValueError):
            workflow_settings._skill_blocks(self.skill, strict=True)
        # 发送时条件不满足的引用不读，缺了也不阻断。
        workflow_settings._skill_blocks(self.skill, strict=True, locks={'track': '国内剧'})


if __name__ == '__main__':
    unittest.main()
