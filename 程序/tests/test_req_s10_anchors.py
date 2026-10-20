"""REQ-S10 测试锚定：视频阶段的数据依赖、门禁与 SKILL 页面文字。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine
import local_video
import pet_bus
import project_settings
import skill_tools
import stage_flow
import stage_parallel
from agent.core import save

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '10视频生成SKILL'


def _auto_review_project(folder):
    """一个镜头的最小项目：本地与云端两条下载路径都用它。"""
    root = Path(folder)
    (root / 'episode.json').write_text(json.dumps({'shots': [
        {'id': 'SH001', 'duration': 5, 'video_prompt': '推镜', 'frame': 'f.png'}]}), encoding='utf-8')
    (root / 'config.json').write_text(json.dumps({
        'reserve_seconds': 0, 'budget_seconds': 0, 'live_enabled': True,
        'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe', 'local_video': {}}), encoding='utf-8')
    (root / 'f.png').write_bytes(b'\x89PNG\r\n\x1a\n')
    return root


def _local_poll(root, qc_errors=(), pet=None):
    """跑一次 LocalStudio.poll 的下载＋质检分支，返回 (版本记录, 返回文案)。"""
    studio = object.__new__(local_video.LocalStudio)
    studio.root = root
    studio.db = root / 'data' / 'state.json'
    studio.cfg = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe', 'local_video': {}}
    studio.episode_path = root / 'episode.json'
    studio.episode = json.loads(studio.episode_path.read_text(encoding='utf-8'))
    if pet is not None:
        studio.pet = pet
    save(studio.db, {'shots': {'SH001': [{
        'version': 1, 'state': 'queued', 'task_id': 'PID', 'backend': 'comfy',
        'endpoint': 'http://127.0.0.1:8189', 'output_node': '92', 'seconds': 5,
        'review': 'pending'}]}})

    class FakeAPI:
        def __init__(self, url):
            self.url = url

        def call(self, path, payload=None, **kw):
            if path.startswith('/history/'):
                return {'PID': {'status': {'status_str': 'success'},
                                'outputs': {'92': {'gifs': [{'filename': 'x.mp4', 'type': 'output'}]}}}}
            raise AssertionError(path)

        def download(self, item, dest):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b'video')

    with patch('local_video.LocalAPI', FakeAPI), \
            patch('local_video.check', return_value={'errors': list(qc_errors)}), \
            patch('local_video.command'), \
            patch('agent.media.probe', return_value={'streams': []}), \
            patch.object(engine.Studio, 'record_video_usage'), \
            patch.object(engine.Studio, 'publish_manifest'):
        message = local_video.LocalStudio.poll(studio, 'SH001')
    return studio.state()['shots']['SH001'][-1], message


def _cloud_poll(root, qc_errors=()):
    """跑一次 Studio.poll 的云端下载＋质检分支，返回 (版本记录, 返回文案)。"""
    studio = object.__new__(engine.Studio)
    studio.root = root
    studio.db = root / 'data' / 'state.json'
    studio.cfg = {'live_enabled': True, 'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    studio.episode_path = root / 'episode.json'
    studio.episode = json.loads(studio.episode_path.read_text(encoding='utf-8'))
    save(studio.db, {'shots': {'SH001': [{
        'version': 1, 'state': 'succeeded', 'task_id': 'TASK', 'seconds': 5,
        'review': 'pending'}]}})

    class FakeClient:
        def poll(self, task_id):
            return {'status': 'succeeded', 'url': 'https://example.com/v.mp4'}

        def download_video(self, task_id, dest):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b'video')

    studio.client = lambda: FakeClient()
    with patch('engine.check', return_value={'errors': list(qc_errors)}), \
            patch('engine.command'), \
            patch.object(engine.Studio, 'record_video_usage'), \
            patch.object(engine.Studio, 'publish_manifest'):
        message = engine.Studio.poll(studio, 'SH001')
    return studio.state()['shots']['SH001'][-1], message


class ReqS10AutoReviewAnchorTests(unittest.TestCase):
    """REQ-S10-18：本地与云端自动验收同读 project_settings.auto_review，默认关。"""

    def test_req_s10_18_local_auto_review_reads_project_settings_only(self):
        """REQ-S10-18：打开项目设置 auto_review 后，本地下载质检通过即自动放行；不创建三虎也成立。"""
        with tempfile.TemporaryDirectory() as td:
            root = _auto_review_project(td)
            self.assertTrue(project_settings.set_auto_review(root, True))
            version, message = _local_poll(root)
            self.assertTrue(version.get('qc_pass'))
            self.assertEqual(version.get('review'), 'pass')
            self.assertEqual(version.get('review_by'), 'auto')
            self.assertEqual(version.get('review_note'), engine.AUTO_REVIEW_NOTE)
            self.assertIn('已按自动验收设置放行（未做内容审核）', message)

    def test_req_s10_18_off_or_missing_key_waits_for_human_on_both_paths(self):
        """REQ-S10-18：auto_review 关或键缺失时，本地与云端都不放行，待人工验收。"""
        with tempfile.TemporaryDirectory() as td:
            root = _auto_review_project(td)
            for label, prepare in (('missing', lambda: None),
                                   ('off', lambda: project_settings.set_auto_review(root, False))):
                with self.subTest(key=label):
                    prepare()
                    local, local_message = _local_poll(root)
                    cloud, cloud_message = _cloud_poll(root)
                    for version in (local, cloud):
                        self.assertEqual(version.get('review'), 'pending')
                        self.assertNotEqual(version.get('review_by'), 'auto')
                    self.assertIn('待您验收', local_message)
                    self.assertIn('等您验收', cloud_message)

    def test_req_s10_18_qc_errors_never_pass_on_both_paths(self):
        """REQ-S10-18：技术质检有错误时，即使 auto_review 打开，两路也都不自动放行。"""
        with tempfile.TemporaryDirectory() as td:
            root = _auto_review_project(td)
            self.assertTrue(project_settings.set_auto_review(root, True))
            local, _ = _local_poll(root, qc_errors=['时长不符'])
            cloud, _ = _cloud_poll(root, qc_errors=['时长不符'])
            for version in (local, cloud):
                self.assertFalse(version.get('qc_pass'))
                self.assertNotEqual(version.get('review'), 'pass')
                self.assertNotEqual(version.get('review_by'), 'auto')

    def test_req_s10_18_restart_keeps_sanhu_variables_off_and_both_paths_agree(self):
        """REQ-S10-18：重启后三虎变量默认 False，项目设置仍为 True，本地与云端结果一致（都放行）。"""
        class RestartedPet:
            """新进程里的三虎：没有任何自动变量被打开。"""

            def should_auto_run(self, stage_id):
                return False

        with tempfile.TemporaryDirectory() as td:
            root = _auto_review_project(td)
            self.assertTrue(project_settings.set_auto_review(root, True))
            local, _ = _local_poll(root, pet=RestartedPet())
            cloud, _ = _cloud_poll(root)
            for version in (local, cloud):
                self.assertEqual(version.get('review'), 'pass')
                self.assertEqual(version.get('review_by'), 'auto')
                self.assertEqual(version.get('review_note'), engine.AUTO_REVIEW_NOTE)

    def test_req_s10_18_shared_predicate_defaults_off(self):
        """REQ-S10-18：共用判据在报告有错、开关缺失或值不是 True 时一律为关。"""
        with tempfile.TemporaryDirectory() as td:
            root = _auto_review_project(td)
            self.assertFalse(engine.auto_review_ready(root, {'errors': []}))
            self.assertFalse(engine.auto_review_ready(root, {'errors': ['x']}))
            self.assertFalse(engine.auto_review_ready(root, None))
            project_settings.put(root, 'auto_review', 'yes')
            self.assertFalse(engine.auto_review_ready(root, {'errors': []}))
            self.assertTrue(project_settings.set_auto_review(root, True))
            self.assertTrue(engine.auto_review_ready(root, {'errors': []}))
            self.assertFalse(engine.auto_review_ready(root, {'errors': ['x']}))


class ReqS10AnchorTests(unittest.TestCase):
    def test_req_s10_03_video_depends_on_keyframe_and_previs_is_only_sg05(self):
        """REQ-S10-03：视频依赖表只列 keyframe；需要预演的业务前置由 SG-05 表达。"""
        self.assertEqual(stage_flow.DEPENDS['video'], ('keyframe',))
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-05']['from'], gates['SG-05']['to'], gates['SG-05']['check']),
                         ('previs', 'video', 'previs_ready'))

    def test_req_s10_32_skill_page_locations_use_current_stage_label(self):
        """REQ-S10-32：视频 SKILL 不再写旧阶段号，页面动作仍只登记在页面上执行。"""
        expected = pet_bus.stage_label('video')
        texts = {path.name: path.read_text(encoding='utf-8') for path in SKILL_DIR.glob('*.skill.md')}
        self.assertEqual(len(texts), 5)
        for name, text in texts.items():
            self.assertNotIn('08 视频生成', text, name)
        page_lines = [line for text in texts.values() for line in text.splitlines()
                      if 'video.' in line and '→' in line and '视频生成' in line]
        self.assertTrue(page_lines)
        for line in page_lines:
            self.assertIn(expected, line)
        for tool in ('video.batchSubmit', 'video.retry', 'video.pause', 'video.resume'):
            self.assertIn(tool, skill_tools.PAGES)
            self.assertNotIn(tool, skill_tools.READY)


if __name__ == '__main__':
    unittest.main(verbosity=2)
