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
from idea_chat_controller import bubble_timestamp, collapse_preview
from platform_tools import open_target
from ui_tokens import COLORS, FONTS, SPACING
from ui_widgets import FormDialog, TextArea

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
BUBBLE_BACK=COLORS['background_card']  # 内容框的底色：气泡两边的留白用它刷，色块才贴着字
BUBBLE_FONT=('Microsoft YaHei UI',10)
BUBBLE_TIME_FONT=('Microsoft YaHei UI',9)
BUBBLE_PAD=10          # 气泡里文字与色块边缘的距离
BUBBLE_GAP=14          # 气泡离画面左右两边各留这么多
BUBBLE_FLOOR=70        # 气泡最窄也有这么宽
BUBBLE_LINE=13         # 量不出字宽时的兜底：一个字大约这么宽
BUBBLE_MAX_RATIO=0.72  # 第 71 期任务 6：字再多，色块也不铺满整行，一行才看得下去
BUBBLE_SLACK=26        # 量字宽只是估算（字号、全角半角都有出入），留一截余地，
                       # 免得一句话末了一个字被挤到下一行


class IdeaChatMixin:
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
    def refit_bubbles(self,event=None):
        """第 69 期任务 1：窗口一改宽窄就重算气泡的左右边距——只动边距，
        上面的字和您正在写的那段一个字节都不碰。"""
        box=getattr(self,'idea_log',None)
        if box is None or not box.winfo_exists():return
        if event is not None and getattr(event,'widget',None) is not box:return
        width=int(box.winfo_width() or 0)
        if width<=1 or width==getattr(self,'_bubble_width',None):return
        self._bubble_width=width
        for name,text,mine in getattr(self,'_bubble_rows',[]):
            left,right=self.bubble_margins(box,text,mine)
            for tag in (name,name+'_time',name+'_meta',name+'_toggle',name+'_thinking'):
                try:box.tag_configure(tag,lmargin1=left,lmargin2=left,rmargin=right)
                except tk.TclError:pass
    def bubble_font(self):
        """量字宽用的字体；量不出来给 None（退回「一个字 BUBBLE_LINE 像素」的估算）。"""
        face=getattr(self,'_bubble_font','missing')
        if face=='missing':
            try:
                from tkinter import font as tkfont
                face=tkfont.Font(font=BUBBLE_FONT)
            except Exception:
                face=None
            self._bubble_font=face
        return face
    def bubble_margins(self,box,text,mine):
        """第 69 期任务 1：一条气泡的左右边距——量出这段字的宽窄，把色块贴着字放，
        于是每条气泡长短不一、左右错落，看起来才是聊天。

        第 71 期任务 6：字再多，色块也不铺满整行——顶到 BUBBLE_MAX_RATIO 就换行，
        一行到底看不下去、也不好操作。"""
        width=max(240,int(box.winfo_width() or 0))
        span=max(BUBBLE_FLOOR,width-2*BUBBLE_GAP)
        span=min(span,max(BUBBLE_FLOOR,int(width*BUBBLE_MAX_RATIO)))
        body=max(BUBBLE_FLOOR,min(span,self.text_width(text)+BUBBLE_PAD*2+BUBBLE_SLACK))
        # 微信式对话：模型在左、用户在右，气泡仍按文字实际宽度收紧。
        if mine:
            return max(0,width-BUBBLE_GAP-body),BUBBLE_GAP
        return BUBBLE_GAP,max(0,width-BUBBLE_GAP-body)
    def bubble_time(self,at):
        """气泡上面那一行小字（实现搬到 L3 idea_chat_controller，入口不变）。"""
        return bubble_timestamp(at)
    def bubble_preview(self,text):
        """过长的消息先给紧凑预览（实现搬到 L3 idea_chat_controller，入口不变）。"""
        return collapse_preview(text)
    def toggle_bubble(self,box,name):
        """点击“展开全文／收起”只改当前气泡的正文，不重建输入区。"""
        record=getattr(self,'_bubble_full',{}).get(name)
        if not record:return 'break'
        ranges=box.tag_ranges(name)
        if len(ranges)<2:return 'break'
        was_disabled=str(box.cget('state'))=='disabled'
        if was_disabled:box.configure(state='normal')
        # 记住视口顶端那一行：整段先删后插会让 Text 一拍内塌缩再撑开，视口跳到空白处。
        try:top=box.index('@0,0')
        except tk.TclError:top=None
        start=str(ranges[0])
        try:
            record['expanded']=not record['expanded']
            shown=record['text'] if record['expanded'] else record['preview']
            # 先插新正文再删旧正文，内容高度不会瞬间归零。
            box.insert(ranges[-1],shown+'\n',name)
            box.delete(start,ranges[-1])
            toggle=name+'_toggle'
            spans=box.tag_ranges(toggle)
            if len(spans)>=2:
                end=spans[-1]
                box.insert(end,('收起' if record['expanded'] else '展开全文')+'\n',toggle)
                box.delete(spans[0],end)
        finally:
            if was_disabled:box.configure(state='disabled')
        try:
            if record['expanded'] or top is None:
                # 展开：视口不动，正文往下长，和微信一样原地展开。
                if top is not None:box.yview(top)
            elif box.compare(start,'<',top):
                # 收起：气泡开头已滚出视口时，把视口拉回这条气泡开头，不留空白。
                box.yview(start+' linestart -3 lines')
            else:
                box.yview(top)
        except tk.TclError:
            pass
        return 'break'
    def bubble_target_at(self,box,event):
        """鼠标位置对应的真实消息；元信息和“展开全文”也归回它所属的气泡。"""
        try:tags=box.tag_names(box.index('@%d,%d'%(event.x,event.y)))
        except tk.TclError:return None
        for tag in tags:
            if str(tag)=='bubble_example':
                return 'example','bubble_example'
            parts=str(tag).split('_')
            if len(parts)>=2 and parts[0]=='bubble' and parts[1].isdigit():
                return int(parts[1]),'bubble_'+parts[1]
        return None
    def copy_selected_bubble_text(self,event=None):
        """保留原生拖选体验；Ctrl+C 只复制用户实际选中的文字。"""
        box=getattr(self,'idea_log',None)
        if box is None:return 'break'
        try:text=box.get('sel.first','sel.last')
        except tk.TclError:return 'break'
        if not text:return 'break'
        from prompt_window import copy_text
        reason=copy_text(box,text)
        self.status.set('复制失败：'+reason if reason else '已复制选中文字')
        return 'break'
    def notice_selected_bubble_text(self,event):
        """长按拖选到消息正文后给出明确复制提示；不改动 Tk 原生蓝色选区。"""
        box=event.widget
        try:
            selected=box.tag_ranges('sel')
            tags=box.tag_names(selected[0]) if len(selected)>=2 else ()
        except tk.TclError:return None
        if any(str(tag).startswith('bubble_') and str(tag).split('_')[1:2] and
               str(tag).split('_')[1].isdigit() for tag in tags):
            self.status.set('已选中气泡正文，按 Ctrl+C 复制。')
        return None
    def begin_bubble_click(self,event,index,name):
        """记录正文按下位置；正在编辑同一气泡时交还给 Tk 原生选字。"""
        edit=getattr(self,'_bubble_edit',None)
        if edit and edit.get('box') is event.widget and edit.get('index')==index:
            self._bubble_click=None
            return None
        self._bubble_click={'box':event.widget,'index':index,'name':name,
                            'x':event.x,'y':event.y,'dragged':False}
        return None
    def track_bubble_click(self,event):
        """鼠标移动说明用户在选字，不能误切进编辑态。"""
        click=getattr(self,'_bubble_click',None)
        if click and click.get('box') is event.widget:
            if abs(event.x-click['x'])>3 or abs(event.y-click['y'])>3:
                click['dragged']=True
        return None
    def finish_bubble_click(self,event):
        """短按正文进入编辑；长按拖选继续使用原生蓝色选区。"""
        click=getattr(self,'_bubble_click',None)
        self._bubble_click=None
        self.notice_selected_bubble_text(event)
        if not click or click.get('box') is not event.widget or click.get('dragged'):
            return None
        try:
            selected=event.widget.tag_ranges('sel')
            if len(selected)>=2 and event.widget.compare(selected[0],'!=',selected[-1]):
                return None
        except tk.TclError:
            return None
        return self.safe(lambda:self.start_bubble_edit(event,click['index'],click['name']))
    def copy_bubble_message(self,index):
        """右键“复制整条信息”：只取持久化的正文，不把界面元信息混进去。"""
        if index == 'example':
            text=self.idea_example()
            if not text:return None
            from prompt_window import copy_text
            reason=copy_text(self.idea_log,text)
            self.status.set('复制失败：'+reason if reason else '已复制软件示例')
            if reason:return None
            return text
        import idea_chat
        rows=idea_chat.load(self.idea_chat_context(),model=self.displayed_chat_model(),gateway=self.idea_chat_gateway())
        if not 0<=index<len(rows):return None
        text=str(rows[index].get('text') or '')
        if not text:return None
        from prompt_window import copy_text
        reason=copy_text(self.idea_log,text)
        self.status.set('复制失败：'+reason if reason else '已复制整条信息')
        if reason:return None
        return text
    def delete_bubble_message(self,index):
        """右键“删除整条信息”：移出当前对话，并保留最近删除恢复记录。"""
        import idea_chat
        model=self.displayed_chat_model()
        rows=idea_chat.load(self.idea_chat_context(),model=model,gateway=self.idea_chat_gateway())
        if not 0<=index<len(rows):return None
        idea_chat.remove(self.idea_chat_context(),index,model=model,gateway=self.idea_chat_gateway())
        self.show_conversation();self.status.set('已删除整条信息；可在右键菜单恢复最近删除')
        return index
    def restore_latest_bubble_message(self):
        """恢复当前模型聊天页最近删除的一条完整消息。"""
        import idea_chat
        row=idea_chat.restore_latest_removed(self.idea_chat_context(),model=self.displayed_chat_model(),gateway=self.idea_chat_gateway())
        self.show_conversation();self.status.set('已恢复最近删除的整条信息')
        return row
    def clear_bubble_view(self):
        """压缩当前聊天的模型上下文并隐藏旧消息；刷新仅恢复原文显示。"""
        if getattr(self,'_bubble_edit',None):self.finish_bubble_edit()
        import idea_chat
        from collections import Counter
        model=self.displayed_chat_model()
        rows=idea_chat.compact_context(self.idea_chat_context(),model=model,gateway=self.idea_chat_gateway()) if self.root else []
        hidden=getattr(self,'_idea_hidden_messages',{})
        hidden[self.bubble_view_key(model)]=Counter(json.dumps({k:v for k,v in row.items() if k!='context_compacted'},sort_keys=True,ensure_ascii=False) for row in rows)
        self._idea_hidden_messages=hidden
        box=self.idea_log
        self._idea_view_generation=getattr(self,'_idea_view_generation',0)+1
        for job in getattr(self,'_idea_view_after_jobs',()):
            try:box.after_cancel(job)
            except tk.TclError:pass
        self._idea_view_after_jobs=[]
        self._bubble_click=None
        self._bubble_rows=[];self._bubble_full={}
        box.configure(state='normal')
        box.delete('1.0','end')
        for name in [one for one in box.tag_names() if one.startswith('bubble_')]:
            box.tag_delete(name)
        self.status.set('已清屏并压缩历史上下文（本地摘录）；完整聊天已保留，点击“刷新”可重新显示。')
    def bubble_view_key(self,model):
        """清屏范围按项目和模型隔离，只在本次应用会话内保存。"""
        return (str(Path(self.root).resolve()) if self.root else '',
                getattr(model, 'model_id', '') or str(model or '').strip())
    def update_idea_attachment_status(self):
        """仅展示用户已选择的文件名；路径和正文不出现在界面或聊天记录。"""
        self.refresh_uploaded_idea_attachments()
        label=getattr(self,'idea_attachment_status',None)
        if label is None:return
        prepared=getattr(self.idea_chat_controller,'attachment_details',())
        from idea_attachments import display_name
        details=[('%s（原文件，将由 Agent 自行读取）' % display_name(name) if count is None
                  else '%s（%d 字）' % (name, count)) for name,count in prepared]
        if not details:
            import idea_attachments
            from stage_execution_service import idea_attachment_local_mode
            for value in getattr(self,'idea_attachment_paths',()):
                if idea_attachment_local_mode(self.root):
                    details.append('%s（原文件，将由 Agent 自行读取）' % display_name(value))
                    continue
                try:details.append('%s（%d 字）' % (Path(value).name, len(idea_attachments.read_source(Path(value)))))
                except (OSError, ValueError):continue
        label.set(('已引用：'+'、'.join(details)) if details else '')
        # 未附档时不保留一整行空白；发送／阶段配置即可紧贴输入框。选择文件后才
        # 显示文件名，且仍不暴露本地路径。
        widget=getattr(self,'idea_attachment_status_label',None)
        row=getattr(self,'idea_input_row',None)
        if widget is None or row is None:return
        if details:
            if not widget.winfo_manager():widget.pack(anchor='w',pady=(1,0),after=row)
        elif widget.winfo_manager():
            widget.pack_forget()
    def refresh_uploaded_idea_attachments(self):
        """上传库与本轮引用分开显示，发送后仍可管理项目副本。"""
        panel=getattr(self,'idea_uploaded_panel',None)
        if panel is None or not panel.winfo_exists():return
        from stage_execution_service import stage_idea_attachment_paths
        from idea_attachments import archive_pair, display_name
        from tkinter import font as tkfont
        table=self.idea_uploaded_table
        # 原件创建时间代表入库顺序，不让转换稿后续编辑改变显示顺序。
        def upload_order(path):
            original,_converted=archive_pair(path)
            archived=original if original.is_file() else path
            return archived.stat().st_ctime_ns,path.name
        paths=sorted(stage_idea_attachment_paths(self.root),key=upload_order)
        self._idea_uploaded_selected=getattr(self,'_idea_uploaded_selected',set()).intersection(paths)
        children=table.tree.get_children()
        if children:table.tree.delete(*children)
        self._idea_uploaded_paths={str(index):path for index,path in enumerate(paths)}
        table.tree.configure(columns=tuple(self._idea_uploaded_paths))
        face=tkfont.Font(font=FONTS['body'])
        values=[]
        for index,path in enumerate(paths):
            label=('☑ ' if path in self._idea_uploaded_selected else '☐ ')+display_name(path)
            table.tree.column(str(index),width=face.measure(label)+SPACING['xl'],stretch=False)
            values.append(label)
        if paths:table.tree.insert('', 'end', iid='attachments', values=values)
        table.refresh_empty_state()
        self.idea_attachment_delete_button.state(['!disabled'] if self._idea_uploaded_selected else ['disabled'])
        if paths:
            if not panel.winfo_manager():panel.pack(fill='x',pady=(SPACING['xs'],SPACING['none']),after=self.idea_input_row)
        else:panel.pack_forget()
    def uploaded_idea_attachment_at(self,event):
        tree=self.idea_uploaded_table.tree
        if tree.identify_row(event.y)!='attachments':return None
        column=tree.identify_column(event.x)
        return str(int(column[1:])-1) if column and column!='#0' else None
    def toggle_uploaded_idea_attachment(self,column):
        path=self._idea_uploaded_paths.get(column)
        if path is None:return 'break'
        from idea_attachments import display_name
        selected=self._idea_uploaded_selected
        if path in selected:selected.remove(path)
        else:selected.add(path)
        self.idea_uploaded_table.tree.set('attachments',column,('☑ ' if path in selected else '☐ ')+display_name(path))
        self.idea_attachment_delete_button.state(['!disabled'] if selected else ['disabled'])
        return 'break'
    def choose_idea_attachments(self):
        """选择创意附档；分模式准入、归档和解析均在后台进行。"""
        paths=self.file_dialog.open_files(
            title='选择要提交给模型的创意附档', parent=self.win,
            filetypes=[('文本、Office 与 PDF', '*.txt *.md *.markdown *.doc *.docx *.xls *.xlsx *.ppt *.pptx *.pdf *.json *.csv *.yaml *.yml *.log'),
                       ('所有文件', '*.*')])
        if not paths:return ()
        self.idea_chat_controller.start_attachment_preparation(self.root, paths)
        if getattr(self,'idea_send',None) is not None:self.idea_send.state(['disabled'])
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
    def bubble_edit_position_allowed(self,box,index,selection=True):
        """编辑态的插入点／选区只能落在正文标记内，气泡外的标题和控件永远只读。"""
        edit=getattr(self,'_bubble_edit',None)
        if not edit or edit.get('box') is not box:return True
        try:
            if selection:
                ranges=box.tag_ranges('sel')
                if len(ranges)>=2 and (box.compare(ranges[0],'<',edit['start']) or
                                       box.compare(ranges[-1],'>',edit['end'])):
                    return False
            return not (box.compare(index,'<',edit['start']) or box.compare(index,'>',edit['end']))
        except tk.TclError:return False
    def guard_bubble_edit_key(self,event):
        """聊天记录常态只读；编辑时也阻止内容越过当前气泡正文边界。"""
        edit=getattr(self,'_bubble_edit',None)
        if not edit or edit.get('box') is not event.widget:
            # 只读记录区仍应保留 Tk 原生的阅读导航；普通字符才需要拦截，
            # 防止焦点停在记录区时意外改写内容。
            if event.keysym in {'Up','Down','Left','Right','Prior','Next',
                                'Home','End','Tab','ISO_Left_Tab'}:
                return None
            return 'break'
        box=event.widget
        try:insert=box.index('insert')
        except tk.TclError:return 'break'
        if not self.bubble_edit_position_allowed(box,insert):return 'break'
        if event.keysym=='BackSpace' and not box.tag_ranges('sel') and box.compare(insert,'<=',edit['start']):
            return 'break'
        if event.keysym=='Delete' and not box.tag_ranges('sel') and box.compare(insert,'>=',edit['end']):
            return 'break'
        return None
    def guard_bubble_edit_pointer(self,event):
        """只在拖选越出正文时限制边界，正文内的选择完全交给 Tk。"""
        edit=getattr(self,'_bubble_edit',None)
        box=event.widget
        if not edit or edit.get('box') is not box:return None
        try:point=box.index('@%d,%d'%(event.x,event.y))
        except tk.TclError:return 'break'
        if not (box.compare(point,'<',edit['start']) or box.compare(point,'>',edit['end'])):
            return None
        if box.compare(point,'<',edit['start']):point=edit['start']
        else:point=edit['end']
        box.mark_set('insert',point)
        return None
    def start_bubble_edit(self,event,index,name):
        """单击消息正文后直接编辑；不再弹出编辑或删除窗口。"""
        if not isinstance(index,int):return 'break'
        box=event.widget
        if getattr(self,'_bubble_edit',None):self.finish_bubble_edit()
        ranges=box.tag_ranges(name)
        if len(ranges)<2:return 'break'
        import idea_chat
        model=self.displayed_chat_model()
        rows=idea_chat.load(self.idea_chat_context(),model=model,gateway=self.idea_chat_gateway())
        if not 0<=index<len(rows):
            raise ValueError('这条对话已不存在，请刷新后重试')
        # 折叠的长消息进入编辑时先还原全文，避免只修改预览那几行。
        record=getattr(self,'_bubble_full',{}).get(name,{})
        original=str(record.get('text') or rows[index].get('text') or '').strip()
        box.configure(state='normal',cursor='xterm')
        box.delete(ranges[0],ranges[-1])
        box.insert(ranges[0],original,name)
        body_end=box.index('%s+%dc'%(ranges[0],len(original)))
        box.insert(body_end,'\n',name)
        start,end='bubble_edit_start','bubble_edit_end'
        box.mark_set(start,ranges[0]);box.mark_gravity(start,'left')
        box.mark_set(end,body_end);box.mark_gravity(end,'right')
        self._bubble_edit={'box':box,'index':index,'start':start,'end':end,'original':original,
                           'model':model,'context':self.idea_chat_context()}
        try:box.mark_set('insert',box.index('@%d,%d'%(event.x,event.y)))
        except tk.TclError:box.mark_set('insert',start)
        box.focus_set()
        self.status.set('正在直接编辑消息；只能改气泡正文，删空后点击其他位置即可删除。')
        return 'break'
    def finish_bubble_edit(self,event=None,commit=True):
        """把当前气泡内的直接编辑同步到对话记录；空内容表示删除该条。"""
        edit=getattr(self,'_bubble_edit',None)
        if not edit:return None
        self._bubble_edit=None
        box=edit['box']
        try:value=box.get(edit['start'],edit['end']).strip()
        except tk.TclError:value=edit['original']
        try:box.mark_unset(edit['start'],edit['end'])
        except tk.TclError:pass
        if not commit:
            self.show_conversation()
            self.status.set('已取消修改这条对话')
            return 'break'
        if value==edit['original']:
            self.show_conversation()
            return 'break'
        import idea_chat
        model=edit['model']
        if value:idea_chat.replace(edit['context'],edit['index'],value,model=model,gateway=self.idea_chat_gateway());notice='已修改这条对话'
        else:idea_chat.remove(edit['context'],edit['index'],model=model,gateway=self.idea_chat_gateway());notice='已删除这条对话'
        self.show_conversation()
        self.status.set(notice)
        return 'break'
    def add_bubble(self,box,row,index):
        """把一条对话排成微信式左右气泡，并在顶部标出说话者／模型名。"""
        raw_text=str(row.get('text') or '')
        # 软件示例是只读、可复制的参考文本；不能为了普通聊天气泡的排版
        # ``strip`` 掉它首尾的换行或空格，否则展示内容已不再等于程序提供的示例。
        # 普通消息仍沿用既有的首尾空白清理，避免空白消息生成气泡。
        text=raw_text if index == 'example' else raw_text.strip()
        if not text.strip():return
        mine=str(row.get('role'))=='user'
        left,right=self.bubble_margins(box,text,mine)
        name='bubble_'+str(index)
        # 页面刚建好时框子还没量过宽度，这一条要留着，等真实宽度下来再摆一次（见 refit_bubbles）。
        getattr(self,'_bubble_rows',[]).append((name,text,mine))
        # 用户气泡仍贴右侧；正文一律由气泡左边开始，长句更容易读。
        align='left'
        example=index == 'example'
        model_back, model_meta = self.model_chat_colors(row.get('model'))
        look=dict(justify=align,
                  background='' if example else (COLORS['success_subtle'] if mine else model_back),
                  foreground=COLORS['text_secondary'] if example else COLORS['text_primary'],
                  lmargin1=left,lmargin2=left,rmargin=right,
                  spacing1=2,spacing2=1,spacing3=4,font=BUBBLE_FONT,wrap='word')
        # Tk 默认连边距一起刷成气泡色，那样每条都是满屏一条；把两边留白按框底的白走，
        # 色块才贴着字（-lmargincolor／-rmargincolor，Tk 8.6 起）。
        bubble_padding=0 if example else BUBBLE_PAD
        margin_back=box.cget('bg') if example else BUBBLE_BACK
        try:box.tag_configure(name,borderwidth=bubble_padding,relief='flat',
                              lmargincolor=margin_back,rmargincolor=margin_back,**look)
        except tk.TclError:box.tag_configure(name,**look)
        box.tag_configure(name+'_meta',justify=align,foreground=COLORS['text_muted'] if example else (model_meta if not mine else COLORS['text_secondary']),
                          lmargin1=left,lmargin2=left,rmargin=right,spacing1=4,spacing3=1,
                          font=BUBBLE_TIME_FONT)
        box.insert('end',self.model_name(row)+'\n',name+'_meta')
        import idea_chat
        injection = idea_chat.skill_injection_summary(row)
        if injection:
            box.insert('end', injection+'\n', name+'_meta')
        stamp=self.bubble_time(row.get('at'))
        if stamp:
            box.tag_configure(name+'_time',justify=align,foreground=COLORS['text_muted'],
                              lmargin1=left,lmargin2=left,rmargin=right,spacing1=0,spacing3=1,font=BUBBLE_TIME_FONT)
            box.insert('end',stamp+'\n',name+'_time')
        # 软件示例是用户填写前唯一的完整参考，不能被折叠；真实长对话仍保持收起功能。
        preview,folded=(text,False) if index=='example' else self.bubble_preview(text)
        self._bubble_full[name]={'text':text,'preview':preview,'expanded':not folded}
        box.insert('end',preview+'\n',name)
        if folded:
            toggle=name+'_toggle'
            # 操作在本条气泡的右下角，而非正文下方左侧；它属于 Text 内容，滚动时和
            # 对应消息一起移动，不会遮住用户正在阅读的其它消息。
            box.tag_configure(toggle,justify='right',foreground=COLORS['primary'],underline=True,
                              lmargin1=left,lmargin2=left,rmargin=right,spacing1=0,spacing3=3,
                              font=BUBBLE_TIME_FONT)
            box.insert('end','展开全文\n',toggle)
            box.tag_bind(toggle,'<Button-1>',lambda event,b=box,n=name:self.toggle_bubble(b,n))
            box.tag_bind(toggle,'<Enter>',lambda event,b=box:b.configure(cursor='hand2'))
            box.tag_bind(toggle,'<Leave>',lambda event,b=box:b.configure(cursor='xterm'))
        if isinstance(index,int):
            # 只允许编辑真实消息；只读软件示例仍可拖选复制。
            box.tag_bind(name,'<Button-1>',lambda event,i=index,n=name:self.begin_bubble_click(event,i,n))
            box.tag_bind(name,'<Enter>',lambda event,b=box:b.configure(cursor='hand2'))
            box.tag_bind(name,'<Leave>',lambda event,b=box:b.configure(cursor='xterm'))
    def show_thinking(self,model):
        """模型正在请求时，在最近一条消息下方放临时状态；不会写入对话记录。"""
        self._thinking_model=model if str(model or '').strip() else 'AI 助手'
        self.show_conversation()
    def clear_thinking(self):
        if getattr(self,'_thinking_model',''):
            self._thinking_model=''
            self.show_conversation()
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
                usage_label.set_text(idea_chat.usage_summary(rows))
                tip = getattr(self, 'idea_usage_tip', None)
                if tip is not None:tip.text = usage_label.full_text
            session_label = getattr(self, 'idea_session_label', None)
            if session_label is not None and session_label.winfo_exists():
                from writing_api import chat_session_summary
                session_label.set_text(chat_session_summary(self.root, model) if self.root else '')
                tip = getattr(self, 'idea_session_tip', None)
                if tip is not None:tip.text = session_label.full_text
            thinking=getattr(self,'_thinking_model','')
            if thinking and self.bubble_view_key(thinking) == self.bubble_view_key(self.displayed_chat_model()):
                name='bubble_thinking'
                left,right=self.bubble_margins(box,thinking,False)
                self._bubble_rows.append((name,thinking,False))
                box.tag_configure(name+'_thinking',justify='left',foreground=COLORS['text_secondary'],
                                  lmargin1=left,lmargin2=left,rmargin=right,spacing1=2,spacing3=3,
                                  font=BUBBLE_TIME_FONT)
                box.insert('end',thinking+' 模型正在思考…\n',name+'_thinking')
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
            if hidden is None:
                self.add_bubble(box,{'role':'assistant','model':'示例模板','text':self.idea_template},'example')
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
                self.open_flow_agent('writing', '简报信息提取', request['prompt'], request['prompt'], intake_only=True)
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
            ttk.Label(row, text=label).pack(side='left', padx=(0, SPACING['sm']))
            entry = TextArea(row, height=2, width=50, wrap='word')
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
            def received(result):
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
                self.show_conversation();self.update_script_download_button()
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
                    self.status.set('已收到 '+model+' 的回复；完整剧本可下载保存。')
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
            self.status.set(prefix+'已提交创意并启动剧本 Agent；模型回复完整剧本后可下载保存。')
        self.update_script_download_button()
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
            return controller.request_is_current(token) and not cancelled.is_set() and self.root == project
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
            claimed = claim_stage_process_slot(request['ticket'])
            if claimed['state'] == 'granted':
                dispatch(claimed['slot'])
            elif claimed['state'] == 'queued':
                self.status.set('模型请求排队中（第%d位），界面保持响应。' % claimed['position'])
                pending['timer'] = self.win.after(200, poll_slot)
            else:
                receive({'ok': False, 'error': claimed.get('reason', '模型请求已取消')})
        if request['state'] == 'granted':
            dispatch(request['slot'])
        else:
            self.status.set('模型请求排队中（第%d位），界面保持响应。' % request['position'])
            pending['timer'] = self.win.after(200, poll_slot)
    def script_agent_processes(self):
        """返回当前剧本阶段由本窗口启动、仍在运行的 Agent 进程。"""
        sessions=getattr(self,'flow_processes',{})
        return [(key,process) for key,process in sessions.items()
                if len(key)>1 and key[1]=='writing' and process.poll() is None]
    def interrupt_script_agent(self):
        """中断当前剧本 API 请求或本窗口启动的剧本 Agent，不影响其他制作阶段。"""
        self._idea_semantic_pending = None
        api_active=getattr(self,'_idea_requesting',False)
        processes=self.script_agent_processes()
        launching=getattr(self,'_script_agent_launching',False)
        if not api_active and not processes and not launching:
            self.status.set('当前没有可中断的剧本 Agent 调用。')
            return False
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
        detail=('，已结束进程 '+', '.join(stopped)) if stopped else ''
        info=self.background_tasks.cancellation_status() if api_active else None;notice=(' '+info['text']) if info is not None else '';preserved='已返回正文会归档到 responses/ 供核对；' if api_active else '';self.status.set('已中断剧本 Agent 调用'+detail+'；'+preserved+'本机不再把这次回复写入界面或正式采用，可修改创意后重新发送。'+notice)
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
    def open_flow_agent(self,stage,label,prompt,followup=None,on_receipt=None,_config=None,*,intake_only=False,new_session=False):
        from workflow_settings import current,writer_style_summary
        from workflow_engines import prompt_with_settings,launch_interactive
        from agent_dispatch import signature,claim,finish,outcome,retryable
        if self.worker:raise ValueError('正在打开或发送 Agent 任务，请稍候；未重复发送。')
        # 「发送待核实」的安全重试必须沿用第一次已经解析的引擎。原来递归重进时会重新
        # 读取阶段配置，恰逢面板刷新／配置回退就可能把 Claude 的续发错误地交给 Codex。
        if stage == 'writing' and not intake_only and _config is None:
            from workflow_settings import validate_selected_skills
            validate_selected_skills(self.root, stage)
        config=_config if _config is not None else current(self.root,stage);followup=followup if followup is not None else prompt
        if stage == 'writing' and not intake_only:
            from workflow_settings import freeze_skills
            config = freeze_skills(config)
        native_claude = config['engine'] in ('claude-desktop-app', 'desktop-app')
        bounded_writing = stage == 'writing' and config['engine'] == 'claude'
        new_session = bool(new_session and stage == 'writing' and config['engine'] == 'claude' and not intake_only)
        use_cli = not native_claude and (config['engine']!='codex' or config['program'] or config['model'])
        # CLI 继续复用同一进程；提取结束后不能占住唯一槽位又排队启动剧本进程。
        setup_key=hashlib.sha256((json.dumps(config,sort_keys=True)+('brief-intake' if intake_only and not use_cli else '')).encode()).hexdigest()
        from codex_tasks import prepare_task
        project=self.root
        name=next((p['name'] for p in self.projects.info['projects'] if Path(p['path'])==project),project.name)
        title=name+' '+label
        if config['engine']=='qwen':
            from qwen_adapter import window_title
            title=window_title(name,stage,getattr(self,'page_index',None))
        def build():
            from workflow_context import continuation_instruction,snapshot
            from stage_execution_service import project_context
            from workflow_context_controller import request_stage_instruction
            from workflow_context_budget import prepare_request_context
            if config['engine']=='codex':
                from codex_skill_sync import sync_codex_skills
                sync_result=sync_codex_skills()
                if sync_result['errors'] or sync_result['conflicts']:
                    raise ValueError('Codex 技能同步未完成：'+ '; '.join(
                        sync_result['errors']+sync_result['conflicts']))
            data={} if intake_only or bounded_writing else snapshot(project_context(project))
            receipt=claim(project,signature(stage,prompt,followup,config,data),title)
            if on_receipt is not None:on_receipt(receipt)
            if receipt['duplicate'] and use_cli:return {'receipt':receipt}
            if not use_cli:receipt['duplicate']=False
            try:
                if stage=='previs':
                    from native_apps import open_blender
                    open_blender()
                if intake_only:
                    # 提取阶段不得附加“直接生成剧本”的 SKILL/阶段交付指令。
                    full,budget=prepare_request_context(prompt,stage,'brief_intake',report=True)
                    continuation,continuation_budget=prepare_request_context(followup,stage,'brief_intake',report=True)
                elif bounded_writing:
                    full,budget=prepare_request_context(
                        prompt_with_settings(prompt,config,stage=stage),stage,'explicit_writing_inputs',report=True)
                    continuation,continuation_budget=prepare_request_context(
                        prompt_with_settings(followup,config,stage=stage),stage,'explicit_writing_inputs',report=True)
                else:
                    context,strategy=request_stage_instruction(project,stage,data)
                    full,budget=prepare_request_context(
                        prompt_with_settings(context+prompt,config,stage=stage),stage,strategy,report=True)
                    continuation,continuation_budget=prepare_request_context(
                        prompt_with_settings(continuation_instruction(project,stage,data)+followup,config,stage=stage),
                        stage,'continuation_summary',report=True)
                finish(receipt,'preparing','',skill_injection=config.get('skill_injection'),context_budget={
                    'initial':budget,'continuation':continuation_budget})
                if native_claude:
                    from codex_tasks import task_file_reference
                    from stage_execution_service import register_download_inbox
                    # Claude Desktop 常常不能直接写本机路径、只给下载文件：要求下载件沿用目标文件名，
                    # 并登记目标，助手会从「下载」文件夹按文件名收回到原位置。
                    full = full + ('\n\n【交付方式】优先直接写入任务中给出的目标路径；若无法写入本机文件，'
                                   '请以可下载文件交付，文件名必须与目标路径的文件名完全一致，'
                                   '用户下载后助手会自动放回对应位置。')
                    task_file = task_file_reference(project, stage, full)
                    try:register_download_inbox(project, full)
                    except (OSError, ValueError) as exc:LOGGER.warning('下载收件箱登记失败：%s', exc)
                    reference = (f'请读取并执行本次任务文件：{task_file}\n'
                                 '其中引用的 SKILL 和附件按任务需要读取，不重复加载无关内容。'
                                 '若无法读取本地文件，请提示启用文件访问并授权对应目录，或请用户上传文件；不要假定已读。')
                    return {'receipt':receipt,'prompt':reference,'task_file':str(task_file)}
                if use_cli:return {'receipt':receipt,'prompt':full,'followup':continuation,
                                   'context_budget':{'initial':budget,'continuation':continuation_budget}}
                result=prepare_task(project,title,stage,full,followup=continuation,setup_key=setup_key,
                                    delivery_summary='' if intake_only else writer_style_summary(config,stage))
                result['receipt']=receipt;result['context_budget']={
                    'initial':budget,'continuation':continuation_budget};return result
            except Exception as exc:finish(receipt,'failed',str(exc));raise
        def dispatch(result):
            receipt=result['receipt']
            if receipt['duplicate']:
                sessions=getattr(self,'flow_processes',{})
                key=(str(project),stage,config['engine'],setup_key)
                live=key in sessions and sessions[key].poll() is None
                if retryable(receipt,live):
                    finish(receipt,'failed','上次发送结果未确认，且对应 Agent 窗口已关闭')
                    self.status.set('上次 Agent 发送未确认且窗口已关闭，正在自动重新启动…')
                    self.open_flow_agent(stage,label,prompt,followup,on_receipt,_config=config,intake_only=intake_only,new_session=new_session)
                    return
                if not live:
                    finish(receipt,'failed','上次 Agent 窗口已关闭，请重新点击启动')
                    self.notifier.info('上次 Agent 窗口未在运行，任务状态已重置；请再次点击“手动制作分镜”。', title='请重新点击', modal=True);return
                state={'preparing':'正在打开或发送','sent':'已发送','uncertain':'发送结果待核实'}[receipt['state']]
                self.status.set('相同任务'+state+'，已复用记录，本次不重复发送。请在对应 Agent 窗口继续。');return
            if use_cli:
                launch_cli(result);return
            try:done(result)
            except Exception as exc:finish(receipt,'failed',str(exc));raise
        def launch_cli(result):
            receipt=result['receipt'];full=result['prompt'];continuation=result['followup']
            sessions=getattr(self,'flow_processes',{});key=(str(project),stage,config['engine'],setup_key)
            if key in sessions and sessions[key].poll() is None:
                if new_session:
                    def close_old():
                        from workflow_engines import close_for_restart
                        try:close_for_restart(project,sessions[key])
                        except Exception as exc:finish(receipt,'failed',str(exc));raise
                    def closed(_):
                        sessions.pop(key,None)
                        launch_cli(result)
                    self.status.set('正在结束空闲 Claude 会话，准备以新上下文重新创作…')
                    self.async_(close_old,closed);return
                def submit():
                    try:
                        if config['engine']=='qwen':
                            from qwen_adapter import submit_existing
                            text=submit_existing(sessions[key],continuation,title=title)
                            return {'ok':True,'reason':text,'send_dispatched':True}
                        from workflow_engines import submit_existing
                        return submit_existing(sessions[key],continuation,title=title)
                    except Exception as exc:
                        finish(receipt,'uncertain',str(exc));raise
                def submitted(value):
                    outcome(receipt,value);self.status.set(value['reason'])
                    if not value['ok']:self.notifier.info(value['reason'], title='请检查 Agent 输入框', modal=True)
                self.async_(submit,submitted);return
            def launched(result):
                sessions[key]=result['process'];self.flow_processes=sessions
                if stage=='writing':
                    self._script_agent_launching=False
                    self.update_script_interrupt_button()
                finish(receipt,'sent','启动时已传入初始任务',task_file=result['task_file'])
                self.status.set('已启动 '+result['engine']+'，初始任务已自动提交，可在窗口继续讨论。')
            def launch(slot=None):
                try:return launch_interactive(project,stage,title,full,config,followup=continuation,slot=slot,
                                              **({'new_session':True} if new_session else {}))
                except Exception as exc:finish(receipt,'failed',str(exc));raise
            from workflow_engines import request_stage_process_slot, claim_stage_process_slot
            request=request_stage_process_slot(project,stage)
            if request['state']=='granted':
                self.async_(lambda:launch(request['slot']),launched);return
            self.status.set('模型请求排队中（第%d位），界面保持响应。' % request['position'])
            def poll_slot():
                if getattr(self,'shutting_down',False) or getattr(self,'_closing',False):
                    finish(receipt,'failed','模型请求已在关闭时取消')
                    return
                claimed=claim_stage_process_slot(request['ticket'])
                if claimed['state']=='queued':
                    self.status.set('模型请求排队中（第%d位），界面保持响应。' % claimed['position'])
                    self.win.after(200,poll_slot);return
                if claimed['state']=='granted':
                    self.status.set('已获得模型请求槽位，正在启动…')
                    self.async_(lambda:launch(claimed['slot']),launched);return
                finish(receipt,'failed',claimed['reason'])
                self.status.set(claimed['reason'])
            self.win.after(200,poll_slot)
        def done(result):
            receipt=result['receipt']
            clipboard_text=result['prompt']
            task_file=result.get('task_file')
            if task_file and Path(task_file).is_file():
                try:clipboard_text=Path(task_file).read_text(encoding='utf-8')
                except OSError:clipboard_text=result['prompt']
            from prompt_window import copy_text
            copy_text(self.win,clipboard_text)
            if native_claude:
                from workflow_settings import find_program
                from platform_tools import launch_windows_app
                program = find_program(config)
                if config['engine'] == 'desktop-app':
                    app = config.get('display_model') or '桌面模型'
                    launch_windows_app(program, app)
                    message = '已打开 '+app+'，任务已复制到剪贴板；请切到该窗口粘贴并手动发送。'
                    finish(receipt,'prepared',message,task_file=task_file)
                    self.status.set(message)
                    self.notifier.info(message,title='请粘贴并发送')
                    return
                launch_windows_app(program, 'Claude Desktop')
                from codex_paste import paste_existing
                def claude_pasted(value):
                    finish(receipt,'prepared' if value['ok'] else 'failed',value['reason'],task_file=task_file)
                    self.status.set(value['reason'])
                    level=getattr(self,'gate_level',None)
                    if value['ok'] and callable(level) and level()=='auto':
                        # 全自动不拦截 Claude Desktop：它只能由用户点发送，这里明确提示，
                        # 避免自动链看似停住却没有说明；状态栏原文也会转给三虎。
                        message=('三虎全自动：'+label+' 的任务已粘贴到 Claude Desktop，'
                                 '请切到 Claude Desktop 手动点击发送；完成后产物会自动收回。')
                        self.status.set(message)
                        self.notifier.warning(message,title='请手动发送')
                self.status.set('正在将本次任务粘贴到 Claude Desktop，请检查后手动发送…')
                self.async_(lambda:paste_existing(title,clipboard_text,program=program,deadline_seconds=45),claude_pasted)
                return
            if config.get('desktop_program'):
                from platform_tools import launch_windows_app
                launch_windows_app(config['desktop_program'], 'Codex 桌面')
            open_target(result['url'])
            from codex_paste import paste_existing
            def pasted(result):
                finish(receipt,'prepared' if result['ok'] else 'failed',result['reason'])
                self.status.set(result['reason'])
            self.async_(lambda:paste_existing(result['title'],clipboard_text,result.get('draft_prompt',''),result.get('project',''),deadline_seconds=45 if result.get('mode')=='new' else 15),pasted)
            self.status.set('正在将本次任务粘贴到 GPT 桌面，请在窗口中手动点击发送…')
        self.async_(build,dispatch)
