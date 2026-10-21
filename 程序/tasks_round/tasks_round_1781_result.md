# R1781：修复轮（含全量基线验证）——后台全量红后反复重跑：先修 5 个红，再加红后冷却

1. 本轮类型：§3.2 修复轮（失败回归导致测试资产修复，按 §3 归类为修复轮；全量只是验证范围）。用户问题：全量测试执行频率是否过高。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k auto_full_safe`：31/31（新增 `RedCooldownTests` 6 条）。
   - 定向 `-k desktop_automation_service desktop_tray force_quit test_timers`：44/44，6.4 秒。
   - 定向 `-k ui_edges soak_light`：全绿（`test_ui_edges` 8 路并行最慢 232 秒，`test_soak_light` 17.6 秒）。
   - `smoke_test.py --affected desktop_tray`：9/9（含默认冒烟 8/8）。
   - 架构门禁 375 条：1 错 1 败，均为工作树环境缺文件，与本轮无关，R1775 结果文件已记录同样两条（见「未通过项」）。
   - 完整安全全量：**本轮未跑**。本轮改了 `desktop_tray.py`（启动路径）与运行器，合入 master 后由后台通道补跑；未跑前不写通过。历史凭据仍是 R1734。

3. project_status.md 欠账少了吗：本轮改源码 +1（`desktop_tray.py`、`scripts/auto_full_safe.py`、`run_selftests.py`、`smoke_test.py`）；全量欠账由合入后补跑清账。

## 调查结论（频率是否过高）

- 规则本身不高频：主干累计 8 个源码轮次才欠一次，提前 2 轮后台补跑，并有 15 分钟安静期防抖。
- 绿凭据（common-dir `full-safe-receipts.json`）：10-15～10-17 约 29 次（最密 15 分钟一次）；10-18～10-19 共 3 次；R1734（10-19）之后无新凭据，隔了 42 个提交。
- 2026-10-21 05:56 的后台全量（HEAD `bdd48715`，6195 条、927 秒）红在 5 个文件。红了不写凭据，欠账一直成立，之后每个提交都会再起约 16 分钟的全量——这才是“又跑起来了”的来源。

## 根因与修复（5 个红，断言未动）

| 红 | 根因 | 修复 |
|---|---|---|
| `test_desktop_automation_service`（16 条） | `desktop.py:608` 的 `cancel_timers` 现调 `self.cancel_resize()`，测试替身没有 | `make_desktop` 替身补 `cancel_resize` 空实现 |
| `test_force_quit`（7 条） | `finish_close` 新增 `self.close_tray()`，`Stub` 没有 | `subject()` 替身补 `close_tray` |
| `test_ui_edges` 1 条、`test_timers` 1 条 | 测试里构造 `Desktop`（28 个测试文件、约 132 处）会走 `setup_tray()` 起真实托盘线程：满载时 5 秒建窗超时；托盘的 `after` 轮询任务还残留在 `after info` 里 | `desktop_tray.SUPPRESS_TRAY_ENV`＝`DRAMA_SUPPRESS_TRAY`：`setup_tray` 在该变量为 1 时跳过；`run_selftests.py`、`smoke_test.py` 与 `DRAMA_SUPPRESS_MODAL` 同处 `setdefault`；`test_desktop_tray` 的子进程用例清掉该变量，仍走真托盘 |
| `test_soak_light` 1 条（12.065 秒 > 10 秒） | 全量并发下机器负载，不是回归 | 未改阈值。单独跑通过；上面的托盘抑制也减少了并发负载 |

## 红后冷却（`scripts/auto_full_safe.py`）

- 新增纯函数 `red_cooldown(result, head, now)`：只认真红（排除 0 与环境受阻 `BLOCKED_CODE`）；同一 HEAD 已红返回 `head`，冷却期内 `RED_COOLDOWN_SECONDS`（4 小时）返回 `time`。
- `status()`：冷却中则 `auto_due` 为假；门禁已因欠账报红（`required`）时只越过时间冷却，不越过同 HEAD。`--status` 增加「红后冷却」一栏。
- `runbook.md` §4 补充说明。欠账规则的权威仍是 `run_selftests`，未改。
- 测试：`tests/test_auto_full_safe.py::RedCooldownTests` 6 条（同 HEAD 不重跑、新 HEAD 冷却内外、绿/受阻/缺失不冷却、时间戳不可读不挡、`status()` 抑制、`required` 越过）。

## 未通过项（环境原因，非本轮引入）

- `test_agents_md.test_performance_history_is_declared_as_historical_only`：工作树缺 `程序/维护记录/基准历史.json`（`.gitignore` 排除）。
- `test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references`：`AIGC创作全流程` 是 gitlink（160000），工作树里为空目录。
- 两条在主检出与 `.wt/ci` 干净检出中不受影响。

## 其他发现（仅记录，未处理）

- 只读调查（历史垃圾文件与疑似无用模块清单）的证据已汇总给用户，清理另起轮次，不在本轮范围。
- 本轮验证时第一次定向跑因别的会话占用跨树 GUI 令牌等待 15 分钟；架构门禁重复跑过一次（为取失败用例名）。

## 提交

- 已提交，commit hash 见 git log `R1781:`。
