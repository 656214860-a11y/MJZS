# R3299：台账并发空文件锁初始化 PermissionError 修复
<!-- round-evidence: {"commit_base": "368371a5", "credential_hits": 0, "evidence_sha256": "d3220f695631beea", "exit": 0, "failed": 0, "passed": 175, "round": 3299, "tests": "run_selftests.py -k request_ledger l1_reliability_r3248 money_invariants model_metering pet_llm request_recording line_endings branch_coverage_floor"} -->

- 轮次类型：§3.2 修复轮，仅根因模块及必要回归测试。
- 测试与三个基线：原四线程预算断言100次实红3次，受控真实Windows锁2项先红；修后303/303稳定验证、直接/门面消费者963/963、最终4项真实空锁回归全绿0skip；默认8核心+probe日志9/9；最终全架构532/532、265.508秒。唯一冻结完整safe diagnostic8580条/620.1秒/skip5/2个范围外红，exit1，1504份冻结全不变；显式NO_RECEIPT，未冒称全量通过或正式绿凭据。
- 欠账：R3294完整全量唯一台账阻断已修且稳定绿；本轮完整全量另有2个范围外红（文件索引项master已有修复、WebSocket关闭帧另轮处理），不扩展本轮。用户本人真实删除/重装、任务书总体交付及master整合由lead负责。

## 起点、授权与范围

当前工作树dsh-6187d0c7-f35d、分支codex/skill-residue-governance；起点HEAD=`368371a51fd9d0f27365a7bfe7a58d0c22fe4d0d`（R3294-FAIL），开工status干净。前轮R3290=`57406202`、R3287=`ee67ca06`、R3283=`d90358b7`、R3279=`9b620f1c`。R3294修复本身绿，完整全量8576条/709.5秒/skip5/唯一台账PermissionError，NO_RECEIPT；本轮补记其正式提交368371a5。

已读AGENTS、runbook相关§3/4/12/13/15、任务书决策及R3294/R3290结果；加载diagnosing-bugs、minimal-diff-fix、scoped-tests，采用项目运行器与用户要求完整全量。`dev.py claim`实领R3299，scope根因模块/测试与另53活跃分支无重叠，无对应队列任务。master40200330对两个目标与当前树无diff；未同步master，冻结期不改基线。不合master、不代用户重装。

## 复现与根因检查点

1. 原`ModelMoneyBudgetTests.test_concurrent_requests_share_one_ceiling`原封不动重复100次，6.762秒，3次errors、exit1，均`_ledger_file_transaction`锁前`stream.flush()` PermissionError Errno13。UTF8日志`logs/R3299_original_repeat_red.log`，job pwsh-5fc736767aad4563已采集，原始摘要为`Ran 100 tests in 6.762s / FAILED (errors=3)`；栈`tests/test_request_ledger.py:552 sum(pool.map(...)) → :547 authorize_model → infra/request_ledger.py:416 authorize_units → :606 transaction → :78 stream.flush() / PermissionError: [Errno 13] Permission denied`。
2. 外置最小真实Windows探针common-dir/round-local-evidence/R3299/empty_lock_probe.py：空文件句柄持有首字节范围锁时文件仍0B，另一独立句柄LK_NBLCK冲突为PermissionError；锁前write/flush同样PermissionError。释放后flush成功。`logs/R3299_empty_lock_probe.log` exit0。证明Windows支持beyond EOF锁，无需初始化字节。
3. 新增真实子进程锁夹具，只有拿到空文件锁才发布ready，父进程再进入事务；有界5秒ready、10秒子进程上限、finally终止并wait释放。受控测试超时/取消两项稳定在初始化flush失败，未进入原有轮询，异常释放边界原实现已绿，不冒称第三项先红。`logs/R3299_controlled_red.log`，3条、0.105秒、2errors，job pwsh-d80a3626ed0c425c已采集。原始摘要`Ran 3 tests in 0.105s / FAILED (errors=2)`，两项首个异常均`:78 stream.flush() / PermissionError: [Errno 13] Permission denied`，with退出重flush又报错；原始red/stability日志额外复制到common-dir证据目录。初版误导不存在私有helper而ImportError（job pwsh-dd20bae5ae0549fe），已修正，首遍不是行为红证据。
4. 已确认的失败路径：锁前不必要的初始化write/flush可绕过锁竞争轮询直接PermissionError。stat大小判断无tell问题，不能靠概率或通用重试规避。额外内存加载HEAD原函数（未改生产）分别在stat=0后、Python缓冲write后等待owner写1并锁的两个受控探针并未复现；append可能已移EOF，不能声称简单stat TOCTOU充分，真实四线程CRT内部竞争窗口未精确观测。正反证均保留common-dir/round-local-evidence/R3299/controlled_toctou.py及UTF8 logs/R3299_controlled_toctou.log；最终记录先缓冲写0B→owner写1并锁→contender flush未立即失败→owner释放→事务进入，exit0。首个探针以预期失败断言结束exit1，属假说否证而非产品新红。最小生产修改仅删除锁前stat/write/flush；保留seek0、原有锁外有界轮询、checkpoint、_REQUEST_LOCK读改写与finally释放。现存非空锁文件兼容。平台Windows11 Enterprise LTSC 10.0.26100 64位，随附Python3.14.7 MSC v.1944 AMD64。

## 验证与恢复检查点

- 修后稳定验证job `pwsh-48d0400b41b84c4c`已采集exit0：新3项+原预算300次，303/303、21.068秒，`logs/R3299_stability_green.log`。不再无理由追加压力。
- affected job `pwsh-c55517ae5ae147f2`已采集exit0：`smoke_test.py --affected request_ledger`，40/40、12.7秒、0skip，默认8核心+probe+affected门禁日志10/10，`logs/R3299_affected.log`。该工具只识别裸模块名，实际未自动纳入infra及pet_llm门面消费者，故另按AST补全。
- 新增第4项行为回归验证：子进程持空锁期间事务确实进入checkpoint轮询、另一账本可完成事务（等待不占全局锁）、释放后等待事务成功；保持原4线程预算断言无diff。最终新4项0.276秒全绿，`logs/R3299_controlled_green.log`；行尾16/16、0.7秒，`logs/R3299_static.log`，job pwsh-fdc485c708fd425b已采集exit0。此第4项未单独先红，不冒称先红。
- AST按request_ledger/pet_llm/model_metering包路径及门面收集28个测试关键词，实际选中29个文件/79工作单元，消费者job `pwsh-9487e3ed7de24887`已采集exit0：963/963、44.9秒、0skip，含R3248跨进程授权/结算、超时、checkpoint、异常释放、结算降级契约。`logs/R3299_consumers.log`。已有Tk销毁after stderr但无测试红，不篡改断言。
- 独立默认smoke已exit0，8核心+probe日志9/9，`logs/R3299_smoke.log`。首遍全架构job `pwsh-a56a029ed9f24b2a`已采集exit1：532条266.892秒唯一`test_baseline_decision_points_match_current_entities`因删除初始化if导致request_ledger基线152!=151，其余531绿。`logs/R3299_architecture.log`。
- 基线同步补scope与另53活跃分支无重叠。官方`scripts/branch_coverage_report.py`仅测六目标tests.test_request_ledger/tests.test_l1_reliability_r3248/tests.test_money_invariants/tests.test_model_metering/tests.test_pet_llm/tests.test_request_recording；首遍未设PYTHONPATH，原子进程导入测试空stdout失败，工具拒写JSON（logs/R3299_branch_measurement.log，154条5.463秒，非可信测量），已补项目规定PYTHONPATH重跑成功。最终`logs/R3299_branch_measurement_final.log` exit0，common-dir/round-local-evidence/R3299/branch_measurement.json tests_ok=true；request_ledger官方实测115/151=76.2%，原115/152=75.7%。仅同步其module行points/percent及总points2367→2366，其余模块行与覆盖率下限原样，未冒称其它模块重测/整份全量覆盖率。job pwsh-8a1b5e8303614116已采集。
- 首次最终架构复验job `pwsh-00cc93168b7b452f`已采集exit4294967295，日志停在test_text_measure_boundary，无Ran/FAILED汇总；核验其PID已不存在、无全量PID，Application事件查询未返回崩溃项，1504冻结无漂移。原因未知，不推定外部清理，不算测试红或通过。`logs/R3299_architecture_final.log`保留。lead确认未清理并授权安全单份重跑。实际后台run_in_background=true无超时包装唯一job `pwsh-5905a68a94734345`，直接UTF8日志`logs/R3299_architecture_verified.log`及common-dir/round-local-evidence/R3299/architecture_exit.json，该job已采集exit0：完整532/532、265.508秒，失败集合空，与前轮532一致。退出JSON已落盘。
- 状态页本地仅轮次投影3300供N=M+1；提交前从HEAD原字节还原3278，不提交。全部1502份Python源码/测试及基线JSON、状态页共1504份已冻到common-dir/round-local-evidence/R3299/frozen_hashes.json。2026-11-18 07:34前核验共享full-safe/auto-full锁及全量PID均不存在、git diff --check通过；启动脚本再次检查hash/锁/PID。唯一完整`run_selftests.py --all --safe --allow-dirty-diagnostic`实际后台job `pwsh-19d1451b8036472a`已采集exit1，UTF8 `logs/R3299_full_safe_diagnostic.log`，common-dir/round-local-evidence/R3299/full_frozen_verification.json核验1504份全部不变(frozen_unchanged=true)。实际07:33:57启动、07:44:28结束，全量锁PID31124已释放；8580条620.1秒、skip5、2个文件各1红、无GUI_DEFERRED，NO_RECEIPT非正式凭据。台账41条/R3248可靠性27条/原tables15条32.0秒/resize9条14.7秒/语音12条11.2秒均绿。运行期未改源码/测试/基线。生产SHA256=`7b95763b3270d29b7d49e793931edbb0136bcb74c33910ab160e3a0ca78a5c4d`；测试=`05225f0f9953be8e79e58e42343756407f3020e8652f108c854e32adfd21138f`。临时脚本仅放common-dir/round-local-evidence/R3299，不写生产logs下py。


## 完整全量范围外失败与后续入口

原始UTF8日志3056行完整汇总、3068–3073实际skip清单、3075–3120完整两项原栈。5项实际skip逐项与tests/skip_reasons.py及维护记录/skip台账.json核对：aigc_lint两项+core一项缺发行bundled skill，desktop_tray setUpClass及最小化循环两项缺隐藏桌面任务栏宿主（既有R1850整类条件），无新增skip、无GUI_DEFERRED。

1. `test_file_origin_provenance.FileOriginProvenanceTests.test_concurrent_records_do_not_lose_entries`：`:51 list(pool.map(...)) → infra/file_index.py:178 record_origin → :76 _index_lock → :116 _relative`，`ValueError: 索引只收项目内文件：<隔离临时项目>/project/工作流任务/文件索引/index.json`。原日志3077–3110。不把合法路径拒绝误称台账预算回归。
2. `test_platform_tools.WebSocketTests.test_handshake_text_fragments_ping_and_close`：`tests/test_platform_tools.py:403 self.assertEqual(frames['close'][0], 0x8)`，`KeyError: 'close'`。原日志3115–3120。

后续最小模块命令（本轮不再执行、不改断言）：程序cwd、随附Python -B、PYTHONUTF8=1、PYTHONPATH=tests;程序，分别`run_selftests.py -k file_origin_provenance --serial`与`run_selftests.py -k platform_tools --serial`；两者不涉及Tk。必要时用`python -B -m unittest test_file_origin_provenance.FileOriginProvenanceTests.test_concurrent_records_do_not_lose_entries -v`或`test_platform_tools.WebSocketTests.test_handshake_text_fragments_ping_and_close -v`锁单项。

结束只读对master40200330精确核对：`git diff HEAD..master --stat -- 程序/infra/file_index.py 程序/tests/test_file_origin_provenance.py 程序/contract/platform_tools.py 程序/tests/test_platform_tools.py`只有前两文件（file_index +24/-2、测试+93）；master已有_index_lock锁前resolve移入线程锁、_relative针对Windows \\?\ atomic replace的严格父路径/非reparse修复和真实受控回归。lead独立核对相同，文件索引不在本轮重造。platform_tools生产/测试与master无diff；WebSocket待新整合轮独立复现。冻结中未同步master；下轮先整合最新master后验收，避免旧树历史阻断连锁。

## 失败检查点提交

lead已明确同意本轮以`R3299-FAIL: 修复台账空锁初始化并发异常`独立收尾，不再全量、不扩修两个范围外模块。只提交根因infra/request_ledger.py、新真实行为测试tests/test_request_ledger.py、官方实测分支覆盖率基线三行同步、本轮结果及官方生成tasks_round/evidence/R3299.json。原4线程预算断言未修改；无通用吞错、无限重试、预算放宽、新依赖或生产模块。

状态页已从起点HEAD原字节恢复3278，SHA256=`94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`，git diff --exit-code通过，不暂存。日志、临时探针、用户配置/数据与状态页不入库，git diff --check通过。

FAIL前缀不匹配提交工具ROUND_MESSAGE_RE，不能假设--tests自动attach。已先用官方`round_evidence.py 3299 -k request_ledger l1_reliability_r3248 money_invariants model_metering pet_llm request_recording line_endings branch_coverage_floor`实际生成tasks_round/evidence/R3299.json，commit_base368371a5，175/175、failed0、exit0，credential_scan.ran=true且hits=[]，generated_at2026-11-18T07:47:11；job pwsh-cb340f4fd9c64875已采集exit0，UTF8日志logs/R3299_official_evidence.log。随后用官方stamp_result写机器头，并复扫最终暂存新增行0命中，再统一dev.py commit收FAIL检查点。机器目标绿证据不替代完整全量，明确NO_RECEIPT、不称任务书整体完成；结果文件提交前冻结，自身hash由lead引用所在提交或下一轮补记，避免自引用额外提交。
