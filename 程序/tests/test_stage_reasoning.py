# -*- coding: utf-8 -*-
"""阶段推理等级自检（REQ-S01-82 / R2541）：配置持久化、options 注入、协议映射、选择器菜单。

契约四条：
1. `reasoning` 存项目 `skill_config.json` 阶段项，档位 auto/low/medium/high，缺省与坏值归一为 auto；
2. 「自动」不附加任何请求参数；
3. 参数只下发给带 `reasoning` 能力标签的模型，并按 wire_api 映射
   （chat→reasoning_effort / responses→reasoning.effort / messages→thinking.budget_tokens）；
4. 选择器菜单项只显示模型名，能推理的项带「推理·<档位>」标记，档位走内嵌子菜单。

运行：python -B test_stage_reasoning.py（含 Tk 的用例在隐藏桌面 runner 下跑）
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

from skip_reasons import PLATFORM_TKINTER, PLATFORM_TK_DISPLAY

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(1, HERE)
os.chdir(PROGRAM)

import infra.model_router as model_router
import stage_config
import stage_model_value


def _adapter(wire_api='chat', capabilities=('reasoning',)):
    """裸 ModelAdapter：挂上一条带能力标签的模型记录，只为测 payload 拼装。"""
    adapter = model_router.ModelAdapter()
    adapter.wire_api = wire_api
    adapter.models = {'m1': {'capabilities': tuple(capabilities)}}
    return adapter


def _payload(adapter, options=None, model='m1'):
    return adapter.payload(model, [{'role': 'user', 'content': 'hi'}], options or {}, 'sys')


class StageReasoningConfigTests(unittest.TestCase):
    """REQ-S01-82：reasoning 字段持久化与归一化。"""

    def test_default_and_legacy_entries_read_as_auto(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_config.get(td, 'script')[stage_config.REASONING], 'auto')
            # 模拟旧项目：写一份没有 reasoning 字段的配置，读出仍是 auto（向后兼容）
            stage_config.save_all(td, {'script': {'model': 'qwen-max', 'skills': []}})
            entry = stage_config.get(td, 'script')
            self.assertEqual(entry[stage_config.REASONING], 'auto')
            self.assertEqual(entry['model'], 'qwen-max')

    def test_put_persists_and_normalizes_reasoning(self):
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'script', reasoning='high')
            self.assertEqual(stage_config.get(td, 'script')[stage_config.REASONING], 'high')
            stage_config.put(td, 'script', reasoning='乱写的')
            self.assertEqual(stage_config.get(td, 'script')[stage_config.REASONING], 'auto')
            stage_config.put(td, 'script', reasoning=' HIGH ')
            self.assertEqual(stage_config.get(td, 'script')[stage_config.REASONING], 'high')

    def test_put_reasoning_leaves_model_and_skills_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'script', model='qwen-max', skills=['pipeline-script-preparation'])
            stage_config.put(td, 'script', reasoning='low')
            entry = stage_config.get(td, 'script')
            self.assertEqual(entry['model'], 'qwen-max')
            self.assertEqual(entry['skills'], ['pipeline-script-preparation'])

    def test_clean_reasoning(self):
        self.assertEqual(stage_config.clean_reasoning('medium'), 'medium')
        self.assertEqual(stage_config.clean_reasoning(''), 'auto')
        self.assertEqual(stage_config.clean_reasoning(None), 'auto')
        self.assertEqual(stage_config.clean_reasoning('xhigh'), 'auto')


class ReasoningOptionsTests(unittest.TestCase):
    """DES-S01-82：stage_model_value 把已存档位翻译成可并入 options 的一项。"""

    def test_auto_and_missing_read_as_no_option(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(stage_model_value.reasoning_options(td, 'script'), {})
            stage_config.put(td, 'script', reasoning='auto')
            self.assertEqual(stage_model_value.reasoning_options(td, 'script'), {})

    def test_saved_level_returns_option(self):
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'storyboard', reasoning='low')
            self.assertEqual(stage_model_value.reasoning(td, 'storyboard'), 'low')
            self.assertEqual(stage_model_value.reasoning_options(td, 'storyboard'),
                             {'reasoning': 'low'})

    def test_broken_config_falls_back_to_no_option(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / 'skill_config.json'
            bad.write_text('not json', encoding='utf-8')
            self.assertEqual(stage_model_value.reasoning_options(td, 'script'), {})


class ReasoningPayloadTests(unittest.TestCase):
    """DES-S01-82：ModelAdapter.payload 按 wire_api 与能力标签映射推理档位。"""

    def test_chat_wire_sends_reasoning_effort(self):
        body = _payload(_adapter('chat'), {'reasoning': 'low'})
        self.assertEqual(body['reasoning_effort'], 'low')
        self.assertNotIn('reasoning', body)

    def test_responses_wire_sends_reasoning_effort_object(self):
        body = _payload(_adapter('responses'), {'reasoning': 'high'})
        self.assertEqual(body['reasoning'], {'effort': 'high'})
        self.assertNotIn('reasoning_effort', body)

    def test_messages_wire_sends_thinking_budget(self):
        body = _payload(_adapter('messages'),
                        {'reasoning': 'medium', 'max_tokens': 60000})
        self.assertEqual(body['thinking'],
                         {'type': 'enabled',
                          'budget_tokens': model_router.REASONING_THINKING_BUDGET['medium']})

    def test_thinking_budget_is_capped_below_max_tokens(self):
        body = _payload(_adapter('messages'),
                        {'reasoning': 'high', 'max_tokens': 4096})
        self.assertEqual(body['thinking']['budget_tokens'], 4095)
        # max_tokens-1 不足思考预算下限 1024 时干脆不下发
        body = _payload(_adapter('messages'),
                        {'reasoning': 'low', 'max_tokens': 1024})
        self.assertNotIn('thinking', body)

    def test_model_without_reasoning_capability_gets_nothing(self):
        adapter = _adapter('chat', capabilities=('vision',))
        body = _payload(adapter, {'reasoning': 'high'})
        self.assertNotIn('reasoning_effort', body)

    def test_auto_and_unknown_levels_send_nothing(self):
        adapter = _adapter('chat')
        for options in ({}, {'reasoning': 'auto'}, {'reasoning': 'xhigh'},
                        {'reasoning': '  '}):
            body = _payload(adapter, options)
            self.assertNotIn('reasoning_effort', body, options)
            self.assertNotIn('reasoning', body, options)

    def test_level_strings_are_normalized(self):
        body = _payload(_adapter('chat'), {'reasoning': ' HIGH '})
        self.assertEqual(body['reasoning_effort'], 'high')


class WritingReasoningInjectionTests(unittest.TestCase):
    """DES-S01-82：WritingRequestAdapter._call 把本阶段档位并入 options。"""

    class _FakeAdapter:
        wire_api = 'chat'

        def __init__(self):
            self.seen = None

        def chat(self, messages, options=None, model='', system=''):
            self.seen = dict(options or {})
            return {'ok': True, 'text': 'x', 'model': model, 'usage': {}, 'data': None}

    def test_call_injects_saved_reasoning(self):
        import writing_api
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'script', reasoning='low')
            inner = self._FakeAdapter()
            adapter = writing_api.WritingRequestAdapter(inner, {}, 'm1', project=td, stage='script')
            result = adapter.chat([{'role': 'user', 'content': 'hi'}],
                                  options={'max_tokens': 100}, model='m1')
            self.assertTrue(result['ok'])
            self.assertEqual(inner.seen.get('reasoning'), 'low')
            self.assertEqual(inner.seen.get('max_tokens'), 100)

    def test_explicit_reasoning_in_options_is_not_overridden(self):
        import writing_api
        with tempfile.TemporaryDirectory() as td:
            stage_config.put(td, 'script', reasoning='low')
            inner = self._FakeAdapter()
            adapter = writing_api.WritingRequestAdapter(inner, {}, 'm1', project=td, stage='script')
            adapter.chat([{'role': 'user', 'content': 'hi'}],
                         options={'max_tokens': 100, 'reasoning': 'high'}, model='m1')
            self.assertEqual(inner.seen.get('reasoning'), 'high')

    def test_auto_stage_injects_nothing(self):
        import writing_api
        with tempfile.TemporaryDirectory() as td:
            inner = self._FakeAdapter()
            adapter = writing_api.WritingRequestAdapter(inner, {}, 'm1', project=td, stage='script')
            adapter.chat([{'role': 'user', 'content': 'hi'}],
                         options={'max_tokens': 100}, model='m1')
            self.assertNotIn('reasoning', inner.seen)


class ReasoningPickerTests(unittest.TestCase):
    """REQ-S01-82：选择器仅模型名、推理标记与档位区（R2964 起为上方卡片浮层）。"""

    def setUp(self):
        try:
            import tkinter as tk
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.tk = tk
        try:
            self.win = self.tk.Tk()
        except self.tk.TclError:
            self.skipTest(PLATFORM_TK_DISPLAY)
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        class Fake(object):
            pass

        self.desktop = Fake()
        self.desktop.win = self.win
        self.desktop.root = Path(self.tmp.name) / 'p'
        self.desktop.root.mkdir(parents=True, exist_ok=True)
        self.desktop.app = Path(self.tmp.name) / '程序'
        self.desktop.app.mkdir(parents=True, exist_ok=True)

    def _spec_rows(self, picker):
        return picker._popup_spec()

    def test_popup_shows_names_level_badge_and_persists_choice(self):
        import model_pool
        import stage_model_picker
        data = model_pool.upsert(model_pool.raw(self.desktop.app),
                                 {'label': '会推理', 'model': 'reasoner-1',
                                  'capabilities': ['reasoning', 'vision']})
        model_pool.store(data, self.desktop.app)
        picker = stage_model_picker.StageModelPicker(self.win, self.desktop, 'keyframe')
        self.addCleanup(picker.destroy)
        self.assertIn('reasoner-1', picker._capable)
        self.assertIn('会推理', picker.labels())
        for provider, options in picker.groups.items():
            for _model_id, label in options:
                self.assertNotIn('%s · %s' % (provider, label), picker.labels(),
                                 '菜单项只显示模型名称，不得带「供应商 · 」前缀')

        spec = self._spec_rows(picker)
        models = [row for row in spec if row['kind'] == 'model']
        capable = [row for row in models if row['label'] == '会推理']
        self.assertEqual(len(capable), 1)
        self.assertEqual(capable[0]['badge'], '推理·自动', '能推理的模型项要带当前档位标记')
        plain = [row for row in models if row['id'] not in picker._capable]
        self.assertTrue(plain and all(not row['badge'] for row in plain),
                        '不带推理能力的模型项不得有档位标记')
        reasoning = [row for row in spec if row['kind'] == 'reasoning']
        self.assertEqual([row['label'] for row in reasoning], ['推理等级'])
        self.assertEqual([value for value, _label, _cur in reasoning[0]['levels']],
                         ['auto', 'low', 'medium', 'high'])
        self.assertFalse(any(row['kind'] == 'add' for row in spec),
                         'REQ-S01-91：「+ 添加模型…」移到共享输入框「＋」下拉，模型浮层不再保留')

        picker.choose_reasoning('high')
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['reasoning'], 'high')
        spec = self._spec_rows(picker)
        models = [row for row in spec if row['kind'] == 'model']
        self.assertEqual([row['badge'] for row in models if row['label'] == '会推理'],
                         ['推理·高'])
        reasoning = [row for row in spec if row['kind'] == 'reasoning']
        self.assertEqual([cur for _v, _l, cur in reasoning[0]['levels']],
                         [False, False, False, True], '高档应为当前档')

        picker.choose_reasoning('没这档')
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['reasoning'], 'auto')


if __name__ == '__main__':
    unittest.main()
