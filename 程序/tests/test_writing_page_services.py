"""剧本准备页服务可独立注入，不依赖 Desktop 全局宿主（R1988，J2）。"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_files_panel import ProjectFilesPanel
from desktop_writing_page import WritingPageServices


def _page(services, **kwargs):
    host = SimpleNamespace(win=object(), writing_page_services=services, **kwargs)
    page = ProjectFilesPanel.__new__(ProjectFilesPanel)
    page.page = host
    return page


class WritingPageServicesTests(unittest.TestCase):
    def services(self):
        return WritingPageServices(open_path=Mock(), context_menu=Mock(), confirm=Mock(return_value=True),
                                   confirm_project_removal=Mock(return_value=True))

    def test_services_are_immutable(self):
        with self.assertRaises(Exception):
            self.services().confirm = None

    def test_confirm_document_uses_injected_confirm_without_global_host(self):
        services = self.services()
        services.confirm.return_value = False
        page = _page(services, root=Path('p'))
        page.selected_script = Mock(return_value=Path('a.md'))
        page.confirm_document('剧本大纲')
        services.confirm.assert_called_once()
        self.assertEqual(services.confirm.call_args.args[0], page.page.win)

    def test_open_script_file_uses_injected_open_path(self):
        services = self.services()
        page = _page(services)
        page.current_script_tree = Mock(return_value=SimpleNamespace(selection=lambda: ('x.md',)))
        with patch.object(Path, 'is_file', return_value=True):
            page.open_script_file()
        services.open_path.assert_called_once_with(Path('x.md'))

    def test_script_menu_uses_injected_context_menu(self):
        services = self.services()
        page = _page(services, safe=lambda call: call())
        page.script_row_category = {'r': 'script'}
        page.keep_one_selection = Mock()
        tree = Mock()
        tree.identify_row.return_value = 'r'
        tree.selection.return_value = ('r',)
        page.script_menu(tree, SimpleNamespace(y=0))
        services.context_menu.assert_called_once_with(page.page.win)

    def test_last_script_removal_recycles_selected_file_without_project_removal(self):
        from script_workspace_service import ScriptDeletionSelection
        services = self.services()
        services.confirm_project_removal.return_value = False
        page = _page(services, root=Path('p'), status=Mock())
        page.selected_scripts = Mock(return_value=ScriptDeletionSelection(paths=(Path('only.md'),), deletes_all=True))
        page.confirmed_note = Mock(return_value='')
        page.fill_script_list = Mock()
        with patch('storage_maintenance.recycle_paths', return_value=[{}]) as recycle:
            page.delete_script()
        services.confirm_project_removal.assert_not_called()
        services.confirm.assert_called_once()
        self.assertIn('确定将 only.md 移入项目回收站吗？', services.confirm.call_args.args[2])
        recycle.assert_called_once_with(Path('p'), [Path('only.md')], '删除项目剧本')
        page.fill_script_list.assert_called_once()
        page.page.status.set.assert_called_once_with('已移入回收站：only.md')

    def test_multi_selected_rows_offer_only_delete_and_recycle_together(self):
        """REQ-S01-76：Ctrl／Shift 多选后右键只给「删除」，确认一次把选中的几份一起移入回收站；右键别的行改选那一行。"""
        import tempfile
        from contract import project_stages
        services = self.services()
        with tempfile.TemporaryDirectory() as td:
            folder = project_stages.writing(Path(td)) / '创意_20261101' / '项目剧本'
            folder.mkdir(parents=True)
            files = [folder / name for name in ('一.md', '二.md', '三.md')]
            for path in files:
                path.write_text('正文', encoding='utf-8')
            page = _page(services, root=Path(td), safe=lambda call: call(), status=Mock())
            page.script_row_category = {}
            page.fill_script_list = Mock()
            tree = Mock()
            tree.get_children.return_value = tuple(str(path) for path in files)
            tree.selection.return_value = (str(files[0]), str(files[2]))
            tree.identify_row.return_value = str(files[0])
            page.script_tree = tree
            page.script_menu(tree, SimpleNamespace(y=0))
            tree.selection_set.assert_not_called()
            menu = services.context_menu.return_value
            self.assertEqual([call.args[0] for call in menu.command.call_args_list], ['删除'])
            with patch('storage_maintenance.recycle_paths', side_effect=lambda root, items, reason: list(items)) as recycle:
                menu.command.call_args.args[1]()
            services.confirm.assert_called_once()
            self.assertIn('确定将选中的 2 份剧本文件移入项目回收站吗？', services.confirm.call_args.args[2])
            services.confirm_project_removal.assert_not_called()
            self.assertEqual(recycle.call_args.args,
                             (Path(td), [files[0].resolve(), files[2].resolve()], '批量删除项目剧本'))
            page.fill_script_list.assert_called_once()
            page.page.status.set.assert_called_once_with('已移入回收站 2 份剧本文件')
            menu.command.reset_mock()
            tree.identify_row.return_value = str(files[1])
            tree.selection_set.side_effect = lambda row: setattr(tree.selection, 'return_value', (row,))
            page.script_menu(tree, SimpleNamespace(y=0))
            tree.selection_set.assert_called_once_with(str(files[1]))
            # R3200 M5：剧本行右键新增「在文件夹中显示」「另存为…」，其余动作与顺序不变。
            self.assertEqual([call.args[0] for call in menu.command.call_args_list],
                             ['查看', '添加到全局素材库', '重命名', '采用此剧本', '在文件夹中显示', '另存为…', '删除'])


if __name__ == '__main__':
    unittest.main()
