# -*- coding: utf-8 -*-
"""T4：导入台账消费——``check_updates`` 四态、local-modified、删除闭环。

``skill_import_service.check_updates(program, probe=...)`` 遍历
``data/skills/导入台账.json``：已安装目标缺失→``source-missing``；已安装内容
摘要与台账 ``sha256`` 不一致→``local-modified``（用户手改，不提示覆盖）；
否则按来源重算摘要：``file``／``dir`` 本地路径直读、``repo`` 本地目录重扫
候选、``repo`` 远程走 ``_git_clone`` 重克隆、``archive`` 与 T3 远程链接行交给
``probe``（``skill_archive.probe_row`` 本地 ZIP、``skill_remote_service.probe_row``
远程下载）；探针缺省或候选消失→``source-missing``。

删除闭环：``uninstall_skill`` 与面板 ``delete_checked_skills`` 成功后经
``forget_ledger_targets`` 摘除对应台账行。
"""
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import skill_archive
import skill_import_service
import skill_panel
import skill_registry
import skill_remote_service
from test_skill_repo_import import make_program, write_manifest, write_package


def import_file(program, registry, source, stage='script', stage_dir='01剧本准备SKILL'):
    """单文件／包入口 → plan_import → perform_import（与面板文件导入同管线）。"""
    plan = skill_import_service.plan_import(
        Path(source), registry.user_stage_directory_for(stage), stage, registry)
    return skill_import_service.perform_import(plan, program)


def ledger_rows(program):
    return skill_import_service._read_items(skill_import_service.ledger_path(program))


def only_key(rows):
    assert len(rows) == 1, rows
    return next(iter(rows))


class CheckUpdatesLocalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def test_file_source_unchanged_then_source_newer(self):
        source = write_manifest(self.root / 'src' / 'a.skill.md', name='alpha', stage='script')
        import_file(self.program, self.registry, source)
        key = only_key(ledger_rows(self.program))
        self.assertEqual(skill_import_service.check_updates(self.program), {key: 'unchanged'})
        source.write_text(source.read_text(encoding='utf-8') + '\n改动\n', encoding='utf-8')
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'source-newer')

    def test_local_modified_beats_source_check(self):
        source = write_manifest(self.root / 'src' / 'b.skill.md', name='beta', stage='script')
        import_file(self.program, self.registry, source)
        key = only_key(ledger_rows(self.program))
        target = self.program / 'data' / 'skills' / key
        target.write_text(target.read_text(encoding='utf-8') + '\n本地手改\n', encoding='utf-8')
        source.write_text(source.read_text(encoding='utf-8') + '\n源也改了\n', encoding='utf-8')
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'local-modified')

    def test_missing_source_and_missing_target_are_source_missing(self):
        source = write_manifest(self.root / 'src' / 'c.skill.md', name='gamma', stage='script')
        import_file(self.program, self.registry, source)
        key = only_key(ledger_rows(self.program))
        source.unlink()
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'source-missing')
        # 重建源后目标再删：两类缺失都落 source-missing。
        write_manifest(self.root / 'src' / 'c.skill.md', name='gamma', stage='script')
        (self.program / 'data' / 'skills' / key).unlink()
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'source-missing')

    def test_dir_package_source_digest(self):
        package = write_package(self.root / 'pkgs' / 'one', dirname='pack', stage='script')
        entry = package / 'SKILL.md'
        import_file(self.program, self.registry, entry)
        rows = ledger_rows(self.program)
        self.assertEqual(rows[only_key(rows)]['source_kind'], 'dir')
        key = only_key(rows)
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'unchanged')
        (package / 'references' / 'rules.md').write_text('改过的规则', encoding='utf-8')
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'source-newer')

    def test_legacy_row_without_source_kind_still_checked(self):
        """T3 前的旧台账行没有 source_kind／source_url 等字段：按 kind 推导来源类型。"""
        target = self.program / 'data' / 'skills' / '01剧本准备SKILL' / 'old.skill.md'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('---\nname: old-one\nstage: script\n---\n# 旧条目\n正文\n',
                          encoding='utf-8')
        digest = skill_import_service._tree_digest(target)
        key = '01剧本准备SKILL/old.skill.md'
        source = self.root / 'legacy-src' / 'old.skill.md'
        source.parent.mkdir(parents=True)
        source.write_text(target.read_text(encoding='utf-8'), encoding='utf-8')
        skill_import_service.save(skill_import_service.ledger_path(self.program),
                                   {'version': 1, 'items': {key: {
                                       'source': str(source), 'kind': 'manifest',
                                       'name': 'old-one', 'sha256': digest,
                                       'imported_at': '2026-01-01 00:00:00'}}})
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'unchanged')
        source.write_text('---\nname: old-one\nstage: script\n---\n# 旧条目\n改了\n',
                          encoding='utf-8')
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'source-newer')


class CheckUpdatesRepoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)
        self.repo = self.root / 'repo'
        self.repo.mkdir()

    def test_local_repo_per_candidate_status(self):
        write_manifest(self.repo / 'a.skill.md', name='ra', stage='script')
        write_manifest(self.repo / 'b.skill.md', name='rb', stage='script')
        skill_import_service.import_from_repo(str(self.repo), self.program,
                                              self.registry, confirm=lambda m: True)
        rows = ledger_rows(self.program)
        self.assertEqual(len(rows), 2)
        statuses = skill_import_service.check_updates(self.program)
        self.assertEqual(set(statuses.values()), {'unchanged'})
        # 只改一个候选：它的行 source-newer，另一行仍 unchanged。
        (self.repo / 'a.skill.md').write_text(
            (self.repo / 'a.skill.md').read_text(encoding='utf-8') + '\n改\n',
            encoding='utf-8')
        statuses = skill_import_service.check_updates(self.program)
        by_name = {rows[k]['name']: statuses[k] for k in rows}
        self.assertEqual(by_name['ra'], 'source-newer')
        self.assertEqual(by_name['rb'], 'unchanged')

    def test_local_repo_missing_dir_and_vanished_candidate(self):
        write_manifest(self.repo / 'gone.skill.md', name='gone', stage='script')
        skill_import_service.import_from_repo(str(self.repo), self.program,
                                              self.registry, confirm=lambda m: True)
        key = only_key(ledger_rows(self.program))
        # 候选从仓库消失（行还在）：source-missing。
        (self.repo / 'gone.skill.md').unlink()
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'source-missing')
        # 整个本地仓库目录没了：同样 source-missing。
        write_manifest(self.repo / 'gone.skill.md', name='gone', stage='script')
        import shutil
        shutil.rmtree(self.repo)
        self.assertEqual(skill_import_service.check_updates(self.program)[key], 'source-missing')

    def test_remote_repo_row_uses_clone_probe(self):
        """import_from_repo 的 url 行带 source_url/source_ref：更新检测重新克隆比对。"""
        calls = []

        def fake_clone(url, ref, dest):
            calls.append((url, ref))
            Path(dest).mkdir(parents=True, exist_ok=True)
            body = '# V%s\n' % len(calls)
            write_manifest(Path(dest) / 'r.skill.md', name='remote-repo',
                           stage='script', body=body)

        with mock.patch.object(skill_import_service, '_git_clone', side_effect=fake_clone):
            skill_import_service.import_from_repo('o/r@main', self.program,
                                                  self.registry, confirm=lambda m: True)
            key = only_key(ledger_rows(self.program))
            statuses = skill_import_service.check_updates(self.program)
            self.assertEqual(statuses[key], 'source-newer',
                             '第二次克隆内容不同→source-newer')
            self.assertEqual(calls[-1], ('https://github.com/o/r', 'main'))
            # 克隆失败（源不可达）→ source-missing。
            with mock.patch.object(skill_import_service, '_git_clone',
                                   side_effect=skill_import_service.ImportBlocked('no net')):
                self.assertEqual(skill_import_service.check_updates(self.program)[key],
                                 'source-missing')


class CheckUpdatesArchiveProbeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    @staticmethod
    def _zip_bytes(entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
        return buffer.getvalue()

    def test_local_zip_probe_unchanged_and_newer(self):
        payload_v1 = self._zip_bytes({'pack/SKILL.md':
            '---\nname: zip-pack\nstage: script\n---\n# 包\n正文\n',
            'pack/references/r.md': '规则一'})
        zip_path = self.root / 'skill-pack.zip'
        zip_path.write_bytes(payload_v1)
        skill_archive.import_archive(zip_path, self.program, self.registry,
                                     confirm=lambda m: True)
        rows = ledger_rows(self.program)
        key = only_key(rows)
        self.assertEqual(rows[key]['source_kind'], 'archive')
        probe = lambda k, r: skill_archive.probe_row(k, r, self.program, self.registry)
        self.assertEqual(skill_import_service.check_updates(
            self.program, probe=probe)[key], 'unchanged')
        # 换一个内容不同的 zip：条目摘要变→source-newer。
        payload_v2 = self._zip_bytes({'pack/SKILL.md':
            '---\nname: zip-pack\nstage: script\n---\n# 包\n正文二\n',
            'pack/references/r.md': '规则一'})
        zip_path.write_bytes(payload_v2)
        self.assertEqual(skill_import_service.check_updates(
            self.program, probe=probe)[key], 'source-newer')
        # zip 被删：source-missing。
        zip_path.unlink()
        self.assertEqual(skill_import_service.check_updates(
            self.program, probe=probe)[key], 'source-missing')

    def test_probe_absent_leaves_archive_rows_source_missing(self):
        """不接探针时 archive 行无法本地判定→source-missing（UI 总会接探针）。"""
        payload = self._zip_bytes({'p/SKILL.md':
            '---\nname: zp\nstage: script\n---\n# 包\n正文\n'})
        zip_path = self.root / 'p.zip'
        zip_path.write_bytes(payload)
        skill_archive.import_archive(zip_path, self.program, self.registry,
                                     confirm=lambda m: True)
        key = only_key(ledger_rows(self.program))
        self.assertEqual(skill_import_service.check_updates(self.program)[key],
                         'source-missing')


class CheckUpdatesRemoteProbeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    @staticmethod
    def _zip_bytes(entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
        return buffer.getvalue()

    class FakeResponse:
        def __init__(self, data):
            self._stream = io.BytesIO(data)
            self.headers = {}

        def read(self, n=-1):
            return self._stream.read(n)

        def close(self):
            pass

    def _remote_probe(self, opener, cache):
        def probe(key, row):
            return skill_remote_service.probe_row(
                key, row, self.program, self.registry, opener=opener, cache=cache)
        return probe

    def test_remote_zip_row_re_downloads_and_compares(self):
        payload = {'data': self._zip_bytes({'pack/SKILL.md':
            '---\nname: rzip\nstage: script\n---\n# 远程包\n一\n'})}
        opener = mock.Mock(side_effect=lambda url, timeout=None, **kw:
                           self.FakeResponse(payload['data']))
        with mock.patch.dict(os.environ):
            os.environ.pop('DRAMA_SUPPRESS_NETWORK', None)
            skill_remote_service.import_from_url('https://cdn.example.com/p.zip',
                                                 self.program, self.registry,
                                                 confirm=lambda m: True, opener=opener)
        key = only_key(ledger_rows(self.program))
        # 同一份字节再下→unchanged（缓存命中同名文件覆盖写）。
        cache = {}
        statuses = skill_import_service.check_updates(
            self.program, probe=self._remote_probe(opener, cache))
        self.assertEqual(statuses[key], 'unchanged')
        # 源端换了内容→source-newer。
        payload['data'] = self._zip_bytes({'pack/SKILL.md':
            '---\nname: rzip\nstage: script\n---\n# 远程包\n二\n'})
        cache.clear()
        statuses = skill_import_service.check_updates(
            self.program, probe=self._remote_probe(opener, cache))
        self.assertEqual(statuses[key], 'source-newer')
        # 404 → source-missing。
        opener.side_effect = skill_import_service.ImportBlocked('下载失败：HTTP 404')
        cache.clear()
        statuses = skill_import_service.check_updates(
            self.program, probe=self._remote_probe(opener, cache))
        self.assertEqual(statuses[key], 'source-missing')

    def test_remote_probe_declines_non_remote_rows(self):
        """本地 file/dir/repo 行交给默认判定；probe 返回 None 表示不接管。"""
        source = write_manifest(self.root / 's' / 'x.skill.md', name='lx', stage='script')
        import_file(self.program, self.registry, source)
        key = only_key(ledger_rows(self.program))
        probe = lambda k, r: skill_remote_service.probe_row(
            k, r, self.program, self.registry, opener=mock.Mock())
        self.assertEqual(skill_import_service.check_updates(
            self.program, probe=probe)[key], 'unchanged')


class DeleteClosureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.program, self.registry = make_program(self.root)

    def test_uninstall_removes_ledger_row(self):
        source = write_manifest(self.root / 'src' / 'd.skill.md', name='delta', stage='script')
        import_file(self.program, self.registry, source)
        self.assertEqual(len(ledger_rows(self.program)), 1)
        self.registry.scan(force=True)
        skill_import_service.uninstall_skill(self.program, self.registry, 'delta')
        self.assertEqual(ledger_rows(self.program), {}, '卸载成功后台账不得残留行')

    def test_forget_ledger_targets_only_drops_matching_rows(self):
        a = write_manifest(self.root / 'src' / 'e1.skill.md', name='e-one', stage='script')
        b = write_manifest(self.root / 'src' / 'e2.skill.md', name='e-two', stage='script')
        import_file(self.program, self.registry, a)
        import_file(self.program, self.registry, b)
        self.assertEqual(len(ledger_rows(self.program)), 2)
        target = self.program / 'data' / 'skills' / '01剧本准备SKILL' / 'e1.skill.md'
        removed = skill_import_service.forget_ledger_targets(self.program, [target])
        self.assertEqual(removed, 1)
        rows = ledger_rows(self.program)
        self.assertEqual([rows[k]['name'] for k in rows], ['e-two'])
        # 再删一次幂等：无匹配行返回 0。
        self.assertEqual(skill_import_service.forget_ledger_targets(
            self.program, [target]), 0)

class PanelDeleteLedgerTests(unittest.TestCase):
    """面板勾选删除成功后台账行同步摘除（GUI，隐藏桌面；同 test_skills 删除用例夹具）。"""
    import tkinter as tk
    from test_skills import PanelTests
    tk = tk
    setUp = PanelTests.setUp

    def test_delete_checked_skills_clears_ledger(self):
        program = Path(self.tmp.name) / '程序'
        builtin = program / 'skills'
        user = program / 'data' / 'skills'
        (builtin / '01剧本准备SKILL').mkdir(parents=True)
        registry = skill_registry.Registry(builtin, user_root=user)
        source = Path(self.tmp.name) / 'panel-del.skill.md'
        source.write_text('---\nname: panel-del\nstage: script\n---\n# 面板删除\n正文\n',
                          encoding='utf-8')
        plan = skill_import_service.plan_import(
            source, registry.user_stage_directory_for('script'), 'script', registry)
        skill_import_service.perform_import(plan, program)
        ledger = skill_import_service.ledger_path(program)
        self.assertEqual(len(skill_import_service._read_items(ledger)), 1)
        with mock.patch.object(skill_panel, '__file__', str(program / 'skill_panel.py')):
            with mock.patch.object(skill_panel.skill_registry, 'default_registry',
                                   return_value=registry):
                with mock.patch.object(skill_panel, 'confirm', return_value=True):
                    panel = skill_panel.Panel(self.win, self.desktop, 'script')
                    self.addCleanup(panel.destroy)
                    self.assertIn('panel-del', panel.vars)
                    panel.vars['panel-del'].set(True)
                    records = panel.delete_checked_skills()
        self.assertTrue(records)
        self.assertFalse((user / '01剧本准备SKILL' / 'panel-del.skill.md').exists())
        self.assertEqual(skill_import_service._read_items(ledger), {},
                         '面板删除成功后台账必须无残留行')


class PanelUpdateCheckTests(unittest.TestCase):
    """面板「检查更新」入口与重新导入分发（GUI，隐藏桌面）。"""
    import tkinter as tk
    from test_skills import PanelTests
    tk = tk
    setUp = PanelTests.setUp

    def _panel(self):
        """面板＋假程序目录：``__file__`` 补丁持续到用例结束，程序派生路径全部落在临时目录。"""
        program = Path(self.tmp.name) / '程序'
        builtin = program / 'skills'
        (builtin / '01剧本准备SKILL').mkdir(parents=True, exist_ok=True)
        registry = skill_registry.Registry(builtin, user_root=program / 'data' / 'skills')
        for module, value in (
                (skill_panel, str(program / 'skill_panel.py')),
                (skill_import_service, str(program / 'skill_import_service.py'))):
            patcher = mock.patch.object(module, '__file__', value)
            patcher.start()
            self.addCleanup(patcher.stop)
        with mock.patch.object(skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        return panel, program, registry

    def test_manage_menu_offers_update_check_and_dispatches(self):
        self.assertIn('检查更新', skill_panel.MANAGE_LABELS)
        panel, _program, _registry = self._panel()
        panel.skill_action.set('检查更新')
        with mock.patch.object(panel, 'check_skill_updates', return_value='ok') as check:
            self.assertEqual(panel.choose_skill_action(), 'ok')
            check.assert_called_once()
        self.assertEqual(panel.skill_action.get(), skill_panel.MANAGE_ALL)

    def test_check_updates_empty_ledger_reports_status(self):
        panel, _program, _registry = self._panel()
        panel.check_skill_updates()
        self.assertIn('没有导入记录', panel.state.cget('text'))

    def test_source_newer_file_row_reimports_via_service_path(self):
        """file 行 source-newer → 重新导入走 plan_import＋perform_import，旧版进回收站。"""
        import skill_panel_import
        panel, program, registry = self._panel()
        source = Path(self.tmp.name) / 'upd.skill.md'
        source.write_text('---\nname: upd-one\nstage: script\n---\n# 一\n正文\n',
                          encoding='utf-8')
        plan = skill_import_service.plan_import(
            source, registry.user_stage_directory_for('script'), 'script', registry)
        skill_import_service.perform_import(plan, program)
        # 源端更新 → check_updates 报 source-newer。
        source.write_text('---\nname: upd-one\nstage: script\n---\n# 二\n正文\n',
                          encoding='utf-8')
        statuses = skill_import_service.check_updates(program)
        key = only_key(statuses)
        self.assertEqual(statuses[key], 'source-newer')
        row = skill_import_service.ledger_items(program)[key]
        with mock.patch.object(skill_panel_import, 'confirm', return_value=True):
            ok = skill_panel_import._reimport_ledger_row(panel, key, row)
        self.assertTrue(ok)
        target = program / 'data' / 'skills' / '01剧本准备SKILL' / 'upd.skill.md'
        self.assertIn('# 二', target.read_text(encoding='utf-8'))
        # 台账 sha256 已刷新为新内容 → 再查 unchanged。
        statuses = skill_import_service.check_updates(program)
        self.assertEqual(statuses[key], 'unchanged')


if __name__ == '__main__':
    unittest.main()
