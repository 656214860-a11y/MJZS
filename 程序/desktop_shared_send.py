"""共享输入框的发送分流（R2898，任务书轮 4）：``/`` 命令与自由文本 → 当前阶段既有入口。

- 剧本准备（``script``）保留完整创意对话链；
- 初步分镜（``storyboard``）走分镜批量直连链（并传递输入框补充要求）；
- 剧本结构（``script_structure``）及全部后续制作阶段默认走直连 API 文件输出模式
  （``send_stage_file``），严格按 SKILL 与用户要求只输出阶段文件、不对话；若显式选择
  桌面/CLI 引擎且该阶段支持 Agent 流程，再回落 ``open_flow_agent``。
会员闸门复用 ``account.stage_gate``；上游完成门禁由本模块在发送前统一执行。
"""
from __future__ import annotations

from pathlib import Path

import infra.app_logging as app_logging
import domain.skill_command as skill_command
import ui.desktop_shared_input_extras as input_extras
from contract import pet_bus
from orchestrator.storyboard_plan_service import storyboard_work_plan
from orchestrator.storyboard_selection import selected_many, sync_structured_script

# pet 阶段 → open_flow_agent 流程名；键集合必须始终是 pet_bus.STAGES 的子集。
FLOW_FOR_STAGE = {'script': 'writing', 'storyboard': 'storyboard', 'assets': 'assets',
                  'keyframe': 'frames', 'previs': 'previs', 'video': 'video_prompt',
                  'audio': 'audio'}
FLOW_LABEL = {'writing': '剧本准备', 'storyboard': '初步分镜', 'assets': '资产管理',
              'frames': '首帧管理', 'previs': '白模预演', 'video_prompt': '视频提示词',
              'audio': '配音与字幕'}
# 没有对话流程、但页面登记了发送动作的阶段：输入框里有字时照样开动这一步，并说明文字
# 用不上（%s＝阶段名）；文字留在输入框里，不清空。
STAGE_ACTION_TEXT_UNUSED = '「%s」这一步不使用输入框里的文字：发送键启动的是本页的制作，文字仍留在输入框。'
# 初步分镜页及各阶段共享输入框占位提示（REQ-S01-114：统一前缀＋阶段尾句，全部由
# ui.desktop_shared_input_extras.stage_placeholder 派生，接口与取值语义不变）。
STORYBOARD_PLACEHOLDER = input_extras.stage_placeholder('storyboard')
DEFAULT_STAGE_PLACEHOLDER = input_extras.stage_placeholder('')
STAGE_PLACEHOLDERS = {
    'script': input_extras.stage_placeholder('script'),
    'script_structure': input_extras.stage_placeholder('script_structure'),
    'storyboard': STORYBOARD_PLACEHOLDER,
}
_STORYBOARD_PREP_ATTR = '_storyboard_send_prep'


def sync_stage_placeholder(box, stage):
    """宿主注入的占位同步：输入框不反向导入发送分流。"""
    if box is None or not hasattr(box, '_placeholder'):
        return
    hint = STAGE_PLACEHOLDERS.get(str(stage or ''), DEFAULT_STAGE_PLACEHOLDER)
    if getattr(box, '_placeholder_active', False):
        try:
            box._remove_placeholder()
        except Exception:
            app_logging.swallowed()
    box._placeholder = hint
    if hint and not str(box.get('1.0', 'end-1c') or '').strip():
        try:
            box._restore_placeholder()
        except Exception:
            app_logging.swallowed()


def stage_for_index(index):
    """页序号 → pet 阶段；非阶段页（参考网站／会员账户／首页）返回空串。"""
    try:
        number = int(index)
    except (TypeError, ValueError):
        return ''
    return pet_bus.STAGES[number] if 0 <= number < len(pet_bus.STAGES) else ''


def current_stage(desktop):
    return stage_for_index(getattr(desktop, 'page_index', None))


def _say(desktop, text):
    status = getattr(desktop, 'status', None)
    if status is not None:
        try:
            status.set(str(text))
        except Exception:
            app_logging.swallowed()
    getattr(desktop, 'reply_note', lambda *a, **k: None)('progress', current_stage(desktop), text)


def upstream_send_error(project, stage, status=None):
    """发送前统一门禁：上游空白／阻塞则拒绝并提示，放行返回空串。

    有 ``stage_parallel`` 门禁的阶段走 ``evaluate``；无门禁行时看紧邻上游的完成证据，
    显式跳过（skipped）豁免。``script`` 与无项目放行，简报门禁仍由宿主发送路径负责。
    ``storyboard`` 使用 ``storyboard_send_readiness``（REQ-S03-55），说明写入状态栏。
    """
    stage = str(stage or '')
    if not stage or stage == 'script' or stage not in pet_bus.STAGES:
        return ''
    if project in (None, ''):
        # REQ-S13-54：无项目放行是本门禁自己的契约，简报门禁由宿主发送路径负责。
        return ''
    try:
        import orchestrator.stage_parallel as stage_parallel
        row = stage_parallel.gate_for(stage)
    except Exception:
        return ''
    if row is not None:
        try:
            result = stage_parallel.evaluate(project, stage)
        except Exception:
            return ''
        if result.get('verdict') == stage_parallel.UPSTREAM_BLANK:
            return '请先完成/确认「%s」阶段' % stage_parallel.label(result.get('from'))
        if not result.get('ok'):
            return stage_parallel.blocked_text(result) or '上游阶段未完成，请先处理'
        return ''
    index = pet_bus.STAGES.index(stage)
    if index <= 0:
        return ''
    upstream = pet_bus.STAGES[index - 1]
    try:
        import orchestrator.stage_parallel as _sp
        if _sp.stage_state(project, upstream) in _sp.EXEMPT_STATES:
            return ''
    except Exception:
        app_logging.swallowed()
    if stage == 'storyboard' and upstream == 'script_structure':
        try:
            from orchestrator.stage_completion_service import storyboard_send_readiness
            sendable, note, _filled = storyboard_send_readiness(project)
        except Exception:
            return ''
        if sendable and note and status is not None:
            try:
                status.set(str(note))
            except Exception:
                app_logging.swallowed()
        return '' if sendable else (note or '请先到「剧本结构」页确认一份结构剧本，再回来发送')
    try:
        from orchestrator.stage_completion_service import completion_evidence
        ok, detail = completion_evidence(project, upstream)
    except Exception:
        return ''
    if ok:
        return ''
    return '请先完成/确认「%s」阶段（%s）' % (pet_bus.stage_name(upstream), detail or '上游成果未完成')


def _notify_error(desktop, text):
    notifier = getattr(desktop, 'notifier', None); getattr(desktop, 'reply_note', lambda *a, **k: None)('error', current_stage(desktop), text)
    error = getattr(notifier, 'error', None)
    if callable(error):
        try:
            error(str(text))
            return
        except Exception:
            app_logging.swallowed()
    _say(desktop, str(text))


def _draft_text(desktop):
    reader = getattr(desktop, 'draft_text', None)
    if not callable(reader):
        return ''
    try:
        return str(reader() or '')
    except Exception:
        return ''


def _account_block(desktop, stage):
    """会员闸门：``account.stage_gate`` 放行返回空串；判不出时放行（页面自身闸门仍在）。"""
    account = getattr(desktop, 'account', None)
    gate = getattr(account, 'stage_gate', None)
    if not callable(gate):
        return ''
    try:
        return str(gate(stage) or '')
    except Exception:
        app_logging.swallowed()
        return ''


def _goto_stage(desktop, stage):
    """``/阶段`` 命令的切页：走 ``show_stage`` 同步建页（含锁定路由）。技能命令不换页。"""
    show = getattr(desktop, 'show_stage', None)
    if callable(show):
        try:
            show(stage)
            return True
        except Exception as exc:
            app_logging.swallowed()
            _notify_error(desktop, '切换阶段失败：%s' % exc)
            return False
    return False


# SEND-2／REQ-S01-105：没登记发送动作、也没有对话流程的阶段，空发送＝手动制作入口。
EMPTY_SEND_STAGES = ('animatic', 'continuity', 'final', 'edit', 'delivery')


def empty_send_action(desktop, stage, parent=None):
    """空发送＝这一阶段的手动制作动作；真正开始制作才受理（REQ-S01-105）。"""
    if stage not in EMPTY_SEND_STAGES:
        return None
    from orchestrator.stage_models import manual_command
    def action(stage=stage):
        if stage not in ('animatic', 'continuity', 'final', 'edit', 'delivery'):
            raise ValueError('未登记空发送动作的阶段：%r' % stage)
        reason = _account_block(desktop, stage)
        if reason:
            _say(desktop, reason)
            return False
        if stage == 'animatic':
            # 注册器的 animatic 呈现分支需要注入 L4 动作；这里直接用同一呈现语义切页。
            present = getattr(desktop, 'present_stage', None)
            if callable(present):
                from orchestrator.stage_handler_registry import StagePresentation
                if present(StagePresentation.SHOW_ANIMATIC, '') is False:
                    return False
            _say(desktop, '已切到「分镜预演」：在页面上选择参考图与临时声音，再点「生成分镜预演」。')
            return ''
        import orchestrator.stage_handler_registry as stage_handler_registry
        result = stage_handler_registry.start(desktop, stage, trigger='manual')
        if result is False:
            return False
        if isinstance(result, str) and result:
            _say(desktop, result)
            return False
        if stage == 'continuity':
            produce = getattr(desktop, 'generate_continuity_ledger', None)
        elif stage == 'final':
            produce = getattr(desktop, 'make_final_storyboard', None)
        else:
            import orchestrator.stage_exec as stage_exec
            produce = lambda: stage_exec.show(desktop, stage, parent)
        if not callable(produce):
            return False
        safe = getattr(desktop, 'safe', None)
        return safe(produce) if callable(safe) else produce()
    return manual_command(desktop, stage, action, parent)


def _open_flow(desktop, stage, prompt):
    """派发到 ``open_flow_agent``；失败回 False 让输入框保留原文。"""
    flow = FLOW_FOR_STAGE.get(stage)
    if not flow:
        return False
    reason = _account_block(desktop, stage)
    if reason:
        _say(desktop, reason)
        return False
    launch = getattr(desktop, 'open_flow_agent', None)
    if not callable(launch):
        _say(desktop, '当前页面还没有 Agent 发送入口')
        return False
    try:
        launch(flow, FLOW_LABEL[flow], prompt)
    except Exception as exc:
        _notify_error(desktop, '发送失败：%s' % exc)
        return False
    return True


def _clear_storyboard_prep(desktop, token=None):
    if token is not None and getattr(desktop, '_storyboard_send_token', None) is not token:
        return False
    desktop._storyboard_send_prep = False
    desktop._storyboard_send_ticket = None
    desktop._storyboard_send_token = None
    return True


def _storyboard_prep_active(desktop):
    """准备期防重；已取消／替换的旧 ticket 不永久锁住下一次发送。"""
    if not getattr(desktop, _STORYBOARD_PREP_ATTR, False):
        return False
    ticket = getattr(desktop, '_storyboard_send_ticket', None)
    accepts = getattr(getattr(desktop, 'background_tasks', None), 'accepts', None)
    if ticket is not None and callable(accepts) and not accepts(ticket):
        _clear_storyboard_prep(desktop)
        return False
    return True


def _window_alive(desktop):
    win = getattr(desktop, 'win', None)
    if win is None or not hasattr(win, 'winfo_exists'):
        return True
    try:
        return bool(win.winfo_exists())
    except Exception:
        return False


def send_storyboard(desktop, text='', *, only=None):
    """初步分镜窄入口（REQ-S03-54）：空发送／自由文本／点名技能共用，不直接 ``_open_flow``。

    ``text`` 是补充要求（不替代结构剧本全文）；``only`` 为点名技能名单时只跑这些，
    不读、不改 ✦ 勾选；``only is None`` 时走勾选默认技能。真正进入异步准备才返回 True。
    """
    if getattr(desktop, 'root', None) is None:
        _say(desktop, '请先选择项目')
        return False
    if _storyboard_prep_active(desktop) or getattr(desktop, 'worker', False):
        _say(desktop, '正在准备分镜任务，请稍候再发送。')
        return False
    request_text = str(text or '').strip()
    named = [str(name) for name in only] if only else None
    project = desktop.root
    model_snap = None
    shared = getattr(desktop, 'shared_input', None)
    snap = getattr(shared, 'request_model', None) if shared is not None else None
    if snap is not None:
        model_snap = snap

    def action():
        reason = _account_block(desktop, 'storyboard')
        if reason:
            _say(desktop, reason)
            return False
        return _start_storyboard_batch(desktop, project, request_text, named, model_snap)

    # 初步分镜已改用底部共享输入框（自带模型下拉与 ✦ 技能），点击发送直接执行，不再弹旧手动确认窗。
    safe = getattr(desktop, 'safe', None)
    try:
        result = safe(action) if callable(safe) else action()
    except Exception as exc:
        app_logging.swallowed()
        _notify_error(desktop, '发送失败：%s' % exc)
        return False
    return result is True


def _named_skill_config(project, names, model_snapshot=None):
    """点名执行：内存里收窄 stage_skills，不写 stage_config。"""
    from orchestrator.workflow_settings import current
    import orchestrator.skill_registry as skill_registry
    config = dict(current(project, 'storyboard', model_snapshot=model_snapshot))
    registry = skill_registry.default_registry(project=project)
    paths, missing = [], []
    for name in names:
        item = registry.getById(name)
        if item is None:
            for entry in registry.getAll():
                if str(getattr(entry, 'name', '') or '') == name:
                    item = entry
                    break
        if item is None:
            missing.append(name)
            continue
        paths.append(str(item.path))
    if missing and not paths:
        raise ValueError('没有这个技能或子引擎：/%s' % missing[0])
    config['stage_skills'] = paths
    config['skills'] = []
    config['skill'] = ''
    config['named_execution'] = True
    config['named_skills'] = list(names)
    return config


def open_storyboard_skill(desktop, key=None, *, request_text='', only=None, model_snapshot=None):
    """批量准备分镜任务；实现留在发送模块，Desktop 只保留兼容包装。"""
    project = desktop.root
    if project is None:
        return False
    if _storyboard_prep_active(desktop):
        return False
    request_text = str(request_text or '').strip()
    named = [str(name) for name in only] if only else None
    batch = {}
    token = object()
    desktop._storyboard_send_prep = True
    desktop._storyboard_send_ticket = None
    desktop._storyboard_send_token = token

    def work():
        try:
            from orchestrator.storyboard_selection import selected_many
            scripts = list(selected_many(project, 'script'))
            existing = list(selected_many(project, 'storyboard'))
        except Exception as exc:
            return ('err', '读取结构剧本输入失败：' + str(exc))
        try:
            from stage_execution_service import storyboard_produced_scripts as produced_scripts
            from orchestrator.workflow_tasks import storyboard_batch_prompt
            made = produced_scripts(project)
            already = [path for path in scripts if path in made]
            prompt, followup = storyboard_batch_prompt(project, scripts, existing)
            if request_text:
                supplement = '\n补充要求：' + request_text
                prompt = prompt + supplement
                followup = followup + supplement
            if named:
                prompt = ('点名执行：只运行技能 ' + '、'.join(named)
                          + '，不附带未点名的默认勾选。\n' + prompt)
                followup = '点名执行：只运行技能 ' + '、'.join(named) + '。\n' + followup
            batch.update(prompt=prompt, followup=followup, named=named)
            if not already:
                return ('ok', '正在启动分镜制作 agent…')
            return ('ok', '已跳过 ' + str(len(already)) + ' 个已制作分镜的剧本：'
                    + '、'.join(Path(path).name for path in already) + '；继续处理其余剧本／分镜。')
        except Exception as exc:
            return ('err', str(exc))

    def finish(payload):
        if not _clear_storyboard_prep(desktop, token):
            return
        if (desktop.root != project or getattr(desktop, 'shutting_down', False)
                or not _window_alive(desktop)):
            return
        kind, value = payload if isinstance(payload, tuple) and len(payload) == 2 else ('ok', payload)
        if kind == 'err':
            _say(desktop, value)
            return
        config = None
        if batch.get('named'):
            try:
                config = _named_skill_config(project, batch['named'], model_snapshot)
            except Exception as exc:
                _say(desktop, str(exc))
                return
        elif model_snapshot is not None:
            from orchestrator.workflow_settings import current
            try:
                config = current(project, 'storyboard', model_snapshot=model_snapshot)
            except Exception:
                config = None
        kwargs = {'_config': config} if config is not None else {}
        desktop._storyboard_request_text = request_text
        desktop.open_flow_agent('storyboard', '初步分镜', batch['prompt'], batch['followup'], **kwargs)
        if batch.get('named'):
            _say(desktop, '点名执行：' + '、'.join(batch['named']) + '。' + str(value or ''))
        else:
            _say(desktop, value)

    try:
        ticket = desktop.async_(work, finish)
    except Exception:
        _clear_storyboard_prep(desktop, token)
        raise
    if getattr(desktop, '_storyboard_send_token', None) is token:
        desktop._storyboard_send_ticket = ticket
    return ticket


def _read_status(desktop):
    status = getattr(desktop, 'status', None)
    if not hasattr(status, 'get'):
        return ''
    try:
        return str(status.get() or '')
    except Exception:
        app_logging.swallowed()
        return ''


def _ensure_storyboard_script(project):
    if project is None:
        return
    try:
        if not selected_many(project, 'script'):
            sync_structured_script(project)
    except (OSError, ValueError, TypeError):
        app_logging.swallowed()


def _storyboard_idle_note(project):
    if project is None:
        return ''
    try:
        plan = storyboard_work_plan(project)
    except (OSError, ValueError, KeyError, TypeError):
        app_logging.swallowed()
        return ''
    if not plan['scripts']:
        return '未选择结构剧本，请先在上方勾选一份结构剧本再发送'
    if not plan['todo'] and not plan['revise']:
        return '当前勾选的结构剧本均已生成并采用分镜；如需重做请先取消采用或勾选其他剧本'
    return ''


def _start_storyboard_batch(desktop, project, request_text, named, model_snap):
    """经 Desktop 的 L4 适配器进入统一阶段启动入口。"""
    starter = getattr(desktop, 'start_storyboard_send', None)
    if not callable(starter):
        _say(desktop, '当前页面还没有分镜发送入口')
        return False
    _ensure_storyboard_script(project)
    before = _read_status(desktop)
    started = starter(project, request_text, named, model_snap) is True
    if not started and _read_status(desktop) == before:
        note = _storyboard_idle_note(project)
        if note:
            _say(desktop, note)
    return started


def _read_stage_skills_text(project, stage, only=None):
    """读取点名技能（/技能）或本阶段已勾选／默认技能的正文，供直连 API 严格按 SKILL 输出文件。"""
    try:
        import orchestrator.skill_registry as skill_registry
        import orchestrator.stage_config as stage_config
        registry = skill_registry.default_registry(project=project)
    except Exception:
        return ''
    names = list(only or ())
    if not names:
        try:
            entry = stage_config.get(project, stage) or {}
            names = list(entry.get('skills') or ())
        except Exception:
            names = []
    items = []
    for name in names:
        found = registry.getById(name)
        if found is None:
            found = next((s for s in registry.getAll() if str(getattr(s, 'name', '') or '') == name), None)
        if found is not None:
            items.append(found)
    if not items and not only:
        items = list(registry.getByStage(stage))[:2]
    chunks = []
    for item in items:
        path = getattr(item, 'path', None)
        if path and Path(path).is_file():
            try:
                body = Path(path).read_text(encoding='utf-8-sig', errors='replace').strip()
            except OSError:
                body = ''
            if body:
                chunks.append('【SKILL：%s】\n%s' % (getattr(item, 'name', Path(path).stem), body))
    return '\n\n'.join(chunks)


def _is_direct_api_record(model_pool, cand, rec):
    """仅可直连的 API 模型才走阶段文件直连；排除 Desktop／CLI 及未配好地址的条目。"""
    if not cand or not isinstance(rec, dict):
        return False
    if model_pool.call_mode(rec, cand) != 'API':
        return False
    return not model_pool.model_admission_error(
        rec, require_context_length=False, require_certified=False)


def _resolve_stage_api_target(project, stage, *, only=None, model_snapshot=None):
    """为非聊天阶段解析直连 API 模型配置与 SKILL 正文；未配置或显式选了桌面/CLI 引擎则返回 (None, '')。"""
    import infra.model_pool as model_pool
    import orchestrator.stage_config as stage_config
    program = Path(__file__).resolve().parent
    records = model_pool.pool(program=program)
    if not records:
        return None, ''
    chosen = ''
    record = None
    if isinstance(model_snapshot, dict) and model_snapshot.get('id'):
        cand = str(model_snapshot.get('id') or '').strip()
        rec = model_snapshot.get('record') or records.get(cand)
        if _is_direct_api_record(model_pool, cand, rec):
            chosen, record = cand, rec
    elif isinstance(model_snapshot, (tuple, list)) and len(model_snapshot) == 2 and model_snapshot[0]:
        cand = str(model_snapshot[0] or '').strip()
        rec = model_snapshot[1] if isinstance(model_snapshot[1], dict) else records.get(cand)
        if _is_direct_api_record(model_pool, cand, rec):
            chosen, record = cand, rec
    if not chosen:
        try:
            entry = stage_config.get(project, stage) or {}
            selected = str(entry.get('model') or '').strip()
        except Exception:
            selected = ''
        if selected and selected != model_pool.AUTO:
            rec = records.get(selected)
            if not _is_direct_api_record(model_pool, selected, rec):
                return None, ''
            chosen, record = selected, rec
        else:
            try:
                import writing_api
                cap = writing_api.capture_request_model(project)
                cand = str((cap or {}).get('id') or '').strip()
                rec = (cap or {}).get('record') or records.get(cand)
                if _is_direct_api_record(model_pool, cand, rec):
                    chosen, record = cand, rec
            except Exception:
                app_logging.swallowed()
            if not chosen:
                for cand, rec in records.items():
                    if _is_direct_api_record(model_pool, cand, rec):
                        chosen, record = cand, rec
                        break
    if not chosen or not isinstance(record, dict):
        return None, ''
    config = {'engine': 'qwen', 'model': chosen, 'api': True}
    skill_text = _read_stage_skills_text(project, stage, only=only)
    return config, skill_text


def _active_stage_document(desktop, stage):
    if stage == 'script_structure':
        box = getattr(desktop, 'script_structure_editor_preview_content_box', None)
        active = getattr(box, 'active', None)
        if isinstance(active, dict) and active.get('path'):
            return active['path']
    return None


def _finish_stage_file_ui(desktop, stage, job):
    results = list(getattr(job, 'results', None) or ())
    entry = results[0] if results else {'ok': False, 'error': '未返回结果', 'path': '', 'stopped': False}
    label = pet_bus.stage_name(stage)
    if entry.get('stopped'):
        _say(desktop, '「%s」直连输出已停止。' % label)
        return
    if not entry.get('ok'):
        _say(desktop, '「%s」输出未完成：%s' % (label, entry.get('error') or '未知原因'))
        return
    target = Path(entry['path']) if entry.get('path') else None
    if stage == 'script_structure' and target is not None:
        try:
            sync_structured_script(desktop.root)
        except Exception:
            app_logging.swallowed()
    text = '「%s」已按技能输出文件：%s' % (label, target.name if target is not None else '')
    _say(desktop, text); getattr(desktop, 'reply_note', lambda *a, **k: None)('artifact', stage, text, path=str(target) if target is not None else '', title=target.name if target is not None else '')
    if hasattr(desktop, 'pet_report'):
        try:
            desktop.pet_report(stage, text)
        except Exception:
            app_logging.swallowed()
    panel = getattr(desktop, 'files_panel', None)
    if panel is not None and callable(getattr(panel, 'fill_script_list', None)):
        try:
            panel.fill_script_list()
        except Exception:
            app_logging.swallowed()
    if stage == 'script_structure' and target is not None:
        page_obj = getattr(desktop, 'script_structure_page', None)
        if page_obj is not None and callable(getattr(page_obj, 'show_document', None)):
            try:
                page_obj.show_document(target)
            except Exception:
                app_logging.swallowed()


def send_stage_file(desktop, stage, text='', *, only=None):
    """非聊天阶段（S02 剧本结构及各后续制作阶段）统一入口：直连 API 按 SKILL 仅输出阶段文件，不对话。"""
    import queue
    from orchestrator import storyboard_direct_api
    project = getattr(desktop, 'root', None)
    if project is None:
        _say(desktop, '请先选择项目')
        return False
    reason = _account_block(desktop, stage)
    if reason:
        _say(desktop, reason)
        return False
    shared = getattr(desktop, 'shared_input', None)
    snap = getattr(shared, 'request_model', None) if shared is not None else None
    config, skill_text = _resolve_stage_api_target(project, stage, only=only, model_snapshot=snap)
    if config is None:
        return False
    messages = queue.Queue()
    active_path = _active_stage_document(desktop, stage)
    try:
        job = storyboard_direct_api.launch_stage_file(
            project, stage, config, skill_text,
            instruction=str(text or '').strip(), active_path=active_path, report=messages.put)
    except ValueError as exc:
        _say(desktop, str(exc))
        return False
    label = pet_bus.stage_name(stage)
    _say(desktop, '正在直连 %s 按技能输出「%s」阶段文件…' % (config['model'], label))
    win = getattr(desktop, 'win', None)
    if win is None or not hasattr(win, 'after'):
        return True

    def drain():
        while True:
            try:
                msg = messages.get_nowait()
            except queue.Empty:
                break
            _say(desktop, msg)
        if job.is_alive():
            if _window_alive(desktop):
                win.after(300, drain)
        elif _window_alive(desktop):
            _finish_stage_file_ui(desktop, stage, job)

    win.after(300, drain)
    return True


def _send_free(desktop, stage, text):
    """自由文本：script 走对话链；storyboard 走分镜链；其余制作阶段直连 API 按 SKILL 仅输出阶段文件。"""
    text = str(text or '').strip()
    if not text:
        return False
    if not stage:
        _say(desktop, '请先打开一个制作阶段页面')
        return False
    if stage == 'script':
        sender = getattr(desktop, 'send_message', None)
        if not callable(sender):
            _say(desktop, '剧本准备页尚未就绪，请稍后重试')
            return False
        safe = getattr(desktop, 'safe', None)
        if callable(safe):
            safe(sender)
        else:
            sender()
        # send_message 只在真正受理时清空输入框；简报缺项等早退路径保留原文。
        return not _draft_text(desktop)
    if stage == 'storyboard':
        return send_storyboard(desktop, text)
    before = _read_status(desktop)
    if send_stage_file(desktop, stage, text):
        return True
    if _read_status(desktop) != before:
        return False
    if stage in FLOW_FOR_STAGE:
        return _open_flow(desktop, stage, text)
    _say(desktop, '「%s」请先在右下角模型下拉框选择一个可用的 API 模型，再发送要求（按技能直接输出阶段文件，不对话）。'
         % pet_bus.stage_name(stage))
    return False


def _skill_items(desktop):
    shared = getattr(desktop, 'shared_input', None)
    items = getattr(shared, 'skill_items', None)
    if callable(items):
        try:
            return list(items())
        except Exception:
            app_logging.swallowed()
    try:
        import orchestrator.skill_registry as skill_registry
        return list(skill_registry.default_registry(
            project=getattr(desktop, 'root', None)).getAll())
    except Exception:
        return []


def _resolve_skill(desktop, parsed):
    """技能与用户包命令统一解析为注册入口的 (目标阶段, 技能文件)。"""
    kind = str(parsed.get('kind') or '')
    name = str(parsed.get('name') or '')
    stage = str(parsed.get('stage') or '') or current_stage(desktop)
    # 两种类别共用注册器已校验的入口与项目层优先级。
    if kind not in ('skill', 'engine'):
        return '', ''
    for item in _skill_items(desktop):
        if str(getattr(item, 'name', item) or '') == name:
            target = str(getattr(item, 'stage', '') or '') or stage
            path = getattr(item, 'path', None)
            return target, Path(path) if path else None
    return '', ''


def _skill_prompt(name, path, rest):
    lines = ['请完整读取并严格遵循本地技能文件：%s' % (path or name)]
    lines.append('技能：%s' % name)
    lines.append('任务：' + rest if rest else '请按该技能完成当前阶段任务。')
    return '\n'.join(lines)


def _skill_send_notices(injection):
    """REQ-S01-118：冻结降级信号 → 对话区/状态栏各一条说明（发送仍走已装下部分）。"""
    injection = injection or {}
    notices = []
    if injection.get('skipped') or injection.get('degraded'):
        notices.append('技能引用装不下本次请求，已省略部分引用')
    if any(isinstance(row, dict) and str(row.get('status')) == 'resource'
           for row in injection.get('references') or ()):
        notices.append('技能含无法随请求发送的文件，已省略')
    return notices


def _skill_send_refusal_text(exc):
    """REQ-S01-118：冻结拒绝按类别翻译说明；不认识的错误原样转述。"""
    text = str(exc)
    if 'context_window_unknown' in text or '未填写上下文窗口' in text:
        return '模型没有填上下文长度，请在模型管理里补充'
    if '超出预算' in text or '超过上限' in text or '预算不足' in text or '正文合计' in text:
        return '技能正文超出模型上下文'
    return text


def _skill_send_notice(desktop, text, *, model=None):
    """技能发送的应用内说明：状态栏一句＋对话区一条不署名的 notice（REQ-S01-118）。"""
    text = str(text or '').strip()
    if not text:
        return
    desktop.status.set(text)
    try:
        import domain.idea_chat as idea_chat
        idea_chat.append(desktop.idea_chat_context(), 'notice', text,
                         model=model, gateway=desktop.idea_chat_gateway())
    except Exception:
        app_logging.swallowed()
    desktop.show_conversation()


def send_skill_request(desktop, name, path, rest):
    """REQ-S01-118：剧本页 /技能名 发送。

    接口模型（直连 API）时复用 ``send_message`` 同一条应用内请求链：只把本条点名
    技能（不夹带阶段默认勾选集）经 ``freeze_skills`` 冻结后装进请求，不再让 Agent
    去读本地技能文件；引用被省略或含不可发送资源时降级并说明，正文装不下或模型
    没填上下文长度时拒绝并说明，两处说明都以 ``notice`` 落对话区＋状态栏各一次。
    非接口模型返回 ``False``，由 ``_send_skill`` 回落到原命令行链，行为逐字不变。
    """
    import domain.idea_chat as idea_chat
    import writing_api
    import orchestrator.workflow_settings as workflow_settings
    request_model = writing_api.capture_request_model(desktop.root)
    if not request_model['id']:
        return False
    controller = desktop.idea_chat_controller
    if controller.requesting:
        raise ValueError('模型正在回复，请不要重复发送。')
    named = str(name or '').strip()
    def adjust(settings):
        settings['model'] = request_model['id']
        settings['engine'] = 'qwen'
        settings['invocation_mode'] = 'api'
        settings['stage_skills'] = [str(path)] if path else []
        settings['skills'] = []
        settings['skill'] = ''
        settings['named_execution'] = True
        settings['named_skills'] = [named]
    try:
        request_model['settings'] = workflow_settings.resolve_for_send(
            desktop.root, 'writing', direct_api=True,
            model_snapshot=(request_model['id'], request_model['record']), adjust=adjust)
    except ValueError as exc:
        _skill_send_notice(desktop, _skill_send_refusal_text(exc), model=request_model['label'])
        return True
    model = request_model['label']
    task = str(rest or '').strip() or '请按该技能完成当前阶段任务。'
    visible = '/' + named + ((' ' + str(rest).strip()) if str(rest or '').strip() else '')
    controller.mark_sent()
    injection = request_model['settings'].get('skill_injection')
    context = desktop.idea_chat_context()
    gateway = desktop.idea_chat_gateway()
    idea_chat.append(context, 'user', visible, model=model, gateway=gateway,
                     skill_injection=injection)
    notices = _skill_send_notices(injection)
    for notice in notices:
        idea_chat.append(context, 'notice', notice, model=model, gateway=gateway)
    desktop._idea_view_model_request = getattr(desktop, '_idea_view_model_request', 0) + 1
    desktop._idea_view_model_cache = (desktop.root, model)
    desktop.set_idea_model_filter(model)
    desktop.discard_idea_draft()
    desktop.show_conversation()
    for notice in notices:
        desktop.status.set(notice)
    project = desktop.root
    token, cancelled = controller.begin_request(cancellable=True)
    async_ticket = {'value': None}
    if getattr(desktop, 'idea_send', None) is not None:
        desktop.idea_send.state(['disabled'])
    desktop.update_script_interrupt_button()
    desktop.show_thinking(model)
    received = lambda result: desktop._idea_api_received(token, model, request_model, result)
    desktop.begin_stream()
    def ask():
        from stage_execution_service import reply_to_writing
        return desktop.stream_call(reply_to_writing, project, task,
                                   user_message=visible, request_model=request_model,
                                   cancelled=cancelled.is_set)
    desktop.submit_idea_api_request(project, token, cancelled, ask, received,
                                    str(model) + ' 模型正在思考…', async_ticket)
    return True


def _send_skill(desktop, stage, parsed):
    """技能／用户包命令只在当前页的入口里执行，不换页（DOC-D8-7）；换页只认 ``/阶段``。

    初步分镜（S03）：点名技能走 ``send_storyboard(..., only=[name])``，只跑点名的那一个，
    不读 ✦ 勾选、不改 stage_config；其余 flow 阶段仍走 ``_open_flow``。
    """
    name = str(parsed.get('name') or '')
    rest = str(parsed.get('rest') or '').strip()
    home, path = _resolve_skill(desktop, parsed)
    if not home:
        _say(desktop, '没有这个技能或子引擎：/%s' % name)
        return False
    if not stage:
        _say(desktop, '请先打开一个制作阶段页面')
        return False
    if stage == 'storyboard':
        return send_storyboard(desktop, rest, only=[name])
    if stage == 'script':
        # REQ-S01-118：接口模型先把技能发送交给应用内请求；不受理（非接口模型）再回落原命令行链。
        if send_skill_request(desktop, name, path, rest):
            return True
    else:
        before = _read_status(desktop)
        if send_stage_file(desktop, stage, rest, only=[name]):
            return True
        if _read_status(desktop) != before:
            return False
    if stage not in FLOW_FOR_STAGE:
        _say(desktop, '「%s」请先在右下角模型下拉框选择一个可用的 API 模型，再使用 /%s 直接输出阶段文件。'
             % (pet_bus.stage_name(stage), name))
        return False
    return _open_flow(desktop, stage, _skill_prompt(name, path, rest))


def send(desktop, stage, text, parsed):
    """共享输入框 ``on_send``：返回真值＝已受理（输入框随即清空）。"""
    stage = str(stage or '') or current_stage(desktop); getattr(desktop, 'reply_note', lambda *a, **k: None)('user', stage, text)
    if isinstance(parsed, dict):
        kind = parsed.get('kind')
        if kind == 'stage':
            target = str(parsed.get('name') or '')
            rest = str(parsed.get('rest') or '').strip()
            if target not in pet_bus.STAGES:
                _say(desktop, '没有这个阶段：/%s' % target)
                return False
            if not _goto_stage(desktop, target):
                return False
            _say(desktop, '已切换到「%s」' % pet_bus.stage_name(target))
            if not rest:
                return True
            # ``/阶段 /skill名`` 这种连发：剩余正文在新阶段上下文里重新解析，
            # 不能把 ``/skill名`` 当普通文本发给 Agent。
            return send(desktop, target, rest, skill_command.parse_command(
                rest, stage=target, skills=_skill_items(desktop)))
        if kind in ('skill', 'engine'):
            return _send_skill(desktop, stage, parsed)
    return _send_free(desktop, stage, text)


def _attachments(desktop):
    """附件入口：只有剧本准备页有附件链路；其余阶段提示用页面自带入口。"""
    if current_stage(desktop) == 'script':
        chooser = getattr(desktop, 'choose_idea_attachments', None)
        if callable(chooser):
            try:
                chooser()
                return
            except Exception as exc:
                _notify_error(desktop, '附件选择失败：%s' % exc)
                return
    _say(desktop, input_extras.ATTACHMENT_UNSUPPORTED)


def _voice(desktop, box, button):
    """共享输入框的麦克风听写：VoiceInput 绑定共享 Text，按钮按原样式接线。"""
    try:
        from ui.desktop_voice_input import VoiceInput
    except Exception:
        return None
    voice = getattr(desktop, 'shared_voice', None)
    if voice is None or getattr(voice, 'box', None) is not box:
        voice = VoiceInput(box, button, status=getattr(desktop, 'status', None),
                           project=getattr(desktop, 'root', None))
        desktop.shared_voice = voice
    else:
        voice.button = button
    safe = getattr(desktop, 'safe', None)
    button.configure(command=(lambda: safe(voice.toggle)) if callable(safe)
                    else voice.toggle)
    return voice


def host_options(desktop):
    """``SharedStageInput`` 的宿主回调集：发送分流、附件、语音（模型选择器已内嵌为下拉框）。"""

    def on_send(text, parsed):
        shared = getattr(desktop, 'shared_input', None)
        stage = getattr(shared, 'stage', '') or current_stage(desktop)
        try:
            return send(desktop, stage, text, parsed)
        finally:
            if shared is not None:
                try:
                    shared.end_request()
                except Exception:
                    app_logging.swallowed()

    return {'on_send': on_send,
            'on_upstream_error': lambda project, stage, status=None: upstream_send_error(
                project, stage, status),
            'stage_action_fallback': lambda stage: (empty_send_action(desktop, stage)
                                                    if stage in EMPTY_SEND_STAGES else None),
            'on_attachment': lambda: _attachments(desktop),
            'continue_state': lambda box: input_extras.continue_state(
                getattr(box, 'stage', ''),
                getattr(getattr(box, 'desktop', None), 'idea_chat_controller', None)),
            'on_voice': lambda button: _voice(desktop,
                                              getattr(desktop, 'shared_input').input,
                                              button)}


def make_shared_input(desktop):
    """桌面宿主唯一一份共享输入框实例（任务书轮 4：跨页同实例，只换 ``set_stage``）。"""
    import desktop_shared_input
    return desktop_shared_input.SharedStageInput(
        getattr(desktop, 'input_dock', None) or desktop.body, desktop=desktop, stage='script',
        shortcuts=desktop.shortcuts, options=host_options(desktop))
