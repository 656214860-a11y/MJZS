# R1176：四角色共享 SKILL、审核依据与空模板修复

- 类型：修复轮。来源：R1173 诊断 J1/J2、K；用户明确授权四项修复。
- 验证：定向 71/71，smoke_test.py --gate 9/9（默认 8/8；增量无待跑用例，0 条）。完整安全回归及其架构检查待执行，本检查点不代表完成。
- 欠账：正式 master 全量凭据当前仍 R1160，未据分支测试勾销；提交信息见本报告后续回填。

## 根因与改动

原 API 只有编剧收到 SKILL；审核没有简报，返工没有简报／计划。规则外置后，模型不能从独立请求中取得这些依据。空节奏模板仍在两条入口拼入强制规则标题。

1. `hollmwood_roles` 统一构造共享 SKILL，导演／编剧／编辑／演员／审核和返工每个请求各带一份。导演后各请求都带已确认简报与导演计划，审核另带当前候选，返工另带意见和前稿。
2. `writing_api` 将阶段交付契约从共享 SKILL 中拆为独立参数，仍只用于编剧及其返工，避免审核或规划被要求输出剧本。
3. `hollmwood_roles.rhythm_prompt` 统一节奏投影，API 与桌面 `workflow_settings` 共用：空文本、仅注释、元数据与空 rules/constraints 不注入；自定义非空／未知格式保留。原始模板读取仍保留，未清空用户配置。

产品只改上述 3 个模块；未改 L0 角色文案、ROLE_ORDER、MAX_REVISIONS、串行控制流、审核放行逻辑、SKILL 文件或 brief 字段。未改用户项目／真实模型调用／应用运行状态。

## 断言迁移登记

| 文件 | 旧口径与新证据 |
| --- | --- |
| test_hollmwood_roles | writer-only SKILL 改为每次请求共享且恰好一次；编剧专属交付契约保留排除断言。新增 13 次请求（含三个阶段退回）验证简报、时间、导演计划、当前候选和返工依据；新增空／自定义模板投影测试。 |
| test_hollmwood_agent_delivery | 首发／续发不含占位模板；空面板输入同样跳过；自定义节奏及项目角色覆盖断言强化为恰好一次。 |
| test_script_agent_delivery_assembly | SKILL 与交付契约分别传递；自定义模板标题同步两端共用的标题，启用／禁用各自出现次数保留。 |
| test_writing_api | 真正执行角色装配的本地替身集成覆盖全部 7 次请求的共享内联 SKILL、简报／计划和空模板排除；落盘及日志原断言保留。 |
| test_stage_prompt_governance | 未改断言，既有单份规则与 SKILL 引用检查纳入定向验证。 |

## 实测记录

- 随附 Python `-B run_selftests.py -k hollmwood stage_prompt_governance script_agent_delivery_assembly writing_api`：71/71，1.2 秒（不含等待其他工作树 GUI 锁的时间），无失败。
- `-B smoke_test.py --gate`：9/9；增量台账无待跑用例（0 条），不冒称额外回归数量。
- AST 检查、`git diff --check` 通过。未执行真实模型，不能用本地替身证明模型创作质量。

## 收尾状态

安全全量待执行，完成后回填结果、自审及同步回执。主目录六项既有用户改动不纳入本次提交。
