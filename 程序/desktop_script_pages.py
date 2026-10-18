"""剧本结构页与剧本相关方法。

``ScriptPagesMixin`` 通过实例的 ``script_page_services`` 使用文件打开与菜单服务。
Desktop 在组合入口注入服务；独立页面测试不需要初始化 Desktop 或登记全局宿主。
"""
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
from ui_tokens import COLORS, SCRIPT_VIEW_FONT, SCRIPT_VIEW_PADDING, SPACING, TEXT_DESC
from ui_widgets import DataTable, PrimaryButton, SecondaryButton, TextArea
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


@dataclass(frozen=True)
class ScriptPageServices:
    """剧本页的外部 UI 能力；由组合入口提供，不携带全局宿主。"""
    open_path: Callable
    context_menu: Callable


class ScriptPagesMixin:
    """Desktop 的剧本页方法集（见模块说明）。"""
    def refresh_script_chat_for_selected_model(self):
        """阶段配置确认后，立刻切换到已选模型的独立聊天页。"""
        box = getattr(self, 'idea_log', None)
        if box is None or not box.winfo_exists():
            return False
        if getattr(self,'_bubble_edit',None):self.finish_bubble_edit()
        self._idea_view_model_request=getattr(self,'_idea_view_model_request',0)+1
        self._idea_view_model_cache=(self.root,self.idea_chat_model())
        self.show_conversation()
        self.update_script_download_button()
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
    def open_script_quality(self, folder=False):
        project, path = getattr(self, '_script_quality_report', ('', ''))
        if project == str(self.root) and path and Path(path).is_file():
            self.script_page_services.open_path(Path(path).parent if folder else path)
        elif folder and (project_stages.writing(self.root) / 'quality').is_dir():
            self.script_page_services.open_path(project_stages.writing(self.root) / 'quality')
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
    def update_script_interrupt_button(self):
        """按剧本 API 请求或剧本 Agent 的运行状态更新中断按钮。"""
        button=getattr(self,'idea_interrupt',None)
        if button is None or not button.winfo_exists():return
        active=(getattr(self,'_idea_requesting',False) or
                bool(getattr(self,'_script_agent_queue',None)) or
                getattr(self,'_script_agent_launching',False) or bool(self.script_agent_processes()))
        button.state(['!disabled'] if active else ['disabled'])
    def refresh_script_workspace(self):
        """刷新剧本聊天和文件表；旧 Claude 思考块会先清洗，必要时仅重发一次正文请求。"""
        import idea_chat
        import writing_api
        repaired = idea_chat.repair_internal_replies(self.idea_chat_context(), model=self.idea_chat_model(), gateway=self.idea_chat_gateway())
        getattr(self,'_idea_hidden_messages',{}).pop(self.bubble_view_key(self.idea_chat_model()),None)
        imported = self.import_script_downloads()
        notice = ('已从下载文件夹更新' + '、'.join(kind + '「' + path.name + '」' for kind, path in imported) + '；') if imported else ''
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
            self.show_conversation();self.update_script_download_button()
            self.status.set(result.get('quality_summary') or ('已恢复并刷新 ' + model + ' 的正文；完整剧本可下载保存。'))
        from stage_execution_service import reply_to_writing
        self.submit_idea_api_request(
            project, token, cancelled,
            lambda: reply_to_writing(project, creative, cancelled=cancelled.is_set,
                                     request_model=request_model),
            received, model + ' 模型正在重新生成正文…')
        return True
    def import_script_downloads(self):
        """刷新时收回 Claude Desktop 等窗口已下载到「下载」文件夹的同项目设定／大纲／角色卡／剧本：同类覆盖原文件。"""
        import idea_chat
        from stage_execution_service import import_downloaded_creatives
        selected = self.displayed_chat_model()
        if not selected:return []
        provider, model = idea_chat.storage_identity(selected)
        try:
            from stage_execution_service import collect_download_inbox
            # 先按任务书登记的目标文件名收回，再按剧本准备四段式文件名补收（如跨日重新生成）。
            collected=[('文件', path) for path in collect_download_inbox(self.root)]
            return collected+import_downloaded_creatives(self.idea_chat_context(), provider=provider, model=model)
        except (OSError, ValueError) as exc:
            LOGGER.warning('收回下载文件失败：%s', exc)
            return []
    def update_script_download_button(self):
        """按当前模型输出的类型启用下载（设定／大纲／角色卡／剧本），按钮文字随之变化；首次回复绝不弹完成框。"""
        import idea_chat
        button=getattr(self,'idea_download',None)
        if button is None or not button.winfo_exists():return False
        kind='' if getattr(self,'_idea_requesting',False) else idea_chat.download_kind(
            idea_chat.latest_text(self.idea_chat_context(),model=self.displayed_chat_model(),gateway=self.idea_chat_gateway()))
        button.configure(text='下载'+(kind or '文件'))
        button.state(['!disabled'] if kind else ['disabled'])
        return bool(kind)
    def download_script(self):
        """下载当前模型输出（设定／大纲／角色卡／剧本）；只有剧本下载后才通知三虎询问是否进入分镜。"""
        import idea_chat
        selected_model = self.displayed_chat_model()
        reply=idea_chat.latest_text(self.idea_chat_context(),model=selected_model,gateway=self.idea_chat_gateway())
        kind=idea_chat.download_kind(reply)
        if not kind:raise ValueError('请先让模型生成完整剧本（或设定、大纲、角色卡），再下载。')
        provider, model = idea_chat.storage_identity(selected_model)
        from stage_execution_service import publish_idea_creative
        saved=idea_chat.save_reply(self.idea_chat_context(),reply,provider=provider,model=model,
                                   publish=publish_idea_creative)
        self.brief_editor=(saved,getattr(self,'idea_log',None))
        self.close_dialog()
        refresh=getattr(self,'refresh_script_list',None)
        if callable(refresh):refresh()
        self.status.set(kind+'已下载：'+saved.name)
        listener=getattr(self.pet,'script_downloaded',None)
        if kind=='剧本' and callable(listener):listener(saved)
        self.update_script_download_button()
        return saved
    def confirm_script(self):
        """兼容旧入口：保存动作改为用户显式下载。"""
        return self.download_script()
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
        import script_contract
        from script_workspace_service import script_structure_documents
        structure = script_structure_documents(self.root)
        source_directory = structure.source_directory
        structure_directory = structure.output_directory
        source = structure.source
        target = structure.target
        # 将两份剧本放入同一个等分网格。动作栏与说明文字不参与分配，窗口缩放时
        # 上、下内容框始终各占剩余阅读区域的一半。
        split_area = ttk.Frame(self.content)
        split_area.pack(fill='both', expand=True)
        split_area.columnconfigure(0, weight=1)
        split_area.rowconfigure(0, weight=1, uniform='script_structure_preview')
        split_area.rowconfigure(2, weight=1, uniform='script_structure_preview')
        structure_note = ('剧本整理：本地规则提取人物、场景、道具、事件、冲突、台词与分场要素，再由规则校验完整性和一致性后输出结构剧本（未调用模型）；'
                          '不切镜头、不生成分镜 JSON，也不会改动自然语言原稿。')
        from script_preview_service import LOADING_PREVIEW, preview_chunks, read_preview, should_load_async
        def content_box(parent, title, file_heading, documents, active_path, empty, attribute,
                        editable=True, kind='natural'):
            # 文件栏与正文同一行：左列只管选择／确认剧本文件，右列专心阅读和编辑正文。
            # 不再把这份文件清单重复放到页面底部。
            box = ttk.Frame(parent, padding=SPACING["sm"])
            # 可拖动的横向分隔条：自然／结构剧本目录列与正文列都可按阅读需要调宽。
            body = ttk.Panedwindow(box, orient='horizontal'); body.pack(fill='both', expand=True)
            files = ttk.Frame(body)
            # 高度交给外层上下等分网格。这里若声明 12 行，会成为 Tk 的刚性
            # 最小请求高度，窄窗口先撑满上框、把下方结构剧本挤出可视区。
            file_table = DataTable(files, columns=[('script', file_heading, 170)], show='headings',
                                   height=1, selectmode='browse', auto_hide_scrollbars=True)
            file_list = file_table.tree
            # 文件栏仅用于选择；正文是本页的主要阅读区。原来的 260px 在窄窗口
            # 抢走过多空间，缩为约三分之二并允许随窗口继续收缩。
            file_list.column('script', anchor='w', width=170, minwidth=105, stretch=True)
            file_table.pack(fill='both', expand=True)
            available = tuple(path for path in documents if path and path.is_file())
            active = {'path': active_path if active_path in available else (available[0] if available else None)}
            if available:
                for path in available:
                    file_list.insert('', 'end', iid=str(path), values=(path.name,))
                file_list.selection_set(str(active['path']))
            else:
                file_list.insert('', 'end', values=('尚无可用文件',))
            preview_area = ttk.Frame(body)
            preview_header = ttk.Frame(preview_area)
            preview_header.pack(fill='x', pady=(SPACING["none"], SPACING["xs"]))
            ttk.Label(preview_header, text='剧本内容', style='Muted.TLabel').pack(side='left')
            # 编辑操作贴着正文标题的右侧，不再占用内容框上方的一整行。
            controls = ttk.Frame(preview_header)
            controls.pack(side='right')
            text_area = ttk.Frame(preview_area); text_area.pack(fill='both', expand=True)
            preview, horizontal = _build_script_preview(text_area)
            body.add(files, weight=1)
            body.add(preview_area, weight=4)
            preview_ticket = {'value': 0}
            def set_preview(value, ticket=None):
                """小文本立即显示；大文本在 Tk 空闲时分块插入，避免一次性重排。"""
                styled = script_view_style.should_style(value)
                _set_script_wrap(preview, horizontal, styled)
                preview.configure(state='normal')
                preview.delete('1.0', 'end')
                preview.configure(state='disabled')
                chunks = iter(preview_chunks(value))
                def append_chunk():
                    if ticket is not None and ticket != preview_ticket['value']:
                        return
                    try:
                        chunk = next(chunks)
                    except StopIteration:
                        try:
                            preview.configure(state='normal')
                            if styled:
                                script_view_style.apply_tags(preview, value, kind)
                            # 初始预览不能成为“恢复删除”的一条历史记录；只恢复用户本次编辑中的动作。
                            preview.edit_reset()
                            preview.configure(state='disabled')
                        except tk.TclError:
                            pass
                        return
                    try:
                        preview.configure(state='normal')
                        preview.insert('end', chunk)
                        preview.configure(state='disabled')
                        self.win.after_idle(append_chunk)
                    except tk.TclError:
                        pass
                if ticket is None:
                    preview.configure(state='normal')
                    preview.insert('end', value)
                    if styled:
                        script_view_style.apply_tags(preview, value, kind)
                    preview.edit_reset()
                    preview.configure(state='disabled')
                else:
                    _safe_after_idle(self.win, append_chunk)
            def load_preview(path):
                """大文本在后台读取；选中项变化或进入编辑态时丢弃旧结果。"""
                preview_ticket['value'] += 1
                ticket = preview_ticket['value']
                if not should_load_async(path):
                    set_preview(read_preview(path, empty))
                    return
                set_preview(LOADING_PREVIEW)
                expected = Path(path) if path else None
                # 不使用 self.async_：后者代表独占的业务工作，会错误地禁用用户操作。
                # 预览读取独立排队，结果只由 Tk 主线程的 after 回写。
                preview_results = queue.Queue(maxsize=1)
                threading.Thread(
                    target=lambda: preview_results.put((ticket, expected, read_preview(expected, empty))),
                    daemon=True,
                ).start()
                def await_preview():
                    try:
                        result_ticket, result_path, value = preview_results.get_nowait()
                    except queue.Empty:
                        try:
                            self.win.after(50, await_preview)
                        except tk.TclError:
                            pass
                        return
                    if (result_ticket != preview_ticket['value'] or active['path'] != result_path or
                            str(preview.cget('state')) != 'disabled'):
                        return
                    try:
                        if preview.winfo_exists():
                            set_preview(value, ticket=ticket)
                    except tk.TclError:
                        pass
                _safe_after(self.win, 20, await_preview)
            load_preview(active['path'])
            def select_document(_event=None):
                selected = file_list.selection()
                if not selected or not available:
                    return
                if str(preview.cget('state')) == 'normal':
                    file_list.selection_set(str(active['path']))
                    self.status.set('请先保存或完成当前修改，再切换剧本。')
                    return
                chosen = Path(selected[0])
                if chosen == active['path']:
                    return
                active['path'] = chosen
                load_preview(chosen)
            file_list.bind('<<TreeviewSelect>>', select_document)
            def delete_document():
                """目录右键删除只移入项目回收站；来源稿删除后刷新会隐藏关联结构稿。"""
                selected = file_list.selection()
                from script_workspace_service import selected_workspace_document
                destination = selected_workspace_document(available, selected[0] if selected else None)
                from storage_maintenance import recycle_paths
                records = recycle_paths(self.root, [destination], '删除' + title)
                if not records:
                    raise ValueError('未能安全移入项目回收站，原文件未删除。')
                self.show(PAGE['script_structure'])
                self.status.set('已将' + destination.name + '移入回收站；关联的结构剧本已按来源刷新。')
            def open_document_menu(event):
                row = file_list.identify_row(event.y)
                if not row or row not in {str(path) for path in available}:
                    return None
                file_list.selection_set(row)
                menu = self.script_page_services.context_menu(file_list).command('删除（移入回收站）', lambda:self.safe(delete_document))
                self._script_structure_file_menu = menu
                return menu.popup(event)
            file_list.bind('<Button-3>', open_document_menu)
            def begin_edit():
                if not editable or active['path'] is None:
                    raise ValueError('当前没有可修改的剧本文档。')
                preview.configure(state='normal')
                edit.state(['disabled']); restore.state(['!disabled']); save.state(['!disabled'])
                preview.focus_set()
            def save_edit():
                if not editable or active['path'] is None:
                    raise ValueError('当前没有可保存的剧本文档。')
                value = preview.get('1.0', 'end-1c').strip()
                if not value:
                    raise ValueError('剧本内容不能为空。')
                destination = Path(active['path'])
                from script_contract import save_natural_script
                save_natural_script(destination, value)
                preview.configure(state='disabled')
                edit.state(['!disabled']); restore.state(['disabled']); save.state(['disabled'])
                self.status.set('已保存'+title+'：'+destination.name)
                if destination == source:
                    self.status.set('已保存剧本准备阶段剧本；如需更新下方结构化剧本，请重新执行“手动制作结构剧本”。')
            def restore_deleted():
                if str(preview.cget('state')) == 'disabled':
                    raise ValueError('请先点击“修改内容”，再恢复刚删除的文字。')
                try:
                    preview.edit_undo()
                except tk.TclError as exc:
                    raise ValueError('没有可恢复的删除内容。') from exc
            edit = SecondaryButton(controls, text='修改内容', command=lambda:self.safe(begin_edit))
            edit.pack(side='left')
            restore = SecondaryButton(controls, text='恢复删除', command=lambda:self.safe(restore_deleted))
            restore.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); restore.state(['disabled'])
            save = PrimaryButton(controls, text='保存修改', command=lambda:self.safe(save_edit))
            save.pack(side='left', padx=(SPACING["sm"], SPACING["none"])); save.state(['disabled'])
            setattr(self, attribute, preview)
            setattr(self, attribute + '_edit_button', edit)
            setattr(self, attribute + '_restore_button', restore)
            setattr(self, attribute + '_save_button', save)
            setattr(self, attribute + '_files', file_list)
            return box
        self.script_structure_source_box = content_box(
            split_area,
            '自然剧本（采用：'+source.name+'）' if source else '自然剧本（待选择采用版本）',
            '自然剧本目录（01剧本准备）', structure.source_documents, source,
            '尚未找到剧本准备阶段的剧本。请先生成、下载或导入剧本。',
            'script_structure_source_preview', editable=source is not None, kind='natural')
        self.script_structure_source_box.grid(row=0, column=0, sticky='nsew', pady=(SPACING["xs"], SPACING["none"]))
        actions = FlowBar(split_area); actions.grid(row=1, column=0, sticky='ew', pady=(SPACING["sm"], SPACING["xs"]))
        def start_structure():
            if script_contract.resolve_script_source(self.root) is None:
                raise ValueError('请先选择自然剧本并点击“采用选中剧本”；已采用文件被修改或删除后须重新采用。')
            started = self.pet_script_structure_batch(trigger='manual', refresh_page=True)
            if not started:
                raise ValueError('剧本结构正在执行，或三虎自动化暂不可用。')
            self.status.set(started)
        from stage_models import manual_command
        action_group = ttk.Frame(actions)
        action_group.pack(anchor='center', pady=SPACING["xs"])
        def adopt_source():
            from stage_execution_service import adopt_natural_script
            selected = self.script_structure_source_preview_files.selection()
            if not selected:raise ValueError('请先选择一份自然剧本。')
            adopted = adopt_natural_script(self.root, selected[0])
            self.status.set('已采用自然剧本：'+adopted.name)
            self.show(self.page_index)
        SecondaryButton(action_group, text='采用选中剧本', command=lambda:self.safe(adopt_source)).pack(
            side='left', padx=(SPACING['none'], SPACING['xs']))
        manual = PrimaryButton(action_group, text='手动制作结构剧本', width=STAGE_ACTION_WIDTH,
                               command=lambda:self.safe(manual_command(self, 'script_structure', start_structure, self.win)))
        manual.pack(side='left', padx=(SPACING["none"], SPACING["xs"])); self.script_structure_manual_button = manual
        ui_plugin_registry.module('stage_flow').follow(manual, 'script_structure')
        self.stage_button = ui_plugin_registry.module('skill_panel').stage_button(action_group, self, PAGE['script_structure'])
        self.stage_button.pack(side='left', padx=(SPACING["sm"], SPACING["xs"]))
        self.script_structure_output_box = content_box(
            split_area,
            '结构剧本', '结构剧本目录（02剧本结构）', structure.output_documents, target,
            '尚未生成结构化剧本。点击上方“手动制作结构剧本”，或由三虎全自动模式执行。',
            'script_structure_output_preview', editable=True, kind='structured')
        self.script_structure_output_box.grid(row=2, column=0, sticky='nsew', pady=(SPACING["none"], SPACING["none"]))
        # 流程说明留在两块内容之后的右下角，避免占用顶部阅读空间。
        info = ttk.Label(self.content, text=structure_note, style='Muted.TLabel', justify='right',
                         wraplength=TEXT_DESC['wraplength'])
        info.pack(anchor='e', pady=(SPACING["xs"], SPACING["none"]))
        self.script_structure_info_label = info
        self.script_structure_source_directory = source_directory
        self.script_structure_output_directory = structure_directory
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
