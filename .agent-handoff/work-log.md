# 近期工作

- 2026-10-12：R1335 阶段④分集增量上下文（独立功能轮）。script_contract 新增 split_script_episodes 与分集账本 剧本分集增量账本.json（每集 sha256＋based_on 其余集快照）；writing_api.reply() 前注入只含改动集正文、_save_formal_script() 后更新账本；workflow_tasks._episode_change_notice() 只给 Agent 集号；首次／无账本退化全量。定向 5＋1＋1 全绿、默认冒烟 8/8、架构棘轮 3/3；writing_api／script_contract 红点与基线同形（缺 gitlink 假红）；全量未跑。见 [R1335](../程序/tasks_round/tasks_round_1335_result.md)。

- 2026-10-12：O10 完成并提交 R1330。采用事务化：`confirm_gates` 相位 pending／applied／failed、`pending()` 只认 applied（旧记录无 state 按已确认），`stage_execution_service.adopt_asset_plan_choice` 先记 pending → 落盘 → 成功记 applied，失败记 failed、中断留 pending，`asset_detail._pick` 失败给恢复提示。定向 96/96、架构棘轮 5/5、默认冒烟 8/8、0 红。收口安全全量见 [R1330](../程序/tasks_round/tasks_round_1330_result.md)。

- 2026-10-12：O09 完成并提交 R1322。就绪绑定来源分镜摘要与预演文件：`white_model_service` 新增 `shot_digest`／`source_digest`／`evidence_state`／`record_evidence`，`previs_routing.ready` 按证据失效，`previs_automation.verify` 校验通过即登记，`local_previs` 状态列与导入共用。定向 138/138、关联 172/172、默认冒烟 8/8、架构 312/312。

- 2026-10-12：O09 收口安全全量。干净 master 工作树第 1 次 4522/475.5 秒／1 文件红（SG-05 探针夹具只写 preview，同符新语义），定向补 `record_evidence`（R1328）后第 2 次 4522 条〈437.4 秒、0 红，凭据 round=1322、tree=42e782ea，`last_full_safe_all_round` 刷到 1322。见 [R1322](../程序/tasks_round/tasks_round_1322_result.md)。

- 2026-10-12：O07 完成并收口。白模镜头目录加项目身份与集维度（`white_model_service`）、新建项目即写 `project_id`、旧目录迁移（可重复／不覆盖／失败回滚＋来源版本清单）、白模页打开时调用一次；同步 `架构统一基数.json` 第四项三处行号。定向与接缝 805 条、默认冒烟 8/8、架构 312/312。见 [R1312](../程序/tasks_round/tasks_round_1312_result.md)。

- 2026-10-12：O07 收口全量。干净 master 工作树第 2 次 `--all --safe` 4516/4516、388.1 秒、0 红，绿凭据写入 `.git/full-safe-receipts.json`（round=1312、tree=12ad4759）；第 1 次的 21 文件红全部来自新建工作树缺嵌套子模块。

- 2026-10-12：O08 完成并提交 R1316。`previs_routing.decisions_for` 成为唯一有效决策（覆盖优先），门禁 `stage_parallel.previs_ready` 改用它；`ready` 增开 `source` 按集解析并连接到 dispatch、automatic_candidates、previs_automation.start 与 L3。新增 4 条四场景一致性用例；定向 143/143、接缝 398/398、架构 312/312、默认冒烟 8/8。见 [R1316](../程序/tasks_round/tasks_round_1316_result.md)。

- 2026-10-12：O06 完成并收口。修复新门禁暴露的三处测试/探针回归与 `platform_tools.tool_path` 缓存遮蔽缺陷，台账轮次 1307→1308。提交 a167b7c / 8760e41 / fbdd23d；干净内容树 0e2a2f06 全量 4504/4504 通过（无执行器绿凭据）。见 [R1307](../程序/tasks_round/tasks_round_1307_result.md)。

- R1162 收尾：Claude Desktop 改为与 Codex 共用全文任务书投递；提交 db0e878、同步回执 6523465。后续问答只读确认 CLI 仍传任务文件路径，并澄清任务书与素材正文的区别；真实窗口是否完成全文粘贴仍未知。仅补交接记录，不扩展生产改动。

- R1070：按用户要求核验并更新交接；确认 R1069 提交 bc6358e、中央状态 completed，开始时工作树干净。仅接力/状态/报告文档，未继续优化。

- R1069：接力入口、分类记忆及会话提示完成；定向 23/23、冒烟 8/8；master 提交 bc6358e，中央任务 completed。见 [报告](../程序/tasks_round/tasks_round_1069_result.md)。
- R1068：隔离批量删除证明定向 90/90、冒烟 8/8、架构 309/309；真实源码未删除。提交 c80b965，见 [报告](../程序/tasks_round/tasks_round_1068_result.md)。
