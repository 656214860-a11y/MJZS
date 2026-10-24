"""媒体页（配音／后期／交付）服务可独立注入，不依赖 Desktop 全局宿主（R1983 J2 第五页）。"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from desktop_media_pages import MediaPageServices, MediaPagesMixin


def _services():
    return MediaPageServices(
        open_path=Mock(), file_dialog=Mock(), confirm=Mock(return_value=True), open_studio=Mock(),
        comfy_executable=Mock(return_value='C:/comfy.exe'), find_editor_shortcut=Mock(return_value='lnk'))


class MediaPageServicesTests(unittest.TestCase):
    def test_services_are_immutable(self):
        with self.assertRaises(Exception):
            _services().confirm = None

    def test_editor_shortcut_uses_injected_service(self):
        services = _services()
        host = SimpleNamespace(media_page_services=services)
        self.assertEqual(MediaPagesMixin.find_editor_shortcut(host), 'lnk')
        services.find_editor_shortcut.assert_called_once_with()

    def test_restore_keyframe_asks_injected_confirm(self):
        services = _services()
        services.confirm.return_value = False
        host = SimpleNamespace(media_page_services=services, win=object())
        MediaPagesMixin.restore_keyframe(host, {'id': 'S1'}, 'EP1', None, None)
        services.confirm.assert_called_once()
        self.assertEqual(services.confirm.call_args.args[:2], (host.win, '恢复首帧'))


if __name__ == '__main__':
    unittest.main()
