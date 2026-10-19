# -*- coding: utf-8 -*-
"""REQ-S09 测试锚定：白模预演里标 ✅ 却无测试锚点的需求。

覆盖 REQ-S09-11/13/14/20/21/22/23/25/32/34/42。其中 11、13、23、32 的既有测试已在本轮
补上 ``REQ-S09`` docstring（见 ``test_previs``、``test_previs_monitor``、
``test_white_model_identity``）；本文件补的是原有测试没有真正走到的行为：

- 分流：只把复杂镜头交给 Agent，简单／中等／已就绪只跳过，并留下 ``分流结果.json``；
- 自动制作前置：忙碌互斥、Claude Desktop 拦截、Blender 缺失拦截、派发前冻结快照与配置；
- 逐镜校验：文件存在且非空、含视频流、时长误差 ≤0.5 秒；失败指向制作报告；
- 停止：本机等待被停止记「待核对」，未做的镜头记「已停止」，强制停止只结束本项目进程；
- 进度：无效帧数回退「Agent 制作中」，监视页每 5 秒刷新，手动派发开浏览器、无人值守不弹；
- 备注与入口：备注合并写入记录，页面能交给 Codex／Claude 并提供线上工具入口；
- 完成：阶段完成必须同时满足 SG-05 的 ``ok`` 与 ``started``，``previs.json`` 本身不算证据；
- 任务书：只做简化白模与低分辨率预览，不制作 4K 精片、不使用付费 API、不移动 Blender。

所有断言针对真实函数与常量；需要落盘时一律在 ``tempfile.TemporaryDirectory()`` 内进行，
不打开真实用户项目，也不依赖本机 Blender／ffprobe。
"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import platform_tools
import previs_automation
import previs_batch_service
import previs_monitor
import previs_routing
import stage_completion_service as completion
import stage_execution_service
import white_model
import white_model_service as wm
import workflow_engines
import workflow_settings
from agent.core import save
from platform_tools import ExecutionStopped
from project_context import ProjectContext


def _context(root):
    return ProjectContext.snapshot(Path(root), lambda stage: Path(root), {}, None)


def _episode(root, shots, episode_id='EP001', name='episode.json'):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'episode_id': episode_id, 'title': episode_id, 'shots': shots},
                               ensure_ascii=False), encoding='utf-8')
    return path


def _shot(sid, action='他追逐并抢夺道具', camera='跟拍', duration=5):
    return {'id': sid, 'action': action, 'camera': camera, 'duration': duration}


def _publish(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def _config(engine='codex'):
    return {'engine': engine, 'model': 'm', 'program': '', 'skill': ''}


class _Watched(dict):
    """记下写进 summary 的每一句话：收尾时 summary 会被覆盖。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.summaries = []

    def __setitem__(self, key, value):
        if key == 'summary':
            self.summaries.append(str(value))
        super().__setitem__(key, value)


class _WorkspaceCase(unittest.TestCase):
    """把白模成果目录与全部缓存都隔离到临时目录。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / 'p'
        self.root.mkdir(parents=True)
        self.space = base / 'space'
        for cache in (wm._BASE_CACHE, wm._DIR_CACHE, wm._WORKSPACE_CACHE):
            cache.clear()
            self.addCleanup(cache.clear)
        patcher = patch.object(wm, 'workspace', lambda: self.space)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch(self, obj, name, value):
        patcher = patch.object(obj, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def wait(self, state, timeout=20):
        deadline = time.monotonic() + timeout
        while state.get('busy') and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(state.get('busy'), '白模批次没有在时限内收尾')

    def start_env(self, *, verify=None, run=None, monitor=None, engine='codex', blender=True):
        """替掉所有会碰真实后台／真实 Blender 的协作者，只留下 start 的编排逻辑。"""
        self.patch(previs_routing, 'ready', lambda context, sid, source=None: False)
        self.patch(workflow_settings, 'current', lambda project, stage: _config(engine))
        self.patch(workflow_settings, 'find_program', lambda config: 'codex.exe')
        self.patch(wm, 'find_blender',
                   lambda refresh=False: Path('D:/Blender/blender.exe') if blender else None)
        self.patch(previs_batch_service, 'prepare_batch', lambda *args, **kwargs: '测试提示词')
        self.runs = []
        self.patch(workflow_engines, 'run_background',
                   run or (lambda *args, **kwargs: self.runs.append(args)))
        self.patch(previs_automation, 'verify', verify or (lambda *args, **kwargs: False))
        if monitor is not None:
            self.patch(previs_monitor, 'start', monitor)


class RoutingDispatchAnchorTests(_WorkspaceCase):
    def test_req_s09_14_dispatch_sends_only_complex_shots_and_records_every_routing(self):
        shots = [
            _shot('SH001', action='他站在原地说话', camera='固定'),
            _shot('SH002', action='他走到桌边坐下', camera='固定'),
            _shot('SH003'),
            _shot('SH004'),
        ]
        source = _episode(self.root, shots)
        self.patch(previs_routing, 'ready',
                   lambda context, sid, source=None: sid == 'SH004')
        state = {'busy': False, 'status': {}, 'progress': {}}
        started, published = [], []
        groups = previs_routing.dispatch(
            _context(self.root), source, [shot['id'] for shot in shots], state,
            start_complex=lambda *args, **kwargs: started.append((args, kwargs)),
            publish=lambda path, data: (published.append((path, data)), _publish(path, data))[1])

        self.assertEqual(groups, {'simple': ['SH001'], 'medium': ['SH002'],
                                  'complex': ['SH003']})
        self.assertEqual(started[0][0][2], ['SH003'], '只把复杂镜头交给 Agent')
        self.assertEqual(state['status'][str(self.root) + '|SH001'], '无需白模，已跳过')
        self.assertEqual(state['status'][str(self.root) + '|SH002'], '待线上制作／导入')
        self.assertNotIn(str(self.root) + '|SH003', state['status'], '复杂镜头不写跳过状态')
        self.assertIn('已就绪 1 镜跳过', state['summary'])

        path, data = published[0]
        self.assertEqual(path.name, '分流结果.json')
        self.assertIn('工作流任务', path.parts)
        self.assertIn('白模分流记录', path.parts)
        self.assertEqual(data['ready_skipped'], ['SH004'], '已就绪的镜头同样跳过')
        self.assertEqual(data['groups']['complex'], ['SH003'])
        self.assertEqual(set(data['decisions']), {'SH001', 'SH002', 'SH003', 'SH004'})

    def test_req_s09_14_dispatch_refuses_while_another_batch_is_busy(self):
        source = _episode(self.root, [_shot('SH001')])
        with self.assertRaisesRegex(ValueError, '已有白模任务运行中'):
            previs_routing.dispatch(_context(self.root), source, ['SH001'],
                                    {'busy': True}, publish=_publish)


class StartPreconditionAnchorTests(_WorkspaceCase):
    def test_req_s09_20_a_second_batch_is_refused_while_one_is_running(self):
        source = _episode(self.root, [_shot('SH001')])
        with self.assertRaisesRegex(ValueError, '已有白模任务进行中'):
            previs_automation.start(self.root, source, ['SH001'], {'busy': True})

    def test_req_s09_20_claude_desktop_and_missing_blender_are_blocked_before_dispatch(self):
        source = _episode(self.root, [_shot('SH001')])
        self.start_env(engine='claude-desktop-app')
        with self.assertRaisesRegex(ValueError, '后台模型'):
            previs_automation.start(self.root, source, ['SH001'], {'status': {}, 'progress': {}})

        self.patch(workflow_settings, 'current', lambda project, stage: _config('codex'))
        self.patch(wm, 'find_blender', lambda refresh=False: None)
        with self.assertRaisesRegex(ValueError, '未找到本地 Blender'):
            previs_automation.start(self.root, source, ['SH001'], {'status': {}, 'progress': {}})

    def test_req_s09_20_snapshot_and_config_are_frozen_before_the_worker_runs(self):
        source = _episode(self.root, [_shot('SH001'), _shot('SH002')])
        self.start_env()
        state = {'status': {}, 'progress': {}}
        previs_automation.start(self.root, source, ['SH001', 'SH002'], state)
        self.wait(state)

        batch = Path(state['log_dir'])
        snapshot = json.loads((batch / '分镜快照.json').read_text(encoding='utf-8'))
        config = json.loads((batch / '调用配置.json').read_text(encoding='utf-8'))
        self.assertEqual([shot['id'] for shot in snapshot['shots']], ['SH001', 'SH002'])
        self.assertEqual(config['engine'], 'codex')
        self.assertEqual(config['program'], 'codex.exe')

        # 派发后改分镜／改选镜都不影响这一批：快照保留派发时的内容。
        _episode(self.root, [_shot('SH999')], name='episode.json')
        unchanged = json.loads((batch / '分镜快照.json').read_text(encoding='utf-8'))
        self.assertEqual([shot['id'] for shot in unchanged['shots']], ['SH001', 'SH002'])


class VerifyAndWorkerAnchorTests(_WorkspaceCase):
    def verify_shot(self, tmp, *, duration=5.0, video=True, preview=b'video-bytes'):
        base = Path(tmp)
        shot_dir = base / 'shot'
        shot_dir.mkdir(exist_ok=True)
        preview_path = shot_dir / 'SH001.mp4'
        preview_path.write_bytes(preview)
        project_file = shot_dir / 'SH001.blend'
        project_file.write_bytes(b'blend')
        shot_dir.joinpath('预演记录.json').write_text(json.dumps({
            'preview': str(preview_path), 'project_file': str(project_file)}), encoding='utf-8')
        source = _episode(self.root, [_shot('SH001')])
        probe = {'format': {'duration': str(duration)},
                 'streams': ([{'codec_type': 'video'}] if video else [{'codec_type': 'audio'}])}
        return shot_dir, source, SimpleNamespace(returncode=0, stdout=json.dumps(probe))

    def test_req_s09_21_verify_requires_a_real_video_and_registers_evidence_once(self):
        with tempfile.TemporaryDirectory() as td:
            shot_dir, source, probe = self.verify_shot(td)
            with patch.object(stage_execution_service, 'white_model_shot_directory',
                              lambda *args, **kwargs: shot_dir), \
                 patch.object(stage_execution_service, 'sync_previs_copy',
                              lambda *args, **kwargs: None), \
                 patch('integrations.tool_path', lambda *args, **kwargs: 'ffprobe'), \
                 patch('subprocess.run', return_value=probe):
                self.assertTrue(previs_automation.verify(self.root, 'SH001', 5, source))
                record = wm.read_record(shot_dir)
                evidence = record['evidence']
                self.assertEqual(evidence['preview_bytes'], len(b'video-bytes'))
                self.assertEqual(evidence['media']['duration'], 5.0)
                self.assertEqual(wm.evidence_state(record, Path(record['preview']),
                                                   source, 'SH001'), 'ok')
                first = evidence['verified_at']
                self.assertTrue(previs_automation.verify(self.root, 'SH001', 5, source))
                self.assertEqual(wm.read_record(shot_dir)['evidence']['verified_at'], first,
                                 '证据未变时复用，不重复登记')

    def test_req_s09_21_verify_rejects_empty_missing_stream_and_wrong_duration(self):
        cases = [
            ('empty', {'preview': b''}, 5.0, True),
            ('no-video', {'video': False}, 5.0, True),
            ('wrong-duration', {'duration': 5.6}, 5.0, True),
            ('missing-project-file', {'preview': b'video-bytes'}, 5.0, False),
        ]
        for name, kwargs, seconds, expect_project_file in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                if name == 'missing-project-file':
                    shot_dir, source, probe = self.verify_shot(td)
                    (shot_dir / 'SH001.blend').unlink()
                else:
                    shot_dir, source, probe = self.verify_shot(td, **kwargs)
                with patch.object(stage_execution_service, 'white_model_shot_directory',
                                  lambda *args, **kwargs: shot_dir), \
                     patch.object(stage_execution_service, 'sync_previs_copy',
                                  lambda *args, **kwargs: None), \
                     patch('integrations.tool_path', lambda *args, **kwargs: 'ffprobe'), \
                     patch('subprocess.run', return_value=probe):
                    self.assertFalse(previs_automation.verify(self.root, 'SH001', seconds, source))
                self.assertEqual(wm.read_record(shot_dir), {'preview': str(shot_dir / 'SH001.mp4'),
                                                            'project_file': str(shot_dir / 'SH001.blend')})

    def test_req_s09_21_worker_reuses_ready_previs_without_running_the_engine(self):
        source = _episode(self.root, [_shot('SH001')])
        self.start_env(verify=lambda *args, **kwargs: True)
        state = {'status': {}, 'progress': {}}
        previs_automation.start(self.root, source, ['SH001'], state)
        self.wait(state)
        self.assertEqual(state['status'][str(self.root) + '|SH001'], '已就绪')
        self.assertEqual(state['progress'][str(self.root) + '|SH001'], 'ready')
        self.assertEqual(json.loads((Path(state['log_dir']) / '状态.json').read_text(encoding='utf-8')),
                         {'SH001': {'state': 'ready', 'reused': True}})
        self.assertEqual(self.runs, [], '已就绪的镜头不再调用引擎')

    def test_req_s09_21_worker_runs_shots_in_order_and_marks_failure_with_the_report(self):
        source = _episode(self.root, [_shot('SH001'), _shot('SH002')])
        self.start_env(verify=lambda *args, **kwargs: False)
        state = {'status': {}, 'progress': {}}
        previs_automation.start(self.root, source, ['SH001', 'SH002'], state)
        self.wait(state)
        self.assertEqual([args[2].name for args in self.runs], ['SH001', 'SH002'], '批内逐镜顺序执行')
        for sid in ('SH001', 'SH002'):
            self.assertTrue(state['status'][str(self.root) + '|' + sid].startswith('失败：'))
            self.assertIn('制作报告', state['status'][str(self.root) + '|' + sid])
            self.assertEqual(state['progress'][str(self.root) + '|' + sid], 'failed')
        result = json.loads((Path(state['log_dir']) / '状态.json').read_text(encoding='utf-8'))
        self.assertEqual({sid: item['state'] for sid, item in result.items()},
                         {'SH001': 'failed', 'SH002': 'failed'})
        self.assertIn('失败项请查看运行日志', state['summary'])


class StopAnchorTests(_WorkspaceCase):
    def test_req_s09_22_local_stop_marks_the_in_flight_result_as_pending_review(self):
        source = _episode(self.root, [_shot('SH001')])
        self.start_env()
        self.patch(platform_tools, 'execution_checkpoint',
                   lambda: (_ for _ in ()).throw(ExecutionStopped('本机已停止等待', started=True)))
        state = {'status': {}, 'progress': {}}
        previs_automation.start(self.root, source, ['SH001'], state)
        self.wait(state)
        key = str(self.root) + '|SH001'
        self.assertEqual(state['status'][key], '本机已停止等待；结果待核对')
        self.assertEqual(state['progress'][key], 'unknown')
        self.assertTrue(state['stop'])
        result = json.loads((Path(state['log_dir']) / '状态.json').read_text(encoding='utf-8'))
        self.assertEqual(result['SH001']['state'], 'unknown')

    def test_req_s09_22_force_stop_only_terminates_this_projects_engines(self):
        state = {'busy': True, 'status': {},
                 'progress': {'p|SH001': 'running', 'p|SH002': 'queued', 'p|SH003': 'ready'}}
        with patch.object(workflow_engines, 'terminate', return_value=['123']) as terminate:
            self.assertEqual(previs_automation.force_stop('p', state), ['123'])
            terminate.assert_called_once_with('p')
        self.assertTrue(state['stop'])
        self.assertEqual(state['status']['p|SH001'], '已强制停止')
        self.assertEqual(state['status']['p|SH002'], '已强制停止')
        self.assertNotIn('p|SH003', state['status'], '已就绪的镜头不需要改状态')
        self.assertIn('1 个制作进程', state['summary'])

    def test_req_s09_22_shots_after_the_stop_are_marked_stopped_not_failed(self):
        source = _episode(self.root, [_shot('SH001'), _shot('SH002')])

        def stop_while_running(*args, **kwargs):
            self._state['stop'] = True

        self.start_env(run=stop_while_running)
        self._state = {'status': {}, 'progress': {}}
        previs_automation.start(self.root, source, ['SH001', 'SH002'], self._state)
        self.wait(self._state)
        self.assertEqual(self._state['status'][str(self.root) + '|SH001'], '已强制停止')
        self.assertEqual(self._state['progress'][str(self.root) + '|SH001'], 'cancelled')
        self.assertEqual(self._state['status'][str(self.root) + '|SH002'], '已停止')
        self.assertEqual(self._state['progress'][str(self.root) + '|SH002'], 'cancelled')
        self.assertIn('已强制停止', self._state['summary'])


class ProgressAndMonitorAnchorTests(_WorkspaceCase):
    def test_req_s09_23_invalid_or_missing_frames_show_agent_is_still_making_it(self):
        from previs_progress_service import status_value
        with tempfile.TemporaryDirectory() as td:
            log = Path(td)
            (log / 'SH001_进度.json').write_text(json.dumps(
                {'shot_id': 'SH001', 'stage': 'render', 'completed': 120, 'total': 100}),
                encoding='utf-8')
            state = {'progress': {'p|SH001': 'running'}, 'log_dir': td, 'busy': True}
            self.assertEqual(status_value(state, 'p', 'SH001', '制作中'),
                             ('indeterminate', 0, 'Agent 制作中'))
            (log / 'SH001_进度.json').unlink()
            self.assertEqual(status_value(state, 'p', 'SH001', '制作中'),
                             ('indeterminate', 0, 'Agent 制作中'))
        self.assertEqual(previs_monitor.REFRESH_SECONDS, 5)
        page = previs_monitor.render({}, Path('p'))
        self.assertIn('content="5"', page)
        self.assertIn('每 5 秒', page)

    def test_req_s09_23_batch_result_is_queued_for_the_pet_announcer(self):
        state = {}
        previs_automation.announce(state, True, '自动制作结束：1/1 就绪', 7)
        self.assertEqual(state['news'].get_nowait(), (7, True, '自动制作结束：1/1 就绪'))

    def test_req_s09_23_manual_dispatch_opens_the_monitor_but_unattended_does_not(self):
        opened = []

        def monitor(state, project):
            opened.append(project)
            state['monitor'] = ('http://127.0.0.1:65535/', None)
            return state['monitor']

        source = _episode(self.root, [_shot('SH001')])
        self.start_env(monitor=monitor)
        state = _Watched(status={}, progress={})
        previs_automation.start(self.root, source, ['SH001'], state, monitor=True)
        self.wait(state)
        self.assertEqual(opened, [self.root])
        self.assertTrue(any('65535' in text for text in state.summaries),
                        '手动派发要把监视页地址说给用户')

        unattended = {'status': {}, 'progress': {}}
        previs_automation.start(self.root, source, ['SH001'], unattended, monitor=False)
        self.wait(unattended)
        self.assertEqual(opened, [self.root], '无人值守不弹浏览器')


class NotesAndEntryAnchorTests(_WorkspaceCase):
    def test_req_s09_25_notes_are_merged_into_the_record_and_media_is_kept(self):
        shot_dir = Path(self.temp.name) / 'shot'
        shot_dir.mkdir()
        record = {'preview': 'preview.mp4', 'project_file': 'scene.blend', 'shot_id': 'SH001'}
        _publish(shot_dir / '预演记录.json', record)
        wm.save_previs_notes(shot_dir, 'SH001', '他先转身再抬手，机位从左侧跟到正面',
                             publish=_publish)
        saved = wm.read_record(shot_dir)
        self.assertEqual(saved['notes'], '他先转身再抬手，机位从左侧跟到正面')
        self.assertEqual(saved['preview'], 'preview.mp4')
        self.assertEqual(saved['project_file'], 'scene.blend')
        self.assertTrue(saved['updated_at'])

    def test_req_s09_25_page_offers_online_tools_and_hands_the_shot_to_codex_or_claude(self):
        self.assertGreaterEqual(len(white_model.TOOLS), 1)
        for title, url in white_model.TOOLS:
            self.assertTrue(title)
            self.assertTrue(url.startswith('https://'), url)

        class Widget:
            def __init__(self, *args, **kwargs):
                pass

            def pack(self, *args, **kwargs):
                pass

            def insert(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                return ''

            def destroy(self):
                pass

            def lift(self, *args, **kwargs):
                pass

        buttons = {}

        class Button(Widget):
            def __init__(self, parent=None, text='', command=None, **kwargs):
                self.text = text
                self.command = command
                buttons[text] = command

        class Var:
            def __init__(self, value=''):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        calls = {}
        shot_dir = Path(self.temp.name) / 'shot'
        shot_dir.mkdir()
        desktop = SimpleNamespace(
            win=None,
            root=self.root,
            current_frame_json=lambda: self.root / 'episode.json',
            open_flow_agent=lambda *args, **kwargs: calls.setdefault('agent', args),
            status=SimpleNamespace(set=lambda text: None))

        with patch.object(white_model, 'BaseDialog', Widget), \
             patch.object(white_model, 'Card', Widget), \
             patch.object(white_model, 'TextArea', Widget), \
             patch.object(white_model, 'PrimaryButton', Button), \
             patch.object(white_model, 'SecondaryButton', Button), \
             patch.object(white_model.ttk, 'Label', Widget), \
             patch.object(white_model.ttk, 'LabelFrame', Widget), \
             patch.object(white_model.ttk, 'Frame', Widget), \
             patch.object(white_model.tk, 'StringVar', Var), \
             patch.object(white_model, 'shot_directory', lambda *args, **kwargs: shot_dir), \
             patch.object(white_model, 'read_record', lambda root: {}), \
             patch.object(white_model, 'find_blender',
                          lambda refresh=False: Path('D:/Blender/blender.exe')):
            white_model.open_previs(desktop, 'SH001')
            buttons['开始白模制作']()

        self.assertEqual(calls['agent'][0], 'previs')
        self.assertEqual(calls['agent'][1], '白模预演')
        prompt = calls['agent'][2]
        self.assertIn('Blender', prompt)
        self.assertIn('备注', prompt)
        self.assertIn('SH001', prompt)


class CompletionEvidenceAnchorTests(_WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.source = _episode(self.root, [_shot('SH001')], name='storyboard/EP001.json')
        (self.root / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': [str(self.source)]}), encoding='utf-8')

    def test_req_s09_34_completion_needs_both_sg05_ok_and_started(self):
        from stage_parallel import previs_ready

        ok, _detail = completion.completion_evidence(self.root, 'previs')
        self.assertFalse(ok, '白模还没开始：ok 为真但 started 为假也不算完成')
        self.assertFalse(previs_ready(self.root)['started'])

        # previs.json 存在本身不是证据。
        save(self.root / '09白模预演' / 'output' / 'previs.json',
             {'shots': {'SH001': {'preview': '09白模预演/assets/SH001/x.mp4'}}})
        ok, _detail = completion.completion_evidence(self.root, 'previs')
        self.assertFalse(ok)
        self.assertFalse(previs_ready(self.root)['started'])

        from stage_execution_service import record_previs_evidence, white_model_shot_directory
        directory = white_model_shot_directory(self.root, 'SH001', source=self.source)
        directory.mkdir(parents=True, exist_ok=True)
        media = directory / 'SH001_白模预演.mp4'
        media.write_bytes(b'preview')
        (directory / '预演记录.json').write_text(json.dumps({'preview': str(media)}), encoding='utf-8')
        record_previs_evidence(self.root, 'SH001', self.source,
                               media={'duration': 5, 'has_video': True})
        self.assertTrue(previs_ready(self.root)['ok'])
        self.assertTrue(previs_ready(self.root)['started'])
        ok, _detail = completion.completion_evidence(self.root, 'previs')
        self.assertTrue(ok)

        # 再加一个复杂镜头但没预演：已开始，但 SG-05 不通过。
        self.source = _episode(self.root, [_shot('SH001'), _shot('SH002')],
                               name='storyboard/EP001.json')
        (self.root / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': [str(self.source)]}), encoding='utf-8')
        gate = previs_ready(self.root)
        self.assertFalse(gate['ok'])
        self.assertTrue(gate['started'])
        ok, _detail = completion.completion_evidence(self.root, 'previs')
        self.assertFalse(ok, 'SG-05 不通过时不能算阶段完成')


class BatchPromptAnchorTests(_WorkspaceCase):
    def test_req_s09_42_prompt_keeps_simplified_preview_and_local_blender_only(self):
        source = _episode(self.root, [{'id': 'SH001', 'title': '第一镜'}])
        captured = {}

        def prompt_with_settings(prompt, config):
            captured['prompt'] = prompt
            return prompt

        with patch.object(wm, 'find_blender', lambda refresh=False: Path('D:/Blender/blender.exe')), \
             patch('agent.shot_assets.assets', return_value=[]), \
             patch('workflow_engines.prompt_with_settings', prompt_with_settings):
            prompt = previs_batch_service.prepare_batch(
                self.root, source, ['SH001'], {'engine': 'codex'})

        self.assertIn('只需要简化白模', prompt)
        self.assertIn('不制作4K精片', prompt)
        self.assertIn('不使用达芬奇、付费API或图像生成服务', prompt)
        self.assertIn('blender --background', prompt)
        self.assertIn('低分辨率预览', prompt)
        self.assertIn('不要安装、卸载或移动Blender', prompt)
        self.assertEqual(captured['prompt'], prompt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
