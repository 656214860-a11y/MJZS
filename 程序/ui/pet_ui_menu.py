# -*- coding: utf-8 -*-
"""三虎右键菜单构建、日夜重绘与常用动作辅助（L4，UX-SANHU-FIX）。

从 ``PetViewMixin`` 与 ``PetStagesMixin`` 抽离为无状态模块函数：避免顶破
``PetViewMixin`` 类行数棘轮与 ``Pet`` 多写共享状态棘轮。
"""
import contract.pet_bus as pet_bus
import infra.app_logging as app_logging
import orchestrator.desktop_auto_state as desktop_auto_state
import orchestrator.stage_flow as stage_flow
import ui_tokens
from ui.pet_ui_support import DETAIL_MENU_LABEL, PANEL_MENU_LABEL, QUIT_LABEL
from ui_widgets import ContextMenu

ADVANCE_MENU_LABEL = '推进当前阶段'
RETRY_MENU_LABEL = '重试失败项'
SKIP_MENU_LABEL = '跳过当前阻塞项'
SPEECH_MENU_LABEL = '语音识别设置…'
DAILY_REPORT_MENU_LABEL = '今日日报'
OPEN_SETTINGS_MENU_LABEL = '打开设置…'


def theme_label():
    """右键主题项文案：动态显示当前日间／夜间状态。"""
    current = '夜间' if ui_tokens.current_theme() == 'night' else '日间'
    return '切换日间/夜间主题（当前：%s）' % current


def build_menu(pet):
    """按使用频率从上往下构建 4 块 3 分隔线右键菜单（中间 2 块带禁用小标题）。"""
    pet.menu_index.clear()
    pet._menu_labels.clear()
    menu = ContextMenu(pet.win)
    pet.menu = menu
    # ① 高频主操作（最顶部）
    menu.command('向三虎提问', lambda: pet.act('chat'))
    pet._add_menu(ADVANCE_MENU_LABEL, lambda: pet.act(pet.advance_current_stage), name='advance')
    pet._add_menu(PANEL_MENU_LABEL, lambda: pet.act(pet.show_panel, speak=False), name='panel')
    menu.separator()
    # ② 任务控制（暂停项直接调 pause_action，避免双重包裹 act）
    pet._add_section('任务控制')
    pet._add_menu(pet.pause_label(), pet.pause_action, name='pause')
    pet._add_menu(RETRY_MENU_LABEL, lambda: pet.act('retry'), name='retry')
    pet._add_menu(DETAIL_MENU_LABEL, lambda: pet.act(pet.show_details, speak=False), name='details')
    pet._add_menu(SKIP_MENU_LABEL, lambda: pet.act('skip'), name='skip')
    menu.separator()
    # ③ 常用工具
    pet._add_section('常用工具')
    pet._build_model_menu()
    pet._add_menu(SPEECH_MENU_LABEL, lambda: pet.act(pet.open_speech_settings), name='speech')
    pet._add_menu(theme_label(), lambda: pet.act(pet.toggle_theme), name='theme')
    pet._add_menu(pet.snooze_label(), lambda: pet.act(pet.toggle_snooze), name='snooze')
    pet._add_menu(DAILY_REPORT_MENU_LABEL, lambda: pet.act(pet.show_daily_report), name='report')
    menu.separator()
    # ④ 设置与退出（单一设置入口，退出固定最底行）
    pet._add_menu(OPEN_SETTINGS_MENU_LABEL, lambda: pet.act(pet.open_settings), name='settings')
    pet._add_menu(QUIT_LABEL, lambda: pet.act(pet.quit_app), name='quit')
    return menu


def toggle_theme(pet):
    """一键切换日间／夜间主题，持久化设置、刷新全窗与三虎并播报反馈。"""
    import ui.pet_settings_ui as pet_settings_ui
    target = 'day' if ui_tokens.current_theme() == 'night' else 'night'
    effective, _persisted = pet_settings_ui.apply_theme_choice(pet, target)
    if effective is None:
        effective = ui_tokens.set_theme(target) or ui_tokens.current_theme()
    pet.refresh_pet_theme()
    name = '夜间' if effective == 'night' else '日间'
    pet.notice = '已切换到%s主题' % name
    return effective


def open_speech_settings(pet):
    """直达语音识别设置弹窗并留下反馈。"""
    import ui.speech_settings_ui as speech_settings_ui
    try:
        win = speech_settings_ui.open_speech_settings(pet, parent=getattr(pet, 'win', None))
        pet.notice = '已打开语音识别设置窗口'
        return win
    except Exception as exc:
        pet.errors.append(('speech.settings', str(exc)))
        pet.notice = '未能打开语音识别设置，请稍后重试。'
        return None


def show_daily_report(pet):
    """生成并播报今日制作日报。"""
    data, path = pet.daily_report()
    if path is None:
        pet.notice = '还没打开项目，暂时无法生成今日日报。'
        return None
    if not pet.notice:
        pet.notice = '今日日报已生成：' + path.name
    return data, path


def _pick_target_stage(pet):
    """按当前页与 13 阶段进度选取待推进阶段；全完成返回 None。"""
    states = pet.stage_states()
    current = pet.page_stage(getattr(pet.desktop, 'page_index', None))
    if current in pet_bus.STAGES and str(states.get(current) or '') not in stage_flow.DONE_STATES:
        return current
    for stage in pet_bus.STAGES:
        if str(states.get(stage) or '') not in stage_flow.DONE_STATES:
            return stage
    return None


def _dispatch_stage(pet, stage):
    """尝试经宿主入口安全派发某一阶段；无自动入口返回空串。"""
    kick = getattr(pet.desktop, 'pet_start', None)
    if callable(kick):
        try:
            text = str(kick(stage) or '').strip()
            if text:
                return text
        except Exception as exc:
            pet.errors.append(('advance.start', str(exc)))
    advanced = pet.advance_stage(stage)
    if advanced:
        return advanced
    if stage == 'script_structure':
        return pet.script_structure_batch()
    if stage == 'storyboard':
        return pet.storyboard_batch()
    if stage == 'keyframe':
        return pet.firstframe_batch(trigger='manual')
    return ''


def advance_current_stage(pet):
    """右键「推进当前阶段」：按当前 13 阶段进度推进，付费阶段严格走确认护栏。"""
    project = getattr(pet.desktop, 'root', None)
    if project is None:
        pet.notice = '还没打开项目，请先新建或打开一个项目再推进当前阶段。'
        return pet.notice
    if getattr(pet.agent, 'paused', False):
        pet.notice = '三虎当前已暂停，请先点击「继续」后再推进阶段。'
        return pet.notice
    stage = _pick_target_stage(pet)
    if not stage:
        pet.notice = '全部 13 个制作阶段均已完成，可在「进度面板」或「今日日报」查看成果。'
        return pet.notice
    name = pet_bus.STAGE_NAMES.get(stage, stage)
    if stage in stage_flow.PAID_STAGES:
        if pet.agent.level == 'auto':
            allowed, declined = pet._authorize_paid_stage(stage)
            if not allowed:
                pet.notice = declined or ('「%s」属于付费阶段，未获授权前不会执行。' % name)
                return pet.notice
        elif not pet.confirm_start('推进当前阶段 · 付费确认',
                                   '「%s」属于付费阶段，可能会产生模型或接口费用。\n\n确认继续推进吗？' % name):
            pet.notice = '已取消推进「%s」：付费步骤需您确认后才会执行。' % name
            return pet.notice
    if stage_flow.unchecked(project, stage):
        pet.notice = '「%s」尚未勾选任何 SKILL，请先在底部「技能」里勾选后再推进。' % name
        return pet.notice
    result = _dispatch_stage(pet, stage)
    if result:
        pet.notice = '推进当前阶段（%s）：%s' % (name, result)
        return pet.notice
    index = list(pet_bus.STAGES).index(stage) + 1
    pet.notice = '当前阶段「%s」（%d/%d）：请在该页确认参数后点击「%s」。' % (
        name, index, len(pet_bus.STAGES), stage_flow.manual_label(stage))
    return pet.notice


def _clear_stage_backoff(desktop, stage):
    """清除指定阶段对应的无人值守退避计时（存在时）。"""
    poll_name = desktop_auto_state.PET_STAGE_POLL.get(stage)
    if not poll_name:
        return ''
    if hasattr(desktop, 'auto'):
        try:
            desktop_auto_state.flow_set(desktop, poll_name, '_due', 0)
        except Exception:
            app_logging.swallowed()
    return poll_name


def _retry_one_stage(pet, stage):
    """把单个失败／阻塞阶段重新放回执行链，兼容真宿主与测试替身。"""
    desktop = pet.desktop
    poll_name = _clear_stage_backoff(desktop, stage)
    direct = getattr(desktop, 'pet_retry_stage', None)
    if callable(direct):
        try:
            return str(direct(stage) or '')
        except Exception as exc:
            pet.errors.append(('retry.direct', str(exc)))
    if pet.agent.level in stage_flow.AUTO_LEVELS and not getattr(pet.agent, 'paused', False):
        started = pet.start_stage(stage)
        if started:
            return started
    kick = getattr(desktop, 'pet_start', None)
    if callable(kick):
        allowed = (stage not in stage_flow.PAID_STAGES
                   or pet.confirm_start('重试付费阶段', '「%s」属于付费阶段，确认重新执行吗？'
                                        % pet_bus.STAGE_NAMES.get(stage, stage)))
        if allowed:
            try:
                started = str(kick(stage) or '')
                if started:
                    return started
            except Exception as exc:
                pet.errors.append(('retry.start', str(exc)))
    advanced = pet.advance_stage(stage)
    if advanced:
        return advanced
    if poll_name:
        unattended = getattr(desktop, 'kick_unattended', None)
        if callable(unattended):
            try:
                unattended(poll_name)
                return poll_name
            except Exception as exc:
                pet.errors.append(('kick', str(exc)))
    return ''


def retry_failures(pet):
    """记录失败与阻塞阶段、清账解阻，并真实重新放回执行链。"""
    failures = [item for item in getattr(pet.agent, 'failures', ()) if isinstance(item, dict)]
    count = len(failures)
    stages = []
    for item in failures:
        stage = str(item.get('stage') or '').strip()
        if stage and stage not in stages:
            stages.append(stage)
    blocked = getattr(pet.auto, 'blocked', None)
    blocked_stage = str(blocked[0] or '').strip() if isinstance(blocked, (tuple, list)) and blocked else ''
    if blocked_stage and blocked_stage not in stages:
        stages.append(blocked_stage)
    if count == 0 and not blocked_stage:
        pet.notice = '现在没有待确认的项，不用重试'
        return True
    pet.agent.clear_failures()
    pet.auto.blocked = None
    pet._gate_said = ''
    pet.bstate.reset_advance()
    restarted = []
    for stage in stages:
        pet.attempts[stage] = 0
        if _retry_one_stage(pet, stage):
            restarted.append(pet_bus.STAGE_NAMES.get(stage, stage))
    names = '、'.join(restarted or [pet_bus.STAGE_NAMES.get(s, s) for s in stages])
    if count:
        pet.notice = '已重试失败项：%d 项（%s），已解除阻塞并交回执行链' % (count, names)
    else:
        pet.notice = '已解除阻塞项（%s）并重新交回执行链' % names
    return True
