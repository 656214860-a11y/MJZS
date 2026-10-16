# 当前验证索引

## 最近正式全量
R1605：HEAD e59e5136e2992ae18832d05083ab56bb75416242，5346项、410个测试文件、0红，测试615.7秒/执行器631秒。common-dir/full-safe-receipts.json 为权威。

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