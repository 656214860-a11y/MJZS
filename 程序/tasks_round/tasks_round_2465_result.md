# R2465 架构收口轮：清理主基线欠账

## 结论

清理当前 master 带入的若干架构欠账：Qwen 命令定位下沉、`aigc_lint` 边界修复、覆盖率基线刷新、skip 台账同步。

## 关键改动

- [client_profiles.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/client_profiles.py)
  - 新增 `qwen_command(config)`，承接 Qwen CLI 定位。
- [qwen_adapter.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/qwen_adapter.py)
  - `command()` 改为委托 `client_profiles.qwen_command()`。
- [workflow_settings.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/workflow_settings.py)
  - 不再动态 import `qwen_adapter`，循环依赖 `qwen_adapter → workflow_settings → qwen_adapter` 已拆。
- [aigc_lint.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/aigc_lint.py)
  - 去掉 ImportError 捕获，临时文件清理改走 `file_cache.remove_temporary_file()`，JSON 解析改用 `loads()`。
- [覆盖率基线.json](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/维护记录/覆盖率基线.json)
  - 重跑 8 组定向用例刷新到 `363` 模块、`59` 有覆盖。
- [skip台账.json](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/维护记录/skip台账.json)
  - 补齐源码 skip 项，台账与源码双向一致。

## 验证

- `test_aigc_lint`、ImportError 边界、回收边界、循环依赖：15/15 通过（2 skip）。
- `test_coverage_baseline`：5/5 通过。
- `test_skip_hygiene`：3/3 通过。
- `test_no_circular_import`：2/2 通过。

## 提交

- 已提交：`8bd33692daf2e8614f70377c14599ad0fbd83fb9`
- 分支：`codex/wip-R2465`
