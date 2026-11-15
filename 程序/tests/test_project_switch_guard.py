# -*- coding: utf-8 -*-
"""侧栏项目切换：必须确认、任务运行中拒绝、取消后高亮回到当前项目。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop
from desktop_project_pages import ProjectPageServices


def make_app(root='D:/p/甲_20260101', projects=None, busy=''):
    app = MagicMock()
    # 页面服务改为注入后，MagicMock 的宿主要带真服务，desktop.confirm 补丁才会生效（R1983 J2，断言未动）。
    app.project_page_services = ProjectPageServices(open_path=lambda *a, **k: desktop.open_path(*a, **k),
        context_menu=lambda *a, **k: desktop.ContextMenu(*a, **k),
        confirm=lambda *a, **k: desktop.confirm(*a, **k))
    app.root = Path(root)
    app.projects.info = {'projects': projects or [
        {'name': '甲', 'path': 'D:/p/甲_20260101'}, {'name': '乙', 'path': 'D:/p/乙_20260102'}]}
    app.worker = busy == 'worker'
    app.idea_chat_controller.requesting = busy == 'chat'
    app.script_agent_processes.return_value = [('k', 'p')] if busy == 'agent' else []
    app.project_switch_blocker = lambda: desktop.Desktop.project_switch_blocker(app)
    app.restore_project_selection = lambda: desktop.Desktop.restore_project_selection(app)
    app._sync_project_picker = lambda **kw: desktop.Desktop._sync_project_picker(app,**kw)
    app._sync_project_group_styles = lambda: desktop.Desktop._sync_project_group_styles(app)
    return app


class ProjectSwitchGuardTests(unittest.TestCase):
    def test_cancel_keeps_project_and_restores_highlight(self):
        app = make_app()
        with patch.object(desktop, 'confirm', return_value=False):
            self.assertFalse(desktop.Desktop.request_project_switch(app, 'D:/p/乙_20260102'))
        app.open_project_or_cleanup.assert_not_called()
        # R2897：高亮＝选择器回到「● 当前项目」；甲是当前项目，应选中第 0 项。
        app.project_picker.current.assert_called_with(0)
        self.assertIn('● 甲', app.project_picker.set_values.call_args.args[0])

    def test_confirm_names_both_projects_then_opens(self):
        app = make_app()
        with patch.object(desktop, 'confirm', return_value=True) as ask:
            desktop.Desktop.request_project_switch(app, 'D:/p/乙_20260102')
        message = ask.call_args.args[2]
        self.assertIn('乙', message)
        self.assertIn('甲', message)
        app.open_project_or_cleanup.assert_called_once_with('D:/p/乙_20260102')

    def test_running_task_blocks_switch_without_asking(self):
        for busy in ('worker', 'chat', 'agent'):
            with self.subTest(busy=busy):
                app = make_app(busy=busy)
                with patch.object(desktop, 'confirm') as ask:
                    with self.assertRaises(ValueError):
                        desktop.Desktop.request_project_switch(app, 'D:/p/乙_20260102')
                ask.assert_not_called()
                app.open_project_or_cleanup.assert_not_called()
                app.project_picker.current.assert_called_with(0)

    def test_current_project_row_is_marked(self):
        app = make_app()
        rows = [desktop.Desktop.project_row_text(app, p) for p in app.projects.info['projects']]
        self.assertTrue(rows[0].startswith('● '))
        self.assertFalse(rows[1].startswith('●'))


if __name__ == '__main__':
    unittest.main()
