# R2082 剧本准备页输入框改成 Claude Code 桌面版样式（功能轮）

轮次类型：功能轮。日期：2026-10-30。分支：codex/wip-R2082（由 claude/script-input-box-redesign-5b47b2 领号时带过来）。

- 跑了哪些测试与基线：`run_selftests.py -k idea_chat ui_edges script_composer cancellation desktop_async writing_restart`（隐藏桌面）全通过；压缩代码后再跑 `-k project_page_services script_composer idea_chat ui_edges` 全通过；默认冒烟 8/8 通过；`--architecture` 余 2 红（见下）。
- `project_status.md` 欠账：未减少；分支不提交状态页。
- 契约有意变更：中断按钮并入发送按钮、附件改卡片，相关用例按新界面同步（见「测试」），断言未弱化。

## 需求

REQ-S01-62～64、DES-S01-62／63 写在 `docs/stages/S01_剧本准备.md`，锚定到 `tests/test_script_composer.py`。

## 改动

- 输入区改为一个圆角框：顶部是附件卡片行（无附件时不占位），中间是无边框输入框，底部左侧「+」上传，右侧发送按钮。
- 发送按钮空闲时显示上箭头、走底栏「发送」；任务运行中切换为终止图标、点击终止；附件入库校验期间不可点。底栏「中断」按钮移除，「发送」保留。
- 运行中在输入框按 Esc 等同终止；空闲时不拦截。
- 附件卡片按上传顺序排列，单击打开（原件优先），右上角 × 删除单个，仍弹确认、仍走回收站、原件不动。去掉勾选多选和垃圾桶按钮。
- 本轮会带上的附件卡片用主色边框；「已引用：…」文字行去掉，字数等明细放卡片悬停提示（`idea_attachment_status` 仍保留同样文本）。
- 框上方的提示标签和框外 ↵ 去掉，改为框内占位提示「输入想法，Enter 发送，＋ 上传附件」。
- 新增 `ui_composer_style.py`（L4）放卡片与框内按钮样式，`ui_widgets.setup_styles` 调用；图标常量加在 `ui_tokens.py`。已登记 `tests/architecture/_layers.py`、`architecture.md`，刷新 `维护记录/覆盖率基线.json`（327 个模块）与 `维护记录/skip台账.json`。
- `ui_widgets.py`、`desktop_idea_chat.py` 守住行数上限，未抬高。

## 测试

- 新增 `tests/test_script_composer.py`：发送／终止切换、Esc 只在运行中终止、引用卡片高亮与 × 位于右上角。
- 同步：`tests/test_idea_chat.py`（中断改测合一按钮、附件改测卡片 × 删除与单击打开、上传图标改 `ICON_ADD`）、`tests/test_ui_edges.py`（占位提示、「+」与发送按钮在框内）、`tests/test_project_page_services.py`（`delete_uploaded_idea_attachment` 改为传单个路径，断言未动）。

## 仍红（均非本轮引入）

- `test_idea_chat.BubbleLayoutTests` 单独跑时红（3 failures、4 errors）；在 HEAD（4bbf8411）的临时 worktree 跑同样命令也红（3 failures、5 errors），属首绘时序问题。经 `run_selftests.py` 跑时通过。
- `--architecture`：`test_performance_history_is_declared_as_historical_only`（`维护记录/基准历史.json` 未纳入版本库，只在主目录有）；`test_round_number_continuous`（分支不提交状态页，HEAD 上同样 2076≠2077）。

## 其他

- worktree 中 skills 子模块为空，用 `tar --exclude=.git` 从主目录复制以跑测试，不影响 git 状态。
- 用户反映「无法输入符号 ();」：隐藏桌面合成按键（含 Shift）可正常输入 `()`，全局没有吞键绑定，暂无法复现，待用户补充输入法和现象。

## 未运行

- `--all --safe`、真实界面目测截图。未 push。
