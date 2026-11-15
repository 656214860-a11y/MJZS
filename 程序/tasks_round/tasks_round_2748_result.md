# R2748 结果：T10 包化批次 1 首块——error_codes 迁入 contract/ 包
<!-- round-evidence: {"commit_base": "31e6577a", "credential_hits": 0, "evidence_sha256": "1a6bac70925fe124", "exit": 0, "failed": 0, "passed": 38, "round": 2748, "tests": "run_selftests.py -k layers error_codes http_client"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3，T10「大模块拆分与包化路线」批次 1 首块：1 个模块 ≤3 上限）。分支 `codex/wip-R2748`（基于 R2720 `codex/wip-R2720`，专用 T10 工作树 `devin-t10`）。队列：无对应 ID（T10 来自任务书）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过（本轮实测两次）。
   - 定向 `run_selftests.py -k "layers circular hygiene startup coverage distribution error_codes http_client legacy"`：17 文件 101 条；首轮仅 `test_coverage_baseline` 2 红（基线未含新包模块，预期内），重跑 `coverage_report.py` 刷新基线并同步 runbook §11 数字后复跑 **5/5 绿**，合计 101/101。
   - `test_layers`/`test_no_circular_import`/`test_static_hygiene`/`test_startup_budget` 全绿；`distribution_build.py` plan **undecided=0**；导入冒烟 `import error_codes, contract.error_codes, http_client` 通过。
   - 全量 `--all --safe`：未跑。未改 `_layers.py` 登记表、启动路径、Tk 生命周期、删除语义，不触发合入前强制全量条款；分支不累计欠账。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；T10 从「方案就绪」推进到「包机制首块落地」。

## 交付

- `程序/contract/__init__.py`（新增）：仅 docstring，不再导出（用户拍板口径）。
- `程序/error_codes.py` → `程序/contract/error_codes.py`（`git mv`，内容零改动）。
- `程序/error_codes.py`（新建薄门面）：显式再导出 `CODES/ErrorCode/code_data/code_of/describe/from_http_result/lookup`；测试与外部脚本的扁平名导入不受影响，门面清除轮统一改写后删除。
- `程序/http_client.py`：唯一生产消费方，`from error_codes import …` → `from contract.error_codes import …`（docstring 同步）。
- `程序/distribution_manifest.md`：保留区加 `程序/contract/**`（与 `程序/agent/**` 同先例）。
- `程序/architecture.md`：目录树加 `contract/` 条目。
- `程序/PROJECT_MAP.md`：「模型与安全」行补 `contract/error_codes.py` 与门面说明。
- `程序/维护记录/覆盖率基线.json`：重跑 `scripts/coverage_report.py`（9 组定向用例全通过）刷新，模块口径 372→374；`runbook.md` §11 数字同步（61 覆盖／313 未覆盖）。

## 关键机制结论（供后续批次复用）

- `tests/architecture/_layers.py` **无需改动**：`LAYERS` 只登记顶层模块名；`contract.error_codes` 这类带点导入经 `LAYERS.get()` 得 None 被跳过（与 `agent.core` 等先例一致）；门面 `error_codes.py` 保留 L0 登记，「有实体 .py」不变量仍满足。
- `test_legacy_facade_manifest` 只管 `legacy_compat` 函数级门面，**模块级薄门面无登记要求**；方案文档中「登记 facade manifest」的说法据此修正为「无需登记，门面清除轮删除」。
- `production_files()` 只扫顶层，`contract/` 子包模块暂不进分层扫描口径（与 `agent/` 一致）；`coverage_report.production_modules()` 递归口径**会**收录，故必须同轮刷新覆盖率基线——这是每个搬家轮的固定动作。
- `distribution_build.py` 直接解析 manifest 表格生成正则，改 `.md` 即生效，无需动构建器。

## 验证与提交

- 见上「测试」节；提交信息 `R2748: …`，证据 `tasks_round/evidence/R2748.json`。

## 未覆盖／下一步

- 批次 1 其余候选（同轮 ≤3 模块节奏）：`model_protocol`、`pet_settings_contract`、`script_brief`、`script_output_spec`、`storyboard_contract`、`shot_selection`、`frame_checks`、`api_models`、`artifact_lineage`——每轮重复本轮动作：`git mv`＋门面＋生产侧 import 改写＋manifest/地图/基线刷新。
- 门面清除轮（远期）：改写全部测试扁平导入后删除各顶层门面，并升级 `_scan.production_files()` 递归口径。
