import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image
from infra import client_accounts, gflow_images, model_pool, pet_llm


class ModelConnectionTests(unittest.TestCase):
    def test_pet_uses_configured_route_on_rejection_or_missing_primary(self):
        def credential(name, program):
            if name == 'MISSING':
                raise ValueError('missing')
            return name
        for primary in ('FIRST', 'MISSING'):
            with self.subTest(primary=primary), tempfile.TemporaryDirectory() as folder:
                calls = []
                def transport(url, payload, headers, timeout):
                    calls.append(headers['Authorization'])
                    if calls[-1] == 'Bearer FIRST':
                        return {'ok': False, 'status': 429}
                    return {'ok': True, 'status': 200, 'data': {}}
                client = pet_llm.Client(program=folder, transport=transport)
                config = dict(key_env=primary, connections=[
                    {}, dict(base_url='https://unused.invalid', key_env='MISSING'),
                    dict(base_url='https://fallback.invalid', key_env='SECOND')])
                with patch.object(model_pool, 'credential', side_effect=credential):
                    result = client.ask('intent.route', '测试', model_patch=config)
                self.assertTrue(result['ok'])
                self.assertEqual(calls, ['Bearer FIRST', 'Bearer SECOND'] if primary == 'FIRST' else ['Bearer SECOND'])

    def test_client_account_is_a_single_argument(self):
        config = dict(program='example', client_accounts=[
            dict(option='--profile',value='account one'), dict(option='--profile',value='account two')])
        self.assertEqual(client_accounts.account_args(config), ['--profile','account one'])
        self.assertEqual(client_accounts.account_args(config), ['--profile','account two'])

    def test_flow_quota_advances_to_next_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder)/'result.png'
            exe = Path(folder)/'gflow.exe'
            exe.touch()
            calls = []
            class Child:
                def __init__(self, kind, args, stdout, **kwargs):
                    profile = args[args.index('--profile') + 1]
                    calls.append(profile)
                    self.returncode = int(profile == 'first')
                    if self.returncode:
                        stdout.write(json.dumps({'error':{'type':'https://gflow-cli.dev/errors/rate-limit',
                                                         'charged':'no'}}).encode())
                    else:
                        Image.new('RGB',(8,8)).save(args[args.index('--out-file')+1])
                def poll(self): return self.returncode
                def __enter__(self): return self
                def __exit__(self,*args): pass
            cfg = dict(program=str(exe),model='nano2-lite',profiles=['first','second'])
            with patch.object(gflow_images,'spawn',Child):
                gflow_images.generate(cfg, '石板巷', [], dest, threading.Event())
            self.assertEqual(calls,['first','second'])
            self.assertEqual(cfg['profiles'][0],'second')
            with Image.open(dest) as image:
                self.assertEqual(image.format,'PNG')
