# -*- coding: utf-8 -*-
"""会话分支/节点树（L4）：``DataTable`` 展示 checkpoint 树 + 切换对比/重新提问。

只消费 ``ui_tokens``；切换与提问经 ``on_switch(id)`` / ``on_ask(id, mode)`` 回调注入。
树按 ``parent_id`` 链展平为缩进行（父在前），避免业务层直造裸 ``ttk.Treeview``。
"""
from __future__ import annotations

from tkinter import ttk

from ui_tokens import SPACING
from ui_widgets import DataTable, SecondaryButton


def flatten_nodes(nodes):
    """把 ``(id, parent_id, label)`` 展平为 ``[(id, depth, label)]``；父节点须在前。"""
    depth = {}
    rows = []
    for node in nodes or ():
        node_id = str((node or {}).get('id') or '')
        if not node_id:
            continue
        parent_id = str((node or {}).get('parent_id') or '')
        depth[node_id] = depth.get(parent_id, -1) + 1
        rows.append((node_id, depth[node_id], str((node or {}).get('label') or node_id)))
    return rows


def build_branch_tree(parent, nodes, *, current_id='', on_switch=None, on_ask=None, height=8):
    """把 checkpoint 节点铺成缩进树；切换/延续提问/独立提问三按钮。返回 Frame。"""
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    table = DataTable(frame, columns=(('node', '节点', 0),), height=height,
                      show='tree', horizontal=False)
    table.pack(fill='x')
    items = {}
    for node_id, depth, label in flatten_nodes(nodes):
        items[node_id] = table.tree.insert('', 'end', iid=node_id, text='　' * depth + label)
    if current_id and current_id in items:
        table.tree.selection_set(items[current_id])
        table.tree.see(items[current_id])
    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])

    def selected():
        selection = table.tree.selection()
        return selection[0] if selection else ''

    def switch():
        node_id = selected()
        if node_id and on_switch is not None:
            on_switch(node_id)

    def ask(mode):
        node_id = selected()
        if node_id and on_ask is not None:
            on_ask(node_id, mode)

    SecondaryButton(row, text='切换到此节点', command=switch).pack(side='left', padx=SPACING['xs'])
    SecondaryButton(row, text='延续提问', command=lambda: ask('continue')).pack(
        side='left', padx=SPACING['xs'])
    SecondaryButton(row, text='独立提问', command=lambda: ask('independent')).pack(
        side='left', padx=SPACING['xs'])
    return frame
