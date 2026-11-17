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

import app_logging
import domain.skill_command as skill_command
import infra.ui_plugin_registry as ui_plugin_registry
from contract import pet_bus
from ui.desktop_shared_menus import AddMenuPanel, CandidatePopup, SkillPickPanel
from ui_popup import make_passive_popup, monitor_bounds
from ui.ui_shortcuts import ShortcutRegistry
from ui_tokens import (COLORS, FONTS, ICON_ADD, ICON_MICROPHONE, ICON_SEND, ICON_SKILL,
                       SPACING, TEXT_ROWS)
from ui_widgets import BaseDialog, Card, SecondaryButton, TextArea, PrimaryButton, Tooltip

SHORTCUT_SCOPE = 'shared_input'
# 技能悬停说明卡片的换行宽度（像素常量，R2923：避免内联字面量触碰视觉 token 棘轮）。
SKILL_CARD_WRAP = 300


def _widget_path(widget):
    """控件的 Tk 路径：Widget 取 ``_w``；``event.widget`` 在被点控件随绑定销毁时
    回退成路径字符串（R3040），两种形态统一成路径再比较。"""
    if widget is None:
        return ''
    path = getattr(widget, '_w', None)
    return str(path) if path else str(widget)


def _widget_within(widget, ancestor):
    """widget 是否落在 ancestor 子树内（place 出去的浮层也是它的子孙）。

    按路径判：``wpath == apath`` 或以 ``apath + '.'`` 开头；ancestor 为根 ``.``
    时恒真。销毁控件的事件回退字符串与活控件走同一规则，不再依赖 ``.master`` 链
    （字符串没有 master，旧写法对它恒 False，曾把面板内点击误判成外部点击）。
    """
    wpath = _widget_path(widget)
    apath = _widget_path(ancestor)
    if not wpath or not apath:
        return False
    if apath == '.':
        return True
    return wpath == apath or wpath.startswith(apath + '.')


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


def upstream_send_error(project, stage):
    """发送门禁（任务书轮 3）：当前阶段上游空白 → 拒绝并提示；放行返回 ``''``。

    有 ``stage_parallel`` 门禁的阶段走 ``evaluate``（UPSTREAM_BLANK／BLOCKED 都拦）；
    没有门禁行的非 script 阶段看紧邻上游阶段的 ``completion_evidence``，上游被显式
    跳过（skipped）时豁免；``script`` 与无项目一律放行（简报门禁由宿主发送路径负责）。
    """
    stage = str(stage or '')
    if not stage or stage == 'script' or stage not in pet_bus.STAGES:
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
    try:
        from orchestrator.stage_completion_service import completion_evidence
        ok, detail = completion_evidence(project, upstream)
    except Exception:
        return ''
    if ok:
        return ''
    return '请先完成/确认「%s」阶段（%s）' % (pet_bus.stage_name(upstream), detail or '上游成果未完成')


RING_INSET = SPACING['xs'] // 4  # 输入框外环露边宽度（1px）


def _composer_shell(parent):
    """R3060：输入区与工具行共用一条外框——外框由包裹层 1px 底色边承担
    （ttk 主题不支持 -highlight*），Card 内缩 RING_INSET 露出环色。"""
    ring = tk.Frame(parent, bg=COLORS['border_default'])
    ring.pack(side='left', fill='both', expand=True,
             padx=(SPACING['sm'], SPACING['none']))
    box = Card(ring, padding=(SPACING['sm'], SPACING['xs']))
    box.pack(fill='both', expand=True, padx=RING_INSET, pady=RING_INSET)
    return ring, box


def _row_icon(row, glyph, command):
    """工具行左侧图标钮（✦／＋／麦克风同款）：无边框字形钮，左对齐排布。"""
    button = SecondaryButton(row, text=glyph, width=0,
                             style='Tokens.Composer.Icon.TButton', command=command)
    button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
    return button


class _CandidateFlow:
    """``/`` 与 ``@`` 光标级候选流（R2980）：触发 token 扫描 → 候选条目 →
    光标锚定自绘浮层的采纳与文本替换。

    ``SharedStageInput`` 继承本类；只依赖宿主已建好的 ``input``／``stage``／
    ``desktop``／``status`` 与 ``skill_items``／``engine_names``／``send`` 等
    既有入口，拆出只为把宿主类压回复杂度棘轮线以内。
    """

    # ── ``/`` 与 ``@`` 候选（R2980：光标级触发 token → 光标锚定自绘浮层） ──
    def _on_trigger_key(self, _event):
        """``/``、``@`` 键按下：等默认插入完成后重扫光标处触发 token。"""
        try:
            self.after_idle(self._refresh_candidates)
        except Exception:
            app_logging.swallowed()
        return None

    def _on_button_release(self, _event):
        """鼠标点击移动光标不产生 KeyRelease：同样重扫，锚点跟随光标。"""
        try:
            self.after_idle(self._refresh_candidates)
        except Exception:
            app_logging.swallowed()
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
        self._refresh_candidates()

    def _on_return(self, event):
        """Enter 发送（Shift+Enter 换行）；候选开着先采纳当前项不发送（R2980）。

        返回 ``'break'`` 拦截同组件上后绑的页面级 Enter 绑定（如剧本页 send_on_enter），
        保证 13 页共用同一条发送路径；Shift+Enter 返回 None 放行默认换行。
        """
        if getattr(event, 'state', 0) & 0x1:
            return None
        if self.candidates.open and self.candidates.entries:
            entry = self.candidates.selected()
            if entry is not None:
                self._apply_candidate(entry)
                return 'break'
        self.send()
        return 'break'

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
        """``@`` 候选（R2980）：仅剧本准备页，列已入库附件的显示名。"""
        if self.stage != 'script':
            return ()
        project = self.project
        if project is None:
            return ()
        needle = str(query or '').strip().lower()
        entries = []
        try:
            from domain.idea_attachments import display_name
            from stage_execution_service import stage_idea_attachment_paths
            for path in stage_idea_attachment_paths(project):
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
            self.input.delete(start, end)
            self.input.insert(start, insert)
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
        except Exception:
            app_logging.swallowed()

    def _on_input_configure(self, event=None):
        if event is not None and getattr(event, 'widget', None) is not self:
            return
        if self.candidates.open:
            try:
                self.after_idle(self.candidates.place)
            except Exception:
                app_logging.swallowed()
        for panel in (getattr(self, 'skill_panel', None),
                      getattr(self, 'add_panel', None)):
            if panel is not None and panel.is_open():
                try:
                    self.after_idle(panel.place_panel)
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


class SharedStageInput(_CandidateFlow, ttk.Frame):
    """底部固定共享输入框：单实例跨页复用，``stage`` 只换补全与门禁上下文。"""

    def __init__(self, master, *, desktop=None, stage='script', shortcuts=None, options=None):
        super().__init__(master)
        options = dict(options or {})
        self.desktop = desktop
        self.stage = str(stage or 'script')
        self.status = options.get('status') or _status_of(desktop)
        self.shortcuts = shortcuts if shortcuts is not None else ShortcutRegistry()
        self.on_send = options.get('on_send')
        self.on_skill_config = options.get('on_skill_config')
        self.on_attachment = options.get('on_attachment')
        self.on_voice = options.get('on_voice')
        self._skills = list(options.get('skills') or ())
        self._engines = options.get('engines')
        self.in_flight = False
        self.request_model = None
        # R2942 流畅度：/ 补全与技能列表每次按键都读注册表/目录，这里按内容树记忆，
        # 导入新 skill 或切阶段后失效。
        self._skills_cache = None
        self._engines_cache = None
        self._build()

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
        self.input = TextArea(box, height=TEXT_ROWS['sm'], wrap='word',
                              highlightthickness=0, width=1)
        self.input.pack(fill='x')
        for seq, color in (('<FocusIn>', COLORS['border_input_hover']),
                           ('<FocusOut>', COLORS['border_default'])):
            self.input.bind(seq, lambda _e, c=color: ring.configure(bg=c), add='+')

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
        Tooltip(self.send_button, '发送（Enter）\nShift+Enter 换行；运行中变为终止')
        Tooltip(self.model_picker, '选择模型\n切换本阶段对话模型与推理档位')

        # ``/`` 与 ``@`` 候选：锚在文本光标的卡片浮层（R2980，desktop_shared_menus）。
        self.candidates = CandidatePopup(self)
        self._active_token = None
        self._mention_cache = None
        # 选中候选后插入的 token 范围上共享样式（ui_tokens 取色，不写内联 hex）。
        self.input.tag_configure('shared_token',
                                 background=COLORS['primary_subtle'],
                                 foreground=COLORS['selection_text'])
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
        # 候选开着时：上下键选、Tab 采纳、失焦收掉、窗口重排跟随锚定（DSH 行为）。
        self.input.bind('<Up>', self.candidates.key, add='+')
        self.input.bind('<Down>', self.candidates.key, add='+')
        self.input.bind('<Tab>', self.candidates.key, add='+')
        self.input.bind('<FocusOut>', self.candidates.focus_out, add='+')
        self.bind('<Configure>', self._on_input_configure, add='+')
        # ``/`` 与 ``@`` 触发、``Esc`` 关闭都走宿主 ShortcutRegistry 登记（任务书轮 3／R2980）。
        self.shortcuts.bind(self.input, ('/',), self._on_trigger_key,
                            scope=SHORTCUT_SCOPE, name='slash_completion')
        self.shortcuts.bind(self.input, ('@',), self._on_trigger_key,
                            scope=SHORTCUT_SCOPE, name='mention_completion')
        self.shortcuts.bind(self.input, ('<Escape>',),
                            lambda _e: self.close_completion(),
                            scope=SHORTCUT_SCOPE, name='dismiss_completion')
        self.shortcuts.bind(self.input, ('<KP_Enter>',), self._on_return,
                            scope=SHORTCUT_SCOPE, name='send_on_enter')
        self._sync_model_label()

    # ── 上下文 ──────────────────────────────────────────────────────────
    @property
    def project(self):
        return project_root(self.desktop)

    def set_stage(self, stage):
        """切页只换上下文：不重建实例，只刷新模型下拉框与补全候选。"""
        self.stage = str(stage or 'script')
        picker = getattr(self, 'model_picker', None)
        if picker is not None:
            try:
                from ui.skill_panel_support import stage_for
                picker.stage = stage_for(self.stage)
            except Exception:
                app_logging.swallowed()
        # R2942：换页先收掉补全弹层（锚点与候选都变），并让技能/引擎缓存下轮重取。
        self.close_completion()
        self._skills_cache = None
        self._sync_model_label()

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
        if self._engines_cache is not None:
            return self._engines_cache
        try:
            self._engines_cache = tuple(skill_command.sub_engine_names())
            return self._engines_cache
        except Exception:
            return ()

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

    def _show_panel(self, panel):
        """图标下拉互斥展开：先收 / 补全与另一个面板；已开着再点图标＝收起。"""
        self.candidates.close()
        self._active_token = None
        other = self.add_panel if panel is self.skill_panel else self.skill_panel
        if other.is_open():
            other.hide()
        panel.toggle()
        self._hide_skill_card()

    def _hide_panels(self):
        """收掉 ✦／＋ 两个图标下拉与悬停说明卡；返回是否有面板原本开着。"""
        hidden = False
        for panel in (getattr(self, 'skill_panel', None),
                      getattr(self, 'add_panel', None)):
            if panel is not None and panel.is_open():
                panel.hide()
                hidden = True
        self._hide_skill_card()
        return hidden

    def _panel_outside_click(self, event):
        """点在面板与它的图标钮之外：收掉开着的下拉（图标钮开合走 command）。"""
        widget = getattr(event, 'widget', None)
        for panel in (getattr(self, 'skill_panel', None),
                      getattr(self, 'add_panel', None)):
            if panel is None or not panel.is_open():
                continue
            if _widget_within(widget, panel):
                continue
            anchors = [anchor for anchor in panel.anchor_widgets()
                       if anchor is not None]
            if any(_widget_within(widget, anchor) for anchor in anchors):
                continue
            panel.hide()
            self._hide_skill_card()

    def _release_panel_click(self, event):
        """输入框销毁时摘掉整窗 ``<Button-1>`` 监听，不留指向死控件的绑定。"""
        if event.widget is not self:
            return
        top = getattr(self, '_panel_click_top', None)
        funcid = getattr(self, '_panel_click_id', None)
        try:
            if top is not None and funcid:
                top.unbind('<Button-1>', funcid)
        except Exception:
            app_logging.swallowed()

    def _hide_skill_card(self):
        self._cancel_skill_card_hide()
        card = getattr(self, '_skill_card', None)
        self._skill_card = None
        if card is not None:
            try:
                card.destroy()
            except Exception:
                app_logging.swallowed()

    @staticmethod
    def _skill_name(item):
        """技能规范名：``Skill`` 对象取 ``.name``、字典取 ``name``、字符串原样——
        不取 ``str(item)`` 的 ``Skill(name @ stage)`` repr，也不映射别名。"""
        if isinstance(item, dict):
            return str(item.get('name') or '')
        name = getattr(item, 'name', None)
        if name is not None:
            return str(name)
        return str(item or '')

    @staticmethod
    def _skill_display(item):
        """列表行只显示技能包原始 ``name``（REQ-S01-91），不拼 displayName。"""
        return SharedStageInput._skill_name(item) or '（未命名技能）'

    def _skill_stage(self, item):
        """技能归属阶段 id（``stage_id`` 归一）：显式 ``stage`` 字段优先，
        缺失按名回查注册表；判不出返回 ``''``。"""
        stage = item.get('stage') if isinstance(item, dict) else getattr(item, 'stage', None)
        if not stage:
            name = self._skill_name(item)
            if name:
                try:
                    import skill_registry
                    found = skill_registry.default_registry().getById(name)
                    stage = getattr(found, 'stage', None) if found is not None else None
                except Exception:
                    app_logging.swallowed()
        if not stage:
            return ''
        try:
            import skill_registry
            return skill_registry.stage_id(stage)
        except Exception:
            return str(stage)

    def _skill_defaultable(self, item):
        """可设为本阶段默认：项目已开 且 归属阶段==当前阶段（R3040：
        跨阶段与判不出阶段的行不给会永远写不进的死勾选框）。"""
        if self.project is None:
            return False
        own = self._skill_stage(item)
        if not own:
            return False
        try:
            import skill_registry
            return own == skill_registry.stage_id(self.stage)
        except Exception:
            return own == self.stage

    def _skill_list_items(self):
        """当前阶段技能在前、其余在后；去重、限量。"""
        try:
            import orchestrator.skill_registry as skill_registry
            registry = skill_registry.default_registry(project=self.project)
            current = list(registry.getByStage(self.stage))
            seen = {self._skill_name(item) for item in current if self._skill_name(item)}
            others = [item for item in registry.getAll()
                      if self._skill_name(item) and self._skill_name(item) not in seen]
            return (current + others)[:20]
        except Exception:
            app_logging.swallowed()
            return list(self.skill_items())[:20]

    def _default_skills(self):
        """当前阶段在三虎默认里的 skill 名单（stage_config 条目的 skills 字段）。"""
        try:
            import orchestrator.stage_config as stage_config
            project = self.project
            if project is None:
                return []
            entry = stage_config.get(project, self.stage) or {}
            return list(entry.get('skills') or [])
        except Exception:
            app_logging.swallowed()
            return []

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

    # ── 悬停说明卡：与技能行同一行、行右侧紧贴（Devin 式，R2971 定版） ──
    def _schedule_skill_card_hide(self):
        """离开技能行延迟收说明卡：给鼠标移向卡片留 200ms 窗口。"""
        self._cancel_skill_card_hide()
        try:
            self._skill_card_hide_id = self.after(200, self._hide_skill_card)
        except Exception:
            app_logging.swallowed()

    def _cancel_skill_card_hide(self):
        job = getattr(self, '_skill_card_hide_id', None)
        self._skill_card_hide_id = None
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                app_logging.swallowed()

    def _show_skill_card(self, item, owner):
        """悬停卡片：与 ``owner``（技能行）同一行、在行右侧紧贴显示；
        右缘出屏翻到行左侧，纵向对行中心，最后钳进屏幕（R2971 定版）。"""
        self._cancel_skill_card_hide()
        self._hide_skill_card()
        try:
            body = self._skill_description(item)
            if not body:
                body = '（该技能没有填写 description）'
            card = BaseDialog(self, '', modal=False, chrome=False)
            # 说明卡必须豁免 ui_theme 接管（R2997 悬停状态机口径）：只标 _positioned_once
            # 防得住居中、防不住隐藏初始化挂的 <Map>→grab——grab 一抢，技能行 Leave/Enter
            # 循环、卡片反复弹出（用户报的 bug）。make_passive_popup 摘掉 Map 绑定并恢复
            # 透明度（pet_cloud／ui_popup／ui_tooltip 同款写法）。
            make_passive_popup(card)
            card.configure(bg=COLORS['background_card'])
            tk.Label(card, text=body, justify='left', wraplength=SKILL_CARD_WRAP,
                     bg=COLORS['background_card'], fg=COLORS['text_primary'],
                     font=FONTS['hint'], padx=SPACING['md'], pady=SPACING['sm']).pack()
            # 卡片自身也算悬停区：移入取消待收、移出重新计时。
            card.bind('<Enter>', lambda _e: self._cancel_skill_card_hide())
            card.bind('<Leave>', lambda _e: self._schedule_skill_card_hide())
            card.update_idletasks()
            card_w = card.winfo_reqwidth()
            card_h = card.winfo_reqheight()
            px, py = owner.winfo_rootx(), owner.winfo_rooty()
            pw = owner.winfo_width()
            ph = owner.winfo_height()
            margin = SPACING['sm']
            gap = SPACING['xs']
            # 钳位跟技能行所在显示器走：winfo_screenwidth/height 恒为主屏尺寸，
            # 副屏上会把说明卡拽回主屏矩形（R3031，同 CandidatePopup 修法）。
            mleft, mtop, mright, mbottom = monitor_bounds(
                self.winfo_toplevel(), px + pw + gap, py + ph // 2)
            x = px + pw + gap
            if x + card_w > mright - margin:
                x = px - card_w - gap
            y = py + (ph - card_h) // 2
            x = max(mleft + margin, min(x, mright - card_w - margin))
            y = max(mtop + margin, min(y, mbottom - card_h - margin))
            card.geometry('+%d+%d' % (x, y))
            # Toplevel 的 geometry 定的是含边框的窗口原点，winfo_root* 是客户区
            # 原点——实测一次偏差再按差值贴正（标题栏/侧框宽度随主题变）。
            card.update_idletasks()
            dx = card.winfo_rootx() - x
            dy = card.winfo_rooty() - y
            if dx or dy:
                card.geometry('+%d+%d' % (x - dx, y - dy))
            self._skill_card = card
        except Exception:
            app_logging.swallowed()

    def _skill_description(self, item):
        """悬停说明：字典取 ``description``；``Skill`` 对象直接读属性（``str(item)``
        是 ``Skill(name @ stage)`` repr，不能拿去 ``getById`` 查——R2971 修正）。"""
        if isinstance(item, dict):
            return str(item.get('description') or '')
        desc = getattr(item, 'description', None)
        if desc is not None:
            return str(desc)
        try:
            import orchestrator.skill_registry as skill_registry
            registry = skill_registry.default_registry(project=self.project)
            found = registry.getById(SharedStageInput._skill_name(item))
            if found is not None:
                return str(getattr(found, 'description', '') or '')
        except Exception:
            app_logging.swallowed()
        return ''

    def _pick_skill(self, item):
        """点击技能：把 ``/技能名`` 写进输入框并聚焦（不自动发送）。"""
        name = self._skill_name(item)
        self._hide_panels()
        if name:
            self.set_text('/' + name + ' ')
            try:
                self.input.focus_set()
                self.input.mark_set('insert', 'end-1c')
            except Exception:
                app_logging.swallowed()

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
        _say(self.status, '附件入口由当前页面提供')
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
        """发送门禁 → 命令解析 → 快照捕获 → 宿主 ``on_send``；返回是否受理。"""
        value = self.text()
        if not value:
            return False
        error = upstream_send_error(self.project, self.stage)
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
