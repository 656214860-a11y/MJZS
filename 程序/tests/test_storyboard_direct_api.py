# -*- coding: utf-8 -*-
"""初步分镜选 API 模型时的直连执行器（REQ-S03-53）：不经 Qwen、合格 JSON 才发布、
手动与三虎同一执行器、强制停止能中断请求。模型请求全部用假适配器，不调用真实 API。"""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def good_episode(**extra):
    data = {'episode_id': 'EP001', 'title': '雨夜', 'duration': 6, 'prompt_language': 'zh',
            'source_script': '', 'shots': [{
                'id': 'SH001', 'title': '开场', 'duration': 6, 'characters': [], 'location': '街头', 'props': [],
                'frame': 'frames/SH001.png', 'frame_prompt': '雨夜街头静止画面',
                'video_prompt': '镜头缓推，雨夜街头，行人撑伞走过。', 'dialogue': []}]}
    data.update(extra)
    return data


class FakeAdapter:
    """按顺序返回预置回复；记录每次请求。block 给了就一直等到被取消。"""

    def __init__(self, *replies, block=None):
        self.replies = list(replies)
        self.calls = []
        self.block = block

    def stream(self, messages, options=None, model='', system='', on_chunk=None, cancelled=None):
        self.calls.append({'messages': list(messages), 'system': system})
        if self.block is not None:
            self.block.set()
            while not (cancelled and cancelled()):
                threading.Event().wait(0.01)
            return {'ok': False, 'text': '', 'error': '请求已取消', 'error_class': 'cancelled', 'model': model}
        text = self.replies.pop(0)
        return {'ok': True, 'text': text, 'error': '', 'model': model, 'response_meta': {'finish_reason': 'stop'}}

    chat = stream


class DirectApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.script = self.project / '02剧本结构' / 'EP001_雨夜.md'
        self.script.parent.mkdir(parents=True)
        self.script.write_text('第一场 街头\n' + '雨夜，行人匆匆。' * 800, encoding='utf-8')
        self.config = {'engine': 'qwen', 'model': 'deepseek-v4-pro', 'program': ''}
        self.messages = []

    def run_batch(self, adapter, **extra):
        from orchestrator import storyboard_direct_api as api
        return api.run_batch(self.project, self.config, 'SKILL正文', scripts=[self.script], adapter=adapter,
                             record={'name': 'deepseek-v4-pro'}, report=self.messages.append, **extra)

    def boards(self):
        return sorted(self.project.rglob('*_分镜.json'))

    def test_req_s03_53_direct_model_only_for_pool_models(self):
        """REQ-S03-53：引擎为 qwen 且所选模型在模型池里才直连；桌面程序和本机 Codex／Claude 不直连。"""
        from orchestrator import storyboard_direct_api as api
        pool = {'deepseek-v4-pro': {'name': 'deepseek-v4-pro', 'call_mode': 'API'},
                'desk': {'name': 'desk', 'call_mode': 'Desktop'}}
        with patch('model_pool.pool', return_value=pool):
            self.assertEqual('deepseek-v4-pro', api.direct_model(self.config)[0])
            self.assertIsNone(api.direct_model({'engine': 'qwen', 'model': 'desk'}))
            self.assertIsNone(api.direct_model({'engine': 'qwen', 'model': 'missing'}))
            self.assertIsNone(api.direct_model({'engine': 'codex', 'model': 'deepseek-v4-pro'}))

    def test_req_s03_53_valid_json_is_published_without_qwen(self):
        """REQ-S03-53：合格 JSON 发布分镜与同名文档，全程不碰 qwen_adapter，请求里带完整剧本不截断。"""
        adapter = FakeAdapter(json.dumps(good_episode(), ensure_ascii=False))
        with patch('orchestrator.qwen_adapter.window_title') as qwen, patch('orchestrator.qwen_adapter.submit_existing') as submit:
            results = self.run_batch(adapter)
        qwen.assert_not_called()
        submit.assert_not_called()
        self.assertTrue(results[0]['ok'], results)
        boards = self.boards()
        self.assertEqual(1, len(boards))
        saved = json.loads(boards[0].read_text(encoding='utf-8'))
        self.assertEqual('EP001', saved['episode_id'])
        self.assertTrue(saved['source_script'].endswith('EP001_雨夜.md'))
        self.assertEqual(1, len(list(self.project.rglob('分镜文档/*.md'))))
        request = ''.join(str(m.get('content', '')) for m in adapter.calls[0]['messages'])
        self.assertIn('雨夜，行人匆匆。' * 800, request)
        self.assertIn('SKILL正文', adapter.calls[0]['system'])
        self.assertTrue(any('EP001' in text for text in self.messages))

    def test_req_s03_53_invalid_json_retries_once_then_writes_nothing(self):
        """REQ-S03-53：不合格带错误清单重试一次，仍不合格不落盘并给出原因。"""
        adapter = FakeAdapter(json.dumps(good_episode(duration=99)), '不是JSON')
        results = self.run_batch(adapter)
        self.assertEqual(2, len(adapter.calls))
        retry = ''.join(str(m.get('content', '')) for m in adapter.calls[1]['messages'])
        self.assertIn('duration', retry)
        self.assertFalse(results[0]['ok'])
        self.assertTrue(results[0]['error'])
        self.assertEqual([], self.boards())

    def test_req_s03_53_retry_can_recover(self):
        """REQ-S03-53：第一次不合格、重试合格则发布。"""
        adapter = FakeAdapter(json.dumps(good_episode(duration=99)), json.dumps(good_episode()))
        self.assertTrue(self.run_batch(adapter)[0]['ok'])
        self.assertEqual(1, len(self.boards()))

    def test_req_s03_53_manual_and_auto_share_one_executor(self):
        """REQ-S03-53：手动按钮与三虎 _start_storyboard 都经 open_flow_agent，分流点只有一处；其他阶段不进直连。"""
        import desktop_idea_chat as chat
        host = Mock(root=self.project, worker=False, projects=Mock(info={'projects': []}))
        request = chat._FlowAgentRequest('storyboard', '手动制作分镜', '任务', None, None, self.config,
                                         False, False, False)
        with patch('workflow_settings.current', return_value=self.config), \
                patch('orchestrator.storyboard_direct_api.direct_model', return_value=('deepseek-v4-pro', {'name': 'x'})), \
                patch('desktop_storyboard_direct.run_storyboard_direct') as direct, \
                patch('orchestrator.qwen_adapter.window_title') as qwen:
            chat._FlowAgentLaunch(host, request).build()
        direct.assert_called_once()
        qwen.assert_not_called()
        request = chat._FlowAgentRequest('video_prompt', '视频提示词', '任务', None, None, self.config, False, False, False)
        with patch('workflow_settings.current', return_value=self.config), \
                patch('orchestrator.storyboard_direct_api.direct_model', return_value=('m', {})) as model, \
                patch('desktop_storyboard_direct.run_storyboard_direct') as direct, \
                patch('orchestrator.qwen_adapter.window_title', return_value='Q'):
            chat._FlowAgentLaunch(host, request).build()
        direct.assert_not_called()
        model.assert_not_called()

    def test_req_s03_53_stop_interrupts_request_and_writes_nothing(self):
        """REQ-S03-53：workflow_engines.terminate 能中断进行中的直连请求，停止后不落盘；重复启动被拒。"""
        from orchestrator import storyboard_direct_api as api
        import workflow_engines
        started = threading.Event()
        adapter = FakeAdapter(block=started)
        job = api.launch(self.project, self.config, 'SKILL正文', scripts=[self.script], adapter=adapter,
                         record={'name': 'm'}, report=self.messages.append)
        self.assertTrue(started.wait(5))
        with self.assertRaisesRegex(ValueError, '正在直连制作'):
            api.launch(self.project, self.config, 'SKILL正文', scripts=[self.script], adapter=adapter, record={})
        workflow_engines.terminate(self.project)
        job.join(5)
        self.assertFalse(job.is_alive())
        self.assertEqual([], self.boards())
        self.assertFalse(job.results[0]['ok'])


class StoryboardDirectProductionPathTests(unittest.TestCase):
    """REQ-S03-53 真实路径（FIX-S03-DIRECT-ERROR）：不注入 adapter 也要能发出请求并发布；
    失败结果带错误码与原因，状态栏总结直接写「哪一集、为什么」，整批未启动不误报集数。"""

    API_RECORD = {'name': 'fixture-api', 'model': 'fixture-api', 'call_mode': 'API',
                  'base_url': 'https://example.test/v1', 'wire_api': 'chat',
                  'key_env': 'FIXTURE_API_KEY', 'context_length': 128000}

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.script = self.project / '02剧本结构' / 'EP001_雨夜.md'
        self.script.parent.mkdir(parents=True)
        self.script.write_text('第一场 街头\n' + '雨夜，行人匆匆。' * 800, encoding='utf-8')
        self.config = {'engine': 'qwen', 'model': 'fixture-api', 'program': ''}
        self.messages = []

    def boards(self):
        return sorted(self.project.rglob('*_分镜.json'))

    def _real_path(self, replies):
        """真实路径补丁：池里放一条 API 记录；PoolAdapter.stream 依次返回 replies。"""
        import contextlib
        import infra.model_router as model_router
        stack = contextlib.ExitStack()
        stack.enter_context(patch('infra.model_pool.pool',
                                  return_value={'fixture-api': dict(self.API_RECORD)}))
        stack.enter_context(patch('infra.model_pool.require_certified', return_value=False))
        stack.enter_context(patch('infra.model_pool.health_is_blocked', return_value=False))
        stack.enter_context(patch.object(model_router.PoolAdapter, 'stream',
                                        Mock(side_effect=list(replies))))
        return stack

    def test_real_path_without_injected_adapter_publishes(self):
        """不传 adapter／record 的真实路径：能发出请求并发布分镜（改前 ImportError）。"""
        from orchestrator.storyboard_direct_api import run_batch
        reply = {'ok': True, 'text': json.dumps(good_episode(), ensure_ascii=False), 'error': '',
                 'model': 'fixture-api', 'response_meta': {'finish_reason': 'stop'}}
        with self._real_path([reply]):
            results = run_batch(self.project, self.config, 'SKILL正文', scripts=[self.script],
                                report=self.messages.append)
        self.assertTrue(results[0]['ok'], results)
        self.assertEqual('', results[0]['code'])
        self.assertEqual(1, len(self.boards()))

    def test_request_failure_carries_code_and_reason(self):
        """HTTP 401 → E-AUTH-REJECTED，error 以错误码开头且含原始状态码，不落盘。"""
        from orchestrator.storyboard_direct_api import run_batch
        reply = {'ok': False, 'status': 401, 'error': 'HTTP 401 unauthorized', 'error_class': 'auth'}
        with self._real_path([reply]):
            results = run_batch(self.project, self.config, 'SKILL正文', scripts=[self.script])
        self.assertFalse(results[0]['ok'])
        self.assertEqual('E-AUTH-REJECTED', results[0]['code'])
        self.assertTrue(results[0]['error'].startswith('[E-AUTH-REJECTED]'), results[0]['error'])
        self.assertIn('401', results[0]['error'])
        self.assertEqual([], self.boards())

    def test_validation_failure_is_contract_violation(self):
        """两次回复都不合格 → E-CONTRACT-VIOLATION，error 里带校验问题原文。"""
        from orchestrator.storyboard_direct_api import run_batch
        bad = {'ok': True, 'text': '不是JSON', 'error': '', 'response_meta': {'finish_reason': 'stop'}}
        with self._real_path([bad, bad]):
            results = run_batch(self.project, self.config, 'SKILL正文', scripts=[self.script])
        self.assertFalse(results[0]['ok'])
        self.assertEqual('E-CONTRACT-VIOLATION', results[0]['code'])
        self.assertIn('回复里没有找到 JSON 对象', results[0]['error'])
        self.assertEqual([], self.boards())

    def test_batch_level_failure_keeps_reason(self):
        """整批开工前失败（模型准入）→ E-CONFIG-INVALID，error 保留中文原因。"""
        import infra.model_pool
        from orchestrator.storyboard_direct_api import Job
        with patch('infra.model_pool.pool', return_value={'fixture-api': dict(self.API_RECORD)}), \
                patch.object(infra.model_pool, 'model_admission_error',
                             return_value='这条模型没有填写上下文窗口'):
            job = Job(self.project, self.config, 'SKILL正文', scripts=[self.script])
            job.run()
        self.assertFalse(job.results[0]['ok'])
        self.assertEqual('E-CONFIG-INVALID', job.results[0]['code'])
        self.assertIn('这条模型没有填写上下文窗口', job.results[0]['error'])

    def test_summary_text_shows_reasons(self):
        """状态栏总结：整批未启动写「没有启动」＋原因；一成一败带文件名与原因；全成到句号。"""
        from ui.desktop_storyboard_direct import summary_text
        batch = summary_text([{'source': '', 'ok': False, 'stopped': False, 'path': '',
                               'error': '[E-CONFIG-INVALID] 配置无效或缺失：这条模型没有填写上下文窗口'}])
        self.assertIn('没有启动', batch)
        self.assertIn('这条模型没有填写上下文窗口', batch)
        self.assertNotIn('失败 1 集', batch)
        mixed = summary_text([
            {'source': str(self.project / 'EP001_雨夜.md'), 'ok': True, 'stopped': False,
             'path': 'EP001_雨夜_分镜.json', 'error': ''},
            {'source': str(self.project / 'EP002_雨夜.md'), 'ok': False, 'stopped': False,
             'path': '', 'error': '[E-AUTH-REJECTED] 凭据被服务拒绝'}])
        self.assertIn('成功 1 集，失败 1 集', mixed)
        self.assertIn('EP002_雨夜.md', mixed)
        self.assertIn('[E-AUTH-REJECTED]', mixed)
        done = summary_text([{'source': str(self.project / 'EP001_雨夜.md'), 'ok': True,
                              'stopped': False, 'path': 'EP001_雨夜_分镜.json', 'error': ''}])
        self.assertEqual('初步分镜直连完成：成功 1 集，失败 0 集。', done)

    def test_summary_text_and_log_leave_no_absolute_path(self):
        """状态栏与通知只写文件名：总结文字不出现项目绝对路径。"""
        from ui.desktop_storyboard_direct import summary_text
        text = summary_text([
            {'source': str(self.script), 'ok': False, 'stopped': False, 'path': '',
             'error': '[E-IO-WRITE] 写入文件失败'},
            {'source': str(self.script), 'ok': True, 'stopped': False,
             'path': 'EP001_雨夜_分镜.json', 'error': ''}])
        self.assertIn('EP001_雨夜.md', text)
        self.assertNotIn(str(self.project), text)

    def test_adapter_classes_come_from_model_router(self):
        """守卫：PoolAdapter／ModelAdapter 只住 infra.model_router，不许从 model_pool 取。"""
        import ast
        from tests.architecture._scan import ROOT, module_scan_files, parse
        bad = []
        for path in module_scan_files():
            relative = path.relative_to(ROOT).as_posix()
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.ImportFrom) and node.module in ('infra.model_pool', 'model_pool'):
                    bad += ['%s:%d from %s import %s' % (relative, node.lineno, node.module, alias.name)
                            for alias in node.names if alias.name in ('PoolAdapter', 'ModelAdapter')]
                elif isinstance(node, ast.Attribute) and node.attr in ('PoolAdapter', 'ModelAdapter'):
                    parts, value = [], node.value
                    while isinstance(value, ast.Attribute):
                        parts.append(value.attr)
                        value = value.value
                    if isinstance(value, ast.Name):
                        parts.append(value.id)
                    if '.'.join(reversed(parts)) in ('infra.model_pool', 'model_pool'):
                        bad.append('%s:%d %s.%s' % (relative, node.lineno,
                                                    '.'.join(reversed(parts)), node.attr))
        self.assertEqual([], bad)


class StageFileDirectApiTests(unittest.TestCase):
    """通用阶段直连 API 文件输出引擎：严格按 SKILL 仅输出阶段文件、不对话，并原子发布。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.project.mkdir(parents=True)
        self.config = {'engine': 'qwen', 'model': 'deepseek-v4-pro', 'api': True}

    def test_script_structure_outputs_file_only_strips_fence_and_writes_manifests(self):
        from orchestrator import storyboard_direct_api as api
        from contract import script_contract
        writing = self.project / 'writing'
        writing.mkdir(parents=True)
        source = writing / '剧本_雨夜.md'
        source.write_text('第一场 街头\n阿远站在雨里，攥紧旧信封。\n', encoding='utf-8')
        fenced = '```markdown\n# 第1集 雨夜\n\n## 分场剧本\n\n### 场次 1 街头·夜\n阿远攥紧旧信封，雨水顺着眉骨滑落。\n```'
        adapter = FakeAdapter(fenced)
        notices = []
        result = api.run_stage_file_batch(
            self.project, 'script_structure', self.config, '【结构化SKILL】只输出分场结构剧本',
            instruction='强化雨夜情绪与特写细节', adapter=adapter,
            record={'name': 'deepseek-v4-pro'}, report=notices.append)
        self.assertTrue(result['ok'], result)
        target = Path(result['path'])
        self.assertTrue(target.is_file())
        body = target.read_text(encoding='utf-8')
        self.assertTrue(body.startswith('# 第1集 雨夜'))
        self.assertNotIn('```', body)
        self.assertIn(api.STAGE_FILE_ONLY_RULES, adapter.calls[0]['system'])
        self.assertIn('【结构化SKILL】', adapter.calls[0]['system'])
        prompt = adapter.calls[0]['messages'][0]['content']
        self.assertIn('强化雨夜情绪与特写细节', prompt)
        self.assertIn('阿远站在雨里', prompt)
        self.assertTrue(script_contract.structured_script_paths(self.project))
        self.assertTrue(any('已输出' in msg for msg in notices))

    def test_downstream_stage_writes_canonical_dir_and_backs_up_overwrite(self):
        from orchestrator import storyboard_direct_api as api
        from contract.stage_path_service import write_dir
        adapter = FakeAdapter('# 剪辑方案 v1\n快切开场。', '# 剪辑方案 v2\n三秒钩子强化。')
        first = api.run_stage_file_batch(
            self.project, 'edit', self.config, '【剪辑SKILL】',
            instruction='第一版剪辑节奏', adapter=adapter, record={'name': 'deepseek-v4-pro'})
        self.assertTrue(first['ok'], first)
        target = Path(first['path'])
        self.assertEqual(target.parent.resolve(), write_dir(self.project, 'edit').resolve())
        self.assertIn('剪辑方案 v1', target.read_text(encoding='utf-8'))
        second = api.run_stage_file_batch(
            self.project, 'edit', self.config, '【剪辑SKILL】',
            instruction='第二版加强开场钩子', adapter=adapter, record={'name': 'deepseek-v4-pro'})
        self.assertTrue(second['ok'], second)
        self.assertIn('剪辑方案 v2', target.read_text(encoding='utf-8'))
        backups = list((target.parent / '历史版本').glob('*.md'))
        self.assertEqual(len(backups), 1)
        self.assertIn('剪辑方案 v1', backups[0].read_text(encoding='utf-8'))

    def test_storyboard_run_batch_forwards_request_text(self):
        from orchestrator import storyboard_direct_api as api
        script = self.project / '02剧本结构' / 'EP001_雨夜.md'
        script.parent.mkdir(parents=True)
        script.write_text('第一场 街头\n雨夜行人。\n', encoding='utf-8')
        adapter = FakeAdapter(json.dumps(good_episode(), ensure_ascii=False))
        results = api.run_batch(
            self.project, self.config, 'SKILL正文', scripts=[script],
            request_text='多给男主眼神特写', adapter=adapter, record={'name': 'deepseek-v4-pro'})
        self.assertTrue(results[0]['ok'], results)
        request = ''.join(str(m.get('content', '')) for m in adapter.calls[0]['messages'])
        self.assertIn('多给男主眼神特写', request)


class StoryboardDirectReplyAreaTests(unittest.TestCase):
    """FIX-S03-UX-POLISH：run_storyboard_direct 全链路接入 reply_note 并在启动/失败时自动展开。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve() / '项目'
        self.script = self.project / '02剧本结构' / 'EP001_雨夜.md'
        self.script.parent.mkdir(parents=True)
        self.script.write_text('第一场 街头\n雨夜行人。\n', encoding='utf-8')
        self.board = self.project / '03初步分镜' / '分镜拆分' / 'EP001_雨夜_分镜.json'
        self.board.parent.mkdir(parents=True)
        self.board.write_text('{}', encoding='utf-8')
        self.config = {'engine': 'qwen', 'model': 'deepseek-v4-pro', 'program': ''}

    def _make_host(self, *, reply_note=None, reply_area=None, with_reply_attrs=True):
        from types import SimpleNamespace
        scheduled = []
        statuses = []

        class _Status:
            def set(self, text):
                statuses.append(str(text))

        host = SimpleNamespace(
            root=self.project,
            status=_Status(),
            win=SimpleNamespace(after=lambda _ms, fn: scheduled.append(fn)),
            pet_reports=[],
            files_panel=SimpleNamespace(fill_script_list=Mock()),
            storyboard_editor_page=SimpleNamespace(refresh=Mock()),
            notifier=SimpleNamespace(error=Mock()),
            pet=None,
        )
        host.pet_report = lambda stage, text: host.pet_reports.append((stage, text))
        if with_reply_attrs:
            host.reply_note = reply_note
            host.reply_area = reply_area
        return host, scheduled, statuses

    def _run_direct(self, host, scheduled, *, progress_messages=(), results=()):
        from ui.desktop_storyboard_direct import run_storyboard_direct
        alive = [True]

        class _FakeJob:
            def __init__(self, res):
                self.results = list(res)

            def is_alive(self):
                return alive[0]

        def fake_launch(_root, _config, _prompt, **kwargs):
            report = kwargs['report']
            for msg in progress_messages:
                report(msg)
            return _FakeJob(results)

        with patch('orchestrator.storyboard_direct_api.launch', side_effect=fake_launch), \
                patch('orchestrator.storyboard_selection.selected_many', return_value=[self.script]), \
                patch('orchestrator.workflow_settings.skill_prompt', return_value='SKILL'):
            run_storyboard_direct(host, self.config)
            self.assertEqual(len(scheduled), 1)
            drain = scheduled.pop(0)
            drain()
            self.assertEqual(len(scheduled), 1)
            alive[0] = False
            scheduled.pop(0)()

    def test_run_storyboard_direct_writes_start_progress_artifact_and_summary(self):
        notes = []
        host, scheduled, _statuses = self._make_host(
            reply_note=lambda kind, stage, text='', **kw: notes.append((kind, stage, text, kw)))
        self._run_direct(
            host, scheduled,
            progress_messages=['EP001 分镜已生成：EP001_雨夜_分镜.json（1 镜）'],
            results=[{'source': str(self.script), 'ok': True, 'stopped': False,
                      'path': str(self.board), 'error': '', 'code': ''}])
        self.assertGreaterEqual(len(notes), 4)
        self.assertEqual(notes[0][0], 'progress')
        self.assertEqual(notes[0][1], 'storyboard')
        self.assertIn('正在直连 API', notes[0][2])
        self.assertIs(notes[0][3].get('expand'), True)
        self.assertTrue(any(k == 'progress' and s == 'storyboard' and 'EP001 分镜已生成' in t
                            for k, s, t, _kw in notes))
        artifacts = [n for n in notes if n[0] == 'artifact']
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0][1], 'storyboard')
        self.assertEqual(artifacts[0][3].get('path'), str(self.board))
        self.assertEqual(artifacts[0][3].get('title'), self.board.name)
        self.assertTrue(any('成功 1 集' in t for _k, s, t, _kw in notes if s == 'storyboard'))

    def test_run_storyboard_direct_failure_expands_and_supports_legacy_3arg_stub(self):
        from types import SimpleNamespace
        notes = []
        host, scheduled, _statuses = self._make_host(
            reply_note=lambda kind, stage, text='', **kw: notes.append((kind, stage, text, kw)))
        self._run_direct(
            host, scheduled,
            progress_messages=['EP001_雨夜.md 的分镜没有生成：[E-AUTH-REJECTED] 401'],
            results=[{'source': str(self.script), 'ok': False, 'stopped': False,
                      'path': '', 'error': '[E-AUTH-REJECTED] 401', 'code': 'E-AUTH-REJECTED'}])
        errors = [n for n in notes if n[0] == 'error']
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][1], 'storyboard')
        self.assertIn('[E-AUTH-REJECTED]', errors[0][2])
        self.assertIs(errors[0][3].get('expand'), True)

        legacy_notes = []
        expanded = []
        area = SimpleNamespace(stage='storyboard', set_expanded=lambda flag: expanded.append(bool(flag)))
        host2, scheduled2, _statuses2 = self._make_host(
            reply_note=lambda kind, stage, text: legacy_notes.append((kind, stage, text)),
            reply_area=area)
        self._run_direct(
            host2, scheduled2,
            results=[{'source': str(self.script), 'ok': False, 'stopped': False,
                      'path': '', 'error': '[E-AUTH-REJECTED] 401', 'code': 'E-AUTH-REJECTED'}])
        self.assertTrue(any(k == 'progress' and '正在直连 API' in t for k, _s, t in legacy_notes))
        self.assertTrue(any(k == 'error' and '[E-AUTH-REJECTED]' in t for k, _s, t in legacy_notes))
        self.assertGreaterEqual(expanded.count(True), 2)

    def test_run_storyboard_direct_stopped_writes_notice_and_legacy_host_safe(self):
        notes = []
        host, scheduled, _statuses = self._make_host(
            reply_note=lambda kind, stage, text='', **kw: notes.append((kind, stage, text, kw)))
        self._run_direct(
            host, scheduled,
            results=[{'source': str(self.script), 'ok': False, 'stopped': True,
                      'path': '', 'error': '已停止', 'code': ''}])
        notices = [n for n in notes if n[0] == 'notice']
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0][1], 'storyboard')
        self.assertIn('已停止', notices[0][2])

        plain_host, scheduled2, statuses2 = self._make_host(with_reply_attrs=False)
        self._run_direct(
            plain_host, scheduled2,
            progress_messages=['EP001 分镜已生成：EP001_雨夜_分镜.json（1 镜）'],
            results=[{'source': str(self.script), 'ok': True, 'stopped': False,
                      'path': str(self.board), 'error': '', 'code': ''}])
        self.assertTrue(any('成功 1 集' in text for text in statuses2))


if __name__ == '__main__':
    unittest.main()
