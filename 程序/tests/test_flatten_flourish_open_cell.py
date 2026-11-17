"""压平 pet_ui_support.flourish 与 _AssetPage.open_cell 的 elif 长链：旧实现原样内嵌，
用记账替身把每种姿势／每一列都跑一遍，逐次对照画了什么、调了谁。"""
import unittest
from types import SimpleNamespace
from unittest import mock

import desktop_asset_pages
import ui.pet_ui_support as pet_ui_support
LEGACY_FLOURISH = r'''def _legacy_flourish(canvas, pose, step, ox, oy, body, outline, accent, blush):
    """这一帧的猫在做什么：爪子／舌头／张开的嘴／甩起来的尾巴／腮红。

    每个动作各自带一个 'pose-xxx' 标签；端坐（sit）不加东西，就是上面那套基础画法。
    """
    if pose == 'walk':
        for paw in (14, 44):
            canvas.create_oval(paw + ox, 50 + oy, paw + 10 + ox, 58 + oy,
                               fill=body, outline=outline, width=1, tags=('pose-walk', 'paw'))
    elif pose == 'lick':
        canvas.create_line(50 + ox, 44 + oy, 58 + ox, 54 + oy, fill=body, width=6,
                           tags=('pose-lick', 'paw'))
        canvas.create_arc(27 + ox, 43 + oy, 37 + ox, 54 + oy, start=180, extent=180,
                          style='pieslice', fill=TONGUE, outline=outline, tags=('pose-lick', 'tongue'))
    elif pose == 'yawn':
        # 第 24 期第 6 条：原来打哈欠是在脸上张开一张墨色的嘴——64 像素里就是一个黑窟窿
        # （用户原话「像有个黑色大鼻子很丑」）。改成两团腮红：困意靠脸红说，脸不用张开。
        for side in (13, 43):
            canvas.create_oval(side + ox, 37 + oy, side + 8 + ox, 44 + oy, fill=blush,
                               outline='', tags=('pose-yawn', 'blush'))
    elif pose == 'wag':
        sway = 6 if step % 2 else -6
        canvas.create_line(56 + ox, 54 + oy, 63 + ox, 54 + sway + oy, smooth=True,
                           fill=outline, width=3, tags=('pose-wag', 'tail'))
    elif pose == 'nuzzle':
        for side in (14, 42):
            canvas.create_oval(side + ox, 40 + oy, side + 8 + ox, 46 + oy, fill=blush,
                               outline='', tags=('pose-nuzzle', 'blush'))
    return pose
'''

LEGACY_OPEN_CELL = r'''def _legacy_open_cell(self, aid,col):
    self.table.selection_set(aid);self.table.focus(aid)
    if col=='#0':
        self.toggle_asset(aid);return
    if col=='#1':
        # 第 64 期任务 13：「资产编号」那一格就是进详情的入口（主页面不再嵌正典板）。
        # 走 after_idle：点这一格的是内容框自己的事件处理，等它结束再整页重建。
        self.page.win.after_idle(lambda:self.page.safe(lambda:self.page.open_asset_detail(aid)))
    elif col=='#2':
        def save_name(name):
            self.page.rename_asset(aid,name,refresh=False)
            self.registry[aid]['name']=name;self.table.set(aid,'name',name)
        self.table.cell_hover.edit_name(aid,self.registry[aid].get('name',aid),save_name,self.page.status.set,'#2')
    elif col=='#3':
        if self.registry[aid]['status']=='已导入':self.preview()
    elif col=='#4':self.page.view_reference_images(aid)
    elif col=='#5':self.detail(aid,'note')
    elif col=='#6':self.show_prompt(self.page,aid,self.registry[aid])
'''


class _Canvas:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.calls.append((name, args, sorted(kwargs.items())))


class FlourishEquivalence(unittest.TestCase):
    def test_every_pose_and_step_draws_the_same(self):
        namespace = dict(vars(pet_ui_support))
        exec(compile(LEGACY_FLOURISH, 'legacy_flourish', 'exec'), namespace)
        drawn = 0
        for pose in ('sit', 'walk', 'lick', 'yawn', 'wag', 'nuzzle', 'unknown', None):
            for step in (0, 1, 2, 7):
                for ox, oy in ((0, 0), (3, -2)):
                    old, new = _Canvas(), _Canvas()
                    args = (pose, step, ox, oy, '#body', '#line', '#accent', '#blush')
                    self.assertEqual(pet_ui_support.flourish(new, *args), namespace['_legacy_flourish'](old, *args))
                    self.assertEqual(new.calls, old.calls, (pose, step))
                    drawn += len(new.calls)
        self.assertGreater(drawn, 50)   # 对照不能是空对空


class _Recorder:
    """open_cell 的宿主：所有方法调用都记账，registry 是真字典。"""

    def __init__(self, status):
        self.log = []
        self.registry = {'A1': {'name': '旧名', 'status': status}}
        self.page = self._node('page')
        self.page.win = self._node('page.win')
        self.page.status = self._node('page.status')
        self.table = self._node('table')
        self.table.cell_hover = self._node('table.cell_hover')

    def _node(self, label):
        log = self.log

        class Node:
            def __getattr__(self, name):
                return lambda *args, **kwargs: log.append((label + '.' + name, args, kwargs))
        return Node()

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return lambda *args, **kwargs: self.log.append(('self.' + name, args, kwargs))


def _normalise(log):
    out = []
    for name, args, kwargs in log:
        out.append((name, tuple('<callable>' if callable(a) else a if isinstance(a, (str, int, float, bool, dict, tuple, type(None))) else '<' + type(a).__name__ + '>' for a in args), sorted(kwargs.items())))
    return out


class OpenCellEquivalence(unittest.TestCase):
    def test_every_column_routes_the_same(self):
        namespace = dict(vars(desktop_asset_pages))
        exec(compile(LEGACY_OPEN_CELL, 'legacy_open_cell', 'exec'), namespace)
        legacy = namespace['_legacy_open_cell']
        current = desktop_asset_pages._AssetPage.open_cell
        routed = 0
        for status in ('已导入', '待生成'):
            for col in ('#0', '#1', '#2', '#3', '#4', '#5', '#6', '#7', 'name'):
                old, new = _Recorder(status), _Recorder(status)
                self.assertEqual(current(new, 'A1', col), legacy(old, 'A1', col))
                self.assertEqual(_normalise(new.log), _normalise(old.log), (status, col))
                routed += len(new.log)
                # 回调也要一样：after_idle 里的详情入口、改名框的保存函数
                for (name, args, _), (old_name, old_args, _) in zip(new.log, old.log):
                    for a, b in zip(args, old_args):
                        if callable(a) and name.endswith('edit_name'):
                            a('新名'), b('新名')
                            self.assertEqual(_normalise(new.log), _normalise(old.log))
                            self.assertEqual(new.registry, old.registry)
        self.assertGreater(routed, 20)


if __name__ == '__main__':
    unittest.main()
