"""语音输入离线化任务书轮 5：独立对话框复用共享听写组件。

白模预演「动作与机位备注」与阶段「调用设置」的「补充制作要求」两个可编辑
多行文本框在 Windows 上各挂一颗麦克风，绑定同一个 ``VoiceInput`` 组件
（partial/final 渲染、AI 优化生命周期与共享输入框同一实现）。
``VoiceInput`` 本体由 ``test_shared_input_voice`` 覆盖，这里只锚定接线：
按钮存在、组件绑对文本框、状态与项目上下文正确传入。
"""
import os
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

import desktop_voice_input
import white_model
import workflow_settings_dialog


class _VoiceRecorder:
    """记录 VoiceInput 的构造参数；不启动录音与识别。"""

    instances = []

    def __init__(self, box, button, **kwargs):
        self.box, self.button, self.kwargs = box, button, kwargs
        _VoiceRecorder.instances.append(self)


class DialogVoiceInputTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'project'
        self.project.mkdir()
        self.status = tk.StringVar(master=self.win, value='')
        _VoiceRecorder.instances.clear()

    def _recorded(self):
        self.assertEqual(len(_VoiceRecorder.instances), 1, '对话框应只创建一个听写组件')
        return _VoiceRecorder.instances[0]

    def test_white_model_notes_has_mic_bound_to_voice_input(self):
        shot_dir = Path(self.tmp.name) / 'shot'
        desktop = SimpleNamespace(win=self.win, root=self.project, status=self.status,
                                  video=None, current_frame_json=lambda: self.project / 'ep.json',
                                  open_flow_agent=lambda *a, **k: None)
        with patch.object(os, 'name', 'nt'), \
                patch.object(white_model, 'shot_directory', lambda *a, **k: shot_dir), \
                patch.object(white_model, 'read_record', lambda root: {'notes': '既有备注'}), \
                patch.object(white_model, 'find_blender', lambda refresh=False: None), \
                patch.object(desktop_voice_input, 'VoiceInput', _VoiceRecorder):
            white_model.open_previs(desktop, 'SH001')
            self.win.update_idletasks()
        voice = self._recorded()
        self.assertIsInstance(voice.box, tk.Text, '听写必须绑定备注文本框')
        self.assertIn('既有备注', voice.box.get('1.0', 'end'), '绑定的应是备注框而非其他文本')
        self.assertIs(voice.kwargs.get('status'), self.status)
        self.assertIs(voice.kwargs.get('project'), self.project)
        self.assertTrue(voice.button.winfo_exists())

    def test_flow_settings_notes_has_mic_bound_to_voice_input(self):
        saved = {'engine': 'claude', 'profiles': {
            'claude': {'program': '', 'model': '', 'skill': '', 'instructions': '既有要求'},
            'qwen': {'program': '', 'model': '', 'skill': '', 'instructions': ''}}}
        desktop = SimpleNamespace(win=self.win, _flow_settings_dialogs={}, status=self.status)
        with patch.object(os, 'name', 'nt'), \
                patch.object(workflow_settings_dialog, 'load', lambda *a, **k: saved), \
                patch.object(workflow_settings_dialog, 'preset_skill',
                             lambda folder: SimpleNamespace(is_file=lambda: False)), \
                patch.object(workflow_settings_dialog, 'find_program',
                             lambda config: ''), \
                patch('stage_parallel.page_lines', lambda *a, **k: []), \
                patch.object(desktop_voice_input, 'VoiceInput', _VoiceRecorder):
            workflow_settings_dialog.show_settings(desktop, self.project, stage='previs')
            self.win.update_idletasks()
        voice = self._recorded()
        self.assertIsInstance(voice.box, tk.Text, '听写必须绑定补充要求文本框')
        self.assertIn('既有要求', voice.box.get('1.0', 'end'), '绑定的应是补充要求框')
        self.assertIsInstance(voice.kwargs.get('status'), tk.StringVar)
        self.assertEqual(str(voice.kwargs.get('project')), str(self.project))
        self.assertTrue(voice.button.winfo_exists())

    def test_non_windows_builds_no_mic(self):
        shot_dir = Path(self.tmp.name) / 'shot'
        desktop = SimpleNamespace(win=self.win, root=self.project, status=self.status,
                                  video=None, current_frame_json=lambda: self.project / 'ep.json',
                                  open_flow_agent=lambda *a, **k: None)
        with patch.object(os, 'name', 'posix'), \
                patch.object(white_model, 'shot_directory', lambda *a, **k: shot_dir), \
                patch.object(white_model, 'read_record', lambda root: {}), \
                patch.object(white_model, 'find_blender', lambda refresh=False: None), \
                patch.object(desktop_voice_input, 'VoiceInput', _VoiceRecorder):
            white_model.open_previs(desktop, 'SH001')
            self.win.update_idletasks()
        self.assertEqual(_VoiceRecorder.instances, [], '非 Windows 不应创建听写组件')


if __name__ == '__main__':
    unittest.main()
