# R3860 修复轮：总控退役验收中的测试前置条件
<!-- round-evidence: {"commit_base": "b85eb285", "credential_hits": 0, "evidence_sha256": "d86832e18f141205", "exit": 0, "failed": 0, "passed": 51, "round": 3860, "tests": "run_selftests.py -k resources previs_monitor_exposure ui_edges_autopilot"} -->

- 类型：§3.2 修复轮（含全量基线验证）。只修已复现的测试前置条件，不改产品规则。
- 测试：上一固定树b85eb285安全全量9207条、1108.1秒、3文件各1红，退出1，无绿凭据；本轮定向复验进行中。
- 欠账：总控退役尚未合入，最终全量凭据与任务完成文件待收口。

## 范围与因果证据

执行[内建总控退役任务书](总控机制删除任务书_R3811.md)最终验收。主体变化检查点b85eb285（R3818-FAIL），本轮真实领号3860。

1. `test_resources.test_ensure_free_rejects_oversized_request` 原先先读free，再要求free+1时必拒绝，其他测试释放磁盘会使后次free增大。用精确两次采样100→101复现原断言`StorageError not raised`。修复为固定同一次真实disk_usage返回值；required/available/code/异常类型等原断言保持，不改资源服务。
2. `test_sanhu_auto_mode_persists_and_polls_handoff` 原settle最多80×10ms，在完整树日志中后台仍busy而断言完成文案。先改为5秒终态等待仍复现busy失败，因此重新读真实回调发现：用例`cancel_timers()`取消了自动tick，win.update并不执行应用结果队列消费；原代码只在等待结束后tick一次。最小修复是在等待中调用真实`d._tick_once()`消费交接结果，并以handoff_busy终态及5秒上界断言结束。完成文案、产物、digest与仅整理一次断言保持。不改产品执行器，不调整产品性能契约。
3. `test_previs_monitor_exposure.test_non_get_methods_never_return_the_page` 全量出现一次ConnectionAbortedError10053；两文件独立17/17、外置96次真实HTTP探针全部501，未复现。只补method subTest定位，不捕获连接异常、不重试、不放宽非200与不含页面断言，产品监控器不变。

## 验证与收尾

- 定向：`run_selftests.py -k resources previs_monitor_exposure ui_edges_autopilot --jobs 1 --gui-jobs 1`，隐藏桌面，51/51、281.5秒（含GUI排队）、0skip、退出0。第一次仅延长等待仍失败，加入真实tick后全绿；日志`logs/R3860_targeted2_utf8.txt`。
- 磁盘红绿：原测试置入free100→101序列稳定复现StorageError未抛；修后同序列通过。回环HTTP独立17条及96真实请求探针未复现10053，原断言保留，后续全量仍须观察。
- 安全全量须在提交后的干净内容树执行。不得以定向或历史全绿替代。
- 不改用户配置、媒体或数据；不清他人锁；不推送。
- 本轮提交与后续master合入完成后再补hash与任务完成文件。
