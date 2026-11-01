# R1506 结构治理轮：拆分 pet_ui.py（Pet 类按主题迁入 4 个 Mixin）

1. **本轮类型？** 结构治理轮（只搬代码，不改逻辑）。
2. **测试与基线？** 默认冒烟 8/8；架构门禁全绿（首次 5 项红，均为“被检代码换了文件／按文件的基线”，处理见下，断言未动）；pet／app_metadata／line_endings／tier／model／budget 等相关自检 1185 条首次 2 个文件红（读 `pet_ui.py` 源码的 `test_pet_test_service`、按文件登记显示源的 `test_app_metadata`），已处理；全量与干净检出验证见提交后记录。
3. **是否欠账？** 改了层级登记表（风险路径），须全量转绿。

## 改动

`pet_ui.py` 4832 → **915 行**（`Pet` 类原 3894 行／230 个方法）。方法体未改、`self` 语义不变，`Pet` 继承 4 个 L4 Mixin：

| 模块 | 内容 | 方法数／行数 |
|---|---|---|
| `pet_ui_stages.PetStagesMixin` | 阶段推进、自动流程、一键制作、恢复与付费确认 | 58／约 1180 |
| `pet_ui_settings.PetSettingsMixin` | 模型、档位、预算、勿扰、开机自启等设置 | 33／约 350 |
| `pet_ui_voice.PetVoiceMixin` | 播报、气泡、问候、报告、对话与项目概览 | 66／约 1120 |
| `pet_ui_view.PetViewMixin` | 窗口绘制、动画、菜单、爪子、点击与弹出 | 58／约 680 |
| `pet_ui_support` | 上述方法用到的模块级常量、辅助函数与小类（104 个名字，含 `GearButton／Cat／StageQueue／Autostart` 等） | 约 580 |

- 用 AST 脚本批量完成：迁出方法用到的模块级名字逐个解析，外部导入原样导入，模块级定义连同其依赖闭包迁入 `pet_ui_support`，`pet_ui` 重新导入，所有旧的 `pet_ui.<名字>` 引用不变；新模块无导入环、无未使用导入。
- **留在 `pet_ui.py` 的 5 个方法**（`register_model／set_tier／tier_config／tier_name／_fill_model_menu`）：测试会直接改写 `pet_ui.TIER_NAMES／TIER_CYCLE`，`register_tier` 也用 `global` 改写它们（还有 `TIER_MODELS／tier_models`），迁走会让改写对不上，所以这几个名字与用到它们的方法一起留下。
- 剩余的 `pet_ui.py`：`Pet` 的构造与核心访问器（`__init__／client／core／bus／machine／agent／snapshot／pump／click`）、档位注册表与 5 个相关方法，以及启动入口函数（`attach／watch_status／start`）。

## 门禁与测试的调整（断言未动）

- `_layers.py` 登记 5 个新模块（L4）；`test_module_size_ratchet` 把 `pet_ui.py` 从超限登记表删除（已不超限）；`test_token_boundary`：`pet_ui.py` 的 45 处内联 hex 按迁出位置记为 `pet_ui.py` 1 + `pet_ui_support.py` 44（合计不增）；`test_event_bus_boundary`：播报调用方集合加入 `pet_ui_voice.py`；`test_stage_display_boundary`：分镜阶段播报标签在 `pet_ui_voice.py`；`legacy_compat` 的兼容登记里 `optional_asset_counts` 的调用方改为 `pet_ui_support`（`test_legacy_facade_manifest` 要求登记与生产引用一致）；TODO 注释快照按原分类更新。
- `test_pet_test_service`（2）改读 `_scan.pet_ui_text()`（合并 Pet 全部来源）；`test_app_metadata`：显示名检查的来源由 `pet_ui.py` 改为实际使用 `APP_NAME` 的 `pet_ui_settings.py`，两个历史标识符常量（`AUTOSTART_NAME`、`启动…pyw`）随模块级迁到 `pet_ui_support.py`，该文件加入“旧名字面量只允许标识符”的检查。
- `architecture.md`、`PROJECT_MAP.md` 同步。

## 提交

已提交，见 git log 标题 `R1506:`。
