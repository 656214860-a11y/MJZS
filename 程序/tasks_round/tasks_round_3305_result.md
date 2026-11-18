# R3305：整合 L1 基础设施主干批次的独立验收轮
<!-- round-evidence: {"commit_base": "78f58597", "credential_hits": 0, "evidence_sha256": "8d5f309272513547", "exit": 0, "failed": 0, "passed": 181, "round": 3305, "tests": "run_selftests.py -k request_ledger l1_bounded_growth_r3269 l1_lost_update l1_p2_semantics l1_reliability_r3248 round_claim branch_coverage_floor coverage_baseline layers"} -->

- 轮次类型：独立整合／§3.10 验证轮；只整合已提交 master，逐段处理冲突，不混入两个 UI 红项修复。
- 测试与三个基线：官方覆盖率目标并集行111/111、分支1531条绿（既有skip2），冲突定向181/181与覆盖率下限门禁绿；affected外层900秒超时，内层3119条／910.8秒／1个新startup扫描红／既有skip5，非通过。官方local_ci exit已绿（默认9/9、静态28/28、架构532/532）。完整 safe 本轮未运行，不能声称当前树全量绿。
- 欠账：R3302 完整冻结诊断的两个 UI 红项及本轮实测 temporary_sweep 启动扫描红留下一独立新会话；不混修、不弱化断言。用户本人删除／重装尚未执行，任务书整体未完成。

## 起点与授权

工作树 dsh-6187d0c7-f35d、分支 codex/skill-residue-governance；开工 git status --short 为空。补记 R3302-FAIL hash `78f585974e65999d4192fc084e2023c82c443ab3`，即本轮功能父；master 固定输入 `71393d999ee7a5fb46d01c855e7d9f6e8c23bc95`，新增15提交（L1轮2–4及对应修复／整合）。已读 AGENTS、runbook §12/13/16、R3302/3301/3290、任务书已确认决策，加载 scoped-tests 与 tech-writer。统一 dev.py claim 实领 R3305，scope 与另53活跃分支无重叠，无匹配队列项不冒领。

lead 明确本会话严格独立整合；发生冲突后不修 UI、不在已知红项上盲跑完整全量。只操作本树，不合入 master、不 push、不碰其它树活跃 PID／锁，不代用户真实删除重装。

## 合并与双边事实

`git merge --no-commit --no-ff master` 出现5冲突：architecture.md、runbook.md、project_status.md、维护记录/分支覆盖率基线.json、维护记录/覆盖率基线.json。

- 架构相邻两行逐行核验：L1 保留 master 的 temporary_sweep，L2 保留功能父的 skill_residue_service。没有整块择一。
- runbook 覆盖率口径根据官方重测实际字段同步，双方旧测量完整保留于双父提交与本地证据目录。
- 两个覆盖率 JSON 不手填合计；目标取双方并集，以官方工具直接重建。行10组（10∪9），分支84组（81∪84）。分支下限采用自动合并后 master 上调值，绝不降低。
- request_ledger 自动合并复核：master 每日备份、损坏指引和懒索引全部保留；功能父 R3299 去掉锁前初始化写入的修复保留。并发、备份、R3248 直接回归已覆盖通过。
- ui/speech_settings_ui.py、tests/test_model_manager_actions.py、ui/ui_motion.py、tests/test_ui_motion_perf.py、tests/test_platform_tools.py 相对功能父无diff；保留既有全部滚动／焦点／屏幕／下载行为及 WebSocket 修复。

## 状态页提交边界

双父状态页仅第3行轮次头 1+/1-，正文逐字一致：功能父3278/R3277，master3304/R3303（L1轮2–4已合入）。原始 diff、双父原字节存于 git-dir/round-local-evidence/R3305；功能父 SHA256 `94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`，master SHA256 `e0696bf9f9c53ab6729316e260c82bfdd3884c28494f143979674088a0b620b4`。

按共享 hook 与 lead 裁定，功能分支提交不含 project_status.md；测试时临时投影最新结果+1，收尾恢复功能父原字节并 unstage。不能称恢复 master 字节。最终 master 由 lead 保留其正文并更新轮次头。

## 实测检查点

随附 Python -B、PYTHONUTF8=1、PYTHONIOENCODING=utf-8、FFmpeg PATH 前置、程序 cwd；临时脚本仅 git-dir/round-local-evidence/R3305，不进入生产扫描路径。日志 UTF8。

- 官方测量 job `pwsh-27f3c24bdcbb4a55` 已采集exit0。行覆盖率10组111/111、28.908秒（外层30.791秒），真实655模块／75覆盖，日志 logs/R3305_line_measure.log:3–5、81–82。分支覆盖率84组1531条、175.511秒（外层177.038秒）、2项既有aigc_lint缺bundled skip、85模块1331/2428决策点，日志 logs/R3305_branch_measure.log:123–125、323–324。两个JSON均由官方工具直接写入。
- 分支下限表与master父完全相同，未降低；定向门禁实测通过。相对master测量仅三模块变化：request_ledger因R3299移除初始化条件，157/121点变156/120；file_index本次74/93（master75/93）；platform_tools本次49/119（master48/119）。如实保留本次测量，不手调覆盖数；各项均满足既有下限。
- 冲突／交互定向 `run_selftests.py -k request_ledger l1_bounded_growth_r3269 l1_lost_update l1_p2_semantics l1_reliability_r3248 round_claim branch_coverage_floor coverage_baseline layers --serial` 已exit0，181条／49.0秒／0skip，覆盖每日备份、懒索引、锁争用零写、四线程共享预算、跨进程互斥、R3248及L1三批直接回归。日志 logs/R3305_targeted.log:40、52。
- 唯一串行验收job `pwsh-b147f5ee2b1046bf` 已采集exit1。官方affected覆盖22个生产模块、168测试文件（前述口头23为误计，以实际命令22为准）；外层smoke900秒上限命中，外层901.793秒退出，默认8核心+probe=9项绿、affected项超时红，不得称affected绿。日志 logs/R3305_affected.log:24–34。未重复启动affected或full。
- 隐藏桌面子运行留下完整自然汇总：3119条／910.8秒／1文件1红／5项既有skip，无GUI_DEFERRED；日志已在任何后续测试前独立复制为 logs/R3305_affected_hidden.log:2209–2235。唯一红 test_desktop_startup_perf.DesktopStartupPerfTests.test_startup_path_does_not_recurse_directories，tests/test_desktop_startup_perf.py:345 `len(recursive_walk)==0` 实为1；原栈 temporary_sweep.py后台thread work:51→sweep_stale_temporary_files:31→os.walk，被测试count_walk:331捕获。此模块由master本批新增；本轮未改该模块／启动断言，不称既有两UI红或仅超时无实红。5skip为aigc_lint2+core1 bundled缺失、desktop_tray2隐藏桌面无Explorer宿主，与R3302一致。
- 已核本树相关PID全退出后启动新阶段官方 `scripts/local_ci.py exit`，job `pwsh-5ce5fdd403b14f8d` 已采集exit0：默认8核心+probe=9/9，静态28/28／27.385秒，架构532/532／198.392秒，失败集合空且数量与上轮532相同。日志 logs/R3305_ci_exit_detail.log:23–36、686–691。前runner因affected失败未进入CI，本次为独立补跑。lead明确裁定R3305-FAIL独立整合检查点，不扩修temporary_sweep或两UI。
- 源码冻结于 git-dir/round-local-evidence/R3305/source_frozen.json，1509份tracked现存.py、SHA256 `b4073be16f334108b683ed23073fb286d72feb5511a87077d4c1b5c9ae6247a9`；CI结束后与7项候选文档／基线／状态投影逐项核对，全无漂移。投影N3306=M3305+1，随后恢复功能父状态页SHA256 `94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`，git diff HEAD状态页为空且未暂存。
- 所有要求保留的hash（9b620f1c、d90358b7、ee67ca06、57406202、368371a5、e56f42fc、f34f4491、78f58597）均为HEAD祖先。pins官方检查2项0问题；git diff --check与暂存--check全绿；无未解决冲突。

## 失败检查点提交与下一独立会话

采用 `R3305-FAIL:` 双父merge检查点，保留全部既有hash；不合master、不push。`commit_round.attach_evidence` 对FAIL前缀不匹配而不自动生成证据（既有工具局限），故显式调用官方 round_evidence.py 对上述真实181定向目标再跑并扫描最终暂存新增行，然后官方stamp_result写机器头，通过dev.py commit-FAIL收尾。首次显式官方入口（不带--serial）实跑181条但exit1、1红、扫描0；CLI吞掉捕获输出，无原栈，原JSON已保存在本地证据official_first_failed.json。已向lead报告，获准仅一次同181官方复测并旁路保存完整stdout以定位，不改工具、不反复测到绿；唯一复测job `pwsh-f5229905f01e4086` 已采集exit0，官方同181目标22.4秒、0红0skip、凭据扫描0，完整输出 logs/R3305_official_targeted_detail.log:23、35。首次job `pwsh-88299073acb5469a` exit1和原JSON保留；--serial首测与默认池官方测量存在执行差异，但首个默认池红项未留堆栈，不能臆定根因、不能宣称稳定全绿。不再复测。最终机器证据是该次真实定向通过，不抹除历史失败。证据类型为真实定向命令，不冒称merge-ci-exit全验收或full-safe绿；实际CI绿与affected红分别如上。原始日志、临时探针、状态页、用户数据不入暂存。

下一新会话最小入口（程序cwd、同环境、隐藏桌面运行器）：`run_selftests.py -k desktop_startup_perf l1_bounded_growth_r3269 --serial`。先核temporary_sweep调度在desktop.py:702、后台线程与窗口首次可交互时序，保持启动零递归断言，不能改成忽略后台线程来造绿。另两项既有红按R3302原证据独立诊断：model_manager_actions语音表单1154==viewport1154，以及ui_motion_perf顶部yview0.001；不得改places/delta／加sleep掩盖。最终完整safe、任务完成文件与合master由lead安排；用户本人删除／重装仍待用户实际执行，不标TASK_COMPLETE。
