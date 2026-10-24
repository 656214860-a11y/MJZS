"""剧本准备页服务可独立注入，不依赖 Desktop 全局宿主（R1988，J2）。"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_writing_page import WritingPageServices, _WritingPage


def _page(services, **kwargs):
    host = SimpleNamespace(win=object(), writing_page_services=services, **kwargs)
    page = _WritingPage.__new__(_WritingPage)
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
        with patch('desktop_page_support._host', None):
            page.confirm_document('剧本大纲')
        services.confirm.assert_called_once()
        self.assertEqual(services.confirm.call_args.args[0], page.page.win)

    def test_open_script_file_uses_injected_open_path(self):
        services = self.services()
        page = _page(services)
        with patch('desktop_page_support._host', None):
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
        with patch('desktop_page_support._host', None):
            page.script_menu(tree, SimpleNamespace(y=0))
        services.context_menu.assert_called_once_with(page.page.win)

    def test_last_script_removal_asks_injected_gate(self):
        services = self.services()
        services.confirm_project_removal.return_value = False
        page = _page(services, root=Path('p'))
        page.selected_script = Mock(return_value=Path('only.md'))
        page.all_script_items = Mock(return_value=['only.md'])
        with patch('desktop_page_support._host', None):
            page.delete_script()
        services.confirm_project_removal.assert_called_once_with(page.page.win, ['only.md'])


if __name__ == '__main__':
    unittest.main()
