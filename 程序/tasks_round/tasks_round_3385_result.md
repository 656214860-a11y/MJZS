# R3385 结果文件 — K2 契约路径修复、报告函数归位 L3、动态越层豁免单源化
<!-- round-evidence: {"commit_base": "af2c08ea", "credential_hits": 0, "evidence_sha256": "945812363388c276", "exit": 0, "failed": 0, "passed": 86, "round": 3385, "tests": "run_selftests.py -k script_contract layers"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（任务书 K2 指定类型：D-01/D-02/D-03 根因修复——`contract/` 路径与动态越层、L3 报告权威归位、豁免台账单源化；先红后绿）。
2. **测试跑了吗、三个基线过了吗？** 全部实跑：`tests/test_script_contract.py` 58/58 绿；`tests/architecture/test_layers.py`＋`test_no_circular_import.py` 8/8 绿；`smoke_test.py --architecture` 531/532（唯一红 `test_round_number_continuous` 为分支固有状态——`project_status.md` 仅 master 可提交，合并轮豁免）；`smoke_test.py --affected script_contract` 9 项轮检全过、定向门禁跑 54 模块，唯一红 `test_pet_ui.test_tick_once_drains_into_the_bus` 经主工作区复现证实为 **master 既有回归**（与本 diff 无关，详见「附带发现」）；分支覆盖率基线按 90 个目标 1742 用例真实重测（tests_ok）。
3. **欠账少了吗？** 是：FF-02 动态越层 1→0、FF-03 豁免登记源 2→1；D-01（`program_root()` 指向 `程序/contract`）、D-02（报告函数权威不在 L3）、D-03（豁免双源）三条诊断债消除。

## K2-1　`program_root()` 缺省指向程序目录（先红后绿）

- **红**：新增 `ProgramRootTests.test_program_root_defaults_to_program_dir`，断言 `(root/'skills').is_dir()`；修复前 `Path(__file__).resolve().parent`＝`程序/contract`，无 `skills/`，红。
- **绿**：`contract/script_contract.py` 改 `parent.parent`（`contract/script_contract.py → 程序/`）；显式 `program` 入参语义不变。实测 `sc.program_root()` → `程序/`，`skills/` 存在。
- 影响面：`orchestrator/script_skill_report.py` 两处 `program_root()` 调用同步受益（原缺省口径下注册表实际扫的是 `contract/` 子目录）。

## K2-2　报告函数权威归位 L3（按消费者实情删除）

- **消费者盘点**：`manifest_rows`/`audit_rows`/`merge_problems`/`support_rows`/`unlisted_skills` 全仓仅 `tests/test_script_contract.py` 经顶层门面 `script_contract` 消费；生产代码零调用。
- **处置**：`contract/script_contract.py` 删除 5 个函数本体（含 3 处 `import_module('script_skill_report')` 动态越层）；权威实现在 `orchestrator/script_skill_report.py`——原有 `manifest_rows`/`audit_rows`/`merge_problems` 保留，本轮补入 `support_rows`/`unlisted_skills`（纯报告组合逻辑；`AUDIT`/`MERGE_LANDING`/`MERGE_PART`/`MERGE_OWNER` 等事实常量仍由 L0 提供，L3→L0 向下引用合法）。
- 顶层门面 `script_contract.py` 同步摘除 5 个再导出名；`program_root` 保留在 L0（路径权威）。
- **测试契约变化（AGENTS §2.4）**：`tests/test_script_contract.py` 8 处调用由 `sc.*` 改调 `script_skill_report.*`（L3 实体），断言一字未动。

## K2-3　动态越层清零（FF-02：1→0）

- `KNOWN_DYNAMIC_UPWARD` 中 `("script_contract.py","script_contract","script_skill_report")` 随实现删除自然消失；`test_no_circular_import.py` 的 `KNOWN_DYNAMIC_CYCLES` 同步摘除 `("script_contract","script_skill_report")` 二环（棘轮只降不升）。
- 实测 `_dynamic_upward_pairs() − _upward_pairs()` ＝ `{engine→white_model, keyframe_batch→stage_parallel}`，`script_contract` 边消失。

## K2-4　豁免单源化（FF-03：2→1）

- `维护记录/架构统一基数.json` 新增「动态层级」段（`count`/`baseline_exempt`/`items`，与「层级」段同构，登记 engine→white_model、keyframe_batch→stage_parallel 两条既存豁免）。
- `tests/architecture/test_layers.py` 删除硬编码 `KNOWN_DYNAMIC_UPWARD`，改读台账：断言「实测动态越层 == 台账登记」「豁免数 ≤ baseline_exempt」「disposition/reason 登记规范」，新增/消除均以台账为准。
- 豁免登记源由「架构统一基数.json＋test_layers.py 硬编码」2 源收敛为「架构统一基数.json」1 源。

## 附带修复与发现（本轮实测）

- **工作树运行环境缺口**：`test_pet_ui` FrameBatchSeam 2 红系工作树缺 `运行环境/ffmpeg`；`mklink /J 运行环境 → 主工作区`（gitignored，不入库）后该 2 红转绿。
- **孤儿子模组内容**：`skills/01 剧本准备SKILL/` 下 4 个嵌套 gitlink（剧本锻造/编剧技能集/HoLLMwood/AIGC创作全流程）在工作树无内容，已从主工作区拷入（gitlink 边界内不入库）；`test_the_audit_covers_every_script_skill` 由红转绿。
- **master 既有回归（非本 diff）**：`test_pet_ui.DesktopSeamTests.test_tick_once_drains_into_the_bus` 期望 `('stage.completed','delivery')` 实得 `('stage.paused','delivery')`；在**主工作区 master** 单测复现同样失败，master auto-full-safe（.wt/ci）同项同因红并标 SUSPECT_CONCURRENCY。疑与 R3298 pet_bus 终态事件运行序号接线（dc3b3bb8 合入）相关，属 UI/编排车道范围，本车道不代修，已登记待办。
- **`test_round_number_continuous` 分支固有红**：`project_status.md` 仅 master 可提交（pre-commit 硬闸），分支上「状态轮次 == 最新结果+1」结构性不成立，合并轮 `_merge_in_progress` 豁免。
- **分支覆盖率基线真实重测**：`script_contract.py` 决策点 134→132（删 5 函数净减 2 点）；covered 一度 40→38、percent 28.8% 低于棘轮下限 29.0%。按门禁口径「真实退化须先补用例」，新增 `StructureManifestProblemsTests`（缺件/坏 JSON/名单比对/路径读不到四类边界，8 个决策点转覆盖）后重测：covered 46、percent 34.8%，下限不动。90 目标 1742 用例全过，基线 `tests_ok=true`，totals 1530/2739。

## 测试记录

| 项 | 结果 |
| --- | --- |
| `run_selftests.py -k script_contract script_skill_report layers`（任务书指定） | 86 条用例全过，0 红（含 architecture.test_layers 6 条） |
| `tests/test_script_contract.py` | 58/58 OK（新增 ProgramRootTests＋StructureManifestProblemsTests） |
| `tests/architecture/test_layers.py`＋`test_no_circular_import.py` | 8/8 OK |
| `smoke_test.py --architecture` | 531/532；唯一红 `test_round_number_continuous`（分支固有，合并轮豁免） |
| `smoke_test.py --affected script_contract` | 9 项轮检全过；定向门禁 54 模块，唯一红 pet_ui master 既有回归 |
| `run_selftests.py -k pet_ui`（串行复跑） | 611/612；ffmpeg 2 红已消，余 1 红同 master 既有回归 |
| 分支覆盖率基线重测 | 90 目标 1742 用例 OK；script_contract 46/132＝34.8% ≥ 下限 29.0 |
| 全量回归 | 未触发（分支轮不累计；合并前按规则走 exit-CI） |

## 欠账与阻塞

- **G-1 仍阻塞**（6 个地基分支未合）：K1、K10、K11 继续标注「阻塞于 G-1」，本车道不代做他人合并。
- FF-18 冷导入：K2 删除 3 处 `import_module` 动态导入、未新增导入路径；冷导入基线 K14 验收时统一复测。
- master 既有 pet_ui 回归已登记，移交对应车道（非本任务书范围）。

## 提交

- commit_base：`af2c08ea`（R3384 K0-R 复核提交，含 R3384 结果文件）
- 本轮文件：`contract/script_contract.py`、`orchestrator/script_skill_report.py`、`script_contract.py`、`tests/test_script_contract.py`、`tests/architecture/test_layers.py`、`tests/architecture/test_no_circular_import.py`、`维护记录/架构统一基数.json`、`维护记录/分支覆盖率基线.json`、本结果文件
- commit hash：见 git log（`R3385:` 前缀）
- 测试契约变化：`tests/test_script_contract.py` 报告类调用改调 L3 `script_skill_report`（§2.4 已注明）；断言未动
- 断言未动声明：除上述测试调用路径迁移与新增边界用例外，全部既有断言原样
- 全量：未跑（分支轮；合并轮 exit-CI 为准）
- 合并：待 merge_round 流程
- 工作树环境备注：`运行环境` junction 与 4 个子模组内容拷贝为 gitignored/工作树本地状态，不进入提交
- 结果：R3385 提交完成，K2 四项勾选条件全部满足，待合入 master
- 收尾自检：credential 扫描随 commit_round 证据生成；FF-02/FF-03 实测值已回填上表
- 阻塞：无新增；G-1 阻塞项不变
- 移交：pet_ui 回归移交 UI/编排车道；G-1 等待 6 地基分支合入
- 备注：`test_round_number_continuous` 分支固有红与 pet_ui master 回归均已在上文给出复现证据
- 完成定义核对：K2-1～K2-4 全部落地且有测试/实测证据；结果文件三问已答；未越权改动他人车道文件；未提交 project_status.md
- 车道边界：仅动 `contract/`、`orchestrator/script_skill_report.py`、顶层门面、`tests/`、`维护记录/` 台账与基线
- 依赖说明：L3→L0 引用方向合法；L0 不再反向依赖 L3
- 回滚预案：`git revert <commit>` 即可整体回退；台账「动态层级」段删除、测试改回硬编码需同步
- 后续衔接：K8（Severity 统一）、K9（L0 纯度门）不依赖 G-1，可继续；K1/K10/K11 待 G-1
- 质量自评：报告函数归位后 L0 不再含注册表 IO；豁免单源化消除双源漂移风险；新增边界用例真实提高覆盖
- 风险提示：`script_skill_report` 的 `support_rows`/`unlisted_skills` 为从 contract 迁移的既有逻辑逐字搬运，行为等价
- 验证充分性：先红后绿留痕、架构门禁、定向门禁、覆盖率棘轮四层证据齐备；唯一未全绿项均有 master 复现/结构性说明
- 经验沉淀：分支上跑全量架构门禁前先预期 `test_round_number_continuous` 固有红；工作树首次跑 Tk 测试前先补 `运行环境` junction
- 时间戳：2026-11-18 晚（R3385 轮内）
- 签署：Devin（SWE-2 Flash Max）
- 附：本文件即 K2 轮全部交付物之一；勾选行文字按规则未动，逐条对账由 K23 完成文件负责
- END
