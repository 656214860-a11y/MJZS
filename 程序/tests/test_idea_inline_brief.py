"""R1099：内联八项门禁、制作锁别名和项目内覆盖保存。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import idea_chat
import script_contract
from contract.script_contract import PRODUCTION_LOCK_DEFINITIONS
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
            result = injected_chat.receive_brief(root, '【附档：输入/材料.xlsx】',
                inline_text='故事题材：冒险喜剧\n交付形态：markdown文档',
                lock_definitions=PRODUCTION_LOCK_DEFINITIONS, attachment_reference={'brief_texts': [text]})
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
            text = draft().replace('故事画幅:', '画幅:').replace('视频模型:', '视频模型版本:')
            result = injected_chat.receive_brief(root, '【附档：输入/材料.md】',
                inline_text=template, inline_template=template, lock_definitions=PRODUCTION_LOCK_DEFINITIONS,
                attachment_reference={'brief_texts': [text]})
            self.assertEqual(result['missing'], ())
            self.assertEqual(result['fields']['story_summary'], VALUES['故事梗概'])
            self.assertEqual(result['fields']['production_locks']['aspect_ratio'], '9:16')
            self.assertEqual(result['fields']['production_locks']['video_model_version'], 'MiniMax H3')
            changed = template.replace('示例故事梗概', '手写梗概').replace('示例故事画幅', '4:3')
            result = injected_chat.receive_brief(root, '【附档：输入/材料.md】',
                inline_text=changed, inline_template=template, lock_definitions=PRODUCTION_LOCK_DEFINITIONS,
                attachment_reference={'brief_texts': [text]})
            self.assertEqual(result['fields']['story_summary'], '手写梗概')
            self.assertEqual(result['fields']['production_locks']['aspect_ratio'], '4:3')

    def test_non_inline_receive_reads_attachment_lock_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            result = injected_chat.receive_brief(root, '请读取附档\n故事画幅：', lock_definitions=PRODUCTION_LOCK_DEFINITIONS,
                attachment_reference={'brief_texts': [draft()]})
            self.assertEqual(result['fields']['production_locks'],
                             {'aspect_ratio': '9:16', 'video_model_version': 'MiniMax H3',
                              'delivery_format': '只要 markdown 文档'})

    def test_refresh_locks_syncs_attachments_and_returns_project_locks(self):
        # R2862：总控与内联制作锁协调器已删；制作锁改由弹窗预选，入口只读项目锁。
        from skill_panel_workflow import PanelWorkflowMixin
        view = SimpleNamespace(project=lambda: 'unused')
        with patch('stage_execution_service.sync_writing_attachment_locks') as sync, \
                patch('stage_config.workflow_lock', return_value={'aspect_ratio': '9:16'}):
            self.assertEqual(PanelWorkflowMixin.refresh_locks(view), {'aspect_ratio': '9:16'})
        sync.assert_called_once_with('unused')

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
            result = injected_chat.receive_brief(root, draft(), inline_text=draft(),
                                                lock_definitions=PRODUCTION_LOCK_DEFINITIONS)
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


class DefaultExampleGuardTests(unittest.TestCase):
    """随程序的示例文本：开头是技能说明和各把锁的选项；六行锁留空等用户填，故事字段是示例值。

    契约（必填字段、本阶段必填锁、锁的选项）改了而示例没跟着改，这里会红。
    """

    EXAMPLE = Path(__file__).resolve().parents[1] / '默认创意示例.md'
    STAR = '* '  # 必填行的行首标记；解析时会被去掉，不进取值
    CREATED = '2026-11-22'  # 晚于赛道、素材来源的生效日，三把锁都必填
    # 示例里六行锁的行序：锁键 → 示例里写的标签（必须是契约登记的标签或别名）。
    LOCK_LINES = (('material_source', '素材来源'), ('track', '赛道'), ('delivery_format', '交付形态'),
                  ('video_model_version', '视频模型'), ('aspect_ratio', '故事画幅'),
                  ('splice_mode', '段缝衔接方式'))

    def setUp(self):
        self.text = self.EXAMPLE.read_text(encoding='utf-8-sig')
        self.lines = self.text.splitlines()
        self.definitions = {item['key']: item for item in PRODUCTION_LOCK_DEFINITIONS}
        self.example_label = dict(self.LOCK_LINES)
        first = next((index for index, line in enumerate(self.lines)
                      if self._label(line) == self.LOCK_LINES[0][1]), 0)
        # 第一行锁之前是说明段，之后是字段行。
        self.header, self.body = self.lines[:first], self.lines[first:]
        self.required_keys = tuple(script_contract.stage_lock_requirements('script', self.CREATED))
        self.required_locks = tuple(self.definitions[key]['label'] for key in self.required_keys)

    def _label(self, line):
        """顶层字段行的标签（去掉行首必填标记）；缩进行、没有冒号的行返回空串。"""
        if line[:1].isspace() or ':' not in line:
            return ''
        head = line.split(':', 1)[0]
        return head[len(self.STAR):] if head.startswith(self.STAR) else head

    def _missing(self, text):
        """和界面发送时同一种调法：输入已去掉行尾标记，模板参数传 None，script 阶段。"""
        return idea_chat.inline_required_missing(None, idea_chat.strip_inline_required_markers(text),
                                                 stage='script', lock_definitions=PRODUCTION_LOCK_DEFINITIONS,
                                                 created_at=self.CREATED)

    def _value(self, label):
        for line in self.body:
            if self._label(line) == label:
                return line.split(':', 1)[1].strip()
        self.fail('示例里没有「%s:」这一行' % label)

    def _listed_options(self, label):
        """说明段里「<锁名>可选 → 甲 / 乙」那一行列出的选项。"""
        for line in self.header:
            head, arrow, tail = line.strip().partition('→')
            if arrow and head.strip() == label + '可选':
                return [option.strip() for option in tail.split(' / ')]
        self.fail('说明段里没有「%s可选 → …」这一行' % label)

    def _first_choices(self):
        """三把必填锁各取说明段列出的第一个选项：示例里的标签 → 取值。"""
        return {self.example_label[key]: self._listed_options(self.example_label[key])[0]
                for key in self.required_keys}

    def _rewritten(self, values):
        """把指定标签那一行的取值换成给定内容（连同它下面缩进的续行），标签和其余各行原样。"""
        kept, skipping = [], False
        for line in self.lines:
            label = self._label(line)
            if label and label in values:
                kept.append(line.split(':', 1)[0] + ':' + (' ' + values[label] if values[label] else ''))
                skipping = True
                continue
            if skipping and line[:1].isspace():
                continue
            skipping = False
            kept.append(line)
        return '\n'.join(kept)

    def test_example_pasted_unchanged_is_stopped_for_exactly_the_required_locks(self):
        """必填锁留空：原样粘贴发不出去，点名的正好是本阶段必填的锁，故事字段的示例值不被点名。"""
        self.assertEqual(sorted(self._missing(self.text)), sorted(self.required_locks))

    def test_choosing_a_listed_option_for_each_required_lock_passes_the_send_check(self):
        self.assertEqual(self._missing(self._rewritten(self._first_choices())), ())

    def test_each_empty_required_value_is_reported_by_name(self):
        chosen = self._first_choices()
        for key in self.required_keys:
            label = self.definitions[key]['label']
            with self.subTest(lock=label):
                others = {name: value for name, value in chosen.items() if name != self.example_label[key]}
                self.assertEqual(self._missing(self._rewritten(others)), (label,))
        for label in ('故事梗概', '故事集数', '单集时间', '故事题材'):
            with self.subTest(field=label):
                self.assertEqual(self._missing(self._rewritten(dict(chosen, **{label: ''}))), (label,))

    def test_lock_lines_are_blank_and_the_header_lists_registered_options(self):
        self.assertEqual([self._label(line) for line in self.body[:len(self.LOCK_LINES)]],
                         [label for _key, label in self.LOCK_LINES])
        for key, label in self.LOCK_LINES:
            item = self.definitions[key]
            with self.subTest(lock=label):
                self.assertIn(label, (item['label'], *item.get('aliases', ())))
                self.assertEqual(self._value(label), '', '锁行留空，由用户照说明段的选项自己填')
                listed = self._listed_options(label)
                self.assertGreaterEqual(len(listed), 2)
                self.assertEqual([option for option in listed if option not in item['options']], [])

    def test_sent_with_chosen_locks_stores_exactly_those_options(self):
        chosen = self._first_choices()
        sent = idea_chat.strip_inline_required_markers(self._rewritten(chosen))
        with tempfile.TemporaryDirectory() as td:
            root = make_minimal_project(td)
            result = injected_chat.receive_brief(root, sent, inline_text=sent, stage='script',
                                                lock_definitions=PRODUCTION_LOCK_DEFINITIONS,
                                                created_at=self.CREATED)
        self.assertEqual(result['missing'], ())
        locks = result['fields']['production_locks']
        for key in self.required_keys:
            with self.subTest(lock=self.example_label[key]):
                self.assertEqual(locks.get(key), chosen[self.example_label[key]])
                self.assertIn(locks.get(key), self.definitions[key]['options'])

    def test_filling_from_the_missing_items_dialog_lands_on_the_blank_lock_lines(self):
        """缺项弹窗保存时经 fill_idea_brief 调 merge_brief_creation 回填：值落在空着的锁行上，不在文末另起一行。"""
        merged = idea_chat.merge_brief_creation(self.text, self._first_choices())
        self.assertEqual(len(merged.splitlines()), len(self.lines))
        self.assertEqual(self._missing(merged), ())

    def test_required_marks_match_the_contract(self):
        starred = [self._label(line) for line in self.body if line.startswith(self.STAR)]
        self.assertEqual(sorted(starred),
                         sorted((*script_contract.INLINE_REQUIRED_LABELS, *self.required_locks)))
        for label in script_contract.INLINE_REQUIRED_LABELS:
            with self.subTest(field=label):
                self.assertTrue(self._value(label), '必填的故事字段保留示例值，供用户照着改')
        must = [line for line in self.header if '必须写明' in line]
        self.assertEqual(len(must), 1, '说明段要有且只有一行写明本页必须写明的锁')
        for label in self.required_locks:
            self.assertIn(label, must[0])
        self.assertIn('星号', must[0], '说明段要交代行首星号表示必填')
        self.assertEqual(idea_chat.strip_inline_required_markers(self.text), self.text,
                         '一行只用行首星号一种必填标记，不再带行尾的全角标记')
        self.assertNotIn('必填项', self.text, '旧的行尾星号必填项写法会被当成取值的一部分，不再使用')

    def test_theme_line_precedes_genre_so_the_genre_line_wins(self):
        """「故事主题」是「故事题材」的别名，后写的覆盖先写的：题材行排在后面，用户改题材才算数。"""
        labels = [self._label(line) for line in self.body]
        self.assertIn('故事主题', labels)
        self.assertIn('故事题材', labels)
        self.assertLess(labels.index('故事主题'), labels.index('故事题材'))
        self.assertEqual(idea_chat.extract_brief_creation(self.text).get('故事题材'), self._value('故事题材'))

    def test_world_setting_line_sits_after_the_supplement_and_leaks_into_no_other_field(self):
        """「世界设定」不是登记的字段，解析时并进它前面那个字段：放在文末的「内容补充」之后，只并进内容补充。

        放在画风后面会混进画风；放在梗概、题材后面还会把空着的必填项顶住，清空了也不被点名。
        「关键事件」「参考作品」并进故事角色是改前就有的行为，不在这一条里。
        """
        fields = idea_chat.extract_brief_creation(idea_chat.strip_inline_required_markers(self.text))
        for label in ('故事集数', '单集时间', '故事题材', '故事梗概', '故事画风', '特殊要求'):
            with self.subTest(field=label):
                self.assertEqual(fields.get(label), self._value(label), '这个字段的值只能是它自己那一行')
        labels = [label for label in map(self._label, self.body) if label]
        self.assertEqual(labels[-2:], ['内容补充', '世界设定'])
        self.assertEqual(self._value('内容补充'), '', '内容补充留空，由用户自己写')
        self.assertEqual(fields.get('内容补充'), '世界设定: ' + self._value('世界设定'))

    def test_header_is_description_and_adds_no_fields(self):
        self.assertTrue(self.header, '示例开头要有技能说明段')
        self.assertIn('short-drama-director', self.header[0])
        self.assertFalse(self.header[0][:1].isspace())
        self.assertNotRegex(self.header[0], '[:：]')
        self.assertEqual([line for line in self.header[1:] if not line.startswith('  ')], [],
                         '说明段首行之后的行都缩进，才不会被当成字段')
        self.assertNotRegex('\n'.join(self.header), r'[|\t]')
        self.assertEqual([line for line in self.lines if line.startswith('/')], [])
        body_heads = [line.split(':', 1)[0] for line in self.body if line and not line[:1].isspace()]
        self.assertEqual(list(idea_chat.inline_template_labels(self.text)), body_heads)
        lock_labels = tuple(name for item in PRODUCTION_LOCK_DEFINITIONS
                            for name in (item['label'], *item.get('aliases', ())))
        self.assertEqual(idea_chat.extract_brief_creation('\n'.join(self.header), extra_labels=lock_labels,
                                                          include_extra=True), {})


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
            with patch('writing_api.capture_request_model', return_value={'id': 'gpt-4o', 'label': 'gpt-4o', 'model_id': 'test-model', 'record': {'context_length': 1_000_000}}), \
                 patch('writing_api.preparation_continuation', return_value=True) as continuation, \
                 patch.object(d.idea_chat_controller, 'prepare_submission', return_value=prepared), \
                 patch('stage_execution_service.reply_to_writing', return_value=result) as reply, \
                 patch('idea_chat.receive_brief') as receive, \
                 patch('idea_chat.save_brief_creation') as save, \
                 patch.object(d, 'show_missing_idea_brief') as missing, \
                 patch.object(d, 'refresh_script_list') as refresh, \
                 patch.object(d, 'async_', side_effect=finish), \
                 patch('workflow_engines.request_stage_process_slot', return_value={'state': 'granted', 'slot': 'test'}), \
                 patch.object(d, '_idea_live_missing', return_value=()):
                # 发送门禁防抖（R2663）在 send_message 内的 update 里可能落进来，以清空后的草稿
                # 再调一次被 mock 的 preparation_continuation；把门禁缺失判据隔离，本断言只核 send_message 的调用。
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
            with patch('writing_api.capture_request_model', return_value={'id': 'gpt-4o', 'label': 'gpt-4o', 'record': {'context_length': 1_000_000}}), \
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
                # 轮 4 契约：共享输入框空文本 Enter 不派发（send() 直接拒收）；
                # 有内容时 Enter 才进 send_message。
                d.idea_input.event_generate('<Return>'); win.update()
                send.assert_not_called()
                d.idea_input.insert('1.0', '一条创意'); win.update()
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
            # R3060：上传完成的附件以「@原名」行落在输入框顶部，原有文本整体下移保留。
            self.assertEqual(d.draft_text(), '@材料.txt\n保留这条追问\n故事题材：手填题材')
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
