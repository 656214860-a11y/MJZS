"""想法对话的气泡方法集（从 desktop_idea_chat.IdeaChatMixin 原样迁出，R1806）。

方法体未改、self 语义不变，IdeaChatMixin 通过继承 IdeaBubblesMixin 获得；仍与 Tk 控件紧耦合，故与 desktop_idea_chat 同属 L4。"""
import json
import tkinter as tk
from tkinter import ttk
from ui_motion import Spinner
from ui_tokens import COLORS, FONTS, ICON_COPY, ICON_DELETE, ICON_FONT, ICON_REWIND, SPACING
from pathlib import Path
from orchestrator.idea_chat_controller import ALL_MODELS, bubble_timestamp, collapse_preview, model_bar_items, model_bar_selection


BUBBLE_BACK=COLORS['background_card']  # 内容框的底色：气泡两边的留白用它刷，色块才贴着字
BUBBLE_FILL=COLORS['surface_hover']    # 气泡正文外框内的浅灰底（参考 DeepSeek 对话：正文框一圈淡底）
BUBBLE_FONT=('Microsoft YaHei UI',10)
BUBBLE_TIME_FONT=('Microsoft YaHei UI',9)
BUBBLE_PAD=10          # 气泡里文字与色块边缘的距离
BUBBLE_GAP=14          # 气泡离画面左右两边各留这么多
BUBBLE_FLOOR=70        # 气泡最窄也有这么宽
BUBBLE_LINE=13         # 量不出字宽时的兜底：一个字大约这么宽
BUBBLE_MAX_RATIO=0.84  # 字再多，色块也不铺满整行；比例取自用户认可的长消息气泡（占记录区约 84%）
BUBBLE_SLACK=26        # 量字宽只是估算（字号、全角半角都有出入），留一截余地，
                       # 免得一句话末了一个字被挤到下一行
# 模型目录条：一行紧凑标签，底色与聊天气泡框一致；高度按内容自适应，首建时给个占位值。
MODEL_BAR_FONT=FONTS['hint']
MODEL_BAR_HEIGHT=SPACING['xl']+SPACING['xs']


class IdeaBubblesMixin:
    def _clear_bubble_view(self, box, reset_width=True):
        """清空气泡框的行台账、气泡标签与文本；重绘前调用。清屏压缩沿用当前宽度，故不重置。"""
        self._bubble_rows=[]
        self._bubble_full={}
        if reset_width:
            self._bubble_width=int(box.winfo_width() or 0)
        box.configure(state='normal')
        for name in [one for one in box.tag_names() if one.startswith('bubble_')]:
            box.tag_delete(name)
        box.delete('1.0','end')
    def refit_bubbles(self,event=None):
        """第 69 期任务 1：窗口一改宽窄就重算气泡的左右边距——只动边距，
        上面的字和您正在写的那段一个字节都不碰。"""
        box=getattr(self,'idea_log',None)
        if box is None or not box.winfo_exists():return
        if event is not None and getattr(event,'widget',None) is not box:return
        width=int(box.winfo_width() or 0)
        if width<=1 or width==getattr(self,'_bubble_width',None):return
        self._bubble_width=width
        for name,text,mine,framed in getattr(self,'_bubble_rows',[]):
            left,right=self.bubble_margins(box,text,mine)
            pad=BUBBLE_PAD if framed else 0
            for tag in (name,name+'_time',name+'_meta',name+'_toggle',name+'_thinking',name+'_actions'):
                if tag==name:
                    # 正文 tag 带内边距，色块贴着字、跟着气泡左右分列。
                    l,r=left+pad,right+pad
                elif tag==name+'_time':
                    # 页脚整句要看得全：钉在对话区左右边沿，不跟用户气泡右移（见 add_bubble）。
                    l=r=BUBBLE_GAP
                else:
                    # 模型名／图标／展开等框外行贴着这条气泡的左边沿，不加内边距。
                    l,r=left,right
                try:box.tag_configure(tag,lmargin1=l,lmargin2=l,rmargin=r)
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
        # 左右分列（REQ-S01-65）：用户在右、按字宽收紧；模型在左、按可用宽度铺开。
        # 分列只由这里的边距决定，正文的 justify 一律左对齐（见 add_bubble）。
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
    def _bubble_tag_index(self, tag):
        """气泡标签「bubble_<n>」里的序号；不是这种标签返回 None。"""
        parts=str(tag).split('_')
        if len(parts)>=2 and parts[0]=='bubble' and parts[1].isdigit():
            return int(parts[1])
        return None
    def bubble_target_at(self,box,event):
        """鼠标位置对应的真实消息；元信息和“展开全文”也归回它所属的气泡。"""
        try:tags=box.tag_names(box.index('@%d,%d'%(event.x,event.y)))
        except tk.TclError:return None
        for tag in tags:
            if str(tag)=='bubble_example':
                return 'example','bubble_example'
            index=self._bubble_tag_index(tag)
            if index is not None:
                return index,'bubble_'+str(index)
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
        if any(self._bubble_tag_index(tag) is not None for tag in tags):
            self.status.set('已选中气泡正文，按 Ctrl+C 复制。')
        return None
    def _idea_display_rows(self):
        """当前气泡框显示的行（按显示顺序）；尚未渲染时回退到当前模型的历史。"""
        rows=getattr(self,'_idea_view_rows',None)
        if rows is not None:return rows
        import idea_chat
        return idea_chat.load(self.idea_chat_context(),model=self.displayed_chat_model(),gateway=self.idea_chat_gateway())
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
        rows=self._idea_display_rows()
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
        rows=self._idea_display_rows()
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
        rows=self._idea_display_rows()
        if not 0<=index<len(rows):return None
        row=rows[index]
        try:idea_chat.remove_message(self.idea_chat_context(),row,gateway=self.idea_chat_gateway())
        except ValueError:
            self.show_conversation();self.status.set('这条消息已不存在，已刷新')
            return None
        # 删掉某模型最后一条后它的标签会消失、视图换到别的模型；恢复仍应找回这条所属的模型。
        self._idea_last_deleted=(self.root,str(row.get('model') or '').strip() if isinstance(row,dict) else '')
        self.show_conversation();self.status.set('已删除整条信息；可在右键菜单恢复最近删除')
        return index
    def restore_latest_bubble_message(self):
        """恢复当前模型聊天页最近删除的一条完整消息。"""
        import idea_chat
        last=getattr(self,'_idea_last_deleted',None)
        model=last[1] if isinstance(last,tuple) and last[0]==self.root and last[1] else self.displayed_chat_model()
        row=idea_chat.restore_latest_removed(self.idea_chat_context(),model=model,gateway=self.idea_chat_gateway())
        self._idea_last_deleted=None
        if model:self.set_idea_model_filter(model)
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
        self._clear_bubble_view(box, reset_width=False)
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
        example=index == 'example'
        # 页面刚建好时框子还没量过宽度，这一条要留着，等真实宽度下来再摆一次（见 refit_bubbles）。
        getattr(self,'_bubble_rows',[]).append((name,text,mine,not example))
        # 左右分列只由边距决定（用户贴右、模型贴左）；正文与署名一律左对齐，符合阅读习惯。
        align='left'
        _model_back, model_meta = self.model_chat_colors(row.get('model'))
        # 参考 DeepSeek 对话：正文铺一圈浅灰底框（淡底＋左右内边距，不画描边线），分列仍按
        # 用户靠右、模型靠左（REQ-S01-65 的左右位置区分保留），文字一律左对齐。软件示例是只读参考，不铺框。
        pad=BUBBLE_PAD if not example else 0
        body_left=left+pad
        body_right=right+pad
        fill='' if example else BUBBLE_FILL
        look=dict(justify=align,background=fill,
                  foreground=COLORS['text_secondary'] if example else COLORS['text_primary'],
                  lmargin1=body_left,lmargin2=body_left,rmargin=body_right,
                  spacing1=2,spacing2=1,spacing3=4,font=BUBBLE_FONT,wrap='word')
        # 框外的留白保持内容框底色（lmargincolor/rmargincolor），灰色只铺正文那一段——
        # 色块才贴着字、按字宽收窄；若把留白也刷成灰色，用户气泡左侧大半屏都会变成灰条。
        # 不设 relief：Text 的描边按每个显示行各画一圈，多行正文会出现横线，用户明确不要。
        margin_back=box.cget('bg') if example else BUBBLE_BACK
        try:box.tag_configure(name,lmargincolor=margin_back,rmargincolor=margin_back,**look)
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
        # 页脚留在底框外面，但必须整句可见：左右边距钉在对话区边沿、整段按词换行——
        # 若跟着用户气泡收窄，右侧只剩一个气泡的宽度，再加 wrap='none' 就会被内容框裁掉。
        # 文字对齐跟气泡分列一致：用户消息（SKILL 摘要只挂在用户消息上）右对齐，模型消息左对齐。
        import idea_chat
        footer='  '.join(part for part in (idea_chat.skill_injection_summary(row),self.bubble_time(row.get('at'))) if part)
        if footer:
            box.tag_configure(name+'_time',justify='right' if mine else 'left',foreground=COLORS['text_muted'],
                              lmargin1=BUBBLE_GAP,lmargin2=BUBBLE_GAP,rmargin=BUBBLE_GAP,
                              spacing1=0,spacing3=1,font=BUBBLE_TIME_FONT,wrap='word')
            box.insert('end',footer+'\n',name+'_time')
        if isinstance(index,int):
            self.add_bubble_actions(box,name,index,left,right,rewindable=mine)
        # 新建的气泡 tag（含淡底）默认优先级高于 sel，会把选中高亮压下去；每插一条就把 sel 提回最高，
        # 保证「选了哪段」始终可见、光标/选区不闪跳。
        try:box.tag_raise('sel')
        except tk.TclError:pass
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
        self._bubble_rows.append((name,thinking,False,False))
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
    def build_idea_model_bar(self, parent):
        """在聊天气泡框上方建一条可横向滚动的模型目录条；先隐藏，≥2 个模型才显示。"""
        bar=tk.Frame(parent,bg=COLORS['background_card'])
        canvas=tk.Canvas(bar,height=MODEL_BAR_HEIGHT,highlightthickness=0,bg=COLORS['background_card'])
        scroll=ttk.Scrollbar(bar,orient='horizontal',command=canvas.xview)
        canvas.configure(xscrollcommand=scroll.set)
        inner=tk.Frame(canvas,bg=COLORS['background_card'])
        canvas.create_window((0,0),window=inner,anchor='nw')
        inner.bind('<Configure>',lambda event:self._fit_idea_model_bar(canvas,inner,scroll))
        canvas.bind('<Configure>',lambda event:self._fit_idea_model_bar(canvas,inner,scroll))
        canvas.grid(row=0,column=0,sticky='ew')
        bar.columnconfigure(0,weight=1)
        self.idea_model_bar=bar
        self.idea_model_bar_canvas=canvas
        self.idea_model_bar_inner=inner
        self.idea_model_bar_scroll=scroll
        bar.pack(side='top',fill='x')
        bar.pack_forget()
        return bar
    def _fit_idea_model_bar(self, canvas, inner, scroll):
        """目录条内容变化后更新滚动区域；内容溢出才露出横向滚动条。"""
        canvas.configure(scrollregion=canvas.bbox('all'))
        height=inner.winfo_reqheight()
        if height>1:canvas.configure(height=height)
        if inner.winfo_reqwidth()>canvas.winfo_width():
            if not scroll.winfo_manager():scroll.grid(row=1,column=0,sticky='ew')
        elif scroll.winfo_manager():scroll.grid_remove()
    def render_idea_model_bar(self, items, selected):
        """重建模型目录条：每个已调用模型一个标签（右上角 × 关闭＝清空该模型历史）；选中高亮；无记录时隐藏。"""
        bar=getattr(self,'idea_model_bar',None)
        if bar is None or not bar.winfo_exists():return
        inner=self.idea_model_bar_inner
        for child in inner.winfo_children():child.destroy()
        if not items:
            if bar.winfo_manager():bar.pack_forget()
            return
        scroll=getattr(self,'idea_scroll',None)
        if not bar.winfo_manager():
            bar.pack(side='top',fill='x',before=scroll) if scroll is not None else bar.pack(side='top',fill='x')
        for name in items:
            active=name==selected
            bg=COLORS['primary_subtle'] if active else COLORS['background_card']
            tab=tk.Frame(inner,bg=bg,cursor='hand2')
            tab.pack(side='left',padx=(SPACING['none'],SPACING['xs']))
            tag=tk.Label(tab,text=name,font=MODEL_BAR_FONT,bg=bg,cursor='hand2',
                         fg=COLORS['primary'] if active else COLORS['text_secondary'],
                         padx=SPACING['sm'],pady=SPACING['xs'])
            tag.pack(side='left')
            # 右上角关闭：确认后清空该模型全部历史，标签随记录消失。
            close=tk.Label(tab,text='×',font=MODEL_BAR_FONT,bg=bg,fg=COLORS['text_secondary'],cursor='hand2')
            close.pack(side='left',anchor='n',padx=(SPACING['none'],SPACING['xs']))
            tab.model_tag,tab.close_tag=tag,close
            for widget in (tab,tag):
                widget.bind('<Button-1>',lambda event,key=name:(self.safe(lambda:self.select_idea_model(key)),'break')[1])
            close.bind('<Button-1>',lambda event,key=name:(self.safe(lambda:self.delete_all_bubble_messages(key)),'break')[1])
        self._fit_idea_model_bar(self.idea_model_bar_canvas,inner,self.idea_model_bar_scroll)
    def set_idea_model_filter(self, model, root=None):
        """目录条选中态的唯一写入口：点击、发送与配置确认都走它，避免多个 Mixin 写同一 self 属性。"""
        self._idea_model_filter=model
        self._idea_model_filter_root=self.root if root is None else root
    def select_idea_model(self, model):
        """点击目录条标签：把气泡框切到该模型（或「全部」）的对话视图。"""
        if not self.root:return
        self.set_idea_model_filter(model)
        self.show_conversation()
        self._sync_stage_model_picker(model)

    def _sync_stage_model_picker(self, model):
        """目录条切到某模型时，让共享输入框的模型下拉跟着显示该模型。"""
        shared = getattr(self, 'shared_input', None)
        picker = getattr(shared, 'model_picker', None)
        if picker is not None and callable(getattr(picker, 'set_model_label', None)):
            picker.set_model_label(model)

    def _model_tab_rows(self, root, selected, all_rows):
        """某模型标签下显示的行：本模型会话＋旧版目录里署名为它、会话里没有的记录。

        目录条标签取自合并后的全部记录；只读本模型文件会出现“有标签、点开却没记录”。
        """
        from stage_execution_service import project_context
        import idea_chat
        own=idea_chat.load(project_context(root),model=selected,gateway=self.idea_chat_gateway())
        def labelled(rows):
            return [row for row in rows if isinstance(row,dict) and str(row.get('model') or '').strip()==selected]
        candidates=labelled(all_rows)
        # 合并记录已去重：署名为它的条数不多于会话里的，就没有残留可补（最常见的情况，免得逐条比对）。
        if len(candidates)<=len(labelled(own)):return own
        extra=[row for row in candidates if not any(idea_chat.same_message(row,mine) for mine in own)]
        if not extra:return own
        return sorted(own+extra,key=lambda row:str(row.get('at') or ''))
    def idea_view_rows(self, root, model, resolving_model):
        """按当前选中键解析要显示的行，并同步目录条；返回显示行列表。

        项目切换时回落到默认选中（当前模型），选中模型无记录回落「全部」；具体模型走
        L2 按模型读取（保留旧版迁移与重复消息语义），「全部」直接展示合并行。
        """
        if root!=getattr(self,'_idea_model_filter_root',None):
            self.set_idea_model_filter(None,root)
        from stage_execution_service import project_context
        import idea_chat
        all_rows=idea_chat.load(project_context(root),model='',gateway=self.idea_chat_gateway()) if root and not resolving_model else []
        items=model_bar_items(all_rows)
        if not resolving_model:
            selected=model_bar_selection(self._idea_model_filter,items,model)
            self.set_idea_model_filter(selected,root)
            rows=all_rows if selected==ALL_MODELS else self._model_tab_rows(root,selected,all_rows)
        else:
            selected=''
            rows=[]
        self.render_idea_model_bar(items,selected)
        self._idea_view_rows=list(rows)
        if root and not resolving_model:self.__dict__.setdefault('_idea_history_known',{})[root]=bool(all_rows)
        return rows
