# -*- coding: utf-8 -*-
"""第 43 期：模型池（规格《三虎模型设置》）与三虎四任务模型的路由。

两条线各测一头：
- model_pool：一条记录怎么规范化、模型池从哪读、密钥从哪找、写盘往返、覆盖怎么算；
- model_router.resolve_agent_model／agent_patch：「自动」按复杂度挑、四个维度分开、
  挑不出来时降级到降级模型、降级也不行就说清原因。
一律不联网：传输函数都是假的，密钥用一个临时目录里的 .env。
"""
import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workflow_settings

import model_pool
import infra.model_router as model_router
import model_secrets

ABSENT_KEY = 'CODEX_TEST_KEY_ABSENT'          # 一定不在环境变量里的名字


def install_test_protector(case):
    """替换 Windows DPAPI：模型池单测只验证调用链，不依赖执行进程的用户配置文件。"""
    original = model_secrets.PROTECTOR
    case.addCleanup(setattr, model_secrets, 'PROTECTOR', original)
    key_name = model_secrets.name_for('llama-3-8b')
    saved_key = os.environ.pop(key_name, None)

    def restore_environment():
        if saved_key is not None:
            os.environ[key_name] = saved_key

    case.addCleanup(restore_environment)
    marker = b'TEST-DPAPI\0'

    def protect(data, decrypt=False, label=''):
        payload = bytes(data)
        if decrypt:
            if not payload.startswith(marker):
                raise ValueError('测试密文无效')
            return payload[len(marker):][::-1]
        return marker + payload[::-1]

    model_secrets.PROTECTOR = protect


@contextlib.contextmanager
def no_env_keys(*names):
    """临时把环境变量里那几把密钥摘掉：本机可能真配了，用例不能依赖它。"""
    saved = {name: os.environ.pop(name, None) for name in names}
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is not None:
                os.environ[name] = value


def env_dir(root, keys=('DEEPSEEK_API_KEY',)):
    """造一个程序目录：.env 里放指定的几个密钥名（值只要形状合法）。"""
    root = Path(root)
    (root / '.env').write_text(''.join('%s=sk-test-%d\n' % (name, index)
                                       for index, name in enumerate(keys)), encoding='utf-8')
    return root


class RecordTests(unittest.TestCase):
    def setUp(self):
        workflow_settings.clear_desktop_installation_cache()

    def test_a_record_keeps_the_six_fields_and_normalises_junk(self):
        item = model_pool.record({'label': ' 本地 ', 'model': 'llama',
                                  'base_url': ' http://127.0.0.1:8000/v1 ', 'wire_api': '乱写',
                                  'cost': '9', '没这个键': 1})
        self.assertEqual(item['label'], '本地')
        self.assertEqual(item['base_url'], 'http://127.0.0.1:8000/v1')
        self.assertEqual(item['wire_api'], model_pool.DEFAULT_WIRE, '认不出的协议退回 chat')
        self.assertEqual(item['path'], model_pool.DEFAULT_PATH)
        self.assertEqual(item['cost'], 3, '成本夹在 1~3')
        self.assertNotIn('没这个键', item, '认不出的键不写进配置')

    def test_the_shipped_pool_contains_api_models_and_desktop_agents(self):
        pool = model_pool.pool(program=Path('不存在的目录'))
        self.assertEqual(list(pool), ['deepseek-v4-flash', 'deepseek-v4-pro', 'gpt-4o', 'qwen-max',
                                      'chatgpt-desktop', 'claude-desktop', 'claude-desktop-app'])
        self.assertEqual(pool['gpt-4o']['key_env'], 'OPENAI_API_KEY')
        self.assertEqual(model_pool.desktop_engine('claude-desktop'), 'claude')
        self.assertEqual(model_pool.status(pool['chatgpt-desktop']), (True, '桌面 Agent'))

    def test_custom_claude_code_ids_use_the_claude_vendor_and_engine(self):
        for name in ('claude code', 'Claude Code', 'claude-code', 'claude_code', 'Claude Code Cli'):
            with self.subTest(name=name):
                item = model_pool.record({'model': name, 'provider': 'desktop'})
                self.assertEqual(model_pool.provider_name(name, item), 'Anthropic')
                self.assertEqual(model_pool.desktop_engine(name), 'claude')
        self.assertEqual(model_pool.desktop_engine('claude-desktop-app'), 'claude-desktop-app')
        self.assertEqual(model_pool.desktop_engine('claude-opus-5.5'), '')
        self.assertEqual(model_pool.desktop_engine('my-claude-code-server'), '')

    def test_the_stored_pool_is_authoritative(self):
        data = {'models': {'mine': {'model': 'my-model', 'base_url': 'https://example.test/v1',
                                    'key_env': 'K'}}}
        self.assertEqual(list(model_pool.pool(config=data)), ['chatgpt-desktop', 'claude-desktop', 'claude-desktop-app', 'mine'],
                         '内建桌面 Agent 固定展示在前，用户保存的 API 模型保持可选')

    def test_explicit_desktop_deletion_survives_reload_and_other_saves(self):
        for target in model_pool.DESKTOP_ENGINES:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as td:
                data = model_pool.remove({}, target)
                model_pool.store(data, td)
                self.assertNotIn(target, model_pool.pool(program=td))
                self.assertTrue(set(model_pool.DESKTOP_ENGINES) - {target} <= set(model_pool.pool(program=td)))
                data = model_pool.upsert(model_pool.raw(td), {'model': 'custom', 'label': 'Custom'})
                model_pool.store(data, td)
                self.assertNotIn(target, model_pool.pool(program=td))
                restored = model_pool.upsert(data, model_pool.default_pool()[target], target)
                self.assertIn(target, model_pool.pool(restored))
                self.assertNotIn(target, restored.get('deleted_desktop_models', []))

    def test_the_four_task_fields_come_from_the_config(self):
        data = {'agent': {'models': {'default': 'x', 'chat': 'y', 'escalate': 'z', 'fallback': 'w'}}}
        self.assertEqual(model_pool.agent_models(config=data),
                         {'default': 'x', 'chat': 'y', 'escalate': 'z', 'fallback': 'w'})
        self.assertEqual(model_pool.agent_models(config={})['default'], model_pool.AUTO, '出厂＝自动')

    def test_options_put_auto_first_only_when_asked(self):
        pool = model_pool.default_pool()
        self.assertEqual(model_pool.options(pool)[0], (model_pool.AUTO, model_pool.AUTO_LABEL))
        self.assertNotIn(model_pool.AUTO, [model_id for model_id, _label in
                                           model_pool.options(pool, with_auto=False)])
        self.assertEqual(model_pool.id_of_label('DeepSeek V4 Pro', model_pool.options(pool)),
                         'deepseek-v4-pro')
        self.assertEqual(model_pool.id_of_label('认不出来', model_pool.options(pool)), '认不出来')
        self.assertEqual(model_pool.label_of(model_pool.AUTO, pool), model_pool.AUTO_LABEL)

    def test_desktop_options_are_marked_only_when_the_shared_probe_cannot_find_them(self):
        pool = model_pool.default_pool()
        # 与本机真实模型池隔离：用户配置过的程序路径不能左右「未安装」判据。
        isolated = patch('model_pool.pool', return_value=pool)
        isolated.start()
        self.addCleanup(isolated.stop)
        workflow_settings.clear_desktop_installation_cache()
        with patch('workflow_settings.find_program', return_value='C:/Apps/agent.exe'):
            labels = dict(model_pool.options(pool, labeler=workflow_settings.desktop_model_label))
        self.assertNotIn('未安装', labels['chatgpt-desktop'])
        self.assertNotIn('未安装', labels['claude-desktop'])

        workflow_settings.clear_desktop_installation_cache()
        with patch('workflow_settings.find_program', side_effect=ValueError('not installed')):
            labels = dict(model_pool.options(pool, labeler=workflow_settings.desktop_model_label))
        self.assertIn('未安装', labels['chatgpt-desktop'])
        self.assertIn('未安装', labels['claude-desktop'])

    def test_desktop_probe_exception_is_marked_and_cached_without_reaching_the_ui(self):
        pool = model_pool.default_pool()
        with patch('model_pool.pool', return_value=pool), \
                patch('workflow_settings.find_program', side_effect=RuntimeError('probe failed')) as probe:
            first = dict(model_pool.options(pool, labeler=workflow_settings.desktop_model_label))
            second = dict(model_pool.options(pool, labeler=workflow_settings.desktop_model_label))
        self.assertIn('未安装', first['chatgpt-desktop'])
        self.assertIn('未安装', first['claude-desktop'])
        self.assertEqual(first, second)
        self.assertEqual(probe.call_count, 3, '每个桌面引擎在本进程只探测一次')


class ProviderDisplayTests(unittest.TestCase):
    """同一厂商的 API／桌面入口在阶段配置和模型表中必须落在同一目录。"""

    def test_gpt_api_and_chatgpt_desktop_share_the_gpt_provider_label(self):
        pool = model_pool.default_pool()
        custom = model_pool.record({'model': 'gpt-6-astra', 'provider': 'openai-compatible'})
        self.assertEqual(model_pool.provider_name('chatgpt-desktop', pool['chatgpt-desktop']), 'GPT')
        self.assertEqual(model_pool.provider_name('gpt-6-astra', custom), 'GPT')


class RecordFieldTests(unittest.TestCase):
    """第 43 期：规格那张表单里的 Provider／能力标签／上下文长度／备注都要存得住。"""

    def test_the_extra_fields_survive_and_normalise_junk(self):
        item = model_pool.record({'model': 'm', 'provider': '乱写', 'note': ' 给分镜用 ',
                                  'context_length': '32000',
                                  'capabilities': ['reasoning', '没这个', 'fast', 'reasoning']})
        # 第 65 期任务 5：Provider 只是一行标签，用户选「自定义」要能自己敲名字，
        # 所以写进来什么就存什么；只有空着才退回默认。
        self.assertEqual(item['provider'], '乱写', '自定义的 Provider 名字原样留住')
        self.assertEqual(model_pool.record({'model': 'm'})['provider'], model_pool.DEFAULT_PROVIDER,
                         '空着才退回默认')
        self.assertEqual(item['capabilities'], ['reasoning', 'fast'], '认得的按登记表顺序去重留住')
        self.assertEqual(item['context_length'], 32000)
        self.assertEqual(item['note'], '给分镜用')

    def test_a_capability_sentence_is_accepted(self):
        self.assertEqual(model_pool.capabilities_of('fast, cheap；乱写'),
                         ['fast', 'cheap'], '配置文件里手写成一句话也收')
        self.assertEqual(model_pool.capability_text(['structured-output', 'vision']), '结构化输出、视觉')
        self.assertEqual(model_pool.context_length_of('0'), '', '0 与乱写一样算没填')
        self.assertEqual(model_pool.context_length_of('abc'), '')

    def test_the_shipped_pool_carries_its_capabilities(self):
        """池子是权威，路由的能力匹配就从这儿读——出厂的几条不能是空标签。"""
        pool = model_pool.default_pool()
        self.assertIn('fast', pool['deepseek-v4-flash']['capabilities'])
        self.assertIn('vision', pool['gpt-4o']['capabilities'])
        self.assertEqual(pool['qwen-max']['context_length'], 32000)


class LocalSecretTests(unittest.TestCase):
    """规格里的第二种放法：密钥直接输进来，用系统加密存本机（明文不落盘、配置 JSON 不写）。"""

    def setUp(self):
        install_test_protector(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = Path(self.tmp.name) / '程序'
        self.program.mkdir()
        self.record = {'label': '我的本地模型', 'model': 'llama-3-8b',
                       'base_url': 'http://127.0.0.1:8000/v1'}

    def test_saving_a_key_names_it_and_never_writes_the_plain_text(self):
        item = model_pool.save_local_key(self.record, 'sk-local-abcdef', self.program)
        self.assertEqual(item['key_env'], model_pool.secret_name(self.record))
        self.assertTrue(item['key_env'], '没填密钥名就按模型 ID 起一个')
        self.assertEqual(model_pool.local_key_of(item, self.program), 'sk-local-abcdef')
        target = model_secrets.path(item['key_env'], self.program)
        self.assertTrue(target.is_file())
        self.assertNotIn(b'sk-local-abcdef', target.read_bytes(), '盘上不许出现明文')

    def test_a_key_name_in_the_record_wins(self):
        item = model_pool.save_local_key({'model': 'llama-3-8b', 'key_env': 'MINE_KEY'},
                                         'sk-local-1', self.program)
        self.assertEqual(item['key_env'], 'MINE_KEY')
        self.assertTrue(model_secrets.path('MINE_KEY', self.program).is_file())

    def test_a_stored_key_makes_the_model_usable_and_probe_sends_it(self):
        item = model_pool.save_local_key(self.record, 'sk-local-abcdef', self.program)
        self.assertEqual(model_pool.status(item, self.program), (True, '可用'))
        sent = []

        def send(url, payload, head, timeout):
            sent.append({'url': url, 'head': head})
            return {'ok': True, 'status': 200, 'data': {}}

        self.assertTrue(model_pool.probe(item, send, self.program)['ok'])
        self.assertEqual(sent[0]['url'], 'http://127.0.0.1:8000/v1/chat/completions')
        self.assertEqual(sent[0]['head']['Authorization'], 'Bearer sk-local-abcdef')

    def test_an_empty_or_spaced_key_is_refused(self):
        for bad in ('', '   ', 'sk a', 'sk\tabc'):
            with self.assertRaises(ValueError):
                model_pool.save_local_key(self.record, bad, self.program)

    def test_clearing_takes_the_model_back_to_missing_a_key(self):
        item = model_pool.save_local_key(self.record, 'sk-local-abcdef', self.program)
        self.assertTrue(model_pool.clear_local_key(item, self.program))
        self.assertFalse(model_pool.clear_local_key(item, self.program), '本来就没存')
        self.assertEqual(model_pool.local_key_of(item, self.program), '')
        self.assertFalse(model_pool.status(item, self.program)[0])

    def test_a_broken_or_foreign_file_counts_as_missing(self):
        item = model_pool.save_local_key(self.record, 'sk-local-abcdef', self.program)
        model_secrets.path(item['key_env'], self.program).write_bytes(b'\x00not encrypted')
        self.assertEqual(model_pool.local_key_of(item, self.program), '')
        self.assertFalse(model_pool.status(item, self.program)[0])

    def test_only_the_first_four_characters_are_readable(self):
        self.assertEqual(model_pool.redacted('sk-local-abcdef'), 'sk-l****')
        self.assertEqual(model_pool.redacted('ab'), '****')
        self.assertEqual(model_pool.redacted(''), '****')


class EnvKeyTests(unittest.TestCase):
    """R505 P0：新密钥仅存 DPAPI；旧 private/.env 可显式、可恢复地迁移。"""

    def setUp(self):
        install_test_protector(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = Path(self.tmp.name) / '程序'
        self.program.mkdir()
        self.record = {'label': '我的本地模型', 'model': 'llama-3-8b',
                       'base_url': 'https://mine.test/v1', 'key_env': 'MINE_KEY'}

    def test_the_typed_key_lands_in_dpapi_without_creating_an_env_file(self):
        path = model_pool.save_key_env(self.record, 'sk-env-123', self.program)
        self.assertEqual(path, model_secrets.path('MINE_KEY', self.program))
        self.assertFalse(model_pool.env_file(self.program).exists())
        self.assertNotIn(b'sk-env-123', path.read_bytes())
        with no_env_keys('MINE_KEY'):
            self.assertEqual(model_pool.key_of(self.record, self.program), 'sk-env-123')
            self.assertEqual(model_pool.status(self.record, self.program), (True, '可用'))

    def test_a_legacy_env_is_migrated_before_a_new_key_is_saved(self):
        target = model_pool.env_file(self.program)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# 旧密钥\nOTHER_KEY=sk-other\nMINE_KEY=sk-old\n',
                          encoding='utf-8')
        model_pool.save_key_env(self.record, 'sk-new', self.program)
        self.assertFalse(target.exists(), '所有旧条目加密后才可清除明文文件')
        self.assertEqual(model_pool.named_key('OTHER_KEY', self.program), 'sk-other')
        self.assertEqual(model_pool.named_key('MINE_KEY', self.program), 'sk-new')

    def test_a_bad_key_or_a_nameless_record_is_refused(self):
        with self.assertRaises(ValueError):
            model_pool.save_key_env(self.record, '   ', self.program)
        with self.assertRaises(ValueError):
            model_pool.save_key_env(self.record, 'has space', self.program)
        with self.assertRaises(ValueError):
            model_pool.save_key_env({'label': '没名字', 'model': ''}, 'sk-1', self.program)

    def test_a_failed_legacy_migration_keeps_the_plaintext_file_for_recovery(self):
        target = model_pool.env_file(self.program)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('MINE_KEY=sk-old\n', encoding='utf-8')
        original = model_secrets.PROTECTOR
        model_secrets.PROTECTOR = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('DPAPI unavailable'))
        self.addCleanup(setattr, model_secrets, 'PROTECTOR', original)
        with self.assertRaises(OSError):
            model_pool.migrate_key_env(self.program)
        self.assertTrue(target.is_file(), '加密失败不得删除用户的旧密钥文件')


class StoreTests(unittest.TestCase):
    def test_upsert_remove_and_store_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            data = model_pool.upsert({}, {'label': '本地', 'model': 'llama',
                                          'base_url': 'https://x.test/v1', 'key_env': 'LOCAL_KEY'})
            self.assertEqual(list(model_pool.pool(data)), list(model_pool.default_pool()) + ['llama'],
                             '第一次落盘把出厂那四条一起写进去，加自己的模型不会顶掉它们')
            data = model_pool.with_tasks(data, {'default': 'llama', 'chat': 'llama'})
            path = model_pool.store(data, td)
            self.assertTrue(Path(path).is_file())
            again = model_pool.raw(td)
            self.assertEqual(list(model_pool.pool(again))[-1], 'llama', '写盘再读回来还在')
            self.assertIn('deepseek-v4-flash', model_pool.pool(again), '出厂那几条也在')
            self.assertEqual(model_pool.agent_models(again)['default'], 'llama')
            self.assertEqual(model_pool.agent_models(again)['escalate'],
                             model_pool.TASKS_DEFAULT['escalate'], '没填的维度补出厂默认')
            self.assertNotIn('llama', model_pool.pool(model_pool.remove(again, 'llama')))

    def test_an_empty_model_id_is_refused(self):
        with self.assertRaises(ValueError):
            model_pool.upsert({}, {'label': '没 ID'})
        self.assertEqual(model_pool.model_id_of({'label': '只有显示名'}), '',
                         '显示名当不了 id（否则会写出一条没有模型 ID 的记录）')

    def test_the_same_id_overwrites_instead_of_duplicating(self):
        data = model_pool.upsert({}, {'model': 'llama', 'base_url': 'https://a.test/v1'})
        data = model_pool.upsert(data, {'model': 'llama', 'base_url': 'https://b.test/v1'})
        self.assertEqual(len(model_pool.pool(data)), len(model_pool.default_pool()) + 1)
        self.assertEqual(model_pool.pool(data)['llama']['base_url'], 'https://b.test/v1')


class KeyTests(unittest.TestCase):
    def test_the_key_comes_from_the_env_file_then_the_private_one(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(model_pool.key_of({'key_env': ABSENT_KEY}, td), '', '两处都没有就是空')
            self.assertEqual(model_pool.status({'model': 'm', 'base_url': 'https://x.test/v1',
                                                'key_env': ABSENT_KEY}, td),
                             (False, '缺 %s（.env）' % ABSENT_KEY))
            (Path(td) / '.env').write_text('%s=sk-a\n' % ABSENT_KEY, encoding='utf-8')
            self.assertEqual(model_pool.key_of({'key_env': ABSENT_KEY}, td), 'sk-a')
            (Path(td) / '.env').unlink()
            (Path(td) / 'private').mkdir(exist_ok=True)
            # 迁入后同名密钥以加密存储为准（不再回读 .env），所以第二处用另一个变量名。
            second = ABSENT_KEY + '_PRIVATE'
            (Path(td) / 'private' / '.env').write_text('%s=sk-b\n' % second, encoding='utf-8')
            self.assertEqual(model_pool.key_of({'key_env': second}, td), 'sk-b',
                             'private/.env 也认（其余模块的密钥就放那儿）')

    def test_a_record_without_an_address_is_not_usable(self):
        with tempfile.TemporaryDirectory() as td:
            ok, why = model_pool.status({'model': 'm', 'key_env': 'K'}, td)
            self.assertFalse(ok)
            self.assertIn('API 根地址', why)

    def test_patch_for_translates_a_pool_record_into_client_config(self):
        records = model_pool.default_pool()
        patch = model_pool.patch_for('qwen-max', records)
        self.assertEqual(patch['base_url'], 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.assertEqual(patch['key_env'], 'DASHSCOPE_API_KEY')
        self.assertEqual(patch['flash_model'], 'qwen-max')
        self.assertEqual(patch['pro_model'], 'qwen-max')
        self.assertEqual(model_pool.patch_for(model_pool.AUTO, records), {}, '自动＝不加覆盖')


class ProbeTests(unittest.TestCase):
    def test_probe_sends_one_minimal_request(self):
        seen = {}

        def send(url, payload, head, timeout):
            seen.update(url=url, payload=payload, head=head)
            return {'ok': True, 'status': 200, 'data': {}}

        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(model_pool.record({'model': 'deepseek-v4-flash',
                                                         'base_url': 'https://api.deepseek.com',
                                                         'key_env': 'DEEPSEEK_API_KEY'}), send, td)
        self.assertTrue(result['ok'])
        self.assertEqual(seen['url'], 'https://api.deepseek.com/chat/completions')
        self.assertEqual(seen['payload']['max_tokens'], model_pool.PROBE_TOKENS)
        self.assertNotIn('temperature', seen['payload'])
        self.assertGreaterEqual(model_pool.PROBE_TOKENS, 16, '第 65 期任务 8：太小会被服务商拒收')
        self.assertEqual(seen['head']['Authorization'], 'Bearer sk-test-0')
        self.assertGreaterEqual(result['ms'], 0, '规格里那句「连接成功，延迟 xxx ms」要有数')

    def test_anthropic_probe_keeps_an_existing_v1_root(self):
        seen = {}

        def send(url, payload, head, timeout):
            seen.update(url=url, payload=payload, head=head)
            return {'ok': True, 'status': 200, 'data': {}}

        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(model_pool.record({
                'model': 'claude-opus-5.5', 'provider': 'Anthropic',
                'base_url': 'https://api.b.ai/v1', 'wire_api': 'messages',
                'key_env': 'DEEPSEEK_API_KEY'}), send, td)
        self.assertTrue(result['ok'])
        self.assertEqual(seen['url'], 'https://api.b.ai/v1/messages')
        self.assertNotIn('temperature', seen['payload'])
        self.assertIn('x-api-key', seen['head'])

    def test_probe_without_a_key_never_calls_out(self):
        calls = []
        with tempfile.TemporaryDirectory() as td:
            result = model_pool.probe(model_pool.record({'model': 'm', 'base_url': 'https://x.test/v1',
                                                         'key_env': ABSENT_KEY}),
                                      lambda *args: calls.append(args), td)
        self.assertFalse(result['ok'])
        self.assertEqual(calls, [], '缺密钥就不该真发出去')
        self.assertIn(ABSENT_KEY, result['error'])

    def test_probe_reports_a_transport_crash_instead_of_raising(self):
        def boom(*args):
            raise TimeoutError('连接超时')

        with tempfile.TemporaryDirectory() as td:
            env_dir(td)
            result = model_pool.probe(model_pool.record({'model': 'm', 'base_url': 'https://x.test/v1',
                                                         'key_env': 'DEEPSEEK_API_KEY'}), boom, td)
        self.assertFalse(result['ok'])
        self.assertIn('连接超时', result['error'])


class StubSkill:
    """只带路由要看的几个字段（阶段面板里的 SKILL 就是这么被挑的）。"""

    name = 'stub'
    tools = ()

    def __init__(self, capabilities=(), preferredModels=(), fallbackModels=()):
        self.capabilities = tuple(capabilities)
        self.preferredModels = tuple(preferredModels)
        self.fallbackModels = tuple(fallbackModels)


class PoolRoutingTests(unittest.TestCase):
    """第 43 期：模型管理里加的那条，阶段配置挑中就得发得出去（不是只能看）。

    模型管理是 API 配置的唯一入口，所以地址／协议／密钥名全部照池里那一份走；一条记录一个
    适配器。一律不联网：传输函数收下每次请求，用例自己检查发到哪儿去了。
    """

    def setUp(self):
        install_test_protector(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = env_dir(self.tmp.name, ('MINE_KEY',))
        self.calls = []
        self.data = model_pool.upsert({}, {'label': '我的本地模型', 'model': 'llama-3-8b',
                                           'base_url': 'https://mine.test/v1', 'key_env': 'MINE_KEY',
                                           'capabilities': ['long-context'], 'context_length': 32000})

    def send(self, url, payload, head, timeout):
        self.calls.append({'url': url, 'payload': payload, 'head': head, 'timeout': timeout})
        return {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': 'pong'}}]}}

    def router(self, records=None):
        return model_router.ModelRouter(program=self.program, records=records or model_pool.pool(self.data),
                                        transport=self.send)

    def test_the_record_is_sent_to_its_own_endpoint_and_key(self):
        router = self.router()
        choice = router.select(StubSkill(), {'model': 'llama-3-8b'})
        self.assertTrue(choice.ok, choice.reason)
        self.assertIn('单次', choice.reason)
        result = router.chat(choice, [{'role': 'user', 'content': 'ping'}])
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], 'pong')
        self.assertEqual(self.calls[0]['url'], 'https://mine.test/v1/chat/completions')
        self.assertEqual(self.calls[0]['head']['Authorization'], 'Bearer sk-test-0')
        self.assertEqual(self.calls[0]['payload']['model'], 'llama-3-8b')

    def test_editing_the_address_moves_the_next_request(self):
        """在模型管理里把地址改了：下一次请求就发到新地方（不用重启）。"""
        data = model_pool.upsert(self.data, {'model': 'llama-3-8b', 'label': '我的本地模型',
                                             'base_url': 'https://new.test/v1', 'key_env': 'MINE_KEY'})
        router = self.router(model_pool.pool(data))
        self.assertTrue(router.chat(router.select(StubSkill(), {'model': 'llama-3-8b'}), []).get('ok'))
        self.assertEqual(self.calls[0]['url'], 'https://new.test/v1/chat/completions')

    def test_the_wire_api_switch_from_the_pool_is_honoured(self):
        data = model_pool.upsert(self.data, {'model': 'llama-3-8b', 'label': '我的本地模型',
                                             'base_url': 'https://mine.test/v1', 'key_env': 'MINE_KEY',
                                             'wire_api': 'responses'})
        router = self.router(model_pool.pool(data))
        self.assertTrue(router.chat(router.select(StubSkill(), {'model': 'llama-3-8b'}), []).get('ok'))
        self.assertEqual(self.calls[0]['url'], 'https://mine.test/v1/responses')
        self.assertIn('input', self.calls[0]['payload'])

    def test_native_messages_endpoint_does_not_duplicate_an_existing_v1(self):
        """兼容 Claude 服务常把 /v1 已写进根地址，最终只能请求一次 /v1/messages。"""
        data = model_pool.upsert(self.data, {'model': 'claude-test', 'label': 'Claude 测试',
                                             'base_url': 'https://mine.test/v1', 'key_env': 'MINE_KEY',
                                             'provider': 'anthropic', 'wire_api': 'messages'})
        router = self.router(model_pool.pool(data))
        choice = router.select(StubSkill(), {'model': 'claude-test'})
        self.assertTrue(router.chat(choice, [{'role': 'user', 'content': 'ping'}]).get('ok'))
        self.assertEqual(self.calls[0]['url'], 'https://mine.test/v1/messages')

    def test_the_pools_capability_tags_drive_the_matching(self):
        """能力标签从池里读：便宜的那条自定义模型带 vision，就该它上。"""
        data = model_pool.upsert(self.data, {'model': 'llama-vision', 'label': '本地视觉',
                                             'base_url': 'https://mine.test/v1', 'key_env': 'MINE_KEY',
                                             'capabilities': ['vision']})
        router = self.router(model_pool.pool(data))
        choice = router.select(StubSkill(capabilities=('vision',)))
        self.assertEqual(choice.model, 'llama-vision', choice.reason)

    def test_a_key_typed_in_the_manager_reaches_the_request(self):
        """「直接输入」那把（本机加密）也发得出去：不用 .env，请求头上就是它。"""
        item = model_pool.save_local_key({'label': '我的本地模型', 'model': 'llama-3-8b',
                                          'base_url': 'https://mine.test/v1'},
                                         'sk-local-777', self.program)
        router = self.router(model_pool.pool(model_pool.upsert({}, item)))
        self.assertTrue(router.chat(router.select(StubSkill(), {'model': 'llama-3-8b'}), []).get('ok'))
        self.assertEqual(self.calls[0]['head']['Authorization'], 'Bearer sk-local-777')

    def test_a_custom_model_without_a_key_is_not_usable(self):
        data = model_pool.upsert(self.data, {'model': 'no-key', 'label': '没配密钥',
                                             'base_url': 'https://mine.test/v1',
                                             'key_env': 'CODEX_TEST_KEY_ABSENT'})
        router = self.router(model_pool.pool(data))
        with no_env_keys('CODEX_TEST_KEY_ABSENT'):
            choice = router.select(StubSkill(), {'model': 'no-key'})
        self.assertFalse(choice.ok)
        self.assertIn('用不了', choice.reason)

    def test_an_explicit_adapter_list_stays_authoritative(self):
        """显式给了适配器（用例、别的子系统）就不去翻盘上的池子。"""
        class Fake(model_router.ModelAdapter):
            provider = 'fake'
            models = {'fake-cheap': {'capabilities': (), 'cost': 1}}

            def available(self):
                return True

        router = model_router.ModelRouter(adapters=[Fake()], program=self.program)
        self.assertEqual(router.adapter_for('fake-cheap').provider, 'fake')
        self.assertIsNone(router.adapter_for('llama-3-8b'), '池里的自定义模型不参与这条链')


class ResolveTests(unittest.TestCase):
    """规格里的 resolveAgentModel：四个维度分开、「自动」按复杂度挑、挑不出来就降级。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.program = env_dir(self.tmp.name, ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY'))
        self.pool = model_pool.default_pool()

    def resolve(self, task='default', **kwargs):
        return model_router.resolve_agent_model(task, records=self.pool, program=self.program, **kwargs)

    def test_auto_takes_the_cheapest_usable_model_for_a_simple_step(self):
        choice = self.resolve(context={'complexity': 'simple'})
        self.assertTrue(choice.ok)
        self.assertTrue(choice.auto)
        self.assertEqual(choice.model, 'deepseek-v4-flash')

    def test_auto_never_picks_a_desktop_agent(self):
        choice = self.resolve(context={'complexity': 'simple'})
        self.assertNotIn(choice.model, model_pool.DESKTOP_ENGINES)

    def test_auto_takes_the_expensive_one_for_a_complex_step(self):
        choice = self.resolve(context={'task': 'writing.breakdown'})
        self.assertEqual(choice.model, 'deepseek-v4-pro', '复杂任务表里那几条走贵的一档')
        self.assertTrue(choice.auto)

    def test_auto_takes_a_middle_model_for_a_medium_step(self):
        choice = self.resolve(context={'complexity': 'medium'})
        self.assertGreaterEqual(self.pool[choice.model]['cost'], 2, '中等任务不挑最便宜的那一档')
        self.assertNotEqual(choice.model, 'deepseek-v4-flash')

    def test_each_dimension_has_its_own_model(self):
        chat = self.resolve('chat')
        self.assertEqual(chat.model, 'deepseek-v4-pro')
        self.assertFalse(chat.auto)
        self.assertIn('对话模型', chat.reason)
        self.assertEqual(self.resolve('escalate').model, 'deepseek-v4-pro')
        self.assertEqual(self.resolve('fallback').model, 'deepseek-v4-flash')

    def test_a_picked_model_wins_over_auto(self):
        with tempfile.TemporaryDirectory() as td:
            program = env_dir(td)
            data = model_pool.with_tasks({}, {'default': 'deepseek-v4-pro'})
            choice = model_router.resolve_agent_model('default', config=data, records=self.pool,
                                                      program=program)
        self.assertEqual(choice.model, 'deepseek-v4-pro')
        self.assertFalse(choice.auto)
        self.assertIn('默认模型', choice.reason)

    def test_a_model_without_a_key_degrades_to_the_fallback(self):
        with tempfile.TemporaryDirectory() as td:                 # 这个目录里没有 OPENAI_API_KEY
            program = env_dir(td, ('DEEPSEEK_API_KEY',))
            data = model_pool.with_tasks({}, {'default': 'gpt-4o'})
            with no_env_keys('OPENAI_API_KEY'):
                choice = model_router.resolve_agent_model('default', config=data, records=self.pool,
                                                          program=program)
        self.assertTrue(choice.ok)
        self.assertTrue(choice.degraded)
        self.assertEqual(choice.model, 'deepseek-v4-flash')
        self.assertIn('用不了', choice.reason)

    def test_nothing_usable_gives_up_with_a_reason(self):
        with tempfile.TemporaryDirectory() as td:
            program = env_dir(td, ())                             # 一把密钥都没有
            with no_env_keys('DEEPSEEK_API_KEY', 'OPENAI_API_KEY', 'DASHSCOPE_API_KEY'):
                choice = model_router.resolve_agent_model('default', records=self.pool,
                                                          program=program)
        self.assertFalse(choice.ok)
        self.assertIn('池里没有配好密钥的模型', choice.reason)
        self.assertTrue(choice.describe())

    def test_an_empty_pool_says_where_to_add_one(self):
        choice = model_router.resolve_agent_model('chat', records={}, program=self.program)
        self.assertFalse(choice.ok)
        self.assertIn('模型管理', choice.reason)

    def test_agent_patch_is_empty_for_auto_and_full_for_a_model(self):
        auto = self.resolve()
        self.assertEqual(model_router.agent_patch(auto, records=self.pool, program=self.program), {})
        with tempfile.TemporaryDirectory() as td:
            program = env_dir(td)
            data = model_pool.with_tasks({}, {'default': 'deepseek-v4-pro'})
            choice = model_router.resolve_agent_model('default', config=data, records=self.pool,
                                                      program=program)
        patch = model_router.agent_patch(choice, records=self.pool, program=program)
        self.assertEqual(patch['pro_model'], 'deepseek-v4-pro')
        self.assertEqual(patch['base_url'], 'https://api.deepseek.com')

    def test_the_complexity_reader_follows_the_task_table(self):
        self.assertEqual(model_router.complexity_of('bug.diagnose'), 'complex')
        self.assertEqual(model_router.complexity_of('intent.route'), 'simple')
        self.assertEqual(model_router.complexity_of('intent.route', {'complexity': '复杂写法'}), 'simple')
        self.assertEqual(model_router.complexity_of('intent.route', {'complexity': 'COMPLEX'}), 'complex')


class WireFollowsProviderTests(unittest.TestCase):
    """第 65 期任务 8：协议栏跟着 Provider 自动配（model_pool.wire_for_provider）。"""

    def test_every_registered_provider_has_a_wire(self):
        for provider, _label in model_pool.PROVIDERS:
            self.assertIn(model_pool.wire_for_provider(provider), model_pool.WIRE_LABELS,
                          provider + ' 得能自动摆到一档已知协议上')

    def test_an_unknown_provider_falls_back_to_the_default_wire(self):
        self.assertEqual(model_pool.wire_for_provider(''), model_pool.DEFAULT_WIRE)
        self.assertEqual(model_pool.wire_for_provider('某家没登记的服务商'), model_pool.DEFAULT_WIRE)

    def test_the_probe_uses_sixteen_tokens(self):
        self.assertEqual(model_pool.PROBE_TOKENS, 16)


class NamedKeyTests(unittest.TestCase):
    """第 65 期任务 1：全程序只留一份明文 .env，云图片／TTS／Qwen 都按名字读写它。"""

    def setUp(self):
        install_test_protector(self)

    def test_save_and_read_back_by_name(self):
        with tempfile.TemporaryDirectory() as td:
            program = env_dir(td, ())
            target = model_pool.save_named_key('TTS_API_KEY', 'sk-tts-1', program)
            self.assertEqual(target, model_secrets.path('TTS_API_KEY', program))
            self.assertFalse(model_pool.env_file(program).exists())
            self.assertNotIn(b'sk-tts-1', target.read_bytes())
            self.assertEqual(model_pool.named_key('TTS_API_KEY', program), 'sk-tts-1')

    def test_the_same_name_overwrites_instead_of_appending(self):
        with tempfile.TemporaryDirectory() as td:
            program = env_dir(td, ())
            model_pool.save_named_key('TTS_API_KEY', 'sk-one', program)
            model_pool.save_named_key('TTS_API_KEY', 'sk-two', program)
            self.assertEqual(model_pool.named_key('TTS_API_KEY', program), 'sk-two')
            self.assertFalse(model_pool.env_file(program).exists())

    def test_a_blank_name_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                model_pool.save_named_key('', 'sk-1', env_dir(td, ()))

    def test_the_env_variable_still_wins(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {'CODEX_NAMED_KEY_ENV': 'sk-env'}):
                self.assertEqual(model_pool.named_key('CODEX_NAMED_KEY_ENV', env_dir(td, ())), 'sk-env')

    def test_an_unknown_name_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(model_pool.named_key(ABSENT_KEY, env_dir(td, ())), '')


class HttpErrorBodyScrubTests(unittest.TestCase):
    """网关把请求头原样回显进错误体时，凭据不能流进 UI／任务 JSON（R1777 审计）。"""

    def test_error_body_is_scrubbed_before_it_leaves_the_transport(self):
        import io
        import urllib.error
        from unittest import mock
        key = 'sk-abcdef1234567890'
        error = urllib.error.HTTPError('https://x.test', 401, 'no', {}, io.BytesIO(
            ('invalid key ' + key + ' api_key=zzz999').encode()))
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch.object(model_pool, '_http_opener', return_value=opener):
            result = model_pool._http_transport('https://x.test', {}, {'Authorization': 'Bearer ' + key}, 5)
        self.assertFalse(result['ok'])
        self.assertNotIn(key, result['error'])
        self.assertNotIn('zzz999', result['error'])
        self.assertIn('HTTP 401', result['error'])
