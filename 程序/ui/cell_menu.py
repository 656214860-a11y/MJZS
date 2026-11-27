"""内容框格子的右键菜单（查看／删除）——从 cell_hover.py 拆出（R3033 模块棘轮）。

第 46 期第 1／9 条：右键「查看」＝打开这一格（与单击同一条路），「删除」＝只删右键点中的
那一行。删除从此不再看「高亮」：逐个删除认右键那一行，批量删除只认勾选行。
第 52 期第 2 条：菜单只在「鼠标底下这一格真能打开一个文件」时才弹——纯文字格与勾选列
都不弹。delete 收一个人参＝delete(row)，收两个人参＝delete(row, column)（第 57 期第 3 条：
资产页「参考图」那一格删的是这一格的参考图，别处删的还是这一行的那张图）。
"""
import inspect
import tkinter as tk
from ui_widgets import ContextMenu

ROW_MENU_VIEW = '查看'          # 右键菜单第一项：等同单击这一格
ROW_MENU_DELETE = '删除'        # 右键菜单第二项：逐个删除（目标就是右键那一行）


def wants_column(callback):
    """这个回调要不要第二个人参（「哪一列」）：delete(row) 与 delete(row, column) 都收。

    第 57 期第 3 条：资产页「参考图」那一格删的是这一格的参考图，别处删的还是这一行的那张图——
    同一份右键菜单得把「右键落在哪一列」交给回调，而老写法（一个人参）照旧不动。
    """
    try:
        parameters = list(inspect.signature(callback).parameters.values())
    except (TypeError, ValueError):
        return False
    if any(item.kind == item.VAR_POSITIONAL for item in parameters):
        return True
    return len([item for item in parameters
                if item.kind in (item.POSITIONAL_ONLY, item.POSITIONAL_OR_KEYWORD)]) >= 2


def call_delete(delete, row, column):
    """按回调自己的签名把「那一列」传下去。"""
    return delete(row, column) if wants_column(delete) else delete(row)


def popup_row_menu(tree, row, column, view=None, delete=None, x=None, y=None):
    """弹一次「查看／删除」：view(row, column) 与 delete 拿到的都是右键那一格那一行。

    column 给 None＝这一格没有「查看」（比如勾选列）。两项都摆不出来就不弹，返回 None。
    delete 收一个人参＝delete(row)，收两个人参＝delete(row, column)。
    """
    # 保留本模块的可替换菜单工厂，供无 Tk 根窗口的逻辑测试使用。
    context_menu = ContextMenu(tree, menu_factory=tk.Menu)
    has_view = view is not None and column is not None
    if has_view:
        context_menu.command(ROW_MENU_VIEW, lambda: view(row, column))
    if delete is not None:
        if has_view:
            context_menu.separator()
        context_menu.command(ROW_MENU_DELETE, lambda: call_delete(delete, row, column))
    menu = context_menu.menu
    if menu.index('end') is None:
        return None
    context_menu.popup_at(x if x is not None else tree.winfo_pointerx(),
                          y if y is not None else tree.winfo_pointery())
    return menu


def bind_row_menu(tree, view=None, delete=None, columns=None, checkbox_column='#0'):
    """给内容框装右键菜单（第 46 期第 1 条）：columns 给 None 就认所有格。

    只认格子上（表头、列宽拖动条上不弹），并把右键那一行交给调用方——调用方因此不必
    去猜「用户到底想删高亮那行还是勾选那行」。

    第 52 期第 2 条：勾选列不弹（那一格没有可打开的文件）；columns 给了就只认这几列。
    """
    allowed = None if columns is None else {str(item) for item in columns}

    def handler(event):
        if tree.identify_region(event.x, event.y) not in ('cell', 'tree'):
            return None
        row = tree.identify_row(event.y)
        if not row:
            return None
        column = tree.identify_column(event.x)
        if column == checkbox_column:
            return None
        if allowed is not None and column not in allowed:
            return None
        popup_row_menu(tree, row, column, view, delete, event.x_root, event.y_root)
        return 'break'

    tree.bind('<Button-3>', handler, add='+')
    tree.row_menu = handler
    return handler
