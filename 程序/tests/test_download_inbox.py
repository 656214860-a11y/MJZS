# -*- coding: utf-8 -*-
"""桌面 Agent 下载收件箱：任务书目标文件被下载到「下载」文件夹后，按文件名放回原位置。"""
import json
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

    def _outline_target(self, day):
        return (self.project / '01剧本准备' / 'Google' / 'Google Gemini 4 Argon' / ('创意_' + day)
                / '项目大纲' / ('摄影侠_项目大纲_Google_' + day + '.md'))

    def test_newer_dated_download_is_saved_as_new_batch_and_old_kept(self):
        """REQ-S01-68：下载件只差日期且更新时，另存到新日期批次，旧版本保留。"""
        old = self._outline_target('20261018')
        old.parent.mkdir(parents=True)
        old.write_text('旧大纲', encoding='utf-8')
        now = time.time()
        os.utime(old, (now - 600, now - 600))
        register_download_inbox(self.project, str(old), now=now - 60)
        self._download('摄影侠 项目大纲 Google 20261030.md', '新大纲'.encode('utf-8'), at=now)
        new = self._outline_target('20261030')
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [new])
        self.assertEqual(new.read_text(encoding='utf-8'), '新大纲')
        self.assertEqual(old.read_text(encoding='utf-8'), '旧大纲', '旧日期版本保留')
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [],
                         '收回后登记项移除，不重复写')

    def test_exact_name_wins_over_dated_download(self):
        """REQ-S01-68：有同名下载件时按同名收回，不走日期匹配。"""
        old = self._outline_target('20261018')
        now = time.time()
        register_download_inbox(self.project, str(old), now=now - 60)
        self._download('摄影侠_项目大纲_Google_20261018.md', '同名'.encode('utf-8'), at=now)
        self._download('摄影侠_项目大纲_Google_20261030.md', '新日期'.encode('utf-8'), at=now)
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [old])
        self.assertFalse(self._outline_target('20261030').exists())

    def test_dated_download_needs_same_name_and_newer_date(self):
        """REQ-S01-68：日期匹配要求去日期后名字相同，日期合法且更新。"""
        old = self._outline_target('20261018')
        now = time.time()
        pending = [{'target': str(old), 'since': now - 60}]
        for name in ('摄影侠 项目设定 Google 20261030.md', '摄影侠 项目大纲 Google 20261001.md',
                     '摄影侠 项目大纲 Google 20261399.md'):
            self._download(name, at=now)
        self.assertEqual(download_inbox.match_registered(self.downloads, pending, now), [])

    def test_dated_download_skips_when_new_batch_file_is_newer(self):
        """REQ-S01-68：新日期批次里已有更新的文件时跳过，不覆盖。"""
        old = self._outline_target('20261018')
        new = self._outline_target('20261030')
        new.parent.mkdir(parents=True)
        new.write_text('用户已改', encoding='utf-8')
        now = time.time()
        self._download('摄影侠 项目大纲 Google 20261030.md', at=now - 30)
        pending = [{'target': str(old), 'since': now - 60}]
        self.assertEqual(download_inbox.match_registered(self.downloads, pending, now), [])

    def test_expired_registrations_are_dropped(self):
        target = self.project / '05资产管理' / 'C01.png'
        now = time.time()
        register_download_inbox(self.project, str(target), now=now - download_inbox.PENDING_MAX_AGE - 10)
        self._download('C01.png', at=now)
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [])

    def _gemini_target(self, day):
        return (self.project / '01剧本准备' / 'Google' / 'Google Gemini' / ('创意_' + day)
                / '项目大纲' / ('摄影侠_项目大纲_Google_' + day + '.md'))

    def _pending(self):
        from orchestrator.stage_download_inbox_service import _download_inbox_path
        return json.loads(_download_inbox_path(self.project).read_text(encoding='utf-8'))['pending']

    def test_req_s01_74_one_download_goes_only_to_latest_dispatch(self):
        """REQ-S01-74：两次派发（换了模型名）都对上同一份下载时，只写最近一次派发的位置，旧登记一并销账。"""
        old = self._outline_target('20261018')
        latest = self._gemini_target('20261030')
        now = time.time()
        register_download_inbox(self.project, str(old), now=now - 6000)
        register_download_inbox(self.project, str(latest), now=now - 60)
        self._download('摄影侠_项目大纲_Google_20261030.md', '新大纲'.encode('utf-8'), at=now)
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [latest])
        self.assertEqual(latest.read_text(encoding='utf-8'), '新大纲')
        self.assertFalse(self._outline_target('20261030').exists(), '旧派发的模型目录不另存副本')
        self.assertEqual(self._pending(), [])
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [])

    def test_req_s01_74_latest_dispatch_wins_even_when_it_only_matches_by_date(self):
        """REQ-S01-74：最近一次派发只差日期时，按它换日期另存；更早的同名登记不再写。"""
        earlier = self._gemini_target('20261030')
        latest = self._outline_target('20261018')
        now = time.time()
        register_download_inbox(self.project, str(earlier), now=now - 6000)
        register_download_inbox(self.project, str(latest), now=now - 60)
        self._download('摄影侠 项目大纲 Google 20261030.md', '新大纲'.encode('utf-8'), at=now)
        written = self._outline_target('20261030')
        self.assertEqual(collect_download_inbox(self.project, now=now, downloads=self.downloads), [written])
        self.assertFalse(earlier.exists())
        self.assertEqual(self._pending(), [])


if __name__ == '__main__':
    unittest.main()
