"""页面 Mixin 共用的宿主转发与页面常量（L4）。

``Desktop`` 的页面构建方法正逐页迁到 ``desktop_*_page.py`` 的 Mixin 里（R1499 起）。这些方法用到
``confirm``／``open_path``／``ContextMenu``／``FileDialog`` 等名字，而测试按 ``desktop.<名字>`` 打补丁；
这里的转发函数在调用时取 ``desktop`` 里的当前值，所以补丁照常生效。``desktop`` 在模块级调用
``bind_host`` 登记自身，本模块不导入 ``desktop``，没有导入环。多页共用的缩略图／行高常量也放这里。
"""
from responsive_ui import row_height_for

# 第 52 期第 3 条：资产管理「名称」「导入图片」两列的缩略图——长边 72 像素，行高 80（图上下留白）。
# 第 65 期任务 4：用户要「缩略图缩小一倍」，这一档 72 → 36（行高跟着 fit_row_height 一起收）。
THUMB_SIZE = 36
# 第 58 期第 2 条：行高按格子里最高的那点内容算——这两张表是 72 像素的缩略图，
# 行高就是图高加上下余地（实际值由 responsive_ui.fit_row_height 当场算）。
ASSET_ROW_HEIGHT = row_height_for(THUMB_SIZE)

_host = None


def bind_host(module):
    """由 ``desktop`` 在定义完 confirm／ContextMenu 等名字后调用，登记转发目标。"""
    global _host
    _host = module


def confirm(*args, **kwargs):
    return _host.confirm(*args, **kwargs)


def open_path(*args, **kwargs):
    return _host.open_path(*args, **kwargs)


def ContextMenu(*args, **kwargs):  # noqa: N802 - 与原名一致，方法体未改
    return _host.ContextMenu(*args, **kwargs)


def FileDialog(*args, **kwargs):  # noqa: N802
    return _host.FileDialog(*args, **kwargs)


def confirm_project_removal_from_last_script(*args, **kwargs):
    return _host.confirm_project_removal_from_last_script(*args, **kwargs)
