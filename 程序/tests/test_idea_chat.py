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
from unittest.mock import Mock, patch
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
        'latest_text', 'compact_context', 'remove_all',
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
    def test_model_rename_keeps_history_and_deleted_message_identity(self):
        import model_pool
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            records = model_pool.default_pool()
            with patch('model_pool.pool', return_value=records):
                old_label = records['gpt-4o']['label']
                idea_chat.append(proj, 'assistant', '改名前的正文', model=old_label)
                original = idea_chat.model_history_path(proj, old_label)
                idea_chat.remove(proj, 0, model=old_label)
                records['gpt-4o']['label'] = '我的新名字'
                self.assertEqual(idea_chat.model_history_path(proj, '我的新名字'), original)
                idea_chat.restore_latest_removed(proj, model='我的新名字')
                self.assertEqual(idea_chat.load(proj, model='我的新名字')[0]['text'], '改名前的正文')
                idea_chat.append(proj, 'user', '改名后的正文', model='我的新名字')
                self.assertEqual(len(idea_chat.load(proj, model='gpt-4o')), 2)

    def test_legacy_display_folder_migrates_history_and_recycle_bin_once(self):
        import model_pool
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            identity = idea_chat.chat_model('gpt-4o')
            old = idea_chat.model_history_path(td, str(identity), provider=identity.provider)
            old.parent.mkdir(parents=True)
            row = {'role': 'user', 'text': '旧消息', 'model': str(identity), 'at': 'x'}
            old.write_text(json.dumps({'messages': [row]}), encoding='utf-8')
            old.with_name('已删除消息.json').write_text(json.dumps({'messages': [
                {'model': str(identity), 'index': 1, 'row': dict(row, text='已删消息')}
            ]}), encoding='utf-8')
            self.assertEqual(len(idea_chat.load(td, model=identity)), 1)
            idea_chat.restore_latest_removed(td, model=identity)
            self.assertEqual([r['text'] for r in idea_chat.load(td, model=identity)], ['旧消息', '已删消息'])
            idea_chat.remove_all(td, model=identity)
            self.assertEqual(idea_chat.load(td, model=identity), [])
            self.assertEqual(json.loads(old.read_text(encoding='utf-8'))['messages'], [])

    def test_rename_before_first_read_preserves_legacy_folder_lookup(self):
        import model_pool
        with tempfile.TemporaryDirectory() as td:
            records = model_pool.default_pool()
            old = records['gpt-4o']
            path = idea_chat.model_history_path(td, old['label'], provider=model_pool.provider_name('gpt-4o', old))
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'messages': [{'role': 'user', 'text': '尚未迁移', 'model': old['label']}]}), encoding='utf-8')
            changed = model_pool.upsert({'models': records}, dict(old, label='新名称'), 'gpt-4o')
            with patch('model_pool.pool', return_value=changed['models']):
                self.assertEqual([r['text'] for r in idea_chat.load(td, model='gpt-4o')], ['尚未迁移'])

    def test_ambiguous_legacy_folder_is_not_assigned_to_either_model(self):
        import model_pool
        with tempfile.TemporaryDirectory() as td:
            records = {'first': dict(model='first', label='同名', provider='GPT'),
                       'second': dict(model='second', label='同名', provider='GPT')}
            old = idea_chat.model_history_path(td, '同名', provider='GPT')
            old.parent.mkdir(parents=True)
            content = json.dumps({'messages': [{'role': 'user', 'text': '旧记录', 'model': '同名'}]})
            old.write_text(content, encoding='utf-8')
            with patch('model_pool.pool', return_value=records):
                with self.assertRaisesRegex(ValueError, '无法确定'):
                    idea_chat.load(td, model='first')
            self.assertEqual(old.read_text(encoding='utf-8'), content)

    def download_page(self, root, model):
        page = SimpleNamespace(
            idea_chat_context=lambda: project_context(root),
            idea_chat_gateway=idea_chat_gateway, idea_chat_model=lambda: model,
            idea_download=Mock(), close_dialog=Mock(), status=Mock(), pet=Mock())
        page.update_script_download_button = lambda: Desktop.update_script_download_button(page)
        page.displayed_chat_model = lambda: Desktop.displayed_chat_model(page)
        return page

    def test_download_uses_current_model_latest_reply_and_identity(self):
        with tempfile.TemporaryDirectory() as td, patch(
                'idea_chat.storage_identity', side_effect=lambda label: (label.lower(), label)) as identity:
            first = '# 自然剧本\n场景 1：雨夜\n台词：旧稿。\n' + '旧稿' * 200
            other = '# 自然剧本\n场景 1：晴天\n台词：其他模型。\n' + '其他' * 200
            latest = '# 自然剧本\n场景 1：雨夜\n台词：最新稿。\n' + '新稿' * 200
            idea_chat.append(td, 'assistant', first, model='DeepSeek')
            idea_chat.append(td, 'assistant', other, model='GPT')
            idea_chat.append(td, 'assistant', latest, model='DeepSeek')
            page = self.download_page(td, 'DeepSeek')
            self.assertTrue(page.update_script_download_button())
            saved = Desktop.download_script(page)
            self.assertEqual(saved.read_text(encoding='utf-8').strip(), latest)
            self.assertIn('deepseek', saved.name.lower())
            self.assertEqual(Desktop.download_script(page), saved)
            self.assertEqual(identity.call_args.args, ('DeepSeek',))

    def test_download_cannot_borrow_another_model_reply(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'assistant', '# 自然剧本\n场景 1\n台词：你好\n' + '正文' * 200,
                             model='GPT')
            page = self.download_page(td, 'DeepSeek')
            self.assertFalse(page.update_script_download_button())
            with self.assertRaisesRegex(ValueError, '请先让模型生成完整剧本'):
                Desktop.download_script(page)

    def test_compact_context_keeps_original_and_new_messages_across_reload(self):
        with tempfile.TemporaryDirectory() as td:
            original = '世界观：雨城。' + '旧讨论细节' * 1500
            idea_chat.append(td, 'user', original, model='模型甲')
            idea_chat.append(td, 'user', '其他模型完整消息', model='模型乙')
            before = idea_chat.load(td, model='模型甲')
            idea_chat.compact_context(td, model='模型甲')
            _idea_chat._history_cache.clear()
            rows = idea_chat.load(td, model='模型甲')
            self.assertEqual(rows[0]['text'], original)
            self.assertEqual(rows[0]['at'], before[0]['at'])
            self.assertTrue(rows[0]['context_compacted'])
            context = idea_chat.history_context(rows)
            self.assertIn('世界观：雨城', context)
            self.assertLess(len(context), 1801)
            self.assertNotIn('context_compacted', idea_chat.load(td, model='模型乙')[0])
            idea_chat.append(td, 'user', '清屏后的新要求：主角保留底片', model='模型甲')
            self.assertIn('清屏后的新要求：主角保留底片',
                          idea_chat.history_context(idea_chat.load(td, model='模型甲')))
            idea_chat.compact_context(td, model='模型甲')
            self.assertTrue(all(row['context_compacted'] for row in idea_chat.load(td, model='模型甲')))
            idea_chat.replace(td, 0, '修订后的设定应完整进入上下文', model='模型甲')
            self.assertNotIn('context_compacted', idea_chat.load(td, model='模型甲')[0])

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
                             {'项目设定', '项目大纲', '角色卡', '项目剧本'})
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

    def test_review_drafts_overwrite_in_place_while_natural_script_keeps_versions(self):
        with tempfile.TemporaryDirectory() as td:
            options = dict(at=0, provider='DeepSeek', model='DeepSeek V4 Flash', publish=publish_idea_creative)
            first = idea_chat.save_reply(td, '# 项目设定\n第一版', **options)
            stamp = first.stat().st_mtime_ns
            again = idea_chat.save_reply(td, '# 项目设定\r\n第一版\n', **options)
            self.assertEqual(first, again)
            self.assertEqual(first.stat().st_mtime_ns, stamp)
            second = idea_chat.save_reply(td, '# 项目设定\n第二版', **options)
            third = idea_chat.save_reply(td, '# 项目设定\n第三版', **options)
            self.assertEqual(first.name, Path(td).name + '_项目设定_DeepSeek_19700101.md')
            # 前三项审阅参考放弃历史版本：同一路径覆盖，不再追加 (N) 序号。
            self.assertEqual(second, first)
            self.assertEqual(third, first)
            self.assertEqual(first.read_text(encoding='utf-8').strip(), '# 项目设定\n第三版')
            # 同一正文复用不重写，正文改变则覆盖为最新一版。
            self.assertEqual(idea_chat.save_reply(td, '# 项目设定\n第二版', **options), first)
            self.assertEqual(first.read_text(encoding='utf-8').strip(), '# 项目设定\n第二版')
            # 自然剧本是唯一正式交付，仍保留版本：异稿追加 (N)，不覆盖。
            script = idea_chat.save_reply(td, '第1集\n场景：夜 外街道\n阿明：开始。', **options)
            script_v2 = idea_chat.save_reply(td, '第1集\n场景：夜 外街道\n阿明：开始。\n阿明：继续。', **options)
            self.assertNotEqual(script, script_v2)
            self.assertIn('(1)', script_v2.name)

    def test_review_draft_overwrite_spans_creative_batches(self):
        with tempfile.TemporaryDirectory() as td:
            options = dict(provider='DeepSeek', model='DeepSeek V4 Flash', publish=publish_idea_creative)
            first = idea_chat.save_reply(td, '# 项目设定\n第一版', at=0, **options)
            second = idea_chat.save_reply(td, '# 项目设定\n第二版', at=86400, **options)
            # 跨天续改仍覆盖同一份，不落到新批次产生副本。
            self.assertEqual(second, first)
            self.assertIn('创意_19700101', second.as_posix())
            self.assertEqual(second.read_text(encoding='utf-8').strip(), '# 项目设定\n第二版')
            self.assertFalse((second.parents[2] / '创意_19700102').exists())

    def test_download_reuses_auto_saved_setting_with_outline_reference_and_preserves_full_text(self):
        from stage_execution_service import publish_stage_text
        with tempfile.TemporaryDirectory() as td:
            context = project_context(td)
            value = '# 项目设定\n后续项目大纲按此设定。\n' + '设定正文' * 6000 + '\n待确认'
            path = _idea_chat.reply_document_path(context, value, at=0, model='DeepSeek', file_type='项目设定')
            publish_stage_text(path, value + '\n', lambda content: bool(content), lambda _path: None)
            stamp = path.stat().st_mtime_ns
            saved = idea_chat.save_reply(td, value, at=0, model='DeepSeek', publish=publish_idea_creative)
            self.assertEqual(saved, path)
            self.assertEqual(saved.stat().st_mtime_ns, stamp)
            self.assertEqual(saved.read_text(encoding='utf-8').strip(), value)
            changed = idea_chat.save_reply(td, value + '。', at=0, model='DeepSeek', publish=publish_idea_creative)
            self.assertEqual(changed.read_text(encoding='utf-8'), value + '。')

    def test_non_project_model_reply_is_not_saved_as_a_project_file(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, '不是项目设定、大纲或剧本'):
                idea_chat.save_reply(td, '你好，我正在思考。', publish=publish_idea_creative)

    def test_brief_intake_writes_raw_then_complete_only_after_required_fields(self):
        with tempfile.TemporaryDirectory() as td:
            first = idea_chat.receive_brief(td, '故事梗概：夜班照相馆收到一张会显影未来的旧底片。')
            self.assertTrue(first['raw_path'].is_file())
            self.assertEqual(first['missing'], ('main_characters', 'genre', 'length', 'delivery_format'))
            self.assertIn('主要角色、题材类型、篇幅', first['followup'])
            self.assertFalse(idea_chat.brief_complete_path(td).exists())
            done = idea_chat.receive_brief(
                td, '主要角色：少年摄影师林默，长发女孩阿青\n题材类型：都市悬疑\n篇幅：24集\n交付形态：markdown')
            self.assertEqual(done['missing'], ())
            self.assertTrue(done['complete_path'].is_file())
            data = json.loads(done['complete_path'].read_text(encoding='utf-8'))
            self.assertEqual(data['brief']['genre'], '都市悬疑')
            self.assertEqual(data['brief']['length'], '24集')
            self.assertIn('physical_features', data['recommended_missing'])

    def test_production_locks_are_advisory_outside_lock_stages(self):
        with tempfile.TemporaryDirectory() as td:
            result = idea_chat.receive_brief(
                td,
                '故事梗概：夜班照相馆收到一张会显影未来的旧底片。\n'
                '主要角色：摄影师林默与阿青\n题材类型：都市悬疑\n篇幅：24集',
                workflow={'name': 'AIGC全流程', 'skill_ref': 'skills/AIGC/SKILL.md', 'lock': {}}, stage='audio',
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

    def test_brief_form_empty_and_multiline_fields_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.save_brief_creation(td, {'故事梗概': '第一行\n第二行', '故事角色': '阿青'})
            values = idea_chat.brief_creation_values(td)
            self.assertNotIn('故事主体', values)
            self.assertEqual(values['故事梗概'], '第一行\n第二行')
            values = idea_chat.brief_creation_values(td, '故事角色：\n特殊要求：不要旁白')
            self.assertEqual(values['故事角色'], '')
            self.assertEqual(values['特殊要求'], '不要旁白')

    def test_brief_attachment_defaults_preserve_explicit_empty_and_manual_values(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.save_brief_creation(td, {'故事角色': '手填角色'})
            values = idea_chat.brief_creation_values(td, attachment_values={
                '故事角色': '附档角色', '故事梗概': '附档梗概'})
            self.assertEqual(values['故事角色'], '手填角色')
            self.assertEqual(values['故事梗概'], '')

    def test_brief_multiline_dialogue_does_not_become_a_field(self):
        text = '故事梗概：夜幕降临\n阿青：谁在那里？\n灯突然亮了\n故事角色：阿青\n画幅：16:9'
        fields = idea_chat.extract_brief_creation(text, extra_labels=('画幅',))
        self.assertEqual(fields['故事梗概'], '夜幕降临\n阿青：谁在那里？\n灯突然亮了')
        self.assertEqual(fields['故事角色'], '阿青')

    def test_archived_attachment_populates_brief_without_changing_local_delivery(self):
        from stage_execution_service import archive_idea_attachments, stage_idea_brief_defaults, stage_idea_attachment_reference
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / '创意.txt'
            source.write_text('故事集数：12集\n故事梗概：第一行\n第二行\n主要角色：阿青\n题材类型：悬疑', encoding='utf-8')
            with patch('stage_execution_service.idea_attachment_local_mode', return_value=True):
                archive_idea_attachments(td, (source,))
                result = stage_idea_brief_defaults(td)
                self.assertEqual(result['values']['故事角色'], '阿青')
                self.assertEqual(result['values']['故事梗概'], '第一行\n第二行')
                self.assertEqual(result['values']['故事集数'], '12集')
                self.assertEqual(result['values']['故事题材'], '悬疑')
                self.assertNotIn('第一行', stage_idea_attachment_reference(td)['context'])
                source.unlink()
                self.assertEqual(stage_idea_brief_defaults(td)['values'], result['values'])

    def test_brief_followup_does_not_repeat_provided_fields(self):
        fields = {'story_summary': '一个完整故事', 'main_characters': '阿青', 'genre': '', 'length': ''}
        question = idea_chat.brief_followup(fields)
        self.assertIn('题材类型、篇幅', question)
        self.assertNotIn('故事梗概', question)
        self.assertNotIn('主要角色', question)

    def test_brief_label_values_are_missing_instead_of_placeholder_content(self):
        for value in ('故事角色', '角色', '故事集数：单集时间：', '故事角色故事题材'):
            with self.subTest(value=value):
                self.assertEqual(idea_chat._brief_value('故事梗概：' + value, ('故事梗概',)), '')
        fields = idea_chat._brief_fields('故事梗概：故事主体\n故事角色：角色\n故事题材：题材\n篇幅：故事集数：单集时间：')
        for field in ('story_summary', 'main_characters', 'genre', 'length'):
            self.assertEqual(fields[field], '')

    def test_brief_intake_reuses_user_chat_history_from_other_model(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '故事梗概：夜班照相馆收到能显影未来的旧底片。\n主要角色：摄影师林默与阿青\n题材类型：都市悬疑\n篇幅：24集', model='DeepSeek V4 Flash')
            idea_chat.append(td, 'assistant', '虚构的主要角色：不应被当作用户设定。', model='DeepSeek V4 Flash')
            done = idea_chat.receive_brief(td, '请输出第6集到第10集的剧本\n交付形态：markdown')
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

    def test_model_history_is_stored_by_stable_id_and_imports_legacy_rows(self):
        with tempfile.TemporaryDirectory() as td:
            idea_chat.append(td, 'user', '旧位置的 DeepSeek 创意', model='DeepSeek V4 Flash')
            path = idea_chat.model_history_path(td, 'DeepSeek V4 Flash')
            self.assertTrue(path.is_file())
            self.assertIn('模型会话', path.parts)
            self.assertTrue(path.parent.parent.name.startswith('deepseek-v4-flash--'))
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
        import stage_config
        if not stage_config.path(proj).exists():
            stage_config.put(proj, 'script', skills=['pipeline-script-preparation'])
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

    def test_missing_selected_skill_keeps_draft_and_does_not_start_request(self):
        import stage_config
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            project = make_minimal_project(td)
            d, win = self.desktop(project)
            d.show(0); self.settle_script_page(win)
            self.say(d, self.complete_draft())
            save(stage_config.path(project), {'script': {'model': 'gpt-4o', 'skills': ['missing-skill']}})
            with patch.object(d, 'submit_idea_api_request') as api, patch.object(d, 'open_flow_agent') as agent:
                with self.assertRaisesRegex(ValueError, '已勾选的 SKILL 未加载'):
                    d.send_message()
            api.assert_not_called()
            agent.assert_not_called()
            self.assertEqual(d.draft_text(), self.complete_draft())
            self.assertEqual(idea_chat.load(project), [])

    @staticmethod
    def complete_draft(summary='一个夜班照相馆的故事'):
        return ('故事梗概：' + summary + '\n故事角色：摄影师林默\n故事题材：都市悬疑\n'
                '故事集数：12集\n单集时间：120秒\n故事画幅：9:16\n'
                '视频模型：MiniMax H3\n交付形态：只要 markdown 文档')

    def test_sending_starts_the_selected_workflow_without_creating_a_script_file(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            seen = []
            d.open_flow_agent = lambda *args, **kwargs: seen.append((args, kwargs))
            self.say(d, self.complete_draft())
            d.send_message(); win.update()
            self.assertEqual(len(seen), 1)
            args, _ = seen[0]
            self.assertEqual(args[:2], ('writing', '剧本准备'))
            self.assertIn('一个夜班照相馆的故事', args[2])
            self.assertIn('必须先完整遵循本次工作流所选 SKILL', args[2])
            self.assertIn('按①项目设定 → ②剧本大纲 → ③角色卡 → ④自然剧本逐阶段输出', args[2])
            self.assertIn('前提齐全时本次只输出阶段①项目设定，末尾“待确认”', args[2])
            self.assertIn('每个关键阶段都必须用户确认，不能自动跳到下一阶段', args[2])
            self.assertIn('每次只输出当前阶段一个文件，不一次输出多阶段', args[2])
            self.assertFalse(list((writing_dir(proj) / '创意对话').glob('提交_*.md')),
                             '发送创意不能先创建提交文件')
            self.assertEqual(d.draft_text().strip(), '', '发出去之后下面那段草稿就空了')
            self.assertIn(('left', self.complete_draft()), self.bubbles(d),
                          '用户气泡贴右侧，但正文从气泡左边开始')
            self.assertEqual([row['role'] for row in idea_chat.load(proj)], ['user'])
            self.assertEqual(len(idea_chat.load(proj)[0]['skill_injection']['loaded']), 1)
            self.assertIn('本次已加载 1 项', self.log_text(d))
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
            with patch.object(d.notifier, 'info') as notice:
                d.send_message(); win.update()
            self.assertEqual(seen, [])
            self.assertFalse(idea_chat.brief_raw_path(proj).is_file())
            self.assertFalse(idea_chat.brief_complete_path(proj).exists())
            messages = idea_chat.load(proj)
            self.assertEqual(messages, [])
            self.assertEqual(tuple(d._idea_missing_dialog.brief_fields), ('故事题材', '故事角色', '故事集数', '单集时间', '交付形态'))
            notice.assert_not_called()
            self.assertEqual(d.idea_row.winfo_manager(), 'pack', '启动工作流后发送框仍固定显示')

    def test_the_composer_expands_for_content_and_enter_sends(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            d.idea_input.delete('1.0', 'end'); win.update(); d._fit_composer()
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
            d.idea_input.delete('1.0', 'end'); win.update()
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
            d.idea_input.delete('1.0', 'end'); win.update()
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
            d.idea_input.delete('1.0', 'end')
            d.idea_input.insert('1.0', draft); win.update()
            d.show(1); win.update()
            d.show(0); win.update()
            self.assertEqual(d.draft_text(), draft, '切换页面不会丢失尚未发送的输入')

    def test_empty_script_list_keeps_category_headers_and_chat_visible(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            win.deiconify()
            self.settle_script_page(win, .4)
            self.assertTrue(d.script_box.winfo_ismapped(), '没有文件也保留分类标题栏')
            for category, title in (('setting', '项目设定'), ('outline', '项目大纲'),
                                    ('character', '角色卡'), ('script', '项目剧本')):
                tree = d.script_trees[category]
                self.assertEqual(tree.heading('name')['text'], title)
                self.assertTrue(tree.winfo_ismapped())
                self.assertFalse(tree._data_table.empty_label.winfo_ismapped(), '空态不能遮住标题栏')
                self.assertEqual(tree.get_children(), ())
            self.assertTrue(d.idea_log.winfo_ismapped(), '聊天记录仍保留可用空间')

    def test_delayed_script_rows_are_not_covered_by_empty_state(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            path = writing_dir(proj) / 'GPT' / 'Codex' / '创意_20261007' / '项目剧本' / '前10集剧本.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('第1集\n场景 1：室内\n小明：开始。', encoding='utf-8')
            d, win = self.desktop(proj)
            d.show(0); win.deiconify()
            self.settle_script_page(win, .4)
            tree = d.script_trees['script']
            self.assertIn(str(path), tree.get_children())
            self.assertFalse(tree._data_table.empty_label.winfo_ismapped(), '延迟填表后不能仍显示暂无数据')

    def test_refresh_script_workspace_shows_agent_internal_draft(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.deiconify()
            self.settle_script_page(win, .4)
            path = writing_dir(proj) / script_contract.RAW_SCRIPT_NAME
            path.write_text('\n'.join('## 第%d集\n场景 1：室内\n小明：开始。' % n for n in range(1, 11)), encoding='utf-8')
            self.assertTrue(d.refresh_script_workspace())
            self.settle_script_page(win, .4)
            tree = d.script_trees['script']
            self.assertIn(str(path), tree.get_children())
            self.assertIn('内部工作稿', tree.item(str(path), 'values')[0])
            self.assertFalse(tree._data_table.empty_label.winfo_ismapped())

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
            action_labels = {'发送', '中断', '刷新', '下载文件', '下载设定', '下载大纲', '下载角色卡', '下载剧本', '剧本目录', '删除剧本', '添加剧本'}
            labels = {button.cget('text') for button in buttons}
            self.assertTrue({'中断', '剧本目录', '删除剧本', '添加剧本'} <= labels)
            for button in buttons:
                if button.cget('text') in action_labels:
                    self.assertEqual(button.cget('width'), desktop.SCRIPT_ACTION_WIDTH)

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
            self.assertFalse(hasattr(d, 'idea_brief_editor'))
            self.assertEqual(d._bubble_full['bubble_example']['text'], d.idea_example())
            self.assertEqual(d.draft_text(), '', '下方发送框初始为空')
            self.assertIn('对话AI · 示例模板', self.log_text(d), '示例只在只读气泡显示')
            with patch.object(d.notifier, 'info') as notice, patch.object(d, 'start_script_workflow') as launch:
                d.send_message(); win.update()
            launch.assert_not_called()
            self.assertEqual(len(d._idea_missing_dialog.brief_fields), 6)
            notice.assert_not_called()
            self.assertFalse(hasattr(d, 'open_brief_creation_form'))
            self.assertEqual(idea_chat.load(proj), [], '一个字都不许发出去')
            self.assertFalse(idea_chat.brief_raw_path(proj).exists(), '示例被门禁拦截后不应落盘')

    def test_followup_can_complete_required_fields_below_unchanged_example(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            d.idea_input.insert('1.0', self.complete_draft())
            with patch.object(d.notifier, 'info') as notice, patch.object(
                    d, 'start_script_workflow', return_value=('Codex', False)) as launch:
                d.send_message()
            notice.assert_not_called()
            launch.assert_called_once()
            self.assertEqual(launch.call_args.args, (self.complete_draft(),))
            config = launch.call_args.kwargs['config']
            self.assertEqual(config['engine'], 'codex')
            self.assertIn('pipeline-script-preparation', config['frozen_skill_prompt'])
            self.assertEqual(len(config['skill_injection']['loaded']), 1)

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_local_attachment_send_extracts_without_sending_body(self, _mode):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            source = Path(td) / '素材.txt'
            source.write_text('故事梗概：照片预示未来\n故事角色：阿青\n故事题材：悬疑\n故事集数：12集', encoding='utf-8')
            paths = archive_idea_attachments(proj, (source,))
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            d.idea_attachment_paths = paths
            self.say(d, self.complete_draft())
            with patch('writing_api.model_label', return_value=''), patch.object(
                    d, 'start_script_workflow', return_value=('Codex', False)) as launch, patch.object(
                    d.notifier, 'info') as form:
                d.send_message()
            form.assert_not_called()
            sent = launch.call_args.args[0]
            self.assertIn('请先读取', sent)
            self.assertNotIn('照片预示未来', sent)

    @patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
    def test_unreadable_attachment_form_has_actionable_first_line(self, _mode):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            source = Path(td) / '素材.pdf'
            source.write_bytes(b'%PDF-unparsed')
            paths = archive_idea_attachments(proj, (source,))
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            d.idea_attachment_paths = paths
            with patch('writing_api.model_label', return_value=''), patch.object(d.notifier, 'info') as notice:
                d.send_message(); win.update()
            notice.assert_not_called()
            notices = [widget.cget('text') for widget in d._idea_missing_dialog.content.winfo_children() if widget.winfo_class() == 'TLabel']
            self.assertTrue(any(text.splitlines()[0] == idea_chat.BRIEF_ATTACHMENT_NOTICE
                                for text in notices))

    def test_brief_form_save_does_not_send_or_replace_chat_draft(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            d.idea_input.delete('1.0', 'end')
            with patch.object(d, 'send_message') as send:
                d.idea_input.insert('1.0', '尚未发送的草稿'); win.update()
                send.assert_not_called()
            self.assertEqual(d.idea_input.get('1.0', 'end-1c'), '尚未发送的草稿')
            self.assertEqual(idea_chat.load(proj), [])
            self.assertFalse(idea_chat.brief_raw_path(proj).exists())
            self.assertFalse(hasattr(d, 'open_brief_creation_form'))

    def test_software_example_can_be_selected_and_copied_from_readonly_bubble(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0); self.settle_script_page(win)
            box = d.idea_log
            start, end = box.tag_ranges('bubble_example')
            end = box.index(str(end) + '-1c')
            box.tag_add('sel', start, end)
            box.event_generate('<<Copy>>'); win.update()
            self.assertEqual(win.clipboard_get(), box.get(start, end))
            self.assertEqual(win.clipboard_get(), d.idea_example())
            self.assertTrue(d.idea_log.tag_ranges('bubble_example'))

    @patch('stage_execution_service.idea_attachment_local_mode', new=lambda _project: False)
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
            attachment_name = Path(d.idea_attachment_paths[0]).name
            self.assertRegex(attachment_name, r'^p_附件文本_角色设定_\d{8}\.md$')
            self.assertIn('已引用：' + attachment_name, d.idea_attachment_status.get())
            seen=[]
            d.open_flow_agent=lambda *args, **kwargs: seen.append(args)
            self.say(d, self.complete_draft() + '\n请基于附档创作')
            d.send_message(); win.update()
            self.assertIn('【附档：' + attachment_name, seen[0][2])
            self.assertIn('主要角色：林默', seen[0][2])
            self.assertEqual(d.idea_attachment_paths, ())
            self.assertIn('【已引用：' + attachment_name, idea_chat.load(proj)[0]['text'])

    @patch('stage_execution_service.idea_attachment_local_mode', new=lambda _project: True)
    def test_local_attachment_status_and_submission_only_expose_relative_path(self):
        from stage_execution_service import archive_idea_attachments, prepare_idea_attachment_selection
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            source = Path(td) / '设定.pdf'
            source.write_bytes(b'PRIVATE_BINARY_PDF')
            archived = archive_idea_attachments(proj, (source,))
            prepared = prepare_idea_attachment_selection(proj, archived)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            d.idea_chat_controller.replace_attachments(prepared['paths'], prepared['details'])
            d.update_idea_attachment_status()
            self.assertIn('设定.pdf（原文件，将由 Agent 自行读取）', d.idea_attachment_status.get())
            self.assertNotIn(str(source), d.idea_attachment_status.get())
            seen = []
            d.open_flow_agent = lambda *args, **kwargs: seen.append(args)
            self.say(d, self.complete_draft() + '\n请参考本地素材')
            d.send_message(); win.update()
            self.assertIn(archived[0].relative_to(proj).as_posix(), seen[0][2])
            self.assertIn('请先读取并解析', seen[0][2])
            self.assertNotIn('PRIVATE_BINARY_PDF', seen[0][2])
            self.assertNotIn(str(source), seen[0][2])

    def test_uploaded_file_list_survives_send_clear_and_deletes_only_confirmed_copy(self):
        from stage_execution_service import archive_idea_attachments
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            source = Path(td) / '角色设定.txt'
            source.write_text('角色设定', encoding='utf-8')
            archived = archive_idea_attachments(proj, (source,))[0]
            d, win = self.desktop(proj)
            d.show(0); win.update()
            tree = d.idea_uploaded_table.tree
            self.assertEqual(tree.item(tree.get_children()[0], 'values'), ('☐ ' + source.name,))
            d.idea_attachment_paths = ()
            d.update_idea_attachment_status(); win.update()
            self.assertTrue(d.idea_uploaded_panel.winfo_manager())
            d.toggle_uploaded_idea_attachment('0'); win.update()
            self.assertNotIn('disabled', d.idea_attachment_delete_button.state())
            with patch('desktop.confirm', return_value=False):
                d.delete_uploaded_idea_attachment()
            self.assertTrue(archived.is_file())
            self.assertEqual(len(tree.get_children()), 1)
            with patch('desktop.confirm', return_value=True) as confirm_delete:
                d.delete_uploaded_idea_attachment()
            win.update()
            self.assertIn(source.name, confirm_delete.call_args.args[2])
            self.assertNotIn(str(source), confirm_delete.call_args.args[2])
            self.assertTrue(source.is_file())
            self.assertFalse(archived.exists())
            self.assertEqual(tree.get_children(), ())
            self.assertFalse(d.idea_uploaded_panel.winfo_manager())
            self.assertIn('disabled', d.idea_attachment_delete_button.state())
            self.assertIn('原始文件未删除', d.status.get())

    def test_uploaded_attachments_are_horizontal_ordered_and_openable(self):
        from stage_execution_service import archive_idea_attachments
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            sources = [Path(td) / name for name in ('先传.txt', '后传.txt', '最后.txt')]
            for source in sources:
                source.write_text(source.stem, encoding='utf-8')
            archived = archive_idea_attachments(proj, sources)
            d, win = self.desktop(proj)
            d.show(0); win.deiconify(); win.update()
            tree = d.idea_uploaded_table.tree
            self.assertEqual(tree.item('attachments', 'values'),
                             tuple('☐ ' + source.name for source in sources))
            self.assertEqual(len(tree.get_children()), 1)
            self.assertFalse(hasattr(d, 'idea_uploaded_heading'))
            self.assertEqual(d.idea_composer_label.cget('text'), '输入想法/上传附件---->enter/发送')
            self.assertEqual(d.idea_attachment_delete_button.winfo_rootx(),
                             d.idea_attachment_button.winfo_rootx())
            self.assertEqual(d.idea_attachment_delete_button.winfo_width(),
                             d.idea_attachment_button.winfo_width())
            self.assertEqual(d.idea_uploaded_table.winfo_rootx(), d.idea_input.winfo_rootx())
            d.toggle_uploaded_idea_attachment('0')
            d.toggle_uploaded_idea_attachment('2')
            d.refresh_uploaded_idea_attachments()
            self.assertEqual(d._idea_uploaded_selected, {archived[0], archived[2]})
            x, y, width, height = tree.bbox('attachments', '1')
            with patch('desktop.open_path') as opened:
                d.open_uploaded_idea_attachment(SimpleNamespace(x=x + width // 2, y=y + height // 2))
            from idea_attachments import archive_pair
            opened.assert_called_once_with(archive_pair(archived[1])[0])
            with patch('desktop.confirm', return_value=True):
                d.delete_uploaded_idea_attachment()
            self.assertFalse(archived[0].exists())
            self.assertTrue(archived[1].exists())
            self.assertFalse(archived[2].exists())
            self.assertTrue(all(source.exists() for source in sources))
            self.assertEqual(tree.item('attachments', 'values'), ('☐ ' + sources[1].name,))

    def test_uploaded_legacy_text_without_original_remains_openable(self):
        from stage_execution_service import archive_idea_attachments
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            source = Path(td) / '素材.txt'
            source.write_text('素材', encoding='utf-8')
            archived = archive_idea_attachments(proj, (source,))[0]
            legacy = archived.parent / '故事创意_20200101__旧材料.txt.md'
            legacy.write_text('旧材料', encoding='utf-8')
            d, win = self.desktop(proj)
            d.show(0); win.deiconify(); win.update()
            self.settle_script_page(win)
            column = next(key for key, path in d._idea_uploaded_paths.items() if path == legacy)
            x, y, width, height = d.idea_uploaded_table.tree.bbox('attachments', column)
            with patch('desktop.open_path') as opened:
                d.open_uploaded_idea_attachment(SimpleNamespace(x=x + width // 2, y=y + height // 2))
            opened.assert_called_once_with(legacy)

    def test_a_failed_workflow_keeps_the_draft_without_creating_a_submission(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); win.update()
            d.open_flow_agent = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('工作流没有启动'))
            self.say(d, self.complete_draft())
            with self.assertRaisesRegex(ValueError, '工作流没有启动'):
                d.send_message()
            self.assertEqual(d.idea_input.get('1.0', 'end-1c'), self.complete_draft())
            self.assertFalse(list((writing_dir(proj) / '创意对话').glob('提交_*.md')),
                             '启动失败也不能留下未获模型回复的剧本文档')

    def queued_api_request(self, proj):
        import stage_config
        import workflow_process_registry as registry
        stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
        d, win = self.desktop(proj)
        d.show(0); self.settle_script_page(win)
        running = registry.reserve_process_slot('running-project', 'script')
        self.addCleanup(registry.release_process_slot, running)
        self.addCleanup(registry.cancel_project_slot_requests, proj)
        pending = []
        d.async_ = lambda fn, done=None, **kwargs: pending.append((fn, done)) or 1
        self.say(d, self.complete_draft())
        d.send_message()
        self.assertEqual(pending, [])
        return d, win, registry, running, pending

    def test_queued_request_does_not_follow_project_switch(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            proj = make_minimal_project(td)
            target = make_minimal_project(other)
            d, win, registry, running, pending = self.queued_api_request(proj)
            with patch.object(d.list, 'selection_set'), patch.object(d.list, 'see'):
                d.load(target)
            registry.release_process_slot(running)
            self.settle_script_page(win, .3)
            self.assertFalse(d.idea_chat_controller.requesting)
            self.assertEqual(pending, [], '切项目必须撤销原项目排队请求')
            self.assertFalse(any(item['project'] == str(proj) for item in registry._queued))

    def test_interrupt_removes_only_its_queue_ticket(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win, registry, running, pending = self.queued_api_request(proj)
            following = registry.request_process_slot(proj, 'script')
            d.interrupt_script_agent()
            registry.release_process_slot(running)
            claimed = registry.claim_process_slot(following['ticket'])
            self.assertEqual(claimed['state'], 'granted', '中断不能留下无人领取的队首或误撤同项目其他请求')
            self.addCleanup(registry.release_process_slot, claimed['slot'])
            self.settle_script_page(win, .3)
            self.assertEqual(pending, [])

    def test_process_poll_preserves_waiting_api_request(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win, registry, running, pending = self.queued_api_request(proj)
            d.flow_processes = {(str(proj), 'writing'): Mock(poll=Mock(return_value=None))}
            d.poll_flow_processes()
            self.assertTrue(any(item['project'] == str(proj) for item in registry._queued))
            d.flow_processes = {}
            d.interrupt_script_agent()


    def test_refresh_retry_can_be_cancelled_before_publication(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            pending, published = [], []
            d.async_ = lambda fn, done=None, **kwargs: pending.append((fn, done)) or 1
            with patch('idea_chat.repair_internal_replies', return_value={'retry_creative': '恢复创意'}), \
                    patch('writing_api.capture_request_model', return_value={
                        'id': 'deepseek-v4-flash', 'record': {}, 'label': 'DeepSeek V4 Flash', 'provider': 'DeepSeek'}), \
                    patch.object(d, 'show_conversation'), patch.object(d, 'refresh_script_list'):
                d.refresh_script_workspace()
            def reply(project, creative, **kwargs):
                self.assertEqual(project, proj)
                self.assertEqual(creative, '恢复创意')
                self.assertEqual(kwargs['request_model']['id'], 'deepseek-v4-flash')
                cancelled = kwargs.get('cancelled')
                self.assertTrue(callable(cancelled), '恢复调用必须收到取消回调')
                self.assertFalse(cancelled())
                d.interrupt_script_agent()
                if not cancelled():published.append(creative)
                return {'ok': False, 'error': '已取消'}
            with patch('writing_api.reply', side_effect=reply):
                result = pending[0][0]()
                pending[0][1](result)
            self.assertEqual(published, [])
            self.assertFalse(d.idea_chat_controller.requesting)

    def test_enter_after_model_change_displays_the_submitted_conversation(self):
        import stage_config
        import model_pool
        self.enterContext(patch('model_pool.pool', return_value=model_pool.default_pool()))
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
            d, win = self.desktop(proj)
            d.show(0); self.settle_script_page(win)
            old_model = d.idea_chat_model()
            idea_chat.append(proj, 'user', '旧模型历史', model=old_model)
            d.show_conversation(); self.settle_script_page(win)
            stage_config.put(proj, 'script', model='qwen-max')
            new_model = d.idea_chat_model()
            self.assertNotEqual(old_model, new_model)
            self.say(d, self.complete_draft('切换模型后的新输入'))
            pending = []
            d.async_ = lambda fn, done=None, **kwargs: pending.append((fn, done)) or 1
            win.deiconify(); win.update()
            d.idea_input.focus_force(); win.update()
            with patch('workflow_engines.request_stage_process_slot', return_value={'state':'granted', 'slot':'test'}):
                d.idea_input.event_generate('<Return>')
                self.settle_script_page(win)
            self.assertEqual(len(pending), 1)
            import skill_panel
            self.assertEqual(d.stage_button.cget('text'), skill_panel.stage_button_label(d, 'script'))
            self.assertEqual(d.draft_text(), '')
            self.assertIn('切换模型后的新输入', idea_chat.load(proj, model=new_model)[-1]['text'])
            self.assertIn('切换模型后的新输入', self.log_text(d))
            self.assertNotIn('旧模型历史', self.log_text(d))
            pending[0][1]({'ok':True, 'text':'新模型回复'})
            self.settle_script_page(win)
            self.assertIn('新模型回复', self.log_text(d))
            self.assertEqual(idea_chat.load(proj, model=old_model)[-1]['text'], '旧模型历史')

    def test_model_selection_waits_for_confirmation_and_cancel_discards_it(self):
        import skill_panel
        import stage_config
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
            d, win = self.desktop(proj)
            d.send_message = Mock()
            launcher = Mock()
            for confirm_selection in (False, True):
                window = self.tk.Toplevel(win)
                panel = skill_panel.Panel(window, d, 'script')
                panel.launcher_button = launcher
                self.assertEqual(panel.model_id(), 'deepseek-v4-flash')
                panel.set_model('qwen-max')
                panel.choose_provider()
                self.assertEqual(stage_config.get(proj, 'script')['model'], 'deepseek-v4-flash')
                panel.set_model('qwen-max')
                panel.choose_model()
                self.assertEqual(stage_config.get(proj, 'script')['model'], 'deepseek-v4-flash')
                panel.save_and_refresh_notes()
                panel.check_all_skills(False)
                self.assertEqual(stage_config.get(proj, 'script')['model'], 'deepseek-v4-flash')
                launcher.configure.assert_not_called()
                if confirm_selection:
                    panel.confirm()
                    self.assertEqual(stage_config.get(proj, 'script')['model'], 'qwen-max')
                    launcher.configure.assert_called_once_with(text=skill_panel.stage_button_label(d, 'script'))
                else:
                    window.destroy()
                    self.assertEqual(stage_config.get(proj, 'script')['model'], 'deepseek-v4-flash')
            d.send_message.assert_not_called()

    def test_editor_review_failure_displays_actual_progress_and_next_request_resets(self):
        import stage_config
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
            d, win = self.desktop(proj)
            d.show(0); win.update()
            pending = []
            d.async_ = lambda fn, done=None, **kwargs: pending.append(done) or 1
            d.idea_chat_controller._clock = iter((100.0, 101.0)).__next__
            self.say(d, self.complete_draft())
            with patch('workflow_engines.request_stage_process_slot', return_value={'state':'granted', 'slot':'test'}):
                d.send_message()
            pending.pop()({'ok': False, 'error': '导演未通过 editor：REVISE: 人物动机不连贯',
                           'hollmwood_review_failed_role': 'editor'})
            self.assertEqual(d.hollmwood_role_status.get(),
                             '导演：审核未通过  ·  编剧：已通过  ·  编辑：未通过  ·  演员：未开始')
            self.assertIn('人物动机不连贯', d.status.get())
            self.say(d, self.complete_draft())
            with patch('workflow_engines.request_stage_process_slot', return_value={'state':'granted', 'slot':'test'}):
                d.send_message()
            self.assertEqual(d.hollmwood_role_status.get(),
                             '导演：等待  ·  编剧：等待  ·  编辑：等待  ·  演员：等待')

    def test_direct_model_failure_ends_an_active_script_stage(self):
        """直接 API 调用失败不能只留在状态栏，自动链必须收到 script 失败事件。"""
        import stage_config
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            stage_config.put(proj, 'script', model='deepseek-v4-flash',
                             skills=['pipeline-script-preparation'])
            d, win = self.desktop(proj)
            d.show(0); win.update()
            emitted = []
            d.pet.auto.active = 'script'
            d.pet._emit = lambda kind, **payload: emitted.append((kind, payload))
            def immediate(fn, done=None, **_ignored):
                if done is not None:
                    done(fn())
            d.async_ = immediate
            self.say(d, self.complete_draft('雨夜照相馆收到会显影未来的旧底片。'))
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
            found = []; colors = []; styles = []
            def click_cancel():
                def walk(widget):
                    if 'text' in widget.keys() and str(widget.cget('text')) == '取消':
                        found.append(widget)
                        colors.append(widget.master.master.master.cget('bg'))
                        styles.append(str(widget.cget('style')))
                        widget.invoke();return True
                    return any(walk(child) for child in widget.winfo_children())
                walk(win)
            win.after(30, click_cancel)
            self.assertFalse(desktop_module.confirm_project_removal_from_last_script(win, ['最后一份.md']))
            self.assertEqual(len(found), 1)
            self.assertEqual(colors, ['#c62828'])
            self.assertEqual(styles, ['Tokens.Secondary.TButton'])

    def test_only_explicit_recycle_accepts_and_close_paths_cancel(self):
        import desktop as desktop_module
        from ui_widgets import BaseDialog, PrimaryButton
        for action in ('recycle', 'window-close', 'escape'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as td:
                proj = make_minimal_project(td)
                _d, win = self.desktop(proj)
                seen = []
                timed_out = []
                watchdog = []

                def act():
                    dialog = next(child for child in win.winfo_children()
                                  if isinstance(child, BaseDialog))
                    button = next(child for child in BaseDialog._descendants(dialog)
                                  if 'text' in child.keys()
                                  and str(child.cget('text')) == '移入回收站')
                    def timeout():
                        timed_out.append(True)
                        dialog.destroy()
                    watchdog.append(win.after(2000, timeout))
                    seen.append((isinstance(button, PrimaryButton), str(button.cget('style'))))
                    if action == 'recycle':
                        button.invoke()
                    elif action == 'window-close':
                        dialog.tk.call(dialog.protocol('WM_DELETE_WINDOW'))
                    else:
                        dialog.focus_force()
                        dialog.event_generate('<Escape>')

                win.after(30, act)
                accepted = desktop_module.confirm_project_removal_from_last_script(win, ['最后一份.md'])
                for timer in watchdog:
                    win.after_cancel(timer)
                self.assertEqual(timed_out, [], '确认窗关闭路径不得卡住')
                self.assertEqual(accepted, action == 'recycle')
                self.assertEqual(seen, [(True, 'Tokens.Danger.TButton')])
                self.assertTrue(proj.is_dir(), '确认窗本身不得执行文件删除')


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
            self.assertIn('对话AI · ' + model, self.log_text(d))
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

    def test_delete_all_menu_order_and_persistent_history_removal(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            model = d.idea_chat_model()
            idea_chat.append(proj, 'user', '要删除的隐藏历史', model=model)
            idea_chat.append(proj, 'assistant', '要删除的回复', model=model)
            idea_chat.append(proj, 'user', '其他模型保留', model='另一模型')
            idea_chat.remove(proj, 1, model=model)
            d.show(0)
            self.settle_script_page(win)
            event = SimpleNamespace(widget=d.idea_log, x=8, y=8)
            with patch.object(d, 'bubble_target_at', return_value=(0, 'bubble_0')), \
                 patch('desktop.ContextMenu.popup', return_value='break'):
                d.open_bubble_menu(event)
            labels = [d._bubble_menu.entrycget(i, 'label')
                      for i in range(d._bubble_menu.index('end') + 1)
                      if d._bubble_menu.type(i) != 'separator']
            self.assertEqual(labels[labels.index('删除整条信息') + 1], '删除全部信息')
            with patch('desktop.confirm', return_value=False):
                self.assertIsNone(d.delete_all_bubble_messages())
            self.assertEqual(len(idea_chat.load(proj, model=model)), 1)
            d.clear_bubble_view()
            with patch('desktop.confirm', return_value=True):
                self.assertEqual(d.delete_all_bubble_messages(), 1)
            d.refresh_script_workspace()
            self.settle_script_page(win)
            self.assertNotIn('要删除的隐藏历史', self.log_text(d))
            _idea_chat._history_cache.clear()
            self.assertEqual(idea_chat.load(proj, model=model), [])
            self.assertEqual(idea_chat.load(proj, model='另一模型')[0]['text'], '其他模型保留')
            with self.assertRaisesRegex(ValueError, '没有可恢复'):
                idea_chat.restore_latest_removed(proj, model=model)
            self.assertTrue(list(Path(proj).rglob('恢复位置.json')))
            d._idea_requesting = True
            with patch('desktop.confirm') as confirmation:
                with self.assertRaisesRegex(ValueError, '模型正在回复'):
                    d.delete_all_bubble_messages()
                confirmation.assert_not_called()
            d._idea_requesting = False

    def test_delete_all_targets_displayed_history_when_configuration_changed(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            displayed = d.idea_chat_model()
            idea_chat.append(proj, 'assistant', '当前气泡中的历史', model=displayed)
            idea_chat.append(proj, 'user', '其他模型的历史', model='另一模型')
            d.show(0)
            self.settle_script_page(win)
            self.assertIn('当前气泡中的历史', self.log_text(d))
            with patch.object(d, 'idea_chat_model', return_value='另一模型'), \
                 patch('desktop.confirm', return_value=True):
                self.assertEqual(d.delete_all_bubble_messages(), 1)
                self.settle_script_page(win)
                self.assertNotIn('当前气泡中的历史', self.log_text(d))
                d.show_conversation()
                self.settle_script_page(win)
                self.assertNotIn('当前气泡中的历史', self.log_text(d))
            self.assertEqual(idea_chat.load(proj, model=displayed), [])
            self.assertEqual(idea_chat.load(proj, model='另一模型')[0]['text'], '其他模型的历史')

    def test_message_actions_target_displayed_model_after_configuration_changed(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            displayed = d.idea_chat_model()
            idea_chat.append(proj, 'assistant', '当前气泡正文', model=displayed,
                             context_budget={'input_tokens': 123, 'context_limit': 64000, 'output_reserved': 4096},
                             request_usage={'prompt_tokens': 110, 'completion_tokens': 30, 'cached_tokens': None})
            idea_chat.append(proj, 'assistant', '另一模型正文', model='另一模型')
            d.show(0)
            self.settle_script_page(win)
            self.assertIn('输入估算 123', d.idea_usage_label.cget('text'))
            with patch.object(d, 'idea_chat_model', return_value='另一模型'):
                with patch('prompt_window.copy_text', return_value='') as copied:
                    self.assertEqual(d.copy_bubble_message(0), '当前气泡正文')
                    self.assertEqual(copied.call_args.args[1], '当前气泡正文')
                d.delete_bubble_message(0)
                self.assertEqual(idea_chat.load(proj, model=displayed), [])
                d.restore_latest_bubble_message()
                self.assertEqual(idea_chat.load(proj, model=displayed)[0]['text'], '当前气泡正文')
                self.assertEqual(idea_chat.load(proj, model='另一模型')[0]['text'], '另一模型正文')
                d.refresh_script_chat_for_selected_model()
                self.settle_script_page(win)
                self.assertIn('另一模型正文', self.log_text(d))
                self.assertNotIn('当前气泡正文', self.log_text(d))
                self.assertEqual(d.idea_usage_label.cget('text'), '本模型暂无用量记录')

    def test_delete_all_removes_legacy_duplicates_and_protects_other_files(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '当前历史', model='模型甲')
            idea_chat.save_rows(proj, [
                {'role': 'user', 'text': '旧版重复', 'model': '模型甲'},
                {'role': 'user', 'text': '旧版其他模型', 'model': '模型乙'}])
            artifact = Path(proj) / '已保存剧本.md'
            artifact.write_text('已保存正文', encoding='utf-8')
            idea_chat.remove_all(proj, '模型甲')
            _idea_chat._history_cache.clear()
            self.assertEqual(idea_chat.load(proj, model='模型甲'), [])
            self.assertEqual(idea_chat.load(proj, model='模型乙')[0]['text'], '旧版其他模型')
            self.assertEqual(artifact.read_text(encoding='utf-8'), '已保存正文')
            idea_chat.append(proj, 'user', '失败时保留', model='模型甲')
            gateway = idea_chat_gateway()
            gateway['recycle_paths'] = lambda *args: []
            with self.assertRaisesRegex(OSError, '未能移入回收站'):
                idea_chat.remove_all(proj, '模型甲', gateway=gateway)
            self.assertEqual(idea_chat.load(proj, model='模型甲')[0]['text'], '失败时保留')

    def test_editing_right_click_finishes_edit_without_opening_clear_menu(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0)
            self.settle_script_page(win)
            d._bubble_edit = {'editing': True}
            event = SimpleNamespace(widget=d.idea_log, x=8, y=8)
            with patch.object(d, 'finish_bubble_edit') as finish, \
                 patch('desktop.ContextMenu') as menu:
                self.assertEqual(d.open_bubble_menu(event), 'break')
            finish.assert_called_once_with()
            menu.assert_not_called()

    def test_clear_screen_compacts_context_and_refresh_only_restores_display(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            model = d.idea_chat_model()
            original = '主角保留底片。' + '冗长讨论' * 1500
            idea_chat.append(proj, 'user', original, model=model)
            d.show(0)
            self.settle_script_page(win)
            d.clear_bubble_view()
            self.assertLess(len(idea_chat.history_context(idea_chat.load(proj, model=model))), 1801)
            d.refresh_script_workspace()
            self.settle_script_page(win)
            self.assertIn('主角保留底片', self.log_text(d))
            self.assertEqual(idea_chat.load(proj, model=model)[0]['text'], original)
            self.assertLess(len(idea_chat.history_context(idea_chat.load(proj, model=model))), 1801)

    def test_clear_bubbles_cancels_pending_display_without_changing_saved_content(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            for index in range(20):
                idea_chat.append(proj, 'user', '保留的消息 %d' % index)
            d, win = self.desktop(proj)
            d.show(0)
            self.settle_script_page(win)
            d.idea_input.insert('1.0', '保留草稿')
            draft = d.draft_text()
            attachments = d.idea_attachment_paths
            saved = idea_chat.load(proj)
            d.show_conversation()  # 首批历史尚在空闲队列中。
            self.assertTrue(d._idea_view_after_jobs)
            d.clear_bubble_view()
            self.settle_script_page(win)
            self.assertEqual(self.log_text(d), '')
            self.assertEqual(d._bubble_rows, [])
            self.assertEqual(d._bubble_full, {})
            self.assertEqual(d._idea_view_after_jobs, [])
            self.assertEqual(idea_chat.load(proj), [dict(row, context_compacted=True) for row in saved])
            self.assertEqual(d.draft_text(), draft)
            self.assertEqual(d.idea_attachment_paths, attachments)
            d.refresh_script_workspace()
            self.settle_script_page(win)
            self.assertIn('保留的消息 19', self.log_text(d))

    def test_clear_screen_keeps_old_messages_hidden_when_sending_and_redrawing(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            d, win = self.desktop(proj)
            model = d.idea_chat_model()
            idea_chat.append(proj, 'user', '清屏前的历史', model=model)
            d.show(0)
            self.settle_script_page(win)
            saved = idea_chat.load(proj, model=model)
            d.clear_bubble_view()
            d.open_flow_agent = lambda *args, **kwargs: None
            draft = SendMessageTests.complete_draft('清屏后新发送')
            d.idea_input.delete('1.0', 'end')
            d.idea_input.insert('1.0', draft)
            d.send_message()
            self.settle_script_page(win)
            self.assertNotIn('清屏前的历史', self.log_text(d))
            self.assertIn('清屏后新发送', self.log_text(d))
            self.assertEqual(d.copy_bubble_message(1), draft)
            d.show_thinking(model)
            self.settle_script_page(win)
            self.assertNotIn('清屏前的历史', self.log_text(d))
            self.assertIn('模型正在思考', self.log_text(d))
            idea_chat.append(proj, 'assistant', '清屏后新回复', model=model)
            d.clear_thinking()
            self.settle_script_page(win)
            self.assertNotIn('清屏前的历史', self.log_text(d))
            self.assertIn('清屏后新回复', self.log_text(d))
            self.assertEqual(idea_chat.load(proj, model=model)[:1], [dict(row, context_compacted=True) for row in saved])
            d.delete_bubble_message(1)
            self.settle_script_page(win)
            self.assertNotIn('清屏前的历史', self.log_text(d))
            self.assertIn('清屏后新回复', self.log_text(d))

    def test_clear_screen_menu_is_available_on_message_example_and_blank_area(self):
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            d.show(0)
            self.settle_script_page(win)
            event = SimpleNamespace(widget=d.idea_log, x=8, y=8)
            for target in ((0, 'bubble_0'), ('example', 'bubble_example'), None):
                with self.subTest(target=target), \
                        patch.object(d, 'bubble_target_at', return_value=target), \
                        patch('desktop.ContextMenu.popup', return_value='break'), \
                        patch.object(d, 'clear_bubble_view') as clear:
                    self.assertEqual(d.open_bubble_menu(event), 'break')
                    menu = d._bubble_menu
                    index = menu.index('end')
                    self.assertEqual(menu.entrycget(index, 'label'), '清屏')
                    menu.invoke(index)
                    clear.assert_called_once_with()

    def test_clear_screen_is_scoped_and_preserves_new_identical_messages(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            proj = make_minimal_project(td)
            other_proj = make_minimal_project(other)
            d, win = self.desktop(proj)
            with patch.object(d, 'idea_chat_model', return_value='模型甲'):
                idea_chat.append(proj, 'user', '相同正文', at=1000, model='模型甲')
                saved = idea_chat.load(proj, model='模型甲')
                idea_chat.save_rows(proj, [dict(saved[0], model='模型乙')], model='模型乙')
                idea_chat.append(other_proj, 'user', '另一项目历史', model='模型甲')
                d.show(0)
                self.settle_script_page(win)
                d.clear_bubble_view()
                d.show_conversation()
                self.settle_script_page(win)
                self.assertEqual(self.log_text(d), '')
                idea_chat.save_rows(proj, saved + saved, model='模型甲')
                d.show_conversation()
                self.settle_script_page(win)
                self.assertEqual(self.log_text(d).count('相同正文'), 1)
                self.assertTrue(d.idea_log.tag_ranges('bubble_1'))
                d.clear_bubble_view()
                d.show_conversation()
                self.settle_script_page(win)
                self.assertEqual(self.log_text(d), '')
                with patch.object(d, 'idea_chat_model', return_value='模型乙'):
                    d.refresh_script_chat_for_selected_model()
                    self.settle_script_page(win)
                    self.assertIn('相同正文', self.log_text(d))
                d.refresh_script_chat_for_selected_model()
                self.settle_script_page(win)
                self.assertEqual(self.log_text(d), '')
                d.root = other_proj
                d.show_conversation()
                self.settle_script_page(win)
                self.assertIn('另一项目历史', self.log_text(d))

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
            model = d.displayed_chat_model()
            d.show_thinking(model); win.update()
            self.assertIn(model + ' 模型正在思考…', self.log_text(d))
            d._idea_view_model_cache = (d.root, '另一个模型')
            d.show_conversation(); win.update()
            self.assertNotIn('模型正在思考…', self.log_text(d))
            d.clear_thinking(); win.update()
            self.assertNotIn('模型正在思考…', self.log_text(d))

    def test_only_what_you_type_below_the_line_gets_sent(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            idea_chat.append(proj, 'user', '先前的创意')
            idea_chat.append(proj, 'assistant', '先前的纲要')
            d, win = self.desktop(proj)
            d.show(0); win.update()
            d.idea_input.delete('1.0', 'end')
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

    def test_session_label_explains_dimensions_and_follows_model_switch(self):
        """O14：界面要说明会话模型/调用方式、请求身份、上下文与项目共享成果。"""
        with tempfile.TemporaryDirectory() as td:
            d, win = self.desktop(make_minimal_project(td))
            self.sync_async(d)
            d.show(0)
            self.settle_script_page(win)
            text = d.idea_session_label.cget('text')
            self.assertIn('当前会话：', text)
            self.assertIn('按模型隔离', text)
            self.assertIn('不隐藏也不复制项目成果', text)
            with patch.object(d, 'idea_chat_model', return_value='另一模型'):
                d.refresh_script_chat_for_selected_model()
                self.settle_script_page(win)
                self.assertIn('另一模型', d.idea_session_label.cget('text'))


class SessionOverviewTests(unittest.TestCase):
    """O14：只读说明把会话、请求身份、上下文与项目共享成果分开。"""

    def test_overview_separates_session_context_and_adoption(self):
        import writing_api
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            proj = make_minimal_project(td)
            folder = writing_dir(proj)
            (folder / '项目设定').mkdir(parents=True, exist_ok=True)
            save(folder / '项目设定' / '设定.md', '# 项目设定\n内容\n')
            save(folder / 'preparation_state.json', {
                'version': 1, 'brief_hash': 'x',
                'documents': [{'path': '项目设定/设定.md', 'stage': '项目设定',
                               'sha256': 'y', 'confirmed': True}]})
            info = writing_api.chat_session_overview(proj, 'gpt-4o')
            self.assertEqual(info['model'], 'gpt-4o')
            self.assertEqual(info['invocation'], 'API 直连')
            self.assertIn('按模型隔离', info['context'])
            self.assertEqual(info['shared_confirmed_documents'], 1)
            self.assertEqual(info['adopted_script'], '尚未采用自然剧本')
            self.assertEqual(writing_api.chat_session_overview(proj, 'claude-code')['invocation'],
                             '本机 CLI（claude）')
            summary = writing_api.chat_session_summary(proj, 'gpt-4o')
            self.assertIn('gpt-4o', summary)
            self.assertIn('已确认阶段文件 1 份', summary)
            self.assertIn('不隐藏也不复制项目成果', summary)


if __name__ == '__main__':
    unittest.main(verbosity=2)
