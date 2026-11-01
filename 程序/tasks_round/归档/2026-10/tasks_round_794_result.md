# R794 结果｜结构治理轮（执行，验收阻断）

## 完成内容

- 迁移 `confirm_gates.py` 的 `record`／`forget` 与 `previs_routing.py` 的 `set_override`／`dispatch`：四个正式 JSON 发布点均改为必须接收 L3 注入的发布器，L2 不再直接导入 `agent.core.save`。
- `stage_execution_service` 新增确认门与白模预演的发布网关；`desktop.py` 与 `local_previs.py` 只委托 L3。路径、登记格式、授权语义和分流结果均未改变。
- 新增白模预演发布边界门禁；第 3 项 pending 由 28 降至 24，第 4 项保持 21。台账保留四条 `migrated` 证据；三条既存 L3 裸 JSON 读取仅随代码插入重定位行号。
- 真机截图暴露的白模按钮回归已定位并修复：两处 UI 回归测试替身仍使用旧 `previs_routing.dispatch` 签名，未接收新的关键字 `publish`。替身现按正式注入契约接收该参数；`test_final_viewer` 的分镜整理调用也已补接既有 L3 `storyboard_gateway()`。

## 验证

- `smoke_test.py`：8/8 通过。
- `smoke_test.py --affected confirm_gates previs_routing stage_execution_service desktop local_previs`：9/9 通过。
- `run_selftests.py -k "confirm_gates previs_routing unification_ratchet" --safe`：28 条／0 红。
- 白模按钮及行选择回归：`run_selftests.py -k "manual_gate row_targets previs" --safe`：118 条／0 红。
- `test_final_viewer`（补接 L3 网关后）：13 条／0 红。
- `smoke_test.py --architecture`：162/162 通过（新增白模发布边界门禁后由 159 增至 162）。

按 §5，`794 - 791 = 3`，本轮必须运行完整安全全量。实际执行 `run_selftests.py --all --safe`：3,581 条、2 个文件有红。`test_final_viewer` 的直接 L2 调用已在全量之后补为 L3 网关注入并以定向回归验证通过；另一个红项为 `tests/test_perf_baseline.py` 的 300 行滚动中位 151.4ms（后续复跑为 167.0ms），均高于 150ms 硬线。

因此完整安全全量**未通过**，`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 必须保持 791，且本轮不得标记为 `[TASK_COMPLETE]`。后续先处理滚动性能硬线，再重新运行全量以验收 R794。

## Git

- 本轮未提交；commit hash：无。
