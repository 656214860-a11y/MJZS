# R3298 结果：L0 契约层防崩溃与协议补齐任务书 · 轮 4B（D4＋D5 兼容接线）
<!-- round-evidence: {"commit_base": "dfaa16a2", "credential_hits": 0, "evidence_sha256": "c4bbc6ab836c9c1f", "exit": 0, "failed": 0, "passed": 321, "round": 3298, "tests": "run_selftests.py -k artifact_schema continuity animatic pet_bus pet_agent broadcaster diagnostic"} -->

## 三问

1. **本轮类型**：任务书轮 4B——兼容轮（接线）。只接 `artifact_schema`／`pet_bus` 的属主读写点与终态事件调用方，不改 L0 契约语义本身。
2. **测试跑了吗、三个基线过了吗**：跑了。定向自检 321 条全绿；`smoke_test.py --affected continuity_ledger animatic_service pet_agent` 10/10 绿；默认冒烟 9/9 绿；架构门禁 502 条中 1 红（`test_round_number_continuous`，工作树状态页陈旧的既有欠账，见下）；未触发全量（任务书标「否」）。
3. **欠账少了吗**：少了。D4 读取侧五态分类已接到全部 9 个登记属主；D5 终态事件已带真实运行序号，跨 run 同文失败/完成不再互吞。

## 前置核对（R0-c）

`git merge-base --is-ancestor codex/whitelist-framework master` → **已合入**（master 现至 R3296/R3297 段）。轮 4B 前置解除，本轮开工合规。领号：`round_claim.py` → **R3298**（worktree `dsh-5158b800-34ae`，分支 `codex/wip-R3259`）。

## 实现决策

### D4-c/D4-d：属主读取点 classify＋G8 处置

- `artifact_schema` 新增内存计数 `note_read_state(kind,state)`／`read_state_counts()`（L0 不能 import L1，所以计数落在本模块）；`infra/diagnostic_capture` 在 `_save_state` 并入 `artifact_versions` 段、`export()` 前先 `flush_artifact_states()` 收走。读取路径零写盘零提示。
- 九个登记属主全部在自己的读取点调 `classify` 并计数：`desktop_queue`（`desktop_automation_service._load`）、`continuity_ledger`/`continuity_issues`（`infra/continuity_ledger.read/read_issues`）、`animatic_manifest`（`domain/animatic_service.evidence`）、`artifact_lineage`（`record/_entry/affected`）、`recon_card`（`recon_service.load_card`）、`edit_records`/`edit_habit_rules`（`edit_habits.load_records/load_rules`）、`desktop_send_ledger`（`load`）。`file_cache.read_json` 签名未动，未新增 `def read_json`。
- `legacy`/`missing` 照常使用只计数；`future` 可读。属主写入口拒写：`continuity_ledger.publish_bundle/sync_issues/decide_issue`、`animatic_service.build_bundle`（发布前守卫）、`stage_animatic_gateways.confirm_animatic`、`desktop_automation_service._save`、`edit_habits._save_records/_save_rules`、`desktop_send_ledger.record`（跳过更新＝下次整份重发，安全方向）、`recon_service.save_card`（返回 `UserError`）、`artifact_lineage.record`（跳过登记）。
- 「发一次【警告】」落在新 `infra/broadcaster.warn_once(key,text)`：进程内按 key 去重，向 `logs/sanhu_progress.log` 追加一行 `【警告】…`（绝对路径），失败静默返回 False。**不走 `Broadcaster` 类**——`test_event_bus_boundary` 只允许 desktop/pet_ui 实例化它做用户可见播报；warn_once 是属主写路径内部告警，前缀仍出自本模块 `PREFIX_PATTERNS`。
- **L0 边界说明**：`artifact_lineage` 是 L0，不能 import L1 `broadcaster`，future 账本只能「跳过登记＋分类计数进诊断账本」，没有用户可见警告——登记为边界欠账（见下）。

### D4-e：写方双写

- `continuity_ledger`（台账＋问题表）、`animatic_service` 清单、`artifact_lineage` 账本、`desktop_queue` 排队记录改走 `artifact_schema.stamp()`：正常写入同时含 `schema_version` 与旧键 `version`（旧版程序仍能读）；`recon_card`/`edit_*`/`desktop_send_ledger` 登记 `legacy=None`，只写 `schema_version`（本就无旧键可保）。

### D5-d：终态事件运行序号

- `contract/pet_bus`：`Bus.begin_run(stage)`／`current_run(stage)`（逐阶段递增序号）＋ `with_current_run(bus, kind, payload)`——只对 `TERMINAL_EVENTS` 且带 `stage`、未显式传 `run` 的负载注入当前序号；`current_run==0` 不注入，保持旧去重口径。
- 注入点收敛在两处受控转发：`pet_agent.Agent._emit` 与 `ui/pet_ui.Pet._emit` 自动补 run，覆盖全部 `pet._emit('stage.failed'/'stage.completed'/'script.completed'/…)` 调用方（desktop 页、pet_ui_stages、stage_handler_registry._fail、stage_completion_service 注入的 emit 回调）。`skill_orchestrator` 在 `_run_skill` 入口 `begin_run` 并显式给 `stage.started/script.completed/stage.completed/stage.failed` 传 `run=`；`stage_handler_registry.start()`（手动/自动/三虎唯一启动入口）在门禁前先 `begin_run`，门禁失败也带本轮序号。进度类事件不带 run（`stage.paused`/`stage.executing`/`notify.*` 等照旧）。
- **emit_status 评估**：`Bus.emit_status`（4A 已交付）保留；本轮逐一核对 `emit_verified_completion`、`Agent.fail`、`stage_handler_registry._fail` 等调用方——没有任何一处按 delivered/suppressed/failed 分支改变行为（suppressed 本就等于真重复），故无调用方改用，符合「只让确需区分的调用方改用」。
- 效果：用户再次点运行 → `begin_run` 序号 +1 → 同文 `stage.failed` 幂等键不同 → 状态机订阅者再次收到并可离开旧结算态；同 run 内重复上报仍去重。

## 测试证据

- 新增 `tests/test_artifact_schema_wiring.py`（14 条）：九属主 legacy/missing 读、future 读写拒、双写断言、分类计数。
- `tests/test_pet_bus.py` +122 行：`begin_run/current_run`、`with_current_run` 注入规则、跨 run 二次失败双送达、同 run 重复仍压制、`Agent._emit` 自动注入（终态带 run／进度无 run／二次失败再达订阅者）。
- `tests/test_broadcaster.py` +`WarnOnceTests`（2 条）：同键单行去重、写失败静默且占位。
- `tests/test_artifact_schema.py` +`ReadStateCounterTests`（2 条）：计数聚合、副本隔离、存储破坏静默降级（覆盖两个 try 的 handler 方向）。
- 命令与结果：
  - `run_selftests.py -k artifact_schema continuity animatic pet_bus pet_agent` → **272 条全绿**（修 `pet_bus.py` 门面漏导 `with_current_run` 后复跑）。
  - `run_selftests.py -k artifact_schema continuity animatic pet_bus pet_agent broadcaster diagnostic`（修复后复跑）→ **321 条全绿**。
  - `smoke_test.py --affected continuity_ledger animatic_service pet_agent` → **10/10 绿**（门禁 138 秒）。
  - `smoke_test.py` → **9/9 绿**。
  - `smoke_test.py --affected <21 关键词广选>` 首轮选中 206 文件/3832 条超 900 秒门禁超时；孤儿进程跑完 **3832 条仅 1 红**（`test_lane_merge_queue`，见环境欠账），其余全绿——覆盖面证据保留。
  - `smoke_test.py --architecture` → 502 条，**1 红**（见下）。

## 架构门禁对比基线

改前首轮 4 红 → 修复后 **1 红**：

| 失败 | 处置 |
| --- | --- |
| `test_broadcaster_is_text_log_not_cross_module_state_bus`（broadcaster.py:68） | warn_once 改为模块内自含日志追加，不再实例化 `Broadcaster` → 绿 |
| `test_no_new_silent_exception_handlers`（artifact_schema:217、diagnostic_capture:89） | diagnostic_capture 改用 `app_logging.swallowed()`；artifact_schema 属 L0 不能引 L1，按 platform_tools 先例在 `ALLOWED` 登记 1 处并注明理由 → 绿 |
| `test_baseline_decision_points_match_current_entities`（broadcaster 4→6） | 按工具口径真实重测：`scripts/branch_coverage_report.py` 以基线 81 个定向目标＋新增 `tests.test_artifact_schema_wiring` 共 82 个目标重跑两轮（1540 条用例全过），刷新 `维护记录/分支覆盖率基线.json`；broadcaster 50.0%(3/6)、artifact_schema 78.6%(33/42)、artifact_lineage 68.2%、continuity_ledger 45.3%、pet_bus 53.1%、diagnostic_capture 46.3%，全部不低于下限 → 绿 |
| `test_round_number_continuous`（3234 != 3287） | **既有欠账，非本轮引入**：本工作树 `project_status.md` 停在 R3233 时代（master 已至 R3297）；状态页仅 master 可提交，工作树内无法修。改前即红，与本次 diff 无关 |

## 环境欠账（非本轮引入，如实记录）

- `test_lane_merge_queue`「起不来」：`round_claim.git_common_dir()` 以 `text=True` 起 git 子进程，GBK 区域设置下解码 git 的 UTF-8 中文路径输出抛 `UnicodeDecodeError` → `stdout=None` → `.strip()` 崩。`PYTHONUTF8=1` 复跑 **10/10 绿**。本轮未改 `round_claim.py`（范围外），仅记录；同因 `round_claim.py` 裸跑也需 `PYTHONUTF8=1`。
- `smoke_test.py --affected` 广选超时：900 秒门禁包装器超时属选型过宽，非产品缺陷；任务书建议的窄口径 `--affected continuity_ledger animatic_service pet_agent` 已绿。

## 剩余欠账／边界

- `artifact_lineage`（L0）future 账本拒写但无用户可见【警告】（不能 import L1 broadcaster）；以分类计数进诊断账本承接，是否补属主侧告警待下轮评估。
- `desktop_send_ledger` 对 `missing` 版本台账按「无记录」处理（`validate` 口径未变，安全方向＝整份重发）；分类仍计数。
- `emit_status` 无调用方改用（见上评估）；能力已在 4A 就位。
- `pet_ui_stages.report_done` 等手工完成路径不 `begin_run`，沿用最近一次运行序号——同文同 run 的极端重复仍可能去重，属可接受口径（文本含完成说明，实际撞键概率极低）。
- 任务书收尾的《任务完成文件》须全部轮次完成后才输出，本轮不出。

## 提交

- 轮次：**R3298**；提交信息 `R3298: L0契约层任务书轮4B——产物版本五态接线…＋终态事件运行序号接线…`；证据 `tasks_round/evidence/R3298.json`（targeted 321 条全绿、credential_hits 0）。
- commit hash 以 `git log` 为准（提交对象不含自身哈希）；本结果文件随该提交入库。
