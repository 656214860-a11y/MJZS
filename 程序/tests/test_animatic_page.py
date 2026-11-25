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
    labels = []
    last = menu.index('end')
    for index in range(0, (last or -1) + 1):
        labels.append(str(menu.entrycget(index, 'label')))
    return labels


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
        source = Path(animatic_page.__file__).read_text(encoding='utf-8')
        for needle in ('tk.PhotoImage', 'messagebox', 'simpledialog', 'Toplevel(',
                       'tk.Menu(', 'ttk.Button(', 'tk.Button(', 'json.loads', 'json.load('):
            with self.subTest(needle=needle):
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


class SendCommandTests(_PageCase):
    """REQ-S04-96：发送键默认生成；「只重做 SHxxx」单镜重做；斜杠命令放行。"""

    def test_empty_send_generates_timeline(self):
        self.show()
        with patch('stage_execution_service.run_animatic_timeline') as run:
            accepted = self.page.shared_input.stage_action('animatic')()
        self.assertTrue(accepted)
        run.assert_called_once()
        self.assertEqual(self.project, run.call_args[0][0])

    def test_typed_redo_only_regenerates_that_shot(self):
        self.show()
        self.page.shared_input.set_text('只重做 SH001')
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = self.page.shared_input.stage_action('animatic')()
        self.assertTrue(accepted)
        redo.assert_called_once_with(self.project, 'SH001')

    def test_redo_unknown_shot_stays_local(self):
        self.show()
        with patch('stage_execution_service.regenerate_animatic_shot') as redo:
            accepted = animatic_page.run_command(self.page, self.state, '重做 SH099')
        self.assertFalse(accepted)
        self.assertFalse(redo.called)
        self.assertTrue(any('SH099' in message for message in self.page.status.messages))

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
                 '查看提示词与所用参考图', '写批注'],
                _menu_labels(menu))
            menu.invoke(0)
        redo.assert_called_once_with(self.project, 'SH001')

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
        audio_import.assert_called_once_with(self.project, audio)
        into.assert_called_once()
        self.assertEqual([clip], list(into.call_args[0][2]))
        self.assertEqual(3, len(result['imported']))

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
            self.assertIn('本地生成参考草图', labels)
            submenu = menu.nametowidget(menu.entrycget(labels.index('修改参考图分类'), 'menu'))
            submenu.invoke(0)  # 第一个分类＝角色
        reclassify.assert_called_once_with(self.project, ref, '角色')

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
        result = type('Result', (), {'ok': True, 'reason': ''})()
        with patch('stage_execution_service.generate_animatic_reference',
                   return_value=result) as generate:
            state['edit_commit']()
        generate.assert_called_once()
        self.assertEqual(('一只猫', 'model.safetensors'), generate.call_args[0][1:3])


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

    def test_video_menu_has_external_open(self):
        self.show()
        state = self.state
        menu = animatic_page.video_context_menu(self.page, state)
        self.assertIn('用外部播放器打开', _menu_labels(menu))


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


if __name__ == '__main__':
    unittest.main()
