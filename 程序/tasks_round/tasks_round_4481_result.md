# tasks_round_4481_result — FIX-S03-SEND-SILENT（初步分镜点击发送后没有任何反应）
<!-- round-evidence: {"commit_base": "84bed5cf2", "credential_hits": 0, "evidence_sha256": "cabd2a189b3d4539", "exit": 0, "failed": 0, "passed": 119, "round": 4481, "tests": "run_selftests.py -k desktop_shared_input shared_input_stages idea_send_gate script_composer stage_command_contract"} -->

## 三问

- **本轮属于 §3 哪种类型**：修复轮（§3.2）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 定向测试：`run_selftests.py -k desktop_shared_input shared_input_stages idea_send_gate script_composer stage_command_contract` → 119 条用例（原 112 条 + 新增 7 条），0 文件有红，0 跳过，退出码 0。
  - 架构门禁：`smoke_test.py --architecture` → Ran 708 tests in 295.918s，OK，退出码 0（改后实测，非历史凭据）。
  - 默认冒烟基线 8/8：本轮未跑 `smoke_test.py` 默认档（验收命令未含）；全量 `--all --safe` 未跑，欠账口径以 `full-safe-receipts.json` 为准，本轮不宣称消灭历史全量欠账。
- **欠账少了吗**：本轮为单卡缺陷修复轮，消除了 03 初步分镜页点击发送静默无反应的 3 类产品根因并补齐 7 条自动化回归测试，不涉及主干既有全量欠账变更。

## 缺陷复现方式与改前红灯原文（基线 `84bed5cf2`）

先在 3 个允许修改的测试文件新增 7 条用例（含 2 组子测试，共 9 项失败点），未改产品代码运行定向命令，退出码 1（119 条用例，3 文件 9 项红，既有 112 条全绿）：

1. **复现 1（切页发送键沿用 01 置灰/中断态）**：`test_desktop_shared_input.py::SendButtonRunningStateTests::test_switching_from_disabled_script_stage_re_enables_storyboard_send_button`
   - 01 页置灰共享 `send_button` 或切至中断态后调用 `set_stage('storyboard')`，发送键仍为 `disabled`。
2. **复现 2（01 防抖门禁与中断态刷新跨页误置灰）**：`test_idea_send_gate.py::IdeaSendGateTests` 两条用例
   - `shared_input.stage = 'storyboard'` 时，`_apply_idea_send_state()` 仍触发 `update_script_interrupt_button` 与状态栏写入；真实 `update_script_interrupt_button()` 在空闲/运行态下仍篡改 `send_button`。
3. **复现 3（异步回调未捕获异常、无条件覆盖直连状态、dict 快照解包崩溃、读取异常静默）**：`test_shared_input_stages.py::StoryboardSendChainTests` 四条用例
   - `open_flow_agent` 抛 `ValueError` 时 `finish()` 未捕获；`open_flow_agent` 写入直连 API 状态后被 `finish()` 覆写；`request_model` 为 `writing_api.capture_request` 风格 dict 时 `/技能` 透传给 `workflow_settings.current` 导致解包失败；`storyboard_work_plan` 抛错时 `_start_storyboard_batch` 状态栏为空。

```text
共 119 条用例，76.9 秒；3 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过

### test_idea_send_gate（3 条红）
===== test_apply_idea_send_state_skips_when_not_on_script_stage =====
  File "程序\tests\test_idea_send_gate.py", line 92
AssertionError: Expected 'mock' to not have been called. Called 1 times.

===== test_update_script_interrupt_button_ignores_non_script_stage (script_task_active=False) =====
  File "程序\tests\test_idea_send_gate.py", line 107
AssertionError: Expected 'configure' to not have been called. Called 1 times.

===== test_update_script_interrupt_button_ignores_non_script_stage (script_task_active=True) =====
  File "程序\tests\test_idea_send_gate.py", line 107
AssertionError: Expected 'configure' to not have been called. Called 1 times.

### test_shared_input_stages（5 条红）
===== test_finish_preserves_status_written_by_open_flow_agent =====
  File "程序\tests\test_shared_input_stages.py", line 642
AssertionError: '正在启动分镜制作 agent…' != '正在直连 API 制作初步分镜（后台进行，可点「强制停止制作」中断）…'

===== test_named_skill_ignores_writing_dict_request_model_snapshot =====
  File "程序\tests\test_shared_input_stages.py", line 673
AssertionError: Lists differ: [{'id': 'gpt-4o', 'record': {'context_length': 8192}, ...}] != [None]

===== test_start_storyboard_batch_reports_work_plan_error_to_status =====
  File "程序\tests\test_shared_input_stages.py", line 688
AssertionError: '读取结构剧本输入失败' not found in ''

===== test_finish_reports_open_flow_agent_error_instead_of_raising (with_notifier=True / False) =====
  File "程序\desktop_shared_send.py", line 426, in finish
    desktop.open_flow_agent('storyboard', '初步分镜', batch['prompt'], batch['followup'], **kwargs)
ValueError: 未配置分镜模型，请先设置

### test_desktop_shared_input（1 条红）
===== test_switching_from_disabled_script_stage_re_enables_storyboard_send_button =====
  File "程序\tests\test_desktop_shared_input.py", line 411
AssertionError: True is not false
```

## 改动清单（文件:行号）

- `程序/ui/desktop_shared_input_extras.py:232-235, 372-395, 436-466`：
  - `_ComposerExtras.__init__` 缓存默认发送字形 `_send_idle_glyph`（容错 `AttributeError`/`tk.TclError`，不新增 `ICON_SEND` 引用）。
  - `_ComposerExtras._reset_send_button` 在 `stage_changed` 开头（非 `'script'` 阶段）复位 `_send_interrupt=False`、恢复字形与 `command=box.send`、清除 `disabled` 与 `_stage_flow_forced`，再调用 `_sync_send_state()` 与 `sync_send_art(box)`。
  - 新增导出 `normalize_stage_model_snapshot(snapshot)`（仅放行 2 元组，过滤 `writing_api.capture_request` 的 dict 快照）与 `launch_storyboard_flow(desktop, batch, request_text, value, kwargs, hooks)`（捕获 `open_flow_agent` 异常经 `notify_error` 提示，仅在状态栏未被更新时写默认文案；以 `hooks` 三元组收拢参数至 6 个以满足复杂度门禁 ≤ 7）。
- `程序/ui/desktop_idea_send_gate.py:33-35`：`_apply_idea_send_state` 清掉 `_idea_send_state_after` 后检测 `shared_input.stage`，非 `'script'` 字符串阶段直接早退。
- `程序/ui/desktop_script_pages.py:317-320`：`update_script_interrupt_button` 开头检测 `shared_input.stage`，非 `'script'` 字符串阶段直接早退。
- `程序/desktop_shared_send.py:307, 423-424, 462-464`（总行数由 999 降至 993，满足 ≤ 1000 上限）：
  - `send_storyboard` 通过 `input_extras.normalize_stage_model_snapshot(snap)` 规范化快照；
  - `open_storyboard_skill` 的 `finish()` 委托 `input_extras.launch_storyboard_flow(...)`；
  - `_storyboard_idle_note` 捕获 `(OSError, ValueError, KeyError, TypeError) as exc` 时返回 `'读取结构剧本输入失败：%s' % exc`。
- `程序/tests/test_desktop_shared_input.py:404-428`：新增 1 条切页复位与点击触发测试。
- `程序/tests/test_idea_send_gate.py:86-110`：新增 2 条非剧本阶段门禁与中断态隔离测试。
- `程序/tests/test_shared_input_stages.py:607-690`：新增 4 条异步异常提示、直连状态保护、dict 快照过滤与输入读取报错测试。

## 改前产物改动统计（`git diff --numstat`，不含本结果文件与自动证据）

```text
5	11	程序/desktop_shared_send.py
25	0	程序/tests/test_desktop_shared_input.py
25	0	程序/tests/test_idea_send_gate.py
84	0	程序/tests/test_shared_input_stages.py
3	0	程序/ui/desktop_idea_send_gate.py
4	1	程序/ui/desktop_script_pages.py
55	0	程序/ui/desktop_shared_input_extras.py
```

## 改后验收命令与尾部输出

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k desktop_shared_input shared_input_stages idea_send_gate script_composer stage_command_contract`（退出码 `0`）

```text
共 119 条用例，12.1 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 `0`）

```text
----------------------------------------------------------------------
Ran 708 tests in 295.918s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证项与卡外发现

- **未验证项**：
  - 默认冒烟 `smoke_test.py`（8/8 基线）与全量自测 `run_selftests.py --all --safe`（本卡验收命令未要求，未执行）。
  - 真实可见桌面窗口下点击 03 初步分镜发送并走真 API/外部 CLI 流程（当前测试在隐藏桌面与 stub/mock 宿主下验证）。
- **卡外发现**：
  - 运行 `test_script_composer` 期间隐藏桌面日志仍存在既有的 Tk 销毁后残余 `after` 回调噪声（如 `invalid command name "..._apply_idea_send_state"` / `poll` / `start_account_renewal`），为基线既有现象，不在本卡范围，未顺手改动。

## 提交状态

- 通过 `scripts\dev.py commit` 提交至分支 `codex/fix-s03-send-silent`（含 `--tests desktop_shared_input shared_input_stages idea_send_gate script_composer stage_command_contract` 及自动生成的 `程序/tasks_round/evidence/R4481.json`）；未合入 `master`，未 `push`。
