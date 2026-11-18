# -*- coding: utf-8 -*-
"""L1 任务书轮3（丢失更新）：读失败处置不写回空值 + ``agent.publication.access()``
跨进程互斥覆盖 account_store／project_settings／usage_history／model_pool 四处读—改—写，
以及 lease_verifier 签名长度不符负例（正例／篡改／未知 kid 已由 test_account_client 覆盖）。
"""
import json
import os
import subprocess
import threading
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_account_client import KEYS, _b64, payload, sign

import infra.account_store as account_store
import infra.lease_verifier as lease_verifier
import infra.model_pool as model_pool
from infra.config_patch import ConfigSnapshot
import infra.project_settings as project_settings
import infra.usage_history as usage_history

PROGRAM = Path(__file__).resolve().parents[1]


def _spawn_pair(script, args):
    """起两个子进程跑同一段脚本（跨进程并发写），全部返回 0 才继续。"""
    procs = [subprocess.Popen([sys.executable, '-B', '-c', script, *args],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
             for _ in range(2)]
    for proc in procs:
        _out, err = proc.communicate(timeout=300)
        assert proc.returncode == 0, err


class AccountStoreStrictReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / '账户' / 'session.json'

    def _seed(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return self.path.read_bytes()

    def test_missing_file_starts_empty_and_writes(self):
        data = account_store.save_session({'email': 'a@b.c', 'refresh_token': 'rt'}, self.path)
        self.assertEqual(data['email'], 'a@b.c')
        self.assertTrue(self.path.is_file())

    def test_read_failure_refuses_write_and_preserves_bytes(self):
        original = self._seed({'email': 'a@b.c', 'refresh_token': 'rt', 'server_time': 5})
        with mock.patch.object(account_store, 'read',
                               side_effect=PermissionError(13, 'denied by av')):
            with self.assertRaises(ValueError) as ctx:
                account_store.save_session({'lease': 'x'}, self.path)
        self.assertIn('账户会话文件', str(ctx.exception))
        self.assertIn(str(self.path), str(ctx.exception))
        self.assertIn('重新登录', str(ctx.exception))
        self.assertEqual(self.path.read_bytes(), original)

    def test_corrupt_json_refuses_write_and_preserves_bytes(self):
        original = self._seed({'email': 'a@b.c'})
        self.path.write_bytes(b'{"email": "a@b.c",')          # 截断的坏 JSON
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            account_store.mark_update_seen('9.9.9', self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_merge_write_keeps_fields_and_server_time_only_grows(self):
        account_store.save_session({'email': 'a@b.c', 'refresh_token': 'rt',
                                    'server_time': 100}, self.path)
        account_store.save_session({'lease': 'L', 'server_time': 50}, self.path)
        data = account_store.load(self.path)
        self.assertEqual(data['refresh_token'], 'rt')
        self.assertEqual(data['lease'], 'L')
        self.assertEqual(data['server_time'], 100)
        account_store.note_server_time(200, self.path)
        self.assertEqual(account_store.load(self.path)['server_time'], 200)

    def test_two_processes_merge_session_fields_without_loss(self):
        script = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra import account_store\n"
            "path = sys.argv[2]\n"
            "tag = sys.argv[3]\n"
            "for i in range(30):\n"
            "    account_store.save_session({'email': tag + '@x', 'refresh_token': tag + '-' + str(i),\n"
            "                                  'lease': 'lease-' + tag + '-' + str(i)}, path)\n"
            "    account_store.mark_update_seen('v' + tag + '-' + str(i), path)\n"
            "print('done', flush=True)\n"
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'session.json'
            _spawn_pair(script, [str(PROGRAM), str(path), 'x'])
            # 两个进程写同一组键：最后一次写入者的值胜出，但文件必须始终是合法 JSON、
            # 且 server_time／last_email 等合并字段不被清空。
            data = json.loads(path.read_text(encoding='utf-8'))
        self.assertIn('refresh_token', data)
        self.assertIn('lease', data)
        self.assertIn('update_seen', data)
        self.assertTrue(data['refresh_token'].startswith(('x-', 'y-')))


class ProjectSettingsWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'proj'
        self.project.mkdir()

    def test_corrupt_file_is_quarantined_then_put_succeeds(self):
        target = project_settings.file(self.project)
        broken = b'{"auto_review": tru'
        target.write_bytes(broken)
        self.assertIs(project_settings.put(self.project, 'auto_review', True), True)
        data = json.loads(target.read_text(encoding='utf-8'))
        self.assertIs(data['auto_review'], True)
        corrupt = target.with_name(target.name + '.corrupt')
        self.assertTrue(corrupt.is_file())
        self.assertEqual(corrupt.read_bytes(), broken)

    def test_put_merges_without_dropping_other_keys(self):
        project_settings.put(self.project, 'auto_review', True)
        project_settings.put(self.project, 'auto_adopt', True)
        data = json.loads(project_settings.file(self.project).read_text(encoding='utf-8'))
        self.assertIs(data['auto_review'], True)
        self.assertIs(data['auto_adopt'], True)

    def test_two_processes_distinct_keys_all_survive(self):
        script = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra import project_settings\n"
            "project, tag = sys.argv[2], sys.argv[3]\n"
            "for i in range(50):\n"
            "    project_settings.put(project, 'k_' + tag + '_' + str(i), i)\n"
            "print('done', flush=True)\n"
        )
        procs = [subprocess.Popen([sys.executable, '-B', '-c', script,
                                   str(PROGRAM), str(self.project), tag],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
                 for tag in ('a', 'b')]
        for proc in procs:
            _out, err = proc.communicate(timeout=300)
            self.assertEqual(proc.returncode, 0, err)
        data = json.loads(project_settings.file(self.project).read_text(encoding='utf-8'))
        self.assertEqual(len(data), 100)
        self.assertTrue(all(('k_a_%d' % i) in data and ('k_b_%d' % i) in data
                            for i in range(50)))


class UsageHistoryWriteTests(unittest.TestCase):
    @staticmethod
    def _days(td):
        path = Path(td) / usage_history.HISTORY_DIR / '2026-11.json'
        return json.loads(path.read_text(encoding='utf-8'))['days']

    def test_record_today_merges_days_across_calls(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(usage_history.record_today(td, '2026-11-17', 10, '1.5', 2))
            self.assertTrue(usage_history.record_today(td, '2026-11-18', 20, '2.5', 3))
            days = self._days(td)
            self.assertIn('2026-11-17', days)
            self.assertIn('2026-11-18', days)

    def test_two_processes_archive_different_days_without_loss(self):
        script = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra import usage_history\n"
            "project, offset = sys.argv[2], int(sys.argv[3])\n"
            "for i in range(10):\n"
            "    usage_history.record_today(project, '2026-11-%02d' % (10 + offset + i),\n"
            "                               100 + i, '1', 1)\n"
            "print('done', flush=True)\n"
        )
        with tempfile.TemporaryDirectory() as td:
            procs = [subprocess.Popen([sys.executable, '-B', '-c', script,
                                       str(PROGRAM), td, str(offset)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
                     for offset in (0, 10)]
            for proc in procs:
                _out, err = proc.communicate(timeout=300)
                self.assertEqual(proc.returncode, 0, err)
            days = self._days(td)
        self.assertEqual(len(days), 20)          # 两进程各写 10 个不同日期，零丢失


class ConfigPatchTests(unittest.TestCase):
    def test_only_changed_fields_replace_latest_and_baseline_is_deep(self):
        data = ConfigSnapshot({'models': {'old': {}}, 'health': {'at': 'old'}, 'removed': True})
        data['models']['new'] = {}
        del data['removed']
        data['added'] = None
        latest = {'models': {'old': {}}, 'health': {'at': 'new'}, 'removed': False, 'other': True}
        self.assertEqual(data.apply_to(latest),
                         {'models': {'old': {}, 'new': {}}, 'health': {'at': 'new'},
                          'added': None, 'other': True})
        self.assertFalse(latest['removed'])

    def test_copy_and_update_keep_explicit_same_empty_assignment(self):
        data = ConfigSnapshot({'health': {}, 'deleted': True})
        copied = data.copy()
        copied.update({'health': {}})
        del copied['deleted']
        self.assertEqual(copied.apply_to({'health': {'at': 'new'}, 'deleted': True}), {'health': {}})
        self.assertEqual(data, {'health': {}, 'deleted': True})
        self.assertEqual(json.loads(json.dumps(copied)), {'health': {}})
        self.assertEqual(ConfigSnapshot({}).apply_to({'keep': True}), {'keep': True})


class ModelPoolUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.program = Path(self.temp.name)
        self.config = model_pool.config_file(self.program)
        self.config.parent.mkdir(parents=True, exist_ok=True)

    def _seed_config(self, data):
        self.config.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def test_record_health_merges_without_wiping_models(self):
        self._seed_config({'models': {'m1': {'model': 'gpt-x'}}, 'agent': {'name': '三虎'}})
        entry = model_pool.record_health('m1', {'ok': True, 'at': 't', 'config_version': 'v'},
                                         program=self.program)
        self.assertTrue(entry['ok'])
        data = json.loads(self.config.read_text(encoding='utf-8'))
        self.assertIn('m1', data['models'])
        self.assertEqual(data['agent']['name'], '三虎')
        self.assertTrue(data[model_pool.HEALTH_KEY]['m1']['ok'])
        # 再记一条别的模型：第一条健康度保留（锁内重读合并，不是整份覆盖）
        model_pool.record_health('m2', {'ok': False, 'at': 't2'}, program=self.program)
        data = json.loads(self.config.read_text(encoding='utf-8'))
        self.assertIn('m1', data[model_pool.HEALTH_KEY])
        self.assertIn('m2', data[model_pool.HEALTH_KEY])

    def test_unreadable_config_skips_write_instead_of_wiping(self):
        original = b'{"models": {"m1": {"model": "gpt-x"}},'
        self.config.write_bytes(original)
        entry = model_pool.record_health('m1', {'ok': True}, program=self.program)
        self.assertTrue(entry['ok'])
        self.assertEqual(self.config.read_bytes(), original)   # 坏配置原样保留，不盖空表

    def _controlled_store_and_health(self, initial, change, *, health_first=True):
        """管道只控制读写顺序，不用调度概率替代跨进程契约。"""
        self._seed_config(initial)
        script = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra import model_pool\n"
            "program = sys.argv[2]\n"
            "data = model_pool.raw(program)\n"
            "print('ready', flush=True)\n"
            "if sys.stdin.readline().strip() != 'publish': raise RuntimeError('no release')\n"
            + change + "\nmodel_pool.store(data, program)\n"
        )
        health = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra import model_pool\n"
            "entry = model_pool.record_health('shared', {'ok': True, 'at': 'new'}, program=sys.argv[2])\n"
            "assert entry['at'] == 'new'\n"
        )
        env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        proc = subprocess.Popen(
            [sys.executable, '-B', '-c', script, str(PROGRAM), str(self.program)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        ready = []
        reader = threading.Thread(target=lambda: ready.append(proc.stdout.readline()), daemon=True)
        reader.start()
        try:
            reader.join(timeout=20)
            self.assertFalse(reader.is_alive(), 'store child did not read its snapshot')
            self.assertEqual(ready, ['ready\n'])
            def record_health():
                result = subprocess.run(
                    [sys.executable, '-B', '-c', health, str(PROGRAM), str(self.program)],
                    capture_output=True, text=True, encoding='utf-8', env=env, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(result.returncode, 0, result.stderr)
            if health_first:
                record_health()
            _out, err = proc.communicate('publish\n', timeout=30)
            self.assertEqual(proc.returncode, 0, err)
            if not health_first:
                record_health()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=10)
            reader.join(timeout=10)
        return json.loads(self.config.read_text(encoding='utf-8'))

    def test_stale_store_keeps_concurrent_health_in_both_orders(self):
        changes = (
            "data['models']['added'] = {'model': 'added'}",
            "data = data.copy(); data['models']['added'] = {'model': 'added'}",
            "data = model_pool.upsert(data, {'model': 'added'}, 'added')",
            "data = model_pool.remove(data, 'old')",
            "data = model_pool.with_tasks(data, {'default': 'added'})",
        )
        for has_health in (False, True):
            initial = {'models': {'old': {'model': 'old'}}, 'other': {'keep': True}}
            if has_health:
                initial[model_pool.HEALTH_KEY] = {'shared': {'ok': False, 'at': 'old'}}
            for health_first in (False, True):
                for change in changes:
                    with self.subTest(has_health=has_health, health_first=health_first, change=change):
                        data = self._controlled_store_and_health(initial, change, health_first=health_first)
                        self.assertEqual(data[model_pool.HEALTH_KEY]['shared']['at'], 'new')
                        self.assertEqual(data['other'], {'keep': True})
                        if 'remove(' in change:
                            self.assertNotIn('old', data['models'])
                            self.assertIn('old', data['deleted_desktop_models'])
                        elif 'with_tasks(' in change:
                            self.assertEqual(data['agent']['models']['default'], 'added')
                        else:
                            self.assertIn('added', data['models'])

    def test_stale_store_explicit_clear_and_delete_are_not_merged_back(self):
        initial = {'models': {'old': {'model': 'old'}},
                   model_pool.HEALTH_KEY: {'shared': {'ok': False, 'at': 'old'}},
                   'other': {'keep': True}}
        for old_health in ({}, initial[model_pool.HEALTH_KEY]):
            initial[model_pool.HEALTH_KEY] = old_health
            for change, expected in (("data[model_pool.HEALTH_KEY] = {}", {}),
                                     ("data.update({model_pool.HEALTH_KEY: {}})", {}),
                                     ("data[model_pool.HEALTH_KEY] = None", None),
                                     ("del data[model_pool.HEALTH_KEY]", 'missing')):
                with self.subTest(old_health=old_health, change=change):
                    data = self._controlled_store_and_health(initial, change)
                    self.assertEqual(data.get(model_pool.HEALTH_KEY, 'missing'), expected)
                    self.assertEqual(data['models'], initial['models'])
        data = self._controlled_store_and_health(initial, "data['models'] = {}")
        self.assertEqual(data['models'], {})
        self.assertEqual(data[model_pool.HEALTH_KEY]['shared']['at'], 'new')

    def test_snapshot_metadata_stays_in_memory_and_dict_conversion_is_full_replace(self):
        initial = {'models': {}, model_pool.HEALTH_KEY: {'old': {}}}
        self._seed_config(initial)
        data = model_pool.raw(self.program)
        self.assertIsInstance(data, dict)
        self.assertEqual(json.loads(json.dumps(data)), initial)
        self.assertEqual(json.loads(json.dumps(data.copy())), initial)
        full = dict(data)
        del full[model_pool.HEALTH_KEY]
        model_pool.store(full, self.program)
        self.assertEqual(json.loads(self.config.read_text(encoding='utf-8')), {'models': {}})

    def test_plain_dict_store_still_replaces_the_entire_document(self):
        self._seed_config({'models': {'old': {'model': 'old'}}, model_pool.HEALTH_KEY: {'old': {}}})
        model_pool.store({'models': {}}, self.program)
        self.assertEqual(json.loads(self.config.read_text(encoding='utf-8')), {'models': {}})

    def test_store_keeps_health_written_after_the_config_snapshot(self):
        before = model_pool.raw(self.program)
        model_pool.record_health('shared', {'ok': True, 'at': 'new'}, program=self.program)
        before['models'] = {'new_model': {'model': 'fixture'}}
        model_pool.store(before, self.program)
        persisted = model_pool.raw(self.program)
        self.assertEqual(persisted['models'], before['models'])
        self.assertEqual(persisted[model_pool.HEALTH_KEY]['shared']['at'], 'new')

    def test_two_processes_health_and_store_do_not_rollback(self):
        script_health = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra import model_pool\n"
            "program = sys.argv[2]\n"
            "for i in range(15):\n"
            "    model_pool.record_health('shared', {'ok': True, 'at': 't%d' % i}, program=program)\n"
            "print('done', flush=True)\n"
        )
        script_store = (
            "import sys, json\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra import model_pool\n"
            "program, tag = sys.argv[2], sys.argv[3]\n"
            "for i in range(15):\n"
            "    data = model_pool.raw(program)\n"
            "    models = data.get('models') or {}\n"
            "    models['u_' + tag + '_' + str(i)] = {'model': 'm'}\n"
            "    data['models'] = models\n"
            "    model_pool.store(data, program)\n"
            "print('done', flush=True)\n"
        )
        procs = [
            subprocess.Popen([sys.executable, '-B', '-c', script_health,
                              str(PROGRAM), str(self.program)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW),
            subprocess.Popen([sys.executable, '-B', '-c', script_store,
                              str(PROGRAM), str(self.program), 'u'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW),
        ]
        for proc in procs:
            _out, err = proc.communicate(timeout=300)
            self.assertEqual(proc.returncode, 0, err)
        data = json.loads(self.config.read_text(encoding='utf-8'))
        self.assertIn('shared', data.get(model_pool.HEALTH_KEY, {}))
        self.assertEqual(len([k for k in data.get('models', {}) if k.startswith('u_u_')]), 15)


class LeaseVerifierSignatureTests(unittest.TestCase):
    def test_signature_length_mismatch_is_rejected(self):
        body, _sig = sign(payload()).split('.')
        short = _b64(b'\x01' * 16)                     # 远短于 RSA-2048 的 256 字节
        self.assertIsNone(lease_verifier.verify(body + '.' + short, KEYS))
        long_sig = _b64(b'\x01' * 300)                 # 长于模长同样拒绝
        self.assertIsNone(lease_verifier.verify(body + '.' + long_sig, KEYS))


if __name__ == '__main__':
    unittest.main()
