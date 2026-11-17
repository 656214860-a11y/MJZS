# -*- coding: utf-8 -*-
"""「设置 → SKILL 管理」页（生命周期任务书 T7）：全部 SKILL 平铺列表与安装级操作。

分工：本页只做安装级增删查（导入／说明／体检／删除）；阶段勾选仍归各阶段面板，
避免双入口（规则 28）。数据在用户主动打开时后台加载（规则 33），列表列
name/displayName/阶段/层/体检状态；删除走 ``skill_import_service.uninstall_skill``
回收站口径，内置层只读不提供删除。

线程封送：worker 只写 ``queue.Queue``，Tk 侧 ``after(50)`` 轮询回填——``after``
只能在 Tk 主线程登记，后台线程直调会抛 ``main thread is not in main loop``，
与 ``desktop_async_tasks`` 同一口径。
"""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import pet_bus
import skill_import_service
import ui.skill_lifecycle_service as skill_lifecycle_service
import orchestrator.skill_project_layer as skill_project_layer
import skill_registry
import workflow_settings
from contract import platform_tools
from ui_dialogs import FileDialog
from ui_tokens import COLORS, FONTS, SPACING, TEXT_DESC, TEXT_ROWS
from ui_widgets import (BaseDialog, DataTable, SecondaryButton, SelectBox, TextArea,
                        Tooltip, ask_confirmation, ask_string, notify)

PAGE_TITLE = 'SKILL 管理'
NOTE_MANAGE = ('这里管「装了哪些 SKILL」：导入、看说明、体检、删除。'
               '每个阶段用不用哪个 SKILL 仍在各阶段面板里勾选，两边不重复。')
IMPORT_TITLE = '导入 SKILL'
_STATUS_LABELS = {'ok': '正常', 'warning': '警告', 'problem': '问题', 'error': '预演失败'}
# 平铺列表列宽（DataTable 列定义第三位是显示宽度字符数，不走 width= 关键字）。
_COLUMNS = (('name', '名称', 180), ('display', '显示名', 140), ('stage', '阶段', 90),
            ('layer', '层', 70), ('status', '体检', 70))


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


def skills_page(frame, pet, width=None):
    """设置页「SKILL 管理」格；返回 seams（hint 供底部保存回退文案）。"""
    _page_title(frame, PAGE_TITLE, NOTE_MANAGE)
    hint = tk.StringVar(value='列表在后台加载，打开项目后项目层 SKILL 也会列出。')
    project = _project_of(pet)
    registry = skill_registry.default_registry(_program_of(pet), project=project)
    state = {'skills': [], 'disabled': [], 'health': {}, 'registry': registry,
             'project': project, 'tk': frame, 'problems': 0, 'error': '', 'load_gen': 0}

    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    SecondaryButton(bar, text='导入 SKILL…',
                    command=lambda: import_dialog(pet, state, refresh)).pack(side='left')
    SecondaryButton(bar, text='体检详情',
                    command=lambda: health_dialog(pet, state)).pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    SecondaryButton(bar, text='刷新', command=lambda: load(state, fill)).pack(side='left')

    table = DataTable(frame, columns=list(_COLUMNS), height=TEXT_ROWS['2xl'],
                      empty_text='暂无 SKILL，点「导入 SKILL…」添加。',
                      auto_hide_scrollbars=True)
    table.pack(fill='both', expand=True, pady=(SPACING['sm'], SPACING['none']))
    tree = table.tree

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

    def update_delete_state(_event=None):
        selected = _selected(tree, state)
        reason = '先在列表里选中一个 SKILL。'
        if selected is not None:
            reason = ('内置 SKILL 只读，不能删除。'
                      if getattr(selected, 'layer', '') == 'builtin' else
                      skill_lifecycle_service.skill_delete_block_reason(
                          state['project'], selected.name))
        delete.state(['disabled'] if reason else ['!disabled'])
        delete_tip.text = reason or '将所选 SKILL 移入回收站。'

    state['update_delete_state'] = update_delete_state
    tree.bind('<<TreeviewSelect>>', update_delete_state, add='+')
    update_delete_state()
    ttk.Label(frame, textvariable=hint, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))

    def refresh():
        load(state, fill)

    def fill():
        tree.delete(*tree.get_children())
        skills = sorted(state['skills'], key=lambda s: (skill_project_layer.LAYER_ORDER.get(
            getattr(s, 'layer', ''), 9), getattr(s, 'name', '') or ''))
        for skill in skills:
            name = getattr(skill, 'name', '') or ''
            status = state['health'].get(name, '')
            tree.insert('', 'end', iid=name or str(id(skill)), values=(
                name, getattr(skill, 'displayName', '') or '',
                pet_bus.stage_label(getattr(skill, 'stage', '') or ''),
                skill_project_layer.LAYER_LABELS.get(getattr(skill, 'layer', ''), '—'),
                _STATUS_LABELS.get(status, status or '—')))
        for skill in state.get('disabled', []):
            name = getattr(skill, 'name', '') or ''
            iid = 'disabled|' + name
            tree.insert('', 'end', iid=iid, tags=('disabled',), values=(
                name, getattr(skill, 'displayName', '') or '—',
                pet_bus.stage_label(getattr(skill, 'stage', '') or ''),
                skill_project_layer.LAYER_LABELS.get(getattr(skill, 'layer', ''), '—'),
                '已禁用'))
        tree.tag_configure('disabled', foreground=COLORS['text_muted'])
        table.refresh_empty_state()
        update_delete_state()
        if state.get('error'):
            hint.set('SKILL 列表加载失败：%s' % state['error'])
            return
        counts = {}
        for row in state['health'].values():
            counts[row] = counts.get(row, 0) + 1
        summary = '共 %d 个 SKILL' % len(skills)
        if counts:
            summary += '；体检：' + ' · '.join('%s %d' % (_STATUS_LABELS.get(k, k), v)
                                              for k, v in sorted(counts.items()))
        if state['problems'] > 0:
            summary += '；另有全局问题/警告 %d 条' % state['problems']
        hint.set(summary + '。内置层只读；删除只影响用户层与项目层（进回收站可恢复）。')

    load(state, fill)
    return {'hint': hint, 'tree': tree, 'state': state, 'refresh': refresh,
            'delete': delete, 'delete_tip': delete_tip}


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
            modified = (skill_import_service.local_modifications(program)
                        if program is not None else {})
            report = workflow_settings.skill_health_report(
                registry, project=project, local_modified=modified)
            health = {row.get('name'): row.get('status') for row in report.get('skills', [])}
            problems = len(report.get('problems', ())) + len(report.get('warnings', ()))
            result_q.put((skills, disabled, health, problems, ''))
        except Exception as exc:
            result_q.put(([], [], {}, 0, str(exc)))

    def poll():
        widget = state['tk']
        try:
            alive = widget.winfo_exists()
        except tk.TclError:
            alive = False
        if not alive or state['load_gen'] != generation:
            return
        try:
            skills, disabled, health, problems, error = result_q.get_nowait()
        except queue.Empty:
            widget.after(50, poll)
            return
        state['skills'], state['disabled'] = skills, disabled
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
            except (OSError, UnicodeError, ValueError):
                meta, body = {}, ''
        if not str(meta.get('name') or ''):
            meta = dict(meta)
            meta['name'] = name
        skill = skill_registry.Skill(meta, body, path,
                                     layer=str(entry.get('layer') or ''))
        out.append(skill)
    return out


def _selected(tree, state):
    pick = tree.selection()
    if not pick:
        return None
    iid = pick[0]
    disabled = iid.startswith('disabled|')
    name = iid.split('|', 1)[-1] if disabled else iid
    pool = state.get('disabled', []) if disabled else state['skills']
    return next((s for s in pool if getattr(s, 'name', '') == name), None)


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


def remove_skill(pet, tree, state, refresh, hint):
    """删除：仅用户层／项目层；内置层只读，已禁用项按登记路径回收，回收站语义由服务把关。"""
    skill = _selected(tree, state)
    if skill is None:
        hint.set('先在列表里选中一个 SKILL。')
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
