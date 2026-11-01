# R1597 O1 并发许可超时禁止执行

修复轮；来源：tasks_round_1596_result.md O1/J/K。无匹配中央队列ID。
修复：许可等待使用单调时钟；到期抛出TimeoutError并由parallel_map记录该单元失败，绝不调用worker。Governor读写由可重入锁保护；共享实例初始化串行化。
验证：新增全局满额、同资源冲突用例先红（均观察到worker被调用），修复后test_stage_parallel共52项通过；默认冒烟8/8；smoke_test.py --affected stage_parallel通过，0红文件。
测试执行器首次因沙箱不能写common-dir测试锁而等待，已停止该进程，以授权权限正常重跑通过。未重复全量；最近正式全量仍为R1595，5305项，非本轮树凭据。架构全门禁本轮未运行（单模块修复，未改分层）。
自审通过：未触及用户配置/项目；失败明确返回，不增加无许可降级。O2入口覆盖、O4取消期限按后续条目实施，不冒称本轮完成。
提交：本报告与stage_parallel.py、tests/test_stage_parallel.py同批提交，hash由git log按R1597查询。
下一项：O2，随后O7；全部12项仍是持续目标，未完成清单不得结束目标。
