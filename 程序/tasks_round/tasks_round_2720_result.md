# R2720 结果：SWE-2 T10 启动——包化依赖扫描器＋方案实测修订与口径确认
<!-- round-evidence: {"commit_base": "a684ab97", "credential_hits": 0, "evidence_sha256": "72592ed6480ab358", "exit": 0, "failed": 0, "passed": 22, "round": 2720, "tests": "run_selftests.py -k layers"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3，任务书 T10「大模块拆分与包化路线」的启动轮：只读扫描＋方案修订＋口径确认；无生产代码改动）。分支 `codex/t10-packaging`（专用 T10 工作树 `devin-t10`，基于 master `a684ab97`）。队列：无对应 ID（T10 来自任务书，非中央队列条目）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过（本轮实测）。
   - 架构门禁：未跑 `--architecture`——本轮只新增 `scripts/`（非产品目录）开发工具与 `docs/review/` 文档，不触碰生产模块、分层登记表与门禁清单；提交证据带 `--tests layers` 定向。
   - 全量 `--all --safe`：未跑（分支不累计欠账；本轮无生产 .py 改动）。
   - 扫描器实测：`package_dep_scan.py` 对 362 个顶层生产模块跑通，输出分层分布、跨层族与全量 JSON。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；T10 从「未启动」推进到「批次 1 可执行」。

## 交付

- `程序/scripts/package_dep_scan.py`（新增，开发工具，不进分发副本）：只读 AST 扫描，复用 `tests/architecture/_scan.py` 口径；输出每模块层级、静态/动态出入度、tests/scripts/agent 等非生产消费者计数、前缀族聚类与跨层清单；`--json` 全量、`--family` 单族。
- `程序/docs/review/包化迁移方案_T10.md`（修订）：追加「扫描实测」一节——362 模块分层分布（L0=30/L1=50/L2=71/L3=75/L4=130/L5=2）、36/38 前缀族跨层、按任务书「先 L0 后 UI」修订的七批表、每批同轮触点清单（`_layers.py`/`_scan.py`/`distribution_manifest.md`/`PROJECT_MAP.md`/`architecture.md`/动态导入字符串/smoke 检查项/启动器）；「已确认口径」一节记录用户四项拍板。

## 扫描关键结论

- 几乎所有前缀族跨层（asset/pet/project/script/stage/workflow 横跨全部 5 层）→「按层分包、按族分批」成立，无整族直搬捷径。
- 批次 1 试点候选（小体量 L0）：`error_codes`（产入 1）、`model_protocol`（1）、`pet_settings_contract`（3）、`script_brief`（1）、`script_output_spec`（1）、`storyboard_contract`（1）、`shot_selection`（2）、`frame_checks`（2）、`api_models`（4）、`artifact_lineage`（3）。
- 批次 1 候选模块无动态导入字符串、无持久化模块路径；测试引用面约 110 文件，按拍板靠薄门面不改写。
- 活跃车道冲突扫描（`dev.py scope`）：R2542/R2694/R2700/walnut-shannon 均不触碰 account/project/contract 候选文件。

## 用户拍板（2026-11-15）

包名 `contract/infra/domain/orchestrator/ui`；`__init__.py` 只放 docstring 不再导出；批次 1＝contract 试点小模块；测试 import 不改写靠门面。

## 验证与提交

- `smoke_test.py` 默认冒烟 8/8；`run_selftests.py -k layers` 定向（证据文件 `tasks_round/evidence/R2720.json`）。
- 提交：见本文件末尾记录（`dev.py commit` 自动生成证据）。
- 注：本轮先以 R2714 领号，提交时中央计数器已被他车道推进至 R2716，按规则重领 R2720；R2714 证据文件已废弃删除。

## 未覆盖／下一步

- 下一轮（批次 1 执行）：`git mv` ~10 个小 L0 模块进 `程序/contract/`，建空 `__init__.py` 与同名薄门面，改写生产侧 import 为包路径，更新 `_layers.py`（登记 `contract`→0，保留原名）、`distribution_manifest.md`（加 `程序/contract/**`）、`PROJECT_MAP.md`、`architecture.md`；验收 `test_layers`/`test_no_circular_import`/`test_static_hygiene`/`test_startup_budget` + `distribution_build.py --verify`。
- 已知盲区（记录不改）：包内模块暂不进入 `production_files()` 顶层口径，与 `agent/` 子包现状一致；门面清除轮再统一升级 `_scan.py` 递归口径。
