# R3709 结果：A 可观测性取证轮（任务书执行轮）
<!-- round-evidence: {"commit_base": "7e638057", "credential_hits": 0, "evidence_sha256": "2348e890bc17a9c5", "exit": 0, "failed": 0, "passed": 8, "round": 3709, "tests": "run_selftests.py -k writing_stream model_metering"} -->

- 轮次类型：任务书执行轮（A 维可观测性取证）＋随验最小修复（§3.2 修复轮要素）。取证主体为真实 Desktop/Tk 链路三跑；两处产品缺陷在取证中定位并做最小根因修复。
- 是否跑测试：跑了。默认冒烟 `python smoke_test.py --affected writing_stream model_metering` 10/10 通过（内含定向门禁 `run_selftests.py -k writing_stream model_metering` 25 秒 0 红，覆盖 test_writing_api／test_model_metering／test_fault_injection_chain／架构边界）；新增回归用例随定向门禁同绿。架构门禁与全量安全自测本轮不声明（无结构治理改动；合入 master 前按 §5 补跑）。
- 积压是否下降：是——A 维「成功/超时/取消」三跑证据全部落盘并通过链路核对；取证中发现的「取消后仍回退普通请求」「尝试元数据在结算重读后丢失」两处缺陷已修复并配回归测试。

## 1. 三问

1. **什么类型轮**：任务书《桌面与云服务架构及全链路验收任务书》执行顺序第 3 步「A 可观测性」——假供应商＋真实界面驱动成功/超时/取消三跑，UI→请求→供应商回执→产物→费用全链路取证并脱敏导出。取证中按失败闭环做了两处最小修复。
2. **是否跑测试**：跑了——冒烟 10/10、定向门禁 0 红、新增回归用例通过；三跑探针本身即端到端实测。
3. **积压是否下降**：是——验收台账 A 项由「待验」转「通过」；两处链路缺陷闭环。

## 2. 取证方法（复用现有，零新增产品依赖）

- 驱动：`scripts/acceptance_chain_probe.py`（本轮新增）——`scripts/gui_hidden.py` 隐藏桌面内实例化真实 `Desktop`，走 `send_message → submit_idea_api_request → stage_execution_service.reply_to_writing → writing_api.reply → WritingRequestAdapter → model_metering.metered(RequestLedger) → model_pool.http_stream → api_endpoints.http_stream → RequestsJsonOpener → 本机假供应商` 全链。
- 假供应商：本机 `ThreadingHTTPServer`，OpenAI 兼容 `/chat/completions`；模型池「自定义」提供方 `base_url` 指本机回环（`normalize_url` 允许 loopback HTTP），`key_env` 仅注入探针进程环境变量 `FAKE_ACCEPTANCE_KEY`，跑完恢复 `配置/宠物/配置.json` 原状。
- 场景：`ok` 正常 SSE；`timeout` 首块后挂起（探针内 `WRITING_REQUEST_TIMEOUT` 覆盖为 15s，与生产 180s 同一 socket read-timeout 代码路径）；`cancel` 慢速流中途调真实 `interrupt_script_agent()`。
- 只读插桩：包装 `model_metering.metered`／`writing_api.chat_streaming`／`WritingRequestAdapter.stream/.chat` 记录 request_id、on_chunk 回调数、错误分类与栈（`debug_trace.log`），不改产品行为。
- 证据：`tasks_round/evidence/R3709/{ok,timeout,cancel}/`——`supplier_log.jsonl`（供应商回执）、`request_ledger.json`、`token_ledger.json`（无独立文件时以台账 `kind=tokens` 行为费用态权威）、`model_events/`（脱敏诊断事件）、`transcript.json`、`artifacts/`＋`artifacts_manifest.json`、`desktop-task-history.json`、`app_log_window.jsonl`、`summary.json`、`debug_trace.log`。

## 3. 三跑结果与链路核对

### 3.1 ok（成功）

- 供应商：seq1 `stream=true` 收讫、9 分片、`finished=true`、`auth_present=true`（凭据经 `key_env` 注入、未落盘）。
- 台账：`70d8d486…` `state=settled`、`money_state=estimated`、`kind=tokens`、`budget_cost=0.000180` CNY（按供应商上报 usage 120+30 token 与验收价表 `acceptance-fake-v1` 估算）；attempts 记 `status=200 wire_api=chat retry_count=0`。
- 产物：回复为合规「项目设定」稿（一级标题＝阶段名、末尾「待确认」），经 `_preparation_step` 验收后发布为待确认草稿 `01剧本准备/自定义/验收假供应商/创意_20261119/项目设定/p_项目设定_自定义_20261119.md`，并归档 `responses/`；`transcript.json` 含 user+assistant 两行。
- 诊断：`model_events/model_diagnostics/20261119_130057_*.json` 记 `ok=true status=200 error_class=''`，仅安全元数据（无正文/密钥）。

### 3.2 timeout（超时）

- 供应商：seq1 `stream=true` 首块后挂起→客户端 15s（探针值；生产同路径 180s）socket 超时；seq2–4 `stream=false` 为普通请求的有界重放（`MAX_REPLAY_ATTEMPTS=3`，各约 15s 间隔）。
- 计量：metered#1 `0d2fd52a…` 流式 15.17s 超时、`on_chunk_calls=0`；按既定规则「未投递任何分片且未取消→退回普通请求」，metered#2 `2cf3e533…` 普通请求 3 次传输重试后 `error_class=timeout` 失败。
- 台账：两条均 `state=unknown`、`money_state=unknown`、`budget_cost=0.267445`（保留额＝输入估算 251061＋输出上限 8192 的预留额）；**不记 0、不冒充成功**。
- 结果：`assistant_replies=0`、无产物采用；诊断事件 `ok=false error_class=timeout usage 全 0`；`chat_streaming` 终态 `ok=False` 如实上抛 UI。

### 3.3 cancel（取消）

- 供应商：seq1 `stream=true` 慢速流（0.4s/块），服务端正常发完；客户端在首个数据行 checkpoint 处被 `ExecutionStopped` 中止，`on_chunk_calls=0`。
- 中断入口：探针等待 `STATE.chunks_sent` 非空后调真实 `d.interrupt_script_agent()`（即 UI「中断」同一代码路径），非模拟取消。
- 计量/台账：`27f8288b…` `state=unknown`、`money_state=unknown`、`budget_cost=0.267445`；**修复后未再退回普通请求**（`cancelled()` 为真时 `chat_streaming` 不再 fallback），供应商仅收到 1 个请求，无重复计费面。
- 结果：`assistant_replies=0`、无产物采用；`desktop-task-history` 记该任务 `state=late reason=cancelled succeeded=false`（迟到结果不回调 UI，符合规则 30）；`transcript.json` 仅 user 行。
- 说明：取消路径在 `_ensure_reply_active` 抛 `WritingCancelledError`，短路于 `_record_model_diagnostic` 之前，故本场景无 `model_diagnostics` 事件——属取消边界设计内行为，费用不确定性由台账 `unknown` 承载。

### 3.4 贯通核对

- request_id 唯一且三处互证：台账 `id` ↔ `debug_trace.log` metered request_id ↔ 供应商 seq 时间戳（台账 `at` 与供应商 `at` 同步到毫秒级，任务创建→授权→供应商收讫顺序一致）。
- 费用三态齐备：`settled/estimated`（ok 实测回报）、`unknown/unknown`（timeout、cancel 不确定用量保留预留额）、无静默免费。
- 脱敏：证据内无 prompt 正文、无生成正文、无密钥；`supplier_log` 仅元数据；`model_events` 仅安全字段；密钥扫描 0 命中。

## 4. 本轮修复（验收中定位的最小根因）

1. **`domain/writing_stream.py`**：流式失败退回普通请求的条件补 `and not (cancelled is not None and cancelled())`——此前「0 分片＋未取消」判据不含取消信号，取消落在流读取窗口内时会多发一次普通请求（早期取证跑次中实测出现 stream→chat 双计量）。回归：`tests/test_writing_api.py::StreamingChatTests.test_cancelled_request_does_not_fall_back`。
2. **`infra/model_metering.py`**：`_record_attempt` 在 `ledger.project` 存在时把 `record_request_attempt` 纳入 `ledger.transaction()`——此前尝试元数据在结算事务重读后被覆盖丢失，台账 `attempts` 为空。回归：`tests/test_model_metering.py::AttemptPersistenceTests.test_attempt_metadata_survives_settle`。

## 5. 阻塞与未测项（如实登记）

- `token_ledger.json`：三个临时项目均未生成独立 Token 台账文件；费用/用量态以 `request_ledger.json` 的 `kind=tokens` 条目为权威（quantities/rates/price_version/currency/budget_cost/money_state 齐全），不视为缺口。
- `debug_trace.log` 为 append-only，含本轮多次探针迭代的历史块（行号差异来自探针版本演进）；`summary.json`/`request_ledger.json`/`supplier_log.jsonl` 为每跑覆盖的权威快照。
- 取消场景无 `model_diagnostics` 事件：取消短路设计使然，已在 §3.3 说明；如需取消也留诊断事件属后续改进项，不影响本轮验收结论。
- B/C/D/E/F 各维未动；SSH 面阻塞结论沿用 R3707 登记。

## 6. 下一步（自动续跑）

- R4（B 安全边界）：测试服 API 级验证——有效/失效会话、权益拒绝、限流、敏感字段遮盖、管理面暴露面、TLS/配置版本；SSH 受阻项保持「未测」。

## 7. 变更文件

- `程序/scripts/acceptance_chain_probe.py`（新增：A 维取证探针）
- `程序/domain/writing_stream.py`（取消不再回退普通请求）
- `程序/infra/model_metering.py`（尝试元数据入结算事务）
- `程序/tests/test_writing_api.py`、`程序/tests/test_model_metering.py`（回归用例）
- `程序/tasks_round/evidence/R3709/`（三跑脱敏证据包）
- `程序/tasks_round/桌面与云服务验收台账.md`（A 项状态与取证记录）
- `程序/tasks_round/tasks_round_3709_result.md`（本文件）

## 8. 提交

- 见文末 `round-evidence` 头与 git 提交回执（`dev.py commit` 自动生成 `evidence/R3709.json` 凭据并盖章本文件）。

---
*R3709 · 桌面与云服务架构及全链路验收任务书 · A 可观测性取证轮*
*下一动作：R4 开始 B 维安全边界 API 级验证*
*基线：冒烟 10/10（含 --affected writing_stream model_metering 门禁 0 红）；架构/全量本轮不声明*
*恢复：读本文件＋验收台账 §2＋`scripts/acceptance_chain_probe.py --help`；证据在 `tasks_round/evidence/R3709/`*
*注意：取消/超时的 `unknown` 费用态为设计内诚实记账，非缺陷；两处修复均有回归用例钉住*
