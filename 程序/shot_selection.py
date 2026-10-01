"""Shared production tables: every row click toggles its submission checkbox."""

def bind_shot_checks(tree,toggle,cell_click=None):
    def select(sid):
        tree.focus_set()
        tree.focus(sid)
        if tree.selection()!=(sid,):
            tree.selection_set(sid)

    def click(event):
        # Leave heading sorting/select-all and separator resizing to ttk.
        if tree.identify_region(event.x,event.y) not in ('tree','cell'):
            return
        sid=tree.identify_row(event.y)
        if not sid:return
        # 第 41 期第 1 条：带下拉框的格子（「选择资产」）自己认下这一下——它认了就不
        # 切换本行勾选，认不了（返回假）才照旧切换。
        if cell_click is not None and cell_click(event):
            return 'break'
        select(sid)
        toggle(sid)
        return 'break'

    def space(event):
        sid=tree.focus()
        if not sid or not tree.exists(sid):
            selected=tree.selection()
            sid=selected[0] if selected else None
        if sid:
            select(sid)
            toggle(sid)
        return 'break'

    tree.bind('<Button-1>',click)
    tree.bind('<space>',space)
