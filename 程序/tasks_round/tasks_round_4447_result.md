# R4447：SANHU-FIX-1B 三虎半自动档轮询放行与无人值守开关失败回报（S-01 / S-15 第一条）
<!-- round-evidence: {"commit_base": "c561c2e4c", "credential_hits": 0, "evidence_sha256": "3b26d0939194da01", "exit": 0, "failed": 0, "passed": 160, "round": 4447, "tests": "run_selftests.py -k sanhu_mode pet_agent desktop_automation_service copy_rules"} -->

- 轮次类型：§3.2 修复轮（卡面 SANHU-FIX-1B W2；溯源 SANHU-AUDIT 报告 S-01 高、S-15 第一条）。
- 测试跑了吗：跑了。先红（摘要见下）→ 修后 `sanhu_mode` 24 条全绿；卡面验收命令 196 条中 194 条绿，仅剩 2 条基线过期红（`ui_edges_autopilot`，举证为无关项见末节）；架构门禁 708 条全绿（改前 704 绿＋4 红均为本轮登记滞后，修后 0 红）。默认冒烟与全量 `--all --safe` 未跑（卡面未列）。
- 欠账少了吗：未新增欠账。`pet_ui_stages.py` 棘轮登记按实测 1144＋15 下调为 1159（原登记 1161→1159，文件 1201 行在 1202 上限内）；覆盖率基线随新模块刷新为 688/134。
- 车道：`codex/sanhu-fix-1b`，基线 c561c2e4。不合入、不 push。

## 先红原文摘要（改前 `run_selftests.py -k sanhu_mode`，exit 1；新用例按设计失败）

`SanhuSemiPollTests` 新用例在基线上红，失败形态与卡面缺陷逐条对应：

- `test_semi_unattended_start_then_final_poll_allowed`：`AssertionError: False is not true`——`_execute_unattended_stage('final','auto')` 已回报「已自动开始」，但 `should_auto_run('final')` 被 `mode != 'auto' → return False` 拦死（S-01 根因，`pet_ui_stages.py:823-831`）。
- `test_semi_free_poll_group_all_allowed`：`AssertionError: False is not true`——半自动下 6 项免费轮询（auto_adopt／final／keyframe／previs／edit／delivery）的 `should_auto_run` 全为 False。
- `test_semi_paid_poll_group_runs_only_when_granted`：`AttributeError: 'PetStagesMixin' object has no attribute 'grant_paid'`。
- `test_semi_submit_and_review_never_run`：同上 `AttributeError`（grant_paid 尚不存在）。
- `test_switch_write_failure_reports_undispatched_and_stage_failed`：`AssertionError`——写 `UNATTENDED_SWITCH_SETTERS` 失败仍返回「已自动开始…」而非「阶段未派发：…」（S-15 第一条，`desktop_pet_bridge.py` 原 except 静默 pass）。

`test_hint_level_allows_no_poll` 与 `test_auto_level_still_reads_the_sanhu_variables` 在基线上即绿（行为契约不变项，改后仍绿）。先红逐字输出经隐藏桌面运行确认；上文为各用例失败签名摘要。

## 改了哪几处

- `ui/pet_poll_policy.py`（新增，L4 纯逻辑）：`FREE_SEMI_VARS`（auto_adopt/auto_final/auto_first_frame/auto_previs/auto_edit/auto_handoff 六变量）、`PAID_SEMI_VARS`（auto_asset/auto_video）、`NEVER_SEMI_VARS`（auto_submit/auto_review）；`canonical_var(stage_id)` 经 `pet_ui_support.AUTO_STAGE_VARIABLES` 归一（短 stage_id／process_id／变量名均可）；`allowed(level, mode, stage_id, granted, *, read_auto_var)`——`level=='auto'` 或 `mode=='auto'` 照旧读 `read_auto_var`（全自动行为逐字不变）；`level=='semi'` 时 NEVER→False、FREE→True、PAID→仅当归一变量名或别名命中 `granted`、未登记→False；其余档→False。宿主授权簿记：`grants(host)` 懒初始化 `host._auto_granted`（不落盘）、`grant_paid`／`revoke_paid`／`clear_paid_grants`。
- `ui/pet_ui_stages.py`（+14/-15，文件 1201 行 ≤1202 上限）：`should_auto_run` 委托 `pet_poll_policy.allowed(self.agent.level, self.mode, stage_id, pet_poll_policy.grants(self), read_auto_var=…)`，读三虎变量与异常口径不变；`grant_paid`／`revoke_paid`／`clear_paid_grants` 一行式委托 policy（保持卡面方法契约且文件不膨大）；`_auto_stage_completed`／`_auto_stage_failed` 先 `revoke_paid(stage)` 再 `auto.done`；`set_level`／`set_paw_level` 任一切档 `clear_paid_grants()`。`set_paw_level` 半自动走 `mode='manual'` 的行为不改。
- `ui/desktop_pet_bridge.py`（+2/-2）：`_execute_unattended_stage` 中 `UNATTENDED_SWITCH_SETTERS[name](self.root, True)` 抛 `(OSError, ValueError, KeyError, TypeError)` 时返回 `'阶段未派发：'+str(exc)`——`start_stage` 见此前缀发 `stage.failed`（pet_ui_stages.py:298 既有机制），不再谎报「已自动开始」。
- `tests/test_sanhu_mode.py`（+106/-1）：新增 `SanhuSemiPollTests` 7 条用例覆盖卡面 6 条边界行为（真 Pet ＋ `_BooleanFlag`，不建窗口；沿用既有 `set_paw_level` 真路径）。
- `tests/architecture/_layers.py`（+4/-0）：L4 登记 `pet_poll_policy`；同层边 `('pet_ui_stages','pet_poll_policy')`、`('pet_poll_policy','pet_ui_support')`。
- `tests/architecture/test_complexity_ratchet.py`（+1/-1）：`PetStagesMixin` 登记 1161→1159（实测 1144＋15 余量；初稿曾到 1223 超 1202 文件上限，授权簿记下沉 policy 后回落）。
- `维护记录/覆盖率基线.json`：15 目标全量重测刷新 687/133→688/134（含 `tests.test_publication_recovery`）。
- `runbook.md`（+2/-2）：§11 两处口径同步 687→688、133→134、554 未触达不变，注明「随新增 `ui/pet_poll_policy.py` 刷新」。

## 验收命令输出尾部原文

命令 1：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k sanhu_mode pet_agent ui_edges_autopilot desktop_automation_service copy_rules`（目录 程序，exit 1——仅 2 条基线过期红，见末节举证）

```
共 196 条用例，47.3 秒；2 个文件有红
最慢 10 路工作单元：test_ui_edges_autopilot#3 38.7 秒 / 14 条 …
实际跳过 0 条用例：本机没有任何登记位被跳过
### test_ui_edges_autopilot（1 条红）
test_adopt_skips_adopted_without_confirm … IndexError: list index out of range
### test_ui_edges_autopilot（1 条红）
test_per_line_tts_stop_and_line_progress … AssertionError: 4 != 2
```

剔除无关项后定向组：`run_selftests.py -k sanhu_mode pet_agent desktop_automation_service copy_rules`（exit 0）：`共 160 条用例，8.6 秒；0 个文件有红 / ALL TESTS PASSED`（含 sanhu_mode 24 条、pet_agent 93 条、desktop_automation_service 15 条、copy_rules 18 条、pet_agent_error_wiring 10 条）。

命令 2：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（目录 程序，exit 0）

```
Ran 708 tests in 268.232s
OK
✅ 架构治理测试：tests/architecture
```

git diff --numstat（工作树 vs c561c2e4）：

```
2	2	程序/runbook.md
4	0	程序/tests/architecture/_layers.py
1	1	程序/tests/architecture/test_complexity_ratchet.py
106	1	程序/tests/test_sanhu_mode.py
2	2	程序/ui/desktop_pet_bridge.py
14	15	程序/ui/pet_ui_stages.py
42	36	程序/维护记录/覆盖率基线.json
```

另有新增未跟踪文件 `程序/ui/pet_poll_policy.py`（+73）与本结果文件。

## 决定题 1 按建议 A 执行口径

付费步骤先问授权：半自动档下 assets／video 两条付费轮询默认不放行，仅在本次运行经 `grant_paid` 显式授权后放行；阶段完成（`_auto_stage_completed`）、失败（`_auto_stage_failed`）与任何一次 `set_level`／`set_paw_level` 切档自动撤销；`auto_submit`／`auto_review` 在半自动恒不放行（`NEVER_SEMI_VARS`），即使调用 `grant_paid` 亦不例外。授权集合只存内存不落盘，与用户 11-23「付费步骤先问授权」裁决一致。

## 待文档同步

- 覆盖率基线与 runbook §11 已同步（688/134/554）。
- 分支轮不改 `project_status.md`（runbook §12：分支结果由合并轮统一推进状态）。

## 无关项举证（2 条基线过期红，非本卡引入，未改）

1. `test_adopt_skips_adopted_without_confirm`（test_ui_edges_autopilot.py:2188）：断言页内存在「手动采用分镜」按钮。R4380（`7b2354c9e`，初步分镜单编辑器改版）已删除该页全部顶部按钮、采用收进右键菜单（`ui/storyboard_files.py:636-637` 类注释「取消顶部按钮与双表…采用收进编辑器右键菜单」）；同基线 `test_board_assets_buttons.py:134,207-209` 明文断言该按钮必须为 0 颗。此用例未随改版同步 → 基线即红。
2. `test_per_line_tts_stop_and_line_progress`（test_ui_edges_autopilot.py:1030）：断言停止后 `len(states)==2`。R4346（`cf908c6d8`）把 `run_lines` 改为批次开始即整批落盘全部句子（`domain/tts_api.py:677-681`），时间轴清单恒为 4 条 → 基线即红。
   两轮引入均晚于该测试文件最近一次绿凭据（R4315，commit_base b52a39ef1，36/36），早于本车道基线 c561c2e4。正交性佐证：本工作树无 `程序/配置/宠物/配置.json`（`infra/config_snapshot.py:12`），GUI 用例中 `pet.agent.level=='hint'`、`mode=='manual'`，本卡策略对该组合返回 False，与旧行为逐位一致；且两条用例不经过 `should_auto_run`／`_execute_unattended_stage` 路径。按卡注「如顺跑须单列无关项，不改无关测试」，留待后续轮次同步测试契约。

## 未验证项与卡外发现

- 全量 `--all --safe` 与默认冒烟未跑（卡面未列命令；合入出口 CI 覆盖）。
- `grant_paid` 的宿主侧调用方（谁向用户问授权后调用）不在本卡范围，留待后续轮接线。
- 本机 `运行环境` 不在本工作树内，测试走主工作区解释器；`程序/logs` 未读（卡面禁止）。
