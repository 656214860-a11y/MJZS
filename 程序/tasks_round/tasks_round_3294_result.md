# R3294：同页重建滚动偏移历史阻断修复
<!-- round-evidence: {"commit_base": "57406202", "credential_hits": 0, "evidence_sha256": "62c220eda552d457", "exit": 0, "failed": 0, "passed": 58, "round": 3294, "tests": "run_selftests.py -k ui_edges_tables window_resize_coalescing timers page_paint_freeze line_endings"} -->

- 轮次类型：§3.2 修复轮（含全量基线验证）；只修唯一滚动阻断。
- 测试与三个基线：原断言先红后绿；定向42/42、最终定向24/24、affected215/215均0skip；默认8核心＋probe＝日志9/9；最终架构532/532、254.925秒。冻结完整全量8576条、709.5秒、skip5，唯一范围外request_ledger并发PermissionError，exit1，明确NO_RECEIPT，不称全量通过。
- 欠账：本轮唯一滚动阻断已修复；新暴露账本阻断交lead另轮裁定，不扩改。任务书轮4真实删除／用户本人重装、整体任务完成文件与master合入由lead统筹。

## 起点与授权

直接授权本子会话实际领号、最小修复、测试、独立正常提交；不合master，不代用户重装。工作树dsh-6187d0c7-f35d、分支codex/skill-residue-governance，开工HEAD=`57406202416dd11df15ccfc8fb7288099f23f4df`（R3290-FAIL），status干净。前轮R3287=`ee67ca06`、R3283=`d90358b7`、R3279=`9b620f1c`。

已读AGENTS、runbook相关节、残留SKILL治理任务书决策、R3283/R3287/R3290结果；加载diagnosing-bugs、minimal-diff-fix、scoped-tests（项目专有运行器与用户要求全量优先）。统一入口dev.py claim领R3294，初始scope与另53条活跃分支无重叠；根因路径定位后补scope。

R3290前子会话补验117/117、exit0、扫描0、四目标前后SHA256不变，全部job结束；其机器补验仅在common-dir `round-local-evidence/R3290/postcommit_verification.json`，不是R3290已入库证据。R3290-FAIL前缀不匹配提交工具`^R(\d+):`，未自动附入库证据／重跑--tests，本轮不修范围外工具。

## 先红与测量检查点

- 随附Python -B、PYTHONUTF8=1、FFmpeg PATH，`run_selftests.py -k ui_edges_tables --serial`自动隐藏桌面：15条、13.6秒、1红、0skip。原断言tests/test_ui_edges_tables.py:538未改，210.0与246.0差36。UTF8原始logs/R3294_red_tables.log。
- 外置最小probe只运行原失败1条，统一scripts/gui_hidden.py真实隐藏桌面＋common-dir共享GUI令牌，1.628秒红，logs/R3294_scroll_measure_red.log。时序显示首建region951/viewport705，重建前offset246、req已902；重建region收敛915/viewport705，restore_scroll收到246而Tk夹至210。并非恢复参数丢失，仍需控件换行／布局测量定位根因。
- probe首遍公共锁路径误用工作树.git文件，FileNotFoundError，未运行Tk断言；修正指向common-dir后才获得上述真实测量，不冒称首遍有效。
- 2026-11-18检查点：第二probe job `pwsh-58c106edd5ca43ed`排队共享GUI令牌，持有PID44592是其它树skill-budget-verify-c351ca11完整全量（lead确认），未抢锁／未重复启动。命令同最小probe，输出logs/R3294_scroll_widgets_red.log；外置脚本common-dir/round-local-evidence/R3294/scroll_probe.py，计划量首建/重建控件请求尺寸及wraplength。恢复时先收集该job，不重复执行。
- widget probe首个180秒等待已超时退出（未执行测试，不计行为红）；采集后唯一1800秒续接job `pwsh-1fd6248c515f426f`已结束exit1，实际执行原失败断言。logs/R3294_scroll_widgets_red.log证据：同一1130画布宽，首建status Label wrap1102／req高23，重建wrap640／req高42；首建content实际req902但region951，重建915。根因模块ui/desktop_layout.py：全局_last_fit_width跳过同宽新标签，三元组收敛忽略后代请求尚在传播，自身Configure又被抑制。
- 最小生产修改仅该模块：逐标签比较目标wrap而非仅画布宽变化；使用已有完整请求签名，保留8轮有界after_idle及销毁防护，去掉不再使用的_last_fit_width两行状态。绿probe job `pwsh-da455930c0504b90`已采集exit0：原断言不改，首建／重建region910、viewport705，offset205→205，换页0；logs/R3294_scroll_measure_green.log。
- 新增真实Tk回归tests/test_window_resize_coalescing.py同宽新标签及嵌套请求传播；外置harness仅在内存加载HEAD原模块、不写源码回退，2条中同宽标签先红200!=772（logs/R3294_new_tests_red.log）。嵌套传播回归在原实现已绿，只作为边界保护，不冒称先红。
- 两点必要性隔离：保留当前wrap修改、仅在内存替换为HEAD原_apply_layout，原滚动断言仍红205!=246差41，1条1.535秒（logs/R3294_wrap_only_diagnostic.log），证明收敛签名必须同修。
- 定向job `pwsh-558e6f62e42d44c1`已采集exit0：ui_edges_tables/window_resize_coalescing/timers/page_paint_freeze 42/42、32.4秒、0skip，logs/R3294_targeted.log；原tables15条全绿。
- 最终affected job `pwsh-1f0b9b495d18411b`已采集exit0：smoke_test.py --affected desktop_layout覆盖全部9个消费者模块，215/215、110.7秒、0skip，默认8核心＋隐藏桌面probe＋affected门禁为日志10/10，logs/R3294_affected.log。
- 首次冻结生产SHA256 c7c09da2a24fd49c1d621b3c21b0bc95463f6bc63f7c5cfb3e0a914dfc53e5ff（随后仅改注释，最终生产SHA256见下）；resize测试87078b4b98cd23ad628222a168cc5679bb6b8d6b8afef2e8d7c402af8d768462；未改原tables测试4777376852f1333e92dc93fbb26edd0a34d5189f6aa8cd1869a6e4993a852f83。完整记录common-dir/round-local-evidence/R3294/frozen_hashes.json。状态页仅本地投影3295，提交前还原HEAD原字节3278。
- 首遍全架构job `pwsh-deaaafb827de4553`已采集exit1：532条249.809秒，唯一红test_todo_comment_snapshot，因新增注释“总高暂时相同”关键词“暂时”被收为TODO快照新增项；原始logs/R3294_architecture.log。不改快照／豁免，仅改注释为“总高相同也”，逻辑不变，重新冻结生产SHA256=`01f11b9c2393531fd119bf823c92396e4117f82d441cee8cf98bd8f04c7c60a2`。
- 最终注释版本定向job `pwsh-81682f2e9b724dd6`已采集exit0：原tables15＋resize9，24/24、18.5秒、0skip，logs/R3294_targeted_final.log。全架构复验job `pwsh-ea965354d62d420c`已采集exit0：532/532、254.925秒，与前轮532不变，失败集合空；logs/R3294_architecture_final.log。独立默认冒烟日志9/9（8核心＋probe）exit0，logs/R3294_smoke.log；行尾16/16＋长度2/2合18/18、1.7秒，logs/R3294_static_targeted.log。
- 冻结完整全量唯一job `pwsh-59f71aee046e4cf3`已采集exit1，06:47:50开始、06:59:50结束，full-safe锁PID51648已释放，`run_selftests.py --all --safe --allow-dirty-diagnostic`，logs/R3294_full_safe_diagnostic.log。共8576条／709.5秒，skip5、无GUI_DEFERRED、仅1红；原tables15条34.6秒与resize9条13.9秒均绿。源码／测试3份SHA256前后完全一致，common-dir/round-local-evidence/R3294/full_frozen_verification.json的frozen_unchanged=true。明确NO_RECEIPT，不写正式绿凭据／分层／增量台账；最新master整合树正式验收由lead负责。
- 唯一失败`test_request_ledger.ModelMoneyBudgetTests.test_concurrent_requests_share_one_ceiling`：tests/test_request_ledger.py:552 sum(pool.map(reserve,range(4))) → :547 authorize_model → infra/request_ledger.py:416 authorize_units → :606 transaction → :78 stream.flush()，PermissionError: [Errno 13] Permission denied。原始全量日志3098汇总、3119–3155完整栈。只读查阅不作根因结论，不修改request_ledger；lead已裁定下一独立轮处理。
- 5个实际skip逐项对照既有维护记录/skip台账.json与tests/skip_reasons.py：test_aigc_lint两项及test_core一项缺发行bundled skill；test_desktop_tray类setUpClass及最小化循环两项缺隐藏桌面任务栏宿主（既有R1850登记包含整类条件）。与R3290相同，未新增skip。
- 外置全量脚本在启动前核验SHA256、无全量锁与PID，结束再次比哈希。首启动检查job `pwsh-2e6063299f134dbd`因pwsh未在Python PATH而exit1，未执行全量／无锁；已采集并改系统PowerShell绝对路径，不算测试执行。
- 状态页已从git show HEAD原字节恢复3278，SHA256=`94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`，git diff --exit-code -- project_status.md为0，不暂存。原tests/test_ui_edges_tables.py无diff，原delta=2保留。

## 提交检查点

lead已基于完整失败集合裁定本轮以`R3294-FAIL: 修复同页重建滚动偏移历史阻断`独立检查点提交；本轮修复行为绿，完整全量红，不标任务书完成。最小暂存仅ui/desktop_layout.py、tests/test_window_resize_coalescing.py、本轮结果与官方生成tasks_round/evidence/R3294.json；日志／状态页／用户数据／外置probe不入库。`git diff --check`通过。

提交工具FAIL前缀不匹配`^R(\d+):`，不会自动attach或运行--tests；已先读官方round_evidence.py CLI／契约，将显式调用官方入口实际扫描暂存新增行、运行`-k ui_edges_tables window_resize_coalescing timers page_paint_freeze line_endings`生成目标绿机器证据，再用dev.py commit正常统一入口收FAIL检查点，不修改工具／不伪造全量绿色。官方入口job `pwsh-cb9d180c27734adf`已采集exit0，生成tasks_round/evidence/R3294.json（commit_base57406202）：credential_scan.ran=true、hits=[]；目标58/58、failed0、exit0，generated_at2026-11-18T07:08:43。UTF8日志logs/R3294_official_evidence.log；其中目标合并原tables15＋resize9＋timers9＋paint9＋line_endings16，不是全量凭据。已等待共享GUI令牌后执行，没有deferred。本文件随后用官方stamp_result写机器头，再对最终暂存新增行实际复扫；只记录扫描结果，不记录任何敏感取值。

结果文件提交前冻结，自身提交hash由lead引用本文件所在提交或下一轮补记，避免为了自引用额外提交。本轮不标整体TASK_COMPLETE，剩余账本红由lead另轮接手。
