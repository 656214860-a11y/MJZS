# -*- coding: utf-8 -*-
"""「设置」窗口：齿轮点开的那四格——基础功能／模型配置／自动化等级／预算（第 44 期）。

用户这一轮的要求：
- 「三虎设置」改名「设置」，入口做成齿轮，摆在窗口左上角标题（V0.7）旁边，做得醒目；
- 点开这一格把原来的「基础」做进去，名字叫「基础功能」；「模型」改名「模型配置」；
- 附件里的「SKILL 管理」这一轮不做。

这一层只管画：落盘与即时生效全在 pet_ui.Pet 上（save_settings／budget_limits…），模型那一格借
pet_models_ui.settings_page 画。窗口照 skill_panel 那套来：Toplevel ＋ transient ＋ Escape 关闭，
关掉不留尾巴；每一格都留了接缝（hint／refresh…），自检按得到、也问得到。
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import pet_agent
import pet_models_ui
import environment_check
import skill_budget
import usage_overview
import token_saver
from app_metadata import APP_NAME
from pet_settings_contract import TABS, LEVEL_NOTES
from ui_tokens import FONTS, SPACING
from ui_widgets import BaseDialog, Card, LineInput, PrimaryButton, SecondaryButton, TextArea, SelectBox

HUB_TITLE = '设置'
HUB_GEOMETRY = '880x620'
# 第 66 期：新加的那一格叫「Token 节省」——附件《Token 节省完整命令清单》全收在这儿。
TOKEN_TITLE = 'Token 节省'
# 分页次序＝用户要的次序：基础功能、模型配置、自动化等级、预算（SKILL 管理不做）。
# 第 46 期第 6 条：第二格改名「三虎模型配置」（用户点名要的名字）。
NOTE_HUB = ('三虎的设置都收在这里：基础功能、三虎模型配置、自动化等级、Token 节省、预算、开发信息。'
            '改完立刻生效，不用重启。')
NOTE_BASIC = '名字、贴片动画、免打扰、开机自启——改完立刻生效，同时写进全局配置。'
NOTE_LEVEL = '这一档决定三虎「自己动手还是等您点头」；写进配置，下次开机照这一档来。'
NOTE_BUDGET = ('硬限制：Token 按天算，其余按项目累计。越线即暂停那一步并报一声——'
               '宁可少做，也不偷偷花钱。')
NAME_NOTE = '名字按规格定死：界面、通知、日志、气泡一律用「三虎」。'
# 第 47 期第 8 条：开发信息那一格——版本、开发者与联系方式在界面里只写这一份。
DEV_TITLE = '开发信息'
APP_TITLE = APP_NAME
DEVELOPER_NAME = 'Bill Lai'
DEVELOPER_MAIL = '2748350153@qq.com'
NOTE_DEV = ('这一格是出身说明：应用叫什么、这一版是第几版、谁做的、怎么联系。'
            '版本号与窗口左上角那一行同源（desktop.VERSION），界面里只有这一份。')
# 预算五类（与 pet_agent.BUDGET_NAMES 同一套机器名）：Token 按天，其余按项目。
BUDGET_FIELDS = (('tokens', 'Token（每天）'), ('image', '生图（每项目）'), ('firstframe', '首帧（每项目）'),
                 ('video', '视频（每项目）'), ('voice', '配音（每项目）'))
UNIT_OF = {'tokens': 'tokens', 'image': '张', 'firstframe': '张', 'video': '个镜头', 'voice': '条'}


def parent_of(pet):
    return getattr(pet, 'win', None)


def open_hub(pet, tab=None):
    """打开「设置」；tab 给了 'basic'／'model'／'level'／'budget' 就直接落在那一格。"""
    parent = parent_of(pet)
    win = BaseDialog(parent, '', modal=False, chrome=False)
    win.title(HUB_TITLE)
    win.geometry(HUB_GEOMETRY)
    win.transient(parent or None)
    win.bind('<Escape>', lambda event: win.destroy())
    body = Card(win)
    body.pack(fill='both', expand=True, padx=SPACING['md'], pady=SPACING['md'])
    ttk.Label(body, text=HUB_TITLE, font=FONTS['title']).pack(anchor='w')
    ttk.Label(body, text=NOTE_HUB, style='Muted.TLabel', wraplength=780).pack(
        anchor='w', pady=(SPACING['xs'], SPACING['sm']))
    # 第 48 期第 1 条：分页头改成自己的按钮行 —— 分页（Notebook）的头里塞不进别的控件，而用户要
    # 「API统一配置」就摆在「三虎模型配置」右边；顺手把「目录」做成真正的按钮：当前那一格用
    # Selected 样式亮着，点一下就切。
    bar = ttk.Frame(body)
    bar.pack(fill='x')
    tabs = {}
    manager_button = None
    for key, title in TABS:
        button = SecondaryButton(bar, text=title, command=lambda k=key: select(win, k))
        button.pack(side='left', padx=(0, SPACING['xs']))
        tabs[key] = button
        if key == 'model':
            # 第 51 期第 1 条：与同排的分页按钮同一格式（原来一个人用琥珀色的 Highlight）。
            manager_button = SecondaryButton(bar, text=pet_models_ui.MANAGER_BUTTON,
                                             command=lambda: pet.open_model_manager())
            manager_button.pack(side='left', padx=(0, SPACING['xs']))
    stack = ttk.Frame(body)
    stack.pack(fill='both', expand=True, pady=(SPACING['sm'], 0))
    pages = {}
    for key, title in TABS:
        pages[key] = ttk.Frame(stack, padding=SPACING['md'])
    seams = {'basic': basic_page(pages['basic'], pet),
             'model': pet_models_ui.settings_page(pages['model'], pet, with_manager=False),
             'level': level_page(pages['level'], pet),
             'token': token_page(pages['token'], pet),
             'budget': budget_page(pages['budget'], pet),
             'dev': dev_page(pages['dev'], pet)}
    seams['model']['manager'] = manager_button          # 那颗键还在这一扇窗里，只是换了一级
    footer = ttk.Frame(body)
    footer.pack(fill='x', pady=(SPACING['sm'], 0))
    SecondaryButton(footer, text='关闭', command=win.destroy).pack(side='right')
    win._pet_tabs = tabs
    win._pet_manager = manager_button
    win._pet_pages = pages
    win._pet_seams = seams
    select(win, tab)
    return win


def select(win, tab=None):
    """把「设置」切到某一格（按钮行 ＋ 页面栈）；认不出的名字就停着不切（绝不抛）。"""
    pages = getattr(win, '_pet_pages', None) or {}
    tabs = getattr(win, '_pet_tabs', None) or {}
    if tab not in pages:
        return None
    try:
        for key, frame in pages.items():
            if key == tab:
                frame.pack(fill='both', expand=True)
            else:
                frame.pack_forget()
        for key, button in tabs.items():
            button.configure(style='Tokens.Primary.TButton' if key == tab else 'Tokens.Secondary.TButton')
        win._pet_tab = tab
    except Exception:
        return None
    return pages[tab]


def current(win):
    """现在亮着的是哪一格（认不出来返回 None）。"""
    return getattr(win, '_pet_tab', None)


def page_title(frame, text, note):
    """每一格的抬头：一行标题 ＋ 一行说明。"""
    ttk.Label(frame, text=text, font=FONTS['title']).pack(anchor='w')
    ttk.Label(frame, text=note, style='Muted.TLabel', wraplength=700).pack(
        anchor='w', pady=(SPACING['xs'], SPACING['md']))


def basic_page(frame, pet):
    """基础功能：名字（只读）、贴片动画、免打扰时段、立刻安静、开机自启。"""
    page_title(frame, '基础功能', NOTE_BASIC)
    now = pet.pet_settings()
    hint = tk.StringVar(value='改完立刻生效，同时写进全局配置。')
    grid = ttk.Frame(frame)
    grid.pack(fill='x', anchor='w')
    grid.columnconfigure(1, weight=1)
    row = 0
    ttk.Label(grid, text='宠物名字').grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    ttk.Label(grid, text=now['name']).grid(row=row, column=1, sticky='w')
    row += 1
    ttk.Label(grid, text=NAME_NOTE, style='Muted.TLabel', wraplength=600).grid(
        row=row, column=1, sticky='w', pady=(0, SPACING['sm']))
    row += 1

    anim = tk.BooleanVar(value=bool(now['anim']))

    def apply_anim():
        state = pet.set_anim(anim.get())
        anim.set(bool(state))
        hint.set('贴片动画已%s。' % ('打开' if state else '关掉'))
        return state

    ttk.Checkbutton(grid, text='贴片动画（关掉更省 CPU）', variable=anim,
                    command=apply_anim).grid(row=row, column=1, sticky='w', pady=(0, SPACING['sm']))
    row += 1
    ttk.Label(grid, text='免打扰时段').grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    window = ttk.Frame(grid)
    window.grid(row=row, column=1, sticky='w')
    start = tk.StringVar(value='%02d' % int(now['dnd'][0]))
    end = tk.StringVar(value='%02d' % int(now['dnd'][1]))
    ttk.Spinbox(window, from_=0, to=23, width=3, textvariable=start).pack(side='left')
    ttk.Label(window, text='点到').pack(side='left', padx=SPACING['xs'])
    ttk.Spinbox(window, from_=0, to=23, width=3, textvariable=end).pack(side='left')
    ttk.Label(window, text='点（这段时间只记账，不打扰）').pack(side='left', padx=SPACING['xs'])

    def save_dnd():
        try:
            pair = pet.set_dnd(int(start.get()), int(end.get()))
        except (TypeError, ValueError):
            hint.set('时段要填 0-23 之间的整点。')
            return None
        if not pair:
            hint.set('时段没改成：起止要各填一个 0-23 的整点，且首尾不能对得一样。')
            return None
        start.set('%02d' % pair[0])
        end.set('%02d' % pair[1])
        hint.set('免打扰时段已改成 %02d:00 - %02d:00。' % pair)
        return pair

    SecondaryButton(window, text='保存时段', command=save_dnd).pack(side='left', padx=(SPACING['sm'], 0))
    row += 1
    ttk.Label(grid, text='立刻安静').grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    snooze = tk.StringVar(value=pet.snooze_label())

    def quiet():
        pet.toggle_snooze()
        snooze.set(pet.snooze_label())
        hint.set(pet.notice)
        return snooze.get()

    SecondaryButton(grid, textvariable=snooze, command=quiet).grid(
        row=row, column=1, sticky='w')
    row += 1
    ttk.Label(grid, text='开机自启').grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
    auto = tk.BooleanVar(value=bool(now['autostart']))

    def apply_autostart():
        state = pet.set_autostart(auto.get())
        auto.set(bool(state))
        hint.set(pet.notice)
        return state

    ttk.Checkbutton(grid, text=pet.autostart_label(), variable=auto,
                    command=apply_autostart).grid(row=row, column=1, sticky='w')
    row += 1
    ttk.Label(grid, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=700).grid(
        row=row, column=0, columnspan=2, sticky='w', pady=(SPACING['md'], 0))
    seams = {'hint': hint, 'anim': anim, 'start': start, 'end': end, 'autostart': auto,
             'snooze': snooze, 'apply_anim': apply_anim, 'save_dnd': save_dnd,
             'apply_autostart': apply_autostart}
    return seams


def level_page(frame, pet):
    """自动化等级：三档各一行（名字 ＋ 一句人话），点哪一档立刻生效并写盘。"""
    page_title(frame, '自动化等级', NOTE_LEVEL)
    hint = tk.StringVar(value='')
    now = pet.level({})
    picked = tk.StringVar(value=now)

    def apply():
        level = picked.get()
        pet.set_level(level)
        hint.set('%s：%s' % (pet_agent.LEVEL_NAMES.get(level, level), pet_ui_note(level)))
        return level

    for level in pet_agent.LEVELS:
        ttk.Radiobutton(frame, text='%s · %s' % (pet_agent.LEVEL_NAMES.get(level, level),
                                                 pet_ui_note(level)),
                        value=level, variable=picked, command=apply).pack(anchor='w', pady=SPACING['xs'])
    ttk.Label(frame, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=700).pack(
        anchor='w', pady=(SPACING['md'], 0))

    def restore():
        picked.set(pet_agent.DEFAULT_LEVEL)
        return apply()

    SecondaryButton(frame, text='回到出厂那一档', command=restore).pack(anchor='w', pady=(SPACING['md'], 0))
    return {'hint': hint, 'picked': picked, 'apply': apply, 'restore': restore}


def pet_ui_note(level):
    """一句话解释自动化档位；标签与界面模块无关。"""
    return LEVEL_NOTES.get(level, '')


def cost_reconciliation_dialog(parent, project):
    """让用户核对已有请求，费用变更独立于制作任务状态。"""
    from pet_llm import RequestLedger
    from ui_dialogs import FileDialog
    ledger = RequestLedger(project).load()
    def eligible():
        return [row for row in ledger.entries if row.get('state') in ('unknown', 'settled', 'cancelled') and not row.get('cost_group')]
    rows = eligible()
    win = BaseDialog(parent, '费用核对', modal=False)
    body = ttk.Frame(win); body.pack(fill='both', expand=True, padx=SPACING["lg"], pady=SPACING["lg"])
    ttk.Label(body, text='请填写本笔请求的最终账单金额；0 表示已确认无费用。\n凭据只保存在本机，不会上传。核对不会重发或取消制作任务。').pack(anchor='w')
    def labels():
        return [f"{row.get('legacy_label', row.get('id'))} / {row.get('kind')} / {row.get('model', '模型未记录')}" for row in rows]
    choices = labels()
    selected = SelectBox(body, values=choices, state='readonly', width=75)
    selected.pack(fill='x', pady=SPACING["sm"])
    fields = {}
    for key, label in [('amount', '最终账单金额'), ('currency', '币种（例如 CNY）'),
                       ('reviewer', '核对人'), ('evidence', '本地账单凭据文件')]:
        ttk.Label(body, text=label).pack(anchor='w')
        fields[key] = tk.StringVar(master=win)
        LineInput(body, textvariable=fields[key]).pack(fill='x')
    hint = tk.StringVar(master=win, value='选择请求后填写账单信息。' if rows else '暂无可核对请求；进行中请求请先查询最终结果。')
    def pick(_event=None):
        row = rows[selected.current()]
        fields['currency'].set(row.get('currency') or '')
        fields['amount'].set('')
        status = {'reserved': '预留', 'unknown': '金额未知', 'estimated': '估算', 'reconciled': '已核对'}
        hint.set('原金额：%s；费用状态：%s；已有 %d 次核对' % (
            row.get('budget_cost') if row.get('budget_cost') is not None else '未知',
            status.get(RequestLedger.effective_money_state(row), '未计价'), len(row.get('cost_reconciliations', []))))
    def browse():
        path = FileDialog(win).open_file(title='选择本地账单凭据')
        if path: fields['evidence'].set(path)
    def save_cost():
        if selected.current() < 0:
            hint.set('请先选择请求。'); return None
        row = rows[selected.current()]
        try:
            result = ledger.reconcile_cost(row['id'], row['kind'], **{key: var.get() for key, var in fields.items()})
        except (ValueError, OSError) as exc:
            hint.set(str(exc)); return None
        rows[selected.current()] = result
        hint.set('已核对：%s %s；已保留凭据摘要和修订记录。' % (result['budget_cost'], result['currency']))
        return result
    def import_legacy():
        try:
            count = ledger.import_legacy_video_costs()
        except (ValueError, OSError) as exc:
            hint.set(str(exc)); return None
        rows[:] = eligible()
        selected.configure(values=labels())
        selected.set('')
        fields['amount'].set('')
        hint.set('已导入或更新 %d 笔旧视频/Comfy云图片费用；金额保持未知，请逐笔核对。进行中任务需先查询最终结果，再重新导入。' % count)
        return count
    selected.bind('<<ComboboxSelected>>', pick)
    SecondaryButton(body, text='导入视频/Comfy 旧账', command=import_legacy).pack(anchor='w', pady=SPACING["sm"])
    SecondaryButton(body, text='选择凭据', command=browse).pack(anchor='w', pady=SPACING["sm"])
    PrimaryButton(body, text='保存核对结果', command=save_cost).pack(anchor='w')
    ttk.Label(body, textvariable=hint, wraplength=650).pack(anchor='w', pady=SPACING["sm"])
    return {'window': win, 'fields': fields, 'selected': selected, 'pick': pick, 'save': save_cost, 'hint': hint,
            'import_legacy': import_legacy}


def budget_page(frame, pet):
    """预算：五类硬限制一张表 ＋ 现在用了多少 ＋ 保存／恢复默认。"""
    page_title(frame, '预算', NOTE_BUDGET)
    limits = pet.budget_limits()
    used = pet.budget_usage().get('used', {})
    hint = tk.StringVar(value='改完点「保存」立刻生效；越线的步骤会被拦下来并报一声。')
    grid = ttk.Frame(frame)
    grid.pack(fill='x', anchor='w')
    grid.columnconfigure(1, weight=1)
    fields = {}
    for row, (kind, label) in enumerate(BUDGET_FIELDS):
        ttk.Label(grid, text=label).grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
        var = tk.StringVar(value=str(limits.get(kind, '')))
        fields[kind] = var
        LineInput(grid, textvariable=var, width=16).grid(row=row, column=1, sticky='w')
        ttk.Label(grid, text='已用 %d %s' % (used.get(kind, 0), UNIT_OF.get(kind, '')),
                  style='Muted.TLabel').grid(row=row, column=2, sticky='w', padx=(SPACING['md'], 0))

    def read():
        return {kind: var.get().strip() for kind, var in fields.items()}

    def save():
        values = read()
        try:
            saved = pet.save_budget_limits(values)
        except ValueError as exc:
            hint.set(str(exc))
            return None
        for kind, var in fields.items():
            var.set(str(saved.get(kind, '')))
        hint.set('已保存预算：%s。' % '；'.join(
            '%s %d' % (pet_agent.BUDGET_NAMES.get(kind, kind), saved.get(kind, 0))
            for kind in pet_agent.BUDGET_KINDS))
        return saved

    def restore():
        for kind, var in fields.items():
            var.set(str(pet_agent.DEFAULT_BUDGET.get(kind, '')))
        hint.set('已填回出厂那五档，点「保存」才真的写盘。')
        return read()

    def show_usage():
        """用量总览：只读汇总当前项目已落盘的模型调用事件与请求台账。"""
        project = token_project(pet)
        if project is None:
            hint.set('还没打开项目，没有可汇总的用量。')
            return None
        snapshot = skill_budget.for_project(project, getattr(pet, 'program', None)).snapshot()
        text = usage_overview.report_text(usage_overview.summarize(project, snapshot))
        from ui_widgets import notify
        notify(pet.win, text, title='用量总览')
        return text

    def reconcile_usage():
        project = token_project(pet)
        if project is None:
            hint.set('还没打开项目，没有可核对的费用。'); return None
        try:
            return cost_reconciliation_dialog(pet.win, project)
        except (ValueError, OSError) as exc:
            hint.set(str(exc)); return None

    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(SPACING['md'], 0))
    PrimaryButton(bar, text='保存', command=save).pack(side='left')
    SecondaryButton(bar, text='恢复默认', command=restore).pack(side='left', padx=(SPACING['sm'], 0))
    SecondaryButton(bar, text='用量总览', command=show_usage).pack(side='left', padx=(SPACING['sm'], 0))
    SecondaryButton(bar, text='费用核对', command=reconcile_usage).pack(side='left', padx=(SPACING['sm'], 0))
    ttk.Label(frame, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=700).pack(
        anchor='w', pady=(SPACING['md'], 0))
    ttk.Label(frame, text='SKILL 那本账（阶段编排）读的就是这几档：%s。' % skill_budget_sentence(),
              style='Muted.TLabel', wraplength=700).pack(anchor='w', pady=(SPACING['sm'], 0))
    return {'hint': hint, 'fields': fields, 'save': save, 'restore': restore, 'read': read, 'show_usage': show_usage,
            'reconcile_usage': reconcile_usage}


NOTE_TOKEN = ('附件那六条通用优化都在这儿：固定前缀在前、推理降档、子 Agent 用 fast、压缩阈值降到 70%、'
              'AGENTS.md 只回结论、.codexignore 少扫。「保存」记住这几档，「写入项目」与「写入全局」'
              '把配置落到盘上。')
TOKEN_ROWS = (('model_reasoning_effort', '推理强度', token_saver.REASONING_EFFORTS),
              ('model_reasoning_summary', '推理摘要', token_saver.SUMMARIES),
              ('model_verbosity', '输出冗长度', token_saver.VERBOSITIES))
TOKEN_ENTRIES = (('model_context_window', '上下文窗口'), ('model_auto_compact_token_limit', '压缩阈值'),
                 ('subagent_model', '子 Agent 模型'), ('max_thinking_tokens', '最大思考 token'),
                 ('subagent_limit', '并行子 Agent'))


def token_seed(pet):
    """这一页要显示的八个值：先读全局配置里存过的那份，读不出来就是出厂那几档。"""
    reader = getattr(pet, 'token_settings', None)
    if callable(reader):
        try:
            return dict(reader() or {})
        except Exception:
            return {}
    return {}


def token_project(pet):
    """当前项目根：AGENTS.md／.codexignore／.codex/config.toml 就写在这儿（没开项目就是 None）。"""
    for holder in (getattr(pet, 'agent', None), pet):
        value = getattr(holder, 'project', None)
        if value:
            return Path(value)
    return None


def token_page(frame, pet):
    """Token 节省：附件那六条通用优化 ＋ 各提供商缓存；改完能写盘（项目级／全局级两张单子）。"""
    page_title(frame, TOKEN_TITLE, NOTE_TOKEN)
    hint = tk.StringVar(value='')
    now = token_saver.normalize(token_seed(pet))
    state = tk.StringVar(value='；'.join(token_saver.scan_lines(token_saver.scan(project=token_project(pet)))))
    ttk.Label(frame, textvariable=state, style='Muted.TLabel', wraplength=780, justify='left').pack(anchor='w')

    grid = ttk.Frame(frame)
    grid.pack(fill='x', anchor='w', pady=(SPACING['sm'], 0))
    grid.columnconfigure(1, weight=1)
    fields = {}
    row = 0
    for key, label, choices in TOKEN_ROWS:
        ttk.Label(grid, text=label).grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
        var = tk.StringVar(value=str(now[key]))
        fields[key] = var
        ttk.OptionMenu(grid, var, str(now[key]), *[str(item) for item in choices]).grid(
            row=row, column=1, sticky='w')
        row += 1
    for key, label in TOKEN_ENTRIES:
        ttk.Label(grid, text=label).grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
        var = tk.StringVar(value=str(now[key]))
        fields[key] = var
        LineInput(grid, textvariable=var, width=14).grid(row=row, column=1, sticky='w')
        row += 1
    note = tk.StringVar(value=token_saver.REASONING_SAVING.get(now['model_reasoning_effort'], ''))
    ttk.Label(grid, textvariable=note, style='Muted.TLabel').grid(
        row=row, column=0, columnspan=2, sticky='w', pady=(SPACING['xs'], 0))

    text = TextArea(frame, height=11, width=92, wrap='none')
    text.pack(fill='both', expand=True, pady=(SPACING['sm'], 0))

    def read():
        return {key: var.get().strip() for key, var in fields.items()}

    def refresh():
        table = token_saver.normalize(read())
        note.set(token_saver.REASONING_SAVING.get(table['model_reasoning_effort'], ''))
        body = token_saver.preview_text(table)
        text.delete('1.0', 'end')
        text.insert('1.0', body)
        return body

    def fill(table):
        for key, var in fields.items():
            var.set(str(table[key]))

    def save():
        table = token_saver.normalize(read())
        fill(table)
        writer = getattr(pet, 'set_token_settings', None)
        if callable(writer):
            try:
                writer(table)
            except Exception as exc:
                hint.set('写盘没成功：%s' % exc)
                refresh()
                return table
        hint.set('已保存：推理 %s，窗口 %s，压缩阈值 %s。' % (table['model_reasoning_effort'],
                                                     table['model_context_window'],
                                                     table['model_auto_compact_token_limit']))
        refresh()
        return table

    def restore():
        table = token_saver.normalize()
        fill(table)
        hint.set('已填回出厂那几档，点「保存」才真的写盘。')
        refresh()
        return table

    def write_project():
        root = token_project(pet)
        if root is None:
            hint.set('还没打开项目，先开一个项目再写。')
            return ()
        try:
            written = token_saver.deliver_project(root, read())
        except OSError as exc:
            hint.set('写项目没成功：%s' % exc)
            return ()
        hint.set('已写进项目：%s。' % '、'.join(path.name for path in written))
        return written

    def write_global():
        try:
            path = token_saver.deliver_global(read(), home=getattr(pet, 'codex_home', None))
        except OSError as exc:
            hint.set('写全局没成功：%s' % exc)
            return None
        hint.set('已写进全局配置：%s' % path)
        return path

    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(SPACING['sm'], 0))
    for label, command, button_class in (("保存", save, PrimaryButton), ("恢复默认", restore, SecondaryButton),
                                         ("写入项目", write_project, SecondaryButton),
                                         ("写入全局", write_global, SecondaryButton)):
        button_class(bar, text=label, command=command).pack(side='left', padx=(0, SPACING['sm']))
    ttk.Label(frame, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=780).pack(
        anchor='w', pady=(SPACING['sm'], 0))
    refresh()
    return {'hint': hint, 'fields': fields, 'values': read, 'save': save, 'restore': restore,
            'write_project': write_project, 'write_global': write_global, 'refresh': refresh,
            'note': note, 'text': text, 'state': state, 'seed': now}


def app_version():
    """版本号来自基础元数据，不为一个常量反向导入桌面宿主。"""
    from app_metadata import VERSION
    return str(VERSION or '')


def runtime_sentence():
    """一句运行环境：本机自带的 Python 与 Tk，用户不用另外装东西。"""
    import platform
    return 'Python %s · Tkinter %s · 本机自带，无需另外安装' % (platform.python_version(), tk.TkVersion)


def dev_page(frame, pet):
    """开发信息：应用名、版本、开发者、邮箱与运行环境，另给一颗「复制邮箱」。"""
    page_title(frame, DEV_TITLE, NOTE_DEV)
    version = app_version()
    hint = tk.StringVar(value='')
    grid = ttk.Frame(frame)
    grid.pack(fill='x', anchor='w')
    grid.columnconfigure(1, weight=1)
    rows = (('应用名称', APP_TITLE), ('当前版本', version or '未知'), ('开发者', DEVELOPER_NAME),
            ('联系方式', DEVELOPER_MAIL), ('运行环境', runtime_sentence()))
    for row, (label, value) in enumerate(rows):
        ttk.Label(grid, text=label).grid(row=row, column=0, sticky='w', padx=(0, SPACING['md']), pady=SPACING['xs'])
        ttk.Label(grid, text=value, wraplength=560, justify='left').grid(row=row, column=1, sticky='w')

    def copy_mail():
        """复制邮箱：剪贴板全程序只有 prompt_window.copy_text 一处出口，这里不另写一份。"""
        from prompt_window import copy_text
        reason = copy_text(pet.win, DEVELOPER_MAIL)
        if reason:
            hint.set('复制失败：%s（%s）；请手动选中复制' % (DEVELOPER_MAIL, reason))
        else:
            hint.set('邮箱已复制：' + DEVELOPER_MAIL)
        return DEVELOPER_MAIL

    def check_environment():
        """环境自检：只读核对外部依赖，结果弹窗显示，不改任何设置。"""
        from ui_widgets import notify
        text = environment_check.report_text()
        notify(pet.win, text, title='环境自检')
        hint.set(environment_check.summary(environment_check.run_checks()))
        return text

    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(SPACING['md'], 0))
    SecondaryButton(bar, text='复制邮箱', command=copy_mail).pack(side='left')
    SecondaryButton(bar, text='环境自检', command=check_environment).pack(side='left', padx=(SPACING['sm'], 0))
    ttk.Label(frame, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=700).pack(
        anchor='w', pady=(SPACING['md'], 0))
    ttk.Label(frame, text='用着不顺、要加功能、发现有错，都发这个邮箱；版本号、开发者与联系方式只在'
                          '「设置 → 开发信息」这一格维护。',
              style='Muted.TLabel', wraplength=700).pack(anchor='w', pady=(SPACING['sm'], 0))
    return {'version': version, 'mail': DEVELOPER_MAIL, 'developer': DEVELOPER_NAME,
            'runtime': runtime_sentence(), 'hint': hint, 'copy_mail': copy_mail,
            'check_environment': check_environment}


def skill_budget_sentence():
    """把 SKILL 编排那本账现在的三档写清楚（只读，改在上面那张表里改）。"""
    now = skill_budget.configured()
    return '、'.join('%s %d' % (skill_budget.LABELS[kind], now[skill_budget.LIMIT_OF[kind]])
                     for kind in skill_budget.KINDS)
