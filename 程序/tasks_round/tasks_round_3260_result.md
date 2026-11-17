# R3260：成熟依赖任务最终交付与凭据汇总
<!-- round-evidence: {"commit_base": "8317c4cc", "credential_hits": 0, "evidence_sha256": "ecf179b1c9db3fe8", "exit": 0, "failed": 0, "passed": 0, "round": 3260, "tests": "docs-only"} -->

## 三问

1. 类型：文档/状态接续轮，仅任务书、整体汇报和同名完成文件，不改产品源码。
2. 验证：主树最终完整安全回归起点8317c4cc、干净树，718文件、8495条、0红、942.765秒，5条既有条件skip；机器绿凭据已写，内容树与HEAD:程序一致。默认冒烟9/9、依赖15/15、合入CI/架构通过，R3257运行器/soak69条绿。
3. 欠账：本任务引入的旧mock、分发缺项、性能调度与复核P2均已闭环；不宣称未实际执行的真实登录后制作、收费服务或隐藏桌面托盘能力已覆盖。原失败/中断/诊断全部保留。

## 已完成交付事实

- R3249 565e8389：主体命名/HTTP/生产锁/兼容修复经标准队列合入。
- R3253 0838f1ed：R3250异常固定安全信息与默认系统+certifi/显式CA兼容，两个复核P2已独立复审确认修复。
- R3256 e3ae52d5：历史.agent-handoff归档和_wm.log分发排除，源历史文件保留，未知文件守卫不放宽。
- R3258 8317c4cc：soak纳入既有独占性能队列，所有断言/阈值不变。
- 主树requests备份后由2.32.3升级到锁定2.34.2；主树依赖15/15、默认冒烟9/9，用户配置/项目未覆盖。

## 最终绿色目录/ZIP

构建来源本功能树HEAD8317c4cc（仅tasks_round未提交文档在明确排除区），标准distribution_build，未用allow-undecided。新目录.selftmp/requests-8317-final：2762清单文件，verify无缺项/排除项/摘要差异/额外项，京剧整包完整。

副本自身Python-I-Xutf8-B独立核验：Python3.14.7、requests2.34.2、Pillow13.0.0，五入口导入、PNG、118公共CA、系统+certifi pool、显式CA、真实本机中文HTTP JSON、合成URL/非法header/Timeout凭据不外传全部ok。未读用户config/private或联网收费API。

持久ZIP：Git common-dir/deliverables/漫剧助手-成熟依赖绿色版-8317c4cc.zip；152625331字节，2763成员，testzip=None。

SHA256：e9f694f2d5d6b1b32fd28c7af1b4bccb7f4d9e9ff5e34933ecdd118bda8a213c。

机器归档证据 common-dir/requests-migration-evidence/final-8317-archive.json；旧候选/错误诊断/失败全量日志全部保留，不将旧结果替换为绿。

## GUI与外部能力覆盖边界

真实隐藏桌面launcher/Desktop/Tk登录页、after及WM关闭已观察；未真实登录/未调用收费服务，不能声称人工完成13阶段。严格审计阻止真实自启注册表和退出维护子进程，相关正常路径依赖主树完整测试验收；不放宽权限制造通过。复制native路径hidden初始化异常已用同字节主树路径对照，产品图片验证未弱化。

## 文档与并发建议

正式《引入成熟框架与工作树规范任务书》逐项对账；《成熟依赖整体交付汇报_20261118.md》给最终包/边界/合入；《成熟依赖并发任务评估_20261117.md》覆盖50工作树提交/未提交路径。没有停止他人任务；建议避免另起HTTP底层、协调UI共享文件，业务契约和队列不全面重写。

## 提交与状态

最终凭据已核验：common-dir/full-safe-receipts.json最后匹配条目round3258、at=2026-11-18T01:53:50、seconds=942.765、tree=31bb237777256535d7001b6850b066cf370996f1，等于8317c4cc:程序。原始全绿日志已保存common-dir/requests-migration-evidence/full-main-r3258-green.log。本轮仅文档，不另跑产品全量；完成文件逐项映射并经taskbook_closure检查，合入仍走标准CI。文档提交hash与合入hash据实际git log后续核验，不预填成功。
