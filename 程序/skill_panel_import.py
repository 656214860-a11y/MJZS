"""阶段配置面板的 SKILL 导入动作（R2881 拆出）：文件导入与仓库导入。

面板本体在 ``skill_panel.Panel``；本模块只承载「新增 SKILL」各入口与
「检查更新」的交互，导入管线（预检→暂存→换入→试冻结→登记）与台账消费
（``check_updates``／``forget_ledger_targets``）仍全部在服务层。
仓库地址形态见 ``skill_import_service.parse_repo_ref``。
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui_dialogs import FileDialog
from ui_tokens import (CHAR_WIDTH, DIALOG_MIN_HEIGHT, DIALOG_MIN_WIDTH,
                       FONTS, SPACING)
from ui_widgets import (BaseDialog, HintLabel, PrimaryButton, SecondaryButton,
                        TextArea, ask_confirmation, ask_string)

TITLE = '阶段配置'
confirm = ask_confirmation


def _reload_panel_skills(panel):
    """导入成功后重扫注册表并重建本阶段勾选网格（文件导入与仓库导入共用）。

    模块级函数而非 Panel 方法：既有测试以未绑定方式调用 Panel 方法、self 是 Mock，
    方法内再调 self._reload_panel_skills 会落到 Mock 自动属性上空转。
    """
    panel.registry.scan(force=True)
    panel.skills = list(panel.registry.getByStage(panel.stage))
    for child in panel.skill_content.winfo_children():
        child.destroy()
    panel.vars = {}
    panel.build_flow_skill(panel.skill_content)
    bind_wheel = getattr(panel, '_bind_form_wheel', None)
    if callable(bind_wheel):
        bind_wheel(panel.skill_content)
    sync_form = getattr(panel, '_sync_form_view', None)
    if callable(sync_form):
        sync_form()
    panel.load()


def _import_plan(panel, plan):
    """预检问题确认 → ``perform_import`` → 重建面板；文件与文件夹入口共用。

    模块级函数而非 Panel 方法：既有测试以未绑定方式调用 Panel 方法、self 是 Mock，
    方法内再调 self._import_plan 会落到 Mock 自动属性上空转（同 ``_reload_panel_skills``）。
    """
    import skill_import_service
    alerts = skill_import_service.import_alerts([plan])
    if plan['problems'] or alerts:
        label = (str(plan['source'].parent) if plan['kind'] == 'package'
                 else str(plan['source']))
        parts = [skill_import_service.untrusted_source_notice(label, plans=[plan])]
        if plan['problems']:
            parts.append('导入前发现以下问题：\n\n'
                         + '\n'.join('· ' + p for p in plan['problems']))
        parts.append('仍要导入吗？')
        if not confirm(panel.winfo_toplevel(), TITLE, '\n\n'.join(parts), dangerous=True):
            return None
    try:
        # 回收站跟随程序目录（R2073：用户层在 程序/data/skills/<阶段>/）。
        result = skill_import_service.perform_import(
            plan, skill_import_service.program_of(plan['target_dir']))
    except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
        panel.state.configure(text='新增 SKILL 失败：' + str(exc))
        return None
    target = result['target']
    _reload_panel_skills(panel)
    label = target.parent.name if plan['kind'] == 'package' else target.name
    panel.state.configure(text='已新增 SKILL：' + label + ('（整包导入）' if plan['kind'] == 'package' else ''))
    panel.refresh_notes(str(target))
    return target


def _report_batch(panel, report, lead):
    """批量来源导入（ZIP／仓库／链接）成功后的共用收尾：重扫面板＋状态行。"""
    _reload_panel_skills(panel)
    names = '、'.join(item['name'] for item in report['installed']) or '无'
    suffix = ''
    if report['failed']:
        suffix = '；失败 ' + str(len(report['failed'])) + ' 个'
    if report['skipped']:
        suffix += '；跳过 ' + str(len(report['skipped'])) + ' 个'
    panel.state.configure(text=lead + '（%s）：%s%s' % (report['label'], names, suffix))
    return report


def _import_layer(panel):
    """「导入到」选择：``'project'``／``'user'``；没显式选「项目」、无项目或注册表无项目层回落用户层。"""
    var = getattr(panel, 'import_scope_var', None)
    wants_project = var is not None and str(var.get() or '') == '项目'
    project = getattr(getattr(panel, 'desktop', None), 'root', None)
    has_layer = isinstance(getattr(panel.registry, 'project_skills', None), (str, Path))
    return 'project' if (wants_project and project and has_layer) else 'user'


def _import_target_dir(panel, stage):
    """按「导入到」选择取阶段写入目录；轻量 registry 替身退回用户层口径。"""
    if _import_layer(panel) == 'user':
        return panel.registry.user_stage_directory_for(stage)
    fn = getattr(panel.registry, 'stage_directory_for', None)
    return fn(stage, 'project') if fn is not None else None


class PanelImportMixin:
    """Panel 的 SKILL 导入方法集（面板本体在 skill_panel.Panel）。"""

    def add_skill_from_file(self):
        """显式导入 SKILL 到本阶段的受控注册目录：外部包整包导入，预检、试冻结、旧版进回收站。"""
        import skill_import_service
        source = FileDialog(self.winfo_toplevel()).open_file(title='新增 SKILL',
                                            filetypes=[('SKILL', ('*.skill.md', 'SKILL.md')), ('全部文件', '*.*')])
        if not source:
            return None
        try:
            plan = skill_import_service.plan_import(
                source, _import_target_dir(self, self.stage), self.stage, self.registry)
        except skill_import_service.ImportBlocked as exc:
            self.state.configure(text='新增 SKILL 失败：' + str(exc))
            return None
        return _import_plan(self, plan)

    def add_skill_from_folder(self):
        """本地文件夹导入：根目录须是 SKILL 包（SKILL.md，README 兜底，同 ``_package_source``
        口径），整包走与文件导入相同的预检→换入→试冻结→登记管线。"""
        import skill_import_service
        import skill_registry
        folder = FileDialog(self.winfo_toplevel()).directory(title='新增 SKILL（文件夹）')
        if not folder:
            return None
        try:
            entry = skill_registry.Registry._package_source(Path(folder))
        except OSError:
            entry = None
        if entry is None:
            self.state.configure(text='新增 SKILL 失败：所选文件夹不是 SKILL 包（根目录需要 SKILL.md）')
            return None
        try:
            plan = skill_import_service.plan_import(
                entry, _import_target_dir(self, self.stage), self.stage, self.registry)
        except skill_import_service.ImportBlocked as exc:
            self.state.configure(text='新增 SKILL 失败：' + str(exc))
            return None
        return _import_plan(self, plan)

    def add_skill_from_archive(self):
        """ZIP 压缩包导入：``skill_archive`` 安全解包后按包／清单候选走与仓库导入
        相同的预检→换入→试冻结→登记管线。"""
        import skill_archive
        import skill_import_service
        path = FileDialog(self.winfo_toplevel()).open_file(
            title='新增 SKILL（ZIP）',
            filetypes=[('ZIP 压缩包', '*.zip'), ('全部文件', '*.*')])
        if not path:
            return None
        program = Path(skill_import_service.__file__).resolve().parent

        def _confirm(message):
            return confirm(self.winfo_toplevel(), TITLE, message, dangerous=True)

        try:
            report = skill_archive.import_archive(
                path, program, self.registry, stage_hint=self.stage, confirm=_confirm,
                options=skill_archive.ArchiveOptions(layer=_import_layer(self)))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.state.configure(text='ZIP 导入失败：' + str(exc))
            return None
        return _report_batch(self, report, 'ZIP 导入完成')

    def add_skill_from_repo(self):
        """从仓库地址导入 SKILL：owner/repo 简写、完整 URL（可带 @分支）或本地目录；
        仓库内每个 SKILL.md／*.skill.md 走与文件导入相同的预检→换入→试冻结→登记管线。"""
        import skill_import_service
        text = ask_string(self.winfo_toplevel(), TITLE,
                          'SKILL 仓库地址或本地目录（owner/repo、完整 URL 可带 @分支、本地路径）：')
        if not text or not str(text).strip():
            return None
        program = Path(skill_import_service.__file__).resolve().parent

        def _confirm(message):
            return confirm(self.winfo_toplevel(), TITLE, message, dangerous=True)

        try:
            report = skill_import_service.import_from_repo(
                str(text).strip(), program, self.registry,
                stage_hint=self.stage, confirm=_confirm, layer=_import_layer(self))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.state.configure(text='仓库导入失败：' + str(exc))
            return None
        return _report_batch(self, report, '仓库导入完成')

    def add_skill_from_url(self):
        """从 http(s) 链接导入 SKILL：GitHub 仓库（``#ref``／``/tree/<ref>/<子目录>``）
        或 ``.zip`` 直链；下载进 ``data/skills/下载缓存/`` 后走与本地 ZIP 相同的
        解包→预检→换入→试冻结→登记管线（``skill_remote_service``）。"""
        import skill_import_service
        import skill_remote_service
        text = ask_string(self.winfo_toplevel(), TITLE,
                          'SKILL 链接（GitHub 仓库地址或 .zip 直链）：')
        if not text or not str(text).strip():
            return None
        program = Path(skill_import_service.__file__).resolve().parent

        def _confirm(message):
            return confirm(self.winfo_toplevel(), TITLE, message, dangerous=True)

        try:
            report = skill_remote_service.import_from_url(
                str(text).strip(), program, self.registry,
                stage_hint=self.stage, confirm=_confirm, layer=_import_layer(self))
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.state.configure(text='链接导入失败：' + str(exc))
            return None
        return _report_batch(self, report, '链接导入完成')

    # ── T4：台账消费——检查更新与重新导入 ──

    def check_skill_updates(self):
        """「检查更新」：遍历导入台账做更新体检；有更新的条目给「重新导入」。"""
        import skill_import_service
        program = Path(skill_import_service.__file__).resolve().parent
        cache = {}

        def _probe(key, row):
            import skill_archive
            import skill_remote_service
            status = skill_remote_service.probe_row(
                key, row, program, self.registry, cache=cache)
            if status is None:
                status = skill_archive.probe_row(key, row, program, self.registry)
            return status

        try:
            project = getattr(getattr(self, 'desktop', None), 'root', None)
            statuses = skill_import_service.check_updates(
                program, probe=_probe, project=project)
            items = skill_import_service.ledger_items(program)
        except Exception as exc:
            self.state.configure(text='SKILL 更新检查失败：' + str(exc))
            return None
        return show_skill_updates(self, items, statuses)


_UPDATE_STATUS_LABELS = {'unchanged': '已是最新', 'source-newer': '有更新',
                         'local-modified': '本地已修改', 'source-missing': '源不可用'}


def _update_detail_text(key, row, status):
    return '\n'.join([
        '%s（%s）' % (row.get('name') or key, key),
        '状态：%s' % _UPDATE_STATUS_LABELS.get(status, status),
        '来源：%s' % (row.get('source') or '—'),
        '版本：%s' % (row.get('version') or '—'),
        '导入时间：%s' % (row.get('imported_at') or '—'),
    ])


def _reimport_ledger_row(panel, key, row):
    """按台账行重走对应来源的导入管线（旧版自动进回收站）；返回是否完成换入。"""
    import skill_archive
    import skill_import_service
    import skill_registry
    import skill_remote_service
    program = Path(skill_import_service.__file__).resolve().parent
    kind = str(row.get('source_kind') or
               ('dir' if row.get('kind') == 'package' else 'file'))
    layer = str(row.get('scope') or 'user')
    registry = skill_import_service.registry_for_ledger_row(program, row, panel.registry)
    stage = skill_registry.stage_from_path(Path(key).parent / 'stage_probe') \
        or str(getattr(panel, 'stage', '') or '')
    stage = skill_registry.stage_id(stage) or stage

    def _confirm(message):
        return confirm(panel.winfo_toplevel(), TITLE, message, dangerous=True)

    try:
        if kind in ('file', 'dir'):
            source = Path(str(row.get('source') or ''))
            if kind == 'dir':
                entry = skill_registry.Registry._package_source(source)
                if entry is None:
                    raise skill_import_service.ImportBlocked(
                        '来源文件夹已不是 SKILL 包：' + str(source))
                source = entry
            plan = skill_import_service.plan_import(
                source, skill_import_service._stage_dir_for(registry, stage, layer),
                stage, registry)
            return _import_plan(panel, plan) is not None
        report = None
        if kind == 'archive':
            if row.get('source_url'):
                report = skill_remote_service.import_from_url(
                    str(row['source_url']), program, registry,
                    stage_hint=stage, confirm=_confirm, layer=layer)
            else:
                report = skill_archive.import_archive(
                    str(row.get('source') or ''), program, registry,
                    stage_hint=stage, confirm=_confirm,
                    options=skill_archive.ArchiveOptions(layer=layer))
        elif kind == 'repo':
            url = str(row.get('source_url') or '')
            ref = str(row.get('source_ref') or '')
            if url:
                text = url + ('#' + ref if ref else '')
                try:
                    skill_remote_service.parse_source(text)
                except skill_import_service.ImportBlocked:
                    text = ''
                if text:
                    report = skill_remote_service.import_from_url(
                        text, program, registry, stage_hint=stage,
                        confirm=_confirm, layer=layer)
            if report is None:
                text = (url + ('@' + ref if ref else '')) if url \
                    else str(row.get('source') or '')
                report = skill_import_service.import_from_repo(
                    text, program, registry, stage_hint=stage,
                    confirm=_confirm, layer=layer)
        else:
            raise skill_import_service.ImportBlocked('台账来源类型无法识别：' + kind)
        _report_batch(panel, report, '重新导入完成')
        return True
    except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
        panel.state.configure(text='重新导入失败：' + str(exc))
        return False


def show_skill_updates(panel, items, statuses):
    """更新检查结果窗（只读列表＋详情）；``source-newer`` 条目可「重新导入所选」。"""
    if not items:
        panel.state.configure(text='SKILL 更新检查：没有导入记录')
        return None
    pending = [(key, row) for key, row in items.items()
               if statuses.get(key) != 'unchanged']
    if not pending:
        panel.state.configure(text='SKILL 更新检查：全部已是最新')
        return None
    window = BaseDialog(panel.winfo_toplevel(), 'SKILL 更新检查',
                        modal=False, chrome=False)
    window.resizable(True, True)
    window.minsize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)
    body = ttk.Frame(window, padding=SPACING['md'])
    body.pack(fill='both', expand=True)

    counts = {}
    for key, _row in pending:
        state = statuses[key]
        counts[state] = counts.get(state, 0) + 1
    summary = '导入台账 %d 条，需关注 %d 条：%s（已是最新 %d 条未列出）' % (
        len(items), len(pending),
        ' · '.join('%s %d' % (_UPDATE_STATUS_LABELS.get(state, state), count)
                   for state, count in sorted(counts.items())),
        len(items) - len(pending))
    HintLabel(body, text=summary).pack(anchor='w', pady=(SPACING['none'], SPACING['sm']))

    content = ttk.Frame(body)
    content.pack(fill='both', expand=True)
    content.columnconfigure(1, weight=1)
    content.rowconfigure(0, weight=1)
    list_frame = ttk.Frame(content)
    list_frame.grid(row=0, column=0, sticky='ns',
                    padx=(SPACING['none'], SPACING['sm']))
    box = tk.Listbox(list_frame, selectmode='browse', exportselection=False,
                     width=CHAR_WIDTH['field_md'] // 2, font=FONTS['body'])
    box.pack(side='left', fill='both', expand=True)
    list_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=box.yview)
    list_scroll.pack(side='right', fill='y')
    box.configure(yscrollcommand=list_scroll.set)
    for key, row in pending:
        box.insert('end', '%s · %s' % (row.get('name') or key,
                                       _UPDATE_STATUS_LABELS.get(statuses[key],
                                                                 statuses[key])))

    detail = TextArea(content, state='disabled')
    detail.grid(row=0, column=1, sticky='nsew')
    detail_scroll = ttk.Scrollbar(content, orient='vertical', command=detail.yview)
    detail_scroll.grid(row=0, column=2, sticky='ns')
    detail.configure(yscrollcommand=detail_scroll.set)

    def _selected():
        pick = box.curselection()
        if not pick:
            return None, None
        return pending[pick[0]]

    def show_detail(_event=None):
        key, row = _selected()
        detail.configure(state='normal')
        detail.delete('1.0', 'end')
        if key is not None:
            detail.insert('1.0', _update_detail_text(key, row, statuses[key]))
        detail.configure(state='disabled')

    def reimport():
        key, row = _selected()
        if key is None:
            panel.state.configure(text='SKILL 更新检查：先在列表里选一条')
            return
        if statuses.get(key) != 'source-newer':
            panel.state.configure(text='SKILL 更新检查：该条目不是「有更新」，无需重新导入')
            return
        if _reimport_ledger_row(panel, key, row):
            window.destroy()
            panel.check_skill_updates()

    box.bind('<<ListboxSelect>>', show_detail)
    box.selection_set(0)
    show_detail()

    actions = ttk.Frame(body)
    actions.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    SecondaryButton(actions, text='关闭', width=CHAR_WIDTH['xl'],
                    command=window.destroy).pack(side='right')
    SecondaryButton(actions, text='刷新', width=CHAR_WIDTH['xl'],
                    command=lambda: (window.destroy(),
                                     panel.check_skill_updates())).pack(
        side='right', padx=(SPACING['none'], SPACING['sm']))
    PrimaryButton(actions, text='重新导入所选', width=CHAR_WIDTH['xl'],
                  command=reimport).pack(side='left')
    return window
