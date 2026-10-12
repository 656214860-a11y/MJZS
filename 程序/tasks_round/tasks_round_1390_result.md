# R1390：UI 路线图 §三 覆盖率审计 — 门禁口径对齐递归（用户可见删除／事件总线／阶段完成）

类型：修复轮（§3.2，2026-10-12）。中央轮次：1390。范围＝路线图 v1 §三「已存在权威，仅需审计覆盖率（7 项）」——把仍只扫根目录的覆盖率门禁对齐到 R922／R1381 确立的**递归口径**，并逐项给裁定；**不改生产代码**。

## 三个必答
- 本轮类型：修复轮（§3.2）——只改架构门禁测试与共享扫描辅助，不改生产代码／阶段／路径／分层。
- 测试：定向 4 文件 **8/8**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **336/336**（数量不变：本轮改既有门禁，未新增文件）。
- 欠账：本轮不清欠账；`1390−1386=4<5` 且未命中 §5 升级条件 → **不跑全量**。

## §三 七项裁定（只读核查 + 本轮加固）
| 项 | 权威入口 | 覆盖证据 | 裁定 |
| --- | --- | --- | --- |
| 1 项目配置读写 | desktop_settings_service／stage_workspace_service | test_desktop_settings_boundary（desktop 全部 mutation 委托 service）＋test_path_authority（assets.json／config.json 归域文件）＋test_json_io_boundary | 已收口 |
| 2 日志前缀／事件名 | broadcaster.PREFIX_PATTERNS／pet_bus.CONTRACT | test_event_bus_boundary（跨模块状态只经 pet_bus；**本轮递归化**）＋coverage ratchet kind 25（事件名∈CONTRACT，三源 0） | 已收口（加固） |
| 3 缓存失效 | file_cache published／recycled／externally_overwritten | coverage ratchet kind 20（JSON 替换后必发失效通知；R840 三源 0） | 已收口 |
| 4 项目选择／切换 | DesktopStartupController／desktop_settings_service | desktop.py 已统一经控制器（410/415）；功能级测试 test_ui_edges／test_timers／test_desktop_startup_perf＋test_project_context_boundary | **缺口**：缺「所有项目进入路径必经控制器」的架构覆盖门禁 → 登记待办 |
| 5 删除 | storage_maintenance.recycle_paths() | test_deletion_gateway＋test_remove_authority（**本轮递归化**，scripts/ 开发脚本显式豁免）＋test_recycle_service＋coverage ratchet kind 22 | 已收口（加固） |
| 6 阶段完成核验 | stage_completion_service | test_completion_gate（stage.completed 必经核验；**本轮递归化**） | 已收口（加固） |
| 7 阶段配置 SKILL 说明与标签 | skill_panel 说明解析／注册文件名 | test_skill_notes（README 优先→SKILL 回退）＋test_skills／test_skill_panel_imported（chinese_skill_display／skill_checkbox_label／registered_skill_checkbox_label 语义） | 已收口 |

## 实现（不改生产代码）
- `tests/architecture/_scan.py`：新增 `EXCLUDED_PARTS` 与 `production_files_recursive()`（递归口径；仍排除 tests／tasks_round／维护记录／.git／__pycache__，以及 smoke_test／run_selftests／selftest_sandbox 与 `test*` 前缀，与 `production_files()` 同语义）。
- `test_deletion_gateway.py`／`test_remove_authority.py`：扫描改递归；对 `程序/scripts/`（开发维护脚本，**非用户可见删除路径**）显式豁免（`_DEV_SCRIPT_PARTS={'scripts'}`）。
- `test_completion_gate.py`：两处扫描改递归。
- `test_event_bus_boundary.py`：三处扫描（直调 `bus.emit`／`_emit` 包装器／`broadcaster` 调用）改递归。
- 子目录实测影响：删除仅 `scripts/clean_dev.py`（已豁免）、`stage.completed` 0、直调 `bus.emit` 0、`_emit` 包装器仍仅 `pet_agent.py`／`pet_ui.py`。

## 测试契约同步（§2.4）
- 无既有断言被改；`维护记录/架构统一基数.json` 无行号平移。

## 验证
- 定向：上述 4 个门禁文件 **8/8、OK**。
- 架构：`smoke_test.py --architecture` **336/336、0 红**（134.99 秒）。
- 默认冒烟：**8/8、0 失败**。
- 全量：**不跑**（见「三个必答」）。

## 提交
- 内容＋报告＋接力：一次提交 `fdb1daf`（9 文件：`tests/architecture/_scan.py`＋4 个门禁测试＋本报告＋`程序/project_status.md`＋`.agent-handoff/backlog.md`／`snapshot.md`）。

## 复盘：路线图 v1 §三
- 7 项中 **6 项已收口**（其中第 2／5／6 项本轮由「根目录门禁」升为「递归门禁」，覆盖 `batch_frames_tool/`／`agent/`／`scripts/` 等子目录）；**1 项（第 4 项 项目进入路径）登记为待办**。
- 未做（说明理由）：其余仍走 `production_files()`（根目录）的门禁（coverage ratchet 的 20/21/22/24/25/26 段、test_json_io／table 等）是否同批递归化，需逐段评估子目录候选，另轮处理，不与本轮混改。
