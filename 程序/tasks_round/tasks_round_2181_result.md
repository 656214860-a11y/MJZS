# R2181 结果：剧本准备页紧凑布局测试同步 R2131 的提示锚点；更正 R2165、R2169 结果里的全量记录（修复轮）

## 三问
- 轮次类型：修复轮（§3.2）。来源是全量 `--all --safe` 的真红 `test_desktop_compact_layout`：919c88ee（R2169）和 957ad83a（R2179）两次全量都红这一条。用户确认在本会话修。无对应队列 ID。
- 测试和三个基线：在 worktree 分支 `claude/grill-script-prep-logic-audit-af3f57` 上运行（已快进到 master 957ad83a），含 Tk 的都经 `工作流任务/gui_hidden.py`。
  - `run_selftests.py -k test_desktop_compact_layout`：改动前 5 条红 1 条，改动后 5 条全过（15.0 秒；另外排队等 GUI 令牌约 5 分半，当时 master 的后台全量占着隐藏桌面）。
  - 默认冒烟：通过 8 项，失败 0 项。
  - `--architecture`：本轮未运行。只改了一个测试的期望值和两份结果文件，不是结构治理或跨层改动（§5）。
  - 全量 `--all --safe` 本轮未运行，分支不累计全量欠账（§5）。master 957ad83a 的后台全量 13:05 结束，退出码 1，用时 587 秒，只红这一条。
  - 真机未手动核对：本轮没有改产品代码。
- 轮次号：领号放在提交前一刻，领到 R2181，改动随 `git switch -c` 带到分支 `codex/wip-R2181`。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 根因
- R2131（630b8309「剧本准备页输入框空框由一行增为两行，提示对齐首行」）把 `desktop_writing_page.update_input_hint` 里提示层的定位从 `rely=0.5, anchor='w'`（按输入框中线垂直居中）改成 `y=SPACING['none'], anchor='nw'`（对齐首行顶边）。这是有意的 UI 契约变更，代码与 R2131 的需求一致，不改代码。
- R2131 同步了 `tests/test_idea_chat.py`（空框高度 1 改 2）和 `tests/test_ui_edges.py`（锚点 `'w'` 改 `'nw'`，并新增首行顶边对齐断言），漏了 `tests/test_desktop_compact_layout.py::test_actions_hint_and_full_file_details` 里的锚点断言。
- 复现：在 master 957ad83a 上运行 `run_selftests.py -k test_desktop_compact_layout`。

改动前：

```
  test_desktop_compact_layout     5 条    14.9 秒  ✗ 1
  File "...\tests\test_desktop_compact_layout.py", line 179, in test_actions_hint_and_full_file_details
    self.assertEqual(d.idea_input_hint.place_info()['anchor'], 'w')
AssertionError: 'nw' != 'w'
```

改动后：

```
  test_desktop_compact_layout     5 条    15.0 秒
共 5 条用例，347.6 秒；0 个文件有红
ALL TESTS PASSED
```

## 改动
- `tests/test_desktop_compact_layout.py`：锚点期望值 `'w'` 改为 `'nw'`，加一行注释，注明这是 R2131 的契约有意变更（§2.4）。紧接着的横向对齐断言（提示左缘与输入框首字左缘相差不超过 2 像素）不动，改后在 800×600 下通过。没有删除、放宽或跳过任何断言（断言未弱化）。纵向对齐已由 `tests/test_ui_edges.py` 的首行顶边断言覆盖，这里不重复加。
- `tasks_round/tasks_round_2165_result.md` 第 12 行：原文末句说后台全量改由合并轮 R2169 的提交触发，实际没有触发。改为：R2169 提交后钩子同样没有启动后台全量，12:03 手动补跑。
- `tasks_round/tasks_round_2169_result.md` 第 9 行：原文说由本轮提交后的 post-commit 钩子在后台自动补跑，实际钩子没有启动（没有锁，日志未更新）。改为记录手动补跑的经过和结果：HEAD 919c88ee，退出码 1，用时 594 秒，红 `test_soak_light` 与 `test_desktop_compact_layout`。

## 同类复核
- 在 `tests/` 里搜按旧契约断言的位置（`rely` 0.5、锚点 `'w'`、空输入框高度 1、「保持一行」）：只剩 `tests/test_pet_ui.py:6461`，那是桌宠气泡的 `cloud.hint`，与输入框无关，不动。
- 919c88ee 全量的另一条红 `test_soak_light`：最慢一轮 10.549 秒，超过 `ROUND_SECONDS_LIMIT = 10`。定向复跑 `-k test_soak_light test_desktop_compact_layout` 时 soak 全过，957ad83a 的全量里也没有红，判断为机器负载，不改。

## 范围外（只记录，未改）
- 提交后钩子不启动后台全量的根因由另一个会话排查。本轮不动 `post-commit`、`auto_full_safe.py` 等钩子相关文件。

## 提交
提交说明首行为 `R2181: 剧本准备页紧凑布局测试同步 R2131 的提示锚点，更正 R2165、R2169 的全量记录（修复轮）`。只提交 `tests/test_desktop_compact_layout.py`、`tasks_round/tasks_round_2165_result.md`、`tasks_round/tasks_round_2169_result.md` 和本文件；未 push，未合入 master。
