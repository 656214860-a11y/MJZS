# -*- coding: utf-8 -*-
"""R3125（任务书 P4，Q7=B／Q18／Q19）：旧目录迁移工具。

覆盖：只搬 ``stage_layout.LEGACY`` 登记的旧目录；按后缀落到 docs／assets／output；
迁移前逐文件备份、目标冲突不覆盖、重复执行幂等；E1 清单重指向（避免已完成阶段退回
未完成）与 E2 绝对路径改写；``--dry-run`` 不写盘。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import contract.stage_layout as stage_layout
from agent.core import save
from orchestrator import legacy_migration


def _project(tmp):
    root = Path(tmp) / '项目'
    (root / 'writing' / '创意_20260101').mkdir(parents=True)
    (root / 'writing' / '创意_20260101' / '大纲.md').write_text('大纲正文', encoding='utf-8')
    (root / 'episode' / 'frames').mkdir(parents=True)
    (root / 'episode' / 'frames' / 'EP001_SH001_8a7043f5.png').write_bytes(b'\x89PNG')
    return root


class PlanTests(unittest.TestCase):
    def test_plan_maps_docs_and_media_to_their_stage_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            ops = {op['source']: op for op in legacy_migration.plan(root)}
            doc = ops['writing/创意_20260101/大纲.md']
            self.assertEqual(doc['target'], '01剧本准备/docs/大纲.md')
            self.assertEqual(doc['action'], 'move')
            frame = ops['episode/frames/EP001_SH001_8a7043f5.png']
            self.assertEqual(frame['target'], '08首帧管理/assets/EP001_SH001_8a7043f5.png')

    def test_plan_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            before = sorted(p.as_posix() for p in root.rglob('*'))
            legacy_migration.plan(root)
            self.assertEqual(before, sorted(p.as_posix() for p in root.rglob('*')))

    def test_existing_identical_target_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            target = root / '01剧本准备' / 'docs' / '大纲.md'
            target.parent.mkdir(parents=True)
            target.write_text('大纲正文', encoding='utf-8')
            op = {item['source']: item for item in legacy_migration.plan(root)}['writing/创意_20260101/大纲.md']
            self.assertEqual((op['action'], op['reason']), ('skip', '目标已存在且内容一致'))

    def test_existing_different_target_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            target = root / '01剧本准备' / 'docs' / '大纲.md'
            target.parent.mkdir(parents=True)
            target.write_text('另一份正文', encoding='utf-8')
            op = {item['source']: item for item in legacy_migration.plan(root)}['writing/创意_20260101/大纲.md']
            self.assertEqual(op['action'], 'conflict')


class ApplyTests(unittest.TestCase):
    def test_move_backs_up_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            done, stamp = legacy_migration.apply(root, legacy_migration.plan(root))
            moved = [op for op in done if op['action'] == 'moved']
            self.assertEqual(len(moved), 2)
            self.assertTrue((root / '01剧本准备' / 'docs' / '大纲.md').is_file())
            self.assertFalse((root / 'writing' / '创意_20260101' / '大纲.md').exists())
            backup = root / Path(*moved[0]['backup'].split('/'))
            self.assertTrue(backup.is_file())
            # 工作流任务/迁移备份/<时间戳>/<原相对路径>
            self.assertEqual(backup.parents[3].name, '迁移备份')
            again = [op for op in legacy_migration.plan(root) if op['action'] == 'move']
            self.assertEqual(again, [])

    def test_report_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            done, stamp = legacy_migration.apply(root, legacy_migration.plan(root))
            path = legacy_migration.report(root, done, stamp)
            self.assertTrue(path.is_file())
            text = path.read_text(encoding='utf-8')
            self.assertIn('迁移报告', text)
            self.assertIn('大纲.md', text)


class ManifestTests(unittest.TestCase):
    def test_repoint_manifest_follows_the_moved_storyboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            legacy = root / 'episode' / 'audio' / 'S01.wav'
            legacy.parent.mkdir(parents=True)
            legacy.write_bytes(b'RIFF')
            manifest = root / '11配音与字幕' / '成果确认' / 'old.json'
            manifest.parent.mkdir(parents=True)
            save(manifest, {'schema': 1, 'scope': {'source': 'episode/audio/S01.wav',
                                                   'source_sha256': 'x'}, 'outputs': []})
            done, _stamp = legacy_migration.apply(root, legacy_migration.plan(root))
            saved = legacy_migration.repoint_manifests(root, legacy_migration.mapping_of(done))
            self.assertTrue(saved)
            self.assertFalse(manifest.exists(), '旧指纹清单应当被替换')
            new_path = root / Path(*saved[0].split('/'))
            data = json.loads(new_path.read_text(encoding='utf-8'))
            self.assertEqual(data['scope']['source'], '11配音与字幕/assets/S01.wav')

    def test_absolute_paths_are_rewritten_to_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            manifest = root / '10视频生成' / 'assets' / 'assets_manifest.json'
            manifest.parent.mkdir(parents=True)
            absolute = str((root / 'episode' / 'frames' / 'EP001_SH001_8a7043f5.png').resolve())
            save(manifest, {'mode': 'local', 'assets': [{'path': absolute}]})
            done, _stamp = legacy_migration.apply(root, legacy_migration.plan(root))
            rewritten = legacy_migration.rewrite_absolute_manifests(root, legacy_migration.mapping_of(done))
            self.assertEqual(rewritten, ['10视频生成/assets/assets_manifest.json'])
            data = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(data['assets'][0]['path'], '08首帧管理/assets/EP001_SH001_8a7043f5.png')


class CliTests(unittest.TestCase):
    def _run(self, *args):
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'migrate_legacy_layout.py'
        return subprocess.run([sys.executable, '-B', str(script), *args],
                              capture_output=True, text=True, encoding='utf-8')

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            before = sorted(p.as_posix() for p in root.rglob('*'))
            done = self._run('--project', str(root), '--dry-run')
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('待迁移', done.stdout)
            self.assertEqual(before, sorted(p.as_posix() for p in root.rglob('*')))

    def test_real_run_moves_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            done = self._run('--project', str(root))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue((root / '01剧本准备' / 'docs' / '大纲.md').is_file())

    def test_missing_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self._run('--project', str(Path(tmp) / '不存在'))
            self.assertEqual(done.returncode, 2)


if __name__ == '__main__':
    unittest.main()
