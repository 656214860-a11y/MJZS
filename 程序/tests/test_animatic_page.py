# -*- coding: utf-8 -*-
"""REQ-S04-95…99 + DES-S04-25：S04 分镜预演少按钮新布局——``ui/animatic_page.py`` 契约。

布局：上方播放区＋中间时间线（对白／音乐轨）＋右侧文件面板（导入自动分类、
点选分镜、参考图右键）＋底栏发送键（空＝生成预演，「只重做 SHxxx」＝单镜重做）＋
状态栏摘要＋生成后才出现的三项确认与「锁定」。原 7 项功能入口全部保留，不新增弹窗。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
os.chdir(HERE)

import selftest_env  # noqa: F401,E402  自检环境必须先于 tkinter 生效

import tkinter as tk
from tkinter import ttk

import tk_test_support  # noqa: E402

import ui.animatic_page as animatic_page  # noqa: E402  本卡新建；缺失即本组全红
from infra.pet_state import PAGE_OF as PAGE  # noqa: E402
from ui_widgets import ContextMenu, DescriptionBlock, LineInput, PrimaryButton, SecondaryButton  # noqa: E402


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _storyboard(root, shots=(('SH001', 5),)):
    """已采用分镜一份：03初步分镜/分镜拆分/ep1.json ＋ ui_settings.json。"""
    board = {'episode_id': 'EP001', 'title': '集', 'shots': [
        {'id': sid, 'title': '镜', 'duration': seconds, 'characters': [],
         'location': 'LOC_01', 'frame': 'frames/%s.png' % sid,
         'video_prompt': '提示词' + sid, 'dialogue': []}
        for sid, seconds in shots]}
    source = root / '03初步分镜' / '分镜拆分' / 'ep1.json'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
    relative = source.relative_to(root).as_posix()
    (root / 'ui_settings.json').write_text(json.dumps(
        {'adopted_storyboards': [relative]}, ensure_ascii=False), encoding='utf-8')
    return source


def _animatic_bundle(root, timeline):
    """已合成版本：镜头图＋版本视频＋临时音频＋清单（照 test_req_s04_anchors 口径）。"""
    from contract.stage_path_service import write_dir
    from domain.animatic_service import CONFIRMATIONS, MANIFEST, digest
    folder = write_dir(root, 'animatic')
    files = {}
    for row in timeline['shots']:
        image = '镜头/%s/v1.png' % row['id']
        target = folder / image
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'image-' + row['id'].encode())
        files[image] = target.read_bytes()
        target = folder / '镜头' / row['id'] / 'v2.png'
        target.write_bytes(b'image2-' + row['id'].encode())
        files['镜头/%s/v2.png' % row['id']] = target.read_bytes()
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
    return folder


class _Status:
    def __init__(self):
        self.messages = []

    def set(self, text):
        self.messages.append(str(text))

    def get(self):
        return self.messages[-1] if self.messages else ''


class _Panel:
    """文件面板假实现：只记登记了什么。"""

    def __init__(self):
        self.select = {}
        self.imports = {}
        self.menus = {}

    def set_select_handler(self, key, fn, default=None):
        if fn is None:
            self.select.pop(key, None)
        else:
            self.select[key] = (fn, default)

    def set_import_handler(self, stage, fn):
        if fn is None:
            self.imports.pop(stage, None)
        else:
            self.imports[stage] = fn

    def set_menu_handler(self, stage, fn):
        if fn is None:
            self.menus.pop(stage, None)
        else:
            self.menus[stage] = fn


class _Shared:
    """共享输入框假实现：阶段动作、文本与 on_send 覆盖。"""

    def __init__(self):
        self.actions = {}
        self.on_send = None
        self._text = ''
        self.ended = 0

    def set_stage_action(self, stage, action):
        if action is None:
            self.actions.pop(stage, None)
        else:
            self.actions[stage] = action

    def stage_action(self, stage):
        return self.actions.get(stage)

    def text(self):
        return self._text

    def set_text(self, value):
        self._text = value

    def end_request(self):
        self.ended += 1


class _Files:
    def __init__(self):
        self.results = []
        self.calls = []

    def open_files(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class _Services:
    def __init__(self):
        self.opened = []

    def open_path(self, path):
        self.opened.append(str(path))


class _Page:
    """孤立假宿主：提供页面需要的属性与同步 async_。"""

    def __init__(self, win, project=None):
        self.win = win
        self.root = Path(project) if project else None
        self.content = ttk.Frame(win)
        self.content.pack(fill='both', expand=True)
        self.status = _Status()
        self.settings = {}
        self.worker = False
        self.page_index = 3
        self.files_panel = _Panel()
        self.shared_input = _Shared()
        self.file_dialog = _Files()
        self.media_page_services = _Services()
        self.segments = {}
        self.went = []
        self.reported = []
        self.reply_notes = []
        self.reply_note = lambda kind, stage, text='', **kw: self.reply_notes.append(
            (kind, stage, str(text), kw))

    def async_(self, fn, done=None, show_progress=True, label=None):
        result = fn()
        if done is not None:
            done(result)
        return result

    def safe(self, fn):
        return fn()

    def set_status_segment(self, key, text, tooltip=None):
        self.segments[key] = (str(text), tooltip)

    def go(self, index):
        self.went.append(index)

    def pet_report(self, stage, text):
        self.reported.append((stage, text))


def _labels(widget):
    return [str(w.cget('text')) for w in _walk(widget)
            if isinstance(w, (ttk.Label, tk.Label))]


def _menu_labels(menu):
    last = menu.index('end')
    if last is None:
        return []
    return [str(menu.entrycget(index, 'label'))
            for index in range(0, last + 1)]


class ParseCommandTests(unittest.TestCase):
    """REQ-S04-96：底栏输入框指令解析（无 Tk 的纯函数）。"""

    def test_empty_or_plain_text_means_generate(self):
        for text in ('', '   ', '生成', '重新合成', '把节奏调快一点'):
            with self.subTest(text=text):
                self.assertEqual({'action': 'generate'},
                                 animatic_page.parse_animatic_command(text))

    def test_shot_id_means_redo_and_normalizes(self):
        cases = {'只重做 SH003': 'SH003', '重做 sh003': 'SH003',
                 '重做SH3': 'SH003', '重做 sh12': 'SH012', '重做 SH0007': 'SH007'}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual({'action': 'redo_shot', 'shot_id': expected},
                                 animatic_page.parse_animatic_command(text))


class FormatSummaryTests(unittest.TestCase):
    """REQ-S04-98：状态栏摘要格式。"""

    def test_summary_counts_shots_refs_and_state(self):
        timeline = {'shots': [{'id': 'SH001'}, {'id': 'SH002'}]}
        library = {'角色': ['a'], '场景': [], '风格': ['b', 'c'], '未分类': []}
        text = animatic_page.format_status_summary(timeline, library, '整轨', 'animatic_v001', False)
        self.assertIn('分镜 2 镜', text)
        self.assertIn('参考图 3 张', text)
        self.assertIn('整轨', text)
        self.assertIn('未确认', text)

    def test_summary_locked_and_ungenerated(self):
        locked = animatic_page.format_status_summary(
            {'shots': []}, {}, '逐镜 TTS', 'animatic_v002', True)
        self.assertIn('已锁定', locked)
        fresh = animatic_page.format_status_summary({'shots': []}, {}, '静音', None, False)
        self.assertIn('未生成', fresh)


class SourceBoundaryTests(unittest.TestCase):
    """REQ-S04-99：新页面不弹窗、不手写 PhotoImage、不用裸控件、不读裸 JSON。"""

    def test_module_has_no_forbidden_calls(self):
        import ui.animatic_prefs_bar as animatic_prefs_bar
        for mod in (animatic_page, animatic_prefs_bar):
            source = Path(mod.__file__).read_text(encoding='utf-8')
            for needle in ('tk.PhotoImage', 'messagebox', 'simpledialog', 'Toplevel(',
                           'tk.Menu(', 'ttk.Button(', 'tk.Button(', 'json.loads', 'json.load('):
                with self.subTest(module=mod.__name__, needle=needle):
                    self.assertNotIn(needle, source)


class _PageCase(unittest.TestCase):
    """隐藏根窗＋孤立假宿主；临时项目目录随用例清理。"""

    with_storyboard = True
    with_bundle = False

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(prefix='animatic-page-')
        self.addCleanup(self._temp.cleanup)
        import asset_thumbs
        self._asset_thumbs = asset_thumbs
        self._cache_root = asset_thumbs.CACHE_ROOT
        asset_thumbs.reset_worker()
        asset_thumbs.forget()
        asset_thumbs.CACHE_ROOT = Path(self._temp.name) / 'thumbs'
        self.addCleanup(self._restore_thumbs)
        self.project = Path(self._temp.name) / 'project'
        self.project.mkdir()
        if self.with_storyboard:
            self.source = _storyboard(self.project)
        self.win = tk_test_support.make_root()
        self.addCleanup(self.win.destroy)
        self.page = _Page(self.win, self.project)
        if self.with_bundle:
            from stage_execution_service import load_or_sync_animatic_timeline
            self._animatic_bundle = _animatic_bundle(
                self.project, load_or_sync_animatic_timeline(self.project))

    def _restore_thumbs(self):
        self._asset_thumbs.reset_worker()
        self._asset_thumbs.forget()
        self._asset_thumbs.CACHE_ROOT = self._cache_root

    def show(self):
        self.frame = animatic_page.show(self.page)
        return self.frame

    @property
    def state(self):
        return self.frame._animatic_state


class GuidePageTests(_PageCase):
    """REQ-S04-95/99：空项目显示引导，确认锁定条不出现。"""

    with_storyboard = False

    def test_guide_when_no_adopted_storyboard(self):
        frame = self.show()
        self.assertTrue(frame.winfo_exists())
        blocks = [w for w in _walk(self.page.content) if isinstance(w, DescriptionBlock)]
        self.assertTrue(any('请先在初步分镜完成并采用分镜' in str(b.cget('text')) for b in blocks),
                        '缺分镜时应给引导说明')
        buttons = [w for w in _walk(self.page.content) if isinstance(w, PrimaryButton)]
        self.assertEqual(1, len(buttons), '引导页只留一颗跳转主按钮')
        buttons[0].invoke()
        self.assertEqual([PAGE['storyboard']], self.page.went)
        self.assertEqual([], [w for w in _walk(self.page.content) if isinstance(w, ttk.Checkbutton)],
                         '未生成时不得出现确认勾选')


class LayoutTests(_PageCase):
    """REQ-S04-95/96/98：三段布局、发送键与文件面板挂钩、状态栏摘要。"""

    def test_layout_hooks_and_summary(self):
        self.show()
        cells = [text for text in _labels(self.page.content) if text.startswith('SH001')]
        self.assertTrue(cells, '时间线应给 SH001 一格')
        self.assertTrue(callable(self.page.shared_input.stage_action('animatic')),
                        '发送键应登记 animatic 阶段动作')
        self.assertIn(self.page.page_index, self.page.files_panel.select,
                      '文件面板应登记点选回调')
        self.assertIn('animatic', self.page.files_panel.imports,
                      '文件面板应登记导入回调')
        self.assertIn('animatic', self.page.files_panel.menus,
                      '文件面板应登记右键挂钩')
        segment = self.page.segments.get('animatic_note', ('',))[0]
        self.assertIn('分镜 1 镜', segment)
        self.assertIn('未生成', segment)
        buttons = [w for w in _walk(self.page.content)
                   if isinstance(w, (PrimaryButton, SecondaryButton))]
        self.assertLessEqual(len(buttons), 1, '常驻按钮应不超过一颗')
        self.assertEqual([], [w for w in _walk(self.page.content) if isinstance(w, ttk.Checkbutton)],
                         '未生成版本时确认条应隐藏')

    def test_destroy_releases_hooks_and_segment(self):
        frame = self.show()
        shared = self.page.shared_input
        wrapped = shared.on_send
        frame.destroy()
        tk_test_support.pump(self.win, .1)
        self.assertIsNone(shared.stage_action('animatic'), '页面销毁应撤销发送动作')
        self.assertIsNot(shared.on_send, wrapped, '页面销毁应还原 on_send')
        self.assertEqual('', self.page.segments['animatic_note'][0],
                         '页面销毁应清空状态段')


class TimelineInteractionTests(_PageCase):
    """REQ-S04-95/97：时间线格宽随时长、显示缩略图，点击与键盘都能选中镜头。"""

    def test_cells_width_thumbnail_selection_and_keyboard(self):
        self.win.geometry('1080x760')
        self.win.update()
        self.source = _storyboard(self.project, (('SH001', 2), ('SH002', 10)))
        from contract.stage_path_service import write_dir
        folder = write_dir(self.project, 'animatic') / '镜头'
        for sid in ('SH001', 'SH002'):
            (folder / sid).mkdir(parents=True, exist_ok=True)
            (folder / sid / 'v1.png').write_bytes(b'png')
        seen, images = [], []

        def fake_thumbnail(parent, path, size=0):
            image = tk.PhotoImage(width=1, height=1)
            images.append(image)
            seen.append((Path(path), size))
            return image

        with patch.object(animatic_page.asset_thumbs, 'thumbnail', side_effect=fake_thumbnail):
            self.show()
            state = self.state
            first = state['shot_widgets']['SH001']
            second = state['shot_widgets']['SH002']
            self.assertLess(int(first.cget('width')), int(second.cget('width')),
                            '镜头格宽必须随时长比例增加')
            bars = [w for w in _walk(self.page.content) if isinstance(w, ttk.Scrollbar)
                    and str(w.cget('orient')) == 'horizontal']
            self.assertTrue(bars, '长时间线必须有横向滚动条，不能挤压或截断镜头格')
            self.assertTrue(any(path.name == 'v1.png' and path.parent.name == 'SH001'
                                and size == state['layout_metrics']['thumb_size']
                                for path, size in seen),
                            '镜头格应装入当前图版本缩略图')
            first.focus_force()
            self.win.update()
            first.event_generate('<Right>')
            tk_test_support.pump(self.win, .05)
            self.assertEqual('SH002', state['selected_shot'],
                             '时间线右方向键应选中下一镜')
            current = state['shot_widgets']['SH002']
            self.assertIs(self.win.focus_get(), current,
                          '方向键选中下一镜后键盘焦点应跟着走')
            self.assertEqual('SelectedShot.TFrame', str(current.cget('style')),
                             '选中镜头格应有可见焦点边框')
            self.assertTrue(any('SH002 当前镜头草图' in text for text in _labels(self.page.content)),
                            '播放区应跟随当前选中镜头换大图')
            first_current = state['shot_widgets']['SH001']
            first_current.focus_set()
            first_current.event_generate('<Return>')
            tk_test_support.pump(self.win, .05)
            self.assertEqual('SH001', state['selected_shot'],
                             'Enter 应选中获得键盘焦点的镜头格')
            self.assertTrue(any('SH001 当前镜头草图' in text for text in _labels(self.page.content)),
                            '点选/键盘选中第一镜后播放区应同步回第一镜')
            second_current = state['shot_widgets']['SH002']
            second_current.focus_set()
            with patch.object(animatic_page, 'shot_context_menu') as menu_factory:
                second_current.event_generate('<Shift-F10>')
                tk_test_support.pump(self.win, .05)
            menu_factory.assert_called_once()
            menu_factory.return_value.popup_at.assert_called_once()


class ConfirmBarTests(_PageCase):
    """REQ-S04-98：有可播放版本才出现三项确认＋「锁定」。"""

    with_bundle = True

    def test_confirm_bar_shows_after_playable_version(self):
        self.show()
        checks = [w for w in _walk(self.page.content) if isinstance(w, ttk.Checkbutton)]
        self.assertEqual(3, len(checks), '应有节奏／时长／对白同步三项确认')
        locks = [w for w in _walk(self.page.content) if isinstance(w, SecondaryButton)
                 and str(w.cget('text')) == '锁定']
        self.assertEqual(1, len(locks), '应有且只有一颗「锁定」')
        segment = self.page.segments.get('animatic_note', ('',))[0]
        self.assertIn('未确认', segment)

    def test_compact_880x600_keeps_lock_inside_and_restores_regular_sizes(self):
        self.win.geometry('880x600+0+0')
        tk_test_support.pump(self.win, .2)
        self.show()
        tk_test_support.pump(self.win, .2)
        state = self.state
        metrics = state['layout_metrics']
        self.assertTrue(metrics['compact'], '880×600 主窗口应进入紧凑布局')
        self.assertLess(metrics['cell_height'], animatic_page._TIMELINE_CELL_HEIGHT)
        self.assertLess(metrics['thumb_size'], animatic_page._TIMELINE_THUMB_SIZE)
        lock = next(w for w in _walk(self.page.content)
                    if isinstance(w, SecondaryButton) and str(w.cget('text')) == '锁定')
        self.assertTrue(lock.winfo_ismapped())
        self.assertLessEqual(lock.winfo_rootx() + lock.winfo_width(),
                             self.frame.winfo_rootx() + self.frame.winfo_width() + 1,
                             '锁定按钮不得横向越出分镜预演页')
        self.assertLessEqual(lock.winfo_rooty() + lock.winfo_height(),
                             self.frame.winfo_rooty() + self.frame.winfo_height() + 1,
                             '锁定按钮不得纵向越出分镜预演页')
        self.assertIsNone(state.get('video_view'), '默认优先外置播放，不应预先挂载 VideoPreview')
        player_cover = state.get('player_cover')
        self.assertIsNotNone(player_cover, '紧凑布局应保留轻量封面容器')
        self.assertEqual(metrics['player_height'], int(float(player_cover.cget('height'))))
        compact_cell = state['shot_widgets']['SH001']
        self.assertEqual(metrics['cell_height'], int(float(compact_cell.cget('height'))))
        self.win.geometry('1280x900+0+0')
        tk_test_support.pump(self.win, .3)
        self.assertFalse(state['layout_metrics']['compact'], '窗口拉高后应回到常规布局')
        restored = state['shot_widgets']['SH001']
        self.assertEqual(animatic_page._TIMELINE_CELL_HEIGHT,
                         int(float(restored.cget('height'))))

    def test_lock_blocked_until_all_checked(self):
        self.show()
        with patch('stage_execution_service.lock_animatic') as lock:
            lock_button = next(w for w in _walk(self.page.content)
                               if isinstance(w, SecondaryButton) and str(w.cget('text')) == '锁定')
            lock_button.invoke()
        self.assertFalse(lock.called, '三项未勾全不得调后端锁定')
        self.assertTrue(any('勾选' in message for message in self.page.status.messages),
                        '未勾全时状态栏应提示')

    def test_lock_calls_gateway_and_reports(self):
        self.show()
        for widget in _walk(self.page.content):
            if isinstance(widget, ttk.Checkbutton):
                widget.invoke()
        with patch('stage_execution_service.lock_animatic') as lock:
            lock_button = next(w for w in _walk(self.page.content)
                               if isinstance(w, SecondaryButton) and str(w.cget('text')) == '锁定')
            lock_button.invoke()
        lock.assert_called_once_with(self.project, rhythm=True, duration=True, dialogue_sync=True)
        self.assertTrue(any(kind == 'user' and stage == 'animatic' and text == '锁定分镜预演'
                            for kind, stage, text, _kw in self.page.reply_notes),
                        '锁定入口应在回话区保留用户指令')
        self.assertTrue(any(kind == 'progress' and stage == 'animatic' and '回写分镜时长' in text
                            for kind, stage, text, _kw in self.page.reply_notes),
                        '锁定过程应写入回话区')
        self.assertTrue(any(kind == 'reply' and stage == 'animatic' and '已锁定' in text
                            for kind, stage, text, _kw in self.page.reply_notes),
                        '锁定结果应写入回话区')


class SendCommandTests(_PageCase):
    """REQ-S04-96：发送键默认生成；「只重做 SHxxx」单镜重做；斜杠命令放行。"""

    def test_empty_send_generates_timeline(self):
        self.show()
        with patch('stage_execution_service.run_animatic_timeline') as run:
            accepted = self.page.shared_input.stage_action('animatic')()
        self.assertTrue(accepted)
        run.assert_called_once()
        self.assertEqual(self.project, run.call_args[0][0])
        self.assertEqual(self.source, run.call_args.kwargs['source'],
                         '整片合成应带当前分镜源，不能让网关猜最近采用')
        self.assertEqual({}, run.call_args.kwargs['settings'])

    def test_typed_redo_only_regenerates_that_shot(self):
        self.show()
        self.page.shared_input.set_text('只重做 SH001')
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = self.page.shared_input.stage_action('animatic')()
        self.assertTrue(accepted)
        redo.assert_called_once_with(self.project, 'SH001', settings={})

    def test_redo_unknown_shot_stays_local(self):
        self.show()
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = animatic_page.run_command(self.page, self.state, '重做 SH099')
        self.assertFalse(accepted)
        self.assertFalse(redo.called)
        self.assertTrue(any('SH099' in message for message in self.page.status.messages))

    def test_generate_writes_process_and_reply_entries(self):
        """UX-S04-23：真实发送入口把用户指令、进度与产物写进共用过程与回话区。"""
        self.show()
        video = self.project / '版本' / 'animatic_v001.mp4'
        with patch('stage_execution_service.run_animatic_timeline', return_value=video):
            accepted = self.page.shared_input.stage_action('animatic')()
        self.assertTrue(accepted)
        self.assertTrue(any(kind == 'user' and stage == 'animatic' and text == '生成分镜预演'
                            for kind, stage, text, _kw in self.page.reply_notes),
                        '空发送应在回话区保留用户指令')
        self.assertTrue(any(kind == 'progress' and stage == 'animatic'
                            and '正在合成分镜预演' in text and kw.get('expand') is True
                            for kind, stage, text, kw in self.page.reply_notes),
                        '开始生成应写入进度并展开回话区')
        self.assertTrue(any(kind == 'artifact' and stage == 'animatic'
                            and kw.get('path') == str(video)
                            for kind, stage, text, kw in self.page.reply_notes),
                        '生成完成应写入可打开的产物记录')

    def test_unknown_redo_writes_error_to_reply_area(self):
        self.show()
        accepted = animatic_page.run_command(self.page, self.state, '重做 SH099')
        self.assertFalse(accepted)
        self.assertTrue(any(kind == 'error' and stage == 'animatic'
                            and 'SH099' in text and kw.get('expand') is True
                            for kind, stage, text, kw in self.page.reply_notes),
                        '本地拦截错误也应进入回话区，而不是只闪状态栏')

    def test_redo_refreshes_selected_shot_preview_without_video(self):
        """REQ-S04-83/95：单镜重做完，未合成整片时播放区的大图也换成新版本。"""
        self.show()
        updated = dict(self.state['timeline'])
        updated['shots'] = [dict(self.state['timeline']['shots'][0], image_version=2)]
        with patch('stage_execution_service.regenerate_animatic_shot', return_value=updated), \
             patch.object(animatic_page, '_render_player') as render_player:
            accepted = animatic_page.run_command(self.page, self.state, '只重做 SH001')
        self.assertTrue(accepted)
        self.assertTrue(render_player.called,
                        '单镜重做后不能只刷新时间线，播放区当前镜大图也要刷新')

    def test_backend_error_is_written_to_status_and_reply_area(self):
        """UX-S04-23/REQ-S04-99：生成业务异常不冒泡成全局弹窗，写状态栏与回话区。"""
        self.show()
        with patch('stage_execution_service.run_animatic_timeline',
                   side_effect=ValueError('ComfyUI 未就绪')), \
             patch('infra.diagnostic_capture.record_degradation') as degradation:
            accepted = animatic_page.run_command(self.page, self.state, '')
        self.assertTrue(accepted, '后台任务本身已受理；失败应作为业务结果回到本页')
        degradation.assert_called_once()
        self.assertTrue(any('ComfyUI 未就绪' in message for message in self.page.status.messages),
                        '生成失败应写状态栏')
        self.assertTrue(any(kind == 'error' and stage == 'animatic'
                            and 'ComfyUI 未就绪' in text and kw.get('expand') is True
                            for kind, stage, text, kw in self.page.reply_notes),
                        '生成失败应写入过程与回话区并展开')

    def test_on_send_intercepts_free_text_and_delegates_slash(self):
        self.show()
        shared = self.page.shared_input
        previous = lambda value, parsed: 'delegated'
        shared.on_send = previous
        self.show()  # 第二次建页把 on_send 再包一层，前一层是 previous
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = shared.on_send('只重做 SH001', None)
        self.assertTrue(accepted)
        self.assertTrue(redo.called)
        self.assertGreater(shared.ended, 0, '本地命令受理后应释放在途标记')
        self.assertEqual('delegated', shared.on_send('/分镜 x', {'kind': 'any'}),
                         '斜杠命令应交给原发送链')


class ShotMenuTests(_PageCase):
    """REQ-S04-97：镜头格右键菜单六项动作。"""

    def test_menu_items_and_redo(self):
        self.show()
        state = self.state
        row = state['timeline']['shots'][0]
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            menu = animatic_page.shot_context_menu(self.page, state, row)
            self.assertEqual(
                ['重做这一镜', '用导入的图替换', '改时长', '切换图版本',
                 '查看提示词与所用参考图', '写批注', '试听本镜对白'],
                _menu_labels(menu))
            menu.invoke(0)
        redo.assert_called_once_with(self.project, 'SH001', settings={})

    def test_replace_image_uses_gateway(self):
        self.show()
        state = self.state
        self.page.file_dialog.results = [str(self.project / 'new.png')]
        with patch('stage_execution_service.replace_animatic_shot_image') as replace:
            animatic_page.shot_context_menu(self.page, state,
                                            state['timeline']['shots'][0]).invoke(1)
        replace.assert_called_once_with(self.project, 'SH001', self.project / 'new.png')

    def test_edit_seconds_inline(self):
        self.show()
        state = self.state
        animatic_page.shot_context_menu(self.page, state,
                                        state['timeline']['shots'][0]).invoke(2)
        entry = next((w for w in _walk(self.page.content) if isinstance(w, LineInput)), None)
        self.assertIsNotNone(entry, '改时长应展开页内单行输入条')
        entry.delete(0, 'end')
        entry.insert(0, '8')
        with patch('stage_execution_service.update_animatic_shot') as update:
            state['edit_commit']()
        update.assert_called_once_with(self.project, 'SH001', seconds=8)

    def test_switch_version_submenu(self):
        self.show()
        state = self.state
        state['timeline']['shots'][0]['image_version'] = 1
        from contract.stage_path_service import write_dir
        folder = write_dir(self.project, 'animatic') / '镜头' / 'SH001'
        folder.mkdir(parents=True)
        (folder / 'v1.png').write_bytes(b'v1')
        (folder / 'v2.png').write_bytes(b'v2')
        menu = animatic_page.shot_context_menu(self.page, state, state['timeline']['shots'][0])
        submenu = menu.nametowidget(menu.entrycget(3, 'menu'))
        labels = [submenu.entrycget(i, 'label') for i in range(submenu.index('end') + 1)]
        self.assertIn('v1', labels)
        self.assertIn('v2', labels)
        with patch('stage_execution_service.update_animatic_shot') as update:
            submenu.invoke(labels.index('v2'))
        update.assert_called_once_with(self.project, 'SH001', image_version=2)

    def test_note_inline_and_info_strip(self):
        self.show()
        state = self.state
        menu = animatic_page.shot_context_menu(self.page, state, state['timeline']['shots'][0])
        menu.invoke(4)  # 查看提示词与所用参考图
        self.assertIn('提示词SH001', str(state['info_label'].cget('text')))
        menu.invoke(5)  # 写批注
        entry = next(w for w in _walk(self.page.content) if isinstance(w, LineInput))
        entry.insert(0, '注意这镜')
        with patch('stage_execution_service.update_animatic_shot') as update:
            state['edit_commit']()
        update.assert_called_once_with(self.project, 'SH001', note='注意这镜')


class FilesPanelHookTests(_PageCase):
    """DES-S04-25：导入按扩展名自动归位；参考图右键两项。"""

    def test_import_handler_classifies_by_suffix(self):
        """REQ-S04-70/71：文件面板导入按后缀分流——图片进参考库归位、音频进对白/音乐轨。"""
        self.show()
        handler = self.page.files_panel.imports['animatic']
        image = self.project / '林夏.png'
        image.write_bytes(b'png')
        audio = self.project / 'track.wav'
        audio.write_bytes(b'wav')
        clip = self.project / 'other.mp4'
        clip.write_bytes(b'mp4')
        imported_audio = type('Result', (), {'ok': True, 'data': audio})()
        with patch('stage_execution_service.import_animatic_reference_library',
                   return_value=(image,)) as refs, \
             patch('stage_execution_service.import_animatic_audio',
                   return_value=imported_audio) as audio_import, \
             patch('ui.desktop_files_panel_filters.import_into_stage',
                   return_value={'imported': [clip], 'skipped': [], 'rejected': []}) as into:
            result = handler([image, audio, clip])
        refs.assert_called_once()
        self.assertEqual([image], list(refs.call_args[0][1]))
        self.assertEqual({'characters': [], 'locations': ['LOC_01']}, refs.call_args[1],
                         '参考图导入必须带分镜角色/场景名，否则全部误归 风格/')
        audio_import.assert_called_once_with(self.project, audio)
        into.assert_called_once()
        self.assertEqual([clip], list(into.call_args[0][2]))
        self.assertEqual(3, len(result['imported']))
        self.assertTrue(any(kind == 'artifact' and stage == 'animatic'
                            and kw.get('path') == str(image)
                            for kind, stage, text, kw in self.page.reply_notes),
                        '文件面板导入成功也应在回话区留下可打开产物记录')

    def test_select_handler_switches_storyboard_source(self):
        self.show()
        select = self.page.files_panel.select[self.page.page_index][0]
        with patch('stage_execution_service.load_or_sync_animatic_timeline') as load:
            select(self.source)
            select(self.project / 'notes.txt')
        load.assert_called_once_with(self.project, self.source)

    def test_reference_row_menu(self):
        """REQ-S04-73：参考图右键可改分类与对应名，并提供本地生成参考草图入口。"""
        self.show()
        from contract.stage_path_service import shared_reference_dir
        ref = shared_reference_dir(self.project) / '角色' / '林夏.png'
        ref.parent.mkdir(parents=True)
        ref.write_bytes(b'png')
        hook = self.page.files_panel.menus['animatic']
        menu = ContextMenu(self.win)
        with patch('stage_execution_service.reclassify_animatic_reference') as reclassify:
            hook(menu, ref)
            labels = _menu_labels(menu)
            self.assertIn('修改参考图分类', labels)
            self.assertIn('修改参考图对应名', labels)
            self.assertIn('本地生成参考草图', labels)
            submenu = menu.nametowidget(menu.entrycget(labels.index('修改参考图分类'), 'menu'))
            submenu.invoke(0)  # 第一个分类＝角色
        reclassify.assert_called_once_with(self.project, ref, '角色')

    def test_reference_rename_uses_inline_entry_and_keeps_category(self):
        """REQ-S04-73：右键修改对应名，保留原分类并在缺扩展名时补回原扩展名。"""
        self.show()
        from contract.stage_path_service import shared_reference_dir
        ref = shared_reference_dir(self.project) / '角色' / '林夏.png'
        ref.parent.mkdir(parents=True)
        ref.write_bytes(b'png')
        hook = self.page.files_panel.menus['animatic']
        menu = ContextMenu(self.win)
        hook(menu, ref)
        labels = _menu_labels(menu)
        menu.invoke(labels.index('修改参考图对应名'))
        entry = next((w for w in _walk(self.page.content) if isinstance(w, LineInput)), None)
        self.assertIsNotNone(entry, '修改对应名应使用页内输入条，不弹窗')
        entry.delete(0, 'end')
        entry.insert(0, '林夏正面')
        with patch('stage_execution_service.reclassify_animatic_reference') as reclassify:
            self.state['edit_commit']()
        reclassify.assert_called_once_with(self.project, ref, '角色', new_name='林夏正面.png')

    def test_sketch_generate_uses_settings_model(self):
        self.show()
        from contract.stage_path_service import shared_reference_dir
        ref = shared_reference_dir(self.project) / 'x.png'
        ref.parent.mkdir(parents=True)
        ref.write_bytes(b'png')
        self.page.settings['animatic_reference_model'] = 'model.safetensors'
        hook = self.page.files_panel.menus['animatic']
        menu = ContextMenu(self.win)
        hook(menu, ref)
        labels = _menu_labels(menu)
        menu.invoke(labels.index('本地生成参考草图'))
        entry = next((w for w in _walk(self.page.content) if isinstance(w, LineInput)), None)
        self.assertIsNotNone(entry, '生成参考草图应展开页内输入条')
        state = self.state
        entry.insert(0, '一只猫')
        result = type('Result', (), {'ok': True, 'reason': '', 'data': (ref,)})()
        with patch('stage_execution_service.generate_animatic_reference',
                   return_value=result) as generate:
            state['edit_commit']()
        generate.assert_called_once()
        self.assertEqual(('一只猫', 'model.safetensors'), generate.call_args[0][1:3])
        self.assertTrue(any(kind == 'user' and stage == 'animatic' and '一只猫' in text
                            for kind, stage, text, _kw in self.page.reply_notes),
                        '本地生成参考草图应保留用户指令')
        self.assertTrue(any(kind == 'progress' and stage == 'animatic'
                            and '正在生成参考草图' in text and kw.get('expand') is True
                            for kind, stage, text, kw in self.page.reply_notes),
                        '开始生成草图应写入进度并展开回话区')
        self.assertTrue(any(kind == 'artifact' and stage == 'animatic'
                            and kw.get('path') == str(ref)
                            for kind, stage, text, kw in self.page.reply_notes),
                        '草图完成应写入可打开的产物记录')


class RealPanelHookTests(_PageCase):
    """``desktop_files_panel`` 新挂钩：命中登记时委派，未登记行为不变。"""

    def test_import_files_delegates_to_registered_handler(self):
        from ui.desktop_files_panel import FilesPanelImportMixin
        panel = FilesPanelImportMixin()
        panel.page = self.page
        panel.library_view = False
        panel.stage_filter = None
        panel._page_stage = lambda: 'animatic'
        panel.fill_script_list = lambda: None
        self.page.file_dialog.results = [str(self.project / 'a.png')]
        seen = []
        panel.set_import_handler('animatic', lambda paths: seen.extend(paths) or
                                 {'imported': [], 'skipped': [], 'rejected': []})
        with patch('ui.desktop_files_panel.import_into_stage') as fallback:
            panel.import_files()
        self.assertEqual([str(self.project / 'a.png')], seen)
        self.assertFalse(fallback.called, '登记了导入回调不应再走默认导入')

    def test_import_files_keeps_default_without_handler(self):
        from ui.desktop_files_panel import FilesPanelImportMixin
        panel = FilesPanelImportMixin()
        panel.page = self.page
        panel.library_view = False
        panel.stage_filter = None
        panel._page_stage = lambda: 'animatic'
        panel.fill_script_list = lambda: None
        self.page.file_dialog.results = [str(self.project / 'a.png')]
        with patch('ui.desktop_files_panel.import_into_stage',
                   return_value={'imported': [], 'skipped': [], 'rejected': []}) as fallback:
            panel.import_files()
        self.assertTrue(fallback.called, '未登记时应维持原 import_into_stage 路径')

    def test_import_handler_inert_off_page(self):
        """切到别的页后 animatic 导入回调不生效（登记随页码失效）。"""
        from ui.desktop_files_panel import FilesPanelImportMixin
        panel = FilesPanelImportMixin()
        panel.page = self.page
        panel.library_view = False
        panel.stage_filter = 'animatic'
        panel._page_stage = lambda: 'animatic'
        panel.fill_script_list = lambda: None
        self.page.file_dialog.results = [str(self.project / 'a.png')]
        seen = []
        panel.set_import_handler('animatic', lambda paths: seen.extend(paths) or {})
        self.page.page_index = 4   # 切走
        with patch('ui.desktop_files_panel.import_into_stage',
                   return_value={'imported': [], 'skipped': [], 'rejected': []}) as fallback:
            panel.import_files()
        self.assertEqual([], seen)
        self.assertTrue(fallback.called)


class PlayAreaTests(_PageCase):
    """REQ-S04-96：播放区点击播放＋右键「用外部播放器打开」。"""

    with_bundle = True

    def test_video_cover_opens_external_player(self):
        self.show()
        state = self.state
        state['open_video']()
        expected = str(self._animatic_bundle / '版本' / 'animatic_v001.mp4')
        self.assertEqual([expected], self.page.media_page_services.opened)

    def test_cover_plays_and_pauses_in_page_and_releases_on_destroy(self):
        from ui.animatic_player import VideoPreview
        self.show()
        menu = animatic_page.video_context_menu(self.page, self.state)
        labels = _menu_labels(menu)
        with patch('ui.animatic_player.EmbeddedVideo') as factory:
            menu.invoke(labels.index('页内试播'))
            view = self.state['video_view']
            self.assertIsInstance(view, VideoPreview)
            view.toggle()
            factory.assert_called_once_with(view.path, view.winfo_id())
            self.assertEqual(factory.return_value.toggle.call_count, 2)
            self.assertEqual(self.page.media_page_services.opened, [])
            view.destroy()
            factory.return_value.close.assert_called_once()

    def test_inline_play_failure_keeps_cover_and_reports_external_option(self):
        self.show()
        menu = animatic_page.video_context_menu(self.page, self.state)
        labels = _menu_labels(menu)
        with patch('ui.animatic_player.EmbeddedVideo', side_effect=OSError('codec')):
            menu.invoke(labels.index('页内试播'))
        view = self.state['video_view']
        self.assertEqual(view.cover.winfo_manager(), 'pack')
        self.assertIn('外部播放器', self.page.status.get())

    def test_video_menu_has_external_open(self):
        self.show()
        state = self.state
        labels = _menu_labels(animatic_page.video_context_menu(self.page, state))
        self.assertIn('用本地播放器打开', labels)
        self.assertIn('在剪映中打开', labels)
        self.assertIn('页内试播', labels)
        self.assertIn('重新合成新版本', labels)
        self.assertIn('本地生成参考草图', labels, '播放区右键应常驻草图入口')
        self.assertIn('预演设置…', labels)


class TimelineTrackTests(_PageCase):
    """REQ-S04-95/75：对白轨标「对白超长」；音乐轨随有无音乐切换文案。"""

    def test_overlong_dialogue_marked(self):
        self.show()
        state = self.state
        state['timeline']['shots'][0]['dialogue_audio'] = '声音/对白/SH001.mp3'
        with patch('ui.animatic_page.asset_thumbs.media_info',
                   return_value={'duration': 9.5}):
            animatic_page._render_timeline(self.page, state)
        self.assertIn('对白超长', _labels(state['timeline_box']))

    def test_normal_dialogue_not_marked(self):
        self.show()
        state = self.state
        state['timeline']['shots'][0]['dialogue_audio'] = '声音/对白/SH001.mp3'
        with patch('ui.animatic_page.asset_thumbs.media_info',
                   return_value={'duration': 3.0}):
            animatic_page._render_timeline(self.page, state)
        self.assertNotIn('对白超长', _labels(state['timeline_box']))

    def test_dialogue_within_tolerance_not_marked(self):
        """REQ-S04-75：超出镜头时长不足容差不算超长。"""
        self.show()
        state = self.state
        state['timeline']['shots'][0]['dialogue_audio'] = '声音/对白/SH001.mp3'
        with patch('ui.animatic_page.asset_thumbs.media_info',
                   return_value={'duration': 5.05}):
            animatic_page._render_timeline(self.page, state)
        self.assertNotIn('对白超长', _labels(state['timeline_box']))


def _shot_row(sid, seconds, **fields):
    row = {'id': sid, 'title': '镜', 'duration': seconds, 'characters': [],
           'location': 'LOC_01', 'frame': 'frames/%s.png' % sid,
           'video_prompt': '提示词' + sid, 'dialogue': []}
    row.update(fields)
    return row


def _storyboard_named(root, name, shots):
    """再写一份已采用分镜（文件名与镜头字段可定制），追加进采用清单。"""
    board = {'episode_id': 'EP001', 'title': '集', 'shots': shots}
    source = root / '03初步分镜' / '分镜拆分' / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(board, ensure_ascii=False), encoding='utf-8')
    settings_path = root / 'ui_settings.json'
    try:
        prefs = json.loads(settings_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        prefs = {}
    adopted = list(prefs.get('adopted_storyboards') or [])
    adopted.append(source.relative_to(root).as_posix())
    prefs['adopted_storyboards'] = adopted
    settings_path.write_text(json.dumps(prefs, ensure_ascii=False), encoding='utf-8')
    return source


def _wav(path):
    """最小合法 WAV：1 秒 8 kHz 单声道静音。"""
    import struct
    pcm = b'\0\0' * 8000
    path.write_bytes(b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt '
                    + struct.pack('<IHHIIHH', 16, 1, 1, 8000, 16000, 2, 16)
                    + b'data' + struct.pack('<I', len(pcm)) + pcm)
    return path


def _copy_publish(target, source):
    """不依赖 FFmpeg 的导入发布替身；本组只验证路由与归类，校验链另有专项。"""
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_bytes(Path(source).read_bytes())


class ReferenceImportRoutingTests(_PageCase):
    """P1-1（REQ-S04-71/96）：参考图导入必须带分镜角色/场景名，不能全误归 风格/。"""

    def test_import_lands_character_location_and_style_dirs(self):
        _storyboard_named(self.project, 'ep_cast.json', [
            _shot_row('SH007', 6, characters=['林夏'], location='客厅')])
        self.show()
        state = self.state
        for name in ('林夏.png', '客厅.png', '风格.png'):
            (self.project / name).write_bytes(b'png-' + name.encode('utf-8'))
        state['import_fn']([self.project / '林夏.png',
                            self.project / '客厅.png',
                            self.project / '风格.png'])
        from contract.stage_path_service import shared_reference_dir
        folder = shared_reference_dir(self.project)
        self.assertTrue((folder / '角色' / '林夏.png').is_file(),
                        '角色名图应进 角色/，导入必须带分镜 characters')
        self.assertTrue((folder / '场景' / '客厅.png').is_file(),
                        '场景名图应进 场景/，导入必须带分镜 location')
        self.assertTrue((folder / '风格' / '风格.png').is_file())


class SketchEntryTests(_PageCase):
    """P1-2（REQ-S04-99/96）：空参考图、无视频时「本地生成参考草图」依然可触达。"""

    def test_video_menu_without_video_offers_sketch_and_generate(self):
        self.show()
        labels = _menu_labels(animatic_page.video_context_menu(self.page, self.state))
        self.assertIn('本地生成参考草图', labels)
        self.assertIn('生成分镜预演', labels)
        self.assertIn('预演设置…', labels)
        self.assertNotIn('用本地播放器打开', labels)

    def test_empty_player_binds_context_menu(self):
        self.show()
        box = self.state['player_box']
        self.assertTrue(box.bind('<Button-3>'), '无视频态播放容器应绑右键菜单')
        self.assertTrue(any(child.bind('<Button-3>') for child in box.winfo_children()),
                        '无视频态占位控件应绑右键菜单')

    def test_panel_hook_offers_sketch_for_non_reference_file(self):
        self.show()
        self.page.settings['animatic_reference_model'] = 'model.safetensors'
        hook = self.page.files_panel.menus['animatic']
        menu = ContextMenu(self.win)
        hook(menu, self.project / 'ui_settings.json')
        labels = _menu_labels(menu)
        self.assertIn('本地生成参考草图', labels)
        self.assertNotIn('修改参考图分类', labels,
                         '非共享参考图目录内文件不得出现改分类')
        menu.invoke(labels.index('本地生成参考草图'))
        entry = next((w for w in _walk(self.page.content) if isinstance(w, LineInput)), None)
        self.assertIsNotNone(entry, '草图菜单项应展开页内输入条')


class RefreshLifecycleTests(_PageCase):
    """P1-3（REQ-S04-84/98）：重合成后状态不陈旧；切页后迟到回调静默。"""

    with_bundle = True

    def _recompose_v2(self, confirmed=False):
        """把清单改写成 v002 口径（真实 manifest 形态）。"""
        from domain.animatic_service import CONFIRMATIONS, MANIFEST, digest
        folder = self._animatic_bundle
        manifest = json.loads((folder / MANIFEST).read_text(encoding='utf-8'))
        (folder / '版本' / 'animatic_v002.mp4').write_bytes(b'video-v2')
        manifest['video'] = '版本/animatic_v002.mp4'
        manifest['files'].pop('版本/animatic_v001.mp4', None)
        manifest['files']['版本/animatic_v002.mp4'] = digest(b'video-v2')
        manifest['confirmed'] = dict.fromkeys(CONFIRMATIONS, confirmed)
        (folder / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False),
                                      encoding='utf-8')

    def test_refresh_after_recompose_resets_version_and_checks(self):
        self.show()
        state = self.state
        for var in state['checks'].values():
            var.set(True)
        state['confirmed'] = True  # 模拟 v001 已锁定的旧态
        self._recompose_v2()
        animatic_page._refresh(self.page, state)
        self.assertEqual('animatic_v002', state['version_tag'])
        self.assertEqual('animatic_v002.mp4', Path(state['video']).name)
        self.assertFalse(state['confirmed'])
        self.assertTrue(all(not var.get() for var in state['checks'].values()),
                        '新版本落地应复位三项确认勾选')
        segment = self.page.segments['animatic_note'][0]
        self.assertIn('animatic_v002', segment)
        self.assertIn('未确认', segment)

    def test_stale_page_refresh_stays_quiet(self):
        self.show()
        state = self.state
        self.page.page_index = 5  # 用户已切到别的页
        self._recompose_v2()
        self.page.segments.clear()
        animatic_page._refresh(self.page, state)
        self.assertNotIn('animatic_note', self.page.segments,
                         '切页后迟到回调不得再写状态段')
        self.assertEqual('animatic_v001', state['version_tag'],
                         '切页后的回调不得改写本页状态')


class StaleCallbackTests(_PageCase):
    """P1-3：页面失效后异步回调不得再操作界面、写状态段或误建别的页。"""

    def test_dead_frame_callbacks_do_not_raise_or_write(self):
        frame = self.show()
        state = self.state
        frame.destroy()
        tk_test_support.pump(self.win, .1)
        self.page.segments.clear()
        animatic_page._refresh(self.page, state)
        animatic_page._after_sketch(self.page, state, None)
        animatic_page._locked(self.page, state)
        self.assertNotIn('animatic_note', self.page.segments)
        self.assertEqual([], self.page.reported, '页面已销毁不得上报 pet_report')

    def test_stale_page_never_rebuilds_other_index(self):
        self.show()
        state = self.state
        calls = []
        self.page.show = lambda index=None: calls.append(index)
        self.page.page_index = 5  # 页码已切走
        _animatic_bundle(self.project, state['timeline'])
        animatic_page._refresh(self.page, state)
        self.assertEqual([], calls, '页码不匹配不得按旧回调重建任何页')

    def test_live_page_first_version_rebuilds_self(self):
        self.show()
        state = self.state
        calls = []
        self.page.show = lambda index=None: calls.append(index)
        _animatic_bundle(self.project, state['timeline'])
        animatic_page._refresh(self.page, state)
        self.assertEqual([3], calls, '首个版本落地应重建本页补确认条')

    def test_locked_reports_only_when_project_matches(self):
        self.show()
        state = self.state
        self.page.root = Path(self._temp.name) / 'other'
        animatic_page._locked(self.page, state)
        self.assertEqual([], self.page.reported,
                         '项目已切换不得把别项目页面上报到 pet_report')
        self.assertTrue(state['confirmed'])

    def test_destroy_releases_without_shared_input(self):
        self.page.shared_input = None
        frame = self.show()
        frame.destroy()
        tk_test_support.pump(self.win, .1)
        self.assertEqual('', self.page.segments['animatic_note'][0],
                         '无共享输入框时销毁也要清状态段')
        self.assertNotIn('animatic', self.page.files_panel.imports)
        self.assertNotIn(self.page.page_index, self.page.files_panel.select)

    def test_destroy_after_page_switch_releases_own_handlers(self):
        frame = self.show()
        self.page.page_index = 5  # 先切页再销毁：释放仍按建页登记的页码
        frame.destroy()
        tk_test_support.pump(self.win, .1)
        self.assertNotIn(3, self.page.files_panel.select,
                         '切页后销毁应释放建页时登记的页码，不是按新页码')
        self.assertNotIn('animatic', self.page.files_panel.imports)

    def test_on_send_delegates_after_stage_switch(self):
        self.show()
        shared = self.page.shared_input
        shared.stage = 'video'  # 共享框已被别的阶段接管
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = shared.on_send('只重做 SH001', None)
        self.assertTrue(accepted)
        self.assertFalse(redo.called,
                         '共享框已切到别阶段时，本页 wrapped 应放行给原发送链')


class SettingsPassthroughTests(_PageCase):
    """P1-4（REQ-S04-78）：合成与单镜重做必须透传设置与当前分镜源；worker 忙拒重入。"""

    def test_generate_passes_settings_and_current_source(self):
        self.show()
        self.page.settings.update({'animatic_sketch_backend': 'backend_x',
                                   'animatic_allow_paid_sketch': True,
                                   'comfy_url': 'http://127.0.0.1:9',
                                   'ffmpeg': 'f', 'ffprobe': 'p'})
        with patch('stage_execution_service.run_animatic_timeline') as run:
            accepted = animatic_page.run_command(self.page, self.state, '')
        self.assertTrue(accepted)
        run.assert_called_once()
        kwargs = run.call_args.kwargs
        self.assertEqual(self.source, kwargs['source'])
        settings = kwargs['settings']
        self.assertEqual('backend_x', settings['animatic_sketch_backend'])
        self.assertTrue(settings['animatic_allow_paid_sketch'])
        self.assertEqual('f', settings['ffmpeg'])
        self.assertEqual('p', settings['ffprobe'])
        self.assertEqual('http://127.0.0.1:9', settings['url'],
                         'comfy_url 应映射为网关约定的 url 键')

    def test_redo_passes_settings(self):
        self.show()
        self.page.settings.update({'animatic_sketch_backend': 'backend_x',
                                   'comfy_url': 'http://c:1'})
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = animatic_page.run_command(self.page, self.state, '只重做 SH001')
        self.assertTrue(accepted)
        kwargs = redo.call_args.kwargs
        self.assertEqual('backend_x', kwargs['settings']['animatic_sketch_backend'])
        self.assertEqual('http://c:1', kwargs['settings']['url'])

    def test_worker_busy_rejects_run(self):
        self.show()
        self.page.worker = True
        with patch('stage_execution_service.run_animatic_timeline') as run:
            accepted = animatic_page.run_command(self.page, self.state, '')
        self.assertFalse(accepted)
        self.assertFalse(run.called)
        self.assertTrue(any('等待' in message for message in self.page.status.messages),
                        'worker 占用时应提示等待而不是再派一单')

    def test_worker_busy_rejects_redo(self):
        self.show()
        self.page.worker = True
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = animatic_page.run_command(self.page, self.state, '只重做 SH001')
        self.assertFalse(accepted)
        self.assertFalse(redo.called)


class BoardSwitchTests(_PageCase):
    """P1-5：切换已采用分镜后 source/board/版本事实全部同步到新分镜。"""

    def test_select_board_swaps_source_board_and_import_routing(self):
        self.show()
        state = self.state
        source_b = _storyboard_named(self.project, 'ep_b.json', [
            _shot_row('SH009', 4, characters=['丙丁'], location='书房',
                      video_prompt='分镜B提示词')])
        state['select_fn'](source_b)
        self.assertEqual('03初步分镜/分镜拆分/ep_b.json', state['source'],
                         '切分镜后 source 必须跟着换，否则合成与导入还用旧板')
        animatic_page._show_shot_info(self.page, state, state['timeline']['shots'][0])
        self.assertIn('分镜B提示词', str(state['info_label'].cget('text')))
        (self.project / '丙丁.png').write_bytes(b'png-b')
        state['import_fn']([self.project / '丙丁.png'])
        from contract.stage_path_service import shared_reference_dir
        self.assertTrue((shared_reference_dir(self.project) / '角色' / '丙丁.png').is_file(),
                        '切分镜后导入应按新分镜角色归位')


class AudioImportRouteTests(_PageCase):
    """P1-6（REQ-S04-74/76/96）：整轨优先；面板音频落在合成实际读取的子目录。"""

    def test_track_audio_lands_in_track_dir_and_sets_mode(self):
        self.show()
        state = self.state
        with patch('orchestrator.stage_animatic_gateways.media_import_publisher',
                   return_value=_copy_publish):
            state['import_fn']([_wav(self.project / 'voice.wav')])
        from contract.stage_path_service import write_dir
        folder = write_dir(self.project, 'animatic')
        self.assertEqual(1, len(list((folder / '声音' / '整轨').glob('*.wav'))),
                         '面板导入整轨音频必须落 声音/整轨/ 才会被合成读取')
        self.assertEqual('整轨', animatic_page._audio_mode(state))

    def test_music_audio_lands_in_music_dir(self):
        self.show()
        state = self.state
        with patch('orchestrator.stage_animatic_gateways.media_import_publisher',
                   return_value=_copy_publish):
            state['import_fn']([_wav(self.project / 'bgm.wav')])
        from contract.stage_path_service import write_dir
        folder = write_dir(self.project, 'animatic')
        self.assertEqual(1, len(list((folder / '声音' / '音乐').glob('*.wav'))),
                         'bgm/音乐 文件名应落 声音/音乐/')
        self.assertEqual('已导入', animatic_page._music_text(state))
        self.assertEqual('静音', animatic_page._audio_mode(state),
                         '只有音乐不该误报为整轨')

    def test_explicit_track_param_routes(self):
        import stage_execution_service
        with patch('orchestrator.stage_animatic_gateways.media_import_publisher',
                   return_value=_copy_publish):
            result = stage_execution_service.import_animatic_audio(
                self.project, _wav(self.project / 'voice.wav'), track='music')
        from contract.stage_path_service import write_dir
        self.assertTrue(result.ok)
        self.assertTrue(Path(result.data).is_relative_to(
            write_dir(self.project, 'animatic') / '声音' / '音乐'),
            'track= music 必须落 声音/音乐/')

    def test_track_dir_beats_dialogue_audio(self):
        self.show()
        state = self.state
        from contract.stage_path_service import write_dir
        folder = write_dir(self.project, 'animatic') / '声音' / '整轨'
        folder.mkdir(parents=True)
        (folder / 'v.wav').write_bytes(b'x')
        state['timeline']['shots'][0]['dialogue_audio'] = '声音/对白/a.mp3'
        self.assertEqual('整轨', animatic_page._audio_mode(state),
                         '整轨目录有文件时必须优先于逐镜 TTS')

    def test_music_dir_is_not_reported_as_track(self):
        self.show()
        state = self.state
        from contract.stage_path_service import write_dir
        folder = write_dir(self.project, 'animatic') / '声音' / '音乐'
        folder.mkdir(parents=True)
        (folder / 'b.wav').write_bytes(b'x')
        self.assertEqual('静音', animatic_page._audio_mode(state))


class MediaDbViewBoundaryTests(_PageCase):
    """FIX-S04-MEDIA-DB-VIEW：提示词字段兼容与损坏分镜错误提示。"""

    def test_show_shot_info_reads_image_prompt_and_fallbacks(self):
        """仅填 image_prompt（无 video_prompt）时正确展示提示词，并兼容 prompt/description。"""
        _storyboard_named(self.project, 'ep_prompt.json', [
            {'id': 'SH001', 'title': '镜1', 'duration': 4, 'characters': [],
             'location': 'LOC_01', 'frame': 'frames/SH001.png',
             'image_prompt': '雨夜红伞特写', 'dialogue': []},
            {'id': 'SH002', 'title': '镜2', 'duration': 4, 'characters': [],
             'location': 'LOC_01', 'frame': 'frames/SH002.png',
             'prompt': '街道远景', 'dialogue': []},
            {'id': 'SH003', 'title': '镜3', 'duration': 4, 'characters': [],
             'location': 'LOC_01', 'frame': 'frames/SH003.png',
             'description': '角色转身', 'dialogue': []},
        ])
        self.show()
        state = self.state
        shots = state['timeline']['shots']
        menu = animatic_page.shot_context_menu(self.page, state, shots[0])
        menu.invoke(4)  # 查看提示词与所用参考图
        self.assertIn('雨夜红伞特写', str(state['info_label'].cget('text')))
        animatic_page._show_shot_info(self.page, state, shots[1])
        self.assertIn('街道远景', str(state['info_label'].cget('text')))
        animatic_page._show_shot_info(self.page, state, shots[2])
        self.assertIn('角色转身', str(state['info_label'].cget('text')))

    def test_corrupt_adopted_storyboard_sets_status_and_shows_guide(self):
        """已采用分镜 JSON 损坏时打开 S04 不崩溃，status 写入 <=45 字中文报错并展示引导页。"""
        self.source.write_text('{corrupt-json', encoding='utf-8')
        frame = self.show()
        self.assertTrue(frame.winfo_exists())
        self.assertIsNone(self.state['timeline'])
        self.assertTrue(self.page.status.messages, '损坏分镜不得静默吞错，应写入状态栏')
        message = self.page.status.messages[-1]
        self.assertLessEqual(len(message), 45, f'报错文案超出 45 字: {message}')
        self.assertTrue(any('\u4e00' <= ch <= '\u9fff' for ch in message),
                        f'报错文案应为中文: {message}')


class PaginationAndDialoguePerfTests(_PageCase):
    """REQ-S04-105/108/112：时间线 20 镜分页、3000 镜有界控件与优先读 dialogue_seconds。"""

    def test_timeline_page_slice_clamps_and_slices(self):
        from ui.animatic_view_state import TIMELINE_PAGE_SIZE, timeline_page_slice
        self.assertEqual(20, TIMELINE_PAGE_SIZE)
        shots = [{'id': 'SH%03d' % i, 'seconds': 4} for i in range(1, 66)]
        page1, current1, total1 = timeline_page_slice(shots, 1)
        self.assertEqual((20, 1, 4), (len(page1), current1, total1))
        self.assertEqual('SH001', page1[0]['id'])
        self.assertEqual('SH020', page1[-1]['id'])
        page4, current4, total4 = timeline_page_slice(shots, 4)
        self.assertEqual((5, 4, 4), (len(page4), current4, total4))
        self.assertEqual('SH061', page4[0]['id'])
        self.assertEqual('SH065', page4[-1]['id'])
        self.assertEqual((1, 4), timeline_page_slice(shots, 0)[1:])
        self.assertEqual((4, 4), timeline_page_slice(shots, 99)[1:])

    def test_65_shots_paginates_20_then_5_and_hides_pager_at_20(self):
        self.source = _storyboard(
            self.project, [('SH%03d' % i, 4) for i in range(1, 66)])
        self.show()
        state = self.state
        self.assertEqual(20, len(state['shot_widgets']),
                         '65 镜首次渲染只应创建第 1 页的 20 个镜头格')
        self.assertIsNotNone(state.get('pager_bar'), '超过 20 镜应展示翻页条')
        self.assertTrue(any('第 1/4 页（共 65 镜）' in text
                            for text in _labels(state['timeline_box'])))
        animatic_page.set_timeline_page(self.page, state, 4)
        self.assertEqual(5, len(state['shot_widgets']),
                         '切到第 4 页只应创建剩余 5 个镜头格')
        self.assertEqual(['SH061', 'SH062', 'SH063', 'SH064', 'SH065'],
                         list(state['shot_widgets'].keys()))
        self.assertTrue(any('第 4/4 页（共 65 镜）' in text
                            for text in _labels(state['timeline_box'])))

    def test_20_or_fewer_shots_hides_pager_bar(self):
        self.source = _storyboard(
            self.project, [('SH%03d' % i, 4) for i in range(1, 21)])
        self.show()
        state = self.state
        self.assertEqual(20, len(state['shot_widgets']))
        self.assertIsNone(state.get('pager_bar'), '≤20 镜必须隐藏翻页条')
        pager_buttons = [w for w in _walk(state['timeline_box'])
                         if isinstance(w, (PrimaryButton, SecondaryButton))]
        self.assertEqual([], pager_buttons)

    def test_3000_shots_keeps_widget_count_bounded(self):
        self.show()
        state = self.state
        state['timeline'] = {
            'source': state['source'],
            'shots': [{'id': 'SH%04d' % i, 'seconds': 3, 'image_version': 0}
                      for i in range(1, 3001)],
        }
        animatic_page._render_timeline(self.page, state)
        self.assertEqual(20, len(state['shot_widgets']))
        total_widgets = len(list(_walk(self.frame)))
        self.assertLessEqual(total_widgets, 140,
                             f'3000 镜常驻控件应恒定 ≤140，实际 {total_widgets}')

    def test_shot_dialogue_seconds_prefers_recorded_and_falls_back(self):
        from ui.animatic_view_state import shot_dialogue_seconds
        calls = []

        def fake_probe(path):
            calls.append(path)
            return {'duration': 7.5}

        recorded = {'id': 'SH001', 'seconds': 5,
                    'dialogue_audio': '声音/对白/SH001.mp3', 'dialogue_seconds': 8.2}
        self.assertEqual(8.2, shot_dialogue_seconds(self.project, recorded, probe=fake_probe))
        self.assertEqual([], calls, '时间线已有 dialogue_seconds 时不得再扫盘探测')

        legacy = {'id': 'SH001', 'seconds': 5, 'dialogue_audio': '声音/对白/SH001.mp3'}
        self.assertEqual(7.5, shot_dialogue_seconds(self.project, legacy, probe=fake_probe))
        self.assertEqual(1, len(calls), '旧时间线缺 dialogue_seconds 时应兼容兜底探测')

        self.show()
        state = self.state
        state['timeline']['shots'][0].update(recorded)
        with patch('ui.animatic_page.asset_thumbs.media_info') as probe_mock:
            animatic_page._render_timeline(self.page, state)
        self.assertFalse(probe_mock.called, '渲染对白轨有 dialogue_seconds 时不应调 media_info')
        self.assertIn('对白超长', _labels(state['timeline_box']))


class ExternalFirstPlaybackTests(_PageCase):
    """REQ-S04-106：默认外置播放零内嵌解码器、剪映联动与按需页内试播。"""

    with_bundle = True

    def test_default_render_and_click_never_constructs_video_preview(self):
        with patch('ui.animatic_player.VideoPreview') as preview_cls:
            self.show()
            state = self.state
            self.assertIsNone(state.get('video_view'), '默认不应构造 VideoPreview')
            self.assertIsNotNone(state.get('player_cover'), '默认应渲染轻量封面')
            state['activate_player']()
        preview_cls.assert_not_called()
        expected = str(self._animatic_bundle / '版本' / 'animatic_v001.mp4')
        self.assertEqual([expected], self.page.media_page_services.opened)

    def test_jianying_menu_calls_launch_editor_and_opens_video_dir(self):
        self.show()
        state = self.state
        launched = []
        self.page.launch_editor = lambda: launched.append('jianying')
        menu = animatic_page.video_context_menu(self.page, state)
        labels = _menu_labels(menu)
        self.assertIn('用本地播放器打开', labels)
        self.assertIn('在剪映中打开', labels)
        self.assertIn('页内试播', labels)
        self.assertIn('预演设置…', labels)
        menu.invoke(labels.index('在剪映中打开'))
        self.assertEqual(['jianying'], launched)
        self.assertIn(str(self._animatic_bundle / '版本'),
                      self.page.media_page_services.opened)

    def test_jianying_missing_falls_back_to_video_dir_and_status(self):
        self.show()
        state = self.state
        menu = animatic_page.video_context_menu(self.page, state)
        labels = _menu_labels(menu)
        menu.invoke(labels.index('在剪映中打开'))
        self.assertIn(str(self._animatic_bundle / '版本'),
                      self.page.media_page_services.opened)
        self.assertIn('剪映', self.page.status.get())

    def test_inline_preview_menu_mounts_video_preview_on_demand(self):
        from ui.animatic_player import VideoPreview
        self.show()
        state = self.state
        self.assertIsNone(state.get('video_view'))
        menu = animatic_page.video_context_menu(self.page, state)
        labels = _menu_labels(menu)
        with patch('ui.animatic_player.EmbeddedVideo') as factory:
            menu.invoke(labels.index('页内试播'))
            view = state.get('video_view')
            self.assertIsInstance(view, VideoPreview)
            factory.assert_called_once()
            view.destroy()
            factory.return_value.close.assert_called_once()


class DialogueAuditionTests(_PageCase):
    """REQ-S04-107：镜头格右键「试听本镜对白」非阻塞打开或友好提示。"""

    def test_audition_with_audio_opens_path(self):
        self.show()
        state = self.state
        row = state['timeline']['shots'][0]
        row['dialogue_audio'] = '04分镜预演/声音/对白/SH001.mp3'
        menu = animatic_page.shot_context_menu(self.page, state, row)
        labels = _menu_labels(menu)
        self.assertIn('试听本镜对白', labels)
        menu.invoke(labels.index('试听本镜对白'))
        expected = str(self.project / '04分镜预演/声音/对白/SH001.mp3')
        self.assertEqual([expected], self.page.media_page_services.opened)

    def test_audition_without_audio_sets_status_without_error(self):
        self.show()
        state = self.state
        row = state['timeline']['shots'][0]
        row['dialogue_audio'] = None
        menu = animatic_page.shot_context_menu(self.page, state, row)
        labels = _menu_labels(menu)
        menu.invoke(labels.index('试听本镜对白'))
        self.assertEqual([], self.page.media_page_services.opened)
        self.assertEqual('该镜头暂无对白音频', self.page.status.get())


class PrefsBarTests(_PageCase):
    """REQ-S04-110：页内「预演设置…」条读写模型池 gflow-* 与桌面偏好，零弹窗。"""

    def test_gflow_model_ids_filters_image_gflow_entries(self):
        from ui.animatic_prefs_bar import gflow_model_ids
        records = {
            'gflow-zeta': {'modality': 'image'},
            'gflow-nano2': {'modality': 'image'},
            'gflow-veo': {'modality': 'video'},
            'openai-img': {'modality': 'image'},
        }
        self.assertEqual(['gflow-nano2', 'gflow-zeta'], gflow_model_ids(records))
        self.assertEqual([], gflow_model_ids({}))

    def test_prefs_bar_lists_gflow_saves_settings_and_collapses(self):
        from ui_widgets import SelectBox
        self.show()
        state = self.state
        self.page.settings_file = Path(self._temp.name) / 'desktop_settings.json'
        pool_data = {'gflow-nano2': {'modality': 'image', 'model': 'nano2'}}
        with patch('infra.model_pool.pool', return_value=pool_data):
            menu = animatic_page.video_context_menu(self.page, state)
            labels = _menu_labels(menu)
            menu.invoke(labels.index('预演设置…'))
            combos = [w for w in _walk(state['edit_box']) if isinstance(w, SelectBox)]
            all_values = [val for combo in combos for val in combo.cget('values')]
            self.assertIn('gflow-nano2', all_values, '模型池存在 gflow-nano2 时下拉应可见')
            entries = [w for w in _walk(state['edit_box']) if isinstance(w, LineInput)]
            self.assertTrue(entries, '应包含本地参考图模型名输入框')
            entries[0].delete(0, 'end')
            entries[0].insert(0, 'sdxl_base.safetensors')
            self.assertEqual([], [w for w in self.win.winfo_children()
                                  if isinstance(w, tk.Toplevel)], '偏好条不得弹出新窗口')
            state['edit_commit']()
        self.assertEqual([], state['edit_box'].winfo_children(), '保存后偏好条应自动收起')
        self.assertEqual('gflow-nano2', self.page.settings.get('animatic_gflow_model'))
        self.assertEqual('sdxl_base.safetensors',
                         self.page.settings.get('animatic_reference_model'))
        saved = json.loads(self.page.settings_file.read_text(encoding='utf-8'))
        self.assertEqual('gflow-nano2', saved.get('animatic_gflow_model'))
        self.assertEqual('external', saved.get('animatic_player_mode'))

    def test_prefs_bar_handles_empty_gflow_pool_without_crashing(self):
        from ui.animatic_prefs_bar import GFLOW_EMPTY_OPTION
        from ui_widgets import SelectBox
        self.show()
        state = self.state
        with patch('infra.model_pool.pool', return_value={}):
            menu = animatic_page.video_context_menu(self.page, state)
            labels = _menu_labels(menu)
            menu.invoke(labels.index('预演设置…'))
            combos = [w for w in _walk(state['edit_box']) if isinstance(w, SelectBox)]
            all_values = [val for combo in combos for val in combo.cget('values')]
            self.assertIn(GFLOW_EMPTY_OPTION, all_values)
            state['edit_commit']()
        self.assertEqual('', self.page.settings.get('animatic_gflow_model'),
                         '未配置 gflow-* 时保存不得写入占位提示文本')
        self.assertEqual([], state['edit_box'].winfo_children())


class DebounceAndPanelPerfTests(_PageCase):
    """REQ-S04-108/109/111：<Configure> 150ms 防抖、销毁不迟到重绘与四分组折叠边界。"""

    def test_five_configure_events_coalesce_to_one_sync(self):
        frame = self.show()
        with patch.object(animatic_page, '_sync_layout_metrics') as sync:
            for _ in range(5):
                frame.event_generate('<Configure>')
            self.win.update()
            self.assertEqual(0, sync.call_count, '150ms 防抖期内不应立即重绘')
            tk_test_support.pump(self.win, .25)
        self.assertEqual(1, sync.call_count, '连续 5 次 <Configure> 应合并为 1 次防抖重绘')

    def test_destroy_cancels_pending_debounced_configure(self):
        frame = self.show()
        with patch.object(animatic_page, '_sync_layout_metrics') as sync:
            frame.event_generate('<Configure>')
            self.win.update()
            frame.destroy()
            tk_test_support.pump(self.win, .25)
        self.assertEqual(0, sync.call_count, '页面销毁后不得再触发迟到防抖重绘')

    def test_async_dispatch_and_s04_panel_four_groups_contract(self):
        """REQ-S04-109/111：后台任务走宿主 async_ 且 S04 面板四分组折叠与预取上限生效。"""
        from contract.file_index_contract import FileRow
        from ui import desktop_files_panel_index as panel_index
        rows = [
            FileRow(path='_shared/reference_images/角色/林夏.png', stage='animatic', kind='资产'),
            FileRow(path='04分镜预演/版本/animatic_v001.mp4', stage='animatic', kind='视频'),
            *[FileRow(path=f'04分镜预演/镜头/SH{i:03d}/v1.png', stage='animatic', kind='图片')
              for i in range(1, 51)],
            FileRow(path='04分镜预演/声音/对白/SH001.mp3', stage='animatic', kind='音频'),
        ]
        groups = panel_index.animatic_grouped_rows(rows)
        labels = [label for _gid, label, _members in groups]
        self.assertEqual(['参考图库 (1)', '预演版本 (1)', '镜头草图 (50)', '临时声音 (1)'], labels)
        open_map = {label: panel_index.group_default_open(gid)
                    for gid, label, _members in groups}
        self.assertEqual({'参考图库 (1)': True, '预演版本 (1)': True,
                          '镜头草图 (50)': False, '临时声音 (1)': True}, open_map)
        prefetch = panel_index.prefetch_media_paths(groups, self.project)
        self.assertLessEqual(len(prefetch), 40)
        self.assertFalse(any('镜头' in str(path) for path in prefetch))
        self.assertTrue(any('声音' in str(path) for path in prefetch))

        async_calls = []
        orig_async = self.page.async_

        def track_async(fn, done=None, show_progress=True, label=None):
            async_calls.append(label)
            return orig_async(fn, done, show_progress=show_progress, label=label)

        self.page.async_ = track_async
        self.show()
        with patch('stage_execution_service.run_animatic_timeline',
                   return_value=self.project / '版本' / 'animatic_v001.mp4'):
            animatic_page.run_command(self.page, self.state, '')
        self.assertEqual(1, len(async_calls), '合成任务必须经宿主 async_ 托管执行')


if __name__ == '__main__':
    unittest.main()
