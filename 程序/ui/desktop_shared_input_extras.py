"""共享输入框新增能力（UX-CHAT-INPUT-EXTRAS，REQ-S01-112/113/114）。

``desktop_shared_input`` 已逼近 1000 行上限，本模块集中以下主体逻辑，
``SharedStageInput`` 只在 ``__init__`` 末尾 ``extras.attach(self)`` 接线一条：

- REQ-S01-114：``COMPOSER_BASE_PLACEHOLDER`` 统一占位前缀＋``stage_placeholder`` 阶段尾句；
- REQ-S01-113：``ATTACHMENT_UNSUPPORTED`` 非剧本阶段附件明确文案；
- REQ-S01-112：``continue_state`` 续写提示条、``quick_reply_rules`` 本地规则胶囊栏、
  ``sync_send_art`` 发送键三态圆形视觉（全部颜色/间距走 ui_tokens，不写内联 hex）。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import infra.app_logging as app_logging
import infra.tk_timers as tk_timers
from contract import pet_bus
from ui.ui_rounded import element_photo
from ui_widgets import SecondaryButton
from ui_tokens import COLORS, SPACING

# REQ-S01-114：十三阶段占位提示的统一前缀；各阶段以它为开头再附一句本阶段指引。
COMPOSER_BASE_PLACEHOLDER = '@引用文件，/快捷指令和 skill'
PLACEHOLDER_TAILS = {
    'script': '输入故事创意或修改要求（Enter 发送，Shift+Enter 换行）',
    'script_structure': '输入结构化整理或修改要求，直接按技能输出阶段文件（Enter 发送）',
    'storyboard': '输入补充要求发送制作分镜，空输入按结构剧本生成（Enter 发送）',
}
DEFAULT_PLACEHOLDER_TAIL = '输入阶段修改要求，直接按技能输出阶段文件（Enter 发送，Shift+Enter 换行）'

# REQ-S01-113：不支持附件的非剧本阶段，＋菜单「添加附件」状态栏明确文案。
ATTACHMENT_UNSUPPORTED = '本阶段暂不支持附件'

# REQ-S01-112：续写提示条默认文案与按钮标签。
CONTINUE_PROMPT = '请从上次中断处继续'
CONTINUE_LABEL = '继续上次对话'
CONTINUE_HINT = '上次回复中断，可从断点继续。'
# continue_plan() 产出中可作为续写文案的显式键（按序取用）。
_CONTINUE_TEXT_KEYS = ('continue_text', 'prompt', 'instruction')

# REQ-S01-112：快捷答复胶囊上限与各阶段静态建议（本地规则表，无网络/模型/递归扫盘）。
QUICK_REPLY_LIMIT = 3
QUICK_REPLY_SCRIPT = '生成自然剧本'
QUICK_REPLY_NO_LOCKS = '补充制作锁：'
_QUICK_STAGE_HINTS = {
    'script_structure': '整理为结构化剧本',
    'storyboard': '按结构剧本生成分镜',
    'animatic': '生成分镜预演',
    'assets': '盘点本阶段资产',
    'continuity': '生成连贯性清单',
    'final': '生成分镜定稿',
    'keyframe': '生成首帧',
    'previs': '生成白模预演',
    'video': '生成视频提示词',
    'audio': '生成配音与字幕',
    'edit': '进入后期剪辑',
    'delivery': '生成交付清单',
}

# 发送键圆形底图边长：与 Tokens.Composer.Send.TButton 的圆环图元同尺寸。
_SEND_ART_SIZE = SPACING['2xl']


def stage_placeholder(stage):
    """REQ-S01-114：占位提示＝统一常量前缀＋本阶段一句指引。"""
    tail = PLACEHOLDER_TAILS.get(str(stage or ''), DEFAULT_PLACEHOLDER_TAIL)
    return COMPOSER_BASE_PLACEHOLDER + '；' + tail


def continue_prompt(plan):
    """REQ-S01-112：continue_plan 产出里的显式续写文案，缺省回默认指令。"""
    if isinstance(plan, dict):
        for key in _CONTINUE_TEXT_KEYS:
            value = str(plan.get(key) or '').strip()
            if value:
                return value
    return CONTINUE_PROMPT


def continue_state(stage, controller):
    """REQ-S01-112：可续写 → ``{'text': 续写文案}``；否则 ``None``。

    纯判定不碰 Tk：只读 ``controller.can_continue`` 与 ``continue_plan()``，
    不另造状态机；非剧本准备阶段（无 idea_chat_controller 会话）恒为 None。
    """
    if str(stage or '') != 'script' or controller is None:
        return None
    if not getattr(controller, 'can_continue', False):
        return None
    plan = None
    probe = getattr(controller, 'continue_plan', None)
    if callable(probe):
        try:
            plan = probe()
        except Exception:
            app_logging.swallowed()
    return {'text': continue_prompt(plan)}


def quick_reply_rules(stage, ctx):
    """REQ-S01-112：快捷答复规则表——纯本地判定，只消费传入 ``ctx`` 快照。

    ``ctx`` 键：``has_project``/``missing_locks``/``has_natural_script``。
    不调模型、不联网、不读盘；最多返回 ``QUICK_REPLY_LIMIT`` 条可行动文案。
    """
    ctx = ctx or {}
    if not ctx.get('has_project', True):
        return ()
    suggestions = []
    missing = [str(item).strip() for item in ctx.get('missing_locks') or ()
               if str(item).strip()]
    if missing:
        suggestions.append(QUICK_REPLY_NO_LOCKS + '、'.join(missing[:QUICK_REPLY_LIMIT]))
    stage = str(stage or '')
    if stage == 'script':
        if ctx.get('has_natural_script') is False:
            suggestions.append(QUICK_REPLY_SCRIPT)
    else:
        hint = _QUICK_STAGE_HINTS.get(stage)
        if hint:
            suggestions.append(hint)
    if ctx.get('needs_review'):
        suggestions.append('检查本阶段产物并确认')
    return tuple(suggestions[:QUICK_REPLY_LIMIT])


def collect_quick_context(box):
    """REQ-S01-112：从已接线状态取胶囊栏快照——单文件 JSON 读与浅层目录枚举，
    不递归扫盘、不读文件正文、不联网、不调模型。"""
    ctx = {'has_project': False, 'missing_locks': (), 'has_natural_script': None}
    project = getattr(box, 'project', None)
    if project is None:
        return ctx
    ctx['has_project'] = True
    try:
        import orchestrator.stage_config as stage_config
        from contract.script_contract import (PRODUCTION_LOCK_DEFINITIONS,
                                              stage_lock_requirements)
        values = stage_config.workflow_lock(project)
        labels = {item['key']: item['label'] for item in PRODUCTION_LOCK_DEFINITIONS}
        required = stage_lock_requirements(str(box.stage),
                                           stage_config.project_created_at(project))
        ctx['missing_locks'] = tuple(labels.get(key, key) for key in required
                                     if not str(values.get(key) or '').strip())
    except Exception:
        app_logging.swallowed()
    if str(box.stage) == 'script':
        ctx['has_natural_script'] = _has_natural_script(project)
    return ctx


def _has_natural_script(project):
    """自然剧本存在判定：阶段目录 ≤3 层 glob 浅枚举，不递归、不读正文、不做 sha
    （``natural_script_paths`` 的指纹去重对本判定过重）。取不到返回 ``None``。"""
    try:
        from contract.stage_path_service import read_dirs
        for folder in read_dirs(project, 'script'):
            if not folder.is_dir():
                continue
            for pattern in ('*.md', '*/*.md', '*/*/*.md'):
                for path in folder.glob(pattern):
                    if not path.is_file():
                        continue
                    name = path.name.lower()
                    if ('剧本' in path.name or 'script' in name
                            or '项目剧本' in path.parent.name):
                        return True
    except Exception:
        app_logging.swallowed()
        return None
    return False


def default_quick_replies(box):
    """REQ-S01-112：默认胶囊建议＝本地快照＋规则表。"""
    return quick_reply_rules(getattr(box, 'stage', ''), collect_quick_context(box))


def sync_send_art(box):
    """REQ-S01-112：发送键三态圆形视觉——强调底实心圆＋居中 MDL2 字形。

    ``idle/running`` 取 ``primary`` 底＋``on_accent`` 字形（running 的停止方块
    仍是既有 ``ICON_STOP`` 文本）；``disabled`` 取 ``disabled_bg``＋``disabled_text``
    低对比。样式名 ``Tokens.Composer.Send.TButton``、字形切换、点击与
    UX-INPUT-FLOW 防重语义不变。
    """
    button = getattr(box, 'send_button', None)
    if button is None or not button.winfo_exists():
        return
    disabled = bool(button.instate(['disabled']))
    running = bool(getattr(box, '_send_interrupt', False))
    key = ('disabled' if disabled else ('running' if running else 'idle'),
           COLORS['primary'], COLORS['disabled_bg'], COLORS['on_accent'],
           COLORS['disabled_text'])
    if getattr(box, '_send_art_key', None) == key:
        return
    box._send_art_key = key
    fill = COLORS['disabled_bg'] if disabled else COLORS['primary']
    image, _ = element_photo(box.winfo_toplevel(), fill, _SEND_ART_SIZE // 2,
                             _SEND_ART_SIZE, _SEND_ART_SIZE)
    try:
        # ttk.Button 无 -foreground 部件选项：字形色由 Tokens.Composer.Send.TButton
        # 样式承担（idle/running→on_accent、disabled→disabled_text，见 ui_composer_style）。
        button.configure(image=image, compound='center')
    except tk.TclError:
        app_logging.swallowed()


def _wrap_after(box, name, hook):
    """实例级后挂钩：``box.<name>(...)`` 照常执行后跑 ``hook()``；hook 异常不冒头。"""
    original = getattr(box, name)

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            hook()
        except Exception:
            app_logging.swallowed()
        return result

    setattr(box, name, wrapped)


class _ComposerExtras:
    """续写提示条＋快捷答复胶囊栏＋发送键图元的管理对象（挂 ``box.extras``）。"""

    def __init__(self, box):
        self.box = box
        self._continue_muted = False
        self._quick_muted = False
        try:
            self._send_idle_glyph = str(box.send_button.cget('text') or '')
        except (AttributeError, tk.TclError):
            self._send_idle_glyph = ''
        card = box.input_card
        self.continue_bar = ttk.Frame(card, style='Composer.Notice.TFrame')
        ttk.Label(self.continue_bar, text=CONTINUE_HINT,
                  style='Composer.Notice.TLabel').pack(
                      side='left', padx=(SPACING['sm'], SPACING['xs']),
                      pady=SPACING['xs'] // 2)
        SecondaryButton(self.continue_bar, text=CONTINUE_LABEL,
                        style='Tokens.Composer.Model.TButton',
                        command=self._continue_clicked).pack(
                            side='right', padx=(SPACING['none'], SPACING['sm']),
                            pady=SPACING['xs'] // 2)
        self.quick_bar = ttk.Frame(card, style='Composer.TFrame')
        self._quick_buttons = []
        self.sync_continue()
        self.refresh_quick()

    # ── 续写提示条（自动接入）───────────────────────────────────────────
    def _state(self):
        provider = getattr(self.box, 'continue_state', None)
        if not callable(provider):
            return None
        try:
            state = provider(self.box)
        except Exception:
            app_logging.swallowed()
            return None
        if not isinstance(state, dict) or not str(state.get('text') or '').strip():
            return None
        return state

    def sync_continue(self):
        """数据源真且未静音 → 显示；为假 → 收起并解除静音（下一次中断再出现）。"""
        if self._state() is None:
            self._continue_muted = False
            self.continue_bar.pack_forget()
            return
        if self._continue_muted or self.continue_bar.winfo_manager():
            if self._continue_muted:
                self.continue_bar.pack_forget()
            return
        self.continue_bar.pack(fill='x', before=self.box.input)

    def hide_continue(self):
        self._continue_muted = True
        self.continue_bar.pack_forget()

    def _continue_clicked(self):
        """点击即收：续写文案作为普通用户消息经既有 send() 发出。"""
        state = self._state()
        self.hide_continue()
        if state is None:
            return
        box = self.box
        box.set_text(state['text'])
        try:
            box.input.mark_set('insert', 'end-1c')
            box.input.focus_set()
        except Exception:
            app_logging.swallowed()
        box.send()

    # ── 快捷答复胶囊 ────────────────────────────────────────────────────
    def _suggestions(self):
        provider = getattr(self.box, 'on_quick_replies', None)
        try:
            items = provider(self.box) if callable(provider) else default_quick_replies(self.box)
        except Exception:
            app_logging.swallowed()
            return ()
        seen = []
        for item in items or ():
            text = str(item or '').strip()
            if text and text not in seen:
                seen.append(text)
            if len(seen) >= QUICK_REPLY_LIMIT:
                break
        return tuple(seen)

    def refresh_quick(self):
        """重算胶囊：有正文或被静音不显示；清空/切页后由钩子恢复。"""
        for button in self._quick_buttons:
            button.destroy()
        self._quick_buttons = []
        if self._quick_muted or self._raw():
            self.quick_bar.pack_forget()
            return
        suggestions = self._suggestions()
        if not suggestions:
            self.quick_bar.pack_forget()
            return
        for text in suggestions:
            button = SecondaryButton(self.quick_bar, text=text,
                                     style='Tokens.Composer.Model.TButton',
                                     command=lambda value=text: self._quick_clicked(value))
            button.pack(side='left', padx=(SPACING['none'], SPACING['xs']),
                        pady=SPACING['xs'] // 2)
            self._quick_buttons.append(button)
        if not self.quick_bar.winfo_manager():
            self.quick_bar.pack(fill='x', after=self.box.icon_row)

    def _raw(self):
        try:
            return self.box._raw_text().strip()
        except Exception:
            return ''

    def _quick_clicked(self, text):
        """REQ-S01-112：点击只填入输入框，不自动发送（可撤销）。"""
        self._quick_muted = True
        self.quick_bar.pack_forget()
        box = self.box
        box.set_text(text)
        try:
            box.input.mark_set('insert', 'end-1c')
            box.input.focus_set()
        except Exception:
            app_logging.swallowed()

    # ── 宿主薄钩子（由 _wrap_after 挂在现有方法尾）────────────────────────
    def text_edited(self):
        """输入框有正文 → 胶囊隐藏；删空 → 解除静音并按需恢复。"""
        if self._raw():
            self._quick_muted = True
            if self.quick_bar.winfo_manager():
                self.quick_bar.pack_forget()
        elif self._quick_muted:
            self._quick_muted = False
            self.refresh_quick()

    def cleared(self):
        """清空/成功发送后：续写条静音收起（REQ-S01-112：新请求/清空同步收起），
        胶囊解除静音按需恢复。"""
        self.hide_continue()
        self._quick_muted = False
        self.refresh_quick()

    def _reset_send_button(self):
        """切离剧本准备页时复位共享发送键，避免 01 必填置灰或中断态残留。"""
        box = self.box
        if str(getattr(box, 'stage', '') or '') == 'script':
            return
        box._send_interrupt = False
        button = getattr(box, 'send_button', None)
        if button is not None and button.winfo_exists():
            try:
                if self._send_idle_glyph:
                    button.configure(text=self._send_idle_glyph, command=box.send)
                else:
                    button.configure(command=box.send)
                button.state(['!disabled'])
            except tk.TclError:
                app_logging.swallowed()
            button._stage_flow_forced = False
        sync = getattr(box, '_sync_send_state', None)
        if callable(sync):
            sync()
        sync_send_art(box)

    def stage_changed(self):
        self._reset_send_button()
        self._continue_muted = False
        self._quick_muted = False
        self.sync_continue()
        self.refresh_quick()

    def tick(self):
        """400ms 巡检：发送键三态图＋续写条数据源（can_continue 变化随拍出现）。"""
        if not self.box.winfo_exists():
            return
        sync_send_art(self.box)
        self.sync_continue()


def _default_continue_state(box):
    """REQ-S01-112：宿主未注入 ``continue_state`` 时的缺省数据源——读
    ``desktop.idea_chat_controller``（仅剧本页 ``can_continue`` 为真才出条）。"""
    desktop = getattr(box, 'desktop', None)
    controller = getattr(desktop, 'idea_chat_controller', None)
    return continue_state(getattr(box, 'stage', ''), controller)


def _expand_reply_area(desktop, stage):
    """若宿主持有回话区且正停在目标制作阶段，则自动展开。"""
    stage = str(stage or '')
    if not stage or stage == 'script':
        return
    area = getattr(desktop, 'reply_area', None)
    if area is None or not callable(getattr(area, 'set_expanded', None)):
        return
    current = getattr(area, 'stage', None)
    if isinstance(current, str) and current != stage:
        return
    try:
        area.set_expanded(True)
    except Exception:
        app_logging.swallowed()


def _reply_note_with_expand(desktop, kind, stage, text, *, expand=False):
    """向宿主回话区写记录并按需展开；兼容无回话区或仅收 3 参的旧桩。"""
    stage = str(stage or '')
    if not stage or stage == 'script':
        return
    note = getattr(desktop, 'reply_note', None)
    expanded = False
    if callable(note):
        try:
            if expand:
                note(kind, stage, text, expand=True)
                expanded = True
            else:
                note(kind, stage, text)
        except TypeError:
            try:
                note(kind, stage, text)
            except Exception:
                app_logging.swallowed()
        except Exception:
            app_logging.swallowed()
    if expand and not expanded:
        _expand_reply_area(desktop, stage)


def _wrap_upstream_error(box):
    """包装上游门禁回调：返回非空错误时同步记入回话区并自动展开（非 script 阶段）。"""
    gate = getattr(box, 'on_upstream_error', None)
    if not callable(gate):
        return

    def wrapped(*args, **kwargs):
        error = gate(*args, **kwargs) or ''
        stage = kwargs.get('stage') if 'stage' in kwargs else (
            args[1] if len(args) > 1 else getattr(box, 'stage', ''))
        stage_name = str(stage or '')
        if error and stage_name and stage_name != 'script':
            _reply_note_with_expand(
                getattr(box, 'desktop', None), 'error', stage_name, str(error), expand=True)
        return error

    box.on_upstream_error = wrapped


def _wrap_stage_action(box):
    """包装阶段动作：storyboard 空发送受理后，若当前在 storyboard 页则展开回话区。"""
    original = getattr(box, 'run_stage_action', None)
    if not callable(original):
        return

    def wrapped(stage=None):
        accepted = original(stage)
        target = str(stage or getattr(box, 'stage', '') or '')
        if accepted and target == 'storyboard':
            _expand_reply_area(getattr(box, 'desktop', None), 'storyboard')
        return accepted

    box.run_stage_action = wrapped


def attach(box):
    """REQ-S01-112/113：把附加条挂进输入卡，并在既有方法尾注册薄钩子。

    只改实例不改类：``_on_flow_edit`` 改指 ``box._schedule_refresh``
    （文本改动路径与按键/几何路径汇到同一个后挂钩）。
    """
    if not callable(getattr(box, 'continue_state', None)):
        box.continue_state = _default_continue_state
    manager = _ComposerExtras(box)
    _wrap_after(box, 'set_stage', manager.stage_changed)
    _wrap_after(box, 'clear', manager.cleared)
    _wrap_after(box, '_schedule_refresh', manager.text_edited)
    _wrap_upstream_error(box)
    _wrap_stage_action(box)
    box.input._on_flow_edit = lambda *args: box._schedule_refresh(*args)
    box._send_art_key = None
    box.extras = manager
    tk_timers.repeat(box, 400, manager.tick)
    return manager


def normalize_stage_model_snapshot(snapshot):
    """仅保留 workflow_settings.current 约定的 2 元组快照，过滤 script 阶段 dict。"""
    if isinstance(snapshot, tuple) and len(snapshot) == 2:
        return snapshot
    return None


def launch_storyboard_flow(desktop, batch, request_text, value, kwargs, hooks):
    """异步分镜准备收尾：捕获 open_flow_agent 异常并避免覆盖其已写状态栏。"""
    read_status, say, notify_error = hooks
    before = read_status(desktop)
    desktop._storyboard_request_text = request_text
    try:
        desktop.open_flow_agent(
            'storyboard', '初步分镜', batch['prompt'], batch['followup'], **kwargs)
    except Exception as exc:
        app_logging.swallowed()
        notify_error(desktop, str(exc) or '启动初步分镜失败')
        _expand_reply_area(desktop, 'storyboard')
        return False
    if read_status(desktop) == before:
        if batch.get('named'):
            say(desktop, '点名执行：' + '、'.join(batch['named']) + '。' + str(value or ''))
        else:
            say(desktop, value)
    _expand_reply_area(desktop, 'storyboard')
    return True


__all__ = ['ATTACHMENT_UNSUPPORTED', 'COMPOSER_BASE_PLACEHOLDER', 'CONTINUE_LABEL',
           'CONTINUE_PROMPT', 'QUICK_REPLY_LIMIT', 'attach', 'collect_quick_context',
           'continue_prompt', 'continue_state', 'default_quick_replies',
           'launch_storyboard_flow', 'normalize_stage_model_snapshot',
           'quick_reply_rules', 'stage_placeholder', 'sync_send_art']
