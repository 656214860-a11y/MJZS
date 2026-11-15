# -*- coding: utf-8 -*-
"""第 63 期附件「全部阶段子Agent启动逻辑优化命令」的自检：并行配置 ＋ 全局并发 ＋ 门禁 ＋ 统一日志。

附件给了三条硬要求，这一份逐条盯着：
- 任务 3.1：11 个阶段的 parallel_unit／parallel_degree／serial_within／concurrency_limit／retry_policy
  都要有，且与附件末尾那张「各阶段并行配置速查表」一个字都不差；
- 任务 3.2：五条阶段间门禁都要能拦住「上游真的做了却没做全」，而空项目一律放行（第 47 期起的规矩）；
- 任务 3.3：全局并发 ≤ 8、单阶段 ≤ 表内上限、同一资源串行，每次起手／收场都记进 logs/。

运行：python test_stage_parallel.py
"""
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import stage_parallel as spec
from pet_bus import STAGES


def make_project(td, states=None):
    """一个只有阶段状态的最小项目。"""
    proj = Path(td) / 'p'
    (proj / '工作流任务' / '宠物').mkdir(parents=True)
    if states:
        (proj / '工作流任务' / '宠物' / '阶段状态.json').write_text(
            json.dumps({'stages': states}, ensure_ascii=False), encoding='utf-8')
    return proj


class SpeedTableTests(unittest.TestCase):
    """附件末尾那张速查表：阶段／并行单元／并行度／批内串行／并发上限，逐格核对。"""

    TABLE = (
        ('剧本准备', '无（整段串行）', '1', '—', 1),
        ('剧本结构', '无（整段串行）', '1', '—', 1),
        ('初步分镜', '场景', '2-3', '是', 3),
        ('分镜预演', '批次', '1-3', '是', 3),
        ('资产管理', '资产（角色／场景／道具）', '3-5', '是', 5),
        ('连贯性清单', '无（整段串行）', '1', '—', 1),
        ('分镜定稿', '无（整段串行）', '1', '—', 1),
        ('首帧管理', '镜头', '4-6', '—', 6),
        ('白模预演', '批次', '2-3', '是', 3),
        ('视频生成', '批次', '2-3', '是', 3),
        ('配音与字幕', '音轨（角色／场景）', '3-5', '是', 5),
        ('后期剪辑', '无（整段串行）', '1', '—', 1),
        ('质检与交付', '检查项', '2-4', '—', 4),
    )

    def test_the_table_matches_the_attachment(self):
        rows = [(row[0], row[1], row[2], row[3], row[4]) for row in spec.rows()]
        self.assertEqual(rows, list(self.TABLE))

    def test_every_stage_has_a_config(self):
        self.assertEqual(spec.stages(), tuple(STAGES))
        for stage in STAGES:
            row = spec.config(stage)
            for key in ('unit', 'min', 'max', 'serial', 'limit', 'retry', 'why'):
                self.assertIn(key, row, stage)

    def test_no_stage_may_exceed_the_global_cap(self):
        for stage in spec.stages():
            self.assertLessEqual(spec.concurrency_limit(stage), spec.GLOBAL_LIMIT, stage)
            self.assertTrue(spec.config(stage)['why'], stage)

    def test_a_generator_stage_is_parallel_and_a_checking_stage_is_not(self):
        for stage in ('storyboard', 'assets', 'keyframe', 'previs', 'video', 'audio', 'delivery'):
            self.assertNotEqual(spec.unit(stage), spec.NONE, stage)
        for stage in ('script', 'script_structure', 'continuity', 'final', 'edit'):
            self.assertEqual(spec.unit(stage), spec.NONE, stage)
            self.assertEqual(spec.concurrency_limit(stage), 1, stage)

    def test_the_unknown_stage_falls_back_to_serial(self):
        self.assertEqual(spec.unit('编出来的'), spec.NONE)
        self.assertEqual(spec.degree_text('编出来的'), '1')

    def test_retry_and_rate_limit_follow_the_attachment(self):
        self.assertEqual(spec.retry_attempts('script'), 2)
        self.assertEqual(spec.on_exhaust('script'), spec.ON_BLOCK)
        for stage in ('keyframe', 'previs', 'video'):
            self.assertEqual(spec.on_exhaust(stage), spec.ON_MANUAL, stage)
        self.assertTrue(spec.rate_limited('video'), '只有视频这一步要处理接口限流')
        self.assertFalse(spec.rate_limited('keyframe'))

    def test_the_text_table_covers_every_stage(self):
        text = spec.table_text()
        for row in self.TABLE:
            self.assertIn(row[0], text)


class GovernorTests(unittest.TestCase):
    """任务 3.3：全局 ≤8、单阶段 ≤ 表内上限、同一资源串行。"""

    def setUp(self):
        self.governor = spec.Governor(clock=lambda: 0.0)

    def test_the_global_cap_is_eight(self):
        got = [self.governor.acquire('keyframe') for _ in range(6)]
        self.assertTrue(all(item['ok'] for item in got))
        self.assertTrue(self.governor.acquire('assets')['ok'])
        self.assertTrue(self.governor.acquire('assets')['ok'])
        self.assertEqual(self.governor.running(), 8)
        blocked = self.governor.acquire('video')
        self.assertFalse(blocked['ok'])
        self.assertIn('全局并发已达上限 8 路', blocked['reason'])
        self.assertEqual(self.governor.running(), 8)

    def test_one_stage_cannot_go_past_its_own_limit(self):
        for _ in range(3):
            self.assertTrue(self.governor.acquire('video')['ok'])
        blocked = self.governor.acquire('video')
        self.assertFalse(blocked['ok'])
        self.assertIn('视频生成 并发已达上限 3 路', blocked['reason'])

    def test_the_same_resource_waits_its_turn(self):
        first = self.governor.acquire('keyframe', resource='SH001')
        self.assertTrue(first['ok'])
        self.assertTrue(self.governor.acquire('keyframe', resource='SH002')['ok'])
        same = self.governor.acquire('keyframe', resource='SH001')
        self.assertFalse(same['ok'])
        self.assertIn('同一资源 SH001', same['reason'])
        self.governor.release(first['ticket'])
        self.assertTrue(self.governor.acquire('keyframe', resource='SH001')['ok'])

    def test_numbers_go_back_when_a_stage_settles(self):
        tickets = [self.governor.acquire('assets')['ticket'] for _ in range(3)]
        self.assertEqual(self.governor.release(tickets[0]), True)
        self.assertEqual(self.governor.release(tickets[0]), False, '同一个号不会还两次')
        self.assertEqual(self.governor.stage_running('assets'), 2)
        self.assertEqual(self.governor.release_stage('assets'), 2)
        self.assertEqual(self.governor.running(), 0)

    def test_the_snapshot_is_read_only_numbers(self):
        self.governor.acquire('audio')
        snap = self.governor.snapshot()
        self.assertEqual((snap['limit'], snap['running'], snap['stages']), (8, 1, {'audio': 1}))
        self.assertEqual(len(snap['tickets']), 1)
        self.assertEqual(self.governor.slowed, [], '没被挡住过就不该有降速记录')

    def test_the_whole_app_shares_one_controller(self):
        """任务 4.2：全局 8 路是「所有阶段一起数」的，所以控制器只能有一份。"""
        import pet_agent
        with tempfile.TemporaryDirectory() as td:
            agent = pet_agent.Agent(project=Path(td), persist=False)
        self.assertIs(spec.shared(), spec.shared())
        self.assertIs(agent.governor, spec.shared())


class ParallelMapTests(unittest.TestCase):
    """一次把一批单元跑掉：保序、一个单元出错不连坐、在飞不超过配置。"""

    def test_implicit_and_explicit_entry_share_capacity(self):
        from unittest.mock import patch
        governor = spec.Governor(limit=1)
        entered, release = threading.Event(), threading.Event()
        first = []
        def worker(item):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test release timeout')
        thread = threading.Thread(target=lambda: first.extend(spec.parallel_map(
            'keyframe', ['held'], worker, governor=governor, wait=0)))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            called = []
            with patch.object(spec, 'shared', return_value=governor):
                second = spec.parallel_map('animatic', ['new'], called.append, wait=0)
            self.assertEqual(called, [])
            self.assertIsInstance(second[0][2], TimeoutError)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(first[0][2])
        self.assertEqual(governor.running(), 0)

    def test_timeout_never_executes_without_a_permit(self):
        for limit, held_resource, requested in ((1, 'busy', 'other'), (2, 'same', 'same')):
            with self.subTest(limit=limit):
                governor = spec.Governor(limit=limit)
                held = governor.acquire('keyframe', held_resource)['ticket']
                called = []
                rows = spec.parallel_map('keyframe', [requested], called.append,
                                         governor=governor, wait=0)
                self.assertEqual(called, [])
                self.assertIsInstance(rows[0][2], TimeoutError)
                self.assertEqual(governor.running(), 1)
                self.assertTrue(governor.release(held))

    def test_worker_failure_releases_its_permit(self):
        governor = spec.Governor(limit=1)
        def fail(item):
            raise ValueError('worker failed')
        rows = spec.parallel_map('keyframe', ['one'], fail, governor=governor, wait=0)
        self.assertIsInstance(rows[0][2], ValueError)
        self.assertEqual(governor.running(), 0)
        self.assertTrue(governor.acquire('keyframe', 'one')['ok'])

    def test_order_is_kept_and_one_bad_unit_does_not_stop_the_rest(self):
        def worker(item):
            if item == 2:
                raise ValueError('第二个坏了')
            return item * 10
        results = spec.parallel_map('keyframe', [1, 2, 3], worker)
        self.assertEqual([row[0] for row in results], [1, 2, 3])
        self.assertEqual([row[1] for row in results], [10, None, 30])
        self.assertIsInstance(results[1][2], ValueError)
        self.assertIsNone(results[0][2])

    def test_a_single_agent_stage_runs_one_unit_at_a_time(self):
        live = {'now': 0, 'most': 0}
        lock = threading.Lock()

        def worker(item):
            with lock:
                live['now'] += 1
                live['most'] = max(live['most'], live['now'])
            try:
                return item
            finally:
                with lock:
                    live['now'] -= 1
        spec.parallel_map('script', range(5), worker)
        self.assertEqual(live['most'], 1)

    def test_the_governor_caps_what_is_in_flight(self):
        governor = spec.Governor(limit=2, clock=lambda: 0.0)
        live = {'now': 0, 'most': 0}
        lock = threading.Lock()

        def worker(item):
            with lock:
                live['now'] += 1
                live['most'] = max(live['most'], live['now'])
            try:
                return item
            finally:
                with lock:
                    live['now'] -= 1
        results = spec.parallel_map('keyframe', range(8), worker, governor=governor)
        self.assertLessEqual(live['most'], 2, '全局上限是硬上限')
        self.assertEqual([row[0] for row in results], list(range(8)))
        self.assertEqual(governor.running(), 0, '跑完要把号都还掉')

    def test_the_cap_wins_over_the_degree_floor(self):
        """上限比「并行度下限」还小时，上限说了算（视频生成下限 2 路，全局只剩 1 路就跑 1 路）。"""
        governor = spec.Governor(limit=1, clock=lambda: 0.0)
        live = {'now': 0, 'most': 0}
        lock = threading.Lock()

        def worker(item):
            with lock:
                live['now'] += 1
                live['most'] = max(live['most'], live['now'])
            try:
                return item
            finally:
                with lock:
                    live['now'] -= 1
        spec.parallel_map('video', range(4), worker, governor=governor)
        self.assertEqual(live['most'], 1)
        self.assertEqual(governor.running(), 0)


class SkillLayerTests(unittest.TestCase):
    """任务 4.2：SKILL 的同层并行也走三虎那份全局控制器，不再自己无条件开线程。"""

    def orch(self, execute, limit=2):
        import skill_orchestrator

        class Stub(skill_orchestrator.Orchestrator):
            pass
        Stub.execute = execute
        return Stub(errors=[], governor=spec.Governor(limit=limit, clock=lambda: 0.0))

    def test_the_layer_rides_the_governor(self):
        live = {'now': 0, 'most': 0}
        lock = threading.Lock()

        def execute(self, sid, context):
            with lock:
                live['now'] += 1
                live['most'] = max(live['most'], live['now'])
            try:
                return {'skill': sid, 'status': 'done'}
            finally:
                with lock:
                    live['now'] -= 1
        orch = self.orch(execute, limit=1)
        rows = orch._run_parallel(['firstframe-batch', 'firstframe-retry', 'firstframe-quality'],
                                  {'stage': 'video'})
        self.assertEqual([row['skill'] for row in rows],
                         ['firstframe-batch', 'firstframe-retry', 'firstframe-quality'])
        self.assertEqual(live['most'], 1, '全局只剩 1 路时，同层也一次只跑一个')
        self.assertEqual(orch.governor.running(), 0, '跑完要把号还掉')

    def test_a_broken_unit_becomes_a_failed_row(self):
        def execute(self, sid, context):
            if sid == 'bad':
                raise ValueError('工具没实现')
            return {'skill': sid, 'status': 'done'}
        orch = self.orch(execute, limit=2)
        rows = orch._run_parallel(['good', 'bad'], {'stage': 'video'})
        self.assertEqual([row['status'] for row in rows], ['done', 'failed'])
        self.assertEqual(orch.errors, [('bad', '工具没实现')])
        self.assertEqual(orch.governor.running(), 0)


class LogTests(unittest.TestCase):
    """任务 5.3：一条日志五个键固定，按阶段落到项目根 logs/。"""

    def test_the_row_has_exactly_the_five_fields(self):
        row = spec.log_row('assets', 'submit', 'start', '3 项', at=0)
        for key in spec.LOG_FIELDS:
            self.assertIn(key, row)
        self.assertEqual(row['stage'], 'assets')
        self.assertEqual(row['status'], 'start')

    def test_it_lands_in_the_stage_folder_and_reads_back(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            path = spec.log_write(proj, 'video', 'dispatch', 'start', '批次 B01', at=0)
            self.assertEqual(path.name, 'video.agent_logs.jsonl')
            self.assertEqual(path.parent, proj / 'logs')
            rows = spec.log_read(proj, 'video')
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]['stage'], rows[0]['task'], rows[0]['status']), ('video', 'dispatch', 'start'))
            self.assertIn('批次 B01', spec.log_line(rows[0]))

    def test_a_missing_project_is_not_an_error(self):
        self.assertIsNone(spec.log_write(None, 'video', 'dispatch', 'start'))
        self.assertEqual(spec.log_read(None, 'video'), ())
        self.assertEqual(spec.log_read(Path('不存在的目录'), 'video'), ())


class GateTests(unittest.TestCase):
    """任务 3.2：五条门禁。只拦「上游真的做了却没做全」的，空项目一律放行。"""

    def test_the_five_gates_are_the_ones_the_attachment_asks_for(self):
        self.assertEqual(spec.gate_ids(), ('SG-A', 'SG-B', 'SG-01', 'SG-02', 'SG-03', 'SG-04', 'SG-05'))
        pairs = [(row['from'], row['to']) for row in spec.GATES]
        self.assertEqual(pairs, [('storyboard', 'animatic'), ('animatic', 'assets'), ('assets', 'continuity'), ('continuity', 'final'), ('final', 'keyframe'),
                                 ('keyframe', 'previs'), ('previs', 'video')])
        self.assertIsNone(spec.gate_for('script'), '剧本准备没有上游门禁')

    def test_an_empty_project_walks_through_every_gate(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            for stage in STAGES:
                result = spec.evaluate(proj, stage)
                if stage in ('animatic', 'assets'):
                    self.assertFalse(result['ok'], stage)
                    self.assertTrue(result['started'], stage)
                    continue
                self.assertTrue(result['ok'], stage)
                self.assertFalse(result['started'], stage)
            self.assertEqual(spec.blocked_stages(proj, 'continuity'), ())

    def test_assets_that_stopped_halfway_block_the_continuity_step(self):
        from ui_edges_support import make_minimal_project
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            store = proj / 'episode' / 'assets' / '资产清单'
            store.mkdir(parents=True, exist_ok=True)
            (store / 'assets.json').write_text(json.dumps(
                {'CHAR_001': {'name': '主角', 'character_anchor': '短发'}, 'PROP_009': {'name': '外卖袋'}},
                ensure_ascii=False), encoding='utf-8')
            result = spec.evaluate(proj, 'continuity')
            self.assertFalse(result['ok'])
            self.assertIn('2 项资产还没导入图片', ' '.join(result['problems']))
            text = spec.blocked_text(result)
            self.assertIn('资产管理', text)
            self.assertIn('先到 05 资产管理', text)

    def test_a_stage_that_never_started_is_not_a_blocker(self):
        from ui_edges_support import make_minimal_project
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            store = proj / 'episode' / 'assets' / '资产清单'
            store.mkdir(parents=True, exist_ok=True)
            (store / 'assets.json').write_text(json.dumps(
                {'CHAR_001': {'name': '主角'}}, ensure_ascii=False), encoding='utf-8')
            self.assertTrue(spec.evaluate(proj, 'continuity')['ok'])
            self.assertEqual(spec.blocked_stages(proj, 'continuity'), ())

    def test_missing_first_frames_block_the_previs_step_once_keyframe_has_run(self):
        from ui_edges_support import make_adopted_project
        with tempfile.TemporaryDirectory() as td:
            proj = make_adopted_project(td)
            self.assertTrue(spec.evaluate(proj, 'previs')['ok'], '首帧这一步压根没开始时不许拦')
            states = {'keyframe': {'state': 'success'}}
            (proj / '工作流任务' / '宠物').mkdir(parents=True, exist_ok=True)
            (proj / '工作流任务' / '宠物' / '阶段状态.json').write_text(
                json.dumps({'stages': states}, ensure_ascii=False), encoding='utf-8')
            result = spec.evaluate(proj, 'previs')
            self.assertFalse(result['ok'])
            self.assertIn('缺首帧', result['detail'])
            self.assertEqual(spec.blocked_stages(proj, 'previs'), ('keyframe',))

    def test_frame_completeness_does_not_reuse_generation_candidates(self):
        from unittest.mock import patch
        from keyframe_comfy import pending_shots
        from stage_completion_service import completion_evidence
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / 'media'
            base.mkdir()
            source = root / 'adopted.json'
            (base / 'good.png').write_bytes(b'image')
            (base / 'empty.png').touch()
            (root / 'outside.png').write_bytes(b'outside')
            cases = (
                ({'id': 'missing-field'}, '未配置'),
                ({'id': 'deleted', 'frame': 'good.png', 'frame_deleted': True}, '已删除'),
                ({'id': 'outside', 'frame': '../outside.png'}, '越界'),
                ({'id': 'missing', 'frame': 'missing.png'}, '缺首帧'),
                ({'id': 'empty', 'frame': 'empty.png'}, '空文件'),
                ({'id': 'directory', 'frame': '.'}, '缺首帧'),
                ({'id': 'invalid', 'frame': ['good.png']}, '未配置'),
            )
            for shot, reason in cases:
                with self.subTest(shot=shot['id']), \
                        patch.object(spec, '_adopted', return_value=[(source, [shot])]), \
                        patch.object(spec, 'has_run', return_value=True), \
                        patch('contract.storyboard_paths.media_root', return_value=base):
                    result = spec.frames_ready(root)
                    self.assertFalse(result['ok'])
                    self.assertTrue(result['started'])
                    self.assertIn(reason, ' '.join(result['problems']))
                    self.assertFalse(completion_evidence(root, 'keyframe')[0])
            # 删除、越界、未配置仍不进入自动生成队列。
            self.assertEqual(pending_shots([c[0] for c in cases[:3]], base), [])

    def test_frame_completion_requires_nonempty_shots_and_keeps_unstarted_navigation(self):
        from unittest.mock import patch
        from stage_completion_service import completion_evidence
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for shots in ([], [{'id': 'unconfigured'}], [{'id': 'missing', 'frame': 'gone.png'}]):
                with self.subTest(shots=shots), \
                        patch.object(spec, '_adopted', return_value=[(root / 'adopted.json', shots)]), \
                        patch.object(spec, 'has_run', return_value=False), \
                        patch('contract.storyboard_paths.media_root', return_value=root):
                    result = spec.frames_ready(root)
                    self.assertTrue(result['ok'])
                    self.assertFalse(result['started'])
                    self.assertNotIn('首帧都在', result['detail'])
                    self.assertFalse(completion_evidence(root, 'keyframe')[0])

    def test_frame_completion_checks_all_episodes_and_preserves_files(self):
        from unittest.mock import patch
        from tests.image_fixtures import png
        from keyframe_evidence import make_evidence
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root / 'good.png'
            raw = png()
            good.write_bytes(raw)
            first = (root / 'ep1.json', [{'id': 'S001', 'frame': 'good.png'}])
            episode = {'shots': first[1]}
            first[1][0]['frame_evidence'] = make_evidence(first[0], episode, first[1][0], good)
            save(first[0], episode)
            second = (root / 'ep2.json', [{'id': 'S001'}])
            with patch.object(spec, '_adopted', return_value=[first, second]), \
                    patch.object(spec, 'has_run', return_value=False), \
                    patch('contract.storyboard_paths.media_root', return_value=root):
                self.assertFalse(spec.frames_ready(root)['ok'])
            with patch.object(spec, '_adopted', return_value=[first]), \
                    patch('contract.storyboard_paths.media_root', return_value=root):
                result = spec.frames_ready(root)
                self.assertTrue(result['ok'])
                self.assertTrue(result['started'])
            self.assertEqual(good.read_bytes(), raw)

    def test_the_audit_lists_all_five_gates(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            text = spec.audit_text(proj)
            for gate in spec.gate_ids():
                self.assertIn(gate, text)
            self.assertEqual(len(spec.audit(proj)), 7)
            keyframe = spec.page_lines(proj, 'keyframe')
            self.assertIn('并行：镜头 4-6 路', keyframe[0])
            self.assertIn('门禁：SG-03', keyframe[1])          # 进首帧管理前先看批次划分
            self.assertIn('门禁：SG-04', spec.page_lines(proj, 'previs')[1])   # 进白模预演前先看首帧


class BriefTests(unittest.TestCase):
    """任务 2.1～2.11 的「应有逻辑」要真的写进任务书。"""

    def test_single_agent_stages_say_so(self):
        text = spec.brief_text('script')
        self.assertIn('只有 1 个执行者', text)
        self.assertIn('不要开并行子任务', text)

    def test_the_storyboard_book_carries_its_own_constraints(self):
        text = spec.brief_text('storyboard')
        self.assertIn('场景', text)
        self.assertIn('同一集只输出一份分镜 JSON', text)
        self.assertIn('三元组', text)

    def test_the_asset_book_keeps_the_inside_order(self):
        text = spec.brief_text('assets')
        self.assertIn('正典板（转盘图）→ 状态变体 → 锚点字符串 → 参考职责声明', text)
        self.assertIn('手上不持道具', text)

    def test_the_video_book_bans_static_description(self):
        text = spec.brief_text('video')
        self.assertIn('只写动作、镜头运动与物理交互', text)
        self.assertIn('不写长相、服装、场景描述', text)
        self.assertIn('限流', text)

    def test_the_previs_book_keeps_the_batch_serial(self):
        self.assertIn('同批次内的镜头禁止并行', spec.brief_text('previs'))

    def test_the_audio_book_keeps_one_voice(self):
        self.assertIn('同一个音色 ID', spec.brief_text('audio'))

    def test_the_delivery_book_lists_three_checks(self):
        text = spec.brief_text('delivery')
        self.assertIn('画面、音频、格式', text)
        self.assertIn('汇总', text)

    def test_the_block_form_has_a_header(self):
        block = spec.brief_block('keyframe')
        self.assertTrue(block.startswith('\n【本步怎么并行（照这个来）】'))
        self.assertIn('逐字读取 character_anchor', block)

    def test_the_pseudocode_shows_the_orchestrator_loop(self):
        text = spec.pseudocode()
        self.assertIn('CONFIG[stage]', text)
        self.assertIn('governor.acquire', text)


class AgentWiringTests(unittest.TestCase):
    """任务 3.1／3.3 落到父编排器上：配置、发号、日志、门禁。"""

    def setUp(self):
        import pet_agent
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.agent = pet_agent.Agent(project=self.project, persist=False)

    def test_the_orchestrator_reads_the_same_table(self):
        self.assertEqual(self.agent.parallel_plan('keyframe'), spec.config('keyframe'))

    def test_the_retry_ceiling_follows_the_stage(self):
        self.assertEqual(self.agent.retry_limit('keyframe'), min(self.agent.settings['max_attempts'], 2))

    def test_a_finished_stage_hands_its_numbers_back(self):
        ticket = self.agent.acquire('video', resource='B01')['ticket']
        self.assertEqual(self.agent.parallel_snapshot()['running'], 1)
        self.agent.release_stage('video')
        self.assertEqual(self.agent.parallel_snapshot()['running'], 0)
        self.assertFalse(self.agent.release(ticket))

    def test_the_stage_log_lands_in_the_project(self):
        path = self.agent.log_stage('assets', 'submit', 'start', '3 项', at=0)
        self.assertTrue(Path(path).is_file())
        self.assertEqual(self.agent.agent_logs[-1]['stage'], 'assets')

    def test_the_gate_answers_in_plain_words(self):
        self.assertEqual(self.agent.blocked_reason('continuity'), '')
        self.assertTrue(self.agent.gate('continuity')['ok'])


class FlowWiringTests(unittest.TestCase):
    """stage_flow：门禁进 blockers；自动推进遇门禁停住；弹窗多一句并行说明。"""

    def test_the_gate_joins_the_blocker_list(self):
        import stage_flow
        from ui_edges_support import make_minimal_project
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            store = proj / 'episode' / 'assets' / '资产清单'
            store.mkdir(parents=True, exist_ok=True)
            (store / 'assets.json').write_text(json.dumps({'CHAR_001': {'name': '主角'}}), encoding='utf-8')
            (proj / '工作流任务' / '宠物').mkdir(parents=True, exist_ok=True)
            (proj / '工作流任务' / '宠物' / '阶段状态.json').write_text(
                json.dumps({'stages': {'assets': {'state': 'success'}}}), encoding='utf-8')
            self.assertEqual(stage_flow.blockers(proj, 'continuity'), ['assets'])

    def test_the_chain_stops_at_a_blocked_stage_and_waits(self):
        import stage_flow
        auto = stage_flow.Auto(gate=lambda stage: '上游没做全' if stage == 'assets' else '')
        auto.script_done('semi')
        self.assertEqual(auto.next_stage(), 'script')
        auto.done('script')
        self.assertEqual(auto.next_stage(), 'script_structure')
        auto.done('script_structure')
        self.assertEqual(auto.next_stage(), 'storyboard')
        auto.done('storyboard')
        self.assertEqual(auto.next_stage(), 'animatic')
        auto.done('animatic')
        self.assertIsNone(auto.next_stage(), '被门禁挡住就不往下推')
        self.assertEqual(auto.blocked[0], 'assets')
        self.assertEqual(auto.state()['blocked'], 'assets')
        self.assertEqual(auto.next_stage(), None, '还是停在这一步，不退也不跳')
        auto.done('assets')
        self.assertEqual(auto.next_stage(), 'continuity', '上游补好了就接着走')

    def test_the_popup_line_says_how_parallel_it_is(self):
        import stage_flow
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / 'p'
            (proj / '工作流任务' / '宠物').mkdir(parents=True)
            subject = type('Stub', (), {})()
            subject.root, subject.app = proj, HERE
            lines = stage_flow.summary_lines(subject, 'storyboard')
            self.assertLessEqual(len(lines), 4)
            self.assertTrue(lines[1].startswith('SKILL：'), lines)
            self.assertIn('并行：场景 2-3 路', lines[1])
            data = stage_flow.step_summary(subject, 'storyboard', proj)
            self.assertEqual(data['parallel'], '场景 2-3 路')


class PetUiWiringTests(unittest.TestCase):
    """pet_ui：门禁那一句与并发现状都从父 Agent 转出来。"""

    def pet(self):
        import pet_ui
        class Stub(pet_ui.Pet):
            agent = None
        pet = object.__new__(Stub)
        pet.errors = []
        return pet

    def test_the_gate_sentence_comes_from_the_agent(self):
        pet = self.pet()
        pet.agent = type('A', (), {'blocked_reason': lambda self, stage, **kw: '资产没锁完'})()
        self.assertEqual(pet.gate_reason('continuity'), '资产没锁完')

    def test_a_broken_agent_never_takes_the_page_down(self):
        pet = self.pet()

        def boom(stage, **kw):
            raise RuntimeError('读不出来')
        pet.agent = type('A', (), {'blocked_reason': boom, 'parallel_snapshot': boom})()
        self.assertEqual(pet.gate_reason('continuity'), '')
        self.assertEqual(pet.parallel_snapshot()['running'], 0)
        self.assertEqual([name for name, _ in pet.errors][:1], ['gate'])


class ShotFrameProblemTests(unittest.TestCase):
    def test_unreadable_frame_keeps_found_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            (base / 'ok.png').write_bytes(b'x')

            def boom(*a, **k):
                raise OSError('读不出')
            self.assertEqual(spec._shot_frame_problem('src', {}, {'id': 'S1', 'frame': 'ok.png'}, base, '9:16', boom),
                             ('S1 的首帧路径无法读取', True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
