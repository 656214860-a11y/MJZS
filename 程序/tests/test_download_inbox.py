# -*- coding: utf-8 -*-
"""桌面 Agent 下载收件箱：任务书目标文件被下载到「下载」文件夹后，按文件名放回原位置。"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import download_inbox
from stage_execution_service import collect_download_inbox, register_download_inbox


class DownloadInboxTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.project = base / '摄影侠_20260930'
        self.project.mkdir()
        self.downloads = base / 'Downloads'
        self.downloads.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _download(self, name, data=b'PNG', at=None):
        path = self.downloads / name
        path.write_bytes(data)
        if at is not None:
            os.utime(path, (at, at))
        return path

    def test_targets_cover_absolute_and_relative_paths_inside_project_only(self):
        absolute = self.project / '05资产管理' / 'C01.png'
        text = ('输出：' + str(absolute) + '；\n'
                '01剧本准备/Anthropic/Claude Desktop/创意_20261014/项目大纲/摄影侠_项目大纲_Anthropic_20261014.md（仅当产出该类内容时使用）\n'
                '参考：' + str(self.project / '01剧本准备' / '输入' / '附件.md') + '\n'
                '外部：D:/别处/外部.png')
        targets = download_inbox.expected_targets(self.project, text)
        self.assertEqual([path.name for path in targets],
                         ['C01.png', '摄影侠_项目大纲_Anthropic_20261014.md'])

    def test_collect_moves_named_download_back_to_target_once(self):
        target = self.project / '05资产管理' / 'C01.png'
        now = time.time()
        register_download_inbox(self.project, '输出：' + str(target), now=now - 10)
        self._download('C01 (1).png', b'new-image', at=now)
        done = collect_download_inbox(self.project, now=now, downloads=self.downloads)
        self.assertEqual(done, [target])
        self.assertEqual(target.read_bytes(), b'new-image')
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [])

    def test_download_before_dispatch_or_older_than_target_is_ignored(self):
        target = self.project / '05资产管理' / 'C01.png'
        now = time.time()
        self._download('C01.png', b'stale', at=now - 3600)
        register_download_inbox(self.project, '输出：' + str(target), now=now)
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [])
        self.assertFalse(target.exists())

    def test_regenerated_existing_target_is_overwritten_by_newer_download(self):
        target = self.project / '01剧本准备' / '项目大纲' / '摄影侠_项目大纲_Anthropic_20261014.md'
        target.parent.mkdir(parents=True)
        target.write_text('旧大纲', encoding='utf-8')
        now = time.time()
        os.utime(target, (now - 600, now - 600))
        register_download_inbox(self.project, str(target), now=now - 60)
        self._download(target.name, '新大纲'.encode('utf-8'), at=now)
        backups = []
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads,
                                                backups=backups), [target])
        self.assertEqual(target.read_text(encoding='utf-8'), '新大纲')
        # 覆盖前原文件先备份到项目「覆盖前备份」，用户手改的内容不会凭空消失。
        self.assertEqual([original for original, _backup in backups], [target])
        self.assertEqual(backups[0][1].read_text(encoding='utf-8'), '旧大纲')
        self.assertTrue(backups[0][1].is_relative_to(self.project / '工作流任务' / '覆盖前备份'))

    def test_space_separated_download_matches_underscore_target(self):
        target = self.project / '01剧本准备' / '项目设定' / '一百块流浪记_项目设定_Google_20261021.md'
        now = time.time()
        register_download_inbox(self.project, str(target), now=now - 10)
        self._download('一百块流浪记 项目设定 Google 20261021.md', '设定'.encode('utf-8'), at=now)
        done = collect_download_inbox(self.project, now=now, downloads=self.downloads)
        self.assertEqual(done, [target])
        self.assertEqual(target.read_text(encoding='utf-8'), '设定')

    def test_expired_registrations_are_dropped(self):
        target = self.project / '05资产管理' / 'C01.png'
        now = time.time()
        register_download_inbox(self.project, str(target), now=now - download_inbox.PENDING_MAX_AGE - 10)
        self._download('C01.png', at=now)
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [])


if __name__ == '__main__':
    unittest.main()
