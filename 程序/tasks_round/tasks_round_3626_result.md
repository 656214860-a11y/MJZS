# R3626 — A11 第五批失败事件接线
<!-- round-evidence: {"commit_base": "44325aa9", "credential_hits": 0, "evidence_sha256": "aad2755cb031b03e", "exit": 0, "failed": 0, "passed": 108, "round": 3626, "tests": "run_selftests.py -k test_stage_command_contract test_animatic_scope test_req_s03_anchors test_dynamic_import_registry test_continuity_scope test_complexity_ratchet test_module_size_ratchet"} -->

1. §3.3 结构治理轮。执行《六层架构收口与企业级演进任务书》A11 第五批，来源为 R3614「严格闭包交接」的 `pet._emit`。专用工作树 `1b12`，分支 `codex/architecture-a11-failure-event`，起点 `44325aa9`。R3626 归属已核验。范围扫描提示前序批次与其他在用车道共享文件，本轮在指定起点单独推进。
2. 默认冒烟 8/8，隐藏桌面探针通过，汇总 9/9。完整架构 601/604，以下三条在本专用树的 `44325aa9` 基线也复现。本轮保存失败检查点。
3. 严格闭包注册器 4 → 3，桥接 9 → 9。共享安全全量最近绿凭据 R3589，本分支未运行安全全量。状态页由合入轮同步。

## 变更和行为证据

- 三个生产模块。注册器通过原有运行注入位置调用 `run_action`，L4 `stage_run_action` 处理会员准入、运行登记和自动启动失败。发布沿用 `Pet._emit` 的当前运行序号和事件总线。事件动作异常被捕获，原始失败原因按原路径返回。
- 改前红测在制作锁阻断时观测到注入发布动作调用 0 次，期望 1 次。改后验证手动制作锁返回原因，手动分镜输入缺失与手动 Animatic 返回空串，手动均无失败事件。Animatic 自动入口仍切页等待人工确认。
- 真实总线测试中，手动登记序号 1，两个自动分镜输入失败分别保留序号 2 和 3，各发一条 `stage.failed`，成功事件、后备推进、打开分镜任务与成功播报各 0 次。已有测试覆盖会员拒绝保留上一轮序号、登记失败中止派发、取消／替换／关窗无迟到交付、切项目拒绝旧请求。
- 严格扫描按种类与目标核对。基线注册器 4 条，移除 `unresolved-target: pet._emit` 一条。剩余 `desktop.pet_report`、`desktop.open_storyboard_skill`、`desktop.show`。桌面桥接 9 条原样保留。严格消费者继续拒绝剩余闭包缺口。

## 验证

- 最终受影响冒烟 10/10，隐藏桌面定向 233/233，其中后台生命周期 14 条、请求生命周期 6 条、关闭窗口 2 条。提交凭据定向 108/108，凭据扫描 0 命中。
- 修订后的严格闭包、复杂度与模块体积棘轮及阶段命令等定向 92/92。隐藏桌面既有三虎测试 39 条，38 通过。`DesktopSeamTests.test_tick_once_drains_into_the_bus` 在 `44325aa9` 的三个生产模块与本轮实现下均只收到 `stage.paused`，断言要求 `stage.completed`。
- 行覆盖既有 10 组目标 115/115，核心下限 11/11，83/662 个模块有行覆盖。初跑定位图片解码器缺失，临时目录提供 FFmpeg 后通过，覆盖报告未写入仓库。
- L0/L1 分支覆盖既有 93 组目标执行 1775 条，报告 5 个失败、33 个错误、4 个跳过，测量未写入覆盖报告。首帧相关失败可用临时 FFmpeg 修复，剧本相关失败缺少 `AIGC创作全流程`、`剧本锻造`、`编剧技能集` 的固定版本夹具。专用树没有对应子模块映射，未从其他工作树取用夹具。

完整架构失败集合：

| 测试 | 本树实测原因 |
| --- | --- |
| `test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only` | 缺少 `程序/维护记录/基准历史.json`。 |
| `test_round_baselines.RoundBaselineTests.test_round_number_continuous` | 分支状态页头为 3409，基线预期 3615，加入本报告后预期 3627。 |
| `test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references` | 未检出 00 全流程包的 `short-drama-director/references/screenplay-gate-engine.md`。 |

R3614 记载的复杂度登记和解释器依赖白名单在本次最终全跑均通过。与 R3614 报告相比，本树缺历史数据和技能引用两个夹具，状态页断言仍红。第一版触及的参数、嵌套和模块行数棘轮已在最终全跑复绿。

## 交接

本批只收口失败事件。完整架构与分支覆盖应在具备固定版本夹具的环境复验。总任务书、A11 其余分镜和预演接线、桌面桥接缺口仍待原计划处理。
