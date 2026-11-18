# R3311 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 6A（D7 结构治理轮：资产类别唯一权威）
<!-- round-evidence: {"commit_base": "e7439b5e", "credential_hits": 0, "evidence_sha256": "c9d7f5327ced2518", "exit": 0, "failed": 0, "passed": 26, "round": 3311, "tests": "run_selftests.py -k asset_contract script_manifest"} -->

## 三问

1. **本轮类型**：结构治理轮（§3.3／任务书轮 6A·D7 第一组）——`script_manifest_contract.KINDS` 改名 `MANIFEST_KINDS` 并由 `asset_contract.KINDS` 派生，不留别名；同轮改完全部消费者；物理特征五件字段化助手自 `script_manifest_schema` 原样迁入 `asset_contract`（唯一行为变化是定义位置，口径一字未动）。未触碰任务书「明确不做」的 6B/6C/6D。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `run_selftests.py -k asset_contract script_manifest` 26 条全绿（`script_manifest` 片段无对应测试文件，补跑 `-k script_contract model_output` 85 条全绿覆盖真实消费者）；`smoke_test.py --affected asset_contract script_manifest_contract` 10/10 绿；默认 `smoke_test.py` 9/9 绿；`smoke_test.py --architecture` 502 条 failures=1（`test_round_number_continuous`，`project_status.md` 陈旧的既有欠账，改前改后同一失败集合，见 §架构门禁对比基线）。
3. **欠账少了吗**：少了。资产类别三名（character/scene/prop）自此只有 `asset_contract.KINDS` 一个权威；剧本清单五类显式写成 `asset_contract.KINDS + ('scene_breakdown','emotion_curve')`，错引 L0 时编译期/导入期即报错，不再静默漏掉 `scene_breakdown`/`emotion_curve` 两类校验；`script_manifest_contract` 不再有第二份 `KINDS`。

## 前置核对

- 领号：`round_claim.py next` → **R3311**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`，commit_base `e7439b5e`；3305–3310 已被其他并行工作树领走，round-claims.json 已核对归属本树）。
- 任务书 D7 要求逐条执行：`grep -rn "KINDS\|script_manifest_contract" 程序/` 找全引用点（生产＋测试都改）；`script_manifest_contract.KINDS` → `MANIFEST_KINDS` 由 `asset_contract.KINDS` 派生；不留别名；全仓不再有从 `script_manifest_contract` 取 `KINDS` 的 import。
- 决策来源：`tasks_round_3230_result.md` §2.2/§2.3 H4——`asset_contract.KINDS` 为唯一源，`script_manifest_contract.KINDS` 必须改名派生、禁别名；任务书约线 67 与 §4 测试表约线 731 复述同口径。

## 实现

### 唯一权威（`contract/script_manifest_contract.py`）

```python
import contract.asset_contract as asset_contract

MANIFEST_KINDS = asset_contract.KINDS + ('scene_breakdown', 'emotion_curve')
MANIFEST_OF_KIND = dict(zip(MANIFEST_KINDS, MANIFESTS))
KIND_OF_MANIFEST = dict(zip(MANIFESTS, MANIFEST_KINDS))
```

- 旧 `KINDS = ('character','scene','prop','scene_breakdown','emotion_curve')` 整体删除，**无 `KINDS = MANIFEST_KINDS` 别名**；`hasattr(mc,'KINDS') == False` 已断言。
- `MANIFESTS` 五文件名元组、`HEADER`、`STAGE_OUTPUTS`、`STAGE_MANIFESTS` 等其余导出原样未动。

### 消费者迁移（同轮全改）

| 文件 | 改动 |
| --- | --- |
| `contract/script_manifest_schema.py` | `from contract.script_manifest_contract import … KINDS …` → `MANIFEST_KINDS`；`schema()` 的五类循环改遍历 `MANIFEST_KINDS`；物理特征助手改从 `contract.asset_contract` 导入并按原名再导出（见下） |
| `contract/script_contract.py` | manifest 导入行 `KINDS` → `MANIFEST_KINDS`（行数回收到模块上限内，见 §过程插曲） |
| `script_contract.py`（顶层门面） | 再导出清单 `KINDS` → `MANIFEST_KINDS` |
| `tests/test_script_contract.py` | `sc.KINDS` → `sc.MANIFEST_KINDS`（`test_the_five_manifests_and_their_producers`）；新增 `DefaultsTests`＋`test_non_mapping_physical_features_are_reported` 补分支覆盖（见 §测试契约变更） |
| `contract/asset_contract.py` | 顶层 `import contract.script_contract` 删除（断环）；迁入 `PHYSICAL_KEYS`/`HINTS`/`SPLIT`/`_pieces`/`_hit`/`split_features`/`field_features`；`KINDS = ('character','scene','prop')` 保持唯一权威 |
| `维护记录/分支覆盖率基线.json` | 官方工具 `scripts/branch_coverage_report.py` 按基线 targets 全量复测重写（结构变了决策点数变了，门禁要求） |

### 为什么助手要迁到 `asset_contract`（最简方案决策，任务书未指明位置）

`script_manifest_contract` 现在要 import `asset_contract` 取 `KINDS`；而 `asset_contract` 原先顶层 `import contract.script_contract`（用 `script_contract.PHYSICAL_KEYS` 等做资产校验）。若助手仍留在 `script_manifest_schema`，依赖链成环：`asset_contract → script_contract → script_manifest_schema → asset_contract`。最简解法是把这五件纯函数助手（无任何 script 依赖、只操作字符串/dict）上移到 `asset_contract`——它们本来就是「资产条目长什么样」的一部分，归属合理；`script_manifest_schema` 按原名再导出，`script_contract.py:1042` 的既有导入、`tests/` 里全部 `sc.split_features`/`sc.field_features`/`sc.PHYSICAL_KEYS` 调用点**一字未改**仍工作（已用 `is` 同一性断言核验）。

## 消费者清单（全仓核对后）

- **旧 `script_manifest_contract.KINDS` 的直接消费者**（改前全仓仅 2 处）：`contract/script_contract.py`、`contract/script_manifest_schema.py`——均已改 `MANIFEST_KINDS`。
- **门面级 `KINDS` 消费者**：`script_contract.py` 门面、`tests/test_script_contract.py`——均已改。
- **`MANIFEST_KINDS` 现存引用**：`contract/script_contract.py:41`、`contract/script_manifest_schema.py:19,340`、`script_contract.py:25`、`tests/test_script_contract.py:85`——全部是新名，无一处取旧名。
- **`asset_contract.KINDS` 现存引用**：`contract/script_manifest_contract.py`（派生源）、`tests/test_asset_contract.py:32`（`ac.KINDS` 遍历，语义本就正确）。
- **同名 `KINDS` 但属其他概念、明确不动**：`contract/file_naming.py`（文件名类目）、`domain/asset_batch_service.py`（资产前缀映射）、`domain/skill_command.py`、`orchestrator/skill_budget.py`、`orchestrator/storyboard_page_controller.py`、`smoke_test.py` 局部表、`ui/` 各处——与剧本/资产契约无关。
- **`STAGE_MANIFESTS` 等其余 manifest 契约导入方**：`contract/stage_layout.py`、`tests/test_recon_service.py`、`tests/architecture/_layers.py`（L0 登记）——不涉 KINDS，未动。

## 测试契约变更（AGENTS §2.4 如实记录）

- **`script_contract.KINDS`／`contract.script_contract.KINDS` 公开名移除**：旧值是五类清单 kind（含 scene_breakdown/emotion_curve），与 `asset_contract.KINDS` 三类资产 kind 同名不同集正是本轮要消的歧义源。现公开面为 `MANIFEST_KINDS`（五类）＋ `asset_contract.KINDS`（三类资产）；全仓 grep 证实无任何 `script_contract.KINDS`／`contract.script_contract.KINDS`／`from …script_contract import KINDS` 消费者，门面无 `__all__`、`import *` 实测通过。
- **新增 2 条用例**（`tests/test_script_contract.py`，补结构迁移后 `script_manifest_schema` 的 4 个未覆盖决策点，非弱化既有断言）：
  - `DefaultsTests.test_every_kind_has_its_own_shell_and_unknown_kind_is_empty`：五类 `defaults()` 空壳键集逐类断言＋未知类别返回 `{}`（覆盖 `defaults()` 的 scene/scene_breakdown/emotion_curve 分支与落空分支）。
  - `ValidateTests.test_non_mapping_physical_features_are_reported`：`physical_features` 给 list 时 `validate` 报「必须是对象或字符串」（覆盖 `validate` 的 elif 负分支）。
- 既有断言零改动：`split_features`/`field_features`/`normalize`/`validate`/`schema`/`manifest` 全部行为用例原样通过。

## 测试证据

- `run_selftests.py -k asset_contract script_manifest` → **26 条全绿**（任务书字面口径；`script_manifest` 文件名片段无匹配，manifest 消费者实为 `test_script_contract*`／`test_model_output_contract`）。
- `run_selftests.py -k script_contract model_output` → **85 条全绿**（真实消费者补跑：`test_script_contract` 4 分片 56 条＋`test_script_contract_production_locks` 6 条＋`test_model_output_contract` 23 条）。
- `smoke_test.py --affected asset_contract script_manifest_contract` → **10/10 绿**（门禁段定向自检全过）。
- `smoke_test.py` → **9/9 绿**。
- `smoke_test.py --architecture` → **502 条，failures=1**（见下节）。
- 契约不变量脚本断言（临时核验，未入库）：`MANIFEST_KINDS` 五元组＝`asset_contract.KINDS`＋两剧本类；`mc` 无 `KINDS` 属性；schema 再导出与 asset_contract `is` 同一；`schema()` 产五 manifest、kind const 正确——全过。

## 架构门禁对比基线

| 时点 | 结果 |
| --- | --- |
| 改前（本工作树 HEAD `e7439b5e`，未含本轮 diff） | 502 条，failures=1：`test_round_number_continuous`（`project_status.md` 停在 3234，状态页仅 master 可提交，工作树固有欠账） |
| 改后 | 502 条，failures=1：同一用例 `test_round_number_continuous`（`3234 != 3305`——期望值随最新结果文件递增，本文件落盘领号 R3311 后口径同前）——**失败集合不变，零新增红** |

过程插曲（如实记录）：

1. **`test_no_module_exceeds_its_cap` 曾红**：`contract/script_contract.py` 1104 行 > 上限 1103——manifest 导入行换名后换行排版多占一行；把该 import 收成单行长括号格式，回到 1103 行，复跑转绿。
2. **`test_baseline_decision_points_match_current_entities` 曾红**：助手迁入使 `asset_contract.py` 决策点 53→66、`script_manifest_schema.py` 44 点中 4 点失覆盖——按门禁规则先补用例（上节 2 条新测试把 schema 补到 44/44＝100%），再用官方 `scripts/branch_coverage_report.py` 按基线 targets 全量复测重写 `分支覆盖率基线.json`（2546 决策点、1352 覆盖；`asset_contract.py` 66 点 86.4%、`script_manifest_schema.py` 44 点 100%、`script_manifest_contract.py` 0 点 100%），复跑转绿。基线 JSON 由工具整体重写，`file_index.py` 等行序/覆盖数随全量测量刷新属正常。
3. **诊断脚本** `.selftmp_cov_diag.py` 等临时文件已删除，`git status` 仅余本轮 7 个授权文件。

## 欠账与处置

1. **`test_round_number_continuous` 红**：`project_status.md` 停在 3234，工作树分支无法提交状态页——沿用 R3267/R3280/R3286/R3298/R3300/R3304 同口径既有欠账，合入轮由 master 侧同步解决；本轮未授权改状态页，如实记录。
2. **`script_contract.KINDS` 公开名移除**：属本轮契约变更（消歧义的必要一环），全仓无消费者、测试已同步；若外部脚本/插件曾按名取用会报 AttributeError——仓内 grep 已证无此类用法。
3. **物理特征助手归属**：现定义在 `asset_contract`、由 `script_manifest_schema` 再导出；若未来剧本清单与资产契约彻底分家，可再评估是否下沉回 schema 层——当前 L0 同层内归属合理，不预做抽象。
4. **全量绿凭据**：本轮为结构治理轮，按 §5 适用 `--architecture`＋定向自检，未跑 `--all --safe`；common-dir 全量凭据状态未在本轮核验，如实标注「未运行」。

## 提交

- 提交信息：`R3311: …`（见 git log）；暂存范围仅 `程序/` 下本轮 7 个文件（5 改 1 测试改 1 基线 JSON），`project_status.md` 未动。
