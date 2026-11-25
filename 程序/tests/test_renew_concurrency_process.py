"""Two desktop processes coordinate renewal using the same temporary session."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from contract.service_contract import success
from infra import account_store, lease_verifier
from orchestrator.account_controller import AccountController
from tests.test_account_client import DID, KEYS, NOW, _Store, payload, sign


def _worker(folder, name):
    path = folder / 'session.json'
    lease_verifier.PUBLIC_KEYS = KEYS

    class Client:
        def renew(self, token, device_id):
            assert token == 'first' and device_id == DID
            with (folder / 'requests.txt').open('a', encoding='utf-8') as stream:
                stream.write(name + '\n')
            return success({'refresh_token': 'successor', 'lease': sign(payload(sid='successor-session'))})

    def submit(work, done, label):
        (folder / name).touch()
        deadline = time.monotonic() + 15
        while not ((folder / 'first').exists() and (folder / 'second').exists()):
            if time.monotonic() >= deadline:
                raise RuntimeError('Workers did not reach the renewal barrier')
            time.sleep(0.01)
        done(work())

    results = []
    ctl = AccountController(submit=submit, clock=lambda: NOW, store=_Store(path), client=Client())
    assert ctl.renew(results.append)
    result = results[0]
    assert result.ok and lease_verifier.verify(result.data['lease'])
    assert account_store.load(path)['refresh_token'] == 'successor'


class RenewalProcessTests(unittest.TestCase):
    def test_two_processes_read_one_successor_and_never_clear_the_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            path = folder / 'session.json'
            account_store.save_session({'refresh_token': 'first', 'lease': sign(payload())}, path)
            program = Path(__file__).resolve().parents[1]
            command = [sys.executable, '-m', 'tests.test_renew_concurrency_process', temporary]
            workers = [subprocess.Popen([*command, name], cwd=program, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.PIPE) for name in ('first', 'second')]
            try:
                for worker in workers:
                    _, errors = worker.communicate(timeout=25)
                    self.assertEqual(worker.returncode, 0, errors.decode(errors='replace'))
            finally:
                for worker in workers:
                    if worker.poll() is None:
                        worker.kill()
                    worker.communicate()
            self.assertEqual(len((folder / 'requests.txt').read_text(encoding='utf-8').splitlines()), 1)
            self.assertEqual(account_store.load(path)['refresh_token'], 'successor')


    def test_response_does_not_restore_session_cleared_during_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'session.json'
            account_store.save_session({'refresh_token': 'first', 'lease': sign(payload())}, path)

            class Client:
                def renew(self, token, device_id):
                    account_store.clear_session(path)
                    return success({'refresh_token': 'successor', 'lease': sign(payload())})

            result = []
            ctl = AccountController(submit=lambda work, done, label: done(work()),
                                    store=_Store(path), client=Client())
            self.assertTrue(ctl.renew(result.append))
            self.assertFalse(result[0].ok)
            self.assertEqual(result[0].data['code'], 'session_invalid')
            self.assertNotIn('refresh_token', account_store.load(path))


if __name__ == '__main__':
    _worker(Path(sys.argv[1]), sys.argv[2])
