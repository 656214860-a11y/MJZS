# R2191 层级按真实依赖重登记，台账 35→21（结构治理轮·执行）

来源：`tasks_round/tasks_round_2178_result.md` J 节 **J3**。日期：2026-11-01。
基线：`codex/wip-R2189` @ cd800e82（J2）。不改生产代码。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：架构门禁 412 项，只剩 2 条与本轮无关的既有红；`层级` 台账 35→21；`KNOWN_DYNAMIC_UPWARD` 5→3。债务：`--all --safe` 欠账 +1，本分支未跑全量；本轮改了层级登记表，**合入 master 前须跑全量**。

## 改动

按真实静态依赖重登记 8 个模块（`tests/architecture/_layers.py`）：

| 模块 | 旧 | 新 | 依据 |
|---|---|---|---|
| artifact_lineage | L1 | L0 | 无依赖，被 L0 `script_contract` 引用 |
| pet_state、ui_plugin_registry、integrations | L4／L4／L3 | L1 | 只依赖 L0／L1 |
| qwen_setup | L4 | L1 | 只依赖 `api_endpoints`／`model_pool`，与 `model_secrets` 同类 |
| qwen_adapter | L4 | L3 | 引擎适配器，与 `workflow_engines` 同层 |
| workflow_settings、legacy_compat | L4 | L3 | 依赖 L3 的 `stage_config`／`stage_models`／`skill_registry`／`edit_habits` |

首选 L2 的 `qwen_setup`／`qwen_adapter` 会触发 L2 返回契约与发布债务两条门禁（要加新登记），违背「不加新豁免」，故改为 L1／L3；架构门禁两次对比可证。

## 登记

- `维护记录/架构统一基数.json` 的 `层级`：删 14 条已不越层的项，`count`／`baseline_exempt` 35→21。剩 21 条是真实反向依赖（含 `confirm_gates`／`idea_document_paths`→`legacy_compat`）。
- `test_layers.KNOWN_DYNAMIC_UPWARD` 删 2 行（`keyframe_model_service`、`stage_models`→`workflow_settings`），5→3。
- `architecture.md`：分层表 L0～L4 各行同步，并加 R2191 说明段。
- 无新增模块，覆盖率基线不变。

## 新增测试

无。本轮是登记纠正，由既有 `test_layers`（双向棘轮：未登记越层与多余台账都红）覆盖。

## 测试

- `smoke_test.py --architecture`（经 `工作流任务\gui_hidden.py`）：412 项，剩 2 条红，与 R2184／R2189 相同且与本轮无关：`test_round_number_continuous`（状态页只在 master 更新）、`test_performance_history_is_declared_as_historical_only`（`基准历史.json` 被忽略，工作树没有）。
- 首跑（`qwen_setup`／`qwen_adapter` 登记 L2）多出 `test_service_return_contract`、`test_unification_ratchet` 两条红，改登记后转绿；断言未动。
- 未运行：`--all --safe` 全量。

## 回滚

`git revert <本轮提交>`。不涉及用户数据与配置格式。

## 下一步

J4：`workflow_settings` 提供「校验 → 取当前设置 → 冻结 SKILL」固定顺序的单一入口，`writing_api` 与 `desktop_idea_chat` 的 4 处改调它。开工前先同步 master 复核行号。
