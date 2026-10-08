# R1182：R1173 J3 契约轮验证检查点

- 类型：契约轮。用户授权自动按优先级完成 R1173 附件 J、K；J1/J2 先完成，现处理 J3。尚未 TASK_COMPLETE，全量待跑。
- 基线：J1/J2 对应实现 005ffc0，干净全量基点 65649b0，4271/4271、架构 310/310；R1180 收尾 c92a16e 仅文档。当前生产与测试进入本轮前一致，不重做已完成修复。
- 本轮定向 72/72，1.2 秒；冒烟门禁 9/9，增量串行无红。新增 2 个测试方法，预计完整基数 4273，实际以全量输出为准。
- 中央领取 R1182；show 无对应队列 ID，不认领他人任务。未修改 L1 以上生产代码、SKILL、brief 契约或用户六项既有变更。

## 顺序验收

1. J1 + K 请求矩阵：[TASK_COMPLETE]。R1176/R1180 已完成导演、编剧、编辑、演员、全部审核及返工共享 SKILL；brief、计划、候选、意见实际请求矩阵已覆盖。当前生产与测试对比 65649b0 无变化，原全量日志尾为 ALL TESTS PASSED。旧 writer-only 断言迁移原因与新增正反断言见 R1176，不重写历史。
2. J2 + K 节奏投影：[TASK_COMPLETE]。两端共用空白/注释/元数据占位过滤，保留自定义非空与未知格式；首发、续发及 API 均已有测试。完成前两项后才启动本轮 J3。
3. J3 + K 契约固化：进行中。AGENTS §3.4 白名单精确补入既有 L0 hollmwood_rules；architecture 新增权威和交接表。L0 正文已符合裁决，无需再次修改；这不是把旧结构轮更名为契约轮。

## 逐项审计与断言登记

| 契约项 | 权威与结论 | 验证 |
| --- | --- | --- |
| 导演节奏 | 所选 SKILL；时长由确认 brief 单集时间 | 新增角色职责与权威断言；已有 137 秒独立简报矩阵 |
| 编剧 | 完整自然语言正文，禁止结构化；对白字数引用 SKILL | 保留职责边界并新增断言，交付契约仅编剧含返工 |
| 编辑 | 完整改写逻辑、动机、转场，保留导演计划 | 新增职责断言，已有返工前稿和意见检查 |
| 演员 | 可表演正文，不擅增角色或改结局 | 新增职责断言，原最终演员稿断言保留 |
| 审核 | 同一 SKILL、brief、计划、候选；APPROVED/REVISE: | 新增权威及机制断言，原重试上限/前缀判据不改 |
| 单窗口 | 共享 L0 五组常量各一次，只交演员正文 | 新增最终交付检查，原首发/续发引用一次测试保留 |
| 默认模板 | 元数据和空 rules/constraints，不携带详细尺度 | 原空白/默认/自定义/未知格式测试保留 |
| 契约白名单 | 六个明确授权模块，且均登记 L0 | 新增架构一致性测试，不泛化到所有 L0 |

仅新增 `test_stage_prompt_governance.test_hollmwood_authority_and_handoff_contract` 与 `test_agents_md.test_contract_round_whitelist_matches_authorized_l0_scope`，不删改旧测试。旧 20 字、60–90/100 秒与详细节拍规则不得回流；也不将 SKILL 的 24 或 6~18 复制进角色常量。

来源核对：00 包 `dialogue-speed-check.md:45–46` 为 ≤24 合规、>24 拆镜；`dialogue-doctor-7d.md:16` 推荐 6~18。speed-check 的第 85 行示例将 24 标为阈值，存在包内表述边界差异；遵循用户已裁决的 ≤24/>24，未修改 SKILL，也不在程序另建字数算法。

## 验证与下一步

目录为独立 assistant-hollmwood-dedupe/程序；使用 D:/漫剧制作助手/运行环境/Python/python.exe：
- `-B run_selftests.py -k hollmwood stage_prompt_governance script_agent_delivery_assembly writing_api`：72/72，1.2 秒。
- `-B smoke_test.py --gate`：9/9；日志 HOLLMWOOD-R1182-targeted.log、HOLLMWOOD-R1182-gate.log 位于系统临时目录。
- 一次只读 rg 误带程序前缀无匹配，已用正确相对路径重读；不是测试失败。
- 下一步干净提交后运行 `-B run_selftests.py --all --safe --gui-jobs 1`（前轮并行 GUI 曾不稳定，本轮直接用执行器支持的串行 GUI），通过后记录实际结果、自审、更新状态和接力，并停止。
- 不将隔离分支结果冒作含用户六项改动的 master 正式凭据。未实发模型或重启应用。
