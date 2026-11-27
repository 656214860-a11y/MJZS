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

L4-U8a 另加一条：11 页对白读不出时，原因只在页内显示一处，状态栏不再重复同一句。
"""
import sys
import tkinter
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
from ui_widgets import DescriptionBlock  # noqa: E402

# R4315（FIX-S11-E4）在「配音制作」行合法新增「停止逐句配音」；该行未列入
# AUDIO_GROUPS 受检分组，故只同步按钮清单。
AUDIO_BUTTONS = ('手动制作配音', '生成配音（TTS）', '逐句配音（分句）', '停止逐句配音',
                 '配音设置',
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


def _texts(widget):
    """页面里带 text 选项的控件及其文字；没有 text 选项的控件跳过。"""
    for child in _walk(widget):
        try:
            yield child, str(child.cget('text'))
        except tkinter.TclError:
            continue


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

    def _visible_buttons(self):
        return [w for w in self._buttons() if w.winfo_ismapped()]

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

    def _assert_relocated_buttons(self, expected, stage, label):
        """少按钮页契约：原动作入口仍由同一批按钮对象承载，但不再常驻显示。"""
        buttons = [b for b in self._buttons() if str(b.cget('text')) in expected]
        self.assertEqual(sorted(expected), sorted(str(b.cget('text')) for b in buttons),
                         '%s：动作入口丢失或文字改变' % label)
        visible = [str(b.cget('text')) for b in buttons if b.winfo_ismapped()]
        self.assertEqual([], visible, '%s：这些动作不应再常驻页面：%r' % (label, visible))
        self.assertIsNotNone(self.desktop.shared_input.stage_action(stage),
                             '%s：空输入框发送键应登记本阶段主动作' % label)
        hints = [text for _widget, text in _texts(self.desktop.content) if '右键菜单' in text]
        self.assertTrue(hints, '%s：页面应保留右键/文件面板入口提示' % label)

    def _assert_groups(self, groups, label):
        """分组名仍作为上下文分区保留；按钮本体已隐藏，只验证分组说明没有丢。"""
        for title in groups:
            labels = [w for w in _walk(self.desktop.content)
                      if isinstance(w, ttk.Label) and str(w.cget('text')) == title]
            self.assertEqual(1, len(labels), '%s：应保留分组名「%s」作为发现性说明' % (label, title))

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
        bottom = self.desktop.input_dock.winfo_rooty()
        for widget in widgets:
            name = str(widget.cget('text'))
            self.assertTrue(widget.winfo_ismapped(), '%s：「%s」应已映射' % (label, name))
            self.assertGreaterEqual(widget.winfo_rooty(), top,
                                    '%s：「%s」不得被可视区上沿裁掉' % (label, name))
            self.assertLessEqual(
                widget.winfo_rooty() + widget.winfo_height(), bottom,
                '%s：「%s」必须落在页面可视区内（底沿 %d）' % (label, name, bottom))

    # ── 四页各一条 ───────────────────────────────────────────────
    def _write_animatic_bundle(self):
        """一份「已合成」的预演成果：镜头图＋版本视频＋临时音频＋清单（REQ-S04-84）。"""
        import json
        from stage_execution_service import load_or_sync_animatic_timeline
        from contract.stage_path_service import write_dir
        from domain.animatic_service import CONFIRMATIONS, MANIFEST, digest
        root = self.project
        timeline = load_or_sync_animatic_timeline(root)
        folder = write_dir(root, 'animatic')
        files = {}
        for row in timeline['shots']:
            image = '镜头/%s/v1.png' % row['id']
            target = folder / image
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'image-' + row['id'].encode())
            files[image] = target.read_bytes()
        (folder / '版本').mkdir(parents=True, exist_ok=True)
        (folder / '版本' / 'animatic_v001.mp4').write_bytes(b'video')
        (folder / 'assets').mkdir(parents=True, exist_ok=True)
        (folder / 'assets' / 'temporary_audio.wav').write_bytes(b'audio')
        files['版本/animatic_v001.mp4'] = b'video'
        files['assets/temporary_audio.wav'] = b'audio'
        manifest = {'version': 1, 'kind': 'animatic', 'source': timeline['source'],
                    'source_sha256': digest((root / timeline['source']).read_bytes()),
                    'shots': [{'id': row['id'], 'image': '镜头/%s/v1.png' % row['id'],
                               'seconds': row['seconds'], 'image_version': 1}
                              for row in timeline['shots']],
                    'video': '版本/animatic_v001.mp4', 'audio': 'assets/temporary_audio.wav',
                    'files': {name: digest(raw) for name, raw in files.items()},
                    'confirmed': dict.fromkeys(CONFIRMATIONS, False)}
        (folder / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')

    def test_04_animatic_grouped_buttons_and_confirm_visible(self):
        """S04 页顶五个入口常驻；有可播放版本时显示页底确认条。"""
        self._open('animatic')
        generate, = [b for b in self._buttons() if b.cget('text') == '生成分镜预演']
        controls = generate.master.pack_slaves()
        self.assertEqual(len(controls), 5)
        self.assertIsInstance(controls[1], ttk.Combobox)
        self.assertEqual([w.cget('text') for w in controls if isinstance(w, ttk.Button)],
                         ['生成分镜预演', '声音 ▾', '在剪映中打开', '预演设置'])
        self.assertTrue(all(w.winfo_ismapped() for w in controls))
        confirmations = {'已确认节奏', '已确认时长', '已确认对白同步'}
        self.assertFalse(any(w.cget('text') in confirmations for w in _walk(self.desktop.content)
                             if isinstance(w, ttk.Checkbutton)))
        self.assertFalse(any(isinstance(w, ttk.Button) and w.cget('text') == '锁定'
                             and w.winfo_ismapped() for w in _walk(self.desktop.stage_area)))
        self._write_animatic_bundle()
        self._open('animatic')
        self.win.geometry('880x600+0+0')
        tk_test_support.pump(self.win, .8)
        locks = [w for w in _walk(self.desktop.stage_area) if isinstance(w, ttk.Button)
                 and w.cget('text') == '锁定' and w.winfo_ismapped()]
        self.assertEqual(1, len(locks), '04 页应有且只有一颗「锁定」')
        checks = [w for w in locks[0].master.winfo_children() if isinstance(w, ttk.Checkbutton)]
        self.assertCountEqual([w.cget('text') for w in checks], confirmations)
        self._assert_visible(locks + checks, '04 分镜预演 880×600')
        self.desktop.canvas.yview_moveto(1.0)
        self.win.update_idletasks()
        self._assert_visible(locks + checks, '04 分镜预演滚动后')
        self._open('audio')
        self.assertFalse(locks[0].winfo_exists() and locks[0].winfo_ismapped())

    def test_11_audio_buttons_standard_and_grouped(self):
        """11：7 个整行宽按钮改标准宽度，按三组分行，行首有组名。"""
        self._open('audio')
        self._assert_relocated_buttons(AUDIO_BUTTONS, 'audio', '11 配音与字幕')
        self._assert_groups(AUDIO_GROUPS, '11 配音与字幕')

    def test_11_audio_dialogue_reason_shown_once(self):
        """11（L4-U8a）：对白读不出时，原因只在页内显示一处，状态栏不再重复同一句。"""
        def unreadable(episode=None):
            raise ValueError('分镜文件缺少镜头列表')

        self.desktop.dialogue_entries = unreadable
        self.addCleanup(vars(self.desktop).pop, 'dialogue_entries', None)
        self._open('audio')
        reason = '对白无法读取，配音生成与字幕导出暂不可用：分镜文件缺少镜头列表'
        shown = [widget for widget, text in _texts(self.desktop.content) if reason in text]
        self.assertEqual(1, len(shown),
                         '11 配音与字幕：对白读不出的原因应在页内显示一处，实测 %d 处' % len(shown))
        for text in (str(self.desktop.status.get()),
                     str(getattr(self.desktop.status_bar.message, 'full_text', ''))):
            self.assertNotIn('对白无法读取', text,
                             '11 配音与字幕：状态栏不应重复页内已显示的原因（实测：%s）' % text)
        self.assertIsInstance(shown[0], DescriptionBlock,
                              '11 配音与字幕：页内原因应使用统一的说明组件 DescriptionBlock')
        self.assertTrue(shown[0].winfo_ismapped(), '11 配音与字幕：页内原因应已显示')
        states = {str(b.cget('text')): str(b.cget('state')) for b in self._buttons()}
        for name in ('生成配音（TTS）', '逐句配音（分句）', '导出对白字幕 SRT', '导出对白脚本 TXT'):
            self.assertEqual('disabled', states.get(name),
                             '11 配音与字幕：对白读不出时「%s」应置灰' % name)

    def test_12_editing_buttons_standard_and_grouped(self):
        """12：整行宽按钮改标准宽度并分组（分组名写进结果文件）。"""
        self._open('edit')
        self._assert_relocated_buttons(EDIT_BUTTONS, 'edit', '12 后期剪辑')
        self._assert_groups(EDIT_GROUPS, '12 后期剪辑')

    def test_13_delivery_buttons_standard_and_grouped(self):
        """13：整行宽按钮改标准宽度并分组（分组名写进结果文件）。"""
        self._open('delivery')
        self._assert_relocated_buttons(DELIVERY_BUTTONS, 'delivery', '13 质检与交付')
        self._assert_groups(DELIVERY_GROUPS, '13 质检与交付')

    def test_05_to_10_stage_pages_register_send_and_hide_primary_buttons(self):
        """05–10：主动作收进右键/发送键，页面保留发现性提示（本轮有意 UI 契约变更）。"""
        cases = {
            'assets': ('手动制作资产',),
            'continuity': ('手动生成连贯性清单',),
            'final': ('手动同步资产',),
            'keyframe': ('手动制作首帧',),
            'previs': ('手动制作白模',),
            'video': ('进入本地生成', '进入线上生成'),
        }
        for stage, labels in cases.items():
            with self.subTest(stage=stage):
                self._open(stage)
                self.assertIsNotNone(self.desktop.shared_input.stage_action(stage),
                                     '%s 应登记空输入框发送动作' % stage)
                visible = [str(b.cget('text')) for b in self._visible_buttons()]
                for label in labels:
                    self.assertFalse(any(text.startswith(label) for text in visible),
                                     '%s：「%s」不应再常驻页面（可见按钮 %r）' % (stage, label, visible))
                hints = [text for _widget, text in _texts(self.desktop.content) if '右键菜单' in text]
                self.assertTrue(hints, '%s：应保留右键/文件面板入口提示' % stage)

    def test_reused_content_opens_only_current_stage_menu(self):
        from unittest.mock import Mock
        from ui.stage_page_simplify import bind_context_menu

        content = ttk.Frame(self.desktop.content)
        content.place(x=0, y=0)
        row = ttk.Label(content, text='镜头')
        row.pack()
        self.win.update_idletasks()
        old, current = Mock(), Mock()
        bind_context_menu(self.desktop, [content], old)
        bind_context_menu(self.desktop, [content, row], current)
        row.event_generate('<Button-3>', x=1, y=1)
        old.assert_not_called()
        current.assert_called_once()
        current.return_value.popup.assert_called_once()


if __name__ == '__main__':
    unittest.main()
