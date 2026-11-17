# R3273：SKILL 上下文预算任务书第一轮——前缀预设与未知窗口契约
<!-- round-evidence: {"commit_base": "5beeb194", "credential_hits": 0, "evidence_sha256": "cf4624ac91b53484", "exit": 0, "failed": 0, "passed": 25, "round": 3273, "tests": "run_selftests.py -k context_budget_model skill_deep_inline"} -->

## 三问

- 类型：§3.2 修复轮；任务书第一轮，仅落实纯函数预算契约，发送链路 T1/T2 留第二轮。
- 验证：定向 25/25，默认冒烟实测 9/9；架构 502 条、2 失败 1 错误（改动前基线，见下）；本轮未跑全量，不引用历史绿色作当前通过。
- 欠账：第一轮纯函数完成；原始故障尚未修完，未宣称完成。架构基线三个问题记录待合并前闭环。

## 授权与执行边界

用户授权分析诊断报告、按任务书逐轮实施、每轮启动下一子会话并最终合入 master。当前功能工作树分支由中央领号入口创建为 `codex/wip-r3273`，实际领取 R3273（任务书原建议轮次不再占用）。

任务书新增执行复核补充：修正错误程序根、快照二次查池、API/CLI 区别、包装/提示漏计、最终完整请求预检与假绿验收。R3269 是未领号历史草稿，仅作调查线索；归档前已脱敏用户项目路径，不作为测试凭据。

## 改动

1. `contract/workflow_context_budget.py` 新增用户指定的应用默认容量表及 `preset_context_length`；明确不是厂商所有型号真实保证。模型家族区分大小写无关，版本/分隔符后缀允许，拒绝相似词误匹配。
2. `skill_inline_token_budget(0/None/空/负值)` 返回 0；已知正窗口原算式不变。相应 None→0 是任务书明确的有意测试契约变化，不弱化其他断言。
3. 复用 `tests/test_context_budget_model.py` 与 `tests/test_skill_deep_inline.py`，新增/强化纯函数行为测试。

## 先红后绿

工作目录 `程序`；随附解释器，环境 `PYTHONUTF8=1; PYTHONIOENCODING=utf-8`：

`python -B run_selftests.py -k context_budget_model skill_deep_inline`

- 红：25 条，4 个测试方法失败（含 26 个失败子用例），exit 1。
- 绿：25/25，0 跳过，0.8 秒，exit 0。
- 原始日志：common-dir `task-logs/R3273-round1/red.log`、`green.log`。可复跑测试已纳入本轮。
- `python -B smoke_test.py`：9 项通过、0 失败，exit 0。该版本不支持 `--probe`（首次 exit 2 已记录，改用当前 runner 支持的默认入口）。

## 三基线实测

- 默认冒烟：9/9（文档历史基线 8 不冒充当前实测）。
- 架构：`python -B smoke_test.py --architecture`，502 条，2 failures + 1 error，161.579 秒。失败集合：`test_round_number_continuous`（当前分支历史状态页头3264但已有3269草稿）；`test_script_stages_name_only_their_approved_00_references`（工作树缺固定版本技能包；按原始 traceback 更正最初口述误名）；`test_performance_history_is_declared_as_historical_only`（工作树缺未跟踪运行基准历史文件）。本轮未改相应实现/测试，后续合入前修状态及受控补齐测试输入，不降门禁。
- 全量：本轮未跑，最终集成将按用户要求跑安全全量，凭据以 common-dir 正式 receipt 为准。

## 提交与接续

本文件随本轮提交；commit hash 用 Git 中 `R3273:` 记录定位，避免自引用修改提交。尚未实发远端 API、未修改用户项目或生产模型池、未新增依赖。

下一轮自动启动独立子会话，落实 T1/T2 真实 API 消费、两阶段正文预留、发送模型快照贯穿及 CLI 兼容。第一轮不等于原故障修复完成。
