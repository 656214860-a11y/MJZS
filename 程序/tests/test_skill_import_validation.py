"""单文件 SKILL 导入在复制前校验并确认。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_panel
import skill_import_service
import skill_registry
from test_skills import write_skill


class SkillImportValidationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target_dir = self.root / 'target' / '01剧本准备SKILL'
        self.panel = mock.Mock()
        self.panel.stage = 'script'
        self.panel.registry.user_stage_directory_for.return_value = self.target_dir
        self.panel.registry.getAll.return_value = [skill_registry.Skill({'name': 'known'})]
        self.panel.registry.getByStage.return_value = []
        self.panel.skill_content.winfo_children.return_value = []

    def run_import(self, source, accept=False):
        with mock.patch.object(skill_panel, 'FileDialog') as dialog, \
                mock.patch.object(skill_panel, 'confirm', return_value=accept) as confirm:
            dialog.return_value.open_file.return_value = str(source)
            result = skill_panel.Panel.add_skill_from_file(self.panel)
        return result, confirm

    def test_cancel_combined_field_stage_and_overwrite_warning_preserves_file(self):
        source = self.root / 'broken.skill.md'
        source.write_text('---\nname: broken\nstage: keyframe\n---\n', encoding='utf-8')
        self.target_dir.mkdir(parents=True)
        target = self.target_dir / source.name
        target.write_bytes(b'original')
        result, confirm = self.run_import(source)
        self.assertIsNone(result)
        confirm.assert_called_once()
        message = confirm.call_args.args[2]
        for fragment in ('缺字段', '与本阶段不一致', '已存在', '继续将覆盖'):
            self.assertIn(fragment, message)
        self.assertTrue(confirm.call_args.kwargs['dangerous'])
        self.assertEqual(target.read_bytes(), b'original')
        self.panel.registry.scan.assert_not_called()
        self.panel.build_flow_skill.assert_not_called()

    def test_confirm_allows_invalid_manifest_copy(self):
        # R1432：正文为空的清单发送时必被拦，导入同样硬拦（见 test_empty_body_is_blocked_even_after_confirm）；
        # 这里保留「字段不全但有正文，确认后可导入」的原断言。
        source = self.root / 'broken.skill.md'
        source.write_text('---\nname: broken\n---\n# 正文\n', encoding='utf-8')
        result, confirm = self.run_import(source, accept=True)
        confirm.assert_called_once()
        self.assertEqual(result.read_bytes(), source.read_bytes())
        self.panel.registry.scan.assert_called_once_with(force=True)

    def test_valid_manifest_with_known_conflict_needs_no_confirmation(self):
        source = write_skill(self.root / 'source', 'valid', conflicts='known')
        result, confirm = self.run_import(source)
        confirm.assert_not_called()
        self.assertEqual(result.read_bytes(), source.read_bytes())

    def test_package_uses_light_name_validation_and_cancellation_creates_nothing(self):
        source = self.root / 'external' / 'SKILL.md'
        source.parent.mkdir()
        source.write_text('---\nname: external\n---\n没有标题', encoding='utf-8')
        result, confirm = self.run_import(source)
        self.assertIsNone(result)
        self.assertIn('未找到可显示的技能名称', confirm.call_args.args[2])
        self.assertFalse(self.target_dir.exists())
        self.panel.registry.scan.assert_not_called()
        source.write_text('---\nname: external\n---\n# 外部包标题\n', encoding='utf-8')
        result, confirm = self.run_import(source)
        confirm.assert_not_called()
        self.assertEqual(result, self.target_dir / 'external' / 'SKILL.md')
        self.assertEqual(result.read_bytes(), source.read_bytes())

    def test_unreadable_source_does_not_copy_or_scan(self):
        source = self.root / 'invalid.skill.md'
        for content in (None, b'\xff\xfe\xff'):
            with self.subTest(content=content):
                if content is not None:
                    source.write_bytes(content)
                result, confirm = self.run_import(source)
                self.assertIsNone(result)
                confirm.assert_not_called()
                self.assertIn('读不出源文件', self.panel.state.configure.call_args.kwargs['text'])
                self.assertFalse(self.target_dir.exists())
                self.panel.registry.scan.assert_not_called()


class StableImportTests(unittest.TestCase):
    """R1432：整包导入、重名硬拦、试冻结失败撤回、覆盖时旧版进回收站、导入台账。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program = self.root / 'program'
        self.target_dir = self.program / 'skills' / '01剧本准备SKILL'
        self.panel = mock.Mock()
        self.panel.stage = 'script'
        self.panel.registry.user_stage_directory_for.return_value = self.target_dir
        self.panel.registry.getAll.return_value = []
        self.panel.registry.getByStage.return_value = []
        self.panel.skill_content.winfo_children.return_value = []

    def run_import(self, source, accept=False):
        with mock.patch.object(skill_panel, 'FileDialog') as dialog, \
                mock.patch.object(skill_panel, 'confirm', return_value=accept) as confirm:
            dialog.return_value.open_file.return_value = str(source)
            result = skill_panel.Panel.add_skill_from_file(self.panel)
        return result, confirm

    def state_text(self):
        return self.panel.state.configure.call_args.kwargs['text']

    def package(self, name='外部包', reference='references/rules.md', body='规则正文'):
        folder = self.root / 'download' / name
        (folder / 'references').mkdir(parents=True)
        (folder / '.git').mkdir()
        (folder / '.git' / 'HEAD').write_text('ref', encoding='utf-8')
        (folder / 'references' / 'rules.md').write_text(body, encoding='utf-8')
        (folder / 'SKILL.md').write_text('---\nname: ext-pack\n---\n# 外部包\n见 [规则](%s)\n' % reference,
                                         encoding='utf-8')
        return folder / 'SKILL.md'

    def test_package_import_brings_references_and_skips_git(self):
        source = self.package()
        result, confirm = self.run_import(source)
        confirm.assert_not_called()
        self.assertEqual(result, self.target_dir / '外部包' / 'SKILL.md')
        self.assertEqual((self.target_dir / '外部包' / 'references' / 'rules.md').read_text(encoding='utf-8'), '规则正文')
        self.assertFalse((self.target_dir / '外部包' / '.git').exists())
        self.assertEqual([p.name for p in self.target_dir.iterdir()], ['外部包'], '暂存目录不得留在阶段目录里')
        ledger = skill_import_service.read_json(skill_import_service.ledger_path(self.program))
        row = ledger['items']['01剧本准备SKILL/外部包']
        self.assertEqual((row['kind'], row['name'], row['source']), ('package', 'ext-pack', str(source.parent)))
        self.assertEqual(len(row['sha256']), 64)
        self.assertIn('整包导入', self.state_text())

    def test_broken_reference_is_rolled_back_without_leftovers(self):
        source = self.package(reference='references/missing.md')
        result, confirm = self.run_import(source, accept=True)
        self.assertIsNone(result)
        self.assertIn('试冻结失败', self.state_text())
        self.assertIn('引用缺失', self.state_text())
        self.assertEqual(list(self.target_dir.iterdir()), [])
        self.panel.registry.scan.assert_not_called()
        self.assertFalse((skill_import_service.ledger_path(self.program)).exists())

    def test_failed_update_restores_the_previous_version(self):
        good = self.package()
        self.run_import(good)
        (good.parent / 'SKILL.md').write_text('---\nname: ext-pack\n---\n# 外部包\n见 [规则](references/gone.md)\n',
                                             encoding='utf-8')
        self.panel.registry.getAll.return_value = [
            skill_registry.Skill({'name': 'ext-pack'}, '', path=self.target_dir / '外部包' / 'SKILL.md')]
        result, confirm = self.run_import(good, accept=True)
        self.assertIsNone(result)
        self.assertIn('继续将覆盖', confirm.call_args.args[2])
        restored = (self.target_dir / '外部包' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('references/rules.md', restored, '试冻结失败后必须恢复旧版')

    def test_overwrite_moves_previous_version_to_recycle_bin(self):
        source = self.root / 'lead.skill.md'
        write = lambda text: source.write_text('---\nname: lead\n---\n# %s\n' % text, encoding='utf-8')
        write('旧版')
        self.run_import(source, accept=True)
        write('新版')
        self.panel.registry.getAll.return_value = [
            skill_registry.Skill({'name': 'lead'}, '', path=self.target_dir / 'lead.skill.md')]
        result, confirm = self.run_import(source, accept=True)
        self.assertIn('新版', result.read_text(encoding='utf-8'))
        recycled = list((self.program / '工作流任务' / '回收站').rglob('lead.skill.md'))
        self.assertEqual(len(recycled), 1)
        self.assertIn('旧版', recycled[0].read_text(encoding='utf-8'))

    def test_duplicate_name_elsewhere_is_blocked_before_any_copy(self):
        other = self.program / 'skills' / '02 剧本整理SKILL' / 'lead.skill.md'
        self.panel.registry.getAll.return_value = [skill_registry.Skill({'name': 'lead'}, '', path=other)]
        source = self.root / 'lead.skill.md'
        source.write_text('---\nname: lead\n---\n# 正文\n', encoding='utf-8')
        result, confirm = self.run_import(source, accept=True)
        self.assertIsNone(result)
        confirm.assert_not_called()
        self.assertIn('重名', self.state_text())
        self.assertFalse(self.target_dir.exists())

    def test_empty_body_is_blocked_even_after_confirm(self):
        source = self.root / 'empty.skill.md'
        source.write_text('---\nname: empty\n---\n', encoding='utf-8')
        result, confirm = self.run_import(source, accept=True)
        self.assertIsNone(result)
        self.assertIn('内容为空', self.state_text())
        self.assertEqual(list(self.target_dir.iterdir()), [])
