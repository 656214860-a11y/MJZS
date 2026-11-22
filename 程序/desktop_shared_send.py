"""共享输入框的发送分流（R2898，任务书轮 4）：``/`` 命令与自由文本 → 当前阶段既有入口。

阶段 → ``open_flow_agent`` 流程名的映射只此一处（``workflow_settings.STAGE_CONFIG_STAGES``
的阶段侧）；没有 Agent 流程的阶段（剧本结构／分镜预演／连贯性清单／分镜定稿／后期剪辑／
质检与交付）回状态栏提示，不新开对话。会员闸门复用 ``account.stage_gate``，上游完成门禁
由 ``desktop_shared_input.upstream_send_error`` 在发送前统一执行，这里不复制判定。

没有 Agent 流程的阶段里，页面在共享输入框上登记了发送动作（``set_stage_action``，目前是
剧本结构页）的，自由文本改为执行该动作并说明文字用不上，见 ``_run_stage_action``。
"""
from __future__ import annotations

from pathlib import Path

import infra.app_logging as app_logging
import domain.skill_command as skill_command
from contract import pet_bus

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


def _notify_error(desktop, text):
    notifier = getattr(desktop, 'notifier', None)
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


def _run_stage_action(desktop, stage):
    """没有对话流程的阶段：页面登记了发送动作就开动它；返回这一阶段有没有登记。

    说明先写、动作后跑：动作自己的开工提示、「正在执行」或报错是状态栏的最后一句，
    不被这句说明盖掉。
    """
    shared = getattr(desktop, 'shared_input', None)
    registered = getattr(shared, 'stage_action', None)
    if not callable(registered) or registered(stage) is None:
        return False
    _say(desktop, STAGE_ACTION_TEXT_UNUSED % pet_bus.stage_name(stage))
    shared.run_stage_action(stage)
    return True


def _send_free(desktop, stage, text):
    """自由文本：script 走剧本准备既有发送链（简报/制作锁/直连 API 全保留）。"""
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
    if stage not in FLOW_FOR_STAGE:
        if _run_stage_action(desktop, stage):
            return False    # 文字没有被使用：返回假值让输入框保留原文
        _say(desktop, '「%s」阶段暂无对话入口；请使用页面上的制作按钮，或输入 /阶段名 换到有对话入口的阶段。'
             % pet_bus.stage_name(stage))
        return False
    return _open_flow(desktop, stage, text)


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


def _no_entry_hint(stage, home, name):
    """当前页没有对话入口：技能属于有入口的别的阶段时，给出用户自己换页的写法。"""
    here = pet_bus.stage_name(stage)
    if home != stage and home in FLOW_FOR_STAGE:
        there = pet_bus.stage_name(home)
        return ('「%s」页暂无对话入口，/%s 没有发送；要在「%s」里用它，请输入 /%s /%s'
                % (here, name, there, there, name))
    return '「%s」阶段暂无 Agent 入口，/%s 请在页面操作中使用。' % (here, name)


def _send_skill(desktop, stage, parsed):
    """技能／用户包命令只在当前页的入口里执行，不换页（DOC-D8-7）；换页只认 ``/阶段``。"""
    name = str(parsed.get('name') or '')
    rest = str(parsed.get('rest') or '').strip()
    home, path = _resolve_skill(desktop, parsed)
    if not home:
        _say(desktop, '没有这个技能或子引擎：/%s' % name)
        return False
    if not stage:
        _say(desktop, '请先打开一个制作阶段页面')
        return False
    if stage not in FLOW_FOR_STAGE:
        _say(desktop, _no_entry_hint(stage, home, name))
        return False
    return _open_flow(desktop, stage, _skill_prompt(name, path, rest))


def send(desktop, stage, text, parsed):
    """共享输入框 ``on_send``：返回真值＝已受理（输入框随即清空）。"""
    stage = str(stage or '') or current_stage(desktop)
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
    _say(desktop, '附件请在当前阶段页面的制作入口中添加')


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
            'on_attachment': lambda: _attachments(desktop),
            'on_voice': lambda button: _voice(desktop,
                                              getattr(desktop, 'shared_input').input,
                                              button)}


def make_shared_input(desktop):
    """桌面宿主唯一一份共享输入框实例（任务书轮 4：跨页同实例，只换 ``set_stage``）。"""
    import desktop_shared_input
    return desktop_shared_input.SharedStageInput(
        getattr(desktop, 'input_dock', None) or desktop.body, desktop=desktop, stage='script',
        shortcuts=desktop.shortcuts, options=host_options(desktop))
