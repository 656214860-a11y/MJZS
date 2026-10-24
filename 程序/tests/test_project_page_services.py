"""项目页与创意对话菜单的服务可独立注入，不依赖 Desktop 全局宿主（R1983 J2 第三页）。"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_idea_menus import IdeaMenusMixin
from desktop_project_pages import ProjectPageServices, ProjectPagesMixin


def _services():
    return ProjectPageServices(open_path=Mock(), context_menu=Mock(), confirm=Mock(return_value=True))


class ProjectPageServicesTests(unittest.TestCase):
    def test_services_are_immutable(self):
        with self.assertRaises(Exception):
            _services().confirm = None

    def test_request_project_switch_uses_injected_confirm(self):
        services = _services()
        services.confirm.return_value = False
        host = SimpleNamespace(
            project_page_services=services, win=object(), root=None, status=Mock(),
            projects=SimpleNamespace(info={'projects': [{'name': '乙', 'path': 'p/乙'}]}),
            project_switch_blocker=lambda: '', restore_project_selection=Mock())
        self.assertFalse(ProjectPagesMixin.request_project_switch(host, 'p/乙'))
        self.assertEqual(services.confirm.call_args.args[:2], (host.win, '切换项目'))
        host.restore_project_selection.assert_called_once_with()

    def test_open_current_project_uses_injected_open_path(self):
        services = _services()
        host = SimpleNamespace(project_page_services=services, root=Path('proj'))
        ProjectPagesMixin.open_current_project(host)
        services.open_path.assert_called_once_with(Path('proj'))

    def test_project_menu_uses_injected_context_menu(self):
        services = _services()
        item = {'name': '甲', 'path': 'p/甲'}
        tree = SimpleNamespace(identify_row=lambda y: 'p/甲')
        host = SimpleNamespace(project_page_services=services, win=object(), worker=False, list=tree,
                               projects=SimpleNamespace(info={'projects': [item]}), safe=Mock())
        try:
            ProjectPagesMixin.project_menu(host, SimpleNamespace(y=0, x_root=0, y_root=0))
        except Exception:
            pass  # 菜单本身是 Mock，后续弹出细节不在本用例范围
        services.context_menu.assert_called_once_with(host.win)

    def test_idea_attachment_delete_asks_injected_confirm(self):
        services = _services()
        services.confirm.return_value = False
        path = Path('a.md')
        host = SimpleNamespace(project_page_services=services, win=object(),
                               _idea_uploaded_paths={'i': path}, _idea_uploaded_selected={path})
        with patch('idea_attachments.display_name', return_value='a'):
            IdeaMenusMixin.delete_uploaded_idea_attachment(host)
        self.assertEqual(services.confirm.call_args.args[:2], (host.win, '删除附件'))


if __name__ == '__main__':
    unittest.main()
