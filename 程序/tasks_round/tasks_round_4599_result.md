# R4599 轮次结果（S04-W3：新建 S04 页顶工具条与右栏镜头检查器模块及架构登记）
<!-- round-evidence: {"commit_base": "7ff41edb1", "credential_hits": 0, "evidence_sha256": "1e16d5a3c2796575", "exit": 0, "failed": 0, "passed": 186, "round": 4599, "tests": "run_selftests.py -k animatic_page animatic_timeline copy_rules layer_relations button_boundary ui_icons_boundary dialog_boundary module_size_ratchet coverage_baseline complexity_ratchet"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（执行《分镜预演工作台与管理预览审核改造任务书》卡 `S04-W3`，落地 `REQ-S04-116` L4 组件层与 `DES-S04-39` 拆分登记，并联动压平 `animatic_timeline.filter_shots` 嵌套深度以通过复杂度棘轮门禁）。
- **测试跑了吗、三个基线过了吗**：已运行——覆盖率基线重测 19 组定向目标 239/239 通过（73.14s，`modules_total=707`、`modules_covered=187`）；隐藏桌面 `tests.test_animatic_page` 86/86 通过（34.56s）；16 组架构／文案／静态门禁（`test_copy_rules`、`test_layer_relations`、`test_button_boundary`、`test_ui_icons_boundary`、`test_dialog_boundary`、`test_module_size_ratchet`、`test_coverage_baseline`、`test_complexity_ratchet`、`test_token_boundary`、`test_font_boundary`、`test_function_size_ratchet`、`test_layers`、`test_agent_doc_budget`、`test_agents_md`、`test_static_names`、`test_static_hygiene`）全部通过；默认冒烟 `smoke_test.py` 9/9 通过；全量安全回归留待任务书收尾／合并轮按口径执行。
- **欠账少了吗**：新增两枚 L4 模块均严守 ≤1000 行（197/257 行）、零弹窗、零裸按钮、零手写 `tk.PhotoImage`、零魔法像素/hex 常量；同层边与覆盖率基线及 `runbook.md` §11 同步登记完毕；顺手消除了 `animatic_timeline.py::filter_shots` 的 AST 嵌套超限（7→≤2），零新增欠账。

## 改动清单

- `程序/ui/animatic_toolbar.py`（新建，197 行 ≤260）：
  - 实现 `build_toolbar`、`refresh_toolbar`、`build_audio_menu`、`apply_audio_action`。
  - 严格固定 5 个顶级交互控件：主按钮（无视频「生成分镜预演」／有视频「重新合成」）、草图引擎 `SelectBox`（默认 `text_card`，即选即经 `publish_desktop_preferences` 落盘）、「声音 ▾」`SecondaryButton`（弹出含 5 项动作＋分隔线的 `ContextMenu`：导入整轨配音…、导入背景音乐…、逐镜临时 TTS 开关、移除整轨配音、移除背景音乐）、「在剪映中打开」（常驻可见，无视频时仅写状态栏）、「预演设置」。
- `程序/ui/animatic_inspector.py`（新建，257 行 ≤380）：
  - 实现 `REVIEW_LABELS`、`review_label`、`build_inspector`、`render_inspector`。
  - 渲染当前选中镜头的大图预览（经 `ui.asset_thumbs.thumbnail`）、版本号 `SelectBox`、元信息行（场次／镜号／景别／运镜／时长／角色／场景／批注）、带来源徽章（`[S05 资产]`／`[角色]`／`[场景]`／`[风格]`／`[未分类]`）的命中参考图列表、「导入参考图…」「打开草图目录」快捷按钮、5 项单镜快捷操作（改时长／重做／换图／试听对白／批注）及「待审／通过／需修改」三态审核高亮按钮。
- `程序/ui/animatic_prefs_bar.py`（213 行）：默认草图引擎回退改为 `'text_card'`，同步新增「逐镜临时 TTS」开关并写入 `animatic_use_tts`。
- `程序/domain/animatic_timeline.py`：拆出 `_matches_scene` 与 `_matches_status`，压平 `filter_shots` 嵌套深度（7→≤2）以满足 `test_complexity_ratchet`（`test_animatic_timeline` 27/27 全绿，行为等价）。
- `程序/tests/architecture/_layers.py`：在 `_register(4, ...)` 追加 `animatic_toolbar`、`animatic_inspector`，并在 `SAME_LAYER_EDGES` 登记全部单向同层依赖边（含 W4 将使用的 `animatic_page -> animatic_toolbar/animatic_inspector`）。
- `程序/维护记录/覆盖率基线.json` 与 `程序/runbook.md`（§11）：运行 `scripts/coverage_report.py`（沿用既有 19 组定向目标）刷新生产运行时模块总数 705→707，并同步 `runbook.md` §11 口径数字（707 / 187 / 520）。
- `程序/tests/test_animatic_page.py`：`SourceBoundaryTests` 覆盖新建两模块；新增 `ToolbarAndInspectorTests`（3 条，锚定 `REQ-S04-116`）。

## 先红后绿证据

新建两模块前先更新 `tests/test_animatic_page.py` 并运行 `SourceBoundaryTests` 与 `ToolbarAndInspectorTests`，实测 **Ran 4 tests in 0.641s, FAILED (failures=1, errors=3)**：
- `test_module_has_no_forbidden_calls`：`ModuleNotFoundError: No module named 'ui.animatic_inspector'`
- `test_req_s04_116_toolbar_five_controls_engine_save_audio_menu_and_jianying`：`ModuleNotFoundError: No module named 'ui.animatic_toolbar'`
- `test_req_s04_116_inspector_renders_large_preview_badges_actions_and_review`：`ModuleNotFoundError: No module named 'ui.animatic_inspector'`
- `test_req_s04_116_prefs_bar_defaults_to_text_card_and_toggles_tts`：`AssertionError: unexpectedly None : 偏好条应提供逐镜临时 TTS 开关`

实现并登记后，`test_animatic_page` 86/86 全绿，16 组架构／文案／静态门禁全绿，默认冒烟 9/9 全绿。

## 提交状态

- 工作树：`D:\漫剧制作助手\.agents\worktrees\s04-workbench-spec`
- 分支：`codex/s04-workbench-spec`（未 `git push`）
- 提交方式：经 `scripts/dev.py commit` 提交。
