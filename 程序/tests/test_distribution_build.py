# -*- coding: utf-8 -*-
"""O45：把《分发清单》变成可复跑、可校验的分发构建器。"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'distribution_build.py'
_spec = importlib.util.spec_from_file_location('distribution_build_subject', SCRIPT)
subject = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(subject)

MANIFEST = {
    'keep': ['启动漫剧制作助手.pyw', '启动助手.cmd', '运行环境/Python/', '程序/app.py',
             '程序/desktop.py', '程序/skills/', '程序/配置/', '程序/agent/', '程序/extra/'],
    'exclude': ['程序/tests/**', '程序/tasks_round/**', '程序/维护记录/**',
                '程序/scripts/**', '程序/logs/**', '程序/private/**'],
}

SOURCE_FILES = {
    '启动漫剧制作助手.pyw': 'launcher',
    '启动助手.cmd': 'cmd',
    '运行环境/Python/python.exe': 'exe',
    '程序/app.py': 'app',
    '程序/desktop.py': 'desktop',
    '程序/skills/00全流程SKILL/jingju-skills/SKILL.md': 'jingju',
    '程序/配置/默认.json': '{}',
    '程序/agent/core.py': 'core',
    '程序/extra/thing.txt': 'extra',
    '程序/tests/test_x.py': 'test',
    '程序/tasks_round/a.md': 'round',
    '程序/维护记录/b.json': '{}',
    '程序/scripts/tool.py': 'tool',
    '程序/logs/x.log': 'log',
    '程序/private/密钥/a.dpapi': 'secret',
    '程序/a.pyc': 'pyc',
    '.git/config': 'git',
}


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
        self.assertIn('程序/skills/00全流程SKILL/jingju-skills/SKILL.md', buckets['keep'])
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

    def test_verify_requires_the_jingju_package(self):
        subject.build(self.base / 'out', self.source, MANIFEST)
        (self.base / 'out' / subject.JINGJU_PACKAGE / 'SKILL.md').unlink()
        verdict = subject.verify(self.base / 'out', self.source, MANIFEST)
        self.assertFalse(verdict['ok'])
        self.assertFalse(verdict['checks']['jingju_package']['ok'])

    def test_cli_plan_only_reports_and_copies_nothing(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = subject.main(['--root', str(self.source)])
        self.assertEqual(code, 0)
        self.assertIn('undecided', buffer.getvalue())
        self.assertEqual(list(self.base.glob('out*')), [])


if __name__ == '__main__':
    unittest.main()
