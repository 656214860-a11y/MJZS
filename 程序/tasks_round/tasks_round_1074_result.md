# R1074：退出维护调度

- 类型：结构治理轮，执行子场景。来源 `C:/Users/LAIBIAO/AppData/Local/Temp/architecture-review-20261005-01.html` 候选 03；用户确认保守方案。
- 状态：TASK_COMPLETE，已完成本轮获批的保守调度重构与代码级验收；不声称后台完成协议或实机退出验收已完成。
- 范围：两个生产 module，desktop 与新增 L3 exit_maintenance。仅集中三路调度策略与固定大小的脱敏派发摘要，不执行真实维护、不扩大清理范围。
- 行为：窗口销毁后 storage→logs→workspace 依次派发，但工作进程不串行等待；强制退出仍只派发 storage。storage 异常传播；可选日志／仓库仅吞 OSError，其他异常传播。重复正常 close 仍由既有 _closing 守卫抑制，不给直接 finish_close 或 force_quit 增加新幂等语义。
- 观察边界：现有 launch_cleanup 不返回进程句柄。本轮输出只称 scheduled，不称 completed，固定三项且不含路径、异常正文或子进程输出，completion=unobserved。后台清理失败仍由原实现／原测试约束；未新增持久化日志、监控线程、重试或完成协议。
- 测试：新增 6 条 Desktop 特征回归及 5 条协调入口测试。原断言不改、不删、不 skip。旧版本 ab3b6c2 的 desktop 源码仅加载到内存测试模块，对照 17/17；迁移后定向 58/58（1.2 秒），默认冒烟 8/8，受影响检查 9/9。正式安全全量 4026/4026、0 失败，含架构 309/309（改前 309，持平）。
- 正式凭据：干净 master 检查点 813b662；tree=c924740a7a042954a6e4e086736a15fe5c31437c、round=1074、seconds=295.657、at=2026-10-06T00:23:14，由执行器记录于 Git common-dir/full-safe-receipts.json。日志位于系统临时目录 R1074-full.log。后续仅文档回填，不冒充最终文档树重新全量受测。
- 验证过程：最初迁移前 runner 因 .git 写锁权限等待，主动中止，未记为通过；获授权后重跑当前实现。旧版本对照首次因测试切换 cwd 导致导入路径失效，17 个 setup 错误；固定进程内绝对导入路径后 17/17，无测试断言修改。
- 设计：interface 只接程序位置与退出意图；隐藏三路顺序、非对称异常规则和摘要状态。删除该 module 会让这些知识回到 UI，不引入 adapter 家族或第二套清理实现。
- 自审：没有用户数据、密钥、配置或清理范围变更；未更改三个实际维护 module。强制退出新增的摘要仅 stdout，不增加磁盘维护操作。
- 风险：GUI 无控制台运行时摘要可能不可见；后台实际完成及实机退出未验收。持久完成回执需要另行设计工作进程协议，不能由本轮派发状态推断。
- 回滚：以 git revert 协调撤销两个生产文件、层级登记、新增测试与相关文档，不 reset、不 push。
- 收尾：文档／轮次门禁 15/15（0.8 秒），diff --check 通过；中央任务 completed，validate 0 errors、1 条既有 architecture-unfreeze-1-2 租约警告，未修改他人任务。N=1075、M=1074。
