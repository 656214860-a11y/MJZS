"""首帧管理页服务可独立注入，不依赖 Desktop 全局宿主（R1983 J2 第二页）。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_storyboard_page import StoryboardPageServices, _FirstFramePage


def _page(services, **kwargs):
    host = SimpleNamespace(win=object(), storyboard_page_services=services, status=Mock())
    page = _FirstFramePage.__new__(_FirstFramePage)
    page.page = host
    for key, value in kwargs.items():
        setattr(page, key, value)
    return page


class StoryboardPageServicesTests(unittest.TestCase):
    def services(self):
        return StoryboardPageServices(open_path=Mock(), file_dialog=Mock(), confirm=Mock(return_value=True))

    def test_services_are_immutable(self):
        with self.assertRaises(Exception):
            self.services().confirm = None

    def test_view_frame_image_uses_injected_open_path(self):
        services = self.services()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'a.png').write_bytes(b'x')
            page = _page(services, base=base, episode={'shots': [{'id': 'S1', 'frame': 'a.png'}]},
                         exists=lambda shot: True)
            page.view_frame_image('S1')
        services.open_path.assert_called_once_with((base / 'a.png').resolve())

    def test_replace_uses_injected_file_dialog(self):
        services = self.services()
        services.file_dialog.return_value.open_file.return_value = ''
        page = _page(services, base=Path('p'))
        page.replace({'id': 'S1'})
        services.file_dialog.assert_called_once_with(page.page.win)
        services.file_dialog.return_value.open_file.assert_called_once()

    def test_batch_delete_asks_injected_confirm(self):
        services = self.services()
        services.confirm.return_value = False
        shot = {'id': 'S1'}
        page = _page(services, rows=[('i1', shot, 0, None, None)], exists=lambda s: True,
                     work_targets=lambda: (['i1'], 'checked'), work_hint=lambda w, h: '')
        result = page.delete_checked_frames()
        self.assertEqual(result, [])
        self.assertEqual(services.confirm.call_args.args[:2], (page.page.win, '批量删除首帧'))
        self.assertTrue(services.confirm.call_args.kwargs['dangerous'])


if __name__ == '__main__':
    unittest.main()
