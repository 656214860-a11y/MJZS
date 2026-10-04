# R984：资产图片绑定、创意附档与续跑台账写服务结果迁移

本轮为结构治理轮，执行 `维护记录/架构统一路线图_v2.md` 第 1 项；三个 L2 服务、五个写入口接入既有四字段结果，同轮检查调用方、测试和采用方棘轮。测试已运行，基线未全绿；project_status.md 仅 master 可维护，本轮不写，其欠账未减少。

- asset_detail_service：两个绑定入口的成功路径返回结果；本地输入校验返回 UserError，OSError 经既有回滚后返回 SystemError，发布器编程异常继续传播。图片及索引的既有回滚不变。
- idea_attachments：归档入口结果携带原路径元组；已知附件校验失败为 UserError，磁盘失败（含 DOCX 包装的 OSError）为 SystemError，发布器 TypeError/KeyError/ValueError 不被吞掉。保留原有逐文件发布，不宣称多附档原子回滚。
- asset_resume：记录与清除均返回结果；底层清除返回 False 不再丢弃，空编号记录也传播清除失败。桌面显示未清除提示，L3 检查失败后才解包。

本次改测试因契约变更：旧资产绑定 OSError 断言改为 L3 检查结果后的 ValueError，原图片/索引字节恢复断言保留；台账辅助函数解包成功结果，所有计数/退避/落盘断言保留。新增成功形状、已知校验、各发布点 I/O 错误、编程异常、调用方拒绝失败结果及清除失败不丢台账测试；未 skip 或削弱既有行为断言。

采用方由 16 增至 19，scope_audit_pending 由 10 降至 9，历史豁免由 34 降至 32。整个第 1 项及全部 18 项仍未完成。

## 验证与自审

- 定向：45 条，1.131 秒，全部通过；涵盖三个服务、调用方以及相关发布边界和采用方棘轮。
- 默认冒烟：8/8。
- 架构门禁：283 条，98.528 秒；282 通过，仅轮次连续断言失败：963 != 985。未越权改 master 专属状态文件或削弱断言。
- 默认增量：3881 条，325.9 秒，6 个失败文件、7 条失败。失败为 architecture.test_round_baselines（上述编号）、test_baseline_history（缺基准历史文件）、test_asset_gating（31 != 24）、test_pet_ui（8 != 3）、test_script_contract（缺外部入口）、test_skills（两条 71 != 73）。没有运行分支完整安全全量。
- 新出现的 test_pet_ui 计数失败：按 diagnosing-bugs 的最小复现步骤，复跑与无附加消息的行数断言相符的 `tests.test_pet_ui.StickerFitTests.test_the_progress_bubble_numbers_every_line`，1 条、0.320 秒通过。增量过滤输出未保留测试名堆栈，故该定位仍待原失败堆栈确认；独立通过不代表原失败修复，不推断根因，未修改相关产品代码或断言。
- 自审：仅三个 L2 服务及必要调用方、测试、计数台账和本报告；未改 Tk 控件/事件绑定、用户数据、master 或其他工作树。I/O 错误受控返回，发布器编程异常传播；原回滚断言保留。测试总门禁未达标，自审结论不通过。

状态：[TASK_FAILED]。保留诊断性提交，提交凭据待追记；不得据此声称路线图完成或 master 已同步。
