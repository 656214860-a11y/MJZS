# 风险与未知

- R1596 清单 O1–O12 已全部完成并合入 master，但每项只到其报告与门禁记录的范围；不得由此推定真实质量或真实成本已验收。
- 8项真实验收已由用户延期到实际使用阶段，详见[统一清单](../程序/说明/实际使用阶段待验收清单.md)。真实质量、商用许可、账单、剪辑软件兼容及目标用户体验均不得由模拟测试推定通过。O12 的真实账单核对同样延期。
- P0-4现有故障链包含模拟供应商和真实本地存储/编码；P1-4技术样例不证明第三方编辑器实导入或真实对白对齐。
- 金额预估依赖费率配置；未计价或账单缺失须保留未知。未知Comfy工作流在金额预算启用时会被拒绝；关闭预算不等于免费。实际GPU、存储、带宽与供应商账单尚未实测闭环。
- O10 的峰值门槛是进程内 tracemalloc，不含操作系统页缓存；超大媒体、跨卷移动、磁盘满等外部条件未实测。
- 溯源覆盖矩阵只登记本树可核验字段：文本/TTS 费用来源、字幕与交付链路未核验，本地工作流版本只记路径未记内容摘要，云视频种子与服务商可复现性未知。不得据此声称全链路可复现。
- 存储保护依据已登记来源，不能推断未登记的外部软件引用；同盘回收不等于释放容量。
- 最近成功完整安全全量属于 R1624（13dea0a，02:01:23 绿、502 秒、0 红、凭据 round 1624／内容树 bde64b00，架构门禁含在内）；此前的 R1619（b6863b4）是上一档真实全量。R1625／R1626 是文档轮，不冒称同树全量。
- 结构治理轮拆分的两类静默风险（R1624 实测各踩一次）：①方法或常量被迁走后调用点仍引用旧名字 → `NameError`（`pet_cloud_timing` 的 `SHAPE_ROUND`，由 `tests/test_static_names.py` 抓到）；②`patch.object(旧模块, 名字)` 在名字转出后失效、用例静默失真（`test_skill_notes` 的 `markdown_document`）。拆分轮必须跑一次「未定义名扫描＋补丁点审计」，不能只看被迁新模块自身的用例。
- `test_desktop_startup_perf` 的「首日选择框 1 秒内可见」在并发负载下会抖：d8d0fc5 的全量里红、单跑 14/14 绿。全量收尾阶段不要再并发跑自检，否则可能污染凭据。
- `本地CI.cmd exit`／`local_ci.py exit` 只到「默认冒烟＋静态门禁＋架构门禁」，**不等于全量绿**；全量仍需 `run_selftests.py --all --safe` 的凭据。
- 随附解释器是 3.15.0a2（alpha），标准库按设计裁掉 58 个模块（`tests/test_stdlib_closure.py` 的 `PRUNED`）：缺 `trace`／`symtable`／`sqlite3` 等属正常。迁稳定版时必须重新决定裁剪清单，不能沿用（R1626 §9）。
- R1676 已按用户授权提交 `程序/配置/SKILL/预设.json` 与 `.claude/settings.local.json`；后者是本机绝对路径配置，换机后需复核。`.claude/scheduled_tasks.lock` 仍按仓库 `.git/info/exclude` 的 claude-code-runtime 规则不跟踪（运行期 PID／会话锁）。

- 安全全量欠账：上次真实绿仍是 R1624（旧内容树）；截至 R1678 已累计 13 个源码轮次（门禁线 8）。后台已触发，但 `.wt/ci` 工作树当前不存在，上次运行在 `.wt/ci/程序/run_selftests.py` 缺失时以 `BrokenProcessPool` 退出（78 秒，非断言失败）；同段日志还有 `test_idea_inline_brief` 16 条中 9 条失败。后台补跑完成前不得声称当前树全量通过。
- R1654 已补齐 `distribution_manifest.md` 对 `data_model.md`／`runbook.md`／`task_states.md` 的声明（`test_distribution_selfcheck` 3/3、冒烟 8/8）；不要再把 R1625 的该项红当作当前阻塞。
- R1678 新增需求锚定门禁 `tests/architecture/test_requirement_traceability.py`：✅ 需求必须有测试锚点，基线 `维护记录/需求锚定基线.json` 记录现状欠账 152/298，只许减少；新增或修改 ✅ 需求须同轮补锚点。
- R1696 的维护脚本本身通过直接 unittest（9/9），但执行器证据不完整：`run_selftests -k aigc_package_diff` 汇总后未退出，`smoke_test.py --gate` 两次在跨树 GUI 令牌等待处 900 秒超时。不要把 9 条 0 红或默认冒烟 8/8 当成门禁通过；复跑前先确认无并行 GUI 自检会话。

完整旧记录见[风险归档](history/r1591-handoff-before/risks.md)。
