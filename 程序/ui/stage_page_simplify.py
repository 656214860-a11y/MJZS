# -*- coding: utf-8 -*-
"""Animatic 之后各制作阶段的「少按钮页面」接线工具。

页面不碰共享输入框与文件面板核心，只沿用它们已开放的登记接口：
空输入框发送键＝本阶段主行动；右侧项目文件面板承接导入、点选与文件右键；
页面/表格右键承接原按钮动作。登记的回调随页面锚点销毁释放，避免跨页串扰。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui_tokens import SPACING
from ui_widgets import ContextMenu, DescriptionBlock, Tooltip


def discoverability_hint(page, text):
    """在页首放一行操作发现提示；返回标签（测试与调用方可保留引用）。"""
    content = page.content
    label = DescriptionBlock(content, text='右键菜单  ·  Shift+F10')
    label.tooltip = Tooltip(label, str(text or ''))
    children = content.pack_slaves()
    options = {'anchor': 'w', 'fill': 'x', 'pady': (SPACING['none'], SPACING['xs'])}
    if children:
        label.pack(before=children[0], **options)
    else:
        label.pack(**options)
    return label


def bind_context_menu(page, widgets, build):
    """把 ``build(event) -> ContextMenu`` 绑到一组控件；支持 Shift+F10/Menu 键。"""
    widgets = [widget for widget in widgets if widget is not None]

    def mouse(event):
        menu = build(event)
        if menu is not None:
            menu.popup(event)
        return 'break'

    def keyboard(event):
        widget = event.widget
        menu = build(event)
        if menu is not None:
            x = widget.winfo_rootx() + max(1, widget.winfo_width() // 2)
            y = widget.winfo_rooty() + max(1, widget.winfo_height() // 2)
            menu.popup_at(x, y)
        return 'break'

    # 内容容器会跨阶段复用。只替换本入口自己的绑定，其他编辑/行菜单继续有效。
    targets = dict.fromkeys(widget for root in widgets for widget in _walk(root))
    for widget in targets:
        previous = getattr(widget, '_stage_menu_bindings', {})
        for sequence, handle in previous.items():
            widget.unbind(sequence, handle)
        widget._stage_menu_bindings = {
            sequence: widget.bind(sequence, callback, add='+')
            for sequence, callback in (('<Button-3>', mouse), ('<Shift-F10>', keyboard),
                                       ('<App>', keyboard))
        }
    return mouse


def menu(page, entries):
    """按 ``[(label, command), ...]`` 建菜单；label 为 None 时分隔，命令为 None 时禁用。"""
    built = ContextMenu(page.win)
    for entry in entries:
        if entry is None or entry[0] is None:
            built.separator()
            continue
        label, command = entry[0], entry[1]
        if command is None:
            built.disabled(label)
        else:
            built.command(label, command)
    return built


def register_stage_send(page, stage, action, anchor):
    """登记空输入框发送动作；anchor 销毁时只释放本页登记的那份。"""
    shared = getattr(page, 'shared_input', None)
    register = getattr(shared, 'set_stage_action', None)
    if not callable(register):
        return None
    register(stage, action)

    def release(_event=None):
        getter = getattr(shared, 'stage_action', None)
        try:
            current = getter(stage) if callable(getter) else None
        except tk.TclError:
            return
        if current is action:
            try:
                register(stage, None)
            except tk.TclError:
                pass

    if anchor is not None:
        anchor.bind('<Destroy>', release, add='+')
    return action


def _hook_registered(panel, kind, key, ours):
    box = getattr(panel, '_' + kind + '_handlers', None)
    entry = (box or {}).get(key)
    if entry is None:
        return False
    current = entry[1] if isinstance(entry, tuple) else entry
    return current is ours


def _select_registered(panel, page_key, ours):
    entry = getattr(panel, '_select_handlers', {}).get(page_key)
    return bool(entry and entry[0] is ours)


def register_files_panel(page, stage, anchor, *, import_handler=None, menu_hook=None,
                         select_handler=None, select_default=None):
    """登记右侧项目文件面板的阶段挂钩；anchor 销毁时只释放本页的挂钩。"""
    panel = getattr(page, 'files_panel', None)
    if panel is None:
        return {}
    registered = {}
    if callable(import_handler):
        setter = getattr(panel, 'set_import_handler', None)
        if callable(setter):
            setter(stage, import_handler)
            registered['import'] = import_handler
    if callable(menu_hook):
        setter = getattr(panel, 'set_menu_handler', None)
        if callable(setter):
            setter(stage, menu_hook)
            registered['menu'] = menu_hook
    if callable(select_handler):
        setter = getattr(panel, 'set_select_handler', None)
        if callable(setter):
            page_key = getattr(page, 'page_index', None)
            setter(page_key, select_handler, default=select_default)
            registered['select'] = (page_key, select_handler)

    def release(_event=None):
        current_panel = getattr(page, 'files_panel', None)
        if current_panel is None:
            return
        if registered.get('import') is not None and _hook_registered(
                current_panel, 'import', stage, registered['import']):
            setter = getattr(current_panel, 'set_import_handler', None)
            if callable(setter):
                setter(stage, None)
        if registered.get('menu') is not None and _hook_registered(
                current_panel, 'menu', stage, registered['menu']):
            setter = getattr(current_panel, 'set_menu_handler', None)
            if callable(setter):
                setter(stage, None)
        if registered.get('select') is not None:
            page_key, ours = registered['select']
            if _select_registered(current_panel, page_key, ours):
                setter = getattr(current_panel, 'set_select_handler', None)
                if callable(setter):
                    setter(page_key, None)

    if anchor is not None:
        anchor.bind('<Destroy>', release, add='+')
    return registered


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def relocate_buttons(page, labels, anchors=(), stage=None, send_label=None, hint=None):
    """把页面上已建好的动作按钮收进上下文菜单，按钮本体隐藏但不销毁。

    菜单项只调用原按钮的 ``invoke()``：确认、置灰、异步回调与 stage_flow 跟随关系
    全部沿用。动态文案（例如「转场：…」）按前缀匹配，弹出菜单时读按钮当下文案。
    返回被迁移的按钮清单，测试可据此断言入口仍在。
    """
    content = getattr(page, 'content', None)
    if content is None:
        return []
    wanted = tuple(labels or ())
    found = []
    for widget in _walk(content):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            text = str(widget.cget('text'))
        except tk.TclError:
            continue
        if any(text == item or text.startswith(item) for item in wanted) and widget not in found:
            found.append(widget)
    for button in found:
        try:
            flow_visibility = getattr(button.master, 'set_visible', None)
            if callable(flow_visibility):
                flow_visibility(button, False)
            manager = button.winfo_manager()
            if manager == 'pack':
                button.pack_forget()
            elif manager == 'grid':
                button.grid_remove()
            elif manager == 'place':
                button.place_forget()
        except tk.TclError:
            pass

    # FlowBar 的定宽标题是原按钮组的一部分。整组收进菜单后释放行高。
    for bar in {button.master for button in found}:
        children = bar.winfo_children()
        if callable(getattr(bar, 'set_visible', None)) and all(
                child in found or isinstance(child, ttk.Label) for child in children):
            if bar.winfo_manager() == 'pack':
                bar.pack_forget()
            elif bar.winfo_manager() == 'grid':
                bar.grid_remove()

    def invoke(button):
        try:
            if button.instate(('disabled',)):
                page.status.set('「' + str(button.cget('text')) + '」现在不可用：请先满足页面上写出的前置条件。')
                return False
            button.invoke()
            return True
        except Exception as exc:
            page.note(str(exc))
            return False

    def menu_builder(_event):
        built = ContextMenu(page.win)
        for button in found:
            try:
                text = str(button.cget('text'))
            except tk.TclError:
                continue
            if button.instate(('disabled',)):
                built.disabled(text)
            else:
                built.command(text, lambda target=button: invoke(target))
        return built

    anchors = [widget for widget in anchors if widget is not None]
    if anchors:
        bind_context_menu(page, [*anchors, content], menu_builder)
    if stage and send_label:
        sender = next((button for button in found if str(button.cget('text')).startswith(send_label)), None)
        if sender is not None:
            register_stage_send(page, stage, lambda: invoke(sender), anchors[0] if anchors else None)
    if hint:
        discoverability_hint(page, hint)
    return found
