# R2935 结果：T10 包化——ui/（L4 界面组件）批次 17 模块迁移
<!-- round-evidence: {"commit_base": "52fbbbd2", "credential_hits": 0, "exit": 0, "failed": 0, "passed": 986, "round": 2935, "tests": "run_selftests.py -k pet_ui pet_cloud ui_ app_metadata button_consistency"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --architecture` 架构门禁当轮实测 **470/470 全绿**（随附解释器口径）；定向 40 个测试文件 986 条用例全绿；覆盖率基线重测 **488 模块／70 覆盖**。
3. **欠账少了吗**：是。T10 包化推进第四批：`ui/`（L4）落地 17 个低扇出模块实体＋17 个别名门面，五层包（contract/infra/domain/orchestrator/ui）全部起步。剩余 L3 模块（约 45 个）、L4 大模块（desktop/pet_ui/ui_widgets/app 等）与顶层前缀族、`app.py`/`pet_cloud.py`/`writing_api.py` 拆分仍是后续批次。

## 本轮交付

| 项 | 内容 |
|---|---|
| `ui/` 实体 | 17 个 L4 模块 `git mv` 入 `ui/`：pet_cloud（含 pet_cloud_text/geometry/shape/tail/timing/hint/place/move_guard 八个天然簇）＋ui_popup、ui_usage_detail、ui_usage_indicator、ui_tooltip、ui_splash、ui_composer_style、ui_stage_popups、ui_hover_fade。入选口径：`_layers.py` 登记 L4 且静态+动态扇出最低的簇；desktop/pet_ui/ui_widgets/app 等重消费者留待后续批次与拆分轮。 |
| 别名门面 ×17 | 顶层同名 `.py` 为 `sys.modules[__name__] = ui.<名>` 别名门面；`ui_plugin_registry.module()` 动态登记与测试扁平名补丁面不受影响。 |
| 消费方 import | 12 个生产文件改包路径导入（desktop、pet_ui 及 pet_ui_stages/view/voice、ui_widgets、production_lock_fields、ui/ 包内 5 文件）；**修正一处脚本缺陷**：`import X`→`import ui.X` 会丢绑定名，统一补 `as X`（6 文件），否则 `pet_cloud.SHAPE_CLOUD` 等属性访问 NameError——首轮定向 100+ 红的根因，修复后 986 条全绿。 |
| `__file__`/日志名 | 本批 17 模块无 `Path(__file__).parent` 根锚、无 `getLogger(__name__)`，无需修正（迁移前扫描 0 命中）。 |
| 测试路径同步 | `test_app_metadata.py`（`ui_splash.py`）、`test_button_consistency.py`（`ui_stage_popups.py`）改 `ui/<名>.py`；complexity/module_size/token/dialog/tooltip 等 basename 键登记表不改（registry_key/path.name 口径即 basename）。 |
| 棘轮台账 | `架构统一基数.json` 本批 17 模块 0 命中，无需改动。 |
| 基线与文档 | `覆盖率基线.json` 重测 **488 模块／70 覆盖**（+17 实体＋`ui/__init__.py`）；`runbook.md` §11 数字同步（470/70/400→488/70/418）；`architecture.md` 目录树加 `ui/`；`PROJECT_MAP.md` 5 处、`distribution_manifest.md` glob 同步。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `smoke_test.py --architecture`（随附解释器）：**470/470 全绿**（当轮实测，一轮过）。
- 定向：`run_selftests.py -k pet_ui pet_cloud ui_ app_metadata button_consistency` → 40 个测试文件 **986 条用例 0 红**（首轮暴露 `import ui.X` 丢绑定名，修复后复绿）。
- 导入冒烟：`ui.*` 实体、扁平门面、desktop/pet_ui/ui_widgets 重消费者全部可导入，无循环。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按 `full-safe-receipts.json` 凭据口径执行）。

## 过程损耗（如实）

- 迁移脚本 `import X`→`import ui.X` 未保留绑定名（应为 `import ui.X as X`），pet_ui 云朵链 100+ 条用例红；定位为属性访问 NameError 类问题，补 `as` 后归零。**教训**：批量改写 `import X` 必须带 `as X`，或改用 `from ui import X`。
- 上轮（R2930）教训已执行：提交后核对 `git status` 零残留，本轮提交前已确认全部改动在暂存面内。

## 下一步（T10 后续批次）

- 剩余 L3 模块（约 45 个：stage_execution_service、writing_api、skill_orchestrator、desktop_*_controller 等）与 L4 重模块（desktop、pet_ui、ui_widgets、app）逐批同法迁移；`import ui.X as X` 规则与包感知扫描器适配直接复用。
- `app.py`、`pet_cloud.py`（已入 ui/ 实体）、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
