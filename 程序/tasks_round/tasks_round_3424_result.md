# R3424 — A9-2 登记入口未知层与冲突拒绝
<!-- round-evidence: {"commit_base": "95a5d713", "credential_hits": 0, "evidence_sha256": "96a39914921a83f8", "exit": 0, "failed": 0, "passed": 28, "round": 3424, "tests": "run_selftests.py -k test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map"} -->

## 三问
1. 类型：AGENTS §3.3 结构治理轮（执行子场景）。来源《六层架构收口与企业级演进任务书》A9、R3411 G/I/J/K、R3416 J、R3419 F 及父任务对 A9 第二批的明确授权；不启动下一轮，不宣称 A9/任务书整体完成。
2. 测试：先负例后正例；冒烟8/8＋隐藏探针通过，精确定向97/97，改后完整架构549项、546通过、同一2 failures＋1 error；新增4项全过，无新增架构失败，整体未绿。
3. 欠账：本批收口登记入口接受未知层和静默覆盖层级的问题；包身份、未登记模块、包初始化扫描、动态注册及 TOOLS 分类尚未收口。没有调整层级条目或豁免。

## A. 基线、领号、scope 与所有权
- 基线 `95a5d7133610a8917ca2d793218ecf9d6824557e`（A9-1 检查点）；初始树干净、detached HEAD。新建 `codex/architecture-a9-identity-boundary`，`round_claim.py next` 领取 R3424；队列 show 未发现本子批匹配项，不冒领其他任务。
- `dev.py scope` 检查 96 条活跃分支，26 条有重叠、70 条无重叠、errors 为空。其中 21 条含 `_layers.py`，逐一读其登记函数，均保留未校验的直接赋值实现，没有本批等价修复；A9-1 的 test_layers 改动已在基线。L1 `ea9f94ed`、foundation `b30f63b6` 为原 owner 的登记/业务交付，不抢改生产模块。仅在 architecture §3 增补本批语义，不替换其他车道的分层表。
- 实施模块仅 3 个：`tests/architecture/_layers.py`、`tests/architecture/test_layers.py`、`architecture.md`。结果及 evidence 属轮次记录；不改 `_scan.py`、环消费者、五个生产环模块、master、project_status 或私有/忽略文件；不推送。
- 本树没有随附解释器，首次路径检查失败后核实并借用 `D:/漫剧制作助手/运行环境/Python/python.exe`，统一 UTF-8；未复制运行数据。早期猜测的 owner 分支名和部分脚本/测试路径不存在，改用 scope 实际分支名及精确文件搜索完成核对，不把失败读取当证据。

## B. 先检验前提与缩小范围
- 当前 `module_scan_files()` 有 6 组同 stem：file_index、file_index_contract、file_naming、global_library_service、legacy_migration、storage_maintenance；另有 16 个包实体未登记，及 4 个已知顶层 TOOLS。完整身份迁移必须同时处理扫描器、层级表、实际消费者、权威/生成视图，不能在本批三模块内可靠强启用。
- 临时隔离包树：`contract/shared.py` 写 `from ui import shared`，层级图分别登记 contract.shared=0、ui.shared=4，旧实际 `_upward_pairs()` 返回空集，证实身份漏检；`contract/__init__.py` 写同样导入，现有扫描集不含该文件，证实初始化盲区。这两项只是 A9-3 输入，本批未声称修好。
- 登记字典本身能区分 contract.shared 与 ui.shared，也能区分 contract 与 contract.__init__；正例通过，不能把扫描器的折叠误说成字典的同名碰撞。按授权缩小为**已提交登记的层级值及同一精确键的重复登记语义**，不新建第二套身份扫描器。
- 真实坏样本：`_register(None, 'client')` 后 client→high 的实际分层扫描返回空集；`_register(4, 'high')` 后 `_register(0, 'high')` 静默覆盖，越层告警可消失。包初始化/跨包同 stem 名称亦经登记样本覆盖，不将其扩大解释为真实包扫描已启用。

## C. 改前负例、实现与正例
- 4 个计划永久测试先注入实际 test_layers 模块命名空间，在旧实现运行：4 方法、13 failures（subTest）、0 errors，exit1，0.004 秒。关键失败 `AssertionError: ValueError not raised`：未知层 7 例、同一键冲突 3 例、实际越层告警保护 3 例；不同包同 stem、包名/初始化名独立登记、合法层级及同层幂等是原本通过的正例。
- `_register()` 先校验层级为 int/float 且存在于 LAYER_NAMES，再校验全部名称是否与已登记值冲突，最后整批赋值。拒绝 None、bool、字符串、NaN、越界/未知数值；冲突失败不留下先写的 new_module。现有 responsive_ui 同层重复登记继续允许。
- 永久 `LayerRegistrationCanaryTests` 使用真实注册函数；最后一项调用实际 `_upward_pairs()` 和 LayerDirectionTests 守卫，证明拒绝错误登记后原越层边/告警仍在。A9-1 的 PackageImportCanaryTests 原样保留。
- 改前后 LAYERS/TOOLS 规范 JSON 完全相等：411/5，SHA256 `2c8ed600a35862467f8efae3be82fb248cd431d35da84f6b8bacab1f444cd7ed`。静态18/动态2豁免未改，层级/扫描集/动态行为未改。

## D. 适用验证与完整架构对照
- 改前 `python -B smoke_test.py --architecture`：545 项，542 通过，2 failures＋1 error，324.463 秒，exit1。
- `python -B smoke_test.py --affected test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map test_branch_coverage_entity test_selftests`：实际选择7文件（关键词亦匹配 test_selftests_gui_token），97/97、0 skip，25.3秒，exit0；8项默认冒烟＋隐藏探针＋定向门禁共10/10。覆盖新增4方法、A9-1原3方法、既有环、自审、生成索引及两个非架构消费者；其余架构消费者由完整架构覆盖。含Tk测试经自动隐藏桌面执行。
- 改后 `python -B smoke_test.py --architecture`：549项，546通过，2 failures＋1 error，308.260秒，exit1。自动比较改前/后完整失败ID集合完全相同（3项），新增4个canary全通过。结果文件已存在时状态轮次断言为3409 != 3425。无新增测试模块，规则11生成索引一致性通过，无须重写生成稿。
- 标准 evidence 精确定向：`run_selftests.py -k test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map`，28/28、exit0；凭据扫描0命中。此重复运行仅为标准提交生成真实机器证据，不扩大/重复全量。
- 三项既有失败：`test_agents_md.AgentsMdConsistencyTests.test_performance_history_is_declared_as_historical_only`（缺维护记录/基准历史.json）；`test_round_baselines.RoundBaselineTests.test_round_number_continuous`（改前 N=3409、M=3419）；`test_skill_reference_injection.SkillReferenceInjectionTests.test_script_stages_name_only_their_approved_00_references`（缺 screenplay-gate-engine.md）。不复制私有记录/技能，不删除断言。
- 安全全量未运行：仅登记入口校验，没有改任何实际层级登记、生产逻辑、启动/Tk/删除语义；本功能分支无 master 累计触发。合入前由主干按 AGENTS §5 重判层级登记相关触发。`dev.py debt` 实读上次绿色 R3293、最新 R3419、源码轮次23/线8，主干 False、后台触发 False；最近后台全量 HEAD 0e3fc76 退出1，四个历史失败文件与 R3419 交接一致，未改 receipts。

## E. 提交与状态
本批使用标准 `scripts/dev.py commit -m "R3424-FAIL: A9登记入口未知层与冲突拒绝及既有门禁阻塞" --tests test_layers test_no_circular_import test_gate_selfaudit test_rule_guard_map` 保存检查点，不标整体绿色或 [TASK_COMPLETE]。仅功能分支记录本结果，N=3409、M=3424，N=M+1 不满足，父任务合入轮须按实际最新结果更新状态页（本结果对应3425）。

标准入口的 ROUND_MESSAGE_RE 仍只匹配 `R数字:`；沿用R3419方式，先显式执行原 `round_evidence.py 3424 -k ...`、再由原 `stamp_result()` 写机器头并暂存 evidence，未改提交脚本或跳过测试。检查点提交哈希由 `git log -1 --format=%H -- 程序/tasks_round/evidence/R3424.json` 唯一定位，最终交接给出完整值，避免自引用哈希。提交白名单仅三模块、本结果、evidence/R3424.json；`git diff --check` 通过，无受忽略文件，完成后核验干净工作树。

## F. A9-3 精确输入
1. H01：以 R3419 的增强解析为底，先设计包限定身份与薄门面 alias 映射；6组同 stem 必须逐项核验兼容/副作用，保留包初始化独立节点。补上未登记16实体及未知本地目标的分类策略。不要把本批“拒绝已登记的未知层级值”说成“所有未知模块已拒绝”。本批登记函数保持字符串精确键，不提供扫描身份转换。
2. 完整身份批次须同步 `_scan.py`、`_layers.py`、实际分层/环消费者、architecture 与必要生成视图；若仍超过3模块继续拆为可独立验收项，先影子差异与同 stem/初始化坏样本，不增豁免。规则11现行索引仍映射 test_layers，不因本批新增测试类而改生成稿。
3. 环迁移继续等待 L1 对 api_endpoints/diagnostic_capture/model_metering/model_pool/request_ledger 的拆环证据；本批未触碰这些生产模块或迁移环扫描。
4. H03/H09 动态注册目标与未知键、TOOLS 的实际生产组件分类、ASR独立运行闭包另拆批；接收原 owner 等价交付，不增加新依赖或第二网络/存储/钱包入口。
5. 三项既有失败分别交付/主干状态/A14 owner 处理，父任务合入后复验完整架构；本任务到本批提交即止，不启动 A9-3。
