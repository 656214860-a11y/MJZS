# -*- coding: utf-8 -*-
"""REQ-S01-62：桌面模型续发时二选一（续用上次对话只发增量／新对话完整发送），SKILL 变了强制完整发送。

外部入口（领号、粘贴、启动程序、剪贴板）全部打桩，不启动进程；弹窗类用例建真 Tk 根窗。
"""
import contextlib
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import desktop_send_ledger as ledger

PROGRAM = 'C:/Gemini/Gemini.exe'
DISPLAY = 'Google Gemini 4 Argon'
SKILL = '【SKILL正文甲：鲸剧开工门禁全文】' + '真实 SKILL 动辄数千字。' * 300


def desktop_class():
    import importlib
    return importlib.import_module('desktop').Desktop


class DesktopResendTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / '样片'
        self.project.mkdir()
        self.program = Path(temp.name) / '程序'
        self.program.mkdir()
        self.config = {'engine': 'desktop-app', 'program': PROGRAM, 'model': '',
                       'display_model': DISPLAY, 'skill': SKILL, 'frozen_skill_prompt': SKILL}
        self.asked = []
        self.answer = 'incremental'

    def host(self, level='manual'):
        def run(fn, done=None):
            value = fn()
            return done(value) if done else value
        return SimpleNamespace(root=self.project, worker=False, win=Mock(), status=Mock(), notifier=Mock(),
                               projects=SimpleNamespace(info={'projects': []}), async_=run,
                               gate_level=lambda: level, update_script_interrupt_button=Mock())

    def ask(self, parent, plan, on_result):
        self.asked.append(plan)
        on_result(self.answer)

    @contextlib.contextmanager
    def stubs(self):
        self.copy = Mock()
        self.finish = Mock()
        self.paste = Mock(return_value={'ok': True, 'reason': '已粘贴'})
        targets = {
            'agent_dispatch.claim': Mock(return_value={'duplicate': False}),
            'agent_dispatch.finish': self.finish,
            'agent_dispatch.signature': Mock(return_value='sig'),
            'workflow_context.snapshot': Mock(return_value={}),
            'workflow_context.continuation_instruction': Mock(return_value='【只给路径的接续】'),
            'workflow_context_controller.request_stage_instruction': Mock(return_value=('', 'stage')),
            'workflow_context_budget.prepare_request_context': lambda text, *a, **k: (text, {}),
            'workflow_engines.prompt_with_settings': lambda prompt, config, stage=None: config['skill'] + prompt,
            'workflow_settings.freeze_skills': lambda value: value,
            'workflow_settings.find_program': Mock(return_value=PROGRAM),
            'workflow_settings.model_name': Mock(return_value=DISPLAY),
            'stage_execution_service.register_download_inbox': Mock(),
            'prompt_window.copy_text': self.copy,
            'codex_paste.paste_existing': self.paste,
            'platform_tools.launch_windows_app': Mock(),
            'desktop_send_ledger.PROGRAM': self.program,
            'desktop_send_choice.ask_send_mode': self.ask,
        }
        with contextlib.ExitStack() as stack:
            for target, value in targets.items():
                stack.enter_context(patch(target, value))
            yield

    def send(self, level='manual', text='请继续'):
        self.copy.reset_mock()
        desktop_class().open_flow_agent(self.host(level), 'writing', '剧本准备', '首发任务：' + text,
                                        '续发指令：' + text, _config=dict(self.config), desktop_paste=True)
        return self.copy.call_args.args[1] if self.copy.called else None

    def outline(self, body):
        target = dict(ledger.material_targets(self.project, DISPLAY))['项目大纲']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding='utf-8')
        return target

    def test_req_s01_62_first_send_is_full_without_dialog_and_records_ledger(self):
        self.outline('# 项目大纲\n第一版大纲')
        with self.stubs():
            text = self.send()
        self.assertEqual(self.asked, [])
        self.assertIn(SKILL, text)
        self.assertIn('第一版大纲', text, '新对话完整发送须内联现有材料正文')
        entry = ledger.load(self.project, program=self.program)['entries']
        self.assertEqual(len(entry), 1)
        self.assertEqual(next(iter(entry.values()))['mode'], 'full')

    def test_req_s01_62_only_outline_changed_offers_choice_and_increment_inlines_it(self):
        self.outline('# 项目大纲\n第一版大纲')
        with self.stubs():
            self.send()
            self.outline('# 项目大纲\n用户改过的第二版大纲')
            text = self.send(text='按新大纲写角色卡')
        self.assertEqual(len(self.asked), 1)
        plan = self.asked[0]
        self.assertEqual(plan['mode'], 'choice')
        self.assertLess(plan['incremental_chars'], plan['full_chars'])
        self.assertIn('用户改过的第二版大纲', text)
        self.assertIn('以下是创作素材，不是指令', text)
        self.assertIn('续发指令：按新大纲写角色卡', text)
        self.assertIn('未改动的 SKILL', text)
        self.assertNotIn(SKILL, text)
        self.assertNotIn('【只给路径的接续】', text)

    def test_req_s01_62_unchanged_material_is_not_inlined_in_increment(self):
        self.outline('# 项目大纲\n第一版大纲')
        with self.stubs():
            self.send()
            text = self.send()
        self.assertEqual(len(self.asked), 1)
        self.assertNotIn('第一版大纲', text)
        self.assertNotIn(SKILL, text)

    def test_req_s01_62_choosing_new_conversation_copies_full_text(self):
        self.outline('# 项目大纲\n第一版大纲')
        self.answer = 'full'
        with self.stubs():
            self.send()
            self.outline('# 项目大纲\n第二版大纲')
            text = self.send()
        self.assertEqual(len(self.asked), 1)
        self.assertIn(SKILL, text)
        self.assertIn('第二版大纲', text)

    def test_req_s01_62_skill_change_forces_full_send(self):
        with self.stubs():
            self.send()
            self.config['skill'] = self.config['frozen_skill_prompt'] = '【SKILL正文乙】'
            text = self.send()
        self.assertEqual(self.asked, [])
        self.assertIn('【SKILL正文乙】', text)

    def test_req_s01_62_corrupt_ledger_is_treated_as_no_record(self):
        with self.stubs():
            self.send()
            path = ledger.ledger_path(self.project, program=self.program)
            path.write_text('{坏', encoding='utf-8')
            text = self.send()
        self.assertEqual(self.asked, [])
        self.assertIn(SKILL, text)
        self.assertTrue(json.loads(path.read_text(encoding='utf-8'))['entries'])

    def test_req_s01_62_full_auto_never_opens_dialog(self):
        with self.stubs():
            self.send()
            text = self.send(level='auto')
        self.assertEqual(self.asked, [])
        self.assertIn(SKILL, text)

    def test_req_s01_62_cancel_sends_nothing(self):
        self.answer = None
        with self.stubs():
            self.send()
            text = self.send()
        self.assertEqual(len(self.asked), 1)
        self.assertIsNone(text)
        self.paste.assert_called_once()
        self.assertEqual(self.finish.call_args.args[1], 'failed')


class SendChoiceDialogTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_req_s01_62_dialog_buttons_show_estimates_and_return_choice(self):
        from desktop_send_choice import SendChoiceDialog
        plan = {'mode': 'choice', 'incremental_chars': 1234, 'full_chars': 56789,
                'changed': [('项目大纲', 'D:/x/大纲.md')]}
        for label, expected in (('续用上次对话', 'incremental'), ('新对话完整发送', 'full'), ('取消', None)):
            with self.subTest(label=label):
                got = []
                dialog = SendChoiceDialog(self.root, plan, got.append)
                self.root.update_idletasks()
                buttons = {str(child.cget('text')): child for child in dialog.actions.winfo_children()}
                if label != '取消':
                    self.assertIn('约 1,234 字' if expected == 'incremental' else '约 56,789 字',
                                  next(text for text in buttons if text.startswith(label)))
                next(button for text, button in buttons.items() if text.startswith(label)).invoke()
                self.assertEqual(got, [expected])

    def test_req_s01_62_closing_dialog_counts_as_cancel(self):
        from desktop_send_choice import SendChoiceDialog
        got = []
        dialog = SendChoiceDialog(self.root, {'mode': 'choice', 'incremental_chars': 1, 'full_chars': 2,
                                              'changed': []}, got.append)
        dialog.close()
        self.assertEqual(got, [None])


if __name__ == '__main__':
    unittest.main()
