# R3614 — A11 第四批会员准入与运行登记
<!-- round-evidence: {"commit_base": "025982b4", "credential_hits": 0, "evidence_sha256": "bf1a895f939aedcb", "exit": 0, "failed": 0, "passed": 79, "round": 3614, "tests": "run_selftests.py -k test_dynamic_import_registry test_animatic_scope test_continuity_scope test_req_s03_anchors architecture.test_stage_command_contract"} -->

1. §3.3 结构治理轮。起点 `025982b4`，专用工作树 `70eb`，分支 `codex/architecture-a11-runtime-account`。标准入口领 R3614，中央队列无对应条目。范围扫描相对 master 报告与 R3607 前序车道及其他共用文件车道重叠。本轮基于指定起点追加单批次，未合并其他车道。
2. 默认冒烟 8/8，隐藏桌面探针通过（汇总 9/9），受影响冒烟 10/10。完整架构跑 604 条，601 通过，3 失败。类行数登记值已按实测下调并定向复验，剩余历史失败见下。
3. 严格闭包诊断中，注册器 6 → 4，桌面桥接 9 → 9。共享最近安全全量绿凭据为 R3589。本分支本轮未跑安全全量，master 专属状态页留待合入轮同步。

## 改动与行为

- 三个生产模块。L3 `orchestrator/stage_handler_registry.py` 接收显式 `prepare_run` 动作。L4 `ui/desktop_pet_bridge.py` 的自动阶段入口与手动／自动分镜入口统一注入。L4 `ui/pet_ui_stages.py` 调用既有会员判定与 `Bus.begin_run()`，并处理自动链启动失败。
- 会员允许时按准入、登记、派发的顺序各调用一次。会员拒绝时运行序号不变，禁止制作派发。手动返回原因，自动单次发送 `stage.failed`。自动重复遇到同一拒绝时，使用独立事件键及 `run=0`，避免归到上次运行或被幂等键吞掉。
- 登记返回 `False` 或抛异常时，注册器原样返回 `False` 或传播同一异常，立即停止。自动入口将每次失败交给既有失败通道，禁止降级唤醒轮询。备用动作的 `False` 与异常保持原样传播。辅助命令仍不登记制作运行。
- 改前红测捕获两个原始失败。拒绝用例得到备用动作的返回值，登记 `False` 用例同样得到备用动作返回值。终态用例增加真实事件总线的重复拒绝、同一异常实例、登记与派发顺序和自动入口禁止降级推进。

## 实测与历史失败

- 隐藏桌面生命周期专项 36/36，覆盖取消、替换、关窗后不接受迟到结果，切项目后请求不跨项目交付，以及启动登记失败。定向架构专项 20/20，含终态大小棘轮、剩余闭包拒绝、未解析或越层注入目标被拒绝。
- 较宽定向 794 条，仅 `test_pet_ui.DesktopSeamTests.test_tick_once_drains_into_the_bus` 失败。实测只有 `stage.paused`，断言要求 `stage.completed`。在同一工作树、同一夹具下从 `025982b4` 载入三个原生产模块单独复现同一失败。
- 完整架构初跑出现夹具缺失及中间实现门禁失败。补入 R3607 工作树的本地历史夹具、Git 子模块 Markdown 夹具和两个技能入口，FFmpeg 使用只读随附版本。没有提交夹具、改变 Git 子模块指针或修改解释器。
- 完整架构复跑的三条失败为 `test_complexity_ratchet.ComplexityRatchet.test_registries_track_real_values`（进程载入的是旧登记上限 1182，终态上限为 1161）、`test_dependency_whitelist.DependencyWhitelistTests.test_site_packages_whitelist`（借用解释器包含 annotated-types、pydantic、pydantic-core、typing-extensions、typing-inspection）以及 `test_round_baselines.RoundBaselineTests.test_round_number_continuous`（分支状态头 3409，复跑时预期 3608，加入本报告后预期 3615）。后两条与 R3607 终态的失败类型一致。
- 既有行覆盖目标 115/115，通过 11/11 核心路径覆盖率下限，覆盖 83/662 模块。覆盖报告写入临时目录。
- 既有 93 个分支覆盖目标在隐藏桌面执行 1775 条，1771 通过、4 跳过。94/94 个 L0/L1 模块达到既有下限，双向决策点 1538/2737。覆盖下限未改。初跑本地技能夹具不完整，补齐后复跑通过。
- 增量 `--gate` 台账在本工作树展开到 749 个文件，取消该运行以避免重复全量。受影响冒烟和显式定向命令承担本批增量验证。以 `R3614-FAIL` 提交失败检查点，保留环境、状态头及已复现的历史回归证据。

## 严格闭包交接

| 诊断 | 结果 |
| --- | --- |
| `gate` | 消除。会员查询由 L4 显式动作执行 |
| `begin` | 消除。准入后登记，登记失败终止派发 |
| `pet._emit` | 保留在注册器 `_fail`。会员拒绝已由 L4 发布。制作锁拒绝、分镜输入读取失败／无输入、Animatic 待人工确认仍共享旧出口。后续迁移需保留各路径的手动返回值、自动单次终态、已登记运行序号与人工确认语义 |
| `desktop.pet_report` / `desktop.open_storyboard_skill` | 分镜已就绪回报与打开分镜任务 |
| `desktop.show` | Animatic 切页入口 |

桌面桥接的 9 条另有范围。A11 及总任务书仍未收尾。
