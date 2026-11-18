# R3357：缺语音密钥状态断言的待执行门禁回调隔离
<!-- round-evidence: {"commit_base": "9794ccaf", "credential_hits": 0, "evidence_sha256": "4193182b2a692180", "exit": 0, "failed": 0, "passed": 7, "round": 3357, "tests": "run_selftests.py -k script_composer"} -->

- 类型：§3.2 独立最小修复轮；仅测试 fixture 边界，不变更生产。
- 测试与三个基线：诊断原例通过；12自然样本通过；真实Tk受控交错原断言后置回调3/3红、前置3/3绿；最小修复后同样交错6/6绿。稳定5轮150/150、官方8直接消费者210/210／skip0、默认smoke9/9、静态28/28、架构532/532全绿；最终冻结完整8712条／834.5秒／735文件／996工作单元／0红，既有skip5，无GUI_DEFERRED，NO_RECEIPT诊断口径。
- 欠账：R3350唯一红项以fixture隔离闭环，固定候选本轮完整实测全绿；正式master干净收据、用户本人删除／重装、任务书整体仍未完成，不标TASK_COMPLETE。

## 领号与固定候选

补记前轮提交 `9794ccafb7f59efd7168fead672aaad1b79b86de`（R3350-FAIL）。原 skill-transport-final 干净、MERGE_HEAD 空，dev.py claim 实际 exit1：`拒绝领取轮次：分支 codex/skill-transport-final 领先 master 14 个源码提交（>10，文档/结果提交不计）。先 rebase 到最新主干或回合，再领取轮次。`

lead 已预授权正规新树路径。查重后从固定 `72caf20b22ebce33593e8f5bc0e85264b0f721be` 创建 skill-microphone-final／codex/skill-microphone-final；正常 dev.py claim 领取3357，scope tests/test_script_composer.py 无重叠（另63活跃分支），再 ff-only 精确承接9794ccaf。不改gate／record／历史，不追master，不动旧树。复制两阶段既有gitlink工作资源（不带.git）与ignored基准历史JSON；AIGC普通文件、另3gitlink、pin2保持。

已读AGENTS、runbook领号提交验证规则、R3350／3327与任务书已确认决策；加载diagnosing-bugs、minimal-diff-fix、scoped-tests。解释器随附Python -B，UTF8／tests+程序PYTHONPATH，FFmpeg及Git usr/bin前置PATH；不安装依赖。

## 红绿证据与最小边界

原full R3350在tests/test_script_composer.py:287期望DASHSCOPE_API_KEY、实际还缺必填。恢复官方原测试run_selftests.py -k script_composer --serial exit0；随后12自然原方法全绿，真实桌面返回时pending均已清空，说明此失败依赖回调相对顺序。

git-dir/round-local-evidence/R3357/probe.py用真实Tk、原按钮invoke和完整原方法，只在内存延迟初始gate注册，保留实际_apply_idea_send_state回调。让其点击前到期3/3绿；让其点击后、原win.update内到期3/3原key断言红。StringVar内存事件精确记录：缺key提示先写入，必填提示后写入，同R3350失败文本。无sleep、无timeout放宽。首版复用after_cancel后已删除Tcl命令的探针无效，已明确弃用；有效证据为controlled_valid_detail.log及controlled_red_result.json。

仅缺key方法新增与同文件254–258既有语音错误用例一致的after_cancel pending边界；原DASHSCOPE_API_KEY、MicrophoneRecorder不应开麦、按钮样式与真实按钮调用全部保留。修后完全相同before/after交错6/6绿，见controlled_fixed_detail.log／probe_result.json。发送门禁独立test_idea_send_gate与其消费者随后完整复验。

Tk日志另见既有SharedInput._toggle_voice调用Desktop.safe后None再次调用的TypeError，原输入已有、状态已正常写入；不在本轮改生产或冒认修复。

## 中断恢复

原job pwsh-07b08713ba244013中断后unknown job，日志仅GUI_WAIT210秒，无测试汇总，未计通过。lead与本agent独立核本树相关Python PID为0后，同R3357单份恢复job pwsh-0228c397eb1b4651；官方原例exit0与probe完整采集。其它树GUI holder正常存活未抢锁／杀PID。持久diagnostic_checkpoint.json、recovery.md记录命令、PID、日志、退出结果；不重领号或复制仍在运行任务。

## 后续验证检查点

验证job pwsh-c2b98924d4fc477e完整exit0：5轮各30条（150条）／0红0skip；官方8直接消费者210条／18工作单元／13.5秒／0skip；local_ci exit306.0秒，smoke9／static28／architecture532全绿。稳定覆盖完整script_composer、shared_input_voice、dialog_voice_input、idea_send_gate与idea_request_lifecycle。消费者由官方affected计划6文件加独立gate／lifecycle2文件，无900秒wrapper。

最终full前查公共full／auto锁和PID，14:57发现其它树full-safe-selftest.lock PID53440／R3346，started_at1794984818.6758413，63996／61428为包装链；本轮不抢锁／force／重复运行，等待自然收尾。auto状态旧后台红／cooldown time原样保留。唯一full随后按--all --safe --allow-dirty-diagnostic执行，不写正式收据。

日志和临时脚本均git-dir或ignored logs，不入暂存；状态页本地投影3358已finally恢复HEAD原SHA256 `18e751efa23415c26d57e39f67aa822ebb5793e7230e22e0e5a21e5168031ace`，不功能提交。

## 完整冻结验收及自动恢复

等待job中断后独立核本树／原全量PID为0、两锁空且无full_checkpoint／result，才启动首次实际full。首次job pwsh-96dbbc2446944d08／wrapper65352在无最终汇总时被环境中断：无full_result，日志止于idea_chat组，未出现FAIL／ERROR。1591逐份冻结零漂移；status仍投影23c0d70c…615c说明finally未执行。原日志／freeze／checkpoint／interruption.json完整归档git-dir/R3357/interrupted_attempt1，不计红或绿。确认全链进程0后精确恢复HEAD状态18e751；本次自身残留full锁PID58072／R3357经官方_pid_is_alive确认False，仅由官方acquire_full_safe_lock→release回收，不手删或抢活锁。

随后15:22:21+08:00用Start-Process持久启动相同full.py，PID59476，明确绝对解释器／脚本／工作目录／UTF8 stdout与stderr，detached_full_process.json保存时间命令；独立后续CIM确认其与gui_hidden链存活，不依赖会话长任务。观察等待job只Wait-Process，不拥有full；unknown后以真实PID／退出JSON恢复，未重跑仍活任务。

最终full_result.json已由同wrapper自然写出exit0、外层844.581秒。`logs/R3357_full_safe_diagnostic.log:8–9`证735文件／996工作单元；2672行script_composer实际7条绿；3133行8712条／834.5秒／0红；3145–3150行既有skip恰5（bundled3／隐藏桌面托盘2），无新增skip；3153行ALL TESTS PASSED。GUI_DEFERRED=0，NO_RECEIPT原文2处（6／3151行）。

源码、测试、维护JSON、状态投影、pyw含未跟踪项共1591份，freeze SHA256 `c572c354a0df9b784e81f24529d4b374c97f8db3e08e881d8bc332734bad160a`；前后changed_files=[]，状态恢复后其它冻结文件drift=[]。final_audit.py真实exit0，当前8/8、前轮适配器64/64与模型池233/233消费者全部实际执行，missing=[]。进程59476及本树子链最终0。

公共receipt前后SHA256均 `fe024bde7b97cdd7e72794774fd9e0b0c511ecd0c6c41f3560f315f20555837e`；不修改或恢复公共receipt，不写绿凭据／分层基线／增量台账，不把诊断绿冒称master正式收据。生产代码、line／branch维护JSON不改，也未重复测line／branch。

## 提交边界

仅暂存5行fixture、本结果及官方自动机器证据。正常dev.py commit使用R3357:与--tests script_composer，实际定向测试与新增行凭据扫描后生成证据／stamp；日志／探针／状态页／资源不暂存。不合master、不push、不代用户删除或重装；总体完成文件与正式主干收据由lead统筹。回滚仅revert本轮即可恢复原fixture，生产不受影响。提交hash由Git回执及lead交付补记，避免自引用另起提交。
