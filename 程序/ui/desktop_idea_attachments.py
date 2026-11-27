"""创意附件的桌面方法集（从 ``desktop_idea_chat.IdeaChatMixin`` 原样迁出，R2505）。

迁出原因：``IdeaChatMixin`` 超出类行数棘轮上限（769 > 748），附件这一簇（状态行、卡片、
选择入库、入库轮询、插入引用）自成一事，整块搬出后方法体未改、``self`` 语义不变。
`IdeaChatMixin` 通过继承 ``IdeaAttachmentsMixin`` 获得这些方法；仍与 Tk 控件和 ``self``
状态紧耦合，故与 ``desktop_idea_chat`` 同属 L4。
"""
import tkinter as tk
from pathlib import Path

import infra.app_logging as app_logging


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
        if not getattr(self,'idea_attachment_paths',()):self._idea_cursor_ref_names=set()
        self._sync_idea_ref_block()
    # ── R3060：附件以「@原名」行内文本落在输入框顶部引用区（与手动 @ 引用同一显示效果），
    #    不再有卡片行；引用区行打 idea_ref 标签由本方法集统一重建，右键 @ 行可打开／删除副本／取消引用。 ──
    def _idea_ref_block_names(self):
        """顶部引用区应显示的显示名：本轮引用全量，@ 手动插入的除外（它们已在光标处）。"""
        from domain.idea_attachments import display_name
        cursor=getattr(self,'_idea_cursor_ref_names',set()) or set()
        names=[]
        for path in getattr(self,'idea_attachment_paths',()):
            shown=display_name(path)
            if shown in cursor or Path(path).name in cursor:continue
            if shown not in names:names.append(shown)
        return names
    def _sync_idea_ref_block(self):
        """按本轮引用重建顶部「@原名」引用区：先删带 idea_ref 标签的旧行，再从 1.0 写入新块。

        REQ-S01-107：标签行逐行核对——整行仍是「@名」且名字在本轮引用或
        ``_idea_synced_ref_names``（本方法上次写入的引用名集）内才删，标签被
        编辑扩写到用户正文的行保留并摘掉标签；删行与写块并成一次可撤销动作。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return
        try:
            from domain.idea_attachments import display_name
            names=self._idea_ref_block_names()
            valid=set(names)
            for path in getattr(self,'idea_attachment_paths',()):
                valid.add(display_name(path));valid.add(Path(path).name)
            # 引用缩减/清空后旧行不再属本轮，但仍是同步写入而非用户正文：
            # 并入上次写入集，让已取消引用的「@名」行能被认出并删掉。
            valid|=getattr(self,'_idea_synced_ref_names',set()) or set()
            marked=set()
            if 'idea_ref' in box.tag_names():
                ranges=box.tag_ranges('idea_ref')
                for i in range(0,len(ranges)-1,2):
                    try:
                        a=int(str(ranges[i]).split('.')[0]);b=int(str(ranges[i+1]).split('.')[0])
                    except (ValueError,IndexError):continue
                    marked.update(range(a,max(a,b)))
            try:box.edit_separator()
            except tk.TclError:pass
            try:box.configure(autoseparators=False)
            except tk.TclError:pass
            for line in sorted(marked,reverse=True):
                try:text=box.get('%d.0'%line,'%d.end'%line)
                except tk.TclError:continue
                if text.startswith('@') and text[1:] in valid:
                    try:box.delete('%d.0'%line,'%d.0'%(line+1))
                    except tk.TclError:app_logging.swallowed()
                else:
                    try:box.tag_remove('idea_ref','%d.0'%line,'%d.0'%(line+1))
                    except tk.TclError:pass
            if not names:
                if 'idea_ref' in box.tag_names():box.tag_remove('idea_ref','1.0','end')
                self._idea_synced_ref_names=set()
                try:
                    box.configure(autoseparators=True)
                    box.edit_separator()
                except tk.TclError:pass
                return
            box.mark_set('_idea_ref_sync',box.index('insert'))
            box.insert('1.0',''.join('@%s\n'%n for n in names))
            box.tag_add('idea_ref','1.0','%d.0'%(len(names)+1))
            box.mark_set('insert','_idea_ref_sync')
            self._idea_synced_ref_names=set(names)
            # 草稿恢复等途径带回的未标记同名 @ 行紧跟引用区，去重避免双份。
            keep=set(names);scan=len(names)+1
            for _ in range(12):
                try:text=box.get('%d.0'%scan,'%d.end'%scan)
                except tk.TclError:break
                if text.startswith('@') and text[1:] in keep:
                    try:box.delete('%d.0'%scan,'%d.0'%(scan+1))
                    except tk.TclError:app_logging.swallowed()
                    continue
                if not text.startswith('@'):break
                scan+=1
            try:
                box.configure(autoseparators=True)
                box.edit_separator()
            except tk.TclError:pass
        except tk.TclError:app_logging.swallowed()
    def remove_idea_ref_line(self,path):
        """删掉输入框里对应「@原名／@文件名」的那一行（取消引用或删除副本时调用）。"""
        box=getattr(self,'idea_input',None)
        if box is None or not box.winfo_exists():return
        from domain.idea_attachments import display_name
        names={Path(path).name,display_name(path)}
        try:last=int(str(box.index('end-1c')).split('.')[0])
        except (tk.TclError,ValueError):return
        for line in range(1,last+1):
            try:text=box.get('%d.0'%line,'%d.end'%line)
            except tk.TclError:return
            if text.startswith('@') and text[1:] in names:
                try:box.delete('%d.0'%line,'%d.0'%(line+1))
                except tk.TclError:app_logging.swallowed()
                return
    def _idea_attachment_at(self,event):
        """右键落点是否命中「@名」行；命中返回对应已入库路径，否则 None。"""
        box=getattr(self,'idea_input',None)
        if box is None or getattr(event,'widget',None) is not box:return None
        try:
            index=box.index('@%d,%d'%(int(event.x),int(event.y)))
            line=int(str(index).split('.')[0])
            text=box.get('%d.0'%line,'%d.end'%line)
        except (tk.TclError,ValueError,TypeError,AttributeError):return None
        if not text.startswith('@') or not text[1:]:return None
        name=text[1:]
        from stage_execution_service import stage_idea_mention_candidates
        from domain.idea_attachments import display_name
        seen=set()
        candidates=[Path(item['path']) for item in stage_idea_mention_candidates(self.root) if item.get('path')]+[Path(p) for p in getattr(self,'idea_attachment_paths',())]
        for path in candidates:
            key=str(path)
            if key in seen:continue
            seen.add(key)
            if name in (display_name(path),Path(path).name):return path
        return None
    def unreference_idea_attachment(self,path):
        """右键「取消引用」：移出本轮发送名单，项目副本保留，并删掉输入框里的 @ 行。"""
        from domain.idea_attachments import display_name
        name=display_name(path)
        self.idea_chat_controller.unreference_attachment(path)
        self.remove_idea_ref_line(path)
        self.update_idea_attachment_status()
        self.status.set('已取消引用：'+name+'；文件仍保留在项目已上传列表。')
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
