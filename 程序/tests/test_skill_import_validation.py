"""单文件 SKILL 导入在复制前校验并确认。"""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import skill_panel
import skill_panel_import
import skill_import_service
import skill_registry
from skip_reasons import PLATFORM_SYMLINK
from test_skills import SKILL_TEMPLATE, write_skill


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
        with mock.patch.object(skill_panel_import, 'FileDialog') as dialog, \
                mock.patch.object(skill_panel_import, 'confirm', return_value=accept) as confirm:
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
        with mock.patch.object(skill_panel_import, 'FileDialog') as dialog, \
                mock.patch.object(skill_panel_import, 'confirm', return_value=accept) as confirm:
            dialog.return_value.open_file.return_value = str(source)
            result = skill_panel.Panel.add_skill_from_file(self.panel)
        return result, confirm

    def _replacement_plan(self):
        from agent import publication
        self.enterContext(mock.patch.object(publication, 'ROOT', self.root / 'transactions'))
        source = write_skill(self.root / 'source', 'lead', conflicts='known')
        plan = skill_import_service.plan_import(source, self.target_dir, 'script', self.panel.registry)
        skill_import_service.perform_import(plan, self.program)
        plan['target'].write_text('old', encoding='utf-8')
        return plan

    def test_record_failure_restores_previous_skill_and_allows_retry(self):
        plan = self._replacement_plan()
        ledger = skill_import_service.ledger_path(self.program)
        previous = ledger.read_bytes()
        record = skill_import_service.record

        def fail_after_write(*args, **kwargs):
            record(*args, **kwargs)
            raise OSError('record failed after write')

        with mock.patch.object(skill_import_service, 'record', side_effect=fail_after_write):
            with self.assertRaisesRegex(OSError, 'record failed'):
                skill_import_service.perform_import(plan, self.program, now=123)
        self.assertEqual(plan['target'].read_text(encoding='utf-8'), 'old')
        self.assertEqual(ledger.read_bytes(), previous)
        skill_import_service.perform_import(plan, self.program)
        self.assertEqual(len(skill_import_service.ledger_items(self.program)), 1)

    def test_forget_failure_restores_skill_and_allows_retry(self):
        plan = self._replacement_plan()
        skill = mock.Mock(path=plan['target'])
        skill.name = plan['name']
        skill.get.return_value = False
        self.panel.registry.getAll.return_value = [skill]
        with mock.patch.object(skill_import_service, 'forget_ledger_targets',
                               side_effect=PermissionError('forget failed')):
            with self.assertRaisesRegex(skill_import_service.ImportBlocked, 'forget failed'):
                skill_import_service.uninstall_skill(self.program, self.panel.registry, plan['name'])
        self.assertEqual(plan['target'].read_text(encoding='utf-8'), 'old')
        skill_import_service.uninstall_skill(self.program, self.panel.registry, plan['name'])
        self.assertFalse(plan['target'].exists())
        self.assertEqual(skill_import_service.ledger_items(self.program), {})
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service.uninstall_skill(self.program, self.panel.registry, plan['name'])

    def test_failed_restore_leaves_old_skill_queryable_and_retriable(self):
        from ui import skill_install_recovery
        plan = self._replacement_plan()
        with (mock.patch.object(skill_import_service, 'record', side_effect=OSError('record failed')),
              mock.patch.object(skill_install_recovery, 'restore_recycle_batch',
                                side_effect=PermissionError('restore failed')) as restore):
            with self.assertRaisesRegex(skill_import_service.ImportBlocked,
                                       'record failed.*restore failed') as caught:
                skill_import_service.perform_import(plan, self.program)
        self.assertIsInstance(caught.exception.__cause__, OSError)
        batch = restore.call_args.args[1]
        self.assertIn(str(batch), str(caught.exception))
        self.assertFalse(plan['target'].exists())
        self.assertTrue((batch / '恢复位置.json').is_file())
        skill_install_recovery.restore_recycle_batch(self.program, batch)
        self.assertEqual(plan['target'].read_text(encoding='utf-8'), 'old')

    def test_ledger_recovery_failure_retries_on_next_access(self):
        from agent import publication
        plan = self._replacement_plan()
        ledger = skill_import_service.ledger_path(self.program)
        previous = ledger.read_bytes()
        record = skill_import_service.record

        def fail_after_write(*args, **kwargs):
            record(*args, **kwargs)
            raise OSError('record failed')

        with (mock.patch.object(skill_import_service, 'record', side_effect=fail_after_write),
              mock.patch.object(publication, '_copy', side_effect=PermissionError('ledger restore failed'))):
            with self.assertRaisesRegex(skill_import_service.ImportBlocked,
                                       'record failed.*ledger restore failed') as caught:
                skill_import_service.perform_import(plan, self.program, now=123)
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertEqual(plan['target'].read_text(encoding='utf-8'), 'old')
        skill_import_service.ledger_items(self.program)
        self.assertEqual(ledger.read_bytes(), previous)

    def test_interrupt_after_swap_restores_original_scope_without_ui_callback(self):
        plan = self._replacement_plan()
        later = self.root / 'later-project'
        later.mkdir()
        other = later / plan['target'].name
        other.write_text('other project', encoding='utf-8')

        def interrupt(*args):
            self.panel.registry.project_root = later
            self.panel.winfo_exists.return_value = False
            raise KeyboardInterrupt

        with mock.patch.object(skill_import_service, '_verify', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                skill_import_service.perform_import(plan, self.program)
        self.assertEqual(plan['target'].read_text(encoding='utf-8'), 'old')
        self.assertEqual(other.read_text(encoding='utf-8'), 'other project')
        self.panel.registry.scan.assert_not_called()

    def test_record_failure_preserves_user_replacement_and_reports_recovery_location(self):
        plan = self._replacement_plan()

        def replace_target(*args, **kwargs):
            path = plan['target']
            replacement = path.with_name('user-edit.tmp')
            replacement.write_text('user edit', encoding='utf-8')
            replacement.replace(path)
            raise OSError('record failed')

        with mock.patch.object(skill_import_service, 'record', side_effect=replace_target):
            with self.assertRaisesRegex(skill_import_service.ImportBlocked, 'record failed.*回收') as caught:
                skill_import_service.perform_import(plan, self.program)
        self.assertEqual(plan['target'].read_text(encoding='utf-8'), 'user edit')
        self.assertIsInstance(caught.exception.__cause__, OSError)

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

class SkillImportBoundsTests(unittest.TestCase):
    """R2555 批次：导入体积与符号链接护栏。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target_dir = self.root / 'target' / '01剧本准备SKILL'
        self.registry = skill_registry.Registry.__new__(skill_registry.Registry)

    def _package(self):
        package = self.root / 'pkg'
        package.mkdir()
        (package / 'SKILL.md').write_text('---\nname: pkg\n---\n# 正文\n', encoding='utf-8')
        return package

    def test_package_with_symlink_is_blocked(self):
        package = self._package()
        outside = self.root / 'outside.txt'
        outside.write_text('secret', encoding='utf-8')
        link = package / 'leak.txt'
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest(PLATFORM_SYMLINK)
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_import_service._check_package_bounds(package)

    def test_package_over_file_count_is_blocked(self):
        package = self._package()
        with mock.patch.object(skill_import_service, 'PACKAGE_MAX_FILES', 1):
            skill_import_service._check_package_bounds(package)  # 仅 SKILL.md，不超限
            (package / 'a.txt').write_text('x', encoding='utf-8')
            with self.assertRaises(skill_import_service.ImportBlocked):
                skill_import_service._check_package_bounds(package)

    def test_single_manifest_over_size_is_blocked_before_read(self):
        source = self.root / 'big.skill.md'
        source.write_bytes(b'x' * 16)
        with mock.patch.object(skill_import_service, 'SINGLE_MAX_BYTES', 8):
            with self.assertRaises(skill_import_service.ImportBlocked):
                skill_import_service.plan_import(source, self.target_dir, 'script', self.registry)

    def test_normal_package_passes_bounds(self):
        package = self._package()
        skill_import_service._check_package_bounds(package)  # 不抛即过


class _QueuedDesktop:
    """``async_queued`` 替身：像 Desktop 一样把 fn 放上工作线程，done 留在调用方线程回调。"""

    def __init__(self):
        self.root = None
        self.submitted = []
        self.errors = []

    def async_queued(self, fn, done=None, label=None, show_progress=True, retryable=False):
        self.submitted.append({'fn': fn, 'done': done, 'label': label,
                               'retryable': retryable})
        box = {}

        def run():
            try:
                box['value'] = fn()
            except Exception as exc:
                box['error'] = exc

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(30)
        self.errors.extend(box.get('error') for _ in [0] if 'error' in box)
        if 'error' not in box and done is not None:
            done(box.get('value'))
        return len(self.submitted)


class SkillImportAuditFixTests(unittest.TestCase):
    """AUD-SKILL D5/D6：非 SKILL 清单硬拒、更新体检不占界面线程。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target_dir = self.root / 'target' / '01剧本准备SKILL'
        self.panel = mock.Mock()
        self.panel.stage = 'script'
        self.panel.registry.user_stage_directory_for.return_value = self.target_dir
        self.panel.registry.getAll.return_value = []
        self.panel.registry.getByStage.return_value = []
        self.panel.skill_content.winfo_children.return_value = []

    def run_import(self, source, accept=False):
        with mock.patch.object(skill_panel_import, 'FileDialog') as dialog, \
                mock.patch.object(skill_panel_import, 'confirm', return_value=accept) as confirm:
            dialog.return_value.open_file.return_value = str(source)
            result = skill_panel.Panel.add_skill_from_file(self.panel)
        return result, confirm

    def state_text(self):
        return self.panel.state.configure.call_args.kwargs['text']

    def test_non_skill_manifest_is_rejected_before_copy(self):
        """「全部文件」选中的 .txt 不是 SKILL 清单：复制前硬拒，不再提示新增成功。"""
        source = self.root / 'notes.txt'
        source.write_text(SKILL_TEMPLATE % {'name': 'notes.txt', 'display': '记事',
                                            'stage': 'script', 'tool': '', 'depends': '',
                                            'conflicts': '', 'paid': 'false'},
                          encoding='utf-8')
        result, confirm = self.run_import(source)
        self.assertIsNone(result)
        confirm.assert_not_called()
        self.assertIn('不是 SKILL 清单', self.state_text())
        self.assertIn('skill.md', self.state_text())
        self.assertFalse((self.target_dir / 'notes.txt').exists())
        self.panel.registry.scan.assert_not_called()

    def _update_panel(self):
        desktop = _QueuedDesktop()
        panel = mock.Mock()
        panel.stage = 'script'
        panel.desktop = desktop
        panel.registry = mock.Mock()
        return panel, desktop

    def test_check_updates_probes_on_background_thread(self):
        """「检查更新」的克隆／下载体检必须在后台线程跑，结果回界面线程再开窗。"""
        panel, desktop = self._update_panel()
        seen = []

        def fake_check(program, *, probe=None, project=None):
            seen.append(threading.current_thread())
            return {}

        with mock.patch.object(skill_import_service, 'check_updates',
                               side_effect=fake_check), \
                mock.patch.object(skill_import_service, 'ledger_items', return_value={}):
            skill_panel.Panel.check_skill_updates(panel)
        self.assertTrue(desktop.submitted, '体检应提交到桌面后台队列而不是界面线程同步跑')
        self.assertEqual(len(seen), 1)
        self.assertIsNot(seen[0], threading.current_thread(),
                         'check_updates 必须在工作线程执行')
        self.assertFalse(desktop.errors)
        self.assertIn('没有导入记录',
                      panel.state.configure.call_args.kwargs['text'])

    def test_check_updates_failure_still_reports_on_state(self):
        """后台体检异常仍落在状态行（与同步路径同一文案），不丢反馈。"""
        panel, desktop = self._update_panel()
        with mock.patch.object(skill_import_service, 'check_updates',
                               side_effect=RuntimeError('boom')), \
                mock.patch.object(skill_import_service, 'ledger_items', return_value={}):
            skill_panel.Panel.check_skill_updates(panel)
        text = panel.state.configure.call_args.kwargs['text']
        self.assertIn('SKILL 更新检查失败', text)
        self.assertIn('boom', text)
