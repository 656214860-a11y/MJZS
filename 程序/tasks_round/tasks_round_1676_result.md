# R1676 修复轮：双击目录表头误开文件 + 用户既有改动入库

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（含提交收尾）。修复“勾选文件后双击目录表头仍打开文件”，并把用户既有 3 个改动、接力快照与 `.claude/` 按授权入库；不重构、不改契约。
2. **测试跑了吗？三个基线过了吗？** 定向用例 1/1、默认冒烟 8/8；架构门禁全量与安全全量未跑，不能记作“三个基线全过”。
3. **project_status.md 的欠账少了吗？** 没有。本轮只做修复与入库收尾，未清历史欠账。

## 根因与复现

- 现象：项目文件处于勾选/高亮状态时，双击 Treeview 表头（分类名/全选）或列宽分隔线，仍会打开上次选中文件。
- 根因：`<Double-1>` 绑定覆盖表头区域，处理函数无条件读取 `tree.selection()[0]`，没有按双击落点判断是否命中数据行。
- 复现：勾选任一剧本文件 → 双击表头 → 文件被打开。

## 改动

- `程序/desktop_writing_page.py`：双击改用 `event.widget` 与 `responsive_ui.row_toggle_target()` 只认落点行；表头/分隔线直接返回；键盘 `<Return>` 仍打开当前高亮行；暴露 `self.open_script_file` 供回归用例调用。
- `程序/tests/test_idea_chat.py`：新增真实 Tk 用例，钉住“表头不打开、行内双击打开、Enter 打开”。
- `程序/配置/SKILL/预设.json`：用户原有 3 项改动完整保留（剧本模型改为 `claude code cli`，新增 Gemini 4／CCC／Qwen 预设）。
- `.agent-handoff/snapshot.md`：补记 R1675 合并与清理收尾。
- `.claude/settings.local.json`：按用户要求强制纳入跟踪；同目录 `scheduled_tasks.lock` 仍按 `.git/info/exclude` 的 claude-code-runtime 规则排除（运行期锁，含 PID/会话 ID）。

## 验证

- 定向：`test_idea_chat.SendMessageTests.test_double_click_on_script_header_does_not_open_selected_file` 1/1 通过。
- 默认冒烟：8/8 通过。
- 架构子集：`tests.architecture.test_round_baselines` 5 项中 4 项通过；唯一失败为“R1676 欠一次完整安全全量”（上次 R1624，已 13 个源码轮次 > 门禁线 8）。post-commit 已触发后台补跑，未手动全量。
- 未跑：架构门禁全量、安全全量；未重启 GUI 做人工双击复验。

## 自审

- 分层：UI 仅复用 `responsive_ui.row_toggle_target()`，未新增反向 import。
- 契约：未改 `responsive_ui` 公开函数签名；`open_script_file` 实例属性仅为可测性。
- 范围：只动用户点名文件；`预设.json` 原样保留，未增删内容。
- 风险：`settings.local.json` 含本机绝对路径，换机后需复核；`scheduled_tasks.lock` 未跟踪，避免每次会话产生工作树噪声。

## 提交

- 以 `R1676: ...` 收尾提交，commit hash 见 `git log`。
