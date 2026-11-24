# -*- coding: utf-8 -*-
"""O45：把《分发清单》变成可复跑、可校验的分发构建器。"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import release_runtime
from scripts import release_snapshot
from tests.test_release_runtime import write_dist

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'distribution_build.py'
_spec = importlib.util.spec_from_file_location('distribution_build_subject', SCRIPT)
subject = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(subject)

MANIFEST = {
    'keep': ['启动漫剧制作助手.pyw', '启动助手.cmd', '运行环境/Python/', '程序/app.py',
             '程序/desktop.py', '程序/requirements.txt', '程序/skills/', '程序/配置/',
             '程序/agent/', '程序/extra/', '程序/voice_engine/'],
    'exclude': ['程序/tests/**', '程序/tasks_round/**', '程序/维护记录/**',
                '程序/scripts/**', '程序/logs/**', '程序/private/**',
                '程序/external_tools.lock.json'],
}

SOURCE_FILES = {
    '启动漫剧制作助手.pyw': 'launcher',
    '启动助手.cmd': 'cmd',
    '运行环境/Python/python.exe': 'exe',
    '程序/app.py': 'app',
    '程序/desktop.py': 'desktop',
    '程序/requirements.txt': 'requests==2.34.2\n',
    '程序/voice_engine/requirements.lock': 'numpy==1.26.4\n',
    '程序/voice_engine/supply_chain.lock.json': json.dumps({
        'source_template': 'https://pypi.org/project/{name}/{version}/',
        'licenses': {'numpy': 'BSD-3-Clause'},
    }),
    '程序/external_tools.lock.json': json.dumps({'tools': {
        '运行环境/Python/python.exe': {'version': 'Python fixture', 'sha256': 'a' * 64,
                                      'bytes': 3, 'source': 'https://python.org/',
                                      'license': 'PSF-2.0'},
    }}),
    '程序/skills/example-package/SKILL.md': 'jingju',
    '程序/配置/默认.json': '{}',
    '程序/agent/core.py': 'core',
    '程序/extra/thing.txt': 'extra',
    '程序/tests/test_x.py': 'test',
    '程序/tasks_round/a.md': 'round',
    '程序/维护记录/b.json': '{}',
    '程序/维护记录/外部技能包哈希.json': json.dumps({'packages': {}}),
    '程序/scripts/tool.py': 'tool',
    '程序/logs/x.log': 'log',
    '程序/private/密钥/a.dpapi': 'secret',
    '程序/a.pyc': 'pyc',
    '.git/config': 'git',
}

# 规格《03 安装签名与分发》§2.3：升级只覆盖程序文件；下列本机数据只保留不覆盖。
# `程序/data/skill_note_terms_zh.json` 是唯一随包的内置数据文件，属程序文件。
UPGRADE_DATA_EXCLUDE = [
    '程序/config.json', '程序/projects.json', '程序/desktop_settings.json',
    '程序/data/*/**', '程序/data/desktop_settings.json', '程序/data/客户端档案.json',
    '程序/data/语音识别.json', '程序/data/语音词典.json', '程序/data/*.flag',
    '程序/配置/宠物/**', '程序/配置/素材库.json',
]

UPGRADE_USER_FILES = {
    '程序/config.json': '{"downloads_root": "D:/库", "video_backend": "comfy"}',
    '程序/projects.json': '{"active": "样例", "projects": [{"name": "样例"}]}',
    '程序/desktop_settings.json': '{"geometry": "1024x768"}',
    '程序/private/密钥/a.dpapi': 'key-bytes',
    '程序/private/账户/token.dpapi': 'token-bytes',
    '程序/private/桌面续发/keep.txt': 'keep-me',
    '程序/data/job_store/jobs.json': '{"jobs": [1]}',
    '程序/data/artifact_index/demo/index.json': '{"items": []}',
    '程序/data/metrics/usage.jsonl': '{"n": 1}\n',
    '程序/data/desktop_settings.json': '{"local": true}',
    '程序/data/客户端档案.json': '{"profile": "fixture"}',
    '程序/data/语音识别.json': '{"backend": "offline"}',
    '程序/data/语音词典.json': '{"words": []}',
    '程序/data/selfcheck_failopen.flag': '',
    '程序/配置/宠物/配置.json': '{"pet": "fixture"}',
    '程序/配置/素材库.json': '{"assets": [1, 2]}',
    '程序/logs/app.log': 'startup ok\n',
}

UPGRADE_PROJECT_FILES = {
    '我的项目/样例/skill_config.json': '{"locks": []}',
    '我的项目/样例/素材/图1.png': b'\x89PNG\r\n\x1a\nfake-bytes',
    '我的项目/样例/分镜/shot1.json': '{"shot": 1}',
    '我的项目/样例/音频/v1.wav': b'RIFFfake',
}

UPGRADE_PROGRAM_V2 = {
    '启动漫剧制作助手.pyw': 'launcher-v2',
    '程序/app.py': 'app-v2',
    '程序/desktop.py': 'desktop-v2',
    '程序/voice_engine/requirements.lock': 'numpy==9.9\n',
    '运行环境/Python/python.exe': 'exe-v2',
    '程序/data/skill_note_terms_zh.json': 'terms-v2',
}


def upgrade_manifest():
    return {'keep': MANIFEST['keep'] + ['程序/data/skill_note_terms_zh.json'],
            'exclude': MANIFEST['exclude'] + UPGRADE_DATA_EXCLUDE}


def make_source(root):
    root = Path(root)
    for rel, text in SOURCE_FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    return root


class DistributionBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = make_source(self.base / '源')
        self.addCleanup(self.temp.cleanup)

    def stray(self, rel='程序/stray/note.txt'):
        path = self.source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('stray', encoding='utf-8')
        return path

    def test_actual_manifest_excludes_agent_archive_and_window_probe_log(self):
        manifest = subject.parse_manifest()
        relatives = ('.agent-handoff/archive/snapshot-before-o06-pause-20261012.md', '_wm.log')
        for relative in relatives:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'diagnostic-history')
        planned = subject.plan(self.source, manifest)
        for relative in relatives:
            self.assertIn(relative, planned['excluded'])
            self.assertNotIn(relative, planned['keep'])
            self.assertEqual((self.source / relative).read_bytes(), b'diagnostic-history')

    def test_actual_manifest_excludes_unlicensed_external_skill(self):
        relative = '程序/skills/01 剧本准备SKILL/剧本锻造/SKILL.md'
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('unlicensed fixture', encoding='utf-8')
        planned = subject.plan(self.source, subject.parse_manifest())
        self.assertIn(relative, planned['excluded'])
        self.assertNotIn(relative, planned['keep'])

    def test_actual_manifest_never_ships_machine_state_under_data_or_config(self):
        machine_state = (
            '程序/data/job_store/jobs.json',
            '程序/data/artifact_index/demo/index.json',
            '程序/data/config_snapshots/pool-1.json',
            '程序/data/metrics/usage.jsonl',
            '程序/data/voice_asr_venv/Scripts/python.exe',
            '程序/data/voice_models/demo/model.bin',
            '程序/data/skills/demo/SKILL.md',
            '程序/data/desktop_settings.json',
            '程序/data/客户端档案.json',
            '程序/data/语音识别.json',
            '程序/data/语音词典.json',
            '程序/data/selfcheck_failopen.flag',
            '程序/data/autotune_disable_prefetch.flag',
            '程序/配置/宠物/配置.json',
            '程序/配置/素材库.json',
        )
        shipped_seeds = (
            '程序/data/skill_note_terms_zh.json',
            '程序/配置/客户端档案.json',
            '程序/配置/SKILL/预设.json',
        )
        unregistered = ('程序/data/未登记.json', '程序/配置/未登记.json')
        for relative in machine_state + shipped_seeds + unregistered:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture', encoding='utf-8')
        planned = subject.plan(self.source, subject.parse_manifest())
        for relative in machine_state:
            self.assertIn(relative, planned['excluded'])
            self.assertNotIn(relative, planned['keep'])
        for relative in shipped_seeds:
            self.assertIn(relative, planned['keep'])
        for relative in unregistered:
            self.assertIn(relative, planned['undecided'])

    def test_parse_manifest_reads_both_tables_of_the_real_document(self):
        parsed = subject.parse_manifest()
        self.assertIn('启动漫剧制作助手.pyw', parsed['keep'])
        self.assertIn('开发者工具/启动助手.cmd', parsed['keep'])
        self.assertIn('程序/tests/**', parsed['exclude'])
        self.assertIn('程序/private/**', parsed['exclude'])
        self.assertNotIn('路径/模式', parsed['keep'])
        self.assertNotIn('原因', parsed['keep'])

    def test_plan_splits_keep_excluded_and_undecided(self):
        self.stray()
        buckets = subject.plan(self.source, MANIFEST)
        self.assertIn('程序/app.py', buckets['keep'])
        self.assertIn('程序/skills/example-package/SKILL.md', buckets['keep'])
        self.assertIn('程序/tests/test_x.py', buckets['excluded'])
        self.assertIn('程序/private/密钥/a.dpapi', buckets['excluded'])
        self.assertIn('程序/a.pyc', buckets['excluded'])
        self.assertNotIn('.git/config', buckets['keep'] + buckets['excluded'])
        self.assertIn('程序/stray/note.txt', buckets['undecided'])

    def test_build_copies_only_the_keep_set_and_never_touches_source(self):
        before = {rel: (self.source / rel).read_bytes()
                  for rel in subject.candidate_files(self.source)}
        report = subject.build(self.base / 'out', self.source, MANIFEST)
        after = {rel: (self.source / rel).read_bytes()
                 for rel in subject.candidate_files(self.source)}
        self.assertEqual(before, after)
        out = self.base / 'out'
        self.assertTrue((out / '程序/app.py').is_file())
        self.assertFalse((out / '程序/tests/test_x.py').exists())
        self.assertFalse((out / '程序/private/密钥/a.dpapi').exists())
        self.assertFalse((out / '程序/logs/x.log').exists())
        self.assertEqual(report['files'], len(subject.candidate_files(out)) - 1)

    def test_build_prunes_unlocked_runtime_distribution_from_copy_only(self):
        write_dist(self.source, 'requests', '2.34.2', 'requests')
        write_dist(self.source, 'pydantic', '2.14.3', 'pydantic')
        report = subject.build(self.base / 'out', self.source, MANIFEST)
        self.assertEqual(report['runtime']['removed_distributions'], ['pydantic'])
        self.assertTrue((self.source / release_runtime.SITE / 'pydantic/__init__.py').is_file())
        self.assertFalse((self.base / 'out' / release_runtime.SITE / 'pydantic/__init__.py').exists())
        verdict = subject.verify(self.base / 'out', self.source, MANIFEST)
        self.assertTrue(verdict['checks']['release_runtime']['ok'], verdict)

    def test_build_writes_version_and_per_file_digest(self):
        subject.build(self.base / 'out', self.source, MANIFEST)
        saved = json.loads((self.base / 'out' / subject.DIGEST_NAME).read_text(encoding='utf-8'))
        rows = {item['path']: item for item in saved['entries']}
        self.assertEqual(rows['程序/app.py']['sha256'], hashlib.sha256(b'app').hexdigest())
        self.assertEqual(rows['程序/app.py']['bytes'], len(b'app'))
        self.assertIn('version', saved)
        self.assertIn('exclude_patterns', saved)

    def test_build_refuses_destination_inside_source(self):
        with self.assertRaises(ValueError):
            subject.build(self.source / 'out', self.source, MANIFEST)

    def test_build_refuses_nonempty_destination(self):
        out = self.base / 'out'
        out.mkdir()
        (out / 'existing.txt').write_text('x', encoding='utf-8')
        with self.assertRaises(ValueError):
            subject.build(out, self.source, MANIFEST)

    def test_side_by_side_build_does_not_change_previous_release(self):
        previous = self.base / 'previous-release'
        subject.build(previous, self.source, MANIFEST)
        before = {rel: (previous / rel).read_bytes()
                  for rel in subject.candidate_files(previous)}
        subject.build(self.base / 'next-release', self.source, MANIFEST)
        after = {rel: (previous / rel).read_bytes()
                 for rel in subject.candidate_files(previous)}
        self.assertEqual(after, before)

    def test_build_refuses_undecided_unless_explicitly_allowed(self):
        self.stray()
        with self.assertRaises(ValueError):
            subject.build(self.base / 'out', self.source, MANIFEST)
        report = subject.build(self.base / 'out2', self.source, MANIFEST,
                               allow_undecided=True)
        self.assertGreater(report['files'], 0)
        self.assertTrue((self.base / 'out2' / '程序/stray/note.txt').is_file())

    def test_verify_accepts_a_clean_build(self):
        subject.build(self.base / 'out', self.source, MANIFEST)
        verdict = subject.verify(self.base / 'out', self.source, MANIFEST)
        self.assertTrue(verdict['ok'], verdict)
        self.assertTrue(verdict['release_ready'], verdict)
        self.assertTrue((self.base / 'out/sbom.cdx.json').is_file())
        self.assertTrue((self.base / 'out/THIRD_PARTY_NOTICES.txt').is_file())
        self.assertGreater(verdict['checks']['supply_chain']['components'], 0)

    def test_verify_blocks_release_when_skill_license_is_unconfirmed(self):
        registry = self.source / '程序/维护记录/外部技能包哈希.json'
        registry.write_text(json.dumps({'packages': {
            'skills/01 剧本准备SKILL/剧本锻造': {
                'source': 'https://github.com/zhlmi/script-forging.git',
                'commit': 'b' * 40,
                'tree': 'c' * 40,
            },
        }}), encoding='utf-8')
        skill = self.source / '程序/skills/01 剧本准备SKILL/剧本锻造/SKILL.md'
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text('fixture', encoding='utf-8')
        subject.build(self.base / 'out', self.source, MANIFEST)
        verdict = subject.verify(self.base / 'out', self.source, MANIFEST)
        self.assertTrue(verdict['ok'], verdict)
        self.assertFalse(verdict['release_ready'], verdict)
        self.assertIn('skill:skills/01 剧本准备SKILL/剧本锻造',
                      verdict['checks']['supply_chain']['release_blockers'])

    def test_excluded_unlicensed_skill_is_absent_from_release_sbom(self):
        registry = self.source / '程序/维护记录/外部技能包哈希.json'
        registry.write_text(json.dumps({'packages': {
            'skills/01 剧本准备SKILL/剧本锻造': {
                'source': 'https://github.com/zhlmi/script-forging.git',
                'commit': 'b' * 40,
                'tree': 'c' * 40,
            },
        }}), encoding='utf-8')
        skill = self.source / '程序/skills/01 剧本准备SKILL/剧本锻造/SKILL.md'
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text('fixture', encoding='utf-8')
        manifest = {key: list(value) for key, value in MANIFEST.items()}
        manifest['exclude'].append('程序/skills/01 剧本准备SKILL/剧本锻造/**')
        subject.build(self.base / 'out', self.source, manifest)
        verdict = subject.verify(self.base / 'out', self.source, manifest)
        self.assertTrue(verdict['release_ready'], verdict)
        sbom = json.loads((self.base / 'out/sbom.cdx.json').read_text(encoding='utf-8'))
        self.assertNotIn('skill:skills/01 剧本准备SKILL/剧本锻造',
                         {item['bom-ref'] for item in sbom['components']})

    def test_verify_flags_injected_excluded_file(self):
        subject.build(self.base / 'out', self.source, MANIFEST)
        leak = self.base / 'out' / '程序/tests/leaked.py'
        leak.parent.mkdir(parents=True, exist_ok=True)
        leak.write_text('x', encoding='utf-8')
        verdict = subject.verify(self.base / 'out', self.source, MANIFEST)
        self.assertFalse(verdict['ok'])
        self.assertIn('程序/tests/leaked.py', verdict['checks']['no_excluded']['hits'])

    def test_verify_flags_a_missing_required_entry(self):
        subject.build(self.base / 'out', self.source, MANIFEST)
        (self.base / 'out' / '程序/app.py').unlink()
        verdict = subject.verify(self.base / 'out', self.source, MANIFEST)
        self.assertFalse(verdict['ok'])
        self.assertIn('程序/app.py', verdict['checks']['keep_present']['missing'])

    def test_verify_checks_every_packaged_skill_in_digest(self):
        subject.build(self.base / 'out', self.source, MANIFEST)
        relative = '程序/skills/example-package/SKILL.md'
        (self.base / 'out' / relative).unlink()
        verdict = subject.verify(self.base / 'out', self.source, MANIFEST)
        self.assertFalse(verdict['ok'])
        self.assertIn(relative, verdict['checks']['digest']['mismatch'])

    def test_cli_plan_only_reports_and_copies_nothing(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = subject.main(['--root', str(self.source)])
        self.assertEqual(code, 0)
        self.assertIn('undecided', buffer.getvalue())
        self.assertEqual(list(self.base.glob('out*')), [])

    def _write_payloads(self, root, payloads):
        root = Path(root)
        for rel, data in payloads.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, bytes):
                path.write_bytes(data)
            else:
                path.write_text(data, encoding='utf-8')

    def _overlay(self, package, install, limit=None):
        """zip 覆盖安装：把分发副本里的文件逐个覆盖到安装目录；limit 模拟中途断电。"""
        package = Path(package)
        copied = 0
        for path in sorted(p for p in package.rglob('*') if p.is_file()):
            target = Path(install) / path.relative_to(package)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
            if limit is not None and copied >= limit:
                break
        return copied

    def _tree(self, root):
        root = Path(root)
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in sorted(root.rglob('*')) if p.is_file()}

    def _upgrade_fixture(self):
        """旧版安装目录＝旧源构建＋运行时本机数据＋用户项目；另构建新版分发副本。"""
        manifest = upgrade_manifest()
        old_source = make_source(self.base / '旧源')
        self._write_payloads(old_source, UPGRADE_USER_FILES)
        self._write_payloads(old_source, {'程序/data/skill_note_terms_zh.json': 'terms-v1'})
        install = self.base / '安装'
        subject.build(install, old_source, manifest)
        installed = {rel: (data + '-installed' if isinstance(data, str) else data)
                     for rel, data in UPGRADE_USER_FILES.items()}
        self._write_payloads(install, installed)
        self._write_payloads(install, UPGRADE_PROJECT_FILES)
        new_source = make_source(self.base / '新源')
        self._write_payloads(new_source, UPGRADE_USER_FILES)
        self._write_payloads(new_source, UPGRADE_PROGRAM_V2)
        new_dist = self.base / '新副本'
        subject.build(new_dist, new_source, manifest)
        return install, new_dist

    def test_upgrade_preserves_user_data_byte_for_byte(self):
        install, new_dist = self._upgrade_fixture()
        before = {rel: (install / rel).read_bytes() for rel in UPGRADE_USER_FILES}
        project_before = self._tree(install / '我的项目')
        saved = json.loads((new_dist / subject.DIGEST_NAME).read_text(encoding='utf-8'))
        paths = {item['path'] for item in saved['entries']}
        self.assertFalse(paths & set(UPGRADE_USER_FILES), paths & set(UPGRADE_USER_FILES))
        for rel in paths:
            self.assertFalse(rel.startswith(('程序/private/', '程序/配置/宠物/', '程序/logs/')), rel)
            if rel.startswith('程序/data/'):
                self.assertEqual(rel, '程序/data/skill_note_terms_zh.json', rel)
        self._overlay(new_dist, install)
        verdict = release_snapshot.check_upgrade(new_dist, install)
        self.assertTrue(verdict['ok'], verdict)
        after = {rel: (install / rel).read_bytes() for rel in UPGRADE_USER_FILES}
        self.assertEqual(before, after)
        self.assertEqual(project_before, self._tree(install / '我的项目'))

    def test_upgrade_preserves_replaces_program_files_with_new(self):
        install, new_dist = self._upgrade_fixture()
        self._overlay(new_dist, install)
        verdict = release_snapshot.check_upgrade(new_dist, install)
        self.assertTrue(verdict['ok'], verdict)
        for rel, text in UPGRADE_PROGRAM_V2.items():
            self.assertEqual((install / rel).read_text(encoding='utf-8'), text, rel)
        self.assertEqual((install / '程序/data/语音识别.json').read_text(encoding='utf-8'),
                         UPGRADE_USER_FILES['程序/data/语音识别.json'] + '-installed')
        self.assertEqual((install / '程序/config.json').read_text(encoding='utf-8'),
                         UPGRADE_USER_FILES['程序/config.json'] + '-installed')

    def test_upgrade_preserves_rollback_restores_old_install(self):
        install, new_dist = self._upgrade_fixture()
        snap = self.base / '升级前快照'
        shutil.copytree(install, snap)
        manifest_before = self._tree(install)
        total = len([p for p in new_dist.rglob('*') if p.is_file()])
        copied = self._overlay(new_dist, install, limit=max(1, total // 2))
        self.assertLess(copied, total)
        verdict = release_snapshot.check_upgrade(new_dist, install)
        self.assertFalse(verdict['ok'], verdict)
        self.assertTrue(verdict['missing'] or verdict['mismatch'], verdict)
        self.assertNotEqual(self._tree(install), manifest_before)
        shutil.rmtree(install)
        shutil.copytree(snap, install)
        self.assertEqual(manifest_before, self._tree(install))


if __name__ == '__main__':
    unittest.main()
