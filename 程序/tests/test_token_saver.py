# -*- coding: utf-8 -*-
"""第 66 期：附件《多模型子 Agent Token 节省完整命令清单》的验收用例。

附件把整件事分成五段，这里也按五段验：
- 阶段一 通用六条：前缀布局、AGENTS.md 规则、推理降档、子 Agent 廉价模型、压缩阈值、.codexignore；
- 阶段二 各提供商缓存：Claude 显式 cache_control（含协议、请求体、usage 口径）、DeepSeek／Qwen
  前缀字节级稳定、Seedance 固定前缀、GPT 前缀门槛；
- 阶段三 ClawMux：压缩在路由之前、配置能写盘、路由表检得出来；
- 阶段四 CC Switch：四家地址（火山那条别写错）与本地路由环境变量；
- 阶段五 验证：命中率怎么读、速查表与八条注意事项。

另加两组「接上了没有」的用例：真发请求那一路（model_router／model_pool）与设置页那一格。
运行：python test_token_saver.py
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import codex_tasks
import model_pool
import model_router
import pet_agent
import pet_llm
import pet_settings_ui
import pet_ui
import token_saver

import selftest_sandbox

selftest_sandbox.isolate(pet_ui, model_pool, pet_agent)


class Fake:
    """假传输：记下每一次请求，按剧本回话（与真网络无关）。"""

    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.calls = []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append({'url': url, 'payload': payload, 'headers': headers})
        if self.replies:
            return self.replies.pop(0)
        return {'ok': True, 'status': 200, 'data': {}}


# ── 阶段一 ·【通用原则 1】统一前缀布局 ───────────────────────────────────────
class LayoutTests(unittest.TestCase):

    def test_fixed_content_always_comes_first(self):
        messages = token_saver.layout_messages(
            fixed=['固定前缀'], history=[{'role': 'assistant', 'content': '上文'}], current='当前任务')
        self.assertEqual([item['role'] for item in messages], ['system', 'assistant', 'user'])
        self.assertEqual(messages[0]['content'], '固定前缀')
        self.assertEqual(messages[-1]['content'], '当前任务')

    def test_empty_fixed_pieces_are_dropped_and_a_missing_task_is_omitted(self):
        self.assertEqual(token_saver.layout_messages(fixed=['好', ''], current=None),
                         [{'role': 'system', 'content': '好'}])

    def test_two_fixed_prefixes_keep_their_order(self):
        messages = token_saver.layout_messages(fixed=['人设', '快照'], current='做')
        self.assertEqual([item['content'] for item in messages], ['人设', '快照', '做'])

    def test_the_fingerprint_is_stable_and_moves_when_the_text_moves(self):
        self.assertEqual(token_saver.prefix_fingerprint('人设'), token_saver.prefix_fingerprint('人设'))
        self.assertNotEqual(token_saver.prefix_fingerprint('人设'), token_saver.prefix_fingerprint('人设 '))

    def test_a_prefix_with_a_clock_or_a_random_id_is_not_stable(self):
        self.assertTrue(token_saver.has_dynamic('2026-09-23 12:11 生成'))
        self.assertTrue(token_saver.has_dynamic('批次 1727000000'))
        self.assertTrue(token_saver.has_dynamic('id=3f2504e0-4f89-11d3-9a0c-0305e82c3301'))
        self.assertTrue(token_saver.has_dynamic('用 uuid4 生成'))
        self.assertFalse(token_saver.is_stable(''))
        self.assertTrue(token_saver.is_stable('人设：三虎，说话简洁'))

    def test_the_pet_client_builds_its_messages_through_the_same_helper(self):
        payload = pet_llm.build_payload('intent.route', '继续', context={'stage': 'keyframe'})
        expected = token_saver.layout_messages(
            fixed=[pet_llm.SYSTEM_PREFIX,
                   '项目快照：' + json.dumps({'stage': 'keyframe'}, ensure_ascii=False, sort_keys=True)],
            current='继续')
        self.assertEqual(payload['messages'], expected)

    def test_both_fixed_prefixes_the_pet_ships_are_cache_safe(self):
        for prefix in (pet_llm.SYSTEM_PREFIX, pet_llm.CHAT_PREFIX):
            self.assertTrue(token_saver.is_stable(prefix), prefix[:20])


# ── 阶段一 ·【通用原则 2】AGENTS.md 只回结论 ─────────────────────────────────
class AgentsRuleTests(unittest.TestCase):

    def test_the_section_carries_the_five_rules_the_attachment_writes(self):
        section = token_saver.agents_section()
        self.assertIn(token_saver.AGENTS_HEADING, section)
        for snippet in ('head -c 6000', '文件:行号', '结论（1-3 行）', '精确路径', '结构化摘要'):
            self.assertIn(snippet, section)
        self.assertEqual(len(token_saver.AGENTS_RULES), 5)

    def test_merging_is_idempotent_and_keeps_what_the_user_wrote(self):
        once = token_saver.merge_agents('# 我的项目\n\n随手写两句。\n')
        self.assertIn('随手写两句。', once)
        self.assertIn(token_saver.AGENTS_HEADING, once)
        self.assertEqual(token_saver.merge_agents(once), once)

    def test_an_empty_file_gets_just_the_rules(self):
        self.assertEqual(token_saver.merge_agents(''), token_saver.agents_section())
        self.assertEqual(token_saver.merge_agents(None), token_saver.agents_section())

# ── 阶段一 ·【通用原则 3】推理强度降档 ───────────────────────────────────────
class ReasoningTests(unittest.TestCase):

    def test_the_six_strengths_are_all_known_and_explained(self):
        self.assertEqual(token_saver.REASONING_EFFORTS,
                         ('none', 'minimal', 'low', 'medium', 'high', 'xhigh'))
        for effort in token_saver.REASONING_EFFORTS:
            self.assertTrue(token_saver.REASONING_SAVING.get(effort))
        self.assertIn('省 40-50%', token_saver.REASONING_SAVING['low'])
        self.assertIn('多花', token_saver.REASONING_SAVING['high'])

    def test_the_shipped_lines_are_low_none_low(self):
        self.assertEqual(token_saver.config_lines(),
                         ('model_reasoning_effort = "low"', 'model_reasoning_summary = "none"',
                          'model_verbosity = "low"', 'model_context_window = 128000',
                          'model_auto_compact_token_limit = 90000'))

    def test_an_unknown_strength_falls_back_to_low(self):
        table = token_saver.normalize({'model_reasoning_effort': '超强', 'model_verbosity': '啰嗦'})
        self.assertEqual(table['model_reasoning_effort'], 'low')
        self.assertEqual(table['model_verbosity'], 'low')
        self.assertEqual(table['model_reasoning_summary'], 'none')

    def test_merging_replaces_only_the_known_keys_at_the_top(self):
        original = 'model_reasoning_effort = "high"\n[profiles.x]\nmodel_verbosity = "high"\n'
        merged = token_saver.merge_config(original, {'model_reasoning_effort': 'minimal'})
        self.assertIn('model_reasoning_effort = "minimal"', merged)
        self.assertIn('[profiles.x]', merged)
        self.assertIn('model_verbosity = "high"', merged)
        self.assertEqual(token_saver.merge_config(merged, {'model_reasoning_effort': 'minimal'}), merged)

    def test_the_reader_takes_back_the_five_keys(self):
        found = token_saver.config_values('\n'.join(token_saver.config_lines()))
        self.assertEqual(found['model_reasoning_effort'], 'low')
        self.assertEqual(found['model_context_window'], '128000')


# ── 阶段一 ·【通用原则 4】子 Agent 切换廉价模型 ──────────────────────────────
class SubagentEnvTests(unittest.TestCase):

    def test_the_two_variables_are_the_ones_the_attachment_names(self):
        self.assertEqual(token_saver.subagent_env(),
                         {'CODEX_CODE_SUBAGENT_MODEL': 'fast', 'MAX_THINKING_TOKENS': '10000'})
        self.assertEqual(token_saver.SUBAGENT_ENV_KEYS, ('CODEX_CODE_SUBAGENT_MODEL', 'MAX_THINKING_TOKENS'))

    def test_the_saved_numbers_win_over_the_shipped_ones(self):
        env = token_saver.subagent_env({'subagent_model': 'cheap', 'max_thinking_tokens': 4096})
        self.assertEqual(env['CODEX_CODE_SUBAGENT_MODEL'], 'cheap')
        self.assertEqual(env['MAX_THINKING_TOKENS'], '4096')

    def test_the_codex_task_child_process_gets_them(self):
        with tempfile.TemporaryDirectory() as td:
            env = codex_tasks.RPC(program=td).environment()
        self.assertEqual(env['CODEX_CODE_SUBAGENT_MODEL'], 'fast')
        self.assertEqual(env['MAX_THINKING_TOKENS'], '10000')

    def test_a_setting_from_the_token_page_reaches_the_child_process(self):
        with tempfile.TemporaryDirectory() as td:
            pet_agent.save_settings({'token': {'subagent_model': 'qwen-turbo', 'max_thinking_tokens': 2048}}, td)
            env = codex_tasks.RPC(program=td).environment()
        self.assertEqual(env['CODEX_CODE_SUBAGENT_MODEL'], 'qwen-turbo')
        self.assertEqual(env['MAX_THINKING_TOKENS'], '2048')

    def test_a_broken_config_still_hands_over_the_shipped_pair(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / '配置' / '宠物').mkdir(parents=True)
            (Path(td) / '配置' / '宠物' / '配置.json').write_text('{ 坏掉的', encoding='utf-8')
            env = codex_tasks.RPC(program=td).environment()
        self.assertEqual(env['CODEX_CODE_SUBAGENT_MODEL'], 'fast')

    def test_the_parallel_advice_caps_at_two(self):
        self.assertEqual(token_saver.SUBAGENT_LIMIT, 2)
        self.assertIn('压到 2 个以内', token_saver.parallel_advice(5))
        self.assertIn('合适', token_saver.parallel_advice(2))
        self.assertEqual(token_saver.normalize({'subagent_limit': 9})['subagent_limit'], 2)


# ── 阶段一 ·【通用原则 5】自动压缩阈值 ───────────────────────────────────────
class CompactTests(unittest.TestCase):

    def test_seventy_percent_of_the_window_is_the_recommendation(self):
        self.assertEqual(token_saver.COMPACT_RATIO, 0.7)
        self.assertEqual(token_saver.compact_limit(128000), 89600)

    def test_the_limit_can_only_be_lowered_never_raised(self):
        table = token_saver.normalize({'model_context_window': 128000,
                                       'model_auto_compact_token_limit': 200000})
        self.assertEqual(table['model_auto_compact_token_limit'], 115200)
        self.assertEqual(token_saver.COMPACT_CEILING, 0.9)

    def test_a_lower_limit_is_kept_as_asked(self):
        table = token_saver.normalize({'model_context_window': 128000,
                                       'model_auto_compact_token_limit': 40000})
        self.assertEqual(table['model_auto_compact_token_limit'], 40000)

    def test_a_small_window_gets_proportionally_clamped(self):
        table = token_saver.normalize({'model_context_window': 32000,
                                       'model_auto_compact_token_limit': 90000})
        self.assertEqual(table['model_auto_compact_token_limit'], 28800)

    def test_a_silly_window_or_limit_falls_back(self):
        table = token_saver.normalize({'model_context_window': '零', 'model_auto_compact_token_limit': -5})
        self.assertEqual(table['model_context_window'], 128000)
        self.assertEqual(table['model_auto_compact_token_limit'], 90000)


# ── 阶段一 ·【通用原则 6】项目级 .codexignore ────────────────────────────────
class IgnoreTests(unittest.TestCase):

    def test_the_shipped_list_covers_the_two_play_asset_folders(self):
        text = token_saver.codexignore_text()
        for pattern in ('assets/raw/', 'renders/', 'node_modules/', '*.log', '__snapshots__/'):
            self.assertIn(pattern, text)

    def test_merging_only_adds_what_is_missing(self):
        merged = token_saver.merge_codexignore('# 我自己加的\nlogs/\n')
        self.assertIn('logs/', merged)
        self.assertIn('renders/', merged)
        self.assertEqual(merged.count('renders/'), 1)
        self.assertEqual(token_saver.merge_codexignore(merged), merged)

    def test_an_absent_file_becomes_the_whole_list(self):
        self.assertEqual(token_saver.merge_codexignore(''), token_saver.codexignore_text())

# ── 阶段二 · Claude 显式缓存 ─────────────────────────────────────────────────
class AnthropicCacheTests(unittest.TestCase):

    def test_the_marker_is_an_ephemeral_breakpoint(self):
        self.assertEqual(token_saver.cache_control(), {'type': 'ephemeral'})
        self.assertEqual(token_saver.cache_control('1h'), {'type': 'ephemeral', 'ttl': '1h'})
        self.assertEqual(token_saver.CACHE_TTLS, ('5m', '1h'))

    def test_the_request_body_marks_the_cache_at_the_top(self):
        body = token_saver.anthropic_payload('claude-opus-5', '人设', [{'role': 'user', 'content': '做'}])
        self.assertEqual(body['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(body['system'], '人设')
        self.assertEqual(body['max_tokens'], 1024)
        self.assertEqual(body['messages'], [{'role': 'user', 'content': '做'}])

    def test_the_usage_reads_claudes_own_field_names(self):
        usage = token_saver.anthropic_usage({'usage': {'input_tokens': 12, 'output_tokens': 3,
                                                       'cache_read_input_tokens': 9,
                                                       'cache_creation_input_tokens': 4}})
        self.assertEqual(usage, {'prompt_tokens': 12, 'completion_tokens': 3, 'cached_tokens': 9,
                                 'cache_creation_tokens': 4})
        self.assertEqual(token_saver.anthropic_usage(None)['cached_tokens'], 0)

    def test_the_text_comes_out_of_the_content_blocks(self):
        self.assertEqual(token_saver.anthropic_text({'content': [{'type': 'text', 'text': '你好'}]}), '你好')
        self.assertEqual(token_saver.anthropic_text(None), '')

    def test_the_text_falls_back_to_an_openai_shaped_gateway_response(self):
        response = {'content': [{'type': 'thinking', 'thinking': 'hidden'}],
                    'choices': [{'message': {'content': '网关正文'}}]}
        self.assertEqual(token_saver.anthropic_text(response), '网关正文')

    def test_the_five_providers_each_have_a_cache_note(self):
        modes = dict((row[0], row[1]) for row in token_saver.CACHE_MODES)
        self.assertEqual(list(modes), ['Claude', 'Qwen', 'DeepSeek', 'Seedance', 'GPT'])
        self.assertIn('显式', modes['Claude'])

    def test_the_pool_sends_anthropic_records_to_the_native_wire(self):
        self.assertEqual(model_pool.wire_for_provider('anthropic'), 'messages')
        self.assertIn('messages', model_pool.WIRE_LABELS)
        for provider, _label in model_pool.PROVIDERS:
            self.assertIn(model_pool.wire_for_provider(provider), model_pool.WIRE_LABELS)

    def test_the_connection_test_uses_the_anthropic_shape(self):
        with tempfile.TemporaryDirectory() as td:
            # 该用例验证传入临时程序目录的 DPAPI 记录；不能让开发机的真实环境变量盖掉它。
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('DEEPSEEK_API_KEY', None)
                model_pool.save_named_key('DEEPSEEK_API_KEY', 'sk-test-0', td)
                fake = Fake()
                result = model_pool.probe(model_pool.record({'model': 'claude-opus-5',
                                                             'base_url': 'https://api.anthropic.com',
                                                             'provider': 'anthropic', 'wire_api': 'messages',
                                                             'key_env': 'DEEPSEEK_API_KEY'}), fake, td)
        self.assertTrue(result['ok'])
        self.assertEqual(fake.calls[0]['url'], 'https://api.anthropic.com/v1/messages')
        self.assertEqual(fake.calls[0]['headers']['x-api-key'], 'sk-test-0')
        self.assertEqual(fake.calls[0]['headers']['anthropic-version'], token_saver.ANTHROPIC_VERSION)
        self.assertEqual(fake.calls[0]['payload']['max_tokens'], model_pool.PROBE_TOKENS)


# ── 阶段一＋二 · 真发请求那一路也照前缀布局走 ────────────────────────────────
class RouterPrefixTests(unittest.TestCase):

    def adapter(self, wire='chat'):
        item = model_router.ModelAdapter(program=HERE, transport=Fake(), key='sk-test')
        item.base_url = 'https://x.test/v1'
        item.path = '/chat/completions'
        item.wire_api = wire
        item.models = {'m': {'capabilities': (), 'cost': 1}}
        return item

    def test_the_system_prefix_sits_at_the_very_front(self):
        body = self.adapter().payload('m', [{'role': 'user', 'content': '任务'}], None, '固定前缀')
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': '固定前缀'})
        self.assertEqual(body['messages'][1]['content'], '任务')

    def test_no_system_means_no_extra_message(self):
        self.assertEqual(len(self.adapter().payload('m', [{'role': 'user', 'content': '任务'}])['messages']), 1)

    def test_temperature_is_sent_only_when_a_call_explicitly_requests_it(self):
        item = self.adapter()
        plain = item.payload('m', [{'role': 'user', 'content': '任务'}])
        explicit = item.payload('m', [{'role': 'user', 'content': '任务'}], {'temperature': 0.2})
        self.assertNotIn('temperature', plain)
        self.assertEqual(explicit['temperature'], 0.2)

    def test_the_chat_call_carries_the_prefix_and_the_answer_comes_back(self):
        item = self.adapter()
        item.transport = Fake([{'ok': True, 'status': 200,
                                'data': {'choices': [{'message': {'content': '好'}}]}}])
        result = item.chat([{'role': 'user', 'content': '做'}], model='m', system='人设')
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], '好')
        self.assertEqual(item.transport.calls[0]['payload']['messages'][0]['content'], '人设')

    def test_a_read_timeout_returns_a_clear_chinese_message(self):
        item = self.adapter()

        def timeout(*args):
            raise TimeoutError('The read operation timed out')

        item.transport = timeout
        result = item.chat([{'role': 'user', 'content': '做'}], model='m')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], '模型响应超时，请稍后重试或切换更快模型。')

    def test_an_anthropic_adapter_marks_the_cache_and_reads_its_own_usage(self):
        item = self.adapter('messages')
        item.transport = Fake([{'ok': True, 'status': 200,
                                'data': {'content': [{'type': 'text', 'text': '你好'}],
                                         'usage': {'input_tokens': 10, 'output_tokens': 2,
                                                   'cache_read_input_tokens': 8,
                                                   'cache_creation_input_tokens': 0}}}])
        result = item.chat([{'role': 'user', 'content': '做'}], model='m', system='人设')
        self.assertEqual(result['text'], '你好')
        self.assertEqual(result['usage'], {'prompt_tokens': 10, 'completion_tokens': 2, 'cached_tokens': 8})
        body = item.transport.calls[0]['payload']
        self.assertEqual(body['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(body['system'], '人设')
        self.assertEqual(item.transport.calls[0]['url'], 'https://x.test/v1/messages')

    def test_the_hit_lands_in_the_ledger(self):
        item = self.adapter('messages')
        item.transport = Fake([{'ok': True, 'status': 200,
                                'data': {'content': [{'type': 'text', 'text': '好'}],
                                         'usage': {'input_tokens': 100, 'output_tokens': 2,
                                                   'cache_read_input_tokens': 80}}}])
        router = model_router.ModelRouter(adapters=[item], ledger=pet_llm.Ledger())
        choice = model_router.Choice('m', item, '用例指定', '', (), 1, 'tokens')
        router.chat(choice, [{'role': 'user', 'content': '做'}])
        self.assertEqual(router.ledger.hit_rate(), 0.8)

    def test_a_named_claude_adapter_is_available_without_the_pool(self):
        self.assertEqual(model_router.AnthropicAdapter.wire_api, 'messages')
        self.assertIn('claude-opus-5', model_router.AnthropicAdapter.models)
        self.assertEqual(model_router.AnthropicAdapter.key_env, 'ANTHROPIC_API_KEY')

    def test_the_pet_client_reads_claudes_cache_field_too(self):
        usage = pet_llm.usage_of({'data': {'usage': {'input_tokens': 12, 'output_tokens': 3,
                                                     'cache_read_input_tokens': 9}}})
        self.assertEqual(usage, {'prompt_tokens': 12, 'completion_tokens': 3, 'cached_tokens': 9})


# ── 阶段二 · Seedance 固定前缀 ──────────────────────────────────────────────
class SeedanceTests(unittest.TestCase):

    def test_the_three_fixed_pieces_keep_their_order(self):
        text = token_saver.seedance_prefix(style='日系动画，赛璐璐上色', characters=['三虎', '小满'],
                                           camera='特写多用，避免大远景')
        self.assertEqual(text.split('\n'), ['画风定义：日系动画，赛璐璐上色',
                                            '角色参考图描述：三虎、小满',
                                            '镜头语言偏好：特写多用，避免大远景'])

    def test_the_same_input_gives_the_same_bytes(self):
        twice = [token_saver.seedance_prefix(style='日系', characters=['三虎'], camera='特写') for _ in range(2)]
        self.assertEqual(token_saver.prefix_fingerprint(twice[0]), token_saver.prefix_fingerprint(twice[1]))

    def test_missing_pieces_are_simply_left_out(self):
        self.assertEqual(token_saver.seedance_prefix(style='日系'), '画风定义：日系')
        self.assertEqual(token_saver.seedance_prefix(), '')

# ── 阶段三 · ClawMux：压缩在路由之前 ───────────────────────────────────────
class ClawMuxTests(unittest.TestCase):

    def test_the_configuration_matches_the_attachment(self):
        table = token_saver.clawmux_config()
        self.assertEqual(table['compression'], {'threshold': 0.75, 'model': 'zai/glm-5-turbo',
                                                'targetRatio': 0.6})
        self.assertEqual(table['server'], {'port': 3456, 'host': '127.0.0.1'})
        self.assertEqual(table['routing']['models'], {'LIGHT': 'zai/glm-5-turbo',
                                                      'MEDIUM': 'anthropic/claude-sonnet-4.5',
                                                      'HEAVY': 'openai/gpt-5.4'})

    def test_the_written_file_is_byte_stable(self):
        self.assertEqual(token_saver.clawmux_json(), token_saver.clawmux_json())
        self.assertTrue(token_saver.clawmux_json().endswith('\n'))

    def test_the_three_tiers_are_the_three_that_are_registered(self):
        self.assertEqual(token_saver.CLAWMUX_TIERS, ('LIGHT', 'MEDIUM', 'HEAVY'))
        table = token_saver.clawmux_config(models={'light': 'zai/glm-5-turbo'})
        self.assertEqual(table['routing']['models']['LIGHT'], 'zai/glm-5-turbo')

    def test_the_routing_table_is_checked_for_the_three_known_traps(self):
        self.assertEqual(token_saver.routing_problems(), ())
        broken = token_saver.clawmux_config(models={'LIGHT': 'clawmux/auto', 'MEDIUM': 'nope'})
        problems = token_saver.routing_problems(broken)
        self.assertTrue(any('无限循环' in line for line in problems))
        self.assertTrue(any('provider/model' in line for line in problems))
        self.assertTrue(any('还没配模型' in line
                            for line in token_saver.routing_problems({'routing': {'models': {}}})))

    def test_compression_runs_before_the_route_against_the_smallest_window(self):
        self.assertEqual(token_saver.COMPRESS_HARD_RATIO, 0.9)
        self.assertEqual(token_saver.compression_limit([128000, 32000]), 28800)
        self.assertEqual(token_saver.compression_limit([128000]), 115200)
        self.assertEqual(token_saver.compression_limit([]), 0)

    def test_the_health_check_and_the_four_steps(self):
        self.assertEqual(token_saver.health_url(), 'http://127.0.0.1:3456/health')
        self.assertEqual(token_saver.health_url(4000), 'http://127.0.0.1:4000/health')
        steps = token_saver.clawmux_steps()
        self.assertEqual(steps[0], 'npm install -g clawmux')
        self.assertEqual(steps[1], 'clawmux init')
        self.assertIn('~/.openclaw/clawmux.json', steps[2])


# ── 阶段四 · CC Switch 多 Provider 管理 ────────────────────────────────────
class SwitchTests(unittest.TestCase):

    def test_the_four_providers_are_listed_with_their_addresses(self):
        rows = token_saver.provider_rows()
        self.assertEqual(len(rows), 4)
        urls = [row[1] for row in rows]
        for url in ('https://ark.cn-beijing.volces.com/api/plan/v3', 'https://api.anthropic.com',
                    'https://dashscope.aliyuncs.com/compatible-mode/v1', 'https://api.openai.com'):
            self.assertIn(url, urls)

    def test_the_volcano_address_may_not_be_written_wrong(self):
        self.assertTrue(token_saver.url_ok('https://ark.cn-beijing.volces.com/api/plan/v3'))
        self.assertFalse(token_saver.url_ok('https://ark.cn-beijing.volces.com/api/coding/v3'))
        self.assertFalse(token_saver.url_ok('https://ark.cn-beijing.volces.com/api/v3'))
        self.assertFalse(token_saver.url_ok(''))

    def test_the_local_route_hides_the_token_behind_a_local_address(self):
        self.assertEqual(token_saver.LOCAL_ROUTE_ENV, {'ANTHROPIC_AUTH_TOKEN': 'PROXY_MANAGED',
                                                       'ANTHROPIC_BASE_URL': 'http://127.0.0.1:15721'})


# ── 阶段五 · 验证与监控 ─────────────────────────────────────────────────────
class VerifyTests(unittest.TestCase):

    def test_the_hit_rate_line_calls_out_the_seventy_percent_target(self):
        self.assertIn('90%', token_saver.hit_rate_line(0.9))
        self.assertIn('达标', token_saver.hit_rate_line(0.9))
        self.assertNotIn('达标', token_saver.hit_rate_line(0.5))
        self.assertIn('0%', token_saver.hit_rate_line(0))

    def test_the_cache_sentence_counts_the_share(self):
        said = token_saver.cache_hit_sentence({'prompt_tokens': 100, 'cached_tokens': 80})
        self.assertIn('100', said)
        self.assertIn('80', said)
        self.assertIn('80%', said)
        self.assertIn('没报用量', token_saver.cache_hit_sentence({}))

    def test_the_six_things_to_watch_are_all_listed(self):
        self.assertEqual(len(token_saver.VERIFY_STEPS), 6)
        text = '\n'.join('%s %s' % pair for pair in token_saver.VERIFY_STEPS)
        for snippet in ('/cost', 'cache_info', '/stats', 'cache_read_input_tokens', 'ClawMux', 'CC Switch'):
            self.assertIn(snippet, text)


# ── 速查表与注意事项 ────────────────────────────────────────────────────────
class SpeedTableTests(unittest.TestCase):

    def test_the_ten_rows_are_in_priority_order(self):
        self.assertEqual([row[0] for row in token_saver.SPEED_TABLE], list(range(1, 11)))
        self.assertEqual(token_saver.SPEED_TABLE[0][1], '统一前缀布局')
        self.assertIn('70%', token_saver.SPEED_TABLE[0][2])
        self.assertIn('fast', token_saver.SPEED_TABLE[2][1])

    def test_the_aligned_text_starts_with_the_four_headers(self):
        lines = token_saver.speed_table_text()
        self.assertEqual(len(lines), 11)
        self.assertEqual([cell.strip() for cell in lines[0].split('|')],
                         ['优先级', '优化项', '预期节省', '适用模型'])

    def test_the_eight_notes_are_kept_verbatim(self):
        self.assertEqual(len(token_saver.NOTES), 8)
        whole = '\n'.join(token_saver.NOTES)
        for snippet in ('/api/plan/v3', '不标记等于放弃 90% 折扣', 'API Key 认证', '路由之前',
                        '2 个以内', '只能调低不能调高', '不中途切换模型', 'RUST_LOG=codex_core=warn'):
            self.assertIn(snippet, whole)

# ── 写盘：项目级三份 ＋ 全局一份 ＋ 阶段零扫描 ──────────────────────────────
class ApplyTests(unittest.TestCase):

    def test_a_project_gets_the_three_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'p'
            root.mkdir()
            written = token_saver.deliver_project(root, {'model_reasoning_effort': 'minimal'})
            self.assertEqual(len(written), 3)
            self.assertIn(token_saver.AGENTS_HEADING, (root / 'AGENTS.md').read_text(encoding='utf-8'))
            self.assertIn('renders/', (root / '.codexignore').read_text(encoding='utf-8'))
            self.assertIn('model_reasoning_effort = "minimal"',
                          (root / '.codex' / 'config.toml').read_text(encoding='utf-8'))

    def test_delivering_twice_changes_nothing_the_second_time(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'p'
            root.mkdir()
            token_saver.deliver_project(root)
            first = [(path, path.read_text(encoding='utf-8')) for path in token_saver.deliver_project(root)]
            second = [(path, path.read_text(encoding='utf-8')) for path in token_saver.deliver_project(root)]
            self.assertEqual(first, second)

    def test_a_project_file_that_already_has_rules_is_left_alone(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'p'
            root.mkdir()
            (root / 'AGENTS.md').write_text('# 我的\n\n' + token_saver.agents_section(), encoding='utf-8')
            token_saver.deliver_project(root)
            self.assertEqual((root / 'AGENTS.md').read_text(encoding='utf-8'),
                             '# 我的\n\n' + token_saver.agents_section())

    def test_the_global_file_lands_in_the_codex_home(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'home'
            path = token_saver.deliver_global(home=target)
            self.assertEqual(path, target / 'config.toml')
            self.assertIn('model_auto_compact_token_limit', path.read_text(encoding='utf-8'))

    def test_the_codex_home_follows_the_environment_variable(self):
        before = os.environ.get('CODEX_HOME')
        self.addCleanup(self.restore_home, before)
        os.environ['CODEX_HOME'] = os.path.join(HERE, '.selftmp-token-home')
        self.assertEqual(token_saver.codex_home(), Path(HERE) / '.selftmp-token-home')
        self.assertEqual(token_saver.codex_home(home='D:/elsewhere'), Path('D:/elsewhere'))

    @staticmethod
    def restore_home(before):
        if before is None:
            os.environ.pop('CODEX_HOME', None)
        else:
            os.environ['CODEX_HOME'] = before

    def test_the_scan_reports_what_is_still_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'p'
            root.mkdir()
            home = Path(td) / 'home'
            bare = token_saver.scan(project=root, home=home)
            self.assertFalse(bare['agents'])
            self.assertEqual(len(bare['ignore_missing']), len(token_saver.IGNORE_PATTERNS))
            self.assertEqual(bare['config_keys'], ())
            token_saver.deliver_project(root)
            done = token_saver.scan(project=root, home=home)
            self.assertTrue(done['agents_rules'])
            self.assertEqual(done['ignore_missing'], ())

    def test_the_scan_reads_the_environment_pair(self):
        report = token_saver.scan(environ={'CODEX_CODE_SUBAGENT_MODEL': 'fast'})
        self.assertEqual(report['subagent_env']['CODEX_CODE_SUBAGENT_MODEL'], 'fast')
        lines = token_saver.scan_lines(report)
        self.assertTrue(lines)
        self.assertIn('fast', '\n'.join(lines))

    def test_the_preview_shows_every_file_it_would_write(self):
        text = token_saver.preview_text()
        for snippet in ('AGENTS.md', '.codexignore', '.codex/config.toml', 'clawmux.json', 'renders/'):
            self.assertIn(snippet, text)


# ── 设置页那一格 ───────────────────────────────────────────────────────────
class FakePet:
    """够 token_page 用的一只假三虎：项目根、全局配置目录、存读那八档。"""

    def __init__(self, program, project=None, home=None):
        self.program = Path(program)
        self.project = Path(project) if project else None
        self.codex_home = Path(home) if home else None
        self.errors = []

    def token_settings(self):
        return token_saver.normalize(pet_agent.load_settings(program=self.program).get('token') or {})

    def set_token_settings(self, values):
        table = token_saver.normalize(values)
        pet_agent.save_settings({'token': table}, self.program)
        return table


class SettingsTabTests(unittest.TestCase):

    def test_the_token_page_sits_between_the_level_and_the_budget(self):
        keys = [key for key, _title in pet_settings_ui.TABS]
        self.assertIn('token', keys)
        self.assertLess(keys.index('level'), keys.index('token'))
        self.assertLess(keys.index('token'), keys.index('budget'))
        self.assertEqual(dict(pet_settings_ui.TABS)['token'], pet_settings_ui.TOKEN_TITLE)

    def test_the_gear_and_the_right_click_menu_still_share_one_table(self):
        self.assertEqual(pet_ui.SETTINGS_ENTRIES, tuple(pet_settings_ui.TABS))

    def test_the_hub_note_lists_the_new_page(self):
        self.assertIn(pet_settings_ui.TOKEN_TITLE, pet_settings_ui.NOTE_HUB)


class TokenPageTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            from tkinter import ttk
            cls.tk, cls.ttk = tk, ttk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest('tkinter 不可用')
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = Path(self.tmp.name) / 'program'
        self.project = Path(self.tmp.name) / 'p'
        self.project.mkdir(parents=True)
        self.home = Path(self.tmp.name) / 'home'
        self.pet = FakePet(self.program, self.project, self.home)

    def page(self, pet=None):
        frame = self.tk.Frame(self.win)
        return frame, pet_settings_ui.token_page(frame, pet or self.pet)

    def walk(self, widget, kind):
        found = []
        if isinstance(widget, kind):
            found.append(widget)
        for child in widget.winfo_children():
            found.extend(self.walk(child, kind))
        return found

    def test_the_page_starts_on_the_shipped_numbers(self):
        _frame, seams = self.page()
        fields = seams['fields']
        self.assertEqual(fields['model_reasoning_effort'].get(), 'low')
        self.assertEqual(fields['model_context_window'].get(), '128000')
        self.assertEqual(fields['model_auto_compact_token_limit'].get(), '90000')
        self.assertEqual(fields['subagent_model'].get(), 'fast')
        self.assertEqual(fields['subagent_limit'].get(), '2')

    def test_the_page_does_not_borrow_the_model_pages_drop_downs(self):
        frame, _seams = self.page()
        self.assertEqual(self.walk(frame, self.ttk.Combobox), [])

    def test_the_four_buttons_are_all_there(self):
        frame, _seams = self.page()
        texts = [str(button.cget('text')) for button in self.walk(frame, self.ttk.Button)]
        for label in ('保存', '恢复默认', '写入项目', '写入全局'):
            self.assertIn(label, texts)

    def test_saving_writes_the_eight_numbers_into_the_global_config(self):
        _frame, seams = self.page()
        seams['fields']['model_reasoning_effort'].set('minimal')
        table = seams['save']()
        self.assertEqual(table['model_reasoning_effort'], 'minimal')
        self.assertEqual(pet_agent.load_settings(program=self.program)['token']['model_reasoning_effort'],
                         'minimal')
        self.assertEqual(pet_settings_ui.token_seed(self.pet)['model_reasoning_effort'], 'minimal')

    def test_a_silly_number_is_clamped_before_it_is_saved(self):
        _frame, seams = self.page()
        seams['fields']['model_auto_compact_token_limit'].set('999999')
        table = seams['save']()
        self.assertEqual(table['model_auto_compact_token_limit'], 115200)
        self.assertEqual(seams['fields']['model_auto_compact_token_limit'].get(), '115200')

    def test_an_unknown_strength_falls_back_and_the_note_says_the_saving(self):
        _frame, seams = self.page()
        seams['fields']['model_reasoning_effort'].set('飞快')
        seams['save']()
        self.assertEqual(seams['fields']['model_reasoning_effort'].get(), 'low')
        self.assertIn('省 40-50%', seams['note'].get())

    def test_restoring_fills_the_shipped_numbers_back(self):
        _frame, seams = self.page()
        seams['fields']['model_context_window'].set('32000')
        seams['save']()
        seams['restore']()
        self.assertEqual(seams['fields']['model_context_window'].get(), '128000')
        self.assertIn('出厂', seams['hint'].get())

    def test_writing_the_project_lands_the_three_files_and_reports_them(self):
        _frame, seams = self.page()
        self.assertEqual(len(seams['write_project']()), 3)
        self.assertTrue((self.project / 'AGENTS.md').is_file())
        self.assertTrue((self.project / '.codexignore').is_file())
        self.assertTrue((self.project / '.codex' / 'config.toml').is_file())
        self.assertIn('已写进项目', seams['hint'].get())

    def test_writing_without_a_project_says_so_instead_of_crashing(self):
        _frame, seams = self.page(FakePet(self.program, None, self.home))
        self.assertEqual(seams['write_project'](), ())
        self.assertIn('还没打开项目', seams['hint'].get())

    def test_writing_the_global_config_lands_in_the_codex_home(self):
        _frame, seams = self.page()
        path = seams['write_global']()
        self.assertEqual(path, self.home / 'config.toml')
        self.assertTrue(path.is_file())
        self.assertIn('model_context_window', path.read_text(encoding='utf-8'))
        self.assertIn('已写进全局配置', seams['hint'].get())

    def test_the_preview_pane_shows_the_files_that_would_be_written(self):
        _frame, seams = self.page()
        body = seams['text'].get('1.0', 'end')
        self.assertIn(token_saver.AGENTS_HEADING, body)
        self.assertIn('.codexignore', body)
        self.assertIn('clawmux.json', body)

    def test_the_state_line_reads_the_current_configuration(self):
        _frame, seams = self.page()
        self.assertIn('推理强度', seams['state'].get())
        self.assertIn('子 Agent', seams['state'].get())


if __name__ == '__main__':
    unittest.main(verbosity=2)
