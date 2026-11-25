# -*- coding: utf-8 -*-
"""「设置 → SKILL 管理」页：注册 SKILL 树形列表与安装级操作。

分工：本页只做安装级增删查（导入／说明／体检／删除）；阶段勾选仍归各阶段面板，
避免双入口（规则 28）。数据在用户主动打开时后台加载（规则 33）。真实外部包
作为父节点展开包内子技能；阶段目录根部总入口、独立 SKILL、旧包分别标注，
阶段与来源只做列和筛选，不伪造成包。删除走统一回收站口径，内置层只读。

线程封送：worker 只写 ``queue.Queue``，Tk 侧 ``after(50)`` 轮询回填——``after``
只能在 Tk 主线程登记，后台线程直调会抛 ``main thread is not in main loop``，
与 ``desktop_async_tasks`` 同一口径。
"""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.pet_skill_tree import (
    _SOURCE_FILTER_LABELS,
    _build_manage_rows,
    _filters_active,
    _remember_expansion,
    _selected,
    render_manage_rows,
    update_detail,
    STATUS_LABELS,
)
import pet_bus
import skill_import_service
import ui.skill_lifecycle_service as skill_lifecycle_service
import orchestrator.skill_project_layer as skill_project_layer
import skill_registry
import workflow_settings
from contract import platform_tools
from ui_dialogs import FileDialog
from ui_tokens import FONTS, SPACING, TEXT_DESC, TEXT_ROWS
from ui_widgets import (BaseDialog, DataTable, LineInput, SecondaryButton, SelectBox, TextArea,
                        Tooltip, ask_confirmation, ask_string, notify)

PAGE_TITLE = 'SKILL 管理'
NOTE_MANAGE = '展开技能包查看子技能。'
IMPORT_TITLE = '导入 SKILL'
# 树形列表列宽（DataTable 列定义第三位是显示宽度字符数，不走 width= 关键字）。
# 前五个 values 顺序保持原契约（名称/显示名/阶段/层/体检），名称改由树列展示；
# 类型与作用域追加在末尾，供用户分辨真包、独立 SKILL、包内子技能和旧包。
_COLUMNS = (('name', '名称', 180), ('display', '显示名', 140), ('stage', '阶段', 90),
            ('layer', '层', 70), ('status', '体检', 70), ('kind', '类型', 90),
            ('scope', '作用域', 150))
_VISIBLE_COLUMNS = ('display', 'kind', 'stage', 'layer', 'status', 'scope')


def _page_title(frame, text, note):
    """每一格的抬头：一行标题 ＋ 一行说明（与 pet_settings_ui.page_title 同式，本地副本防循环）。"""
    ttk.Label(frame, text=text, font=FONTS['title']).pack(anchor='w')
    ttk.Label(frame, text=note, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).pack(
        anchor='w', pady=(SPACING['xs'], SPACING['md']))


def _project_of(pet):
    """当前项目根（与 pet_settings_ui.token_project 同口径：agent 快照优先、pet 兜底）。"""
    for holder in (getattr(pet, 'agent', None), pet):
        value = getattr(holder, 'project', None)
        if value:
            return Path(value)
    return None


def _program_of(pet):
    """安装根：优先宠物持有的 program（自检喂临时目录时跟着走），退回本模块所在目录。"""
    program = getattr(pet, 'program', None)
    if program:
        return Path(program)
    return Path(skill_import_service.__file__).resolve().parent


def _build_filter_bar(frame, state, apply_filter):
    """筛选行：文本、来源、阶段都只是过滤条件，不参与树的分组身份。"""
    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    ttk.Label(bar, text='筛选').pack(side='left')
    entry = LineInput(bar, textvariable=state['filter_text'])
    entry.pack(side='left', fill='x', expand=True, padx=(SPACING['xs'], SPACING['none']))
    Tooltip(entry, '按名称、说明或包内路径筛选；Ctrl+F 聚焦，Esc 清空文本。')
    source = SelectBox(bar, values=list(_SOURCE_FILTER_LABELS), state='readonly',
                       textvariable=state['source_filter'], fit=True)
    source.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
    source.set('全部来源')
    stage_labels = ['全部阶段'] + [pet_bus.stage_label(sid) for sid in pet_bus.STAGES]
    state['stage_ids'] = {'全部阶段': ''}
    state['stage_ids'].update({pet_bus.stage_label(sid): sid for sid in pet_bus.STAGES})
    stage = SelectBox(bar, values=stage_labels, state='readonly',
                      textvariable=state['stage_filter'], fit=True)
    stage.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
    stage.set('全部阶段')
    clear = SecondaryButton(bar, text='清空', command=lambda: clear_filter(state, apply_filter))
    clear.pack(side='left', padx=(SPACING['sm'], SPACING['none']))

    def changed(*_args):
        apply_filter()

    state['filter_text'].trace_add('write', changed)
    state['source_filter'].trace_add('write', changed)
    state['stage_filter'].trace_add('write', changed)
    source.bind('<<ComboboxSelected>>', lambda _event: apply_filter(), add='+')
    stage.bind('<<ComboboxSelected>>', lambda _event: apply_filter(), add='+')

    def escape(_event=None):
        if state['filter_text'].get():
            state['filter_text'].set('')
            return 'break'
        return None

    entry.bind('<Escape>', escape, add='+')
    return {'entry': entry, 'source': source, 'stage': stage, 'clear': clear}


def clear_filter(state, apply_filter):
    state['filter_text'].set('')
    state['source_filter'].set('全部来源')
    state['stage_filter'].set('全部阶段')
    apply_filter()
    return True


def _delete_block_reason(selected, state):
    """删除按钮口径：包内行与阶段总入口都不能伪装成可独立回收的安装包。"""
    if selected is None:
        return '先在列表里选中一个 SKILL。'
    kind = selected.row.get('kind') if hasattr(selected, 'row') else ''
    if kind == 'child':
        return '包内子技能随父包管理，不能单独删除。'
    if kind == 'legacy':
        return ''
    if kind == 'stage-entry':
        return '阶段总入口不是技能包；为避免误回收整个阶段目录，这里不提供删除。'
    if getattr(selected, 'layer', '') == 'builtin':
        return '内置 SKILL 只读，不能删除。'
    return skill_lifecycle_service.skill_delete_block_reason(state['project'], selected.name)


def _delete_tip_text(selected, reason):
    if reason:
        return reason
    kind = selected.row.get('kind') if hasattr(selected, 'row') else ''
    return ('将所选旧包整包移入回收站。' if kind == 'legacy'
            else '将所选 SKILL 移入回收站。')


def skills_page(frame, pet, width=None):
    """设置页「SKILL 管理」格；返回 seams（hint 供底部保存回退文案）。"""
    _page_title(frame, PAGE_TITLE, NOTE_MANAGE)
    hint = tk.StringVar(value='列表在后台加载，打开项目后项目层 SKILL 也会列出。')
    project = _project_of(pet)
    registry = skill_registry.default_registry(_program_of(pet), project=project)
    state = {'skills': [], 'disabled': [], 'health': {}, 'registry': registry,
             'project': project, 'tk': frame, 'problems': 0, 'error': '', 'load_gen': 0,
             'rows': [], 'rowmap': {}, 'expanded': set(),
             'filter_text': tk.StringVar(value=''), 'source_filter': tk.StringVar(value='全部来源'),
             'stage_filter': tk.StringVar(value='全部阶段'), 'stage_ids': {}, 'detail': None}

    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    SecondaryButton(bar, text='导入 SKILL…',
                    command=lambda: import_dialog(pet, state, refresh)).pack(side='left')
    SecondaryButton(bar, text='体检详情',
                    command=lambda: health_dialog(pet, state)).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    SecondaryButton(bar, text='残留包管理…', command=lambda: residue_dialog(pet, refresh)).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    SecondaryButton(bar, text='刷新', command=lambda: load(state, fill)).pack(side='left')

    def apply_filter():
        render_manage_rows(tree, state)
        update_delete_state()
        update_detail(tree, state)

    filter_widgets = _build_filter_bar(frame, state, apply_filter)
    table = DataTable(frame, columns=list(_COLUMNS), height=TEXT_ROWS['xl'],
                      show='tree headings', empty_text='暂无 SKILL，点「导入 SKILL…」添加。',
                      auto_hide_scrollbars=True, takefocus=True)
    table.pack(fill='both', expand=True, pady=(SPACING['sm'], SPACING['none']))
    tree = table.tree
    tree.heading('#0', text='技能包 / 技能', anchor='w')
    tree.column('#0', width=_COLUMNS[0][2], stretch=True)
    tree.configure(displaycolumns=list(_VISIBLE_COLUMNS))

    actions = ttk.Frame(frame)
    actions.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    SecondaryButton(actions, text='查看说明',
                    command=lambda: show_note(pet, tree, state)).pack(side='left')
    SecondaryButton(actions, text='重命名…',
                    command=lambda: rename_skill(pet, tree, state, refresh, hint)).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    SecondaryButton(actions, text='编辑',
                    command=lambda: edit_skill(pet, tree, state, hint)).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    SecondaryButton(actions, text='禁用/启用',
                    command=lambda: toggle_disabled(pet, tree, state, refresh, hint)).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    delete = SecondaryButton(actions, text='删除',
                             command=lambda: remove_skill(pet, tree, state, refresh, hint))
    delete.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
    delete_tip = Tooltip(delete, '先在列表里选中一个 SKILL。')

    detail = TextArea(frame, height=TEXT_ROWS['md'], wrap='word', state='disabled')
    detail.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    state['detail'] = detail

    def update_delete_state(_event=None):
        selected_item = _selected(tree, state)
        reason = _delete_block_reason(selected_item, state)
        delete.state(['disabled'] if reason else ['!disabled'])
        delete_tip.text = _delete_tip_text(selected_item, reason)

    def toggle_row(_event=None):
        item = tree.focus()
        if item and tree.get_children(item):
            tree.item(item, open=not bool(tree.item(item, 'open')))
            if tree.item(item, 'open'):
                state['expanded'].add(item)
            else:
                state['expanded'].discard(item)
            return 'break'
        return None

    def focus_filter(_event=None):
        if not frame.winfo_manager():
            return None
        filter_widgets['entry'].focus_set()
        filter_widgets['entry'].select_range(0, 'end')
        return 'break'

    def open_selected(_event=None):
        show_note(pet, tree, state)
        return 'break'

    def selected(_event=None):
        update_delete_state()
        update_detail(tree, state)

    state['update_delete_state'] = update_delete_state
    tree.bind('<<TreeviewSelect>>', selected, add='+')
    tree.bind('<<TreeviewOpen>>', _remember_expansion(tree, state, True), add='+')
    tree.bind('<<TreeviewClose>>', _remember_expansion(tree, state, False), add='+')
    tree.bind('<space>', toggle_row, add='+')
    tree.bind('<Return>', open_selected, add='+')
    tree.bind('<Control-f>', focus_filter, add='+')
    frame.winfo_toplevel().bind('<Control-f>', focus_filter, add='+')
    update_delete_state()
    update_detail(tree, state)
    ttk.Label(frame, textvariable=hint, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))

    def refresh():
        load(state, fill)

    def fill():
        visible = render_manage_rows(tree, state)
        update_delete_state()
        update_detail(tree, state)
        first = tree.get_children()
        if first and not tree.focus():
            tree.focus(first[0])
        if state.get('error'):
            hint.set('SKILL 列表加载失败：%s' % state['error'])
            return
        counts = {}
        for row in state['health'].values():
            counts[row] = counts.get(row, 0) + 1
        summary = '共 %d 个注册 SKILL' % len(state['skills'])
        packages = sum(1 for item in state.get('rows', []) if item.row.get('kind') == 'package')
        legacy = sum(1 for item in state.get('rows', []) if item.row.get('kind') == 'legacy')
        if packages or legacy:
            summary += '；技能包 %d 个、旧包 %d 个' % (packages, legacy)
        if _filters_active(state):
            summary += '；筛选后可见 %d 行' % visible
        if counts:
            summary += '；体检：' + ' · '.join('%s %d' % (STATUS_LABELS.get(k, k), v)
                                              for k, v in sorted(counts.items()))
        if state['problems'] > 0:
            summary += '；另有全局问题/警告 %d 条' % state['problems']
        hint.set(summary + '。包内子技能随父包管理；阶段与来源只是列和筛选条件。')

    load(state, fill)
    return {'hint': hint, 'tree': tree, 'state': state, 'refresh': refresh,
            'delete': delete, 'delete_tip': delete_tip, 'detail': detail,
            'filter': filter_widgets, 'apply_filter': apply_filter}


def load(state, done):
    """后台扫描注册表＋体检报告；worker 只写队列，Tk 侧轮询回填（规则 33）。

    ``after`` 只能在 Tk 主线程登记，后台线程直调会抛 ``main thread is not in
    main loop``；结果经 ``queue.Queue`` 交接，主线程 ``after(50)`` 轮询，与
    ``desktop_async_tasks`` 同一封送口径。``load_gen`` 防止连续刷新时旧轮询
    回填过期结果；页面销毁后轮询自行停止。
    """
    registry = state['registry']
    project = state['project']
    result_q = queue.Queue()
    state['load_gen'] += 1
    generation = state['load_gen']

    def work():
        try:
            registry.scan(force=True)
            skills = list(registry.getAll())
            disabled = _disabled_skill_objects(registry)
            program = skill_import_service.program_of_registry(registry)
            scan_program = program or Path(registry.root).parent
            modified = (skill_import_service.local_modifications(program)
                        if program is not None else {})
            report = workflow_settings.skill_health_report(
                registry, project=project, local_modified=modified)
            health = {row.get('name'): row.get('status') for row in report.get('skills', [])}
            problems = len(report.get('problems', ())) + len(report.get('warnings', ()))
            rows = _build_manage_rows(skills, disabled, scan_program)
            result_q.put((skills, disabled, rows, health, problems, ''))
        except Exception as exc:
            result_q.put(([], [], [], {}, 0, str(exc)))

    def poll():
        widget = state['tk']
        try:
            alive = widget.winfo_exists()
        except tk.TclError:
            alive = False
        if not alive or state['load_gen'] != generation:
            return
        try:
            skills, disabled, rows, health, problems, error = result_q.get_nowait()
        except queue.Empty:
            widget.after(50, poll)
            return
        state['skills'], state['disabled'] = skills, disabled
        state['rows'] = rows
        state['health'], state['problems'] = health, problems
        state['error'] = error
        done()

    threading.Thread(target=work, name='skills-manage-load', daemon=True).start()
    state['tk'].after(50, poll)


def _disabled_skill_objects(registry):
    """禁用登记 → 可展示的 Skill 对象：尽量解析盘上文件取显示名/阶段/正文。"""
    out = []
    for entry in registry.disabled_entries():
        name = str(entry.get('name') or '')
        if not name:
            continue
        path = Path(str(entry.get('path') or '')) if entry.get('path') else None
        meta, body = {}, ''
        if path is not None and path.is_file():
            try:
                meta, body = skill_registry.parse(
                    path.read_text(encoding='utf-8-sig'), source=str(path))
                package_names = {name.casefold() for name in skill_import_service._PACKAGE_ENTRY_NAMES}
                if path.name.casefold() in package_names:
                    meta = skill_registry.imported_package_meta(meta, body, path.parent, path)
            except (OSError, UnicodeError, ValueError):
                meta, body = {}, ''
        if not str(meta.get('name') or ''):
            meta = dict(meta)
            meta['name'] = name
        skill = skill_registry.Skill(meta, body, path,
                                     layer=str(entry.get('layer') or ''))
        out.append(skill)
    return out


def show_note(pet, tree, state):
    """查看说明：选中 SKILL 的说明正文弹窗（只读，不做在线翻译）。"""
    from skill_panel_support import note_text
    skill = _selected(tree, state)
    if skill is None:
        return None
    win = BaseDialog(getattr(pet, 'win', None), 'SKILL 说明：' + str(getattr(skill, 'name', '')),
                     modal=False)
    body = TextArea(win.content, state='disabled')
    body.pack(fill='both', expand=True)
    body.configure(state='normal')
    body.insert('1.0', note_text(skill, localize=False) or '（无说明正文）')
    body.configure(state='disabled')
    SecondaryButton(win.actions, text='关闭', command=win.destroy).pack(side='right')
    return win


def health_dialog(pet, state):
    """体检详情：复用阶段面板的体检报告窗，范围是全部 SKILL。"""
    import skill_panel
    registry = state['registry']
    try:
        program = skill_import_service.program_of_registry(registry)
        modified = (skill_import_service.local_modifications(program)
                    if program is not None else {})
        report = workflow_settings.skill_health_report(
            registry, project=state['project'], local_modified=modified)
    except Exception as exc:
        notify(getattr(pet, 'win', None), 'SKILL 体检失败：%s' % exc, title='SKILL 体检', modal=False)
        return None
    return skill_panel.show_skill_health_report(
        getattr(pet, 'win', None), report, lead='全部',
        refresh=lambda: health_dialog(pet, state))


def _is_disabled_row(tree, state):
    pick = tree.selection()
    return bool(pick) and pick[0].startswith('disabled|')


def _kind_of(item):
    return str(item.row.get('kind') or '') if hasattr(item, 'row') else ''


def _remove_legacy_package(pet, state, skill, refresh, hint):
    """旧包删除：沿用残留包通道的双确认与整包回收凭据。"""
    row = skill.row
    label = str(row.get('relative_path') or getattr(skill, 'name', ''))
    if not ask_confirmation(getattr(pet, 'win', None), '回收旧包',
                            '旧包「%s」未挂载到阶段，不参与执行。将把整包移入回收站，是否继续？'
                            % label, dangerous=True):
        return None
    if not ask_confirmation(getattr(pet, 'win', None), '再次确认回收',
                            '确认回收旧包「%s」及其全部内容？可从程序回收站恢复。' % label,
                            dangerous=True):
        return None
    result = skill_project_layer.dispose_residue(
        _program_of(pet), [label], package_source=skill_registry.Registry._package_source)
    hint.set(result.reason)
    if not result.ok:
        return None
    refresh()
    return result


def remove_skill(pet, tree, state, refresh, hint):
    """删除：仅用户层／项目层；内置层只读，已禁用项按登记路径回收，回收站语义由服务把关。"""
    skill = _selected(tree, state)
    if skill is None:
        hint.set('先在列表里选中一个 SKILL。')
        return None
    kind = _kind_of(skill)
    if kind == 'child':
        hint.set('包内子技能随父包管理，不能单独删除；请选中父包。')
        return None
    if kind == 'legacy':
        return _remove_legacy_package(pet, state, skill, refresh, hint)
    if kind == 'stage-entry':
        hint.set('阶段总入口不是技能包；为避免误回收整个阶段目录，这里不提供删除。')
        return None
    if getattr(skill, 'layer', '') == 'builtin':
        hint.set('内置 SKILL 只读，不能删除；要换行为请用用户层同名覆盖。')
        return None
    reason = skill_lifecycle_service.skill_delete_block_reason(
        state['project'], skill.name)
    if reason:
        hint.set(reason)
        update_delete_state = state.get('update_delete_state')
        if callable(update_delete_state):
            update_delete_state()
        return None
    program = _program_of(pet)
    layer_label = skill_project_layer.LAYER_LABELS.get(getattr(skill, 'layer', ''), '')
    disabled = _is_disabled_row(tree, state)
    names = 'SKILL「%s」（%s版%s）' % (getattr(skill, 'name', ''), layer_label,
                                    '，已禁用' if disabled else '')
    if not ask_confirmation(getattr(pet, 'win', None), '删除 SKILL',
                            '将把%s移入程序回收站（可恢复），是否继续？' % names, dangerous=True):
        return None
    try:
        skill_lifecycle_service.uninstall_skill_entry(
            program, state['registry'], getattr(skill, 'name', ''), project=state['project'])
    except skill_import_service.ImportBlocked as exc:
        hint.set('删除失败：%s' % exc)
        update_delete_state = state.get('update_delete_state')
        if callable(update_delete_state):
            update_delete_state()
        return None
    hint.set('%s 已移入回收站。' % names)
    refresh()
    return True


def rename_skill(pet, tree, state, refresh, hint):
    """重命名：先干跑统计受影响项目，确认后落盘改名并迁引用／台账／禁用登记。"""
    skill = _selected(tree, state)
    if skill is None:
        hint.set('先在列表里选中一个 SKILL。')
        return None
    kind = _kind_of(skill)
    if kind == 'child':
        hint.set('包内子技能不是独立安装项，不能在这里单独重命名。')
        return None
    if kind == 'legacy':
        hint.set('旧包未挂载到注册表，不能按 SKILL 改名；可编辑目录或回收后重新导入。')
        return None
    if kind == 'stage-entry':
        hint.set('阶段总入口不是技能包，不能按包改名；请直接编辑入口文件。')
        return None
    old = getattr(skill, 'name', '') or ''
    new = ask_string(getattr(pet, 'win', None), '重命名 SKILL',
                     '新名称（字母、数字与 . _ -，以字母或数字开头）：', initialvalue=old)
    if new is None:
        return None
    program = _program_of(pet)
    try:
        plan = skill_lifecycle_service.rename_plan(
            program, state['registry'], old, str(new).strip(), project=state['project'])
    except skill_import_service.ImportBlocked as exc:
        hint.set('重命名失败：%s' % exc)
        return None
    affected = plan['affected_count']
    message = ('将把 SKILL「%s」改名为「%s」（%s）。\n\n'
               '· 影响 %d 个项目的阶段配置引用\n'
               '· 导入台账同步改键并重算摘要\n'
               '· 已禁用登记同步改名\n'
               '· 旧文件进回收站（可恢复）\n\n是否继续？'
               % (old, plan['new'], '包' if plan['kind'] == 'package' else '清单', affected))
    if not ask_confirmation(getattr(pet, 'win', None), '重命名 SKILL', message,
                            dangerous=True):
        return None
    try:
        result = skill_lifecycle_service.apply_rename(program, plan)
    except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
        hint.set('重命名失败：%s' % exc)
        return None
    _sync_agents_background(program)
    notify(getattr(pet, 'win', None),
           '已重命名为「%s」；%d 个项目的引用已同步。' % (plan['new'], affected),
           title='重命名 SKILL', modal=False)
    refresh()
    return result


def edit_skill(pet, tree, state, hint):
    """编辑：系统默认程序打开条目（清单开文件、包开目录）；保存后靠指纹热加载生效。"""
    skill = _selected(tree, state)
    if skill is None:
        hint.set('先在列表里选中一个 SKILL。')
        return None
    kind = _kind_of(skill)
    if kind == 'child':
        target = getattr(skill, 'path', None)
    elif kind == 'legacy':
        target = Path(skill.row.get('package_root') or getattr(skill, 'path', '') or '')
    elif kind == 'stage-entry':
        target = getattr(skill, 'path', None)
    else:
        target = None
    if target is not None:
        try:
            platform_tools.open_path(target)
        except (OSError, ValueError) as exc:
            hint.set('打开失败：%s' % exc)
            return None
        hint.set('已交给系统默认程序打开；保存后回到本页点「刷新」即可看到改动。')
        return target
    name = getattr(skill, 'name', '') or ''
    try:
        entry = skill_lifecycle_service.find_skill_entry(_program_of(pet), state['registry'], name)
    except Exception as exc:
        hint.set('定位失败：%s' % exc)
        return None
    if entry is None:
        hint.set('找不到 SKILL「%s」的文件。' % name)
        return None
    target = entry['path'].parent if entry['kind'] == 'package' else entry['path']
    try:
        platform_tools.open_path(target)
    except (OSError, ValueError) as exc:
        hint.set('打开失败：%s' % exc)
        return None
    hint.set('已交给系统默认程序打开；保存后回到本页点「刷新」即可看到改动。')
    return target


def toggle_disabled(pet, tree, state, refresh, hint):
    """启停用：禁用登记进 ``data/skills/disabled_skills.json``，文件保留、列表灰显。"""
    skill = _selected(tree, state)
    if skill is None:
        hint.set('先在列表里选中一个 SKILL。')
        return None
    kind = _kind_of(skill)
    if kind == 'child':
        hint.set('包内子技能随父包启停，不能单独禁用；请选中父包。')
        return None
    if kind == 'legacy':
        hint.set('旧包未挂载到阶段，本来就不参与执行；无需禁用。')
        return None
    name = getattr(skill, 'name', '') or ''
    disabling = not _is_disabled_row(tree, state)
    verb = '禁用' if disabling else '启用'
    if not ask_confirmation(getattr(pet, 'win', None), verb + ' SKILL',
                            '将%s SKILL「%s」（文件保留在磁盘，随时可恢复），是否继续？'
                            % (verb, name), dangerous=disabling):
        return None
    try:
        skill_lifecycle_service.set_skill_disabled(_program_of(pet), state['registry'],
                                                 name, disabled=disabling)
    except skill_import_service.ImportBlocked as exc:
        hint.set('%s失败：%s' % (verb, exc))
        return None
    hint.set('已%s「%s」。%s' % (verb, name,
                               '禁用后不再参与发送与 Agent 同步，可随时启用。'
                               if disabling else '已恢复正常。'))
    refresh()
    return True


def _sync_agents_background(program):
    """改名后后台重算 Codex／Claude／共享 agents 同步标记；失败不阻断页面。"""
    def run():
        try:
            from orchestrator import agent_skill_sync
            agent_skill_sync.sync_all_agent_skills(program=program)
        except Exception:
            import infra.app_logging as app_logging
            app_logging.swallowed('SKILL 管理页改名后 agent 同步失败')
    threading.Thread(target=run, name='skills-manage-agent-sync', daemon=True).start()


class _ImportFlow:
    """导入对话框的取数与安装管线（从 ``import_dialog`` 拆出，函数尺寸门禁）。

    五种来源都汇到同一组 ``single_plan``／``install_plan``／``batch``：单文件与
    文件夹先解析 SKILL 自带阶段再定点安装；ZIP／仓库／链接走批量报告。
    """

    def __init__(self, pet, state, refresh, win, hint, stage_box, layer_var):
        self.pet = pet
        self.state = state
        self.refresh = refresh
        self.win = win
        self.hint = hint
        self.stage_box = stage_box
        self.layer_var = layer_var
        self.project = state['project']
        self.registry = state['registry']

    def stage_hint(self):
        index = self.stage_box.current()
        return pet_bus.STAGES[index - 1] if index and index > 0 else ''

    def layer(self):
        return 'project' if (self.project is not None and self.layer_var.get() == '项目') else 'user'

    def confirm(self, message):
        return ask_confirmation(self.win, IMPORT_TITLE, message, dangerous=True)

    def done(self, report, lead):
        self.win.destroy()
        installed = report.get('installed') or []
        failed = report.get('failed') or []
        skipped = report.get('skipped') or []
        suffix = '成功 %d 个' % len(installed)
        if failed:
            suffix += '；失败 %d 个' % len(failed)
        if skipped:
            suffix += '；跳过 %d 个' % len(skipped)
        notify(getattr(self.pet, 'win', None), '%s（%s）：%s' % (lead, report.get('label', ''), suffix),
               title=IMPORT_TITLE, modal=False)
        self.refresh()

    def single_plan(self, source, stage):
        if not stage:
            self.hint.set('这个 SKILL 没声明阶段，请在上方「默认阶段」里选一个。')
            return None
        target = self.registry.stage_directory_for(stage, self.layer())
        if target is None:
            self.hint.set('找不到「%s」阶段的%s层目录。' % (
                pet_bus.stage_label(stage), '项目' if self.layer() == 'project' else '用户'))
            return None
        try:
            return skill_import_service.plan_import(source, target, stage, self.registry)
        except skill_import_service.ImportBlocked as exc:
            self.hint.set('导入失败：' + str(exc))
            return None

    def install_plan(self, plan, lead):
        alerts = skill_import_service.import_alerts([plan])
        if plan['problems'] or alerts:
            label = (str(plan['source'].parent) if plan['kind'] == 'package'
                     else str(plan['source']))
            parts = [skill_import_service.untrusted_source_notice(label, plans=[plan])]
            if plan['problems']:
                parts.append('导入前发现以下问题：\n\n'
                             + '\n'.join('· ' + p for p in plan['problems']))
            parts.append('仍要导入吗？')
            if not self.confirm('\n\n'.join(parts)):
                return None
        try:
            skill_import_service.perform_import(
                plan, skill_import_service.program_of(plan['target_dir']))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.hint.set('导入失败：' + str(exc))
            return None
        self.win.destroy()
        notify(getattr(self.pet, 'win', None), '%s：%s' % (lead, plan['name']),
               title=IMPORT_TITLE, modal=False)
        self.refresh()
        return plan['name']

    def batch(self, report, lead):
        self.win.destroy()
        self.done(report, lead)

    def pick_file(self):
        source = FileDialog(self.win).open_file(
            title='导入 SKILL',
            filetypes=[('SKILL', ('*.skill.md', 'SKILL.md', '*.md')), ('全部文件', '*.*')])
        if not source:
            return None
        plan = self.single_plan(source, _file_stage(source) or self.stage_hint())
        return self.install_plan(plan, '文件导入完成') if plan else None

    def pick_folder(self):
        folder = FileDialog(self.win).directory(title='导入 SKILL（文件夹）')
        if not folder:
            return None
        try:
            entry = skill_registry.Registry._package_source(Path(folder))
        except OSError:
            entry = None
        if entry is None:
            self.hint.set('所选文件夹不是 SKILL 包（根目录需要 SKILL.md）。')
            return None
        plan = self.single_plan(entry, _package_stage(entry) or self.stage_hint())
        return self.install_plan(plan, '文件夹导入完成') if plan else None

    def pick_archive(self):
        import ui.skill_archive as skill_archive
        path = FileDialog(self.win).open_file(title='导入 SKILL（ZIP）',
                                             filetypes=[('ZIP 压缩包', '*.zip'), ('全部文件', '*.*')])
        if not path:
            return None
        try:
            report = skill_archive.import_archive(
                path, _program_of(self.pet), self.registry, stage_hint=self.stage_hint(),
                confirm=self.confirm,
                options=skill_archive.ArchiveOptions(layer=self.layer()))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.hint.set('ZIP 导入失败：' + str(exc))
            return None
        return self.batch(report, 'ZIP 导入完成')

    def pick_repo(self):
        text = ask_string(self.win, IMPORT_TITLE,
                          'SKILL 仓库地址或本地目录（owner/repo、完整 URL 可带 @分支、本地路径）：')
        if not text or not str(text).strip():
            return None
        try:
            report = skill_import_service.import_from_repo(
                str(text).strip(), _program_of(self.pet), self.registry,
                stage_hint=self.stage_hint(), confirm=self.confirm, layer=self.layer())
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.hint.set('仓库导入失败：' + str(exc))
            return None
        return self.batch(report, '仓库导入完成')

    def pick_url(self):
        import ui.skill_remote_service as skill_remote_service
        text = ask_string(self.win, IMPORT_TITLE, 'SKILL 链接（GitHub 仓库地址或 .zip 直链）：')
        if not text or not str(text).strip():
            return None
        try:
            report = skill_remote_service.import_from_url(
                str(text).strip(), _program_of(self.pet), self.registry,
                stage_hint=self.stage_hint(), confirm=self.confirm, layer=self.layer())
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.hint.set('链接导入失败：' + str(exc))
            return None
        return self.batch(report, '链接导入完成')


def import_dialog(pet, state, refresh):
    """导入入口：五种来源（T2/T3 既有管线）＋默认阶段与导入到选择。"""
    project = state['project']
    win = BaseDialog(getattr(pet, 'win', None), IMPORT_TITLE, modal=False)
    body = win.content
    stage_box = SelectBox(body, values=['（按 SKILL 自带阶段）'] +
                          [pet_bus.stage_label(s) for s in pet_bus.STAGES],
                          state='readonly')
    stage_box.pack(anchor='w', pady=(SPACING['none'], SPACING['sm']))
    stage_box.current(0)
    layer_var = tk.StringVar(value='项目' if project else '全局')
    if project is not None:
        layer_row = ttk.Frame(body)
        layer_row.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
        ttk.Label(layer_row, text='导入到').pack(side='left')
        layer_box = SelectBox(layer_row, values=['项目', '全局'], state='readonly',
                              textvariable=layer_var)
        layer_box.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        layer_box.current(0)
    hint = tk.StringVar(value='单文件／文件夹按 SKILL 自带阶段归档；仓库与链接逐包自报阶段，「默认阶段」兜底。')
    flow = _ImportFlow(pet, state, refresh, win, hint, stage_box, layer_var)

    bar = ttk.Frame(body)
    bar.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    for label, handler in (('文件', flow.pick_file), ('文件夹', flow.pick_folder),
                           ('ZIP', flow.pick_archive), ('仓库', flow.pick_repo),
                           ('链接', flow.pick_url)):
        SecondaryButton(bar, text=label, command=handler).pack(
            side='left', padx=(SPACING['none'], SPACING['xs']))
    ttk.Label(body, textvariable=hint, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
    SecondaryButton(win.actions, text='关闭', command=win.destroy).pack(side='right')
    return win


def residue_dialog(pet, refresh):
    """用户主动打开的批量回收通道；主列表只展示旧包，批量清点与回收仍归这里。"""
    win = BaseDialog(getattr(pet, 'win', None), '残留包管理', modal=False)
    ttk.Label(win.content, text='仅列出非阶段资料包；回收整个包，可在程序回收站恢复。',
              wraplength=TEXT_DESC['wraplength']).pack(anchor='w')
    table = DataTable(win.content, columns=[('name', '包名', _COLUMNS[0][2]),
                                           ('path', '位置', _COLUMNS[1][2]),
                                           ('count', '子技能数', _COLUMNS[3][2]),
                                           ('size', '占用空间', _COLUMNS[2][2]),
                                           ('description', '包说明', _COLUMNS[2][2])],
                      height=TEXT_ROWS['lg'], selectmode='extended', empty_text='没有非阶段残留包。')
    table.pack(fill='both', expand=True, pady=(SPACING['sm'], SPACING['none']))
    hint = tk.StringVar(value='')
    rows = {}

    def load_rows():
        table.tree.delete(*table.tree.get_children())
        rows.clear()
        try:
            for row in skill_project_layer.scan_residue(
                    _program_of(pet), package_source=skill_registry.Registry._package_source):
                key = row['relative_path']
                rows[key] = row
                table.tree.insert('', 'end', iid=key,
                                  values=(row['name'], row['relative_path'], row['sub_skill_count'],
                                          '%s B' % format(row['size'], ','), row['description']))
        except OSError as exc:
            hint.set('残留包扫描失败：' + str(exc))

    def dispose():
        selected = table.tree.selection()
        chosen = [rows[key] for key in selected if key in rows]
        if not chosen:
            hint.set('先选择一个或多个残留包。')
            return None
        if not ask_confirmation(win, '回收残留包',
                                '将以下整包移入回收站？\n' + '\n'.join(row['path'] for row in chosen),
                                dangerous=True):
            return None
        if not ask_confirmation(win, '再次确认回收',
                                '确认回收 %d 个包及其全部内容？可从程序回收站恢复。' % len(chosen),
                                dangerous=True):
            return None
        result = skill_project_layer.dispose_residue(
            _program_of(pet), [row['relative_path'] for row in chosen],
            package_source=skill_registry.Registry._package_source)
        hint.set(result.reason)
        if result.ok:
            load_rows()
            refresh()
        return result

    ttk.Label(win.content, textvariable=hint, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).pack(anchor='w', pady=(SPACING['sm'], SPACING['none']))
    SecondaryButton(win.actions, text='关闭', command=win.destroy).pack(side='right')
    SecondaryButton(win.actions, text='移入回收站…', command=dispose).pack(side='left')
    SecondaryButton(win.actions, text='刷新', command=load_rows).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    win._pet_seams = {'residue': {'tree': table.tree, 'rows': rows, 'dispose': dispose, 'hint': hint}}
    load_rows()
    return win


def _file_stage(source):
    try:
        meta, _body = skill_registry.parse(Path(source).read_text(encoding='utf-8-sig'),
                                           source=str(source))
        return skill_registry.stage_id(meta.get('stage', ''))
    except (OSError, UnicodeError, ValueError):
        return ''


def _package_stage(entry):
    try:
        entry = Path(entry)
        skill_md = entry if entry.is_file() else entry / 'SKILL.md'
        if not skill_md.is_file():
            return ''
        meta, _body = skill_registry.parse(skill_md.read_text(encoding='utf-8-sig'),
                                           source=str(skill_md))
        return skill_registry.stage_id(meta.get('stage', ''))
    except (OSError, UnicodeError, ValueError):
        return ''
