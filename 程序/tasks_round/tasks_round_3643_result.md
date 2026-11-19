# R3643 — A11 第七批桌面桥接收口
<!-- round-evidence: {"commit_base": "c98dd0c1", "credential_hits": 0, "evidence_sha256": "8cc22ed26a582bdd", "exit": 0, "failed": 0, "passed": 81, "round": 3643, "tests": "run_selftests.py -k test_dynamic_import_registry test_desktop_auto_state test_unattended_chain_tables test_continuity_scope test_idea_request_lifecycle test_module_size_ratchet test_no_circular_import test_complexity_ratchet"} -->

1. §3.3 结构治理轮。执行《六层架构收口与企业级演进任务书》A11 第七批，改动 3 个生产模块。轮次分配与校验在专用工作树 `3413` 完成。
2. 默认冒烟 8/8，加隐藏桌面探针为 9/9。受影响门禁 11/11，隐藏桌面定向 102/102。完整架构 602/605，失败集合见下节。
3. 严格入口诊断由 9 条降至 0。共享安全全量最近绿凭据为 R3633，本分支未运行安全全量。状态页轮次为 3409，加入本报告后期望 3644，由合入车道同步。

## 压缩检查点

- 检查点 `c98dd0c1b5a4a035d186eef5b7152f337c8d3228` 以共同基点 `0e3fc76355eaa63cecb2d8220ea2f7fdb0842787` 为父提交，提交说明记录来源与 tree。
- 原起点 `4e8deeeac1f26678219177f754de57ed38f4658b` 和检查点的 Git tree 同为 `02aab876d2faf6832fab13bf93d7e64b73d73c2f`。按领号脚本同一口径，源码提交数从 11 降为 1。原分支仍指向 `4e8deeea`，新分支为 `codex/architecture-a11-compact`。

## 行为与红绿证据

- 基线严格扫描只拒绝 `ui/desktop_pet_bridge.py`。未注册时间调用 1 条，未解析名称查表 2 条、继承动作 3 条及反射开关 1 条，阶段键与条件各 1 条。新闭包用例先红，报告全部 9 条。受守卫参数的用例先红，报告 `(5, 'unresolved-key', None)`。最终全域扫描检查 3 份入口报告、4 次注册器启动调用，桥接进入点 2 处，总诊断为 0。
- 桥接使用现有 L3 启动入口和 L4 运行注入。阶段键验证首语句须确认有限字符串域，守卫拒绝未知键、未知目标、未知条件、参数改绑及发生在守卫前或嵌套作用域的调用。开关表持有明确设置函数，旧字符串表从同一来源导出。轮询唤醒沿用退避、忙碌和项目判断。剧本结构、连贯性、首帧仍分别走原处理器。
- 直接派发测试验证三个阶段分别调用一次，处理器返回 `False` 或抛异常时结果原样传递。开关测试验证单次登记、设置与唤醒，含可处理的写入异常，并断言无额外事件。既有用例覆盖单次启动 Agent、切页、事件，取消、替换、切项目、关窗拒绝迟到结果。无 Tk 的生命周期和既有阶段定向为 57/57，合并命令契约与状态表定向为 109/109。
- 仓库行覆盖脚本定向 59/59。桥接 45/109，三虎阶段接线 128/895，状态表 86/100，227/662 个生产模块有行覆盖。
- 在临时项目经正常启动入口实测资产、定稿、预演、视频、粗剪、交接六个轮询开关，均真实落盘。
- 增量门禁按共享台账选中 749 个文件、1020 路工作单元，外层 900 秒超时，无完整通过凭据。超时前记录上述三条架构红项及部分范围外服务红项。单独复现的两条首帧事件测试在发送事件前被图片校验拒绝，返回「首帧图片损坏或解码器不可用」。本轮未补历史测试夹具或图片工具。

## 完整架构失败集合

R3632 基线 601/604。首轮 601/605，新增红项为三虎阶段接线模块超出 1202 行上限。已将派发实现移回桥接模块。最终全跑 602/605，行数棘轮通过，失败集合与 R3632 相同。

| 既有失败 | 原因 |
| --- | --- |
| `test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only` | 本树缺 `程序/维护记录/基准历史.json`。 |
| `test_round_baselines.RoundBaselineTests.test_round_number_continuous` | 分支状态页为 3409，R3643 后期望 3644。 |
| `test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references` | 本树缺 00 全流程包的 `screenplay-gate-engine.md`。 |

## A11 收口与 A12 交接

- A11 前六批证据为 R3595、R3600、R3607、R3614、R3626、R3632。本轮封闭最后一组阶段入口，保留 13 阶段与 2 个辅助指令。A11 专项与完整架构状态分别以本报告实测为准。
- A12 接续 A6 的清单，逐项核验产物异常退出恢复、资源上限和 UI 长任务响应，引用已有验收后再补缺。本轮范围止于 A11。
- 按 `R3643-FAIL` 保存检查点，随本报告提交机器证据。提交前定向 81/81，凭据扫描 0 命中。
