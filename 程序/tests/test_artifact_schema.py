"""artifact_schema：版本登记、只读校验与显式迁移。"""
from __future__ import annotations

import unittest

import artifact_schema as schema


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


if __name__ == '__main__':
    unittest.main()