# -*- coding: utf-8 -*-
"""剧本准备「刷新」收回下载文件夹里的创作文件：同类覆盖原文件，不另存副本。

场景：Claude Desktop 窗口只给出下载文件、没有直接写入任务书指定路径；用户把它下载到
「下载」文件夹后点「刷新」，同一份项目大纲应覆盖原来那份并在剧本列表中显示。
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_chat
import platform_tools
from project_context_factory import project_context
from stage_execution_service import publish_idea_creative

OUTLINE_OLD = '# 剧本大纲\n\n第一版大纲：少年拿起相机。\n'
OUTLINE_NEW = '# 剧本大纲\n\n重新生成的大纲：魔王兵临真城。\n'


class DownloadImportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.project = base / '摄影侠_20260930'
        self.project.mkdir()
        self.downloads = base / 'Downloads'
        self.downloads.mkdir()
        self.context = project_context(self.project)

    def tearDown(self):
        self._tmp.cleanup()

    def _download(self, name, text, age=0):
        path = self.downloads / name
        path.write_text(text, encoding='utf-8')
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def _import(self, provider='Anthropic', model='Claude Desktop'):
        return idea_chat.import_downloaded_documents(
            self.context, self.downloads, provider=provider, model=model, publish=publish_idea_creative)

    def _saved_outline(self):
        old = idea_chat.save_reply(self.context, OUTLINE_OLD, provider='Anthropic', model='Claude Desktop',
                                   publish=publish_idea_creative)
        stamp = time.time() - 600
        os.utime(old, (stamp, stamp))
        return old

    def test_newer_download_overwrites_the_same_outline_file(self):
        old = self._saved_outline()
        self._download('摄影侠_项目大纲_Anthropic_20261014.md', OUTLINE_NEW)
        imported = self._import()
        self.assertEqual(imported, [('项目大纲', old)])
        self.assertEqual(old.read_text(encoding='utf-8').strip(), OUTLINE_NEW.strip())
        self.assertEqual(len(list(old.parent.glob('*.md'))), 1, '覆盖原文件，不另存副本')
        self.assertIn(old, idea_chat.creative_documents(self.context))
        # 再次刷新：已收回的文件不再重复导入。
        self.assertEqual(self._import(), [])
        self.assertTrue((self.downloads / '摄影侠_项目大纲_Anthropic_20261014.md').is_file(), '下载原件保持不动')

    def test_browser_copy_suffix_is_accepted_and_newest_download_wins(self):
        old = self._saved_outline()
        self._download('摄影侠_项目大纲_Anthropic_20261014.md', '# 剧本大纲\n\n较早下载。\n', age=60)
        self._download('摄影侠_项目大纲_Anthropic_20261014 (1).md', OUTLINE_NEW)
        self.assertEqual(self._import(), [('项目大纲', old)])
        self.assertEqual(old.read_text(encoding='utf-8').strip(), OUTLINE_NEW.strip())

    def test_first_download_is_saved_when_no_outline_exists_yet(self):
        self._download('摄影侠_项目大纲_Anthropic_20261014.md', OUTLINE_NEW)
        imported = self._import()
        self.assertEqual([kind for kind, _path in imported], ['项目大纲'])
        self.assertEqual(imported[0][1].parent.name, '项目大纲')
        self.assertEqual(imported[0][1].parents[2].name, 'Claude Desktop')

    def test_download_dated_after_existing_outline_is_saved_as_new_file(self):
        old = self._saved_outline()
        later = time.strftime('%Y%m%d', time.localtime(time.time() + 2 * 24 * 3600))
        self._download('摄影侠 项目大纲 Anthropic ' + later + '.md', OUTLINE_NEW)
        imported = self._import()
        self.assertEqual([kind for kind, _path in imported], ['项目大纲'])
        saved = imported[0][1]
        self.assertNotEqual(saved, old)
        self.assertEqual(saved.name, '摄影侠_项目大纲_Anthropic_' + later + '.md')
        self.assertEqual(saved.parents[1].name, '创意_' + later)
        self.assertEqual(saved.read_text(encoding='utf-8').strip(), OUTLINE_NEW.strip())
        self.assertEqual(old.read_text(encoding='utf-8').strip(), OUTLINE_OLD.strip(), '旧日期版本保留')
        self.assertEqual(self._import(), [], '再次刷新不重复导入')

    def test_unrelated_stale_or_mismatched_downloads_are_ignored(self):
        old = self._saved_outline()
        self._download('别的项目_项目大纲_Anthropic_20261014.md', OUTLINE_NEW)
        self._download('摄影侠_项目大纲_DeepSeek_20261014.md', OUTLINE_NEW)
        self._download('摄影侠_角色卡_Anthropic_20261014.md', OUTLINE_NEW)  # 文件名与正文分类不符
        self._download('摄影侠_项目大纲_Anthropic_20261001.md', OUTLINE_NEW, age=idea_chat.DOWNLOAD_IMPORT_MAX_AGE + 60)
        self._download('随手笔记.md', OUTLINE_NEW)
        self.assertEqual(self._import(), [])
        self.assertEqual(old.read_text(encoding='utf-8').strip(), OUTLINE_OLD.strip())

    def test_download_older_than_saved_file_does_not_overwrite(self):
        self._download('摄影侠_项目大纲_Anthropic_20261014.md', OUTLINE_NEW, age=3600)
        old = self._saved_outline()  # 保存于 10 分钟前，比下载新
        self.assertEqual(self._import(), [])
        self.assertEqual(old.read_text(encoding='utf-8').strip(), OUTLINE_OLD.strip())

    def test_missing_downloads_folder_and_publisher_contract(self):
        self.assertEqual(idea_chat.import_downloaded_documents(
            self.context, self.downloads / '不存在', provider='Anthropic', model='Claude Desktop',
            publish=publish_idea_creative), [])
        with self.assertRaisesRegex(TypeError, 'L3'):
            idea_chat.import_downloaded_documents(self.context, self.downloads, provider='Anthropic')


SETTING = '# 项目设定\n\n项目名：《摄影侠》\n故事大体环境：真城。\n'


class BodyNamedDownloadImportTests(unittest.TestCase):
    "REQ-S01-51：文件名不是四段式时，按正文类型与正文项目名安全收回。"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.project = base / '摄影侠_20260930'
        self.project.mkdir()
        self.downloads = base / 'Downloads'
        self.downloads.mkdir()
        self.context = project_context(self.project)

    def tearDown(self):
        self._tmp.cleanup()

    def _download(self, name, text, age=0):
        path = self.downloads / name
        path.write_text(text, encoding='utf-8')
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def _import(self, provider='Google', model='Gemini Desktop'):
        return idea_chat.import_downloaded_documents(
            self.context, self.downloads, provider=provider, model=model, publish=publish_idea_creative)

    def test_req_s01_51_google_named_setting_is_imported_by_body(self):
        source = self._download('google_20261018.md', SETTING)
        imported = self._import()
        self.assertEqual([kind for kind, _path in imported], ['项目设定'])
        saved = imported[0][1]
        self.assertEqual(saved.parent.name, '项目设定')
        self.assertEqual(saved.parents[2].name, 'Gemini Desktop')
        self.assertEqual(saved.read_text(encoding='utf-8').strip(), SETTING.strip())
        self.assertTrue(source.is_file(), '下载原件保持不动')

    def test_req_s01_51_body_project_mismatch_or_missing_is_ignored(self):
        self._download('google_20261018.md', '# 项目设定\n\n项目名：《别的项目》\n故事大体环境：别处。\n')
        self._download('google_20261018 (1).md', '# 项目设定\n\n故事大体环境：没有项目名。\n')
        self._download('google_20261018 (2).md', '# 剧本大纲\n\n## 一句话简介\n少年拿起相机。\n')
        self.assertEqual(self._import(), [])

    def test_req_s01_51_filename_project_falls_back_when_body_has_none(self):
        self._download('摄影侠 项目大纲 Google 20261018.md',
                       '# 剧本大纲\n\n## 一句话简介\n少年拿起相机。\n')
        imported = self._import()
        self.assertEqual([kind for kind, _path in imported], ['项目大纲'])
        self.assertEqual(imported[0][1].read_text(encoding='utf-8').strip(),
                         '# 剧本大纲\n\n## 一句话简介\n少年拿起相机。')

    def test_req_s01_51_filename_project_mismatch_is_ignored(self):
        self._download('别的项目 角色卡 Google 20261018.md',
                       '# 角色卡\n\n## 林夏\n- 姓名：林夏\n')
        self.assertEqual(self._import(), [])

    def test_req_s01_51_body_project_takes_priority_over_filename(self):
        self._download('摄影侠 项目设定 Google 20261018.md',
                       '# 项目设定\n\n项目名：《别的项目》\n故事大体环境：别处。\n')
        self.assertEqual(self._import(), [])

    def test_req_s01_51_partial_filename_project_name_is_ignored(self):
        self._download('摄影侠外传 角色卡 20261018.md',
                       '# 角色卡\n\n## 林夏\n- 姓名：林夏\n')
        self.assertEqual(self._import(), [])

    def test_req_s01_51_title_project_name_imports_outline_role_card_and_script(self):
        self._download('google_20261018.md', '# 剧本大纲：摄影侠\n\n## 一句话简介\n少年拿起相机。\n')
        self._download('google_20261018 (1).md', '# 角色卡：摄影侠\n\n## 林夏\n- 姓名：林夏\n')
        self._download('google_20261018 (2).md', '# 摄影侠 自然剧本\n\n第1集\n\n林夏抬头看向照相馆的灯。\n')
        kinds = sorted(kind for kind, _path in self._import())
        self.assertEqual(kinds, ['自然剧本', '角色卡', '项目大纲'])

    def test_req_s01_51_newest_unsuffixed_candidate_wins(self):
        self._download('google_20261018.md', '# 项目设定\n\n项目名：《摄影侠》\n故事大体环境：旧版。\n', age=60)
        self._download('google_20261018 (1).md', '# 项目设定\n\n项目名：《摄影侠》\n故事大体环境：新版。\n')
        imported = self._import()
        self.assertEqual([kind for kind, _path in imported], ['项目设定'])
        self.assertIn('新版', imported[0][1].read_text(encoding='utf-8'))
        self.assertEqual(len(list(imported[0][1].parent.glob('*.md'))), 1)

    def test_req_s01_51_older_than_saved_file_does_not_overwrite(self):
        saved = idea_chat.save_reply(self.context, SETTING, provider='Google', model='Gemini Desktop',
                                     publish=publish_idea_creative)
        stamp = time.time() - 600
        os.utime(saved, (stamp, stamp))
        self._download('google_20261018.md',
                       '# 项目设定\n\n项目名：《摄影侠》\n故事大体环境：更旧的下载。\n', age=3600)
        self.assertEqual(self._import(), [])
        self.assertEqual(saved.read_text(encoding='utf-8').strip(), SETTING.strip())

    def test_req_s01_51_download_older_than_three_days_is_ignored(self):
        self._download('google_20261018.md', SETTING,
                       age=idea_chat.DOWNLOAD_IMPORT_MAX_AGE + 60)
        self.assertEqual(self._import(), [])

    def test_req_s01_51_non_markdown_or_non_creative_is_ignored(self):
        self._download('google_20261018.txt', SETTING)
        self._download('google_20261018.md', '今天天气不错，先聊聊天。\n')
        self.assertEqual(self._import(), [])


class DownloadsDirectoryTests(unittest.TestCase):
    def test_falls_back_to_home_downloads_without_registry(self):
        with patch.object(platform_tools, 'windows_registry', return_value=None):
            self.assertEqual(platform_tools.downloads_directory(), Path.home() / 'Downloads')


class DeliveryPathTests(unittest.TestCase):
    def test_existing_edited_file_is_the_delivery_target_across_days(self):
        from idea_document_paths import delivery_document_path
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / '摄影侠_20260930'
            project.mkdir()
            context = project_context(project)
            first = delivery_document_path(context, '项目大纲', at=0, provider='Anthropic', model='Claude Desktop')
            first.parent.mkdir(parents=True)
            first.write_text('# 剧本大纲\n用户手改版', encoding='utf-8')
            later = delivery_document_path(context, '项目大纲', at=86400 * 400,
                                           provider='Anthropic', model='Claude Desktop')
            self.assertEqual(later, first)
            script = delivery_document_path(context, '自然剧本', at=86400 * 400,
                                            provider='Anthropic', model='Claude Desktop')
            self.assertEqual(script.parent.name, '项目剧本')
            self.assertFalse(script.exists())


if __name__ == '__main__':
    unittest.main()
