# R3818 结构治理轮：内建总控退役（验收进行中）

- 类型：§3.3 结构治理轮，用户任务书已指定执行范围；遵循最新修订“一次可运行完整提交”的工作包边界。
- 测试：已跑；默认冒烟9/9。定向基线53/53；改后分批154、174、65、72、43条全绿；完整架构580/580（283.854秒、退出0）。首轮全量诊断在GUI阶段异常退出4294967295，不能算通过、无凭据。后定向236条仅分发副本复制一次WinError2，单独复验分发自检`[]`通过；其余图像、首帧、传输、阶段锚点全部通过。20:48启动第二次完整诊断（4 CPU/1 GUI、有随包运行时与OpenSSL）；全量尚未结束，未生成干净树凭据。
- 欠账：专用代码和资源已删除；安全全量、提交与合入尚未完成，不能标任务完成。

## 恢复入口与授权

任务：[内建总控退役任务书](总控机制删除任务书.md)，2026-11-19读取期间由原T1–T7修订为A–E工作包，以最新修订为准。真实领号3818（中央归属已记录），分支 `codex/remove-builtin-skill-control`，工作树 `D:\漫剧制作助手\.agents\worktrees\dsh-efdba593-9ce9`。基线 `839ef93a`（R3810）。待建立验收检查点提交，不能标任务完成。最新rebase基线为master `98dafefa`，覆盖率冲突保留主干最新实测仅删退役实体（102实体、2978决策点、1689覆盖），未降低剩余阈值。

用户授权持续执行、意外中断重试、自主作合理选择，全部测试通过后合入 master；不推送。目录治理任务R3812仅是后续移交，不属于本次实施。

## 已实现与范围

1. 已核对并删除Git跟踪的223个专用资源文件，原清单见 `R3818_退役资源清单.txt`。其他13阶段、imagegen、short-drama-storyboard、storyboard-image-prompts、video-storyboard-gen、templates、skills-lock.json及其他gitlink保持。
2. 删除专用脚本桥、包差异脚本、无其他消费者的桥辅助、五项工具注册；未重写替代实现。
3. `sub_engine_names(skills)` 从注册器快照投影用户／项目包，无文件I/O，扁平技能仍为skill；命令和补全engine类别可达。发送使用注册对象，不拼装目录。
4. 通用Agent同步引用解析复用注册器；逐目标重写，防重复链接二次扩张并保留正文／标签。
5. 残留治理取消特定容器分支，保留回收、恢复、用户资产保护。
6. 13阶段说明移除116处外链，保留有效职责；五阶门控、七维台词、语速、12节拍适用范围、情境词典、六列表、S1–S4与F1–F19在原SKILL内自包含，不另建执行器或门禁。
7. 删除专用测试及skip记录，其他测试改中性fixture和新契约；覆盖率、分层、进程边界仅移除已删除对象，剩余阈值不降。
8. 删除专用说明与无消费者的包阶段归属台账，文档登记快照已再生（84份），补规格与ADR-0014（先查最大号0013后分配）；历史报告保留。
9. `.git/config`精确移除孤立 `submodule.程序/skills/00全流程SKILL/AIGC创作全流程` 节，其他submodule键未改。该项非版本化变化。

## 改前失败与闭环

- 基线：`smoke_test.py` 9/9；`run_selftests.py -k skill_command skill_tools agent_skill_sync skill_residue_service` 53条全绿。
- 新行为红测：`run_selftests.py -k skill_command skill_tools` 27条中2文件红。旧命令扫描触发 `AssertionError: must not scan`；新快照入参遭旧Path转换 `TypeError: ... not 'list'`；工具仍暴露五名。工具红测初版引用了不存在的FUNCTIONS属性，已修正为真实公开接口ready_names并复验，不把该属性错误当生产缺陷。
- `smoke_test.py --probe` 不支持此参数，退出1；改用默认入口，入口自身自动执行隐藏桌面probe并通过。
- 相对链接全局replace存在重复替换风险，改为一次正则回调逐目标改写；新增重复目标／锚点／标签／正文不改的行为用例。另补注册器用户包／项目同名优先、坏包不暴露、发送解析使用项目入口的真实临时目录集成用例（正在定向执行）。
- 定向170条中test_skills两项71!=73：本工作树两个已有gitlink未物化。只在本工作树从主树本地克隆，检出固定版本 `6c3d73994f456b696de536c86602b4022824a535`／`357d1348ccaa1ab75f2f51ef7c90a7f00a686c76`，未改索引，174条复验全绿。
- 架构第一次580条：覆盖率手册数字未同步、分支汇总计数未同步、工作树缺被忽略的历史基准资产、继承状态页头3784但最新结果3809。前三项已分别同步与从本机主树复制测试前置资产；后续43条相关门禁全绿。状态页只可在master提交，需合并收尾同步，不修改其历史正文。
- 最终完整架构 `smoke_test.py --architecture` 580/580，283.854秒、退出0，日志 `logs/R3818_architecture_final.log`。为准确验收，本工作树状态轮次头临时按真实最新结果3818设为3819（未提交），验证脚本结束会恢复原始字节；master上的状态更新留到合并轮。期间临时把诊断.py放logs导致生产扫描5红，已移出程序扫描范围并复验全绿，未放宽门禁。
- 第二次架构580条：分支汇总103!=102（已修并43条复验）、历史基准缺失（已补本机忽略资产并复验）、状态轮次仍不连续。命令原始输出在本树忽略日志 `logs/R3818_architecture.log`；不得把当前其余579项情况直接写成完整全绿。
- 安全全量 `run_selftests.py --all --safe` 被活跃 `full-safe-selftest.lock` 拒绝，持有PID76628、R3807；未回收他人有效锁、未强杀进程。下一步用现有等待接口等待释放后执行。

## 测试ID变化登记

专用对象退役而删除（非通用能力削弱）：
- `test_aigc_lint.py`：全部 BridgeContractTests 与 SkillToolsWiringTests；逐方法ID与理由已在 `R3818_测试ID变更.json` 登记（含所有其他改名／替换用例）。
- `test_aigc_package_diff.py`：全部AigcPackageDiffTests（被测脚本已删除）。
- `test_l1_p2_semantics.py`：仅AigcLintTempTests的 `test_feed_path_removes_file_on_error`、`test_write_temp_failure_leaves_no_residue` 两项；其余23条保留并通过。
- 架构外部资源存在/锚点4项随资源退役；阶段职责检查替换为本地定义、断链、媒体/时间线/放行边界共6项。
- 命令磁盘fixture替换注册器快照fixture，新增空候选禁止扫描；分发专包存在检查替换任意打包技能摘要缺失检查；未知模型退回Seedance格式改为按选中模型能力核对。
- 写作已安装测试保留自然剧本、无关包隔离和通用链接绝对化；不再要求退役包存在。REQ-S03/07追溯语义保留。

## 中断恢复与第二次全量（2026-11-19 20:48）

- 首次全量异常退出后状态页原始字节已恢复。修正3处测试定位：三角色章节标题、S05来源链接→本地正典职责、S07不加载旧包→不默认加载外部包；原角色、确认、冲突、段缝断言保持。
- 环境闭环：本树`运行环境`junction指向主树随附运行时，未修改目标；验收子进程PATH仅前置本机Git自带OpenSSL目录；清理本次3份UTF-16中间日志和根目录临时wrapper，未改门禁。补分发清单漏掉的`docs/specs/**`开发文档排除（其既有8文件导致完整覆盖检查红）。
- 236条定向复验只有分发构建一次临时源文件WinError2，随即同检查复验通过；不能将此写为236全绿。日志`logs/R3818_repro2_utf8.txt`保留。
- 自有变化stash后rebase到master `730cbe28`，再恢复stash，无冲突；纳入主干槽位泄漏与慢测试等待修复，未改那些文件。
- 第二次完整诊断job `pwsh-e8f9d8d4b07d4086`：`D:\漫剧制作助手\.git\r3818_validation.py`外置wrapper，使用`run_selftests.py --all --safe --jobs 4 --gui-jobs 1 --allow-dirty-diagnostic`，输出`logs/R3818_full_safe_diagnostic2.log`，GUI子进程详细输出`logs/hidden_selftest.log`。wrapper运行期间临时将本树状态头设为3819，finally按字节恢复；禁止把临时状态页提交。无凭据预写。
- 21:12第二次全量仍执行，GUI约198路未完成。当前wrapper PID12684→13420→gui_hidden3616→实测8352；job `pwsh-e8f9d8d4b07d4086`。工具进程丢job时先查这些PID与日志，不能重复启动活验收。当前仅看到workflow_process_registry 7条6红（独立7/7绿）和ui_edges_autopilot一项红，需最终堆栈。只读子代理slot-isolation正找可复现污染源，不改产品状态。
- 第二次完整诊断已结束：9205条、3269.1秒，5文件有红：workflow_process_registry6、ui_edges_autopilot1、writing_quality4、desktop_startup_perf4、perf_baseline3；实际skip0，退出1，无凭据。完整栈保留`logs/R3818_full_safe_diagnostic2.log`。
- writing_quality启用检测仍按已退役4个文件名（源码`REFERENCES`）匹配，导致四引擎实际冻结指令不启用辅助报告；已改为匹配本阶段4项角色职责声明，不改报告schema或原有测试断言，真实四引擎测试已提交定向复验。
- registry6红栈为_reap_exited_processes读取前序遗留SimpleNamespace.poll缺失。精确形状复现：给_running放入SimpleNamespace(pid=123)，原类7条中6报相同AttributeError；仅给容量测试setUp增加patch.dict(_running,{},clear=True)并addCleanup恢复后，同样污染前置条件7/7且外国fixture被原样恢复。未清其他4全局、未改产品注册器、未改容量/排队/取消断言；具体上游遗留测试未定位，作为测试隔离问题如实记录。其余时序/性能失败带SUSPECT_CONCURRENCY，已用1CPU/1GUI串行定向复验排队。21:52时GUI令牌属他人PID8600，未抢占。
- 活跃新job：`pwsh-4daee7011b8d455e`写作质检回归（等待GUI）；`pwsh-17d4d63e726a466d`时序/性能串行复验（等待GUI）。原全量job已结束、状态页原字节恢复。
- 最终仍需正式提交后的干净内容树全量凭据、合并轮与任务完成文件。

## 21:26 最新恢复点

- `pwsh-e8f9d8d4b07d4086`仍活跃，第二次全量GUI约172路待完成，未提交。当前只见workflow_process_registry 6红、ui_edges_autopilot一红；不要重复启动全量。
- 已单独复验workflow_process_registry 7/7；子代理slot-isolation已跑多组前序组合（workflow_engines_run、UnknownClient、Claude会话、ContextBudget、RegistryRequestCoverage、DesktopModelPool），均无状态残留，尚无污染来源证据，不得据推测清全局。按CPU原序的≤5分钟有界复现跑到第220单元（721 CPU单元总计）291.1秒，尚未到目标且此前无状态残留；末尾spawn从stdin探针失败，未能证明污染源。不能据此改五全局，等真正全量堆栈。
- 三处测试定位修复均已在236条定向中通过；分发独立复验也通过。14组测试ID／定位变化原因已补进`R3818_测试ID变更.json`。生产编排规则未因此改动。
- 原第一次全量wrapper已删，第二次wrapper在git common-dir外置，本树无根临时脚本；运行环境junction保留用于验收。

## 下一步（不得提前标完成）

1. 定向job `pwsh-ad89b18818964222` 已完成：72/72，0跳过（GUI排队约24分钟，实际各测试0.4–3.7秒），文档登记84份通过。继续收取验证job `pwsh-4afe820e583b4fa5`（根目录 `verify_retirement_r3818.py`：完整架构已580全绿，19:11:47开始dirty diagnostic全量，日志 `logs/R3818_full_safe_diagnostic.log`／`logs/hidden_selftest.log`；finally恢复状态页原字节）。不要重复启动这两份任务，先job_output。当前临时状态头3819来自验证wrapper，不得误提交。若进程中断先核对日志与状态页，按原记录恢复，再重跑失败项。
2. 持续核对工作树与master并发状态；master现已前进至 `f7ef4b98`（R3810修状态头），但主树仍有其他会话暂存 `orchestrator/workflow_engines.py`、`tests/test_request_ledger.py`、`tasks_round/evidence/R3308.json`，另有两份用户任务书未跟踪。禁止覆盖、重置、暂存或混入本任务。任务书本树副本与主树SHA256相同 `C533813185D3D754253E6D03FE5635CC647BF68212B9550CF97A217F1930CB17`。
3. 完成完整架构和安全全量，记录真实命令、退出码、数量和凭据；只在验收通过后提交完整变化。
4. 清除本任务根目录临时迁移/审计脚本（删前确认绝对路径），仅保留正式结果和删除清单。
5. 使用dev.py提交、合并入口，按master专属规则同步状态，输出同名任务完成文件、回滚提交与完整测试ID映射；读取goal后才标complete。
