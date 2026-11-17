"""测试隐藏桌面强制执行（R3039）：载体入库、运行器硬闸、后台补跑不降级直跑。"""
import unittest

from tests.architecture._scan import ROOT

RUN_SELFTESTS = ROOT / 'run_selftests.py'
SMOKE_TEST = ROOT / 'smoke_test.py'
GUI_HIDDEN = ROOT / 'scripts' / 'gui_hidden.py'
AUTO_FULL_SAFE = ROOT / 'scripts' / 'auto_full_safe.py'

OLD_SILENT_FALLBACK = ('else:\n'
                       '            result = subprocess.run(cmd, cwd=program, env=env, '
                       'stdout=log, stderr=subprocess.STDOUT, check=False, **quiet)')


def _text(path):
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


class HiddenDesktopGateTests(unittest.TestCase):
    """隐藏桌面强制执行的静态守护：载体入库、自包装硬闸在位、静默降级已除。"""

    def test_helper_module_is_in_repo(self):
        self.assertTrue(GUI_HIDDEN.is_file(),
                        'scripts/gui_hidden.py 必须入库：任何工作树/干净检出都要拿得到')
        text = _text(GUI_HIDDEN)
        for marker in ('CreateDesktopW', 'lpDesktop', '--probe'):
            self.assertIn(marker, text, 'scripts/gui_hidden.py 缺关键实现/探测子命令')

    def test_run_selftests_self_wraps(self):
        text = _text(RUN_SELFTESTS)
        for marker in ('_run_hidden', 'DRAMA_HIDDEN_DESKTOP', '--visible', '_scope_has_tk'):
            self.assertIn(marker, text, 'run_selftests.py 缺隐藏桌面自包装硬闸')

    def test_smoke_wraps_widget_checks_and_probes(self):
        text = _text(SMOKE_TEST)
        for marker in ('_smoke_hidden', '--probe'):
            self.assertIn(marker, text, 'smoke_test.py 缺 Tk 检查自包装/隐藏桌面探测')

    def test_auto_full_safe_has_no_silent_visible_fallback(self):
        text = _text(AUTO_FULL_SAFE)
        self.assertNotIn('工作流任务', text, 'auto_full_safe 不得再引用未跟踪的运行现场文件')
        self.assertNotIn(OLD_SILENT_FALLBACK, text,
                         'auto_full_safe 不得在隐藏桌面包装缺失时静默降级为可见桌面直跑')
        self.assertIn('scripts', text, 'auto_full_safe 应引用入库的 scripts/gui_hidden.py')


if __name__ == '__main__':
    unittest.main()
