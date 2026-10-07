# R1098 结构治理轮：执行 CRT-026～028 授权删除

- 类型：AGENTS.md §3.3 结构治理轮，执行子场景。
- 测试：本轮工作树定向 114/114、默认 8/8、架构 309/309；架构相对删除前隔离基线 309/309 无下降。完整安全全量本轮未运行，历史主树 R1097 4119/4119，不冒充删除后全量。
- 欠账：仅完成三个获批候选，100 MB 瘦身总目标未完成；SLIM-05～07 删除策略限制仍在。

## 范围与依据

来源：outputs/code-rot-cleaner/app-slimming/UNDER-100MB-NEXT.md，CRT-026、CRT-027、CRT-028。用户在逐项隔离证明后明确批准真实删除。中央入口领取 1098；中央队列没有对应 ID，不认领 facade 或架构解冻任务。

删除 idea_chat.project_document_kind（25 行/1349 字节）、Projects.remove_internal_links（19 行/1107 字节）、workflow_process_registry.cancel_process_slot_request（10 行/334 字节）。合计 54 行/2790 字节 UTF-8 文本；不声称等于整个仓库磁盘释放量。

跟踪源码/脚本/配置精确名称搜索仅命中定义。仍使用的 remove_project_link_node、项目回收入口和 cancel_project_slot_requests 保持原样；未修改测试、依赖、分层、用户项目或配置。公共接口外部动态调用风险已披露并获准实施，不以仓内零引用宣称全生态零消费者。

## 实跑证据

环境：项目随附 Python，-B；独立 codex/slim-crt026-028 工作树。主树既有配置与报告使中央入口拒绝领号，因此使用干净工作树，不移动、暂存或覆盖用户改动。

| 命令 | 结果 |
|---|---|
| run_selftests.py -k idea_chat projects workflow_process_registry | 114/114，62.7 秒，exit 0 |
| smoke_test.py | 8/8，exit 0 |
| run_selftests.py --layer architecture --all | 309/309，30.3 秒，exit 0 |

日志保留于 outputs/code-rot-cleaner/app-slimming/R1098-{focused,smoke,architecture}.log。仅撤销本次测试写入工作树的耗时统计文件，不提交运行统计或日志。

此前隔离未删基线完整安全回归 4119/4119，以及三候选分别试删后的 114/114、8/8、309/309 只作为前置证据。本轮实跑是三项同时删除，不借用前置结果。本轮非发布、未改全量升级入口；与主树真实 R1097 凭据相差 1 轮，未触发三轮周期。真实 UI/外部插件未验收。

## 自审、回滚与提交

自审通过：只改三个授权模块；无新依赖或行为实现；断言零改动；适用定向与架构通过。架构文档只登记维护边界。

回滚：对本轮实现提交执行 git revert，可恢复三处定义；不使用 reset 或清理用户数据。

提交：待收尾提交并合入 master 后回填 commit hash；此处不预报 TASK_COMPLETE。主树状态页轮次只在 master 更新，提交前检查暂存白名单与凭据形态。
