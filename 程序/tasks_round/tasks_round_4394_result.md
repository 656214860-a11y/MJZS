# R4394 结果：UX-MODEL-PAGE 模型管理页按键契约、默认值预填与脏检查守卫
<!-- round-evidence: {"commit_base": "bd508bb19", "credential_hits": 0, "evidence_sha256": "6b59388a7456a702", "exit": 0, "failed": 0, "passed": 130, "round": 4394, "tests": "run_selftests.py -k model_pool batch7_settings_models desktop_compact_layout model_manager_actions"} -->

## 三问

1. **轮次类型**：功能轮（先改 DES 文档、再写测试、后实现；续跑接管，按 2026-11-25 总控裁决把脏检查 Mixin 与默认常量迁入既有 `ui/pet_models_tabs.py`）。
2. **测试跑了吗、三个基线过了吗**：跑了授权的两条。定向 `run_selftests.py -k model_pool batch7_settings_models desktop_compact_layout model_manager_actions`：130 条全绿（改前同口径 130 条 3 红）。`smoke_test.py --architecture`：702 项全绿。默认冒烟 8/8 基线：未运行（卡面未授权该命令，不声称）。
3. **欠账少了吗**：是。模型管理页补齐 DES《05》§15 登记的全部缺项：新建预填主流默认、底行 [取消][保存] 契约、未保存改动四类确认；pet_models_ui.py 由 1083 → 991 行（≤1000 上限内），_ModelManager 538 行（≤600）。

## 允许修改文件盘点（只读盘点清单）

| 文件 | 本轮处理 |
|---|---|
| `docs/specs/05_UIUX与交互规范.md` | +63 行：新增 §15「模型管理页按键清单」（现状盘点表、按键契约、默认值表） |
| `ui/pet_models_ui.py` | 991 行：新增表单 4 输入行、底行 [取消][保存]、脏检查改由继承 Mixin 提供 |
| `ui/pet_models_tabs.py` | 175 行：迁入 `ModelManagerFormGuardMixin` 与默认/表单常量（既有 L4 Mixin 模块） |
| `infra/model_pool.py` | 1117 行（净 0）：仅 `FIELDS` 单行追加 4 键（max_output/temperature/timeout/retries） |
| `tests/test_model_pool.py` | +26：NewModelDefaultsTests 3 条（常量经 `pet_models_tabs` 引用） |
| `tests/test_ui_batch7_settings_models.py` | +123/-8：ModelManagerUxTests 6 条＋两处按钮契约断言更新 |
| `tests/test_model_manager_actions.py` | +8/-6：3 处「关闭」断言同步为 §15.2「取消」契约 |
| `ui/desktop_model_pages.py` | 盘点后未改：模型管理页实现实际在 `ui/pet_models_ui.py` |

## 缺陷复现与先红后绿

- **缺陷**（LOST-05／UXR-04）：模型管理页输入项无主流默认、「关闭」与「保存这条」并列占主按钮位、无「保存＝写入并关闭」路径、未保存改动在切行/新建/切页签/离开时静默丢弃。
- **改前红**：本续跑首轮定向 130 条中 **3 红**，全在 `test_model_manager_actions.py`，原因一致——`AssertionError: 找不到可见按钮：关闭`（独立「关闭」按钮已按 §15.2 撤除，旧契约断言未同步）：`test_blank_form_closes_without_saving`、`test_close_with_filled_form_does_not_save`、`test_save_one_sits_after_delete_on_the_left`。
- **改后绿**：同口径 130 条全绿；条数＝改前条数（断言同步非新增）。

## 改动位置（文件:行号）

- `infra/model_pool.py:32`：`FIELDS` 单行追加 `'max_output','temperature','timeout','retries'`；总行数 1117，登记 URL 仍在 97/103/108/114/975（实测）。
- `ui/pet_models_tabs.py:12-23`：`FORM_FIELDS`、`FORM_DEFAULT_PROVIDER`、`DEFAULT_CONTEXT_LENGTH=262144`、`NEW_MODEL_DEFAULTS`（新建预填默认，DES §15.3 标「可改」）。
- `ui/pet_models_tabs.py:73-175`：`ModelManagerFormGuardMixin`——`_bind_dirty_marks`/`_mark_dirty`/`_confirm_discard`/`_restore_selection`/`on_select`/`_on_tab_changed`/`new_one`/`cancel`/`save_and_close`；`_on_tab_changed` 经 `super()` 落 `ModelManagerModeTabsMixin`（宿主把它排在 MRO 更后）。
- `ui/pet_models_ui.py:6-7`：import 增 `FORM_DEFAULT_PROVIDER/FORM_FIELDS/ModelManagerFormGuardMixin`（零新增 import 边，沿用已登记的 pet_models_ui→pet_models_tabs 边）。
- `ui/pet_models_ui.py:448`：`class _ModelManager(ModelManagerFormGuardMixin, ModelManagerModeTabsMixin)`。
- `ui/pet_models_ui.py:49-50`：窗口 1180x960、最小 820x720（表单 +2 行、底行 +1 行的净高）。
- `ui/pet_models_ui.py:538-540`：协议下拉存 `self.wire_box`（脏标记绑定对象）。
- `ui/pet_models_ui.py:559-562`：能力勾选 `command=self._mark_dirty`。
- `ui/pet_models_ui.py:568-572`：新增「最大输出/温度」「超时（秒）/重试次数」两个输入行。
- `ui/pet_models_ui.py:624`：脏绑定收敛为 `self._bind_dirty_marks()`。
- `ui/pet_models_ui.py:644-650`：底行右对齐 `[取消] [保存]`（Primary），Esc/窗口 X 同走 `cancel`；`self.new_one()` 打开即新建态预填。
- `ui/pet_models_ui.py:871-873/897-902`：`fill` 可选字段回填增 4 键、尾置 `_dirty=False`。
- `tests/test_model_pool.py:22,216-221`：常量引用 `pet_models_tabs.NEW_MODEL_DEFAULTS`。
- `tests/test_model_manager_actions.py:1,66-90`：3 处契约断言同步（见下）。

## §2.4 测试契约变更说明

DES《05》§15.2 有意变更：底行右对齐 `[取消][保存]`（保存＝写入并关闭），**不再有独立「关闭」按钮**；取消在表单脏时先确认。`test_model_manager_actions.py` 同步 3 处：① `test_save_one_sits_after_delete_on_the_left` 右侧定位键「关闭」→底行「保存」，并新增「无『关闭』按钮」断言；② `test_blank_form_closes_without_saving`、③ `test_close_with_filled_form_does_not_save` 点击「关闭」→「取消」，不保存关窗语义原样保留（程序化填入不算脏改动，取消直关）。未弱化、未删除任何其余断言。

## 按推荐执行项（卡面授权，结果单列）

- 默认值取推荐表：上下文 262144（256K）、最大输出 8192、温度 0.7、超时 120s、重试 2 次；均标「可改」，只在新态预填，已存值不覆盖。
- 按钮布局按推荐：底行右对齐 [取消][保存]（Primary 强调色），条目操作居上一行左侧，删除/检测不与保存同排。
- 未保存改动确认覆盖：切行、新建、切调用方式页签、取消/Esc/窗口 X。

## 验证记录

- `run_selftests.py -k model_pool batch7_settings_models desktop_compact_layout model_manager_actions` → **退出码 0**（尾部：`共 130 条用例，79.5 秒；0 个文件有红` / `ALL TESTS PASSED`）。
- `smoke_test.py --architecture` → **退出码 0**（尾部：`Ran 702 tests in 269.634s` / `OK` / `✅ 架构治理测试：tests/architecture`）。

## 未验证项

- `smoke_test.py`（默认冒烟 8/8）与 `smoke_test.py --affected`：未运行（卡面验收只授权上述两条命令）。
- `run_selftests.py --all --safe` 全量：未跑（分支轮不命中 §5 触发条件）。
- 检测按钮真实联网：按卡面约定走桩，未真发请求；UI 为三档宽度几何断言，非人工目视。

## 卡外发现（只记录）

- 定向跑期间跨树 GUI 令牌被其他车道占用（`[GUI_WAIT]` 排队约 30–60s），未影响结果。
- `ModelManagerFormGuardMixin._on_tab_changed` 依赖宿主把 `ModelManagerModeTabsMixin` 排在 MRO 更后（super 落点），已在 Mixin docstring 写明。
