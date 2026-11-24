# -*- coding: utf-8 -*-
"""AST-VERSION-1：资产文字与图片版本记录数据层（09 册 §6 / DOC-D9-4）。

先红后绿依据：改前 ``domain.asset_versions`` 不存在、各写入口不产生版本记录、
``register_image`` 对已有图片直接跳过登记。断言一律落在临时目录，不读写用户项目库。
"""
import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agent.core import save, save_text
from image_fixtures import png
import asset_plan
import asset_batch_service
from asset_reference_images import attach, set_roles, unbind

AID = 'CHAR_001'


def plan_gateway():
    from agent.core import save_bytes, save_text
    from infra.file_cache import remove_temporary_file
    return {'publish_json': save, 'publish_bytes': save_bytes,
            'publish_text': save_text, 'remove_file': remove_temporary_file}


def batch_gateway():
    from stage_execution_service import asset_batch_gateway
    return asset_batch_gateway()


def asset_fields(**overrides):
    asset = {'name': '角色', 'description': '旧描述', 'image_prompt': '正向',
             'negative_prompt': '', 'positive_prompt': '正向', 'prompt': '正向',
             'reference_images': [], 'reference_roles': {}}
    asset.update(overrides)
    return asset


def make_library(tmp, aid=AID, asset=None):
    """最小资产库：<tmp>/assetlib/assets/资产清单/assets.json。"""
    base = Path(tmp) / 'assetlib'
    plan_file = base / 'assets/资产清单/assets.json'
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    save(plan_file, {aid: asset if asset is not None else asset_fields()})
    return base


def make_project(tmp):
    """带 ``asset_library_dir`` 配置的最小项目，供 ``list_versions(project, aid)`` 解析。"""
    project = Path(tmp) / 'proj'
    base = project / 'assetlib'
    base.mkdir(parents=True, exist_ok=True)
    (project / 'config.json').write_text(
        json.dumps({'asset_library_dir': 'assetlib'}, ensure_ascii=False), encoding='utf-8')
    return project, base


def version_file(base, aid=AID):
    return Path(base) / 'assets' / '资产版本' / (aid + '.jsonl')


def read_records(path):
    return [json.loads(line) for line in
            Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


class AppendVersionTests(unittest.TestCase):
    """``domain.asset_versions`` 数据层本体：追加、编号、读取、失败降级。"""

    def test_append_creates_jsonl_with_schema_version(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            record = asset_versions.append_version(
                Path(td), AID,
                {'field': 'fields', 'kind': 'text',
                 'before': {'description': '旧'}, 'after': {'description': '新'}},
                source='manual', publish=save_text, now='2026-11-24T10:00:00')
            self.assertIsNotNone(record)
            self.assertEqual(record['version'], 1)
            self.assertEqual(record['schema_version'], 1)
            self.assertEqual(record['aid'], AID)
            self.assertEqual(record['at'], '2026-11-24T10:00:00')
            self.assertEqual(record['source'], 'manual')
            rows = read_records(version_file(Path(td)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], record)

    def test_versions_increment_per_asset(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for index in range(2):
                asset_versions.append_version(
                    base, AID,
                    {'field': 'fields', 'kind': 'text',
                     'before': {'n': index}, 'after': {'n': index + 1}},
                    source='manual', publish=save_text)
            asset_versions.append_version(
                base, 'LOC_001',
                {'field': 'name', 'kind': 'text',
                 'before': {'name': '旧'}, 'after': {'name': '新'}},
                source='manual', publish=save_text)
            self.assertEqual([r['version'] for r in read_records(version_file(base))], [1, 2])
            self.assertEqual([r['version'] for r in read_records(version_file(base, 'LOC_001'))], [1])

    def test_corrupt_line_is_preserved_and_counted(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            path = version_file(base)
            path.parent.mkdir(parents=True)
            path.write_text('not-json\n{"aid":"CHAR_001","version":1}\n', encoding='utf-8')
            record = asset_versions.append_version(
                base, AID, {'field': 'fields', 'kind': 'text',
                            'before': None, 'after': None},
                source='manual', publish=save_text)
            self.assertEqual(record['version'], 3)
            rows = path.read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0], 'not-json')

    def test_publish_failure_returns_none_and_writes_nothing(self):
        from domain import asset_versions

        def broken(path, text):
            raise OSError('disk full')

        with tempfile.TemporaryDirectory() as td:
            record = asset_versions.append_version(
                Path(td), AID, {'field': 'fields', 'kind': 'text',
                                'before': None, 'after': None},
                source='manual', publish=broken)
            self.assertIsNone(record)
            self.assertFalse(version_file(Path(td)).exists())

    def test_invalid_source_and_aid_rejected(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self.assertIsNone(asset_versions.append_version(
                base, AID, {'field': 'f', 'kind': 'text'},
                source='bogus', publish=save_text))
            self.assertIsNone(asset_versions.append_version(
                base, '../escape', {'field': 'f', 'kind': 'text'},
                source='manual', publish=save_text))
            self.assertFalse((base / 'assets').exists())

    def test_concurrent_appends_keep_unique_sequential_versions(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)

            def work(index):
                result = asset_versions.append_version(
                    base, AID,
                    {'field': 'fields', 'kind': 'text', 'before': None,
                     'after': {'i': index}},
                    source='manual', publish=save_text)
                if result is None:
                    raise AssertionError('append_version 返回 None')
                return result['version']

            with ThreadPoolExecutor(max_workers=8) as pool:
                versions = sorted(pool.map(work, range(8)))
            self.assertEqual(versions, list(range(1, 9)))
            self.assertEqual(len(read_records(version_file(base))), 8)

    def test_image_summary_has_path_and_sha256(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            image = base / 'assets' / 'characters' / 'CHAR_001_x.png'
            image.parent.mkdir(parents=True)
            raw = png(size=(16, 9))
            image.write_bytes(raw)
            summary = asset_versions.image_summary(image, base)
            self.assertEqual(summary['path'], 'assets/characters/CHAR_001_x.png')
            self.assertEqual(summary['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertIsNone(asset_versions.image_summary(base / 'none.png', base))
            self.assertIsNone(asset_versions.image_summary(image, Path(td) / 'other'))


class ReadApiTests(unittest.TestCase):
    """只读 API：``list_versions(project, aid)`` / ``get_version(project, aid, n)``。"""

    def test_list_and_get_versions_resolve_project_library(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            project, base = make_project(td)
            asset_versions.append_version(
                base, AID,
                {'field': 'fields', 'kind': 'text',
                 'before': {'description': 'v1'}, 'after': {'description': 'v2'}},
                source='manual', publish=save_text, now='2026-11-24T10:00:00')
            asset_versions.append_version(
                base, AID,
                {'field': 'name', 'kind': 'text',
                 'before': {'name': '旧'}, 'after': {'name': '新'}},
                source='manual', publish=save_text, now='2026-11-24T11:00:00')
            records = asset_versions.list_versions(str(project), AID)
            self.assertEqual([r['version'] for r in records], [1, 2])
            self.assertEqual(asset_versions.get_version(str(project), AID, 2)['field'], 'name')
            self.assertIsNone(asset_versions.get_version(str(project), AID, 9))
            self.assertEqual(asset_versions.list_versions(str(project), 'CHAR_999'), [])

    def test_record_without_schema_version_still_reads(self):
        from domain import asset_versions
        with tempfile.TemporaryDirectory() as td:
            project, base = make_project(td)
            path = version_file(base)
            path.parent.mkdir(parents=True)
            legacy = {'aid': AID, 'version': 1, 'at': '2026-01-01T00:00:00',
                      'field': 'fields', 'kind': 'text',
                      'before': {'description': '旧'}, 'after': {'description': '新'},
                      'source': 'manual'}
            path.write_text(json.dumps(legacy, ensure_ascii=False) + '\n', encoding='utf-8')
            records = asset_versions.list_versions(str(project), AID)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['version'], 1)
            self.assertNotIn('schema_version', records[0])
            self.assertEqual(asset_versions.get_version(str(project), AID, 1)['source'], 'manual')


class PlanWriteEntryTests(unittest.TestCase):
    """``asset_plan`` 写入口：update_fields／update_planned 成功写入后追加一条。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'proj'
        self.project.mkdir()
        self.base = self.project / 'assetlib'
        plan_file = self.base / 'assets/资产清单/assets.json'
        plan_file.parent.mkdir(parents=True)
        save(plan_file, {AID: asset_fields()})

    def test_update_fields_appends_one_manual_record(self):
        result = asset_plan.update_fields(
            str(self.project), str(self.base), AID,
            {'description': '新描述全量文本'}, gateway=plan_gateway())
        self.assertTrue(result.ok)
        records = read_records(version_file(self.base))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['aid'], AID)
        self.assertEqual(record['version'], 1)
        self.assertEqual(record['schema_version'], 1)
        self.assertEqual(record['source'], 'manual')
        self.assertEqual(record['field'], 'fields')
        self.assertEqual(record['kind'], 'text')
        self.assertEqual(record['before'], {'description': '旧描述'})
        self.assertEqual(record['after'], {'description': '新描述全量文本'})
        self.assertTrue(record['at'])

    def test_update_fields_versions_increment(self):
        gateway = plan_gateway()
        asset_plan.update_fields(str(self.project), str(self.base), AID,
                                 {'description': '第二版'}, gateway=gateway)
        asset_plan.update_fields(str(self.project), str(self.base), AID,
                                 {'description': '第三版'}, gateway=gateway)
        records = read_records(version_file(self.base))
        self.assertEqual([r['version'] for r in records], [1, 2])
        self.assertEqual(records[1]['before'], {'description': '第二版'})
        self.assertEqual(records[1]['after'], {'description': '第三版'})

    def test_update_planned_direct_base_appends_record(self):
        result = asset_plan.update_planned(self.base, AID, {'description': '直写'},
                                           gateway=plan_gateway())
        self.assertTrue(result.ok)
        records = read_records(version_file(self.base))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['source'], 'manual')
        self.assertEqual(records[0]['after'], {'description': '直写'})

    def test_record_failure_does_not_block_plan_write(self):
        real = plan_gateway()

        def flaky_text(path, text):
            raise OSError('disk full')

        gateway = dict(real, publish_text=flaky_text)
        result = asset_plan.update_fields(
            str(self.project), str(self.base), AID,
            {'description': '仍要写入'}, gateway=gateway)
        self.assertTrue(result.ok)
        plan = json.loads((self.base / 'assets/资产清单/assets.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(plan[AID]['description'], '仍要写入')
        self.assertFalse(version_file(self.base).exists())


class BatchWriteEntryTests(unittest.TestCase):
    """``asset_batch_service`` 写入口：register_image／import_asset_image／rename_asset。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = make_library(self.tmp.name)

    def _source(self, name, raw):
        path = Path(self.tmp.name) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def test_register_image_replace_keeps_history_and_versions(self):
        gateway = batch_gateway()
        first_png = png(size=(16, 9))
        second_png = png(size=(8, 8), color='blue')
        src1 = self._source('s1/gen.png', first_png)
        src2 = self._source('s2/gen.png', second_png)
        asset = asset_fields()
        self.assertEqual(asset_batch_service.register_image(
            self.base, AID, asset, src1, gateway=gateway), '已生成并导入')
        registry = json.loads((self.base / 'assets.json').read_text(encoding='utf-8'))
        image1 = registry[AID]['image']
        self.assertTrue((self.base / image1).is_file())
        # 契约变更：生成路不再「已有图片跳过」，而是替换并把旧图留进历史版本。
        self.assertEqual(asset_batch_service.register_image(
            self.base, AID, asset, src2, gateway=gateway), '已生成并导入')
        registry = json.loads((self.base / 'assets.json').read_text(encoding='utf-8'))
        image2 = registry[AID]['image']
        self.assertNotEqual(image2, image1)
        self.assertTrue((self.base / image2).is_file())
        self.assertFalse((self.base / image1).exists())
        history = list((self.base / 'assets/characters/历史版本').glob('*.png'))
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0].name.startswith(Path(image1).stem))
        records = read_records(version_file(self.base))
        self.assertEqual([r['version'] for r in records], [1, 2])
        self.assertTrue(all(r['source'] == 'generated' for r in records))
        self.assertEqual(records[0]['field'], 'image')
        self.assertEqual(records[0]['kind'], 'image')
        self.assertIsNone(records[0]['before'])
        self.assertEqual(records[0]['after']['path'], image1)
        self.assertEqual(records[0]['after']['sha256'], hashlib.sha256(first_png).hexdigest())
        self.assertIn('历史版本', records[1]['before']['path'])
        self.assertEqual(records[1]['before']['sha256'], hashlib.sha256(first_png).hexdigest())
        self.assertEqual(records[1]['after']['path'], image2)
        self.assertEqual(records[1]['after']['sha256'], hashlib.sha256(second_png).hexdigest())

    def test_register_image_record_failure_still_registers(self):
        gateway = batch_gateway()
        real_bytes = gateway['publish_bytes']

        def flaky(path, data):
            if str(path).endswith('.jsonl'):
                raise OSError('disk full')
            return real_bytes(path, data)

        gateway['publish_bytes'] = flaky
        src = self._source('gen.png', png())
        result = asset_batch_service.register_image(
            self.base, AID, asset_fields(), src, gateway=gateway)
        self.assertEqual(result, '已生成并导入')
        registry = json.loads((self.base / 'assets.json').read_text(encoding='utf-8'))
        self.assertTrue(registry[AID]['image'].endswith('.png'))
        self.assertFalse(version_file(self.base).exists())

    def test_import_asset_image_records_versions(self):
        gateway = batch_gateway()
        save(self.base / 'assets.json', {AID: {'name': '角色'}})
        first_png = png(size=(16, 9))
        second_png = png(size=(8, 8), color='blue')
        src1 = self._source('s1/in.png', first_png)
        src2 = self._source('s2/in.png', second_png)
        requirements = {AID: {'name': '角色', 'description': '主角'}}
        kind, _message = asset_batch_service.import_asset_image(
            self.base, Path(self.tmp.name), AID, src1, requirements, gateway=gateway)
        self.assertEqual(kind, 'characters')
        kind, _message = asset_batch_service.import_asset_image(
            self.base, Path(self.tmp.name), AID, src2, requirements, gateway=gateway)
        self.assertEqual(kind, 'characters')
        records = read_records(version_file(self.base))
        self.assertEqual([r['version'] for r in records], [1, 2])
        self.assertTrue(all(r['source'] == 'imported' for r in records))
        self.assertEqual(records[0]['field'], 'image')
        self.assertIsNone(records[0]['before'])
        self.assertEqual(records[0]['after']['path'], 'assets/characters/CHAR_001.png')
        self.assertIn('历史版本', records[1]['before']['path'])
        self.assertEqual(records[1]['before']['sha256'], hashlib.sha256(first_png).hexdigest())
        self.assertEqual(records[1]['after']['sha256'], hashlib.sha256(second_png).hexdigest())

    def test_rename_asset_records_name_change(self):
        gateway = batch_gateway()
        save(self.base / 'assets.json', {AID: {'name': '角色', 'aliases': []}})
        asset_batch_service.rename_asset(self.base, AID, '角色', '新角色名', gateway=gateway)
        records = read_records(version_file(self.base))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['field'], 'name')
        self.assertEqual(record['kind'], 'text')
        self.assertEqual(record['source'], 'manual')
        self.assertEqual(record['before'], {'name': '角色'})
        self.assertEqual(record['after'], {'name': '新角色名'})


class ReferenceWriteEntryTests(unittest.TestCase):
    """``asset_reference_images`` 写入口：attach／set_roles／unbind。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = make_library(self.tmp.name, asset=asset_fields())

    def _plan(self):
        return json.loads((self.base / 'assets/资产清单/assets.json')
                          .read_text(encoding='utf-8'))

    def test_attach_set_roles_unbind_append_records(self):
        src = Path(self.tmp.name) / 'ref1.png'
        src.write_bytes(png(size=(8, 8)))
        self.assertEqual(attach(self.base, AID, [src], role=None), 1)
        first = self._plan()[AID]['reference_images'][0]
        records = read_records(version_file(self.base))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record['version'], 1)
        self.assertEqual(record['source'], 'imported')
        self.assertEqual(record['field'], 'reference_images')
        self.assertEqual(record['kind'], 'text')
        self.assertEqual(record['before']['reference_images'], [])
        self.assertEqual(record['after']['reference_images'], [first])

        set_roles(self.base, AID, [first], '长相')
        second = self._plan()[AID]['reference_images'][0]
        self.assertNotEqual(second, first)
        unbind(self.base, AID, [second])
        records = read_records(version_file(self.base))
        self.assertEqual([r['version'] for r in records], [1, 2, 3])
        self.assertEqual(records[1]['source'], 'manual')
        self.assertEqual(records[1]['field'], 'reference_images')
        self.assertEqual(records[1]['after']['reference_roles'], {second: '长相'})
        self.assertEqual(records[2]['source'], 'manual')
        self.assertEqual(records[2]['after']['reference_images'], [])

    def test_attach_record_failure_still_attaches(self):
        from unittest.mock import patch
        src = Path(self.tmp.name) / 'ref2.png'
        src.write_bytes(png(size=(8, 8)))
        with patch('asset_reference_images.save_text', side_effect=OSError('disk full')):
            self.assertEqual(attach(self.base, AID, [src], role=None), 1)
        self.assertEqual(len(self._plan()[AID]['reference_images']), 1)
        self.assertFalse(version_file(self.base).exists())


class RestoreVersionTests(unittest.TestCase):
    """AST-VERSION-2：``domain.asset_versions`` 的退回写入口与快照重建。

    ``restore_version`` 把记录过的文字字段与图片退到第 n 版之后的状态，并追加一条
    ``source='manual'``、``field='restore'`` 的新记录——历史一条不删；锁定、缺版、
    旧图找不回都拒绝且不改动当前内容。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = make_library(self.tmp.name)
        self.gateway = batch_gateway()

    def _plan(self):
        return json.loads((self.base / 'assets/资产清单/assets.json')
                          .read_text(encoding='utf-8'))

    def _source(self, name, raw):
        path = Path(self.tmp.name) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def test_snapshot_rebuilds_fields_and_image(self):
        from domain import asset_versions
        records = [
            {'version': 1, 'kind': 'text', 'field': 'fields',
             'before': {'description': '旧描述', 'name': '角色'},
             'after': {'description': '第二版', 'name': '角色'}},
            {'version': 2, 'kind': 'image', 'field': 'image', 'before': None,
             'after': {'path': 'assets/characters/a.png', 'sha256': 's2'}},
            {'version': 3, 'kind': 'text', 'field': 'name',
             'before': {'name': '角色'}, 'after': {'name': '改名后'}},
        ]
        snap = asset_versions.snapshot_at(records, 2)
        self.assertEqual(snap['fields']['description'], '第二版')
        self.assertEqual(snap['fields']['name'], '角色')
        self.assertEqual(snap['image']['sha256'], 's2')
        snap0 = asset_versions.snapshot_at(records, 0)
        self.assertIsNone(snap0['image'])
        self.assertEqual(snap0['fields']['description'], '旧描述')
        snap3 = asset_versions.snapshot_at(records, 3)
        self.assertEqual(snap3['fields']['name'], '改名后')

    def test_describe_one_line_summary(self):
        from domain import asset_versions
        self.assertEqual(asset_versions.describe(
            {'kind': 'image', 'field': 'image'}), '换图片')
        self.assertEqual(asset_versions.describe(
            {'kind': 'text', 'field': 'name',
             'before': {'name': '旧名'}, 'after': {'name': '新名'}}), '改名：旧名 → 新名')
        self.assertEqual(asset_versions.describe(
            {'kind': 'text', 'field': 'fields', 'before': {},
             'after': {'description': 'x', 'locked': True}}), '改了 description、locked')
        self.assertEqual(asset_versions.describe(
            {'field': 'restore', 'kind': 'restore', 'restore_of': 2}), '退回第 2 版')

    def test_restore_reverts_text_and_appends_manual_record(self):
        from domain import asset_versions
        gateway = plan_gateway()
        asset_plan.update_planned(str(self.base), AID, {'description': '第二版'}, gateway=gateway)
        asset_plan.update_planned(str(self.base), AID,
                                  {'description': '第三版', 'name': '改名后'}, gateway=gateway)
        record = asset_versions.restore_version(self.base, AID, 1, gateway=self.gateway)
        row = self._plan()[AID]
        self.assertEqual(row['description'], '第二版')
        self.assertEqual(row['name'], '角色')
        self.assertEqual(record['version'], 3)
        self.assertEqual(record['source'], 'manual')
        self.assertEqual(record['field'], 'restore')
        self.assertEqual(record['restore_of'], 1)
        self.assertEqual(len(read_records(version_file(self.base))), 3)

    def test_restore_locked_refused_without_writes(self):
        from domain import asset_versions
        asset_plan.update_planned(str(self.base), AID, {'description': '第二版'},
                                  gateway=plan_gateway())
        plan_file = self.base / 'assets/资产清单/assets.json'
        plan = self._plan()
        plan[AID]['locked'] = True
        save(plan_file, plan)
        before = plan_file.read_text(encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '锁定'):
            asset_versions.restore_version(self.base, AID, 1, gateway=self.gateway)
        self.assertEqual(plan_file.read_text(encoding='utf-8'), before)
        self.assertEqual(len(read_records(version_file(self.base))), 1)

    def test_restore_missing_or_invalid_version_refused(self):
        from domain import asset_versions
        with self.assertRaisesRegex(ValueError, '没有第 9 版'):
            asset_versions.restore_version(self.base, AID, 9, gateway=self.gateway)
        with self.assertRaisesRegex(ValueError, '版本号'):
            asset_versions.restore_version(self.base, AID, 'x', gateway=self.gateway)
        with self.assertRaises((ValueError, TypeError)):
            asset_versions.restore_version(self.base, AID, 1, gateway={})

    def test_restore_image_swaps_current_into_history(self):
        from domain import asset_versions
        first_png = png(size=(16, 9))
        second_png = png(size=(8, 8), color='blue')
        src1 = self._source('s1/gen.png', first_png)
        src2 = self._source('s2/gen.png', second_png)
        asset = asset_fields()
        asset_batch_service.register_image(self.base, AID, asset, src1, gateway=self.gateway)
        asset_batch_service.register_image(self.base, AID, asset, src2, gateway=self.gateway)
        asset_versions.restore_version(self.base, AID, 1, gateway=self.gateway)
        registry = json.loads((self.base / 'assets.json').read_text(encoding='utf-8'))
        current = self.base / registry[AID]['image']
        self.assertEqual(hashlib.sha256(current.read_bytes()).hexdigest(),
                         hashlib.sha256(first_png).hexdigest())
        history = list((self.base / 'assets/characters/历史版本').glob('*.png'))
        self.assertEqual(len(history), 2)
        records = read_records(version_file(self.base))
        self.assertEqual(len(records), 3)
        self.assertEqual(records[2]['restore_of'], 1)
        self.assertEqual(records[2]['source'], 'manual')
        self.assertEqual(records[2]['field'], 'restore')

    def test_restore_image_missing_source_fails_closed(self):
        from domain import asset_versions
        current = self.base / 'assets/characters/cur.png'
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_bytes(png(size=(8, 8)))
        save(self.base / 'assets.json',
             {AID: {'name': '角色', 'image': 'assets/characters/cur.png'}})
        path = version_file(self.base)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {'aid': AID, 'version': 1, 'at': '2026-11-24T10:00:00',
             'field': 'image', 'kind': 'image', 'before': None,
             'after': {'path': 'assets/characters/gone.png', 'sha256': 'f' * 64},
             'source': 'generated'}, ensure_ascii=False) + '\n', encoding='utf-8')
        before = (self.base / 'assets.json').read_text(encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '无法退回'):
            asset_versions.restore_version(self.base, AID, 1, gateway=self.gateway)
        self.assertEqual((self.base / 'assets.json').read_text(encoding='utf-8'), before)
        self.assertTrue(current.is_file())


if __name__ == '__main__':
    unittest.main()
