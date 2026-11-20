# R3365 — 修复轮：地基加固 V2 A3 取消前缀猜值与未知窗口拒发
<!-- round-evidence: {"commit_base": "9e3d1924", "credential_hits": 0, "evidence_sha256": "5fec530d2fda5624", "exit": 0, "failed": 0, "passed": 85, "round": 3365, "tests": "run_selftests.py -k context_budget writing_context_budget_guard skill_budget skill_deep_inline test_writing_restart"} -->

## 三问

1. **本轮类型**：§3.2 修复轮；任务书 V2 A3 的上下文窗口策略纠错。生产范围限定三个模块，不实施 A4 唯一入口收敛。
2. **测试与三个基线**：已先红后绿；首批 42 项及官方 58 项定向通过、默认冒烟 9/9（含隐藏桌面探针）。跨层架构首跑 532 项，529 通过、2 失败、1 错误；具体未绿集合及恢复后复测见下。完整消费者回归已中断，不能称全部验证完成；当前 100 项消费者定向为 99 通过／1 既有 SSE 接缝错误，详见下。没有运行完整安全全量，不生成或冒用整体绿色凭据。`dev.py debt` 当次只读输出上次全量 R3293、最新结果 R3365、源码轮次 10／线 8、主干 False、后台触发 False、红后冷却；另提示 main HEAD `92b8182` 在 16:07:23 的旧后台全量失败清单，不把该历史失败当本树回归结论。
3. **欠账少了吗**：删除按模型名称猜窗口的生产逻辑；API 未知窗口明确拒发，CLI／桌面无 API 窗口仍允许任务工件，300,000 字符硬闸保持。分支覆盖率快照因真实 AST 决策点 25→22 待 root 整合后统一真实测量；不改共享快照、下限、登记表以制造全绿。

## 执行契约（V2 §12）

| 字段 | 本轮事实 |
|---|---|
| 目标 | 同一模型名空窗口不能被前缀或旧 preset 快照赋值，API 在网络／RPM／计量预留前拒绝；显式已知窗口和 CLI／桌面交付保留 |
| 范围 | `contract/workflow_context_budget.py:preset_context_length`；`orchestrator/skill_inline.py:_skill_inline_budget`；`writing_api.py:WritingRequestAdapter.__init__/_call`；相应行为测试与本报告／工具 evidence |
| 前置 | 原任务书 V2 A2 调查验收允许 unknown；已读当前历史对象 R3318（7145f810）及 R3332（f09fe613）和 V2 A2/A3/A4/§12；按本次用户纠正撤回旧报告的过度前置解释 |
| 验收 | 未知 API 返回稳定 `context_window_unknown` 且 transport/RPM/ledger 零调用；同名显式窗口成功；显式冻结快照不被中途池变化影响；CLI 未知窗口完整任务交付，超过 300K 字符仍拒；原输出预留／安全余量断言保持 |
| 风险 | 用户此前依靠猜值的 API 请求改为安全拒绝；提示在模型管理补填 `context_length` 或核实供应商窗口，不自动换模型 |
| 回滚 | root 整合前可正常 `git revert <本轮交付提交>`；不回写真实模型池／私有配置，不接受猜值作为应急窗口 |
| 车道 / owner | 独立 `codex/foundation-context-policy`，子会话 `context-policy-a3`，基准 `9e3d1924b0595544242566809f594d962ec48154`，正常全局领号 R3365，无对应队列任务 ID |

## A2 前置解释纠正：允许未知的调查验收已经满足

V2 A2 要求「查不到真实值的模型，留空并明确标注未知」，验收要求三列「模型名｜窗口值｜来源」，空值项明确「未知，待补」。R3318 已调查原 10 项：只有一项 Google 官方直连确证并填值，其余 9 项 unknown；R3332 的只读目录没有给出中转部署窗口，保持 unknown。**这满足 A2 允许 unknown 的调查验收，不表示 10 个窗口全部补好。**

A3 前置字面为「A2 完成（或确认剩余空值模型不在活跃使用中）」。此前把活跃保存选择 `gpt-6-sol` unknown 视为永久阻塞，超出了 A2 明确允许 unknown 和 A3「未知即拒绝」目标。按本次用户明确纠正，撤回该过度门槛，允许实施 A3 安全拒发。不宣称剩余 unknown inactive，不修改真实模型选择、不猜数值、不探测收费推理 API。

## 根因与最小修复

事实：改动前全仓 grep `preset_context_length`／`PRESET_CONTEXT_BY_PREFIX`，生产消费者恰为 `writing_api.py` 与 `orchestrator/skill_inline.py` 两处。旧测试断言 `gpt-4o→128000`、`qwen3→32000` 等，锁定了任务书明确废弃的错误契约。

- L0 删除前缀表，保留 `preset_context_length(model_id)` 兼容函数并标记 deprecated，恒返回 `''`；未增加 L1 模型池导入，仍为纯函数模块。
- `skill_inline` 只采用显式窗口；API 未知抛出带 `context_window_unknown` 和可操作提示的错误；CLI／桌面未知返回无 token 窗口模式。完整 SKILL 正文装载、已知窗口引用预算与 300K 字符硬闸保持。
- `WritingRequestAdapter` 删除名称 fallback，API 未知在 reasoning、网络、RPM 等待、RequestLedger 构造与授权前返回结构化拒绝；已知显式窗口的输出预留、安全余量、字符限制和已报告用量逻辑保持。
- 旧冻结快照 `source='preset'` 不能继续冒充确证窗口；只有匹配模型的显式来源快照可补足冻结窗口。保留同模型显式快照与在途请求冻结的回归，不扩大到 A4 sender、ModelAdapter 共同入口、端点策略或配置迁移。

## 真实红绿证据

| 阶段 | 命令／观察 | 真实结果 |
|---|---|---|
| 首红 | `python -B -m unittest tests.test_context_budget_model tests.test_skill_context_budget_prestage tests.test_skill_budget_send_entries -q` | 41 tests，13 failures + 1 error。前缀断言明确返回猜值；同名空窗口已发生 synthetic HTTP 请求而非零传输；初加直接适配器测试因走入 mock 发送结果暴露 error。subTest 失败数不是 13 个独立产品缺陷 |
| 首批绿 | 上述三个文件，补 CLI unknown 字符硬闸用例后 | 42 tests / 1.831s 全绿；中间修正 CLI 测试 helper 原先只接受有 token 预算/必 skipped 的假设，分别断言已知预算与未知 CLI 完整正文，未 skip／删除旧成功断言 |
| ledger 断言修正 | 首次新增 patch 错把 `rate_limit` 当实际入口 | 官方定向指出 AttributeError，改用实际 `wait_for_rpm` 与 `infra.pet_llm.RequestLedger`，零调用断言真实覆盖生产边界，不记作产品错误 |
| 官方初次补全 | `run_selftests.py -k context_budget writing_context_budget_guard skill_budget skill_inline` | 56 tests / 4 files 全绿；有意废弃 prefix 成功测试改为 unknown 拒发，known 合成 fixture 显式 128000 保持成功断言 |
| 旧快照先红 | 两个 legacy preset 行为测试 | 2 tests，2 failures：writing 返回 True、skill_inline 不抛异常，证明旧 preset 快照可绕过 |
| 旧快照绿 | 同一官方定向 | 58 tests / 4 files / 1.8s，全绿、0 skip；显式 snapshot 成功和冻结记录不重查池的测试仍绿 |
| 默认冒烟 | `smoke_test.py` | 9 通过 / 0 失败，隐藏桌面 `--probe` 通过；任务书历史口径 8/8，按当次实测报告 |
| 跨层首跑 | `smoke_test.py --architecture` | 532 tests / 255.149s：2 failures、1 error，其余 529 通过；未称全绿 |

首跑架构未绿集合：

1. `test_agents_md.test_performance_history_is_declared_as_historical_only`：本独立树缺忽略文件 `维护记录/基准历史.json`，不是生产变更。随后从原树仅复制该项，不纳管。
2. `test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references`：新树 00 公共 gitlink 目录为空。根据登记文件及 root 提供的 common-dir 官方缓存，核验固定提交 `1a43ae5a019d157eb3d45ad73e800081cb127763` 的 tree 为 `d9a208042147179768f0a24dc54bdfbd5374a9e9`，再将对应固定 archive 解入已确认空目录；gitlink 指针不变、不纳管公共展开文件。
3. `test_branch_coverage_floor.test_baseline_decision_points_match_current_entities`：`workflow_context_budget.py` 快照 25 点／当前 22 点。是删除 3 个前缀分支的真实源码变化；按 root 明确指示，本轮不改共享覆盖率快照／floor，整合 A1/A3/其他车道后由 root 用统一完整 targets 实测刷新。本轮另存真实定向 measurement，不拼接成整体绿快照。

## 消费者回归、资源复测与测量

资源恢复后，`run_selftests.py -k architecture.test_agents_md architecture.test_skill_reference_injection` **24 tests / 2 files 全绿、0 skip**。仅恢复公共测试资源，不改门禁或真实配置。

消费者初次 `smoke_test.py --affected writing_api workflow_context_budget skill_inline skill_deep_inline` 实选 35 files / 50 units，runner 自迁隐藏桌面并串行；执行中宿主丢失 job 句柄，持久 receipt 只有 start/PID 无 exit，wrapper 与 child 均已不在，进一步核实本树无隐藏后代进程，日志停在 GUI 排队。**该次终态为 unknown，不统计整体通过或失败。** 随后以 `Start-Process` 脱离宿主重新启动同一个 official runner，并验证 wrapper／child 持续存活。已完成的非 Tk 部分含 `deep_inline`、guard、restart 等；余下隐藏 Tk 消费者正常等待其他车道有效 GUI 令牌。实际调用图表明广域 35 文件中仍有 `writing_api`／`idea_chat`／Tk 真实消费者，不能全视为无关 substring 匹配。为向 root 交付可整合的源码检查点，明确保留这些必要消费者未完整验证；在先核精确 PID、父子关系、启动时间与命令后，只结束本树 child 68140 进程树，wrapper 63812 正常 finally 写入 **exit=1／finished**。此为 **interrupted 源码检查点**，不是官方 deferred，不把人工中断算产品失败或通过，不以任意等待时长替代验收。未修改产品 runner 或隐藏锁、不重复领号；root 整合后须补完整消费者验证。

精确消费者定向首先定位到两处此前依靠前缀的 `claude-test` 合成 fixture：`test_api_cache_usage.py` 固定缓存正文、`test_writing_restart.py` 原生 Claude 重写各加明确合成 `context_length=200000`，原成功及正文断言全部保留。复测 **100 tests / 8 files：99 通过、1 error**；58 项核心、deep inline 11 项、restart 11 项、restart intent 5 项及缓存固定正文均通过。

唯一 error 是 `test_api_cache_usage.StreamUsageTests.test_stream_requests_usage_and_reads_the_final_usage_chunk` 的 `seen[0]` IndexError。它只调用 `model_pool.http_stream→api_endpoints.http_stream`，不经 A3 任一生产修改；基准 HEAD 的 `_http_opener` 已用 `RequestsJsonOpener`，旧测试仍 patch `urllib.request.HTTPSHandler`，因此列表为空。通过 `git show HEAD:程序/tests/test_api_cache_usage.py` 导出原始测试原文，隔离单跑同一 StreamUsageTests **1 test / 1 error**，复现相同 IndexError；`infra/model_pool.py`、`infra/api_endpoints.py`、`contract/platform_tools.py` 对 HEAD diff 均为空。root 已确认原 main R3359 HTTP 专用线已有修复，本轮不重复改传输测试接缝，整合时保留该修复。

所有含 Tk 的测试由既有 runner 进入隐藏桌面并排队；本轮不抢占其他车道有效 GUI 令牌。wrapper 用 try/finally 记录 child PID、绝对日志和退出 receipt。

另存真实覆盖率测量：`scripts/branch_coverage_report.py tests.test_context_budget_model tests.test_writing_context_budget_guard tests.test_skill_context_budget_prestage tests.test_skill_budget_send_entries tests.test_skill_deep_inline --json <临时另存JSON> --quiet`：**69 tests / 12.051s 全绿，`workflow_context_budget.py` 16/22 = 72.7%**。这五个定向测试仅为本轮消费路径测量，不是共享基线原完整 targets：工具的整批模块总量虽为 91、44/2664，也不能拿该低覆盖定向结果覆盖原完整快照。原 floor 和共享 ledger 均未写入。root 应在整合后用统一完整 targets 重测，不能拼接不同 targets 的单行成总绿。临时原始测量和 receipts 随交付保留 common-dir 证据路径，不纳管运行产物。

## 边界、四态与提交

| 状态 | 真实结论 |
|---|---|
| 已实现 | A3 三个生产模块及对应行为回归已实现；无新生产模块 |
| 已验证 | 核心策略、默认冒烟、资源门禁24项、定向覆盖率69项已验证；消费者100项为99绿／1既有SSE红。必要广消费者中断未完成，架构快照25→22待root统一刷新，**A3全验证未完成** |
| 已合入 | 否；仅当前独立 source 提交，未合 master，由 root 保留 A1 后整合 |
| 已发布 | 否；未 push、未发布，不修改用户模型配置或在途模型选择 |

fresh scope 核验：当前工作树对起点源码/索引为空起步；`shared_layers`、`tests/architecture/_layers.py` 和 `维护记录/架构统一基数.json` 不在本轮改动清单。它们与移动中的 master 差异是 master 后续 L2 合入，不把 incoming 与 master 相等误报为独有，不修改／暂存他人车道、DPI／其他 UI、运行配置、private 或 A1 probe/token learning 文件。

任务书全部任务未完成，本轮不生成全书完成声明。A4 后续由新 child 两阶段实施。安全全量本轮未运行，整体地基任务不得标完成。提交只通过正常 `dev.py commit --tests` 精确列文件；本轮工具版本无 `--files` 参数，使用 `--` 结束 `--tests` 再传相对 `程序` cwd 的位置文件路径，保持相同精确边界。首次误传 repo 相对的 `程序/` 前缀，正常工具报 `程序/程序` pathspec、exit128；随即读回索引仍空、无提交，改正 cwd 相对路径后重试，未绕开门禁。提交自身 hash 仅在交付消息返回，不为补 hash 再提交同轮文档。
