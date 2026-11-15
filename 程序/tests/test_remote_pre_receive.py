"""私有服务器 pre-receive 门禁的纯函数部分：凭据扫描与更新解析。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '维护记录' / '基准脚本'))
import remote_pre_receive as hook  # noqa: E402


class RemotePreReceiveTests(unittest.TestCase):
    def test_secret_patterns_catch_high_confidence_shapes(self):
        diff = ('+++ b/程序/leak.py\n'
                '@@ -0,0 +1,3 @@\n'
                '+key = ' + 'ghp_' + 'a' * 36 + '\n'
                '+aws = ' + 'AKIA' + 'B' * 16 + '\n'
                '+slack = ' + 'xoxb-' + '1' * 20 + '\n'
                '+g = ' + 'AIza' + 'c' * 35 + '\n'
                '+pem = ' + '-----BEGIN ' + 'RSA ' + 'PRIVATE KEY-----' + '\n'
                '+ok = "normal line"\n')
        hits = hook.scan_added_lines(diff)
        rules = {hit.split(':')[-1] for hit in hits}
        self.assertEqual(rules, {'github-token', 'aws-access-key', 'slack-token',
                                 'google-api-key', 'private-key'})
        self.assertEqual(len(hits), 5)

    def test_clean_diff_has_no_hits(self):
        diff = '+++ b/程序/good.py\n@@ -0,0 +1 @@\n+x = 1\n'
        self.assertEqual(hook.scan_added_lines(diff), [])

    def test_hook_is_executable_python_and_covers_program_prefix(self):
        source = Path(hook.__file__).read_text(encoding='utf-8')
        compile(source, hook.__file__, 'exec')
        self.assertIn("PROGRAM_PREFIX = '程序/'", source)
        self.assertIn('core.quotepath=false', source)


if __name__ == '__main__':
    unittest.main()
