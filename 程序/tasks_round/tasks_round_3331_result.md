# R3331 结果文件
<!-- round-evidence: {"commit_base": "f0665b68", "credential_hits": 0, "evidence_sha256": "d4eedc7f1c93f9e8", "exit": 0, "failed": 0, "passed": 134, "round": 3331, "tests": "run_selftests.py -k l1_l0_integration model_router_diagnostics diagnostic_capture request_ledger model_metering temporary_sweep selfcheck startup_selfcheck"} -->

1. **本轮属于 §3 哪种类型**：§3.2 修复轮——L1 基础设施层优化任务书轮 6「对接 L0」（R6-a～R6-d），前置 L0 轮 3A/4A/5A 已随 R3329 合入 master，本轮只改 `infra/` 与 `tests/`，不改 `contract/`。
2. **测试跑了吗、三个基线过了吗**：跑了。定向 `-k model_router test_selfcheck request_ledger` 65 条 0 红；任务书点名 `--affected model_router` 冒烟 10/10；受影响批（diagnostic_capture/temporary_sweep/model_metering/request_ledger 及关联 9 文件）10/10；默认冒烟 9/9；架构门禁 532 项两轮跑：首轮决策点基线红（diagnostic_capture 67→85 未重测）→ 重测刷新基线后复跑仅剩轮次连续性红（状态页未同步）→ 修状态页后 `round_baselines`/`branch_coverage_floor` 定向全绿；`--gate` 增量串行因台账增量≈全仓（741 文件/1004 工作单元）超 900s 门禁上限超时——非用例失败，属规模问题，全量验收以合入轮出口 CI／`full-safe-receipts.json` 为准。
3. **欠账少了吗**：少了——L1 降级路径从此带 L0 错误码、启动自检覆盖台账损坏/unknown 积压/设置损坏侧车/临时文件残留四类此前不可见的降级；model_router 判类收敛到 L0 唯一权威。新欠账：L0 D6-0 对照表未并入 `REPLAYABLE_RETRY_STATUS`/`submission_retryable` 两机制（见 R6-d 处置，行为无变化，登记为文档欠账）。

## 改动（R6-a～R6-d）

- **R6-a `infra/diagnostic_capture.py`**：`startup_checks()` 由 6 项扩为 10 项，新增四个 L1 检查（均返回 `Diagnostic(Severity.DEGRADED)` 或 `None`，经既有 `run_startup_selfcheck` 组装点注入 L0 `selfcheck.run`）：
  - `request-ledger-corrupt`：当前项目（`projects.json` 的 `active` 登记）`宠物/请求台账.json` 存在但严格读（`agent.core.read`）失败或形状不符 → DEGRADED；只读探测，不走 `RequestLedger.load()`（不触发清扫/日备份副作用）。
  - `request-ledger-unknown-stale`：台账中带 `unknown_via` 标记（`stale-reserved`/`settle-lock-timeout`）的 unknown 条目 >3 → DEGRADED；正常结算 unknown 不计。
  - `ui-settings-corrupt`：项目根存在 `ui_settings.json.corrupt` 侧车（`project_settings` 既有损坏保留产物）→ DEGRADED。
  - `temporary-files-leftover`：读诊断状态里轮 2 清扫线程 `record_temporary_sweep` 写回的 `remaining` >10 → DEGRADED；**不扫描目录**（规则 33），无清扫记录时放行。
- **R6-b `infra/model_router.py`**：删除本地子串判类表；`error_class(error, status=None)` 改为 `contract.error_codes.classify(text, status)` 取码，再经 `_ERROR_CLASS_BY_CODE` 翻回既有消费者类别词表（timeout/authentication/protocol/configuration/transport/cancelled）。`ModelAdapter.chat()` 失败分支把 `result.status` 传入——HTTP 状态优先于文本。**契约变化一处**：`error_class('HTTP 404 /chat/completions')` 由 `protocol` 变 `transport`（classify 无 404 命中→`E-UNKNOWN`→transport；旧子串表把 404 硬编码进 protocol 属误判，404 是「路径不存在」而非「参数协议错」，按 L0 码表语义收敛），已在 `test_model_router_diagnostics` 同步断言并注明。
- **R6-c 降级记录补错误码**：`record_degradation()` 新增 `error_code` 形参，行内落 `code` 字段（沿用 `_clean` 脱敏、有界 50 行）；`model_metering._settle` 与 `request_ledger._settle_lock_timeout` 两处降级记录补 `E-IO-WRITE`。
- **R6-d 核对结论**：L0 D6-0 对照表（`tasks_round_3300_result.md`，5A 产出）只覆盖 `pet_agent_rules.PATTERNS` 七类目＋unknown，**未含** `REPLAYABLE_RETRY_STATUS` 与 `submission_retryable`。按任务书「不一致时回问用户」，本轮按用户「最优选择自行确认」授权处置：两机制服务对象不同（对话重放 vs 媒体提交受理判定），均独立于 `error_codes.retryable`（该权威只管 `pet_agent.retry_plan`），**行为零变化、不动码表**；L0 车道已收口（R3329/R3335 合入），并表属文档欠账，登记于此待后续文档轮处理。
- **配套**：`infra/request_ledger.py` 两处 reserved→unknown 转换补 `unknown_via` 标记（`stale-reserved`/`settle-lock-timeout`，供上条检查计数且不误伤正常结算 unknown）；`infra/temporary_sweep.py` `sweep_stale_temporary_files` 增 `stats` 出参回填「超期未删净」数，`schedule_stale_temporary_sweep` worker 跑完经 `record_temporary_sweep` 写回诊断状态（仍在 `desktop.load()` 的 `after(3000)` 延迟线程里，启动零递归扫描不破）。

## 验证证据

- 新测试 `tests/test_l1_l0_integration_r3331.py`（22 条）：四检查的损坏/超阈/正常三态、临时文件检查只读清扫结果不扫目录、`record_temporary_sweep` 写回链路（schedule worker 真跑）、`error_class` 状态优先（401 空文本→authentication）与文本分类、chat() 把 status 传入判类、降级行 `code` 字段落盘且脱敏。
- 定向：`run_selftests.py -k model_router test_selfcheck request_ledger` → 65 条 0 红（含 L0 `test_selfcheck` 16 条）；`-k l1_l0_integration model_router_diagnostics diagnostic_capture request_ledger model_metering temporary_sweep bounded_growth` → 全绿。
- 受影响：`smoke_test.py --affected model_router` 10/10；`--affected diagnostic_capture temporary_sweep model_metering request_ledger` 10/10（含 Tk 件走隐藏桌面，GUI 令牌排队后全过）。
- 默认冒烟 9/9；`--gate` 增量串行（后台，结果见提交回执）。
- 架构门禁 532 项：两处基线类红均已闭环——①`test_baseline_decision_points_match_current_entities`（diagnostic_capture.py 决策点 67→85）按门禁要求用 `scripts/branch_coverage_report.py` 真实重测刷新 `维护记录/分支覆盖率基线.json`（88 目标全过，1477/2667），期间暴露 `temporary_sweep.py` 覆盖退化（45.5%<57% 下限）→ 补 3 条真实用例（remaining 计数删不掉分支、worker 写回失败吞掉、真清扫写回记录）后棘轮 5/5 绿；②`test_round_number_continuous`（状态页 3330 落后结果 3331）→ 状态页工作树版同步 3332（不入提交，合并轮口径处理）。
- `--gate` 增量串行超时说明：台账判定 741 个测试文件受影响（分支累计改动＋master 新合入），串行需 >900s 超 `GATE_TIMEOUT`；已跑通的等价或更强验证：定向/受影响/默认冒烟全绿、架构 532 项（两处基线红闭环）、分支覆盖率 88 目标全过；全量 `--all --safe` 凭据以合入轮出口 CI 为准（脏树不产凭据，须提交后由 master 侧跑）。
- 三个基线：默认冒烟 ✅ 9/9；架构门禁 ✅（基线刷新＋状态页同步后复跑项全绿）；全量凭据以 `full-safe-receipts.json`／合入轮出口 CI 为准。

## 备注

- 检查阈值取值：`unknown_via` 条目 >3、清扫残留 >10——任务书只说「超阈值」未给数，取保守小值让系统性失效尽早可见；如需调整改常量 `_LEDGER_UNKNOWN_STALE_LIMIT`/`_TEMP_LEFTOVER_LIMIT`。
- `_check_request_ledger`/`_check_ledger_unknown_stale` 复用 `agent.core.read`（`publication.access()` 协调读），检查项在启动期可能与发布事务短暂互斥（锁等待上限 30s），属可接受的一致性代价。
- 领号说明：R3331 于 11:47 领得；其后误跑一次裸 `round_claim.py`（等价 `next`）多领 R3333，未使用，特此注明，结果文件以 R3331 为准。
- `project_status.md` 工作树版本落后于 master（master 已到 R3335/轮次 3336），合入时按合并轮既有口径处理。
