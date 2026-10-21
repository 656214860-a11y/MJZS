"""desktop_idea_chat.open_flow_agent 改写成 _FlowAgentLaunch：HEAD 旧实现原样内嵌。宿主替身同步执行 async_ 并截留
win.after 定时器，所有外部入口（派发台账、引擎、上下文、粘贴、剪贴板）只记账；新旧实现跑同一组场景
（GPT 桌面、CLI 首次启动／续发／新会话重启、排队后获槽／超时／被拒、重复任务、Claude Desktop、桌面模型），对照完整调用记录。"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import desktop_idea_chat as module
from window_diff_support import _plain, legacy

LEGACY = "def open_flow_agent(self,stage,label,prompt,followup=None,on_receipt=None,_config=None,*,intake_only=False,new_session=False,desktop_paste=False):\n    from workflow_settings import current,writer_style_summary\n    from workflow_engines import prompt_with_settings,launch_interactive\n    from agent_dispatch import signature,claim,finish,outcome,retryable\n    if self.worker:raise ValueError('正在打开或发送 Agent 任务，请稍候；未重复发送。')\n    if stage == 'writing' and getattr(self, '_script_agent_queue', None):\n        raise ValueError('剧本模型请求正在排队，请等待或先点击中断；未重复发送。')\n    # 「发送待核实」的安全重试必须沿用第一次已经解析的引擎。原来递归重进时会重新\n    # 读取阶段配置，恰逢面板刷新／配置回退就可能把 Claude 的续发错误地交给 Codex。\n    if stage == 'writing' and not intake_only and _config is None:\n        from workflow_settings import validate_selected_skills\n        validate_selected_skills(self.root, stage)\n    config=_config if _config is not None else current(self.root,stage);followup=followup if followup is not None else prompt\n    if stage == 'writing' and not intake_only:\n        from workflow_settings import freeze_skills\n        config = freeze_skills(config)\n    native_claude = config['engine'] in ('claude-desktop-app', 'desktop-app')\n    bounded_writing = stage == 'writing' and config['engine'] == 'claude'\n    if stage == 'writing' and config['engine'] == 'claude' and not intake_only and not new_session:\n        from workflow_engines import claude_session_stale\n        new_session = claude_session_stale(self.root, stage)\n    new_session = bool(new_session and stage == 'writing' and config['engine'] == 'claude' and not intake_only)\n    use_cli = not native_claude and (config['engine']!='codex' or config['program'] or config['model'])\n    # CLI 继续复用同一进程；提取结束后不能占住唯一槽位又排队启动剧本进程。\n    setup_key=hashlib.sha256((json.dumps(config,sort_keys=True)+('brief-intake' if intake_only and not use_cli else '')).encode()).hexdigest()\n    from codex_tasks import prepare_task\n    project=self.root\n    name=next((p['name'] for p in self.projects.info['projects'] if Path(p['path'])==project),project.name)\n    title=name+' '+label\n    if config['engine']=='qwen':\n        from qwen_adapter import window_title\n        title=window_title(name,stage,getattr(self,'page_index',None))\n    def build():\n        from workflow_context import continuation_instruction,snapshot\n        from stage_execution_service import project_context\n        from workflow_context_controller import request_stage_instruction\n        from workflow_context_budget import prepare_request_context\n        if config['engine']=='codex':\n            from codex_skill_sync import sync_codex_skills\n            sync_result=sync_codex_skills()\n            if sync_result['errors'] or sync_result['conflicts']:\n                raise ValueError('Codex 技能同步未完成：'+ '; '.join(\n                    sync_result['errors']+sync_result['conflicts']))\n        data={} if intake_only or bounded_writing else snapshot(project_context(project))\n        receipt=claim(project,signature(stage,prompt,followup,config,data),title)\n        if on_receipt is not None:on_receipt(receipt)\n        if receipt['duplicate'] and use_cli:return {'receipt':receipt}\n        if not use_cli:receipt['duplicate']=False\n        try:\n            if stage=='previs':\n                from native_apps import open_blender\n                open_blender()\n            if intake_only:\n                # 提取阶段不得附加“直接生成剧本”的 SKILL/阶段交付指令。\n                full,budget=prepare_request_context(prompt,stage,'brief_intake',report=True)\n                continuation,continuation_budget=prepare_request_context(followup,stage,'brief_intake',report=True)\n            elif bounded_writing:\n                full,budget=prepare_request_context(\n                    prompt_with_settings(prompt,config,stage=stage),stage,'explicit_writing_inputs',report=True)\n                continuation,continuation_budget=prepare_request_context(\n                    prompt_with_settings(followup,config,stage=stage),stage,'explicit_writing_inputs',report=True)\n            else:\n                context,strategy=request_stage_instruction(project,stage,data)\n                full,budget=prepare_request_context(\n                    prompt_with_settings(context+prompt,config,stage=stage),stage,strategy,report=True)\n                continuation,continuation_budget=prepare_request_context(\n                    prompt_with_settings(continuation_instruction(project,stage,data)+followup,config,stage=stage),\n                    stage,'continuation_summary',report=True)\n            finish(receipt,'preparing','',skill_injection=config.get('skill_injection'),context_budget={\n                'initial':budget,'continuation':continuation_budget})\n            if native_claude:\n                from codex_tasks import task_file_reference\n                from stage_execution_service import register_download_inbox\n                # Claude Desktop 常常不能直接写本机路径、只给下载文件：要求下载件沿用目标文件名，\n                # 并登记目标，助手会从「下载」文件夹按文件名收回到原位置。\n                full = full + ('\\n\\n【交付方式】优先直接写入任务中给出的目标路径；若无法写入本机文件，'\n                               '请以可下载文件交付，文件名必须与目标路径的文件名完全一致，'\n                               '用户下载后助手会自动放回对应位置。')\n                task_file = task_file_reference(project, stage, full)\n                try:register_download_inbox(project, full)\n                except (OSError, ValueError) as exc:LOGGER.warning('下载收件箱登记失败：%s', exc)\n                reference = (f'请读取并执行本次任务文件：{task_file}\\n'\n                             '其中引用的 SKILL 和附件按任务需要读取，不重复加载无关内容。'\n                             '若无法读取本地文件，请提示启用文件访问并授权对应目录，或请用户上传文件；不要假定已读。')\n                return {'receipt':receipt,'prompt':reference,'task_file':str(task_file)}\n            if use_cli:return {'receipt':receipt,'prompt':full,'followup':continuation,\n                               'context_budget':{'initial':budget,'continuation':continuation_budget}}\n            result=prepare_task(project,title,stage,full,followup=continuation,setup_key=setup_key,\n                                delivery_summary='' if intake_only else writer_style_summary(config,stage))\n            result['receipt']=receipt;result['context_budget']={\n                'initial':budget,'continuation':continuation_budget};return result\n        except Exception as exc:finish(receipt,'failed',str(exc));raise\n    def dispatch(result):\n        receipt=result['receipt']\n        if receipt['duplicate']:\n            sessions=getattr(self,'flow_processes',{})\n            key=(str(project),stage,config['engine'],setup_key)\n            live=key in sessions and sessions[key].poll() is None\n            if retryable(receipt,live):\n                finish(receipt,'failed','上次发送结果未确认，且对应 Agent 窗口已关闭')\n                self.status.set('上次 Agent 发送未确认且窗口已关闭，正在自动重新启动…')\n                self.open_flow_agent(stage,label,prompt,followup,on_receipt,_config=config,intake_only=intake_only,new_session=new_session)\n                return\n            if not live:\n                finish(receipt,'failed','上次 Agent 窗口已关闭，请重新点击启动')\n                self.notifier.info('上次 Agent 窗口未在运行，任务状态已重置；请再次点击“手动制作分镜”。', title='请重新点击', modal=True);return\n            state={'preparing':'正在打开或发送','sent':'已发送','uncertain':'发送结果待核实'}[receipt['state']]\n            self.status.set('相同任务'+state+'，已复用记录，本次不重复发送。请在对应 Agent 窗口继续。');return\n        if use_cli:\n            launch_cli(result);return\n        try:done(result)\n        except Exception as exc:finish(receipt,'failed',str(exc));raise\n    def launch_cli(result):\n        receipt=result['receipt'];full=result['prompt'];continuation=result['followup']\n        sessions=getattr(self,'flow_processes',{});key=(str(project),stage,config['engine'],setup_key)\n        if key in sessions and sessions[key].poll() is None:\n            if new_session:\n                def close_old():\n                    from workflow_engines import close_for_restart\n                    try:close_for_restart(project,sessions[key])\n                    except Exception as exc:finish(receipt,'failed',str(exc));raise\n                def closed(_):\n                    sessions.pop(key,None)\n                    launch_cli(result)\n                self.status.set('正在结束空闲 Claude 会话，准备以新上下文重新创作…')\n                self.async_(close_old,closed);return\n            def submit():\n                try:\n                    if config['engine']=='qwen':\n                        from qwen_adapter import submit_existing\n                        text=submit_existing(sessions[key],continuation,title=title)\n                        return {'ok':True,'reason':text,'send_dispatched':True}\n                    from workflow_engines import submit_existing\n                    return submit_existing(sessions[key],continuation,title=title)\n                except Exception as exc:\n                    finish(receipt,'uncertain',str(exc));raise\n            def submitted(value):\n                outcome(receipt,value);self.status.set(value['reason'])\n                if not value['ok']:self.notifier.info(value['reason'], title='请检查 Agent 输入框', modal=True)\n            self.async_(submit,submitted);return\n        def launched(result):\n            sessions[key]=result['process'];self.flow_processes=sessions\n            if stage=='writing':\n                self._script_agent_launching=False\n                self.update_script_interrupt_button()\n            finish(receipt,'sent','启动时已传入初始任务',task_file=result['task_file'])\n            self.status.set('已启动 '+result['engine']+'，初始任务已自动提交，可在窗口继续讨论。')\n        def launch(slot=None):\n            try:return launch_interactive(project,stage,title,full,config,followup=continuation,slot=slot,\n                                          **({'new_session':True} if new_session else {}))\n            except Exception as exc:\n                from workflow_engines import release_stage_process_slot\n                release_stage_process_slot(slot)\n                finish(receipt,'failed',str(exc));raise\n        from workflow_engines import request_stage_process_slot, claim_stage_process_slot\n        request=request_stage_process_slot(project,stage)\n        if request['state']=='granted':\n            self.async_(lambda:launch(request['slot']),launched);return\n        from workflow_engines import cancel_stage_slot_request\n        pending = {'timer': None, 'cancelled': False, 'started': time.monotonic()}\n        def cleanup():\n            pending['cancelled'] = True\n            cancel_stage_slot_request(request['ticket'])\n            timer, pending['timer'] = pending['timer'], None\n            if timer is not None:\n                try:self.win.after_cancel(timer)\n                except tk.TclError:pass\n            if getattr(self, '_script_agent_queue', None) is pending:\n                self._script_agent_queue = None\n                self._script_agent_launching = False\n                self.update_script_interrupt_button()\n        def cancel():\n            cleanup()\n            finish(receipt,'failed','模型排队请求已取消，尚未启动 CLI')\n        pending['cancel'] = cancel\n        if stage == 'writing':\n            self._script_agent_queue = pending\n            self._script_agent_launching = True\n            self.update_script_interrupt_button()\n        self.status.set('模型请求排队中（第%d位），尚未启动 CLI；可点击中断，最多等待 120 秒。' % request['position'])\n        def poll_slot():\n            pending['timer'] = None\n            if pending['cancelled']:return\n            if self.root != project or getattr(self,'shutting_down',False) or getattr(self,'_closing',False):\n                cancel()\n                return\n            if time.monotonic() - pending['started'] >= 120:\n                cleanup()\n                message = '等待模型并发名额超过 120 秒，已退出排队；请检查已有 Agent 任务后重新发送。'\n                finish(receipt,'failed',message)\n                self.status.set(message)\n                return\n            claimed=claim_stage_process_slot(request['ticket'])\n            if claimed['state']=='queued':\n                self.status.set('模型请求排队中（第%d位），尚未启动 CLI；可点击中断，最多等待 120 秒。' % claimed['position'])\n                pending['timer'] = self.win.after(200,poll_slot);return\n            cleanup()\n            if claimed['state']=='granted':\n                if stage == 'writing':\n                    self._script_agent_launching = True\n                    self.update_script_interrupt_button()\n                self.status.set('已获得模型请求槽位，正在启动…')\n                self.async_(lambda:launch(claimed['slot']),launched);return\n            finish(receipt,'failed',claimed['reason'])\n            self.status.set(claimed['reason'])\n        pending['timer'] = self.win.after(200,poll_slot)\n    def done(result):\n        receipt=result['receipt']\n        clipboard_text=result['prompt']\n        task_file=result.get('task_file')\n        if task_file and Path(task_file).is_file():\n            try:clipboard_text=Path(task_file).read_text(encoding='utf-8')\n            except OSError:clipboard_text=result['prompt']\n        from prompt_window import copy_text\n        copy_text(self.win,clipboard_text)\n        if native_claude:\n            from workflow_settings import find_program\n            from platform_tools import launch_windows_app\n            program = find_program(config)\n            if config['engine'] == 'desktop-app':\n                app = config.get('display_model') or '桌面模型'\n                _deliver_desktop_app(self, finish, receipt, task_file, title,\n                                     clipboard_text, program, app, desktop_paste,\n                                     config.get('delivery') or 'paste')\n                return\n            launch_windows_app(program, 'Claude Desktop')\n            from codex_paste import paste_existing\n            def claude_pasted(value):\n                finish(receipt,'prepared' if value['ok'] else 'failed',value['reason'],task_file=task_file)\n                self.status.set(value['reason'])\n                level=getattr(self,'gate_level',None)\n                if value['ok'] and callable(level) and level()=='auto':\n                    # 全自动不拦截 Claude Desktop：它只能由用户点发送，这里明确提示，\n                    # 避免自动链看似停住却没有说明；状态栏原文也会转给三虎。\n                    message=('三虎全自动：'+label+' 的任务已粘贴到 Claude Desktop，'\n                             '请切到 Claude Desktop 手动点击发送；完成后产物会自动收回。')\n                    self.status.set(message)\n                    self.notifier.warning(message,title='请手动发送')\n            self.status.set('正在将本次任务粘贴到 Claude Desktop，请检查后手动发送…')\n            self.async_(lambda:paste_existing(title,clipboard_text,program=program,deadline_seconds=45),claude_pasted)\n            return\n        if config.get('desktop_program'):\n            from platform_tools import launch_windows_app\n            launch_windows_app(config['desktop_program'], 'Codex 桌面')\n        open_target(result['url'])\n        from codex_paste import paste_existing\n        def pasted(result):\n            finish(receipt,'prepared' if result['ok'] else 'failed',result['reason'])\n            self.status.set(result['reason'])\n        self.async_(lambda:paste_existing(result['title'],clipboard_text,result.get('draft_prompt',''),result.get('project',''),deadline_seconds=45 if result.get('mode')=='new' else 15),pasted)\n        self.status.set('正在将本次任务粘贴到 GPT 桌面，请在窗口中手动点击发送…')\n    self.async_(build,dispatch)\n"


class _Proc:
    def __init__(self, alive):
        self.alive = alive

    def poll(self):
        return None if self.alive else 0

    def __repr__(self):
        return '<proc %s>' % self.alive


class _Rec:
    def __init__(self, log, name):
        self._log, self._name = log, name

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return lambda *a, **k: self._log.append((self._name + '.' + name, a, sorted(k.items())))


class _Win(_Rec):
    def __init__(self, log):
        super().__init__(log, 'win')
        self.timers = []

    def after(self, ms, callback):
        self.timers.append(callback)
        self._log.append(('after', ms))
        return 'timer%d' % len(self.timers)


class _Host:
    def __init__(self, log, sessions):
        self.log = log
        self.worker = None
        self.root = Path('P')
        self.page_index = 3
        self._script_agent_queue = None
        self.projects = SimpleNamespace(info={'projects': [{'name': '样例剧', 'path': 'P'}]})
        self.status = _Rec(log, 'status')
        self.notifier = _Rec(log, 'notifier')
        self.win = _Win(log)
        self.flow_processes = {} if sessions is None else sessions
        self.shutting_down = False
        self._closing = False

    def gate_level(self):
        return 'auto'

    def async_(self, work, done=None, **kwargs):
        try:
            value = work()
        except Exception as exc:
            self.log.append(('async failed', type(exc).__name__, str(exc)))
            return
        self.log.append(('async ok', repr(value)))
        if done is not None:
            done(value)

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return lambda *a, **k: self.log.append((name, a, sorted(k.items())))


def _rec(log, name, value=None):
    def call(*a, **k):
        log.append((name, a, sorted(k.items())))
        return value(*a, **k) if callable(value) else value
    return call


SCENARIOS = (
    dict(stage='storyboard', engine='codex'),
    dict(stage='writing', engine='codex', kw={'intake_only': True}),
    dict(stage='storyboard', engine='claude', sessions={}),
    dict(stage='writing', engine='claude'),
    dict(stage='previs', engine='claude', live=True),
    dict(stage='writing', engine='claude', live=True, kw={'new_session': True}),
    dict(stage='storyboard', engine='qwen', live=True),
    dict(stage='storyboard', engine='claude', slot='queued', claims=('queued', 'granted')),
    dict(stage='writing', engine='claude', slot='queued', claims=('denied',)),
    dict(stage='writing', engine='claude', slot='queued', claims=('queued',), clock=(0, 0, 500)),
    dict(stage='storyboard', engine='claude', duplicate=True, state='sent', live=True),
    dict(stage='storyboard', engine='claude', duplicate=True, state='uncertain', retry=True),
    dict(stage='storyboard', engine='codex', duplicate=True, state='preparing'),
    dict(stage='storyboard', engine='claude-desktop-app'),
    dict(stage='storyboard', engine='desktop-app'),
    dict(stage='writing', engine='codex', skill_errors=['冲突']),
)


def _session(make, case):
    import agent_dispatch, codex_paste, codex_skill_sync, codex_tasks, native_apps, platform_tools, prompt_window
    import qwen_adapter, stage_execution_service, workflow_context, workflow_context_budget
    import workflow_context_controller, workflow_engines, workflow_settings
    log = []
    engine = case['engine']
    config = {'engine': engine, 'program': '', 'model': '', 'skill_injection': 'inj', 'display_model': '桌面模型'}
    key_holder = {}
    sessions = dict(case['sessions']) if 'sessions' in case else None   # 场景表是共享常量，不能被上一轮写脏
    if case.get('live'):
        sessions = key_holder
    claims = list(case.get('claims', ()))
    clock = list(case.get('clock', (0,) * 50))
    receipt = {'duplicate': case.get('duplicate', False), 'state': case.get('state', 'preparing'), 'id': 'R'}
    patches = [
        (workflow_settings, 'current', lambda root, stage: dict(config)),
        (workflow_settings, 'writer_style_summary', lambda c, s: '风格'),
        (workflow_settings, 'validate_selected_skills', _rec(log, 'validate')),
        (workflow_settings, 'freeze_skills', lambda c: dict(c, frozen=True)),
        (workflow_settings, 'find_program', lambda c: 'prog.exe'),
        (workflow_engines, 'prompt_with_settings', lambda p, c, stage: 'PS[' + p + ']'),
        (workflow_engines, 'launch_interactive', _rec(log, 'launch', lambda *a, **k: {
            'process': _Proc(True), 'engine': engine, 'task_file': 'tf'})),
        (workflow_engines, 'claude_session_stale', lambda root, stage: False),
        (workflow_engines, 'request_stage_process_slot', _rec(log, 'request_slot', lambda *a: {
            'state': case.get('slot', 'granted'), 'slot': 'S0', 'ticket': 'T', 'position': 2})),
        (workflow_engines, 'claim_stage_process_slot', _rec(log, 'claim_slot', lambda t: {
            'state': claims.pop(0) if claims else 'queued', 'slot': 'S1', 'position': 1, 'reason': '名额被拒'})),
        (workflow_engines, 'cancel_stage_slot_request', _rec(log, 'cancel_slot')),
        (workflow_engines, 'release_stage_process_slot', _rec(log, 'release_slot')),
        (workflow_engines, 'submit_existing', _rec(log, 'submit', {'ok': False, 'reason': '续发待核实'})),
        (workflow_engines, 'close_for_restart', _rec(log, 'close_restart')),
        (qwen_adapter, 'submit_existing', _rec(log, 'qwen_submit', '千问已续发')),
        (qwen_adapter, 'window_title', lambda name, stage, page: 'QWEN ' + name + stage + str(page)),
        (agent_dispatch, 'signature', lambda *a: 'sig:' + a[0]),
        (agent_dispatch, 'claim', _rec(log, 'claim', lambda *a: dict(receipt))),
        (agent_dispatch, 'finish', _rec(log, 'finish')),
        (agent_dispatch, 'outcome', _rec(log, 'outcome')),
        (agent_dispatch, 'retryable', lambda r, live: case.get('retry', False)),
        (codex_tasks, 'prepare_task', _rec(log, 'prepare', lambda *a, **k: {
            'url': 'codex://u', 'title': 'T', 'prompt': 'PROMPT', 'mode': 'new', 'project': 'proj'})),
        (codex_tasks, 'task_file_reference', lambda project, stage, full: Path('missing_task.md')),
        (codex_skill_sync, 'sync_codex_skills', lambda: {'errors': case.get('skill_errors', []), 'conflicts': []}),
        (stage_execution_service, 'project_context', lambda project: {'ctx': 1}),
        (stage_execution_service, 'register_download_inbox', _rec(log, 'inbox')),
        (workflow_context, 'continuation_instruction', lambda project, stage, data: 'CI:'),
        (workflow_context, 'snapshot', lambda value: {'snap': value}),
        (workflow_context_controller, 'request_stage_instruction', lambda project, stage, data: ('CTX:', 'full_stage')),
        (workflow_context_budget, 'prepare_request_context',
         lambda text, stage, strategy, report: (text + '|' + strategy, {'s': strategy})),
        (prompt_window, 'copy_text', _rec(log, 'copy')),
        (codex_paste, 'paste_existing', _rec(log, 'paste', {'ok': True, 'reason': '已粘贴'})),
        (platform_tools, 'launch_windows_app', _rec(log, 'launch_app')),
        (native_apps, 'open_blender', _rec(log, 'blender')),
        (module, 'open_target', _rec(log, 'open_target')),
        (module, '_deliver_desktop_app', _rec(log, 'deliver_desktop')),
        (module.time, 'monotonic', lambda: clock.pop(0) if clock else 0),
    ]
    stack = [mock.patch.object(owner, name, value) for owner, name, value in patches]
    for item in stack:
        item.start()
    try:
        fn = make()
        host = _Host(log, sessions)
        if case.get('live'):
            import hashlib, json
            frozen = dict(config, frozen=True) if case['stage'] == 'writing' and not case.get('kw', {}).get('intake_only') else config
            setup = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
            key_holder[(str(host.root), case['stage'], engine, setup)] = _Proc(True)
        try:
            fn(host, case['stage'], '标签', '提示词', None, lambda r: log.append(('receipt', dict(r))),
               **case.get('kw', {}))
        except Exception as exc:
            log.append(('raised', type(exc).__name__, str(exc)))
        for _ in range(4):
            timers, host.win.timers = host.win.timers, []
            for timer in timers:
                timer()
    finally:
        for item in reversed(stack):
            item.stop()
    return [_plain(item) for item in log]


class OpenFlowAgentEquivalence(unittest.TestCase):
    def test_matches_legacy(self):
        for case in SCENARIOS:
            with self.subTest(case=case):
                expected = _session(lambda: legacy(module, LEGACY, 'open_flow_agent'), case)
                actual = _session(lambda: module.IdeaChatMixin.open_flow_agent, case)
                self.assertEqual(actual, expected)
                self.assertGreaterEqual(len(expected), 2)   # 对照不能是空对空：流程真的走了几步


if __name__ == '__main__':
    unittest.main()
