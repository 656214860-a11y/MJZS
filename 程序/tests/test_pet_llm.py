# -*- coding: utf-8 -*-
"""DeepSeek 客户端自检：缓存优先前缀、压缩、路由与降级、输出限制、错峰、台账。运行：python test_pet_llm.py"""
import json, os, ssl, sys, tempfile, unittest
import urllib.error
from unittest import mock
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import model_secrets
import pet_agent
import pet_bus
import infra.pet_llm as pet_llm
from infra.pet_llm import Client, Ledger, Queue, choose, compress, load_config, model_for


class Fake:
    """假传输：按顺序回放结果，并记下每次真实发出去的请求。"""
    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.calls = []
    def __call__(self, url, payload, headers, timeout):
        self.calls.append({'url': url, 'payload': payload, 'headers': headers, 'timeout': timeout})
        if self.replies:
            return self.replies.pop(0)
        return {'ok': True, 'status': 200, 'data': {'usage': {'prompt_tokens': 10, 'completion_tokens': 2,
                                                              'prompt_cache_hit_tokens': 8}}}


def env_dir(td, key='sk-test-123456'):
    (Path(td) / '.env').write_text('DEEPSEEK_API_KEY=' + key + '\n', encoding='utf-8')
    return Path(td)


class CredentialTests(unittest.TestCase):
    """密钥的判据只有一处：.env 与同名环境变量都没有时，才用本机加密存的那把。

    规格（模型管理）里两种放法在这里合流——界面说这个模型能用，这条链就得找得到同一把钥匙。
    """

    def setUp(self):
        self.original_protector = model_secrets.PROTECTOR
        def protector(data, decrypt=False, label=''):
            payload = bytes(data)
            if decrypt:
                if not payload.startswith(b'test:'):
                    raise ValueError('bad test secret')
                return payload[5:][::-1]
            return b'test:' + payload[::-1]
        model_secrets.PROTECTOR = protector

    def tearDown(self):
        model_secrets.PROTECTOR = self.original_protector

    def test_the_local_key_is_the_last_resort(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            os.environ.pop('CODEX_LOCAL_ONLY_KEY', None)
            with self.assertRaises(ValueError):
                pet_llm.credential({'key_env': 'CODEX_LOCAL_ONLY_KEY'}, program)
            model_secrets.save('CODEX_LOCAL_ONLY_KEY', 'sk-local-1', program)
            self.assertEqual(pet_llm.credential({'key_env': 'CODEX_LOCAL_ONLY_KEY'}, program),
                             'sk-local-1')

    def test_the_local_key_wins_over_the_env_file_after_a_new_save(self):
        with tempfile.TemporaryDirectory() as td:
            program = env_dir(td, key='sk-from-env')
            model_secrets.save('DEEPSEEK_API_KEY', 'sk-local-1', program)
            self.assertEqual(pet_llm.credential({'key_env': 'DEEPSEEK_API_KEY'}, program), 'sk-local-1')

    def test_a_broken_local_file_does_not_break_the_call(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            os.environ.pop('CODEX_BROKEN_KEY', None)
            target = model_secrets.path('CODEX_BROKEN_KEY', program)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'not encrypted at all')
            with self.assertRaises(ValueError):
                pet_llm.credential({'key_env': 'CODEX_BROKEN_KEY'}, program)


class ConfigTests(unittest.TestCase):
    def test_defaults_apply_without_a_config_file(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = load_config(program=Path(td))
            self.assertEqual(cfg['base_url'], 'https://api.deepseek.com')
            self.assertEqual(cfg['flash_model'], 'deepseek-v4-flash')
            self.assertEqual(cfg['pro_model'], 'deepseek-v4-pro')
            self.assertFalse(pet_llm.config_path(Path(td)).exists())

    def test_config_file_overrides_known_keys_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = pet_llm.config_path(Path(td)); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'base_url': 'https://example.test', 'model': '不认识的键'}),
                            encoding='utf-8')
            cfg = load_config(program=Path(td))
            self.assertEqual(cfg['base_url'], 'https://example.test')
            self.assertNotIn('model', cfg)

    def test_endpoint_validates_and_follows_wire_api(self):
        chat = {'base_url': 'https://api.deepseek.com', 'wire_api': 'chat'}
        responses = {'base_url': 'https://api.deepseek.com', 'wire_api': 'responses'}
        self.assertEqual(pet_llm.endpoint(chat), 'https://api.deepseek.com/chat/completions')
        self.assertEqual(pet_llm.endpoint(responses), 'https://api.deepseek.com/responses')
        with self.assertRaises(ValueError):
            pet_llm.endpoint({'base_url': 'ftp://api.deepseek.com'})

    def test_wire_api_switch_changes_payload_shape(self):
        text = '继续做首帧'
        chat = pet_llm.build_payload('intent.route', text, config={'wire_api': 'chat'})
        responses = pet_llm.build_payload('intent.route', text, config={'wire_api': 'responses'})
        self.assertIn('messages', chat)
        self.assertIn('input', responses)
        self.assertEqual(chat['messages'], responses['input'])


class CacheFirstTests(unittest.TestCase):
    def test_prefix_is_first_message_and_never_changes(self):
        first = pet_llm.build_payload('intent.route', '继续')
        second = pet_llm.build_payload('progress.summary', '还剩多少', context={'stage': 'video'})
        self.assertEqual(first['messages'][0], {'role': 'system', 'content': pet_llm.SYSTEM_PREFIX})
        self.assertEqual(second['messages'][0], first['messages'][0])
        self.assertNotIn('20', pet_llm.SYSTEM_PREFIX)          # 前缀里不许出现年份/时间戳

    def test_snapshot_is_key_order_stable(self):
        left = pet_llm.build_payload('intent.route', '继续', context={'stage': 'video', 'missing': 3})
        right = pet_llm.build_payload('intent.route', '继续', context={'missing': 3, 'stage': 'video'})
        self.assertEqual(left, right)

    def test_snapshot_is_omitted_when_empty(self):
        payload = pet_llm.build_payload('intent.route', '继续')
        self.assertEqual(len(payload['messages']), 2)
        self.assertEqual(payload['messages'][-1]['role'], 'user')

    def test_user_prompt_is_compressed(self):
        messy = '第一行\n\n第一行\n----------\n第二行'
        payload = pet_llm.build_payload('intent.route', messy)
        self.assertEqual(payload['messages'][-1]['content'], '第一行\n第二行')

    def test_oversized_snapshot_becomes_stable_metadata(self):
        payload = pet_llm.build_payload('intent.route', '继续', context={'script': '剧本' * 10000})
        snapshot = payload['messages'][1]['content']
        self.assertLessEqual(len(snapshot), pet_llm.REQUEST_CONTEXT_MAX_CHARS + len('项目快照：'))
        self.assertIn('"truncated": true', snapshot)
        self.assertIn('"top_level_keys": ["script"]', snapshot)

    def test_oversized_directive_is_limited_before_transport(self):
        payload = pet_llm.build_payload('intent.route', '继续' * 10000)
        self.assertEqual(len(payload['messages'][-1]['content']), pet_llm.REQUEST_DIRECTIVE_MAX_CHARS)


class PersonaTests(unittest.TestCase):
    """第 15 期：猫咪叫三虎——人设写进固定前缀，且前缀依旧不许出现时间戳。"""

    def test_the_pet_is_named_in_the_fixed_prefix(self):
        self.assertIn(pet_agent.PET_NAME, pet_llm.SYSTEM_PREFIX)
        self.assertIn('三虎', pet_llm.SYSTEM_PREFIX)
        self.assertIn('宠物 Agent', pet_llm.SYSTEM_PREFIX)

    def test_the_persona_is_cute_and_short_winded(self):
        self.assertIn('可爱', pet_llm.SYSTEM_PREFIX)
        self.assertIn('简洁', pet_llm.SYSTEM_PREFIX)
        self.assertIn('漫剧', pet_llm.SYSTEM_PREFIX)

    def test_the_prefix_is_still_a_single_stable_message(self):
        payload = pet_llm.build_payload('intent.route', '继续')
        self.assertEqual(payload['messages'][0]['content'], pet_llm.SYSTEM_PREFIX)
        self.assertNotIn('20', pet_llm.SYSTEM_PREFIX)

    def test_the_stage_list_covers_all_thirteen_stages(self):
        self.assertIn('stage 只能是：' + ' '.join(pet_bus.STAGES) + '。', pet_llm.SYSTEM_PREFIX)


class CompressTests(unittest.TestCase):
    def test_repeats_and_decorations_are_dropped(self):
        sample = '\n'.join(['镜头提示词：猫坐在窗边'] * 6 + ['=====', '=====', '光照：傍晚']) + '\n'
        result = compress(sample)
        self.assertEqual(result, '镜头提示词：猫坐在窗边\n光照：傍晚')

    def test_compression_ratio_beats_forty_percent(self):
        block = '参考资产：CHAR_001 主角 / LOC_001 场景 / 风格：厚涂' + '\n'
        original = block * 20 + '指令：继续生成首帧'
        result = compress(original)
        self.assertGreaterEqual(1 - len(result) / len(original), 0.4)

    def test_compress_is_idempotent_and_keeps_unique_lines(self):
        original = '第一行\n第二行\n第一行\n第三行'
        once = compress(original)
        self.assertEqual(compress(once), once)
        for line in ('第一行', '第二行', '第三行'):
            self.assertIn(line, once)

    def test_hard_limit_truncates(self):
        result = compress('短指令' * 100, limit=10)
        self.assertEqual(len(result), 10)

    def test_short_prompt_is_untouched(self):
        self.assertEqual(compress('继续'), '继续')


class RoutingTests(unittest.TestCase):
    def test_only_complex_tasks_use_pro(self):
        for task in pet_llm.PRO_TASKS:
            self.assertEqual(choose(task)[0], 'pro')
        for task in ('intent.route', 'progress.summary', 'shot.prompts', '未登记的任务'):
            self.assertEqual(choose(task)[0], 'flash')

    def test_max_tokens_per_task_and_ceiling(self):
        self.assertEqual(choose('intent.route')[1], 256)
        self.assertEqual(choose('shot.prompts')[1], 1024)
        self.assertEqual(choose('writing.breakdown')[1], 2048)
        self.assertEqual(choose('intent.route', {'max_tokens': {'intent.route': 99999}})[1],
                         pet_llm.MAX_OUTPUT_CEILING)
        self.assertEqual(pet_llm.build_payload('intent.route', '继续')['max_tokens'], 256)

    def test_model_names_come_from_config(self):
        cfg = {'flash_model': 'F', 'pro_model': 'P'}
        self.assertEqual(model_for('flash', cfg), 'F')
        self.assertEqual(model_for('pro', cfg), 'P')


class ForceTierTests(unittest.TestCase):
    """「换模型」按下的档位：压过任务默认，认不出来的值一律忽略。"""

    def test_the_forced_tier_wins_over_the_task_default(self):
        self.assertEqual(choose("writing.breakdown", {"force_tier": "flash"})[0], "flash")
        self.assertEqual(choose("intent.route", {"force_tier": "pro"})[0], "pro")

    def test_an_empty_or_unknown_force_falls_back_to_the_task(self):
        for value in ("", None, "乱写", "pro1", 5):
            with self.subTest(value=value):
                self.assertEqual(choose("intent.route", {"force_tier": value})[0], "flash")
                self.assertEqual(choose("writing.breakdown", {"force_tier": value})[0], "pro")

    def test_case_and_stray_spaces_are_forgiven(self):
        """手写的配置容易多打一个空格或写成大写：认出来就好，不因为格式换错模型。"""
        self.assertEqual(choose("intent.route", {"force_tier": " PRO "})[0], "pro")
        self.assertEqual(choose("writing.breakdown", {"force_tier": "Flash"})[0], "flash")

    def test_the_payload_carries_the_forced_model(self):
        payload = pet_llm.build_payload("intent.route", "继续", config={"force_tier": "pro"})
        self.assertEqual(payload["model"], "deepseek-v4-pro")
        payload = pet_llm.build_payload("writing.breakdown", "拆一下", config={"force_tier": "flash"})
        self.assertEqual(payload["model"], "deepseek-v4-flash")

    def test_the_output_limit_still_comes_from_the_task(self):
        self.assertEqual(choose("intent.route", {"force_tier": "pro"})[1], 256)
        self.assertEqual(choose("writing.breakdown", {"force_tier": "flash"})[1], 2048)

    def test_the_tiers_constant_is_the_only_list(self):
        self.assertEqual(pet_llm.TIERS, ("flash", "pro"))


class OffPeakTests(unittest.TestCase):
    def stamp(self, hour):
        """构造北京时间 hour 点的 UTC 时间戳（北京时间 = UTC+8）。"""
        return hour * 3600 - 8 * 3600

    def test_window_uses_beijing_time(self):
        self.assertEqual(pet_llm.clock_hour(self.stamp(10)), 10)
        self.assertTrue(pet_llm.in_off_peak(self.stamp(23)))
        self.assertTrue(pet_llm.in_off_peak(self.stamp(3)))
        self.assertFalse(pet_llm.in_off_peak(self.stamp(10)))
        self.assertFalse(pet_llm.in_off_peak(self.stamp(22)))

    def test_next_off_peak_points_at_tonight(self):
        target = pet_llm.next_off_peak(self.stamp(10))
        self.assertEqual(pet_llm.beijing(target) % 86400, 23 * 3600)

    def test_queue_defers_non_urgent_and_sends_urgent_now(self):
        queue = Queue(config={'off_peak': (23, 7)})
        at = self.stamp(10)
        deferred = queue.enqueue('progress.summary', '生成日报', at=at)
        urgent = queue.enqueue('intent.route', '继续', urgent=True, at=at)
        self.assertEqual(deferred['send_after'], pet_llm.next_off_peak(at))
        self.assertEqual(urgent['send_after'], at)
        self.assertEqual([item['task'] for item in queue.ready(at)], ['intent.route'])   # 紧急项立即到期
        due = queue.ready(pet_llm.next_off_peak(at))
        self.assertEqual([item['task'] for item in due], ['progress.summary'])
        self.assertEqual(queue.items, [])

    def test_queue_sends_immediately_inside_the_window(self):
        queue = Queue()
        at = self.stamp(23)
        item = queue.enqueue('progress.summary', '生成日报', at=at)
        self.assertEqual(item['send_after'], at)
        self.assertEqual(len(queue.ready(at)), 1)


class LedgerTests(unittest.TestCase):
    def usage(self, prompt, completion, cached):
        return {'prompt_tokens': prompt, 'completion_tokens': completion, 'cached_tokens': cached}

    def test_hit_rate_and_flash_share(self):
        ledger = Ledger()
        ledger.record('deepseek-v4-flash', self.usage(100, 20, 80), tier='flash')
        ledger.record('deepseek-v4-pro', self.usage(100, 40, 0), tier='pro')
        self.assertEqual(ledger.hit_rate(), 0.4)
        self.assertEqual(ledger.flash_share(), 0.5)
        self.assertEqual(ledger.today_tokens(), 260)

    def test_empty_ledger_reports_zero(self):
        ledger = Ledger()
        self.assertEqual(ledger.hit_rate(), 0.0)
        self.assertEqual(ledger.flash_share(), 0.0)
        self.assertFalse(ledger.over_budget(1000))

    def test_budget_is_a_hard_limit(self):
        ledger = Ledger()
        ledger.record('deepseek-v4-flash', self.usage(900, 50, 0))
        self.assertFalse(ledger.over_budget(1000))
        ledger.record('deepseek-v4-flash', self.usage(100, 0, 0))
        self.assertTrue(ledger.over_budget(1000))
        self.assertFalse(ledger.over_budget(None))

    def test_today_resets_on_the_beijing_day_boundary(self):
        ledger = Ledger()
        yesterday = 15 * 3600 - 8 * 3600                  # 北京时间 1970-01-01 15:00
        ledger.record('deepseek-v4-flash', self.usage(500, 0, 0), at=yesterday)
        today = yesterday + 86400                         # 北京时间次日 15:00
        self.assertEqual(ledger.today_tokens(at=today), 0)
        self.assertEqual(ledger.today_tokens(at=yesterday), 500)

    def test_ledger_persists_in_the_project(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = Ledger(td)
            ledger.record('deepseek-v4-flash', self.usage(100, 10, 90), tier='flash')
            ledger.save()
            restored = Ledger(td).load()
            self.assertEqual(len(restored.entries), 1)
            self.assertEqual(restored.hit_rate(), 0.9)


class HttpTransportTests(unittest.TestCase):
    def test_tls_eof_is_retried_once_before_the_response_is_available(self):
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = b'{"id":"ok"}'
        response.__enter__.return_value = response
        eof = urllib.error.URLError(ssl.SSLEOFError(8, 'UNEXPECTED_EOF_WHILE_READING'))
        from contract.platform_tools import RequestsJsonOpener
        with mock.patch.object(RequestsJsonOpener, 'open', side_effect=[eof, response]) as urlopen, \
             mock.patch('infra.api_endpoints._SLEEP') as sleep:
            result = pet_llm.http_transport('https://gateway.test/v1/messages', {'model': 'claude'},
                                            {'x-api-key': 'test'}, 30)
        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['id'], 'ok')
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0.25)

    def test_tls_eof_is_retried_twice_before_the_response_is_available(self):
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = b'{"id":"ok"}'
        response.__enter__.return_value = response
        eof = urllib.error.URLError(ssl.SSLEOFError(8, 'UNEXPECTED_EOF_WHILE_READING'))
        from contract.platform_tools import RequestsJsonOpener
        with mock.patch.object(RequestsJsonOpener, 'open', side_effect=[eof, eof, response]) as urlopen, \
             mock.patch('infra.api_endpoints._SLEEP') as sleep:
            result = pet_llm.http_transport('https://gateway.test/v1/messages', {'model': 'claude'},
                                            {'x-api-key': 'test'}, 30)
        self.assertTrue(result['ok'])
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.25, 0.5])


class ClientTests(unittest.TestCase):
    def test_ask_sends_fixed_prefix_and_records_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake()
            client = Client(program=env_dir(td), transport=fake)
            result = client.ask('intent.route', '继续', context={'stage': 'keyframe'})
            self.assertTrue(result['ok'])
            self.assertEqual(result['model'], 'deepseek-v4-flash')
            self.assertEqual(fake.calls[0]['url'], 'https://api.deepseek.com/chat/completions')
            self.assertEqual(fake.calls[0]['payload']['messages'][0]['content'], pet_llm.SYSTEM_PREFIX)
            self.assertEqual(fake.calls[0]['payload']['max_tokens'], 256)
            self.assertTrue(fake.calls[0]['headers']['Authorization'].startswith('Bearer '))
            self.assertEqual(client.ledger.hit_rate(), 0.8)
            self.assertEqual(client.ledger.flash_share(), 1.0)

    def test_pro_failure_degrades_to_flash(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': False, 'status': 503, 'error': 'HTTP 503：服务不可用'},
                         {'ok': True, 'status': 200, 'data': {'usage': {'prompt_tokens': 5,
                                                                       'completion_tokens': 5,
                                                                       'prompt_cache_hit_tokens': 0}}}])
            client = Client(program=env_dir(td), transport=fake)
            result = client.ask('writing.breakdown', '把大纲拆成 10 集')
            self.assertTrue(result['ok'])
            self.assertTrue(result['degraded'])
            self.assertEqual(result['model'], 'deepseek-v4-flash')
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(fake.calls[1]['payload']['model'], 'deepseek-v4-flash')
            self.assertEqual(client.ledger.entries[0]['tier'], 'flash')

    def test_a_fallback_model_catches_a_second_retryable_failure(self):
        """第 43 期：两档都限流之后，「三虎设置 → 模型」里那条降级模型接上再发一次。"""
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': False, 'status': 503, 'error': 'HTTP 503：服务不可用'},
                         {'ok': False, 'status': 503, 'error': 'HTTP 503：服务不可用'},
                         {'ok': True, 'status': 200, 'data': {'usage': {'prompt_tokens': 5,
                                                                        'completion_tokens': 5,
                                                                        'prompt_cache_hit_tokens': 0}}}])
            client = Client(program=env_dir(td), transport=fake, config={
                'fallback': {'base_url': 'https://fallback.test', 'key_env': 'DEEPSEEK_API_KEY',
                             'model': 'fb-model', 'path': '/chat/completions', 'wire_api': 'chat'}})
            result = client.ask('writing.breakdown', '把大纲拆成 10 集')
            self.assertTrue(result['ok'])
            self.assertTrue(result['degraded'])
            self.assertEqual(result['model'], 'fb-model')
            self.assertEqual(len(fake.calls), 3)
            self.assertEqual(fake.calls[2]['url'], 'https://fallback.test/chat/completions')
            self.assertEqual(fake.calls[2]['payload']['model'], 'fb-model')

    def test_the_fallback_is_skipped_when_it_was_already_tried(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': False, 'status': 503, 'error': 'HTTP 503：服务不可用'},
                         {'ok': False, 'status': 503, 'error': 'HTTP 503：服务不可用'}])
            client = Client(program=env_dir(td), transport=fake, config={
                'fallback': {'base_url': 'https://api.deepseek.com', 'key_env': 'DEEPSEEK_API_KEY',
                             'model': 'deepseek-v4-flash', 'path': '/chat/completions',
                             'wire_api': 'chat'}})
            result = client.ask('writing.breakdown', '把大纲拆成 10 集')
            self.assertFalse(result['ok'])
            self.assertEqual(len(fake.calls), 2, '降级模型与档位上那条一样就不再发第三次')

    def test_the_key_comes_from_the_private_env_file_too(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'private').mkdir()
            (Path(td) / 'private' / '.env').write_text('DEEPSEEK_API_KEY=sk-private\n', encoding='utf-8')
            fake = Fake()
            client = Client(program=Path(td), transport=fake)
            result = client.ask('intent.route', '继续')
            self.assertTrue(result['ok'])
            self.assertEqual(fake.calls[0]['headers']['Authorization'], 'Bearer sk-private')

    def test_the_key_falls_back_to_the_environment_variable(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake()
            with mock.patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'sk-env'}):
                client = Client(program=Path(td), transport=fake)
                result = client.ask('intent.route', '继续')
            self.assertTrue(result['ok'])
            self.assertEqual(fake.calls[0]['headers']['Authorization'], 'Bearer sk-env')

    def test_non_retryable_error_does_not_degrade(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': False, 'status': 400, 'error': 'HTTP 400：参数错误'}])
            client = Client(program=env_dir(td), transport=fake)
            result = client.ask('writing.breakdown', '把大纲拆成 10 集')
            self.assertFalse(result['ok'])
            self.assertFalse(result['degraded'])
            self.assertEqual(len(fake.calls), 1)
            self.assertIn('400', result['error'])

    def test_budget_exhausted_stops_before_sending(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake()
            client = Client(program=env_dir(td), transport=fake,
                            config={'budget': {'tokens_per_day': 1}})
            client.ledger.record('deepseek-v4-flash', {'prompt_tokens': 5, 'completion_tokens': 5,
                                                       'cached_tokens': 0}, at=pet_llm.time.time())
            result = client.ask('intent.route', '继续')
            self.assertFalse(result['ok'])
            self.assertTrue(result['budget'])
            self.assertEqual(fake.calls, [])
            self.assertIn('预算', result['error'])

    def test_missing_key_returns_error_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake()
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('DEEPSEEK_API_KEY', None)
                client = Client(program=Path(td), transport=fake)
                result = client.ask('intent.route', '继续')
            self.assertFalse(result['ok'])
            self.assertIn('API Key', result['error'])
            self.assertEqual(fake.calls, [])

    def test_transport_error_keeps_the_message(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': False, 'status': 0, 'error': 'URLError：网络连接失败'}])
            client = Client(program=env_dir(td), transport=fake)
            result = client.ask('intent.route', '继续')
            self.assertFalse(result['ok'])
            self.assertIn('网络连接失败', result['error'])
            self.assertEqual(client.calls[0]['status'], 0)

    def test_usage_is_read_from_deepseek_cache_fields(self):
        usage = pet_llm.usage_of({'data': {'usage': {'prompt_tokens': 12, 'completion_tokens': 3,
                                                     'prompt_cache_hit_tokens': 9}}})
        self.assertEqual(usage, {'prompt_tokens': 12, 'completion_tokens': 3, 'cached_tokens': 9})
        self.assertEqual(pet_llm.usage_of(None), {'prompt_tokens': 0, 'completion_tokens': 0, 'cached_tokens': 0})

    def test_flush_writes_the_ledger_into_the_project(self):
        with tempfile.TemporaryDirectory() as td:
            client = Client(project=td, program=env_dir(td), transport=Fake())
            client.ask('intent.route', '继续')
            client.flush()
            self.assertTrue(pet_llm.ledger_path(Path(td)).is_file())

    def test_ask_records_a_sanitized_model_diagnostic_for_project_calls(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': True, 'status': 200, 'data': {
                'id': 'pet-request-1', 'choices': [{'finish_reason': 'stop', 'message': {
                    'content': '不能保存的回复正文', 'reasoning_content': '不能保存的推理'}}],
                'usage': {'prompt_tokens': 3, 'completion_tokens': 2}}}])
            result = Client(project=td, program=env_dir(td), transport=fake).ask('intent.route', '继续')
            files = list((Path(td) / 'model_diagnostics').glob('*.json'))
            self.assertTrue(result['ok'])
            self.assertEqual(len(files), 1)
            saved = json.loads(files[0].read_text(encoding='utf-8'))
            self.assertEqual(saved['context']['subsystem'], 'pet')
            self.assertEqual(saved['finish_reason'], 'stop')
            self.assertEqual(saved['reasoning_fields'], ['reasoning_content'])
            self.assertNotIn('不能保存的回复正文', files[0].read_text(encoding='utf-8'))


class AttemptAccountingTests(unittest.TestCase):
    def test_money_budget_blocks_before_transport_and_does_not_fallback(self):
        from usage_overview import summarize
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'cost_profile.json').write_text(json.dumps({'budget_amount': '0', 'price_table': {
                'currency': 'CNY', 'version': 'fixture', 'model_rates': {
                    'deepseek-v4-pro': {'prompt_tokens': '0.01', 'completion_tokens': '0.01'}}}}), encoding='utf-8')
            fake = Fake()
            result = Client(project=td, program=env_dir(td), transport=fake).ask('writing.breakdown', '拆分')
            self.assertFalse(result['ok'])
            self.assertTrue(result['budget'])
            self.assertEqual(fake.calls, [])
            self.assertEqual(summarize(td)['total']['calls'], 0)
            self.assertEqual(summarize(td)['not_submitted'], 1)

    def test_failed_usage_and_unknown_are_not_overwritten_by_retry(self):
        from usage_overview import summarize
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': False, 'status': 503, 'data': {'usage': {'prompt_tokens': 7, 'completion_tokens': 2}}},
                         {'ok': False, 'status': 503},
                         {'ok': True, 'status': 200, 'data': {'usage': {'prompt_tokens': 3, 'completion_tokens': 1}}}])
            client = Client(project=td, program=env_dir(td), transport=fake, config={
                'fallback': {'base_url': 'https://fallback.test', 'key_env': 'DEEPSEEK_API_KEY',
                             'model': 'fb-model', 'path': '/chat/completions', 'wire_api': 'chat'}})
            self.assertTrue(client.ask('writing.breakdown', '拆分', context={'stage': 'script'})['ok'])
            events = [json.loads(p.read_text(encoding='utf-8')) for p in (Path(td) / 'model_diagnostics').glob('*.json')]
            self.assertEqual(len(events), 3)
            self.assertEqual(len({e['context']['request_id'] for e in events}), 3)
            self.assertEqual(len({e['context']['invocation_id'] for e in events}), 1)
            summary = summarize(td)
            self.assertEqual(summary['total']['unknown_usage'], 1)
            self.assertEqual(summary['by_stage']['script']['total_tokens'], 13)
            self.assertEqual(client.ledger.today_tokens(), 13)

    def test_pending_exists_before_send_and_survives_exception(self):
        with tempfile.TemporaryDirectory() as td:
            def failing(*args):
                files = list((Path(td) / 'model_diagnostics').glob('*.json'))
                self.assertEqual(len(files), 1)
                self.assertEqual(json.loads(files[0].read_text(encoding='utf-8'))['error_class'], 'pending')
                raise TimeoutError('private response body')
            client = Client(project=td, program=env_dir(td), transport=failing)
            with self.assertLogs('pet_llm', level='ERROR'):
                self.assertFalse(client.ask('intent.route', 'private request body')['ok'])
            saved = next((Path(td) / 'model_diagnostics').glob('*.json')).read_text(encoding='utf-8')
            self.assertNotIn('private', saved)
            self.assertEqual(json.loads(saved)['usage'], {})
            self.assertEqual(client.ledger.entries, [])
            held = pet_llm.RequestLedger(td).load().entries[0]
            self.assertEqual(held['state'], 'unknown')
            self.assertEqual(held['money_state'], 'unknown')

    def test_missing_usage_and_preflight_write_failure(self):
        from usage_overview import summarize
        with tempfile.TemporaryDirectory() as td:
            fake = Fake([{'ok': True, 'status': 200, 'data': {}}])
            client = Client(project=td, program=env_dir(td), transport=fake)
            self.assertTrue(client.ask('intent.route', '继续')['ok'])
            self.assertEqual(summarize(td)['total']['unknown_usage'], 1)
            self.assertEqual(client.ledger.entries, [])
            with mock.patch('infra.model_diagnostics.record', side_effect=OSError('disk full')):
                with self.assertLogs('pet_llm', level='ERROR'):
                    self.assertFalse(client.ask('intent.route', '继续')['ok'])
            self.assertEqual(len(fake.calls), 1)


if __name__ == "__main__":
    unittest.main()
