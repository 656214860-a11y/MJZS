# R4200 结果：S01 阶段文档补「示例气泡」需求与设计条目（纯文档轮）
<!-- round-evidence: {"commit_base": "6e687b94", "credential_hits": 0, "evidence_sha256": "868bf76ae7f0e0ff", "exit": 0, "failed": 0, "passed": 0, "round": 4200, "tests": "docs-only"} -->

## 开头三问

- （一）本轮属于哪种类型：功能轮·文档补登（§3.1／§2.7）。只改两份文档＋本结果文件，不改任何 `.py`／测试／配置。车道 `codex/ux-example-locks`，工作树 `.agents/worktrees/ux-example-locks`，基准 `6e687b94`。队列项 UX-C5D（波次 W2）：示例气泡功能已在主干（UX-C5 一线），本卡只补 S01 阶段文档的 REQ／DES 条目并在追溯表登记。
- （二）测试跑了吗、三个基线：跑了卡面指定的定向文档门禁，34 条用例全绿（见「命令与退出码」）。未跑默认冒烟、`smoke_test.py --architecture`、全量自测——纯文档轮按卡面不跑。
- （三）欠账少了吗：无新增欠账。REQ-S01-110 标 🟡 而非 ✅：`test_requirement_traceability` 要求 ✅ 需求在测试里有 `REQ-S01-110` 锚点，本卡不许改测试、现有行为测试均未挂本编号，故按 REQ-S01-98 先例标 🟡 并在条内注明「行为已有测试覆盖但未挂本编号锚点，待复核」。未动门禁阈值、基线与登记表。

## 改了哪些条目

- `docs/stages/S01_剧本准备.md`：
  - `### 输入` 末尾新增 **REQ-S01-110**（🟡）：软件示例气泡的用户可见契约——无聊天记录时显示、内容为随程序打包的 `默认创意示例.md`、只读灰泡不折叠不走排版、右键只给「复制软件示例」、不占消息下标不进发送不落项目文件、有记录项目首绘先显示「正在读取聊天记录…」不闪示例。
  - `### 设计条目` 末尾新增 **DES-S01-110**：实现落点逐条对应主干代码（见下表）。
  - `### 测试锚定` 表尾新增 REQ-S01-110 行：登记已有行为测试文件，注明均未挂本编号锚点。
- `docs/records/对话需求追溯.md`：表尾追加 `11-23 · UX-C5D，示例气泡补登` 一行，链接 REQ／DES-S01-110，注明功能早已在主干、本轮只补文档、需求标 🟡 待复核。
- `tasks_round/tasks_round_4200_result.md`：本文件。

## 代码依据（新条目内容均在主干核实过）

| 条目内容 | 依据 |
| --- | --- |
| 示例内容源 `默认创意示例.md`、`utf-8-sig` 首读缓存 `_idea_example`、缺失退回 `IDEA_FIELDS`＋`INLINE_REQUIRED_LABELS` 字段名空表 | `ui/desktop_idea_chat.py:702-720`（`idea_example()`）；`ui/desktop_idea_chat.py:94`（`IDEA_FIELDS`） |
| 建页存 `page.idea_template` | `ui/desktop_writing_page.py:241` |
| 首绘占位 `show_example_bubble(loading)`：无记录放示例、有记录放「正在读取聊天记录…」（`bubble_loading` 标签，刻意不叫 `bubble_example`）；`idea_history_expected()` 每项目每次运行查一次盘 | `ui/desktop_idea_deferred.py:17-19,25-57`；调用点 `ui/desktop_writing_page.py:208`、`ui/desktop_idea_chat.py:262` |
| `add_bubble` example 分支：`raw_text` 不 strip、不加 `BUBBLE_PAD`、`fill=''`、前景 `text_secondary`、`markdown=False`、不折叠、`add_bubble_actions` 仅 `isinstance(index,int)`；署名行模型名「示例模板」 | `ui/desktop_idea_bubbles.py:324-411`（尤其 327-329、333-334、348-363、370、374-379、406-407）；`orchestrator/idea_chat_controller.py:74-78`（`speaker_name` → 「对话AI · 示例模板」） |
| 右键 `bubble_target_at` 映射 `('example','bubble_example')`；菜单对 example 只给「复制软件示例」 | `ui/desktop_idea_bubbles.py:189-190`；`ui/desktop_idea_menus.py:41,54-55` |
| 复制示例全文、状态栏「已复制软件示例」 | `ui/desktop_idea_bubbles.py:226-233`（`copy_bubble_message('example')`） |
| 不落项目文件：`save_brief` 剥 `idea_example().strip()` 前缀、剥完为空抛「请先填写自己的创意；灰色文字只是软件示例，不会保存到项目。」；发送只读输入框 `draft_text()` | `desktop.py:392-403`、`desktop.py:427-435`；行为测试 `tests/test_ui_edges_pages.py:460-492,1207-1234`、`tests/test_idea_inline_brief.py:473,524,587-633` |
| 有记录不闪示例 | `tests/test_idea_history_first_paint.py:78-112`；`ui/desktop_idea_deferred.py:26-32` 注释（R1949） |
| 模型目录条在示例气泡下不显示 | 既有 REQ-S01-77／DES-S01-77 已覆盖，本轮未重复立条 |

## 命令与退出码

工作目录均为车道 `程序\`，解释器 `..\..\..\..\运行环境\Python\python.exe -B`（相对路径，原样执行；首次误用 bash 会话跑反斜杠路径报 command not found 退出码 127，改用 PowerShell 会话后原样通过，非命令被拒）。

| 命令 | 退出码 | 输出尾部原文 |
| --- | --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` | 0 | `共 34 条用例，1.6 秒；0 个文件有红`／`ALL TESTS PASSED` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 先领 `4198`；R4198 提交被回执机制拒绝后改领 `4200`（见下） |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4200: UX-C5D 补示例气泡文档条目" docs/stages/S01_剧本准备.md docs/records/对话需求追溯.md tasks_round/tasks_round_4200_result.md` | 见下方提交记录 | 见下方提交记录 |

轮次号变更说明：首次 `dev.py commit`（R4198）误把文件参数写成 `程序/` 前缀（相对仓库根而非 `程序/` 工作目录），`git add` 报 pathspec 不存在；但提交回执 `R4198.json` 已先落盘且 identity 绑定那组错误路径，之后任何等价路径写法都被 `commit_retry` 判「轮次已归属其他工作树、分支或命令参数」拒绝。按 R4160 同例车道机制重新领号为 4200，本结果文件由 `tasks_round_4198_result.md` 改名而来，文档内容未变。两次被拒命令原文见完成报告。

改前测试红的条数和失败原因：无——本卡为纯文档补登，验收命令改前未跑（卡面只要求改后全绿）；四份门禁在补登前对既有文档本就全绿，新增条目按既有编号与格式写入后仍全绿。

## 如实说明

- REQ-S01-110 标 🟡 的原因见「开头三问」第三条；若后续轮次在测试里补 `REQ-S01-110` 锚点（docstring 或 `test_req_s01_110_*` 命名），可升 ✅。
- `idea_chat_controller.prepare_submission` 的 `is_example` 形参在签名里存在但函数体未使用，全部调用方传 `False`；示例不进提交实际由「发送只读输入框」保证，文档按后者表述，未把 `is_example` 写成有效行为。
- 「署名显示示例模板」：气泡署名行实际渲染为 `speaker_name` 的「对话AI · 示例模板」，REQ 条目按用户可见口径写「示例模板」，DES 条目写明完整机制。
- 未验证项：未在真实窗口目检气泡外观（折行、颜色、首绘时序），依据为代码与既有隐藏桌面测试；`默认创意示例.md` 正文未逐字复述进文档（条目只写「随程序打包的示例文件」这一契约）。
- 卡外发现（只记录不修）：`prepare_submission` 的 `is_example` 形参疑似历史遗留死参数，建议后续清理轮确认后移除或启用；`docs/records/工程文档登记表.md` 已登记 `默认创意示例.md` 为 S01 权威文档，与本次补登一致。
- 被拒绝的命令：`dir /b ... | findstr` 与 `Get-ChildItem` 各一次（探索性列目录，非卡面命令），均未重试，改用文件搜索工具完成；验收命令首次在 bash 会话因反斜杠路径解析失败（exit 127），改用 PowerShell 会话原样重跑通过；R4198 的 `dev.py commit` 因文件参数误带 `程序/` 前缀被 `git add` 拒绝（exit 1），回执绑定后按先例换号重提。

## 未覆盖项

- 未跑默认冒烟、`smoke_test.py --architecture`、全量自测——纯文档轮按卡面只跑定向验收命令。
- 未 push、未 merge、未动主工作区与其他车道；条目标 🟡 的复核（挂测试锚点后升 ✅）留给后续轮次或总控裁定。
