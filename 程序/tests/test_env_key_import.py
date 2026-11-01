"""项目目录 .env 密钥：第一次迁进本机加密存储，之后不再读该文件，文件本身不删。"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import api_endpoints
import model_secrets


class EnvKeyImportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.env = self.project / '.env'
        original = model_secrets.PROTECTOR
        self.addCleanup(setattr, model_secrets, 'PROTECTOR', original)
        model_secrets.PROTECTOR = lambda data, decrypt=False, label='': (
            data[len(b'enc:'):] if decrypt else b'enc:' + data)
        self.config = {'key_env': 'FAKE_TEST_KEY', 'project_dir': str(self.project),
                       'secret_root': str(self.root)}

    def test_first_read_imports_then_keeps_file(self):
        self.env.write_text('# c\nFAKE_TEST_KEY=sk-abc\nOTHER=\nBAD=has space\n', encoding='utf-8')
        self.assertEqual(api_endpoints.configured_key(self.config), 'sk-abc')
        self.assertTrue(self.env.is_file())
        self.assertEqual(model_secrets.load('FAKE_TEST_KEY', root=self.root), 'sk-abc')
        self.assertEqual(model_secrets.load('BAD', root=self.root), '')

    def test_after_import_the_env_file_is_not_read_again(self):
        self.env.write_text('FAKE_TEST_KEY=sk-abc\n', encoding='utf-8')
        api_endpoints.configured_key(self.config)
        self.env.write_text('FAKE_TEST_KEY=sk-changed\nNEW_ONE=sk-new\n', encoding='utf-8')
        self.assertEqual(api_endpoints.configured_key(self.config), 'sk-abc')
        self.assertEqual(model_secrets.load('NEW_ONE', root=self.root), '')

    def test_existing_encrypted_key_is_never_overwritten(self):
        model_secrets.save('FAKE_TEST_KEY', 'sk-local', root=self.root)
        self.env.write_text('FAKE_TEST_KEY=sk-from-env\n', encoding='utf-8')
        self.assertEqual(api_endpoints.configured_key(self.config), 'sk-local')

    def test_marker_holds_no_secret(self):
        self.env.write_text('FAKE_TEST_KEY=sk-abc\n', encoding='utf-8')
        api_endpoints.configured_key(self.config)
        marker = self.root.joinpath(*model_secrets.IMPORT_MARKER).read_text(encoding='utf-8')
        self.assertNotIn('sk-abc', marker)

    def test_save_failure_is_not_marked_and_retries(self):
        self.env.write_text('FAKE_TEST_KEY=sk-abc\n', encoding='utf-8')
        good = model_secrets.PROTECTOR
        model_secrets.PROTECTOR = lambda *a, **k: (_ for _ in ()).throw(OSError('x'))
        with self.assertRaises(ValueError):
            api_endpoints.configured_key(self.config)
        model_secrets.PROTECTOR = good
        self.assertEqual(api_endpoints.configured_key(self.config), 'sk-abc')


if __name__ == '__main__':
    unittest.main()
