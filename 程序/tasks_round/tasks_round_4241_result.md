# R4241 结果：FIX-S11-E2 续做收尾（整段配音重试与结果未知确认）
<!-- round-evidence: {"commit_base": "365e376c", "credential_hits": 0, "evidence_sha256": "dae2349cb1ce5e5f", "exit": 0, "failed": 0, "passed": 113, "round": 4241, "tests": "run_selftests.py -k request_recording ui_edges_autopilot tts"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（FIX-S11-E2 已完成实现的续做收尾轮）。本轮不改产品行为：保留上一 attempt 留下的 6 文件未提交现场（+347/-15），核对 skip 台账新登记条目，重跑卡面两条验收命令，领号、写结果文件、提交。
- （二）测试跑了吗、三个基线：跑了。卡面两条验收命令——`run_selftests.py -k request_recording ui_edges_autopilot tts` 113 条全绿、退出码 0；`smoke_test.py --architecture` 首跑 700 条中 1 条环境性红（`test_test_move_guard` setUp 内 `git init` 子进程偶发返回非 0，与本卡 6 文件无关），原样重跑 700 条 OK、退出码 0。默认冒烟 8/8 本轮未跑（卡面未列，合并轮出口 CI 会跑）。
- （三）欠账少了吗：少了。FIX-S11-E2 从「实现已绿、skip 台账已登记、未提交」收口为待审交付，等待验收独立复核。

## 续做基准与保留现场

- 续做基准：HEAD `365e376c`（`git log -1 --format=%h` 输出 `365e376c`），分支 `codex/fix-s11-e2`（`git rev-parse --abbrev-ref HEAD` 输出 `codex/fix-s11-e2`）。
- 保留的 5 文件产品/测试现场（本轮零改动）：`程序/domain/tts_api.py`（+111/-8）、`程序/stage_execution_service.py`（+14/-0）、`程序/ui/desktop_media_pages.py`（+7/-7）、`程序/tests/test_request_recording.py`（+143/-0）、`程序/tests/test_ui_edges_autopilot.py`（+63/-0）。
- 保留的 1 文件 skip 登记现场：`程序/维护记录/skip台账.json`（+9/-0），即接口契约指定的唯一新条目。
- `git diff --numstat` 合计 +347/-15，与卡面一致；`git diff --name-only` 仅含上述 6 个允许文件；`git diff --check` 无输出。

## 上一 attempt 证据（转述，未重跑改前红测）

- 改前 6 红 → 改后定向 113 条全绿；架构 700 条仅 skip 卫生 322!=323 一条红（卡面背景，本轮未复跑改前）。
- 续做 attempt bb45be3d 已在 skip台账.json 精确插入该条目后，因误用非免确认命令 `git -c core.quotepath=false status --porcelain` 被拒而停住；本轮只核对、不再插入或修改既有条目。

## skip 台账条目核对（本轮 Read 原文）

`程序/维护记录/skip台账.json` 第 1822–1830 行，唯一新增条目：

```json
  {
   "file": "tests/test_ui_edges_autopilot.py",
   "test": "UiEdgeAutoTests.test_whole_script_tts_unknown_result_asks_before_resend",
   "ordinal": 1,
   "kind": "平台限制",
   "reason_constant": "PLATFORM_TKINTER",
   "reason": "当前环境没有可用 tkinter；安装可用 Tk 后应恢复执行",
   "reference": ""
  },
```

- 与接口契约逐字段一致；排序正确（位于 `UiEdgeAutoTests.test_whole_script_tts_reuses_unchanged_audio` 之后、`WorkerThreadSafetyTests.test_seedream_probe_reports_reachable` 之前），缩进与相邻条目一致；既有条目未动（numstat +9/-0）。
- 对应测试存在且口径吻合：`程序/tests/test_ui_edges_autopilot.py:1000` `UiEdgeAutoTests.test_whole_script_tts_unknown_result_asks_before_resend`，第 1002–1003 行 `self.tk is None → self.skipTest(PLATFORM_TKINTER)`。
- 架构门禁 skip 卫生三条用例本轮全 ok（`test_ledger_and_source_skip_sets_are_bidirectionally_equal` 等），322!=323 已消除。

## 实现核对（只读，未改）

- `程序/domain/tts_api.py`：`reserve_full_track_attempt`（请求号＝`tts-full:<签名>:<尝试序号>`，`sending`/`unknown` 口径须 confirm 放行、取消返回 None）、`note_full_track_outcome`、`_complete_full_track_attempt`、`synthesize_full_track`（TTSRejected／URLError／非重复 BudgetRejected 记 `failed` 可直接重发，其余记 `unknown`；台账报「该请求已有记录」时改写为说明文案）、`reusable_full_track`（新格式相对路径、旧绝对路径失效退回同名文件）、`publish_full_track`（标记 `file` 只写 `path.name`）。
- `程序/stage_execution_service.py`：`reserve_tts_full_track`／`synthesize_tts_full_track` 注入 `project_context` 与 `tts_gateway`；`publish_tts_full_track`／`reusable_tts_full_track` 由 `orchestrator.stage_gate_gateways` 转发。
- `程序/ui/desktop_media_pages.py` `generate_tts`：沿用→预约（`confirm` 注入 dangerous 确认框「上一次配音请求结果未知，可能已扣费，确认重发？」）→取消不发→发送→发布。
- `程序/tests/test_request_recording.py` 新增 `WholeTrackRetryTests` 5 条覆盖卡面全部边界例（401 后新请求号、超时须确认、成品删除重做、目录改名沿用、旧绝对路径兼容）；既有 `test_direct_tts_stable_id_prevents_resend_after_timeout`、`test_whole_script_tts_reuses_unchanged_audio` 意图由对应用例继续成立，未删未改既有断言。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `git status --short` | 恰好 6 个已修改文件，与允许清单一致，退出码 0 |
| `git log -1 --format=%h` | `365e376c`，退出码 0 |
| `git rev-parse --abbrev-ref HEAD` | `codex/fix-s11-e2`，退出码 0 |
| `git diff --numstat` | +347/-15（6 文件），退出码 0 |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k request_recording ui_edges_autopilot tts` | 113 条 0 红，`ALL TESTS PASSED`，退出码 0 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（第 1 次） | Ran 700 tests，`FAILED (failures=1)`：`test_test_move_guard.TestMoveGuardTests.test_only_a_subject_that_starts_with_the_marker_is_a_move_round` 在 setUp `git init -q -b master` 处 `AssertionError`（stderr 为空），与本卡 diff 无关，退出码 1 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（第 2 次，原样重跑） | Ran 700 tests in 293.091s，`OK`，退出码 0 |
| `git diff --check` | 无输出，退出码 0 |
| `git diff --name-only` | 仅 6 个允许文件，退出码 0 |
| `git diff --numstat` | +347/-15，退出码 0 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 领到轮次 4241，退出码 0 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4241: FIX-S11-E2 续做收尾" --tests request_recording ui_edges_autopilot tts --agent "Devin SWE-2 Flash High" …` | 见提交证据 |

注：定向命令首次在 Git Bash 下因反斜杠路径被 shell 转义（exit 127，命令未实际执行），随后按卡面原文在 PowerShell 下执行成功；另有一次带单引号包裹路径的变体调用被拒，未采用、未影响结果。

## 验收命令原始输出尾部

定向（退出码 0）：

```
共 113 条用例；0 个文件有红；实际跳过 0 条用例
ALL TESTS PASSED
```

架构（第 2 次，退出码 0）：

```
----------------------------------------------------------------------
Ran 700 tests in 293.091s

✅ 架构治理测试：tests/architecture
OK
```

## 未验证项

- 首次架构跑的 `test_test_move_guard` setUp `git init` 失败判定为环境偶发（同类其余用例 setUp 均过、原样重跑 700 条全绿、与本卡 6 文件无关）；未做单测级复现（卡面未列该命令）。若验收复跑再红，请按环境问题另行立案。
- 真实 Tk 桌面未人工点击整段配音按钮；UI 行为由 `test_ui_edges_autopilot` 在隐藏桌面覆盖：本次 hidden desktop 已实际执行、实际跳过 0 条用例，普通无 Tk 环境才按台账 skip。
- 未跑默认冒烟与全量 `run_selftests.py --all --safe`（卡面未列；合并轮出口 CI 会跑）。
- 产品/测试现场为上一 attempt 成果，本轮只读核对未重写；先红后绿证据沿用卡面背景（改前 6 红、改后 113 绿），本轮未复跑改前。

## 待文档同步（DOC-S11 车道在改，本卡不动）

`程序/docs/stages/S11_配音与字幕.md` 以下位置与新行为不一致，建议由 DOC-S11 或后续文档轮同步：

- REQ-S11-12（约 22 行）：「整段按台词＋设置签名复用已有成品，不重复扣费」宜补「请求号＝签名＋尝试序号，尝试账存 `整段配音尝试.json`；上次结果未知重发前须用户确认，取消不发」。
- DES-S11-12（约 81 行）：整段链路 `script_signature → reusable/publish` 宜补 `reserve_tts_full_track`／`synthesize_tts_full_track` 与尝试账状态（sending／failed／unknown／done）。
- IF-S11-07／IF-S11-21（约 123／135 行）：`整段配音.json` 的 `file` 字段口径由绝对路径改为相对音频目录文件名（旧绝对路径仍可读、失效退回同名文件）。
- UX-S11-02（约 197 行）：「台词音色未变直接沿用」宜补「上次结果未知时先弹确认，取消不发、不产生新请求」。

## 提交

- 本文件随 `dev.py commit` 同批提交；正式 evidence 由提交工具生成 `tasks_round/evidence/R4241.json`，commit hash 见交付报告。
