"""页面差分测试的公共件：同一份脚本驱动「旧实现」与「新实现」两个页面，逐步对照可观察状态。

旧实现是把原函数源码原样内嵌后在模块命名空间的副本里 exec 出来的；新实现是仓库里现在的函数。
对照的“可观察状态”是整棵控件树（类名、文字、状态、样式、布局管理器参数、请求尺寸、是否映射、
文本框／输入框／列表／画布内容），所以只要改写改变了页面长什么样或点了以后变成什么样，就会红。
"""
import os
import re
import sys
import time
import tkinter as tk
from pathlib import Path

OPTIONS = ('text', 'state', 'style', 'width', 'height', 'relief', 'takefocus', 'show', 'selectmode',
           'wraplength', 'justify', 'values', 'anchor', 'padding', 'orient')
SAFE_BUTTONS = ('刷新列表', '立即重试', '刷新', '全选', '取消选择', '清除选择')


def freeze_times(root, stamp=1700000000):
    """项目里所有文件与目录的修改时间钉死，列表里的日期列才跨次运行一致。"""
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            try:
                os.utime(os.path.join(base, name), (stamp, stamp))
            except OSError:
                pass


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def _clean(value, roots):
    text = str(value)
    for root in roots:
        text = text.replace(root, '<ROOT>')
    text = re.sub(r'(?<!\d)\d{2}:\d{2}(:\d{2})?(?!\d)', 'HH:MM', text)   # 运行期才写的文件，修改时间是现在
    return re.sub(r'pyimage\d+|!\w+\d*|\.\d{5,}', '#', text)


def describe(widget, roots):
    row = [widget.winfo_class()]
    for option in OPTIONS:
        try:
            row.append((option, _clean(widget.cget(option), roots)))
        except tk.TclError:
            continue
    try:
        variable = str(widget.cget('textvariable'))
        if variable:
            row.append(('var', _clean(widget.getvar(variable), roots)))
    except tk.TclError:
        pass
    manager = widget.winfo_manager()
    info = {}
    if manager in ('pack', 'grid', 'place'):
        raw = getattr(widget, manager + '_info')()
        info = {key: _clean(value, roots) for key, value in raw.items() if key != 'in'}
    row.append((manager, tuple(sorted(info.items()))))
    row.append(('mapped', bool(widget.winfo_ismapped())))
    row.append(('req', (widget.winfo_reqwidth(), widget.winfo_reqheight())))
    cls = widget.winfo_class()
    if cls == 'Treeview':
        rows = []
        for iid in widget.get_children():
            rows.append((_clean(iid, roots), tuple(_clean(v, roots) for v in widget.item(iid, 'values')),
                         tuple(widget.item(iid, 'tags')), _clean(widget.item(iid, 'text'), roots)))
        row.append(('rows', tuple(rows)))
        row.append(('selection', tuple(_clean(i, roots) for i in widget.selection())))
        row.append(('display', _clean(widget.cget('displaycolumns'), roots)))
    elif cls == 'Text':
        row.append(('content', _clean(widget.get('1.0', 'end'), roots)))
    elif cls in ('TEntry', 'Entry', 'TCombobox'):
        try:
            row.append(('entry', _clean(widget.get(), roots)))
        except tk.TclError:
            pass
    elif cls == 'Listbox':
        row.append(('items', tuple(_clean(widget.get(i), roots) for i in range(widget.size()))))
    elif cls == 'Canvas':
        texts = []
        for item in widget.find_all():
            if widget.type(item) == 'text':
                texts.append(_clean(widget.itemcget(item, 'text'), roots))
        row.append(('canvas', (len(widget.find_all()), tuple(texts))))
    return tuple(row)


def snapshot(root_widget, roots):
    return [describe(w, roots) for w in walk(root_widget)]


def pump(win, seconds=0.05):
    end = time.time() + seconds
    while True:
        win.update()
        if time.time() >= end:
            return
        time.sleep(0.005)


def safe_call(function, *args):
    """步骤里的异常也属于可观察行为：旧新两边必须抛同样的东西。"""
    try:
        return ('ok', function(*args))
    except Exception as exc:
        return ('raised', type(exc).__name__, str(exc))


def buttons(widget):
    return [w for w in walk(widget) if w.winfo_class() in ('TButton', 'Button')]


def button_by_text(widget, text):
    for button in buttons(widget):
        try:
            if str(button.cget('text')) == text:
                return button
        except tk.TclError:
            continue
    return None


def trees(widget):
    return [w for w in walk(widget) if w.winfo_class() == 'Treeview']


def poke(app, label, steps, roots):
    """做一遍通用探测：安全按钮、各个列表的选中／全选／取消、导航按钮。每步后拍一张快照。"""
    content = app.content
    steps.append((label + ':initial', snapshot(content, roots), _clean(app.status.get(), roots)))
    for text in SAFE_BUTTONS:
        button = button_by_text(content, text)
        if button is not None:
            outcome = safe_call(button.invoke)
            pump(app.win)
            steps.append((label + ':button ' + text, outcome, snapshot(content, roots),
                          _clean(app.status.get(), roots)))
    for index, tree in enumerate(trees(content)):
        rows = tree.get_children()
        if not rows:
            continue
        for picked in (rows[:1], rows[:3], rows):
            tree.selection_set(*picked)
            pump(app.win)
            steps.append((label + ':tree%d select %d' % (index, len(picked)), snapshot(content, roots),
                          _clean(app.status.get(), roots)))
        tree.selection_remove(*tree.selection())
        pump(app.win)
        steps.append((label + ':tree%d cleared' % index, snapshot(content, roots)))
    nav = [b for b in buttons(content) if re.fullmatch(r'SH\d+', str(b.cget('text')))]
    for button in nav[:3]:
        outcome = safe_call(button.invoke)
        pump(app.win)
        steps.append((label + ':nav ' + str(button.cget('text')), outcome, snapshot(content, roots),
                      _clean(app.status.get(), roots)))
    return steps
