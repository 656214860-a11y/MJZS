# -*- coding: utf-8 -*-
"""创意对话的自检：只把模型的输出存成创意文件。

运行：python test_idea_chat.py

两条线各测各的：idea_chat 那一份只管落盘口径（对话记录、模型输出的创意文件），
界面这一份管接线（提交时确实问了模型、模型不回话时怎么说、手动制作剧本读的是模型写的那一份）。
界面用例跑真 Tk，但工作线程那一步改成当场跑（自检里不真开线程）。
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json, os, queue, sys, tempfile, time, unittest
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_chat as _idea_chat
import script_contract
from stage_execution_service import idea_chat_gateway, publish_idea_creative, project_context
from desktop import Desktop, PAGE
from project_stages import writing as writing_dir
from tests.test_ui_edges import make_minimal_project


class _InjectedIdeaChat:
    """测试也经 L3 网关注入，保留 L2 的“无注入即拒绝”契约。"""
    _gateway_operations = frozenset({
        'append', 'load', 'remove', 'repair_internal_replies', 'replace',
        'restore_latest_removed', 'receive_brief', 'save_brief_creation', 'save_rows',
        'latest_text',
    })
    _operations = frozenset({
        'model_history_path', 'history_path', 'deleted_history_path',
        'brief_raw_path', 'legacy_brief_raw_path', 'brief_complete_path',
        'brief_creation_values', 'initial_brief_document', 'default_brief_document',
        'creative_documents', 'latest_reply', 'save_reply', 'save_manual_creative',
    }) | _gateway_operations

    def __getattr__(self, name):
        value = getattr(_idea_chat, name)
        if name not in self._operations:
            return value
        def invoke(*args, **kwargs):
            if name in self._gateway_operations:
                kwargs.setdefault('gateway', idea_chat_gateway())
            return value(project_context(args[0]), *args[1:], **kwargs)
        return invoke


idea_chat = _InjectedIdeaChat()


class FakeClient:
    """一份假的三虎客户端：只记「问了什么」，回一段固定的话。"""

    def __init__(self, reply='主线：夜班照相馆接到一张旧底片。', ok=True, error='模型超时'):
        self.reply = reply
        self.ok = ok
        self.error = error
        self.calls = []

    def ask(self, task, text, context=None, urgent=False, **kwargs):
        self.calls.append({'task': task, 'text': text, 'urgent': urgent, 'context': context,
                           'model_patch': kwargs.get('model_patch')})
        if not self.ok:
            return {'ok': False, 'error': self.error, 'data': None, 'model': None}
        return {'ok': True, 'error': None, 'model': 'fake',
                'data': {'choices': [{'message': {'content': self.reply}}]}}


class SavingTests(unittest.TestCase):
    """落盘口径：对话记录与模型输出的创意文件。"""

    def test_chat_storage_rejects_an_uninjected_gateway(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(TypeError, 'L3 注入'):
                _idea_chat.append(project_context(td), 'user', '不得绕过网关')

    def test_history_cache_returns_copies_and_invalidates_external_changes(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.save_rows(td, [{'role': 'user', 'text': '初始创意'}], model='测试模型')
            first = idea_chat.load(td, model='测试模型')
            first[0]['text'] = '不得污染缓存'
            self.assertEqual(idea_chat.load(td, model='测试模型')[0]['text'], '初始创意')
            path = idea_chat.model_history_path(td, '测试模型')
            path.write_text(json.dumps({'version': 1, 'messages': [
                {'role': 'user', 'text': '外部更新', 'model': '测试模型'}]}, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(idea_chat.load(td, model='测试模型')[0]['text'], '外部更新')

    def test_initial_brief_document_prefers_latest_categorized_creative_file(self):
        with tempfile.TemporaryDirectory() as td:
            old = writing_dir(td) / '旧创意.md'
            chosen = writing_dir(td) / 'Provider' / 'Model' / '创意_20260927' / '项目大纲' / '新创意.md'
            for path, stamp in ((old, 1000), (chosen, 2000)):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('x', encoding='utf-8')
                os.utime(path, (stamp, stamp))

            self.assertEqual(chosen, idea_chat.initial_brief_document(td))

    def test_initial_brief_document_falls_back_to_legacy_or_default_path(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(writing_dir(td) / '创意与剧本.md', idea_chat.initial_brief_document(td))
            legacy = writing_dir(td) / '旧版创意.md'
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text('x', encoding='utf-8')
            self.assertEqual(legacy, idea_chat.initial_brief_document(td))

    def test_creative_documents_large_project_preserves_order_without_obvious_regression(self):
        with tempfile.TemporaryDirectory() as td:
            base=writing_dir(td) / 'Provider' / 'Model' / '创意_20260929' / '项目大纲'
            expected=[]
            for index in range(240):
                path=base / ('创意_%03d.md' % index)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('x',encoding='utf-8')
                os.utime(path,(1000+index,1000+index))
                expected.append(path)
            started=time.perf_counter()
            discovered=idea_chat.creative_documents(td)
            elapsed=time.perf_counter()-started
            self.assertEqual(tuple(expected),discovered)
            self.assertLess(elapsed,3.0,'240 份创意 Markdown 的发现不应出现秒级明显退化')

    def test_stale_brief_discovery_cannot_override_newer_script_page(self):
        with tempfile.TemporaryDirectory() as td:
            provisional=idea_chat.default_brief_document(td)
            selected=writing_dir(td) / 'Provider' / 'Model' / '创意_20260929' / '项目大纲' / '已保存.md'
            selected.parent.mkdir(parents=True,exist_ok=True)
            selected.write_text('x',encoding='utf-8')

            class InputBox:
                def winfo_exists(self): return True

            class View:
                root=td
                page_index=PAGE['script']
                _idea_brief_generation=0
                shutting_down=False
                worker=False
                def __init__(self):
                    self.brief_editor=(provisional,InputBox())
                    self._brief_load_results=queue.Queue()

            view=View()
            Desktop.queue_initial_brief_document(view,view.brief_editor[1],provisional)
            self.assertFalse(view.worker, '首帧只读发现不得占用用户操作门禁')
            _generation,_root,deliver,found,_error=view._brief_load_results.get(timeout=2)
            view._idea_brief_generation+=1  # 新页面已建立，旧页面回调随后才抵达。
            deliver(found)
            self.assertEqual((provisional,view.brief_editor[1]),view.brief_editor)

    def test_initial_brief_discovery_failure_is_visible_without_blocking_input(self):
        """首帧后台发现创意文档失败不能伪装成“没有示例”。"""
        with tempfile.TemporaryDirectory() as td:
            class InputBox:
                def winfo_exists(self): return True

            class View:
                root=td
                page_index=PAGE['script']
                _idea_brief_generation=0
                shutting_down=False
                _async_ticket=0
                worker=False
                def __init__(self):
                    self.brief_editor=(idea_chat.default_brief_document(td),InputBox())
                    self._brief_load_results=queue.Queue()
                    self.q=queue.Queue()
                    self.status=SimpleNamespace(value='',set=lambda value:setattr(self.status,'value',value))

            view=View()
            with patch('idea_chat.initial_brief_document',side_effect=OSError('创意目录不可读')):
                Desktop.queue_initial_brief_document(view,view.brief_editor[1],view.brief_editor[0])
                Desktop._tick_async_result(view)
            self.assertIn('创意历史未加载',view.status.value)

    def test_only_the_model_output_lands_in_the_creative_file(self):
        with tempfile.TemporaryDirectory() as td:
            writing_dir(td).mkdir(parents=True, exist_ok=True)
            reply = idea_chat.save_reply(td, '  模型写的纲要：第一集从旧底片开始。  ', publish=publish_idea_creative)
            self.assertEqual(reply.read_text(encoding='utf-8'), '模型写的纲要：第一集从旧底片开始。')
            self.assertEqual(reply.parent.name, '项目大纲')
            self.assertEqual(reply.parent.parent.name[:3], '创意_')
            self.assertEqual(reply.parent.parent.parent.name, '未知模型')
            self.assertEqual(reply.parent.parent.parent.parent.name, '未知Provider')
            self.assertEqual(reply.parent.parent.parent.parent.parent, writing_dir(td))
            self.assertEqual({path.name for path in reply.parent.parent.iterdir() if path.is_dir()},
                             {'项目设定', '项目大纲', '项目剧本'})
            self.assertEqual(idea_chat.latest_reply(td), reply)
            with self.assertRaises(ValueError):
                idea_chat.save_reply(td, '   ')

    def test_manual_creative_uses_the_same_categorized_atomic_publication(self):
        with tempfile.TemporaryDirectory() as td:
            target = idea_chat.save_manual_creative(td, '阿远：我回来了', at=0, publish=publish_idea_creative)
            self.assertEqual(target.read_text(encoding='utf-8'), '阿远：我回来了')
            self.assertEqual(target.parent.name, '项目剧本')
            self.assertEqual(target.parent.parent.name, '创意_19700101')
            self.assertEqual(target.name,
                             script_contract.stage_file_name(td, '自然剧本', '手动创意', at=0))

    def test_creative_publication_requires_an_injected_l3_publisher(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(TypeError, 'L3'):
                idea_chat.save_manual_creative(td, '阿远：我回来了', at=0)
            with self.assertRaisesRegex(TypeError, 'L3'):
                idea_chat.save_reply(td, '项目剧本：模型回复', at=0)

    def test_saved_creative_files_use_project_name_day_and_sequence_not_time(self):
        with tempfile.TemporaryDirectory() as td:
            reply = idea_chat.save_reply(td, '项目剧本：模型回复', at=0, publish=publish_idea_creative)
            self.assertEqual(reply.parent.parent.name, '创意_19700101')
            self.assertEqual(reply.parent.name, '项目剧本')
            self.assertEqual(reply.name,
                             script_contract.stage_file_name(td, '自然剧本', '模型输出', at=0))

    def test_saved_script_name_uses_project_content_and_day(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'episode').mkdir()
            (root / 'episode' / 'episode.json').write_text(
                json.dumps({'title': '摄像头3', 'episode_id': 'EP008'}, ensure_ascii=False), encoding='utf-8')
            reply = idea_chat.save_reply(root, '项目剧本：模型回复', at=0, publish=publish_idea_creative)
            self.assertEqual(reply.name, root.name + '_自然剧本_模型输出_19700101.md')

    def test_saved_reply_uses_provider_and_model_subdirectories(self):
        with tempfile.TemporaryDirectory() as td:
            reply = idea_chat.save_reply(td, '项目剧本：模型回复', at=0,
                                         provider='DeepSeek', model='DeepSeek V4 Flash', publish=publish_idea_creative)
            self.assertEqual(reply.parent.parent.parent.name, 'DeepSeek V4 Flash')
            self.assertEqual(reply.parent.parent.parent.parent.name, 'DeepSeek')
            self.assertEqual(idea_chat.storage_identity('DeepSeek V4 Flash'),
                             ('DeepSeek', 'DeepSeek V4 Flash'))

    def test_non_project_model_reply_is_not_saved_as_a_project_file(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, '不是项目设定、大纲或剧本'):
                idea_chat.save_reply(td, '你好，我正在思考。', publish=publish_idea_creative)

    def test_brief_intake_writes_raw_then_complete_only_after_required_fields(self):
        with tempfile.TemporaryDirectory() as td:
            first = idea_chat.receive_brief(td, '故事梗概：夜班照相馆收到一张会显影未来的旧底片。')
            self.assertTrue(first['raw_path'].is_file())
            self.assertEqual(first['missing'], ('main_characters', 'genre', 'length'))
            self.assertIn('主要角色、题材类型、篇幅', first['followup'])
            self.assertFalse(idea_chat.brief_complete_path(td).exists())
            done = idea_chat.receive_brief(
                td, '主要角色：少年摄影师林默，长发女孩阿青\n题材类型：都市悬疑\n篇幅：24集')
            self.assertEqual(done['missing'], ())
            self.assertTrue(done['complete_path'].is_file())
            data = json.loads(done['complete_path'].read_text(encoding='utf-8'))
            self.assertEqual(data['brief']['genre'], '都市悬疑')
            self.assertEqual(data['brief']['length'], '24集')
            self.assertIn('physical_features', data['recommended_missing'])

    def test_production_locks_are_recommended_not_a_brief_send_blocker(self):
        with tempfile.TemporaryDirectory() as td:
            result = idea_chat.receive_brief(
                td,
                '故事梗概：夜班照相馆收到一张会显影未来的旧底片。\n'
                '主要角色：摄影师林默与阿青\n题材类型：都市悬疑\n篇幅：24集',
                workflow={'name': 'AIGC全流程', 'skill_ref': 'skills/AIGC/SKILL.md', 'lock': {}},
                lock_definitions=({'key': 'aspect_ratio', 'label': '画幅', 'options': ('9:16',)},),
            )
            self.assertEqual(result['missing'], ())
            self.assertTrue(result['complete_path'].is_file())
            self.assertIn('production_locks', result['complete_path'].read_text(encoding='utf-8'))
            self.assertEqual(result['workflow_projection']['lock']['AIGC全流程'], {})
            self.assertNotIn('制作锁', result['followup'])

    def test_brief_creation_form_and_direct_input_share_one_file(self):
        with tempfile.TemporaryDirectory() as td:
            saved, text = idea_chat.save_brief_creation(td, {
                '故事集数': '24集', '单集时间': '90秒', '故事画风': '都市写实',
                '故事主体': '夜班照相馆', '故事梗概': '旧底片会显影未来。',
                '故事题材': '都市悬疑', '故事角色': '摄影师林默与阿青',
                '物理特征': '林默短发，阿青长发', '故事分集': '第1集发现底片',
                '特殊要求': '结尾留悬念', '内容补充': '无',
            })
            self.assertEqual(saved.name, 'brief_creation.md')
            self.assertIn('故事梗概：旧底片会显影未来。', text)
            remembered = idea_chat.brief_creation_values(td)
            self.assertEqual(remembered['故事角色'], '摄影师林默与阿青')
            result = idea_chat.receive_brief(td, '内容补充：增加雨夜氛围')
            self.assertEqual(result['raw_path'], saved)
            self.assertTrue(saved.is_file())
            self.assertIn('增加雨夜氛围', saved.read_text(encoding='utf-8'))

    def test_brief_followup_does_not_repeat_provided_fields(self):
        fields = {'story_summary': '一个完整故事', 'main_characters': '阿青', 'genre': '', 'length': ''}
        question = idea_chat.brief_followup(fields)
        self.assertIn('题材类型、篇幅', question)
        self.assertNotIn('故事梗概', question)
        self.assertNotIn('主要角色', question)

    def test_brief_intake_reuses_user_chat_history_from_other_model(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '故事梗概：夜班照相馆收到能显影未来的旧底片。\n主要角色：摄影师林默与阿青\n题材类型：都市悬疑\n篇幅：24集', model='DeepSeek V4 Flash')
            idea_chat.append(td, 'assistant', '虚构的主要角色：不应被当作用户设定。', model='DeepSeek V4 Flash')
            done = idea_chat.receive_brief(td, '请输出第6集到第10集的剧本')
            self.assertEqual(done['missing'], ())
            self.assertEqual(done['fields']['main_characters'], '摄影师林默与阿青')
            self.assertEqual(done['fields']['genre'], '都市悬疑')

    def test_the_conversation_round_trips_and_feeds_the_next_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '一个夜班照相馆')
            idea_chat.append(td, 'assistant', '主线：旧底片', model='DeepSeek Chat')
            rows = idea_chat.load(td)
            self.assertEqual([row['role'] for row in rows], ['user', 'assistant'])
            self.assertEqual(rows[-1]['model'], 'DeepSeek Chat')
            self.assertTrue(all(row.get('at') for row in rows))
            prompt = idea_chat.prompt_for('再加一个人物', rows)
            self.assertIn('用户：一个夜班照相馆', prompt)
            self.assertIn('模型：主线：旧底片', prompt)
            self.assertIn('（本次提交的创意）', prompt)
            self.assertIn('再加一个人物', prompt)
            self.assertEqual([line.split('：')[0] for line in idea_chat.history_text(rows).splitlines()],
                             ['用户', '模型'], '一轮一句，前缀各一个')

    def test_switching_models_keeps_separate_persistent_conversations(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '旧模型的创意', model='DeepSeek V4 Flash')
            idea_chat.append(td, 'assistant', '旧模型的回复', model='DeepSeek V4 Flash')
            idea_chat.append(td, 'user', 'Claude 的创意', model='Claude Opus')
            self.assertEqual([row['text'] for row in idea_chat.load(td, model='Claude Opus')],
                             ['Claude 的创意'])
            self.assertEqual([row['text'] for row in idea_chat.load(td, model='DeepSeek V4 Flash')],
                             ['旧模型的创意', '旧模型的回复'])

    def test_model_history_is_stored_under_its_provider_and_imports_legacy_rows(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '旧位置的 DeepSeek 创意', model='DeepSeek V4 Flash')
            path = idea_chat.model_history_path(td, 'DeepSeek V4 Flash')
            self.assertTrue(path.is_file())
            self.assertIn('DeepSeek', path.parts)
            self.assertIn('DeepSeek V4 Flash', path.parts)
            legacy = idea_chat.history_path(td)
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(json.dumps({'messages': [
                {'role': 'user', 'text': '旧统一记录', 'model': 'Claude Opus', 'at': 'x'}
            ]}, ensure_ascii=False), encoding='utf-8')
            self.assertEqual([row['text'] for row in idea_chat.load(td, model='Claude Opus')], ['旧统一记录'])
            self.assertTrue(idea_chat.model_history_path(td, 'Claude Opus').is_file())

    def test_legacy_rows_do_not_mix_into_a_model_partition(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '旧格式记录')
            idea_chat.append(td, 'assistant', 'Claude 的独立记录', model='Claude Opus')
            self.assertEqual(idea_chat.load(td, model='Claude Opus')[-1]['text'], 'Claude 的独立记录')
            self.assertEqual(idea_chat.load(td, model='DeepSeek V4 Flash'), [])
            idea_chat.replace(td, 0, '已修改的 Claude 创意', model='Claude Opus')
            self.assertEqual([row['text'] for row in idea_chat.load(td, model='Claude Opus')],
                             ['已修改的 Claude 创意'])

    def test_a_saved_message_can_be_edited_or_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '原始创意')
            idea_chat.append(td, 'assistant', '原始回复')
            idea_chat.replace(td, 0, '修改后的创意')
            self.assertEqual(idea_chat.load(td)[0]['text'], '修改后的创意')
            idea_chat.remove(td, 1)
            self.assertEqual([row['text'] for row in idea_chat.load(td)], ['修改后的创意'])
            with self.assertRaises(ValueError):
                idea_chat.replace(td, 0, '   ')

    def test_deleted_message_can_be_restored_to_its_original_position(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '第一条')
            idea_chat.append(td, 'assistant', '第二条')
            idea_chat.append(td, 'user', '第三条')
            idea_chat.remove(td, 1)
            self.assertEqual([row['text'] for row in idea_chat.load(td)], ['第一条', '第三条'])
            restored = idea_chat.restore_latest_removed(td)
            self.assertEqual(restored['text'], '第二条')
            self.assertEqual([row['text'] for row in idea_chat.load(td)],
                             ['第一条', '第二条', '第三条'])
            with self.assertRaisesRegex(ValueError, '没有可恢复'):
                idea_chat.restore_latest_removed(td)

    def test_a_broken_history_file_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = idea_chat.history_path(td)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{不是 JSON', encoding='utf-8')
            self.assertEqual(idea_chat.load(td), [])

    def test_reply_text_reads_both_wire_shapes(self):
        chat = {'data': {'choices': [{'message': {'content': '甲'}}]}}
        responses = {'data': {'output_text': '乙'}}
        claude = {'data': {'content': [
            {'type': 'thinking', 'thinking': 'internal'},
            {'type': 'text', 'text': '丙'},
        ]}}
        thinking_only = {'data': {'content': [{'type': 'thinking', 'thinking': 'internal'}]}}
        self.assertEqual(idea_chat.reply_text(chat), '甲')
        self.assertEqual(idea_chat.reply_text(responses), '乙')
        self.assertEqual(idea_chat.reply_text(claude), '丙')
        self.assertEqual(idea_chat.reply_text(thinking_only), '')
        self.assertEqual(idea_chat.reply_text({'data': None}), '')
        self.assertEqual(idea_chat.reply_text({}), '')


class ScriptShapeTests(unittest.TestCase):
    """第 65 期任务 9／10：像不像剧本、取哪一段、空回复怎么说。"""

    def test_only_a_long_text_with_script_marks_counts_as_a_script(self):
        self.assertFalse(idea_chat.looks_like_script('场景 1 只有开头'))
        self.assertFalse(idea_chat.looks_like_script('场景 ' + '补' * 400), '只有一个要素不算')
        self.assertFalse(idea_chat.looks_like_script('场景 镜头 ' + '补' * 200), '太短也不算')
        self.assertTrue(idea_chat.looks_like_script('场景 1 开场\n镜头 2 特写\n台词：你好\n' + '补' * 400))

    def test_latest_text_takes_the_last_reply(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(idea_chat.latest_text(td), '')
            idea_chat.append(td, 'user', '写个剧本')
            idea_chat.append(td, 'assistant', '第一稿')
            idea_chat.append(td, 'user', '再改改')
            self.assertEqual(idea_chat.latest_text(td), '第一稿')

    def test_a_truncated_reply_explains_itself(self):
        cut = {'ok': True, 'data': {'choices': [{'finish_reason': 'length'}]}}
        self.assertIn('额度', idea_chat.why_empty(cut))
        self.assertIn('模型超时', idea_chat.why_empty({'ok': False, 'error': '模型超时'}))
        self.assertIn('空回复', idea_chat.why_empty({}))


class _Harness(unittest.TestCase):
    """建一个真 Desktop（Tk），不让它去挑项目。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def desktop(self, proj):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, 'choose_project', original)
        win = self.tk.Tk()
        win.withdraw()
        self.addCleanup(self._quiet, win)
        from desktop import Desktop
        from local_video import open_studio
        d = Desktop(win, root=HERE)
        d.root = proj
        d.studio = open_studio(proj)
        return d, win

    @staticmethod
    def _quiet(win):
        try:
            win.destroy()
        except Exception:
            pass

    def sync_async(self, d):
        """工作线程那一步改成当场跑；返回收集出错的那张表（界面那一趟不抛异常）。"""
        errors = []

        def run(fn, done=None, show_progress=True):
            try:
                value = fn()
            except Exception as exc:
                errors.append(str(exc))
                return
            if done is not None:
                done(value)

        d.async_ = run
        return errors

    @staticmethod
    def settle_script_page(win, seconds=.18):
        """首帧后的聊天模型/气泡采用后台与空闲分片，等到首批提交。"""
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            win.update()
            time.sleep(.01)
        win.update()

    def log_text(self, d):
        return str(d.idea_log.get('1.0', 'end-1c'))

    def bubbles(self, d):
        """创意框里那几条正文气泡：[(对齐, 正文)]。"""
        box = d.idea_log
        rows = []
        for name in box.tag_names():
            if not __import__('re').fullmatch(r'bubble_\d+', name):
                continue
            spans = box.tag_ranges(name)
            for index in range(0, len(spans), 2):
                rows.append((str(box.tag_cget(name, 'justify')),
                             str(box.get(spans[index], spans[index + 1])).strip()))
        return rows


class SendMessageTests(_Harness):
    """第 65 期任务 9＋第 69 期任务 1：内容框里写 → 发送 → 气泡按时间往下排；落盘只在定稿那一步。"""

    def say(self, d, text):
        box = d.idea_input
        box.configure(fg='#243247')
        box.delete('1.0', 'end'); box.insert('1.0', text)

    def test_sending_starts_the_selected_workflow_without_creating_a_script_file(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            seen = []
            d.open_flow_agent = lambda *args, **kwargs: seen.append((args, kwargs))
            self.say(d, '故事梗概：一个夜班照相馆的故事\n主要角色：摄影师林默\n题材类型：都市悬疑\n篇幅：12集')
            d.send_message(); win.update()
            self.assertEqual(len(seen), 1)
            args, _ = seen[0]
            self.assertEqual(args[:2], ('writing', '剧本准备'))
            self.assertIn('一个夜班照相馆的故事', args[2])
            self.assertIn('必须先完整遵循本次工作流所选 SKILL', args[2])
            self.assertIn('禁止擅自直接返回剧本、大纲或分镜方案', args[2])
            self.assertFalse(list((writing_dir(proj) / '创意对话').glob('提交_*.md')),
                             '发送创意不能先创建提交文件')
            self.assertEqual(d.draft_text().strip(), '', '发出去之后下面那段草稿就空了')
            self.assertIn(('left', '故事梗概：一个夜班照相馆的故事\n主要角色：摄影师林默\n题材类型：都市悬疑\n篇幅：12集'), self.bubbles(d),
                          '用户气泡贴右侧，但正文从气泡左边开始')
            self.assertEqual([row['role'] for row in idea_chat.load(proj)], ['user'])
            self.assertFalse(list(writing_dir(proj).glob('创意_*/*.md')),
                             '工作流未完成前不把创意伪装成模型剧本')

    def test_incomplete_brief_asks_only_missing_fields_without_starting_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            seen = []
            d.open_flow_agent = lambda *args, **kwargs: seen.append(args)
            self.say(d, '故事梗概：夜班照相馆收到一张会显影未来的旧底片。')
            d.send_message(); win.update()
            self.assertEqual(seen, [])
            self.assertTrue(idea_chat.brief_raw_path(proj).is_file())
            self.assertFalse(idea_chat.brief_complete_path(proj).exists())
            messages = idea_chat.load(proj)
            self.assertEqual(messages[-1]['role'], 'assistant')
            self.assertIn('主要角色、题材类型、篇幅', messages[-1]['text'])
            self.assertEqual(d.idea_row.winfo_manager(), 'pack', '启动工作流后发送框仍固定显示')

    def test_the_composer_expands_for_content_and_enter_sends(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            self.assertEqual(int(d.idea_input.cget('height')), 1, '空输入框保持紧凑')
            d.idea_input.insert('1.0', '第一行创意\n第二行创意\n第三行创意')
            win.update(); d._fit_composer(); win.update()
            self.assertGreaterEqual(int(d.idea_input.cget('height')), 3, '输入框自动显示完整多行文字')
            sent = []
            d.send_message = lambda: sent.append(True)
            d.idea_input.focus_force(); win.update()
            d.idea_input.event_generate('<KeyPress-Return>'); win.update()
            self.assertEqual(sent, [True], 'Enter 直接发送；不需要点击按钮')

    def test_clicking_empty_composer_keeps_a_single_stable_height(self):
        """空输入框点击只聚焦，不能触发输入/聊天/画布的 Configure 重绘回路。"""
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); win.update()
            d.idea_input.event_generate('<Button-1>')
            heights=[]
            for _ in range(6):
                win.update_idletasks(); win.update()
                heights.append(int(d.idea_input.cget('height')))
            self.assertEqual(heights[0], 1)
            self.assertEqual(len(set(heights)), 1,
                             '空输入框点击后必须保持一行，不能随对话区压缩来回变化')

    def test_narrow_composer_keeps_the_attachment_button_visible(self):
        """缩窄窗口时先保留右侧附件入口，输入框使用剩余宽度。"""
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            win.geometry('360x760+40+40')
            d.show(0); win.update_idletasks(); win.update()
            row=d.idea_input.master
            button=d.idea_attachment_button
            self.assertTrue(button.winfo_ismapped(), '缩窄窗口后附件图标仍须可见')
            self.assertGreater(button.winfo_width(), 0, '附件图标必须保留实际宽度')
            self.assertLess(d.idea_input.winfo_width(), row.winfo_width(),
                            '窄窗口应缩短输入框，为附件图标留出空间')
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),
                                 row.winfo_rootx()+row.winfo_width()+1,
                                 '附件图标不得被挤出输入行右侧')

    def test_clicking_the_composer_hint_focuses_the_real_input_and_hides_the_static_hint(self):
        """覆盖输入框的静态提示不能吞掉点击。"""
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); win.update()
            self.assertTrue(d.idea_input_hint.place_info(), '空输入框时提示应已显示')
            d.idea_input_hint.event_generate('<Button-1>'); win.update()
            self.assertEqual(int(d.idea_input.cget('height')), 1, '点击提示只应聚焦，不能扩大空输入框')
            self.assertFalse(d.idea_input_hint.place_info(), '取得焦点后必须撤掉提示层')

    def test_composer_right_click_only_offers_paste_for_text_clipboard(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); win.update()
            event = SimpleNamespace(widget=d.idea_input, x_root=1, y_root=1)
            with patch('desktop.tk.Menu') as menu:
                d.idea_input.clipboard_clear()
                self.assertEqual(d.open_idea_paste_menu(event), 'break')
                menu.assert_not_called()
                d.idea_input.clipboard_append('可粘贴的创意')
                self.assertEqual(d.open_idea_paste_menu(event), 'break')
                menu.assert_called_once_with(d.idea_input, tearoff=False)
                self.assertEqual(menu.return_value.add_command.call_args.kwargs['label'], '粘贴')

    def test_unsent_composer_text_survives_leaving_and_returning_to_the_page(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            draft = '先保留这段没有发送的创意\n回到剧本准备页后还要继续写'
            d.idea_input.insert('1.0', draft); win.update()
            d.show(1); win.update()
            d.show(0); win.update()
            self.assertEqual(d.draft_text(), draft, '切换页面不会丢失尚未发送的输入')

    def test_empty_script_list_gives_the_chat_area_the_page_space(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertFalse(d.script_box.winfo_ismapped(), '没有剧本文件时不显示空白文件表')
            self.assertTrue(d.idea_log.winfo_ismapped(), '聊天记录保留并接管可用空间')

    def test_stage_settings_is_immediately_to_the_right_of_send(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertIs(d.stage_button.master, d.idea_row)
            self.assertEqual(d.stage_button.winfo_manager(), 'place')
            self.assertGreaterEqual(d.stage_button.winfo_x(),
                                    d.idea_send.winfo_x()+d.idea_send.winfo_width(),
                                    '阶段配置紧随发送按钮右侧')

    def test_script_interrupt_is_next_to_stage_settings_and_releases_direct_chat(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertGreaterEqual(d.idea_interrupt.winfo_x(),
                                    d.stage_button.winfo_x()+d.stage_button.winfo_width(),
                                    '中断按钮位于阶段配置右侧')
            self.assertEqual(d.idea_interrupt.cget('text'), '中断')
            d._idea_requesting = True; d.worker = True
            d.update_script_interrupt_button(); win.update()
            self.assertFalse(d.idea_interrupt.instate(['disabled']))
            self.assertTrue(d.interrupt_script_agent())
            self.assertFalse(d._idea_requesting)
            self.assertFalse(d.worker)
            self.assertTrue(d.idea_interrupt.instate(['disabled']))

    def test_refresh_is_next_to_interrupt_and_repairs_old_claude_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            model = d.idea_chat_model()
            idea_chat.append(proj, 'user', '请写第一集', model=model)
            idea_chat.append(proj, 'assistant', "[{'type': 'thinking', 'thinking': 'internal'}, {'type': 'text', 'text': '第一集正文'}]", model=model)
            d.show(0); win.update()
            self.assertGreaterEqual(d.idea_refresh.winfo_x(),
                                    d.idea_interrupt.winfo_x()+d.idea_interrupt.winfo_width())
            self.assertTrue(d.refresh_script_workspace())
            self.assertEqual(idea_chat.latest_text(proj), '第一集正文')

    def test_download_is_immediately_left_of_open_script_folder(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertEqual(d.idea_download.winfo_manager(), 'place')
            self.assertEqual(d.idea_open_folder.winfo_manager(), 'place')
            download = (d.idea_download.winfo_x(), d.idea_download.winfo_y(),
                        d.idea_download.winfo_width(), d.idea_download.winfo_height())
            folder = (d.idea_open_folder.winfo_x(), d.idea_open_folder.winfo_y(),
                      d.idea_open_folder.winfo_width(), d.idea_open_folder.winfo_height())
            overlap = (download[0] < folder[0] + folder[2] and folder[0] < download[0] + download[2]
                       and download[1] < folder[1] + folder[3] and folder[1] < download[1] + download[3])
            self.assertFalse(overlap, '下载剧本与剧本目录在窄窗口换行时也不能互相遮挡')
            self.assertEqual(d.idea_open_folder.cget('text'), '剧本目录')

    def test_script_action_bar_uses_compact_renamed_buttons(self):
        import desktop
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            buttons = [child for child in d.idea_row.winfo_children()
                       if isinstance(child, ttk.Button)]
            action_labels = {'发送', '中断', '刷新', '下载剧本', '剧本目录', '删除剧本', '添加剧本'}
            labels = {button.cget('text') for button in buttons}
            self.assertTrue({'中断', '剧本目录', '删除剧本', '添加剧本'} <= labels)
            for button in buttons:
                if button.cget('text') in action_labels:
                    self.assertEqual(button.cget('width'), desktop.STAGE_ACTION_WIDTH)

    def test_script_action_bar_wraps_instead_of_clipping_buttons_when_narrow(self):
        """剧本页缩窄时操作栏分行，不能把“删除剧本”挤成半个字。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            win.geometry('520x760+40+40')
            d.show(0); win.update_idletasks(); win.update()
            buttons = [child for child in d.idea_row.winfo_children()
                       if isinstance(child, ttk.Button)]
            self.assertEqual(d.idea_row.winfo_class(), 'TFrame')
            self.assertTrue(all(button.winfo_manager() == 'place' for button in buttons))
            self.assertTrue(all(button.winfo_width() >= min(button.winfo_reqwidth(),
                                                             d.idea_row.winfo_width())
                                for button in buttons))

    def test_the_composer_remains_visible_after_script_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            d.close_dialog(); win.update()
            self.assertEqual(d.idea_row.winfo_manager(), 'pack', '保存剧本也不隐藏发送框')
            self.assertEqual(d.idea_input.cget('state'), 'normal')

    def test_the_example_is_never_sent(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            self.assertEqual(d.idea_input.get('1.0', 'end-1c'), '', '发送框保持空白，范例不冒充用户输入')
            self.assertIn('模型 · 软件示例', self.log_text(d), '范例显示在上方对话区')
            self.assertIn(d.idea_example(), self.log_text(d))
            d.send_message(); win.update()
            self.assertTrue(d._brief_creation_window.winfo_exists(), '空白创意应打开填写表格')
            self.assertEqual(idea_chat.load(proj), [], '一个字都不许发出去')
            self.assertFalse(idea_chat.brief_raw_path(proj).exists(), '只打开表格不应先落盘')

    def test_software_example_can_be_copied_as_a_whole_message(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); win.update()
            self.assertEqual(d.copy_bubble_message('example'), d.idea_example())
            self.assertEqual(win.clipboard_get(), d.idea_example())
            span=d.idea_log.tag_ranges('bubble_example')
            x, y, _, _ = d.idea_log.bbox(span[0])
            target = d.bubble_target_at(d.idea_log, SimpleNamespace(x=x + 1, y=y + 1))
            self.assertEqual(target[0], 'example', '软件示例气泡必须可被右键命中')

    def test_text_attachment_is_visible_and_submitted_to_the_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            source = Path(td) / '角色设定.md'
            source.write_text('主要角色：林默\n题材类型：都市悬疑\n篇幅：12集', encoding='utf-8')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            with patch('ui_dialogs.filedialog.askopenfilenames', return_value=(str(source),)):
                selected=d.choose_idea_attachments()
            self.assertEqual(selected, ())
            deadline=time.monotonic()+2
            while not d.idea_attachment_paths and time.monotonic()<deadline:
                d.poll_idea_attachment_preparation()
                win.update()
                time.sleep(0.01)
            self.assertEqual(len(d.idea_attachment_paths), 1)
            self.assertTrue(Path(d.idea_attachment_paths[0]).is_file())
            self.assertEqual(Path(d.idea_attachment_paths[0]).parent.name, '输入')
            self.assertEqual(d.idea_attachment_button.cget('text'), '📁')
            self.assertIn('已引用：故事创意_', d.idea_attachment_status.get())
            seen=[]
            d.open_flow_agent=lambda *args, **kwargs: seen.append(args)
            self.say(d, '请基于附档创作')
            d.send_message(); win.update()
            self.assertIn('【附档：故事创意_', seen[0][2])
            self.assertIn('主要角色：林默', seen[0][2])
            self.assertEqual(d.idea_attachment_paths, ())
            self.assertIn('【已引用：故事创意_', idea_chat.load(proj)[0]['text'])

    def test_a_failed_workflow_keeps_the_draft_without_creating_a_submission(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            d.open_flow_agent = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('工作流没有启动'))
            self.say(d, '故事梗概：一个夜班照相馆的故事\n主要角色：摄影师林默\n题材类型：都市悬疑\n篇幅：12集')
            with self.assertRaisesRegex(ValueError, '工作流没有启动'):
                d.send_message()
            self.assertEqual(d.idea_input.get('1.0', 'end-1c'), '故事梗概：一个夜班照相馆的故事\n主要角色：摄影师林默\n题材类型：都市悬疑\n篇幅：12集')
            self.assertFalse(list((writing_dir(proj) / '创意对话').glob('提交_*.md')),
                             '启动失败也不能留下未获模型回复的剧本文档')

    def test_direct_model_failure_ends_an_active_script_stage(self):
        """直接 API 调用失败不能只留在状态栏，自动链必须收到 script 失败事件。"""
        import stage_config
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            emitted = []
            d.pet.auto.active = 'script'
            d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
            def immediate(fn, done=None, **_ignored):
                if done is not None:
                    done(fn())
            d.async_ = immediate
            self.say(d, '故事梗概：雨夜照相馆收到会显影未来的旧底片。\n主要角色：摄影师林默和阿青。\n题材类型：都市悬疑\n篇幅：12集')
            with patch('writing_api.reply', return_value={'ok':False, 'error':'模型未生成导演正文'}):
                d.send_message()
            self.assertEqual(emitted, [('stage.failed', {
                'stage':'script', 'error':'模型调用未完成：模型未生成导演正文'})])

    def test_the_dialogue_box_shows_what_is_already_on_disk(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '先前的创意')
            idea_chat.append(proj, 'assistant', '先前的纲要')
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            self.assertIn(('left', '先前的创意'), self.bubbles(d))
            self.assertIn(('left', '先前的纲要'), self.bubbles(d))


class AgentProcessLifecycleTests(_Harness):
    """桌面 Agent 的异常退出不能让三虎自动链永久停在制作中。"""

    def test_failed_agent_exit_ends_matching_automatic_stage_and_cleans_session(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            emitted = []
            d.pet.auto.active = 'script'
            d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))

            class ExitedProcess:
                def poll(self):
                    return 2

            key = (str(proj), 'writing', 'codex', 'test')
            d.flow_processes = {key: ExitedProcess()}
            d.poll_flow_processes()
            self.assertEqual(d.flow_processes, {})
            self.assertEqual(emitted, [('stage.failed', {
                'stage': 'script',
                'error': 'writing Agent 已异常退出（退出码 2），未确认产出；请检查 Agent 窗口或重试。'
            })])

    def test_normal_agent_exit_only_cleans_session_without_advancing_or_failing(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            emitted = []
            d.pet.auto.active = 'script'
            d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))

            class ExitedProcess:
                def poll(self):
                    return 0

            d.flow_processes = {(str(proj), 'writing', 'codex', 'test'): ExitedProcess()}
            d.poll_flow_processes()
            self.assertEqual(d.flow_processes, {})
            self.assertEqual(emitted, [])

    def test_normal_writing_agent_exit_completes_only_after_natural_script_is_saved(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            writing = writing_dir(proj)
            writing.mkdir(exist_ok=True)
            (writing / 'script_raw.md').write_text('# 自然剧本\n正文', encoding='utf-8')
            d, win = self.desktop(proj)
            emitted = []
            d.pet.auto.active = 'script'
            d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))

            class ExitedProcess:
                def poll(self):
                    return 0

            d.flow_processes = {(str(proj), 'writing', 'codex', 'test'): ExitedProcess()}
            d.poll_flow_processes()
            self.assertEqual(d.flow_processes, {})
            self.assertEqual([kind for kind, _payload in emitted],
                             ['script.completed', 'stage.completed'])


class ScriptHandoffTests(_Harness):
    """剧本入口只交给 Agent 工作流，不再使用模型聊天回话作输入。"""

    def test_legacy_script_entry_sends_the_user_creative_to_the_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            seen = []
            d.open_flow_agent = lambda *args, **kwargs: seen.append(args)
            d.open_codex_skill(None, d.brief_editor[0], '用户没提交过的草稿')
            self.assertEqual(len(seen), 1)
            prompt = str(seen[0][2])
            self.assertIn('用户没提交过的草稿', prompt)
            self.assertIn('尚未保存为剧本文件', prompt)
            self.assertFalse(list((writing_dir(proj) / '创意对话').glob('提交_*.md')))

    def test_legacy_script_entry_does_not_save_the_box_as_a_submission(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            seen = []
            d.open_flow_agent = lambda *args, **kwargs: seen.append(args)
            d.open_codex_skill(None, d.brief_editor[0], '手写的创意')
            self.assertIn('手写的创意', str(seen[0][2]))
            self.assertFalse(list((writing_dir(proj) / '创意对话').glob('提交_*.md')))



class ProjectRemovalWarningTests(_Harness):
    """最后剧本的删除确认必须是红色破坏性提示，默认不删除。"""

    def test_last_script_removal_uses_red_explicit_confirmation(self):
        import desktop as desktop_module
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            _d, win = self.desktop(proj)
            found = []; colors = []
            def click_cancel():
                def walk(widget):
                    if 'text' in widget.keys() and str(widget.cget('text')) == '取消':
                        found.append(widget)
                        colors.append(widget.master.master.master.cget('bg'))
                        widget.invoke();return True
                    return any(walk(child) for child in widget.winfo_children())
                walk(win)
            win.after(30, click_cancel)
            self.assertFalse(desktop_module.confirm_project_removal_from_last_script(win, ['最后一份.md']))
            self.assertEqual(len(found), 1)
            self.assertEqual(colors, ['#c62828'])


class BubbleLayoutTests(_Harness):
    """第 73 期任务 11：微信式左右消息、紧凑、可折叠，模型回复状态清楚。"""

    def test_a_short_message_gets_a_narrower_bubble(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            box = d.idea_log
            short = d.bubble_margins(box, '嗯', True)
            long = d.bubble_margins(box, '这一段话长得多，长到几乎占满一整行，气泡自然就更宽一些', True)
            self.assertGreater(short[0], long[0], '短的用户气泡左侧留白更多——气泡贴着字长')

    def test_user_bubbles_are_right_and_model_bubbles_are_left(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            box = d.idea_log
            left, right = d.bubble_margins(box, '同样一句话', False)
            mine_left, mine_right = d.bubble_margins(box, '同样一句话', True)
            self.assertGreater(mine_left, left, '用户消息贴在右侧')
            self.assertGreater(right, mine_right, '模型消息贴在左侧')

    def test_user_bubble_uses_a_readable_light_green_surface(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '这条由用户发送')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertEqual(d.idea_log.tag_cget('bubble_0', 'background'), '#dff5e3')
            self.assertEqual(d.idea_log.tag_cget('bubble_0', 'foreground'), '#243247')

    def test_model_chat_color_is_stable_and_distinguishes_common_models(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            self.assertEqual(d.model_chat_colors('Claude Opus'), d.model_chat_colors('Claude Opus'))
            self.assertNotEqual(d.model_chat_colors('Claude Opus'), d.model_chat_colors('DeepSeek V4 Flash'))

    def test_message_actions_are_bound_to_the_bubble_not_drawn_below_it(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '可以直接修改我')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertNotIn('编辑  删除', self.log_text(d), '消息下方不再显示编辑／删除文字')
            binding=lambda event: d.idea_log.tk.call(d.idea_log._w, 'tag', 'bind', 'bubble_0', event)
            self.assertTrue(binding('<Button-1>'), '单击消息正文编辑')
            self.assertTrue(d.idea_log.bind('<Button-3>'), '右键应打开整条消息操作菜单')

    def test_single_click_edits_or_deletes_the_message_in_place(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '原始创意')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            event = SimpleNamespace(widget=d.idea_log, x=8, y=8)
            d.start_bubble_edit(event, 0, 'bubble_0'); win.update()
            edit = d._bubble_edit
            self.assertEqual(d.idea_log.tag_cget('bubble_0', 'background'), '#dff5e3')
            self.assertEqual(d.idea_log.cget('selectbackground'), '#3564a8')
            self.assertEqual(d.idea_log.cget('selectforeground'), '#ffffff')
            d.idea_log.tag_add('sel', '%s+1c' % edit['start'], '%s+3c' % edit['start'])
            self.assertEqual(d.idea_log.get('sel.first', 'sel.last'), '始创')
            d.idea_log.delete(edit['start'], edit['end'])
            d.idea_log.insert(edit['start'], '直接修改后的创意')
            d.finish_bubble_edit(); win.update()
            self.assertEqual(idea_chat.load(proj)[0]['text'], '直接修改后的创意')
            d.start_bubble_edit(event, 0, 'bubble_0'); win.update()
            edit = d._bubble_edit
            d.idea_log.delete(edit['start'], edit['end'])
            d.finish_bubble_edit(); win.update()
            self.assertEqual(idea_chat.load(proj), [], '删空消息正文即删除该条，不弹确认窗口')

    def test_dragging_a_bubble_keeps_text_selection_instead_of_entering_edit(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '可以复制的正文')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            click = SimpleNamespace(widget=d.idea_log, x=8, y=8)
            d.begin_bubble_click(click, 0, 'bubble_0')
            d.finish_bubble_click(click); win.update()
            self.assertEqual(d._bubble_edit['index'], 0, '短按正文进入编辑')
            d.begin_bubble_click(click, 0, 'bubble_0')
            d.finish_bubble_click(click); win.update()
            self.assertEqual(d._bubble_edit['index'], 0, '编辑中再次单击不能重建气泡，保留原生选字')
            d.finish_bubble_edit(commit=False); win.update()
            d.begin_bubble_click(click, 0, 'bubble_0')
            d.track_bubble_click(SimpleNamespace(widget=d.idea_log, x=16, y=8))
            d.finish_bubble_click(click); win.update()
            self.assertIsNone(getattr(d, '_bubble_edit', None), '拖动选字不能误进入编辑')
            self.assertEqual(str(d.idea_log.cget('state')), 'normal', '聊天记录必须保持可拖选')
            self.assertEqual(d.idea_log.cget('selectbackground'), '#3564a8')
            self.assertEqual(d.idea_log.cget('inactiveselectbackground'), '#3564a8')
            self.assertEqual(d.guard_bubble_edit_key(SimpleNamespace(
                widget=d.idea_log, keysym='a')), 'break', '未进入编辑时不可改动聊天记录')
            for keysym in ('Down', 'Prior', 'Up', 'Next', 'Home', 'End', 'Tab', 'ISO_Left_Tab'):
                self.assertIsNone(d.guard_bubble_edit_key(SimpleNamespace(
                    widget=d.idea_log, keysym=keysym)), keysym + ' 应保留只读聊天框的阅读导航')

    def test_editing_cannot_cross_a_bubble_body_and_selection_can_be_copied(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            model = d.idea_chat_model()
            idea_chat.append(proj, 'assistant', '长内容' * 250, model=model)
            d.show(0); win.update()
            event = SimpleNamespace(widget=d.idea_log, x=8, y=8)
            d.start_bubble_edit(event, 0, 'bubble_0'); win.update()
            edit = d._bubble_edit
            d.idea_log.mark_set('insert', edit['start'])
            self.assertEqual(d.guard_bubble_edit_key(SimpleNamespace(
                widget=d.idea_log, keysym='BackSpace')), 'break')
            d.idea_log.mark_set('insert', edit['end'])
            self.assertEqual(d.guard_bubble_edit_key(SimpleNamespace(
                widget=d.idea_log, keysym='Delete')), 'break')
            self.assertIn('模型 · ' + model, self.log_text(d))
            self.assertIn('展开全文', self.log_text(d))
            d.finish_bubble_edit(commit=False); win.update()
            body = d.idea_log.tag_ranges('bubble_0')
            d.idea_log.tag_add('sel', body[0], body[1])
            self.assertEqual(d.idea_log.cget('selectbackground'), '#3564a8')
            self.assertEqual(d.idea_log.cget('selectforeground'), '#ffffff')
            d.notice_selected_bubble_text(SimpleNamespace(widget=d.idea_log))
            self.assertIn('按 Ctrl+C 复制', d.status.get())
            self.assertEqual(d.copy_selected_bubble_text(), 'break')
            self.assertIn('长内容', win.clipboard_get())

    def test_right_click_actions_copy_or_delete_the_entire_message(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '完整的一条消息')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertEqual(d.copy_bubble_message(0), '完整的一条消息')
            self.assertEqual(win.clipboard_get(), '完整的一条消息')
            self.assertEqual(d.delete_bubble_message(0), 0)
            self.assertEqual(idea_chat.load(proj), [])

    def test_a_very_long_message_stops_short_of_the_whole_box(self):
        """第 71 期任务 6：字再多，色块也不铺满整行——一行到底就看不下去了。"""
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            box = d.idea_log
            import desktop as desktop_module
            width = max(240, int(box.winfo_width() or 0))
            left, right = d.bubble_margins(box, '很长很长的一句话' * 60, True)
            body = width - left - right
            self.assertGreater(body, 0)
            self.assertLessEqual(body, max(desktop_module.BUBBLE_FLOOR,
                                           int(width * desktop_module.BUBBLE_MAX_RATIO)) + 1,
                                 '色块封顶在可读的那一档')
            short = d.bubble_margins(box, '嗯', True)
            self.assertGreater(short[0], left, '短的用户气泡依旧留白更多')

    def test_dialog_has_a_right_side_scrollbar(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertEqual(d.idea_scroll.winfo_manager(), 'pack')
            self.assertTrue(d.idea_log.cget('yscrollcommand'), '对话内容框应连接右侧滚动条')

    def test_long_message_is_collapsed_and_can_expand(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            idea_chat.append(proj, 'assistant', '长内容' * 250, model=d.idea_chat_model())
            d.show(0); win.update()
            self.assertIn('展开全文', self.log_text(d))
            self.assertEqual(d.idea_log.tag_cget('bubble_0_toggle', 'justify'), 'right',
                             '展开控件固定在本条消息的右侧，并随消息一起滚动')
            d.toggle_bubble(d.idea_log, 'bubble_0'); win.update()
            self.assertIn('收起', self.log_text(d))
            self.assertIn('长内容' * 250, self.log_text(d))

    def test_thinking_notice_is_transient_and_names_the_model(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '请帮我构思')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            d.show_thinking('DeepSeek Chat'); win.update()
            self.assertIn('DeepSeek Chat 模型正在思考…', self.log_text(d))
            d.clear_thinking(); win.update()
            self.assertNotIn('模型正在思考…', self.log_text(d))

    def test_only_what_you_type_below_the_line_gets_sent(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '先前的创意')
            idea_chat.append(proj, 'assistant', '先前的纲要')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            self.assertEqual(d.draft_text(), '', '上面那些气泡不算您在写的字')
            d.idea_input.insert('end', '再补一句')
            win.update()
            self.assertEqual(d.draft_text().strip(), '再补一句', '下面这一段才是要发出去的')
            self.assertIn('先前的创意', self.log_text(d), '气泡一条都没少')


class ComposerLayoutTests(_Harness):
    """第 74 期任务 13：发送入口唯一，输入框固定在聊天记录下方。"""

    def test_composer_is_a_separate_widget_below_the_selectable_readonly_chat_log(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); win.update()
            self.assertIsNot(d.idea_input, d.idea_log)
            self.assertEqual(d.idea_log.cget('state'), 'normal', '聊天记录须保持正常状态以支持鼠标拖选')
            self.assertEqual(d.guard_bubble_edit_key(SimpleNamespace(
                widget=d.idea_log, keysym='a')), 'break', '正常状态仍须由只读保护阻止键盘改写')
            self.assertEqual(d.idea_input.cget('state'), 'normal')
            self.assertGreater(d.idea_input.winfo_rooty(), d.idea_log.winfo_rooty(),
                               '输入框固定在可滚动聊天记录下方')

    def test_script_page_does_not_render_a_second_manual_agent_button(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); win.update()
            pending = list(d.content.winfo_children())
            labels = []
            while pending:
                widget = pending.pop()
                pending.extend(widget.winfo_children())
                try: labels.append(str(widget.cget('text')))
                except Exception: pass
            self.assertNotIn('手动制作剧本', labels)
            self.assertEqual(d.idea_send.cget('text'), '发送')


if __name__ == '__main__':
    unittest.main(verbosity=2)
