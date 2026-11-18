# R3313 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 6B（D7 结构治理轮：云端资产模型能力按名寻址）
<!-- round-evidence: {"commit_base": "946d314c", "credential_hits": 0, "evidence_sha256": "082de827962cee02", "exit": 0, "failed": 0, "passed": 2, "round": 3313, "tests": "run_selftests.py -k production_model_contract cloud_assets"} -->

## 三问

1. **本轮类型**：结构治理轮（§3.3／任务书轮 6B·D7 第二组）——`ASSET_CLOUD_MODELS` 保留为有序元组；云端资产模型的节点类型与参考图上限改为按模型名的命名映射 `ASSET_CLOUD_NODE_TYPES`／`ASSET_CLOUD_REFERENCE_LIMITS`，定义收口在 `contract/production_model_contract.py` 同一处；`infra/cloud_assets.py` 的两个 `dict(zip(元组, 位置值))` 隐性位置契约删除，改引契约映射。未触碰任务书「明确不做」的 6C/6D。
2. **测试跑了吗、三个基线过了吗**：跑了，且先红后绿。新测试在改动前实测 FAIL（`'OpenAIGPTImage1' != 'GeminiImage2Node'`——元组中部插入一个模型后 `zip` 把 `Nano Banana Pro` 错配到第三个节点名，位置契约缺陷实证）＋ ERROR（契约属性缺失）；改动后 `run_selftests.py -k production_model cloud_assets asset_batch` 9 文件 31 条全绿；`smoke_test.py --affected production_model_contract cloud_assets` 10/10 绿；默认 `smoke_test.py` 9/9 绿；`smoke_test.py --architecture` 502 条 failures=1（`test_round_number_continuous`，`project_status.md` 陈旧的既有欠账，改前改后同一失败集合，见 §架构门禁对比基线）。
3. **欠账少了吗**：少了。云端资产模型的「元组位置 ↔ 节点类型/参考图上限」隐性契约消除——往 `ASSET_CLOUD_MODELS` 中间插一个模型（如新增云端模型排在 UI 选项中部）不再静默错位既有模型的节点类型与上限；三个基线（定向自检、默认冒烟、架构门禁失败集合）零新增红。

## 前置核对

- 领号：`round_claim.py next` → **R3313**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`，commit_base `946d314c`；3312 已被其他并行工作树领走）。
- 任务书 D7 6B 验收逐条：节点类型与参考图上限改为按模型名的命名映射、放在同一处定义 ✓；`ASSET_CLOUD_MODELS` 仍保留为有序元组（`domain/asset_batch_service.py:348` 用它的顺序排选项）✓；测试往元组中间插入一个模型、既有模型节点类型与上限不变 ✓。
- 决策来源：任务书约线 670（D7 表 6B 行）；R1647 先例（模型名事实下沉 L0 契约，本模块注释行 12-14 同口径）。

## 实现

### 唯一事实源（`contract/production_model_contract.py:17-29`）

```python
ASSET_CLOUD_NODE_TYPES = {
    'Seedream 5.0 Pro': 'ByteDanceSeedreamNode',
    'Nano Banana Pro': 'GeminiImage2Node',
    'GPT Image 2': 'OpenAIGPTImage1',
}
ASSET_CLOUD_REFERENCE_LIMITS = {
    'Seedream 5.0 Pro': 10,
    'Nano Banana Pro': 14,
    'GPT Image 2': 16,
}
```

- 两个映射均以**模型名为键**，与 `ASSET_CLOUD_MODELS`（第 16 行，原样未动）并列定义在同一处；模块保持零 import 纯数据。
- `ASSET_CLOUD_MODELS` 仍是有序元组——`domain/asset_batch_service.py:348` 的 `choices = [ASSET_LOCAL_MODEL, *ASSET_CLOUD_MODELS]` 与 `cloud_assets.MODELS` 的顺序语义不变。

### 消费端（`infra/cloud_assets.py:12-15`）

```python
NODE_TYPES = dict(production_model_contract.ASSET_CLOUD_NODE_TYPES)
LIMITS = dict(production_model_contract.ASSET_CLOUD_REFERENCE_LIMITS)
```

- 旧 `dict(zip(ASSET_CLOUD_MODELS, ('ByteDanceSeedreamNode', 'GeminiImage2Node', 'OpenAIGPTImage1')))` 与 `dict(zip(ASSET_CLOUD_MODELS, (10, 14, 16)))` 两行位置对齐派生删除；`dict()` 拷贝保留原「模块级可变映射」语义，契约常量不会被消费端污染。
- `LOCAL`／`MODELS` 别名、`validate()`（行 61/65-66）、`graph()`（行 72）的查找方式与报错文案**一字未动**——`NODE_TYPES[model]`／`LIMITS[model]` 仍按模型名取值，行为对三模型逐值等价（Seedream→ByteDanceSeedreamNode/10、Nano Banana Pro→GeminiImage2Node/14、GPT Image 2→OpenAIGPTImage1/16）。

## 最简方案决策（任务书未指明映射放哪一层）

命名映射放 **L0 契约**而非留在 `cloud_assets`：任务书把两文件并列为本轮范围，「放在同一处定义」即契约模块成为云端资产模型事实（有哪些模型＋各自节点类型/参考图上限）的唯一登记处；`NODE_TYPES`/`LIMITS` 全仓 grep 证实仅 `cloud_assets` 内部消费（`validate`/`graph`），无第二消费者，不构成「事实该下沉」的充分条件时仍选择与 `ASSET_CLOUD_MODELS` 同址——元组管顺序、映射管能力，一处看全。`cloud_assets` 保留 `NODE_TYPES`/`LIMITS` 公开名作别名，模块公开面不变。

## 消费者清单（全仓核对后）

- **`ASSET_CLOUD_MODELS` 顺序消费者**：`domain/asset_batch_service.py:342,348`（UI 选项排序，本轮未动）、`infra/cloud_assets.py:11`（`MODELS` 有序清单）、`tests/test_req_s05_anchors.py:209`（断言 `MODELS == list(ASSET_CLOUD_MODELS)`，语义不变仍绿）。
- **`NODE_TYPES`/`LIMITS` 消费者**：仅 `infra/cloud_assets.py` 内部（行 61、65-66、72）；全仓 grep 无任何 `from cloud_assets import NODE_TYPES/LIMITS` 或 `cloud_assets.NODE_TYPES` 外部引用。
- **`LOCAL`/`MODELS` 外部消费者**（均不受影响）：`orchestrator/asset_auto_batch_service.py:7`、`orchestrator/asset_batch_execution.py:98`、`orchestrator/stage_models.py:40,371`、`ui/asset_batch.py:180`、`ui/asset_skill_batch.py:49`、`ui/cloud_assets_dialog.py:2`、`tests/` 多处——名字、值、顺序全部不变。
- **同名 `LIMITS` 但属其他概念、明确不动**：`domain/recon_service.py`、`infra/api_endpoints.py`、`skills/.../sd_core.py`、`validate_prompt.py`——与云端资产模型无关。

## 测试契约变更（AGENTS §2.4 如实记录）

- **零既有断言改动**：`test_req_s05_anchors.py`、`test_api.py`、`test_assets.py`、`test_aspect_ratio_priority.py` 等全部消费方测试原样通过。
- **新增 `tests/test_production_model_contract.py`（2 条用例）**：
  - `test_named_capability_maps_cover_exactly_the_ordered_models`：契约不变量——两个映射键集与 `ASSET_CLOUD_MODELS` 完全一致（防「元组加了模型忘加映射」漂移），三模型节点类型/上限逐值断言。
  - `test_mid_tuple_insert_keeps_existing_models_node_type_and_limit`：任务书验收用例——把 `'探针云端模型'` 插进 `ASSET_CLOUD_MODELS` 第二位（中部），`importlib.reload(cloud_assets)` 重建消费端，断言 `MODELS` 仍反映新元组顺序（顺序职责保留）而三个既有模型的 `NODE_TYPES`/`LIMITS` 逐项不变；`finally` 中还原元组并再 reload，不泄漏状态。

## 先红后绿证据

改动前（契约无映射、cloud_assets 仍 `zip` 派生）实测：

```
FAIL: test_mid_tuple_insert_keeps_existing_models_node_type_and_limit
AssertionError: 'OpenAIGPTImage1' != 'GeminiImage2Node'
ERROR: test_named_capability_maps_cover_exactly_the_ordered_models
AttributeError: module 'contract.production_model_contract' has no attribute 'ASSET_CLOUD_NODE_TYPES'
```

`'OpenAIGPTImage1' != 'GeminiImage2Node'` 即位置契约缺陷实证：元组第 2 位插入后 `Nano Banana Pro` 被错配到第三个节点类名。改动后同文件 2/2 ok。

## 测试证据

- `run_selftests.py -k production_model cloud_assets asset_batch` → 改前 8 文件 29 条全绿；改后 **9 文件 31 条全绿**（新增 `test_production_model_contract` 2 条；`-k` 片段 `production_model`/`cloud_assets` 无同名旧测试文件，资产批次消费者由 `asset_batch` 片段覆盖）。
- `smoke_test.py --affected production_model_contract cloud_assets` → **10/10 绿**（门禁段自动圈定 9 个真实消费者测试文件：`test_api`、`test_app_metadata`、`test_aspect_ratio_priority`、`test_assets`、`test_req_s05_anchors`、`test_ui_edges_autopilot` 等，461 秒含跨树 GUI 令牌等待，0 红）。
- `smoke_test.py` → **9/9 绿**。
- `smoke_test.py --architecture` → **502 条，failures=1**（见下节）。

## 架构门禁对比基线

| 时点 | 结果 |
| --- | --- |
| 改前（本工作树 HEAD `946d314c`，未含本轮 diff） | 502 条，failures=1 errors=0：`test_round_number_continuous`（`project_status.md` 停在 3234，期望 3312——状态页仅 master 可提交，工作树固有欠账） |
| 改后 | 502 条，failures=1：同一用例 `test_round_number_continuous`（`3234 != 3312`）——**失败集合不变，零新增红** |

过程插曲（如实记录）：首次以 `python -X utf8 -B smoke_test.py --architecture` 跑基线时另出现 2 个 ERROR（`test_coverage_tool_runs_on_bundled_interpreter`、`test_branch_coverage_tool_runs_on_bundled_interpreter`，子进程 GBK 输出撞 UTF-8 解码、`completed.stdout` 为 None）；去掉 `-X utf8` 按项目惯用调用（`python -B`）后两例全绿、基线回到 failures=1——确认为调用方式问题而非代码问题，改前改后均按无 `-X utf8` 口径实测。

## 欠账与处置

1. **`test_round_number_continuous` 红**：`project_status.md` 停在 3234，工作树分支无法提交状态页——沿用 R3267–R3311 同口径既有欠账，合入轮由 master 侧同步解决；本轮未授权改状态页，如实记录。
2. **映射键集与元组一致性**：靠 `test_named_capability_maps_cover_exactly_the_ordered_models` 的 set 相等断言守卫，未在契约模块加运行时 assert——保持 L0 纯数据、零 import、无新决策点（分支覆盖基线不受影响）。
3. **全量绿凭据**：本轮为结构治理轮，按 §5 适用 `--architecture`＋定向自检，未跑 `--all --safe`；common-dir 全量凭据状态未在本轮核验，如实标注「未运行」。

## 提交

- 领号 R3313；提交信息 `R3313: …`（见 git log）；暂存范围仅 `程序/` 下本轮 4 个文件（2 改 1 测试新增 1 结果文件），`project_status.md` 未动。
</content>
</invoke><|end_message|><|message_model|><|content_thinking|>Now commit. Per commit_round.py: file args are git-added with cwd=PROGRAM (程序 dir), so pass 程序-relative paths. `--tests` keywords trigger evidence re-run of `run_selftests.py -k production_model_contract cloud_assets` — matches test_production_model_contract.py (2 tests, fast, no GUI). Include the result file so it gets stamped and staged.<|end_message|><|message_model|>exec<|content_invoke_tool_json|>{