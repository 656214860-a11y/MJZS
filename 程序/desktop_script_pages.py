"""剧本结构页与剧本相关方法。

``ScriptPagesMixin`` 通过实例的 ``script_page_services`` 使用文件打开与菜单服务。
Desktop 在组合入口注入服务；独立页面测试不需要初始化 Desktop 或登记全局宿主。
"""
import edit_habits
import pet_state
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable
import project_stages
import script_view_style
import tkinter as tk
import ui_plugin_registry
from desktop_idea_chat import model_error_display
from pathlib import Path
from responsive_ui import FlowBar
from tkinter import ttk
from ui_tokens import (
    BUTTON_WIDTH_EDIT,
    COLORS,
    SCRIPT_VIEW_FONT,
    SCRIPT_VIEW_PADDING,
    SPACING,
)
from ui_widgets import PrimaryButton, SecondaryButton, TextArea
from desktop_page_support import STAGE_ACTION_WIDTH

PAGE = pet_state.PAGE_OF

LOGGER = logging.getLogger(__name__)


def _safe_after(widget, delay, callback):
    """安排一次性 Tk 定时器；窗口销毁后 after 会抛 TclError，吞掉并返回 None 让轮询停下。"""
    try:
        return widget.after(delay, callback)
    except tk.TclError:
        return None


def _safe_after_idle(widget, callback):
    """安排空闲回调；窗口销毁时吞掉 TclError，与 await_preview 既有守卫同构。"""
    try:
        return widget.after_idle(callback)
    except tk.TclError:
        return None


def _set_script_wrap(preview, horizontal, styled):
    """小文件按词换行并收起横向滚动条；大文件保留横向滚动。"""
    preview.configure(wrap='word' if styled else 'none')
    if styled:
        horizontal.grid_remove()
    else:
        horizontal.grid()


def _build_script_preview(text_area):
    """剧本正文文本框与两条滚动条；返回 (文本框, 横向滚动条)。"""
    preview = TextArea(text_area, bg=COLORS["background_card"], fg=COLORS["text_primary"], height=1,
                       wrap='word', undo=True, maxundo=-1, font=SCRIPT_VIEW_FONT, relief='flat',
                       padx=SCRIPT_VIEW_PADDING[0], pady=SCRIPT_VIEW_PADDING[1])
    scroll = ttk.Scrollbar(text_area, orient='vertical', command=preview.yview)
    # 大文件保留全文，以横向滚动浏览长行；小文件由 set_preview 改为按词换行。
    horizontal = ttk.Scrollbar(text_area, orient='horizontal', command=preview.xview)
    preview.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
    preview.grid(row=0, column=0, sticky='nsew'); scroll.grid(row=0, column=1, sticky='ns')
    horizontal.grid(row=1, column=0, sticky='ew')
    text_area.columnconfigure(0, weight=1); text_area.rowconfigure(0, weight=1)
    return preview, horizontal


SCRIPT_EDIT_BUTTON_WIDTH = BUTTON_WIDTH_EDIT  # 编辑/后退/恢复三按钮的字符宽度，给下拉框让出横向空间。


class _DocumentPicker(ttk.Combobox):
    """剧本文件下拉框；对外保持 selection/get_children/item 接口，供页面逻辑与测试读取。"""
    def __init__(self, master, paths, active):
        self._paths = tuple(paths)
        names = [path.name for path in self._paths] or ['尚无可用文件']
        super().__init__(master, values=names, state='readonly', height=min(10, len(names)))
        self.current(self._paths.index(active) if active in self._paths else 0)

    def get_children(self):
        # 无文件时保留一行占位，与旧目录表的“尚无可用文件”行一致（占位行不可选中）。
        return tuple(str(path) for path in self._paths) or ('',)

    def item(self, iid, option=None):
        name = Path(iid).name if iid else '尚无可用文件'
        return (name,) if option == 'values' else {'values': (name,)}

    def selection(self):
        return (str(self._paths[self.current()]),) if self._paths else ()

    def selection_set(self, iid):
        if self._paths and iid in self.get_children():
            self.current(self.get_children().index(iid))


def _reset_preview_text(preview, text, kind):
    """清空预览并整段刷入文本、按需加样式；返回后留在 normal 态由调用方决定下一步。"""
    preview.configure(state='normal')
    preview.delete('1.0', 'end')
    preview.insert('1.0', text)
    if script_view_style.should_style(text):
        script_view_style.apply_tags(preview, text, kind)
    preview.edit_reset()


def _record_natural_edit(page, before, after, name):
    """REQ-S01-58：记下这次修改供「修改习惯」归纳；记录失败不影响已完成的保存。"""
    if not getattr(page, 'root', None):
        return
    try:
        edit_habits.record_edit(page.root, 'script', before, after, name)
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.warning('修改记录未保存：%s', exc)


def _install_script_edit_controls(page, controls, box):
    """给单个剧本预览框装上「编辑／后退／恢复／保存」按钮与无 Tk 的编辑控制器。

    控制器持有撤销栈，只在点「保存」时落盘；本函数只把 Tk 事件与按钮接到控制器回调，不写项目
    数据（落盘由控制器注入的 save_document 完成）。按钮与控制器实例以
    ``attribute + '_edit_button'`` 等名登记到页面实例上，供测试与页面逻辑读取。
    """
    # box 是 _ContentBox：预览框、已读原文、当前文档与内容框配置都从它取。
    preview, loaded, active, kind = box.preview, box.loaded, box.active, box.kind
    title, editable, attribute = box.title, box.editable, box.attribute
    from script_structure_edit_controller import ScriptStructureEditController

    def save_document(value):
        destination = Path(active['path'])
        value = str(value or '').strip()
        if not value:
            raise ValueError('剧本内容不能为空。')
        if kind == 'natural':
            from script_contract import save_natural_script
            save_natural_script(destination, value)
        else:
            from agent.core import save_text
            save_text(destination, value + '\n')

    controller = ScriptStructureEditController(save=save_document)
    editing = {'value': False}
    suppress = {'value': False}

    def sync_buttons():
        if editing['value']:
            # 编辑态下「编辑」变成「退出」，未改动也能直接离开编辑（用户 R1864 要求）。
            edit_button.configure(text='退出')
            edit_button.state(['!disabled'])
            back_button.state(['!disabled'] if controller.can_undo else ['disabled'])
            restore_button.state(['!disabled'])
            save_button.state(['!disabled'] if controller.dirty else ['disabled'])
        else:
            # 框里没有文档就没有可编辑的对象：「编辑」直接禁用，不再点了才报错（R2168）。
            edit_button.state(['!disabled'] if active['path'] is not None else ['disabled'])
            back_button.state(['disabled'])
            restore_button.state(['disabled'])
            save_button.state(['disabled'])
            edit_button.configure(text='编辑')
        if delete_button is not None:
            can_delete = not editing['value'] and active['path'] is not None
            delete_button.state(['!disabled'] if can_delete else ['disabled'])

    def toggle_edit():
        if editing['value']:
            exit_edit()
        else:
            begin_edit()

    def exit_edit():
        if controller.dirty and not page.script_page_services.confirm(page.win, '退出编辑', '有未保存的修改，退出将放弃这些修改。确定退出吗？'):
            return
        editing['value'] = False
        suppress['value'] = True
        try:
            box.set_preview(loaded['raw'])
        finally:
            suppress['value'] = False
        sync_buttons()
        page.status.set('已退出' + title + '编辑。')

    def delete_document():
        if editing['value']:
            raise ValueError('请先退出编辑，再删除。')
        if active['path'] is None:
            raise ValueError('当前没有可删除的' + title + '。')
        name = Path(active['path']).name
        if not page.script_page_services.confirm(page.win, '删除' + title, '将「' + name + '」移入项目回收站，确定删除吗？', dangerous=True):
            return
        box.delete_document()

    def begin_edit():
        if not editable or active['path'] is None:
            raise ValueError('当前没有可修改的剧本文档。')
        _reset_preview_text(preview, loaded['raw'], kind)
        preview.edit_modified(False)
        controller.begin_edit(loaded['raw'])
        editing['value'] = True
        sync_buttons()
        preview.focus_set()

    def on_modified(_event=None):
        if suppress['value'] or not editing['value'] or str(preview.cget('state')) != 'normal':
            return
        if not preview.edit_modified():
            return
        preview.edit_modified(False)
        controller.record_edit(preview.get('1.0', 'end-1c'))
        sync_buttons()

    preview.bind('<<Modified>>', on_modified, add=True)

    def back():
        if not editable or active['path'] is None:
            raise ValueError('当前没有可后退的剧本文档。')
        text = controller.undo()
        suppress['value'] = True
        try:
            _reset_preview_text(preview, text, kind)
            preview.edit_modified(False)
        finally:
            suppress['value'] = False
        sync_buttons()
        page.status.set('已后退' + title + '（未保存）：' + Path(active['path']).name)

    def save():
        if not editing['value'] or active['path'] is None:
            raise ValueError('请先点击“编辑”，修改后再保存。')
        before = loaded['raw']
        controller.save_now()
        loaded['raw'] = controller.current
        sync_buttons()
        hint = '；如要据此制作结构剧本，请重新点击“采用选中剧本”。' if kind == 'natural' else ''
        if kind == 'natural':
            _record_natural_edit(page, before, controller.current, Path(active['path']).name)
        page.status.set('已保存' + title + '：' + Path(active['path']).name + hint)

    def restore_deleted():
        if not editing['value']:
            raise ValueError('请先点击“编辑”，再恢复刚删除的文字。')
        try:
            preview.edit_undo()
        except tk.TclError as exc:
            raise ValueError('没有可恢复的删除内容。') from exc

    delete_button = None
    edit_button = SecondaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='编辑', command=lambda: page.safe(toggle_edit))
    edit_button.pack(side='left')
    back_button = SecondaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='后退', command=lambda: page.safe(back))
    back_button.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); back_button.state(['disabled'])
    restore_button = SecondaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='恢复', command=lambda: page.safe(restore_deleted))
    restore_button.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); restore_button.state(['disabled'])
    save_button = SecondaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='保存', command=lambda: page.safe(save))
    save_button.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); save_button.state(['disabled'])
    setattr(page, attribute + '_save_button', save_button)
    if kind == 'structured':
        delete_button = SecondaryButton(controls, width=SCRIPT_EDIT_BUTTON_WIDTH, text='删除', command=lambda: page.safe(delete_document))
        delete_button.pack(side='left', padx=(SPACING["sm"], SPACING["none"]))
        setattr(page, attribute + '_delete_button', delete_button)
    sync_buttons()
    setattr(page, attribute + '_edit_button', edit_button)
    setattr(page, attribute + '_back_button', back_button)
    setattr(page, attribute + '_restore_button', restore_button)
    setattr(page, attribute + '_controller', controller)


@dataclass(frozen=True)
class ScriptPageServices:
    """剧本页的外部 UI 能力；由组合入口提供，不携带全局宿主。"""
    open_path: Callable
    context_menu: Callable
    confirm: Callable


class ScriptPagesMixin:
    """Desktop 的剧本页方法集（见模块说明）。"""
    def refresh_script_chat_for_selected_model(self):
        """阶段配置确认后，立刻切换到已选模型的独立聊天页。"""
        box = getattr(self, 'idea_log', None)
        if box is None or not box.winfo_exists():
            return False
        self._idea_view_model_request=getattr(self,'_idea_view_model_request',0)+1
        self._idea_view_model_cache=(self.root,self.idea_chat_model())
        self.set_idea_model_filter(self.idea_chat_model())
        self.show_conversation()
        self.update_recon_button()
        return True
    def start_script_workflow(self, creative, *, config=None):
        """启动唯一的剧本 Agent 工作流，模型回复前不生成剧本文档。

        发送框不再直连任意文本 API。模型、SKILL 和追问顺序均由 writing 工作流的
        调用设置负责，避免普通聊天提示词绕开鲸剧等 SKILL 的开工门禁。
        """
        import idea_chat
        from workflow_settings import model_name
        model = config['display_model'] if config is not None else model_name(self.root, 'writing')
        from workflow_tasks import script_followup, script_prompt, writing_restart_requested
        from workflow_engines import current_config
        bounded_input = (config or current_config(self.root, 'writing')).get('engine') == 'claude'
        delivery_at = time.time()
        prompt = script_prompt(self.root, None, 'writing', creative_text=creative,
                               agent_delivery=True, delivery_at=delivery_at, bounded_input=bounded_input)
        followup = script_followup(None, 'writing', project=self.root, creative_text=creative,
                                   agent_delivery=True, delivery_at=delivery_at, bounded_input=bounded_input)
        if bounded_input:
            # 不再以全项目文件变化区分两次“确认”；同一轮重试仍复用相同标识。
            turn = '\n本轮请求标识：' + str(delivery_at)
            prompt += turn
            followup += turn
        self.open_flow_agent('writing', '剧本准备', prompt, followup, _config=config,
                             new_session=writing_restart_requested(creative),
                             desktop_paste=True)
        from workflow_settings import skill_prompt
        from writing_quality import enabled
        if enabled(skill_prompt(config or current_config(self.root, 'writing'), inline=True)):
            from workflow_tasks import natural_script_delivery_path
            self.watch_script_quality(natural_script_delivery_path(self.root, delivery_at))
        return model, False
    def show_script_quality(self, result):
        """Keep quality notices visible without misrepresenting a model review as a pass."""
        if not result.get('quality_summary'):
            return
        self._script_quality_report = (str(self.root), result.get('quality_report_path', ''))
        self.status.set(result['quality_summary'])
    def open_script_quality(self):
        """「质检报告」：优先打开本次内存记录的报告，其次按当前剧本定位历史报告，最后退回质检目录。"""
        project, path = getattr(self, '_script_quality_report', ('', ''))
        folder = project_stages.writing(self.root) / 'quality' if self.root else None
        if project == str(self.root) and path and Path(path).is_file():
            self.script_page_services.open_path(path)
            return
        # 内存无记录（如重启后）时，扫描质检目录，把 hash 目录映射回具体剧本，打开最新的报告。
        if folder is not None and folder.is_dir():
            from writing_quality import list_reports
            rows = list_reports(folder)
            if rows and Path(rows[0]['report_path']).is_file():
                self.script_page_services.open_path(rows[0]['report_path'])
                return
            self.script_page_services.open_path(folder)
        else:
            self.notifier.info('本次尚无质检报告。生成自然剧本后会显示四项结果。')
    def watch_script_quality(self, target):
        """Watch only the task's exact output path; never scan historical documents."""
        project = str(self.root)
        ticket = object()
        self._script_quality_watch = ticket
        self._script_quality_pending_project = project
        self._script_quality_result = None
        started = time.monotonic()
        try:
            stat = target.stat()
            baseline = (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            baseline = None
        state = {'signature': baseline, 'changed': started, 'reported': baseline}
        def poll():
            if (getattr(self, '_script_quality_watch', None) is not ticket or str(self.root) != project
                    or time.monotonic() - started > 3600):
                return
            try:
                stat = target.stat()
                signature = (stat.st_mtime_ns, stat.st_size)
                if signature != state['signature']:
                    state.update(signature=signature, changed=time.monotonic())
                elif signature != state['reported'] and time.monotonic() - state['changed'] >= 10:
                    from stage_execution_service import collect_writing_quality
                    from writing_quality import OPEN, CLOSE
                    text = target.read_text(encoding='utf-8')
                    if OPEN not in text or text.rstrip().endswith(CLOSE) or time.monotonic() - state['changed'] >= 30:
                        result = collect_writing_quality(project, target)
                        stat = target.stat()
                        state['reported'] = state['signature'] = (stat.st_mtime_ns, stat.st_size)
                        self.show_script_quality(result)
                        self._script_quality_result = result
                        import idea_chat
                        notice = result['text'] + '\n\n' + result['quality_summary'] + '\n查看质检报告：' + result['quality_report_path']
                        idea_chat.append(self.idea_chat_context(), 'assistant', notice,
                                         gateway=self.idea_chat_gateway())
                        self.show_conversation()
                        refresh = getattr(self, 'refresh_script_list', None)
                        if callable(refresh):refresh()
            except (OSError, UnicodeError, ValueError) as exc:
                # A file may still be being written. Keep the watcher, without resubmitting to a model.
                if target.exists():self.status.set('剧本质检等待完整文件：' + str(exc))
            _safe_after(self.win, 2000, poll)
        _safe_after(self.win, 2000, poll)
    def script_task_active(self):
        """剧本 API 请求或剧本 Agent 是否在运行（排队、启动中都算）。"""
        return bool(getattr(self,'_idea_requesting',False) or
                    getattr(self,'_script_agent_queue',None) or
                    getattr(self,'_script_agent_launching',False) or self.script_agent_processes())
    def update_script_interrupt_button(self):
        """输入框内发送／终止合一按钮的唯一状态入口：运行中显示终止，空闲时跟随底栏「发送」。"""
        from ui_tokens import ICON_SEND, ICON_STOP
        button=getattr(self,'idea_submit',None)
        if button is None or not button.winfo_exists():return
        if self.script_task_active():
            button.configure(text=ICON_STOP,command=lambda:self.safe(self.interrupt_script_agent))
            button.state(['!disabled'])
            return
        send=getattr(self,'idea_send',None)
        button.configure(text=ICON_SEND,command=lambda:send.invoke() if send is not None else None)
        idle=send is not None and send.winfo_exists() and not send.instate(['disabled'])
        button.state(['!disabled'] if idle else ['disabled'])
    def refresh_script_workspace(self):
        """刷新剧本聊天和文件表；旧 Claude 思考块会先清洗，必要时仅重发一次正文请求。"""
        import idea_chat
        import writing_api
        repaired = idea_chat.repair_internal_replies(self.idea_chat_context(), model=self.idea_chat_model(), gateway=self.idea_chat_gateway())
        getattr(self,'_idea_hidden_messages',{}).pop(self.bubble_view_key(self.idea_chat_model()),None)
        from stage_download_inbox_service import overwrite_backup_notice
        backups = []
        imported = self.import_script_downloads(backups)
        notice = ('已从下载文件夹更新' + '、'.join(kind + '「' + path.name + '」' for kind, path in imported) + '；'
                  + overwrite_backup_notice(backups)) if imported else ''
        self.show_conversation()
        refresh = getattr(self, 'refresh_script_list', None)
        if callable(refresh):
            refresh()
        creative = repaired.get('retry_creative') or ''
        request_model = writing_api.capture_request_model(self.root)
        model = request_model['label']
        if not creative:
            self.status.set(notice + '已刷新对话和剧本文件列表。')
            return True
        if not model:
            self.status.set('已移除无法显示的内部内容；请重新发送上一条创意获取正文。')
            return True
        if getattr(self, '_idea_requesting', False):
            self.status.set('模型正在回复；已刷新显示，稍后会自动显示正文。')
            return True
        request_model = writing_api.capture_request(self.root)
        model = request_model['label']
        project = self.root
        token, cancelled = self.idea_chat_controller.begin_request(cancellable=True)
        if getattr(self, 'idea_send', None) is not None:self.idea_send.state(['disabled'])
        self.update_script_interrupt_button();self.show_thinking(model)
        def received(result):
            if not self.idea_chat_controller.finish_request(token):return
            if getattr(self, 'idea_send', None) is not None and self.idea_send.winfo_exists():self.idea_send.state(['!disabled'])
            self.update_script_interrupt_button();self.clear_thinking()
            reply = str(result.get('response_text') or result.get('text') or '').strip()
            if reply:
                idea_chat.append(self.idea_chat_context(), 'assistant', reply, model=model,gateway=self.idea_chat_gateway(),
                                 context_budget=result.get('context_budget'), request_usage=result.get('request_usage'),
                                 skill_injection=request_model['settings']['skill_injection'])
                self.show_conversation()
            self.show_script_quality(result)
            if not result.get('ok'):
                text, log_only = model_error_display(result)
                if log_only:
                    LOGGER.warning('刷新正文模型调用失败（kind=%s）：%s', result.get('kind') or 'missing',
                                   result.get('error'))
                self.notifier.error(text, title='模型调用失败', modal=False)
                self.status.set('刷新正文失败：' + text)
                return
            if not reply:
                self.notifier.error(idea_chat.why_empty(result), title='模型调用失败', modal=False)
                self.status.set(idea_chat.why_empty(result));return
            self.show_conversation()
            saved = self.auto_save_script_reply(model, result)
            self.status.set(result.get('quality_summary') or saved or ('已恢复并刷新 ' + model + ' 的正文。'))
        from stage_execution_service import reply_to_writing
        self.submit_idea_api_request(
            project, token, cancelled,
            lambda: reply_to_writing(project, creative, cancelled=cancelled.is_set,
                                     request_model=request_model),
            received, model + ' 模型正在重新生成正文…')
        return True
    def import_script_downloads(self, backups=None):
        """刷新时收回 Claude Desktop 等窗口已下载到「下载」文件夹的同项目设定／大纲／角色卡／剧本：同类覆盖原文件。"""
        import idea_chat
        from stage_execution_service import import_downloaded_creatives
        selected = self.displayed_chat_model()
        if not selected:return []
        provider, model = idea_chat.storage_identity(selected)
        try:
            from stage_execution_service import collect_download_inbox
            # 先按任务书登记的目标文件名收回，再按剧本准备四段式文件名补收（如跨日重新生成）。
            collected=[('文件', path) for path in collect_download_inbox(self.root, backups=backups)]
            return collected+import_downloaded_creatives(self.idea_chat_context(), provider=provider, model=model,
                                                         backups=backups)
        except (OSError, ValueError) as exc:
            LOGGER.warning('收回下载文件失败：%s', exc)
            return []
    def auto_save_script_reply(self, model, result):
        """API 回复是设定／大纲／角色卡／剧本时自动存进文件表，返回状态栏说明；无需存档时返回空串。

        剧本工作流已自己落盘的（阶段稿、自然剧本原稿）不再重复存。手改过的文件不覆盖，
        另存新版本并在说明里点名。本对话第一份剧本才通知三虎问要不要进分镜，改稿不再问。
        """
        if any(result.get(key) for key in ('preparation_path', 'script_raw_path', 'natural_script_path')):
            return ''
        import idea_chat
        from stage_execution_service import publish_idea_creative
        try:
            saved = idea_chat.auto_save_reply(self.idea_chat_context(), model, publish=publish_idea_creative,
                                              gateway=self.idea_chat_gateway())
        except (OSError, ValueError) as exc:
            return '未自动存档：' + str(exc)
        if saved is None:
            return ''
        refresh = getattr(self, 'refresh_script_list', None)
        if callable(refresh):refresh()
        listener = getattr(self.pet, 'script_downloaded', None)
        if saved.new_script and callable(listener):listener(saved.path)
        if saved.kept is not None:
            return '「' + saved.kept.name + '」与模型回复不一致（可能手改过），未覆盖；新回复另存为「' + saved.path.name + '」'
        return saved.kind + '已自动存档：' + saved.path.name
    def add_script_files(self):
        """「添加剧本」：选本地 txt／md／docx，按正文归入设定／大纲／角色卡／剧本四列，认不出的归剧本。"""
        if self.root is None:
            raise ValueError('请先打开项目，再添加剧本文件。')
        paths = self.file_dialog.open_files(title='选择要添加的剧本文件', parent=self.win,
                                            filetypes=[('文本与 Word', '*.txt *.md *.markdown *.docx')])
        if not paths:
            return []
        import idea_attachments
        import idea_chat
        from stage_execution_service import publish_idea_creative
        added, failed = [], []
        for value in paths:
            path = Path(value)
            try:
                if path.suffix.lower() not in ('.txt', '.md', '.markdown', '.docx'):
                    raise ValueError('只支持 txt、md、docx')
                added.append(idea_chat.import_local_document(self.idea_chat_context(), idea_attachments.read_source(path),
                                                             path.name, publish=publish_idea_creative))
            except (OSError, ValueError) as exc:
                failed.append(path.name + '：' + str(exc))
        refresh = getattr(self, 'refresh_script_list', None)
        if added and callable(refresh):refresh()
        counts = {}
        for file_type, _saved in added:
            label = idea_chat.DOWNLOAD_LABELS.get(file_type, file_type)
            counts[label] = counts.get(label, 0) + 1
        notice = ('已添加 ' + '、'.join(label + ' ' + str(count) + ' 份' for label, count in counts.items())) if added else '没有添加文件'
        self.status.set(notice + ('；未添加 ' + '；'.join(failed) if failed else ''))
        return added
    def pet_script_structure_batch(self, trigger='auto', refresh_page=False):
        """三虎整理剧本：手动与自动入口复用同一条 Writer/Editor + SKILL 异步链。"""
        pet=getattr(self,'pet',None)
        if self.root is None:
            error='当前没有打开项目，无法制作结构剧本'
            if trigger == 'auto' and pet is not None:
                pet._emit('stage.failed',stage='script_structure',error=error)
                return error
            return ''
        if self.worker:
            # 自动链已将本阶段标为 active。后台占用不是业务失败，排队到当前
            # async_ 收尾后通过 pet_start/L3 重新派发；标记是布尔值，连续心跳
            # 不会堆积多次任务。手动入口仍保持原有“暂不能制作”的提示。
            if trigger == 'auto':
                self._auto_structure_retry=True
                return '当前后台任务完成后将自动制作结构剧本'
            return ''
        import script_contract
        source=script_contract.resolve_script_source(self.root)
        if source is None:
            # 自动链已经把 script_structure 标成 active；这里若只静默返回空串，
            # 它就等不到收场事件并永久停在这一步。手动入口在调用前已有提示，
            # 自动入口必须把同一前置条件转成明确的阶段失败，交给三虎阻塞与展示。
            error='未找到剧本准备阶段的剧本，无法制作结构剧本'
            if trigger == 'auto' and pet is not None:
                pet._emit('stage.failed',stage='script_structure',error=error)
            return error
        if pet is None:return ''
        pet._emit('stage.executing',stage='script_structure',trigger=trigger)
        def work():
            try:return ui_plugin_registry.module('stage_exec').run(self,'script_structure',trigger=trigger)
            except Exception as exc:return {'ok':False,'text':str(exc),'errors':[str(exc)]}
        def received(result):
            self._receive_structure_stage_result(pet,result,refresh_page=refresh_page)
        self.async_(work,received,label='三虎正在整理结构化剧本…')
        return ('已自动开始' if trigger == 'auto' else '已开始') + '「剧本结构」：正在整理原稿'
    def _receive_structure_stage_result(self,pet,result,refresh_page=False):
        """处理结构剧本后台任务结果，并保持三虎阶段事件与页面状态一致。"""
        if bool((result or {}).get('ok')):
            # 阶段完成会立刻通知三虎继续下游；必须先把正稿写入初步分镜的选择，
            # 否则全自动的 pet_storyboard_batch 会看到空输入而不派发任务。
            try:
                from storyboard_selection import sync_structured_script
                from script_contract import structured_script_path
                location = structured_script_path(self.root)
                selected = sync_structured_script(self.root)
                if location.resolve() not in {Path(path).resolve() for path in selected}:
                    raise ValueError('结构化剧本未同步到初步分镜输入')
            except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
                error = '结构化剧本已生成，但同步初步分镜失败：' + str(exc)
                pet._emit('stage.failed',stage='script_structure',error=error)
                self.status.set('三虎整理剧本失败：'+error)
                return
            text='结构化剧本已保存：'+location.relative_to(self.root).as_posix()
            self.pet_report('script_structure',text)
            self.status.set('三虎已完成'+text)
            # 手动制作和三虎自动制作共用回调。过去仅手动入口传 refresh_page，
            # 因而用户正停留在“剧本结构”页时，后台已经写入的正稿不会重建目录栏，
            # 看起来像“已有文件没有刷新”。当前页就是本阶段时同样立即重建。
            if refresh_page or getattr(self, 'page_index', None) == PAGE['script_structure']:
                self.show(PAGE['script_structure'])
            return
        error=str((result or {}).get('text') or '; '.join((result or {}).get('errors') or []) or '结构化剧本未生成')
        pet._emit('stage.failed',stage='script_structure',error=error)
        self.status.set('三虎整理剧本失败：'+error)
    def script_structure(self):
        """上看剧本准备原稿、下看结构化正稿；两框独立滚动并可分别编辑保存。"""
        return _ScriptStructurePage(self).build()
    def dialogue_script(self):
        """Export a readable dialogue script with speaker names and timing for dubbing."""
        from stage_execution_service import export_stage_dialogue_script
        result=export_stage_dialogue_script(self.root,self.current_episode(),self.dialogue_assets())
        if not result.ok:raise ValueError(result.reason)
        p,report=result.data
        if not isinstance(report,dict):
            if report:self.status.set('对白时间按镜头时长估算，属草稿，请在剪映中听校。')
        elif report.get('uncalibrated'):
            self.status.set('对白时间暂按句长估算，还有 %d 句未按实际配音校准，请先听校。'%len(report['uncalibrated']))
        return p


class _ScriptStructurePage:
    """剧本结构页（从 ScriptPagesMixin.script_structure 的闭包原样改写成类，R1816）：共享的局部变量成了实例属性，嵌套函数成了方法；原来的 self（桌面主窗）改叫 page。"""
    def __init__(self, page):
        self.page = page

    def build(self):
        import script_contract
        self.script_contract = script_contract
        from script_workspace_service import script_structure_documents
        structure = script_structure_documents(self.page.root)
        source_directory = structure.source_directory
        structure_directory = structure.output_directory
        self.source = structure.source
        target = structure.target
        # 将两份剧本放入同一个等分网格。动作栏与说明文字不参与分配，窗口缩放时
        # 上、下内容框始终各占剩余阅读区域的一半。
        split_area = ttk.Frame(self.page.content)
        split_area.pack(fill='both', expand=True)
        split_area.columnconfigure(0, weight=1)
        split_area.rowconfigure(0, weight=1, uniform='script_structure_preview')
        split_area.rowconfigure(1, weight=1, uniform='script_structure_preview')
        structure_note = '本地规则整理，不调用模型；不切镜头、不改自然语言原稿。'
        from script_preview_service import LOADING_PREVIEW, preview_chunks, read_preview, should_load_async
        self.LOADING_PREVIEW = LOADING_PREVIEW; self.preview_chunks = preview_chunks; self.read_preview = read_preview; self.should_load_async = should_load_async
        self.page.script_structure_source_box = self.content_box(
            split_area,
            '自然剧本（采用：'+self.source.name+'）' if self.source else '自然剧本（待选择采用版本）',
            '自然剧本', structure.source_documents, self.source,
            '尚未找到剧本准备阶段的剧本。请先生成或添加剧本。',
            # 编辑与“采用”无关：采用记录带内容哈希，改过一次就失效，若按采用状态锁编辑，
            # 保存一次后再也点不开（R1958）。下拉框里选中的任一份都可编辑。
            'script_structure_source_preview', editable=True, kind='natural')
        self.page.script_structure_source_box.grid(row=0, column=0, sticky='nsew', pady=(SPACING["xs"], SPACING["none"]))
        self.page.script_structure_output_box = self.content_box(
            split_area,
            '结构剧本', '结构剧本', structure.output_documents, target,
            '尚未生成结构化剧本。点击上方“手动制作结构剧本”，或由三虎全自动模式执行。',
            'script_structure_output_preview', editable=True, kind='structured')
        self.page.script_structure_output_box.grid(row=1, column=0, sticky='nsew')
        actions = FlowBar(split_area); actions.grid(row=2, column=0, sticky='ew', pady=(SPACING["xs"], SPACING["none"]))
        from stage_models import manual_command
        self.manual_command = manual_command
        action_group = ttk.Frame(actions)
        action_group.pack(anchor='center', pady=SPACING["xs"])
        SecondaryButton(action_group, text='采用选中剧本', command=lambda:self.page.safe(self.adopt_source)).pack(
            side='left', padx=(SPACING['none'], SPACING['xs']))
        manual = PrimaryButton(action_group, text='手动制作结构剧本', width=STAGE_ACTION_WIDTH,
                               command=lambda:self.page.safe(self.manual_command(self.page, 'script_structure', self.start_structure, self.page.win)))
        manual.pack(side='left', padx=(SPACING["none"], SPACING["xs"])); self.page.script_structure_manual_button = manual
        ui_plugin_registry.module('stage_flow').follow(manual, 'script_structure')
        self.page.stage_button = ui_plugin_registry.module('skill_panel').stage_button(action_group, self.page, PAGE['script_structure'])
        self.page.stage_button.pack(side='left', padx=(SPACING["sm"], SPACING["xs"]))
        # 流程说明放到页头右上角（header_status 随宽度自动换行，换页时清空），
        # 不再在内容框下方单占一行，把高度让给两块剧本内容（用户 R1862 要求）。
        info = self.page.header_status
        info.configure(text=structure_note)
        self.page.script_structure_info_label = info
        self.page.script_structure_source_directory = source_directory
        self.page.script_structure_output_directory = structure_directory

    def content_box(self, parent, title, file_heading, documents, active_path, empty, attribute, editable=True, kind='natural'):
        return _ContentBox(self, parent, title, file_heading, documents, active_path, empty, attribute, editable, kind).build()

    def start_structure(self):
        if self.script_contract.resolve_script_source(self.page.root) is None:
            raise ValueError('请先选择自然剧本并点击“采用选中剧本”；已采用文件被修改或删除后须重新采用。')
        started = self.page.pet_script_structure_batch(trigger='manual', refresh_page=True)
        if not started:
            raise ValueError('剧本结构正在执行，或三虎自动化暂不可用。')
        self.page.status.set(started)

    def adopt_source(self):
        from stage_execution_service import adopt_natural_script
        selected = self.page.script_structure_source_preview_files.selection()
        if not selected:raise ValueError('请先选择一份自然剧本。')
        adopted = adopt_natural_script(self.page.root, selected[0])
        self.page.status.set('已采用自然剧本：'+adopted.name)
        self.page.show(self.page.page_index)


class _ContentBox:
    """剧本结构页的一个内容框：文档下拉、正文预览（大文本后台读取、分块插入）与编辑／后退／恢复。"""
    _SPEC = ('title', 'file_heading', 'documents', 'active_path', 'empty', 'attribute', 'editable', 'kind')

    def __init__(self, owner, parent, *spec):
        # 参数对象：spec 按 _SPEC 顺序收拢内容框配置，editable／kind 可省略。
        self.owner = owner
        self.parent = parent
        values = dict(zip(self._SPEC, spec))
        values.setdefault('editable', True); values.setdefault('kind', 'natural')
        for name in self._SPEC:
            setattr(self, name, values[name])

    def build(self):
        # 剧本文件选择改为正文上方的横向下拉框，与操作按钮同一行；正文独占整行宽度。
        box = ttk.Frame(self.parent, padding=(SPACING["xs"], SPACING["none"]))
        self.available = tuple(path for path in self.documents if path and path.is_file())
        preview_area = ttk.Frame(box); preview_area.pack(fill='both', expand=True)
        preview_header = ttk.Frame(preview_area)
        preview_header.pack(fill='x')
        # 编辑操作贴着标题行右侧，下拉框占用其余宽度。
        controls = ttk.Frame(preview_header)
        controls.pack(side='right', padx=(SPACING["sm"], SPACING["none"]))
        self.file_list = _DocumentPicker(preview_header, self.available, self.active_path)
        self.file_list.pack(side='left', fill='x', expand=True)
        self.active = {'path': self.active_path if self.active_path in self.available else (self.available[0] if self.available else None)}
        text_area = ttk.Frame(preview_area); text_area.pack(fill='both', expand=True)
        self.preview, self.horizontal = _build_script_preview(text_area)
        self.preview_ticket = {'value': 0}
        self.loaded = {'raw': ''}
        self.load_preview(self.active['path'])
        self.file_list.bind('<<ComboboxSelected>>', self.select_document)
        self.file_list.bind('<Button-3>', self.open_document_menu)
        _install_script_edit_controls(self.owner.page, controls, self)
        setattr(self.owner.page, self.attribute, self.preview)
        setattr(self.owner.page, self.attribute + '_files', self.file_list)
        return box

    def set_preview(self, value, ticket=None):
        """小文本立即显示；大文本在 Tk 空闲时分块插入，避免一次性重排。"""
        self.loaded['raw'] = str(value or '')
        shown = script_view_style.compact_display(self.loaded['raw'])
        styled = script_view_style.should_style(shown)
        _set_script_wrap(self.preview, self.horizontal, styled)
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.configure(state='disabled')
        chunks = iter(self.owner.preview_chunks(shown))
        def append_chunk():
            if ticket is not None and ticket != self.preview_ticket['value']:
                return
            try:
                chunk = next(chunks)
            except StopIteration:
                try:
                    self.preview.configure(state='normal')
                    if styled:
                        script_view_style.apply_tags(self.preview, shown, self.kind)
                    # 初始预览不能成为“恢复删除”的一条历史记录；只恢复用户本次编辑中的动作。
                    self.preview.edit_reset()
                    self.preview.configure(state='disabled')
                except tk.TclError:
                    pass
                return
            try:
                self.preview.configure(state='normal')
                self.preview.insert('end', chunk)
                self.preview.configure(state='disabled')
                self.owner.page.win.after_idle(append_chunk)
            except tk.TclError:
                pass
        if ticket is None:
            _reset_preview_text(self.preview, shown, self.kind)
            self.preview.configure(state='disabled')
        else:
            _safe_after_idle(self.owner.page.win, append_chunk)

    def load_preview(self, path):
        """大文本在后台读取；选中项变化或进入编辑态时丢弃旧结果。"""
        self.preview_ticket['value'] += 1
        ticket = self.preview_ticket['value']
        if not self.owner.should_load_async(path):
            self.set_preview(self.owner.read_preview(path, self.empty))
            return
        self.set_preview(self.owner.LOADING_PREVIEW)
        expected = Path(path) if path else None
        # 不使用 self.async_：后者代表独占的业务工作，会错误地禁用用户操作。
        # 预览读取独立排队，结果只由 Tk 主线程的 after 回写。
        preview_results = queue.Queue(maxsize=1)
        threading.Thread(
            target=lambda: preview_results.put((ticket, expected, self.owner.read_preview(expected, self.empty))),
            daemon=True,
        ).start()
        def await_preview():
            try:
                result_ticket, result_path, value = preview_results.get_nowait()
            except queue.Empty:
                try:
                    self.owner.page.win.after(50, await_preview)
                except tk.TclError:
                    pass
                return
            if (result_ticket != self.preview_ticket['value'] or self.active['path'] != result_path or
                    str(self.preview.cget('state')) != 'disabled'):
                return
            try:
                if self.preview.winfo_exists():
                    self.set_preview(value, ticket=ticket)
            except tk.TclError:
                pass
        _safe_after(self.owner.page.win, 20, await_preview)

    def select_document(self, _event=None):
        selected = self.file_list.selection()
        if not selected or not self.available:
            return
        if str(self.preview.cget('state')) == 'normal':
            self.file_list.selection_set(str(self.active['path']))
            self.owner.page.status.set('请先保存或完成当前修改，再切换剧本。')
            return
        chosen = Path(selected[0])
        if chosen == self.active['path']:
            return
        self.active['path'] = chosen
        self.load_preview(chosen)

    def delete_document(self):
        """目录右键删除只移入项目回收站；来源稿删除后刷新会隐藏关联结构稿。"""
        selected = self.file_list.selection()
        from script_workspace_service import selected_workspace_document
        destination = selected_workspace_document(self.available, selected[0] if selected else None)
        from storage_maintenance import recycle_paths
        records = recycle_paths(self.owner.page.root, [destination], '删除' + self.title)
        if not records:
            raise ValueError('未能安全移入项目回收站，原文件未删除。')
        self.owner.page.show(PAGE['script_structure'])
        self.owner.page.status.set('已将' + destination.name + '移入回收站；关联的结构剧本已按来源刷新。')

    def open_document_menu(self, event):
        if not self.available:
            return None
        menu = self.owner.page.script_page_services.context_menu(self.file_list).command('删除（移入回收站）', lambda:self.owner.page.safe(self.delete_document))
        self.owner.page._script_structure_file_menu = menu
        return menu.popup(event)
