# R4428：FIX-SEND-AFFECTED-REDS 修复（resolve_for_send 非绝对桩兼容＋三处既有回归对齐）
<!-- round-evidence: {"commit_base": "02ec82451", "credential_hits": 0, "evidence_sha256": "e50f160165404478", "exit": 0, "failed": 0, "passed": 270, "round": 4428, "tests": "run_selftests.py -k flow_agent_launch skill_budget_send_entries test_skills login_gate video_ui"} -->

轮次类型：修复轮（§3.2）。测试跑了（先红后绿）；三个基线：默认冒烟 8/8 未跑（卡面未授权该命令）；架构门禁当轮实测 708 条、0 红；全量回归未跑（卡面禁全量）。欠账：无新增。

## 改动文件（本批全部清单）

- `orchestrator/workflow_settings.py`（`resolve_for_send` 引擎缺失判定收窄）
- `tests/test_skills.py`（`RouterTests.test_select_falls_back_then_gives_up_with_a_reason` 断言对齐 REL-03）
- `tests/test_skill_budget_send_entries.py`（`command_to_frozen` 补两个桩，走通原 CLI 冻结链）
- `tests/test_video_ui.py`（返回钮像素断言对齐 UX-THEME-SIMPLE 重染色契约）
- `tasks_round/tasks_round_4428_result.md`（本文件）

## 缺陷复现方式与改前红

定向命令（原样）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k flow_agent_launch skill_budget_send_entries test_skills login_gate video_ui`

改前基线 `02ec82451`（工作树 `codex/fix-send-affected-reds`，已含 R4427）：共 270 条用例，4 个文件有红，合计 7 条：

- `test_flow_agent_launch` 1 红：`test_full_auto_tells_the_user_to_send_in_claude_desktop`——`workflow_settings.find_program` 被打桩返回相对名 `'Claude.exe'`，REL-03 引入的 `Path(str(find_program(config))).is_file()` 对相对名恒 False，`resolve_for_send` 误判引擎缺失抛 `missing_setup_hint`（`workflow_settings.py:851` → `desktop_idea_chat.py:749`）。
- `test_skill_budget_send_entries` 4 红（`test_cli_raw_engine_command_reaches_qwen_task_with_explicit_128k`、`test_cli_unknown_window_still_delivers_complete_task`、`test_cli_unknown_window_keeps_character_hard_limit`、`test_cli_huge_bodies_stop_before_launch`）：夹具把 `infra.model_pool.pool` 打桩为 API 记录后，UX-B2API（REQ-S01-118）合入的 `_send_skill → send_skill_request`（`desktop_shared_send.py:764-767`）取到非空 `request_model['id']`，去取 `desktop.idea_chat_controller` 报 `AttributeError: 'types.SimpleNamespace' object has no attribute 'idea_chat_controller'`，原 CLI 冻结链根本没走到。
- `test_skills` 1 红：`test_select_falls_back_then_gives_up_with_a_reason`——断言 `'没有可用模型' in choice.reason`，REL-03（R4412）已把无可用模型的统一提示改为 `model_router.missing_setup_hint()`（`infra/model_router.py:689,936`），旧串不再出现。
- `test_video_ui` 1 红：`test_the_way_back_to_the_choose_page_still_works`——像素实测 `(15, 20, 25)`（`text_primary` 日间色），断言仍是旧 `COLORS['primary']` `(15, 111, 192)`。

## 改动点（文件:行号）

- `orchestrator/workflow_settings.py:846-848`：先 `program = str(find_program(config) or '').strip()`；`not program` 判缺失；仅当显式填写 `config.get('program')` 或 `Path(program).is_absolute()` 时才查 `Path(program).is_file()`——相对名自动探测结果不再误判缺失，显式配置与绝对路径的缺失检查原样保留。文件总行数 997 ≤ 998。
- `tests/test_skill_budget_send_entries.py:124-125`：`command_to_frozen` 的 `with` 内补 `patch('writing_api.capture_request_model', return_value={'id': ''})`（让 `send_skill_request` 在 `desktop_shared_send.py:765` 处返回 False 回落原链）与 `patch('ui.desktop_direct_dispatch.dispatch', return_value=False)`（让 `_FlowAgentLaunch.build` 在 `desktop_idea_chat.py:750-751` 不被 API 直连分流截走），完整走通原 CLI 冻结链；预算断言一律未动。
- `tests/test_skills.py:581`：`assertIn('没有可用模型', ...)` → `assertEqual(choice.reason, model_router.missing_setup_hint())`。
- `tests/test_video_ui.py:1121`：`COLORS['primary']` → `COLORS['text_primary']`；下方 WCAG 对比度 ≥3 断言原样未动。

## 改后输出（尾部原文）

定向：`共 270 条用例，32.3 秒；0 个文件有红 … ALL TESTS PASSED`，退出码 0。
架构门禁：`Ran 708 tests in 218.537s / ✅ 架构治理测试：tests/architecture / OK`，退出码 0。

## 契约变更注明

- `tests/test_skills.py:581`：依据 REL-03（R4412）——无可用模型提示已统一为 `model_router.missing_setup_hint()`，断言同步为同一权威函数返回值，未放宽。
- `tests/test_video_ui.py:1121`：依据 UX-THEME-SIMPLE（R4378，提交 `5a999bfc`）——`ui/ui_icons.py:_nav_image` 对 `assets/nav/*.png` 的统一重染色已改 `COLORS['text_primary']`（日间 #0F1419，适配日夜间主题），断言同步新契约色，WCAG ≥3 断言保留。
- `tests/test_skill_budget_send_entries.py`：仅补桩恢复 UX-B2API 前的 CLI 原链测试路径，未改任何预算/冻结断言。
- `orchestrator/workflow_settings.py`：`resolve_for_send` 行为收窄（相对名探测结果不再当缺失），公开签名未变。

## 三个基线数

- 默认冒烟基线：8/8——未跑（卡面未授权该命令），未核实当前值。
- 架构门禁：当轮实测 708 条，0 红，退出码 0。
- 全量回归/欠账：未跑全量（卡面禁全量）；`full-safe-receipts.json` 未核实。

## 未验证项

- `resolve_for_send` 收窄后「显式 `program` 为相对路径但确实缺失」的场景：`validate_profile`（`workflow_settings.py:229-233`）已要求显式 program 必须是绝对 .exe 且存在，正常入口到不了相对显式值；该边角未单独构造用例。
- `find_program` 返回空串/None 的缺失分支（`not program`）无专项新用例，沿用既有 `missing_setup_hint` 抛出路径。
- 定向之外的其它测试文件未跑（卡面限定 `-k` 清单）；是否波及未在清单内的消费者未核实——`resolve_for_send` 的其它调用方行为差异仅限「相对名探测结果不再误报缺失」，方向是放宽误报而非收紧。

## git diff --numstat（提交前原文）

```
3	1	程序/orchestrator/workflow_settings.py
3	1	程序/tests/test_skill_budget_send_entries.py
1	1	程序/tests/test_skills.py
1	1	程序/tests/test_video_ui.py
```

提交哈希：（提交后补记）
