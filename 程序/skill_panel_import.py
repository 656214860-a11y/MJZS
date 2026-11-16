"""阶段配置面板的 SKILL 导入动作（R2881 拆出）：文件导入与仓库导入。

面板本体在 ``skill_panel.Panel``；本模块只承载「新增 SKILL」两条入口的
交互与 ``skill_import_service`` 调用，导入管线（预检→暂存→换入→试冻结→
登记）仍全部在服务层。仓库地址形态见 ``skill_import_service.parse_repo_ref``。
"""
from pathlib import Path

from ui_dialogs import FileDialog
from ui_widgets import ask_confirmation, ask_string

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
    if plan['problems']:
        message = ('导入前发现以下问题：\n\n' + '\n'.join('· ' + p for p in plan['problems'])
                   + '\n\n仍要导入吗？')
        if not confirm(panel.winfo_toplevel(), TITLE, message, dangerous=True):
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
                source, self.registry.user_stage_directory_for(self.stage), self.stage, self.registry)
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
                entry, self.registry.user_stage_directory_for(self.stage), self.stage, self.registry)
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
                path, program, self.registry, stage_hint=self.stage, confirm=_confirm)
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.state.configure(text='ZIP 导入失败：' + str(exc))
            return None
        _reload_panel_skills(self)
        names = '、'.join(item['name'] for item in report['installed']) or '无'
        suffix = ''
        if report['failed']:
            suffix = '；失败 ' + str(len(report['failed'])) + ' 个'
        if report['skipped']:
            suffix += '；跳过 ' + str(len(report['skipped'])) + ' 个'
        self.state.configure(text='ZIP 导入完成（%s）：%s%s' % (report['label'], names, suffix))
        return report

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
                stage_hint=self.stage, confirm=_confirm)
        except (skill_import_service.ImportBlocked, OSError, ValueError) as exc:
            self.state.configure(text='仓库导入失败：' + str(exc))
            return None
        _reload_panel_skills(self)
        names = '、'.join(item['name'] for item in report['installed']) or '无'
        suffix = ''
        if report['failed']:
            suffix = '；失败 ' + str(len(report['failed'])) + ' 个'
        if report['skipped']:
            suffix += '；跳过 ' + str(len(report['skipped'])) + ' 个'
        self.state.configure(text='仓库导入完成（%s）：%s%s' % (report['label'], names, suffix))
        return report
