"""共享底部输入框（R2893，任务书轮 3）：13 个阶段页共用同一实例。

布局（任务书 §4）：``[skill 图标][附件图标] | [TextArea 输入框] | [模型图标][发送]``；
视觉 token 走 ``ui_tokens``，快捷键登记走宿主 ``ShortcutRegistry``（``/`` 补全与
``Esc`` 关闭）。命令解析在无 Tk 的 ``skill_command``；发送门禁复用
``stage_parallel`` 上游判定与 ``stage_completion_service.completion_evidence``。

宿主契约（轮 4 由 Desktop／页面接线）：``desktop.root`` 为项目根、
``desktop.status`` 为状态栏 StringVar；``options`` 携带 ``on_send(text,
parsed)``（返回真值表示已受理，假值＝本组件恢复可用态）与 ``on_skill_config``／
``on_attachment``／``on_model`` 三个入口回调、``status``、``skills``、``engines``，
缺省给出可用兜底。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from pathlib import Path

import app_logging
import skill_command
import ui_plugin_registry
from contract import pet_bus
from ui_shortcuts import ShortcutRegistry
from ui_tokens import (COLORS, FONTS, ICON_ADD, ICON_MICROPHONE, ICON_SEND, ICON_SKILL,
                       SPACING, TEXT_ROWS)
from ui_widgets import BaseDialog, Card, SecondaryButton, TextArea, PrimaryButton

SHORTCUT_SCOPE = 'shared_input'
# 技能悬停说明卡片的换行宽度（像素常量，R2923：避免内联字面量触碰视觉 token 棘轮）。
SKILL_CARD_WRAP = 300
# 技能列表浮层里默认勾选框的尺寸（像素常量，同上）。
SKILL_CHECK_SIZE = 14


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
        import stage_parallel
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
        import stage_parallel as _sp
        if _sp.stage_state(project, upstream) in _sp.EXEMPT_STATES:
            return ''
    except Exception:
        app_logging.swallowed()
    try:
        from stage_completion_service import completion_evidence
        ok, detail = completion_evidence(project, upstream)
    except Exception:
        return ''
    if ok:
        return ''
    return '请先完成/确认「%s」阶段（%s）' % (pet_bus.stage_name(upstream), detail or '上游成果未完成')


class SharedStageInput(ttk.Frame):
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
        self.on_model = options.get('on_model')
        self.on_voice = options.get('on_voice')
        self._skills = list(options.get('skills') or ())
        self._engines = options.get('engines')
        self.in_flight = False
        self.request_model = None
        self._completion_open = False
        self._build()

    # ── 构建 ────────────────────────────────────────────────────────────
    def _build(self):
        # R2923 定版：全部收进一个圆角输入盒——上输入、下一行图标（✦ 技能／＋ 附件／
        # 麦克风语音在左，无边框模型名与发送图标在右，仿 DeepSeek／Devin 桌面）。
        # 模型名在发送按钮左侧、无外框只留文字。
        box = Card(self, padding=(SPACING['sm'], SPACING['xs']))
        box.pack(side='left', fill='both', expand=True,
                 padx=(SPACING['sm'], SPACING['none']))
        # 附件卡片行：无附件时不占位（由桌面侧 refresh_uploaded_idea_attachments 管理显隐）。
        from responsive_ui import FlowBar
        self.attachment_panel = FlowBar(box, style='Composer.TFrame')
        self.input = TextArea(box, height=TEXT_ROWS['sm'], wrap='word')
        self.input.pack(fill='x')

        row = ttk.Frame(box)
        row.pack(fill='x')
        self.skill_button = SecondaryButton(row, text=ICON_SKILL, width=0,
                                            style='Tokens.Composer.Icon.TButton',
                                            command=self.open_skill_list)
        self.skill_button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.attachment_button = SecondaryButton(row, text=ICON_ADD, width=0,
                                                 style='Tokens.Composer.Icon.TButton',
                                                 command=self.open_attachments)
        self.attachment_button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.voice_button = SecondaryButton(row, text=ICON_MICROPHONE, width=0,
                                            style='Tokens.Composer.Icon.TButton',
                                            command=self._toggle_voice)
        self.voice_button.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        self.send_button = PrimaryButton(row, text=ICON_SEND, width=0,
                                         style='Tokens.Composer.Send.TButton',
                                         command=self.send)
        self.send_button.pack(side='right', padx=(SPACING['xs'], SPACING['xs']))
        self.model_button = tk.Label(row, text='模型', cursor='hand2',
                                     bg=COLORS['background_card'],
                                     fg=COLORS['text_muted'], font=FONTS['hint'])
        self.model_button.pack(side='right', padx=(SPACING['sm'], SPACING['none']))
        self.model_button.bind('<Button-1>', lambda _event: self.open_model_picker())

        self._completion = ttk.Frame(self)
        self._list = tk.Listbox(self._completion, exportselection=False,
                                height=TEXT_ROWS['md'], font=FONTS['hint'])
        self._list.pack(fill='x')
        self._list.bind('<<ListboxSelect>>', self._choose_completion)
        self._list.bind('<Escape>', lambda _e: self.close_completion())
        self.input.bind('<KeyRelease>', self._on_key_release, add='+')
        self.input.bind('<Return>', self._on_return, add='+')
        # ``/`` 触发与 ``Esc`` 关闭都走宿主 ShortcutRegistry 登记（任务书轮 3 验收）。
        self.shortcuts.bind(self.input, ('/',), self._on_slash_key,
                            scope=SHORTCUT_SCOPE, name='slash_completion')
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
        """切页只换上下文：不重建实例，只刷新补全候选与模型标签。"""
        self.stage = str(stage or 'script')
        self._sync_model_label()
        if self._completion_open:
            self._refresh_completion()

    def skill_items(self):
        if self._skills:
            return list(self._skills)
        try:
            import skill_registry
            return list(skill_registry.default_registry().getAll())
        except Exception:
            return []

    def engine_names(self):
        if self._engines is not None:
            return tuple(self._engines)
        try:
            return skill_command.sub_engine_names()
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

    # ── 技能列表浮层（R2923 定版：Devin 风格——点击图标弹列表，悬停显示简单说明，
    #    勾选框=本阶段默认 skill，供三虎自动流程使用） ──────────────────────────
    def open_skill_list(self):
        if self._skill_menu_open():
            self._close_skill_menu()
            return
        items = self._skill_list_items()
        defaults = self._default_skills()
        menu = BaseDialog(self, '技能', modal=False, chrome=False)
        menu.configure(bg=COLORS['background_card'])
        self._skill_menu = menu
        self._skill_card = None
        self._skill_check_images = []

        header = tk.Label(menu, text='技能（勾选=本阶段默认，点击名字插入 /技能名）', anchor='w',
                          bg=COLORS['background_card'], fg=COLORS['text_muted'],
                          font=FONTS['hint'], padx=SPACING['sm'], pady=SPACING['xs'])
        header.pack(fill='x')

        def hover(_event, item):
            self._show_skill_card(item, menu)

        def leave(_event):
            self._hide_skill_card()

        from ui_icons import IconLoader
        for item in items:
            name = self._skill_name(item)
            line = tk.Frame(menu, bg=COLORS['background_card'])
            line.pack(fill='x')
            if self.project is not None:
                image = IconLoader.check_indicator(menu, size=SKILL_CHECK_SIZE,
                                                   selected=name in defaults)
                self._skill_check_images.append(image)
                check = tk.Label(line, image=image, bg=COLORS['background_card'], cursor='hand2')
                check.pack(side='left', padx=(SPACING['sm'], SPACING['xs']))
                check.bind('<Button-1>', lambda _event, n=name: self._toggle_skill_default(n))
            row = tk.Label(line, text=self._skill_display(item), anchor='w',
                           bg=COLORS['background_card'], fg=COLORS['text_primary'],
                           font=FONTS['body'], pady=SPACING['xs'], cursor='hand2')
            row.pack(side='left', fill='x', expand=True)
            row.bind('<Enter>', lambda event, it=item: hover(event, it))
            row.bind('<Leave>', leave)
            row.bind('<Button-1>', lambda _event, it=item: self._pick_skill(it))

        tk.Frame(menu, bg=COLORS['border_input_hover'], height=1).pack(fill='x',
                                                                       padx=SPACING['sm'])
        for label, action in (('从仓库导入', self._import_skill_repo),
                              ('本地安装 skill', self._import_skill_local)):
            row = tk.Label(menu, text=label, anchor='w',
                           bg=COLORS['background_card'], fg=COLORS['primary'],
                           font=FONTS['body'], padx=SPACING['sm'], pady=SPACING['xs'],
                           cursor='hand2')
            row.pack(fill='x')
            row.bind('<Button-1>', lambda _event, act=action: act())

        menu.update_idletasks()
        x = self.skill_button.winfo_rootx()
        y = self.skill_button.winfo_rooty() - menu.winfo_reqheight() - SPACING['sm']
        menu.geometry('+%d+%d' % (max(0, x), max(0, y)))

    def _skill_menu_open(self):
        menu = getattr(self, '_skill_menu', None)
        return menu is not None and menu.winfo_exists()

    def _close_skill_menu(self):
        menu = getattr(self, '_skill_menu', None)
        self._skill_menu = None
        self._hide_skill_card()
        if menu is not None:
            try:
                menu.destroy()
            except Exception:
                app_logging.swallowed()

    def _hide_skill_card(self):
        card = getattr(self, '_skill_card', None)
        self._skill_card = None
        if card is not None:
            try:
                card.destroy()
            except Exception:
                app_logging.swallowed()

    @staticmethod
    def _skill_name(item):
        if isinstance(item, dict):
            return str(item.get('name') or '')
        return str(item or '')

    @staticmethod
    def _skill_display(item):
        name = SharedStageInput._skill_name(item)
        shown = name
        if isinstance(item, dict) and item.get('displayName'):
            shown = '%s · %s' % (item.get('displayName'), name)
        return shown or '（未命名技能）'

    def _skill_list_items(self):
        """当前阶段技能在前、其余在后；去重、限量。"""
        try:
            import skill_registry
            registry = skill_registry.default_registry()
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
            import stage_config
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
        import stage_config
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
        self._close_skill_menu()
        self.open_skill_list()

    def _show_skill_card(self, item, owner):
        """悬停卡片：浮层右侧用简单文字显示该技能 description（R2923 定版）。"""
        self._hide_skill_card()
        try:
            body = self._skill_description(item)
            if not body:
                body = '（该技能没有填写 description）'
            card = BaseDialog(self, '', modal=False, chrome=False)
            card.configure(bg=COLORS['background_card'])
            tk.Label(card, text=body, justify='left', wraplength=SKILL_CARD_WRAP,
                     bg=COLORS['background_card'], fg=COLORS['text_primary'],
                     font=FONTS['hint'], padx=SPACING['md'], pady=SPACING['sm']).pack()
            card.update_idletasks()
            x = owner.winfo_rootx() + owner.winfo_width()
            y = owner.winfo_rooty()
            card.geometry('+%d+%d' % (x, y))
            self._skill_card = card
        except Exception:
            app_logging.swallowed()

    @staticmethod
    def _skill_description(item):
        if isinstance(item, dict):
            return str(item.get('description') or '')
        try:
            import skill_registry
            registry = skill_registry.default_registry()
            found = registry.getById(str(item))
            return str(found.get('description') or '') if isinstance(found, dict) else ''
        except Exception:
            return ''

    def _pick_skill(self, item):
        """点击技能：把 ``/技能名`` 写进输入框并聚焦（不自动发送）。"""
        name = self._skill_name(item)
        self._close_skill_menu()
        if name:
            self.set_text('/' + name + ' ')
            try:
                self.input.focus_set()
                self.input.icursor('end')
            except Exception:
                app_logging.swallowed()

    def _import_skill_repo(self):
        """从仓库地址导入（浮层底部入口）：走 skill_import_service 同一管线。"""
        from ui_widgets import ask_string, ask_confirmation
        self._close_skill_menu()
        ref = ask_string(self.winfo_toplevel(), '从仓库导入',
                         'SKILL 仓库地址或本地目录（owner/repo、完整 URL 可带 @分支）：')
        if not ref:
            return
        try:
            import skill_import_service, skill_registry
            from pathlib import Path
            registry = skill_registry.default_registry()
            program = Path(skill_import_service.__file__).resolve().parent
            report = skill_import_service.import_from_repo(
                str(ref).strip(), program, registry, stage_hint=self.stage,
                confirm=lambda message: ask_confirmation(
                    self.winfo_toplevel(), '从仓库导入', message, dangerous=True))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            _say(self.status, '仓库导入失败：%s' % exc)
            return
        _say(self.status, '仓库导入完成（%s）' % str(report.get('label') or ''))
        self._skills = []

    def _import_skill_local(self):
        """本地安装（浮层底部入口）：选 SKILL.md/包 → plan_import → perform_import。"""
        from ui_dialogs import FileDialog
        from ui_widgets import ask_confirmation
        self._close_skill_menu()
        source = FileDialog(self.winfo_toplevel()).open_file(
            title='本地安装 skill', filetypes=[('SKILL', ('*.skill.md', 'SKILL.md')),
                                               ('全部文件', '*.*')])
        if not source:
            return
        try:
            import skill_import_service, skill_registry
            registry = skill_registry.default_registry()
            plan = skill_import_service.plan_import(
                source, registry.user_stage_directory_for(self.stage), self.stage, registry)
        except skill_import_service.ImportBlocked as exc:
            _say(self.status, '本地安装失败：%s' % exc)
            return
        if plan['problems']:
            message = ('导入前发现以下问题：\n\n' + '\n'.join('· ' + p for p in plan['problems'])
                       + '\n\n仍要导入吗？')
            if not ask_confirmation(self.winfo_toplevel(), '本地安装 skill', message,
                                    dangerous=True):
                return
        try:
            result = skill_import_service.perform_import(
                plan, skill_import_service.program_of(plan['target_dir']))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            _say(self.status, '本地安装失败：%s' % exc)
            return
        _say(self.status, '已安装 SKILL：' + str(result['target'].name))
        self._skills = []

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

    def open_model_picker(self):
        if callable(self.on_model):
            return self.on_model()
        _say(self.status, '模型选择由当前页面提供')
        return None

    def _sync_model_label(self):
        """输入框右下角模型名（R2916：无边框纯文字；选择逻辑在宿主回调里）。"""
        label = ''
        try:
            import writing_api
            label = str(writing_api.capture_request_model(self.project)['label'] or '')
        except Exception:
            label = ''
        self.model_button.configure(text=label if label else '模型')

    # ── ``/`` 补全 ───────────────────────────────────────────────────────
    def _on_slash_key(self, _event):
        """``/`` 键按下时补全：等默认插入完成后再取文本刷新候选。"""
        try:
            self.after_idle(self._refresh_completion)
        except Exception:
            app_logging.swallowed()
        return None

    def _on_key_release(self, event):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab', 'ISO_Left_Tab'):
            return
        token = skill_command.command_token(self.text())
        if token:
            self._refresh_completion()
        elif self._completion_open:
            self.close_completion()

    def _on_return(self, event):
        """Enter 发送（Shift+Enter 换行）；补全候选优先——有选中先补全不发送。

        返回 ``'break'`` 拦截同组件上后绑的页面级 Enter 绑定（如剧本页 send_on_enter），
        保证 13 页共用同一条发送路径；Shift+Enter 返回 None 放行默认换行。
        """
        if getattr(event, 'state', 0) & 0x1:
            return None
        if self._completion_open and self._list.size():
            selection = self._list.curselection()
            if selection:
                self._apply_completion(self._list.get(selection[0]))
                return 'break'
        self.send()
        return 'break'

    def _refresh_completion(self):
        options = skill_command.completions(self.text(), stage=self.stage,
                                            skills=self.skill_items(),
                                            engines=self.engine_names())
        self._list.delete(0, 'end')
        for item in options[:12]:
            self._list.insert('end', item)
        if self._list.size():
            self._completion.pack(fill='x', padx=SPACING['sm'],
                                  pady=(SPACING['none'], SPACING['xs']))
            self._completion_open = True
        else:
            self.close_completion()

    def _choose_completion(self, _event=None):
        selection = self._list.curselection()
        if selection:
            self._apply_completion(self._list.get(selection[0]))

    def _apply_completion(self, option):
        name = str(option).lstrip('/')
        current = self.text()
        body = current[1:].lstrip() if current.startswith('/') else current
        rest = body.split(' ', 1)[1] if ' ' in body else ''
        self.input.delete('1.0', 'end')
        self.input.insert('1.0', '/' + name + (' ' + rest if rest else ''))
        self.close_completion()

    def close_completion(self):
        """关闭补全层；只在确实关掉了候选时 ``'break'``，否则放行 Esc 的其他宿主绑定
        （如剧本页输入框的「 Esc 中断任务」）。"""
        if self._completion_open:
            self._completion.pack_forget()
            self._completion_open = False
            return 'break'
        return None

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
