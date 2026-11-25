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

    def video_file(self, root, sid='SH001', number=1):
        path = root / 'data' / sid / ('v%03d' % number) / (sid + '.mp4')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'video')
        return path

    def write_videos(self, root, videos):
        (root / 'data').mkdir(exist_ok=True)
        (root / 'data/state.json').write_text(json.dumps({'shots': videos}), encoding='utf-8')

    def signed_videos(self, root, stale=False):
        from domain import video_staleness
        source = root / 'storyboard/分镜拆分/EP01_分镜.json'
        row = json.loads(source.read_text(encoding='utf-8'))['shots'][0]
        signature = video_staleness.input_signature(source, row, 'cloud')
        if stale:
            signature = '0' * 64
        return {'SH001': [{'version': 1, 'state': 'downloaded', 'review': 'pending', 'created': 1,
                           'file': 'data/SH001/v001/SH001.mp4',
                           video_staleness.INPUT_SIGNATURE_FIELD: signature}]}


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

    def test_active_source_legacy_placeholder_uses_storage_default(self):
        root = self.build()
        from domain.asset_context import active_source
        expected = (root / 'storyboard/分镜拆分/EP01_分镜.json').resolve()
        self.assertEqual(active_source(root, 'storyboard/episode.json'), expected)

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


class AssetUsageTests(Base):
    """DES-S05-51：asset_usage 首帧三档、孤立、已生成视频、读不出分镜按过期。"""

    def test_missing_frame_when_file_absent(self):
        root = self.build()
        usage = asset_plan.asset_usage(root, ASSET, episode_dir='')
        self.assertFalse(usage['orphan'])
        self.assertEqual(usage['rows'][0]['frame'], 'missing')
        self.assertEqual(usage['rows'][0]['video'], 'none')

    def test_stale_frame_when_evidence_missing(self):
        root = self.build()
        self.frame(root)
        usage = asset_plan.asset_usage(
            root, ASSET, episode_dir='',
            frame_problem_fn=lambda *a, **k: '首帧来源已变化')
        self.assertEqual(usage['rows'][0]['frame'], 'stale')
        self.assertTrue(usage['rows'][0]['frame_reason'])

    def test_latest_frame_when_evidence_matches(self):
        root = self.build()
        self.frame(root)
        usage = asset_plan.asset_usage(
            root, ASSET, episode_dir='', frame_problem_fn=lambda *a, **k: '')
        self.assertEqual(usage['rows'][0]['frame'], 'latest')
        self.assertEqual(usage['rows'][0]['frame_reason'], '')

    def test_orphan_usage_has_empty_rows(self):
        root = self.build(shots=[shot('SH002', characters=[])])
        usage = asset_plan.asset_usage(root, ASSET, episode_dir='')
        self.assertTrue(usage['orphan'])
        self.assertEqual(usage['rows'], [])

    def test_current_signed_video_marked_generated(self):
        root = self.build()
        self.frame(root)
        self.write_videos(root, self.signed_videos(root))
        self.video_file(root)
        usage = asset_plan.asset_usage(root, ASSET, episode_dir='')
        self.assertEqual(usage['rows'][0]['video'], 'generated')
        self.assertEqual(usage['rows'][0]['video_version'], 1)
        self.assertEqual(usage['videos'], ['SH001'])
        self.assertEqual(usage['stale_videos'], [])

    def test_stale_signed_video_and_affected_list_are_reported(self):
        root = self.build(shots=[shot(), shot('SH002', characters=[])])
        self.frame(root)
        videos = self.signed_videos(root, stale=True)
        videos['SH002'] = [dict(row, file='data/SH002/v001/SH002.mp4') for row in videos['SH001']]
        self.write_videos(root, videos)
        self.video_file(root)
        self.video_file(root, 'SH002')
        usage = asset_plan.asset_usage(root, ASSET, episode_dir='')
        self.assertEqual(usage['rows'][0]['video'], 'stale')
        self.assertEqual(usage['stale_videos'], ['SH001'])

    def test_legacy_downloaded_video_is_unknown_not_generated(self):
        root = self.build(videos={'SH001': [{'version': 1, 'state': 'downloaded', 'review': 'pending',
                                             'file': 'data/SH001/v001/SH001.mp4'}]})
        self.video_file(root)
        usage = asset_plan.asset_usage(root, ASSET, episode_dir='')
        self.assertEqual(usage['rows'][0]['video'], 'legacy_unknown')

    def test_missing_video_file_and_generating_task_are_distinct(self):
        root = self.build()
        self.frame(root)
        self.write_videos(root, self.signed_videos(root))
        usage = asset_plan.asset_usage(root, ASSET, episode_dir='')
        self.assertEqual(usage['rows'][0]['video'], 'missing')
        self.write_videos(root, {'SH001': [{'version': 1, 'state': 'queued'}]})
        usage = asset_plan.asset_usage(root, ASSET, episode_dir='')
        self.assertEqual(usage['rows'][0]['video'], 'generating')

    def test_frame_check_error_marks_stale_without_raising(self):
        root = self.build()
        self.frame(root)

        def boom(*_a, **_k):
            raise RuntimeError('boom')

        usage = asset_plan.asset_usage(
            root, ASSET, episode_dir='', frame_problem_fn=boom)
        self.assertEqual(len(usage['rows']), 1)
        self.assertEqual(usage['rows'][0]['frame'], 'stale')
        self.assertIn('boom', usage['rows'][0]['frame_reason'])


if __name__ == '__main__':
    unittest.main(verbosity=1)
