"""资产批次 watcher 的失败可见性回归。"""
import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

import asset_skill_batch
from infra.pet_state import PAGE_OF


class _Status:
    def __init__(self):
        self.messages = []

    def set(self, message):
        self.messages.append(message)


class _App:
    def __init__(self):
        self.win = object()
        self.status = _Status()
        self.asset_import_watchers = set()


class AssetSkillBatchWatchTests(TestCase):
    def test_manifest_read_failure_is_visible_and_keeps_retry_timer(self):
        app = _App()
        ticks = []
        with mock.patch.object(asset_skill_batch.tk_timers, 'repeat',
                               side_effect=lambda _win, _ms, tick: ticks.append(tick) or (lambda: None)), \
             mock.patch.object(asset_skill_batch, 'read', side_effect=OSError('台账不可读')):
            asset_skill_batch.watch(app, Path('C:/temporary/批次.json'))
            ticks[0]()
        self.assertEqual(len(ticks), 1)
        self.assertIn('资产自动导入检查未完成：台账不可读；将在约 2 秒后重试', app.status.messages)


class AssetSkillBatchRefreshTests(TestCase):
    """自动导入后只在人停在资产管理页时重画这一页，页码按阶段名取，不写死数字（UX-B6）。"""

    def _import_once(self, page_index):
        app = _App()
        app.page_index = page_index
        app.shown = []
        app.show = app.shown.append
        ticks = []
        with tempfile.TemporaryDirectory() as tmp:
            app.root = Path(tmp) / '项目'
            manifest = app.root / 'workflows' / 'Imagen资产批次' / '批次A' / '批次.json'
            manifest.parent.mkdir(parents=True)
            (manifest.parent / 'CHAR_001.png').write_bytes(b'x')
            manifest.write_text(json.dumps({'base': str(app.root), 'assets': [
                {'id': 'CHAR_001', 'state': 'pending', 'output': 'CHAR_001.png', 'asset': {'name': '甲'}}]}),
                encoding='utf-8')
            with mock.patch.object(asset_skill_batch.tk_timers, 'repeat',
                                   side_effect=lambda _win, _ms, tick: ticks.append(tick) or (lambda: None)), \
                 mock.patch('domain.asset_batch_lifecycle.status', return_value={'state': 'done'}), \
                 mock.patch.object(asset_skill_batch, 'register_image', return_value='已导入'):
                asset_skill_batch.watch(app, manifest)
                ticks[0]()      # 第一遍只记下文件大小和修改时间
                ticks[0]()      # 第二遍文件没再变，才导入
        return app

    def test_import_redraws_assets_page_when_user_is_on_it(self):
        app = self._import_once(PAGE_OF['assets'])
        self.assertIn('CHAR_001 甲：已自动导入', app.status.messages)
        self.assertEqual(app.shown, [PAGE_OF['assets']])

    def test_import_leaves_other_pages_alone(self):
        app = self._import_once(PAGE_OF['storyboard'])
        self.assertIn('CHAR_001 甲：已自动导入', app.status.messages)
        self.assertEqual(app.shown, [])
