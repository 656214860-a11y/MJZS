# R944 修复轮：并行回归超时集合访问

队列：C4-full-suite-shard。当前未完成，尚需完整两轮验收。

根因：concurrent.futures.wait 返回 Future 集合，run_units 对其调用 values 导致 AttributeError，在终止工作进程前进入等待式 shutdown。

修复：通过 pending 映射取得未完成单元，复用该列表生成超时失败记录。新增行为测试覆盖超时分支，没有修改既有断言。

验证：执行器 29/29；默认冒烟 8/8；真实 ProcessPoolExecutor 提交 30 秒 sleep，在 1 秒超时配置下 1.02 秒返回失败记录并退出。架构门禁和全量本轮尚未验证，不引用为通过。

提交：2799dae。

后续核验：架构门禁共 273 项，首次有两项失败（状态轮次过期、完整安全全量欠账）。状态轮次已按最新 R944 报告接续至 945；全量欠账未消除。PID 34828 仍持有全量锁，C4 验收尚未完成。

验收阻塞诊断：test_modules() 实际包含 architecture.test_round_baselines；最新报告 944、last_full_safe_all_round=868，full_safe_required=True。该测试要求最新报告已写全量通过结果，而 main 仅在全部测试无红后保存全量凭据，形成先有通过记录才能跑绿的循环。后续修复须区分正在执行的完整安全验收与普通检查，并在全量成功后记录可核验凭据；不得预填通过文字或跳过测试冒充验收。
