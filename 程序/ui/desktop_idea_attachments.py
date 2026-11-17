"""创意附件的桌面方法集（从 ``desktop_idea_chat.IdeaChatMixin`` 原样迁出，R2505）。

迁出原因：``IdeaChatMixin`` 超出类行数棘轮上限（769 > 748），附件这一簇（状态行、卡片、
选择入库、入库轮询、插入引用）自成一事，整块搬出后方法体未改、``self`` 语义不变。
`IdeaChatMixin` 通过继承 ``IdeaAttachmentsMixin`` 获得这些方法；仍与 Tk 控件和 ``self``
状态紧耦合，故与 ``desktop_idea_chat`` 同属 L4。
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui_tokens import CHAR_WIDTH, SPACING


class IdeaAttachmentsMixin:
    """剧本准备页的创意附件：展示与入库（``@`` 引用插入已由共享输入框接管，R2980）。"""
    def update_idea_attachment_status(self):
        """仅展示用户已选择的文件名；路径和正文不出现在界面或聊天记录。"""
        label=getattr(self,'idea_attachment_status',None)
        prepared=getattr(self.idea_chat_controller,'attachment_details',())
        from domain.idea_attachments import display_name
        tips,details,local={},[],'原文件，将由 Agent 自行读取'
        def note(shown,key,tip):
            tips[key]=tip;details.append('%s（%s）' % (shown,tip))
        for name,count in prepared:
            key=display_name(name);note(key if count is None else name,key,local if count is None else '%d 字' % count)
        if not tips:
            import domain.idea_attachments as idea_attachments
            from stage_execution_service import idea_attachment_local_mode
            local_mode=idea_attachment_local_mode(self.root)
            for value in getattr(self,'idea_attachment_paths',()):
                key=display_name(value)
                if local_mode:note(key,key,local);continue
                try:count=len(idea_attachments.read_source(Path(value)))
                except (OSError, ValueError):continue
                note(Path(value).name,key,'%d 字' % count)
        self._idea_attachment_tips=tips
        if label is not None:label.set(('已引用：'+'、'.join(details)) if details else '')
        self.refresh_uploaded_idea_attachments()
    def refresh_uploaded_idea_attachments(self):
        """输入框内的附件卡片：上传库全部列出，本轮会带上的卡片用主色边框高亮。"""
        panel=getattr(self,'idea_uploaded_panel',None)
        if panel is None or not panel.winfo_exists():return
        from stage_execution_service import stage_idea_attachment_paths
        from domain.idea_attachments import archive_pair, display_name
        from ui_tokens import ICON_CLOSE, ICON_DOCUMENT
        from ui_widgets import Tooltip
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
        paths+=[Path(path) for path in getattr(self,'idea_attachment_paths',()) if key(path) not in known]
        for child in panel.winfo_children():child.destroy()
        tips=getattr(self,'_idea_attachment_tips',{})
        for path in paths:
            name=display_name(path)
            selected=key(path) in referenced
            chip=ttk.Frame(panel,style='Tokens.Chip.Selected.TFrame' if selected else 'Tokens.Chip.TFrame',
                           padding=(SPACING['sm'],SPACING['xs']))
            icon=ttk.Label(chip,text=ICON_DOCUMENT,style='Composer.Chip.Icon.TLabel')
            icon.pack(side='left')
            limit=CHAR_WIDTH['3xl']
            title=ttk.Label(chip,text=name if len(name)<=limit else name[:limit-1]+'…',style='Composer.TLabel')
            close=ttk.Label(chip,text=ICON_CLOSE,style='Composer.Chip.Close.TLabel',cursor='hand2')
            title.pack(side='left',padx=(SPACING['xs'],close.winfo_reqwidth()+SPACING['xs']))
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
        if not panel.winfo_manager():panel.pack(side='top',fill='x',expand=False,padx=(SPACING['xs'],SPACING['xs']))
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
