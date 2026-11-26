"""REQ-S05-02/10/13/14/20/21/23/30/31/40：资产管理阶段的依赖、契约、并行配置、完成判定与 SKILL。"""
import json
import tempfile
import unittest
from pathlib import Path

from contract import asset_contract
import stage_flow
import stage_parallel
from contract import stage_path_service

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '05资产管理SKILL'
SKILLS = ('pipeline-assets', 'asset-auto-fill', 'asset-candidate-wall',
          'asset-copyright-filter', 'asset-dedupe', 'asset-visual-rank')
PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478'
                    '9c6360000002000001e221bc330000000049454e44ae426082')


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


class AssetsScopeTests(unittest.TestCase):
    def test_req_s05_02_assets_depends_on_animatic_and_sg_b_guards_entry(self):
        self.assertEqual(stage_flow.DEPENDS['assets'], ('storyboard',))
        gate = next(row for row in stage_parallel.GATES if row['id'] == 'SG-B')
        self.assertEqual((gate['from'], gate['to']), ('animatic', 'assets'))
        self.assertTrue(gate.get('advisory'))
        self.assertEqual(stage_flow.DEPENDS['continuity'], ('assets',))

    def test_req_s05_10_asset_id_prefixes(self):
        self.assertEqual(asset_contract.PREFIX, {'character': 'CHAR', 'scene': 'LOC', 'prop': 'PROP'})
        self.assertEqual(asset_contract.kind_of('LOC_012'), 'scene')
        self.assertEqual(asset_contract.kind_of('X_001'), '')

    def test_req_s05_13_canon_board_has_seven_views(self):
        self.assertEqual(len(asset_contract.TURNAROUND), 4)
        self.assertEqual(len(asset_contract.HEADS), 3)
        self.assertEqual(len(asset_contract.VIEWS), 7)
        data = asset_contract.defaults('character')
        self.assertEqual(data['reference_role'], '面部、发型、服装')
        self.assertEqual(data['reference_exclude'], '场景、动作、镜头')
        self.assertIs(data['locked'], False)

    def test_req_s05_14_validate_rules(self):
        locked = {'name': 'A', 'locked': True, 'canonical_board': 'board.png'}
        self.assertTrue(any('character_anchor' in item for item in asset_contract.validate(locked, 'CHAR_001')))
        locked['character_anchor'] = 'x'
        self.assertEqual(asset_contract.validate(locked, 'CHAR_001'), [])
        bad_state = {'name': 'A', 'canonical_board': 'b', 'state_variants': [{'state_id': 'S1', 'name': 'n'}]}
        problems = asset_contract.validate(bad_state, 'CHAR_001')
        self.assertTrue(any('CST-01' in item for item in problems))
        self.assertTrue(any('override' in item for item in problems))
        scene = {'name': 'S', 'aspect_ratio': 'wide'}
        self.assertTrue(any('aspect_ratio' in item for item in asset_contract.validate(scene, 'LOC_001')))
        self.assertTrue(any('holder' in item for item in asset_contract.validate({'holder': 'bob'}, 'PROP_001')))

    def test_req_s05_20_parallel_config_is_serial_per_asset(self):
        spec = stage_parallel.CONFIG['assets']
        self.assertTrue(spec['serial'])
        self.assertEqual((spec['min'], spec['max'], spec['limit']), (3, 5, 5))
        self.assertEqual(spec['retry']['attempts'], 2)
        self.assertEqual(spec['retry']['on_exhaust'], stage_parallel.ON_BLOCK)
        self.assertIn('正典板→状态变体→锚点→参考职责', spec['why'])

    def test_req_s05_21_assets_is_a_paid_stage(self):
        self.assertIn('assets', stage_flow.PAID_STAGES)

    def test_req_s05_23_new_directory_and_read_only_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_path_service.write_dir(td, 'assets').name, '05资产管理')
            self.assertEqual(stage_path_service.LEGACY_NUMBERED['assets'], '04资产管理')
            names = [path.name for path in stage_path_service.read_dirs(td, 'assets')]
            self.assertEqual(names[:2], ['05资产管理', '04资产管理'])

    def test_req_s05_31_empty_project_passes_without_started(self):
        with tempfile.TemporaryDirectory() as td:
            result = stage_parallel.assets_locked(Path(td))
        self.assertTrue(result['ok'])
        self.assertFalse(result['started'])

    def test_req_s05_30_sg01_needs_real_image_lock_and_anchor(self):
        from asset_context import library_dir
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            base = library_dir(project)
            plan_file = base / 'assets' / '资产清单' / 'assets.json'
            (base / 'assets' / 'characters').mkdir(parents=True)
            image = base / 'assets' / 'characters' / 'a.png'
            row = {'name': 'A', 'image': 'assets/characters/a.png', 'locked': True, 'character_anchor': 'x'}
            write_json(plan_file, {'CHAR_001': row})
            blocked = stage_parallel.assets_locked(project)
            self.assertFalse(blocked['ok'])
            self.assertTrue(blocked['started'])
            self.assertTrue(any('还没导入图片' in item for item in blocked['problems']))
            image.write_bytes(PNG)
            self.assertTrue(stage_parallel.assets_locked(project)['ok'])
            write_json(plan_file, {'CHAR_001': {**row, 'locked': False}})
            result = stage_parallel.assets_locked(project)
            self.assertFalse(result['ok'])
            self.assertTrue(any('没锁定锚点' in item for item in result['problems']))

    def test_req_s05_32_sg01_reads_images_from_the_registry(self):
        from asset_context import library_dir
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            base = library_dir(project)
            plan_file = base / 'assets' / '资产清单' / 'assets.json'
            (base / 'assets' / 'characters').mkdir(parents=True)
            (base / 'assets' / 'characters' / 'a.png').write_bytes(PNG)
            # 程序真实形态：清单里没有 image（_sync_plan 会剔除），图片只登记在资产库根的 assets.json
            write_json(plan_file, {'CHAR_001': {'name': 'A', 'locked': True, 'character_anchor': 'x'}})
            blocked = stage_parallel.assets_locked(project)
            self.assertFalse(blocked['ok'])
            self.assertTrue(any('还没导入图片' in item for item in blocked['problems']))
            write_json(base / 'assets.json', {'CHAR_001': {'image': 'assets/characters/a.png'}})
            self.assertTrue(stage_parallel.assets_locked(project)['ok'])
            (base / 'assets' / 'characters' / 'a.png').unlink()
            self.assertFalse(stage_parallel.assets_locked(project)['ok'])

    def test_req_s05_31_names_only_draft_is_not_started(self):
        from asset_context import library_dir
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            write_json(library_dir(project) / 'assets' / '资产清单' / 'assets.json',
                       {'CHAR_001': {'name': 'A'}})
            result = stage_parallel.assets_locked(project)
        self.assertTrue(result['ok'])
        self.assertFalse(result['started'])

    def test_req_s05_40_skills_exist_and_entry_depends_on_animatic(self):
        for name in SKILLS:
            with self.subTest(name=name):
                self.assertTrue((SKILL_DIR / (name + '.skill.md')).is_file())
        entry = (SKILL_DIR / 'pipeline-assets.skill.md').read_text(encoding='utf-8')
        self.assertIn('dependsOn: [pipeline-animatic]', entry)
        self.assertIn('paid: false', entry)
        self.assertIn('parallelizable: false', entry)


if __name__ == '__main__':
    unittest.main()
