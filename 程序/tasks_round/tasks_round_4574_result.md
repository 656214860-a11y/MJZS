# R4574 轮次结果（PB-B1-L13：清理 S03 任务书与直连规则的历史资产注入）
<!-- round-evidence: {"commit_base": "9fee6f5cb", "credential_hits": 0, "evidence_sha256": "cf6d583fcdf8cb87", "exit": 0, "failed": 0, "passed": 83, "round": 4574, "tests": "run_selftests.py -k storyboard_scope storyboard_direct_api prompt_templates golden_outputs copy_rules"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（清理 L1 `infra/asset_prompt_rules.py` 与 L3 `orchestrator/workflow_tasks.py` 中残留给 S03 的旧 3 步流程资产清单／锚点注入，刷新对应黄金基线并翻绿 `REQ-S03-56`）。
- **测试跑了吗、三个基线过了吗**：已运行——定向＋架构套件 101/101 通过（含 `test_storyboard_scope`、`test_storyboard_direct_api`、`test_prompt_templates`、`test_golden_outputs`、`test_copy_rules`、`test_requirement_traceability`、`test_layer_relations`、`test_module_size_ratchet`、`test_static_hygiene`）；默认冒烟 9/9 通过（含隐藏桌面探针）；`workflow` 非 GUI 消费者 7 文件 31/31 通过（`test_workflow` 因后台全量持跨树 GUI 锁记 `GUI_DEFERRED`，确认无 `storyboard_direct_rules`／旧资产句断言）；完整全量安全回归留待本任务书四卡合齐后统一执行。
- **欠账少了吗**：`REQ-S03-56`／`DES-S03-56` 完整闭环并翻绿为 ✅，零新增欠账。

## 改动清单

- `程序/infra/asset_prompt_rules.py`：
  - 新增 `storyboard_boundary_rules()`，仅返回 `PROP_RULES + CHARACTER_RULES`（普通道具 `ordinary_props` 与背景人物不分配 `CHAR` 编号的镜头边界，不携带资产建档与锚点复制段）。
  - 校正 `rules('storyboard')` 开头措辞（去除过期的「第2步资产职责」「先读取第1步的固定角色提示词」「每镜引用的编号都必须在统一清单中存在」），明确其供第 05 资产管理补齐提示词使用，保留 `+COMMON` 不破坏 `test_prompt_templates.py` 与 `rules('writing')`。
- `程序/orchestrator/workflow_tasks.py`：
  - `script_prompt(stage='storyboard')` 去除要求 S03 同步生成 `episode/assets/资产清单/assets.json` 与 `资产需求.md` 的旧文案，改为明确「不要求资产清单预先存在，不得自建或改写资产清单，资产清单在采用分镜后由程序同步生成」。
  - `script_prompt(stage='storyboard')`、`script_followup(stage='storyboard')`、`storyboard_direct_rules()` 改为注入 `storyboard_boundary_rules()` 而非旧 `asset_rules('storyboard')`。
- `程序/tests/fixtures/golden/asset_rules_storyboard.txt`：按 `tests/test_golden_outputs.py` 规程以 `GOLDEN_UPDATE=1` 刷新（原因：`REQ-S03-56` 有意清理 `asset_prompt_rules.rules('storyboard')` 开头旧 3 步流程过期措辞；`asset_rules_writing.txt` 未改动）。
- `程序/tests/test_storyboard_scope.py`：新增 `test_req_s03_56_workflow_tasks_drop_legacy_asset_generation_and_keep_shot_boundaries`（覆盖 `direct`、`prompt`、`followup` 三通道及 `asset_prompt_rules.rules('storyboard')`）。
- `程序/docs/stages/S03_初步分镜.md`：`REQ-S03-56`、`DES-S03-56` 翻绿为 ✅，同步更新 `测试锚定` 与 `IF-S03-11`。

## 先红后绿证据

改动前运行 `tests.test_storyboard_scope.StoryboardScopeTests.test_req_s03_56_workflow_tasks_drop_legacy_asset_generation_and_keep_shot_boundaries` 实测 4 项子断言全部失败：

```text
FAIL (channel='direct'): AssertionError: '第2步资产职责' unexpectedly found in ...
FAIL (channel='prompt'): AssertionError: '同步生成episode/assets/资产清单/assets.json' unexpectedly found in ...
FAIL (channel='followup'): AssertionError: '第2步资产职责' unexpectedly found in ...
FAIL: AssertionError: '第2步资产职责' unexpectedly found in asset_prompt_rules.rules('storyboard')
```

改动后全部通过：
- 定向与核心架构门禁（9 模块）：101/101 通过（27.9s）
- `smoke_test.py`：9/9 通过（含隐藏桌面探针）
- `run_selftests.py --serial -k workflow`：7 个非 GUI 文件 31/31 通过（`test_workflow` 因后台进程持有跨树 GUI 锁返回 `GUI_DEFERRED`）

## 提交状态

- 分支：`codex/pb-s04-s05-decouple`
- 提交方式：经 `scripts/dev.py commit` 提交（含证据文件 `tasks_round/evidence/R4574.json`）。
