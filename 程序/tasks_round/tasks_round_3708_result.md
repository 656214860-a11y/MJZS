# R3708 修复正常关窗后的工作区清理入口
<!-- round-evidence: {"commit_base": "86e863bb", "credential_hits": 0, "evidence_sha256": "606d3b8c0a0c40ee", "exit": 0, "failed": 0, "passed": 29, "round": 3708, "tests": "run_selftests.py -k workspace_maintenance exit_maintenance"} -->

1. 修复轮。桌面正常退出派发的旧脚本在模块迁移后已不存在。复用现有后台进程适配器，在指定程序目录按模块名启动同一清理器；强退分流与清理范围沿用现行策略。
2. 红测：对派发命令替换末尾动作为 --help，通过真实解释器验证入口，修复前退出码 2（文件不存在）。修复后工作区维护与退出分派共 29 条定向通过；默认冒烟 9/9，受影响冒烟 10/10。本轮未跑完整架构或安全全量。测试清理使用临时目录，实际程序入口验证使用帮助模式。
3. 旧路径失效已修复。运行时的 scheduled 只表示派发成功。未在用户仓库执行物理清理以验证启动。生产改动仅涉及 infra/workspace_maintenance.py。分支提交回执以 Git R3708 为准。
