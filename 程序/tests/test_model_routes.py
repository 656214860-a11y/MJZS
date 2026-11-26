# -*- coding: utf-8 -*-
"""模型管理页重构与单模型多 API 路线（REQ-UI-MODEL-PAGE-2）全链路自检。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import infra.model_pool as model_pool
import infra.model_router as model_router
import infra.model_routes as model_routes
import infra.model_secrets as model_secrets
import pet_models_ui
from tests.test_ui_batch7_settings_models import Batch7Case, _button, _buttons


def _install_fake_dpapi(case):
    original = model_secrets.PROTECTOR

    def protector(data, decrypt=False, label='模型 API Key'):
        raw = bytes(data)
        if decrypt:
            if not raw.startswith(b'test:'):
                raise ValueError('bad secret')
            return raw[5:][::-1]
        return b'test:' + raw[::-1]

    model_secrets.PROTECTOR = protector
    case.addCleanup(setattr, model_secrets, 'PROTECTOR', original)


class MultiRouteInfraTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = Path(self.tmp.name)
        _install_fake_dpapi(self)

    def test_provider_presets_include_nine_mainstream_entries(self):
        labels = model_routes.preset_labels()
        self.assertEqual(len(labels), 9)
        self.assertIn('DeepSeek 官方', labels)
        self.assertIn('Anthropic (Claude)', labels)
        self.assertIn('硅基流动 (SiliconFlow)', labels)
        self.assertIn('自定义中转', labels)
        anth = model_routes.preset_by_label('Anthropic (Claude)')
        self.assertEqual(anth['wire_api'], 'messages')
        self.assertEqual(anth['base_url'], 'https://api.anthropic.com')

    def test_legacy_single_route_is_wrapped_and_multi_route_mirrors_first_enabled(self):
        legacy = model_pool.record({
            'model': 'deepseek-chat',
            'base_url': 'https://api.deepseek.com',
            'key_env': 'DEEPSEEK_API_KEY',
            'wire_api': 'chat',
        }, 'deepseek-chat')
        self.assertNotIn('routes', legacy, '旧单路线格式不强行注入 routes 键')
        wrapped = model_routes.routes_of(legacy, model_id='deepseek-chat')
        self.assertEqual(len(wrapped), 1)
        self.assertEqual(wrapped[0]['base_url'], 'https://api.deepseek.com')

        multi = model_pool.record({
            'model': 'claude-sonnet',
            'label': 'Claude Sonnet',
            'routes': [
                {'id': 'r1', 'name': '官方', 'base_url': 'https://api.anthropic.com',
                 'wire_api': 'messages', 'model': 'claude-sonnet-4-5', 'enabled': False},
                {'id': 'r2', 'name': '中转', 'base_url': 'https://relay.example/v1',
                 'wire_api': 'chat', 'model': 'anthropic/claude-4.5', 'key_env': 'RELAY_KEY', 'enabled': True},
            ],
        }, 'claude-sonnet')
        self.assertEqual(len(multi['routes']), 2)
        self.assertEqual(multi['base_url'], 'https://relay.example/v1', '顶层镜像必须跟首选启用路线对齐')
        self.assertEqual(multi['wire_api'], 'chat')
        self.assertEqual(multi['key_env'], 'RELAY_KEY')

    def test_per_route_dpapi_keys_are_isolated(self):
        parent = {'model': 'deepseek-pro', 'label': 'DeepSeek Pro'}
        r1 = {'id': 'r1', 'base_url': 'https://api.deepseek.com', 'model': 'deepseek-pro'}
        r2 = {'id': 'r2', 'base_url': 'https://relay.example/v1', 'model': 'ds-pro'}
        n1 = model_routes.save_route_key(parent, r1, 'sk-primary-1111', program=self.program,
                                         model_id='deepseek-pro', index=0)
        n2 = model_routes.save_route_key(parent, r2, 'sk-backup-2222', program=self.program,
                                         model_id='deepseek-pro', index=1)
        self.assertNotEqual(n1, n2)
        r1['key_env'], r2['key_env'] = n1, n2
        self.assertEqual(model_routes.route_key_of(parent, r1, program=self.program, model_id='deepseek-pro', index=0),
                         'sk-primary-1111')
        self.assertEqual(model_routes.route_key_of(parent, r2, program=self.program, model_id='deepseek-pro', index=1),
                         'sk-backup-2222')
        self.assertTrue(model_routes.clear_route_key(parent, r2, program=self.program, model_id='deepseek-pro', index=1))
        self.assertEqual(model_routes.route_key_of(parent, r2, program=self.program, model_id='deepseek-pro', index=1), '')
        self.assertEqual(model_routes.route_key_of(parent, r1, program=self.program, model_id='deepseek-pro', index=0),
                         'sk-primary-1111', '清除备用路线密钥不得影响主路线')

    def test_four_state_badges_persistence_and_backup_aggregation(self):
        parent = model_pool.record({
            'model': 'ds-test',
            'label': 'DS Test',
            'routes': [
                {'id': 'r1', 'name': '官方', 'base_url': 'https://api.deepseek.com', 'model': 'ds-test'},
                {'id': 'r2', 'name': '备用', 'base_url': 'https://relay.example/v1', 'model': 'ds-test-r'},
            ],
        }, 'ds-test')
        # 缺 Key 状态
        b0 = model_routes.model_badge('ds-test', parent, program=self.program)
        self.assertEqual(b0['state'], 'missing')
        self.assertIn('待填 Key', b0['short'])
        # 填上两把密钥 -> 已配置未测
        parent['routes'][0]['key_env'] = model_routes.save_route_key(
            parent, parent['routes'][0], 'sk-one', program=self.program, model_id='ds-test', index=0)
        parent['routes'][1]['key_env'] = model_routes.save_route_key(
            parent, parent['routes'][1], 'sk-two', program=self.program, model_id='ds-test', index=1)
        b1 = model_routes.model_badge('ds-test', parent, program=self.program)
        self.assertEqual(b1['state'], 'idle')
        # 路线 1 测挂 401，路线 2 测通 -> 模型卡聚合标「已切备用」
        model_routes.probe_route(
            parent, parent['routes'][0], model_id='ds-test', index=0, program=self.program,
            transport=lambda *_a: {'ok': False, 'status': 401, 'error': 'HTTP 401: invalid'})
        model_routes.probe_route(
            parent, parent['routes'][1], model_id='ds-test', index=1, program=self.program,
            transport=lambda *_a: {'ok': True, 'status': 200, 'data': {'model': 'ds-test-r', 'choices': [{'message': {'content': 'ok'}}]}})
        b2 = model_routes.model_badge('ds-test', parent, program=self.program)
        self.assertEqual(b2['state'], 'warn')
        self.assertIn('已切备用', b2['short'])
        self.assertIn('2条线路（1已测通）', b2['meta'])
        # 改动路线 2 地址后，配置版本变化自动使旧绿灯失效退回未测试
        parent['routes'][1]['base_url'] = 'https://other-relay.example/v1'
        r2_badge = model_routes.route_badge(parent, parent['routes'][1], model_id='ds-test',
                                            index=1, program=self.program)
        self.assertEqual(r2_badge['state'], 'idle')

    def test_probe_route_override_key_does_not_write_disk(self):
        seen_headers = []
        def transport(url, body, headers, timeout):
            seen_headers.append(headers)
            return {'ok': True, 'status': 200, 'data': {'model': 'm1', 'choices': [{'message': {'content': 'hi'}}]}}
        parent = {'model': 'm1', 'label': 'M1'}
        route = {'id': 'r1', 'base_url': 'https://api.example.test/v1', 'model': 'm1'}
        res = model_routes.probe_route(
            parent, route, model_id='m1', index=0, program=self.program, transport=transport,
            options={'override_key': 'sk-temp-xyz', 'persist': True})
        self.assertTrue(res['ok'])
        self.assertEqual(seen_headers[0]['Authorization'], 'Bearer sk-temp-xyz')
        self.assertEqual(model_routes.all_probe_status(program=self.program), {})

    def test_fetch_remote_models_parses_and_handles_failure(self):
        def ok_transport(url, payload, headers, timeout):
            self.assertIsNone(payload)
            self.assertTrue(url.endswith('/models'))
            return {'ok': True, 'status': 200, 'data': {'data': [{'id': 'gpt-4o'}, {'id': 'deepseek-chat'}, {'id': 'gpt-4o'}]}}
        ok_res = model_routes.fetch_remote_models('https://api.example.test/v1', api_key='sk-1', transport=ok_transport)
        self.assertTrue(ok_res['ok'])
        self.assertEqual(ok_res['models'], ['deepseek-chat', 'gpt-4o'])
        fail_res = model_routes.fetch_remote_models(
            'https://api.example.test/v1', api_key='sk-1',
            transport=lambda *_a: {'ok': False, 'status': 404, 'error': 'HTTP 404'})
        self.assertFalse(fail_res['ok'])
        self.assertIn('手动输入', fail_res['error'])


class MultiRouteFailoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = Path(self.tmp.name)
        _install_fake_dpapi(self)
        model_router._CIRCUITS.clear()

    def _two_route_record(self):
        rec = model_pool.record({
            'model': 'claude-s',
            'label': 'Claude S',
            'routes': [
                {'id': 'r1', 'name': '官方', 'base_url': 'https://primary.test/v1',
                 'wire_api': 'chat', 'model': 'claude-official', 'enabled': True},
                {'id': 'r2', 'name': '中转', 'base_url': 'https://backup.test/v1',
                 'wire_api': 'chat', 'model': 'relay/claude-s', 'enabled': True},
            ],
        }, 'claude-s')
        rec['routes'][0]['key_env'] = model_routes.save_route_key(
            rec, rec['routes'][0], 'sk-primary', program=self.program, model_id='claude-s', index=0)
        rec['routes'][1]['key_env'] = model_routes.save_route_key(
            rec, rec['routes'][1], 'sk-backup', program=self.program, model_id='claude-s', index=1)
        return rec

    def test_chat_fails_over_from_primary_429_to_backup_with_alias_and_isolated_key(self):
        rec = self._two_route_record()
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append((url, payload['model'], headers['Authorization']))
            if 'primary.test' in url:
                return {'ok': False, 'status': 429, 'error': 'HTTP 429: rate limit'}
            return {'ok': True, 'status': 200,
                    'data': {'choices': [{'message': {'content': '来自备用路线'}}]}}
        adapter = model_router.PoolAdapter(rec, model_id='claude-s', program=self.program, transport=transport)
        self.assertTrue(adapter.available())
        res = adapter.chat([{'role': 'user', 'content': '你好'}])
        self.assertTrue(res['ok'])
        self.assertEqual(res['text'], '来自备用路线')
        self.assertEqual(res['route_id'], 'r2')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], ('https://primary.test/v1/chat/completions', 'claude-official', 'Bearer sk-primary'))
        self.assertEqual(calls[1], ('https://backup.test/v1/chat/completions', 'relay/claude-s', 'Bearer sk-backup'))

    def test_chat_stops_on_400_bad_request_without_trying_backup(self):
        rec = self._two_route_record()
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append(url)
            return {'ok': False, 'status': 400, 'error': 'HTTP 400: bad param'}
        adapter = model_router.PoolAdapter(rec, model_id='claude-s', program=self.program, transport=transport)
        res = adapter.chat([{'role': 'user', 'content': '你好'}])
        self.assertFalse(res['ok'])
        self.assertEqual(len(calls), 1)

    def test_chat_skips_disabled_primary_route(self):
        rec = self._two_route_record()
        rec['routes'][0]['enabled'] = False
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append(url)
            return {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': '直达备用'}}]}}
        adapter = model_router.PoolAdapter(rec, model_id='claude-s', program=self.program, transport=transport)
        res = adapter.chat([{'role': 'user', 'content': '你好'}])
        self.assertTrue(res['ok'])
        self.assertEqual(res['route_id'], 'r2')
        self.assertEqual(calls, ['https://backup.test/v1/chat/completions'])


class ModelManagerRedesignUiTests(Batch7Case):
    def test_master_detail_top_actions_and_no_bottom_bar_at_three_widths(self):
        win = self._manager_window()
        for label in ('保存这条', '新建一条', '取消', '关闭'):
            self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == label],
                             '旧底栏按钮 %s 应已移除' % label)
        for width in (pet_models_ui.MANAGER_MIN[0], 990, 1180):
            win.geometry('%dx%d' % (width, pet_models_ui.MANAGER_MIN[1]))
            win.update()
            edge = win.winfo_rootx() + win.winfo_width()
            bottom = win.winfo_rooty() + win.winfo_height()
            save = _button(win, '保存')
            delete = _button(win, '删除')
            test_btn = _button(win, '测试')
            self.assertEqual(str(save.cget('style')), 'Tokens.Primary.TButton')
            self.assertGreater(save.winfo_rootx(), delete.winfo_rootx())
            self.assertEqual(save.winfo_rooty(), delete.winfo_rooty())
            self.assertIn('语音识别', win._pet_mode_buttons)
            self.assertFalse([b for b in _buttons(win) if str(b.cget('text')) == '语音识别…'])
            for btn in (save, delete, _button(win, '+ 新建模型'), _button(win, '检测全部'), test_btn):
                self.assertTrue(btn.winfo_ismapped(), (width, btn.cget('text')))
                self.assertLessEqual(btn.winfo_rootx() + btn.winfo_width(), edge, (width, btn.cget('text')))
                self.assertLessEqual(btn.winfo_rooty() + btn.winfo_height(), bottom, (width, btn.cget('text')))
            # 按钮全部上移，不应压在窗口最底 80px 内
            self.assertLess(save.winfo_rooty(), win.winfo_rooty() + 180)
            self.assertLess(test_btn.winfo_rooty(), bottom - 80)

    def test_backup_routes_collapse_by_default_with_inline_test_and_promote(self):
        record = model_pool.record({
            'model': 'ds-multi',
            'label': 'DS Multi',
            'call_mode': 'API',
            'routes': [
                {'id': 'r1', 'name': '官方直连', 'base_url': 'https://api.deepseek.com', 'model': 'ds-multi'},
                {'id': 'r2', 'name': '备用中转', 'base_url': 'https://relay.test/v1', 'model': 'ds-relay'},
            ],
        }, 'ds-multi')
        self.pet.agent_model_records = lambda: {'ds-multi': record}
        win = self._manager_window()
        win._pet_select_model('ds-multi')
        win.update()
        cards = win._pet_route_cards()
        self.assertEqual(len(cards), 2)
        self.assertTrue(cards[0].is_expanded(), '首选路线默认展开')
        self.assertFalse(cards[1].is_expanded(), '备用路线默认折叠为单行摘要条')
        self.assertTrue(cards[1].test_button.winfo_ismapped(), '折叠态备用路线右侧测试按钮直接可点')
        cards[1].promote_button.invoke()
        win.update()
        cards_after = win._pet_route_cards()
        self.assertEqual(cards_after[0].base_url_entry.get(), 'https://relay.test/v1', '设为首选应提升到路线 1')

    def test_advanced_section_collapsed_by_default_and_restore_defaults(self):
        win = self._manager_window()
        adv = win._pet_advanced_section
        self.assertFalse(adv.is_open(), '高级参数默认折叠')
        for key, value in (('context_length', '262144'), ('max_output', '8192'),
                           ('temperature', '0.7'), ('timeout', '120'), ('retries', '2')):
            self.assertEqual(win._pet_entries[key].get(), value)
        adv.toggle()
        win.update()
        self.assertTrue(adv.is_open())
        win._pet_entries['context_length'].delete(0, 'end')
        win._pet_entries['context_length'].insert(0, '16384')
        _button(win, '恢复默认').invoke()
        self.assertEqual(win._pet_entries['context_length'].get(), '262144')

    def test_provider_preset_autofills_base_url_and_protocol(self):
        win = self._manager_window()
        card = win._pet_route_cards()[0]
        card.provider_var.set('Anthropic (Claude)')
        card.provider_box.event_generate('<<ComboboxSelected>>')
        win.update()
        self.assertEqual(card.base_url_entry.get(), 'https://api.anthropic.com')
        self.assertIn('Anthropic', card.wire_var.get())

    def test_async_route_test_updates_badge_and_five_dim_details(self):
        record = model_pool.record({
            'model': 'ds-probe',
            'label': 'DS Probe',
            'call_mode': 'API',
            'base_url': 'https://api.deepseek.com',
        }, 'ds-probe')
        self.pet.agent_model_records = lambda: {'ds-probe': record}
        self.pet.probe_transport = lambda *_a: {
            'ok': True, 'status': 200,
            'data': {'model': 'ds-probe', 'choices': [{'message': {'content': '收到'}}]},
        }
        win = self._manager_window()
        win._pet_select_model('ds-probe')
        card = win._pet_route_cards()[0]
        card.key_entry.insert(0, 'sk-live-test')
        card.test_button.invoke()
        for _ in range(40):
            win.update()
            if '已测通' in card.status_line_var.get():
                break
            win.after(20)
        self.assertIn('已测通', card.status_line_var.get())
        card.detail_toggle.invoke()
        win.update()
        self.assertIn('连通性：通过', card.detail_text_var.get())
        self.assertTrue(card.verify_button.winfo_ismapped())

    def test_embedded_settings_hub_renders_dsh_multi_route_and_saves(self):
        """REQ-UI-MODEL-PAGE-2 + UX-SETTINGS-MODELS：设置窗右侧内嵌渲染 DSH 多路线视图并经底栏保存。"""
        win = self._hub('model_config')
        seam = win._pet_seams['model_config']
        manager = seam['manager']
        self.assertTrue(seam['cards'].winfo_ismapped())
        self.assertEqual(len(seam['route_cards']()), 1)
        manager.add_route()
        win.update()
        cards = seam['route_cards']()
        self.assertEqual(len(cards), 2)
        seam['entries']['model'].set('deepseek-v4-multi')
        cards[0].base_url_entry.set('https://api.deepseek.com')
        cards[1].base_url_entry.set('https://relay.example.invalid/v1')
        with mock.patch.object(self.pet, 'save_pool') as save_pool:
            _button(win, '保存当前').invoke()
        save_pool.assert_called_once()
        saved = save_pool.call_args.args[0]
        self.assertEqual(saved['model'], 'deepseek-v4-multi')
        self.assertEqual(len(saved['routes']), 2)
        self.assertTrue(win.winfo_exists())


if __name__ == '__main__':
    unittest.main()
