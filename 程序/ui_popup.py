# -*- coding: utf-8 -*-
"""提示浮层不当对话框（R1976）。"""


def make_passive_popup(window):
    """ui_theme.install_window_placement 给每个新 Toplevel 设 -alpha 0、<Map> 时 grab_set 并居中。

    提示浮层一旦抓了 grab，鼠标还停在表格上就会被判成「离开」，卡片刚出现就被自己收掉；点击也会被
    吞给浮层。这里在 <Map> 之前把它摘出来：标记已定位、去掉绑定的 Map／Unmap、直接显形。
    """
    window._positioned_once = True
    window.unbind("<Map>")
    window.unbind("<Unmap>")
    window.attributes("-alpha", 1)
