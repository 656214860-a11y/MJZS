# R859 结果：精简 Git 工作树并保留分支尖端

## 处置

- 已归档 e370 的暂存区残差（205,442 B）与 B1 的工作区残差（126,952 B），均位于主树 `维护记录/归档/`；d2cc 与 R820 原本干净，无需补丁或 zip。
- 已仅通过 `git worktree remove`（脏树使用文档许可的 `--force`）与 `git worktree prune` 移除 e370、d2cc、B1、R820 注册；不删除任何分支 ref。
- `git worktree list` 验收仅余主树、783b、r856 三条。e370 与 R820 在 Windows 文件系统中留下权限/参数错误导致的未注册目录；未用 `rm` 绕过 Git，详见 `维护记录/工作树精简台账.md`。

## 体检与验证

- `run_selftests.py --serial -k workspace maintenance force_quit`：54/54 通过，0 红。
- 修正 linked worktree 的 `.git` 文件形态识别；`repo_health.py --run` 现报告 `worktrees: git=present`，不会把 worktree 误判为非仓库。
- 体检执行清理可再生 pycache 1.30 MiB；`.selftmp` 未删除；4 条 stash 仅报告、未删除。

## 保留边界

- 主树正在进行的 R860 修改、783b 与当前 r856 均未改动；`private`、`data`、`运行环境` 与所有 stash 均不在任何删除路径内。
