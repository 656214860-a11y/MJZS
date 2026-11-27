# -*- coding: utf-8 -*-
"""DSH SKILL 管理页的视图部件与弹窗辅助（L4，无循环依赖 ``pet_skills_manage``）。

承载：顶部作用域分段＋全局操作栏、左侧阶段目录、右侧搜索条、两级树右键菜单、
可折叠完整 Markdown 详情与原地编辑器、说明弹窗、体检弹窗、后台更新检查弹窗。
"""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from agent.core import save_text
from contract.error_codes import user_text
import skill_import_service
import skill_registry
from responsive_ui import ScrollForm
from ui.pet_models_tabs import CompactLineInput, ModeSegmentedControl, set_input_value
from ui.pet_skill_tree import (
    STAGE_NAV_ITEMS,
    SUITE_STAGE,
    _selected,
    stage_counts,
    update_detail,
)
import ui.skill_note_render as skill_note_render
from ui_theme import box_frame
from ui_tokens import BUTTON_GAP, SPACING, TEXT_DESC, TEXT_ROWS
from ui_widgets import (BaseDialog, ContextMenu, DataTable, PrimaryButton,
                        SecondaryButton, TextArea, Tooltip, ask_confirmation, notify)
import workflow_settings

LEFT_NAV_EMBED_WIDTH = 184
LEFT_NAV_WINDOW_WIDTH = 208


def render_md_into_detail(widget, body):
    return skill_note_render.insert(widget, 'end', body)


class InlineDetailEditor:
    """下方可折叠详情卡：读模式渲染完整 Markdown，编辑模式原地修改并原子落盘。"""

    def __init__(self, parent, pet, tree, state, refresh, hint, callbacks):
        self.pet = pet
        self.tree = tree
        self.state = state
        self.refresh = refresh
        self.hint = hint
        self.cb = callbacks
        self.collapsed = False
        self.editing_path = None
        self.original_text = ''
        self.dirty = False

        self.card = box_frame(parent, padding=SPACING['xs'])
        self.card.pack(fill='both', expand=False, pady=(SPACING['sm'], SPACING['none']))
        self._build_header()
        self._build_body()

    def _build_header(self):
        head = ttk.Frame(self.card)
        head.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.toggle_btn = SecondaryButton(head, text='▾ 详情与文档', width=0,
                                          command=self.toggle_collapse)
        self.toggle_btn.pack(side='left')
        self.title_var = tk.StringVar(value='未选择 SKILL')
        self.state['detail_title_var'] = self.title_var
        ttk.Label(head, textvariable=self.title_var, style='Muted.TLabel').pack(
            side='left', padx=(SPACING['sm'], SPACING['none']))

        self.read_bar = ttk.Frame(head)
        self.read_bar.pack(side='right')
        self.delete_btn = SecondaryButton(self.read_bar, text='删除', width=0,
                                          command=self.cb['remove'])
        self.delete_btn.pack(side='right')
        self.delete_tip = Tooltip(self.delete_btn, '先在列表里选中一个 SKILL。')
        ttk.Separator(self.read_bar, orient='vertical').pack(
            side='right', fill='y', padx=SPACING['xs'])
        self.open_btn = SecondaryButton(self.read_bar, text='打开目录', width=0,
                                        command=self.cb['edit_external'])
        self.open_btn.pack(side='right', padx=(SPACING['xs'], SPACING['none']))
        self.edit_btn = SecondaryButton(self.read_bar, text='原地编辑', width=0,
                                        command=self.begin_edit)
        self.edit_btn.pack(side='right', padx=(SPACING['xs'], SPACING['none']))
        self.rename_btn = SecondaryButton(self.read_bar, text='重命名…', width=0,
                                          command=self.cb['rename'])
        self.rename_btn.pack(side='right', padx=(SPACING['xs'], SPACING['none']))
        self.disable_btn = SecondaryButton(self.read_bar, text='禁用/启用', width=0,
                                           command=self.cb['toggle_disabled'])
        self.disable_btn.pack(side='right')

        self.edit_bar = ttk.Frame(head)
        self.save_btn = PrimaryButton(self.edit_bar, text='保存', width=0, command=self.save_edit)
        self.save_btn.pack(side='right')
        self.cancel_btn = SecondaryButton(self.edit_bar, text='取消', width=0,
                                          command=self.cancel_edit)
        self.cancel_btn.pack(side='right', padx=(SPACING['none'], SPACING['xs']))

    def _build_body(self):
        self.body_frame = ttk.Frame(self.card)
        self.body_frame.pack(fill='both', expand=True)
        self.detail = TextArea(self.body_frame, height=TEXT_ROWS['lg'], wrap='word', state='disabled')
        scroll = ttk.Scrollbar(self.body_frame, orient='vertical', command=self.detail.yview)
        self.detail.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.detail.pack(side='left', fill='both', expand=True)
        self.detail.bind('<KeyRelease>', self._on_key_release, add='+')
        self.state['detail'] = self.detail

    def _on_key_release(self, _event=None):
        if self.state.get('editing'):
            self.dirty = (self.detail.get('1.0', 'end-1c') != self.original_text)

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body_frame.pack_forget()
            self.toggle_btn.configure(text='▸ 详情与文档')
        else:
            self.body_frame.pack(fill='both', expand=True)
            self.toggle_btn.configure(text='▾ 详情与文档')
        return self.collapsed

    def sync_actions(self):
        selected = _selected(self.tree, self.state)
        reason = self.cb['delete_block_reason'](selected, self.state)
        self.delete_btn.state(['disabled'] if reason else ['!disabled'])
        self.delete_tip.text = self.cb['delete_tip_text'](selected, reason)
        if selected is None:
            self.disable_btn.configure(text='禁用/启用')
            self.edit_btn.state(['disabled'])
            return
        disabled = self.cb['is_disabled'](self.tree, self.state)
        self.disable_btn.configure(text='启用' if disabled else '禁用')
        path = getattr(selected, 'path', None)
        writable = (path is not None and Path(path).is_file()
                    and getattr(selected, 'layer', '') != 'builtin')
        self.edit_btn.state(['!disabled'] if writable else ['disabled'])

    def begin_edit(self):
        item = _selected(self.tree, self.state)
        if item is None:
            self.hint.set('先在列表里选中一个 SKILL。')
            return False
        if getattr(item, 'layer', '') == 'builtin':
            self.hint.set('内置 SKILL 只读，不能直接编辑。')
            return False
        path = getattr(item, 'path', None)
        if path is None or not Path(path).is_file():
            self.hint.set('当前条目没有可编辑的文档文件。')
            return False
        if self.collapsed:
            self.toggle_collapse()
        try:
            text = Path(path).read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError) as exc:
            self.hint.set('读取文档失败：%s' % exc)
            return False
        self.editing_path = Path(path)
        self.original_text = text
        self.dirty = False
        self.state['editing'] = True
        self.read_bar.pack_forget()
        self.edit_bar.pack(side='right')
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', text)
        self.detail.focus_set()
        self.hint.set('正在原地编辑「%s」；修改完成后点「保存」。' % self.editing_path.name)
        return True

    def save_edit(self):
        if not self.state.get('editing') or self.editing_path is None:
            return False
        content = self.detail.get('1.0', 'end-1c')
        try:
            save_text(self.editing_path, content, encoding='utf-8')
        except OSError as exc:
            self.hint.set('保存失败：%s' % exc)
            return False
        saved_name = self.editing_path.name
        self._exit_edit()
        self.hint.set('已保存「%s」；正在刷新列表。' % saved_name)
        self.refresh()
        return True

    def cancel_edit(self, *, force=False):
        if not self.state.get('editing'):
            return True
        if not force and self.dirty:
            if not self.cb['confirm'](getattr(self.pet, 'win', None), '放弃修改',
                                      '当前 SKILL 文档有未保存修改，确定放弃吗？', dangerous=True):
                return False
        self._exit_edit()
        update_detail(self.tree, self.state, render_markdown=render_md_into_detail)
        self.hint.set('已取消编辑。')
        return True

    def _exit_edit(self):
        self.state['editing'] = False
        self.editing_path = None
        self.original_text = ''
        self.dirty = False
        self.edit_bar.pack_forget()
        self.read_bar.pack(side='right')
        self.detail.configure(state='disabled')

    def confirm_leave(self, action='离开'):
        if not self.state.get('editing') or not self.dirty:
            if self.state.get('editing'):
                self._exit_edit()
            return True
        if not self.cb['confirm'](getattr(self.pet, 'win', None), '未保存修改',
                                  'SKILL 文档尚未保存，确定放弃修改并%s吗？' % action,
                                  dangerous=True):
            return False
        self._exit_edit()
        return True


def build_top_bar(frame, state, callbacks, *, embedded, page_title, note_text):
    """顶部作用域分段（全部 / 项目版 / 全局版）＋右上角统一全局操作栏。"""
    top = ttk.Frame(frame)
    top.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    if not embedded:
        head = ttk.Frame(top)
        head.pack(side='left', padx=(SPACING['none'], SPACING['md']))
        ttk.Label(head, text=page_title, style='ModelSection.TLabel').pack(anchor='w')
        ttk.Label(head, text=note_text, style='Muted.TLabel',
                  wraplength=TEXT_DESC['wraplength']).pack(anchor='w')

    scopes = ('全部', '项目版', '全局版') if state['project'] is not None else ('全部', '全局版')
    scope_tabs = ModeSegmentedControl(top, scopes, command=callbacks['on_scope_change'])
    scope_tabs.pack(side='left')

    PrimaryButton(top, text='+ 导入 SKILL', width=0, command=callbacks['import']).pack(side='right')
    SecondaryButton(top, text='刷新', width=0, command=callbacks['refresh']).pack(
        side='right', padx=(SPACING['none'], BUTTON_GAP))
    SecondaryButton(top, text='体检', width=0, command=callbacks['health']).pack(
        side='right', padx=(SPACING['none'], BUTTON_GAP))
    SecondaryButton(top, text='检查更新', width=0, command=callbacks['check_updates']).pack(
        side='right', padx=(SPACING['none'], BUTTON_GAP))
    residue_btn = SecondaryButton(top, text='残留包管理…', width=0, command=callbacks['residue'])
    return top, scope_tabs, residue_btn


def build_stage_nav(split, state, *, embedded):
    """左侧固定宽阶段目录（全部阶段 / 00 总包 / 01–13），带数量徽章与选中高亮。"""
    width = LEFT_NAV_EMBED_WIDTH if embedded else LEFT_NAV_WINDOW_WIDTH
    pane = ttk.Frame(split, width=width)
    pane.pack(side='left', fill='y')
    pane.pack_propagate(False)
    ttk.Label(pane, text='阶段目录', style='Muted.TLabel').pack(
        anchor='w', pady=(SPACING['none'], SPACING['xs']))
    nav_host = ttk.Frame(pane)
    nav_host.pack(fill='both', expand=True)
    scroller = ScrollForm(nav_host)
    buttons = {}
    for sid, label in STAGE_NAV_ITEMS:
        btn = SecondaryButton(
            scroller.form, text=label, width=0, style='Nav.TButton',
            command=lambda target=label: state['stage_filter'].set(target))
        btn.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        buttons[sid] = btn

    def sync_nav():
        counts = stage_counts(state.get('rows', ()), state['source_filter'].get(),
                              state['filter_text'].get())
        active_sid = state['stage_ids'].get(str(state['stage_filter'].get() or '全部阶段'), '')
        for sid, label in STAGE_NAV_ITEMS:
            count = counts.get(sid, 0)
            buttons[sid].configure(
                text='%s (%d)' % (label, count) if count else label,
                style='Selected.Nav.TButton' if sid == active_sid else 'Nav.TButton')

    sync_nav()
    return pane, buttons, sync_nav


def build_search_row(parent, state, clear_cb, apply_filter):
    """右侧顶部搜索条（CompactLineInput ＋ 清空 ＋ 可见计数）。"""
    bar = ttk.Frame(parent)
    bar.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    syncing = {'lock': False}

    def on_entry_change():
        if syncing['lock']:
            return
        syncing['lock'] = True
        try:
            text = entry.value() if hasattr(entry, 'value') else entry.get()
            if state['filter_text'].get() != text:
                state['filter_text'].set(text)
        finally:
            syncing['lock'] = False

    entry = CompactLineInput(bar, placeholder='搜索技能包、子技能名或说明…',
                             on_change=on_entry_change)
    entry.pack(side='left', fill='x', expand=True)
    entry.bind('<KeyRelease>', lambda _e: on_entry_change(), add='+')
    Tooltip(entry, '按技能包名、子技能名、说明或路径搜索；Ctrl+F 聚焦，Esc 清空。')
    clear_btn = SecondaryButton(bar, text='清空', width=0, command=clear_cb)
    clear_btn.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
    count_var = tk.StringVar(value='')
    ttk.Label(bar, textvariable=count_var, style='Muted.TLabel').pack(
        side='right', padx=(SPACING['sm'], SPACING['none']))

    def on_var_change(*_args):
        if not syncing['lock']:
            syncing['lock'] = True
            try:
                set_input_value(entry, state['filter_text'].get())
            finally:
                syncing['lock'] = False
        apply_filter()

    state['filter_text'].trace_add('write', on_var_change)

    def escape(_event=None):
        if state['filter_text'].get():
            state['filter_text'].set('')
            return 'break'
        return None

    entry.bind('<Escape>', escape, add='+')
    return {'entry': entry, 'clear': clear_btn, 'count_var': count_var}


def open_tree_menu(tree, state, editor, callbacks, event):
    """统一 6 段右键菜单（REQ-UI-UNIFY-1）：展开/查看 → 编辑/改名 → 更新/启停 → 目录 → 分隔线 → 删除。"""
    iid = tree.identify_row(event.y)
    if iid:
        tree.selection_set(iid)
        tree.focus(iid)
    item = _selected(tree, state)
    if item is None:
        return None
    menu = ContextMenu(tree.winfo_toplevel())
    children = tree.get_children(iid) if iid else ()
    if children:
        opened = bool(tree.item(iid, 'open'))
        menu.command('收起子技能' if opened else '展开子技能',
                     lambda row_id=iid, now=opened: tree.item(row_id, open=not now))
    menu.command('查看说明弹窗', callbacks['show_note'])
    menu.separator()
    if getattr(item, 'layer', '') != 'builtin' and getattr(item, 'path', None):
        menu.command('原地编辑', editor.begin_edit)
    else:
        menu.disabled('原地编辑')
    menu.command('外部程序打开', callbacks['edit_external'])
    kind = callbacks['kind_of'](item)
    if kind in ('package', 'skill'):
        menu.command('重命名…', callbacks['rename'])
    else:
        menu.disabled('重命名…')
    menu.separator()
    if kind in ('package', 'skill', 'stage-entry'):
        verb = '启用' if callbacks['is_disabled'](tree, state) else '禁用'
        menu.command(verb, callbacks['toggle_disabled'])
    else:
        menu.disabled('禁用/启用')
    menu.command('检查更新', callbacks['check_updates'])
    menu.command('在文件夹中打开', callbacks['open_folder'])
    menu.separator()
    reason = callbacks['delete_block_reason'](item, state)
    if reason:
        menu.disabled('删除')
    else:
        menu.command('删除', callbacks['remove'])
    state['last_menu'] = menu
    return menu.popup(event)


def show_note(pet, tree, state):
    """查看说明弹窗（快捷入口，供回车/右键大窗阅读）。"""
    from skill_panel_support import note_text
    skill = _selected(tree, state)
    if skill is None:
        return None
    win = BaseDialog(getattr(pet, 'win', None), 'SKILL 说明：' + str(getattr(skill, 'name', '')),
                     modal=False)
    body = TextArea(win.content, state='disabled')
    body.pack(fill='both', expand=True)
    body.configure(state='normal')
    text = note_text(skill, localize=False) or '（无说明正文）'
    if not skill_note_render.insert(body, '1.0', text):
        body.insert('1.0', text)
    body.configure(state='disabled')
    SecondaryButton(win.actions, text='关闭', command=win.destroy).pack(side='right')
    return win


def health_dialog(pet, state):
    import skill_panel
    registry = state['registry']
    try:
        program = skill_import_service.program_of_registry(registry)
        modified = (skill_import_service.local_modifications(program)
                    if program is not None else {})
        report = workflow_settings.skill_health_report(
            registry, project=state['project'], local_modified=modified)
    except Exception as exc:
        notify(getattr(pet, 'win', None), 'SKILL 体检失败：' + user_text(exc), title='SKILL 体检', modal=False)
        return None
    return skill_panel.show_skill_health_report(
        getattr(pet, 'win', None), report, lead='全部',
        refresh=lambda: health_dialog(pet, state))


def check_updates_dialog(pet, state, program, refresh, hint):
    """后台检查已导入 SKILL 台账更新；完成后弹窗展示并支持一键重新导入。"""
    import ui.skill_archive as skill_archive
    import ui.skill_remote_service as skill_remote_service
    registry = state['registry']
    project = state['project']
    result_q = queue.Queue()
    hint.set('正在检查 SKILL 更新…')

    def _probe(key, row, cache):
        status = skill_remote_service.probe_row(key, row, program, registry, cache=cache)
        if status is None:
            status = skill_archive.probe_row(key, row, program, registry)
        return status

    def work():
        cache = {}
        try:
            statuses = skill_import_service.check_updates(
                program, probe=lambda k, r: _probe(k, r, cache), project=project)
            items = skill_import_service.ledger_items(program)
            result_q.put((items, statuses, ''))
        except Exception as exc:
            result_q.put(({}, {}, str(exc)))

    def poll():
        widget = state['tk']
        try:
            alive = widget.winfo_exists()
        except tk.TclError:
            alive = False
        if not alive:
            return
        try:
            items, statuses, err = result_q.get_nowait()
        except queue.Empty:
            widget.after(50, poll)
            return
        if err:
            hint.set('检查更新失败：%s' % err)
            return
        if not items:
            hint.set('SKILL 更新检查：还没有远程或仓库导入记录。')
            return
        _show_updates_window(pet, state, program, items, statuses, refresh, hint)

    threading.Thread(target=work, name='skills-manage-updates', daemon=True).start()
    state['tk'].after(50, poll)


def _show_updates_window(pet, state, program, items, statuses, refresh, hint):
    labels = {'unchanged': '已是最新', 'source-newer': '有更新',
              'local-modified': '本地已修改', 'source-missing': '源不可用'}
    pending = [(k, r) for k, r in items.items() if statuses.get(k) != 'unchanged']
    if not pending:
        hint.set('SKILL 更新检查：全部 %d 项均已是最新。' % len(items))
        return None
    win = BaseDialog(getattr(pet, 'win', None), 'SKILL 更新检查', modal=False)
    table = DataTable(win.content, columns=[('name', '名称', 160), ('status', '状态', 100),
                                            ('source', '来源', 260)],
                      show='headings', height=TEXT_ROWS['lg'])
    table.pack(fill='both', expand=True)
    for key, row in pending:
        table.tree.insert('', 'end', iid=key, values=(
            row.get('name') or key, labels.get(statuses.get(key), statuses.get(key, '')),
            row.get('source_url') or row.get('source') or '—'))

    def update_selected():
        pick = table.tree.selection()
        if not pick:
            hint.set('先在更新列表里选择一项。')
            return
        key = pick[0]
        row = items.get(key) or {}
        if statuses.get(key) != 'source-newer':
            hint.set('该条目不是「有更新」，无需重新导入。')
            return
        _reimport_one((pet, state, program, refresh, hint), win, key, row)

    PrimaryButton(win.actions, text='更新所选', command=update_selected).pack(side='right')
    SecondaryButton(win.actions, text='关闭', command=win.destroy).pack(
        side='right', padx=(SPACING['none'], BUTTON_GAP))
    SecondaryButton(win.actions, text='刷新',
                    command=lambda: (win.destroy(),
                                     check_updates_dialog(pet, state, program, refresh, hint))
                    ).pack(side='left')
    hint.set('SKILL 更新检查：发现 %d 项待处理。' % len(pending))
    return win


def _reimport_one(ctx, win, key, row):
    pet, state, program, refresh, hint = ctx
    import ui.skill_archive as skill_archive
    import ui.skill_remote_service as skill_remote_service
    registry = skill_import_service.registry_for_ledger_row(program, row, state['registry'])
    layer = str(row.get('scope') or 'user')
    stage = skill_registry.stage_from_path(Path(key).parent / 'stage_probe') or SUITE_STAGE
    confirm = lambda msg: ask_confirmation(win, '导入 SKILL', msg, dangerous=True)
    try:
        url = str(row.get('source_url') or '')
        ref = str(row.get('source_ref') or '')
        kind = str(row.get('source_kind') or '')
        if kind == 'archive' and not url:
            skill_archive.import_archive(str(row.get('source') or ''), program, registry,
                                         stage_hint=stage, confirm=confirm,
                                         options=skill_archive.ArchiveOptions(layer=layer))
        elif url:
            text = url + (('#' + ref) if kind == 'repo' and ref else '')
            skill_remote_service.import_from_url(text, program, registry, stage_hint=stage,
                                                 confirm=confirm, layer=layer)
        else:
            skill_import_service.import_from_repo(str(row.get('source') or ''), program, registry,
                                                  stage_hint=stage, confirm=confirm, layer=layer)
    except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
        hint.set('更新失败：%s' % exc)
        return False
    win.destroy()
    hint.set('已更新「%s」。' % (row.get('name') or key))
    refresh()
    return True
