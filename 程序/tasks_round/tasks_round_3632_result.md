# R3632 — A11 第六批分镜呈现接线
<!-- round-evidence: {"commit_base": "b7705e6e", "credential_hits": 0, "evidence_sha256": "1ff58b316fa4ae0e", "exit": 0, "failed": 0, "passed": 129, "round": 3632, "tests": "run_selftests.py -k test_stage_command_contract test_animatic_scope test_req_s03_anchors test_dynamic_import_registry test_no_circular_import test_complexity_ratchet test_module_size_ratchet test_desktop_automation_service test_idea_request_lifecycle test_desktop_close test_project_switch_guard"} -->

1. §3.3 结构治理轮。执行《六层架构收口与企业级演进任务书》A11 第六批。专用工作树 `0cdc`，分支 `codex/architecture-a11-storyboard-present`，起点 `18c27849`。本轮从游离 HEAD 切到指定分支后领取 R3632。共享队列未发现匹配条目。
2. 默认冒烟 8/8，隐藏桌面探针通过，汇总 9/9。完整架构 601/604，失败集合与 R3626 相同。受影响门禁选中 96 个测试文件，等待共享隐藏桌面令牌后开始执行，外层冒烟在 900 秒超时。
3. 严格扫描注册器 3 → 0，桌面桥接 9 → 9。共享安全全量最近绿凭据为 R3589，本分支未执行安全全量。分支状态页停在 3409，本轮结果加入后期望 3633，由合入车道同步。

## 行为与覆盖

- 三个生产模块。L3 决定工作计划与呈现指令，L4 通过既有 `run_action` 接收枚举动作。会员准入、运行登记与失败事件继续委托既有处理器。未知动作报错，确需呈现时缺少注入报错。呈现返回 `False` 或抛错时保留原结果，不产生成功提示或额外事件。
- 分镜已有采用稿且自动链处于分镜时回报 1 次，启动 0 次。待办或修订存在时提交准备 1 次。缺少结构剧本时自动失败事件 1 条，手动 0 条。Animatic 手动和自动各只切页 1 次，手动事件 0 条，自动等待确认事件 1 条。跳过、呈现拒绝与呈现异常测试均断言没有额外事件。
- 红测复现回报和启动返回 `False` 后旧入口仍给出成功提示，缺少注入仍调用桌面。以基线桌面方法重放生命周期测试时，切项目后的工作读取了新项目。现将分镜准备固定在原项目，继续由既有生命周期分发结果，并在 UI 回调前核对项目和窗口。五种交付情境中，当前任务启动 Agent 并更新提示各 1 次，取消、替换、切项目和关窗四种情境均为 0 次。重复交付不重复执行呈现。
- 定向行覆盖 68/68。注册器 93/119（78.2%）、三虎阶段接线 127/895（14.2%）、桌面 151/731（20.7%），235/662 个生产模块有行覆盖。报告存于临时目录。因专用树没有随附运行时，以同版本 Python 3.14.7 在本树配独立副本并安装仓库锁定的生产依赖。
- 轮次证据定向 129/129，凭据扫描 0 命中。取证基于源码一致的初次检查点 `b7705e6e`。
- 受影响隐藏桌面子进程跑完 2107 条，跳过 3 条，16 个工作单元有红（8 个测试模块）。剧本链红项主要由 00 全流程 SKILL 夹具缺失导致。三虎红项为 R3626 已复现的 `test_tick_once_drains_into_the_bus`，以及 2 条首帧证据测试的本地图片工具缺失。该组内 `test_desktop_automation_service` 15/15、项目切换守卫 4/4，含分镜启动的 `test_ui_edges_autopilot` 各分组通过。独立生命周期、关窗和项目切换定向 12/12。

## 完整架构失败集合

| 门禁 | 本树实测 |
| --- | --- |
| `test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only` | 缺少 `程序/维护记录/基准历史.json`。 |
| `test_round_baselines.RoundBaselineTests.test_round_number_continuous` | 状态页 3409，本轮结果加入后期望 3633。 |
| `test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references` | 缺少 00 全流程包的 `short-drama-director/references/screenplay-gate-engine.md`。 |

## 桌面桥接交接

严格消费者全域仍拒绝，仅有以下 9 条桌面桥接诊断。注册器单独送入严格消费者通过。

- 未注册目标 1 条，`time.monotonic`。
- 未解析目标 6 条，`pet_bus.STAGE_NAMES.get` 两处，`self.pet_script_structure_batch`、`self.pet_continuity_ledger`、`self.pet_frame_batch`、`turn_on` 各一处。
- 未解析阶段键 1 条，动态阶段转交。
- 未解析条件 1 条，`self.pet_advance(stage)`。

本轮仅执行 A11 第六批。架构基线仍有上述失败，已按 `R3632-FAIL` 在专用分支提交检查点。
