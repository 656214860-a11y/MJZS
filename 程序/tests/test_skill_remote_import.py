# -*- coding: utf-8 -*-
"""T3：SKILL 远程链接导入——GitHub 仓库／.zip 直链 → 下载缓存 → ZIP 管线。

``skill_remote_service``：``parse_source`` 只收 GitHub 仓库链接（``#ref``／
``/tree/<ref>/<子目录>``）与 ``.zip`` 直链；``download`` 唯一出站口径
``platform_tools.open_https``（测试注入 ``opener``；``DRAMA_SUPPRESS_NETWORK``
下默认入口按不联网返回）；下载落 ``data/skills/下载缓存/`` 后走
``skill_archive`` 同一条解包→预检→换入→试冻结→登记管线；台账行新增
``source_url``／``source_ref``／``version``，仓库导入（``import_from_repo``）
的 url 形态同样落这两个字段。
"""
import io
import os
import tempfile
import tkinter as tk
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

import skill_import_service
import skill_panel
import skill_registry
import skill_remote_service
from test_skill_repo_import import make_program, write_package
from test_skills import PanelTests


def zip_bytes(entries):
    """entries: {arcname: 文本或 bytes} → ZIP 字节串（供假 opener 直接喂）。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FakeResponse:
    """``open_https`` 替身：``read(n)`` 分块、可选 headers、记录 close。"""

    def __init__(self, data, headers=None):
        self._stream = io.BytesIO(data)
        self.headers = headers or {}
        self.closed = False

    def read(self, n=-1):
        return self._stream.read(n)

    def close(self):
        self.closed = True


class Opener:
    """按 URL 分发假响应；记录调用过的 URL。"""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.urls = []

    def __call__(self, url, timeout=None, **kwargs):
        self.urls.append(url)
        value = self.routes[url]
        if isinstance(value, BaseException):
            raise value
        if callable(value):
            return value(url)
        return value


REMOTE_MD = ('---\nname: remote-pack\nstage: 剧本准备\nversion: 2.0.1\n---\n'
             '# 远程技能\n见 [规则](references/rules.md)\n')


class ParseSourceTests(unittest.TestCase):
    def test_github_plain_expands_to_codeload_head(self):
        spec = skill_remote_service.parse_source('https://github.com/acme/tools')
        self.assertEqual(spec['kind'], 'repo')
        self.assertEqual(spec['url'],
                         'https://codeload.github.com/acme/tools/zip/HEAD')
        self.assertEqual(spec['source_url'], 'https://github.com/acme/tools')
        self.assertEqual(spec['source_ref'], '')
        self.assertEqual(spec['source_kind'], 'repo')
        self.assertEqual(spec['scope'], '')
        self.assertIn('github.com/acme/tools', spec['label'])

    def test_github_hash_ref_and_tree_subdir(self):
        spec = skill_remote_service.parse_source(
            'https://github.com/acme/tools/tree/v2/skills/foo#v9')
        self.assertEqual(spec['source_ref'], 'v9', '#ref 优先于 /tree/ 路径里的 ref')
        self.assertEqual(spec['scope'], 'skills/foo')
        self.assertIn('/zip/v9', spec['url'])
        spec = skill_remote_service.parse_source('https://github.com/acme/tools#v1.2.3')
        self.assertEqual(spec['source_ref'], 'v1.2.3')
        self.assertIn('/zip/v1.2.3', spec['url'])

    def test_github_git_suffix_and_bare_host(self):
        spec = skill_remote_service.parse_source('github.com/acme/tools.git')
        self.assertEqual(spec['source_url'], 'https://github.com/acme/tools')
        self.assertEqual(spec['url'], 'https://codeload.github.com/acme/tools/zip/HEAD')

    def test_zip_link_keeps_query_in_download_but_not_label(self):
        spec = skill_remote_service.parse_source(
            'https://cdn.example.com/packs/my-skill.zip?sig=abc123')
        self.assertEqual(spec['kind'], 'archive')
        self.assertEqual(spec['source_kind'], 'archive')
        self.assertIn('sig=abc123', spec['url'])
        self.assertIn('sig=abc123', spec['source_url'])
        self.assertNotIn('sig=', spec['label'])
        self.assertTrue(spec['cache_name'].endswith('.zip'))

    def test_rejected_forms(self):
        for text in ('git@github.com:acme/tools.git',
                     'https://x.com/a.tar.gz',
                     'ftp://x.com/a.zip',
                     'https://user:pw@x.com/a.zip',
                     '随便一段文字',
                     'https://github.com/onlyowner',
                     'https://github.com/acme/tools/releases'):
            with self.assertRaises(skill_import_service.ImportBlocked, msg=text):
                skill_remote_service.parse_source(text)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_download_writes_bytes_and_closes_response(self):
        payload = zip_bytes({'a.txt': 'hello'})
        response = FakeResponse(payload, {'Content-Length': str(len(payload))})
        opener = Opener({'https://x.com/a.zip': response})
        dest = skill_remote_service.download('https://x.com/a.zip',
                                             self.root / 'cache' / 'a.zip', opener=opener)
        self.assertEqual(dest.read_bytes(), payload)
        self.assertTrue(response.closed)
        self.assertEqual(opener.urls, ['https://x.com/a.zip'])

    def test_content_length_over_limit_rejected_before_write(self):
        big = str(skill_import_service.PACKAGE_MAX_BYTES + 1)
        opener = Opener({'https://x.com/big.zip': FakeResponse(b'x', {'Content-Length': big})})
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            skill_remote_service.download('https://x.com/big.zip',
                                          self.root / 'big.zip', opener=opener)
        self.assertIn('上限', str(ctx.exception))
        self.assertFalse((self.root / 'big.zip').exists())

    def test_stream_over_limit_recycles_partial_file(self):
        payload = b'x' * 4096
        opener = Opener({'https://x.com/big.zip': FakeResponse(payload)})
        with mock.patch.object(skill_import_service, 'PACKAGE_MAX_BYTES', 1024):
            with self.assertRaises(skill_import_service.ImportBlocked):
                skill_remote_service.download('https://x.com/big.zip',
                                              self.root / 'big.zip', opener=opener,
                                              recycle_root=self.root)
        self.assertFalse((self.root / 'big.zip').exists(), '超限中断的半截文件必须收走')

    def test_http_error_and_network_error_have_messages(self):
        opener = Opener({'https://x.com/missing.zip':
                         urllib.error.HTTPError('https://x.com/missing.zip', 404, 'nf', {}, None)})
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            skill_remote_service.download('https://x.com/missing.zip',
                                          self.root / 'm.zip', opener=opener)
        self.assertIn('404', str(ctx.exception))
        opener = Opener({'https://x.com/down.zip':
                         urllib.error.URLError(TimeoutError('timed out'))})
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            skill_remote_service.download('https://x.com/down.zip',
                                          self.root / 'd.zip', opener=opener)
        self.assertIn('超时', str(ctx.exception))

    def test_suppress_network_env_blocks_default_opener(self):
        with mock.patch.dict(os.environ, {'DRAMA_SUPPRESS_NETWORK': '1'}):
            with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
                skill_remote_service.download('https://x.com/a.zip',
                                              self.root / 'a.zip')
        self.assertIn('不联网', str(ctx.exception))


class ImportFromUrlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def ledger_rows(self):
        return skill_import_service._read_items(skill_import_service.ledger_path(self.program))

    def test_zip_link_end_to_end_with_ledger_fields(self):
        payload = zip_bytes({
            'pack/SKILL.md': REMOTE_MD,
            'pack/references/rules.md': '规则正文',
        })
        opener = Opener({'https://cdn.example.com/packs/remote.zip?sig=1':
                         FakeResponse(payload)})
        report = skill_remote_service.import_from_url(
            'https://cdn.example.com/packs/remote.zip?sig=1', self.program, self.registry,
            confirm=lambda m: True, opener=opener)
        self.assertEqual(len(report['installed']), 1)
        installed = (self.program / 'data' / 'skills' / '01剧本准备SKILL' / 'pack')
        self.assertTrue((installed / 'SKILL.md').is_file())
        self.assertTrue((installed / 'references' / 'rules.md').is_file())
        row = next(iter(self.ledger_rows().values()))
        self.assertEqual(row['source_url'],
                         'https://cdn.example.com/packs/remote.zip?sig=1')
        self.assertEqual(row['source_kind'], 'archive')
        self.assertEqual(row['source_ref'], '')
        self.assertEqual(row['version'], '2.0.1')
        self.assertNotIn('sig=', row['source'], '展示标签不带签名查询串')
        cache = skill_remote_service.cache_dir(self.program)
        self.assertEqual(len(list(cache.glob('*.zip'))), 1, '下载缓存落盘一份')

    def test_github_repo_zip_with_tree_scope(self):
        payload = zip_bytes({
            'acme-tools-skills/foo/SKILL.md': REMOTE_MD,
            'acme-tools-skills/foo/references/rules.md': '规则',
            'acme-tools-skills/other/readme.txt': '不该被扫到',
        })
        url = 'https://github.com/acme/tools/tree/v2/acme-tools-skills'
        codeload = 'https://codeload.github.com/acme/tools/zip/v2'
        opener = Opener({codeload: FakeResponse(payload)})
        report = skill_remote_service.import_from_url(
            url, self.program, self.registry, confirm=lambda m: True, opener=opener)
        self.assertEqual(opener.urls, [codeload])
        self.assertEqual(len(report['installed']), 1)
        self.assertTrue((self.program / 'data' / 'skills' / '01剧本准备SKILL'
                         / 'foo' / 'SKILL.md').is_file())
        row = next(iter(self.ledger_rows().values()))
        self.assertEqual(row['source_kind'], 'repo')
        self.assertEqual(row['source_url'], 'https://github.com/acme/tools')
        self.assertEqual(row['source_ref'], 'v2')
        self.assertEqual(row['version'], '2.0.1')

    def test_http_404_and_bad_zip_have_clear_errors(self):
        opener = Opener({'https://cdn.example.com/x.zip':
                         urllib.error.HTTPError('https://cdn.example.com/x.zip',
                                                404, 'nf', {}, None)})
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            skill_remote_service.import_from_url(
                'https://cdn.example.com/x.zip', self.program, self.registry,
                confirm=lambda m: True, opener=opener)
        self.assertIn('404', str(ctx.exception))
        opener = Opener({'https://cdn.example.com/bad.zip':
                         FakeResponse('不是压缩包'.encode('utf-8'))})
        with self.assertRaises(skill_import_service.ImportBlocked):
            skill_remote_service.import_from_url(
                'https://cdn.example.com/bad.zip', self.program, self.registry,
                confirm=lambda m: True, opener=opener)
        opener = Opener({'https://cdn.example.com/none.zip':
                         FakeResponse(zip_bytes({'a.txt': '没有 SKILL'}))})
        with self.assertRaises(skill_import_service.ImportBlocked) as ctx:
            skill_remote_service.import_from_url(
                'https://cdn.example.com/none.zip', self.program, self.registry,
                confirm=lambda m: True, opener=opener)
        self.assertIn('SKILL', str(ctx.exception))

    def test_old_ledger_rows_without_new_fields_stay_readable(self):
        ledger = skill_import_service.ledger_path(self.program)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        skill_import_service.save(ledger, {'version': 1, 'items': {
            '01剧本准备SKILL/old.skill.md': {
                'source': '旧来源', 'kind': 'manifest', 'name': 'old',
                'sha256': '0' * 64, 'imported_at': '2026-01-01 00:00:00'}}})
        payload = zip_bytes({'solo.skill.md':
                             '---\nname: solo\nstage: 剧本准备\n---\n# 单文件\n正文'})
        opener = Opener({'https://cdn.example.com/s.zip': FakeResponse(payload)})
        skill_remote_service.import_from_url(
            'https://cdn.example.com/s.zip', self.program, self.registry,
            confirm=lambda m: True, opener=opener)
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 2)
        old = rows['01剧本准备SKILL/old.skill.md']
        self.assertEqual(old['source'], '旧来源')
        self.assertNotIn('source_url', old, '旧行不补字段，读取侧容忍缺字段')

    def test_repo_import_records_source_url_and_ref(self):
        """``import_from_repo`` 的 url 形态同样落 ``source_url``／``source_ref``。"""
        repo = self.root / 'repo'
        write_package(repo, dirname='rp')

        def fake_clone(url, ref, dest):
            Path(dest).mkdir(parents=True)
            import shutil
            shutil.copytree(repo, Path(dest), dirs_exist_ok=True)

        with mock.patch.object(skill_import_service, '_git_clone', side_effect=fake_clone):
            skill_import_service.import_from_repo(
                'https://github.com/o/r@main', self.program, self.registry,
                stage_hint='script', confirm=lambda m: True)
        row = next(iter(self.ledger_rows().values()))
        self.assertEqual(row['source_url'], 'https://github.com/o/r')
        self.assertEqual(row['source_ref'], 'main')


class PanelUrlImportTests(unittest.TestCase):
    tk = tk
    setUp = PanelTests.setUp

    def _panel(self):
        builtin = self.desktop.app / 'skills'
        (builtin / '01剧本准备SKILL').mkdir(parents=True, exist_ok=True)
        registry = skill_registry.Registry(builtin,
                                           user_root=self.desktop.app / 'data' / 'skills')
        with mock.patch.object(skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        return panel

    def test_manage_menu_offers_url_entry_and_dispatches(self):
        self.assertIn('从链接导入', skill_panel.MANAGE_LABELS)
        panel = self._panel()
        panel.skill_action.set('从链接导入')
        with mock.patch.object(panel, 'add_skill_from_url', return_value='ok') as url:
            self.assertEqual(panel.choose_skill_action(), 'ok')
            url.assert_called_once()
        self.assertEqual(panel.skill_action.get(), skill_panel.MANAGE_ALL)

    def test_url_entry_end_to_end_with_injected_opener(self):
        """面板入口全链路：ask_string → 解析 → 假 open_https → 缓存 → 解包 → 安装。"""
        panel = self._panel()
        payload = zip_bytes({'pack/SKILL.md': REMOTE_MD,
                             'pack/references/rules.md': '规则'})
        opener = Opener({'https://cdn.example.com/p.zip': FakeResponse(payload)})
        fake_module = str(self.desktop.app / 'ui' / 'skill_import_service.py')
        with mock.patch('skill_panel_import.ask_string', return_value='https://cdn.example.com/p.zip'), \
                mock.patch.object(skill_import_service, '__file__', fake_module), \
                mock.patch.dict(os.environ):
            os.environ.pop('DRAMA_SUPPRESS_NETWORK', None)
            with mock.patch('contract.platform_tools.open_https', opener):
                report = panel.add_skill_from_url()
        self.assertIsNotNone(report)
        self.assertEqual(len(report['installed']), 1)
        installed = (self.desktop.app / 'data' / 'skills' / '01剧本准备SKILL'
                     / 'pack' / 'SKILL.md')
        self.assertTrue(installed.is_file())
        self.assertIn('链接导入完成', panel.state.cget('text'))

    def test_url_entry_failure_shows_status(self):
        panel = self._panel()
        with mock.patch('skill_panel_import.ask_string', return_value='https://x.com/a.zip'), \
                mock.patch('skill_remote_service.import_from_url',
                           side_effect=skill_import_service.ImportBlocked('下载失败：HTTP 404')):
            self.assertIsNone(panel.add_skill_from_url())
        self.assertIn('链接导入失败', panel.state.cget('text'))
        self.assertIn('404', panel.state.cget('text'))


if __name__ == '__main__':
    unittest.main()
