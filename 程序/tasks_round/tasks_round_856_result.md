# R856 结果：收口仓库体积治理并落地自动清理

## 范围

- 新增 `workspace_maintenance`：仅清理可再生的 `__pycache__`、超期 `.selftmp` 与满足四重闸门的 `.wt` 工作树；删除仅使用 `Path.unlink()`／`Path.rmdir()`，git 判定仅经 `platform_tools`，非仓、缺 git 或异常均保守跳过。
- 新增开发侧 `scripts/repo_health.py`：默认预览，只有 `--run` 才执行 git 维护；测试覆盖退出链和各保守分支。
- 将模块登记为 L1，补齐架构／地图／忽略规则与平台目录链接台账。

## 台账与现场

- 清理前后体积：约 240 MiB → 139 MiB。旧测试日志与备份已可逆归档；用户数据、`private`、`data`、运行环境和保留工作树未触碰。
- `desktop.py` 的退出挂点已由 R846 提交 `a1f98a0` 顺带纳入，本轮不修改该文件。
- `.selftmp` 内 28 个受 ACL 拒绝的旧目录保持跳过；清理器对权限／锁定失败容错，不影响功能。
- 预览核验：`.wt/B1` 与 `.wt/R820` 均显示为保留（`recent`），未计划移除。

## 验证

- `tests.test_workspace_maintenance` + `tests.test_force_quit`：28/28 通过。
- `smoke_test.py`：8/8 通过。
- `python -B scripts/repo_health.py`：预览通过，未改动仓库。

## 说明

- 本轮只加入任务 A 清单内文件；没有混入 R847 或 UI 统一入口暂存内容。
