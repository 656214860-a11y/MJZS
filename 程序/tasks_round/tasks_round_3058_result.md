# R3058 结果：T10 包化——orchestrator/（L3 编排层）第三批 2 个高扇出模块迁移（L3 中扇出收尾）
<!-- round-evidence: {"commit_base": "d6e50d8c", "credential_hits": 0, "evidence_sha256": "63750d5c1013fa03", "exit": 0, "failed": 0, "passed": 170, "round": 3058, "tests": "run_selftests.py -k workflow_settings storyboard_selection workflow file_cache agents_md"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿（首轮 1 红＝smoke_test 源路径检查未随包更新，已修）；`run_selftests.py -k <关键词组>` 10 个测试文件 170 条全绿（3.7 秒）；`smoke_test.py --architecture` 架构门禁 471 项复测；覆盖率基线重测 610 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化 **orchestrator/ L3 中扇出收尾**：`orchestrator/` 实体由 70 → 72 个。L3 顶层仅剩 `writing_api`（954 行，随拆分方案批次）、`stage_execution_service`（扇出 50，建议单独一轮）、`image_agent_runner`（子进程入口永久除外）；L4 顶层 121 个实体随后分批迁 `ui/`；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | 2 个高扇出（22/24）顶层 L3 模块 `git mv` 入 `orchestrator/`：workflow_settings、storyboard_selection。 |
| 别名门面 ×2 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = orchestrator.<名>` 别名门面；2/2 `import <扁平名> is import orchestrator.<名>` 实体同一校验全过。 |
| 消费方 import | 47 个引用文件改包路径导入（行级 `import`/`from` 重写＋引号动态串 `'workflow_settings'`/`'storyboard_selection'` → `'orchestrator.*'`）；AST 复扫残留 2 处均为**正确扁平引用**：`asset_batch.py` 经 `ui_plugin_registry.module('workflow_settings')` 走动态导入唯一入口（注册表键命名空间）、`ui_plugin_registry.py` 注册表自身键表——均经门面解析，不改。批内无同批边。逻辑零改动，仅 import 行。 |
| `__file__` 锚点 ×6 | `orchestrator/workflow_settings.py` 6 处 `Path(__file__).resolve().parent` → `.parents[1]`（BUNDLED_SKILLS 根＋5 处 `model_pool.pool(program=…)`），解析结果仍为 `程序/`；storyboard_selection 无锚点。 |
| 测试取径 ×3 | `test_agents_md.py`（`_read(ROOT/'workflow_settings.py')` → `entity_file()`）、`test_workflow_settings_json_boundary.py`（同法）、`test_file_cache.py`（`storyboard_selection` 读径改 `Path(module.__file__)` 随门面——原 `(program/name)` 会读到 9 行门面使就地改写检查 vacuous 通过，属必须修的真取径）。`test_project_context_boundary`/`test_storyboard_catalog_scan_count`（git show 历史基线）/`test_complexity_ratchet` 天然兼容。断言语义未动。 |
| 冒烟取径 ×1 | `smoke_test.py` 检查项 `程序\workflow_settings.py` 源路径 → `程序\orchestrator\workflow_settings.py`（同 `orchestrator\workflow_tasks.py`/`domain\idea_transcript.py` 既有先例）。 |
| 棘轮台账 | `架构统一基数.json` 第四项本批无命中（覆盖率审计24 retired 条按既有口径未动）；`_layers.py` 扁平登记名天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **610 模块／74 覆盖**（608+2）；`runbook.md` §11 同步（610/74/536）；`architecture.md` orchestrator 目录树「六批共 70 个」→「七批共 72 个」；`distribution_manifest.md` glob 已覆盖；`PROJECT_MAP.md` Agent 工作流/分镜与批次两行路径改 `orchestrator/` 前缀。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过（首轮 7/8——「工作流阶段正确映射到阶段配置」检查读 `程序\workflow_settings.py` 门面源码落空，改包路径后复测绿）。
- `run_selftests.py -k workflow_settings storyboard_selection workflow file_cache agents_md`：10 个测试文件 170 条用例全绿、0 红、3.7 秒。
- `smoke_test.py --architecture`：471 项全量复测（状态页轮次头按先例临时同步为 3059 后运行）。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行）；`distribution_build --verify`（同前批口径）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3058**；新建 `codex/wip-R3058` 分支叠加在 `codex/wip-R3057`（d6e50d8c）之上承接本批（测试取径修复先行入分支）。
- **smoke 源路径检查**：冒烟脚本含硬编码 `程序\<模块>.py` 关键词检查项，本批首次命中已迁移模块；已按 `orchestrator\workflow_tasks.py` 先例改包路径。后续批次迁移前应先 grep smoke_test.py 中被迁模块名。
- **动态串重写边界**：行级重写扩展至引号字面量时曾担心误改注册表键，实测仅命中 import_module 语境；`ui_plugin_registry` 键表与 `module()` 调用保持扁平（注册表命名空间，门面解析）。

## 下一步（T10 后续批次）

- L3 收官仅剩 3 项：`workflow_settings`/`storyboard_selection` 已迁；`writing_api`（954 行）随拆分方案批次；`stage_execution_service`（扇出 50，阶段执行网关）建议单独一轮；`image_agent_runner` 子进程入口永久除外。
- **L4 顶层 121 个实体**分批迁 `ui/`（绝大多数扁出 0–2 叶子 UI 模块）；`app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次；门面清除轮需单独授权。
