"""剧本结构页与剧本相关方法。

``ScriptPagesMixin`` 通过实例的 ``script_page_services`` 使用文件打开与菜单服务。
Desktop 在组合入口注入服务；独立页面测试不需要初始化 Desktop 或登记全局宿主。
"""
import infra.pet_state as pet_state
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable
import contract.project_stages as project_stages
import ui.script_view_style as script_view_style
import tkinter as tk
import infra.ui_plugin_registry as ui_plugin_registry
from ui.desktop_idea_chat import model_error_display
from pathlib import Path
from tkinter import ttk
from ui.script_find_bar import FindBar
from ui.script_line_numbers import LineNumberGutter
from ui.script_outline import OutlinePanel
from ui.script_reading import ReadingAids
from ui_tokens import (
    BUTTON_WIDTH_EDIT,
    COLORS,
    SCRIPT_VIEW_FONT,
    SCRIPT_VIEW_PADDING,
    SCROLLBAR_WIDTH,
    SPACING,
)
from ui_widgets import SecondaryButton, TextArea, Tooltip, ask_string
from ui.desktop_script_edit_session import (
    _install_script_edit_controls,
    _reset_preview_text,
)

PAGE = pet_state.PAGE_OF

LOGGER = logging.getLogger('desktop_script_pages')

# R1973 契约：编辑按钮宽度恒取令牌；REQ-S02-37 撤掉编辑按钮后常量保留，
# test_button_consistency 仍按同名导入核对。
SCRIPT_EDIT_BUTTON_WIDTH = BUTTON_WIDTH_EDIT
SCRIPT_EDITOR_WHEEL_LINES = 8
_HINT_READ_EDITABLE = '快捷键：右键编辑 / 打开其他文件 · Ctrl+F 查找 · Ctrl+G 跳转 · Ctrl+滚轮 / Ctrl+± 缩放 · Ctrl+O 打开文件'
_HINT_READ_ONLY = '只读查看：Ctrl+F 查找 · Ctrl+G 跳转 · Ctrl+滚轮 / Ctrl+± 缩放 · Ctrl+O 打开其他文件（自然/结构剧本/分镜/文本）'
_HINT_EDITING = '编辑中（自动保存）：Ctrl+S 立即保存 · Ctrl+Z 撤销 · Ctrl+Y 重做 · Ctrl+F 查找 · Ctrl+G 跳转 · 右键退出编辑'


def _format_storyboard_json(data):
    """把分镜 JSON 格式化为易读文本，方便在编辑器中顺畅阅览。"""
    shots = data.get('shots') if isinstance(data, dict) else None
    if not isinstance(shots, list):
        return json.dumps(data, ensure_ascii=False, indent=2)
    lines = ['# %s %s' % (data.get('episode_id') or '分镜', data.get('title') or '')]
    meta = []
    if data.get('duration') is not None:
        meta.append('总时长：%s 秒' % data.get('duration'))
    if data.get('source_script'):
        meta.append('来源剧本：%s' % data.get('source_script'))
    if meta:
        lines.append('｜'.join(meta))
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        lines.append('')
        lines.append('## %s｜%s（%ss）' % (
            shot.get('id') or 'SH?', shot.get('title') or '未命名镜头',
            shot.get('duration') if shot.get('duration') is not None else '?'))
        chars = '、'.join(str(c) for c in (shot.get('characters') or ()) if c)
        loc = str(shot.get('location') or '')
        if chars or loc:
            lines.append('- 角色：%s｜场景：%s' % (chars or '无', loc or '未注'))
        if shot.get('dialogue'):
            lines.append('- 对白：%s' % shot.get('dialogue'))
        if shot.get('frame_prompt'):
            lines.append('- 首帧提示词：%s' % shot.get('frame_prompt'))
        if shot.get('video_prompt'):
            lines.append('- 视频提示词：%s' % shot.get('video_prompt'))
    return '\n'.join(lines)


def _read_any_document(path, empty, default_reader):
    """兼容自然剧本、结构剧本、初步分镜/分镜定稿 JSON、docx 与常见编码文本文件。"""
    source = Path(path) if path else None
    if source is None or not source.is_file():
        return empty
    suffix = source.suffix.lower()
    if suffix == '.docx':
        try:
            import domain.idea_attachments as idea_attachments
            return idea_attachments.read_source(source)
        except (OSError, ValueError):
            pass
    if suffix == '.json':
        try:
            from infra.file_cache import read_json
            return _format_storyboard_json(read_json(source))
        except (OSError, UnicodeError, ValueError):
            pass
    text = default_reader(source, empty)
    from domain.script_preview_service import READ_ERROR
    if text != READ_ERROR:
        return text
    for encoding in ('gb18030', 'utf-16', 'latin-1'):
        try:
            return source.read_text(encoding=encoding)
        except (OSError, UnicodeError):
            continue
    return text


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
    """剧本正文文本框、左侧行号槽与两条滚动条；返回 (文本框, 横向滚动条, 行号槽)。"""
    preview = TextArea(text_area, bg=COLORS["background_card"], fg=COLORS["text_primary"], height=1,
                       wrap='word', undo=True, maxundo=-1, font=SCRIPT_VIEW_FONT, relief='flat',
                       padx=SCRIPT_VIEW_PADDING[0], pady=SCRIPT_VIEW_PADDING[1])
    preview._wheel_lines = SCRIPT_EDITOR_WHEEL_LINES
    gutter = LineNumberGutter(text_area, preview)
    scroll = ttk.Scrollbar(text_area, orient='vertical', command=preview.yview)
    # 大文件保留全文，以横向滚动浏览长行；小文件由 set_preview 改为按词换行。
    horizontal = ttk.Scrollbar(text_area, orient='horizontal', command=preview.xview)

    def sync_scroll(first, last):
        scroll.set(first, last)
        gutter.refresh()

    preview.configure(yscrollcommand=sync_scroll, xscrollcommand=horizontal.set)
    gutter.grid(row=0, column=0, sticky='ns')
    preview.grid(row=0, column=1, sticky='nsew')
    scroll.grid(row=0, column=2, sticky='ns')
    horizontal.grid(row=1, column=1, sticky='ew')
    text_area.columnconfigure(1, weight=1); text_area.rowconfigure(0, weight=1)
    return preview, horizontal, gutter


def _document_role(structure, path):
    """REQ-S02-38：判定文档角色——自然剧本／结构剧本可编辑，其余文档只读。

    ``structure`` 是 ``script_structure_documents()`` 的返回；路径按解析后比较，
    空值与解析失败都返回 None（只读）。
    """
    if not path:
        return None
    try:
        target = Path(path).resolve()
    except (OSError, ValueError):
        return None

    def resolved(items):
        for item in items or ():
            try:
                yield Path(item).resolve()
            except (OSError, ValueError):
                continue

    if target in resolved(getattr(structure, 'source_documents', ())):
        return 'natural'
    if target in resolved(getattr(structure, 'output_documents', ())):
        return 'structured'
    return None


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
        import domain.idea_chat as idea_chat
        from orchestrator.workflow_settings import model_name
        model = config['display_model'] if config is not None else model_name(self.root, 'writing')
        from orchestrator.workflow_tasks import script_followup, script_prompt, writing_restart_requested
        from orchestrator.workflow_engines import current_config
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
        from orchestrator.workflow_settings import skill_prompt
        from domain.writing_quality import enabled
        if enabled(skill_prompt(config or current_config(self.root, 'writing'), inline=True)):
            from orchestrator.workflow_tasks import natural_script_delivery_path
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
            from domain.writing_quality import list_reports
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
                    from domain.writing_quality import OPEN, CLOSE
                    text = target.read_text(encoding='utf-8')
                    if OPEN not in text or text.rstrip().endswith(CLOSE) or time.monotonic() - state['changed'] >= 30:
                        result = collect_writing_quality(project, target)
                        stat = target.stat()
                        state['reported'] = state['signature'] = signature
                        self.show_script_quality(result)
                        self._script_quality_result = result
                        import domain.idea_chat as idea_chat
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
        """共享输入框发送键的唯一状态入口：运行中显示终止，空闲时按简报必填置灰（REQ-S01-62/86）。"""
        shared = getattr(self, 'shared_input', None)
        stage = getattr(shared, 'stage', None)
        if isinstance(stage, str) and stage and stage != 'script':
            return
        from ui_tokens import ICON_SEND, ICON_STOP
        button = getattr(shared, 'send_button', None)
        if button is None or not button.winfo_exists():
            return
        if self.script_task_active():
            shared._send_interrupt = True
            button.configure(text=ICON_STOP, command=lambda: self.safe(self.interrupt_script_agent))
            button.state(['!disabled'])
            return
        shared._send_interrupt = False
        button.configure(text=ICON_SEND, command=lambda: self.safe(shared.send))
        try:
            missing = self._idea_live_missing()
        except Exception:
            missing = ()
        # REQ-S02-41（SEND-2）：本阶段正在执行时发送键同样置灰，只动可用态不动图标。
        running = False
        try:
            running = ui_plugin_registry.module('stage_flow').running(getattr(shared, 'stage', ''))
        except Exception:
            running = False
        button.state(['disabled'] if (missing or running) else ['!disabled'])
    def refresh_script_workspace(self):
        """刷新剧本聊天和文件表；旧 Claude 思考块会先清洗，必要时仅重发一次正文请求。"""
        import domain.idea_chat as idea_chat
        import writing_api
        repaired = idea_chat.repair_internal_replies(self.idea_chat_context(), model=self.idea_chat_model(), gateway=self.idea_chat_gateway())
        getattr(self,'_idea_hidden_messages',{}).pop(self.bubble_view_key(self.idea_chat_model()),None)
        from orchestrator.stage_download_inbox_service import overwrite_backup_notice
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
        import domain.idea_chat as idea_chat
        from stage_execution_service import import_downloaded_creatives
        selected = self.displayed_chat_model()
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
        import domain.idea_chat as idea_chat
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
        import domain.idea_attachments as idea_attachments
        import domain.idea_chat as idea_chat
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
        import contract.script_contract as script_contract
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
        return (('已自动开始' if trigger == 'auto' else '已开始')
                + '「剧本结构」：正在整理原稿「' + source.name + '」')
    def _receive_structure_stage_result(self,pet,result,refresh_page=False):
        """处理结构剧本后台任务结果，并保持三虎阶段事件与页面状态一致。"""
        if bool((result or {}).get('ok')):
            # 阶段完成会立刻通知三虎继续下游；必须先把正稿写入初步分镜的选择，
            # 否则全自动的 pet_storyboard_batch 会看到空输入而不派发任务。
            try:
                from orchestrator.storyboard_selection import sync_structured_script
                from contract.script_contract import structured_script_path
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

    _FLOW_NOTE = '本地规则整理，不调用模型；不切镜头、不改自然语言原稿。'

    def build(self):
        import contract.script_contract as script_contract
        self.script_contract = script_contract
        from domain.script_workspace_service import script_structure_documents
        structure = script_structure_documents(self.page.root)
        self.source = structure.source
        self.page.script_structure_page = self
        def run_send():
            """底部发送键承载「手动制作结构剧本」入口（REQ-S02-37 撤掉页面按钮后入口并入这里）：已配置 API 模型时直连按 SKILL 输出结构剧本，否则退回本地规则整理（无弹窗）。"""
            sender = getattr(self.page, 'send_stage_file', None)
            if callable(sender) and sender('script_structure', ''):
                return True
            return self.page.safe(self.start_structure)
        # REQ-S02-37：页面上只留一个编辑器，占满整块内容区（REQ-S02-44：外框与底部
        # 共享输入框同左同右——pack fill='both' 与页内其他整宽区块同一口径）。
        editor_frame = ttk.Frame(self.page.content)
        editor_frame.pack(fill='both', expand=True, pady=(SPACING["xs"], SPACING["none"]))
        self.page.script_structure_editor_box = editor_frame
        self._register_send_action(editor_frame, run_send)
        from domain.script_preview_service import LOADING_PREVIEW, preview_chunks, read_preview, should_load_async
        self.LOADING_PREVIEW = LOADING_PREVIEW; self.preview_chunks = preview_chunks; self.read_preview = read_preview; self.should_load_async = should_load_async
        default = self._default_document(structure)
        self.editor_box = self.content_box(
            editor_frame, '剧本文档', '', (), default,
            '尚未找到剧本准备阶段的剧本。请先在“剧本准备”生成或添加剧本，或在右侧文件面板点选要查看的文档。',
            'script_structure_editor_preview')
        self.editor_box.build().pack(fill='both', expand=True)
        # R3016 P2：说明文字放统一底栏左区段；REQ-S02-37 起段内写当前文件名与采用状态，
        # 原流程说明挪到悬停。
        self._update_status_note(default)
        info = self.page.set_status_segment('script_note', self._note_text, tooltip=self._FLOW_NOTE)
        self.page.script_structure_info_label = info
        self.page.script_structure_source_directory = structure.source_directory
        self.page.script_structure_output_directory = structure.output_directory
        # REQ-S01-102＋REQ-S02-38：登记面板点选回调；default 行的 iid 为项目相对路径。
        panel = getattr(self.page, 'files_panel', None)
        register = getattr(panel, 'set_select_handler', None)
        if callable(register):
            register(self.page.page_index, self.show_document,
                     default=self._default_iid(default))

    def content_box(self, parent, title, file_heading, documents, active_path, empty, attribute, editable=True, kind='natural'):
        """REQ-S02-37：登记的建框入口签名保留；title／file_heading／documents／editable／kind 随单编辑器不再消费，只建唯一 `_ContentBox`。"""
        return _ContentBox(self, parent, empty, attribute, active_path)

    def _register_send_action(self, frame, action):
        """底部发送键在本页承载同一个制作入口；编辑器外框随页面销毁时撤销，不留过期的入口。

        宿主没有共享输入框（独立页面测试的假宿主）时跳过。
        """
        shared = getattr(self.page, 'shared_input', None)
        register = getattr(shared, 'set_stage_action', None)
        if not callable(register):
            return
        register('script_structure', action)

        def release(_event=None):
            if shared.stage_action('script_structure') is action:
                register('script_structure', None)
        frame.bind('<Destroy>', release, add='+')

    def _default_iid(self, path):
        """面板预选行的 iid＝项目相对路径；不在项目内或没有默认文档时为 None。"""
        if path is None or self.page.root is None:
            return None
        try:
            return Path(path).resolve().relative_to(Path(self.page.root).resolve()).as_posix()
        except (OSError, ValueError):
            return None

    def _default_document(self, structure):
        """REQ-S02-38：默认显示采用的自然剧本对应的结构剧本；没有则退回采用的自然剧本。"""
        source = structure.source
        if source is None:
            return None
        try:
            label = self.script_contract._source_label(self.page.root, source)
        except (OSError, ValueError):
            label = None
        if label is not None:
            for candidate in structure.output_documents:
                identity = self.script_contract._structured_source_identity(
                    self.page.root, candidate)
                if identity == ('source', (label,)):
                    return candidate
        return source

    def document_role(self, path):
        """REQ-S02-38：角色判定每次现查文档集，新建删除的文档也算数。"""
        from domain.script_workspace_service import script_structure_documents
        try:
            return _document_role(script_structure_documents(self.page.root), path)
        except (OSError, ValueError):
            return None

    def show_document(self, path):
        """REQ-S01-102→REQ-S02-38：右侧文件面板点选的文件进唯一编辑器。"""
        box = getattr(self, 'editor_box', None)
        if box is not None:
            box.select_document(path)

    def _is_adopted(self, path):
        try:
            source = self.script_contract.resolve_script_source(self.page.root)
        except (OSError, ValueError):
            source = None
        if source is None or path is None:
            return False
        try:
            return Path(source).resolve() == Path(path).resolve()
        except (OSError, ValueError):
            return False

    def _update_status_note(self, path):
        """REQ-S02-37：状态栏段写当前文件名＋角色／采用状态；流程说明在悬停。"""
        if path is None:
            self._note_text = '尚未找到剧本准备阶段的剧本'
        else:
            role = self.document_role(path)
            if role == 'natural':
                tag = '自然剧本' + ('（采用）' if self._is_adopted(path) else '')
            elif role == 'structured':
                tag = '结构剧本'
            else:
                text_path = str(path)
                if '分镜定稿' in text_path:
                    tag = '分镜定稿（只读）'
                elif '初步分镜' in text_path or '分镜拆分' in text_path or '分镜文档' in text_path:
                    tag = '初步分镜（只读）'
                else:
                    tag = '只读'
            self._note_text = '当前：%s｜%s' % (Path(path).name, tag)
        info = getattr(self.page, 'script_structure_info_label', None)
        if info is not None and info.winfo_exists():
            self.page.set_status_segment('script_note', self._note_text,
                                         tooltip=self._FLOW_NOTE)

    def start_structure(self):
        if self.script_contract.resolve_script_source(self.page.root) is None:
            raise ValueError('请先采用一份自然剧本再制作结构剧本；已采用文件被修改或删除后须重新采用。')
        started = self.page.pet_script_structure_batch(trigger='manual', refresh_page=True)
        if not started:
            raise ValueError('剧本结构正在执行，或三虎自动化暂不可用。')
        self.page.status.set(started)


class _ContentBox:
    """REQ-S02-37：剧本结构页的唯一内容框——正文预览（大文本后台读取、分块插入）与编辑会话。

    ``kind``／``editable``／``title`` 不再建框时定死，随当前文件由 ``_sync_role``
    重定；文档选择由 ``select_document(path)`` 接收面板回调传入的路径。
    """

    def __init__(self, owner, parent, empty, attribute, active_path):
        self.owner = owner
        self.parent = parent
        self.empty = empty
        self.attribute = attribute
        self.active_path = active_path
        self.kind = 'natural'
        self.editable = False
        self.title = '剧本文档'

    def build(self):
        # REQ-S02-37：页头一行（分区字样、文档下拉框、大纲/编辑/删除按钮列）全部去掉，
        # 正文独占内容框；左右不留内边距，与底部共享输入框的外框同左同右。
        box = ttk.Frame(self.parent)
        self.frame = box
        self.shortcut_hint = ttk.Label(
            box, text=_HINT_READ_EDITABLE, style='SidebarProjectMuted.TLabel', anchor='w')
        self.shortcut_hint.pack(side='bottom', fill='x', pady=(SPACING['xs'] // 2, SPACING['none']))
        preview_area = ttk.Frame(box); preview_area.pack(fill='both', expand=True)
        # 网格两行：查找条（默认隐藏）／正文行。大纲栏放到正文左侧，
        # 行号槽仍贴在正文左缘；右半区不再放目录。
        preview_area.columnconfigure(1, weight=1)
        preview_area.rowconfigure(1, weight=1)
        self.active = {'path': self.active_path}
        text_area = ttk.Frame(preview_area)
        text_area.grid(row=1, column=1, sticky='nsew')
        self.preview, self.horizontal, self.gutter = _build_script_preview(text_area)
        self.close_button = SecondaryButton(
            text_area, text='×', width=0, style='Tokens.Secondary.TButton', takefocus=True,
            command=lambda: self.owner.page.safe(self.close_document))
        Tooltip(self.close_button, '关闭当前文件（项目文件保留）')
        for sequence in ('<Return>', '<space>'):
            self.close_button.bind(sequence, lambda _e: (self.close_button.invoke(), 'break')[1], add='+')
        self.preview_ticket = {'value': 0}
        self.loaded = {'raw': ''}
        self.zoom_delta = 0
        # ReadingAids 的“大纲”开合钮已随页头一起移除；保留一个不上屏的占位控件，
        # script_reading 里对它的 configure 调用才不会 AttributeError；font 守住
        # ui/ 样式 Label 登记值（L4-F9，desktop_script_pages.py: 1）。
        self.outline_toggle = ttk.Label(preview_area, font=SCRIPT_VIEW_FONT)
        self.aids = ReadingAids(self)
        # L4 边界：输入弹窗由本模块注入，script_reading 不新增 ui_widgets 同层边。
        self.aids.goto_ask = ask_string
        self.find_bar = FindBar(
            preview_area, self.preview,
            on_changed=self.aids.refresh_reading_views,
            notify=lambda message: self.owner.page.status.set(message),
            run=self.owner.page.safe,
            headings=self.aids.heading_lines,
            reveal=self.aids.ensure_line_visible,
        )
        self.find_bar.grid(row=0, column=1, sticky='ew')
        self.find_bar.grid_remove()
        self.outline = OutlinePanel(preview_area, self.preview)
        self.outline.grid(row=0, column=0, rowspan=2, sticky='ns')
        self.outline.grid_remove()
        # REQ-S02-40：行号槽折叠标记数据源与点击回调。
        self.gutter.set_fold_support(self.aids.fold_marks, self.aids.toggle_fold)
        # 必须先于 load_preview 挂上：首屏小文档走 _reset_preview_text，靠它收尾同步三件套。
        self.preview._reading_sync = self.aids.after_text_load
        self._sync_role(self.active['path'])
        self.load_preview(self.active['path'])
        _install_script_edit_controls(self.owner.page, self)
        # REQ-S02-39：会话以 add=True 登记的老菜单整体替换为 ReadingAids 全菜单。
        self.preview.bind('<Button-3>', self.aids.context_menu)
        box.bind('<Destroy>', lambda _e: self.aids.release(), add='+')
        self.preview.bind('<<Modified>>', self.aids.schedule_reading_views, add='+')
        self.preview.bind('<FocusIn>', lambda _e: self.update_shortcut_hint(), add='+')
        self.aids.install_reading_shortcuts()
        shortcuts = getattr(self.owner.page, 'shortcuts', None)
        if shortcuts is not None:
            shortcuts.bind(self.preview, ('<Control-o>', '<Control-O>'),
                           lambda _e: (self.owner.page.safe(self.open_any_document), 'break')[1],
                           scope='剧本结构·' + self.attribute, name='打开其他文件')
        self.update_shortcut_hint()
        setattr(self.owner.page, self.attribute, self.preview)
        setattr(self.owner.page, self.attribute + '_content_box', self)
        return box

    def _set_close_visible(self, visible):
        """关闭×只在有当前文件时浮在正文右上角；不挤压正文布局。"""
        button = getattr(self, 'close_button', None)
        if button is None:
            return
        if visible:
            button.place(relx=1.0, x=-(SCROLLBAR_WIDTH + SPACING['xs']),
                         y=SPACING['xs'], anchor='ne')
            button.lift()
        else:
            button.place_forget()

    def close_document(self):
        """关闭当前显示的文件视图；文件本身保留，保存失败时不丢编辑现场。"""
        if self.active['path'] is None:
            return False
        session = getattr(self, 'edit_session', None)
        if session is not None and session.editing:
            try:
                session.exit_edit()
            except (OSError, ValueError) as exc:
                self.owner.page.status.set('保存失败，未关闭' + self.title + '：' + str(exc))
                return False
        self.active['path'] = None
        self._sync_role(None)
        self.load_preview(None)
        if self.find_bar.visible:
            self.find_bar.hide()
        self.owner.page.status.set('已关闭当前文档；项目文件保留')
        return True

    def update_shortcut_hint(self, editing=None):
        """根据当前是否处于编辑态及是否可编辑，实时提示可用快捷键。"""
        label = getattr(self, 'shortcut_hint', None)
        if label is None:
            return
        if editing is None:
            session = getattr(self, 'edit_session', None)
            editing = bool(session and session.editing)
        if editing:
            text = _HINT_EDITING
        elif self.editable and self.active.get('path') is not None:
            text = _HINT_READ_EDITABLE
        else:
            text = _HINT_READ_ONLY
        try:
            label.configure(text=text)
        except tk.TclError:
            pass

    def open_any_document(self):
        """打开自然剧本、结构剧本、初步分镜、分镜定稿或任意文本格式文件。"""
        dialog = getattr(self.owner.page, 'file_dialog', None)
        if dialog is None or not hasattr(dialog, 'open_file'):
            return
        initial = str(self.owner.page.root) if getattr(self.owner.page, 'root', None) else None
        chosen = dialog.open_file(
            parent=getattr(self.owner.page, 'win', None),
            title='在编辑器中打开文档',
            initialdir=initial,
            filetypes=[
                ('剧本／分镜／文本', '*.md *.txt *.json *.docx *.srt *.ass *.csv *.yaml *.yml'),
                ('全部文件', '*.*'),
            ],
        )
        if chosen:
            self.select_document(chosen)

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
                    self.aids.after_text_load()
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
            self.set_preview(_read_any_document(path, self.empty, self.owner.read_preview))
            return
        self.set_preview(self.owner.LOADING_PREVIEW)
        expected = Path(path) if path else None
        # 不使用 self.async_：后者代表独占的业务工作，会错误地禁用用户操作。
        # 预览读取独立排队，结果只由 Tk 主线程的 after 回写。
        preview_results = queue.Queue(maxsize=1)
        threading.Thread(
            target=lambda: preview_results.put(
                (ticket, expected, _read_any_document(expected, self.empty, self.owner.read_preview))),
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

    def _sync_role(self, path):
        """REQ-S02-38：kind／editable／title 跟随当前文件，并通知会话与状态栏。

        自然／结构剧本可编辑；其余文档只读，正文按 structured 的 Markdown
        样式展示（``script_view_style.spans`` 的自然剧本样式是逐行台词向，
        不适合通用文本文档）。
        """
        role = self.owner.document_role(path)
        self.kind = role or 'structured'
        self.editable = role is not None
        self.title = {'natural': '自然剧本', 'structured': '结构剧本'}.get(role, '文档')
        session = getattr(self, 'edit_session', None)
        if session is not None:
            session.kind = self.kind
            session.editable = self.editable
            session.title = self.title
        self._set_close_visible(path is not None)
        self.owner._update_status_note(path)
        self.update_shortcut_hint()

    def select_document(self, path):
        """REQ-S02-38：显示面板点选的文档；编辑态先退出并落盘，落盘失败留在原文档。"""
        if not path:
            return
        try:
            chosen = Path(path).resolve()
        except (OSError, ValueError):
            return
        if chosen == self.active['path']:
            return
        session = getattr(self, 'edit_session', None)
        if session is not None:
            # 编辑态切换先退出编辑：exit_edit 内含自动保存 flush，落盘失败则留在原文档。
            try:
                session.exit_edit()
            except (OSError, ValueError) as exc:
                self.owner.page.status.set('保存失败，未切换' + self.title + '：' + str(exc))
                return
        self.active['path'] = chosen
        self._sync_role(chosen)
        self.load_preview(chosen)
