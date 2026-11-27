# -*- coding: utf-8 -*-
"""「设置 → SKILL 管理」页：DSH 主从式两级技能包管理（REQ-UI-SKILL-PAGE-1 / REQ-UI-UNIFY-1）。

左侧固定宽阶段目录（全部阶段 / 00 总包 / 01–13）带徽章计数；右侧上方两级树（技能包 → 子技能 /
L0 主入口）＋右键菜单，下方可折叠完整 Markdown 详情预览与原地编辑器；顶部作用域分段切换
（全部 / 项目版 / 全局版）＋右上角统一动作栏（+ 导入 SKILL、检查更新、体检、刷新、动态残留包）。
支持设置窗内嵌（``skills_page``）与独立窗口（``open_manager``）双入口。
"""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from contract import platform_tools
import orchestrator.skill_project_layer as skill_project_layer
import pet_bus
import skill_import_service
import skill_registry
import ui.skill_lifecycle_service as skill_lifecycle_service
from ui.pet_models_tabs import install_compact_form_styles
from ui.pet_skill_tree import (
    STATUS_LABELS,
    SUITE_LABEL,
    SUITE_STAGE,
    _build_manage_rows,
    _filters_active,
    _remember_expansion,
    _selected,
    render_manage_rows,
    stage_display_label,
    stage_ids_map,
    update_detail,
)
from ui.pet_skills_views import (
    InlineDetailEditor,
    build_search_row,
    build_stage_nav,
    build_top_bar,
    check_updates_dialog as _check_updates_dialog,
    health_dialog,
    open_tree_menu,
    render_md_into_detail,
    show_note,
)
from ui_dialogs import FileDialog
from ui_tokens import BUTTON_GAP, SPACING, TEXT_DESC, TEXT_ROWS
from ui_widgets import (BaseDialog, Card, DataTable, LineInput, PrimaryButton,
                        SecondaryButton, SelectBox, Tooltip, ask_confirmation,
                        ask_string, notify)
import workflow_settings

PAGE_TITLE = 'SKILL 管理'
NOTE_MANAGE = '左侧按阶段目录浏览，右侧展开技能包查看子技能与原地编辑文档。'
IMPORT_TITLE = '导入 SKILL'
MANAGER_GEOMETRY = '1120x760'
MANAGER_MIN = (820, 600)
_COLUMNS = (('name', '名称', 180), ('display', '显示名', 140), ('stage', '阶段', 90),
            ('layer', '层', 70), ('status', '体检', 70), ('kind', '类型', 90),
            ('scope', '作用域', 150))
_VISIBLE_COLUMNS = ('display', 'kind', 'stage', 'layer', 'status', 'scope')
_SCOPE_TO_SOURCE = {'全部': '全部来源', '项目版': '项目', '全局版': '用户'}
_SOURCE_TO_SCOPE = {'全部': '全部', '全部来源': '全部',
                    '项目版': '项目版', '项目': '项目版',
                    '全局版': '全局版', '用户': '全局版'}


def _project_of(pet):
    for holder in (getattr(pet, 'agent', None), pet):
        value = getattr(holder, 'project', None)
        if value:
            return Path(value)
    return None


def _program_of(pet):
    program = getattr(pet, 'program', None)
    if program:
        return Path(program)
    return Path(skill_import_service.__file__).resolve().parents[1]


def clear_filter(state, apply_filter):
    state['filter_text'].set('')
    state['source_filter'].set('全部来源')
    state['stage_filter'].set('全部阶段')
    apply_filter()
    return True


def _delete_block_reason(selected, state):
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
    return ('将所选旧包整包移入回收站。' if kind == 'legacy' else '将所选 SKILL 移入回收站。')


def check_updates_dialog(pet, state, refresh, hint):
    return _check_updates_dialog(pet, state, _program_of(pet), refresh, hint)


def _build_skills_workspace(frame, pet, *, embedded=True):
    """构建 DSH SKILL 管理主工作区（设置窗内嵌与独立窗共用）。"""
    install_compact_form_styles(frame)
    hint = tk.StringVar(value='列表在后台加载，打开项目后项目层 SKILL 也会列出。')
    project = _project_of(pet)
    registry = skill_registry.default_registry(_program_of(pet), project=project)
    state = {'skills': [], 'disabled': [], 'health': {}, 'registry': registry,
             'project': project, 'tk': frame, 'problems': 0, 'error': '', 'load_gen': 0,
             'rows': [], 'rowmap': {}, 'expanded': set(), 'editing': False,
             'filter_text': tk.StringVar(value=''), 'source_filter': tk.StringVar(value='全部来源'),
             'stage_filter': tk.StringVar(value='全部阶段'), 'stage_ids': stage_ids_map(),
             'detail': None}

    def refresh():
        if editor.confirm_leave('刷新列表'):
            load(state, fill)

    def on_scope_change():
        mapped = _SCOPE_TO_SOURCE.get(scope_tabs.current(), '全部来源')
        if state['source_filter'].get() != mapped:
            state['source_filter'].set(mapped)
        return True

    top_cbs = {'on_scope_change': on_scope_change,
               'import': lambda: import_dialog(pet, state, refresh),
               'refresh': refresh,
               'health': lambda: health_dialog(pet, state),
               'check_updates': lambda: check_updates_dialog(pet, state, refresh, hint),
               'residue': lambda: residue_dialog(pet, refresh)}
    _top, scope_tabs, residue_btn = build_top_bar(
        frame, state, top_cbs, embedded=embedded, page_title=PAGE_TITLE, note_text=NOTE_MANAGE)

    split = ttk.Frame(frame)
    split.pack(fill='both', expand=True)
    _left, stage_nav, sync_nav = build_stage_nav(split, state, embedded=embedded)
    ttk.Separator(split, orient='vertical').pack(side='left', fill='y', padx=SPACING['sm'])

    right = ttk.Frame(split)
    right.pack(side='left', fill='both', expand=True)
    search = build_search_row(right, state, lambda: clear_filter(state, apply_filter),
                              lambda: apply_filter())
    table = DataTable(right, columns=list(_COLUMNS), height=TEXT_ROWS['lg'],
                      show='tree headings', empty_text='当前阶段暂无 SKILL，点右上角「+ 导入 SKILL」添加。',
                      auto_hide_scrollbars=True, takefocus=True)
    table.pack(fill='both', expand=True)
    tree = table.tree
    tree.heading('#0', text='技能包 / 子技能', anchor='w')
    tree.column('#0', width=_COLUMNS[0][2], stretch=True)
    tree.configure(displaycolumns=list(_VISIBLE_COLUMNS))

    item_cbs = {
        'remove': lambda: remove_skill(pet, tree, state, refresh, hint),
        'rename': lambda: rename_skill(pet, tree, state, refresh, hint),
        'edit_external': lambda: edit_skill(pet, tree, state, hint),
        'open_folder': lambda: open_in_folder(pet, tree, state, hint),
        'toggle_disabled': lambda: toggle_disabled(pet, tree, state, refresh, hint),
        'show_note': lambda: show_note(pet, tree, state),
        'check_updates': lambda: check_updates_dialog(pet, state, refresh, hint),
        'confirm': lambda *a, **k: ask_confirmation(*a, **k),
        'delete_block_reason': _delete_block_reason,
        'delete_tip_text': _delete_tip_text,
        'is_disabled': _is_disabled_row,
        'kind_of': _kind_of,
    }
    editor = InlineDetailEditor(right, pet, tree, state, refresh, hint, item_cbs)

    def apply_filter(*_args):
        target_scope = _SOURCE_TO_SCOPE.get(str(state['source_filter'].get() or '全部来源'))
        if target_scope and scope_tabs.current() != target_scope:
            scope_tabs.select(target_scope, user=False)
        sync_nav()
        visible = render_manage_rows(tree, state)
        search['count_var'].set('显示 %d 项' % visible if visible else '')
        editor.sync_actions()
        update_detail(tree, state, render_markdown=render_md_into_detail)

    state['source_filter'].trace_add('write', apply_filter)
    state['stage_filter'].trace_add('write', apply_filter)
    state['update_delete_state'] = editor.sync_actions

    def toggle_row(_event=None):
        item = tree.focus()
        if item and tree.get_children(item):
            opened = not bool(tree.item(item, 'open'))
            tree.item(item, open=opened)
            (state['expanded'].add if opened else state['expanded'].discard)(item)
            return 'break'
        return None

    def focus_filter(_event=None):
        if not frame.winfo_manager():
            return None
        search['entry'].focus_set()
        search['entry'].select_range(0, 'end')
        return 'break'

    def on_select(_event=None):
        if state.get('editing') and not editor.confirm_leave('切换条目'):
            return
        editor.sync_actions()
        update_detail(tree, state, render_markdown=render_md_into_detail)

    tree.bind('<<TreeviewSelect>>', on_select, add='+')
    tree.bind('<<TreeviewOpen>>', _remember_expansion(tree, state, True), add='+')
    tree.bind('<<TreeviewClose>>', _remember_expansion(tree, state, False), add='+')
    tree.bind('<space>', toggle_row, add='+')
    tree.bind('<Return>', lambda _e: (show_note(pet, tree, state), 'break')[1], add='+')
    tree.bind('<Button-3>', lambda e: open_tree_menu(tree, state, editor, item_cbs, e), add='+')
    from ui.ui_shortcuts import ShortcutRegistry
    ShortcutRegistry().bind(frame.winfo_toplevel(), ('<Control-f>',), focus_filter,
                            scope='skill_manager', name='filter')
    ttk.Label(frame, textvariable=hint, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))

    def fill():
        legacy = sum(1 for item in state.get('rows', []) if item.row.get('kind') == 'legacy')
        if legacy > 0 and not residue_btn.winfo_manager():
            residue_btn.pack(side='right', padx=(SPACING['none'], BUTTON_GAP))
        elif legacy == 0 and residue_btn.winfo_manager():
            residue_btn.pack_forget()
        sync_nav()
        visible = render_manage_rows(tree, state)
        search['count_var'].set('显示 %d 项' % visible if visible else '')
        editor.sync_actions()
        update_detail(tree, state, render_markdown=render_md_into_detail)
        first = tree.get_children()
        if first and not tree.focus():
            tree.focus(first[0])
        if state.get('error'):
            hint.set('SKILL 列表加载失败：%s' % state['error'])
            return
        _set_summary_hint(hint, state, visible, legacy)

    editor.sync_actions()
    update_detail(tree, state, render_markdown=render_md_into_detail)
    load(state, fill)
    return {'hint': hint, 'tree': tree, 'state': state, 'refresh': refresh,
            'delete': editor.delete_btn, 'delete_tip': editor.delete_tip,
            'detail': editor.detail, 'filter': search, 'apply_filter': apply_filter,
            'stage_nav': stage_nav, 'scope_tabs': scope_tabs, 'editor': editor,
            'confirm_leave': editor.confirm_leave, 'residue_button': residue_btn}


def _set_summary_hint(hint, state, visible, legacy):
    counts = {}
    for row in state['health'].values():
        counts[row] = counts.get(row, 0) + 1
    summary = '共 %d 个注册 SKILL' % len(state['skills'])
    packages = sum(1 for item in state.get('rows', []) if item.row.get('kind') == 'package')
    if packages or legacy:
        summary += '；技能包 %d 个%s' % (packages, ('、旧包 %d 个' % legacy) if legacy else '')
    if _filters_active(state):
        summary += '；筛选后可见 %d 行' % visible
    if counts:
        summary += '；体检：' + ' · '.join('%s %d' % (STATUS_LABELS.get(k, k), v)
                                          for k, v in sorted(counts.items()))
    if state['problems'] > 0:
        summary += '；另有全局问题/警告 %d 条' % state['problems']
    hint.set(summary + '。总包置于 00 总包目录，展开可看 L0 主入口与子技能。')


def skills_page(frame, pet, width=None):
    """设置窗内嵌「SKILL 管理」页入口。"""
    return _build_skills_workspace(frame, pet, embedded=True)


def open_manager(pet):
    """独立窗口入口（与模型管理窗口同构：1120×760，最小 820×600）。"""
    parent = getattr(pet, 'win', None)
    win = BaseDialog(parent, '', modal=False, chrome=False)
    win.title(PAGE_TITLE)
    win.geometry(MANAGER_GEOMETRY)
    win.minsize(*MANAGER_MIN)
    if parent is not None:
        win.transient(parent)
    body = Card(win)
    body.pack(fill='both', expand=True, padx=SPACING['md'], pady=SPACING['md'])
    seams = _build_skills_workspace(body, pet, embedded=False)

    def close(_event=None):
        if seams['confirm_leave']('关闭窗口'):
            win.destroy()

    win.protocol('WM_DELETE_WINDOW', close)
    win.bind('<Escape>', close)
    win._pet_seams = {'skills': seams}
    win._pet_hint = seams['hint']
    return win


def load(state, done):
    """后台扫描注册表＋体检报告；worker 只写队列，Tk 侧轮询回填（规则 33）。"""
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
                package_names = {n.casefold() for n in skill_import_service._PACKAGE_ENTRY_NAMES}
                if path.name.casefold() in package_names:
                    pkg_root = path.parent
                    if (pkg_root.parent.is_dir()
                            and skill_registry.detect_composite_suite_entry(pkg_root.parent)):
                        pkg_root = pkg_root.parent
                    meta = skill_registry.imported_package_meta(meta, body, pkg_root, path)
            except (OSError, UnicodeError, ValueError):
                meta, body = {}, ''
        if not str(meta.get('name') or ''):
            meta = dict(meta)
            meta['name'] = name
        out.append(skill_registry.Skill(meta, body, path, layer=str(entry.get('layer') or '')))
    return out


def _is_disabled_row(tree, state):
    pick = tree.selection()
    return bool(pick) and pick[0].startswith('disabled|')


def _kind_of(item):
    return str(item.row.get('kind') or '') if hasattr(item, 'row') else ''


def _remove_legacy_package(pet, state, skill, refresh, hint):
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
    reason = skill_lifecycle_service.skill_delete_block_reason(state['project'], skill.name)
    if reason:
        hint.set(reason)
        if callable(state.get('update_delete_state')):
            state['update_delete_state']()
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
        if callable(state.get('update_delete_state')):
            state['update_delete_state']()
        return None
    hint.set('%s 已移入回收站。' % names)
    refresh()
    return True


def rename_skill(pet, tree, state, refresh, hint):
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
               '· 影响 %d 个项目的阶段配置引用\n· 导入台账同步改键并重算摘要\n'
               '· 已禁用登记同步改名\n· 旧文件进回收站（可恢复）\n\n是否继续？'
               % (old, plan['new'], '包' if plan['kind'] == 'package' else '清单', affected))
    if not ask_confirmation(getattr(pet, 'win', None), '重命名 SKILL', message, dangerous=True):
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
    """用系统默认程序打开条目（清单开文件、包开目录）。"""
    skill = _selected(tree, state)
    if skill is None:
        hint.set('先在列表里选中一个 SKILL。')
        return None
    kind = _kind_of(skill)
    if kind in ('child', 'stage-entry'):
        target = getattr(skill, 'path', None)
    elif kind == 'legacy':
        target = Path(skill.row.get('package_root') or getattr(skill, 'path', '') or '')
    else:
        name = getattr(skill, 'name', '') or ''
        try:
            entry = skill_lifecycle_service.find_skill_entry(_program_of(pet), state['registry'], name)
        except Exception as exc:
            hint.set('定位失败：%s' % exc)
            return None
        if entry is None:
            hint.set('找不到 SKILL「%s」的文件。' % name)
            return None
        target = (entry.get('package_root') or entry['path'].parent
                  if entry['kind'] == 'package' else entry['path'])
    try:
        platform_tools.open_path(target)
    except (OSError, ValueError) as exc:
        hint.set('打开失败：%s' % exc)
        return None
    hint.set('已交给系统默认程序打开；保存后回到本页点「刷新」即可看到改动。')
    return target


def open_in_folder(pet, tree, state, hint):
    skill = _selected(tree, state)
    if skill is None:
        hint.set('先在列表里选中一个 SKILL。')
        return None
    pkg = skill.row.get('package_root') if hasattr(skill, 'row') else ''
    target = Path(pkg) if pkg else (Path(skill.path).parent if getattr(skill, 'path', None) else None)
    if target is None or not target.exists():
        hint.set('找不到 SKILL 所在目录。')
        return None
    try:
        platform_tools.open_path(target)
    except (OSError, ValueError) as exc:
        hint.set('打开目录失败：%s' % exc)
        return None
    return target


def toggle_disabled(pet, tree, state, refresh, hint):
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
    def run():
        try:
            from orchestrator import agent_skill_sync
            agent_skill_sync.sync_all_agent_skills(program=program)
        except Exception:
            import infra.app_logging as app_logging
            app_logging.swallowed('SKILL 管理页改名后 agent 同步失败')
    threading.Thread(target=run, name='skills-manage-agent-sync', daemon=True).start()


class _ImportFlow:
    """导入对话框的统一取数与安装管线：支持复合总包自动入 00 总包与单层输入直达。"""

    def __init__(self, pet, state, refresh, win, controls=None, **legacy):
        controls = dict(controls or legacy)
        self.pet = pet
        self.state = state
        self.refresh = refresh
        self.win = win
        self.hint = controls['hint']
        self.stage_box = controls['stage_box']
        self.layer_var = controls['layer_var']
        self.source_entry = controls.get('source_entry')
        self.project = state['project']
        self.registry = state['registry']

    def stage_hint(self):
        index = self.stage_box.current()
        if not index or index <= 0:
            return ''
        if index == 1:
            return SUITE_STAGE
        pos = index - 2
        return pet_bus.STAGES[pos] if 0 <= pos < len(pet_bus.STAGES) else ''

    def layer(self):
        return 'project' if (self.project is not None and self.layer_var.get() == '项目') else 'user'

    def confirm(self, message):
        return ask_confirmation(self.win, IMPORT_TITLE, message, dangerous=True)

    def done(self, report, lead):
        if self.win.winfo_exists():
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
        target_stage = stage or SUITE_STAGE
        target = self.registry.stage_directory_for(target_stage, self.layer())
        if target is None:
            self.hint.set('找不到「%s」阶段的%s层目录。' % (
                stage_display_label(target_stage), '项目' if self.layer() == 'project' else '用户'))
            return None
        try:
            return skill_import_service.plan_import(source, target, target_stage, self.registry)
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

    def submit_source(self, text=None):
        raw = str(text if text is not None else (
            self.source_entry.get() if self.source_entry is not None else '')).strip().strip('"')
        if not raw:
            self.hint.set('请先输入仓库地址、ZIP 链接或本地路径，或点下方按钮选择文件/文件夹。')
            return None
        local = Path(raw)
        try:
            if local.is_file():
                if local.suffix.casefold() == '.zip':
                    return self._import_zip_path(str(local))
                plan = self.single_plan(local, _file_stage(local) or self.stage_hint())
                return self.install_plan(plan, '文件导入完成') if plan else None
            if local.is_dir():
                return self._import_folder_path(local)
        except OSError:
            pass
        return self._import_remote_or_repo(raw)

    def _import_remote_or_repo(self, raw):
        import ui.skill_remote_service as skill_remote_service
        try:
            skill_remote_service.parse_source(raw)
            is_remote = True
        except skill_import_service.ImportBlocked:
            is_remote = False
        if is_remote:
            try:
                report = skill_remote_service.import_from_url(
                    raw, _program_of(self.pet), self.registry,
                    stage_hint=self.stage_hint(), confirm=self.confirm, layer=self.layer())
                return self.done(report, '链接导入完成')
            except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
                self.hint.set('链接导入失败：' + str(exc))
                return None
        try:
            report = skill_import_service.import_from_repo(
                raw, _program_of(self.pet), self.registry,
                stage_hint=self.stage_hint(), confirm=self.confirm, layer=self.layer())
            return self.done(report, '仓库导入完成')
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.hint.set('仓库导入失败：' + str(exc))
            return None

    def _import_folder_path(self, folder):
        folder = Path(folder)
        if skill_registry.detect_composite_suite_entry(folder) is not None:
            try:
                report = skill_import_service.import_from_repo(
                    str(folder), _program_of(self.pet), self.registry,
                    stage_hint=self.stage_hint(), confirm=self.confirm, layer=self.layer())
                return self.done(report, '总包导入完成')
            except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
                self.hint.set('文件夹导入失败：' + str(exc))
                return None
        try:
            entry = skill_registry.Registry._package_source(folder)
        except OSError:
            entry = None
        if entry is None:
            self.hint.set('所选文件夹不是 SKILL 包（未找到 SKILL.md 或复合总包入口）。')
            return None
        plan = self.single_plan(entry, _package_stage(entry) or self.stage_hint())
        return self.install_plan(plan, '文件夹导入完成') if plan else None

    def _import_zip_path(self, path):
        import ui.skill_archive as skill_archive
        try:
            report = skill_archive.import_archive(
                path, _program_of(self.pet), self.registry, stage_hint=self.stage_hint(),
                confirm=self.confirm,
                options=skill_archive.ArchiveOptions(layer=self.layer()))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.hint.set('ZIP 导入失败：' + str(exc))
            return None
        return self.done(report, 'ZIP 导入完成')

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
        return self._import_folder_path(folder) if folder else None

    def pick_archive(self):
        path = FileDialog(self.win).open_file(title='导入 SKILL（ZIP）',
                                             filetypes=[('ZIP 压缩包', '*.zip'), ('全部文件', '*.*')])
        return self._import_zip_path(path) if path else None

    def pick_repo(self):
        text = ask_string(self.win, IMPORT_TITLE,
                          'SKILL 仓库地址或本地目录（owner/repo、完整 URL 可带 @分支、本地路径）：')
        return self._import_remote_or_repo(str(text).strip()) if text and str(text).strip() else None

    def pick_url(self):
        text = ask_string(self.win, IMPORT_TITLE, 'SKILL 链接（GitHub 仓库地址或 .zip 直链）：')
        return self._import_remote_or_repo(str(text).strip()) if text and str(text).strip() else None


def import_dialog(pet, state, refresh):
    """单层导入弹窗（REQ-UI-SKILL-PAGE-1）：支持自动识别 00 总包、直填地址与快捷选文件。"""
    project = state['project']
    win = BaseDialog(getattr(pet, 'win', None), IMPORT_TITLE, modal=False)
    body = win.content

    stage_row = ttk.Frame(body)
    stage_row.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    ttk.Label(stage_row, text='目标阶段').pack(side='left')
    stage_values = ['自动识别（总包入 00）', SUITE_LABEL] + [pet_bus.stage_label(s) for s in pet_bus.STAGES]
    stage_box = SelectBox(stage_row, values=stage_values, state='readonly')
    stage_box.pack(side='left', padx=(SPACING['xs'], SPACING['md']))
    active_sid = state.get('stage_ids', {}).get(str(state['stage_filter'].get() or '全部阶段'), '')
    if active_sid == SUITE_STAGE:
        stage_box.current(1)
    elif active_sid in pet_bus.STAGES:
        stage_box.current(2 + pet_bus.STAGES.index(active_sid))
    else:
        stage_box.current(0)

    layer_var = tk.StringVar(value='项目' if project else '全局')
    if project is not None:
        ttk.Label(stage_row, text='导入到').pack(side='left')
        layer_box = SelectBox(stage_row, values=['项目', '全局'], state='readonly',
                              textvariable=layer_var)
        layer_box.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
        layer_box.current(0)

    src_row = ttk.Frame(body)
    src_row.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    source_entry = LineInput(src_row)
    source_entry.pack(side='left', fill='x', expand=True)
    Tooltip(source_entry, '支持 GitHub 仓库地址、owner/repo、.zip 链接或本地目录/文件路径')
    hint = tk.StringVar(value='多阶段总包（如自带总控与子技能的仓库）会自动装入「00 总包」，单阶段技能自动归入对应阶段。')
    flow = _ImportFlow(pet, state, refresh, win, {
        'hint': hint, 'stage_box': stage_box, 'layer_var': layer_var, 'source_entry': source_entry,
    })
    PrimaryButton(src_row, text='导入', width=0, command=flow.submit_source).pack(
        side='right', padx=(SPACING['xs'], SPACING['none']))
    source_entry.bind('<Return>', lambda _e: (flow.submit_source(), 'break')[1], add='+')

    quick = ttk.Frame(body)
    quick.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    ttk.Label(quick, text='本地快捷选择：', style='Muted.TLabel').pack(side='left')
    for label, handler in (('文件', flow.pick_file), ('文件夹', flow.pick_folder), ('ZIP', flow.pick_archive)):
        SecondaryButton(quick, text=label, width=0, command=handler).pack(
            side='left', padx=(SPACING['xs'], SPACING['none']))

    ttk.Label(body, textvariable=hint, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
    SecondaryButton(win.actions, text='关闭', command=win.destroy).pack(side='right')
    win._pet_import_flow = flow
    win._pet_import_entry = source_entry
    return win


def residue_dialog(pet, refresh):
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
    SecondaryButton(win.actions, text='刷新', command=load_rows).pack(
        side='right', padx=(SPACING['none'], BUTTON_GAP))
    SecondaryButton(win.actions, text='移入回收站…', command=dispose).pack(side='left')
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
