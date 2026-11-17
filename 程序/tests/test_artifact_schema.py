"""artifact_schema：版本登记、五态分类、只读校验、STEPS 阶梯迁移与受护写盘。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contract import artifact_schema as schema


class RegistryTests(unittest.TestCase):
    def test_every_entry_declares_version_fields_owner(self):
        for kind, item in schema.REGISTRY.items():
            with self.subTest(kind=kind):
                self.assertIsInstance(item['version'], int)
                self.assertIsInstance(item['required'], tuple)
                self.assertTrue(item['owner'])
                self.assertIn('legacy', item)

    def test_spec_rejects_unknown_kind(self):
        with self.assertRaises(KeyError):
            schema.spec('no_such_artifact')


class StampTests(unittest.TestCase):
    def test_stamp_adds_version_and_keeps_original(self):
        payload = {'tasks': []}
        out = schema.stamp('desktop_queue', payload)
        self.assertEqual(out[schema.VERSION_KEY], 1)
        self.assertEqual(out['tasks'], [])
        self.assertNotIn(schema.VERSION_KEY, payload)

    def test_stamp_rejects_non_object(self):
        with self.assertRaises(TypeError):
            schema.stamp('desktop_queue', [])


class ValidateTests(unittest.TestCase):
    def test_current_payload_passes(self):
        self.assertEqual(schema.validate('desktop_queue', {'schema_version': 1, 'tasks': []}), [])

    def test_missing_version_reported(self):
        problems = schema.validate('desktop_queue', {'tasks': []})
        self.assertTrue(any('缺少版本字段' in p for p in problems))

    def test_version_mismatch_reported(self):
        problems = schema.validate('desktop_queue', {'schema_version': 2, 'tasks': []})
        self.assertTrue(any('需迁移' in p for p in problems))

    def test_missing_required_field_reported(self):
        problems = schema.validate('animatic_manifest', {'schema_version': 1, 'kind': 'animatic'})
        self.assertTrue(any('缺少必备字段' in p and 'source' in p for p in problems))

    def test_unknown_kind_reported_not_raised(self):
        self.assertTrue(schema.validate('no_such_artifact', {}))

    def test_non_object_reported(self):
        self.assertEqual(schema.validate('desktop_queue', []), ['desktop_queue 必须是对象'])


class MigrateTests(unittest.TestCase):
    def test_legacy_key_is_lifted_and_source_untouched(self):
        legacy = {'version': 1, 'tasks': []}
        out, actions = schema.migrate('desktop_queue', legacy)
        self.assertEqual(out['schema_version'], 1)
        self.assertEqual(out['tasks'], [])
        self.assertTrue(actions)
        self.assertNotIn('schema_version', legacy)

    def test_missing_version_is_backfilled(self):
        out, actions = schema.migrate('desktop_queue', {'tasks': []})
        self.assertEqual(out['schema_version'], 1)
        self.assertTrue(any('补写' in a for a in actions))

    def test_current_payload_is_stable(self):
        payload = schema.stamp('animatic_manifest', {'kind': 'animatic', 'source': 'x'})
        out, actions = schema.migrate('animatic_manifest', payload)
        self.assertEqual(out, payload)
        self.assertEqual(actions, [])


class ClassifyTests(unittest.TestCase):
    """D4-a：classify 五态分类，只读不抛异常。"""

    def test_current_when_schema_version_matches(self):
        payload = {'schema_version': 1, 'tasks': []}
        self.assertEqual(schema.classify('desktop_queue', payload), 'current')

    def test_legacy_when_only_legacy_key_present(self):
        # 旧键即便版本号相同也算 legacy：缺 schema_version，下次写入顺带补上（G8）。
        self.assertEqual(schema.classify('desktop_queue', {'version': 1, 'tasks': []}), 'legacy')

    def test_missing_when_no_version_at_all(self):
        self.assertEqual(schema.classify('desktop_queue', {'tasks': []}), 'missing')

    def test_future_when_above_registered(self):
        self.assertEqual(schema.classify('desktop_queue', {'schema_version': 2, 'tasks': []}), 'future')
        self.assertEqual(schema.classify('desktop_queue', {'version': 9, 'tasks': []}), 'future')

    def test_invalid_for_non_object_unknown_kind_and_bad_version(self):
        self.assertEqual(schema.classify('desktop_queue', []), 'invalid')
        self.assertEqual(schema.classify('desktop_queue', 'x'), 'invalid')
        self.assertEqual(schema.classify('no_such_kind', {}), 'invalid')
        self.assertEqual(schema.classify('desktop_queue', {'schema_version': 'abc'}), 'invalid')
        self.assertEqual(schema.classify('desktop_queue', {'schema_version': True}), 'invalid')

    def test_null_version_key_reads_as_missing(self):
        # 与 _read_version／validate 同口径：VERSION_KEY 在场即权威，None 视为缺版本。
        self.assertEqual(schema.classify('desktop_queue', {'schema_version': None, 'tasks': []}), 'missing')

    def test_classify_never_raises_and_never_mutates(self):
        payload = {'version': 1, 'tasks': []}
        before = dict(payload)
        for value in ({}, [], 'x', None, 3):
            schema.classify('desktop_queue', value)
        self.assertEqual(payload, before)


class _LadderKind:
    """临时登记一个三版产物类型，供 STEPS 阶梯用例使用；用例结束自动摘除。"""

    KIND = 'test_ladder_artifact'

    @classmethod
    def install(cls, steps):
        schema.REGISTRY[cls.KIND] = {'version': 3, 'required': ('x',),
                                     'owner': 'test', 'legacy': 'version'}
        schema.STEPS[cls.KIND] = dict(steps)
        return cls.KIND

    @classmethod
    def remove(cls):
        schema.REGISTRY.pop(cls.KIND, None)
        schema.STEPS.pop(cls.KIND, None)


def _lift_1_to_2(payload):
    return {**payload, 'v2': True}


def _lift_2_to_3(payload):
    return {**payload, 'v3': True}


class StepsLadderTests(unittest.TestCase):
    """D4-b：migrate 按 STEPS 阶梯逐级抬升；缺步返回问题清单不抛异常。"""

    def setUp(self):
        self.kind = _LadderKind.install({2: _lift_1_to_2, 3: _lift_2_to_3})
        self.addCleanup(_LadderKind.remove)

    def test_ladder_lifts_version_one_to_three(self):
        out, actions = schema.migrate(self.kind, {'schema_version': 1, 'x': 0})
        self.assertEqual(out['schema_version'], 3)
        self.assertTrue(out['v2'])
        self.assertTrue(out['v3'])
        self.assertTrue(any('1→2' in a for a in actions), actions)
        self.assertTrue(any('2→3' in a for a in actions), actions)

    def test_ladder_from_middle_version_only_runs_remaining_steps(self):
        out, actions = schema.migrate(self.kind, {'schema_version': 2, 'x': 0})
        self.assertEqual(out['schema_version'], 3)
        self.assertNotIn('v2', out)
        self.assertTrue(out['v3'])

    def test_missing_step_returns_problems_and_keeps_version(self):
        _LadderKind.remove()
        self.kind = _LadderKind.install({3: _lift_2_to_3})      # 缺 1→2 这一级
        self.addCleanup(_LadderKind.remove)
        out, actions = schema.migrate(self.kind, {'schema_version': 1, 'x': 0})
        self.assertTrue(any('缺少' in a and '迁移步骤' in a for a in actions), actions)
        # 版本号不前进：返回的副本仍是旧版本，不能假装已到 v3。
        self.assertEqual(out['schema_version'], 1)
        self.assertNotIn('v3', out)

    def test_step_exception_becomes_problem_not_crash(self):
        def boom(payload):
            raise RuntimeError('抬升炸了')
        _LadderKind.remove()
        self.kind = _LadderKind.install({2: boom, 3: _lift_2_to_3})
        self.addCleanup(_LadderKind.remove)
        out, actions = schema.migrate(self.kind, {'schema_version': 1, 'x': 0})
        self.assertTrue(any('失败' in a for a in actions), actions)
        self.assertEqual(out['schema_version'], 1)

    def test_future_payload_is_not_lifted(self):
        out, actions = schema.migrate(self.kind, {'schema_version': 9, 'x': 0})
        self.assertEqual(out['schema_version'], 9)
        self.assertNotIn('v3', out)
        self.assertTrue(actions)

    def test_unversioned_payload_runs_full_ladder_from_first_version(self):
        out, actions = schema.migrate(self.kind, {'x': 0})
        self.assertEqual(out['schema_version'], 3)
        self.assertTrue(out['v2'] and out['v3'])

    def test_classify_tracks_ladder_states(self):
        self.assertEqual(schema.classify(self.kind, {'schema_version': 1, 'x': 0}), 'legacy')
        self.assertEqual(schema.classify(self.kind, {'schema_version': 2, 'x': 0}), 'legacy')
        self.assertEqual(schema.classify(self.kind, {'schema_version': 3, 'x': 0}), 'current')
        self.assertEqual(schema.classify(self.kind, {'schema_version': 4, 'x': 0}), 'future')
        self.assertEqual(schema.classify(self.kind, {'version': 2, 'x': 0}), 'legacy')
        self.assertEqual(schema.classify(self.kind, {'x': 0}), 'missing')


class StampBoundaryTests(unittest.TestCase):
    """D4-b：stamp 拒绝高于登记版本的 version；不高于登记版本照常写。"""

    def setUp(self):
        self.kind = _LadderKind.install({2: _lift_1_to_2, 3: _lift_2_to_3})
        self.addCleanup(_LadderKind.remove)

    def test_stamp_rejects_version_above_registered(self):
        with self.assertRaises(ValueError):
            schema.stamp(self.kind, {'x': 0}, version=4)
        with self.assertRaises(ValueError):
            schema.stamp('desktop_queue', {'tasks': []}, version=2)

    def test_stamp_accepts_registered_or_lower_version(self):
        out = schema.stamp(self.kind, {'x': 0}, version=3)
        self.assertEqual(out['schema_version'], 3)
        out = schema.stamp(self.kind, {'x': 0}, version=2)
        self.assertEqual(out['schema_version'], 2)
        out = schema.stamp(self.kind, {'x': 0})
        self.assertEqual(out['schema_version'], 3)


def _json_publish(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def _json_read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


class MigrateFileTests(unittest.TestCase):
    """D4-b/§3c-2：迁移写盘＝.bak 备份→原子发布→读回断言→失败回滚。"""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = Path(self.td.name)
        self.kind = _LadderKind.install({2: _lift_1_to_2, 3: _lift_2_to_3})
        self.addCleanup(_LadderKind.remove)

    def _artifact(self, payload, name='产物.json'):
        path = self.root / name
        _json_publish(path, payload)
        return path

    def test_legacy_artifact_is_migrated_written_and_backed_up(self):
        path = self._artifact({'schema_version': 1, 'x': 0})
        status, payload, actions = schema.migrate_file(
            self.kind, path, publish=_json_publish, read=_json_read)
        self.assertEqual(status, 'written')
        self.assertEqual(payload['schema_version'], 3)
        written = _json_read(path)
        self.assertEqual(written['schema_version'], 3)
        self.assertTrue(written['v2'] and written['v3'])
        backup = Path(str(path) + '.bak')
        self.assertTrue(backup.is_file())
        self.assertEqual(_json_read(backup)['schema_version'], 1)   # .bak 留旧版

    def test_current_artifact_is_skipped_without_write_or_backup(self):
        path = self._artifact({'schema_version': 3, 'x': 0, 'v2': True, 'v3': True})
        before = path.read_bytes()
        status, payload, actions = schema.migrate_file(
            self.kind, path, publish=_json_publish, read=_json_read)
        self.assertEqual(status, 'skipped')
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(Path(str(path) + '.bak').exists())

    def test_future_artifact_is_skipped_and_untouched(self):
        path = self._artifact({'schema_version': 9, 'x': 0})
        status, payload, actions = schema.migrate_file(
            self.kind, path, publish=_json_publish, read=_json_read)
        self.assertEqual(status, 'skipped')
        self.assertEqual(_json_read(path)['schema_version'], 9)

    def test_missing_step_skips_write(self):
        _LadderKind.remove()
        self.kind = _LadderKind.install({3: _lift_2_to_3})
        self.addCleanup(_LadderKind.remove)
        path = self._artifact({'schema_version': 1, 'x': 0})
        before = path.read_bytes()
        status, payload, actions = schema.migrate_file(
            self.kind, path, publish=_json_publish, read=_json_read)
        self.assertEqual(status, 'skipped')
        self.assertTrue(any('缺少' in a for a in actions), actions)
        self.assertEqual(path.read_bytes(), before)

    def test_publish_failure_rolls_back_from_backup(self):
        path = self._artifact({'schema_version': 1, 'x': 0})
        original = _json_read(path)

        def bad_publish(target, payload):
            raise OSError('磁盘被占')

        status, payload, actions = schema.migrate_file(
            self.kind, path, publish=bad_publish, read=_json_read)
        self.assertEqual(status, 'failed')
        self.assertEqual(_json_read(path), original)      # 回滚后与原文件一致
        self.assertTrue(Path(str(path) + '.bak').is_file())

    def test_post_write_assert_failure_rolls_back(self):
        path = self._artifact({'schema_version': 1, 'x': 0})
        original = _json_read(path)

        def lying_publish(target, payload):
            # 发布一个丢了 schema_version 的坏副本：读回断言必须接住并回滚。
            _json_publish(target, {k: v for k, v in payload.items() if k != 'schema_version'})

        status, payload, actions = schema.migrate_file(
            self.kind, path, publish=lying_publish, read=_json_read)
        self.assertEqual(status, 'failed')
        self.assertEqual(_json_read(path), original)

    def test_unreadable_or_non_object_is_skipped(self):
        path = self.root / '空.json'
        path.write_text('not json', encoding='utf-8')
        status, payload, actions = schema.migrate_file(
            self.kind, path, publish=_json_publish, read=_json_read)
        self.assertEqual(status, 'skipped')
        self.assertEqual(path.read_text(encoding='utf-8'), 'not json')


if __name__ == '__main__':
    unittest.main()