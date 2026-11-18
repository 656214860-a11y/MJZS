# R3301：功能分支整合 master 独立验收轮
<!-- round-evidence: {"commit_base": "e56f42fc", "credential_hits": 0, "evidence_sha256": "b3df81dc17805de1", "exit": 0, "failed": 0, "passed": 0, "round": 3301, "tests": "merge-ci-exit"} -->

- 轮次类型：整合验收轮；只整合已提交 master 与现有功能分支冲突，不修 WebSocket。
- 测试与三个基线：官方local_ci exit绿（默认8核心+probe=9/9、静态28/28、架构532/532）；冲突定向268/268、两原并发红各100次共200/200、受影响89文件2185条0红。官方覆盖率81目标1470条全绿且下限不动。完整safe本轮按lead裁定未运行，不能把整合验证绿称为当前树全量绿色。
- 欠账：R3299 完整诊断两红中的文件索引修复由 master 获取；WebSocket 下一独立会话；L2-D22 用户本人真实删除／重装未做，任务书总体未完成。

## 起点与范围

工作树 dsh-6187d0c7-f35d，分支 codex/skill-residue-governance，起点 `e56f42fc06dca9ae93ba26a17257b2aafae0af66`（R3299-FAIL，补记前轮 hash）；开工 git status --short 为空。master=`4020033013d980b10ecef98baed110b45fdad06a`，ahead6/behind10。已读 AGENTS、runbook §12/13/16、任务书原决策、R3276诊断及R3279/R3283/R3287/R3290/R3294/R3299结果；加载 diagnosing-bugs、minimal-diff-fix、scoped-tests、tech-writer。统一 dev.py claim 实领 R3301，无对应队列项不冒领。

领号前无运行中的 run_selftests/smoke/dev/round_evidence PID，共享 common-dir 根无锁文件。scope 报基线与 l1-p2-semantics/wip-R3259/wip-r3282 重叠，语音测试与 pewter-analytical 重叠；只整合已入 master 输入，不修改其它树。lead确认独立整合轮最稳，发生冲突后WebSocket必须下一新会话。

## 冲突与处置检查点

`git merge --no-commit --no-ff master` 实际3处冲突：ui/speech_settings_ui.py、tests/test_model_manager_actions.py、维护记录/分支覆盖率基线.json。非冲突自动合并保留双方提交事实，未整块择一。

语音两边均将长表单改 ScrollForm+固定底部按钮；当前分支更完整，含屏幕尺寸约束、focus滚入、600高全字段Tab/滚轮、取消不保存、下载开始取消完成回归；master仅基础滚动与固定动作。逐hunk保留当前分支完整机制，并恢复master原有窗高不低于请求高断言，按钮ismapped/窗底断言已由原 helper 完整包含。生产ui最终预期与整合前HEAD一致，测试仅新增恢复高度断言，不弱化现有断言。

基线冲突为总点数，自动合并行已混合 master workflow_context_budget/file_index 与分支 request_ledger，不能手填合计或整块取一边。将按合并后 targets 并集使用官方 scripts/branch_coverage_report.py 全目标真实重测覆盖整个JSON；下限表保持原样。

状态页初计划接收master原字节；后核实共享hook在非master分支上无合并豁免，lead明确裁定恢复功能父HEAD原字节、不提交状态页，最终主干保留master正文再更新头。此为明确合并内容选择，详见下文，不称本树恢复master原字节。无push、不合master、不代用户删除重装。

自动合并额外复核：master 的 skill_notes 模拟 `_display_width=len` 与本分支 R3283 真 Tk fixture 叠加，已移除冗余模拟，保留真实字体计量及原两断言，最终该文件与整合前HEAD无diff。desktop_layout自动合并保留master三行请求高度变化处理与R3294完整请求签名/8轮收敛，两者交互由原tables/resize/timers/paint验收。

## 实测验证检查点

- 统一随附Python -B、PYTHONUTF8=1、FFmpeg PATH；临时脚本仅common-dir/round-local-evidence/R3301，日志UTF8，不放生产扫描目录里的.py。
- 官方 `scripts/branch_coverage_report.py` 对合并targets并集81目标整体重测，job `pwsh-f39ec26a9967463a` 已采集exit0：1470条、261.302秒、2既有skip、84模块、1270/2373决策点，工具直接写完整基线JSON。原日志 `logs/R3301_branch_measure.log` 220/222/319/320行。不是手填合计/择一，也不保留先前联合快照为当前测量；历史测量仍在双方父提交。request_ledger114/151=75.5%、file_index74/93=79.6%、workflow_context_budget15/25=60.0%、platform_tools49/119=41.2%；本轮下限表无diff，未下调。2skip为现有aigc_lint缺发行bundle用例。
- 冲突及历史阻断定向 `run_selftests.py -k file_index file_origin_provenance global_library_index global_library_config stage_file_index_publication request_ledger model_manager_actions skill_notes ui_edges_tables window_resize_coalescing timers page_paint_freeze selftests line_endings --serial`，job `pwsh-4da4a20f852e4f72` 已采集exit0：268条、65.9秒、0红0skip。包括文件来源16条、语音12条、原tables15/resize9/timers9/paint9，真Tk经隐藏桌面及跨树GUI令牌执行，未defer。日志 `logs/R3301_targeted.log`。
- 官方受影响消费者 `smoke_test.py --affected desktop_layout speech_settings_ui file_index workflow_context_budget skill_inline workflow_settings writing_api`，job `pwsh-f1e2018adb734d60` 已采集exit0：89文件、2185条、536.4秒、0红，默认+probe+affected门禁合计10/10；实际skip1为test_core发行包缺受测bundled skill既有登记，未新增skip，无GUI_DEFERRED。日志 `logs/R3301_affected.log` 1424–1461行。
- 官方合并候选 `scripts/local_ci.py exit`，job `pwsh-d8e436fd36784971` 已采集exit0：默认冒烟9/9（8核心+probe），静态28/28、31.356秒，架构532/532、256.878秒，失败集合空，与前轮532一致。日志 `logs/R3301_ci_exit.log`，详细官方CI日志已保存 `logs/R3301_ci_exit_detail.log`（原 `logs/ci_最近.log`）。不跑完整safe，本轮不称整体全量绿色。
- 冻结全部tracked现存程序.py共1505份，manifest=`common-dir/round-local-evidence/R3301/source_frozen.json`，规范摘要d595e141eb43b5f7a563189b3916c8772f207affefe81b050f09d36ba77f5954；之后未改源码/测试。
- 状态投影脚本首次因历史文件名非数字正则不匹配而exit1，未写状态文件；改为与门禁一致只收数字结果后成功。当前latest M3301、投影N3302，N=M+1实证true；master原字节SHA256=`19052f580e4c8404f7c5b7ee29bca9a016eaa1669f3d580647587d4e756ed86f`，本地投影SHA256=`61ab37127c3992f324148e7f066934b70379293d0fd2937a051bc0c1a6f9a0be`；收尾按lead后续裁定恢复功能父HEAD原字节（不是master），不提交状态页。原始记录common-dir/round-local-evidence/R3301/status_projection.json。

## 状态页提交硬闸与明确例外

共享已安装 `.git/hooks/pre-commit` 与版本源码 `维护记录/基准脚本/hooks/pre-commit` 第45–47行一致：任何非master分支暂存project_status即拒绝，无MERGE_HEAD豁免。未修改/绕过hook；已向lead报告，他明确裁定本次状态页保留功能父e56f42fc的原版本3278、取消暂存，最终master合入由lead保留当前master正文重写头。不能将功能分支提交状态页伪称合规。

实际 `git diff --numstat HEAD master -- 程序/project_status.md` 原始输出为 `1\t1\t程序/project_status.md`；完整diff仅第3行轮次头由3278/R3277→3297/R3296，正文无差异，没有丢失正文轮次记录。两个头原文均保存在父提交与本地common-dir/round-local-evidence/R3301/status_master_head.diff；本轮结果显式记住master3296/R3293摘要，待最终主干统一更新。N3302=M3301+1是本地实际投影验证，不是提交后状态。

- 稳定性复验：原文件来源并发断言与原4线程共享上限断言各100次，job `pwsh-e6bce1f2580448a6` 已采集exit0；200/200、47.589秒、0失败0错误0skip，日志 `logs/R3301_concurrency_stability.log`，本地JSON concurrency_stability.json。未改断言、未加sleep或重试。

最终状态页恢复功能父字节SHA256=`94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`，`git diff --exit-code HEAD -- 程序/project_status.md` exit0，暂存该路径为空。本地投影前后及双父头差异均记录，正文一致。冻结1505份最终再次核验changed_sources=[]、all_frozen_unchanged=true。

## 提交与下一会话

适用整合验证全绿后以正常 `R3301:` merge提交收尾，双父预期e56f42fc与40200330；使用官方 `scripts/dev.py commit --tests` 入口，不绕hook。工具见MERGE_HEAD会生成 `merge-ci-exit` 机器证据（不自动重复--tests）；这一证据仅声明已执行合并退出CI，不能冒称再跑定向或完整safe。上文实际定向/官方CI/affected/覆盖率/稳定性原始日志独立留存。最终新增行凭据扫描由官方证据工具执行；结果文件提交前冻结，自身hash由lead引用提交或下轮补记，避免自引用加提交。

整合包含master所有功能变化；状态头按明确裁定留功能父，主干仍由lead最终更新。不push、不合功能分支入master、不修改其它树。WebSocket生产和原测试无diff，未在本轮修复；81目标测量内该原模块本次通过不能否定R3299完整safe close KeyError证据。

下一新会话先核干净状态、master版本与scope，再独立领号，运行有界原WebSocket单项复现，保持ping/pong、碎片文本、掩码、close、超时和清理断言；定位证据后最小修复。最小命令（程序cwd、随附Python -B、PYTHONUTF8=1、PYTHONPATH=tests;程序、FFmpeg PATH）：`python -B -m unittest test_platform_tools.WebSocketTests.test_handshake_text_fragments_ping_and_close -v`；模块入口 `run_selftests.py -k platform_tools --serial`。冻结最终源码/测试/基线后唯一完整 `--all --safe --allow-dirty-diagnostic`，无正式收据就如实NO_RECEIPT，最终干净master正式验收由lead负责。

本轮不声明任务书整体完成：WebSocket及最终完整safe、任务完成文件、最终合master待后续；L2-D22真实删除重装仅用户本人操作。


