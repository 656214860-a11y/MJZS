"""仓库根目录只允许登记过的入口：新增根文件必须先在这里写明用途，防止根目录继续变杂。

整理根目录（迁入子目录）牵涉钩子、协议文档、分发清单与并行车道，须用户确认后单独成轮；
在那之前本表冻结现状，只许删、不许无理由增。
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {
    '程序': '源码根目录',
    '.agent-handoff': '代理接力记录',
    '.claude': 'Claude Code 项目配置（settings 等）',
    '.claudeignore': 'Claude 忽略规则', '.gitattributes': 'Git 属性', '.gitignore': 'Git 忽略规则',
    'AGENTS.md': '代理入口协议', 'CLAUDE.md': 'Claude 入口说明',
    'reorganize_install.py': '升级安装整理脚本',
    '使用说明.md': '用户说明', '使用说明.txt': '用户说明（纯文本）',
    '启动助手.cmd': '用户启动入口', '启动助手_测试模式.cmd': '测试模式启动入口',
    '启动漫剧制作助手.pyw': '真实启动入口',
    '本地CI.cmd': '本地 CI 双击入口', 'ci_clean.cmd': '干净检出全量入口',
    'ci_targets.cmd': '指定目标 CI 入口', 'ci_unattended.cmd': '无人值守 CI 入口',
    '漫剧制作助手.ico': '程序图标',
}


class RootLayoutTests(unittest.TestCase):
    def test_tracked_root_entries_are_registered(self):
        out = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-files'], cwd=ROOT,
                             capture_output=True, text=True, encoding='utf-8').stdout.splitlines()
        tracked = {line.split('/')[0] for line in out if line}
        self.assertTrue(tracked, 'git ls-files 无输出')
        self.assertEqual(sorted(tracked - set(ALLOWED)), [], '新增根目录入口须先在 ALLOWED 登记用途')
        self.assertEqual(sorted(set(ALLOWED) - tracked), [], '已不存在的根入口须从 ALLOWED 删除')


if __name__ == '__main__':
    unittest.main()
