"""仓库根目录只允许登记过的入口：新增根文件必须先在这里写明用途，防止根目录继续变杂。

用户只认一个启动入口：快捷方式「漫剧助手」（app_shortcut 生成，不入库）；备用启动与 CI 脚本在 开发者工具/。
本表冻结现状，只许删、不许无理由增。
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {
    '程序': '源码根目录',
    '.claude': 'Claude Code 项目配置（settings 等）',
    '.agents': '仓库级项目开发技能（spec-context-review；说明见 开发者工具/AI开发流程/README.md）',
    '.claudeignore': 'Claude 忽略规则', '.gitattributes': 'Git 属性', '.gitignore': 'Git 忽略规则',
    '.gitmodules': '外部参考与技能包的固定 Git 子模块映射',
    'AGENTS.md': '代理入口协议', 'CLAUDE.md': 'Claude 入口说明',
    'PROJECT_HEALTH.md': '项目健康、开放风险和回归证据',
    'reorganize_install.py': '旧整理入口，提示当前发布方式',
    '使用说明.md': '用户说明', '使用说明.txt': '用户说明（纯文本）',
    '启动漫剧制作助手.pyw': '真实启动入口（快捷方式「漫剧助手」指向它）',
    '开发者工具': '备用启动、测试模式、本地 CI 与开发记录',
    '漫剧制作助手.ico': '程序图标',
}


class RootLayoutTests(unittest.TestCase):
    def test_retired_organizer_never_moves_checkout_or_install_files(self):
        import runpy
        import tempfile
        from unittest.mock import patch

        arrange = runpy.run_path(str(ROOT / 'reorganize_install.py'))['arrange']
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for name in ('.git', 'personal.txt'):
                (base / name).write_text('keep', encoding='utf-8')
            with patch.dict(arrange.__globals__, ROOT=base, PROGRAM=base/'程序', _project_configs=lambda: []):
                with self.assertRaisesRegex(RuntimeError, '发布'):
                    arrange()
            self.assertEqual(sorted(p.name for p in base.iterdir()), ['.git', 'personal.txt'])

    def test_tracked_root_entries_are_registered(self):
        out = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files'], cwd=ROOT,
                             capture_output=True, text=True, encoding='utf-8').stdout.splitlines()
        tracked = {line.split('/')[0] for line in out if line}
        self.assertTrue(tracked, 'git ls-files 无输出')
        self.assertEqual(sorted(tracked - set(ALLOWED)), [], '新增根目录入口须先在 ALLOWED 登记用途')
        self.assertEqual(sorted(set(ALLOWED) - tracked), [], '已不存在的根入口须从 ALLOWED 删除')


if __name__ == '__main__':
    unittest.main()
