"""资产页服务可独立注入，不依赖 Desktop 全局宿主（R1983 J2 第四页）。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_asset_pages import AssetPageServices, AssetPagesMixin, _AssetPage


def _services():
    return AssetPageServices(open_path=Mock(), file_dialog=Mock(), confirm=Mock(return_value=True))


class AssetPageServicesTests(unittest.TestCase):
    def test_services_are_immutable(self):
        with self.assertRaises(Exception):
            _services().confirm = None

    def test_asset_import_uses_injected_file_dialog(self):
        services = _services()
        services.file_dialog.return_value.open_file.return_value = ''
        host = SimpleNamespace(asset_page_services=services, win=object(), asset_base=lambda: Path('b'))
        AssetPagesMixin.asset_import(host, 'characters')
        services.file_dialog.assert_called_once_with(host.win)
        services.file_dialog.return_value.open_file.assert_called_once()

    def test_delete_references_asks_injected_confirm(self):
        services = _services()
        services.confirm.return_value = False
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'assets' / '资产清单').mkdir(parents=True)
            (base / 'assets' / '资产清单' / 'assets.json').write_text(
                json.dumps({'CHAR_001': {'reference_images': ['r.png']}}), encoding='utf-8')
            host = SimpleNamespace(asset_page_services=services, win=object(), asset_base=lambda: base)
            AssetPagesMixin.delete_asset_references(host, 'CHAR_001')
        self.assertEqual(services.confirm.call_args.args[:2], (host.win, '删除参考图'))

    def test_page_preview_uses_injected_open_path(self):
        services = _services()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            (base / 'a.png').write_bytes(b'x')
            host = SimpleNamespace(asset_page_services=services, asset_base=lambda: base)
            page = _AssetPage.__new__(_AssetPage)
            page.page = host
            page.table = SimpleNamespace(selection=lambda: ('CHAR_001',))
            page.registry = {'CHAR_001': {'status': '已导入', 'image': 'a.png'}}
            page.preview()
        services.open_path.assert_called_once_with((base / 'a.png').resolve())


if __name__ == '__main__':
    unittest.main()
