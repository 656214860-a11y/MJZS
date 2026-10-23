"""测试共用的 Tk 控件树遍历：取文本、找控件。只吞 TclError（控件无 text 选项或已销毁），其它异常照常抛出。"""
try:
    import tkinter as tk
    TclError = tk.TclError
except ImportError:  # 无 Tk 的平台：调用方自己 skip，这里只保证能被导入
    TclError = RuntimeError


def _matches(widget, kinds):
    """kinds 为 None 匹配全部；字符串按 winfo_class 比，类型按 isinstance 比。"""
    if kinds is None:
        return True
    names = tuple(k for k in kinds if isinstance(k, str))
    types = tuple(k for k in kinds if isinstance(k, type))
    try:
        if names and widget.winfo_class() in names:
            return True
    except TclError:
        return False
    return bool(types) and isinstance(widget, types)


def _as_kinds(kinds):
    if kinds is None or isinstance(kinds, (str, type)):
        return None if kinds is None else (kinds,)
    return tuple(kinds)


def widget_list(widget, kinds=None):
    """递归收集匹配的控件（先父后子，即打包顺序）。"""
    kinds = _as_kinds(kinds)
    found = [widget] if _matches(widget, kinds) else []
    for child in widget.winfo_children():
        found.extend(widget_list(child, kinds))
    return found


def widget_texts(widget, kinds=None):
    """递归收集匹配控件的 text；没有 text 选项的控件跳过。"""
    found = []
    for item in widget_list(widget, kinds):
        try:
            found.append(str(item.cget('text')))
        except TclError:
            pass
    return found
