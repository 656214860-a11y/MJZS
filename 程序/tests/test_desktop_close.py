import types
import unittest
from unittest.mock import patch

import desktop


class DesktopCloseTests(unittest.TestCase):
    def test_busy_close_restores_main_before_showing_confirmation(self):
        calls = []
        host = types.SimpleNamespace(
            _closing=False,
            busy_reason=lambda: '后台任务仍在运行',
            pet=types.SimpleNamespace(show_main=lambda: calls.append('restore')),
            force_quit=lambda: calls.append('force_quit'),
            win=object(),
        )
        with patch.object(desktop, 'confirm',
                          side_effect=lambda *args, **kwargs: calls.append('confirm') or False):
            desktop.Desktop.close(host)
        self.assertEqual(calls, ['restore', 'confirm'])
        self.assertFalse(host._closing)

    def test_failed_asset_resume_cleanup_is_visible_to_the_user(self):
        messages = []
        host = types.SimpleNamespace(root='project',
                                     status=types.SimpleNamespace(set=messages.append))
        with patch.object(desktop.asset_resume, 'clear', side_effect=OSError('文件被占用')):
            desktop.Desktop.clear_asset_resume(host)
        self.assertIn('续跑记录未清除', messages[-1])
        self.assertIn('文件被占用', messages[-1])


if __name__ == '__main__':
    unittest.main()
