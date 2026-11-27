"""REQ-S05 测试锚定：资产管理（S05）尚无测试锚点的需求行为。

只使用 ``tempfile`` 临时项目和桩件，不联网、不打开真实用户项目。每条测试名与 docstring
都写明锚定的 ``REQ-S05-xx``；断言对应需求原文里可判定的那句行为。已有测试文件确实覆盖的
条目（12/15/16 全部，11/33 的一部分）只在原测试 docstring 认领，本文件补其余行为。
"""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from domain import animatic_service
import asset_batch_service
from contract import asset_contract
import asset_plan
import cloud_assets
from domain import confirm_gates
import pet_bus
from contract import production_model_contract
from asset_context import active_source, library_dir
from project_context_factory import project_context
from stage_execution_service import (
    animatic_reference_paths,
    asset_batch_gateway,
    asset_plan_gateway,
    import_animatic_references,
    require_formal_asset_generation,
)
from contract.stage_path_service import shared_reference_dir, write_dir

ROOT = Path(__file__).resolve().parents[1]


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def _board(path, shot_id='SH001', character='CHAR_001'):
    _write(path, {'episode_id': 'EP001', 'shots': [
        {'id': shot_id, 'characters': [character], 'location': 'LOC_001'}]})
    return path


def _skill_text():
    return (ROOT / 'skills' / '05资产管理SKILL' / 'pipeline-assets.skill.md').read_text(encoding='utf-8')


class ReqS05AnchorTests(unittest.TestCase):
    # --- 场景默认值与项目锁 ----------------------------------------------
    def test_req_s05_03_scene_resolution_uses_project_lock_then_default(self):
        """REQ-S05-03：场景画幅与分辨率默认 16:9／1920x1080，项目锁优先。"""
        self.assertEqual(
            asset_contract.defaults('scene', {'resolution': '1280x720'})['resolution'],
            '1280x720', '锁里有 resolution 时用锁值')
        self.assertEqual(
            asset_contract.defaults('scene', {})['resolution'],
            '1920x1080', '无锁时用默认分辨率')
        self.assertEqual(
            asset_contract.defaults('scene')['resolution'],
            '1920x1080', '不传锁时用默认分辨率')
        # 画幅锁优先也一并断言
        self.assertEqual(
            asset_contract.defaults('scene', {'aspect_ratio': '9:16'}, '1:1')['aspect_ratio'],
            '9:16', '画幅项目锁优先')
        self.assertEqual(
            asset_contract.defaults('scene', {}, '1:1')['aspect_ratio'],
            '1:1', '无锁时用已存偏好')
        self.assertEqual(
            asset_contract.defaults('scene')['aspect_ratio'],
            '16:9', '默认画幅')

    # --- 清单来源与同步 ---------------------------------------------------
    def test_req_s05_01_only_adopted_storyboards_export_assets(self):
        """REQ-S05-01：清单只由「已采用」分镜导出；没有采用分镜时不凭默认目录建清单。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adopted = _board(root / 'storyboard' / '分镜拆分' / 'adopted.json', 'SH001', 'CHAR_001')
            other = _board(root / 'storyboard' / '分镜拆分' / 'other.json', 'SH002', 'CHAR_002')
            _write(root / 'ui_settings.json', {
                'adopted_storyboards': ['storyboard/分镜拆分/adopted.json']})
            context = project_context(root)
            base = library_dir(root)
            rows = asset_plan._sync_plan(
                root, base, ['storyboard/分镜拆分/other.json'], scope='adopted', _adopting=False,
                context=context, gateway=asset_plan_gateway())
            self.assertEqual(rows, {}, '未采用的分镜不能导出资产')
            stored = json.loads((base / 'assets' / '资产清单' / 'assets.json').read_text(encoding='utf-8'))
            self.assertNotIn('CHAR_002', stored)
            rows = asset_plan._sync_plan(
                root, base, ['storyboard/分镜拆分/adopted.json'], scope='adopted', _adopting=False,
                context=context, gateway=asset_plan_gateway())
            self.assertIn('CHAR_001', rows)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _board(root / 'storyboard' / '分镜拆分' / 'other.json', 'SH002', 'CHAR_002')
            _write(root / 'ui_settings.json', {'adopted_storyboards': []})
            context = project_context(root)
            with self.assertRaisesRegex(ValueError, '手动采用分镜'):
                active_source(root, context=context)
            with self.assertRaisesRegex(ValueError, '手动采用分镜'):
                asset_plan._sync_plan(
                    root, library_dir(root), None, scope='adopted', _adopting=False,
                    context=context, gateway=asset_plan_gateway())
            self.assertFalse((library_dir(root) / 'assets' / '资产清单' / 'assets.json').exists())

    def test_req_s05_04_shared_references_are_reused_without_formal_asset_registration(self):
        """REQ-S05-04：分镜预演准备的共享参考图目录由本阶段复用；本地草图不进入正式资产登记。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'board.png'
            source.write_bytes(b'reference-bytes')
            target = shared_reference_dir(root) / (animatic_service.digest(b'reference-bytes') + '.png')
            self.assertEqual(import_animatic_references(root, [source]), (target,))
            self.assertTrue(target.is_relative_to(shared_reference_dir(root)))
            self.assertIn(target, animatic_reference_paths(root))
            self.assertFalse((write_dir(root, 'assets') / 'assets' / '资产清单' / 'assets.json').exists())
            self.assertFalse((write_dir(root, 'assets') / 'assets.json').exists())

    def test_req_s05_05_skill_inputs_do_not_require_manifests(self):
        """REQ-S05-05：内置 pipeline-assets 已退役，清单导出不依赖任何 manifest。"""
        from orchestrator.skill_project_layer import RETIRED_BUILTIN_SKILL_IDS
        self.assertIn('pipeline-assets', RETIRED_BUILTIN_SKILL_IDS)
        self.assertFalse((ROOT / 'skills' / '05资产管理SKILL' / 'pipeline-assets.skill.md').exists())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _board(root / 'storyboard' / '分镜拆分' / 'board.json')
            _write(root / 'ui_settings.json', {
                'adopted_storyboards': ['storyboard/分镜拆分/board.json']})
            rows = asset_plan._sync_plan(
                root, library_dir(root), ['storyboard/分镜拆分/board.json'], scope='adopted',
                _adopting=False, context=project_context(root), gateway=asset_plan_gateway())
            self.assertIn('CHAR_001', rows)
            self.assertIn('LOC_001', rows)
            self.assertFalse((root / 'characterManifest.json').exists())

    def test_req_s05_11_sync_preserves_existing_fields_and_records_used_in(self):
        """REQ-S05-11：同步只补缺失契约字段，已有值一个不动；used_in 记录引用镜头编号。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _board(root / 'storyboard' / '分镜拆分' / 'board.json')
            _write(root / 'ui_settings.json', {
                'adopted_storyboards': ['storyboard/分镜拆分/board.json']})
            base = library_dir(root)
            plan = base / 'assets' / '资产清单' / 'assets.json'
            _write(plan, {'CHAR_001': {
                'name': '旧名', 'character_anchor': '银发', 'locked': True,
                'custom': 'keep', 'used_in': ['OLD']}})
            rows = asset_plan._sync_plan(
                root, base, ['storyboard/分镜拆分/board.json'], scope='adopted', _adopting=False,
                context=project_context(root), gateway=asset_plan_gateway())
            stored = json.loads(plan.read_text(encoding='utf-8'))['CHAR_001']
            self.assertEqual(stored['name'], '旧名')
            self.assertEqual(stored['character_anchor'], '银发')
            self.assertTrue(stored['locked'])
            self.assertEqual(stored['custom'], 'keep')
            self.assertIn('SH001', stored['used_in'])
            self.assertIn('OLD', stored['used_in'], '已有 used_in 不被清空')
            self.assertIn('base_anchor', stored, '缺失的契约字段被补齐')
            self.assertEqual(rows['CHAR_001']['used_in'], ['SH001'])

    def test_req_s05_17_only_registered_existing_images_count_as_imported(self):
        """REQ-S05-17：计划自带的 image 不被采信；只有登记过且文件存在的图片才算已导入。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _board(root / 'storyboard' / '分镜拆分' / 'board.json')
            _write(root / 'ui_settings.json', {
                'adopted_storyboards': ['storyboard/分镜拆分/board.json']})
            base = library_dir(root)
            plan = base / 'assets' / '资产清单' / 'assets.json'
            fake = base / 'assets' / 'characters' / 'fake.png'
            fake.parent.mkdir(parents=True)
            fake.write_bytes(b'fake')
            _write(plan, {'CHAR_001': {'name': '甲', 'image': 'assets/characters/fake.png'}})
            rows = asset_plan._sync_plan(
                root, base, ['storyboard/分镜拆分/board.json'], scope='adopted', _adopting=False,
                context=project_context(root), gateway=asset_plan_gateway())
            self.assertEqual(rows['CHAR_001']['status'], '待导入')
            self.assertNotIn('image', rows['CHAR_001'])

            real = base / 'assets' / 'characters' / 'real.png'
            real.write_bytes(b'real')
            _write(base / 'assets.json', {'CHAR_001': {
                'name': '甲', 'image': 'assets/characters/real.png'}})
            rows = asset_plan._sync_plan(
                root, base, ['storyboard/分镜拆分/board.json'], scope='adopted', _adopting=False,
                context=project_context(root), gateway=asset_plan_gateway())
            self.assertEqual(rows['CHAR_001']['status'], '已导入')
            self.assertEqual(rows['CHAR_001']['image'], 'assets/characters/real.png')

            real.unlink()
            rows = asset_plan._sync_plan(
                root, base, ['storyboard/分镜拆分/board.json'], scope='adopted', _adopting=False,
                context=project_context(root), gateway=asset_plan_gateway())
            self.assertEqual(rows['CHAR_001']['status'], '待导入', '登记了但文件不存在也不算已导入')

    # --- 后端与删除 -------------------------------------------------------
    def test_req_s05_22_backend_names_come_from_l0_and_formal_assets_need_online(self):
        """REQ-S05-22：本地/云端模型名由 L0 统一；正式资产必须选线上 API 模型。"""
        self.assertEqual(cloud_assets.LOCAL, production_model_contract.ASSET_LOCAL_MODEL)
        self.assertEqual(cloud_assets.MODELS, list(production_model_contract.ASSET_CLOUD_MODELS))
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(asset_batch_service.current_model(temporary),
                             production_model_contract.ASSET_LOCAL_MODEL)
            with patch('stage_parallel.evaluate', return_value={'ok': True}):
                with self.assertRaisesRegex(ValueError, '线上 API 模型'):
                    require_formal_asset_generation(temporary, online_model=False)
                require_formal_asset_generation(temporary, online_model=True)

    def test_req_s05_33_deletion_recycles_and_restores_the_same_bytes(self):
        """REQ-S05-33：删除前列出引用镜头；删除走回收站；恢复还原相同字节。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _board(root / 'storyboard' / '分镜拆分' / 'board.json')
            _write(root / 'ui_settings.json', {
                'adopted_storyboards': ['storyboard/分镜拆分/board.json']})
            base = library_dir(root)
            _write(base / 'assets' / '资产清单' / 'assets.json', {'CHAR_001': {'name': '甲'}})
            image = base / 'assets' / 'characters' / 'CHAR_001.png'
            image.parent.mkdir(parents=True)
            raw = b'unique-png-bytes-12345'
            image.write_bytes(raw)
            _write(base / 'assets.json', {'CHAR_001': {
                'name': '甲', 'image': 'assets/characters/CHAR_001.png'}})

            impact = asset_plan.asset_impact(root, 'CHAR_001', episode_dir='')
            references = asset_plan.deletion_references(root, 'CHAR_001', episode_dir='')
            self.assertTrue(impact['protected'])
            self.assertEqual([row['shot'] for row in impact['references']], ['SH001'])
            self.assertEqual(references['shots'], ['SH001'])

            removed = asset_batch_service.remove_asset_image(
                base, 'CHAR_001', gateway=asset_batch_gateway())
            self.assertEqual(removed, image.resolve())
            self.assertFalse(image.exists(), '删除后原位置不再保留文件')
            restored = asset_batch_service.restore_asset_image(
                base, 'CHAR_001', gateway=asset_batch_gateway())
            self.assertEqual(restored, image.resolve())
            self.assertEqual(image.read_bytes(), raw, '恢复必须还原相同字节')

    # --- SKILL 正典准入 ---------------------------------------------------
    def test_req_s05_41_canon_admission_and_conflicts_do_not_overwrite_assets(self):
        """REQ-S05-41：缺来源/锚点/版本不得进正典；冲突只生成待修复项，不覆盖已确认资产。"""
        assets = {'CHAR_001': {
            'name': '甲', 'canonical_board': 'board.png', 'character_anchor': '银发'}}
        before = json.loads(json.dumps(assets, ensure_ascii=False))
        rows = confirm_gates.conflict_candidates(
            ledger={'conflicts': [{'kind': '多图抢同一件事', 'batch_id': 'B1',
                                   'priority': ['a.png', 'b.png'], 'reason': '冲突'}]},
            assets=assets)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['gate_id'], 'G-08')
        self.assertEqual(assets, before, '冲突只生成待修复项，不改已确认资产')

    def test_req_s05_42_panel_text_uses_current_stage_labels(self):
        """REQ-S05-42：组件图使用 pet_bus 的现行阶段标签，不残留旧内部标识。"""
        text = asset_contract.panel_text()
        assets = pet_bus.stage_label('assets')
        continuity = pet_bus.stage_label('continuity')
        self.assertTrue(text.startswith('资产管理页（%s）\n' % assets))
        self.assertIn(continuity, text)
        for stale in ('02_assets', '03_continuity'):
            self.assertNotIn(stale, text)

    def test_req_s05_53_sg_b_advisory_allows_manual_assets_and_keeps_guards(self):
        """REQ-S05-53：S05 数据依赖回归 storyboard，SG-B 改为提醒型放行手动资产，保留线上模型与自动链门禁。"""
        import infra.file_cache as file_cache
        import infra.pet_state as pet_state
        import stage_flow
        import stage_parallel

        self.assertEqual(stage_flow.DEPENDS['assets'], ('storyboard',))
        gate = stage_parallel.gate_for('assets')
        self.assertEqual(gate['id'], 'SG-B')
        self.assertTrue(gate.get('advisory'))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # T1：空项目（未做 S04）——浏览放行并标未开始，手动不拦；全自动 PRODUCTION 拦住，标 skipped 后豁免
            empty = stage_parallel.animatic_ready(root)
            self.assertTrue(empty['ok'])
            self.assertFalse(empty['started'])
            self.assertEqual(empty['verdict'], stage_parallel.UPSTREAM_BLANK)
            self.assertTrue(empty.get('advisory'))
            self.assertEqual(stage_flow.blockers(root, 'assets'), [])
            self.assertFalse(stage_parallel.production_ready(root, 'assets')['ok'])

            advisory = require_formal_asset_generation(root, online_model=True)
            self.assertIsInstance(advisory, str)
            self.assertIn('分镜预演', advisory)
            with self.assertRaisesRegex(ValueError, '线上 API 模型'):
                require_formal_asset_generation(root, online_model=False)

            machine = pet_state.Machine(root, persist=True).load()
            machine.stages['animatic'] = {'state': 'skipped'}
            machine.save()
            exempt = stage_parallel.production_ready(root, 'assets')
            self.assertTrue(exempt['ok'])
            self.assertTrue(exempt['exempt'])

            # T2：S04 已生成未锁定——animatic_ready 为 ok=False, started=True，但 advisory 不拦手动入口
            source = root / '03初步分镜' / '分镜拆分' / 'ep1.json'
            _write(source, {'episode_id': 'EP001', 'shots': [
                {'id': 'SH001', 'duration': 3, 'image_prompt': '街角背影',
                 'characters': ['CHAR_001'], 'location': 'LOC_001'}]})
            _write(root / 'ui_settings.json', {'adopted_storyboards': ['03初步分镜/分镜拆分/ep1.json']})
            folder = write_dir(root, 'animatic')
            folder.mkdir(parents=True, exist_ok=True)
            files = {}
            for name, payload in (('preview.mp4', b'video'), ('temp.wav', b'audio'), ('SH001.png', b'png')):
                (folder / name).write_bytes(payload)
                files[name] = file_cache.file_digest(folder / name)
            manifest = {
                'kind': 'animatic', 'source': '03初步分镜/分镜拆分/ep1.json',
                'source_sha256': file_cache.file_digest(source),
                'video': 'preview.mp4', 'audio': 'temp.wav', 'files': files,
                'shots': [{'id': 'SH001', 'image': 'SH001.png'}],
                'confirmed': {'rhythm': False, 'duration': False, 'dialogue_sync': False},
            }
            _write(folder / animatic_service.MANIFEST, manifest)

            unconfirmed = stage_parallel.animatic_ready(root)
            self.assertFalse(unconfirmed['ok'])
            self.assertTrue(unconfirmed['started'])
            self.assertEqual(stage_parallel.blocked_stages(root, 'assets'), ())
            self.assertFalse(stage_parallel.production_ready(root, 'assets')['ok'])
            advisory2 = require_formal_asset_generation(root, online_model=True)
            self.assertTrue(advisory2)

            # S04 三项确认锁定后：SG-B 通过，不再返回提醒
            manifest['confirmed'] = {'rhythm': True, 'duration': True, 'dialogue_sync': True}
            _write(folder / animatic_service.MANIFEST, manifest)
            locked = stage_parallel.animatic_ready(root)
            self.assertTrue(locked['ok'])
            self.assertTrue(locked['started'])
            self.assertEqual(require_formal_asset_generation(root, online_model=True), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
