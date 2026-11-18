# -*- coding: utf-8 -*-
"""轮 4B（D4-c/d/e）：产物版本契约接线——属主读取点 classify 计数、
legacy/missing 照常读、future 可读拒写、写方双写 schema_version+version。

只用临时目录，不碰真实项目与 ``程序/private``。
"""
import json
import tempfile
import unittest
from pathlib import Path

import contract.artifact_schema as artifact_schema
from agent.core import save


class _Temp(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)


def _counts(kind=None):
    rows = artifact_schema.read_state_counts()
    return rows.get(kind, {}) if kind else rows


# ── continuity_ledger（continuity_ledger／continuity_issues 两个 kind）──────
class ContinuityLedgerWiringTests(_Temp):
    def _ledger(self):
        return {'version': 1, 'stage': 'continuity', 'batches': [], 'conflicts': [],
                'cross_batch': [], 'triplets': [], 'drift': [],
                'summary': {'batches': 0, 'shots': 0, 'ok': True, 'problems': []}}

    def test_publish_bundle_dual_writes_and_reads_classify(self):
        import infra.continuity_ledger as cl
        before = dict(_counts('continuity_ledger'))
        target = cl.publish_bundle(self.tmp, self._ledger())
        data = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)
        self.assertEqual(data.get('version'), 1)          # 旧键保留，旧版程序仍能读
        # 读取点分类：current 计数 +1（相对改动前快照）
        cl.read(self.tmp)
        self.assertGreater(_counts('continuity_ledger').get('current', 0),
                           before.get('current', 0))

    def test_legacy_ledger_reads_silently_and_counts(self):
        import infra.continuity_ledger as cl
        cl.publish_bundle(self.tmp, self._ledger())
        target = cl.ledger_path(self.tmp)
        data = json.loads(target.read_text(encoding='utf-8'))
        data.pop('schema_version')                        # 退回只有旧键 version 的老项目
        target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        before = dict(_counts('continuity_ledger'))
        ledger = cl.read(self.tmp)                        # 无提示、无写盘照常读
        self.assertEqual(ledger.get('version'), 1)
        self.assertNotIn('schema_version', ledger)
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')).get('schema_version'), None)
        self.assertGreater(_counts('continuity_ledger').get('legacy', 0),
                           before.get('legacy', 0))

    def test_missing_version_ledger_reads_and_counts(self):
        import infra.continuity_ledger as cl
        cl.publish_bundle(self.tmp, self._ledger())
        target = cl.ledger_path(self.tmp)
        data = json.loads(target.read_text(encoding='utf-8'))
        data.pop('schema_version')
        data.pop('version')
        target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        before = dict(_counts('continuity_ledger'))
        self.assertEqual(cl.read(self.tmp).get('stage'), 'continuity')
        self.assertGreater(_counts('continuity_ledger').get('missing', 0),
                           before.get('missing', 0))

    def test_future_ledger_reads_but_write_refused(self):
        import infra.continuity_ledger as cl
        cl.publish_bundle(self.tmp, self._ledger())
        target = cl.ledger_path(self.tmp)
        data = json.loads(target.read_text(encoding='utf-8'))
        data['schema_version'] = 2                        # 新版程序写的 future 产物
        raw = target.read_text(encoding='utf-8')
        target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        before = dict(_counts('continuity_ledger'))
        self.assertEqual(cl.read(self.tmp).get('stage'), 'continuity')   # 可读
        self.assertGreater(_counts('continuity_ledger').get('future', 0),
                           before.get('future', 0))
        with self.assertRaises(ValueError):
            cl.publish_bundle(self.tmp, self._ledger())   # 写入口拒绝
        self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['schema_version'], 2)

    def test_issues_sync_dual_writes_and_future_refused(self):
        import infra.continuity_ledger as cl
        path = cl.issues_path(self.tmp)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = cl.sync_issues(self.tmp, self._ledger(), publish=save, now='2026-01-01T00:00:00')
        self.assertIsInstance(rows, list)
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)
        self.assertEqual(data.get('version'), 1)
        # future 问题表：读取照常（登记为空表也返回 dict），写被拒且文件不动
        data['schema_version'] = 9
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.assertIsInstance(cl.read_issues(self.tmp), dict)
        with self.assertRaises(ValueError):
            cl.sync_issues(self.tmp, self._ledger(), publish=save, now='2026-01-01T00:00:01')
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['schema_version'], 9)


# ── desktop_queue（PersistentBackgroundTaskQueue）───────────────────────────
class DesktopQueueWiringTests(_Temp):
    def _queue(self):
        from orchestrator.desktop_automation_service import PersistentBackgroundTaskQueue
        return PersistentBackgroundTaskQueue(self.tmp / 'queue.json',
                                             handlers={'test': lambda payload: 'done'})

    def _write(self, payload):
        (self.tmp / 'queue.json').write_text(json.dumps(payload), encoding='utf-8')

    def _queued_row(self, label='x'):
        return {'id': 't1', 'kind': 'test', 'payload': {}, 'label': label,
                'priority': 0, 'created': 0, 'expires_at': None, 'state': 'queued'}

    def test_legacy_and_missing_queue_read_and_dual_write(self):
        self._write({'version': 1, 'tasks': []})
        queue = self._queue()
        self.assertEqual(queue.labels(), [])               # legacy 照常读
        queue.enqueue_descriptor('test', {}, label='a')    # 唯一落盘写入口
        data = json.loads((self.tmp / 'queue.json').read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)    # 双写新旧键
        self.assertEqual(data.get('version'), 1)
        # 缺版本字段的记录也照常读（G8 missing）
        self._write({'tasks': []})
        self.assertEqual(self._queue().labels(), [])

    def test_future_queue_reads_but_write_refused(self):
        self._write({'version': 2, 'tasks': [self._queued_row('x')]})
        queue = self._queue()
        self.assertEqual(queue.labels(), ['x'])            # future 允许读
        with self.assertRaises(ValueError):
            queue.enqueue_descriptor('test', {}, label='b')  # 写入口拒绝
        data = json.loads((self.tmp / 'queue.json').read_text(encoding='utf-8'))
        self.assertEqual(data['version'], 2)               # 原文件不被覆盖
        self.assertEqual(len(data['tasks']), 1)

    def test_invalid_queue_record_still_refused(self):
        self._write({'version': 'abc', 'tasks': []})
        with self.assertRaises(ValueError):
            self._queue().labels()
        self._write({'version': 1, 'tasks': 'oops'})
        with self.assertRaises(ValueError):
            self._queue().labels()


# ── edit_habits（edit_records／edit_habit_rules）────────────────────────────
class EditHabitsWiringTests(_Temp):
    def setUp(self):
        super().setUp()
        self.program = self.tmp / 'program'
        self.root = self.tmp / 'project'
        self.root.mkdir()

    def test_records_dual_write_and_future_refused(self):
        import orchestrator.edit_habits as habits
        record = habits.record_edit(self.root, 'script', '第一行\n第二行', '第一行\n改过的第二行',
                                    program=self.program)
        self.assertIsNotNone(record)
        path = habits.records_path(self.root, self.program)
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)
        self.assertTrue(habits.load_records(self.root, self.program))
        data['schema_version'] = 5
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.assertTrue(habits.load_records(self.root, self.program))   # future 可读
        with self.assertRaises(ValueError):
            habits.record_edit(self.root, 'script', 'a\nb', 'a\nc', program=self.program)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['schema_version'], 5)

    def test_rules_future_refused(self):
        import orchestrator.edit_habits as habits
        path = habits.rules_path(self.program)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'schema_version': 7, 'rules': []}), encoding='utf-8')
        self.assertEqual(habits.load_rules(self.program), [])            # future 可读
        with self.assertRaises(ValueError):
            habits.add_candidates('script', [{'rule': '新规则', 'evidence': 'e',
                                              'before': 'b', 'after': 'a'}],
                                  program=self.program)


# ── desktop_send_ledger ────────────────────────────────────────────────────
class DesktopSendLedgerWiringTests(_Temp):
    def setUp(self):
        super().setUp()
        self.program = self.tmp / 'program'
        self.root = self.tmp / 'project'
        self.root.mkdir()

    def _sent(self):
        return {'skill_hash': 'h', 'materials': [], 'mode': 'full', 'task_file': ''}

    def test_record_writes_schema_version_and_future_skips(self):
        import orchestrator.desktop_send_ledger as ledger
        ledger.record(self.root, 'script', {'engine': 'e', 'display_model': 'm'}, self._sent(),
                      program=self.program)
        path = ledger.ledger_path(self.root, self.program)
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)
        loaded = ledger.load(self.root, self.program)
        self.assertIsNotNone(loaded)
        self.assertIn('entries', loaded)
        # future 台账：读取按「没有记录」降级（安全方向＝整份重发），写入跳过不覆盖
        data['schema_version'] = 4
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.assertIsNone(ledger.load(self.root, self.program))
        ledger.record(self.root, 'script', {'engine': 'e', 'display_model': 'm'}, self._sent(),
                      program=self.program)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['schema_version'], 4)


# ── recon_service（recon_card）──────────────────────────────────────────────
class ReconCardWiringTests(_Temp):
    def test_card_dual_write_read_and_future_refused(self):
        import domain.recon_service as recon
        card = {'target': '竞品A', 'sources': [{'url': 'https://example.com', 'title': 't'}]}
        result = recon.save_card(self.tmp, card)
        self.assertTrue(result.ok)
        path = recon.card_path(self.tmp)
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)
        self.assertEqual(recon.load_card(self.tmp).get('target'), '竞品A')
        data['schema_version'] = 6
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(recon.load_card(self.tmp).get('target'), '竞品A')   # future 可读
        refused = recon.save_card(self.tmp, card)
        self.assertFalse(refused.ok)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['schema_version'], 6)


# ── artifact_lineage ────────────────────────────────────────────────────────
class ArtifactLineageWiringTests(_Temp):
    def test_record_dual_writes_and_future_skips(self):
        from contract import artifact_lineage as lineage
        artifact = self.tmp / 'out' / 'result.json'
        artifact.parent.mkdir(parents=True)
        artifact.write_text('{}', encoding='utf-8')
        source = self.tmp / 'src.txt'
        source.write_text('src', encoding='utf-8')
        lineage.record(self.tmp, artifact, source, 'test')
        book = artifact.parent / lineage.FILE_NAME
        data = json.loads(book.read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)
        self.assertEqual(data.get('version'), 1)
        self.assertEqual(lineage.check(self.tmp, artifact)['status'], lineage.CURRENT)
        # future 账本：读取照常，登记跳过且文件不被覆盖
        data['schema_version'] = 8
        book.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.assertIsNotNone(lineage._entry(self.tmp, artifact))
        lineage.record(self.tmp, artifact, source, 'test')
        after = json.loads(book.read_text(encoding='utf-8'))
        self.assertEqual(after['schema_version'], 8)
        self.assertEqual(len(after['entries']), 1)             # 没有追加新条目


# ── animatic_manifest ───────────────────────────────────────────────────────
class AnimaticWiringTests(_Temp):
    def _bundle(self, root):
        import domain.animatic_service as service
        from project_context_factory import project_context
        from orchestrator.stage_animatic_gateways import publish_animatic_bundle
        source = root / 'storyboard_draft.json'
        source.write_text(json.dumps({'shots': [{'id': 's1', 'prompt': '门边的人', 'duration': 2}]}),
                          encoding='utf-8')
        reference = root / 'reference.png'
        reference.write_bytes(b'reference')
        audio = root / 'temporary.wav'
        audio.write_bytes(b'audio')

        def render(workspace, *_args):
            target = workspace / 'image.png'
            target.write_bytes(b'image')
            return target

        def assemble(images, durations, sound, target, **_kwargs):
            target.write_bytes(b'video')
            return target

        def publish(artifacts):
            return publish_animatic_bundle(root, artifacts, validate=lambda _: True)

        return service.build_bundle(project_context(root), source, [reference], audio,
            {'ffmpeg': 'stub', 'ffprobe': 'stub'}, publish=publish,
            write_temporary=lambda path, raw: path.write_bytes(raw), render=render, assemble=assemble)

    def test_manifest_dual_writes_and_future_confirm_refused(self):
        import domain.animatic_service as service
        from contract.stage_path_service import write_dir
        result = self._bundle(self.tmp)
        self.assertTrue(result.ok)
        path = write_dir(self.tmp, 'animatic') / service.MANIFEST
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data.get('schema_version'), 1)
        self.assertEqual(data.get('version'), 1)
        self.assertTrue(service.evidence(self.tmp, require_confirmation=False)[0])
        # future 清单：evidence 照常核验（可读），confirm 写入口拒绝
        data['schema_version'] = 3
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.assertTrue(service.evidence(self.tmp, require_confirmation=False)[0])
        from orchestrator.stage_animatic_gateways import confirm_animatic
        with self.assertRaises(ValueError):
            confirm_animatic(self.tmp, rhythm=True, duration=True, dialogue_sync=True)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['schema_version'], 3)


if __name__ == '__main__':
    unittest.main()
