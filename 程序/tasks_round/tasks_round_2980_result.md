# R2980 结果：功能轮——共享输入框 `/` 与 `@` 光标级候选浮层（富文本式引用）
<!-- round-evidence: {"commit_base": "3c103033", "credential_hits": 0, "evidence_sha256": "cbe39885f05747fa", "exit": 0, "failed": 0, "passed": 93, "round": 2980, "tests": "run_selftests.py -k test_skill_command test_idea_attachments test_shared_input_stages test_shared_input_ui"} -->

## 三问

1. **轮次类型**：功能轮（§3.1）。用户任务书：输入框键入 `/`、`@` 弹出菜单——精准触发（`/` 须行首或空白后，`a/b`、URL、`3/4`、`a@b.com` 不触发）、光标级锚定（下方优先、不足翻上、屏幕钳制）、实时过滤＋匹配子串高亮、↑/↓/Enter/Esc 键盘导航且拦截默认行为、采纳后只替换触发词段并补尾空格；先调研可复用组件，结论是复用 `tk.Text` tag 体系与既有 `SharedStageInput`，零第三方依赖。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 **8/8**；`smoke_test.py --architecture` 架构门禁当轮实测 **470/470 全绿**；`smoke_test.py --affected desktop_shared_input` 定向 **174 条 0 红**（另一次 `--affected` 七模块并集 499 条 0 红）；定向 `test_skill_command`/`test_idea_attachments`/`test_shared_input_stages`/`test_shared_input_ui` **93 条全绿**。
3. **欠账少了吗**：是（就本轮范围）。旧 `@` 原生菜单链路（三处）摘除；`SharedStageInput` 719 行超复杂度棘轮登记线，候选流拆为 `_CandidateFlow` mixin 后宿主类 552 行、mixin 213 行，棘轮恢复绿。历史欠账未新增。

## 轮次号说明

开工时 `round_claim.py next` 领得 **R2975**（round-claims.json 有 15:01 记录），实现期间并行车道连续领号，本工作树重领为 **R2980**（15:52 记录，归属本工作树）。R2975 认领无对应提交属正常被顶替；全部代码注释与本文档统一写 R2980。

## 需求与设计（文档先行，§2.7）

- `docs/stages/S01_剧本准备.md` 新增 **REQ-S01-91／DES-S01-91**（光标级 `/`、`@` 候选浮层契约），追溯表登记四个测试文件。
- `architecture.md` R2893 段、`PROJECT_MAP.md` 阶段配置行同步新模块与交互口径。

## 实现

- L2 `skill_command.py`：新增 `trigger_token(text, offset)`——向左扫到行首找最近 `/`/`@`，触发符前必须是行首或 `isspace()`（`a/b`、`https://`、`3/4`、`a@b.com` 均不触发）；`end` 向右扫到空白或 `_TOKEN_END_BREAKS` 中英文句读为止，光标落在 token 中间也能整体替换；`query` 保留中间空格（阶段别名 `03 初步分镜` 可用）。新增 `completion_entries(query, …)`——条目 `{'kind','name','label','insert'}`，insert 含触发符与尾空格；排序＝当前阶段 skill → 其余 skill → 阶段别名 → 子引擎，子串过滤去重保序；`_item_stage`/`_skill_name` 兼容 Skill 对象/字典/字符串。`parse_command` 未动：仍只认整段开头 `/`，行中选中的 `/name ` 是普通文本。
- L4 `desktop_shared_menus.py` 新增 `CandidatePopup`（247 行）：顶层窗下 `place` 卡片浮层（与 `AnchoredPanel` 同描边）；`_cursor_anchor` 取 `Text.bbox('insert')`，先摆光标正下方、不足翻上、按「顶层窗∩屏幕」可视区四边钳制；自绘行＝类别徽标（技能/阶段/子引擎/附件）＋附件行首 `ICON_DOCUMENT`（`ICON_FONT`）＋`query` 子串 `primary_subtle` 底纹高亮，悬停/↑↓/Tab/点击导航，超 12 行显示「… 还有 N 项」。
- L4 `desktop_shared_input.py`：候选流整体拆为 `_CandidateFlow` mixin（213 行，`SharedStageInput(_CandidateFlow, ttk.Frame)`，宿主类 719→552 行过棘轮线）；每次 KeyRelease/ButtonRelease 重扫 `_active_token`，`/` 走 `completion_entries`、`@` 走 `_mention_entries`（仅 `stage=='script'`，经 L3 `stage_idea_attachment_paths` 列已入库附件、`domain.idea_attachments.display_name` 取显示名、上限 30）；`_replace_token` 用 `1.0 + N chars` 索引只换 `[start,end)` 段、尾部多余一个水平空格顺手吃掉、插入体（不含尾空格）加 `shared_token` tag、光标落在插入体后；`_apply_mention` 经 `desktop.idea_chat_controller.add_attachment` 登记本轮引用；`/`/`@`/Esc 仍走宿主 `ShortcutRegistry`；Enter 候选开着先采纳再说（`_on_return` 返回 `'break'` 拦页面级绑定）。
- L2 `domain/idea_attachments.py`：`referenced()` 的 `explicit` 除 `'@'+归档名` 外新增 `'@'+display_name(path)` 匹配，归档名匹配保留兼容。
- 旧 `@` 链路摘除：`desktop_writing_page` 输入框 `<KeyRelease>` 绑定、`desktop_idea_menus.show_idea_reference_menu`、`desktop_idea_attachments.insert_idea_reference`（含类方法数注释同步）。

## 测试与契约变更（§2.4）

- `CompletionPopup`（Listbox，锚输入卡上沿）→ `CandidatePopup`（自绘行，锚文本光标）：属有意 UI 契约变更，`test_shared_input_ui.py`/`test_shared_input_stages.py` 相应断言同步改写并新增覆盖（行中 `/` 触发、无命中收层、实时过滤、`@` 仅剧本页、采纳登记附件、Esc/失焦、面板互斥）。
- `skill_command` 的 `command_token`/`completions` → `trigger_token`/`completion_entries`：`test_skill_command.py` 同步改写并新增 token 边界与条目排序断言。
- `test_idea_attachments.py` 新增显示名引用解析断言。

## 验证记录

- `run_selftests.py --serial -k test_skill_command test_idea_attachments test_shared_input_stages test_shared_input_ui`：93 条全绿（GUI 令牌排队约 5 分钟后执行）。
- `smoke_test.py --affected desktop_shared_input`：174 条 0 红，冒烟门禁 9/9。
- `smoke_test.py --affected skill_command desktop_shared_input desktop_shared_menus idea_attachments desktop_idea_menus desktop_idea_attachments desktop_writing_page`（重构前口径）：499 条 0 红。
- `smoke_test.py`：8/8；`smoke_test.py --architecture`：470/470（首轮两红已闭环：`SharedStageInput` 719>600 → `_CandidateFlow` 拆分；`test_round_number_continuous` 状态页轮次头按规则 27 同步为最新结果+1=2972，本文件落地后工作树同步为 2981）。
- 全量 `--all --safe`：未运行（功能分支不累计欠账，合入 master 前按需补跑）。

## 范围外记录（不代修）

- `project_status.md` 轮次头在本工作树同步为 2981 但**不提交**（pre-commit 规定仅 master 可提交该文件）；合入 master 时由合并轮统一改写。
- round-claims.json 中 R2975 认领记录保留（本工作树 15:01），无对应提交；R2980 认领记录（15:52）归属本工作树。

## 追加修正（同轮收口：用户预览反馈四处）

R2971 提交后用户实测预览反馈，以下修正与 R2980 候选浮层同批入库（同一批未提交文件，按用户「合入」指令随本轮提交）：

1. **面板不可见根因修复**：`AnchoredPanel` 原挂 `SharedStageInput`，`place` 子控件被裁在 master 边界内，输入框贴底时负 y 浮层整体不可见（`/` 补全旧 `CompletionPopup` 同病）。改挂 `host.winfo_toplevel()`，坐标换算窗口相对系＋`lift()`；像素级探针实测修复前后对比确认。
2. **弹出位置与尺寸**：面板下缘悬输入卡顶边、左对齐；宽＝行内容自然宽（封顶输入盒宽）、高随行数，不再通栏。
3. **勾选框语义**：面板打开时一律未勾选（`sync_check` 只刷单行勾选像，不再整版 `refresh`）；勾选写回 `stage_config.skills` 本阶段默认但**不关面板**，点技能名才插入 `/name ` 并关闭。
4. **悬停说明卡**：与技能行同一行、行右侧紧贴 4px、垂直居中，右缘出屏翻到行左侧；`BaseDialog` 建窗标 `_positioned_once` 防 `ui_theme` `<Map>` 钩子重摆，按 `winfo_root*` 实测偏差两步贴正；行 Leave 延迟 200ms 收、移入卡片取消。

验证：`test_shared_input_ui` 定向 24/24 绿（本修正后实测，含 GUI 令牌排队 333s）；S01 文档 REQ-S01-90／DES-S01-90 已同步新契约。
