# R3164 结果（UI 统一组件标准任务书 U0：标准先行）
<!-- round-evidence: {"commit_base": "0117ec3e", "credential_hits": 0, "evidence_sha256": "acb8decd3a80cfc4", "exit": 0, "failed": 0, "passed": 0, "round": 3164, "tests": "docs-only"} -->

- 轮次类型：文档轮（任务书《UI统一组件标准任务书.md》U0，分支 `codex/wip-R3164`）。

## 三问

1. **本轮属于 §3 哪种类型？** 文档轮（§3 未单列文档轮，按任务书 U0 声明）。只改 `ui_components.md`／`design_tokens.md`／`AGENTS.md` 并把任务书入库，不写生产 `.py`、不跑测试。
2. **测试跑了吗、三个基线过了吗？** 未跑——任务书 §5 明确「U0、U7 为文档轮，不跑」smoke／selftest。三个基线数本轮不适用（默认冒烟、架构门禁、全量均未运行；本轮无 `.py` 改动，无代码行为变化）。
3. **欠账少了吗？** 不变。本轮只建立标准与门禁名，不迁移存量；存量违规（测宽近似、emoji 占位、内联字体、自配颜色原生控件、表单控件内联样式）按任务书 D6「谁改谁迁」在 U1–U6 各门禁中冻结，本轮不提前改动。

## 本轮改动

- `tasks_round/UI统一组件标准任务书.md` 入库（自计划工作树 `dsh-4a1e53a6-6ff6` 原样复制，内容未改，本轮只把规划文档纳入版本库）。
- `ui_components.md` 在「表格」与「复用规则」之间新增 8 节：浮层与文字测宽、图标（MDL2/PNG 边界）、框体（Card/Box 分工）、发送键、字体、原生控件、表单控件、消息卡片与 HITL。每节写「入口／禁止／门禁名」。
- `design_tokens.md` 新增「图标」节（`icon.nav.size`＝24px 固定画布）与「框体（Box）」节（`color.border.strong`、直角 1px、内边距 `space.sm`）。
- `AGENTS.md` §2.5 规则 34 尾补一行指针（指向 `ui_components.md` 新增章节）；文件现 16135 字节，16 KB（16384）预算内，余 249 字节。

## U0 验收勾选

- [x] `ui_components.md` 每一节都写明入口、禁止项、对应门禁名，且门禁名与 U1–U6 实际测试文件名一致：U1 `test_text_measure_boundary.py`；U2 `test_nav_icon_size_boundary.py`；U3 `test_icon_source_boundary.py`；U5 `test_box_boundary.py`；U6 `test_font_boundary.py`／`test_native_control_boundary.py`／`test_form_control_boundary.py`。发送键无独立边界门禁，由 `test_script_composer`／`test_shared_input_ui` 锚定（U4）。
- [x] 文件卡片任务新增组件已纳入标准（消息 part 分派渲染 `ui_part_renderers`、HITL `ui_hitl`、参数面板 `ui_param_panel`、缩略图卡/Lightbox `ui_media`、引用溯源 `ui_citation`、树表行预览卡 `desktop_file_card`），其违规项已登记：`ui_hitl` 的 `ttk.Radiobutton` 与 `ui_param_panel` 的 `ttk.Scale` 归表单控件门禁存量冻结。
- [x] `AGENTS.md` 仍在 16 KB 预算内（16135 字节），新增内容只有规则 34 尾的一行指针，未展开。
- [x] REQ/DES 编号可被后续测试锚定：发送键节引用 REQ-S01-62／DES-S01-62（两者均已存在，REQ-S01-62 已由 `test_script_composer` 锚定）；DES-S01-62「发送键主色底＋Fluent PNG」的描述文字由 U4 按任务书「同步 REQ/DES 文字」更新，本轮不提前改。

## 提交

已提交（`R3164`，commit hash 以 Git 日志为准，本轮为文档轮，无 `.py` 改动故不带 `--tests`）。
