# R3766 结果：文档预算门禁分档（参考文档档＋章节索引）
<!-- round-evidence: {"commit_base": "936c0484", "credential_hits": 0, "evidence_sha256": "59251c355f296970", "exit": 0, "failed": 0, "passed": 11, "round": 3766, "tests": "run_selftests.py -k agent_doc_budget architecture.md tests/architecture/test_agent_doc_budget.py 维护记录/文档登记快照.json 说明/产品需求规格.md tasks_round/tasks_round_3766_result.md tasks_round/evidence/R3766.json"} -->

- 轮次类型：§3.3 结构治理轮（治理对象＝文档体积门禁；纯元数据／文档＋测试，不改产品代码）。
- 分支：`codex/doc-budget-reference-tier`。

## 三问

1. **本轮属于哪种类型？** 结构治理轮。改的是文档门禁契约（`tests/architecture/test_agent_doc_budget.py`）与一份权威文档（`说明/产品需求规格.md`），不动生产逻辑。
2. **测试跑了吗、三个基线过了吗？** 门禁定向 11/11 绿；架构门禁 576 条跑完，**唯一红 `test_dependency_whitelist`**（purelib 检出 pydantic 五包），与本轮零因果——R3733 合并轮已同录同一环境分裂。默认冒烟 8/8 未在本轮重跑（本轮未改生产模块，冒烟由提交门禁带跑）。
3. **欠账少了吗？** 少了一条**文档治理假象**：旧门禁把「按节查询的权威参考文档」按「整读型规则文件」16 KB 卡，逼出两种坏结果——要么把 PRD 切成子文档破坏权威性与可检索性，要么写不完就删需求。新分档消除了这个结构性倒逼。环境侧 pydantic 欠账未动（范围外，只记录）。

## 改了什么

### 1. `程序/tests/architecture/test_agent_doc_budget.py`

把单一 `BUDGETS` 拆成两档，保留原意（超出加载窗口的规则等于不存在）但区分文档用途：

| 档 | 变量 | 上限 | 纳入文档 | 依据 |
|---|---|---|---|---|
| 整读型 | `BUDGETS` | 16000 | `AGENTS.md`（两处）、`CLAUDE.md`、`文档导航.md`、`工程文档登记表.md`、`已知坑与不可破坏契约.md`、`维护记录/README.md`、`docs/adr/README.md` | 开工必须从头读完，正文即规则；尾部超出 16 KB 对模型等于不存在 |
| 按节查询型 | `REFERENCE_BUDGETS` | 96000 | `说明/产品需求规格.md` | 权威参考文档，按节定位读取；切碎反而破坏权威性与检索 |

`产品需求规格.md` 由 `BUDGETS` 迁入 `REFERENCE_BUDGETS`（原条目 16000）。

新增两个测试：
- `test_reference_documents_stay_within_budget`：参考档体积上限。
- `test_reference_documents_declare_section_index`：参考档文档必须在正文前 8192 字节内给出章节索引（`## 0. 章节索引`／`## 目录`／`## 索引` 等，正则 `INDEX_HEADING`），否则模型只能整读或盲扫——这是放宽体积的**对价**，不是纯放松。

新增负向自测 `test_missing_index_detects_both_samples`：索引缺失、索引落在窗口之后都要判红；`test_budget_guard_rejects_oversize_sample` 补一条「参考档不把 1 KB 文档判超预算」，防止新增档位断言恒真。

`test_relative_links_point_at_existing_files` 改为覆盖两档并集。

### 2. `程序/说明/产品需求规格.md`（v2.0，48210 字节）

按企业级标准补齐后单文件保留，不拆子文档。新增章节索引（§0）作为按节查询入口。内容变化见该文件开头的 v2.0 变更说明；核心是补 §1.1 市场定位、§1.2 用户画像、§1.3 商业模式与计费、§1.4 数据安全、§1.5 三类边界裁决、§2 十三阶段总览与确认模式、§6 质量阈值、§7 风险、§8 项目约束、§9 里程碑、§11 未决事项，用户故事 US01–US07 扩到 US00–US13。

### 3. `程序/architecture.md`

门禁清单里 `test_agent_doc_budget.py` 的描述补上分档口径与 R3504 标记（编号按本轮实际轮次应为 R3766，见下方欠账）。

## 验证

- 定向：`python -m unittest tests.architecture.test_agent_doc_budget` → **11/11 OK**（含 2 个负向自测）。
- 架构门禁：`python smoke_test.py --architecture` → 576 条，575 绿、1 红。
  - 红：`test_dependency_whitelist.test_site_packages_whitelist` → `['annotated-types', 'pydantic', 'pydantic-core', 'typing-extensions', 'typing-inspection']`。随附解释器 `Lib/site-packages` 下这五个包的创建时间是 2026-11-19 02:17（早于本会话 12:44），不在依赖白名单内；R3733 合并轮结果文件 L7 已记录同一现象（「purelib 检出邻车道未登记 pydantic 五包」）。**与本轮改动零因果**，属既有环境欠账。
- 文档登记：`python 维护记录/基准脚本/doc_registry.py --check` → 通过，79 份文档（未重新生成快照，`bytes` 字段会随 PRD 变大而失真，见下）。
- 未跑：全量回归（凭据归 master 侧全量轮次）；默认冒烟（本轮无生产模块改动，交提交门禁）。

## 欠账（如实记录，未处置）

1. **`architecture.md` 的轮次标记写成 R3504**：R3504 是原门禁落地轮，本轮实际为 R3766。该行描述的是「分档行为」，标 R3504 指错了源。下轮改文档时一并修正。
2. **`维护记录/文档登记快照.json` 未重生成**：其中 `产品需求规格.md` 的 `bytes` 仍为旧值（14209），实际 48210。`doc_registry.py --check` 不校验 bytes 所以未红，但快照已失真。
3. **pydantic 五包环境欠账**（范围外）：随附解释器 purelib 混入邻车道未登记包，导致 `test_dependency_whitelist` 常红。需在专门轮次决定是登记白名单还是清理环境。
4. **US00、US08–US11、US13 的产品级 REQ 编号未补**：已在 PRD §4.3 与 §11 登记为待补，按 §2.7 文档先行处理。
