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
from tests.ui_edges_support import make_minimal_project


VALUES = {'故事梗概': '修表师寻找失踪的父亲', '故事题材': '冒险喜剧',
          '故事角色': '林青：修表师\n  阿禾：船长', '故事集数': '12集',
          '单集时间': '120秒', '故事画幅': '9:16', '视频模型': 'MiniMax H3',
          '交付形态': '只要 markdown 文档'}


def draft(values=None):
    return '\n'.join(label + ':' + value for label, value in (values or VALUES).items())


class InlineBriefTests(unittest.TestCase):
    def test_xlsx_later_cell_and_story_aliases_feed_attachment_gate(self):
        text = ('【工作表：主线】\n设定\t故事集数：12集\n'
                '单集时间：120秒\n故事画幅：9:16\n视频模型：MiniMax H3\n'
                '故事主线：修表师寻找失踪的父亲\n故事人物：林青与阿禾')
        fields = idea_chat.extract_brief_creation(text,
            extra_labels=script_contract.INLINE_REQUIRED_LABELS, include_extra=True)
        self.assertEqual(fields['故事集数'], '12集')
        self.assertEqual(fields['故事梗概'], '修表师寻找失踪的父亲')
        self.assertEqual(fields['故事角色'], '林青与阿禾')
        self.assertEqual(idea_chat.inline_required_missing(None, '', attachment_fields=fields),
                         ('故事题材', '交付形态'))
        self.assertEqual(idea_chat.inline_required_missing(None,
            '故事题材：冒险喜剧\n交付形态：markdown文档', attachment_fields=fields), ())
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            preset = next(iter(workflow_settings.WORKFLOW_PRESETS.values()))
            result = injected_chat.receive_brief(root, '【附档：输入/材料.xlsx】',
                inline_text='故事题材：冒险喜剧\n交付形态：markdown文档',
                lock_definitions=preset['locks'], attachment_reference={'brief_texts': [text]})
            self.assertEqual(result['missing'], ())
            self.assertIn('12集', result['fields']['length'])
            self.assertEqual(result['fields']['story_summary'], '修表师寻找失踪的父亲')
            self.assertEqual(result['fields']['main_characters'], '林青与阿禾')

    def test_all_brief_aliases_and_nested_setting_cell(self):
        for summary in ('故事主线', '故事主体', '剧情'):
            for genre in ('故事主题', '类型', '风格'):
                text = f'{summary}：寻找父亲\n{genre}：冒险\n故事人物：林青'
                fields = idea_chat.extract_brief_creation(text)
                self.assertEqual(fields, {'故事梗概': '寻找父亲', '故事题材': '冒险', '故事角色': '林青'})
        for text in ('设定：故事集数：100 集\n单集时间：90s',
                     '设定\t故事集数：100 集\\n单集时间：90s',
                     '| 设定 | 故事集数：100 集<br>单集时间：90s |'):
            fields = idea_chat.extract_brief_creation(text, extra_labels=('设定',), include_extra=True)
            self.assertEqual(fields.get('故事集数'), '100 集')
            self.assertEqual(fields.get('单集时间'), '90s')

    def test_fill_missing_preserves_manual_and_unknown_text(self):
        text = '我的标题\n自定字段：保留\n故事主线：手填梗概\n故事角色：\n'
        merged = idea_chat.merge_brief_creation(text, {'故事梗概': '附件梗概', '故事角色': '林青'})
        self.assertEqual(merged, text.replace('故事角色：', '故事角色：林青'))

    def test_attachment_values_satisfy_gate_without_template_comparison(self):
        template = draft()
        self.assertEqual(idea_chat.inline_required_missing(template, template,
                         attachment_fields=VALUES), ())
        for label in script_contract.INLINE_REQUIRED_LABELS:
            values = dict(VALUES, **{label: ' \t\n'})
            self.assertEqual(idea_chat.inline_required_missing(template, template,
                             attachment_fields=values), (label,))
        self.assertEqual(idea_chat.inline_required_missing(template, '',
                         attachment_fields={'故事梗概': VALUES['故事梗概']}),
                         script_contract.INLINE_REQUIRED_LABELS[1:] + ('交付形态',))

    def test_attachment_length_requires_explicit_episode_and_duration(self):
        self.assertEqual(idea_chat.extract_brief_creation('篇幅：12集，每集120秒'),
                         {'故事集数': '12集', '单集时间': '120秒'})
        self.assertEqual(idea_chat.extract_brief_creation('篇幅：12集'), {'故事集数': '12集'})

    def test_attachment_locks_and_fields_replace_only_template_placeholders(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            template = draft({label: '示例' + label for label in VALUES})
            preset = next(iter(workflow_settings.WORKFLOW_PRESETS.values()))
            text = draft().replace('故事画幅:', '画幅:').replace('视频模型:', '视频模型版本:')
            result = injected_chat.receive_brief(root, '【附档：输入/材料.md】',
                inline_text=template, inline_template=template, lock_definitions=preset['locks'],
                attachment_reference={'brief_texts': [text]})
            self.assertEqual(result['missing'], ())
            self.assertEqual(result['fields']['story_summary'], VALUES['故事梗概'])
            self.assertEqual(result['fields']['production_locks']['aspect_ratio'], '9:16')
            self.assertEqual(result['fields']['production_locks']['video_model_version'], 'MiniMax H3')
            changed = template.replace('示例故事梗概', '手写梗概').replace('示例故事画幅', '4:3')
            result = injected_chat.receive_brief(root, '【附档：输入/材料.md】',
                inline_text=changed, inline_template=template, lock_definitions=preset['locks'],
                attachment_reference={'brief_texts': [text]})
            self.assertEqual(result['fields']['story_summary'], '手写梗概')
            self.assertEqual(result['fields']['production_locks']['aspect_ratio'], '4:3')

    def test_non_inline_receive_reads_attachment_lock_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            preset = next(iter(workflow_settings.WORKFLOW_PRESETS.values()))
            result = injected_chat.receive_brief(root, '请读取附档\n故事画幅：', lock_definitions=preset['locks'],
                attachment_reference={'brief_texts': [draft()]})
            self.assertEqual(result['fields']['production_locks'],
                             {'aspect_ratio': '9:16', 'video_model_version': 'MiniMax H3',
                              'delivery_format': '只要 markdown 文档'})

    def test_coordinator_refreshes_editable_locks_without_save_badge(self):
        from skill_panel import Panel
        name, preset = next(iter(workflow_settings.WORKFLOW_PRESETS.items()))
        view = SimpleNamespace(project=lambda: 'unused', workflow_choice=Mock(),
                               workflow_summary=Mock(), show_workflow_differences=Mock(), sync_master_skill=Mock(return_value=None),
                               lock_inputs={item['key']: Mock() for item in preset['locks']},
                               lock_fields=Mock())
        with patch('stage_config.current_workflow', return_value={'name': name}), \
                patch('stage_config.workflow_lock', return_value={'aspect_ratio': '9:16'}), \
                patch('stage_config.workflow_deviation_count', return_value=2), \
                patch('stage_execution_service.sync_writing_attachment_locks'):
            Panel.refresh_workflow(view)
        for item in preset['locks']:
            view.lock_inputs[item['key']].insert.assert_called_once_with(
                0, '9:16' if item['key'] == 'aspect_ratio' else '')
        view.workflow_summary.configure.assert_not_called()
        view.workflow_summary.bind.assert_not_called()
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
                         script_contract.INLINE_REQUIRED_LABELS + ('交付形态',))
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
    def test_api_stage_confirmation_keeps_brief_and_refreshes_saved_document(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', '确认')
            result = {'ok': True, 'text': '# 剧本大纲\n正文\n待确认',
                      'preparation_stage': '剧本大纲', 'preparation_path': str(Path(td) / 'outline.md')}
            prepared = {'submission': '确认\n\n附件：故事梗概：雨夜',
                        'visible_value': '确认【已引用：人物.md】',
                        'attachments': {'context': '故事梗概：雨夜', 'names': ['人物.md'],
                                        'brief_texts': ['故事梗概：雨夜']}}
            def finish(_action, received, **_kwargs):
                received(_action())
                return 1
            with patch('writing_api.capture_request_model', return_value={'id': 'gpt-4o', 'label': 'gpt-4o', 'model_id': 'test-model', 'record': {}}), \
                 patch('writing_api.preparation_continuation', return_value=True) as continuation, \
                 patch.object(d.idea_chat_controller, 'prepare_submission', return_value=prepared), \
                 patch('stage_execution_service.reply_to_writing', return_value=result) as reply, \
                 patch('idea_chat.receive_brief') as receive, \
                 patch('idea_chat.save_brief_creation') as save, \
                 patch.object(d, 'show_missing_idea_brief') as missing, \
                 patch.object(d, 'refresh_script_list') as refresh, \
                 patch.object(d, 'async_', side_effect=finish), \
                 patch('workflow_engines.request_stage_process_slot', return_value={'state': 'granted', 'slot': 'test'}):
                d.send_message()
            continuation.assert_called_once_with(d.root, '确认')
            self.assertEqual(reply.call_args.kwargs['user_message'], '确认')
            self.assertEqual(reply.call_args.kwargs['request_model']['model_id'], 'test-model')
            self.assertEqual(reply.call_args.args[1], prepared['submission'])
            receive.assert_not_called()
            save.assert_not_called()
            missing.assert_not_called()
            refresh.assert_called_once()
            self.assertIn('剧本大纲已保存', d.status.get())
            self.assertIn('确认', d.status.get())

    def test_rejected_response_is_shown_once_without_refreshing_official_documents(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', '确认')
            body = '模型返回的完整可见正文，但标题格式不符。'
            result = {'ok': False, 'text': '', 'response_text': body, 'error': '阶段格式不符，未采用'}
            prepared = {'submission': '确认', 'visible_value': '确认',
                        'attachments': {'context': '', 'names': [], 'brief_texts': []}}
            def finish(action, received, **kwargs):
                received(action())
                return 1
            with patch('writing_api.capture_request_model', return_value={'id': 'gpt-4o', 'label': 'gpt-4o', 'record': {}}), \
                 patch('writing_api.preparation_continuation', return_value=True), \
                 patch.object(d.idea_chat_controller, 'prepare_submission', return_value=prepared), \
                 patch('stage_execution_service.reply_to_writing', return_value=result), \
                 patch('idea_chat.append', wraps=idea_chat.append) as append, \
                 patch.object(d, 'refresh_script_list') as refresh, \
                 patch.object(d, 'async_', side_effect=finish), \
                 patch('workflow_engines.request_stage_process_slot', return_value={'state': 'granted', 'slot': 'test'}):
                d.send_message()
            replies = [call for call in append.call_args_list if call.args[1] == 'assistant']
            self.assertEqual(len(replies), 1)
            self.assertEqual(replies[0].args[2], body)
            refresh.assert_not_called()
            self.assertIn('未采用', d.status.get())

    def test_missing_dialog_saves_all_fields_then_explicit_resend(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', '自定字段：保留\n故事梗概：手填梗概\n故事角色：')
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, patch.object(d.notifier, 'info') as notice:
                d.send_message()
                dialog = d._idea_missing_dialog
                self.assertEqual(set(dialog.brief_fields), set(VALUES) - {'故事梗概', '故事画幅', '视频模型'})
                for label, entry in dialog.brief_fields.items():
                    # 下拉框（SelectBox）与文字输入（TextArea）的读写接口不同；R2480 交付形态改下拉框，
                    # 故用控件类型而非字段名判断（与保存辅助 entry_text 一致）。
                    import tkinter as _tk
                    if isinstance(entry, _tk.Text):
                        entry.delete('1.0', 'end'); entry.insert('1.0', VALUES[label])
                    else:
                        entry.set(VALUES[label])
                next(button for button in dialog.actions.winfo_children() if button.cget('text') == '保存').invoke()
                launch.assert_not_called()
                self.assertIn('故事梗概：手填梗概', d.draft_text())
                self.assertIn('自定字段：保留', d.draft_text())
                self.assertEqual(d.draft_text().count('故事角色：'), 1)
                d.send_message()
                launch.assert_called_once()
                notice.assert_not_called()

    def test_missing_dialog_cancel_leaves_draft_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            with patch.object(d, 'start_script_workflow') as launch:
                d.send_message()
                dialog = d._idea_missing_dialog
                self.assertEqual(set(dialog.brief_fields), set(VALUES) - {'故事画幅', '视频模型'})
                dialog.brief_fields['故事梗概'].insert('1.0', '未保存内容')
                dialog.close()
                self.assertEqual(d.draft_text(), '')
                launch.assert_not_called()

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_tabular_attachment_plus_missing_fields_in_input_starts_workflow(self, _local):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            source = Path(td) / '表格转换稿.md'
            body = ('设定\t故事集数：12集\n单集时间：120秒\n'
                    '故事画幅：9:16\n视频模型：MiniMax H3\n'
                    '故事主线：修表师寻找失踪的父亲\n故事人物：林青与阿禾')
            source.write_text(body, encoding='utf-8')
            stored = archive_idea_attachments(root, [source])
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_attachment_paths = tuple(stored)
            d.idea_input.insert('1.0', '故事题材：冒险喜剧\n交付形态：markdown文档')
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
            notice.assert_not_called()
            launch.assert_called_once()
            submission = launch.call_args.args[0]
            self.assertIn('【附档：01剧本准备/输入/', submission)
            self.assertNotIn('修表师寻找失踪的父亲', submission)
            self.assertNotIn(d.idea_template, submission)

    def test_readonly_example_enter_does_not_send_but_input_enter_sends(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            self.assertFalse(hasattr(d, 'idea_brief_editor'))
            with patch.object(d, 'send_message') as send:
                win.deiconify(); win.update()
                d.idea_log.focus_force(); win.update()
                before = d.idea_log.get('1.0', 'end-1c')
                d.idea_log.event_generate('<Return>'); win.update()
                self.assertEqual(d.idea_log.get('1.0', 'end-1c'), before)
                send.assert_not_called()
                d.idea_input.focus_force(); win.update()
                d.idea_input.event_generate('<Return>'); win.update()
                send.assert_called_once()

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_upload_preserves_input_and_uses_attachment_fields_on_send(self, _local):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            source = Path(td) / '材料.txt'
            source.write_text(draft().replace('故事角色:', '主要角色:')
                              .replace('故事画幅:', '画幅:')
                              .replace('视频模型:', '视频模型版本:') + '\n世界设定：海上城市', encoding='utf-8')
            paths = archive_idea_attachments(root, [source])
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', '保留这条追问\n故事题材：手填题材')
            before = d.idea_log.get('1.0', 'end-1c')
            controller = d.idea_chat_controller
            token = object(); controller._attachment_token = token
            controller._attachment_results.put((token, True, {'paths': paths, 'names': ['材料.txt']}))
            d.poll_idea_attachment_preparation()
            self.assertEqual(d.draft_text(), '保留这条追问\n故事题材：手填题材')
            self.assertEqual(tuple(d.idea_attachment_paths), tuple(str(p) for p in paths))
            self.assertEqual(d.idea_log.get('1.0', 'end-1c'), before)
            self.assertFalse(injected_chat.brief_raw_path(root).exists())
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
            launch.assert_called_once()
            notice.assert_not_called()
            self.assertNotIn(d.idea_template, launch.call_args.args[0])

    def test_upload_keeps_manual_multiline_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            current = '我的标题\n故事角色：手填主角\n  配角：保留细节\n自定字段：保留\n内容补充：\n'
            d.idea_input.insert('1.0', current)
            with patch.object(d.idea_chat_controller, 'poll_attachment_preparation',
                              return_value={'ok': True, 'value': {'names': ['材料.txt']}}):
                d.poll_idea_attachment_preparation()
            self.assertEqual(d.draft_text(), current)

    def test_failed_upload_does_not_change_input_or_example(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', '保留用户输入')
            before = d.idea_log.get('1.0', 'end-1c')
            with patch.object(d.idea_chat_controller, 'poll_attachment_preparation',
                              return_value={'ok': False, 'value': '解析失败'}):
                d.poll_idea_attachment_preparation()
            self.assertEqual(d.draft_text(), '保留用户输入')
            self.assertEqual(d.idea_log.get('1.0', 'end-1c'), before)

    def test_explicit_input_is_not_compared_against_default_example(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            # Even identical user-entered values are real input, not implicit sample data.
            d.idea_template = draft()
            d.idea_input.insert('1.0', draft())
            import writing_api
            expected_config = writing_api.capture_request(d.root)['settings']
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice, \
                    patch('idea_chat.inline_required_missing', wraps=idea_chat.inline_required_missing) as missing:
                d.send_message()
            launch.assert_called_once_with(draft(), config=expected_config)
            notice.assert_not_called()
            self.assertIsNone(missing.call_args.args[0])

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_attachment_without_duration_keeps_inline_gate_closed(self, _local):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            source = Path(td) / '材料.txt'
            source.write_text(draft(dict(VALUES, 单集时间='')), encoding='utf-8')
            stored = archive_idea_attachments(root, [source])
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_attachment_paths = tuple(stored)
            with patch.object(d, 'start_script_workflow') as launch, \
                    patch.object(d, 'open_flow_agent') as extract, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
                extract.assert_not_called()
            launch.assert_not_called()
            self.assertEqual(tuple(d._idea_missing_dialog.brief_fields), ('单集时间',))
            notice.assert_not_called()

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_attachment_aliases_send_unchanged_example_without_prompt(self, _local):
        from stage_execution_service import archive_idea_attachments, stage_idea_brief_defaults
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            source = Path(td) / '材料.txt'
            body = ('故事梗概：修表师寻找失踪的父亲\n主要角色：林青与阿禾\n'
                    '题材类型：冒险喜剧\n篇幅：12集，每集120秒\n画幅：9:16\n'
                    '视频模型版本：MiniMax H3\n交付形态：只要 markdown 文档')
            source.write_text(body, encoding='utf-8')
            stored = archive_idea_attachments(root, [source])
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_attachment_paths = tuple(stored)
            self.assertTrue(d.idea_log.tag_ranges('bubble_example'))
            self.assertEqual(d.draft_text(), '')
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice, \
                    patch('stage_execution_service.stage_idea_brief_defaults',
                          wraps=stage_idea_brief_defaults) as defaults:
                d.send_message()
            notice.assert_not_called()
            launch.assert_called_once()
            defaults.assert_called_once()
            self.assertIn('brief_texts', defaults.call_args.kwargs['reference'])
            submission = launch.call_args.args[0]
            self.assertIn('【附档：01剧本准备/输入/', submission)
            self.assertNotIn(body, submission)
            self.assertNotIn('修表师寻找失踪的父亲', submission)
            self.assertEqual(injected_chat.brief_raw_path(root).read_text(encoding='utf-8'), '')

    def test_readonly_example_and_required_hints_remain_when_typing(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            template = d.idea_example() + '\n模板自带提示：（必填）\n'
            with patch.object(d, 'idea_example', return_value=template):
                d.show(0); self.settle_script_page(win)
            body = d._bubble_full['bubble_example']['text']
            self.assertEqual(body, template)
            self.assertEqual(d.draft_text(), '')
            self.assertEqual(body.count('（必填）'), template.count('（必填）'))
            self.assertFalse(d.idea_input.tag_ranges('required_hint'))
            from ui_tokens import COLORS
            self.assertEqual(d.idea_log.tag_cget('bubble_example', 'foreground'), COLORS['text_secondary'])
            self.assertFalse(hasattr(d, 'idea_brief_editor'))
            d.idea_input.insert('end-1c', '新增'); win.update()
            self.assertEqual(d._bubble_full['bubble_example']['text'], body)
            self.assertFalse(hasattr(d, 'open_brief_creation_form'))

    def test_complete_inline_send_saves_and_starts_without_prompt(self):
        default = Path(__file__).resolve().parents[1] / '默认创意示例.md'
        before = default.read_bytes()
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', draft())
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
            launch.assert_called_once()
            notice.assert_not_called()
            self.assertEqual(injected_chat.brief_raw_path(root).read_text(encoding='utf-8'), draft())
            self.assertFalse(hasattr(d, 'idea_brief_editor'))
            self.assertEqual(d.draft_text(), '')
            self.assertNotIn('已一并提交追问', d.status.get())
        self.assertEqual(default.read_bytes(), before)

    def test_only_input_is_submitted_and_saved(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', draft())
            combined = draft()
            with patch.object(d, 'start_script_workflow', return_value=('Codex', False)) as launch, \
                    patch.object(d.notifier, 'info') as notice:
                d.send_message()
            notice.assert_not_called()
            self.assertEqual(launch.call_args.args[0], combined)
            self.assertNotIn(d.idea_template, launch.call_args.args[0])
            self.assertEqual(injected_chat.brief_raw_path(root).read_text(encoding='utf-8'), combined)
            self.assertEqual(injected_chat.load(root)[0]['text'], combined)
            self.assertEqual(d.draft_text(), '')
            self.assertFalse(hasattr(d, 'idea_brief_editor'))

    def test_launch_failure_preserves_input(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            value = draft() + '\n补充：保持角色动机清晰'
            d.idea_input.insert('1.0', value)
            with patch.object(d, 'start_script_workflow', side_effect=ValueError('启动失败')):
                with self.assertRaisesRegex(ValueError, '启动失败'):
                    d.send_message()
            self.assertEqual(d.draft_text(), value)

    def test_page_rebuild_preserves_input_including_cleared_draft(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', '尚未发送的追问')
            d.show(0); self.settle_script_page(win)
            self.assertTrue(d.idea_log.tag_ranges('bubble_example'))
            self.assertEqual(d.draft_text(), '尚未发送的追问')
            d.idea_input.delete('1.0', 'end')
            d.show(0); self.settle_script_page(win)
            self.assertEqual(d.draft_text(), '')
            self.assertFalse(hasattr(d, 'idea_brief_editor'))

    def test_each_missing_value_notifies_without_starting(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            d, win = self.desktop(root)
            d.show(0); self.settle_script_page(win)
            for label in script_contract.INLINE_REQUIRED_LABELS:
                for value in ('',):
                    with self.subTest(label=label, value=value):
                        text = draft(dict(VALUES, **{label: value}))
                        d.idea_input.delete('1.0', 'end'); d.idea_input.insert('1.0', text)
                        with patch.object(d, 'start_script_workflow') as launch, \
                                patch.object(d.notifier, 'info') as notice:
                            d.send_message()
                        launch.assert_not_called()
                        self.assertEqual(tuple(d._idea_missing_dialog.brief_fields), (label,))
                        notice.assert_not_called()
                        d._idea_missing_dialog.close()
                        self.assertEqual(d.draft_text(), text)
            self.assertFalse(injected_chat.brief_raw_path(root).exists())


if __name__ == '__main__':
    unittest.main()
