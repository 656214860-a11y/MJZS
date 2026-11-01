# R2165 结果：剧本 Agent 交给桌面程序或已有会话后，「终止」按钮复位（修复轮）

## 三问
- 轮次类型：修复轮（§3.2）。来源是剧本准备页「发送 → 模型调用」只读审计里的 B1，用户确认先修。代码偏离 REQ-S01-62（只有剧本 API 请求或剧本 Agent 进行中才显示「终止」），改代码，不改需求。
- 测试和三个基线：在 worktree 分支 `claude/grill-script-prep-logic-audit-af3f57` 上运行（经 gui_hidden）。
  - 新测试改动前失败、改动后通过，见下文。
  - 环境补齐：worktree 里 3 个技能子模块是空目录：`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`skills/01 剧本准备SKILL/编剧技能集`。它们的 gitlink 与主检出的 HEAD 一致。运行前按 gitlink 提交用 `git archive` 从主检出临时解出 274 个文件，跑完按清单删除，目录恢复为空，未提交。下面 4 项都在补齐后运行。
  - `run_selftests.py -k workflow idea cancellation script desktop_send`：630 条，0 红（126.3 秒）。补齐前同一组有 13 个文件 38 条红，补齐后全部消失，都由 SKILL 文件缺失引起。其中 `send_message` 相关用例在 `capture_request` 就提前失败，走不到本轮改动。
  - `smoke_test.py --affected desktop_idea_chat`：通过 9 项，失败 0 项。
  - 默认冒烟：通过 8 项，失败 0 项。
  - `--architecture`：411 项，只有轮次基线 `test_round_number_continuous` 失败：状态页「当前轮次」仍是 2153，不等于最新结果报告号＋1。原因是分支不写状态页，由合并轮登记。worktree 缺被忽略的 `维护记录/基准历史.json`，运行前从主检出临时拷入，跑完已删除。
  - 全量 `--all --safe` 本轮未运行。提交后钩子按 `<worktree 根>/运行环境/Python/python.exe` 找解释器，worktree 里没有这个目录，钩子直接跳过，没有触发后台全量。后台全量改由合并轮 R2169 在主检出的提交触发。
  - 真机未手动核对。
- 轮次号：开工时领的是 R2158。提交时中央台账已被其他会话推进（重领前已到 R2164），提交钩子要求提交号等于最新已领号，于是用 `round_claim.py next` 重领为 R2165。改动随之转到分支 `codex/wip-R2165`，结果文件改名，正文其余内容不变。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 复现
1. 剧本准备页的模型选 Claude Desktop、Gemini 等桌面程序，或 GPT 桌面（Codex 无 CLI 程序）。
2. 填好创意点「发送」，任务粘贴或复制到桌面程序。
3. 输入框右下角按钮停在「终止」(■)，不回到「发送」。「删除全部信息」被拦成「模型正在回复」，附档也删不掉。要等用户手动点一次「终止」才恢复。
4. 用 Claude Code CLI 时，第二次发送续发给仍在运行的会话，之后同样卡在启动中；会话进程退出后按钮也不复位。

## 根因
`send_message` 走 Agent 分支时，在 `start_script_workflow` 返回后无条件把 `_script_agent_launching` 置为 True。能把它清掉的只有：CLI 新进程启动成功的 `launched()`、排队取消与超时的 `cleanup()`、后台失败的 `_async_failed`、`begin_request`／`cancel_request`。下面这些出口都不清：
- 桌面程序交付：`_FlowAgentLaunch.done()` 的 Claude Desktop、`desktop-app`、GPT 桌面三条路径；
- 续发给已在运行的 CLI 会话：`launch_cli` 的 `submit_existing` 分支；
- `dispatch` 里「相同任务已复用记录」与「上次窗口已关闭」两个提前返回。

`script_task_active()` 只要看到这个标志就为真，所以按钮、删除全部信息、删附档都被它卡住。在这种状态下点「终止」，还会让 `interrupt_script_agent` 去取消一个不相干的后台任务。

## 改动
- `desktop_idea_chat.py`：`_FlowAgentLaunch` 新增 `settle_launch()`，只对剧本阶段生效，清掉 `_script_agent_launching` 并刷新按钮。它在三个位置调用：
  - `dispatch` 交给 `done()` 之前，覆盖三条桌面交付路径；
  - `dispatch` 复用重复任务记录、不再重试的分支；
  - `launch_cli` 续发已有会话的 `submitted` 回调。
- 自动重试分支（`retryable`）不清标志，因为它会重新进入 `open_flow_agent`，仍处于启动中。CLI 新进程路径维持原样，仍由 `launched()` 清。续发后会话进程还活着时，按钮继续由 `script_agent_processes()` 显示「终止」，进程退出即回到「发送」。

## 测试
- 新增 `tests/test_workflow.py::DesktopModelPoolTests::test_script_launch_flag_clears_once_task_reaches_desktop_or_live_session`（REQ-S01-62）。测试按真实顺序执行：`open_flow_agent` 返回后才置位标志，再执行排队的后台回调。覆盖以下路径：
  - 桌面交付：`desktop-app`、`claude-desktop-app`、GPT 桌面（`codex`）；
  - CLI：首发起进程，第二次续发给活会话，第三次复用重复记录。
  - 进程存活时 `script_task_active()` 为真，`poll()` 返回 0 后为假。
- 改动前失败（4 处，均为断言失败，不是报错）：

```
FAIL: ... (engine='desktop-app')        AssertionError: True is not false
FAIL: ... (engine='claude-desktop-app') AssertionError: True is not false
FAIL: ... (engine='codex')              AssertionError: True is not false
FAIL: ...                               AssertionError: True is not false : 续发给已有会话后仍卡在启动中
Ran 1 test in 1.623s
FAILED (failures=4)
```

- 改动后：`Ran 1 test in 0.812s  OK`。
- 已有测试断言未动。

## 范围外（只记录，未改）
同一次只读审计的其余发现，留待用户逐条拍板：
- B2：剧本阶段会弹出「请再次点击"手动制作分镜"」，提示串到了别的阶段。
- B3：自动重试漏传 `desktop_paste`。
- B4：`watch_script_quality` 在 `prepare` 成功前就启动，失败后仍轮询 1 小时。
- 重复调用：`validate_selected_skills`、`capture_request_model` 各调用 2 次；`refresh_script_workspace` 也重复捕获；排队取槽逻辑写了两份。
- 死代码：`writing_api.py` 的 `cli` 分支恒为假；去重签名白白读写文件；`import idea_chat` 未使用。
- 设计问题：D1 每次续发都带整份 SKILL；D2 `setup_key` 含锁和 SKILL 字段，改锁会另起进程；D3 CLI 与桌面路径也内联 SKILL。

## 提交
提交说明首行为 `R2165: 剧本 Agent 交给桌面程序或已有会话后「终止」按钮复位（修复轮）`。只提交 `desktop_idea_chat.py`、`tests/test_workflow.py` 和本文件；未 push，未合入 master。

## 用户需做
重启应用后生效。
