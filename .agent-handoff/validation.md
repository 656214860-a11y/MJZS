# 当前验证索引

## 最近正式全量
R1624：HEAD 13dea0a92396b5abd2317009caec19dbfad8d6a0，2026-10-17 02:01:23 绿、502 秒、0 红，凭据 round 1624／内容树 bde64b00（`--all --safe` 已含架构门禁）。`.git/full-safe-receipts.json` 与 `.git/auto-full-safe-result.json` 为权威。
历史上一档：R1619（b6863b4）678 秒 0 红；再上是 R1605（e59e513）5346 项、615.7 秒。

## 阶段4 清单执行期（R1627–R1632）证据
- 这几轮改的是 `tests/`、`说明/`、状态页与交接文件：按 §5 不计源码轮，各自只跑定向＋默认冒烟 8/8＋架构门禁（356 项），**没有**各自跑全量，也没有新增全量欠账。
- R1632：定向 7 个文件 70 项 OK（72.5 秒，含新收编的全链 E2E 32.5 秒与 soak 18 秒）、默认冒烟 8/8、架构门禁 356/356（190.9 秒）。
- R1633（T6 本地两条）：定向 `tests.test_perf_batch_queue` 3/3（5.5 秒）、默认冒烟 8/8、架构门禁 356/356；未跑全量。
- R1635（T8 剩余）：定向 `tests.test_selftests` 52/52、条件类站点实跑 219 条用例（1 跳过，见 `程序/outputs/skips_r1635.log`）、默认冒烟 8/8、架构门禁 356/356；未跑全量（沙箱内派生进程被拒，全量须在沙箱外跑）。
- 新增测试文件与用例会进入下一次源码轮的全量：R1624（13dea0a）的凭据不覆盖当前树，不冒称同树全量。

## R1610 清单执行期（R1611–R1626）证据
- R1611–R1623：逐轮定向用例＋架构门禁（345→356 项，各轮报告见 `程序/tasks_round/tasks_round_16*_result.md`）；这些轮**没有**各自跑全量，最终由 R1624 的一次全量统一定性。
- R1624（Q10）：`test_pet_ui` 598 项 OK（76.5 秒）；`test_skill_notes`＋`test_static_names` 22 项 OK；定向门禁 12 个文件 58 项 OK（19.8 秒）；`test_desktop_startup_perf` 14 项 OK；`tests.architecture.test_round_baselines`＋`test_line_endings` 21 项 OK；默认冒烟 8/8；`local_ci exit` 端到端（静态→架构→冒烟）链路实测退出码 1（当时唯一红是欠全量的账簿项）。随后 post-commit 后台全量绿，账簿项自动转绿。
- R1625（Q11）／R1626（Q12）：文档轮，跑 `tests.architecture.test_round_baselines`＋`tests.test_line_endings` 21 项 OK；R1625 另跑默认冒烟 8/8；未跑全量（`.md` 非源码轮）。

## 本次接续四轮（均只跑定向 + 架构门禁 + 默认冒烟）
- R1606（O8）：架构345项164.456秒 OK、冒烟8项通过。
- R1607（O9）：定向 tests/test_seedream_direct.py 22项、架构345项165.697秒 OK、冒烟8项通过。
- R1608（O10）：定向 tests/test_media_publish_streaming.py 3项与受影响回归通过、架构345项165.908秒 OK（首次第四项债务标识因行号下移失配，已同步 point 217→250）、冒烟8项通过。
- R1609（O12）：定向 tests/test_usage_overview.py 11项、架构345项163.673秒 OK、冒烟8项通过。

日志：程序/outputs/r1606-*.log、r1607-*.log、r1608-*.log、r1609-*.log。四轮均未跑全量，不冒称同树全量。

## 未执行
8项真实验收仍按用户延期处理，不由模拟或全量测试替代。历史索引见 [归档](archive.md)。

## 完成性审计（2026-10-16，逐项对当前树复核）
- O1 stage_parallel._claim 无票即抛超时且 worker 不在放行前调用。
- O2 skill_orchestrator 与 stage_execution_service 默认入口均走进程共享许可。
- O3 desktop_automation_service 可恢复队列落盘，含优先级/老化/过期/取消。
- O4 取消与迟到结果持久化并在代次上隔离，不强杀线程。
- O5/O11 task_center_service.project_snapshot 统一 run/task/attempt/remote 标识、分段耗时、原因码与费用。
- O6 model_router 按受理事实分类，仅未受理且可重试时切换并复检预算。
- O7 agent/publication 以持久日志+已提交标记实现崩溃一致发布与恢复。
- O8 desktop_script_pages 经 ScriptPageServices 实例注入 open_path/context_menu。
- O9 native_asset_codec.seedream_provenance 已接入首帧与资产云图。
- O10 agent.core.save_file 按块复制并校验摘要/长度，collect_download_inbox 在发布事务内调用。
- O12 usage_overview.estimate_scenario 缺费率/币种/版本不给金额。
- 门禁日志：r1606-architecture-fixed.log(345/164.456s)、r1607/1608/1609-architecture.log(345)、各轮 smoke 0 失败。
## R1635 收尾复核（阶段4 定向用例，本轮提交）
- T4／T5／T6：tests/test_model_output_contract.py 与 tests/test_outbound_request_contract.py 与 tests/test_perf_batch_queue.py 共 38 项 OK（9.0 秒）。
- T2／T3／T8：tests/test_stage_gate_e2e_probe.py 与 tests/test_selftests.py 共 57 项 OK（6.0 秒）。
- T1／T7：tests/test_recovery_delivery_e2e.py 与 tests/test_soak_light.py 共 8 项 OK（51.5 秒；真实全链 32.9 秒，预算 150 秒）。
- 沙箱内派生隔离进程被拒（Errno 5），自检器退回同进程执行，与既有记录一致；未跑全量，不冒称同树全量。

- R1638：新增 `tests/test_perf_concurrent_submit.py` 1 项 OK（8.5 秒，实测 16 项／4 生产者／2 消费者＝7.74 秒、2.07 项／秒）；轮次基线＋行尾 21 项 OK；未跑全量（欠账 2／8）。
- R1636（文档轮）：只读核验全仓监听面 2 处（previs_monitor.py:130 与 skill 资产 render-monitor-dashboard/server.py:849），§5 补登后者；§4 三条 A 级挂账索引与 维护记录/缺陷台账_20261001.md 的「待实机复验」条目一致；轮次基线＋行尾 21 项 OK；未跑全量（欠账 2／8）。
- R1635 门禁收尾：架构门禁 356 项 OK（196.9 秒）、默认冒烟 8/8 通过、轮次连续性守护 OK；本树仍未跑全量。
