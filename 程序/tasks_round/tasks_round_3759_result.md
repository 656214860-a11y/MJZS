# R3759 结果：D 恢复与连续使用取证轮（任务书执行轮）
<!-- round-evidence: {"commit_base": "ba998374", "credential_hits": 0, "evidence_sha256": "c6ce2621848fe290", "exit": 0, "failed": 0, "passed": 49, "round": 3759, "tests": "run_selftests.py -k request_ledger model_metering"} -->

- 轮次类型：任务书执行轮（D 维恢复与连续使用取证）。纯取证＋文档轮，无产品代码改动（新增取证脚本 `scripts/acceptance_recovery_probe.py`、`scripts/acceptance_recovery_worker.py` 除外）。
- 是否跑测试：跑了。`acceptance_recovery_probe.py` 9/9 检查通过（隐藏桌面三进程实跑）；`smoke_test.py` 9/9；`run_selftests.py -k request_ledger model_metering` 49 条全绿；服务端 `D:\漫剧服务端` `pytest tests/test_offsite.py tests/test_ops.py` 13 条通过（含异地加密上传→取回→恢复演练与 SQLite 备份恢复演练）。
- 积压是否下降：是——验收台账 D 项本机恢复与连续使用链转「通过」；服务端异地备份恢复因管理面不可达记「未测（原因）」，不冒充通过。

## 1. 三问

1. **什么类型轮**：任务书《桌面与云服务架构及全链路验收任务书》执行顺序 D 项「恢复与连续使用」——可丢弃项目上验证强退、重启、已采用成果保全、待核实请求处理与最新可恢复时间点；服务端异地备份恢复在隔离条件下取证或记录阻塞。
2. **是否跑测试**：跑了——桌面恢复链探针 9/9、冒烟 9/9、台账域单测 49 条、服务端备份/异地测试 13 条。
3. **积压是否下降**：是——D 项从「待验」转为「通过（本机恢复链）＋未测（异地备份恢复·管理面不可达）」。

## 2. 取证方法（隔离、可复现、零新增产品依赖）

- **探针**：`scripts/acceptance_recovery_probe.py`（父进程：假供应商＋进程管理＋证据汇总）＋ `scripts/acceptance_recovery_worker.py`（隐藏桌面子进程，`gui_hidden.py` 包装，与 A 轮同一 Desktop 实例化路径）。证据 `tasks_round/evidence/R3759/`。
- **场景链**（单一可丢弃项目 `acceptance-recovery-*/p`，三个独立 OS 进程）：
  1. `adopt`：Desktop 打开项目 → 发送创意稿 → 假供应商回「# 项目设定」阶段稿 → 发「继续」→ 模型推进 →「项目设定」确认落盘（含确认快照）→「剧本大纲」阶段稿待确认 → 进程正常退出。
  2. `hang`：新进程打开同项目 → 发「继续」→ 台账出现 `reserved` 预留且供应商 SSE 请求在途（首块已达）→ 父进程 `os.kill(SIGTERM)` 强杀 worker（TerminateProcess，exit=15）。
  3. `verify`：再开新进程打开同项目 → 空等 8 秒观察窗（核对无自动重发）→ 手动再发「继续」→ 陈旧 reserved 按既有清扫规则转 `unknown`、新请求正常结算、「人物设定（角色卡）」阶段稿产出并推进「剧本大纲」确认。
- **时间压缩**：夭折请求的 `reserved` 按生产规则需等 `REQUEST_RESERVED_STALE_SECONDS=1800`s 才清扫；verify 进程经 `--stale-seconds 2.0` 仅在本进程内存压缩该常量（生产默认不变），走的仍是 `_sweep_stale_reserved` 同一代码路径，由真实重发授权事务触发并落盘。
- **异地备份**：本机出口对 22/8000/8001/8443 呈「TCP connect 成功、协议数据超时」透明代理特征（`network_probe.json`：22 无 SSH banner、管理端口 HTTP GET 无应答；443 `/v1/meta` TLS+GET 200 正常）。SSH/管理面不可达 → 远端取回异地备份恢复**未测**；以服务端本地 `test_offsite.py`（6 条：加密往返/篡改检出/上传→取回→恢复演练/坏凭据/ETag/CLI）＋`test_ops.py`（7 条：含 `test_backup_restore_drill`）13 条通过作部分替代证据，输出存 `service_backup_tests.txt`。

## 3. 结果摘要（9/9，明细见 summary.json）

- **强退点**：剧本准备「继续」推进请求在途——供应商 seq3 SSE 首块已发、正文未完；worker pid 42332 被 `os.kill(SIGTERM)` 杀死（proc returncode=15），台账该请求 `15b64f73…→6a9b7d94…`（两轮 request_id 不同，取末轮）在杀前快照为 `state=reserved, money_state=reserved`（`ledger_at_kill.json`）。
- **重启与恢复耗时**：杀进程 → verify Desktop 就绪（观察窗开始）`recovery_seconds=2.606`；adopt 6.3s／hang 3.4s／verify 13.1s（含 8s 观察窗）。
- **已采用成果保全**：`项目设定`（sha256 `e5b7b72a…`）与 `剧本大纲`（`a6d73b7e…`）两份已确认阶段稿在 adopt→kill→verify 三点 manifest 哈希逐一致（`manifest_*.json`）；`preparation_state.json` 确认位无损。
- **待核实请求处理**：被杀请求终态 `state=unknown, mode=unknown, money_state=unknown, unknown_via='stale-reserved'`（`ledger_final.json`），金额保留为未知不计 0；同事务内新请求 seq4 正常 `settled/estimated`。
- **无自动重发、无假成功**：verify 阶段供应商请求恰为 1 笔（seq4＝人工重发，`verify_phase_requests`）；被杀的 seq3 在供应商侧 `finished=None`（连接随进程死亡），transcript 中该轮「继续」无 assistant 回复、无阶段稿落盘。
- **最新可恢复时间点**：项目文件即时落盘（采用稿/台账随事务提交），台账另有每日 `.bak` 快照；本探针验证「重启后状态＝强杀前最后落盘点」，无半成品文件残留。
- **人工介入步骤**（探针全自动等价）：重开应用 → 打开同一项目 → 剧本页重发「继续」→ 陈旧 reserved 自动转 unknown，无需人工对账即可继续制作。
- **连续使用**：verify 会话在同一项目上完成「打开→观察→重发→下一阶段稿→确认推进」全链路，证明恢复后可直接继续制作。

## 4. 未测／限制（如实记录）

- **服务端异地备份恢复＝未测（管理面不可达）**：22/8000/8001/8443 TCP connect 成功但协议层超时/无 banner（`network_probe.json`，与 R3707 对齐结论、R3739 B 轮一致）；443 应用 API 正常。恢复演练需 SSH 或管理面可达环境，建议在具备该条件的机器上按 `D:\漫剧服务端\scripts\offsite.py` fetch→decrypt→integrity 流程补测。
- **时间压缩为探针内声明**：`stale-seconds=2.0` 只在 verify 子进程内存生效，生产 `REQUEST_RESERVED_STALE_SECONDS=1800` 未改；清扫路径与生产一致，但「真实等待 30 分钟」未做（无必要，机制同一）。
- **强杀方式**：`os.kill(SIGTERM)`→Windows TerminateProcess（exit 15），属强制终止；未覆盖断电/蓝屏级场景（台账 `.lock` 字节锁由 OS 在进程死亡时自动释放，已由 verify 成功取证旁证）。
- 探针项目为临时目录（`%TEMP%\acceptance-recovery-*`），可随时清理；正式安装与真实项目零接触。

## 5. 台账与任务书同步

- `桌面与云服务验收台账.md`：D 行转「通过（R3759）」，§5 填写本记录，页脚加 R3759 更新行；异地备份子项在 §5.2 标「未测（管理面不可达）」。
- 任务书 D 项要求「交由产品负责人定恢复目标」——本机恢复链证据已备，异地恢复目标待 SSH 可达环境补测后由负责人裁决。
