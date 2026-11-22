# -*- coding: utf-8 -*-
"""L4-U7c：04 预演、11 配音、12 剪辑、13 交付四页的整行宽按钮改成分组的标准按钮。

每页一条用例，量三件事：

- 每颗按钮的实际宽度不超过标准宽度的两倍。标准宽度取页面同一套 ``Tokens.*.TButton``
  样式、宽度为 ``STAGE_ACTION_WIDTH`` 的按钮实测值（不写像素魔数）；
- 同组按钮在同一行（``winfo_rooty`` 相同），且按钮挂在 ``FlowBar`` 里，不再由页面
  ``self.button(self.content, …)`` 整行铺开；
- 按钮总数与文字与改前一致（``*_BUTTONS`` 是改前快照）。

11／12／13 另量分组名与组内按钮；04 另量 880×600 下「确认预演」与三个确认勾选
落在页面可视区内（页面没有可见纵向滚动条，只能靠可见区）。

空项目下 12、13 页会走引导分支（L4-U6），本模块用补上分镜前置的夹具量按钮，
不拆引导分支。
"""
import sys
import unittest
from pathlib import Path
from tkinter import ttk

PROGRAM = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(TESTS))

import test_desktop_media_pages as media_fixtures  # noqa: E402  先加载自检环境
import desktop_media_pages  # noqa: E402,F401  （--affected desktop_media_pages 的消费者）
import tk_test_support  # noqa: E402
from responsive_ui import FlowBar  # noqa: E402
from ui.desktop_page_registry import PAGE  # noqa: E402
from ui.desktop_page_support import STAGE_ACTION_WIDTH  # noqa: E402

# 改前快照：按钮文字（顺序按页面原顺序，断言时按集合比较）。
ANIMATIC_BUTTONS = ('导入共享参考图', '选择分镜初稿', '选择临时音频', '本地生成参考草图',
                    '生成分镜预演', '观看预演视频', '确认预演（SG-B）')

AUDIO_BUTTONS = ('手动制作配音', '生成配音（TTS）', '逐句配音（分句）', '配音设置',
                 '导入配音 / 音乐', '校验并确认本阶段成果', '导出对白字幕 SRT',
                 '导出对白脚本 TXT', '打开音频目录', '打开字幕目录',
                 '打开 ElevenLabs（浏览器）')

EDIT_BUTTONS = ('手动制作剪辑', '自动粗剪整集（跳过未验收镜头）', '整理剪映素材交接包',
                '转场：无转场（点击切换）', '背景音乐：未设置', '清除背景音乐',
                '导出抖音版（1080x1920）', '导出B站版（1920x1080）',
                '导出YouTube版（3840x2160）', '启动剪映', '打开后期目录', '校验交接包',
                '校验并确认本阶段成果', '保存剪辑优化清单')

DELIVERY_BUTTONS = ('手动制作交付', '导入剪映最终成片', '校验并确认本阶段成果',
                    '生成商用待填资料', '核验商用交付资料', '选择采用版本…',
                    '打开交付目录', '打开自动剪辑与QC报告目录')

AUDIO_GROUPS = {
    '导入与确认': ('导入配音 / 音乐', '校验并确认本阶段成果'),
    '导出': ('导出对白字幕 SRT', '导出对白脚本 TXT'),
    '打开目录与外部工具': ('打开音频目录', '打开字幕目录', '打开 ElevenLabs（浏览器）'),
}

EDIT_GROUPS = {
    '粗剪与交接': ('自动粗剪整集（跳过未验收镜头）', '整理剪映素材交接包'),
    '转场与配乐': ('转场：无转场（点击切换）', '背景音乐：未设置', '清除背景音乐'),
    '导出平台版本': ('导出抖音版（1080x1920）', '导出B站版（1920x1080）',
                     '导出YouTube版（3840x2160）'),
    '外部工具与目录': ('启动剪映', '打开后期目录'),
    '校验与确认': ('校验交接包', '校验并确认本阶段成果'),
    '优化清单': ('保存剪辑优化清单',),
}

DELIVERY_GROUPS = {
    '导入与确认': ('导入剪映最终成片', '校验并确认本阶段成果'),
    '商用资料': ('生成商用待填资料', '核验商用交付资料'),
    '版本与目录': ('选择采用版本…', '打开交付目录', '打开自动剪辑与QC报告目录'),
}


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


class MediaPageButtonTests(media_fixtures._DesktopCase):
    """补上分镜前置后再量按钮：12、13 页此时不再是引导页。"""

    with_storyboard = True

    def setUp(self):
        super().setUp()
        self.assertTrue(self.desktop.align_studio(), '夹具应补上视频前置（studio）')
        tk_test_support.pump(self.win, .5)

    def _close_desktop(self):
        """关窗前取消版本检查那条 after 作业，避免测试结束后报 invalid command name。"""
        super()._close_desktop()
        try:
            for job in self.win.tk.call('after', 'info'):
                if 'start_update_check' in str(self.win.tk.call('after', 'info', job)):
                    self.win.after_cancel(job)
        except Exception:
            pass

    # ── 量几何的小工具 ───────────────────────────────────────────
    def _open(self, page_name):
        page = PAGE[page_name]
        thrown = self.open_page(page)
        self.assertEqual([], thrown, '第%02d页打开时抛出 Tk 回调异常' % page)
        self.assertEqual(page, self.desktop.page_index)
        return self.desktop

    def _buttons(self):
        return [w for w in _walk(self.desktop.content) if isinstance(w, ttk.Button)]

    def _standard_width(self):
        """同一套 Tokens 按钮样式、宽度取 STAGE_ACTION_WIDTH 的实测宽度。"""
        holder = ttk.Frame(self.desktop.content)
        holder.pack()
        reference = ttk.Button(holder, text='标准宽度', style='Tokens.Secondary.TButton',
                               width=STAGE_ACTION_WIDTH)
        tk_test_support.pump(self.win, .2)
        width = reference.winfo_reqwidth()
        holder.destroy()
        self.assertGreater(width, 0, '量不出标准宽度')
        return width

    def _assert_standard_buttons(self, expected, label):
        buttons = self._buttons()
        self.assertEqual(sorted(expected), sorted(str(b.cget('text')) for b in buttons),
                         '%s：按钮总数或文字与改前快照不一致' % label)
        limit = self._standard_width() * 2
        for button in buttons:
            text = str(button.cget('text'))
            self.assertGreater(button.winfo_width(), 0, '%s：「%s」没有实际宽度' % (label, text))
            self.assertLessEqual(
                button.winfo_width(), limit,
                '%s：「%s」实际宽 %d，超过标准宽度的两倍 %d（仍是整行宽按钮）'
                % (label, text, button.winfo_width(), limit))
            self.assertIsInstance(
                button.master, FlowBar,
                '%s：「%s」应挂在 FlowBar 里，不再由页面整行铺开' % (label, text))

    def _assert_groups(self, groups, label):
        for title, texts in groups.items():
            labels = [w for w in _walk(self.desktop.content)
                      if isinstance(w, ttk.Label) and str(w.cget('text')) == title]
            self.assertEqual(1, len(labels), '%s：应有且只有一个分组名「%s」' % (label, title))
            bar = labels[0].master
            self.assertIsInstance(bar, FlowBar, '%s：分组名「%s」应写在 FlowBar 行首' % (label, title))
            buttons = [w for w in bar.winfo_children() if isinstance(w, ttk.Button)]
            self.assertEqual(sorted(texts), sorted(str(b.cget('text')) for b in buttons),
                             '%s：「%s」分组里的按钮与约定不一致' % (label, title))
            rows = {b.winfo_rooty() for b in buttons}
            self.assertEqual(1, len(rows),
                             '%s：「%s」同组按钮应在同一行（实测 y=%r）' % (label, title, rows))

    def _assert_bars_are_rows(self, label):
        bars = [w for w in _walk(self.desktop.content) if isinstance(w, FlowBar)]
        rows = []
        for bar in bars:
            buttons = [w for w in bar.winfo_children() if isinstance(w, ttk.Button)]
            if not buttons:
                continue
            rows.append(buttons)
            ys = {b.winfo_rooty() for b in buttons}
            self.assertEqual(1, len(ys), '%s：同一行 FlowBar 里的按钮应在同一行（y=%r）' % (label, ys))
        self.assertGreaterEqual(len(rows), 2, '%s：按钮应分成多行 FlowBar，而不是一行一个竖排' % label)
        self.assertGreaterEqual(max(len(row) for row in rows), 2,
                                '%s：至少一行 FlowBar 里要并排两颗按钮' % label)

    def _assert_visible(self, widgets, label):
        canvas = self.desktop.canvas
        top = canvas.winfo_rooty()
        bottom = top + canvas.winfo_height()
        for widget in widgets:
            name = str(widget.cget('text'))
            self.assertTrue(widget.winfo_ismapped(), '%s：「%s」应已映射' % (label, name))
            self.assertGreaterEqual(widget.winfo_rooty(), top,
                                    '%s：「%s」不得被可视区上沿裁掉' % (label, name))
            self.assertLessEqual(
                widget.winfo_rooty() + widget.winfo_height(), bottom,
                '%s：「%s」必须落在页面可视区内（底沿 %d）' % (label, name, bottom))

    # ── 四页各一条 ───────────────────────────────────────────────
    def test_04_animatic_grouped_buttons_and_confirm_visible(self):
        """04：按钮不再竖排；880×600 下「确认预演」与三个勾选可见。"""
        self._open('animatic')
        self._assert_standard_buttons(ANIMATIC_BUTTONS, '04 分镜预演')
        self._assert_bars_are_rows('04 分镜预演')
        self.win.geometry('880x600+0+0')
        tk_test_support.pump(self.win, .8)
        confirms = [b for b in self._buttons() if str(b.cget('text')) == '确认预演（SG-B）']
        self.assertEqual(1, len(confirms), '04 页应有且只有一颗「确认预演（SG-B）」')
        checks = [w for w in _walk(self.desktop.content) if isinstance(w, ttk.Checkbutton)]
        self.assertEqual(3, len(checks), '04 页应有三个确认勾选')
        self._assert_visible(confirms + checks, '04 分镜预演 880×600')

    def test_11_audio_buttons_standard_and_grouped(self):
        """11：7 个整行宽按钮改标准宽度，按三组分行，行首有组名。"""
        self._open('audio')
        self._assert_standard_buttons(AUDIO_BUTTONS, '11 配音与字幕')
        self._assert_groups(AUDIO_GROUPS, '11 配音与字幕')

    def test_12_editing_buttons_standard_and_grouped(self):
        """12：整行宽按钮改标准宽度并分组（分组名写进结果文件）。"""
        self._open('edit')
        self._assert_standard_buttons(EDIT_BUTTONS, '12 后期剪辑')
        self._assert_groups(EDIT_GROUPS, '12 后期剪辑')

    def test_13_delivery_buttons_standard_and_grouped(self):
        """13：整行宽按钮改标准宽度并分组（分组名写进结果文件）。"""
        self._open('delivery')
        self._assert_standard_buttons(DELIVERY_BUTTONS, '13 质检与交付')
        self._assert_groups(DELIVERY_GROUPS, '13 质检与交付')


if __name__ == '__main__':
    unittest.main()
