"""资产批次 watcher 的失败可见性回归。"""
from pathlib import Path
from unittest import TestCase, mock

import asset_skill_batch


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
