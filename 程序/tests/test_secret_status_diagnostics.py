# -*- coding: utf-8 -*-
"""O44：密钥状态可诊断、诊断包不泄露、用户正文与安全诊断分开。"""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import diagnostic_capture
from infra import log_maintenance
from infra import model_diagnostics
import model_secrets

BLOB_HEADER = bytes.fromhex('01000000d08c9ddf0115d1118c7a00c04fc297eb')


def failing_protector(*_args, **_kwargs):
    raise OSError('DPAPI 解不开')


def echo_protector(data, decrypt=False, label='模型 API Key'):
    if decrypt:
        return bytes(data).replace(b'enc:', b'')
    return b'enc:' + bytes(data)


class SecretStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.original = model_secrets.PROTECTOR
        self.addCleanup(lambda: setattr(model_secrets, 'PROTECTOR', self.original))

    def write(self, name, data):
        target = model_secrets.path(name, self.root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def test_unconfigured_when_missing_or_nameless(self):
        model_secrets.PROTECTOR = echo_protector
        self.assertEqual(model_secrets.diagnose('', self.root)['state'], model_secrets.UNCONFIGURED)
        report = model_secrets.diagnose('MISSING_KEY', self.root)
        self.assertEqual(report['state'], model_secrets.UNCONFIGURED)
        self.assertFalse(report['ok'])

    def test_ready_roundtrip_never_repeats_the_secret(self):
        model_secrets.PROTECTOR = echo_protector
        model_secrets.save('MINE_KEY', 'sk-very-secret', self.root)
        report = model_secrets.diagnose('MINE_KEY', self.root)
        self.assertEqual(report['state'], model_secrets.READY)
        self.assertTrue(report['ok'])
        self.assertNotIn('sk-very-secret', json.dumps(report, ensure_ascii=False))

    def test_corrupt_file_is_reported_as_corrupt(self):
        model_secrets.PROTECTOR = failing_protector
        self.write('BROKEN_KEY', b'\x00not a dpapi blob')
        self.assertEqual(model_secrets.diagnose('BROKEN_KEY', self.root)['state'],
                         model_secrets.CORRUPT)

    def test_empty_file_is_corrupt_not_unconfigured(self):
        model_secrets.PROTECTOR = failing_protector
        self.write('EMPTY_KEY', b'')
        self.assertEqual(model_secrets.diagnose('EMPTY_KEY', self.root)['state'],
                         model_secrets.CORRUPT)

    def test_other_user_blob_is_not_called_corrupt(self):
        model_secrets.PROTECTOR = failing_protector
        self.write('FOREIGN_KEY', BLOB_HEADER + b'\x99' * 40)
        self.assertEqual(model_secrets.diagnose('FOREIGN_KEY', self.root)['state'],
                         model_secrets.OTHER_USER)

    def test_verdict_separates_auth_failure_from_unconfigured(self):
        model_secrets.PROTECTOR = echo_protector
        model_secrets.save('MINE_KEY', 'sk-secret', self.root)
        missing = model_secrets.diagnose('MISSING_KEY', self.root)
        failed = model_secrets.verdict('MINE_KEY', self.root, error_class='auth')
        self.assertEqual(failed['state'], model_secrets.AUTH_FAILED)
        self.assertNotEqual(failed['text'], missing['text'])
        self.assertEqual(model_secrets.verdict('MISSING_KEY', self.root,
                                               error_class='auth')['state'],
                         model_secrets.UNCONFIGURED)

    def test_all_five_states_read_differently(self):
        model_secrets.PROTECTOR = echo_protector
        model_secrets.save('MINE_KEY', 'sk-secret', self.root)
        texts = {
            model_secrets.diagnose('MINE_KEY', self.root)['text'],
            model_secrets.diagnose('MISSING_KEY', self.root)['text'],
            model_secrets.verdict('MINE_KEY', self.root, error_class='auth')['text'],
        }
        model_secrets.PROTECTOR = failing_protector
        self.write('BROKEN_KEY', b'\x00broken')
        self.write('FOREIGN_KEY', BLOB_HEADER + b'\x99' * 40)
        texts.add(model_secrets.diagnose('BROKEN_KEY', self.root)['text'])
        texts.add(model_secrets.diagnose('FOREIGN_KEY', self.root)['text'])
        self.assertEqual(len(texts), 5)


class DiagnosticCapturePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.logs = root / 'logs'
        self.error = self.logs / '启动错误.log'
        self.state = self.logs / 'diagnostics' / 'latest.json'
        self.patch = patch.multiple(diagnostic_capture, PROGRAM=root, LOGS=self.logs,
                                    ERROR_LOG=self.error, STATE_FILE=self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.logs.mkdir(parents=True, exist_ok=True)

    def test_preview_detail_lists_files_and_retention(self):
        self.error.write_text('ok', encoding='utf-8')
        rows = diagnostic_capture.preview_detail()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['name'], '启动错误.log')
        self.assertEqual(row['keep_days'], log_maintenance.RETENTION_DAYS)
        self.assertFalse(row['expired'])
        self.assertTrue(row['expires_at'] > row['modified'])
        self.assertIn('%d 天' % log_maintenance.RETENTION_DAYS,
                      diagnostic_capture.retention_note())

    def test_preview_detail_flags_expired_without_deleting(self):
        self.error.write_text('old', encoding='utf-8')
        old = time.time() - (log_maintenance.RETENTION_DAYS + 5) * 86400
        os.utime(self.error, (old, old))
        self.assertTrue(diagnostic_capture.preview_detail()[0]['expired'])
        self.assertTrue(self.error.is_file())

    def test_url_query_parameters_are_redacted_on_export(self):
        (self.logs / 'sanhu_progress.log').write_text(
            'GET https://api.example.com/v1/chat?api_key=sk-live-abc&model=x\n'
            'retry https://s.example.com/t?signature=S3CR3T&x=1\n', encoding='utf-8')
        output = diagnostic_capture.export(Path(self.temp.name) / 'bundle.zip')
        with zipfile.ZipFile(output) as archive:
            text = '\n'.join(archive.read(n).decode('utf-8') for n in archive.namelist())
        self.assertNotIn('sk-live-abc', text)
        self.assertNotIn('S3CR3T', text)
        self.assertIn('[已脱敏]', text)

    def test_export_never_leaves_the_whitelist(self):
        outside = Path(self.temp.name) / 'projects' / '第1集' / 'script.txt'
        outside.parent.mkdir(parents=True)
        outside.write_text('用户的剧本正文不算诊断', encoding='utf-8')
        self.error.write_text('boom', encoding='utf-8')
        # latest.json 与 metrics_summary.json（I14/R3623 指标快照）是白名单成员：造一个让 latest.json 确定在场。
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text('{"degradations": []}', encoding='utf-8')
        # 此例只验证程序日志白名单；产物读取计数由单独用例显式提供。
        with patch.object(diagnostic_capture.artifact_schema, 'read_state_counts', return_value={}):
            output = diagnostic_capture.export(Path(self.temp.name) / 'bundle.zip')
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            text = '\n'.join(archive.read(n).decode('utf-8') for n in names)
        self.assertEqual(sorted(n for n in names if n != 'manifest.json'),
                         ['logs/diagnostics/latest.json', 'logs/metrics_summary.json',
                          'logs/启动错误.log'])
        self.assertNotIn('用户的剧本正文', text)

    def test_export_includes_only_explicit_artifact_state_diagnostic_and_logs(self):
        self.error.write_text('boom', encoding='utf-8')
        counts = {'script_manifest': {'legacy': 1}}
        with patch.object(diagnostic_capture.artifact_schema, 'read_state_counts', return_value=counts):
            output = diagnostic_capture.export(Path(self.temp.name) / 'bundle.zip')
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(sorted(archive.namelist()),
                             ['logs/diagnostics/latest.json', 'logs/metrics_summary.json',
                              'logs/启动错误.log', 'manifest.json'])
            state = json.loads(archive.read('logs/diagnostics/latest.json'))
            manifest = json.loads(archive.read('manifest.json'))
        self.assertEqual(state['artifact_versions'], counts)
        self.assertEqual(sorted(manifest['included']),
                         ['logs/diagnostics/latest.json', 'logs/metrics_summary.json',
                          'logs/启动错误.log'])


class ModelDiagnosticsScrubTests(unittest.TestCase):
    def test_echoed_credential_in_context_is_scrubbed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = model_diagnostics.record(
                folder, {'ok': False, 'error_class': 'auth'},
                {'stage': 'script', 'note': 'server echoed api_key=sk-echoed-123'})
            raw = path.read_text(encoding='utf-8')
        self.assertNotIn('sk-echoed-123', raw)
        self.assertIn('[已脱敏]', raw)

    def test_response_meta_strings_are_scrubbed(self):
        saved = model_diagnostics.event(
            {'ok': True, 'response_meta': {'response_id': 'req_1',
                                           'finish_reason': 'secret=leak-me'}})
        self.assertEqual(saved['response_id'], 'req_1')
        self.assertNotIn('leak-me', json.dumps(saved, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
