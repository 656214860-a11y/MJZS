# -*- coding: utf-8 -*-
"""白模参考视频接进视频接口的自检（第 8 轮）。

运行：python test_white_model_ref.py

盯四件事：
1. **能力表**：谁认参考视频、放哪个槽位（万相 media／火山 content），接不上的话里要给替代方案；
2. **认产物**：不存在／后缀不对／空文件／超上限都当场拦，不生成任务、不扣预算；
3. **拼槽位**：两个适配器真把参考视频拼进请求（不真发请求）；
4. **不许漏**：没勾「白模 · 上传」时请求与从前一模一样（一条都不多）。
"""
import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import white_model_ref
from agent.wan import WanAdapter
from agent.volcengine import VolcengineAdapter

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
# 假 mp4：只验后缀与字节数，这一层不解析视频内容。
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 64
WAN = {'cloud_provider': 'wan', 'model': 'wan2.7-r2v'}
SEED = {'cloud_provider': 'volcengine', 'model': 'doubao-seedance-2-0-pro'}
LOCAL = {'video_backend': 'comfy', 'model': 'wan2.6-i2v-flash'}


def png_file(td):
    spot = Path(td) / 'frame.png'
    spot.write_bytes(PNG)
    return spot


def mp4_file(td, body=MP4, name='白模预演.mp4'):
    spot = Path(td) / name
    if body is not None:
        spot.write_bytes(body)
    return spot


class TargetTests(unittest.TestCase):
    def test_cloud_targets_read_the_provider(self):
        self.assertEqual(white_model_ref.target(WAN), ('wan', 'wan2.7-r2v'))
        self.assertEqual(white_model_ref.target(SEED), ('volcengine', 'doubao-seedance-2-0-pro'))

    def test_a_local_config_is_local(self):
        self.assertEqual(white_model_ref.target(LOCAL), ('local', 'wan2.6-i2v-flash'))
        self.assertEqual(white_model_ref.target(None), ('local', ''))


class SupportTests(unittest.TestCase):
    def test_the_two_cloud_shapes(self):
        self.assertEqual(white_model_ref.support('wan', 'wan2.7-r2v')['slot'], 'media')
        self.assertEqual(white_model_ref.support('wan', 'wan2.7-r2v-2026-06-12')['slot'], 'media')
        self.assertEqual(white_model_ref.support('volcengine', 'doubao-seedance-2-0-pro')['slot'], 'content')
        self.assertEqual(white_model_ref.support('volcengine', 'doubao-seedance-2-5-pro')['slot'], 'content')

    def test_the_others_do_not(self):
        for provider, model in (('local', 'wan2.6-i2v-flash'), ('wan', 'wan2.6-i2v-flash'),
                                ('volcengine', 'seedance-1-0-pro')):
            self.assertIsNone(white_model_ref.support(provider, model),
                              '%s／%s 不该被认成能吃参考视频' % (provider, model))

    def test_the_local_reason_names_a_way_out(self):
        text = white_model_ref.unsupported_reason('local', 'wan2.6-i2v-flash')
        self.assertIn('本地 ComfyUI', text)
        self.assertIn('万相 2.7-r2v', text)
        self.assertIn('取消', text)

    def test_the_cloud_reason_names_the_model(self):
        text = white_model_ref.unsupported_reason('wan', 'wan2.6-i2v-flash')
        self.assertIn('wan2.6-i2v-flash', text)
        self.assertIn('Seedance 2.0', text)


class DescriptorTests(unittest.TestCase):
    """认产物：项目根 → <白模项目>/<项目名>/<镜头号>/预演记录.json → preview 那份视频。"""

    def record(self, td, preview=None, data=None):
        folder = Path(td) / 'P' / 'SH001'
        folder.mkdir(parents=True, exist_ok=True)
        value = {'shot_id': 'SH001', 'preview': str(preview)} if data is None else data
        (folder / '预演记录.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return folder

    def call(self, td, cfg=WAN):
        with patch('white_model.workspace', return_value=Path(td)):
            return white_model_ref.descriptor(Path(td) / 'P', 'SH001', cfg)

    def test_a_ready_video_comes_back_described(self):
        with tempfile.TemporaryDirectory() as td:
            video = mp4_file(td)
            self.record(td, preview=video)
            row = self.call(td)
        self.assertEqual(row['provider'], 'wan')
        self.assertEqual(row['slot'], 'media')
        self.assertEqual(row['name'], '白模预演.mp4')
        self.assertEqual(row['bytes'], len(MP4))
        self.assertEqual(row['sha256'], __import__('hashlib').sha256(MP4).hexdigest())
        self.assertIn('万相 2.7-r2v', row['usage'])

    def test_a_missing_video_is_stopped(self):
        with tempfile.TemporaryDirectory() as td:
            self.record(td, preview=Path(td) / '没有这支.mp4')
            with self.assertRaises(ValueError) as caught:
                self.call(td)
        self.assertIn('不存在', str(caught.exception))
        self.assertIn('第06步', str(caught.exception))

    def test_a_record_without_preview_is_stopped(self):
        with tempfile.TemporaryDirectory() as td:
            self.record(td, data={'shot_id': 'SH001'})
            with self.assertRaises(ValueError):
                self.call(td)

    def test_a_wrong_suffix_is_stopped(self):
        """上传路上是拿在手里的那一份（盘上记录另有第 06 步的分类规则，见下一条）。"""
        with tempfile.TemporaryDirectory() as td:
            row = {'shot_id': 'SH001', 'preview': str(mp4_file(td, name='白模预演.avi'))}
            with self.assertRaises(ValueError) as caught:
                white_model_ref.descriptor(Path(td) / 'P', 'SH001', WAN, record=row)
        self.assertIn('mp4', str(caught.exception))

    def test_a_project_file_is_not_mistaken_for_a_preview(self):
        """第 06 步把非视频的 preview 归到 project_file（.blend 工程），这儿不算参考视频。"""
        with tempfile.TemporaryDirectory() as td:
            self.record(td, preview=mp4_file(td, name='白模预演.blend'))
            with self.assertRaises(ValueError) as caught:
                self.call(td)
        self.assertIn('不存在', str(caught.exception))

    def test_an_empty_file_is_stopped(self):
        with tempfile.TemporaryDirectory() as td:
            self.record(td, preview=mp4_file(td, body=b''))
            with self.assertRaises(ValueError) as caught:
                self.call(td)
        self.assertIn('空文件', str(caught.exception))

    def test_a_too_big_video_is_stopped_before_anything_is_charged(self):
        small = (('wan', ('wan2.7-r2v',), 'media', 1, '试一下上限'),)
        with tempfile.TemporaryDirectory() as td:
            self.record(td, preview=mp4_file(td, body=b'x' * (1024 * 1024 + 1)))
            with patch.object(white_model_ref, 'SUPPORT', small):
                with self.assertRaises(ValueError) as caught:
                    self.call(td)
        self.assertIn('上限', str(caught.exception))
        self.assertIn('不会自动截断', str(caught.exception))

    def test_an_unsupported_target_is_stopped_with_a_way_out(self):
        with tempfile.TemporaryDirectory() as td:
            self.record(td, preview=mp4_file(td))
            for cfg, expected in ((LOCAL, '本地 ComfyUI'),
                                  ({'cloud_provider': 'wan', 'model': 'wan2.6-i2v-flash'}, 'wan2.6-i2v-flash')):
                with self.assertRaises(ValueError) as caught:
                    self.call(td, cfg)
                self.assertIn(expected, str(caught.exception))


class EntryTests(unittest.TestCase):
    def reference(self, td, cfg=SEED):
        video = mp4_file(td)
        folder = Path(td) / 'P' / 'SH001'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / '预演记录.json').write_text(json.dumps({'preview': str(video)}, ensure_ascii=False), encoding='utf-8')
        with patch('white_model.workspace', return_value=Path(td)):
            return white_model_ref.descriptor(Path(td) / 'P', 'SH001', cfg)

    def test_the_wan_shape(self):
        with tempfile.TemporaryDirectory() as td:
            row = white_model_ref.descriptor('随便', 'x', WAN, record={'preview': str(mp4_file(td))})
            entry = white_model_ref.entries(row)[0]
        self.assertEqual(sorted(entry), ['type', 'url'])
        self.assertEqual(entry['type'], 'reference_video')
        self.assertTrue(entry['url'].startswith('data:video/mp4;base64,'))
        self.assertEqual(base64.b64decode(entry['url'].split(',', 1)[1]), MP4, '视频内容原样内嵌')

    def test_the_seedance_shape(self):
        with tempfile.TemporaryDirectory() as td:
            row = self.reference(td)
            entry = white_model_ref.entries(row)[0]
        self.assertEqual(entry['type'], 'video_url')
        self.assertEqual(entry['role'], 'reference_video')
        self.assertTrue(entry['video_url']['url'].startswith('data:video/mp4;base64,'))

    def test_nothing_ticked_gives_nothing(self):
        self.assertEqual(white_model_ref.entries(None), [])
        self.assertEqual(white_model_ref.entries({}), [])

    def test_an_unknown_slot_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            video = mp4_file(td)
            with self.assertRaises(ValueError):
                white_model_ref.entries({'path': str(video), 'slot': '不知道'})

    def test_only_the_three_video_suffixes(self):
        with tempfile.TemporaryDirectory() as td:
            spot = Path(td) / 'a.gif'
            spot.write_bytes(b'GIF89a')
            with self.assertRaises(ValueError):
                white_model_ref.data_url(spot)


class PayloadTests(unittest.TestCase):
    """两个适配器真把参考视频拼进请求（不真发请求）。"""

    def reference(self, td, cfg=WAN):
        row = white_model_ref.descriptor('随便', 'x', cfg, record={'preview': str(mp4_file(td))})
        return row

    def test_the_wan_request_carries_it_in_media(self):
        with tempfile.TemporaryDirectory() as td:
            frame = png_file(td)
            asset = mp4_file(td, name='资产.png')
            asset.write_bytes(PNG)
            shot = {'id': 'SH001', 'duration': 5, 'video_prompt': '画面', 'generate_audio': True,
                    '_reference_mode': 'wan', '_asset_references': [{'id': 'CHAR_001', 'name': '甲', 'path': str(asset)}],
                    '_white_model_reference': self.reference(td)}
            with patch('white_model.workspace', return_value=Path(td)):
                payload = WanAdapter({'model': 'wan2.7-r2v', 'base_url': 'https://dashscope.aliyuncs.com/api/v1'}).payload(shot, frame)
        types = [item['type'] for item in payload['input']['media']]
        self.assertEqual(types, ['first_frame', 'reference_image', 'reference_video'])

    def test_the_seedance_request_carries_it_in_content(self):
        with tempfile.TemporaryDirectory() as td:
            frame = png_file(td)
            shot = {'id': 'SH001', 'duration': 5, 'video_prompt': '画面', 'generate_audio': True,
                    '_reference_mode': 'seedance', '_asset_references': [],
                    '_white_model_reference': self.reference(td, SEED)}
            payload = VolcengineAdapter({'model': 'doubao-seedance-2-0-pro',
                                         'base_url': 'https://ark.cn-beijing.volces.com/api/v3'}).payload(shot, frame)
        roles = [item.get('role') for item in payload['content']]
        self.assertIn('reference_video', roles)
        kinds = [item['type'] for item in payload['content']]
        self.assertEqual(kinds[0], 'text', '提示词还在第一位')

    def test_without_the_tick_the_request_is_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            frame = png_file(td)
            asset = mp4_file(td, name='资产.png')
            asset.write_bytes(PNG)
            shot = {'id': 'SH001', 'duration': 5, 'video_prompt': '画面', 'generate_audio': True,
                    '_reference_mode': 'wan', '_asset_references': [{'id': 'CHAR_001', 'name': '甲', 'path': str(asset)}]}
            payload = WanAdapter({'model': 'wan2.7-r2v', 'base_url': 'https://dashscope.aliyuncs.com/api/v1'}).payload(shot, frame)
        self.assertEqual([item['type'] for item in payload['input']['media']],
                         ['first_frame', 'reference_image'])


class PrepareTests(unittest.TestCase):
    """分镜那一份副本：挂上描述、把用途写进提示词、并把模式拨到参考那一支。"""

    def make_source(self, td):
        proj = Path(td) / 'p'
        (proj / 'episode').mkdir(parents=True)
        (proj / 'episode' / 'assets.json').write_text('{}', encoding='utf-8')
        (proj / 'config.json').write_text(json.dumps({'episode_dir': str(proj / 'episode'),
                                                      'episode_file': str(proj / 'episode' / 'episode.json')}), encoding='utf-8')
        return proj / 'episode' / 'episode.json'

    def shot(self):
        return {'id': 'SH001', 'title': '镜头', 'duration': 5, 'characters': [], 'location': 'LOC_001',
                'frame': 'frames/SH001.png', 'video_prompt': '画面', 'upload_assets': False, 'generate_audio': True}

    def test_the_reference_rides_along_with_the_shot(self):
        from agent.shot_assets import prepare
        with tempfile.TemporaryDirectory() as td:
            src = self.make_source(td)
            row = white_model_ref.descriptor('随便', 'x', SEED, record={'preview': str(mp4_file(td))})
            out = prepare(src, self.shot(), SEED, white=row)
        self.assertIs(out['_white_model_reference'], row)
        self.assertEqual(out['_reference_mode'], 'seedance', '白模那一支要把模式拨到参考这一支')
        self.assertIn('白模预演视频', out['video_prompt'])
        self.assertIn('不复制白模的外观与材质', out['video_prompt'])

    def test_without_a_reference_nothing_changes(self):
        from agent.shot_assets import prepare
        with tempfile.TemporaryDirectory() as td:
            src = self.make_source(td)
            out = prepare(src, self.shot(), SEED)
        self.assertNotIn('_white_model_reference', out)
        self.assertEqual(out['_reference_mode'], 'first_frame')
        self.assertNotIn('白模预演视频', out['video_prompt'])


class ValidateTests(unittest.TestCase):
    """两个提交口都调它：不勾直接放行；勾了就验，验不过当场拦。"""

    class FakeStudio:
        def __init__(self, root, cfg, shot):
            self.root = root
            self.cfg = cfg
            self._shot = shot

        def shot(self, sid):
            return self._shot

    def studio(self, root, cfg, ticked):
        shot = {'id': 'SH001', 'upload_white_model': ticked}
        return self.FakeStudio(root, cfg, shot)

    def test_not_ticked_returns_nothing(self):
        from white_model import validate_video_submission
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(validate_video_submission(self.studio(Path(td) / 'P', WAN, False), 'SH001'))

    def test_ticked_and_ready_returns_the_descriptor(self):
        from white_model import validate_video_submission
        with tempfile.TemporaryDirectory() as td:
            video = mp4_file(td)
            folder = Path(td) / 'P' / 'SH001'
            folder.mkdir(parents=True)
            (folder / '预演记录.json').write_text(json.dumps({'preview': str(video)}, ensure_ascii=False), encoding='utf-8')
            with patch('white_model.workspace', return_value=Path(td)):
                row = validate_video_submission(self.studio(Path(td) / 'P', WAN, True), 'SH001')
        self.assertEqual(row['slot'], 'media')

    def test_ticked_on_the_local_backend_is_stopped_with_a_way_out(self):
        from white_model import validate_video_submission
        with tempfile.TemporaryDirectory() as td:
            video = mp4_file(td)
            folder = Path(td) / 'P' / 'SH001'
            folder.mkdir(parents=True)
            (folder / '预演记录.json').write_text(json.dumps({'preview': str(video)}, ensure_ascii=False), encoding='utf-8')
            with patch('white_model.workspace', return_value=Path(td)):
                with self.assertRaises(ValueError) as caught:
                    validate_video_submission(self.studio(Path(td) / 'P', LOCAL, True), 'SH001')
        self.assertIn('本地 ComfyUI', str(caught.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)