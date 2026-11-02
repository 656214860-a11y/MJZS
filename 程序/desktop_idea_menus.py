"""创意对话的菜单、附件打开与删除确认。

从 ``desktop.Desktop`` 原样迁出（R1505）：方法体未改，``self`` 语义不变，``Desktop`` 通过继承
``IdeaMenusMixin`` 获得。测试按 ``desktop.<名字>`` 打补丁的名字（confirm／open_path 等）经
``Desktop`` 注入的 ``ProjectPageServices``（定义在 ``desktop_project_pages``）在调用时取 ``desktop`` 的当前值，补丁照常生效（R1983 J2）。
"""
import tkinter as tk


class IdeaMenusMixin:
    """Desktop 的创意对话菜单方法集（见模块说明）。"""
    def open_bubble_menu(self,event):
        """消息右键菜单；点击标题、正文或展开控件都能定位同一条消息。"""
        target=self.bubble_target_at(event.widget,event)
        menu=self.project_page_services.context_menu(event.widget)
        if target is not None:
            index,_name=target
            if index == 'example':
                menu.command('复制软件示例',lambda:self.copy_bubble_message('example'))
            else:
                menu.command('恢复最近删除的信息',self.restore_latest_bubble_message)
            menu.separator()
        menu.command('清屏压缩',self.clear_bubble_view)
        self._bubble_menu=menu
        return menu.popup(event)
    def open_idea_paste_menu(self,event):
        """输入框右键时，仅在剪贴板有文字时给出粘贴入口。"""
        box=event.widget
        try:text=str(box.clipboard_get() or '')
        except tk.TclError:return 'break'
        if not text:return 'break'
        menu=self.project_page_services.context_menu(box, menu_factory=tk.Menu).command('粘贴',lambda:box.event_generate('<<Paste>>'))
        self._idea_paste_menu=menu
        return menu.popup(event)
    def open_uploaded_idea_attachment(self,path):
        """单击附件卡片：原件在就打开原件，否则打开项目副本。"""
        if path is not None:
            from idea_attachments import archive_pair
            original,_converted=archive_pair(path)
            self.project_page_services.open_path(original if original.is_file() else path)
        return 'break'
    def delete_uploaded_idea_attachment(self,path):
        """附件卡片右上角 ×：确认后把这一份项目副本移入回收站，原始文件不动。"""
        if path is None:return
        from idea_attachments import display_name
        name=display_name(path)
        if not self.project_page_services.confirm(self.win,'删除附件',
                       '确定将“%s”的项目副本移入回收站吗？\n原始文件不受影响；可从回收站恢复。' % name,
                       dangerous=True):return
        try:self.idea_chat_controller.delete_attachment(self.root,path)
        finally:
            self.update_idea_attachment_status()
        self.status.set('已移入回收站：'+name+'；原始文件未删除。')
    def show_idea_reference_menu(self, event):
        """用户输入 @ 时仅展示当前项目已入库的创意，不访问任意本地文件。"""
        if str(getattr(event,'char',''))!='@':return None
        from stage_execution_service import stage_idea_attachment_paths
        paths=stage_idea_attachment_paths(self.root)
        if not paths:return None
        menu=self.project_page_services.context_menu(event.widget, menu_factory=tk.Menu)
        for path in paths:
            menu.command(path.name,lambda item=path:self.insert_idea_reference(item))
        self._idea_reference_menu=menu
        return menu.popup(event)
