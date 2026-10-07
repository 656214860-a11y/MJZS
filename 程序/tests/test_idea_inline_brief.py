"""R1099：内联八项门禁、制作锁别名和项目内覆盖保存。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import idea_chat
import script_contract
import workflow_settings
from tests.test_idea_chat import _Harness, idea_chat as injected_chat
from tests.test_ui_edges import make_minimal_project


VALUES = {'故事梗概': '修表师寻找失踪的父亲', '故事题材': '冒险喜剧',
          '故事角色': '林青：修表师\n  阿禾：船长', '故事集数': '12集',
          '单集时间': '120秒', '故事画幅': '9:16', '视频模型': 'MiniMax H3',
          '交付形态': '只要 markdown 文档'}


def draft(values=None):
    return '\n'.join(label + ':' + value for label, value in (values or VALUES).items())


class InlineBriefTests(unittest.TestCase):
    def test_coordinator_lists_readonly_locks_and_keeps_deviation_badge(self):
        from skill_panel import Panel
        name, preset = next(iter(workflow_settings.WORKFLOW_PRESETS.items()))
        view = SimpleNamespace(project=lambda: 'unused', workflow_choice=Mock(),
                               workflow_summary=Mock(), show_workflow_differences=Mock())
        with patch('stage_config.current_workflow', return_value={'name': name}), \
                patch('stage_config.workflow_lock', return_value={'aspect_ratio': '9:16'}), \
                patch('stage_config.workflow_deviation_count', return_value=2):
            Panel.refresh_workflow(view)
        text = view.workflow_summary.configure.call_args.kwargs['text']
        self.assertTrue(text.startswith('制作锁'))
        for item in preset['locks']:
            self.assertIn(item['label'] + '=' + ('9:16' if item['key'] == 'aspect_ratio' else '未填写'), text)
        self.assertIn('2 个阶段已本地修改', text)
        view.workflow_summary.bind.assert_called_once()
        self.assertFalse(hasattr(Panel, 'open_workflow_brief'))

    def test_every_empty_or_unchanged_value_is_missing_in_order(self):
        template = draft({label: '示例' + label for label in VALUES})
        self.assertEqual(idea_chat.inline_required_missing(template, draft()), ())
        for label in script_contract.INLINE_REQUIRED_LABELS:
            for value in ('', '示例 ' + label + '（必填）'):
                with self.subTest(label=label, value=value):
                    changed = dict(VALUES, **{label: value})
                    self.assertEqual(idea_chat.inline_required_missing(template, draft(changed)), (label,))
        self.assertEqual(idea_chat.inline_required_missing(template, template),
                         script_contract.INLINE_REQUIRED_LABELS)
        self.assertEqual(script_contract.BRIEF_REQUIRED_FIELDS,
                         ('story_summary', 'main_characters', 'genre', 'length'))

    def test_multiline_boundaries_and_whitespace_placeholders(self):
        template = draft() + '\n世界设定:海岛'
        changed = template.replace('林青：修表师\n  阿禾：船长', '林青：修表师\n    阿禾：船长')
        self.assertIn('故事角色', idea_chat.inline_required_missing(template, changed))
        changed = draft(dict(VALUES, 故事角色='')) + '\n世界设定:不应冒充角色'
        self.assertIn('故事角色', idea_chat.inline_required_missing(template, changed))

    def test_lock_aliases_and_current_inline_values_win_over_saved_values(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            injected_chat.save_brief_creation(root, draft(dict(VALUES, 故事梗概='旧梗概')))
            preset = next(iter(workflow_settings.WORKFLOW_PRESETS.values()))
            result = injected_chat.receive_brief(root, draft(), inline_text=draft(),
                                                lock_definitions=preset['locks'])
            self.assertEqual(result['missing'], ())
            self.assertEqual(result['fields']['story_summary'], VALUES['故事梗概'])
            self.assertEqual(result['fields']['production_locks'],
                             {'aspect_ratio': '9:16', 'video_model_version': 'MiniMax H3',
                              'delivery_format': '只要 markdown 文档'})

    def test_overwrite_preserves_whole_template_without_visual_markers(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            injected_chat.save_brief_creation(root, '旧内容')
            text = '# 我的创意\n' + draft() + '\n内容补充:海岛'
            path, saved = injected_chat.save_brief_creation(root, text.replace('12集', '12集（必填）'))
            self.assertEqual(saved, text)
            self.assertEqual(path.read_text(encoding='utf-8'), text)
            self.assertEqual(injected_chat.brief_creation_values(root)['故事梗概'], VALUES['故事梗概'])


class InlineBriefDesktopTests(_Harness):
    def test_prefilled_example_and_required_tags_do_not_clear_on_typing(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            self.assertEqual(d.draft_text(), d.idea_example())
            self.assertEqual(len(d.idea_input.tag_ranges('required_hint')), 16)
            self.assertGreater(int(d.idea_input.cget('height')), 1)
            d.idea_input.insert('end-1c', '新增'); win.update()
            self.assertTrue(d.draft_text().startswith(d.idea_example()))
            self.assertFalse(hasattr(d, 'open_brief_creation_form'))

    def test_complete_inline_send_saves_and_starts_without_prompt(self):
        default = Path(__file__).resolve().parents[1] / '默认创意示例.md'
        before = default.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_input.delete('1.0', 'end'); d.idea_input.insert('1.0', draft())
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
            launch.assert_called_once()
            notice.assert_not_called()
            self.assertEqual(injected_chat.brief_raw_path(root).read_text(encoding='utf-8'), draft())
        self.assertEqual(default.read_bytes(), before)

    def test_each_missing_or_example_value_notifies_without_starting(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            template_values = idea_chat.extract_brief_creation(d.idea_template,
                extra_labels=idea_chat.inline_template_labels(d.idea_template), include_extra=True)
            for label in script_contract.INLINE_REQUIRED_LABELS:
                for value in ('', template_values[label]):
                    with self.subTest(label=label, value=value):
                        text = draft(dict(VALUES, **{label: value}))
                        d.idea_input.delete('1.0', 'end'); d.idea_input.insert('1.0', text)
                        with patch.object(d, 'start_script_workflow') as launch, \
                                patch.object(d.notifier, 'info') as notice:
                            d.send_message()
                        launch.assert_not_called()
                        self.assertIn('请先填写：' + label, notice.call_args.args[0])
                        self.assertEqual(d.draft_text(), text)
            self.assertFalse(injected_chat.brief_raw_path(root).exists())


if __name__ == '__main__':
    unittest.main()
