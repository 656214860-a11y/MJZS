# R3360-FAIL：固定主干候选整合与性能验收检查点
<!-- round-evidence: {"commit_base": "9e3d1924", "credential_hits": 0, "evidence_sha256": "4f973feacfaf95e5", "exit": 1, "failed": 1, "passed": 81, "round": 3360, "tests": "run_selftests.py -k storage desktop_startup_perf exit_maintenance secret_status_diagnostics l1_lost_update"} -->

- 类型：§3.2 修复轮／固定候选整合；从已审计 master `9e3d1924b0595544242566809f594d962ec48154` 创建独立 `codex/skill-master-final` 工作树。
- 测试与三个基线：官方行11组131条、分支88组1702条真实测量绿；默认9／静态28／架构532及关键定向102＋354＋诊断消费者220、稳定70均绿。两次完整诊断分别8904条唯一诊断fixture红（已闭环）与8905条唯一资产页CPU比值性能红（未闭环），不称完整全绿。
- 欠账：固定主干整合与诊断测试隔离已完成，最终性能／完整全绿／正式master收据仍pending；lead裁定本轮真实FAIL双父检查点，不再扩资产业务／改性能阈值／启动full3。用户本人删除／重装仍manual pending。

## 固定输入与隔离边界

- 独立工作树：`D:\漫剧制作助手\.agents\worktrees\skill-master-final`；正常 `scripts/dev.py claim` 领号 R3360，`dev.py scope` 已核对计划路径。
- 创建时父提交固定为 `9e3d1924b0595544242566809f594d962ec48154`；不追随后续 master ref 推进。
- 待合入输入：R3357 最终正式提交（等待 lead 提供）；当前只读候选 `9794ccafb7f59efd7168fead672aaad1b79b86de` 不提前合入。
- 原树／主树源码、状态、index 均不修改；不 push、不合入 master。主树只读发现 MERGE_HEAD=`051fb324998960dc32f8b16aa183ef9edada7ad6`，已告知 lead，不作处置。
- 本车道 master 原始状态页 SHA256：`20b1af1c0336184c5f8d53e052307edc1a8ccf27c2740cc85569a167e7df061a`；原字节备份于本树 git-dir `round-local-evidence/R3360/project_status.master-original.bin`。整合提交保持父版本原字节且不暂存状态页；必要测试投影在 finally 恢复。

## 冲突与语义验收设计

1. 旧式只读 merge-tree 以共同基点 `72caf20b`、功能候选 `9794ccaf`、固定 master `9e3d1924` 审计；原始输出保存在 git-dir `round-local-evidence/R3360/merge-tree-audit.txt`。实际冲突待最终 R3357 输入重新确认，不重读全部变更文件。
2. Desktop 保留本实例 opened roots 去重、退出前 tuple 快照、destroy 后 exit maintenance、无窗子进程显式 temporary-project；移除打开项目 after(3000) 清扫调度，同时保留 startup_settings、自检、READY/CLOSED 预算及 DEGRADED 播报。
3. 启动性能测试保持 zero-walk 断言，将旧打开后回调契约改为打开零扫描且退出实际清扫；保留 <=50ms 自检要求与其余启动契约。
4. 先对退出子进程多 root 汇总诊断写受控失败回归，再最小接线 stats/remaining 总和后一次 record_temporary_sweep；诊断失败不阻断清理或其它维护，不导入 Tk。
5. 自动合并仍核验 model_pool 锁内 snapshot delta、config_patch 登记与 floor100、L1 UTF8／ledger／Windows 锁、两方 schema/selfcheck，以及 Requests／WebSocket／短窗语音／motion／layout／file_index 的既有精确修复。
6. 覆盖率使用官方工具真实测量，失败拒写 JSON；行目标取双方并集（预期 11 组），分支目标保留 master 完整集合（预期 88 组），以实际最终登记为准；旧 floor 逐项不降。Tk 测量显式隐藏桌面并获取官方 GUI 锁。
7. 受控红绿、相关消费者、CI 与两基线完成后冻结源码、测试和维护 JSON；安全全量 `--all --safe --allow-dirty-diagnostic` 一次，记录全部失败、skip、GUI_DEFERRED 与输入哈希；不把 NO_RECEIPT 当正式收据。

## 实际整合与错误恢复

- 最终固定候选为 `bf0afed06944c2cd1af9485f164c411115f8c55b`，已 `git merge --no-commit --no-ff`；五真实冲突正是 desktop、architecture、runbook、行／分支基线。保留所有历史，不追随后续 master 推进。
- **本轮实质错误与恢复**：首次冲突解析使用 MULTILINE＋DOTALL 正则，其中标记行 `.*` 跨行贪婪匹配，把 desktop／architecture／runbook 的冲突后尾部截掉。发现后停止仅本方持久 PID62472 及其后代；当时 Tk 仍排队，旧链全部结果不作为最终验收，不把其非GUI绿色复用。旧日志归档 `target-invalidated-hidden.log`，未处理其他树活锁。
- 从固定三个输入 `9e3d1924`／共同基点 `72caf20b`／`bf0afed0` 重新逐文件 git merge-file，再显式逐行按冲突边界处理；不再用宽泛正则。恢复后 desktop964行／architecture307行／runbook277行；相对父 numstat 分别 +2/-8、+5/-3、+3/-3（runbook数字后续按真测更新）。完整 restored.diff 与 restore-audit.json 保存于本轮 git-dir；逐项检查 desktop startup_settings／DEGRADED、architecture L0 selfcheck／media_signature／schema 与 L1 config_patch／L2 residue、runbook §12/13/16 和全部尾部均保留。239个变更文件无残留冲突标记，53个变更py AST全通过。
- 首次静态34例中 storage_maintenance1007>1000；未抬cap，已把多root清扫汇总移入既有 L1 temporary_sweep 的同职责 `sweep_opened_projects`，storage仅调用，原单root API／TTL／名称／link规则不变。恢复后静态、层级、共享状态、文档预算43/43，47.086秒，exit0。
- 受控汇总回归：初版夹具遗漏program父目录，已修正并单独留首日志；正式修前两例均因 record 实际0次而失败（非伪造红），日志 storage-red-corrected.log。修后验证成功root去重汇总4/6只写一次、缺失root不扫描、异常root不捏造计数、诊断写失败仍继续library维护。
- 唯一有效首组 target2 持久 PID67276 正常结束：官方定向102条／27.9秒／0红／0skip，含真实启动性能17条，zero-walk／1秒／50ms预算不降；旧调度测试实际验证打开不扫描、无start_stale回调、destroy后清扫真实过期文件并记录1/0。状态finally恢复20b1原字节。日志 target2-hidden.log／target2_result.json。
- 两覆盖目标按双方JSON实际并集：line=11、branch=88。官方工具经 gui_hidden 和 acquire_gui_lock 单链真实测量自然结束，line exit0／131条／52.203秒（外层55.275秒），659生产模块／91有覆盖／568未触及；branch exit0／1702条／290.035秒（外层292.254秒），既有skip2，92实体／1488覆盖决策点／2676总。两个工具原生失败拒写JSON逻辑未改，未拼接数字。config_patch实测4/4=100%、floor100；双方旧floor逐项不降、全部实测不低于floor，final-floor-audit.json的failures=[]。runbook同步真实数字。
- 必要定向消费者 focused：354条／74.2秒／0红／0skip，覆盖模型池快照、lost_update、L1/L0汇总、传输六文件、输入框语音、layout／motion／file_index、D1/D2与包索引；完整日志 focused-hidden.log。广义直接消费者158模块另有冻结清单，由最终full逐项核对实际结果行，不无谓重复上千GUI测试。
- 首次CI出口 exit1／202.281秒：默认9绿／静态28绿／架构532中唯一完成文件闭环红，缺23条任务书原文项；原日志 ci-first-red.log。未改validator／门禁，补齐24原文项及各自实际证据或manual pending，局部门禁8/8绿；复验完整CI2 exit0／299.907秒：默认9／静态28／架构532全绿，失败集合空，架构数量与双方532不变；原始ci-final-green.log。状态finally恢复20b1。完成文件末次两句事实澄清后局部closure8/8再绿，不改源测试基线。
- 完成文件已落 `任务完成/残留SKILL治理·任务完成.md`：九总项＋24原文逐条对应；L2-D22本人删除／重装／共享输入框真实调用均manual pending；没有假勾人工通过。AIGC ee67ca06与bf0afed逐路径mode/blob集合相同，159项；当前本树对ee67ca06包diff为空。历史manifest3,660,831B、Git blobs3,620,518B与两树检出3,620,578B分列，未推断未核验字节差全部来自行尾。requirements父到候选差异为空，最终full后再核。
- 最终full freeze将包含源码／测试／pyw、维护JSON及全部Markdown（含完成文件）；仅本轮结果文件排除，允许full后写实际输出与官方stamp，明确不冒充冻结内容。

## 首次完整冻结验收及精准闭环

- 2026-11-18T17:06:55.8408144+08:00 持久Start-Process启动full PID58324；官方事前full/GUI锁均空、auto=False，未抢活锁。固定暂存候选tree=`84bc52693cf9853384decdb71f3e21826b29b506`，双父9e3d1924＋bf0afed0。首次完整安全诊断8904条／1058.7秒／743文件／1011工作单元，exit1，唯一红文件 test_secret_status_diagnostics，原full日志与JSON已完整归档git-dir/R3360/attempt1，不覆盖。
- 4496个源码／测试／维护JSON／Markdown／pyw／状态冻结项全部零漂移，freeze SHA256=`c989baadf057c868e18fdee22a05ae5a3bcae918eb9f13c2ee664c356d21768b`；本轮结果文件明确排除。状态finally恢复20b1，158消费者逐项实际执行，missing=[]；首轮audit正则漏architecture前缀已依据1461行实际结果纠正，仅审计脚本变更。GUI_DEFERRED=0、NO_RECEIPT=2、receipt前后均fe024bde7b97cdd7e72794774fd9e0b0c511ecd0c6c41f3560f315f20555837e，未写／恢复共享收据。
- 实际skip5逐项对当前固定master323条登记（功能父322，合并保留master323）：bundled缺项3、隐藏桌面托盘宿主2，全部各匹配登记1项；TrayIconTests整类条件由R1850托盘台账说明覆盖。无新增skip，不只套用旧5数字。
- 唯一失败原栈 full.log3389–3407：DiagnosticCapturePreviewTests.test_export_never_leaves_the_whitelist:159，精确ZIP名单原期望只启动错误.log，实际另含合法diagnostics/latest.json。生产diagnostic_capture与该测试对固定master9e3d字节相同，不是退出清扫root或写线程污染。受控trace证明export→flush_artifact_states→读取artifact_schema内存计数→_save_state只写artifact_versions→白名单包含STATE_FILE；临时PROGRAM/LOGS/STATE_FILE已隔离。清空计数原例pass，显式note_read_state后同原断言稳定红（diagnostic-probe-red.json）。
- 最小测试-only修复：原例显式read_state_counts={}输入，原精确名单／用户正文不得入包断言保留；新增非空计数导出严格3项ZIP／manifest included／artifact_versions字段回归。生产、两覆盖率与floor完全不变。受控空非空修后均绿，整文件14绿，5轮带计数种子稳定70/70、0skip。
- 诊断消费者首次配置误传tests.test_*全名导致0匹配／0用例exit0，此结果无效，原log/result/config完整备份invalid-zero-diag，不记通过。恢复消息交错曾出现lead接手PID64132与本方PID67256，两进程核验时均已自然结束，未杀他树；此后明确本方唯一owner。修正叶名关键词diag2实际13文件／220条／17.6秒／0红／0skip，状态finally20b1，完整diag2-hidden.log；不是仅计划清单。
- 最终CI3持久PID46632运行中，结束后重新冻结完整候选验收；不重领号、不追随后续master、不扩生产模块。

## 第二次完整验收与有界性能归因（进行中）

- CI3 exit0／250.674秒，默认9／静态28／架构532全绿，状态finally20b1；仅诊断测试输入隔离和非空严格名单回归进入候选tree=`4363706937a91808d048d62b12d6ccbc019850d5`。
- 官方核验full/GUI={}、auto=False后，2026-11-18T18:01:43.9859642+08:00 Start-Process持久启动第二次最终full PID66792，18:15:22自然写结果；8905条／807.9秒／743文件／1011单元／exit1。诊断文件14条全绿，唯一新红为PerfBaseline.test_the_asset_page_opens_under_the_limit:287。CPU最快343.8ms／参考31.2ms＝11.0，原门槛10.0；墙上最快342.8／中位388.2ms低于1200仅旁证，不能替代CPU判据；三组(墙,CPU)为(894.7,968.8)、(342.8,343.8)、(388.2,375.0)。完整原栈full.log3482–3495，原证据归档attempt2。
- 4496冻结项零漂移，SHA256=`09a94f33a199af1c1b7a31206dd3c3964aa83b40c4220883bbcce06ea43c7caa`；状态20b1恢复、158消费者missing=[]、skip5逐项匹配323台账、GUI_DEFERRED0／NO_RECEIPT2／receipt前后不变。未将失败称完整绿。
- 有界父候选对照：固定9e3d仅git archive到git-dir隔离快照，双方均同300资产fixture／原7项／原3采样／原阈值，各仅2组，隐藏桌面+官方GUI锁同环境。父第1组7绿资产ratio9.0，第2组资产ratio10.6667红（CPU500／reference46.875）；候选第1组7绿资产ratio6.0（375／62.5），第2组资产ratio8.0（375／46.875）绿但冷首帧1549.5>1500红。各组所有数据保存perf-bounded-summary.json／各probe JSON与log，未跨组选最优或丢红。
- 页面采样before/after仅MainThread，pending9/10含_after_first_paint／ready／layout／more_rows／tick／动画，未观察到后台清扫／自检线程；不支持先前“其它线程CPU污染”假设。machine_speed无缓存，页面采样后独立纯Python3次取最快；process_time覆盖进程，阈值／资产页源码／perf用例与固定父无差异，desktop布局存在既有完整签名修复。父同样能红只能证明非候选独有，不能豁免full失败；未找到允许直接将性能红豁免为通过的规则。
- 经lead授权，仅候选一次3采样cProfile自然结束19:01:40，明确插桩绝对耗时不是正式判据。3样本耗时1.070／0.324／0.306秒：首样本ui_theme.ready→place→update_idletasks0.659秒、cell_hover mapped/refresh0.588秒；暖样本Tk update0.188／0.171秒约56–58%，show0.136／0.134秒，资产计划同步0.071／0.070秒约22–23%，392次Path.resolve约0.039秒。完整布局签名未进前50热点，未据猜测回退正确性修复。原始perf-profile.txt/result与4组probe均保存。
- 进一步只读asset_plan发现每注册image逐个resolve＋is_relative_to＋is_file是防链接越界的真实校验，多数不同文件路径；未找到有证据且值得在本整合扩张的安全最小优化。未运行新resolve_audit草稿、未新加资产业务模块、未降低10倍／1500ms门槛、未改正式样本数或挑选政策、未再跑full3。

## FAIL检查点提交与接续

- lead明确裁定本轮以真实 `R3360-FAIL` 独立双父检查点收尾；此提交是可恢复集成交付，不代表任务书整体／最终性能验收完成。后续由lead新独立性能验收轮接续，固定父双方历史全部可达，本轮不合master、不push。
- 本轮官方证据已显式调用 round_evidence.write_evidence，实际暂存scan0；收尾叶关键词storage／desktop_startup_perf／exit_maintenance／secret_status_diagnostics／l1_lost_update真实执行81条／23.3秒／0skip，唯一启动自检成本75.9062ms>原50ms预算红（test_desktop_startup_perf:624），其余80绿。此项先前首组／两次full中通过，现以本次实测红保留，不裁成环境已证、不改阈值或缩目标求绿；checkpoint-first-red-evidence.json与原栈完整留存。官方证据原样exit1／failed1，lead裁定按FAIL检查点stamp后实际尝试dev.py commit一次，若hook硬拒保持现场由lead接手；不伪写judge绿／merge-ci-exit／CI等于完整绿。只暂存固定合并文件／两覆盖维护JSON／测试修复／本结果／完成文件／官方机器证据；日志、运行数据、资源副本、用户配置、状态页不暂存。
- 状态页保持本车道父原字节SHA20b1af1c0336184c5f8d53e052307edc1a8ccf27c2740cc85569a167e7df061a。共享状态正文没有整块取功能侧：本车道提交按功能hook保留固定master父正文，双方差异与记录集合原始输出存project-status-parent-diff.txt／status-record-handoff.json交lead正式主干合并时逐段保留；两父R行集合各7且candidate-only=[]。不把本分支未提交状态页头写成主干已同步。
- 提交hash以Git真实回执与lead接续为准，避免为自引用额外另起提交；当前尚未提交。性能／完整验收／正式收据／人工重装pending，不标TASK_COMPLETE。
- 任务书技术项继续依逐条证据核对；用户本人删除／重装仍为 manual pending，整体不声明 TASK_COMPLETE。
