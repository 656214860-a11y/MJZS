"""语音输入离线化任务书轮 3：共享输入框麦克风——跨页同一实例、销毁即停、按钮布局。

契约（合并 master R2942 后）：``SharedStageInput`` 的 ``voice_button`` 经宿主
``on_voice`` 回调（``desktop_shared_send._voice``）惰性创建唯一 ``VoiceInput``
实例挂在 ``desktop.shared_voice``，绑定共享 Text；``set_stage`` 切页不重建会话；
输入框销毁停录并取消识别。全部 fake，不起真实麦克风与 ASR 引擎。
"""
import os
import queue
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import desktop_shared_input as shared_input
import desktop_shared_send
import contract.platform_tools as platform_tools
import domain.speech_api as speech_api
import writing_api
from skip_reasons import PLATFORM_WINDOWS_ONLY


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


class _FakeRecorder:
    instances = []

    def __init__(self, max_seconds=180, on_chunk=None):
        self.on_chunk, self.peak, self.seconds, self.level, self.error = on_chunk, 2000, 1.0, 0.4, ''
        self.finished, self.stopped = False, False
        _FakeRecorder.instances.append(self)

    def start(self):
        return ''

    def stop(self):
        self.stopped = True
        return b'', self.peak


class _FakeSession:
    instances = []

    def __init__(self, settings, **kwargs):
        self.events, self.sent, self.started, self.finished, self.cancelled = queue.Queue(), [], False, False, False
        _FakeSession.instances.append(self)

    def start(self):
        self.started = True

    def send(self, pcm):
        self.sent.append(pcm)

    def finish(self):
        self.finished = True

    def cancel(self):
        self.cancelled = True


class SharedInputVoiceTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.status = tk.StringVar(master=self.win, value='')
        self.desktop = SimpleNamespace(root=self.root, status=self.status, win=self.win)
        _FakeRecorder.instances.clear()
        _FakeSession.instances.clear()

    def _make(self, **kwargs):
        holder = {}

        def on_voice(button):
            return desktop_shared_send._voice(self.desktop, holder['box'].input, button)

        options = {'on_send': lambda text, parsed: True, 'on_voice': on_voice,
                   'skills': [], 'engines': ()}
        options.update(kwargs.pop('options', {}))
        box = shared_input.SharedStageInput(self.win, desktop=self.desktop, options=options, **kwargs)
        holder['box'] = box
        box.pack(fill='x')
        self.win.update_idletasks()
        self.addCleanup(box.destroy)
        return box

    def _voice(self):
        return getattr(self.desktop, 'shared_voice', None)

    def _listen(self, box):
        """点麦克风进入听写态（fake 录音机与会话）。"""
        with patch.object(platform_tools, 'MicrophoneRecorder', _FakeRecorder), \
                patch.object(speech_api, 'missing_reason', return_value=''), \
                patch.object(speech_api, 'create_session',
                             side_effect=lambda settings, **kw: _FakeSession(settings)):
            box.voice_button.invoke()
            self.win.update()
        return _FakeRecorder.instances[-1], _FakeSession.instances[-1]

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_voice_button_and_voice_bound_to_shared_text(self):
        box = self._make()
        self.assertIsNotNone(box.voice_button)
        _recorder, _session = self._listen(box)
        voice = self._voice()
        self.assertIsNotNone(voice)
        self.assertIs(voice.box, box.input, '听写会话必须绑定共享 Text')
        self.assertIs(voice.button, box.voice_button)
        # 左簇顺序：技能 → 附件 → 麦克风；输入框在按钮行之前（同在输入卡内）。
        row = box.voice_button.master
        self.assertEqual(list(row.winfo_children())[:3],
                         [box.skill_button, box.attachment_button, box.voice_button])
        card_children = list(box.input_card.winfo_children())
        self.assertLess(card_children.index(box.input), card_children.index(row))

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_set_stage_keeps_voice_session_alive(self):
        box = self._make()
        recorder, session = self._listen(box)
        voice = self._voice()
        box.set_stage('assets')
        self.win.update()
        self.assertIs(self._voice(), voice, '切页不得重建听写实例')
        self.assertFalse(recorder.stopped)
        self.assertFalse(session.cancelled)
        self.assertTrue(voice.listening)

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_dictation_writes_into_shared_input_and_closes(self):
        box = self._make()
        recorder, session = self._listen(box)
        voice = self._voice()
        box.input.delete('1.0', 'end'); box.input.insert('1.0', '开头：')
        session.events.put(('partial', 'a', '主角'))
        voice.poll(); self.win.update()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '开头：主角')
        self.assertTrue(box.input.tag_ranges(voice.PARTIAL_TAG))
        box.voice_button.invoke(); self.win.update()          # 再点关闭
        self.assertTrue(recorder.stopped)
        self.assertTrue(session.finished)
        session.events.put(('final', 'a', '主角走进雨夜。'))
        session.events.put(('closed', '', ''))
        voice.poll(); self.win.update()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '开头：主角走进雨夜。')
        self.assertFalse(box.input.tag_ranges(voice.PARTIAL_TAG))

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_destroying_shared_input_stops_and_cancels(self):
        box = self._make()
        recorder, session = self._listen(box)
        box.destroy()
        self.win.update()
        self.assertTrue(recorder.stopped, '输入框销毁必须停录')
        self.assertTrue(session.cancelled, '输入框销毁必须取消识别会话')

    def _ai_dictionary(self, enabled=True):
        return {'hotword': [], 'replace': {},
                'ai': {'enabled': enabled, 'template': 'fix', 'prompt': ''}}

    def _ai_patches(self, chat_result):
        adapter = SimpleNamespace(chat=lambda *a, **k: chat_result)
        return (patch.object(speech_api, 'read_dictionary',
                             return_value=self._ai_dictionary()),
                patch.object(writing_api, 'selected_model',
                             return_value=('m1', {'label': 'm1'})),
                patch.object(writing_api, '_writing_adapter', return_value=adapter))

    def _dictate_and_close(self, session, text='他说子进成。'):
        session.events.put(('final', 'a', text))
        session.events.put(('closed', '', ''))
        self._voice().poll()
        self.win.update()

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_ai_optimize_replaces_dictated_region(self):
        box = self._make()
        patches = self._ai_patches({'ok': True, 'text': '他说子进程。'})
        with patches[0], patches[1], patches[2]:
            _recorder, session = self._listen(box)
            self._dictate_and_close(session)
            time.sleep(0.3)
            self.win.update()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '他说子进程。')
        self.assertIn('AI 优化完成', self.status.get())

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_ai_optimize_skipped_when_disabled(self):
        box = self._make()
        adapter = SimpleNamespace(chat=lambda *a, **k: {'ok': True, 'text': '不应出现'})
        with patch.object(speech_api, 'read_dictionary',
                          return_value=self._ai_dictionary(enabled=False)), \
             patch.object(writing_api, 'selected_model',
                          return_value=('m1', {'label': 'm1'})), \
             patch.object(writing_api, '_writing_adapter', return_value=adapter):
            _recorder, session = self._listen(box)
            self._dictate_and_close(session)
            time.sleep(0.3)
            self.win.update()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '他说子进成。')
        self.assertNotIn('AI 优化', self.status.get())

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_ai_optimize_never_overwrites_user_edits(self):
        box = self._make()
        patches = self._ai_patches({'ok': True, 'text': 'AI改写'})
        with patches[0], patches[1], patches[2]:
            _recorder, session = self._listen(box)
            self._dictate_and_close(session)
            # 模型结果回来前用户手动改了听写区域 → 结果不得覆盖。
            box.input.insert('1.0', '手改：')
            time.sleep(0.3)
            self.win.update()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '手改：他说子进成。')
        self.assertIn('未写入', self.status.get())

    @unittest.skipIf(os.name != 'nt', PLATFORM_WINDOWS_ONLY)
    def test_ai_optimize_failure_keeps_original_text(self):
        box = self._make()
        patches = self._ai_patches({'ok': False, 'text': '他说子进成。', 'reason': '余额不足'})
        with patches[0], patches[1], patches[2]:
            _recorder, session = self._listen(box)
            self._dictate_and_close(session)
            time.sleep(0.3)
            self.win.update()
        self.assertEqual(box.input.get('1.0', 'end-1c'), '他说子进成。')
        self.assertIn('余额不足', self.status.get())

    def test_voice_start_failure_reports_in_status(self):
        """录音机起不来（如非 Windows 无 winmm）：状态栏说明原因，会话不启动，不抛异常。"""

        class _NoMic(_FakeRecorder):
            def start(self):
                return '仅支持 Windows'

        box = self._make()
        self.addCleanup(box.destroy)
        box.pack(fill='x')
        self.win.update_idletasks()
        self.assertIsNotNone(box.voice_button, 'R2942：语音按钮全平台常驻')
        with patch.object(platform_tools, 'MicrophoneRecorder', _NoMic), \
                patch.object(speech_api, 'missing_reason', return_value=''), \
                patch.object(speech_api, 'create_session',
                             side_effect=lambda settings, **kw: _FakeSession(settings)):
            box.voice_button.invoke()
            self.win.update()
        self.assertIn('未能启动', self.status.get())
        self.assertIn('仅支持 Windows', self.status.get())
        self.assertFalse(_FakeSession.instances[-1].started, '录音失败不得启动识别会话')
        # 其余入口不受影响（R2942：按钮是图标，文字在 Tooltip）。
        for widget in (box.skill_button, box.attachment_button, box.send_button):
            self.assertTrue(widget.winfo_exists())


if __name__ == '__main__':
    unittest.main()
