# R1461 结构治理轮：模块行数棘轮、已合并分支清理、运行时计时埋点（优化清单第 5、8、9 项）

1. **本轮类型？** 结构治理轮。
2. **测试与基线？** 新增 `tests/architecture/test_module_size_ratchet.py`（2 项），`test_app_logging.py` 增 4 项；默认冒烟 8/8；架构门禁与定向测试见提交前运行。断言未动。
3. **是否欠账？** 改了 `model_pool.py`、`desktop.py`（各 1 个装饰器），未触及启动入口、删除语义、层级表；计入源码轮次，欠账按 §5 阈值由后台补跑。

## 事实

- 超 1500 行的生产模块 6 个：desktop 7798、pet_ui 4831、pet_cloud 2137、skill_panel 1853、stage_execution_service 1671、script_contract 1553；此前没有任何行数门禁。
- 本地 114 个分支，其中 85 个已完全并入 master；另有 25 个未并入、3 个被其他车道的 worktree 占用。
- 切页（`Desktop.show`）与模型 HTTP（`model_pool.http_transport`）没有运行时耗时记录。

## 改动

- 行数棘轮：新模块 ≤ 1500 行；6 个老模块登记上限（实际向上取整到 50），只许下降，上限比实际高出 100 行必须下调，已不超限必须从登记表删除。
- 分支：`git branch --merged master` 的 85 个本地分支用 `git branch -d`（安全删除，提交仍在 master 历史）清理，114 → 30。未并入的 25 个分支和 `.wt/` 下其他车道的 worktree、日志未动，是否保留由用户决定。
- 计时：`app_logging.timed(name, warn_ms)`（装饰器／上下文，线程安全、可重入），内存累计次数／总耗时／最大耗时，超阈值才写 WARNING，退出时汇总写 `logs/perf_metrics.json`；已接入 `page.show`（800ms）与 `model.http`（30s）。

## 提交

已提交，见 git log 标题 `R1461:`。
