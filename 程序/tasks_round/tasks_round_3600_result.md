# R3600 — A11 第二批阶段注册器闭包
<!-- round-evidence: {"commit_base": "347a1691", "credential_hits": 0, "evidence_sha256": "a53bb5c95bc192d6", "exit": 0, "failed": 0, "passed": 80, "round": 3600, "tests": "run_selftests.py -k test_dynamic_import_registry test_animatic_scope test_account_security"} -->

1. §3.3 结构治理轮。起点 `347a1691`，专用工作树 `d5df`、分支 `codex/architecture-a11-registry-closure`。中央领号归属已核验，计划路径 scope 无重叠。
2. 默认冒烟 8/8，另通过隐藏桌面探针。严格入口仍拒绝，注册器 18 → 10，桌面桥接 9 → 9。独立定向 92/92。
3. 消除 8 条证明缺口。安全全量本轮未启动，共享最近绿色凭据为 R3544。项目状态头与最新结果轮次在 master 合入时同步。

## 改动和证据

- R3506 审计、R3595 结果及凭据与本树实测相符。六个未解目标为 `item.get`、`selected.get`、`str(...).strip`、分隔符 `join` 和两个 `options.get`。键值来自字典或关键字参数，文本来自现有字符串转换。注册器用精确的内建方法表达，守卫在核对内建所有者未遮蔽后识别这些调用。
- 两个未解条件是制作锁 `lock_stage(stage)` 与空技能配置 `stage_flow.unchecked(project, stage)`。静态证明限定到这两个导入身份及其阶段参数位置。目标仍经过登记及层级检查。未知条件、键和未登记目标仍拒绝。
- 新的实际生产诊断断言先以原 18 条跑红，再改实现。新增行为用例核对会员条件失败时回调零次，以及 fallback 返回 False、抛同一异常时各调用一次。既有未知键、制作锁、分镜、Animatic、会员及动态注册测试纳入定向。13 个阶段和 2 个辅助命令沿用原验证与派发路径。
- 隐藏桌面生命周期及手动配置定向 79/79，覆盖取消、替换、关窗、项目身份变化与调用结果只交付一次。A11-1 注入呈现器仍只打开配置一次，配置分支不发起制作动作。受影响冒烟 10/10（含探针）。
- 完整架构首跑 600/603，404.407 秒。失败集合为 `AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only`（本树缺历史文件）、`DependencyWhitelistTests.test_site_packages_whitelist`（借用解释器含 5 个未登记项）、`RoundBaselineTests.test_round_number_continuous`（本树状态头 3409，最新结果后应为 3601）。补入上轮历史文件同哈希副本后，首项定向复验通过。其余两项与 R3595 的失败集合相同。三个固定技能包从 R3595 的工作树恢复内容，仅写本树，并验证技能包登记无问题。
- 既有行覆盖目标 115/115，83/662 个生产模块有覆盖，11 个核心路径全部达到原下限。
- 既有 93 组分支覆盖目标在隐藏桌面复跑，1773 通过、2 跳过，94 个 L0/L1 模块全部达到原下限。双向决策点实测 1535/2737，较上轮少 1 个。首轮受 `test_request_ledger.py:667` 并发写用例失败影响未生成有效结果，复跑通过。行与分支覆盖基线文件及阈值保持原值。

## 剩余逐条交接

| 注册器调用 | 运行时职责 | 后续证明方向 |
| --- | --- | --- |
| `gate` L44 | 宿主账号阶段门禁 | 从账号组合点提供窄门禁能力，核对未挂载账号兼容分支 |
| `machine.skip` L63 | 状态机标记跳过 | 从状态机所有者显式提供跳过命令 |
| `machine.save` L64 | 持久化跳过状态 | 同一命令保持写入顺序和异常隔离 |
| `auto.done` L70 | 自动链继续 | 从自动链所有者提供推进能力 |
| `pet.broadcast` L74 | 跳过文案 | 在宿主展示端组合 |
| `pet._emit` L84 | 自动失败事件 | 从事件发布所有者提供失败通知并验证幂等 |
| `desktop.pet_report` L105 | 分镜已就绪时回报 | 在 L4 组合现有回调 |
| `desktop.open_storyboard_skill` L108 | 打开分镜任务 | 在 L4 组合现有回调 |
| `begin` L157 | 登记运行序号 | 从事件总线所有者提供明确入口 |
| `desktop.show` L171 | 切换 Animatic 页面 | 在 L4 组合现有回调 |

以上十项均为真实生产宿主调用。现有调用接受桌面宿主和替身，兼容路径亦会被审计。完整迁移需要同时处理组合点、适配器及所有者契约，且需保证事件和状态落盘顺序。本批保留严格拒绝。

桌面桥接剩余 `time.monotonic` L45、`STAGE_NAMES.get` L49/L74、动态阶段键 L58、`pet_script_structure_batch` L62、`pet_continuity_ledger` L63、`pet_frame_batch` L66、`turn_on` L72、`pet_advance(stage)` L75。后续需证明阶段键来源、三个宿主分派目标、轮询开关选择及推进条件。
