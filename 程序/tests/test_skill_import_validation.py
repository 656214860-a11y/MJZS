"""单文件 SKILL 导入在复制前校验并确认。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skill_panel
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
        self.panel.registry._stage_directory_for.return_value = self.target_dir
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
        source = self.root / 'broken.skill.md'
        source.write_text('---\nname: broken\n---\n', encoding='utf-8')
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
