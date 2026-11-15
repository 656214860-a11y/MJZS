# R2807 结果：T10 批次1余量＋批次2首批——20 个小体量 L0 模块迁入 contract/
<!-- round-evidence: {"commit_base": "42210dec", "credential_hits": 0, "evidence_sha256": "2fd51e3d2e76b52e", "exit": 0, "failed": 0, "passed": 201, "round": 2807, "tests": "run_selftests.py -k api_models artifact_schema asset_contract episode_contract frame_checks model_protocol pet_settings production_model prompt_templates prop_assets script_brief script_manifest script_output shot_batches shot_selection storyboard_contract workflow_context_budget app_metadata static_hygiene layers coverage_baseline"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3，T10「大模块拆分与包化路线」：contract/ 批次 1 余量 9 模块＋批次 2 小体量 L0 共 20 个，一轮一族内聚搬迁）。分支 `codex/wip-R2807`（专用 T10 工作树 `devin-t10`，叠于 R2796 之上）。队列：无对应 ID（T10 来自任务书）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过。
   - 定向 `run_selftests.py -k <20 模块名 + 架构门禁关键词>`：232 条用例；首轮 `test_no_star_imports`（门面误用 `import *`）与 `test_app_metadata`（AST 钉住扁平模块路径）红，修复后复跑 **app_metadata 5/5、static_hygiene 4/4 绿**，合计全绿。
   - `test_layers`/`test_no_circular_import`/`test_startup_budget`/`test_coverage_baseline`/`test_distribution_*`/`test_legacy_facade_manifest` 全绿；`distribution_build.py` plan **undecided=0**（`程序/contract/**` 已于 R2776 登记）。
   - `coverage_report.py` 9 组定向用例全过，基线刷新 **374→394** 模块（每搬一模块净增一个门面文件）；`runbook.md` §11 数字同步。
   - 全量 `--all --safe`：未跑（分支不累计欠账；未改 `_layers.py` 登记表、启动路径语义、Tk 生命周期、删除语义）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；contract/ 包从 1 个模块扩到 21 个，批次 2 小体量部分落地。

## 交付

- `程序/scripts/package_migrate.py`（新增开发工具，不进分发）：`git mv`＋门面＋生产侧 import 改写＋动态字符串报告；`--fix-facades` 把星号门面改写为显式再导出；`--dry-run` 预检。
- `程序/contract/` 新增 20 个模块（`git mv` 自顶层）：model_protocol、script_brief、script_output_spec、storyboard_contract、frame_checks、prompt_templates、script_manifest_schema、shot_selection、artifact_lineage、artifact_schema、episode_contract、pet_settings_contract、script_manifest_contract、api_models、shot_batches、production_model_contract、workflow_context_budget、asset_contract、prop_assets、app_metadata。
- 20 个顶层同名门面：AST 收集公开名（`__all__` 优先）后 `from contract.<mod> import (…)` 显式再导出，导出面与旧扁平模块一致（含其转引的公共名）。
- 约 55 个生产文件 import 改写为 `contract.*`（含 `contract/` 包内互引）；`scripts/clean_dev.py` 与 `启动漫剧制作助手.pyw` 同步包路径（DISPLAY_SOURCES 契约要求规范路径）。
- `tests/test_app_metadata.py`：`node.module` 期望 `app_metadata`→`contract.app_metadata`（§2.4 有意契约变更同步，断言意图不变）。
- `维护记录/覆盖率基线.json`、`runbook.md` §11：随基线刷新同步。

## 机制修正记录（供后续批次）

- **`import mod` 必须改写为 `import pkg.mod as mod`**：裸 `import pkg.mod` 绑定的是 `pkg`，`mod.attr` 会 NameError（首轮 `test_app_metadata` 暴露，已修脚本并回扫修复 6 个文件）。
- **门面禁 `import *`**：`test_no_star_imports` 拦截；改用 AST 收集公开名显式再导出。
- **动态字符串 5 处全为数据标识**（`artifact_lineage` 产物类型、`script_brief` contract id、`frame_checks` 属性名），非模块引用，按持久化兼容不改。
- **AST 路径钉住测试**：`node.module == '<扁平名>'` 的边界断言须同轮改为包路径（本批仅 test_app_metadata 一处）。

## 验证与提交

- 见上「测试」节；提交信息 `R2807: …`，证据 `tasks_round/evidence/R2807.json`。

## 未覆盖／下一步

- contract/ 余下 9 个 L0：project_context(28)、stage_path_service(30)、storyboard_paths(31)、script_contract(32)、service_contract(32)、project_stages(33)、stage_layout(40)、pet_bus(59)、platform_tools(60)——引用面大，分 2–3 轮；pet_bus/platform_tools 各自单独成轮。
- 批次 3–6（infra/domain/orchestrator/ui）沿用 `package_migrate.py` 同流程；每轮必做覆盖率基线刷新＋runbook 数字＋动态字符串核对。
