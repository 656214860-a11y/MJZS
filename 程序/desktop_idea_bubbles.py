"""想法对话的气泡方法集（从 desktop_idea_chat.IdeaChatMixin 原样迁出，R1806）。

方法体未改、self 语义不变，IdeaChatMixin 通过继承 IdeaBubblesMixin 获得；仍与 Tk 控件紧耦合，故与 desktop_idea_chat 同属 L4。"""
import json
import tkinter as tk
from ui_tokens import COLORS, ICON_COPY, ICON_DELETE, ICON_FONT
from pathlib import Path
from idea_chat_controller import bubble_timestamp, collapse_preview


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
        text=''.join(char for char in text if char not in (ICON_COPY,ICON_DELETE))
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
            self.add_bubble_actions(box,name,index,left,right)
            # 只允许编辑真实消息；只读软件示例仍可拖选复制。
            box.tag_bind(name,'<Button-1>',lambda event,i=index,n=name:self.begin_bubble_click(event,i,n))
            box.tag_bind(name,'<Enter>',lambda event,b=box:b.configure(cursor='hand2'))
            box.tag_bind(name,'<Leave>',lambda event,b=box:b.configure(cursor='xterm'))
    def add_bubble_actions(self,box,name,index,left,right):
        """REQ-S01-66：正文左下角的复制／删除图标；平时与框底同色占位，悬停这条消息才显出来。"""
        actions=name+'_actions'
        box.tag_configure(actions,lmargin1=left,lmargin2=left,rmargin=right,spacing1=0,spacing3=4,font=ICON_FONT)
        for suffix,icon,handler in (('_copy',ICON_COPY,'copy_bubble_message'),
                                    ('_delete',ICON_DELETE,'delete_bubble_message')):
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
        for suffix in ('_copy','_delete'):
            try:box.tag_configure(name+suffix,foreground=color)
            except tk.TclError:pass
    def show_thinking(self,model):
        """模型正在请求时，在最近一条消息下方放临时状态；不会写入对话记录。"""
        self._thinking_model=model if str(model or '').strip() else 'AI 助手'
        self.show_conversation()
    def clear_thinking(self):
        if getattr(self,'_thinking_model',''):
            self._thinking_model=''
            self.show_conversation()
