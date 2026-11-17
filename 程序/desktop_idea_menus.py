"""创意对话的菜单、附件打开与删除确认。

从 ``desktop.Desktop`` 原样迁出（R1505）：方法体未改，``self`` 语义不变，``Desktop`` 通过继承
``IdeaMenusMixin`` 获得。测试按 ``desktop.<名字>`` 打补丁的名字（confirm／open_path 等）经
``Desktop`` 注入的 ``ProjectPageServices``（定义在 ``desktop_project_pages``）在调用时取 ``desktop`` 的当前值，补丁照常生效（R1983 J2）。
"""
import tkinter as tk


class IdeaMenusMixin:
    """Desktop 的创意对话菜单方法集（见模块说明）。"""
    def delete_all_bubble_messages(self,model=None):
        """清空一个模型的全部历史（含旧版目录残留）：目录条标签 × 传入该模型，右键菜单取当前选中标签。"""
        if (getattr(self,'_idea_requesting',False) or getattr(self,'_script_agent_launching',False)
                or self.script_agent_processes()):
            raise ValueError('模型正在回复，请先中断或等待完成，再删除全部信息。')
        if not self.root:return None
        model=str(model or '').strip() or self.idea_model_tab()
        if not model:return None
        if not self.project_page_services.confirm(self.win,'删除全部信息',
                       '删除 '+model+' 的全部历史对话？\n聊天记录将移入回收站，已保存的剧本和附件保留。',dangerous=True):return None
        import idea_chat
        count=idea_chat.remove_all(self.idea_chat_context(),model=model,gateway=self.idea_chat_gateway())
        getattr(self,'_idea_hidden_messages',{}).pop(self.bubble_view_key(model),None)
        self.set_idea_model_filter(None)
        self.show_conversation()
        self.status.set('已删除 '+model+' 的全部历史对话；记录已移入回收站')
        return count
    def idea_model_tab(self):
        """目录条当前选中的具体模型；选「全部」或未选时返回空串。"""
        if getattr(self,'_idea_model_filter_root',None)!=self.root:return ''
        return str(getattr(self,'_idea_model_filter',None) or '').strip()
    def open_bubble_menu(self,event):
        """消息右键菜单；点击标题、正文或展开控件都能定位同一条消息。"""
        target=self.bubble_target_at(event.widget,event)
        menu=self.project_page_services.context_menu(event.widget)
        if target is not None:
            index,name=target
            record=getattr(self,'_bubble_full',{}).get(name)
            # 悬停在某条气泡上时才给展开/收起项：按当前状态摆菜单文字，动作与左下角「展开全文」一致。
            if record is not None and index != 'example':
                if record.get('expanded'):
                    menu.command('收起全文',lambda:self.toggle_bubble(event.widget,name))
                else:
                    menu.command('展开全文',lambda:self.toggle_bubble(event.widget,name))
                menu.separator()
            if index == 'example':
                menu.command('复制软件示例',lambda:self.copy_bubble_message('example'))
            else:
                menu.command('恢复最近删除的信息',self.restore_latest_bubble_message)
            menu.separator()
        if self.idea_model_tab():
            menu.command('删除全部信息',lambda:self.safe(self.delete_all_bubble_messages))
        menu.command('清屏压缩',self.clear_bubble_view)
        self._bubble_menu=menu
        return menu.popup(event)
    def open_idea_paste_menu(self,event):
        """输入框右键：落在「@附件名」行上时给附件操作（R3060），否则仅剪贴板有文字时给粘贴。"""
        box=event.widget
        from pet_state import PAGE_OF
        ref=self._idea_attachment_at(event) if getattr(self,'page_index',None)==PAGE_OF['script'] else None
        if ref is not None:
            menu=self.project_page_services.context_menu(box, menu_factory=tk.Menu)
            menu.command('打开附件',lambda:self.open_uploaded_idea_attachment(ref))
            menu.command('删除附件（移入回收站）',lambda:self.delete_uploaded_idea_attachment(ref))
            menu.command('取消引用',lambda:self.unreference_idea_attachment(ref))
            self._idea_paste_menu=menu
            return menu.popup(event)
        try:text=str(box.clipboard_get() or '')
        except tk.TclError:return 'break'
        if not text:return 'break'
        menu=self.project_page_services.context_menu(box, menu_factory=tk.Menu).command('粘贴',lambda:box.event_generate('<<Paste>>'))
        self._idea_paste_menu=menu
        return menu.popup(event)
    def open_uploaded_idea_attachment(self,path):
        """单击附件卡片：原件在就打开原件，否则打开项目副本。"""
        if path is not None:
            from domain.idea_attachments import archive_pair
            original,_converted=archive_pair(path)
            self.project_page_services.open_path(original if original.is_file() else path)
        return 'break'
    def delete_uploaded_idea_attachment(self,path):
        """附件卡片右上角 ×：确认后把这一份项目副本移入回收站，原始文件不动。"""
        if path is None:return
        from domain.idea_attachments import display_name
        name=display_name(path)
        if not self.project_page_services.confirm(self.win,'删除附件',
                       '确定将“%s”的项目副本移入回收站吗？\n原始文件不受影响；可从回收站恢复。' % name,
                       dangerous=True):return
        try:self.idea_chat_controller.delete_attachment(self.root,path)
        finally:
            self.remove_idea_ref_line(path)
            self.update_idea_attachment_status()
        self.status.set('已移入回收站：'+name+'；原始文件未删除。')
