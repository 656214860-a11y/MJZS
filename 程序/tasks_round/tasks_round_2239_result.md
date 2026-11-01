# R2239 结果：修 R2233／R2237 引入的四道架构门禁红（修复轮）

## 三问
- 轮次类型：修复轮。后台全量在 R2233 之后新报 `test_atomic_write_boundary`、`test_module_size_ratchet`、`test_recycle_service`，R2237 又引入 `test_unification_ratchet`（裸 `json.loads`）。**这些是我的改动造成的，此前我把后台红当存量红是错的**：R2233、R2237 只跑了定向测试，没跑 `--architecture`。
- 测试：`smoke_test.py --architecture` 修前 411 项 5 失败 1 错误；修后 `test_layers`、`test_coverage_baseline`、`test_release_watch`、`test_model_pool_snapshot` 共 21 条通过。剩余 `test_agents_md`、`test_skill_reference_injection` 在本 worktree 红（缺文件／skills 子模块），未在主检出复核。断言未动。
- `project_status.md` 欠账：无变化。

## 改动
- 新增 `config_snapshot.py`（L1）：固定 20 个槽位的环形快照，覆盖最久没写的槽位，用 `agent.core.save_bytes` 写，不删除任何文件。`model_pool.store` 改调它，`model_pool.py` 回到 1117 行上限内（合并了三条 import），不抬上限。
- `scripts/release_watch.py` 读历史改走 `agent.core.read_json`。
- `tests/architecture/_layers.py`、`architecture.md` 登记 `config_snapshot`；`维护记录/覆盖率基线.json` 重跑工具刷新（334 模块，覆盖 52），`runbook.md` §11 数字同步。
- `tests/test_model_pool_snapshot.py` 改为环形槽位语义（原「留最近 20 份并删旧」的实现已移除）。
