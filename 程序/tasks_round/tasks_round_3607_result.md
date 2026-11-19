# R3607 — A11 第三批阶段注册器跳过动作接线
<!-- round-evidence: {"commit_base": "4530fed3", "credential_hits": 0, "evidence_sha256": "56b9089a7e75d59e", "exit": 0, "failed": 0, "passed": 109, "round": 3607, "tests": "run_selftests.py -k test_dynamic_import_registry test_animatic_scope test_account_security test_req_s03_anchors test_continuity_scope"} -->

1. §3.3 结构治理轮。起点 `4530fed3`，专用工作树 `0d12`，分支 `codex/architecture-a11-runtime-host`。中央领号 R3607，实际改动路径无车道重叠。
2. 默认冒烟 8/8，隐藏桌面探针通过，受影响冒烟 10/10（含探针及定向门禁）。严格闭包仍拒绝，注册器 10 → 6，桌面桥接 9 → 9。
3. 消除 4 条真实运行时宿主调用。本轮安全全量未启动，共享最近绿色凭据为 R3589。项目状态头由 master 合入时同步，本轮仅提交专用分支。

## 行为与边界

- `orchestrator/stage_handler_registry.py` 保留阶段键、会员闸、制作锁、勾选条件及辅助命令派发。跳过动作由 `ui/desktop_pet_bridge.py` 注入，自动链先于付费审批的跳过入口与它共用 `ui/pet_ui_stages.py` 的同一实现。仅三个生产模块。
- 严格审计在 L3 仅承认 `start` 的显式、未被覆盖的关键字参数 `skip_action`。注入端沿用目标解析与层级检查，拒绝未知目标、未知条件分支和越层目标。R3600 的内建及谓词证明无回退。
- 原始红测两条。旧实现忽略注入动作，返回跳过固定文案。旧实现缺少动作时仍执行宿主变更。终态对有 Pet 且缺少动作的直接调用抛出明确异常，无 Pet 时保留原文案。两个已知桌面入口均显式注入。
- 每个入口单次标记 skipped、保存、调用自动链推进、播报，完成／失败事件 0 次，未派发制作。标记抛错时保存 0 次，保存、推进、播报的异常仍各按原隔离边界处理。备用回调的 False 和同一异常各原样传回一次。阶段域仍为 13 个制作阶段加 2 个辅助命令。
- 模块行数首跑触发 `pet_ui_stages.py` 上限。精简同一接线路径上的重复注释后为 1202 行，棘轮复验 2/2，原上限不变。

## 验证

- 隐藏桌面专项 85/85，覆盖 A11-1 呈现器打开一次且无制作派发、两个跳过入口、取消、替换、关窗与迟到回调。项目切换队列隔离独立复验 1/1。
- 较宽定向首跑 303 条，仅 `test_workflow_writing_stages` 两条因缺 AIGC 技能夹具报错。补入上一轮工作树的对应本地文件后，该模块 6/6 通过。
- 完整架构首跑 599/603（387.848 秒）。`AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only` 因专用树缺历史夹具报错，补入上一轮同哈希文件后复验通过。`ModuleSizeRatchet.test_no_module_exceeds_its_cap` 已修复并复验通过。其余两项和 R3600 一致：`DependencyWhitelistTests.test_site_packages_whitelist` 检出借用解释器的 5 个额外发行包，`RoundBaselineTests.test_round_number_continuous` 检出分支状态头 3409，首跑预期 3601，加入本结果后预期 3608。新增注入目标拒绝测试与终态严格闭包断言单独复验 2/2。完整架构未重复整套运行。
- 行覆盖 115/115，覆盖 83/662 模块、11/11 核心路径达到原下限。首轮缺 FFmpeg，补入只读随附 FFmpeg 的搜索路径后通过。行覆盖报告写入临时目录。
- 既有 93 个分支覆盖目标在隐藏桌面复跑，1773 通过、2 跳过，94/94 个 L0/L1 模块达到原下限，双向决策点 1535/2737，与 R3600 相同。前次测量缺 `剧本锻造/SKILL.md` 和 `编剧技能集/README_ZH.md`，技能审计报错。补入上一轮的两个本地入口文件并定向复验后，整组通过。覆盖报告写入临时目录，版本控制中的基线和阈值未改。

## 严格闭包逐条对账

| 原诊断 | 本轮结果 |
| --- | --- |
| `gate` L44 | 保留，账号闸门及没有账号宿主的兼容路径 |
| `machine.skip` L63 | 消除，L4 标记跳过 |
| `machine.save` L64 | 消除，L4 在标记后持久化 |
| `auto.done` L70 | 消除，L4 推进现有自动链 |
| `pet.broadcast` L74 | 消除，L4 在推进后播报一次 |
| `pet._emit` L84 | 保留，自动失败事件 |
| `desktop.pet_report` L105 | 保留，分镜已就绪时回报 |
| `desktop.open_storyboard_skill` L108 | 保留，打开分镜任务 |
| `begin` L157 | 保留，制作阶段运行序号 |
| `desktop.show` L171 | 保留，Animatic 切页 |

续接按三组复核。先核对账号闸门兼容及阻断，再把运行序号和失败终态放在同一事件生命周期下验证，最后核对分镜回报、分镜启动与 Animatic 呈现。桌面桥接原有 9 条留在独立范围。
