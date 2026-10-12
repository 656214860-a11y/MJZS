# -*- coding: utf-8 -*-
"""O22 资产变更影响视图自检：引用镜头、需复核文件、孤立/受保护、变体不动正典。运行：python test_asset_impact.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(HERE)

import asset_context
import asset_plan

ASSET = 'CHAR_001'


def shot(sid='SH001', **values):
    item = {'id': sid, 'characters': [ASSET], 'frame': '帧/%s.png' % sid, 'duration': 3}
    item.update(values)
    return item


def gateway():
    def write_json(path, data):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return {'publish_json': write_json,
            'publish_bytes': lambda path, raw: Path(path).write_bytes(raw),
            'publish_text': lambda path, text: Path(path).write_text(text, encoding='utf-8'),
            'remove_file': lambda path: Path(path).unlink(missing_ok=True)}


class Base(unittest.TestCase):
    def build(self, *, shots=None, plan=None, videos=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        (root / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': ['storyboard/分镜拆分/EP01_分镜.json']}), encoding='utf-8')
        story = root / 'storyboard/分镜拆分/EP01_分镜.json'
        story.parent.mkdir(parents=True)
        story.write_text(json.dumps({'episode_id': 'EP01', 'shots': shots if shots is not None else [shot()]}),
                         encoding='utf-8')
        if videos is not None:
            (root / 'data').mkdir()
            (root / 'data/state.json').write_text(json.dumps({'shots': videos}), encoding='utf-8')
        if plan is not None:
            path = asset_plan.plan_file(root, '')
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
        return root

    def frame(self, root, name='帧/SH001.png'):
        path = root / 'storyboard' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\x89PNG')
        return path


class ReferencingShotsTests(unittest.TestCase):
    def test_names_the_field_that_referenced_the_asset(self):
        rows = asset_context.referencing_shots([shot(), shot('SH002', characters=[])], ASSET)
        self.assertEqual(rows, [{'id': 'SH001', 'fields': ['characters']}])

    def test_matches_location_and_props(self):
        rows = asset_context.referencing_shots(
            [shot('SH003', characters=[], location='LOC_002', props=['PROP_004'])], 'PROP_004')
        self.assertEqual(rows, [{'id': 'SH003', 'fields': ['props']}])
        self.assertEqual(asset_context.referencing_shots(
            [shot('SH003', characters=[], location='LOC_002')], 'LOC_002')[0]['fields'], ['location'])

    def test_unknown_asset_matches_nothing(self):
        self.assertEqual(asset_context.referencing_shots([shot()], 'CHAR_999'), [])


class AssetImpactTests(Base):
    def test_referenced_asset_is_protected_with_shots_and_files(self):
        root = self.build(videos={'SH001': [{'id': 'v1'}]})
        self.frame(root)
        impact = asset_plan.asset_impact(root, ASSET, episode_dir='')
        self.assertTrue(impact['adopted'])
        self.assertTrue(impact['protected'])
        self.assertFalse(impact['orphan'])
        self.assertEqual([row['shot'] for row in impact['references']], ['SH001'])
        self.assertEqual(impact['references'][0]['fields'], ['characters'])
        self.assertEqual(len(impact['files']), 1)
        self.assertEqual(impact['videos'], ['SH001'])

    def test_orphan_asset_is_recyclable(self):
        root = self.build(shots=[shot('SH002', characters=[])])
        impact = asset_plan.asset_impact(root, ASSET, episode_dir='')
        self.assertTrue(impact['orphan'])
        self.assertFalse(impact['protected'])
        self.assertEqual(impact['references'], [])

    def test_impact_reports_canon_and_variants(self):
        root = self.build(plan={ASSET: {'name': '银发少女', 'canonical_board': 'assets/正典板/CHAR_001.png',
                                        'character_anchor': '银发、蓝眼',
                                        'state_variants': [{'state_id': 'CST-01', 'name': '常服',
                                                            'override': '深色大衣', 'reference_image': ''}]}})
        impact = asset_plan.asset_impact(root, ASSET, episode_dir='')
        self.assertTrue(impact['in_plan'])
        self.assertEqual(impact['canon'], {'board': 'assets/正典板/CHAR_001.png', 'anchor': '银发、蓝眼'})
        self.assertEqual(impact['variants'], [{'state_id': 'CST-01', 'name': '常服'}])

    def test_invalid_asset_id_is_rejected(self):
        root = self.build()
        for bad in ('', 'CHAR', 'char_1'):
            with self.assertRaises(ValueError):
                asset_plan.asset_impact(root, bad, episode_dir='')

    def test_deletion_references_list_shots_and_warn(self):
        root = self.build()
        self.frame(root)
        refs = asset_plan.deletion_references(root, ASSET, episode_dir='')
        self.assertTrue(refs['protected'])
        self.assertEqual(refs['shots'], ['SH001'])
        self.assertIn('引用', refs['summary'])

    def test_deletion_references_of_an_orphan_are_empty(self):
        root = self.build(shots=[shot('SH7', characters=[])])
        refs = asset_plan.deletion_references(root, ASSET, episode_dir='')
        self.assertFalse(refs['protected'])
        self.assertEqual(refs['shots'], [])
        self.assertIn('孤立', refs['summary'])


class VariantDoesNotTouchCanonTests(Base):
    def test_writing_a_variant_leaves_canon_intact(self):
        root = self.build(plan={ASSET: {'name': '银发少女', 'canonical_board': 'assets/正典板/CHAR_001.png',
                                        'character_anchor': '银发、蓝眼'}})
        episode_dir = asset_plan.plan_file(root, '').parents[2]
        asset_plan.update_planned(episode_dir, ASSET,
                                  {'state_variants': [{'state_id': 'CST-01', 'name': '常服',
                                                       'override': '深色大衣', 'reference_image': ''}]},
                                  gateway=gateway())
        entry = json.loads(asset_plan.plan_file(root, '').read_text(encoding='utf-8'))[ASSET]
        self.assertEqual(entry['canonical_board'], 'assets/正典板/CHAR_001.png')
        self.assertEqual(entry['character_anchor'], '银发、蓝眼')
        self.assertEqual(entry['state_variants'][0]['state_id'], 'CST-01')


if __name__ == '__main__':
    unittest.main(verbosity=1)
