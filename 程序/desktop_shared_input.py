"""共享底部输入框（R2893，任务书轮 3）：13 个阶段页共用同一实例。

布局（R2942 定版）：``[✦ 技能][＋ 添加][🎤 语音] | [TextArea 输入框] | [模型下拉框][发送]``；
✦ 与 ＋ 点开与 ``/`` 补全同款的下拉面板（R2971，``desktop_shared_menus``），不再弹窗。
视觉 token 走 ``ui_tokens``，快捷键登记走宿主 ``ShortcutRegistry``（``/`` 补全与
``Esc`` 关闭）。命令解析在无 Tk 的 ``skill_command``；发送门禁复用
``stage_parallel`` 上游判定与 ``stage_completion_service.completion_evidence``。

宿主契约（轮 4 由 Desktop／页面接线）：``desktop.root`` 为项目根、
``desktop.status`` 为状态栏 StringVar；``options`` 携带 ``on_send(text,
parsed)``（返回真值表示已受理，假值＝本组件恢复可用态）与 ``on_skill_config``／
``on_attachment``／``on_voice`` 入口回调、``status``、``skills``、``engines``，
缺省给出可用兜底。模型选择器（R2942 起）内嵌为右下角 ``StageModelPicker`` 下拉框按钮，
点击弹出模型列表（不再弹模态窗）。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from pathlib import Path

import infra.app_logging as app_logging
import domain.skill_command as skill_command
import infra.tk_timers as tk_timers
import infra.ui_plugin_registry as ui_plugin_registry
from contract import pet_bus
from ui.desktop_shared_input_extras import (ATTACHMENT_UNSUPPORTED,
                                            attach as _extras_attach)
from ui.desktop_shared_menus import (AddMenuPanel, CandidatePopup, SkillPickPanel,
                                     _MenuFlow)
from ui_popup import apply_noactivate, make_passive_popup, monitor_bounds
from ui.ui_shortcuts import ShortcutRegistry
from ui_tokens import (COLORS, FONTS, ICON_ADD, ICON_MICROPHONE, ICON_SEND, ICON_SKILL,
                       SPACING, TEXT_ROWS)
from ui_widgets import BaseDialog, Card, SecondaryButton, TextArea, PrimaryButton, Tooltip

SHORTCUT_SCOPE = 'shared_input'
# 技能悬停说明卡片的换行宽度（像素常量，R2923：避免内联字面量触碰视觉 token 棘轮）。
SKILL_CARD_WRAP = 300
# 发送键承载的阶段制作动作：这一阶段正在执行时不重复开动（%s＝阶段名）。
STAGE_ACTION_BUSY = '「%s」正在执行，请等这一轮结束再点发送。'
# 发送键空闲悬停提示；本阶段在跑时换成 STAGE_ACTION_BUSY 同款说明（SEND-2）。
SEND_TOOLTIP_IDLE = '发送（Enter）\nShift+Enter 换行；运行中变为终止'


def project_root(desktop):
    root = getattr(desktop, 'root', None) if desktop is not None else None
    return Path(root) if root else None


def _status_of(desktop, status=None):
    return status if status is not None else getattr(desktop, 'status', None)


def _say(status, text):
    if status is not None:
        try:
            status.set(str(text))
        except Exception:
            app_logging.swallowed()


def _upstream_error(box):
    """上游门禁由宿主注入，输入框不反向依赖发送分流模块。"""
    gate = getattr(box, 'on_upstream_error', None)
    if not callable(gate):
        return ''
    return gate(box.project, box.stage, box.status) or ''


def _send_empty_storyboard(box):
    """S03 空发送：先过上游门禁，再冻结模型并受理当前阶段动作。"""
    error = _upstream_error(box)
    if error:
        _say(box.status, error)
        return False
    if box.request_model is None:
        box.request_model = box.request_snapshot()
    box.in_flight = True
    try:
        accepted = box.run_stage_action()
    finally:
        box.end_request()
    if accepted is False:
        return False
    box.clear()
    return True


RING_INSET = SPACING['xs'] // 4  # 输入框外环露边宽度（1px）


def _composer_shell(parent):
    """R3060：输入区与工具行共用一条外框——外框由包裹层 1px 底色边承担
    （ttk 主题不支持 -highlight*），Card 内缩 RING_INSET 露出环色。"""
    ring = tk.Frame(parent, bg=COLORS['border_default'])
    ring.pack(side='left', fill='both', expand=True, padx=SPACING['none'])
    box = Card(ring, padding=(SPACING['sm'], SPACING['xs']))
    box.pack(fill='both', expand=True, padx=RING_INSET, pady=RING_INSET)
    return ring, box


class _FlowTextArea(TextArea):
    """共享输入框的本地编辑区，支持有边界的撤销和重做。"""

    def _refresh_tag_colors(self, widget):
        widget.tag_configure('shared_token', background=COLORS['primary_subtle'],
                             foreground=COLORS['selection_text'])

    def __init__(self, master, **kwargs):
        self._on_flow_edit = None
        super().__init__(master, undo=True, autoseparators=True, **kwargs)
        # Ctrl+A/Z/Y 的控件绑定由宿主经 ShortcutRegistry 登记（Tk 的 Text 类绑定
        # 不保证这三个键，Entry 才有）；本类只提供处理入口。

    def _do_undo(self, _event=None):
        try:
            self.edit_undo()
        except tk.TclError:
            pass
        return 'break'

    def _do_redo(self, _event=None):
        try:
            self.edit_redo()
        except tk.TclError:
            pass
        return 'break'

    def _do_select_all(self, _event=None):
        try:
            self.tag_add('sel', '1.0', 'end-1c')
            self.mark_set('insert', '1.0')
            self.see('insert')
        except tk.TclError:
            pass
        return 'break'

    def _flow_notify(self):
        callback = self._on_flow_edit
        if callback is not None:
            callback()

    def insert(self, index, chars, *tags):
        result = super().insert(index, chars, *tags)
        self._flow_notify()
        return result

    def delete(self, index1, index2=None):
        result = super().delete(index1, index2)
        self._flow_notify()
        return result

    def edit_undo(self):
        result = super().edit_undo()
        self._flow_notify()
        return result

    def edit_redo(self):
        result = super().edit_redo()
        self._flow_notify()
        return result


def _row_icon(row, glyph, command):
    """工具行左侧图标钮（✦／＋／麦克风同款）：无边框字形钮，左对齐排布。"""
    button = SecondaryButton(row, text=glyph, width=0,
                             style='Tokens.Composer.Icon.TButton', command=command)
    button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
    return button


class _CandidateFlow(_MenuFlow):
    """``/`` 与 ``@`` 光标级候选流（R2980）：触发 token 扫描 → 候选条目 →
    光标锚定自绘浮层的采纳与文本替换。

    ``SharedStageInput`` 继承本类；只依赖宿主已建好的 ``input``／``stage``／
    ``desktop``／``status`` 与 ``skill_items``／``engine_names``／``send`` 等
    既有入口，拆出只为把宿主类压回复杂度棘轮线以内。菜单侧辅助
    （面板开合、说明卡生命周期、技能行内容、输入区行高）继续经
    ``_MenuFlow``（``ui.desktop_shared_menus``）拆出。
    """

    # ── ``/`` 与 ``@`` 候选（R2980：光标级触发 token → 光标锚定自绘浮层） ──
    def _schedule_refresh(self):
        """文本改动／几何变化合并成单个 ``after_idle`` 刷新（REQ-S01-107：
        一波连续输入只扫一轮；切页／销毁取消待执行回调）。"""
        if self._refresh_job is not None:
            return
        try:
            self._refresh_job = self.after_idle(self._run_pending_refresh)
        except Exception:
            self._refresh_job = None
            app_logging.swallowed()

    def _cancel_pending_refresh(self):
        job = self._refresh_job
        self._refresh_job = None
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                app_logging.swallowed()

    def _flush_pending_refresh(self):
        """Enter／发送走同步判定前，把排队中的重扫先就地跑完（否则刚敲的
        ``/`` 还没开候选，Enter 就把 token 发出去了）。"""
        if self._refresh_job is None:
            return
        self._cancel_pending_refresh()
        self._run_pending_refresh()

    def _run_pending_refresh(self):
        self._refresh_job = None
        try:
            self._refresh_candidates()
        except Exception:
            app_logging.swallowed()
        try:
            self._fit_input_height()
        except Exception:
            app_logging.swallowed()

    def _on_trigger_key(self, _event):
        """``/``、``@`` 键按下：等默认插入完成后重扫光标处触发 token。"""
        self._schedule_refresh()
        return None

    def _on_button_release(self, _event):
        """鼠标点击移动光标不产生 KeyRelease：同样重扫，锚点跟随光标。"""
        self._schedule_refresh()
        return None

    def _raw_text(self):
        try:
            return str(self.input.get('1.0', 'end-1c') or '')
        except Exception:
            return ''

    def _cursor_offset(self):
        """``insert`` 光标折算成文本字符偏移（0 基）。"""
        try:
            index = str(self.input.index('insert'))
            line, _, col = index.partition('.')
            before = self.input.get('1.0', '%s.0' % line)
            return len(before) + int(col or 0)
        except Exception:
            return len(self._raw_text())

    def _on_key_release(self, event):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab', 'ISO_Left_Tab'):
            return
        self._schedule_refresh()

    def _ime_composing(self):
        """输入法组词／选词进行中（best-effort）：Tk 拿不到 IME 组合态，
        只能靠 KeyPress 探针（keycode 229／keysym ``process``）猜；
        测试与宿主可替换本判定，真机覆盖以 Windows 拼音人工项为准。"""
        return bool(self._composing)

    def _on_ime_probe(self, event):
        """KeyPress 探针：组词期常见的 process-key（keycode 229）记为组词中，
        其余按键复位；返回 None 不消费事件，默认插入照常。"""
        try:
            if (getattr(event, 'keycode', 0) == 229
                    or getattr(event, 'keysym', '') == 'process'):
                self._composing = True
            else:
                self._composing = False
        except Exception:
            self._composing = False
        return None

    def _on_escape(self, event):
        """Esc 分层消费：组词中先交输入法；有浮层收一层回 ``'break'``；
        无浮层放行给同组件后绑的宿主绑定（剧本页运行中 Esc＝终止），
        空闲 Esc 不动输入框、不清草稿。"""
        if self._ime_composing():
            return None
        return self.close_completion()

    def _on_return(self, event):
        """Enter 发送（Shift+Enter 换行）；候选开着先采纳当前项不发送（R2980）。

        返回 ``'break'`` 拦截同组件上后绑的页面级 Enter 绑定（如剧本页 send_on_enter），
        保证 13 页共用同一条发送路径；Shift+Enter 返回 None 放行默认换行。
        REQ-S01-107：发送前先把排队中的重扫跑完（刚敲 ``/`` 弹出的候选不会被
        漏判）；输入法组词确认中的 Enter 既不采纳候选也不发任务。
        """
        if getattr(event, 'state', 0) & 0x1:
            return None
        self._flush_pending_refresh()
        if self._ime_composing():
            return None
        if self.candidates.open and self.candidates.entries:
            entry = self.candidates.selected()
            if entry is not None:
                self._apply_candidate(entry)
                return 'break'
        self.send()
        return 'break'

    def _atomic_edit(self, writer):
        """把 ``writer()`` 里连续的 insert/delete 收成一次可撤销动作：
        ``autoseparators`` 会把删、插各自断开，要合并必须临时关掉自动
        分隔、操作前后再补显式分隔符；框不支持 undo 时退回原样执行。"""
        try:
            self.input.edit_separator()
        except tk.TclError:
            writer()
            return
        try:
            self.input.configure(autoseparators=False)
            writer()
        finally:
            try:
                self.input.configure(autoseparators=True)
                self.input.edit_separator()
            except tk.TclError:
                pass

    def _refresh_candidates(self):
        """重扫光标处 ``/``／``@`` token：命中按类别取候选重建浮层，否则收掉。"""
        # 输入命令文本时收掉图标下拉：候选与 ✦／＋ 面板互不叠加（R2971）。
        self._hide_panels()
        token = skill_command.trigger_token(self._raw_text(), self._cursor_offset())
        if token is None:
            self._active_token = None
            if self.candidates.open:
                self.candidates.close()
            return
        self._active_token = token
        # query 尾部已隔空格＝token 已写完：收掉浮层，不再就着旧词重弹。
        if token['query'] != token['query'].rstrip():
            self.candidates.close()
            return
        if token['kind'] == 'mention':
            entries = self._mention_entries(token['query'])
        else:
            entries = skill_command.completion_entries(
                token['query'], stage=self.stage,
                skills=self.skill_items(), engines=self.engine_names())
        if entries:
            self.candidates.refresh(entries, query=token['query'])
        else:
            self.candidates.close()

    def _mention_entries(self, query):
        """``@`` 候选（R2980）：仅剧本准备页，列已入库附件的显示名。

        REQ-S01-107：入库清单按（项目, 阶段）缓存，连续按键不重复扫盘；
        采纳登记新引用或切阶段时失效重取。"""
        if self.stage != 'script':
            return ()
        project = self.project
        if project is None:
            return ()
        key = (str(project), self.stage)
        cached = self._mention_cache
        if cached is None or cached[0] != key:
            try:
                from stage_execution_service import stage_idea_attachment_paths
                paths = tuple(stage_idea_attachment_paths(project))
            except Exception:
                app_logging.swallowed()
                return ()
            self._mention_cache = (key, paths)
        needle = str(query or '').strip().lower()
        entries = []
        try:
            from domain.idea_attachments import display_name
            for path in self._mention_cache[1]:
                name = display_name(path)
                if needle and needle not in name.lower():
                    continue
                entries.append({'kind': 'attachment', 'name': name,
                                'label': '@' + name, 'path': Path(path),
                                'hint': name})
                if len(entries) >= 30:
                    break
        except Exception:
            app_logging.swallowed()
            return ()
        return tuple(entries)

    def _token_index(self, offset):
        """字符偏移 → Tk 行列索引（``1.0 + N chars``）。"""
        return self.input.index('1.0 + %d chars' % max(0, int(offset)))

    def _replace_token(self, token, insert):
        """把 ``[start,end)`` 字符段替换为 ``insert``；插入体（不含尾空格）上 ``shared_token`` tag。"""
        try:
            start = self._token_index(token['start'])
            end = self._token_index(token['end'])
            # token 尾部若已隔一个水平空格，顺手吃掉一个：insert 自带尾空格，
            # 不吃会出现「/name  后文」双空格；换行不吃（不粘连行）。
            if self.input.get(end) in (' ', '\t'):
                end = self.input.index(end + ' + 1 char')
            # 补全插入收成一次可撤销动作：「删 token＋插 /name 」并成一步，
            # Ctrl+Z 一次退回采纳前文本（REQ-S01-107）。
            self._atomic_edit(
                lambda: (self.input.delete(start, end),
                         self.input.insert(start, insert)))
            body = insert.rstrip()
            if body:
                tag_end = self.input.index('%s + %d chars' % (start, len(body)))
                self.input.tag_add('shared_token', start, tag_end)
            caret = self.input.index('%s + %d chars' % (start, len(insert)))
            self.input.mark_set('insert', caret)
            self.input.see(caret)
        except (tk.TclError, TypeError, ValueError, KeyError):
            app_logging.swallowed()

    def _apply_candidate(self, entry):
        """采纳候选：``/`` 换命令 token、``@`` 换引用 token；只替换触发词段。"""
        token = self._active_token
        if token is None or not isinstance(entry, dict):
            self.close_completion()
            return
        kind = str(entry.get('kind') or '')
        if kind == 'attachment' or token['kind'] == 'mention':
            self._apply_mention(entry, token)
            return
        insert = str(entry.get('insert') or '')
        if not insert:
            self.close_completion()
            return
        self._replace_token(token, insert)
        self.close_completion()
        try:
            self.input.focus_set()
        except Exception:
            app_logging.swallowed()

    def _apply_mention(self, entry, token):
        """``@`` 采纳：登记本轮引用并把显示名 token 写回输入框。"""
        name = str(entry.get('name') or '').strip()
        if not name:
            self.close_completion()
            return
        path = entry.get('path')
        if path is not None:
            self._register_attachment(path)
        # R3060：光标处插入的 @引用不进输入框顶部引用区（显示名与引用区一致才排除）。
        desktop = getattr(self, 'desktop', None)
        if desktop is not None:
            cursor = getattr(desktop, '_idea_cursor_ref_names', None)
            if cursor is None:
                cursor = desktop._idea_cursor_ref_names = set()
            cursor.add(name)
        self._replace_token(token, '@' + name + ' ')
        self.close_completion()
        try:
            self.input.focus_set()
        except Exception:
            app_logging.swallowed()

    def _register_attachment(self, path):
        """``@`` 采纳＝本轮显式引用：复用 ``idea_chat_controller.add_attachment`` 登记。"""
        controller = getattr(self.desktop, 'idea_chat_controller', None)
        add = getattr(controller, 'add_attachment', None)
        if not callable(add):
            return
        try:
            add(str(path))
            self._mention_cache = None  # 新引用入库：@ 候选清单下轮重取
        except Exception:
            app_logging.swallowed()

    def close_completion(self):
        """关闭候选浮层与 ✦／＋ 图标下拉（Esc／失焦／切页共用入口）；
        只在确实关掉了浮层时 ``'break'``，否则放行 Esc 的其他宿主绑定
        （如剧本页输入框的「 Esc 中断任务」）。"""
        closed = self.candidates.close()
        self._active_token = None
        if self._hide_panels() or closed == 'break':
            return 'break'
        return None

    # ── 悬停说明卡：与技能行／候选行同一行、行右侧紧贴（Devin 式，R2971 定版） ──
    def _show_skill_card(self, item, owner):
        """悬停卡片：与 ``owner``（技能行／候选行）同一行、在行右侧紧贴显示；
        右缘出屏翻到行左侧，纵向对行中心，最后钳进屏幕（R2971 定版）。"""
        self._cancel_skill_card_hide()
        self._hide_skill_card()
        try:
            body = self._skill_description(item) or '（该技能没有填写 description）'
            card = BaseDialog(self, '', modal=False, chrome=False)
            # 无边框（Flyout／Tooltip 同款）＋ WS_EX_NOACTIVATE，避免 Windows 抢焦导致 / 浮层闪退。
            card.overrideredirect(True)
            make_passive_popup(card)
            apply_noactivate(card)
            card.configure(bg=COLORS['background_card'],
                           highlightthickness=1,
                           highlightbackground=COLORS['border_input_hover'])
            tk.Label(card, text=body, justify='left', wraplength=SKILL_CARD_WRAP,
                     bg=COLORS['background_card'], fg=COLORS['text_primary'],
                     font=FONTS['hint'], padx=SPACING['md'], pady=SPACING['sm']).pack()
            card.bind('<Enter>', lambda _e: self._cancel_skill_card_hide())
            card.bind('<Leave>', lambda _e: self._schedule_skill_card_hide())
            card.update_idletasks()
            card_w, card_h = card.winfo_reqwidth(), card.winfo_reqheight()
            panel = getattr(owner, 'master', None)
            anchor = panel if panel in (getattr(self, 'skill_panel', None),
                                        getattr(getattr(self, 'candidates', None), 'frame', None)) else owner
            px, pw = anchor.winfo_rootx(), anchor.winfo_width() or owner.winfo_width()
            py, ph = owner.winfo_rooty(), owner.winfo_height()
            margin, gap = SPACING['sm'], SPACING['xs']
            mleft, mtop, mright, mbottom = monitor_bounds(
                self.winfo_toplevel(), px + pw + gap, py + ph // 2)
            x = px + pw + gap
            if x + card_w > mright - margin:
                x = px - card_w - gap
            y = py + (ph - card_h) // 2
            x = max(mleft + margin, min(x, mright - card_w - margin))
            y = max(mtop + margin, min(y, mbottom - card_h - margin))
            card.geometry('+%d+%d' % (x, y))
            self._skill_card = card
        except Exception:
            app_logging.swallowed()


class _StageActions:
    """发送键承载的阶段制作动作：页面建页时登记，输入框空着点发送就执行（见 ``send``）。"""

    def set_stage_action(self, stage, action):
        """登记（或替换）这一阶段的发送动作；``action`` 为 None＝取消登记。"""
        self._stage_actions.pop(str(stage or ''), None)
        if action is not None:
            self._stage_actions[str(stage or '')] = action

    def stage_action(self, stage=None):
        """当前（或指定）阶段登记的发送动作；没登记返回 None。"""
        return self._stage_actions.get(str(stage or self.stage))

    def run_stage_action(self, stage=None):
        """执行登记动作；传播 False，旧动作 None 仍视为已执行，运行中不重复开动。"""
        stage = str(stage or self.stage)
        action = self._stage_actions.get(stage)
        if action is None and callable(self.stage_action_fallback):
            action = self.stage_action_fallback(stage)     # SEND-2：五阶段的手动制作兜底
        if action is None:
            return False
        if ui_plugin_registry.module('stage_flow').running(stage):
            _say(self.status, STAGE_ACTION_BUSY % pet_bus.stage_name(stage))
            return False
        result = action()
        return False if result is False else True

    def _sync_send_state(self):
        """SEND-2／REQ-S02-41：本阶段在跑→发送键置灰＋悬停写明；收场恢复。

        只动可用态与悬停：图标归发送键自己与剧本页中断模式（``_send_interrupt``），
        别的闸门置的灰由 stage_flow.apply_state 的既有口径原样保留。"""
        button = getattr(self, 'send_button', None)
        if button is None or getattr(self, '_send_interrupt', False):
            return
        stage = str(self.stage or '')
        running = False
        try:
            flow = ui_plugin_registry.module('stage_flow')
            running = bool(flow.running(stage))
            flow.apply_state(button, stage)
        except Exception:
            app_logging.swallowed()
        tooltip = getattr(self, '_send_tooltip', None)
        if tooltip is not None:
            tooltip.text = (STAGE_ACTION_BUSY % pet_bus.stage_name(stage)
                            if running else SEND_TOOLTIP_IDLE)


class SharedStageInput(_CandidateFlow, _StageActions, ttk.Frame):
    """底部固定共享输入框：单实例跨页复用，``stage`` 只换补全与门禁上下文。"""

    def __init__(self, master, *, desktop=None, stage='script', shortcuts=None, options=None):
        super().__init__(master)
        options = dict(options or {})
        self.desktop = desktop
        self.stage = str(stage or 'script')
        self.status = options.get('status') or _status_of(desktop)
        self.shortcuts = shortcuts if shortcuts is not None else ShortcutRegistry()
        for _key in ('on_send', 'on_upstream_error', 'on_skill_config',
                     'on_attachment', 'on_voice', 'continue_state'):
            setattr(self, _key, options.get(_key))
        self._skills = list(options.get('skills') or ())
        self._engines = options.get('engines')
        self.in_flight = False
        self.request_model = None
        self._stage_actions = {}    # 阶段 → 发送键承载的制作动作（页面建页时登记）
        self.stage_action_fallback = options.get('stage_action_fallback')  # SEND-2：未登记阶段的兜底
        # R2942 流畅度：/ 补全与技能列表每次按键都读注册表/目录，这里按内容树记忆，
        # 导入新 skill 或切阶段后失效。
        self._skills_cache = None
        self._engines_cache = None
        # REQ-S01-107：文本/几何改动合并成单个 after_idle 刷新；销毁前取消。
        self._refresh_job = None
        # （项目根, 阶段）→ 草稿原文：13 页共用一个 Text，各阶段草稿互不覆盖。
        self._drafts = {}
        # 输入法组词探针状态（best-effort，真机覆盖见验收文件）。
        self._composing = False
        self._build()
        _extras_attach(self)   # REQ-S01-112/113：续写条＋发送键图元（唯一接线点）

    # ── 构建 ────────────────────────────────────────────────────────────
    def _build(self):
        # R2923 定版：全部收进一个圆角输入盒——上输入、下一行图标（✦ 技能／＋ 附件／
        # 麦克风语音在左，模型下拉框与发送图标在右，仿 DeepSeek／Devin 桌面）。
        # R2942：模型名不再是无框文字，改为下拉框按钮（点击弹模型列表），位于发送按钮左侧。
        # R3060：输入区与工具行共用一条外框（ttk 主题不支持 -highlight*，外框由
        # 包裹层 input_ring 的 1px 底色边承担，聚焦切换环色）。
        ring, box = _composer_shell(self)
        self.input_ring = ring
        self.input_card = box
        # 附件不再独占卡片行——上传/引用以「@原名」行内文本落在输入框顶部引用区。
        # 输入区去内框线（highlightthickness=0）；width=1：Text 默认按 80 字符报需求宽
        # （≈672px）会顶爆 stage_area 需求宽、面板在最小窗被挤成 1px，实际宽由 fill 决定。
        self.input = _FlowTextArea(
            box, height=TEXT_ROWS['sm'], wrap='word', highlightthickness=0, width=1,
            placeholder='输入指令或补充要求，输入 / 调用技能（Enter 发送，Shift+Enter 换行）')
        self.input._on_flow_edit = self._schedule_refresh
        self.input.pack(fill='x')
        for seq, key in (('<FocusIn>', 'border_input_hover'),
                         ('<FocusOut>', 'border_default')):
            self.input.bind(seq, lambda _e, k=key: ring.configure(bg=COLORS[k]), add='+')

        row = ttk.Frame(box, style='Composer.TFrame')
        row.pack(fill='x')
        # 图标行是 ✦／＋ 面板的锚点（R3031：面板底边贴本行上沿，不再隔整个输入框）。
        self.icon_row = row
        self.skill_button = _row_icon(row, ICON_SKILL, self.open_skill_list)
        self.attachment_button = _row_icon(row, ICON_ADD, self.open_add_menu)
        self.voice_button = _row_icon(row, ICON_MICROPHONE, self._toggle_voice)
        # 圆形描边由命名样式绘制；MDL2 上箭头／方块随运行态切换，不加载 PNG。
        self.send_button = PrimaryButton(
            row, text=ICON_SEND, width=0,
            style='Tokens.Composer.Send.TButton', command=self.send)
        self.send_button.pack(side='right', padx=(SPACING['xs'], SPACING['xs']))
        # R2942：模型选择器=下拉框按钮（点击弹出模型列表），与各页原「模型下拉框」同款，
        # 不再弹模态选择窗。StageModelPicker 自带按钮＋弹出卡片（含推理档位区）。
        # R2964：与发送键拉开一档间距（右侧 padx），避免模型钮贴着发送图标误触。
        from ui.stage_model_picker import StageModelPicker
        self.model_picker = StageModelPicker(row, self.desktop, self.stage)
        self.model_picker.pack(side='right', padx=(SPACING['sm'], SPACING['md']))
        # R2942 定版：五个图标都有悬停提示卡（Tooltip，不进 grab 不抢焦点）。
        Tooltip(self.skill_button, '技能\n点选插入 /名称，勾选=本阶段默认；输入 / 可快速调用')
        Tooltip(self.attachment_button, '添加\n附件、模型与技能导入的统一入口')
        Tooltip(self.voice_button, '语音输入\n点击开始／停止麦克风听写')
        self._send_tooltip = Tooltip(self.send_button, SEND_TOOLTIP_IDLE)
        Tooltip(self.model_picker, '选择模型\n切换本阶段对话模型与推理档位')

        # ``/`` 与 ``@`` 候选：锚在文本光标的卡片浮层（R2980，desktop_shared_menus）。
        self.candidates = CandidatePopup(self)
        self._active_token = None
        self._mention_cache = None
        # 选中候选后插入的 token 范围上共享样式（ui_tokens 取色，不写内联 hex）。
        self.input._refresh_tag_colors(self.input)
        # R2971：✦／＋ 两个图标下拉与 / 补全同一卡片浮层（desktop_shared_menus）；
        # 点面板与各自图标钮之外自动收掉，图标钮自身开合仍走 command。
        self.skill_panel = SkillPickPanel(self)
        self.add_panel = AddMenuPanel(self)
        self._panel_click_top = self.winfo_toplevel()
        self._panel_click_id = (self._panel_click_top.bind(
            '<Button-1>', self._panel_outside_click, add='+')
            if self._panel_click_top is not None else None)
        self.bind('<Destroy>', self._release_panel_click, add='+')
        self.input.bind('<KeyRelease>', self._on_key_release, add='+')
        # 鼠标点光标不触发 KeyRelease：ButtonRelease 同样重扫触发 token。
        self.input.bind('<ButtonRelease>', self._on_button_release, add='+')
        self.input.bind('<Return>', self._on_return, add='+')
        # 输入法组词探针（REQ-S01-107：Tk 拿不到 IME 状态，靠 keycode/keysym 尽力猜）。
        self.input.bind('<KeyPress>', self._on_ime_probe, add='+')
        # 候选开着时：上下键选、Tab 采纳、失焦收掉、窗口重排跟随锚定（DSH 行为）。
        self.input.bind('<Up>', self.candidates.key, add='+')
        self.input.bind('<Down>', self.candidates.key, add='+')
        self.input.bind('<Tab>', self.candidates.key, add='+')
        self.input.bind('<FocusOut>', self.candidates.focus_out, add='+')
        self.input.bind('<FocusOut>',
                        lambda _e: setattr(self, '_composing', False), add='+')
        self.bind('<Configure>', self._on_input_configure, add='+')
        # ``/`` 与 ``@`` 触发、``Esc`` 关闭都走宿主 ShortcutRegistry 登记（任务书轮 3／R2980）。
        self.shortcuts.bind(self.input, ('/',), self._on_trigger_key,
                            scope=SHORTCUT_SCOPE, name='slash_completion')
        self.shortcuts.bind(self.input, ('@',), self._on_trigger_key,
                            scope=SHORTCUT_SCOPE, name='mention_completion')
        self.shortcuts.bind(self.input, ('<Escape>',), self._on_escape,
                            scope=SHORTCUT_SCOPE, name='dismiss_completion')
        self.shortcuts.bind(self.input, ('<KP_Enter>',), self._on_return,
                            scope=SHORTCUT_SCOPE, name='send_on_enter')
        # Tk 的 Text 类绑定不保证 Ctrl+A/Z/Y（Entry 才有），显式补齐标准编辑键；
        # 与 / 触发、Esc 同走 ShortcutRegistry 登记，不落 <Control-> 直绑字面量。
        self.shortcuts.bind(self.input, ('<Control-Key-z>',), self.input._do_undo,
                            scope=SHORTCUT_SCOPE, name='edit_undo')
        self.shortcuts.bind(self.input, ('<Control-Key-y>',), self.input._do_redo,
                            scope=SHORTCUT_SCOPE, name='edit_redo')
        self.shortcuts.bind(self.input, ('<Control-Key-a>',), self.input._do_select_all,
                            scope=SHORTCUT_SCOPE, name='select_all')
        self._sync_model_label()
        sync = getattr(self.desktop, 'sync_stage_placeholder', None)
        if callable(sync):
            sync(self.input, self.stage)
        tk_timers.repeat(self, 400, self._sync_send_state)   # 阶段在跑→发送键置灰（SEND-2）

    # ── 上下文 ──────────────────────────────────────────────────────────
    @property
    def project(self):
        return project_root(self.desktop)

    def _draft_key(self):
        root = self.project
        return (str(root) if root is not None else '', self.stage)

    def _preserve_draft(self):
        """切走前把本阶段草稿原文按（项目, 阶段）存仓（REQ-S01-107：
        13 页共用一个 Text，各阶段草稿互不覆盖；发送成功或用户删空才清）。"""
        self._drafts[self._draft_key()] = self._raw_text()

    def _restore_draft(self):
        """恢复本阶段草稿原文（无存稿则清空）。阶段切换是上下文恢复不是
        编辑动作：撤销栈先清零，避免 Ctrl+Z 把别页草稿倒灌回本页。"""
        text = self._drafts.get(self._draft_key(), '')
        try:
            self.input.edit_reset()
        except tk.TclError:
            pass
        self.input.delete('1.0', 'end')
        self.input.insert('1.0', text)
        try:
            self.input.mark_set('insert', 'end-1c')
        except tk.TclError:
            pass

    def set_stage(self, stage):
        """切页只换上下文：先把旧阶段草稿存仓，再恢复新阶段草稿，其余照旧
        ——不重建实例，只刷新模型下拉框、补全候选与占位提示。"""
        self._preserve_draft()
        self.stage = str(stage or 'script')
        self._mention_cache = None
        picker = getattr(self, 'model_picker', None)
        if picker is not None:
            try:
                from ui.skill_panel_support import stage_for
                picker.stage = stage_for(self.stage)
            except Exception:
                app_logging.swallowed()
        # R2942：换页先收掉补全弹层（锚点与候选都变），并让技能/引擎缓存下轮重取。
        self.close_completion()
        self._cancel_pending_refresh()
        self._restore_draft()
        self._skills_cache = None
        self._engines_cache = None
        self._sync_model_label()
        sync = getattr(self.desktop, 'sync_stage_placeholder', None)
        if callable(sync):
            sync(self.input, self.stage)
        self._sync_send_state()

    def skill_items(self):
        if self._skills:
            return list(self._skills)
        if self._skills_cache is not None:
            return self._skills_cache
        try:
            import orchestrator.skill_registry as skill_registry
            self._skills_cache = list(skill_registry.default_registry(project=self.project).getAll())
            return self._skills_cache
        except Exception:
            return []

    def engine_names(self):
        if self._engines is not None:
            return tuple(self._engines)
        # 只投影已加载的注册表快照；补全引擎候选不另触发递归发现。
        return skill_command.sub_engine_names(self._skills or self._skills_cache or ())

    # ── 入口回调 ────────────────────────────────────────────────────────
    def open_skill_config(self):
        """阶段配置兜底入口（技能图标现走 open_skill_list，此路保留给宿主回调）。"""
        if callable(self.on_skill_config):
            return self.on_skill_config()
        try:
            return ui_plugin_registry.module('skill_panel').show(self.desktop, self.stage)
        except Exception as exc:
            _say(self.status, '阶段配置打开失败：%s' % exc)
            return None

    # ── 图标下拉面板（R2971 定版：✦ 技能／＋ 添加，与 / 补全同一卡片浮层，
    #    不再弹 BaseDialog；勾选框=本阶段默认 skill，点名插入 /技能名） ──────────
    def open_skill_list(self):
        """✦ 技能下拉：面板开合互斥，点名插入、勾选默认、悬停看说明。"""
        self._show_panel(self.skill_panel)

    def open_add_menu(self):
        """＋ 添加下拉：附件、本阶段模型管理、技能导入（仓库／本地）。"""
        self._show_panel(self.add_panel)

    def open_model_manager(self):
        """＋ 菜单「添加模型…」：复用模型选择器的模型管理入口（模型池唯一门）。"""
        opener = getattr(getattr(self, 'model_picker', None),
                         'open_model_manager', None)
        if callable(opener):
            return opener()
        return ''

    def _toggle_skill_default(self, name):
        """勾选/取消本阶段默认 skill：写回 stage_config（三虎自动流程按此执行）。"""
        import orchestrator.stage_config as stage_config
        project = self.project
        if project is None:
            _say(self.status, '请先打开一个项目，再设置本阶段默认技能')
            return
        skills = self._default_skills()
        if name in skills:
            skills.remove(name)
        else:
            skills.append(name)
        try:
            stage_config.put(project, self.stage, skills=skills)
        except (OSError, ValueError) as exc:
            _say(self.status, '默认技能保存失败：%s' % exc)
            return
        self._hide_skill_card()
        panel = getattr(self, 'skill_panel', None)
        if panel is not None and panel.is_open():
            # 只刷被点那一行的勾选像：整版 refresh 会把未点行弹回未勾选，
            # 与「打开时一律不预勾、点了才体现」的定版冲突。
            sync = getattr(panel, 'sync_check', None)
            if callable(sync):
                sync(name)
            else:
                panel.refresh()

    def _import_skill_repo(self):
        """从仓库地址导入（＋ 菜单「添加技能…」下钻）：走 skill_import_service 同一管线。"""
        from ui_widgets import ask_string, ask_confirmation
        self._hide_panels()
        ref = ask_string(self.winfo_toplevel(), '从仓库导入',
                         'SKILL 仓库地址或本地目录（owner/repo、完整 URL 可带 @分支）：')
        if not ref:
            return
        try:
            import ui.skill_import_service as skill_import_service, orchestrator.skill_registry as skill_registry
            from pathlib import Path
            registry = skill_registry.default_registry(project=self.project)
            program = Path(skill_import_service.__file__).resolve().parent
            report = skill_import_service.import_from_repo(
                str(ref).strip(), program, registry, stage_hint=self.stage,
                layer='project' if self.project else 'user',
                confirm=lambda message: ask_confirmation(
                    self.winfo_toplevel(), '从仓库导入', message, dangerous=True))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            _say(self.status, '仓库导入失败：%s' % exc)
            return
        _say(self.status, '仓库导入完成（%s）' % str(report.get('label') or ''))
        self._skills = []
        self._skills_cache = None

    def _import_skill_local(self):
        """本地安装（＋ 菜单「添加技能…」下钻）：选 SKILL.md/包 → plan_import → perform_import。"""
        from ui.ui_dialogs import FileDialog
        from ui_widgets import ask_confirmation
        self._hide_panels()
        source = FileDialog(self.winfo_toplevel()).open_file(
            title='本地安装', filetypes=[('SKILL', ('*.skill.md', 'SKILL.md')),
                                          ('全部文件', '*.*')])
        if not source:
            return
        try:
            import ui.skill_import_service as skill_import_service, orchestrator.skill_registry as skill_registry
            registry = skill_registry.default_registry(project=self.project)
            layer = 'project' if self.project else 'user'
            plan = skill_import_service.plan_import(
                source, registry.stage_directory_for(self.stage, layer), self.stage, registry)
        except skill_import_service.ImportBlocked as exc:
            _say(self.status, '本地安装失败：%s' % exc)
            return
        if plan['problems']:
            message = ('导入前发现以下问题：\n\n' + '\n'.join('· ' + p for p in plan['problems'])
                       + '\n\n仍要导入吗？')
            if not ask_confirmation(self.winfo_toplevel(), '本地安装', message,
                                    dangerous=True):
                return
        try:
            result = skill_import_service.perform_import(
                plan, skill_import_service.program_of(plan['target_dir']))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            _say(self.status, '本地安装失败：%s' % exc)
            return
        _say(self.status, '已安装技能：' + str(result['target'].name))
        self._skills = []
        self._skills_cache = None

    def open_attachments(self):
        if callable(self.on_attachment):
            return self.on_attachment()
        _say(self.status, ATTACHMENT_UNSUPPORTED)
        return None

    def _toggle_voice(self):
        """麦克风听写开关：宿主接线 VoiceInput（绑定本输入框），首击即开麦。"""
        if callable(self.on_voice):
            voice = self.on_voice(self.voice_button)
            if voice is not None:
                safe = getattr(self.desktop, 'safe', None)
                (safe(voice.toggle) if callable(safe) else voice.toggle)()
            return None
        _say(self.status, '语音输入由当前页面提供')
        return None

    def _sync_model_label(self):
        """模型下拉框刷新：按当前阶段重读模型选项，把已保存的一档摆回按钮文案。"""
        picker = getattr(self, 'model_picker', None)
        if picker is not None:
            try:
                picker.refresh_models()
            except Exception:
                app_logging.swallowed()

    # ── 发送 ────────────────────────────────────────────────────────────
    def text(self):
        try:
            return str(self.input.get('1.0', 'end-1c') or '').strip()
        except Exception:
            return ''

    def clear(self):
        try:
            self.input.delete('1.0', 'end')
        except Exception:
            app_logging.swallowed()
        # 用户删空＝放弃本阶段草稿（REQ-S01-107）：存仓里这份一并清掉。
        self._drafts.pop(self._draft_key(), None)
        # 文本清空后触发 token 失效：候选浮层与图标下拉一并收掉（R2980）。
        self.close_completion()

    def set_text(self, value):
        self.clear()
        self.input.insert('1.0', str(value or ''))

    def request_snapshot(self):
        """请求在途的模型快照：发送瞬间捕获，之后切换模型只影响下一次请求。"""
        try:
            import writing_api
            return writing_api.capture_request(self.project)
        except Exception:
            return None

    def send(self):
        """发送门禁 → 命令解析 → 快照捕获 → 宿主 ``on_send``；返回是否受理。

        REQ-S01-107：在途派遣未结束不受理新发送（连点 Enter／按钮、
        ``on_send`` 内重入只算一次）；同步拒绝与异步失败都不动草稿。"""
        if self.in_flight:
            return False
        self._flush_pending_refresh()
        value = self.text()
        if not value:
            # 空输入框＝执行当前阶段登记的发送动作。S03 仍须过上游门禁并冻结模型，
            # 其余阶段保留原 stage_action 契约：不过门禁、不动在途标记与快照。
            if self.stage != 'storyboard':
                return self.run_stage_action()
            return _send_empty_storyboard(self)
        error = _upstream_error(self)
        if error:
            _say(self.status, error)
            return False
        parsed = skill_command.parse_command(
            value, stage=self.stage, skills=self.skill_items(),
            engines=self.engine_names())
        if self.request_model is None:
            self.request_model = self.request_snapshot()
        self.in_flight = True
        try:
            if callable(self.on_send):
                accepted = self.on_send(value, parsed)
            else:
                accepted = True
        except Exception:
            self.in_flight = False
            raise
        if accepted is False:
            self.in_flight = False
            return False
        self.clear()
        return True

    def end_request(self):
        """宿主请求结束后调用：释放在途标记（模型快照保留供下次比对）。"""
        self.in_flight = False
        self.request_model = None
        self._sync_model_label()

    def destroy(self):
        """销毁前取消待执行刷新：``after_idle`` 回调不再触碰已销毁控件。"""
        self._cancel_pending_refresh()
        super().destroy()
