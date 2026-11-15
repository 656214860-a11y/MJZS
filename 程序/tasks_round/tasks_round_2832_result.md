# R2832 结果：T10 批次1收尾——contract/ L0 权威契约族 7 模块迁入＋分层扫描口径补包实体
<!-- round-evidence: {"commit_base": "7eca9163", "credential_hits": 0, "evidence_sha256": "fa86ef82021c5ea2", "exit": 0, "failed": 0, "passed": 116, "round": 2832, "tests": "run_selftests.py -k layers circular size_ratchet complexity service_return structured_script gate_selfaudit coverage_baseline static_hygiene app_metadata facade project_context project_stages service_contract stage_path_service stage_layout"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3，T10「大模块拆分与包化路线」：contract/ 批次 1 余下 7 个 L0 权威契约模块一轮内聚搬迁；pet_bus／platform_tools 因引用面 59–60 留待各自单独成轮）。分支 `codex/wip-R2832`（专用 T10 工作树 `devin-t10`，叠于 R2807 之上）。队列：无对应 ID（T10 来自任务书）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过。
   - `smoke_test.py --architecture` 全量 466 条：迁移相关 11 项红全部修复后复跑，**实质红 0**；余 3 红 1 错均为本工作树固有环境欠账（与本 diff 无关，详见下「环境欠账」）。
   - 定向 `run_selftests.py -k <本批模块名>` 290 条：1 红＝`test_the_audit_covers_every_script_skill`（技能包内容缺失，同环境欠账）。
   - `distribution_build.py --plan`：**undecided=0**（`contract/**` 已于 R2776 登记）。
   - `coverage_report.py` 9 组定向用例 97 条全过，基线刷新 **394→401** 模块、覆盖 62→64；`runbook.md` §11 同步。
   - 全量 `--all --safe`：未跑（分支不累计欠账；未改 `_layers.py` 登记名、启动路径语义、Tk 生命周期、删除语义）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；contract/ 包扩到 28 个 L0 模块，批次 1（除 pet_bus／platform_tools）落地。历史欠账：无新增。

## 交付

- `git mv` 7 模块入 `contract/`：project_context、project_stages、service_contract、stage_path_service、storyboard_paths、script_contract、stage_layout；顶层留显式再导出门面（AST 公开名，与旧导出面一致）。
- 约百个生产文件 import 改写为 `contract.*`（含包内互引）；生产侧已无这 7 个模块的扁平 import（门面仍供 tests／scripts 命中）。
- `scripts/package_migrate.py` 修复：`import mod` 改写正则组号 IndexError（group(4)→group(3)）；抽出 `_rewrite_imports()` 并新增 `--rewrite-only` 幂等恢复入口（本轮 mv/门面完成后改写阶段中断，用其续跑）。
- **`tests/architecture/_scan.py` 新增包感知扫描**（本轮关键机制修正）：`PACKAGE_NAMES`／`package_entity_files()`／`is_package_facade()`／`module_scan_files()`／`_package_target()`／`module_import_rows()`／`module_dynamic_import_rows()`。门面被识别排除、实体以扁平名参与扫描，`contract.x` 导入归一化回登记名 `x`。
- 四个棘轮测试切到 `module_scan_files`：test_layers（分层＋动态越层）、test_no_circular_import（静态＋动态环）、test_module_size_ratchet、test_complexity_ratchet。**登记表零改动**：KNOWN_DYNAMIC_UPWARD／KNOWN_DYNAMIC_CYCLES／OVERSIZE_CAPS／复杂度 caps 全部继续命中（键是 path.name／stem，位置无关）；script_contract→script_skill_report 动态越层与环在实体内被重新发现，棘轮语义不损失。
- 契约同步（§2.4）：test_service_return_contract 三处接受 `contract.service_contract`（adopters 集合不变）；test_structured_script_write_boundary 两处解析路径改 `contract/script_contract.py`；test_gate_selfaudit 的 mock 点改 `module_scan_files`。
- `architecture.md` 目录树 contract/ 注释更新为 28 模块；`维护记录/覆盖率基线.json` 与 `runbook.md` §11 同步。
- 清理：删除误随 R2807 提交的 `tasks_round_2804_result.md`（被拒轮次残留）。

## 机制修正记录（供后续批次）

- **顶层口径扫描对包实体失明**：`production_files()` 只扫顶层，实体迁入包目录后会逃逸分层／环／规模／复杂度棘轮，且门面使 KNOWN 登记「假消除」。解法＝`module_scan_files()`（顶层去门面＋包实体），棘轮键沿用 basename/stem 天然兼容。
- **门面识别**：`is_package_facade` 判据＝除 docstring 外只含 `from <T10包>.<同名> import`；未来 infra/domain/orchestrator/ui 复用同一函数。
- **包内互引归一化**：`contract.x` 在 import_rows 里首段是 `contract`（未登记会丢边），`_package_target` 取第二段还原扁平名；非 T10 包名行为不变。
- pet_bus（59 引用）与 platform_tools（60 引用）引用面最大，按方案各自单独成轮。

## 环境欠账（与本 diff 无关，工作树固有）

- `test_performance_history` ERROR：`维护记录/基准历史.json` 被 gitignore，工作树无此运行文件。
- `test_round_number_continuous` FAIL：`project_status.md` 仅 master 可提交，本分支停在 R2696 口径，中央轮次已到 R2800+。
- `test_skill_reference_injection`、`test_the_audit_covers_every_script_skill` FAIL：技能包内容（screenplay-gate-engine.md、编剧技能集／剧本锻造实体）为未跟踪用户同步内容，本工作树为空目录占位。

## 验证与提交

- 见上「测试」节；提交信息 `R2832: …`，证据 `tasks_round/evidence/R2832.json`。

## 未覆盖／下一步

- contract/ 余 pet_bus、platform_tools 两模块（各一轮）；批次 3–6（infra/domain/orchestrator/ui）沿用 package_migrate＋module_scan_files 口径。
- 门面清除轮：全部生产消费方迁包路径且测试导入改写后，统一删 28 个顶层门面。
