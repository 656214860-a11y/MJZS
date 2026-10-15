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

# 多个页面 Mixin 与 desktop 共用的页面常量与辅助（原在 desktop 模块级）。
STAGE_ACTION_WIDTH=16  # 所有阶段主操作与“阶段配置”共用宽度，页面操作行左侧对齐。

# 第 31 期第 7 条：资产管理页「参考图」「资产图片」两行的标签宽度（字符数）——一样宽，
# 两行按钮的左边缘才对得齐。
ASSET_ROW_LABEL=6

ASSET_ROWS_PER_FRAME=12

# 第 72 期（Round 3）性能门禁：资产表分段建行——先同步建够第一屏的，剩下的按帧补上。
# 当前资产行高约 80 像素，760 像素窗口可见不足十行；首帧放 24 行仍有三屏余量，
# 又不会在首次绘制时为 48 张图同时登记缩略图任务。余项随后按帧补齐。
ASSET_FIRST_ROWS=24

def _prefs(path):
    if not path:return {}
    # 这里故意用不缓存的 agent.core.read：调用方（当前分镜、资产范围、视频模式）会就地改这份
    # 字典再写回，共享缓存对象一旦被就地改，同一轮里其他读者就会看到没保存的值。
    from project_settings import read_prefs
    return read_prefs(path)


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


def open_studio(*args, **kwargs):
    return _host.open_studio(*args, **kwargs)


def open_directory(*args, **kwargs):
    return _host.open_directory(*args, **kwargs)


def find_editor_shortcut(*args, **kwargs):
    return _host.find_editor_shortcut(*args, **kwargs)


def comfy_executable(*args, **kwargs):
    return _host.comfy_executable(*args, **kwargs)


class _HostAttribute:
    """按名字转发到 ``desktop`` 里的同名对象（messagebox、Desktop 类等），调用时才取值。"""

    def __init__(self, name):
        self._name = name

    def __getattr__(self, attribute):
        return getattr(getattr(_host, self._name), attribute)


messagebox = _HostAttribute("messagebox")
Desktop = _HostAttribute("Desktop")
