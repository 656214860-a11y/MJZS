"""REQ-S10-11/13/16/20/23/33：视频生成阶段的服务商表与密钥、逐次调用台账、生成期锁定、版本目录、采用口径与提示词规则。

这些编号原登记在 `维护记录/需求锚定基线.json` 的 `untested_done`，本轮补上落在真实代码行为上的锚点。
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud_video_service
import engine
import stage_parallel
from contract import storyboard_contract
import video_task_state
from pet_llm import RequestLedger
from contract.project_context import ProjectContext


def _shot(index, **extra):
    return {'id': 'S%03d' % index, 'duration': 5, 'video_prompt': '推镜', 'frame': 'f.png', **extra}


def _studio(folder, count=2, **extra):
    root = Path(folder)
    (root / 'episode.json').write_text(
        json.dumps({'shots': [_shot(i + 1, **extra) for i in range(count)]}), encoding='utf-8')
    (root / 'config.json').write_text(
        json.dumps({'reserve_seconds': 0, 'budget_seconds': 0}), encoding='utf-8')
    return engine.Studio(root, factory=lambda *a, **k: None, episode_file='episode.json')


class VideoGenerationRequirementAnchorTests(unittest.TestCase):
    def test_req_s10_11_cloud_provider_table_lists_wan_seedance_and_custom(self):
        """REQ-S10-11：云端服务商为阿里云百炼万相、火山引擎 Seedance，另可填兼容自定义地址。"""
        providers = cloud_video_service.PROVIDERS
        self.assertEqual(set(providers), {'阿里云百炼 · 万相', '火山引擎 · Seedance',
                                          '自定义 · 万相兼容', '自定义 · Seedance兼容'})
        wan = providers['阿里云百炼 · 万相']
        seedance = providers['火山引擎 · Seedance']
        self.assertEqual(wan[:3], ('wan', 'https://dashscope.aliyuncs.com/api/v1', 'wan2.6-i2v-flash'))
        self.assertEqual(seedance[0], 'volcengine')
        self.assertTrue(seedance[1].startswith('https://'))
        # 密钥走环境变量名（只存模型池 DPAPI，不写会话文件）
        self.assertEqual(wan[3], 'DASHSCOPE_API_KEY')
        self.assertEqual(seedance[3], 'ARK_API_KEY')
        # 自定义地址的 base 留空，可填兼容地址
        self.assertEqual(providers['自定义 · 万相兼容'][1], '')
        self.assertEqual(providers['自定义 · Seedance兼容'][1], '')

    def test_req_s10_11_session_folder_is_per_provider_model_and_date(self):
        """REQ-S10-11：每个服务商＋模型一个会话目录 cloud_video/<服务商_模型_日期>。"""
        with tempfile.TemporaryDirectory() as td:
            ctx = ProjectContext.snapshot(td, lambda stage: Path(td))
            result = cloud_video_service.session_folder(
                ctx, 'wan', 'https://dashscope.aliyuncs.com/api/v1', 'wan2.6-i2v-flash', 'episode.json')
            self.assertTrue(result.ok)
            folder = Path(result.data)
            self.assertTrue(folder.is_relative_to(Path(td) / 'cloud_video'))
            self.assertTrue(folder.name.startswith('阿里云_wan2-6-i2v-flash_'))

    def test_req_s10_11_session_key_reads_model_pool_first(self):
        """REQ-S10-11：API Key 只存模型池 DPAPI，读取时优先模型池、不写会话文件。"""
        with tempfile.TemporaryDirectory() as td:
            ctx = ProjectContext.snapshot(td, lambda stage: Path(td))
            with patch('model_pool.named_key', return_value='pool-key-123'):
                self.assertEqual(
                    cloud_video_service.saved_provider_key(ctx, 'wan', cloud_video_service.PROVIDERS),
                    'pool-key-123')

    def test_req_s10_13_authorize_then_settle_records_one_call(self):
        """REQ-S10-13：云端提交前 authorize_units 授权，终态 settle_units 结算，成功后记一笔。"""
        ledger = RequestLedger()  # 内存台账（project=None），不落盘
        ledger.authorize_units('video:abc', 'wan-model', 'video', 'videos', {'seconds': 5}, amount=1)
        entry = ledger._find('video:abc')
        self.assertEqual((entry['state'], entry['kind'], entry['amount']), ('reserved', 'videos', 1))
        ledger.settle_units('video:abc', amount=1)
        self.assertEqual((entry['state'], entry['money_state']), ('settled', 'estimated'))

    def test_req_s10_13_failure_settle_keeps_reservation(self):
        """REQ-S10-13：结算失败保守保留预算占用（标未知，不释放、不记 0）。"""
        ledger = RequestLedger()
        ledger.authorize_units('video:xyz', 'wan-model', 'video', 'videos', {'seconds': 5}, amount=1)
        ledger.settle_units('video:xyz')  # amount=None → 未知
        entry = ledger._find('video:xyz')
        self.assertEqual(entry['state'], 'unknown')
        self.assertEqual(entry['money_state'], 'unknown')

    def test_req_s10_13_download_records_count_and_estimated_seconds(self):
        """REQ-S10-13：视频成功落盘后记一条数＋秒数（估算）请求台账。"""
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            studio.record_video_usage('S001', {'version': 1})
            ledger = RequestLedger(studio.root)
            ledger.load()
            kinds = {e['kind']: e for e in ledger.entries}
            self.assertIn('videos', kinds)
            self.assertIn('seconds', kinds)
            self.assertEqual(kinds['videos']['amount'], 1)
            self.assertEqual(kinds['seconds']['amount'], 5.0)
            self.assertEqual(kinds['seconds']['mode'], 'estimated')

    def test_req_s10_13_cloud_settled_version_not_recorded_twice(self):
        """REQ-S10-13：已按云端结算的版本（有 money_request_id）不再重复记费。"""
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            studio.record_video_usage('S001', {'version': 1, 'money_request_id': 'video:x'})
            ledger = RequestLedger(studio.root)
            ledger.load()
            self.assertEqual(ledger.entries, [])

    def test_req_s10_16_prompt_locked_while_submitting_or_active(self):
        """REQ-S10-16：镜头正在生成或等待结果时不可修改提示词、资产或调用 MCP。"""
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)

            class App:
                submitting_sid = None
                local_submit_sid = None
                studio = None

            submitting = App()
            submitting.studio = studio
            submitting.submitting_sid = 'S001'
            self.assertTrue(video_task_state.prompt_locked(submitting, 'S001'))
            self.assertFalse(video_task_state.prompt_locked(submitting, 'S002'))

            local = App()
            local.studio = studio
            local.local_submit_sid = 'S002'
            self.assertTrue(video_task_state.prompt_locked(local, 'S002'))

    def test_req_s10_16_active_version_locks_the_shot(self):
        """REQ-S10-16：本镜头有结果不确定的活动任务时 generation_active 判定生成中。"""
        from agent.core import save
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            state = studio.state()
            state['shots']['S001'].append({'version': 1, 'state': 'running'})
            save(studio.db, state)
            self.assertTrue(video_task_state.generation_active(studio, 'S001'))
            self.assertFalse(video_task_state.generation_active(studio, 'S002'))

    def test_req_s10_16_assert_prompt_editable_blocks_locked_shot(self):
        """REQ-S10-16：生成中镜头调用 assert_prompt_editable 直接报错拦截。"""
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)

            class App:
                def __init__(self):
                    self.submitting_sid = None
                    self.local_submit_sid = None
                    self.studio = studio
                    self._sid = ''

                def sid(self):
                    return self._sid

            locked = App()
            locked._sid = 'S002'
            locked.local_submit_sid = 'S002'
            with self.assertRaisesRegex(ValueError, '正在生成或等待结果'):
                video_task_state.assert_prompt_editable(locked)

            free = App()
            free._sid = 'S003'
            video_task_state.assert_prompt_editable(free)  # 不抛

    def test_req_s10_20_local_version_folder_is_data_shot_vNNN(self):
        """REQ-S10-20：每次提交一个版本目录 data/<镜头>/vNNN/。"""
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            self.assertEqual(studio.task_folder('S001', {'version': 3}),
                             studio.root / 'data' / 'S001' / 'v003')

    def test_req_s10_20_download_publishes_qc_and_mp4_into_version_folder(self):
        """REQ-S10-20：版本目录含 qc.json 与 <镜头>.mp4，版本记录 file/sha256。"""
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            state = studio.state()
            version = {'version': 1, 'state': 'running', 'created': 0}
            state['shots']['S001'].append(version)
            dest = studio.root / 'data' / 'S001' / 'v001' / 'S001.mp4'
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b'video')
            with patch.object(engine.Studio, 'record_video_usage'):
                studio.publish_downloaded_video(state, 'S001', version, dest, {'errors': []})
            self.assertTrue((dest.parent / 'qc.json').is_file())
            self.assertEqual(version['state'], 'downloaded')
            self.assertEqual(version['file'], os.path.relpath(dest, studio.root))
            self.assertEqual(len(version['sha256']), 64)

    def test_req_s10_23_pinned_then_latest_approved_is_the_single_rule(self):
        """REQ-S10-23：进入成片只认锁定版优先，否则取最后一个已验收版。"""
        digest = 'a' * 64
        first = {'version': 1, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass',
                 'pinned': True, 'file': 'a.mp4', 'sha256': digest}
        second = {'version': 2, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass',
                  'file': 'b.mp4', 'sha256': digest}
        self.assertIs(engine.adopted_edit_version([first, second])[0], first)
        self.assertIs(engine.adopted_edit_version([{**first, 'pinned': False}, second])[0], second)

    def test_req_s10_23_missing_or_replaced_file_never_enters_edit(self):
        """REQ-S10-23：文件缺失、被替换时该镜判不可用，不进剪辑。"""
        from agent.core import save
        versions = [{'version': 1, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass',
                     'file': 'x.mp4', 'sha256': 'a' * 64}]
        with tempfile.TemporaryDirectory() as td:
            adopted, reason = engine.adopted_edit_version(versions, td)
            self.assertIsNone(adopted)
            self.assertEqual(reason, engine.ADOPT_MISSING)
        with tempfile.TemporaryDirectory() as td:
            Path(td, 'x.mp4').write_bytes(b'data')
            adopted, reason = engine.adopted_edit_version(versions, td)
            self.assertIsNone(adopted)
            self.assertEqual(reason, engine.ADOPT_REPLACED)
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            state = studio.state()
            state['shots']['S001'].append({'version': 1, 'state': 'downloaded', 'qc_pass': True,
                                           'review': 'pass', 'file': 'missing.mp4', 'sha256': 'a' * 64})
            save(studio.db, state)
            with self.assertRaisesRegex(ValueError, '视频文件缺失'):
                studio.assemble(['S001'])

    def test_req_s10_33_video_prompt_is_action_and_camera_only(self):
        """REQ-S10-33：视频提示词只写动作与运镜，不重复场景、人物和风格。"""
        from contract.prompt_templates import contract_lines
        first = contract_lines()[0]
        self.assertIn('视频提示词只写动作', first)
        self.assertIn('不重复长相和服装', first)
        self.assertIn('视频提示词只写动作', storyboard_contract.prompt_lines())
        hints = stage_parallel.brief_lines('video')
        self.assertTrue(any('视频提示词只写动作' in line and '不写长相、服装、场景描述' in line
                            for line in hints))


if __name__ == '__main__':
    unittest.main()
