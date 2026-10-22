# R1885 结果：设计 token 剩余两项——元组间距与 width/height/wraplength 迁到刻度（修复轮）

接 R1878。用户 2026-10-22 指示「修复剩余 2 项后提交」。

## 改动
- `ui_tokens.py` 新增三组刻度：`CHAR_WIDTH`（控件字符宽 4–16 档＋输入框 48/64/80）、`TEXT_ROWS`（文本区/表格行数 2–20 共 8 档）、`WRAPLENGTH`（折行宽 480–960，每档 80px）。
- 40 个生产文件迁移（ui_tokens 除外），吸附规则：
  - 元组间距 110 个数字元素 → `SPACING`，规则同 R1878（0/1→none，2–6→xs，7/8/10→sm，12/14→md，18→lg）；
  - 文本区/表格/Treeview/Listbox 的 `height` → `TEXT_ROWS`，就近、平局取大；
  - 按钮/输入/下拉/Spinbox/Label/TextArea 的 `width` → `CHAR_WIDTH`，就近、平局取大（避免裁字）；
  - `wraplength` → `WRAPLENGTH` 向下取档（保证不超出原容器）；
  - 其余像素尺寸（表格列宽、缩略画布、FlowBar 初始高）→ `SPACING['sm'] * n`，四舍五入到 8px 网格。
- 登记豁免（保留在 LAYOUT_NUMBER_BASELINE）：`pet_ui_support.py` 13／`pet_ui_view.py` 1 为宠物插画画布描边宽度；`comfy_service.py` 2 为 ComfyUI 生成分辨率 768（请求参数，不是控件）。
- `tests/architecture/test_token_boundary.py`：`numeric_padding_count` 起算元组元素（门禁变严）；PADDING_BASELINE 仍为空；LAYOUT_NUMBER_BASELINE 132→16（仅豁免）；新增 2 条元组 canary。既有断言未动。

## 可见变化（未实机截图核对）
折行宽多数收窄 10–60px（如 700→640、500→480），可能多折一行；表格/文本区行数 ±1–2 行（如项目列表 3→4 行、13→12 行）；部分按钮宽 11→12 字符、Spinbox 5→6；1px 间距变 0。

## 验证（本轮实测）
- 架构 `smoke_test.py --architecture` 394 条：391 过。3 红均与改动无关：两条缺未入库文件（`维护记录/基准历史.json`、skills 参考文档，worktree 无）；`test_round_number_continuous` 因状态页轮次头 1874 而结果文件已到 R1878/R1885——状态页只许 master 改，合入时同步即消。
- 定向 `run_selftests.py -k`（40 个改动模块名＋desktop/skill_panel/ui_tokens/ui_widgets）411 条：首跑 5 文件红——
  - `test_reference_wall_equivalence`／`test_keyframe_comfy_window_equivalence`／`test_storyboard_files_equivalence`：重构等价测试内嵌的 HEAD 旧实现（LEGACY 字符串）仍是旧字面量；契约有意变更，按同一吸附规则同步 LEGACY（共 13 处），**断言未动**，复跑 4/4、0 红；
  - `test_desktop_compact_layout`（侧栏间隙 5>4）与 `test_skill_panel_dropdown_layout`：在干净 HEAD 临时工作树同样红，为既有环境性红，非本轮引入。
- 全量未跑。

## 合入说明
变基到 master：R1867 已删除三个 *_equivalence 差分测试（独占覆盖为 0），上文所述 LEGACY 同步随之作废；R1868 已做完的间距部分冲突取 master。
