# R2316 结果：拆 stage_execution_service 资产网关簇（J 路线后续 #18，重构轮）

## 改动（行为不变）
- 新增 `stage_asset_gateways.py`（L3）：资产批处理／计划／详情绑定／生成资产导入的 16 个网关函数与 `unwrap_service_result`，原样迁出。
- `stage_execution_service` 在文件头按原名重新导出，旧调用点与 `patch('stage_execution_service.<名>')` 补丁点不变（资产簇内无被补丁的名字；`asset_batch_settings_gateway` 等设置函数留在原处）。
- `stage_execution_service.py` 1442 → 1332 行，仍超 1000，`OVERSIZE_CAPS` 上限降到 1332。
- 同步：`_layers.py` 登记、覆盖率基线（353 模块，未覆盖 300）、`runbook.md` §11、`architecture.md` L3 列表、`test_atomic_write_boundary` 计数（facade 3→2，新模块 1）、`test_asset_plan_publication_boundary` 读取目标改为新模块（同一组函数名断言）。

## 验证
- `run_selftests -k asset stage_execution`：全过。
- `smoke_test.py --architecture`：仅 `test_performance_history_is_declared_as_historical_only` 红（工作树缺 gitignored `基准历史.json`，已知环境红）。
- 未跑全量。断言未动。
