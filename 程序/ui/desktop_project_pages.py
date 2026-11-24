"""项目首页与项目管理。

从 ``desktop.Desktop`` 原样迁出（R1505）：方法体未改，``self`` 语义不变，``Desktop`` 通过继承
``ProjectPagesMixin`` 获得。测试按 ``desktop.<名字>`` 打补丁的名字（confirm／open_path 等）经
``Desktop`` 注入的 ``ProjectPageServices`` 在调用时取 ``desktop`` 的当前值，补丁照常生效（R1983 J2）。
"""
import queue
import threading
import tkinter as tk
import infra.ui_plugin_registry as ui_plugin_registry
from contract.app_metadata import APP_NAME, VERSION
from datetime import date
from pathlib import Path
from domain.projects import (needs_cleanup_after_open_error, is_empty_shell_open_error,
                             project_dir_openable, shell_rescue_dirs, claimed_registration_notice,
                             EMPTY_SHELL_OPEN_NOTICE)
from tkinter import ttk
from responsive_ui import FlowBar, auto_height
from ui.ui_motion import EmptyState, bind_row_hover
from ui_tokens import TEXT_ROWS, COLORS, FONTS, SPACING, TEXT_DESC, DESKTOP_LAYOUT
from ui.desktop_page_registry import (ACCOUNT_TITLE, PAGE_ACCOUNT, PAGE_NAV_ICONS,
                                   PROJECT_ACTION_ICONS, PROJECT_GROUP_ICONS, nav_label)
from ui.ui_icons import IconLoader
from ui_widgets import (BaseDialog, Card, DataTable, NotificationDispatcher, PrimaryButton, SecondaryButton,
                        Tooltip, ask_string)
from orchestrator.recycle_recovery_controller import RecycleRecoveryController
import infra.storage_maintenance as recycle_storage
from dataclasses import dataclass
from typing import Callable


def project_sort_key(item):
    """项目列表按创建时间排；已登记 created_at 的不再碰磁盘（dict.get 的默认值会被提前求值）。"""
    if 'created_at' in item:return item['created_at']
    path=Path(item['path'])
    try:return path.stat().st_ctime
    except OSError:return 0


@dataclass(frozen=True)
class ProjectPageServices:
    """项目页与创意对话菜单（``desktop_idea_menus``）共用的宿主服务；``Desktop`` 注入，页面不读全局宿主。"""
    open_path: Callable
    context_menu: Callable
    confirm: Callable


class RecyclePanelMixin:
    """复用恢复控制器和恢复窗；所有永久删除只委托 storage 网关。"""
    def recycle_recovery_roots(self):
        roots = (getattr(self, 'root', None), getattr(self.projects, 'base', None))
        return tuple(dict.fromkeys(Path(root).resolve() for root in roots if root is not None))

    def _recycle_controller(self):
        return RecycleRecoveryController(getattr(self, 'root', None),
            getattr(self.projects, 'base', None),
            register_restored=getattr(self.projects, 'register_restored_projects', None))

    def recycle_batches(self, roots=None):
        return self._recycle_controller().list_batches()

    def _check_recycle_record(self, record):
        root = Path(record['root']).resolve()
        if root not in self.recycle_recovery_roots():
            raise ValueError('回收批次不属于当前项目或项目库')
        if record.get('unavailable'):
            raise ValueError('回收清单损坏，禁止操作：' + str(record.get('reason', '')))
        return root

    def load_recycle_batch(self, record):
        root = self._check_recycle_record(record)
        return recycle_storage.read_recycle_batch(root, record['batch'])

    def restore_recycled(self, record, source=None):
        self.load_recycle_batch(record)
        controller = self._recycle_controller()
        return controller.restore_batch(record) if source is None else controller.restore_item(record, source)

    def purge_recycled(self, records):
        if not records:
            self.status.set('回收站没有可清空的批次')
            return []
        for record in records:
            self.load_recycle_batch(record)
        count = len(records)
        confirm = self.project_page_services.confirm
        if not confirm(self.win, '永久清空回收站',
                '将永久删除 %d 个回收批次的全部文件，删除后不可恢复。是否继续？' % count, dangerous=True):
            return []
        if not confirm(self.win, '再次确认永久删除',
                '最后确认：永久清空这 %d 个批次？此操作不可撤销、不可恢复。' % count, dangerous=True):
            return []
        groups = {}
        for record in records:
            groups.setdefault(Path(record['root']), []).append(record['batch'])
        removed = []
        try:
            for root, batches in groups.items():
                removed.extend(recycle_storage.purge_recycle_batches(root, batches))
        except (OSError, ValueError) as exc:
            self.status.set('清空未全部完成，已清空 %d 批：%s' % (len(removed), exc))
            raise
        self.status.set('已永久清空 %d 个回收批次' % len(removed))
        return removed

    def purge_expired_recycle(self):
        records = []
        project = getattr(self, 'root', None)
        days = recycle_storage.recycle_retention_days(project) if project is not None else None
        for root in self.recycle_recovery_roots():
            for batch in recycle_storage.expired_recycle_batches(root, days=days):
                records.append({'root': root, 'batch': batch})
        return self.purge_recycled(records)

    def configure_recycle_retention(self):
        root = getattr(self, 'root', None)
        if root is None:
            raise ValueError('请先打开项目，再设置该项目的回收站保留期')
        days = recycle_storage.recycle_retention_days(root)
        value = ask_string(self.win, '回收站保留期',
            '请输入保留天数（默认30；0表示不自动清空）。仅点击清空过期回收站时执行，不会静默删除文件：',
            initialvalue=str(days))
        if value is None:
            return None
        saved = recycle_storage.save_recycle_retention_days(root, value.strip())
        self.status.set('已保存回收站保留期：%d 天（仅显式清空时生效）' % saved)
        return saved

    def open_recycle_recovery(self):
        """打开已承诺的回收站恢复入口；恢复决策与磁盘操作均留在 L2/L3。"""
        dialog=BaseDialog(self.win,'恢复回收站内容',geometry='920x580',minsize=(720,420))
        controller=self._recycle_controller()
        batches=[]
        ttk.Label(dialog.content,text='可恢复整批或选中条目；永久清空不可撤销、不可恢复，需要二次确认。').pack(anchor='w',pady=(SPACING['none'],SPACING['xs']))
        batch_table=DataTable(dialog.content,columns=[('scope','位置',110),('created','创建时间',155),('reason','原因',390)],show='tree headings',height=TEXT_ROWS['lg'],auto_hide_scrollbars=True)
        batch_tree=batch_table.tree
        batch_tree.heading('#0',text='批次');batch_tree.column('#0',width=SPACING['sm'] * 23,stretch=False)
        batch_table.pack(fill='x',expand=False)
        ttk.Label(dialog.content,text='批次条目（原位置）').pack(anchor='w',pady=(SPACING['sm'],SPACING['xs']))
        item_table=DataTable(dialog.content,columns=[('recycled','回收位置',420)],show='tree headings',height=TEXT_ROWS['xl'],auto_hide_scrollbars=True)
        item_tree=item_table.tree
        item_tree.heading('#0',text='原位置');item_tree.column('#0',width=SPACING['sm'] * 53)
        item_table.pack(fill='both',expand=True)
        # 批次条目可多可少：随窗口缩放、随条目数收缩，不留空白（第 R2411 期）。
        fit_items = auto_height(item_tree, item_table)
        def selected_batch():
            selected=batch_tree.selection()
            return batches[int(selected[0])] if selected else None
        def show_items(_event=None):
            item_tree.delete(*item_tree.get_children())
            record=selected_batch()
            if record:
                if record.get('unavailable'):
                    item_tree.insert('', 'end', text='清单损坏：已禁止恢复和永久清空', values=(record['reason'],))
                else:
                    for item in record['items']:
                        item_tree.insert('', 'end', values=(item['recycle_path'],), text=item['source'])
            fit_items()
        def refresh():
            nonlocal batches
            batches=controller.list_batches()
            batch_tree.delete(*batch_tree.get_children());item_tree.delete(*item_tree.get_children())
            for index,record in enumerate(batches):
                batch_tree.insert('', 'end',iid=str(index),text=record['batch'].name,
                                  values=(record['scope'],record['created_at'] or '—',record['reason'] or '—'))
            if batches:batch_tree.selection_set('0');show_items()
        def restore_all():
            record=selected_batch()
            if record is None:raise ValueError('请先选择一个回收批次')
            restored=self.restore_recycled(record)
            refresh();self.reload();self.status.set('已恢复 '+str(len(restored))+' 项回收内容。')
        def restore_selected():
            record=selected_batch();selected=item_tree.selection()
            if record is None or not selected:raise ValueError('请先选择一个待恢复条目')
            source=item_tree.item(selected[0],'text')
            restored=self.restore_recycled(record,source)
            refresh();self.reload();self.status.set('已恢复：'+str(restored[0].name))
        batch_tree.bind('<<TreeviewSelect>>',show_items)
        def purge_selected():
            record=selected_batch()
            if record is None:raise ValueError('请先选中一个回收批次')
            self.purge_recycled([record]);refresh()
        def purge_all():
            self.purge_recycled(batches);refresh()
        # 统一动作区：关闭在最右，主操作紧挨其左，刷新降为最左的次操作。
        dialog.add_action('关闭',dialog.close)
        dialog.add_action('恢复选中条目',lambda:self.safe(restore_selected),primary=True)
        dialog.add_action('恢复整批',lambda:self.safe(restore_all),primary=True)
        dialog.add_action('刷新',lambda:self.safe(refresh))
        maintenance=FlowBar(dialog.content);maintenance.pack(fill='x',pady=SPACING['xs'])
        for text,action in (('永久清空选中批次',purge_selected),('永久清空全部批次',purge_all),
                            ('设置保留期',self.configure_recycle_retention)):
            SecondaryButton(maintenance,text=text,command=lambda fn=action:self.safe(fn)).pack(side='left')
        refresh()
        return dialog


class ProjectPagesMixin(RecyclePanelMixin):
    """Desktop 的项目管理方法集（见模块说明）。"""
    def _start_legacy_project_migration(self):
        """首帧后才在 worker 迁移旧目录；Tk 线程只轮询结果。"""
        if (self._legacy_project_migration_started or not self.projects.legacy_migration_pending
                or getattr(self,'shutting_down',False)):
            return
        self._legacy_project_migration_started=True
        def migrate():
            try:
                self._project_result_data(self.projects.migrate())
            except Exception as exc:
                self._legacy_project_migration_results.put(exc)
            else:
                self._legacy_project_migration_results.put(None)
        threading.Thread(target=migrate,name='legacy-project-migration',daemon=True).start()
        self._poll_legacy_project_migration()
    def _poll_legacy_project_migration(self):
        self._legacy_project_migration_poll_id=None
        if getattr(self,'shutting_down',False):
            return
        try:
            outcome=self._legacy_project_migration_results.get_nowait()
        except queue.Empty:
            self._legacy_project_migration_poll_id=self.win.after(25,self._poll_legacy_project_migration)
            return
        if outcome is None:
            self.projects.refresh_registry();self.reload()
        else:
            self.projects.legacy_migration_pending=False
            self.status.set('旧项目迁移失败：%s；原文件未改动。' % outcome)
    def _project_result_data(self,result):
        """项目登记写服务的 L3 结果只在桌面编排层解包。"""
        from stage_execution_service import unwrap_project_result
        return unwrap_project_result(result)
    def _project_action(self,bar,text,command,*,primary=False):
        """项目动作统一交给可换行的 FlowBar；主操作换主按钮样式，窄窗只增行不裁字。"""
        button=self.button(bar,text,command)
        if primary:button.configure(style='Tokens.Primary.TButton')
        return button
    def fill_projects(self,tree):
        tree.delete(*tree.get_children())
        for state,label in [('making','在制作项目'),('completed','已完成项目')]:
            items=[p for p in self.projects.info['projects'] if p.get('status','making')==state]
            tree.tag_configure('empty-group',foreground=COLORS['text_muted'])
            tree.insert('','end',iid='group:'+state,text=f'{label}（{len(items)}）',open=bool(items),tags=() if items else ('empty-group',))
            for p in sorted(items,key=project_sort_key):
                tree.insert('group:'+state,'end',iid=p['path'],text=self.project_row_text(p))
        # 一个项目都没有时，列表中央给出柔和提示，而不是只留两个空分组标题。
        empty=getattr(tree,'_empty_state',None)
        if empty is not None:empty.show(not self.projects.info['projects'])
    def refresh_sidebar_title(self):
        """R2933：侧栏顶部浮层已删；方法保留给既有调用点，app_title 不存在时直接返回。"""
        title=getattr(self,'app_title',None)
        if title is None:return
        root=getattr(self,'root',None)
        text=APP_NAME
        if root is not None:
            text=next((p['name'] for p in (getattr(self.projects,'info',None) or {}).get('projects',[])
                       if Path(p['path'])==root),'') or Path(root).name or APP_NAME
            limit=DESKTOP_LAYOUT['sidebar_title_chars']
            if len(text)>limit:text=text[:limit-1]+'…'
        if title.cget('text')!=text:title.configure(text=text)
    def project_row_text(self,p):
        """项目行文字：当前打开的项目前加「●」，让用户随时看得出现在在哪个项目里。"""
        path=Path(p['path'])
        if not path.is_dir():note='（目录已失效，可右键清除登记）'
        elif not (path/'config.json').is_file():note='（没有项目配置文件，可重新查找或清除登记）'
        else:note=''
        root=getattr(self,'root',None)
        current=root is not None and path==root
        return ('● ' if current else '')+p['name']+note
    def mark_current_project(self):
        """切换项目后同步侧栏选择器与首页行文字（● 标记），并把项目名写进窗口标题。"""
        self._sync_project_picker(snap=True)
        home=getattr(self,'_project_home_tree',None)
        if home is not None and home.winfo_exists():
            for p in (getattr(self.projects,'info',None) or {}).get('projects',[]):
                if home.exists(p['path']):home.item(p['path'],text=self.project_row_text(p))
        self.refresh_sidebar_title()
        title=APP_NAME+' · '+VERSION
        if self.root is not None:
            from contract.script_contract import project_name
            title+=' · 当前项目：'+project_name(self.root)
        win=getattr(self,'win',None)
        if win is not None:win.title(title)
    def _schedule_project_recovery(self,target):
        """首屏剧本准备页绘制后，再执行可延后的项目维护。"""
        if self._startup_project_recovery_job is not None:
            try:self.win.after_cancel(self._startup_project_recovery_job)
            except tk.TclError:pass
        self._startup_project_recovery_job=self.win.after_idle(
            lambda:self._complete_project_recovery(target))
    def _complete_project_recovery(self,target):
        self._startup_project_recovery_job=None
        if getattr(self,'shutting_down',False) or self.root!=target:return
        self.import_generated_assets()
        # 阶段目录改为按实际使用时才创建。过去每次打开项目都会预建 11 套
        # input/output/assets/... 空骨架，并为根目录再建一层链接，资源管理器
        # 看起来像两份文件；真实产物仍只保存在 writing、episode 等工作目录。
        self.prune_asset_leftovers()
        self.restore_asset_resume()
    def adopt_legacy_layout(self):
        """第 64 期任务 3：老目录接进阶段树（只做目录联接，绝不搬动、绝不删除）。

        用户报的「文件还在旧文件夹中，没有导入新的文件夹架构」：老目录照旧是权威位置，
        阶段目录下补一个同名入口，新老两头都看得见。接不上不拦下「打开项目」，但要说明未归位。
        """
        if not self.root:return {}
        try:
            from contract.stage_layout import adopt_legacy
            result=adopt_legacy(self.root)
        except Exception as exc:
            self.status.set('旧目录未归入新架构：%s；请稍后重试。' % exc)
            return {}
        made=list(result.get('made') or [])
        if made:
            self.status.set('旧目录已归入新架构：'+'、'.join(path.name for path in made))
            self.record_legacy_adoption(made)
        return result
    def record_legacy_adoption(self,made):
        """归位留一笔记录（升级说明要照着看）：_archive/logs/旧目录归位.json。"""
        try:
            from stage_execution_service import record_stage_legacy_adoption
            return record_stage_legacy_adoption(self.root,made)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            # 已完成的目录归位不能回滚，但审计记录失败必须让用户知道它不可追溯。
            self.status.set('旧目录归位记录未写入：%s；请稍后重试。' % exc)
            return None
    def restore_project_selection(self):
        """选择器复位回当前项目；高亮＝当前项目，用户取消或被拦下时不能留在别的项上。"""
        self._sync_project_picker(snap=True)
    def set_project_group(self,state,popup=False):
        """侧栏分组筛选：making/completed/all 切换项目集合；popup 时弹出该组项目选择层（R2946，弹层实现在 PageNavMixin）。"""
        if state!=self._project_group:self._project_group=state;self._sync_project_group_styles();self._sync_project_picker()
        if popup:self._post_project_picker(state)
    def _close_sidebar_expand(self):
        """REQ-UI-SIDEBAR-1：换页／开浮层时收起侧栏项目二级列（实现在 ui.desktop_sidebar_project）。"""
        from ui.desktop_sidebar_project import close_sidebar_expand
        close_sidebar_expand(self)
    def _sync_project_group_styles(self):
        active=getattr(self,'_project_group','making')
        for state,btn in getattr(self,'project_group_buttons',{}).items():
            btn.configure(style='Selected.RailIcon.TButton' if state==active else 'RailIcon.TButton')
    def _sync_project_picker(self,snap=False):
        """项目集合同步：按分组算 ``_picker_items``（R2946 起选择器是弹层，没有下拉框可填）。"""
        projects=(getattr(self.projects,'info',None) or {}).get('projects',[]) or []
        root=getattr(self,'root',None)
        def is_current(p):
            if root is None:return False
            try:return Path(str(p.get('path')))==root
            except (OSError,ValueError):return False
        group=getattr(self,'_project_group','making')
        if group not in ('all','making','completed'):group='making'
        if snap:
            current_group=next((p.get('status','making') for p in projects if is_current(p)),None)
            if group!='all' and current_group is not None and current_group!=group:
                group=current_group
                self._project_group=group
                self._sync_project_group_styles()
        items=[p for p in projects if group=='all' or p.get('status','making')==group]
        items.sort(key=project_sort_key)
        self._picker_items=items
        name_list=getattr(self,'project_name_list',None)
        if name_list is not None:name_list.refresh()
    def _build_project_rail(self,side):
        """侧栏项目区（REQ-UI-SIDEBAR-1）：单个「项目」图标＋名称列表；四个原入口收进右侧二级列。"""
        from ui.desktop_sidebar_project import build_project_rail
        build_project_rail(self,side)
    def project_switch_blocker(self):
        """当前项目还有任务在跑时的拦截原因；空串表示可以切换。"""
        if self.worker:return '后台任务仍在运行'
        if self.idea_chat_controller.requesting:return '创意对话正在等待模型回复'
        if self.script_agent_processes():return '剧本 Agent 仍在运行'
        return ''
    def request_project_switch(self,path):
        """侧栏单击不再直接切换：先拦住进行中的任务，再让用户确认；取消就留在原项目。"""
        from contract.script_contract import project_name
        reason=self.project_switch_blocker()
        if reason and self.root is not None:
            self.restore_project_selection()
            raise ValueError(reason+'，现在切换会让结果写不进当前项目。请等它完成或先中断，再切换项目。')
        target=next((p['name'] for p in self.projects.info['projects'] if p['path']==path),project_name(path))
        current=project_name(self.root) if self.root is not None else ''
        message='切换到项目「'+target+'」？'
        if current:message+='\n\n当前项目：「'+current+'」。切换后所有页面、文件列表与新生成的内容都归「'+target+'」。'
        if not self.project_page_services.confirm(self.win,'切换项目',message):
            self.restore_project_selection()
            self.status.set('已取消切换，仍在项目「'+current+'」')
            return False
        return self.open_project_or_cleanup(path)
    def open_project_or_cleanup(self,path):
        """从侧栏或项目首页打开项目，并记住当天的用户选择。"""
        try:
            self.load(path)
        except Exception as exc:
            if not needs_cleanup_after_open_error(exc):raise
            self.status.set(EMPTY_SHELL_OPEN_NOTICE if is_empty_shell_open_error(exc)
                            else '剧本已删除：请在项目选择窗点击「删除选中项目」清理残留项目。')
            self._cleanup_project_path=str(path)
            self.choose_project()
            return False
        # ``load`` 可能已把资源管理器改名后的旧登记认领到新目录；日常选择必须
        # 记住实际打开的项目，不能把调用入口携带的旧路径再写回设置。
        self.remember_daily_project_choice(getattr(self,'root',None) or path)
        return True
    def daily_project_choice(self):
        """返回今天已确认过的项目；过期、已删或未登记的记录一律不使用。"""
        if self.settings.get('project_choice_day')!=date.today().isoformat():return None
        path=str(self.settings.get('project_choice_path') or '')
        if path in [item.get('path') for item in self.projects.info.get('projects',[])]:return path
        return None
    def remember_daily_project_choice(self,path):
        """仅记录项目入口，不写入用户的剧本、分镜或阶段配置。"""
        from stage_execution_service import publish_desktop_preferences
        result=publish_desktop_preferences(self.settings_file,self.settings,{
            'project_choice_day':date.today().isoformat(),
            'project_choice_path':str(path),
        })
        if not result.ok:raise ValueError(result.reason)
        self.settings=result.data
    def _sync_desktop_project_paths(self,old_path,new_path):
        """认领成功后同步桌面级入口；项目文件改写仍归 Projects 的事务。"""
        from stage_execution_service import publish_desktop_preferences
        old=Path(old_path);new=Path(new_path);updates={}
        if self.settings.get('project_choice_path')==str(old):
            updates['project_choice_path']=str(new)
        legacy=self.settings.get('frame_json_by_project')
        if isinstance(legacy,dict) and str(old) in legacy:
            migrated=dict(legacy);value=migrated.pop(str(old))
            if isinstance(value,str):
                try:value=str(new/Path(value).relative_to(old))
                except ValueError:pass
            migrated[str(new)]=value;updates['frame_json_by_project']=migrated
        if updates:
            result=publish_desktop_preferences(self.settings_file,self.settings,updates)
            if not result.ok:raise ValueError(result.reason)
            self.settings=result.data
    def choose_project(self):
        # 自动续开项目时，三虎的量测只排到这次选择交回事件循环之后；否则
        # 它的 ``update_idletasks`` 会重入本调用栈并放大启动时间。
        if self.projects.legacy_migration_pending:
            self.status.set('正在后台迁移旧项目…')
            self._startup_timer=self.win.after(25,self.choose_project)
            return None
        self.win._desktop_loading_project=True
        try:
            return self._choose_project_impl()
        finally:
            self.win._desktop_loading_project=False
    def _choose_project_impl(self):
        if not self.projects.info['projects']:
            self.safe(self.new)
            return
        cleanup_path=getattr(self,'_cleanup_project_path',None)
        self._cleanup_project_path=None
        startup=bool(getattr(self,'_startup_project_choice',False));self._startup_project_choice=False
        remembered=self.daily_project_choice() if startup and not cleanup_path else None
        if remembered:
            try:self.load(remembered,defer_page=startup);return
            except (ValueError,OSError):
                self.status.set('今天选定的项目已不可用，请选择其他项目或导入新剧本')
        popup=BaseDialog(self.win,'选择项目 · '+APP_NAME,geometry='640x480',minsize=(500,380),modal=False,chrome=False);popup.attributes('-alpha',0)
        # 动作区先占底边：窗口再矮也只压缩项目列表，不把按钮挤到可视区外；
        # FlowBar 在窄窗里自动换行，每个按钮保持自己的请求宽度。
        actions=FlowBar(popup)
        actions.pack(side='bottom',fill='x',padx=SPACING['xl'],pady=(SPACING['none'],SPACING['lg']))
        ttk.Label(popup,text='今天继续哪个故事？',font=FONTS['heading_1']).pack(anchor='w',padx=SPACING['xl'],pady=(SPACING['xl'],SPACING['sm']))
        ttk.Label(popup,text='选择项目后点击进入，或双击项目名称。',style='Muted.TLabel').pack(anchor='w',padx=SPACING['xl'],pady=(SPACING['none'],SPACING['md']))
        missing_notice='项目目录不存在或已被移动，不能进入项目。可「重新查找项目」；选择清除时只清除登记，不动磁盘。'
        notice=tk.StringVar(value=((EMPTY_SHELL_OPEN_NOTICE if Path(cleanup_path).is_dir() else missing_notice)
                                   if cleanup_path else ''))
        notice_label=ttk.Label(popup,textvariable=notice,foreground=COLORS['warning_text'],wraplength=TEXT_DESC['wraplength'])
        notice_label.pack(anchor='w',padx=SPACING['xl'],pady=(SPACING['none'],SPACING['sm']))
        def fit_notice(event):
            if event.width>SPACING['xl']*2:
                notice_label.configure(wraplength=event.width-SPACING['xl']*2)
        popup.bind('<Configure>',fit_notice,add='+')
        tree=ttk.Treeview(popup,show='tree',selectmode='browse');tree.pack(fill='both',expand=True,padx=SPACING['xl'])
        tree._empty_state=EmptyState(popup,'还没有项目\n关闭此窗口后点「+ 新建项目」开始',anchor_widget=tree)  # 与项目首页同一套空状态
        self.fill_projects(tree)
        selected_path=cleanup_path or self.projects.info.get('active')
        if selected_path and tree.exists(selected_path):tree.selection_set(selected_path);tree.see(selected_path)
        def delete_selected_project():
            """项目不完整时也能从选择窗口清理残留目录，无需先成功打开它。"""
            selected=tree.selection()
            if not selected or selected[0].startswith('group:'):
                notice.set('请先选中要删除的项目。');return
            path=selected[0]
            item=next((dict(one) for one in self.projects.info['projects'] if one.get('path')==path),None)
            if item is None:
                notice.set('该项目已不在列表中。');return
            if not Path(path).exists():
                if not self.project_page_services.confirm(popup, '只清除登记',
                        '项目目录已不存在。只清除这条项目登记，不会改动磁盘上的任何文件。是否继续？',
                        dangerous=True):return
                if not self.clear_missing_project(item,confirmed=True):
                    notice.set('清除失效项目登记失败，请查看状态栏后重试。');return
                self.fill_projects(tree)
                notice.set('已只清除失效项目登记。');return
            if not project_dir_openable(path):
                # 空壳登记：目录还在但没有 config.json，回收它找不回项目；先劝取消，
                # 同时把还没登记的项目目录摆出来，用户仍继续就只清登记，绝不动磁盘。
                rescue=shell_rescue_dirs(self.projects.info,self.projects.base,path)
                message=(f"{item.get('name','项目')}\n{path}\n\n"
                         '这个目录里没有项目配置文件（空壳），把它移入回收站找不回项目，建议先取消；'
                         '可改用「重新查找项目」找回，或只清除这条登记，不动磁盘。')
                if rescue:message+='\n\n项目库里尚未登记的目录：\n'+'\n'.join(rescue)
                message+='\n\n仍要继续只会清除这条登记，不会改动磁盘上的任何文件。是否继续？'
                if not self.project_page_services.confirm(popup, '只清除登记',
                        message,dangerous=True):return
                if not self.clear_missing_project(item,confirmed=True):
                    notice.set('清除失效项目登记失败，请查看状态栏后重试。');return
                self.fill_projects(tree)
                notice.set('已只清除失效项目登记。');return
            linked=False
            try:target=self.projects.deletion_target(path)
            except ValueError as exc:
                if '链接' not in str(exc):raise
                target=Path(path);linked=True
            message=(f"{item.get('name','项目')}\n{target}\n\n"
                     +('这是一条项目目录链接。只会删除链接和项目登记，不会删除链接指向的真实目录。是否删除？'
                       if linked else '将把这个项目文件夹及全部素材移入项目库回收站（可恢复，不是永久清除；同一块磁盘上回收不等于释放空间）。是否继续？'))
            if not self.project_page_services.confirm(popup, '移入项目回收站',
                    message,
                    dangerous=True):return
            notice.set('正在删除项目文件夹…');tree.state(['disabled'])
            def gone(_):
                self.reload();self.fill_projects(tree)
                if str(self.root or '')==path:self.load(None)
                if not self.projects.info['projects']:popup.destroy()
                else:
                    notice.set('项目已删除；请选择其他项目或新建项目。')
                    tree.state(['!disabled']);popup.lift();popup.focus_force()
                self.status.set('项目及残留目录已删除')
            self.async_(lambda:self._project_result_data(self.projects.unlink_registered_project(path) if linked else self.projects.delete(path)),gone)
        def refind_selected_project():
            selected=tree.selection()
            if not selected or selected[0].startswith('group:'):
                notice.set('请先选中失效的项目登记。');return
            old=selected[0]
            try:outcome=self._project_result_data(self.projects.reconcile_missing(old))
            except Exception as exc:
                notice.set(str(exc));return
            if outcome.get('state')=='none':
                notice.set('登记还在原位：目录能正常打开，无需重新查找。');return
            if outcome.get('state')=='claimed':
                self.reload();self.fill_projects(tree)
                new=outcome['path'];tree.selection_set(new);tree.see(new)
                notice.set(claimed_registration_notice(old));return
            choices=outcome.get('choices',[]);manual=not choices
            if manual:
                # 指纹没对上时，把项目库里尚未登记的目录摆出来让用户手动指定。
                choices=outcome.get('unregistered',[])
            if not choices:
                notice.set('没有找到可认领的目录；可只清除这条失效登记。');return
            picker=BaseDialog(popup,'选择重新找到的项目目录',modal=False)
            ttk.Label(picker.content,text=('找到多个候选目录，请确认实际项目：' if not manual
                      else '没有自动匹配；请从项目库里未登记的目录中指定一个：')).pack(
                      anchor='w',pady=(SPACING['none'],SPACING['sm']))
            candidate=tk.StringVar(value=choices[0])
            for value in choices:
                ttk.Radiobutton(picker.content,text=value,variable=candidate,value=value).pack(anchor='w',pady=SPACING['xs'])
            def claim():
                try:claimed=self._project_result_data(self.projects.reconcile_missing(old,selected=candidate.get(),manual=manual))
                except Exception as exc:
                    NotificationDispatcher(self.status, parent=picker).error(str(exc), title='无法同步项目登记');return
                picker.close();self.reload();self.fill_projects(tree)
                new=claimed['path'];tree.selection_set(new);tree.see(new)
                notice.set(claimed_registration_notice(old))
            picker.add_action('取消',picker.close)
            picker.add_action('认领此目录',claim,primary=True)
        def enter(event=None):
            selected=tree.selection()
            if not selected or selected[0].startswith('group:'):return
            try:self.load(selected[0])
            except Exception as e:
                # 目录失效不代表剧本被删除；保留登记，等待用户重新定位或确认清除。
                if needs_cleanup_after_open_error(e):
                    notice.set(EMPTY_SHELL_OPEN_NOTICE if is_empty_shell_open_error(e) else missing_notice)
                    return
                NotificationDispatcher(self.status, parent=popup).error(str(e), title='无法打开项目');return
            # 同侧栏入口：成功认领后以 load() 解析出的实际根目录记忆当天选择。
            self.remember_daily_project_choice(getattr(self,'root',None) or selected[0])
            popup.destroy()
        PrimaryButton(actions,text='进入项目 →',command=enter)
        SecondaryButton(actions,text='+ 新建项目',command=lambda:(popup.destroy(),self.safe(self.new)))
        SecondaryButton(actions,text='恢复回收站内容…',command=lambda:self.safe(self.open_recycle_recovery))
        SecondaryButton(actions,text='重新查找项目',command=refind_selected_project)
        SecondaryButton(actions,text='删除选中项目',command=lambda:self.safe(delete_selected_project))
        tree.bind('<Double-1>',enter);tree.bind('<Return>',enter)
        popup.bind('<Escape>',lambda e:popup.destroy());popup.grab_set();tree.focus_set()
    def build_account_nav(self,side):
        """「00 会员账户」排在 01 之上；它不在 self.nav 里，翻页键与阶段页序号都不受影响。"""
        image=IconLoader.nav_icon(side,PAGE_NAV_ICONS.get(PAGE_ACCOUNT))
        self.account_button=SecondaryButton(side,text=nav_label(PAGE_ACCOUNT),image=image,
            compound='image' if image is not None else 'text',width=0,
            command=lambda:self.go_page(PAGE_ACCOUNT),style='RailIcon.TButton')
        Tooltip(self.account_button,ACCOUNT_TITLE)
        self.account_button.pack(anchor='w',pady=(SPACING['none'],DESKTOP_LAYOUT['nav_gap']))
    def project_home(self):
        self.note('选择一个故事继续制作。右键项目可标记完成、恢复制作或删除项目。删除项目＝移入项目库回收站（可恢复，不是永久清除）；同一块磁盘上回收不等于释放空间；登记与磁盘不一致时点“重建项目索引”；可再生缓存由自动清理单独回收。')
        tree=ttk.Treeview(self.content,show='tree',height=TEXT_ROWS['2xl'],selectmode='browse')
        # 动作区先占底边：矮窗口只缩短项目列表，不允许把动作按钮推出可视区。
        actions=FlowBar(self.content);actions.pack(side='bottom',fill='x',pady=SPACING['sm'])
        bind_row_hover(tree)
        tree._empty_state=EmptyState(self.content,'还没有项目\n点击下方「＋ 创建新项目」，开始您的第一个故事',anchor_widget=tree)
        tree.pack(fill='both',expand=True,pady=SPACING['lg']);self.fill_projects(tree)
        self._project_home_tree=tree
        tree.bind('<Button-3>',lambda e:self.project_menu(e,tree))
        def enter(event=None):
            selected=tree.selection()
            if selected and not selected[0].startswith('group:'):self.safe(lambda:self.open_project_or_cleanup(selected[0]))
        tree.bind('<Double-1>',enter);tree.bind('<Return>',enter)
        self._project_action(actions,'进入选中的项目 →',enter,primary=True)
        self._project_action(actions,'＋ 创建新项目',self.new)
        self._project_action(actions,'创建练习项目：雨夜修伞',self.create_practice_project)
        self._project_action(actions,'当前项目存储盘点（只读）',self.show_project_storage)
        self._project_action(actions,'恢复回收站内容…',self.open_recycle_recovery)
        self._project_action(actions,'重建项目索引',self.rebuild_project_index)
        self._project_action(actions,'导出诊断包…',self.export_diagnostics_package)
        self._project_action(actions,'运行状况…',lambda:ui_plugin_registry.module('task_center_ui').show(self))
    def create_practice_project(self):
        """复用项目创建器隔离练习数据；不调用模型、不伪造阶段完成。"""
        sample = Path(__file__).resolve().parents[1] / 'resources' / 'examples' / 'rainy_umbrella'
        project = self._project_result_data(self.projects.create('练习－雨夜修伞', sample / 'episode.json'))
        self.reload()
        self.load(project)
        self.remember_daily_project_choice(project)
        self.project_page_services.open_path(sample / '开始练习.md')
        self.status.set('已创建独立练习项目：10镜60秒；首帧、配音与视频尚未生成，操作步骤见练习指南。')

    def show_project_storage(self):
        if not self.root:
            raise ValueError('请先进入要盘点的项目')
        self.async_descriptor('storage_inspect', {'root': str(self.root.resolve())}, label='项目存储盘点')

    def rebuild_project_index(self):
        """按磁盘事实重建项目索引：补登新目录、移除失效登记；不移动或删除任何项目文件。"""
        outcome=self._project_result_data(self.projects.rebuild_registry())
        self.reload()
        self.status.set('已重建项目索引：补登 %d 个、移除失效 %d 个（未改动磁盘文件）'
                        % (len(outcome.get('added',[])),len(outcome.get('dropped',[]))))
        return outcome
    def set_project_status(self,item,status):
        self._project_result_data(self.projects.set_status(item['path'],status));self.reload()
        if self.root:self._sync_project_picker(snap=True)
        else:self.show(0)
        self.status.set('已完成项目' if status=='completed' else '已恢复到在制作项目')
    def restore_scroll(self,offset):
        """按像素恢复滚动位置：重建后页面高度可能变了，用比例换算回同样的位置。"""
        try:region=[int(float(part)) for part in self.canvas.cget('scrollregion').split()]
        except (ValueError,tk.TclError):return
        height=region[3] if len(region)==4 else 0
        if height<=0:return
        self.canvas.yview_moveto(max(0.0,min(1.0,offset/height)))
    def open_current_project(self):
        if self.root is None:raise ValueError('请先创建项目')
        self.project_page_services.open_path(self.root)
    def project_menu(self,event,tree=None):
        if self.worker:return
        tree=tree if tree is not None else getattr(self,'_project_home_tree',None)
        if tree is None:return
        path=tree.identify_row(event.y)
        if not path or path.startswith('group:'):return
        item=next((dict(p) for p in self.projects.info['projects'] if p['path']==path),None)
        if item is None:return
        return self._project_item_menu(item,event)
    def _project_item_menu(self,item,event):
        menu=self.project_page_services.context_menu(self.win)
        completed=item.get('status','making')=='completed'
        menu.command('恢复为在制作项目' if completed else '标记为已完成项目',lambda:self.safe(lambda:self.set_project_status(item,'making' if completed else 'completed')))
        menu.separator()
        if not Path(item['path']).exists():
            # 与项目选择弹窗一致：幽灵登记没有可回收的目录，只能清登记。
            menu.command('只清除失效项目登记',lambda:self.safe(lambda:self.clear_missing_project(item)))
            menu.separator()
        menu.command('恢复回收站内容…',lambda:self.safe(self.open_recycle_recovery))
        menu.separator()
        menu.command('删除项目及全部素材…',lambda:self.safe(lambda:self.delete_project(item)))
        return menu.popup(event)
    def clear_missing_project(self,item,confirmed=False):
        """主界面右键清理幽灵登记；不把不存在的目录送入回收流程。"""
        path=str(item['path'])
        if project_dir_openable(path):
            raise ValueError('项目目录仍存在，请使用「删除项目及全部素材」移入回收站')
        if not confirmed and not self.project_page_services.confirm(self.win,
                '只清除登记', '项目目录已不存在。只清除这条项目登记，不会改动磁盘上的任何文件。是否继续？',
                dangerous=True):
            return False
        try:self._project_result_data(self.projects.clear_missing_registration(path))
        except (OSError,ValueError) as exc:
            # 注册表落盘失败不能让主界面或选择弹窗看起来像已清理；目录仍存在
            # 的输入错误在上面的显式判断处上抛，只有写入／登记竞态走可重试降级。
            self.status.set('清除失效项目登记失败，请稍后重试：'+str(exc))
            return False
        if str(self.root or '') == path:
            self.root=None
        self.reload()
        self.status.set('已只清除失效项目登记。')
        return True
    def delete_project(self,item,confirmed=False):
        raw_project=Path(item['path'])
        project=raw_project.resolve()
        sessions=[(key,v) for key,v in self.video_sessions.items() if v.root.resolve().is_relative_to(project)]
        for key,v in sessions:
            pending=any(r.get('state') in ('submitting','unknown','queued','running','succeeded') for versions in v.studio.state()['shots'].values() for r in versions)
            if v.busy or getattr(v,'optimizer_busy',False) or pending:raise ValueError('此项目仍有视频或提示词任务，请待任务结束或处理完成后再删除项目；其他页面可以正常使用。')
        linked=False
        try:target=self.projects.deletion_target(item['path'])
        except ValueError as exc:
            if '链接' not in str(exc):raise
            target=raw_project;linked=True
        note=('这是一条项目目录链接。只会删除链接和项目登记，不会删除链接指向的真实目录。'
              if linked else '将项目的剧本、图片、音频、视频和成片移入项目库回收站；可通过“恢复回收站内容…”入口恢复。')
        if not confirmed and not self.project_page_services.confirm(self.win,'移入项目回收站',f"{item['name']}\n{target}\n\n{note} 是否继续？",dangerous=True):return
        for key,v in sessions:
            if hasattr(v,'timer'):v.scheduler.after_cancel(v.timer)
            if self.video is v:self.video=None
            v.footer.destroy();v.window.destroy();self.video_sessions.pop(key,None)
        def completed(_):
            if self.root==target:self.brief_editor=None
            self.reload();self.load(None);self.status.set('项目及全部文件已移入项目库回收站')
        self.async_(lambda:self._project_result_data(self.projects.unlink_registered_project(item['path']) if linked
                            else self.projects.delete(item['path'])),completed)
