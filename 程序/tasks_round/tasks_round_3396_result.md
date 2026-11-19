# R3396 结果文件 — L1 任务书轮 I1：层间关系规范、合规清单与守卫骨架
<!-- round-evidence: {"commit_base": "0ae2c654", "credential_hits": 0, "evidence_sha256": "149efc15d647cdc2", "exit": 0, "failed": 0, "passed": 44, "round": 3396, "tests": "run_selftests.py -k layer_relations layers gate_selfaudit rule_guard_map"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（文档＋门禁；范围内改动：`architecture.md`、新增 `维护记录/层间合规清单.json`、新增 `tests/architecture/test_layer_relations.py`、`tests/architecture/_layers.py` 登记、`scripts/rule_guard_map.py`、`维护记录/规则守卫基线.json`、`维护记录/规则守卫对照.md` 再生成、`tests/architecture/test_gate_selfaudit.py`；零生产 `.py` 改动）。
2. **测试跑了吗、三个基线过了吗？** 跑了。任务书点名 `run_selftests.py -k layer_relations layers gate_selfaudit rule_guard_map` **44 条 0 红**；`smoke_test.py --architecture` **541 条，1 红＝`test_round_number_continuous`（状态页轮次滞后，工作树版按 R3331 先例同步、不入提交，复跑绿）**；默认冒烟 **9/9 绿**；全量回归未触发（零源码变更），欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 无新增欠账；FL-15（层间规则守卫覆盖 0→100%）达成；LR-01~10 存量违规全部落棘轮基线（同层边 763 条首次登记、互依赖 5 对、上行边 21、L1 中文 raise 263 等），后续 I2–I26 逐项收口。

## 领号说明

- `round_claim.py next` 分配 **R3396**（claims 登记 `devin-l1-enterprise`／`codex/l1-enterprise`）。R3391 为上一会话 `next` 已分配未用号，留空不补（编号允许跳空，3381/3384/3385 同例）。

## I1-1　LR-01~LR-10 写入 architecture.md ✅

- `architecture.md` §3 末新增「层间关系规范（LR-01~LR-10，L1 任务书 §5）」小节：十条规则各一行，含编号、规则描述、守卫测试名（`test_layers.py`／`test_layer_relations.py`／`test_no_circular_import.py`／`test_dynamic_import_registry.py`／`test_event_bus_boundary.py`／`test_infra_errors.py`／`test_http_boundary.py`／`test_json_io_boundary.py`／`test_deletion_gateway.py`／`test_platform_process_boundary.py`／`test_thread_boundary.py`／`test_log_sink_boundary.py`／`test_secret_sink_audit.py`／`test_resources.py`／`test_clock_boundary.py`／`test_contract_manifest.py`；未建门禁名为目标态，登记在合规清单）。
- 「当前架构门禁清单」分层与一致性行登记 `test_layer_relations.py`（`test_agents_md.test_architecture_guard_list_matches_actual_test_files` 绿）。

## I1-2　合规清单＋test_layer_relations 棘轮比对 ✅

- 新增 `维护记录/层间合规清单.json`：10 条规则每条含 `id/title/description/guard/metric/violations/baseline/note`。
- 新增 `tests/architecture/test_layer_relations.py`：`_scan()` 单次全仓 AST 扫描（静态＋字面量动态 import、alias-aware 包归一），`test_compliance_ledger_matches_measured_violations` 逐条比对——**实测 > 基线判红；实测 < 基线打印棘轮提示要求下调基线**（不判红）。`real_scan()` 缓存单次扫描供 5 条门禁用例共享。

## I1-3　SAME_LAYER_EDGES 全量登记＋未登记/互依赖判红 ✅

- `_layers.py` 新增 `SAME_LAYER_EDGES: frozenset[tuple[str,str]]`：**763 条存量同层边全部登记**（口径：importer 与 imported 同层的静态 import＋字面量 `import_module`/`__import__`，`from pkg import X` 按包名＋成员展开，`agent/core` 等包内路径归一扁平名；分层计数 L0 28／L1 118／L2 58／L3 145／L4 414）。
- `test_lr03_unregistered_same_layer_edge_is_red`：实测同层边 − 登记表 ≠ ∅ 即红。
- `test_lr03_mutual_same_layer_dependency_is_red`：互依赖对数 > 基线 5 即红。

**口径裁决（记录备查）**：任务书「同层互相依赖即红」按棘轮语义执行——存量 5 对互依赖（L1：`core↔file_cache`、`file_cache↔publication`、`diagnostic_capture↔request_ledger`；L3：`stage_models↔workflow_settings`；L4：`white_model↔white_model_ref`）无法在 I1 内拆除（需 I3a/I3b/I4/I5 模块迁移），故登记 `violations=5/baseline=5`；**任何新增互依赖对使实测超基线即红**，存量随各迁移轮收口。这与本轮「以 I0 实测值为棘轮起点」一致。

## I1-4　四个坏样本自审 ✅

`test_gate_selfaudit.py` 新增 `LayerRelationsSelfAuditTests`（共 4 用例，各含坏/好样本对照，样本全在临时目录）：

| 坏样本 | 断言 |
| --- | --- |
| 未登记同层边（`aaa_mod→bbb_mod` 同层） | `detail['unregistered']` 含该边；登记进 `SAME_LAYER_EDGES` 后消失 |
| 同层互相依赖（`aaa_mod↔bbb_mod`） | `detail['mutual']` 含该对；单向边不算 |
| 非字面量 `import_module(name)` | `detail['nonliteral']` 命中；字面量 `import_module("os")` 不命中 |
| L1 import L2 | `detail['upward']` 含该边；L1→L0 不命中 |

`test_gate_selfaudit` 10 条全绿；`test_rule_guard_map` 7 条全绿（LR-01~10 已登记守卫，`规则守卫对照.md` 再生成含 10 行 LR）。

## 各规则实测 vs 基线（R3396 实测）

| 规则 | 实测违规 | 基线 | 说明 |
| --- | --- | --- | --- |
| LR-01 上行依赖边 | 21 | 21 | 18 条豁免台账＋3 条 `KNOWN_DYNAMIC_UPWARD`；I3 清零 L1 三条 |
| LR-02 循环分量 | 6 | 6 | 静态 1＋动态 5（`test_no_circular_import` 细管） |
| LR-03 未登记同层边＋互依赖 | 5 | 5 | 763 边已登记；互依赖 5 对存量 |
| LR-04 非字面量＋上行动态＋登记表越层 | 4 | 4 | 上行动态 3＋`ui_plugin_registry`(L1) 加载 L2–L5 计 1；I2 收口 |
| LR-05 L0–L3 Tk 回调注册（排除端口） | 5 | 5 | `shot_selection`×2(L0)、`stage_models`×3(L3) |
| LR-06 L1 私有名访问 | 1 | 1 | `task_center_ui.py:15→diagnostic_capture._state` |
| LR-07 L1 中文 raise | 263 | 263 | I6/I7 迁移棘轮；I6 后切 `InfraError` 口径 |
| LR-08 九项横切缺守卫 | 4 | 4 | 缺线程(I10)/日志(I12)/磁盘(I15)/时钟；已有 HTTP/JSON/删除/子进程/密钥 |
| LR-09 无 `__all__` 的 L1 模块 | 57 | 57 | 门面口径 59−2（`file_index`、`global_library_service` 根门面有 `__all__`）；I20 补齐 |
| LR-10 同 LR-09（可替换性同源度量） | 57 | 57 | 端口协议待 G-A4 |

代理指标口径（清单 `metric` 字段已注明）：LR-05 以 L0–L3 的 Tk 回调注册点（`after/bind/protocol/trace*`，排除端口模块 `tk_timers`/`app_logging`）计；LR-07 以 L1 `raise` 含 CJK 文案计数（I6 建 `contract/infra_errors` 后切换为非技术异常计数）；LR-09/LR-10 同源（`__all__` 覆盖即可替换性的前提）。

## 测试证据

- `py -B run_selftests.py -k layer_relations layers gate_selfaudit rule_guard_map`：**5 文件 44 条 0 红**（layer_relations 5、layers 6、gate_selfaudit 10、rule_guard_map 7、model_probe_layers 16），6.9 秒。
- `py -B smoke_test.py --architecture`：**541 条用例，189 秒，1 红**＝`test_round_baselines.test_round_number_continuous`（状态页 3384 落后最新结果 3386→期望 3387）。按 R3331 先例：工作树版 `project_status.md` 同步轮次、**不入提交**（仅 master 可提交状态页），定向复跑 `test_round_baselines` 后状态页随本结果文件落位 3397 时该项转绿——提交前已复验（见下）。
- `py -B smoke_test.py`（默认）：**9/9 绿**。
- `python -B scripts/rule_guard_map.py --write`：`维护记录/规则守卫对照.md` 再生成，含 LR-01~10 十行。

## 改动清单

- `architecture.md`：§3 新增 LR-01~10 表；门禁清单登记 `test_layer_relations.py`。
- `维护记录/层间合规清单.json`（新增）：10 规则棘轮基线。
- `tests/architecture/_layers.py`：`SAME_LAYER_EDGES` 763 条登记。
- `tests/architecture/test_layer_relations.py`（新增）：守卫骨架＋4 条判定用例。
- `tests/architecture/test_gate_selfaudit.py`：+`LayerRelationsSelfAuditTests` 4 用例。
- `scripts/rule_guard_map.py`：`parse_arch_rules()` 解析 architecture.md LR 表并入 `build()`。
- `维护记录/规则守卫基线.json`：+LR-01~10 守卫登记（仅登记已存在文件；`test_infra_errors`/`test_thread_boundary`/`test_log_sink_boundary`/`test_resources`/`test_clock_boundary`/`test_contract_manifest` 为目标态，不登记以免 `test_registered_guard_files_exist` 红）。
- `维护记录/规则守卫对照.md`：再生成。

## 待切换项／移交

- `project_status.md` 工作树版轮次头同步至 3397（不入提交，合并轮口径处理）。
- LR-04 目标态守卫 `test_infra_errors.py` 等六个文件待 I6/I10/I12/I15/I20/G-A2 建成后回填 `规则守卫基线.json`（届时 `test_registered_guard_files_exist` 自动放行）。
- 同层互依赖 5 对、上行边 21 条、L1 中文 raise 263 处为棘轮存量，收口轮次：I3（反向依赖）、I4/I5（模块迁移）、I6/I7（异常层级）。

## 提交

- 分支 `codex/l1-enterprise`；commit 见 `git log`（`dev.py commit` 自动暂存白名单＋生成 `tasks_round/evidence/R3396.json`）。
- 未 push（规则：仅用户明确要求时 push）。

[TASK_COMPLETE]
