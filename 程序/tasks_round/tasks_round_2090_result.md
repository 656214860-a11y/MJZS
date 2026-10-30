# R2090 修 R2074 修改习惯文案触发的 test_copy_rules 红项（修复轮）

轮次类型：修复轮。日期：2026-10-30。分支 `claude/fix-copy-rules`，基于 master `389007ed`（R2086）。

- 本轮运行：`run_selftests -k test_copy_rules test_edit_habits` 23 条 0 红（worktree）；在补齐 SKILL 子模块的临时目录里，默认 `smoke_test.py` 8/8 通过，`test_copy_rules` 再跑全过。未运行 `--all --safe`，由提交后的后台全量补跑。`project_status.md` 债务未减少：该红项此前未单独登记为待办。
- 断言未动，测试与白名单都未改。

## 红项与规则

- 红项：`test_copy_rules.SecondPersonTests.test_interface_copy_speaks_to_you_with_the_polite_pronoun`（10-30 后台全量在 `33b684b` 上报红）。规则要求对用户说话用「您」。
- 豁免方式（`tests/test_copy_rules.py` 的 `PROMPT_FILES`）：写给模型的提示词按整个文件登记，登记后该文件里的「你」全部放行；第三方 SKILL 包整包放行（`VENDORED_SKILL_PACKAGE`）。
- 不登记豁免的理由：`edit_habits.py` 同时有直接给用户看的提示（如“至少攒够 3 次修改再归纳”），整文件放行后这些文案误写「你」也查不出来。

## 修复

1. `edit_habits.py:219` 归纳提示词 `SUMMARY_SYSTEM`：开头「你在分析用户对 AI 生成剧本的修改」改为「任务：分析用户对 AI 生成剧本的修改」，不用人称，其余要求不变。
2. `edit_habits_dialog.py:48-49` 弹窗说明（用户可见）：「记下你的修改」「你采用的规则」改为「您」。原红项列表被截断，这一处是改完第 1 处后复跑才显出来的。
- R2074 的其他新文件（`desktop_script_pages.py` 新增部分）已查，没有「你」。

## 未处理

- `test_leak_teardown`（第 3 轮 after 计数 7，期望不超过 6）属时序波动，本轮未处理。
- 未 push。
