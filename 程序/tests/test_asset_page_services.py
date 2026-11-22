"""资产页服务可独立注入，不依赖 Desktop 全局宿主（R1983 J2 第四页）。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop_asset_pages import AssetPageServices, AssetPagesMixin, _AssetPage
from infra.pet_state import PAGE_OF


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


class AssetPageStaysOnAssetsTests(unittest.TestCase):
    """资产页内的操作做完后重画的是资产管理页，页码按阶段名取，不写死数字（UX-B6）。"""

    def _host(self, base, **extra):
        shown = []
        host = SimpleNamespace(asset_page_services=_services(), win=object(), asset_base=lambda: base,
                               show=shown.append, status=Mock(), **extra)
        return host, shown

    def test_delete_references_redraws_the_assets_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'assets' / '资产清单').mkdir(parents=True)
            (base / 'assets' / '资产清单' / 'assets.json').write_text(
                json.dumps({'CHAR_001': {'reference_images': ['r.png']}}), encoding='utf-8')
            host, shown = self._host(base)
            with patch.object(AssetPagesMixin, 'asset_write_base', return_value=base), \
                 patch('asset_reference_images.unbind') as unbind:
                self.assertTrue(AssetPagesMixin.delete_asset_references(host, 'CHAR_001'))
        unbind.assert_called_once_with(base, 'CHAR_001', ['r.png'])
        self.assertEqual(shown, [PAGE_OF['assets']])

    def test_delete_image_redraws_the_assets_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            (base / 'assets.json').write_text(json.dumps({'CHAR_001': {'image': 'a.png'}}), encoding='utf-8')
            (base / 'a.png').write_bytes(b'x')
            host, shown = self._host(base)
            with patch.object(AssetPagesMixin, 'asset_write_base', return_value=base), \
                 patch.object(AssetPagesMixin, 'asset_batch_gateway', return_value=object()), \
                 patch('domain.asset_batch_service.remove_asset_image') as remove:
                self.assertTrue(AssetPagesMixin.delete_asset_image(host, 'CHAR_001'))
        remove.assert_called_once()
        self.assertEqual(shown, [PAGE_OF['assets']])

    def test_batch_delete_redraws_the_assets_page_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            (base / 'assets.json').write_text(json.dumps({'CHAR_001': {'image': 'a.png'}}), encoding='utf-8')
            host, shown = self._host(base, asset_work_ids=lambda: (['CHAR_001'], 'checked'),
                                     asset_work_hint=lambda targets, how: '',
                                     delete_asset_image=Mock(return_value=True), note=Mock())
            self.assertEqual(AssetPagesMixin.delete_asset_images(host), ['CHAR_001'])
        host.delete_asset_image.assert_called_once_with('CHAR_001', ask=False)
        self.assertEqual(shown, [PAGE_OF['assets']])

    def test_rename_redraws_the_assets_page(self):
        host, shown = self._host(Path('b'), asset_requirements=lambda: {'CHAR_001': {'name': '旧名'}})
        with patch.object(AssetPagesMixin, 'asset_write_base', return_value=Path('b')), \
             patch.object(AssetPagesMixin, 'asset_batch_gateway', return_value=object()), \
             patch('domain.asset_batch_service.rename_asset') as rename:
            AssetPagesMixin.rename_asset(host, 'CHAR_001', name='新名')
        rename.assert_called_once()
        self.assertEqual(shown, [PAGE_OF['assets']])


if __name__ == '__main__':
    unittest.main()
