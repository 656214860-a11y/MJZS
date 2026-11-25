# R4516 六层制作链路集成与独立验收
<!-- round-evidence: {"commit_base": "f2b00bc5e", "credential_hits": 0, "evidence_sha256": "84562ce6f768164d", "exit": 0, "failed": 0, "passed": 578, "round": 4516, "tests": "run_selftests.py -k test_tts test_task_center test_runtime_projection test_usage_overview test_stage_completion_service test_tool_execution_protocol test_tool_result_contract test_skills test_skill_orchestrator_completion test_skill_templates test_video_staleness test_video_revision test_asset_impact test_asset_detail test_ui_theme test_asset_context test_video_source_evidence test_delivery_scope test_startup_selfcheck test_storyboard_storage"} -->

Control 复核了 Devin 的各卡差异，使用随附 Python 验证真实生产入口与临时项目。详情见[任务书](L0-L5制作链路集成任务书.md)、[任务恢复](L0-L5制作链路集成_A卡验收记录.md)、[执行接口](L0-L5制作链路集成_C卡验收记录.md)和[规格与真实取证清单](L0-L5制作链路集成_E卡验收记录.md)。

- A/B 的配音任务快照、任务中心和交付校验三个测试模块独立运行 73 项通过。合成资料覆盖采用音乐、声音、字体、外部补录、凭据改变以及沿来源关系递归盘点。核验通过仅说明证据符合程序规则。
- C/F 的协议、异常和编排集成两组测试独立运行 22 项通过。纯缺工具在步骤级显示缺工具，真实失败优先。默认 mypy 严格检查两个契约文件通过。
- D 已在 R4515 验证 17 项成本回归。E 的历史无签名记录保留无法判断状态，使用已登记的实际输入比较新版本；重复确认与批量标记不会自行产生付费请求。
- 按真实调用点复核新模块、跨层依赖和 UI 呈现；重测覆盖率时保留原下限。商用授权样本双评、真实供应商账单与指定软件实机导入仍按 PRD §10 在实际使用阶段取证。
- 使用仓库分支测量器在隐藏桌面执行 2,439 项定向测试，全部通过；L0/L1 的 103 个实体中，3,132 个可计量决策点有 1,852 个覆盖两种结果，全部达到原有逐模块下限。另用 17 组行覆盖目标测得 694 个生产模块中 149 个有行覆盖；两种测量的目标集合不同。
