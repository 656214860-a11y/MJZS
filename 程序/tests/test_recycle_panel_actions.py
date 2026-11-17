"""回收站动作通过真实临时目录验证；不创建可见 Tk 窗口。"""
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import infra.storage_maintenance as storage
from agent.core import save
from ui.desktop_project_pages import ProjectPagesMixin


def recycle(root, name='note.md', age=0):
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text('用户内容', encoding='utf-8')
    storage.recycle_paths(root, [path], '测试', now=time.time() - age * 86400)
    return next(storage.recycle_base(root).iterdir())


class Panel(ProjectPagesMixin):
    def __init__(self, project, library):
        self.root = project
        self.projects = SimpleNamespace(base=library, register_restored_projects=Mock())
        self.win = None
        self.status = SimpleNamespace(set=Mock())
        self.project_page_services = SimpleNamespace(confirm=Mock(return_value=True))


class RecyclePanelActionsTests(unittest.TestCase):
    def test_browse_uses_existing_controller_and_keeps_roots_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, library = Path(tmp) / 'project', Path(tmp) / 'library'
            first, second = recycle(project), recycle(library)
            panel = Panel(project, library)
            records = panel.recycle_batches()
            self.assertEqual({r['root'] for r in records}, {project, library})
            record = next(r for r in records if r['root'] == project)
            self.assertEqual(record['batch'], first)
            panel.restore_recycled(record)
            self.assertTrue((project / 'note.md').exists())
            self.assertTrue(second.exists())
            panel.projects.register_restored_projects.assert_not_called()

    def test_purge_requires_two_confirmations_and_cancel_preserves_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = recycle(root)
            panel = Panel(root, None)
            record = panel.recycle_batches()[0]
            panel.project_page_services.confirm.side_effect = [True, False]
            self.assertEqual(panel.purge_recycled([record]), [])
            self.assertTrue(batch.exists())
            self.assertEqual(panel.project_page_services.confirm.call_count, 2)
            panel.project_page_services.confirm.side_effect = [True, True]
            self.assertEqual(panel.purge_recycled([record]), [batch.name])
            self.assertFalse(batch.exists())

    def test_existing_window_buttons_execute_selected_and_all_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, library = Path(tmp) / 'project', Path(tmp) / 'library'
            first, second = recycle(project), recycle(library)
            panel = Panel(project, library)
            panel.safe = lambda action: action()
            panel.reload = Mock()
            trees = [MagicMock(), MagicMock()]
            trees[0].selection.return_value = ('0',)
            buttons = {}
            def button(parent, *, text, command):
                buttons[text] = command
                return MagicMock()
            with patch('ui.desktop_project_pages.BaseDialog', return_value=MagicMock()), \
                 patch('ui.desktop_project_pages.DataTable', side_effect=[SimpleNamespace(tree=t, pack=Mock()) for t in trees]), \
                 patch('ui.desktop_project_pages.auto_height', return_value=Mock()), \
                 patch('ui.desktop_project_pages.ttk.Label'), patch('ui.desktop_project_pages.FlowBar'), \
                 patch('ui.desktop_project_pages.SecondaryButton', side_effect=button):
                panel.open_recycle_recovery()
                buttons['永久清空选中批次']()
                self.assertEqual(sum(p.exists() for p in (first, second)), 1)
                buttons['永久清空全部批次']()
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())
            self.assertEqual(panel.project_page_services.confirm.call_count, 4)

    def test_partial_purge_failure_reports_failure_without_touching_other_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, library = Path(tmp) / 'project', Path(tmp) / 'library'
            first, second = recycle(project), recycle(library)
            panel = Panel(project, library)
            record = next(r for r in panel.recycle_batches() if r['root'] == project)
            with patch.object(storage.shutil, 'rmtree', side_effect=OSError('busy')):
                with self.assertRaises(OSError):
                    panel.purge_recycled([record])
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertIn('未全部完成', panel.status.set.call_args.args[0])

    def test_corrupt_manifest_blocks_purge_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = recycle(root)
            (batch / '恢复位置.json').write_text('{bad', encoding='utf-8')
            panel = Panel(root, None)
            record = panel.recycle_batches()[0]
            self.assertTrue(record['unavailable'])
            for action in (lambda: panel.purge_recycled([record]), lambda: panel.restore_recycled(record)):
                with self.assertRaises(ValueError):
                    action()
            self.assertTrue(batch.exists())

    def test_expired_action_is_explicit_and_reads_saved_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, library = Path(tmp) / 'project', Path(tmp) / 'library'
            batch = recycle(root, age=40)
            library_batch = recycle(library, age=40)
            panel = Panel(root, library)
            storage.save_recycle_retention_days(root, 0)
            self.assertEqual(panel.purge_expired_recycle(), [])
            self.assertTrue(batch.exists())
            panel.project_page_services.confirm.assert_not_called()
            storage.save_recycle_retention_days(root, 30)
            self.assertEqual(set(panel.purge_expired_recycle()), {batch.name, library_batch.name})
            self.assertFalse(library_batch.exists())
            self.assertEqual(panel.project_page_services.confirm.call_count, 2)

    def test_settings_cancel_or_save_does_not_purge_or_show_extra_dialog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = recycle(root, age=90)
            panel = Panel(root, None)
            with patch('ui.desktop_project_pages.ask_string', return_value='12'):
                self.assertEqual(panel.configure_recycle_retention(), 12)
            self.assertEqual(storage.recycle_retention_days(root), 12)
            self.assertTrue(batch.exists())
            panel.project_page_services.confirm.assert_not_called()
            with patch('ui.desktop_project_pages.ask_string', return_value=None):
                self.assertIsNone(panel.configure_recycle_retention())


if __name__ == '__main__':
    unittest.main()
