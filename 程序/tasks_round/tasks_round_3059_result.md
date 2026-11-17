# R3059 结果：T10 包化——ui/（L4 界面层）第一批 20 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "029c133d", "credential_hits": 0, "evidence_sha256": "67a82d8b5e9ec13a", "exit": 0, "failed": 0, "passed": 188, "round": 3059, "tests": "run_selftests.py -k script_find script_line script_outline script_reading script_view project_settings_dialog prompt_window qwen_setup edit_habits tts_settings seedream version_picker workflow_settings_dialog writing_page shared_video storyboard_table storyboard_source pet_models_tabs pet_ui_popup previs_progress ui_edges"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿（一次通过）；`run_selftests.py -k <关键词组>` 14 个测试文件（首轮 test_ui_edges_guards 3 红已修，复测该文件 8/8 绿）；`smoke_test.py --architecture` 架构门禁 471 项复测；覆盖率基线重测 630 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化 **ui/ L4 首批**：`ui/` 实体由 17 → 37 个。L4 顶层剩余约 101 个实体继续分批；L3 仅剩 `writing_api`（拆分批）、`stage_execution_service`（扇出 50 单独一轮）、`image_agent_runner`（子进程入口永久除外）；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `ui/` 实体 | 20 个低扇出（0–9，合计 27 条消费边）顶层 L4 模块 `git mv` 入 `ui/`：script_find_bar、script_line_numbers、script_outline、script_reading、script_view_style（剧本阅读套件）、project_settings_dialog、prompt_window、qwen_setup_dialog、edit_habits_dialog、tts_settings、seedream_settings、version_picker、workflow_settings_dialog、writing_page_controller、shared_video_controls、storyboard_table_ui、storyboard_source_selector、pet_models_tabs、pet_ui_popup、previs_progress。全员 `__file__`/`__main__` 复查为零锚点。 |
| 别名门面 ×20 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = ui.<名>` 别名门面；20/20 `import <扁平名> is import ui.<名>` 实体同一校验全过。 |
| 消费方 import | 19 个生产文件改包路径导入（`import X` → `import ui.X as X`、`from X import` → `from ui.X import`、引号动态串 → `'ui.*'`）；批内 3 条同批边手工修（script_outline→script_view_style、script_reading→script_outline/script_view_style、workflow_settings_dialog→qwen_setup_dialog 含 `__import__` 动态串）；AST 复扫残留 **0 处**。逻辑零改动，仅 import 行。 |
| 测试取径 ×10 | 功能/边界测试改 `entity_file()` 取径：`test_copy_entry_boundary`、`test_dialog_boundary`（×2）、`test_json_io_boundary`（prompt_window/tts_settings/previs_progress/qwen_setup_dialog）；`test_ui_edges_guards.program_sources()` 改 `entity_file(p.stem)` 解析实体——**同时治愈 R3055 起潜伏的 engine.py 失配**（engine 门面无 PREDICATE 导致断言必败，本批 -k 首次跑到该文件才暴露）；UI 边界族 6 文件（button/card/data_table/shortcut_registry/text_component/dialog）`parse(ROOT / name)` → `parse(entity_file(stem))`——首轮 --architecture 13 红（12F+1E）全为门面误读，修复后 73 条复测全绿。 |
| 断言兼容 ×3 | `test_ui_edges_guards` 三处按包路径双拼写先例修：`from prompt_window import show` → `prompt_window import show` 子串（兼容 `ui.` 前缀）；`from engine import` 正则 ×2 → `(?:orchestrator\.)?engine`；`sys.modules['workflow_settings']` 桩 → `'orchestrator.workflow_settings'`（lazy import 解析包键，扁平桩打不中实体——断言语义不变：仍是「坏模块回退空串」）。 |
| 棘轮台账 | `架构统一基数.json` 本批 20 模块零命中；`_layers.py` 扁平登记名天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **630 模块／74 覆盖**（610+20）；`runbook.md` §11 同步（630/74/556）；`architecture.md` ui 目录树「首批 17 个」→「两批共 37 个」；`distribution_manifest.md` `程序/ui/**` glob 已覆盖；`PROJECT_MAP.md` 剧本阅读四件套路径改 `ui/` 前缀。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过（一次通过；smoke_test.py 无本批模块源路径检查项）。
- `run_selftests.py -k <20 模块名＋ui_edges>`：14 个测试文件首轮 test_ui_edges_guards 3 红（import 字符串断言＋sys.modules 桩键，见上），修复后该文件单独复测 **8/8 绿**；其余 13 文件首轮全绿（GUI 段经跨队列排队，部分用例因跨树令牌等待未在本轮窗口内跑完，以 dev.py commit 证据跑为准）。
- `smoke_test.py --architecture`：首轮 471 项中 **13 红**（12F+1E）——UI 边界族 6 个测试文件仍 `parse(ROOT / '<模块>.py')` 直读顶层门面（button×5、card×4、data_table×1、shortcut_registry×1、text_component×1、dialog×1），全部改 `entity_file()` 取径后 73 条复测全绿；二轮全量复测 **471/471 全绿（215.0s）**。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）。
- 未跑：`--all --safe` 全量；`distribution_build --verify`（同前批口径）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3059**；新建 `codex/wip-R3059` 分支叠加在 `codex/wip-R3058`（029c133d）之上承接本批。
- **潜伏断言暴露**：test_ui_edges_guards 自 R3055（engine 迁 orchestrator/）起即带失配断言，但此前各批 -k 关键词未命中该文件名，直到本批 -k 含 `ui_edges` 才首次执行——**教训：迁移轮的 -k 应主动纳入源码守卫类测试文件名（guards/edges/boundary）**。
- **sys.modules 桩键漂移**：测试用扁平名桩替模拟坏模块，包路径 lazy import 解析 `orchestrator.*` 键导致桩失效；已改桩键并复测。同类模式已全库 grep 排查，本批范围内无其他扁平桩点。
- **GUI 令牌争用**：跨树令牌被其他车道长占（单次 379–651 秒），部分 GUI 用例排队超时未在本轮窗口内完成；非本批回归，dev.py commit 证据跑将复验。

## 下一步（T10 后续批次）

- L4 剩余约 101 个顶层实体继续分批（desktop_* 页面族、pet_ui_*、ui_widgets/ui_theme 等共享件、asset_*、storyboard_*、pet_agent 系）；`app.py`/`desktop.py`/`pet_cloud.py`/`writing_api.py` 拆分方案批次。
- L3 收官：`stage_execution_service`（扇出 50）单独一轮；`writing_api` 随拆分；`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
