# -*- coding: utf-8 -*-
"""镜头编号重排的自检。"""
import json
import tempfile
import unittest
from pathlib import Path

import shot_numbering as numbering


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def storyboard(episode, title, ids):
    return {'episode_id': episode, 'title': title, 'duration': 15, 'shots': [
        {'id': sid, 'title': title + sid, 'duration': 5, 'characters': [], 'location': 'LOC_001',
         'frame': 'frames/%s.png' % sid, 'video_prompt': title + '的画面 ' + sid} for sid in ids]}


class RenumberTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.ep2 = self.project / 'storyboard/分镜拆分/定稿_EP002/episode.json'
        self.ep3 = self.project / 'storyboard/分镜拆分/EP003_半夜谁在喊有人吗_分镜.json'
        write_json(self.ep2, storyboard('EP002', '外卖长腿了', ['SH004', 'SH005', 'SH006']))
        write_json(self.ep3, storyboard('EP003', '半夜谁在喊有人吗', ['SH001', 'SH002', 'SH003']))
        self.prompts = self.project / 'storyboard/video_prompts'
        self.prompts.mkdir(parents=True)
        for sid, tag in (('SH001', 'E3S1'), ('SH002', 'E3S2'), ('SH003', 'E3S3'),
                         ('SH004', 'E2S1'), ('SH005', 'E2S2'), ('SH006', 'E2S3')):
            (self.prompts / (sid + '.txt')).write_text('%s %s' % (tag, sid), encoding='utf-8')
        (self.project / 'cloud_video/镜头/SH004').mkdir(parents=True)
        (self.project / 'cloud_video/镜头/SH004/SH004.mp4').write_bytes(b'\x00\x01SH004')
        recycled = self.project / '工作流任务/回收站/旧稿/EP002_SH004.json'
        recycled.parent.mkdir(parents=True)
        recycled.write_text('{"id":"SH004"}', encoding='utf-8')

    def ids(self, path):
        return [shot['id'] for shot in json.loads(path.read_text(encoding='utf-8'))['shots']]

    def run_apply(self):
        return numbering.renumber(self.project, [self.ep2, self.ep3], apply=True, log=lambda *a: None)

    def test_mapping_follows_episode_order(self):
        ordered = numbering.storyboard_order([self.ep3, self.ep2])
        self.assertEqual(numbering.build_mapping(ordered),
                         {'SH004': 'SH001', 'SH005': 'SH002', 'SH006': 'SH003',
                          'SH001': 'SH004', 'SH002': 'SH005', 'SH003': 'SH006'})

    def test_dry_run_changes_nothing(self):
        result = numbering.renumber(self.project, [self.ep2, self.ep3], apply=False, log=lambda *a: None)
        self.assertEqual(self.ids(self.ep2), ['SH004', 'SH005', 'SH006'])
        self.assertIsNone(result['backup'])
        self.assertFalse((self.project / '工作流任务/升级备份').exists())

    def test_apply_renumbers_storyboards_and_files(self):
        self.run_apply()
        self.assertEqual(self.ids(self.ep2), ['SH001', 'SH002', 'SH003'])
        self.assertEqual(self.ids(self.ep3), ['SH004', 'SH005', 'SH006'])
        self.assertEqual((self.prompts / 'SH001.txt').read_text(encoding='utf-8'), 'E2S1 SH001')
        self.assertEqual((self.prompts / 'SH004.txt').read_text(encoding='utf-8'), 'E3S1 SH004')
        self.assertEqual(sorted(p.name for p in self.prompts.iterdir()),
                         ['SH001.txt', 'SH002.txt', 'SH003.txt', 'SH004.txt', 'SH005.txt', 'SH006.txt'])
        moved = self.project / 'cloud_video/镜头/SH001/SH001.mp4'
        self.assertEqual(moved.read_bytes(), b'\x00\x01SH004')
        self.assertFalse((self.project / 'cloud_video/镜头/SH004').exists())
        self.assertEqual(numbering.verify(self.project, [self.ep2, self.ep3]), [])

    def test_backup_keeps_originals_and_second_pass_is_idle(self):
        result = self.run_apply()
        backup = result['backup']
        self.assertTrue(backup.is_dir())
        saved = json.loads((backup / self.ep3.relative_to(self.project)).read_text(encoding='utf-8'))
        self.assertEqual([shot['id'] for shot in saved['shots']], ['SH001', 'SH002', 'SH003'])
        self.assertEqual((backup / 'storyboard/video_prompts/SH001.txt').read_text(encoding='utf-8'), 'E3S1 SH001')
        again = numbering.renumber(self.project, [self.ep2, self.ep3], apply=False, log=lambda *a: None)
        self.assertEqual(again['mapping'], {})
        self.assertEqual((again['contents'], again['renames']), ([], []))

    def test_recycle_bin_is_left_alone(self):
        self.run_apply()
        recycled = self.project / '工作流任务/回收站/旧稿/EP002_SH004.json'
        self.assertTrue(recycled.is_file())
        self.assertEqual(recycled.read_text(encoding='utf-8'), '{"id":"SH004"}')

    def test_per_episode_numbering_is_refused_not_silently_corrupted(self):
        """各集都从 SH001 编号时，按编号整体重排会把别集的同名编号一起改掉：必须拒绝且不动任何文件。"""
        write_json(self.ep2, storyboard('EP002', '外卖长腿了', ['SH001', 'SH002', 'SH003']))
        write_json(self.ep3, storyboard('EP003', '半夜谁在喊有人吗', ['SH001', 'SH002', 'SH003']))
        with self.assertRaises(ValueError) as caught:
            numbering.renumber(self.project, [self.ep2, self.ep3], apply=False, log=lambda *a: None)
        message = str(caught.exception)
        self.assertIn('SH001', message)
        self.assertIn('SH004', message)
        self.assertIn(self.ep2.name, message)                       # 报错要点名是哪两份分镜冲突
        self.assertIn(self.ep3.name, message)
        with self.assertRaises(ValueError):
            self.run_apply()
        self.assertEqual(self.ids(self.ep2), ['SH001', 'SH002', 'SH003'])
        self.assertEqual(self.ids(self.ep3), ['SH001', 'SH002', 'SH003'])
        self.assertFalse((self.project / '工作流任务/升级备份').exists())

    def test_conflicting_target_is_reported(self):
        broken = self.project / 'storyboard/分镜拆分/定稿_EP003/episode.json'
        write_json(broken, storyboard('EP003', '冲突', ['SH001', 'SH004']))
        with self.assertRaises(ValueError):
            numbering.build_mapping(numbering.storyboard_order([self.ep2, broken]))


if __name__ == '__main__':
    unittest.main()
