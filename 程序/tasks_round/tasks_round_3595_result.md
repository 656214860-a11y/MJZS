# R3595 — A11 第一批阶段配置消费接线
<!-- round-evidence: {"commit_base": "0dc27b34", "credential_hits": 0, "evidence_sha256": "99e929f57da36f0d", "exit": 0, "failed": 0, "passed": 131, "round": 3595, "tests": "run_selftests.py -k test_stage_command_contract test_dynamic_import_registry test_manual_gate test_manual_plan test_desktop_async_tasks test_desktop_automation_service test_desktop_close test_idea_request_lifecycle test_project_switch_guard test_silent_exception_ratchet"} -->

1. §3.3 结构治理轮。起点 `0dc27b34`，工作树 `2e62`，切回既定分支 `codex/architecture-a11-stage-consumer` 后由中央入口领取 R3595。队列无对应开放项。改动限三个生产模块。
2. 默认冒烟通过 9/9，含 8 项业务检查和隐藏桌面探针。定向、受影响回归、完整架构及覆盖率见下。
3. 收口一条 L3→L4 动态依赖并拒绝未知阶段键。严格阶段闭包与完整架构仍有未通过项目。中央安全全量最近绿色轮次为 R3544，本轮未启动安全全量。

## 行为与边界

- 复核 R3409、R3494、R3506、R3586 报告和标准凭据。起点源码重扫在 `orchestrator/stage_models.py:252` 实得 `upward-target`。真实入口是手动制作选择「修改配置」，由 `manual_command` 调用 `open_config`，旧路径经 `module('skill_panel').show` 打开面板。
- `ui/ui_stage_popups.py` 在现有 L4 组合入口注入一个配置呈现器，并在用户选择配置时通过原注册键懒加载面板。`orchestrator/stage_models.py` 只消费呈现器。配置路径调用一次，返回 False，执行动作不启动。呈现器缺失或异常时显示原失败文案。手动动作明确返回 False 时向调用方传递失败，保留返回 None 的旧动作。
- `orchestrator/stage_handler_registry.py` 依据 `pet_bus.STAGES` 和既有 `pet_performance`、`pet_test` 校验键。未知键在触发门禁、回退和事件前抛出 ValueError。保留已知键的手动/自动门禁、条件分发和 fallback 调用。同一动作经原入口，改动没有第二份注册表、执行状态机、发布写入或重试入口。
- 运行时注册检测与 AST 阶段审计复用原路径。审计仅增加识别字面序列中展开的 L0 `STAGES`，没有新增豁免。重扫 L3 配置消费者及 L4 呈现器均无目标错误。严格生产阶段闭包仍拒绝 27 条，注册器 18 条（16 个未解目标、2 个未解条件），桌面桥接 9 条（1 个未登记目标、6 个未解目标、1 个未解键、1 个未解条件）。
- scope 显示与 A9/A10 共用现有审计文件，及若干 foundation 车道共用阶段注册器或测试。修改仅在本分支提交。后续合入需逐项复核这些文件的交叉改动。运行使用只读来源的随附 Python/FFmpeg，专用树从 R3586 对应工作树恢复测试所需的基准历史与三个固定技能包内容。

## 红测、回归与覆盖率

- 旧手动动作明确返回 False 时，外套实测返回 True。旧注册器对未知键实测调用 fallback，手动/自动都返回 `ran`。终态定向直接跑阶段命令、动态注册及手动命令 53/53。项目切换拦截与同项目请求凭据 10/10。
- Desktop 生命周期用例 20/20，验证取消、替换、关窗及成功/失败各仅交付一次。切项目由在途拦截与请求项目身份校验覆盖。本轮配置呈现器为同步调用；未验证远端任务取消后的落盘行为。
- 标准机器定向 131/131，退出 0，凭据扫描零命中。按三个改动模块执行的受影响冒烟 10/10。额外纳入未改动的 `stage_exec` 时，首轮缺 FFmpeg 路径导致首帧解码失败，失败模块包含在上述绿色受影响复验中。较宽集合的整组重复复验仍在等待其他工作树的 GUI 令牌，停止该重复请求。未终止或绕开其他工作树的测试。
- 现有十组行覆盖目标 115/115，83/662 个生产模块有覆盖，11 个核心路径均达到原定下限。快照与阈值不改。
- 现有 93 组分支覆盖目标在隐藏桌面执行，共 1775 条，1773 通过、2 条登记跳过。94 个 L0/L1 模块全部达到原定下限，1536/2737 个决策点双结果覆盖。首跑缺 FFmpeg 路径导致三项首帧相关用例失败，重跑使用随附 FFmpeg。

## 完整架构

- 终态 `smoke_test.py --architecture` 执行 603 项，601 通过、2 失败，耗时 411.730 秒。与同一起点 R3586 的失败集合相同。
- `DependencyWhitelistTests.test_site_packages_whitelist`：借用环境含白名单外的 `annotated-types`、`pydantic`、`pydantic-core`、`typing-extensions`、`typing-inspection`。
- `RoundBaselineTests.test_round_number_continuous`：专用树继承的状态页轮号不连续。
- 静态分层、循环依赖、动态注册以及阶段闭包的拒绝行为测试通过。严格闭包诊断从 29 条减少到 27 条。修复过程出现的静默异常门禁已通过 `app_logging.swallowed()` 消除，终态无本轮新增架构失败。

## 提交与接续

- 本轮按专项、受影响及完整架构验证，未运行共享台账的 `--gate` 或安全全量。安全全量凭据保持 R3544。专用树继承的状态轮次为 3409，该树最新结果为 3595，状态页预期应为 3596。状态页只能在 master 的合入轮同步。
- 后续按诊断来源拆批。先收口 `stage_handler_registry.py` 内条件与目标的证明，逐项区分有类型依据的宿主协议、外部调用和真正缺边。再收口 `desktop_pet_bridge.py` 的阶段键来源及条件回调。每批用严格入口重算诊断，避免复制阶段状态机或扩大到 L1/L2 车道。项目发布取消、技能文件与台账事务等 A3 消费问题仍需独立验收。
- 本轮只保存第一批检查点。提交哈希由 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_3595_result.md` 定位，标准定向和凭据扫描见 [R3595.json](evidence/R3595.json)。
