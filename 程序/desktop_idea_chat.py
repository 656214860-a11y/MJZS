"""创意对话（剧本准备页的气泡对话）与 Agent 派发的桌面方法集。

从 ``desktop.Desktop`` 原样迁出（R1490 拆分步骤 2）：方法体未改，``self`` 语义不变，``Desktop`` 通过
继承 ``IdeaChatMixin`` 获得。内容包括气泡的显示／折叠／复制／编辑、创意附件、语义简报、
``send_message``／``submit_idea_api_request`` 与 ``open_flow_agent`` 等。仍与 Tk 控件和 ``self`` 状态
紧耦合，所以和 ``desktop`` 同属 L4；纯决策部分已在 L3 ``idea_chat_controller``。依赖被测试按
``desktop.<名字>`` 打补丁的方法（confirm／ContextMenu／open_path 等）留在 ``desktop`` 里。
"""
import hashlib
import json
import logging
import queue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import pet_state
import ui_plugin_registry
from desktop_idea_deferred import IdeaDeferredMixin
from desktop_storyboard_direct import run_storyboard_direct as _run_storyboard_direct
from idea_chat_controller import (bubble_timestamp, collapse_preview, has_interruptible, interrupt_notice,
                                  queue_notice, slot_decision)
from platform_tools import open_target
from ui_tokens import CHAR_WIDTH, TEXT_ROWS, COLORS, FONTS, SPACING
from ui_widgets import FormDialog, TextArea
from desktop_idea_bubbles import (BUBBLE_BACK, BUBBLE_FLOOR, BUBBLE_FONT, BUBBLE_GAP, BUBBLE_LINE, BUBBLE_MAX_RATIO,
                                  BUBBLE_PAD, BUBBLE_SLACK, IdeaBubblesMixin)

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
PAGE = pet_state.PAGE_OF

def script_raw_saved_notice(formal_path=''):
    """剧本原稿发布后的三虎提示。"""
    name = Path(formal_path).name if formal_path else 'script_raw.md'
    return '剧本已自动保存：' + name


def model_error_display(result, default='未收到模型回复'):
    """按 kind 把模型调用失败翻成用户可见文案：返回 (文案, 是否只写日志不进弹窗)。

    鉴权／预算／请求本身（client）是用户可自行处理或与本次请求相关的提示，沿用原始
    error；网络／服务端只在界面给统一的重试提示，原始 error 写日志；编程错误（bug）
    与旧记录缺失 kind 时统一给内部错误提示，原文同样只写日志。
    """
    payload = result if isinstance(result, dict) else {}
    raw = str(payload.get('error') or default)
    kind = str(payload.get('kind') or '')
    if kind in ('auth', 'budget', 'client'):
        return raw, False
    if kind in ('network', 'server'):
        return '模型暂时无法响应，请稍后重试', True
    return '系统内部错误，已记录日志', True


# 第 37 期第 2 条：创意栏那七个字段的名字只写一份（预置示例与灰色字段名都取它）。
# 第 71 期任务 4：跟着新的预置示例换成这一组名字，灰色字段名认的还是同一份。
IDEA_FIELDS=('故事集数','单集时间','故事画风','故事主体','故事梗概','故事题材','故事角色','物理特征','故事分集','特殊要求','内容补充')
# 第 69 期任务 1：剧本准备页的创意框改成一段对话；第 72 期任务 9／10：全部消息靠左、
# 紧凑显示，模型名置顶，长消息可折叠，模型回复中显示思考提示。
# 最下面留一段给您写字，DRAFT_MARK 就是「从这儿往下才是您写的」那条线。
DRAFT_MARK='draft'
DRAFT_HINT='─'*18+' 写您的想法，按「发送」 '


class IdeaChatMixin(IdeaDeferredMixin, IdeaBubblesMixin):
    """Desktop 的创意对话与 Agent 派发方法集（见模块说明）。"""
    # 这些兼容属性保留既有桌面控件与测试的访问方式；状态归属在无 Tk 控制器。
    @property
    def _idea_requesting(self):
        controller = getattr(self, 'idea_chat_controller', None)
        if controller is None:
            return self.__dict__.get('_idea_requesting_fallback', False)
        return controller.requesting
    @_idea_requesting.setter
    def _idea_requesting(self, value):
        controller = getattr(self, 'idea_chat_controller', None)
        if controller is None:
            self.__dict__['_idea_requesting_fallback'] = bool(value)
            return
        controller.requesting = bool(value)
    @property
    def _script_agent_launching(self):
        return self.idea_chat_controller.script_agent_launching
    @_script_agent_launching.setter
    def _script_agent_launching(self, value):
        self.idea_chat_controller.script_agent_launching = bool(value)
    @property
    def _idea_cancel_event(self):
        return self.idea_chat_controller.cancel_event
    @_idea_cancel_event.setter
    def _idea_cancel_event(self, value):
        self.idea_chat_controller.cancel_event = value
    @property
    def idea_attachment_paths(self):
        return self.idea_chat_controller.attachment_paths
    @idea_attachment_paths.setter
    def idea_attachment_paths(self, paths):
        self.idea_chat_controller.replace_attachments(paths)
    def idea_chat_gateway(self):
        """L4 通过 L3 取得创意聊天的受控读写入口。"""
        from stage_execution_service import idea_chat_gateway
        return idea_chat_gateway()
    def idea_chat_context(self):
        """L4 只从 L3 取得创意聊天所需的项目上下文。"""
        from stage_execution_service import project_context
        return project_context(self.root)
    def idea_draft_range(self):
        """固定在聊天区底部的发送框；聊天记录不混入待发送文字。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return '1.0','end-1c'
        return '1.0','end-1c'
    def preserve_idea_draft(self):
        """翻页重建前把尚未发送的创意留在本次运行内，不写入项目文件。"""
        if not self.root:return
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return
        drafts=getattr(self,'_idea_drafts',None)
        if drafts is None:self._idea_drafts=drafts={}
        key=str(Path(self.root).resolve())
        value=self.draft_text()
        if value:drafts[key]=value
        else:drafts.pop(key,None)
    def restore_idea_draft(self):
        """回到剧本准备页时恢复当前项目尚未发送的输入。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists() or not self.root:return
        value=getattr(self,'_idea_drafts',{}).get(str(Path(self.root).resolve()),'')
        if value:
            box.delete('1.0','end');box.insert('1.0',value)
    def discard_idea_draft(self):
        """内容真正送出后，清除对应的内存草稿。"""
        if self.root:getattr(self,'_idea_drafts',{}).pop(str(Path(self.root).resolve()),None)
    def update_idea_attachment_status(self):
        """仅展示用户已选择的文件名；路径和正文不出现在界面或聊天记录。"""
        label=getattr(self,'idea_attachment_status',None)
        prepared=getattr(self.idea_chat_controller,'attachment_details',())
        from idea_attachments import display_name
        tips,details,local={},[],'原文件，将由 Agent 自行读取'
        def note(shown,key,tip):
            tips[key]=tip;details.append('%s（%s）' % (shown,tip))
        for name,count in prepared:
            key=display_name(name);note(key if count is None else name,key,local if count is None else '%d 字' % count)
        if not tips:
            import idea_attachments
            from stage_execution_service import idea_attachment_local_mode
            local_mode=idea_attachment_local_mode(self.root)
            for value in getattr(self,'idea_attachment_paths',()):
                key=display_name(value)
                if local_mode:note(key,key,local);continue
                try:count=len(idea_attachments.read_source(Path(value)))
                except (OSError, ValueError):continue
                note(Path(value).name,key,'%d 字' % count)
        self._idea_attachment_tips=tips
        # 明细不再单独占一行：本轮引用改由附件卡片主色边框表示，字数放在卡片悬停提示里。
        if label is not None:label.set(('已引用：'+'、'.join(details)) if details else '')
        self.refresh_uploaded_idea_attachments()
    def refresh_uploaded_idea_attachments(self):
        """输入框内的附件卡片：上传库全部列出，本轮会带上的卡片用主色边框高亮。"""
        panel=getattr(self,'idea_uploaded_panel',None)
        if panel is None or not panel.winfo_exists():return
        from stage_execution_service import stage_idea_attachment_paths
        from idea_attachments import archive_pair, display_name
        from ui_tokens import ICON_CLOSE, ICON_DOCUMENT
        from ui_widgets import Tooltip
        # 原件创建时间代表入库顺序，不让转换稿后续编辑改变显示顺序。
        def upload_order(path):
            original,_converted=archive_pair(path)
            archived=original if original.is_file() else path
            return archived.stat().st_ctime_ns,path.name
        def key(path):
            try:return str(Path(path).resolve())
            except OSError:return str(path)
        paths=sorted(stage_idea_attachment_paths(self.root),key=upload_order)
        referenced={key(path) for path in getattr(self,'idea_attachment_paths',())}
        known={key(path) for path in paths}
        # 引用了但不在上传库里的文件也要有一张卡片，避免本轮附件在界面上“消失”。
        paths+=[Path(path) for path in getattr(self,'idea_attachment_paths',()) if key(path) not in known]
        for child in panel.winfo_children():child.destroy()
        tips=getattr(self,'_idea_attachment_tips',{})
        for path in paths:
            name=display_name(path)
            selected=key(path) in referenced
            # 内边距必须给控件本身：ttk.Frame 摆子控件不看样式里的 padding，写在样式上时文件名与图标
            # 贴着外沿，白底把圆角边框盖断（选中时主色框尤其明显）。
            chip=ttk.Frame(panel,style='Tokens.Chip.Selected.TFrame' if selected else 'Tokens.Chip.TFrame',
                           padding=(SPACING['sm'],SPACING['xs']))
            icon=ttk.Label(chip,text=ICON_DOCUMENT,style='Composer.Chip.Icon.TLabel')
            icon.pack(side='left')
            limit=CHAR_WIDTH['3xl']
            title=ttk.Label(chip,text=name if len(name)<=limit else name[:limit-1]+'…',style='Composer.TLabel')
            close=ttk.Label(chip,text=ICON_CLOSE,style='Composer.Chip.Close.TLabel',cursor='hand2')
            # 右侧按 × 的实际宽度留位：× 用 place 贴在右上角，不参与卡片的请求宽度，否则会压住文件名末尾。
            title.pack(side='left',padx=(SPACING['xs'],close.winfo_reqwidth()+SPACING['xs']))
            # place 从内边距里侧量起：抵掉卡片内边距，× 仍贴卡片外沿右上角。
            close.place(relx=1.0,x=SPACING['sm'],y=-SPACING['xs'],anchor='ne')
            chip.attachment_path,chip.close_button=path,close
            tip=name+('（%s）' % tips[name] if name in tips else '')
            tip+='\n本轮会一起发送' if selected else '\n单击打开；点 × 删除'
            for widget in (chip,icon,title):
                widget.bind('<Button-1>',lambda event,item=path:self.safe(lambda:self.open_uploaded_idea_attachment(item)) or 'break')
                Tooltip(widget,tip)
            close.bind('<Button-1>',lambda event,item=path:self.safe(lambda:self.delete_uploaded_idea_attachment(item)) or 'break')
            for sequence,flag in (('<Enter>','active'),('<Leave>','!active')):close.bind(sequence,lambda event,flag=flag:event.widget.state([flag]),add='+')
            Tooltip(close,'删除附件')
        if not paths:return panel.pack_forget()
        if not panel.winfo_manager():panel.pack(side='left',fill='x',expand=True,padx=(SPACING['xs'],SPACING['xs']))
        panel.schedule()
    def choose_idea_attachments(self):
        """选择创意附档；分模式准入、归档和解析均在后台进行。"""
        paths=self.file_dialog.open_files(
            title='选择要提交给模型的创意附档', parent=self.win,
            filetypes=[('文本、Office 与 PDF', '*.txt *.md *.markdown *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.pdf *.json *.csv *.yaml *.yml *.log'),
                       ('所有文件', '*.*')])
        if not paths:return ()
        self.idea_chat_controller.start_attachment_preparation(self.root, paths)
        if getattr(self,'idea_send',None) is not None:
            self.idea_send.state(['disabled'])
            self.update_script_interrupt_button()
        self.status.set('正在后台入库和校验 %d 份创意文件…' % len(paths))
        return ()
    def poll_idea_attachment_preparation(self):
        """仅在 Tk 主线程更新附件状态；后台线程绝不触碰控件。"""
        self.poll_idea_semantic_brief()
        result=self.idea_chat_controller.poll_attachment_preparation()
        if result is None:return
        if (getattr(self,'idea_send',None) is not None and self.idea_send.winfo_exists()
                and not self.idea_chat_controller.requesting):
            self.idea_send.state(['!disabled'])
            self.update_script_interrupt_button()
        if not result['ok']:
            self.status.set('创意文件未入库：'+str(result['value']))
            return
        prepared=result['value']
        self.update_idea_attachment_status()
        self.status.set('已入库 %d 份创意文件；发送时读取附档，下方发送框可补充创作信息。' % len(prepared['names']))
    def insert_idea_reference(self, path):
        """把已入库创意插入编辑框，并标记为本轮显式引用。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return
        value=str(Path(path))
        self.idea_chat_controller.add_attachment(value)
        box.insert('insert','@'+Path(path).name)
        self.update_idea_attachment_status()
    def idea_chat_model(self):
        """当前剧本阶段的模型标识；它也是独立聊天页的持久化分区键。"""
        if not self.root:
            return ''
        import writing_api
        direct = writing_api.model_label(self.root)
        if direct:
            return direct
        from workflow_settings import model_name
        return model_name(self.root, 'writing')
    def show_conversation(self):
        """重绘只读聊天记录；长记录按空闲批次插入，不阻塞剧本页首帧。"""
        import idea_chat
        box=getattr(self,'idea_log',None)
        if box is None or not box.winfo_exists():return
        self._idea_view_generation=getattr(self,'_idea_view_generation',0)+1
        generation=self._idea_view_generation
        previous_jobs=getattr(self,'_idea_view_after_jobs',())
        for job in previous_jobs:
            try:box.after_cancel(job)
            except tk.TclError:pass
        jobs=[]
        self._idea_view_after_jobs=jobs
        def alive():
            try:return (generation==getattr(self,'_idea_view_generation',0)
                       and box.winfo_exists() and box is getattr(self,'idea_log',None))
            except tk.TclError:return False
        def cancel_view_jobs(event=None):
            if event is not None and getattr(event,'widget',None) is not box:
                return None
            for job in tuple(jobs):
                try:box.after_cancel(job)
                except tk.TclError:pass
            jobs.clear()
            return None
        box.bind('<Destroy>',cancel_view_jobs,add='+')
        def later(delay, callback):
            if not alive():return None
            try:job=box.after(delay,callback)
            except tk.TclError:return None
            jobs.append(job)
            return job
        def idle(callback):
            if not alive():return None
            try:job=box.after_idle(callback)
            except tk.TclError:return None
            jobs.append(job)
            return job
        root=self.root
        cached=getattr(self,'_idea_view_model_cache',None)
        resolving_model=False
        if root and (not isinstance(cached,tuple) or cached[0]!=root):
            requested=getattr(self,'_idea_view_model_request',0)+1
            self._idea_view_model_request=requested
            resolved=queue.Queue(maxsize=1)
            def resolve_model():
                try:resolved.put(self.idea_chat_model())
                except Exception:resolved.put('')
            def resume():
                try:model=resolved.get_nowait()
                except queue.Empty:
                    later(50,resume)
                    return
                if (not self.shutting_down and requested==getattr(self,'_idea_view_model_request',0)
                        and self.root==root):
                    self._idea_view_model_cache=(root,model)
                    self.show_conversation()
            threading.Thread(target=resolve_model,daemon=True).start()
            later(50,resume)
            # 模型键只用于读取真实历史；软件示例和空会话壳不依赖它，先交还
            # 可见内容。键回来后 resume 按现有页面代次完整重绘真实历史。
            resolving_model=True
        model=cached[1] if root and isinstance(cached,tuple) else ''
        from stage_execution_service import project_context
        rows=idea_chat.load(project_context(root),model=model,gateway=self.idea_chat_gateway()) if root and not resolving_model else []
        if root and not resolving_model:self.__dict__.setdefault('_idea_history_known',{})[root]=bool(rows)
        hidden=getattr(self,'_idea_hidden_messages',{}).get(self.bubble_view_key(model))
        remaining=hidden.copy() if hidden is not None else {}
        visible=[]
        for index,row in enumerate(rows):
            signature=json.dumps({k:v for k,v in row.items() if k!='context_compacted'},sort_keys=True,ensure_ascii=False)
            if remaining.get(signature,0):
                remaining[signature]-=1
            else:
                visible.append((index,row))
        box.configure(state='normal')
        self._bubble_rows=[];self._bubble_full={};self._bubble_width=int(box.winfo_width() or 0)
        for name in [one for one in box.tag_names() if one.startswith('bubble_')]:
            box.tag_delete(name)
        box.delete('1.0','end')
        def finish():
            if not alive():return
            usage_label = getattr(self, 'idea_usage_label', None)
            if usage_label is not None and usage_label.winfo_exists():
                usage_label.set_text(idea_chat.usage_compact(rows))
                tip = getattr(self, 'idea_usage_tip', None)
                if tip is not None:tip.text = idea_chat.usage_summary(rows)
            session_label = getattr(self, 'idea_session_label', None)
            if session_label is not None and session_label.winfo_exists():
                from writing_api import chat_session_lines
                visible, detail = chat_session_lines(self.root, model) if self.root else ('', '')
                session_label.set_text(visible)
                tip = getattr(self, 'idea_session_tip', None)
                if tip is not None:tip.text = detail
            self.drop_thinking_spinner()
            thinking=getattr(self,'_thinking_model','')
            if thinking and self.bubble_view_key(thinking) == self.bubble_view_key(self.displayed_chat_model()):
                self.add_thinking_line(box,thinking)
            if rows:
                try:box.see('end')
                except tk.TclError:pass
            # 一次空闲合并量测；逐条 add_bubble 不再触发布局往返。
            idle(lambda: alive() and self._fit_content_now())
        if visible:
            cursor=[0]
            def append_batch():
                if not alive():return
                end=min(cursor[0]+8,len(visible))
                while cursor[0]<end:
                    index,row=visible[cursor[0]]
                    self.add_bubble(box,row,index);cursor[0]+=1
                if cursor[0]<len(visible):
                    # 递归 after_idle 会被一次 update() 连续清空；真实项目的
                    # 历史消息因此仍会堵住首帧。短时延让输入区先处理事件。
                    later(12,append_batch)
                else:finish()
            idle(append_batch)
        else:
            if hidden is None:self.show_example_bubble(loading=resolving_model and self.idea_history_expected())  # R1949：没读到≠没有，有记录就留读取提示等 resume
            finish()
        # 保持 normal 才能让 Tk 的原生鼠标拖选建立 ``sel`` 标签；只读由
        # guard_bubble_edit_key 控制，避免 disabled 状态吞掉拖选事件。
        box.configure(state='normal')
    def _idea_semantic_key(self, value):
        return (str(self.root), value, tuple(self.idea_attachment_paths))
    def start_idea_semantic_brief(self, value, prepared):
        """提取不是阶段开工：未齐全前不生成剧本，也不保存完成简报。"""
        from stage_execution_service import prepare_idea_semantic_brief, idea_attachment_local_mode
        import writing_api
        key = self._idea_semantic_key(value)
        if getattr(self, '_idea_semantic_resolved', None) == key:
            return False
        pending = getattr(self, '_idea_semantic_pending', None)
        if pending and pending['key'] == key:
            self.status.set('Agent 正在读取附档并提取创作信息，请稍候。')
            return True
        request = prepare_idea_semantic_brief(self.root, value, prepared['attachments'])
        local = idea_attachment_local_mode(self.root)
        pending = {'key': key, 'request': request, 'started': time.monotonic(),
                   'local': local, 'next_poll': 0}
        self._idea_semantic_pending = pending
        try:
            if local:
                self.open_flow_agent('writing', '简报信息提取', request['prompt'], request['prompt'], intake_only=True, desktop_paste=True)
            else:
                project = self.root
                def extract():
                    try:return {'values': writing_api.extract_idea_brief(project, request)}
                    except (ValueError, OSError) as exc:return {'error': str(exc), 'kind': 'client'}
                def received(result):
                    if getattr(self, '_idea_semantic_pending', None) is not pending:return
                    if result.get('error'):
                        self._idea_semantic_pending = None
                        text, log_only = model_error_display(result)
                        if log_only:
                            LOGGER.warning('简报语义提取失败（kind=%s）：%s', result.get('kind') or 'missing', result['error'])
                        self.notifier.info(text, modal=True)
                    else:self.finish_idea_semantic_brief(pending, result['values'])
                self.async_(extract, received, label='模型正在读取附档并提取创作信息…')
        except Exception:
            self._idea_semantic_pending = None
            raise
        self.status.set('正在智能读取附档；提取完成后自动回填，缺项再询问。')
        return True
    def poll_idea_semantic_brief(self):
        pending = getattr(self, '_idea_semantic_pending', None)
        if not pending:return
        from idea_semantic_brief_service import SEMANTIC_BRIEF_POLL_SECONDS, SEMANTIC_BRIEF_TIMEOUT
        if (getattr(self, 'shutting_down', False) or self.page_index != PAGE['script']
                or self._idea_semantic_key(self.draft_text()) != pending['key']):
            self._idea_semantic_pending = None
            self.status.set('输入、附件或项目已变化；未套用旧提取结果，请重新发送。')
            return
        if time.monotonic() - pending['started'] > SEMANTIC_BRIEF_TIMEOUT:
            self._idea_semantic_pending = None
            self.notifier.info('简报提取尚未返回有效结果；请检查 Agent 是否完成提取后重新发送。', modal=True)
            return
        if not pending['local'] or getattr(self, 'worker', False) or time.monotonic() < pending['next_poll']:
            return
        pending['next_poll'] = time.monotonic() + SEMANTIC_BRIEF_POLL_SECONDS
        from stage_execution_service import read_idea_semantic_brief
        try:values = read_idea_semantic_brief(pending['request'])
        except (ValueError, OSError) as exc:
            self._idea_semantic_pending = None
            self.notifier.info(str(exc), modal=True)
            return
        if values is not None:self.finish_idea_semantic_brief(pending, values)
    def finish_idea_semantic_brief(self, pending, values):
        if getattr(self, '_idea_semantic_pending', None) is not pending:return
        self._idea_semantic_pending = None
        current = self.draft_text()
        if self.page_index != PAGE['script'] or self._idea_semantic_key(current) != pending['key']:
            self.status.set('内容已变化，未覆盖当前输入；请重新发送。')
            return
        from stage_execution_service import validate_idea_semantic_sources
        try:validate_idea_semantic_sources(pending['request'])
        except OSError:
            self.notifier.info('附档已不可读取，未套用旧提取结果，请重新发送。', modal=True)
            return
        except ValueError as exc:
            self.notifier.info(str(exc), modal=True)
            return
        import idea_chat
        fields = idea_chat.extract_brief_creation(current, extra_labels=idea_chat.INLINE_REQUIRED_LABELS,
                                                  include_extra=True)
        additions = [label + '：' + value for label, value in values.items() if not fields.get(label)]
        if additions:
            self.idea_input.insert('end', ('\n' if current.strip() else '') + '\n'.join(additions))
        self._idea_semantic_resolved = self._idea_semantic_key(self.draft_text())
        self.status.set('已智能识别并回填创作信息，正在核验必填项。')
        self.send_message()
    def fill_idea_brief(self, values):
        import idea_chat
        box = getattr(self, 'idea_input', None)
        if box is None or not box.winfo_exists():return
        current = self.draft_text()
        merged = idea_chat.merge_brief_creation(current, values)
        if merged != current:
            box.delete('1.0', 'end')
            box.insert('1.0', merged)
            self.preserve_idea_draft()
    def show_missing_idea_brief(self, missing, attachment_fields, notice=''):
        """缺项可一次补齐；保存只更新草稿，发送仍由用户点击。"""
        existing = getattr(self, '_idea_missing_dialog', None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return existing
        import idea_chat
        project, box = self.root, self.idea_input
        fields = dict(attachment_fields)
        fields.update(idea_chat.extract_brief_creation(self.draft_text(),
                      extra_labels=(*idea_chat.INLINE_REQUIRED_LABELS, *missing), include_extra=True))
        dialog = FormDialog(self.win, '补充创作信息')
        self._idea_missing_dialog = dialog
        ttk.Label(dialog.content, text=notice + '以下信息尚未填写。保存后请再次点击发送。').pack(anchor='w', pady=SPACING['sm'])
        from script_contract import PRODUCTION_LOCK_DEFINITIONS, validate_production_locks
        from production_lock_fields import ProductionLockFields
        import stage_config
        lock_labels = {label for item in PRODUCTION_LOCK_DEFINITIONS[5:]
                       for label in (item['label'], *item.get('aliases', ()), item['key'])}
        dialog.brief_fields = {}
        for label in missing:
            if label in lock_labels:
                continue
            row = ttk.Frame(dialog.content)
            row.pack(fill='x', pady=SPACING['xs'])
            ttk.Label(row, text=label).pack(side='left', padx=(SPACING['none'], SPACING['sm']))
            entry = TextArea(row, height=TEXT_ROWS['xs'], width=CHAR_WIDTH['field_sm'], wrap='word')
            entry.pack(side='left', fill='x', expand=True)
            entry.insert('1.0', fields.get(label, ''))
            dialog.brief_fields[label] = entry
        dialog.lock_fields = ProductionLockFields(dialog.content, definitions=PRODUCTION_LOCK_DEFINITIONS[5:])
        dialog.lock_fields.pack(fill='x', pady=SPACING['sm'])
        configured = stage_config.workflow_lock(project)
        for item in PRODUCTION_LOCK_DEFINITIONS:
            for label in (item['label'], *item.get('aliases', ()), item['key']):
                if fields.get(label):
                    configured[item['key']] = fields[label]
                    break
        dialog.lock_fields.set_values(configured)
        def save():
            values = dialog.lock_fields.values()
            try:
                validate_production_locks(values)
                if self.root == project and self.idea_input is box and box.winfo_exists():
                    if stage_config.current_workflow(project).get('name'):
                        from stage_execution_service import save_writing_production_locks
                        old_values = {}
                        for item in PRODUCTION_LOCK_DEFINITIONS[:5]:
                            if item['label'] in dialog.brief_fields:
                                old_values[item['key']] = dialog.brief_fields[item['label']].get('1.0', 'end-1c')
                        save_writing_production_locks(project, {**old_values, **values})
                    updated = {label: entry.get('1.0', 'end-1c')
                               for label, entry in dialog.brief_fields.items()}
                    updated.update({item['label']: values[item['key']] for item in PRODUCTION_LOCK_DEFINITIONS[5:]})
                    self.fill_idea_brief(updated)
                    self.status.set('已保存补充信息，请再次点击发送。')
            except (ValueError, OSError) as exc:
                self.status.set('制作锁保存失败：' + str(exc))
                return
            dialog.close()
        dialog.add_form_actions('保存', save)
        return dialog
    def send_message(self):
        """提交创意；显式 API 模型在聊天框内回复，其余仍启动剧本 Agent。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():raise ValueError('这一页还没建好，请重新打开这一页')
        value=self.draft_text()
        prepared=self.idea_chat_controller.prepare_submission(self.root, value, is_example=False)
        import idea_chat
        import writing_api
        import workflow_settings
        workflow_settings.validate_selected_skills(self.root, 'writing')
        request_model = writing_api.capture_request_model(self.root)
        direct_model = request_model['label']
        continuing = bool(direct_model and prepared and
                          writing_api.preparation_continuation(self.root, value))
        import stage_config, workflow_settings
        workflow_config = stage_config.current_workflow(self.root)
        preset = workflow_settings.WORKFLOW_PRESETS.get(workflow_config.get('name'), {})
        lock_definitions = preset.get('locks') or tuple(
            item for definition in workflow_settings.WORKFLOW_PRESETS.values() for item in definition.get('locks', ()))
        attachment_fields = {}
        if prepared is not None:
            from stage_execution_service import stage_idea_brief_defaults
            reference = prepared['attachments']
            attachment_fields.update(stage_idea_brief_defaults(self.root, reference=reference)['values'])
            # 普通字段沿用 L2 别名；锁标签只来自统筹定义，不再维护第二张映射表。
            lock_labels = tuple(label for item in lock_definitions
                                for label in (item['label'], *item.get('aliases', ())))
            lock_fields = {}
            for text in reference.get('brief_texts', ()):
                for label, field in idea_chat.extract_brief_creation(
                        text, extra_labels=lock_labels, include_extra=True).items():
                    lock_fields.setdefault(label, field)
            attachment_fields.update(lock_fields)
        from script_contract import PRODUCTION_LOCK_DEFINITIONS
        configured_locks = stage_config.workflow_lock(self.root)
        attachment_fields.update({item['label']: configured_locks[item['key']]
            for item in PRODUCTION_LOCK_DEFINITIONS if configured_locks.get(item['key'])})
        missing = () if continuing else idea_chat.inline_required_missing(None, value,
                                                    attachment_fields=attachment_fields,
                                                    stage='script', lock_definitions=lock_definitions,
                                                    created_at=stage_config.project_created_at(self.root))
        if missing:
            notice = idea_chat.BRIEF_ATTACHMENT_NOTICE + '\n' if prepared and prepared['attachments'].get('brief_unreadable') else ''
            self.show_missing_idea_brief(missing, attachment_fields, notice)
            return
        if prepared is None:
            return
        submission=prepared['submission']
        visible_value=prepared['visible_value']
        if direct_model and self.idea_chat_controller.requesting:
            raise ValueError('模型正在回复，请不要重复发送。')
        # UI 故事字段与阶段锁门禁通过后仍核验底层四项契约；缺项只提示，不启动模型。
        brief = {'missing': ()} if continuing else idea_chat.receive_brief(self.idea_chat_context(), submission, workflow=workflow_config,
                                        lock_definitions=lock_definitions, gateway=self.idea_chat_gateway(),
                                        attachment_reference=prepared['attachments'], inline_text=value, stage='script',
                                        created_at=stage_config.project_created_at(self.root))
        if brief['missing']:
            self.notifier.info((brief.get('attachment_notice', '') + '\n' + brief['followup']).strip(), modal=True)
            return
        if brief.get('workflow_projection') is not None:
            stage_config.put_workflow(self.root, brief['workflow_projection'])
        request_model = writing_api.capture_request(self.root)
        direct_model = request_model['label']
        if direct_model:
            model = direct_model
            cleared = False
        else:
            model, cleared = request_model['settings']['display_model'], False
        self.idea_chat_controller.mark_sent()
        if not direct_model:
            # 启动失败不能吞掉用户刚输入的内容；成功启动后才落聊天记录并清空编辑框。
            try:model, cleared = self.start_script_workflow(submission, config=request_model['settings'])
            except Exception:
                self.idea_chat_controller.rollback_sent()
                raise
        if not continuing:
            idea_chat.save_brief_creation(self.idea_chat_context(), value, gateway=self.idea_chat_gateway())
        idea_chat.append(self.idea_chat_context(),'user',visible_value,model=model,gateway=self.idea_chat_gateway(),
                         skill_injection=request_model['settings']['skill_injection'])
        # 本次发送已确定模型，废弃旧的异步解析并用同一分区显示刚保存的消息。
        self._idea_view_model_request=getattr(self,'_idea_view_model_request',0)+1
        self._idea_view_model_cache=(self.root,model)
        if self.stage_button is not None and self.stage_button.winfo_exists():
            self.stage_button.configure(text=ui_plugin_registry.module('skill_panel').stage_button_label(self,'script'))
        box.delete('1.0','end')
        self.discard_idea_draft()
        self.idea_attachment_paths=()
        self.update_idea_attachment_status()
        self.show_conversation()
        prefix = '已打开 '+model+' 的独立对话；' if cleared else ''
        if direct_model:
            project = self.root
            token, cancelled = self.idea_chat_controller.begin_request(cancellable=True)
            async_ticket={'value':None}
            if getattr(self,'idea_send',None) is not None:self.idea_send.state(['disabled'])
            self.update_script_interrupt_button()
            self.show_thinking(model)
            received=lambda result:self._idea_api_received(token,model,request_model,result)
            def ask():
                from stage_execution_service import reply_to_writing
                return reply_to_writing(
                    project, submission, user_message=value, request_model=request_model,
                    cancelled=cancelled.is_set)
            self.submit_idea_api_request(project, token, cancelled, ask, received,
                                         model+' 模型正在思考…', async_ticket)
        else:
            self._script_agent_launching=True
            self.update_script_interrupt_button()
            self.status.set(prefix+'已提交创意并启动剧本 Agent。')
    def _idea_api_received(self, token, model, request_model, result):
        """直连 API 模型的回复落地：聊天记录、状态栏、失败提示与三虎终态。"""
        import idea_chat
        from writing_api import preparation_reply_message
        if not self.idea_chat_controller.finish_request(token):return
        if getattr(self,'idea_send',None) is not None and self.idea_send.winfo_exists():self.idea_send.state(['!disabled'])
        self.update_script_interrupt_button()
        self.clear_thinking()
        visible_reply = str(result.get('response_text') or result.get('text') or '')
        self.show_script_quality(result)
        if visible_reply.strip():
            idea_chat.append(self.idea_chat_context(),'assistant',visible_reply,model=model,gateway=self.idea_chat_gateway(),
                             context_budget=result.get('context_budget'), request_usage=result.get('request_usage'),
                             skill_injection=request_model['settings']['skill_injection'])
            self.show_conversation()
        if not result.get('ok'):
            error=str(result.get('error') or '未收到模型回复')
            kind=('budget' if result.get('reason') == 'context_budget_exceeded'
                  else str(result.get('kind') or ''))
            if kind in ('network', 'server'):
                message='模型暂时无法响应，请稍后重试'
            elif kind in ('auth', 'budget', 'client', ''):
                message='模型调用未完成：'+error
            else:
                message='系统内部错误，已记录日志'
            if kind not in ('auth', 'budget', 'client', ''):
                LOGGER.warning('模型调用失败（kind=%s）：%s', kind or 'missing', error)
            self.status.set(preparation_reply_message(result) or message)
            if result.get('reason') == 'context_budget_exceeded' or '上下文超过' in error or '超过模型上下文' in error:
                self.notifier.error(message, title='请求校验未通过')
            else:
                self.notifier.error(message, title='模型调用失败')
            # 直接 API 模型与桌面 Agent 共用“剧本准备”这个自动阶段。
            # 失败若只写状态栏，三虎会一直把 script 视为 active；仅当
            # 自动链确实正在等待 script 时，才把可恢复的调用失败交给它。
            auto=getattr(getattr(self,'pet',None),'auto',None)
            if getattr(auto,'active',None)=='script':
                # 直连 API 的失败已经是终态；再让通用 Agent 重试只会留下
                # 一个没有新请求的 retrying 状态。因此直接发出终态失败，
                # 明确停在可由用户重试的剧本阶段。
                self.pet._emit('stage.failed',stage='script',error=message)
            return
        reply=str(result.get('text') or '').strip()
        if not reply:
            self.notifier.error(idea_chat.why_empty(result), title='模型调用失败')
            self.status.set(idea_chat.why_empty(result));return
        self.show_conversation()
        if result.get('preparation_path'):
            refresh=getattr(self,'refresh_script_list',None)
            if callable(refresh):refresh()
            self.status.set(preparation_reply_message(result) or (result['preparation_stage']+'已保存，请审阅后回复“确认”；需要修改请直接说明。'))
            return
        if result.get('script_raw_path'):
            refresh=getattr(self,'refresh_script_list',None)
            if callable(refresh):refresh()
            if result.get('quality_passed') is not False:
                self.pet_report('script', script_raw_saved_notice(result.get('natural_script_path', '')))
        if result.get('quality_summary'):
            self.show_script_quality(result)
            return
        if result.get('natural_script_path'):
            self.status.set(preparation_reply_message(result) or ('自然剧本已自动保存：'+result['natural_script_path']))
        else:
            self.status.set(self.auto_save_script_reply(model,result) or '已收到 '+model+' 的回复。')
    def submit_idea_api_request(self, project, token, cancelled, ask, received, label, async_ticket=None):
        """发送与恢复共用票据生命周期；项目切换和取消均撤销本次排队。"""
        from workflow_engines import (request_stage_process_slot, claim_stage_process_slot,
                                      release_stage_process_slot, cancel_stage_slot_request)
        controller = self.idea_chat_controller
        request = request_stage_process_slot(project, 'writing')
        pending = {'timer': None}
        def cleanup():
            cancel_stage_slot_request(request.get('ticket'))
            timer, pending['timer'] = pending['timer'], None
            if timer is not None:
                try:self.win.after_cancel(timer)
                except tk.TclError:pass
        controller.set_request_cleanup(token, cleanup)
        def current():
            return controller.accepts(token, cancelled, self.root, project)
        def receive(result):
            if current():received(result)
        def dispatch(slot):
            if not current():
                release_stage_process_slot(slot)
                if controller.request_is_current(token):controller.cancel_request()
                return
            def work():
                try:
                    if cancelled.is_set():return {'ok': False, 'error': '模型请求已取消'}
                    return ask()
                finally:
                    release_stage_process_slot(slot)
            try:
                if async_ticket is not None:async_ticket['value'] = self._async_ticket + 1
                ticket = self.async_(work, receive, label=label)
                if async_ticket is not None:async_ticket['value'] = ticket
            except Exception:
                release_stage_process_slot(slot)
                controller.cancel_request()
                raise
        def poll_slot():
            pending['timer'] = None
            if not current():
                cleanup()
                if controller.request_is_current(token):controller.cancel_request()
                return
            act(slot_decision(claim_stage_process_slot(request['ticket'])))
        def act(decision):
            action, value = decision
            if action == 'run':
                dispatch(value)
            elif action == 'wait':
                self.status.set(queue_notice(value))
                pending['timer'] = self.win.after(200, poll_slot)
            else:
                receive({'ok': False, 'error': value})
        act(('run', request['slot']) if request['state'] == 'granted' else ('wait', request['position']))
    def script_agent_processes(self):
        """返回当前剧本阶段由本窗口启动、仍在运行的 Agent 进程。"""
        sessions=getattr(self,'flow_processes',{})
        return [(key,process) for key,process in sessions.items()
                if len(key)>1 and key[1]=='writing' and process.poll() is None]
    def cancel_script_agent_queue(self):
        """仅撤销本窗口的剧本 CLI 排队，不影响其他项目或阶段。"""
        pending = getattr(self, '_script_agent_queue', None)
        if pending is None:return False
        pending['cancel']()
        self._script_agent_launching = False
        self.update_script_interrupt_button()
        return True
    def interrupt_script_agent(self):
        """中断当前剧本 API 请求或本窗口启动的剧本 Agent，不影响其他制作阶段。"""
        self._idea_semantic_pending = None
        api_active=getattr(self,'_idea_requesting',False)
        processes=self.script_agent_processes()
        launching=getattr(self,'_script_agent_launching',False)
        queued = bool(getattr(self,'_script_agent_queue',None))
        if not has_interruptible(api_active,processes,launching,queued):
            self.status.set('当前没有可中断的剧本 Agent 调用。')
            return False
        if queued:self.cancel_script_agent_queue()
        self._async_ticket+=1;self.background_tasks.cancel(costly=bool(api_active))
        self.worker=False;self.busy_state.set_busy(False)
        self.idea_chat_controller.cancel_request()
        if getattr(self,'idea_send',None) is not None and self.idea_send.winfo_exists():self.idea_send.state(['!disabled'])
        self.clear_thinking()
        stopped=[]
        from workflow_engines import forget_process
        sessions=getattr(self,'flow_processes',{})
        for key,process in processes:
            try:
                from platform_tools import terminate_process_tree
                if terminate_process_tree(process):
                    stopped.append(str(process.pid))
                forget_process(self.root,process)
            except (OSError,subprocess.SubprocessError):pass
            sessions.pop(key,None)
        self.flow_processes=sessions
        self.update_script_interrupt_button()
        info=self.background_tasks.cancellation_status() if api_active else None
        self.status.set(interrupt_notice(stopped,api_active,info['text'] if info is not None else ''))
        return True
    def idea_example(self):
        """创意栏里那份预置示例（第 37 期第 2 条）：随程序打包，不改动就绝不进项目文件。

        正文只有程序目录这一份（默认创意示例.md）；项目里那份 创意与剧本.md 只有在用户真的
        改过、按过保存之后才会出现（见 save_brief）。程序里那份万一缺了，就退回一张只有字段名
        的空表，界面照常能用。首读一次记在 self._idea_example 上，翻页重建不重复读盘。
        """
        cached=getattr(self,'_idea_example',None)
        if cached is not None:return cached
        path=ROOT/'默认创意示例.md'
        try:
            text=path.read_text(encoding='utf-8-sig') if path.is_file() else ''
        except OSError:
            text=''
        if not text.strip():
            from script_contract import INLINE_REQUIRED_LABELS
            text='\n'.join(label+'：' for label in dict.fromkeys((*IDEA_FIELDS, *INLINE_REQUIRED_LABELS)))+'\n'
        self._idea_example=text
        return text
    def open_flow_agent(self, stage, label, prompt, followup=None, on_receipt=None, _config=None, *, intake_only=False, new_session=False, desktop_paste=False):
        return _FlowAgentLaunch(self, _FlowAgentRequest(stage, label, prompt, followup, on_receipt, _config, intake_only,
                                                       new_session, desktop_paste)).build()


class _FlowAgentRequest:
    """open_flow_agent 的参数对象（收拢 _FlowAgentLaunch 的入参）。"""
    __slots__ = ('stage', 'label', 'prompt', 'followup', 'on_receipt', '_config', 'intake_only', 'new_session', 'desktop_paste')

    def __init__(self, *values):
        for name, value in zip(self.__slots__, values):
            setattr(self, name, value)


class _FlowAgentLaunch:
    """一次 Agent 任务的打开流程：准备任务与上下文、去重派发，按引擎走 CLI（含排队取槽）、Claude Desktop 或 GPT 桌面粘贴。"""
    def __init__(self, host, request):
        self.host = host
        for name in _FlowAgentRequest.__slots__:
            setattr(self, name, getattr(request, name))

    def build(self):
        from workflow_settings import writer_style_summary
        self.writer_style_summary = writer_style_summary
        from workflow_engines import prompt_with_settings,launch_interactive
        self.prompt_with_settings = prompt_with_settings; self.launch_interactive = launch_interactive
        from agent_dispatch import signature,claim,finish,outcome,retryable
        self.signature = signature; self.claim = claim; self.finish = finish; self.outcome = outcome; self.retryable = retryable
        if self.host.worker:raise ValueError('正在打开或发送 Agent 任务，请稍候；未重复发送。')
        if self.stage == 'writing' and getattr(self.host, '_script_agent_queue', None):
            raise ValueError('剧本模型请求正在排队，请等待或先点击中断；未重复发送。')
        # 「发送待核实」的安全重试必须沿用第一次已经解析的引擎。原来递归重进时会重新
        # 读取阶段配置，恰逢面板刷新／配置回退就可能把 Claude 的续发错误地交给 Codex。
        from workflow_settings import resolve_for_send
        self.config=resolve_for_send(self.host.root,self.stage,config=self._config,intake_only=self.intake_only);self.followup=self.followup if self.followup is not None else self.prompt
        if self.stage=='storyboard' and not self.intake_only:
            # 唯一分流点（REQ-S03-53）：选了模型池里的 API 模型就由程序直连，不再经 Qwen Code。
            from storyboard_direct_api import direct_model
            if direct_model(self.config):
                _run_storyboard_direct(self.host,self.config);return
        self.native_claude = self.config['engine'] in ('claude-desktop-app', 'desktop-app')
        self.bounded_writing = self.stage == 'writing' and self.config['engine'] == 'claude'
        if self.stage == 'writing' and self.config['engine'] == 'claude' and not self.intake_only and not self.new_session:
            from workflow_engines import claude_session_stale
            self.new_session = claude_session_stale(self.host.root, self.stage)
        self.new_session = bool(self.new_session and self.stage == 'writing' and self.config['engine'] == 'claude' and not self.intake_only)
        self.use_cli = not self.native_claude and (self.config['engine']!='codex' or self.config['program'] or self.config['model'])
        # CLI 继续复用同一进程；提取结束后不能占住唯一槽位又排队启动剧本进程。
        self.setup_key=hashlib.sha256((json.dumps(self.config,sort_keys=True)+('brief-intake' if self.intake_only and not self.use_cli else '')).encode()).hexdigest()
        from codex_tasks import prepare_task
        self.prepare_task = prepare_task
        self.project=self.host.root
        name=next((p['name'] for p in self.host.projects.info['projects'] if Path(p['path'])==self.project),self.project.name)
        self.title=name+' '+self.label
        if self.config['engine']=='qwen':
            from qwen_adapter import window_title
            self.title=window_title(name,self.stage,getattr(self.host,'page_index',None))
        self.host.async_(self.prepare,self.dispatch)

    def prepare(self):
        from workflow_context import continuation_instruction,snapshot
        from stage_execution_service import project_context
        from workflow_context_controller import request_stage_instruction
        from workflow_context_budget import prepare_request_context
        if self.config['engine']=='codex':
            from codex_skill_sync import sync_codex_skills
            sync_result=sync_codex_skills()
            if sync_result['errors'] or sync_result['conflicts']:
                raise ValueError('Codex 技能同步未完成：'+ '; '.join(
                    sync_result['errors']+sync_result['conflicts']))
        data={} if self.intake_only or self.bounded_writing else snapshot(project_context(self.project))
        receipt=self.claim(self.project,self.signature(self.stage,self.prompt,self.followup,self.config,data),self.title)
        if self.on_receipt is not None:self.on_receipt(receipt)
        if receipt['duplicate'] and self.use_cli:return {'receipt':receipt}
        if not self.use_cli:receipt['duplicate']=False
        try:
            if self.stage=='previs':
                from native_apps import open_blender
                open_blender()
            if self.intake_only:
                # 提取阶段不得附加“直接生成剧本”的 SKILL/阶段交付指令。
                full,budget=prepare_request_context(self.prompt,self.stage,'brief_intake',report=True)
                continuation,continuation_budget=prepare_request_context(self.followup,self.stage,'brief_intake',report=True)
            elif self.bounded_writing:
                full,budget=prepare_request_context(
                    self.prompt_with_settings(self.prompt,self.config,stage=self.stage),self.stage,'explicit_writing_inputs',report=True)
                continuation,continuation_budget=prepare_request_context(
                    self.prompt_with_settings(self.followup,self.config,stage=self.stage),self.stage,'explicit_writing_inputs',report=True)
            else:
                context,strategy=request_stage_instruction(self.project,self.stage,data)
                full,budget=prepare_request_context(
                    self.prompt_with_settings(context+self.prompt,self.config,stage=self.stage),self.stage,strategy,report=True)
                continuation,continuation_budget=prepare_request_context(
                    self.prompt_with_settings(continuation_instruction(self.project,self.stage,data)+self.followup,self.config,stage=self.stage),
                    self.stage,'continuation_summary',report=True)
            self.finish(receipt,'preparing','',skill_injection=self.config.get('skill_injection'),context_budget={
                'initial':budget,'continuation':continuation_budget})
            if self.native_claude:
                from desktop_send_choice import prepare_native  # 交付方式、任务文件、续发计划（REQ-S01-69）
                return prepare_native(self, receipt, full)
            if self.use_cli:return {'receipt':receipt,'prompt':full,'followup':continuation,
                               'context_budget':{'initial':budget,'continuation':continuation_budget}}
            result=self.prepare_task(self.project,self.title,self.stage,full,followup=continuation,setup_key=self.setup_key,
                                delivery_summary='' if self.intake_only else self.writer_style_summary(self.config,self.stage))
            result['receipt']=receipt;result['context_budget']={
                'initial':budget,'continuation':continuation_budget};return result
        except Exception as exc:self.finish(receipt,'failed',str(exc));raise

    def dispatch(self, result):
        receipt=result['receipt']
        if receipt['duplicate']:
            sessions=getattr(self.host,'flow_processes',{})
            key=(str(self.project),self.stage,self.config['engine'],self.setup_key)
            live=key in sessions and sessions[key].poll() is None
            if self.retryable(receipt,live):
                self.finish(receipt,'failed','上次发送结果未确认，且对应 Agent 窗口已关闭')
                self.host.status.set('上次 Agent 发送未确认且窗口已关闭，正在自动重新启动…')
                self.host.open_flow_agent(self.stage,self.label,self.prompt,self.followup,self.on_receipt,_config=self.config,intake_only=self.intake_only,new_session=self.new_session)
                return
            self.settle_launch()
            if not live:
                self.finish(receipt,'failed','上次 Agent 窗口已关闭，请重新点击启动')
                self.host.notifier.info('上次 Agent 窗口未在运行，任务状态已重置；请再次点击“手动制作分镜”。', title='请重新点击', modal=True);return
            state={'preparing':'正在打开或发送','sent':'已发送','uncertain':'发送结果待核实'}[receipt['state']]
            self.host.status.set('相同任务'+state+'，已复用记录，本次不重复发送。请在对应 Agent 窗口继续。');return
        if self.use_cli:
            self.launch_cli(result);return
        self.settle_launch()
        try:self.done(result)
        except Exception as exc:self.finish(receipt,'failed',str(exc));raise

    def settle_launch(self):
        """剧本任务已交给桌面程序或已有会话：本机不再处于启动中，按钮改由进程与请求状态决定。"""
        if self.stage!='writing':return
        self.host._script_agent_launching=False
        refresh=getattr(self.host,'update_script_interrupt_button',None)
        if callable(refresh):refresh()

    def launch_cli(self, result):
        receipt=result['receipt'];full=result['prompt'];continuation=result['followup']
        sessions=getattr(self.host,'flow_processes',{});key=(str(self.project),self.stage,self.config['engine'],self.setup_key)
        if key in sessions and sessions[key].poll() is None:
            if self.new_session:
                def close_old():
                    from workflow_engines import close_for_restart
                    try:close_for_restart(self.project,sessions[key])
                    except Exception as exc:self.finish(receipt,'failed',str(exc));raise
                def closed(_):
                    sessions.pop(key,None)
                    self.launch_cli(result)
                self.host.status.set('正在结束空闲 Claude 会话，准备以新上下文重新创作…')
                self.host.async_(close_old,closed);return
            def submit():
                try:
                    if self.config['engine']=='qwen':
                        from qwen_adapter import submit_existing
                        text=submit_existing(sessions[key],continuation,title=self.title)
                        return {'ok':True,'reason':text,'send_dispatched':True}
                    from workflow_engines import submit_existing
                    return submit_existing(sessions[key],continuation,title=self.title)
                except Exception as exc:
                    self.finish(receipt,'uncertain',str(exc));raise
            def submitted(value):
                self.outcome(receipt,value);self.settle_launch();self.host.status.set(value['reason'])
                if not value['ok']:self.host.notifier.info(value['reason'], title='请检查 Agent 输入框', modal=True)
            self.host.async_(submit,submitted);return
        def launched(result):
            sessions[key]=result['process'];self.host.flow_processes=sessions
            if self.stage=='writing':
                self.host._script_agent_launching=False
                self.host.update_script_interrupt_button()
            self.finish(receipt,'sent','启动时已传入初始任务',task_file=result['task_file'])
            self.host.status.set('已启动 '+result['engine']+'，初始任务已自动提交，可在窗口继续讨论。')
        def launch(slot=None):
            try:return self.launch_interactive(self.project,self.stage,self.title,full,self.config,followup=continuation,slot=slot,
                                          **({'new_session':True} if self.new_session else {}))
            except Exception as exc:
                from workflow_engines import release_stage_process_slot
                release_stage_process_slot(slot)
                self.finish(receipt,'failed',str(exc));raise
        from workflow_engines import request_stage_process_slot, claim_stage_process_slot
        request=request_stage_process_slot(self.project,self.stage)
        if request['state']=='granted':
            self.host.async_(lambda:launch(request['slot']),launched);return
        from workflow_engines import cancel_stage_slot_request
        pending = {'timer': None, 'cancelled': False, 'started': time.monotonic()}
        def cleanup():
            pending['cancelled'] = True
            cancel_stage_slot_request(request['ticket'])
            timer, pending['timer'] = pending['timer'], None
            if timer is not None:
                try:self.host.win.after_cancel(timer)
                except tk.TclError:pass
            if getattr(self.host, '_script_agent_queue', None) is pending:
                self.host._script_agent_queue = None
                self.host._script_agent_launching = False
                self.host.update_script_interrupt_button()
        def cancel():
            cleanup()
            self.finish(receipt,'failed','模型排队请求已取消，尚未启动 CLI')
        pending['cancel'] = cancel
        if self.stage == 'writing':
            self.host._script_agent_queue = pending
            self.host._script_agent_launching = True
            self.host.update_script_interrupt_button()
        self.host.status.set('模型请求排队中（第%d位），尚未启动 CLI；可点击中断，最多等待 120 秒。' % request['position'])
        def poll_slot():
            pending['timer'] = None
            if pending['cancelled']:return
            if self.host.root != self.project or getattr(self.host,'shutting_down',False) or getattr(self.host,'_closing',False):
                cancel()
                return
            if time.monotonic() - pending['started'] >= 120:
                cleanup()
                message = '等待模型并发名额超过 120 秒，已退出排队；请检查已有 Agent 任务后重新发送。'
                self.finish(receipt,'failed',message)
                self.host.status.set(message)
                return
            claimed=claim_stage_process_slot(request['ticket'])
            if claimed['state']=='queued':
                self.host.status.set('模型请求排队中（第%d位），尚未启动 CLI；可点击中断，最多等待 120 秒。' % claimed['position'])
                pending['timer'] = self.host.win.after(200,poll_slot);return
            cleanup()
            if claimed['state']=='granted':
                if self.stage == 'writing':
                    self.host._script_agent_launching = True
                    self.host.update_script_interrupt_button()
                self.host.status.set('已获得模型请求槽位，正在启动…')
                self.host.async_(lambda:launch(claimed['slot']),launched);return
            self.finish(receipt,'failed',claimed['reason'])
            self.host.status.set(claimed['reason'])
        pending['timer'] = self.host.win.after(200,poll_slot)

    def done(self, result):
        if result.get('send_plan'):from desktop_send_choice import choose;return choose(self, result, self.done)
        receipt=result['receipt']
        clipboard_text=result['prompt']
        task_file=result.get('task_file')
        if task_file and Path(task_file).is_file():
            try:clipboard_text=Path(task_file).read_text(encoding='utf-8')
            except OSError:clipboard_text=result['prompt']
        from desktop_send_choice import attachment_payload, deliver_desktop_app  # 长任务改附件＋短指令（REQ-S01-70）
        clipboard_text,attachment=attachment_payload(self.config.get('engine'),task_file,clipboard_text)
        from prompt_window import copy_text
        copy_text(self.host.win,clipboard_text)
        if self.native_claude:
            from workflow_settings import find_program
            from platform_tools import launch_windows_app
            program = find_program(self.config)
            if self.config['engine'] == 'desktop-app':
                app = self.config.get('display_model') or '桌面模型'
                deliver_desktop_app(self.host, self.finish, receipt, task_file, self.title,
                                     clipboard_text, program, app,
                                     (self.config.get('delivery') or 'paste') if self.desktop_paste else 'clipboard',
                                     attachment)
                return
            launch_windows_app(program, 'Claude Desktop')
            from codex_paste import paste_existing
            def claude_pasted(value):
                self.finish(receipt,'prepared' if value['ok'] else 'failed',value['reason'],task_file=task_file)
                self.host.status.set(value['reason'])
                level=getattr(self.host,'gate_level',None)
                if value['ok'] and callable(level) and level()=='auto':
                    # 全自动不拦截 Claude Desktop：它只能由用户点发送，这里明确提示，
                    # 避免自动链看似停住却没有说明；状态栏原文也会转给三虎。
                    message=('三虎全自动：'+self.label+' 的任务已粘贴到 Claude Desktop，'
                                 '请切到 Claude Desktop 手动点击发送；完成后产物会自动收回。')
                    self.host.status.set(message)
                    self.host.notifier.warning(message,title='请手动发送')
            self.host.status.set('正在将本次任务粘贴到 Claude Desktop，请检查后手动发送…')
            self.host.async_(lambda:paste_existing(self.title,clipboard_text,program=program,deadline_seconds=45),claude_pasted)
            return
        if self.config.get('desktop_program'):
            from platform_tools import launch_windows_app
            launch_windows_app(self.config['desktop_program'], 'Codex 桌面')
        open_target(result['url'])
        from codex_paste import paste_existing
        def pasted(result):
            self.finish(receipt,'prepared' if result['ok'] else 'failed',result['reason'])
            self.host.status.set(result['reason'])
        self.host.async_(lambda:paste_existing(result['title'],clipboard_text,result.get('draft_prompt',''),result.get('project',''),deadline_seconds=45 if result.get('mode')=='new' else 15),pasted)
        self.host.status.set('正在将本次任务粘贴到 GPT 桌面，请在窗口中手动点击发送…')
