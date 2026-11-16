# -*- coding: utf-8 -*-
"""缩略图放大图的收起与点击抑制（R3012 自 ``cell_hover`` 拆出，行数棘轮）。

``CellImages`` 混入 ``CellZoomSuppress``：点击选择行／双击打开后收起放大图并抑制
重弹，直到指针离开该格再进入（``_zoom_suppress``）；``zoom_hide`` 与
``zoom_cancel_watch`` 是放大图生命周期的收起半边，供 ``zoom_in``／``zoom_leave``／
看门狗与事件绑定共用——只依赖宿主实例属性，不直接触碰 Tk 控件。
"""
import app_logging


class CellZoomSuppress:
    """混入 ``CellImages``：``_zoom_suppress`` 状态、点击钩子、绑定助手与收起原语。"""

    _zoom_suppress = False      # 类属性默认；实例赋值即遮蔽（等价原 __init__ 实例属性）

    # ── 收起原语 ─────────────────────────────────────────────────────────
    def zoom_hide(self):
        """收起放大图：鼠标一走、一滚、这一层一重排就收。"""
        if self.zoom_pending is not None:
            try:
                self._zoom_owner.after_cancel(self.zoom_pending)
            except Exception:
                app_logging.swallowed()
            self.zoom_pending = None
        self.zoom_cancel_watch()
        self.zoom_key = None
        self.zoom_at = None
        if self.zoom_label is not None:
            try:
                self.zoom_label.place_forget()
            except Exception:
                app_logging.swallowed()
        return None

    def zoom_cancel_watch(self):
        if self.zoom_watch is not None:
            try:
                self._zoom_owner.after_cancel(self.zoom_watch)
            except Exception:
                app_logging.swallowed()
            self.zoom_watch = None
        return None

    # ── 点击抑制（R3012）─────────────────────────────────────────────────
    def _zoom_click(self, key):
        """这格被点击（选择行／双击打开）后：收起放大图并抑制重弹，直到指针离开再进入。"""
        self._zoom_suppress = True
        if self.zoom_key == key:
            self.zoom_hide()
        return None

    def _bind_zoom_click(self, label, key):
        # R3012：点击选择行／打开后抑制放大，直到指针离开再进入（登记在前，不拦原行为）。
        label.bind('<Button-1>', lambda event, key=key: self._zoom_click(key), add='+')
        label.bind('<Double-1>', lambda event, key=key: self._zoom_click(key), add='+')
