# R1647 修复轮：P1-2 越层豁免收口起步（37→35，两条只比事实的依赖消失）

- **本轮类型**：§3.2 修复轮（源码＋分层登记＋台账＋文档；不改契约、不搬目录、不重命名、不删既有文件）。
- **测试与三个基线**：默认冒烟 **8/8**；行尾＋轮次基线 **21/21**（含 `test_round_baselines`）；架构门禁 **357/357（265.0 秒，本轮实测）**；定向 12 模块 **142/142**（`test_layers`／`test_unification_ratchet`／`test_coverage_baseline`／`test_asset_batch_settings_boundary`／`test_stage_model_value`／`test_asset_batch_settings_service`／`test_project_context`／`test_storyboard_adoption_service`／`test_storyboard_final_selection`／`test_assets`／`test_agents_md`／`test_round_baselines`）＋`tests.test_ui_edges.UiEdgeTests.test_unattended_labels_show_the_current_model` 单条。**未跑全量**（改源码轮，欠账未到门禁线 8）。
- **欠账**：改源码 → 全量欠账 **3/8 → 4/8**（改前实测 `--status`：间改过源码的轮次 3、门禁线 8、后台触发 False）。
- **清单依据**：`tasks_round/tasks_round_1645_result.md` J 节 P1-2（“豁免顶到基数上限且无收口路径”，最小闭环＝按 importer 分组择一并开工，先 `asset_batch_service`）。
- **指令冲突记录**：本会话顶部重新下发的提示描述的是「结构治理轮（只读诊断）」，该诊断已由 R1645 交付；当前 active 目标为按顺序完成 `tasks_round_1645_result.md` 清单。本轮按目标执行清单第二项（修复轮），除清单项与必要的台账／门禁同步外未扩大写入范围。

## A 改动

1. `程序/production_model_contract.py`（L0）：**新增** `ASSET_LOCAL_MODEL`／`ASSET_CLOUD_MODELS`；模块说明补 `asset batches`。理由与本模块既有 `LOCAL_KEYFRAME_MODEL` 同口径——「被两处比较的事实放 L0，调用方不必互相 import 只为比一个字符串」。
2. `程序/cloud_assets.py:6,10-13`（L4）：`LOCAL`／`MODELS` 改由 L0 常量派生并**按原名字转发**；`NODE_TYPES`／`LIMITS` 改为用同一份 `ASSET_CLOUD_MODELS` 生成（键不再与常量各写一份）。实测取值逐字不变（见 C）。
3. `程序/asset_batch_service.py:342,348,355`（L2）：`current_model()` 改 `from production_model_contract import ASSET_CLOUD_MODELS, ASSET_LOCAL_MODEL`，不再 import L4 `cloud_assets`。
4. `程序/tests/architecture/_layers.py`：`stage_model_value` 由 L3 改登记为 **L1**（并加一行理由注释）。依据：该模块共 17 行，自述「无编排依赖的项目阶段模型只读访问」，实际只依赖 `file_cache`（L1）与 `pet_bus`（L0），无 Tk、无编排状态；原 L3 登记是按名字后缀分层（`_layers.py` 自身注释禁止的做法）。L1 而非 L2：登进 L2 会命中 `test_every_registered_l2_module_has_a_scope_record`（L2 名册与 `架构统一基数.json.第一项` 完全相等），会把它错误地拖进 `service_contract` 四字段采用方范围。
5. `程序/维护记录/架构统一基数.json`：`层级.items` **37→35**、`count`／`baseline_exempt` 同步 **37→35**；移除的两条＝`asset_batch_service.py` 的 `cloud_assets` 与 `stage_model_value`；其余 35 条 `disposition` 仍全 `exempt`、`reason` 仍为「既存越层，待专项收口」。**未新开任何豁免**。
6. `程序/architecture.md` §3：新增 R1647 段说明两条收口、机制与剩余路径。
7. **放弃并入本轮的一条**（如实登记）：曾实现把 `project_settings.read_prefs` 下沉到新 L1 模块 `settings_prefs`（可一次消掉 4 条 `→ project_settings` 越层），实测发现**新增顶层生产模块会同时触发 `tests/architecture/test_coverage_baseline.py` 的模块口径门禁（工具报 282 ≠ 基线 281）**，按门禁要求必须重跑覆盖率工具刷新 `维护记录/覆盖率基线.json`，并连带 `覆盖率审计`／状态页的口径数字（属 P2-5 明示的高成本项）。故本轮**整体回退**该改动（`settings_prefs.py` 已删除、5 处调用点已还原 `project_settings`），把它记为下一批的前置条件。

## B 验证（本轮实测）

- 扫描口径复核：`_upward_pairs()` 与台账集合 **完全相等（35=35）**，差额为空（同时消掉 P2-8 里「42 vs 37」在本轮的可复核面：改用门禁同一 `_scan.import_rows()`／`production_files()` 复算后两侧一致）。
- 取值不变量：`cloud_assets.LOCAL`／`MODELS`／`NODE_TYPES`／`LIMITS` 与改前字面量逐一相等（脚本断言，非人工比对）。
- 关键命令与结果：
  - `python -B -m unittest tests.architecture.test_layers …tests.test_assets`（12 模块）→ `Ran 142 tests` `OK`。
  - `python -B smoke_test.py` → `通过：8 项 / 失败：0 项`。
  - `python -B smoke_test.py --architecture` → `Ran 357 tests in 265.013s` `OK`（改前 357；本轮未增删用例）。
  - `tests.test_ui_edges.UiEdgeTests.test_unattended_labels_show_the_current_model` → `OK`（0.09 秒，直接盯着 `current_model` 与文案）。
- **失败并纠正的记录**：首次架构门禁出现 3 红（`test_asset_batch_settings_boundary` 旧口径断言 `('project_settings','read_prefs')`、`test_coverage_baseline` 两条模块口径 282≠281），全部由「`settings_prefs` 新模块」引起；按 C2 回退后复跑全绿。此红未修门禁、未调低限值，而是回退了引起口径变化的方案。
- **失败并记录的口径**：`smoke_test.py --affected cloud_assets asset_batch_service …` 在本机 900 秒超时（别名展开的面远大于预期，非失败），故改用具名 unittest 模块与单条用例取值，未把它当作红。

## C 完成判据对照（P1-2 原文）

| 判据 | 结果 |
| --- | --- |
| `层级.items` 行数下降 | ✅ 37 → 35 |
| `baseline_exempt` 同步下调 | ✅ 37 → 35 |
| 门禁 `test_layer_exemptions_are_a_locatable_nonincreasing_baseline` 绿 | ✅（`test_layers` 4 条全绿；断言「扫描结果与台账完全相等」亦绿） |
| 台账 `reason` 仍可定位 | ✅ 35 条全为 `exempt`＋「既存越层，待专项收口」 |

## D 未做与局限

- `asset_batch_service` 仍有 3 条越层（`asset_prompt_rules`／`asset_reference_prompts`／`asset_reference_images` 的 `positive`／`issues`／`display_prompt`／`reference_instruction`／`signature`）：它们是纯取值／纯文本函数，收口＝把函数下沉到更低一层并在原模块保留同名转发；`signature` 还需一并处理其依赖的 `resolve`／`image_bytes`（文件读取），比本轮两条大。**下一批应作为一整组的首选**。
- 未动其余 32 条越层；未跑全量；未实机、未联网；未更新接力文件与状态页正文（仅同步轮次头）。
- 本轮未能收敛的一处**新发现**（只登记不处理）：`project_settings.confirm_unattended` 在整仓生产代码中**没有任何调用点**（递归检索仅命中定义与该模块自身），仅被 `tests/test_ui_edges.py:277` 打桩；它也是 `project_settings` 唯一把该模块钉在 L4 的 UI 依赖。若确认无调用方，删除它即可让 `project_settings` 降层并一次消掉 5 条 `→ project_settings` 越层——但「是否死代码」须另立只读核查轮，本轮不据此改代码。
- 提交：按 §2.6 一次性 `git add`＋`git commit`，提交信息以 `R1647: ` 开头；hash 见 `git log`（本文写入时尚未提交）。