"""想法对话的气泡方法集（从 desktop_idea_chat.IdeaChatMixin 原样迁出，R1806）。

方法体未改、self 语义不变，IdeaChatMixin 通过继承 IdeaBubblesMixin 获得；仍与 Tk 控件紧耦合，故与 desktop_idea_chat 同属 L4。"""
import json
import tkinter as tk
from ui_motion import Spinner
from ui_tokens import COLORS, ICON_COPY, ICON_DELETE, ICON_FONT, ICON_REWIND, SPACING
from pathlib import Path
from idea_chat_controller import bubble_timestamp, collapse_preview


BUBBLE_BACK=COLORS['background_card']  # 内容框的底色：气泡两边的留白用它刷，色块才贴着字
BUBBLE_FONT=('Microsoft YaHei UI',10)
BUBBLE_TIME_FONT=('Microsoft YaHei UI',9)
BUBBLE_PAD=10          # 气泡里文字与色块边缘的距离
BUBBLE_GAP=14          # 气泡离画面左右两边各留这么多
BUBBLE_FLOOR=70        # 气泡最窄也有这么宽
BUBBLE_LINE=13         # 量不出字宽时的兜底：一个字大约这么宽
BUBBLE_MAX_RATIO=0.84  # 字再多，色块也不铺满整行；比例取自用户认可的长消息气泡（占记录区约 84%）
BUBBLE_SLACK=26        # 量字宽只是估算（字号、全角半角都有出入），留一截余地，
                       # 免得一句话末了一个字被挤到下一行


class IdeaBubblesMixin:
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
            for tag in (name,name+'_time',name+'_meta',name+'_toggle',name+'_thinking',name+'_actions'):
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
        # Claude Code 桌面版式（REQ-S01-65）：用户在右、按字宽收紧；模型在左、按可用宽度铺开。
        if mine:
            return max(0,width-BUBBLE_GAP-body),BUBBLE_GAP
        return BUBBLE_GAP,BUBBLE_GAP
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
        # 悬停图标是 Text 里的占位字符，拖选复制时去掉，不把私用区字形混进正文。
        text=''.join(char for char in text if char not in (ICON_COPY,ICON_DELETE,ICON_REWIND))
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
    def copy_bubble_message(self,index):
        """消息左下角「复制」图标：只取持久化的正文，不把界面元信息混进去。"""
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
    def rewind_bubble_message(self,index):
        """消息下方「回退」图标：把这条用户消息放回输入框，可改后重新发送；聊天记录不动。"""
        import idea_chat
        rows=idea_chat.load(self.idea_chat_context(),model=self.displayed_chat_model(),gateway=self.idea_chat_gateway())
        if not 0<=index<len(rows):return None
        text=str(rows[index].get('text') or '')
        box=getattr(self,'idea_input',None)
        if not text or box is None or not box.winfo_exists():return None
        box.delete('1.0','end');box.insert('1.0',text);box.focus_set()
        self.status.set('已把这条消息放回输入框，修改后可重新发送')
        return text
    def delete_bubble_message(self,index):
        """消息左下角「删除」图标：移出当前对话，并保留最近删除恢复记录。"""
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

    def guard_bubble_key(self,event):
        """聊天记录只读：保留 Tk 原生的阅读导航和选字，其余按键一律拦下。"""
        if event.keysym in {'Up','Down','Left','Right','Prior','Next','Home','End','Tab','ISO_Left_Tab'}:
            return None
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
        # 与 Claude Code 桌面版一致：用户气泡贴右侧，名字、正文、引用行和底行都右对齐；模型回复左对齐。
        align='right' if mine else 'left'
        example=index == 'example'
        _model_back, model_meta = self.model_chat_colors(row.get('model'))
        # REQ-S01-65：与 Claude Code 桌面版一致，用户和模型的消息都不铺底色，靠左右位置区分。
        look=dict(justify=align,background='',
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
        # SKILL 注入与时间合成一行，放在这条消息的最下面（复制／删除图标之上）。
        import idea_chat
        footer='  '.join(part for part in (idea_chat.skill_injection_summary(row),self.bubble_time(row.get('at'))) if part)
        if footer:
            box.tag_configure(name+'_time',justify=align,foreground=COLORS['text_muted'],
                              lmargin1=left,lmargin2=left,rmargin=right,spacing1=0,spacing3=1,font=BUBBLE_TIME_FONT)
            box.insert('end',footer+'\n',name+'_time')
        if isinstance(index,int):
            self.add_bubble_actions(box,name,index,left,right,rewindable=mine)
    def add_bubble_actions(self,box,name,index,left,right,rewindable=False):
        """REQ-S01-66：正文左下角的复制／删除／回退图标；平时与框底同色占位，悬停这条消息才显出来。"""
        actions=name+'_actions'
        box.tag_configure(actions,lmargin1=left,lmargin2=left,rmargin=right,spacing1=0,spacing3=4,font=ICON_FONT)
        buttons=[('_copy',ICON_COPY,'copy_bubble_message'),('_delete',ICON_DELETE,'delete_bubble_message')]
        if rewindable:buttons.append(('_rewind',ICON_REWIND,'rewind_bubble_message'))
        for suffix,icon,handler in buttons:
            tag=name+suffix
            box.tag_configure(tag,foreground=box.cget('bg'))
            box.insert('end',icon,(actions,tag))
            box.insert('end','  ',actions)
            box.tag_bind(tag,'<Button-1>',lambda event,i=index,h=handler:(self.safe(lambda:getattr(self,h)(i)),'break')[1])
            box.tag_bind(tag,'<Enter>',lambda event,b=box:b.configure(cursor='hand2'),add='+')
            box.tag_bind(tag,'<Leave>',lambda event,b=box:b.configure(cursor='xterm'),add='+')
        box.insert('end','\n',actions)
        for tag in (name,name+'_meta',name+'_time',name+'_toggle',actions):
            box.tag_bind(tag,'<Enter>',lambda event,b=box,n=name:self.show_bubble_actions(b,n,True),add='+')
            box.tag_bind(tag,'<Leave>',lambda event,b=box,n=name:self.show_bubble_actions(b,n,False),add='+')
    def show_bubble_actions(self,box,name,visible):
        """只改图标前景色，不增删字符，悬停时排版高度不跳。"""
        color=COLORS['text_muted'] if visible else box.cget('bg')
        for suffix in ('_copy','_delete','_rewind'):
            try:box.tag_configure(name+suffix,foreground=color)
            except tk.TclError:pass
    def show_thinking(self,model):
        """模型正在请求时，在最近一条消息下方放临时状态；不会写入对话记录。"""
        self._thinking_model=model if str(model or '').strip() else 'AI 助手'
        self.show_conversation()
    def clear_thinking(self):
        if getattr(self,'_thinking_model',''):
            self._thinking_model=''
            self.end_stream()
            self.drop_thinking_spinner()
            self.show_conversation()
    def add_thinking_line(self,box,thinking):
        """在对话末尾画「<模型> 模型正在思考…」，行首内嵌转圈（仿 Claude Code 桌面版）。"""
        name='bubble_thinking'
        left,right=self.bubble_margins(box,thinking,False)
        self._bubble_rows.append((name,thinking,False))
        box.tag_configure(name+'_thinking',justify='left',foreground=COLORS['text_secondary'],
                          lmargin1=left,lmargin2=left,rmargin=right,spacing1=2,spacing3=3,
                          font=BUBBLE_TIME_FONT)
        start=box.index('end-1c')
        spinner=Spinner(box,background=box.cget('bg'));spinner.start()
        box.window_create('end',window=spinner,align='center',padx=SPACING['xs'])
        self._thinking_spinner=spinner
        box.insert('end',thinking+' 模型正在思考…\n',name+'_thinking')
        box.tag_add(name+'_thinking',start,'end-1c')
        # 已收到的流式文字紧跟在状态行下面；重绘（例如窗口变化）时从缓冲里补回。
        box.tag_configure('bubble_stream',justify='left',foreground=COLORS['text_primary'],font=BUBBLE_FONT,
                          lmargin1=left,lmargin2=left,rmargin=right,spacing1=2,spacing2=1,spacing3=4,wrap='word')
        box.mark_set('stream_start','end-1c');box.mark_gravity('stream_start','left')
        self._stream_shown=0
        self.refresh_stream_text(box)
    def begin_stream(self):
        """一次直连 API 请求开始：清空流式缓冲并开始定时把新文字画到聊天框末尾。"""
        self._stream_parts=[];self._stream_shown=0
        self._stream_generation=getattr(self,'_stream_generation',0)+1
        self.poll_stream(self._stream_generation)
    def stream_call(self,fn,*args,**kwargs):
        """工作线程里调用 fn，期间模型返回的文字片段交给 push_stream。"""
        import writing_stream
        with writing_stream.stream_to(self.push_stream):return fn(*args,**kwargs)
    def push_stream(self,chunk):
        """工作线程调用：只往缓冲追加，不碰 Tk；界面由 poll_stream 在主线程里取。"""
        parts=getattr(self,'_stream_parts',None)
        if parts is not None and chunk:parts.append(str(chunk))
    def end_stream(self):
        self._stream_parts=None;self._stream_shown=0
        self._stream_generation=getattr(self,'_stream_generation',0)+1
    def poll_stream(self,generation):
        if generation!=getattr(self,'_stream_generation',0) or getattr(self,'_stream_parts',None) is None:return
        box=getattr(self,'idea_log',None)
        try:
            if box is not None and box.winfo_exists():
                self.refresh_stream_text(box)
                self.win.after(80,lambda:self.poll_stream(generation))
        except tk.TclError:pass
    def refresh_stream_text(self,box):
        """把缓冲里新增的文字补到状态行下面；只追加新文字，不重绘整个聊天记录。"""
        parts=getattr(self,'_stream_parts',None)
        if not parts or 'stream_start' not in box.mark_names() or not getattr(self,'_thinking_model',''):return
        if len(parts)==getattr(self,'_stream_shown',0) and box.compare('stream_start','!=','end-1c'):return
        at_bottom=box.yview()[1]>=0.98
        text=''.join(parts)
        box.delete('stream_start','end-1c')
        box.insert('end-1c',text,'bubble_stream')
        self._stream_shown=len(parts)
        if at_bottom:box.see('end')
    def drop_thinking_spinner(self):
        """撤掉「模型正在思考」前的转圈；重绘前与回复落地时调用，重复调用安全。"""
        spinner=getattr(self,'_thinking_spinner',None)
        self._thinking_spinner=None
        if spinner is not None:
            try:spinner.destroy()
            except tk.TclError:pass
