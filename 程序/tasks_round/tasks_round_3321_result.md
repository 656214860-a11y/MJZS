# R3321-FAIL：固定主干与残留 SKILL 功能历史的独立整合检查点
<!-- round-evidence: {"commit_base": "72caf20b", "credential_hits": 0, "evidence_sha256": "2208ba2ffddcbb71", "exit": 1, "failed": 1, "passed": 133, "round": 3321, "tests": "run_selftests.py -k platform_tools l1_transport_requests desktop_startup_perf force_quit exit_maintenance model_manager_actions ui_motion_perf ui_edges_tables"} -->

- 类型：§3.10 独立整合／验证轮；仅整合已提交的两个固定输入，不追逐后续主干。
- 测试与三个基线：官方行覆盖率111/111绿，分支覆盖率1536条／1红／skip2，官方拒写JSON；默认smoke、架构、affected及full本轮未运行，不能称当前候选全绿。原关闭协议稳定100/100绿；显式官方定向证据见下。不复用R3317的8694条诊断为本候选结果。
- 欠账：本轮发现并受控复现既有模型池跨进程保存覆盖健康度，lead裁定下一独立修复轮闭环，本轮仅失败整合检查点；用户本人删除／重装与最终master正式收据仍未完成。

## 输入、归属与正规接续

原树 dsh-6187d0c7-f35d／codex/skill-residue-governance 干净，补记 R3317 `c34f5c36dadbd43170ef8beddcf16ef7cdb59fdd`。主树原官方 merge_round PID50008→local_ci PID53716 自然退出，MERGE_HEAD 清空、暂存还原，master 未推进；未获得其会话退出码，故不推测原因。主树两未跟踪任务书草稿不触碰。

原功能树 dev.py claim 实测 exit1：领先 master 11 个源码提交超过10门槛；实际实现按 `git rev-list master..branch -- **/*.py **/*.pyw` 计数（含测试及合并），不是生产 no-merges 口径。未改工具或绕门禁。lead 授权从固定 master 新建正规独立集成车道：工作树 `skill-release-integration`、分支 `codex/skill-release-integration`，起点／第一父 `72caf20b22ebce33593e8f5bc0e85264b0f721be`；正常 dev.py claim 实领3321，scope 与另55活跃分支无重叠。无对应队列项不冒领。

`git merge --no-commit --no-ff c34f5c36dadbd43170ef8beddcf16ef7cdb59fdd` 保留全部历史 hash，第二父为既有功能历史；本树合并冲突不表示主树失败。原树与主树均未写入，不合 master、不 push、不代用户删除／重装。

已读两树 AGENTS、runbook §3/4/12/13/16、任务书已确认决策与 R3305/3308/3317，加载 minimal-diff-fix、scoped-tests、tech-writer；以仓库规则与用户指令为准。程序 cwd、主树随附 Python -B、PYTHONUTF8=1／PYTHONIOENCODING=utf-8、FFmpeg PATH、PYTHONPATH tests+程序；UTF8日志，临时脚本只放本树 git-dir/round-local-evidence/R3321。

## 冲突逐项与资源

- project_status.md：双边除第三行轮次头外正文逐字相同，无正文丢失。保留本新树 master 第一父原字节 SHA256 `18e751efa23415c26d57e39f67aa822ebb5793e7230e22e0e5a21e5168031ace`，功能父原 SHA `94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e` 单独保存。不称该新树字节为旧功能父字节；功能分支不暂存状态页，验收临时投影后 finally 恢复新树第一父原字节。最终主干轮次头由 lead 统一同步。
- 分支覆盖率 JSON：双方快照合并冲突，禁止选择较优数字或手填；保存两父原 JSON，官方 targets 并集84组真实重测。行覆盖率虽自动合入但双边9/10组不同，同样官方10组并集重测；floor 原字节不降。
- test_platform_tools 自动合：原服务线程 join(5)+退出断言及协议帧原断言仍在，主干 Retry.total=2／GET HEAD 断言均保留；将实测稳定 close 用例。
- 本候选保留 R3308 实例曾打开 roots、销毁前不可变去重快照、destroy 后既有 exit→storage 显式临时项目参数；无 desktop 启动 schedule，workspace 范围不扩。R3317 语音默认高屏及600短窗／Tab，motion16/64ms running完成和3秒界限／places3原断言保持。
- 新树只复用旧树两阶段 gitlink 包普通内容（不复制 .git／缓存），3个原 gitlink 索引不改；AIGC159普通跟踪文件随merge带入。复用已核基准历史 JSON（忽略、不暂存），SHA256 `5b0451c27a364b79dd430ca10889a407f2382ceec023aad6d7bd68f6b4946c24`。bootstrap.json 保存双父／快照／目标并集信息。

## 官方测量失败与确定性诊断

- 官方测量job `pwsh-c39e8521286345c5` 已采集exit1；均由gui_hidden实际隐藏桌面＋acquire_gui_lock共享令牌包装。`coverage_report.py` 10组并集111/111／42.152秒，75/655模块，官方直接写行JSON。`branch_coverage_report.py` 84组并集完整1536条／246.665秒／1红／skip2（既有bundled缺失），85模块1343/2446只是失败测量观察值，官方明确拒写JSON，不是绿色基线。日志 `logs/R3321_measure_hidden.log:4,82,207–218,416–417`；命令与退出结果在本git-dir/R3321/measure_result.json。
- 唯一分支测量红：`tests.test_l1_lost_update.ModelPoolUpdateTests.test_two_processes_health_and_store_do_not_rollback`，原264行 `shared not found in {}`；原断言／测试／生产都没改。另readerthread在workflow_process_registry错误注入附近打印UTF8解码异常（日志102–114）；只记录事实，不把它误作模型池红因果。
- 串行后续runner `pwsh-81f5b4ce331640f3` 实际在测量绿前置断言即exit1，故未启动targeted/affected/CI/full；不能冒称它们通过。状态finally恢复新树master父SHA18e751…，不暂存。
- 最小探针job `pwsh-dbd2b3f84eef4b1d` 已采集exit0：原单项有界3次均绿，只证明随机调度可绿，不抹掉整表失败。模型池及原测试在72caf20b、c34f5c36与本候选均相同字节。
- 同探针受控双真实子进程：store子进程先raw读`models={}`后等管道；health子进程同临时config路径、HEALTH_KEY=model_health、PYTHONUTF8=1，成功record_health并回读shared（exit0、stderr空）；再放行store发布旧dict，最终shared确定消失。逆序先store后health则shared保留；双子进程均exit0。原始stdout／stderr／最终数据／环境仅本地 `model_pool_probe.json`，真实Tk隐藏桌面日志 `logs/R3321_model_pool_probe_hidden.log`。根因是store对外部raw旧快照直接save，health内部_update持锁不足以阻止后续旧全量dict覆盖；不把测试3绿作为反证，不盲重跑整表碰绿。
- lead明确裁定新独立模型池修复轮，本轮不改model_pool或测试契约。后续须先确定性回归与最小修复，再官方覆盖率目标并集整表重测，清掉本检查点的临时快照状态。
- 本轮close稳定探针首次目标名误写，`pwsh-e6985cf7fe954dd9` exit1只因未找到类方法，未跑测试；纠正为原`WebSocketTests.test_handshake_text_fragments_ping_and_close`后，`pwsh-3e4f915961eb4f78` exit0，100/100／0.492秒／0skip，原join5／线程退出／协议帧断言均在。`stable_close.json`及`logs/R3321_stable_close_hidden.log`保存成功输出。

## 临时基线与提交边界

按lead授权，分支JSON冲突采用固定master72caf20b完整原字节快照作为失败检查点临时基线，不手填／不拼接／不声称实体点数匹配或真测绿；路径`维护记录/分支覆盖率基线.json`，原字节SHA256 `e9098e85b851633c05400738f5e976b5dcefc938795b04abf3e99236ff55ec03`，下一轮必须替换为官方整表绿测。官方行JSON保留真实111条测量；branch floor两父相同，工作树SHA256 `74b34c38ec72cd7720c25d18a7bfb8a0f186aec41c1f2b58155ac3e41fc646ba`，未降。

R3321-FAIL显式调用官方round_evidence.write_evidence＋stamp_result，实际执行`run_selftests.py -k platform_tools l1_transport_requests desktop_startup_perf force_quit exit_maintenance model_manager_actions ui_motion_perf ui_edges_tables`，job `pwsh-d3cbe13262a3443c` 已采集exit1。真实133条／48.7秒／skip0／1文件红；唯一红为transport自签TLS测试在原160行要求openssl，当前PATH无可执行openssl，`unexpectedly None`；不删除／跳过／放宽原断言，不把环境缺失说成实现绿。日志`logs/R3321_official_targeted_detail.log:156–177`。其它startup15、speech12、motion27、table15、force18、platform与exit本次绿；不等同完整消费者绿。不再重复该组。机器证据扫描0命中、tests exit1 failed1，证据不伪造merge-ci-exit绿。

默认smoke／全架构／完整候选full本轮未运行，无正式full receipt；原本计划的冻结完整diagnostic未启动。所有日志／临时脚本／探针数据留git-dir或ignored logs，不暂存；状态恢复新树第一父原字节。正常dev.py commit -m R3321-FAIL收尾，若hook硬拒则保留现场交lead，不绕hook。

提交前223项暂存仅既有功能历史整合＋官方行测JSON＋本轮结果／证据，无未解决冲突、未跟踪或未暂存变更；状态页未暂存。`git diff --cached --check`提示AIGC既有5处尾空白／EOF及历史R3301结果EOF（共7行告警），这些文件与功能父c34f5c36无diff，属于原历史内容，本轮不为格式改动重写资源；不称该检查绿。原模型池与测试无diff；pins官方检查2项0问题。后续master已观察前进ee0be581，只记录，整合输入保持72caf20b不追。

本轮不标TASK_COMPLETE。下一独立会话从本失败检查点修模型池，先核Git已有openssl真实PATH，再重测临时branch基线、重点消费者、官方CI与固定代码完整候选诊断；正式干净收据及master合入、任务完成文件由lead统筹。提交hash由本轮Git回执及交lead汇总补记，避免自引用额外提交。
