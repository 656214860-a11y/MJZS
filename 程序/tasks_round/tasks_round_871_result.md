# R871 协作治理轮：Git hooks 协议

## 实现

- 增加版本受控的 `维护记录/基准脚本/hooks/commit-msg`，只允许 `R<轮次>:` 或 `R<轮次>-FAIL:` 提交首行。
- 增加 `pre-commit`：只允许默认结果／状态／队列文档直接暂存；其余 `程序/` 文件必须显式写入 `CODEX_STAGE_ALLOWLIST`，因此批量暂存的无关文件会被拒绝。
- `project_status.md` 仅允许 master 提交；工作树改动应写入各自 `tasks_round` 结果。
- `install_git_hooks.py` 按 Git common-dir 安装两个模板，已在当前仓库实际安装。

## 验收

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_round_claim tests.test_git_hooks`：10 条／0 红。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8 项／0 红。
