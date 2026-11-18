# R3350-FAIL：四文件传输验收修复与唯一完整诊断检查点
<!-- round-evidence: {"commit_base": "d122caf0", "credential_hits": 0, "evidence_sha256": "26de009970b8d408", "exit": 0, "failed": 0, "passed": 65, "round": 3350, "tests": "run_selftests.py -k api_cache_usage model_gateway_robustness shared_adapter_infrastructure latent_defects_r2175 model_pool_redirects l1_transport_requests"} -->

- 类型：§3.2 独立修复轮；仅四测试fixture维护，生产不变，固定输入不追主干。
- 测试与三个基线：四文件原50方法12失败子场景先红，修后六文件65条／三轮195条稳定绿；官方64模块消费者1034条／既有skip1绿；默认smoke9/9、静态28/28、架构532/532全绿。唯一冻结完整8712条／722.9秒／skip5／唯一范围外script_composer红，exit1；不能称完整候选全绿。
- 欠账：四传输原红本轮已闭环；lead裁定独立FAIL检查点，下一独立轮处理语音状态时序候选。正式master干净收据、用户本人删除／重装均未完成，不标任务书整体TASK_COMPLETE。

## 输入、领号与边界

补记上一轮独立检查点 `d122caf0cf2c8a024ba9403cca9a6c3514dc7892`（R3327-FAIL）。旧树skill-modelpool-final起点干净、MERGE_HEAD空，官方dev.py claim实际exit1：`拒绝领取轮次：分支 codex/skill-modelpool-final 领先 master 13 个源码提交（>10，文档/结果提交不计）。先 rebase 到最新主干或回合，再领取轮次。` 未改工具／伪record／追master。lead裁定正规新车道：先核目录及分支未占用，从固定 `72caf20b22ebce33593e8f5bc0e85264b0f721be` 创建本树skill-transport-final、分支codex/skill-transport-final，正常dev.py claim实领3350；scope后 `git merge --ff-only d122caf0cf2c8a024ba9403cca9a6c3514dc7892` 精确承接，前后hash均实测。

scope提示foundation-hardening的test_api_cache_usage与七旧分支latent测试重叠：七旧分支仅历史ProjectFilesPanel迁移，不涉及传输；foundation目标最新6b1bdf1a已有HTTPAdapter.send与Response/HTTPResponse构建，目标文件无未提交改动。本轮借鉴此已存在思路，并按授权补严格DNS/socket guard、局部离线解除及guard内finally close，不整分支合入、不修改他树。其余53活跃分支无重叠。

已读AGENTS／runbook领号提交验证规则、任务书确认决策、R3327／3321／3317／3308，加载diagnosing-bugs、minimal-diff-fix、scoped-tests。解释器主树Python -B，PYTHONUTF8=1／PYTHONIOENCODING=utf-8／PYTHONPATH tests+程序；PATH前置主树FFmpeg与Git usr/bin（既有OpenSSL，不安装）。两阶段gitlink仅复制既有资源副本、不带.git；基准历史JSON为ignored既有资源。AIGC普通文件、原3gitlink及pin2不动。

## 原红恢复点

唯一四文件原红命令：`run_selftests.py -k api_cache_usage model_gateway_robustness shared_adapter_infrastructure latent_defects_r2175 --serial`，job `pwsh-57e981d37e654c5a`已采集exit1，50方法／246.7秒／skip0／四文件1+2+1+8子场景红；UTF8日志`logs/R3350_original.log:30–167`保留完整原栈。等待官方GUI令牌自然放行，未抢锁或启动重复GUI任务。临时脚本只放本树git-dir/round-local-evidence/R3350。

## 四根因、修复与原断言

1. cache usage：旧HTTPSHandler fixture不拦截当前model_pool.http_stream→RequestsJsonOpener实际send，seen为空；迁HTTPAdapter.send、真实Response/HTTPResponse，保持原include_usage／cached_tokens／finish_reason／文本和用量断言，增加实际请求一次和已close核验。
2. gateway lifecycle：同旧fixture及offline提前拒绝，导致流式完成事件断言没到目标分支；同样仅迁发送fixture，保留缺完成事件必须失败、正常完成必须成功及分片原断言。
3. shared adapter：Seedream有意迁到RequestsJsonOpener，已不导出no_redirect；仍检查local_video和tts共享原函数，另外对LocalAPI.call／seedream.request_image／tts.synthesize真实入口分别验301/302/303/307/308拒绝、仅一次发送、原认证和正文存在、响应关闭。不是删除身份断言造绿；保留原no_redirect拒绝逻辑测试。新增未模拟请求硬fail自证一方法，零新增skip。
4. latent：Qwen旧HTTP/HTTPSHandler未拦截实际Requests发送；真实loopback原红的error明确为network suppressed。仅放行127.0.0.1精确测试端口探针，offline1时accepted=false；offline0时accepted=true，urllib3.ReadTimeoutError→内置TimeoutError映射，router分类timeout，线程退出。详`logs/R3350_timeout_probe.json`。fixture改为守护精确endpoint、服务支持既有有限重试、deadline10秒、连接读2秒、finally release／join2秒及线程／监听关闭断言，保留原network／timeout／断线／截断体／程序bug断言。无生产缺陷证据，生产不改。

所有纯模拟fixture开启局部offline=0之前先安装DNS/socket硬fail与实际send mock，退出先恢复环境，finally在guard内close；每文件有未模拟DNS/socket自证。Qwen保留原GET／认证／UA／调用次数与五跳转及消息文本断言。AST对比四文件旧assert调用无删除（身份适用集因有意契约迁移收窄，并加真实行为覆盖），audit结果在本地assertion_audit.json。

初次自测日志`logs/R3350_first_green.log`曾因本轮helper误用不存在seedream.transport五子场景红及额外helper要求坏JSON也仅1次红；读取实际request_image入口及既有坏JSON三次重试后仅修helper，不改原业务断言，不冒作生产红。正式修后job `pwsh-cc1d57da7f314bac`已采集exit0：六文件65条／21.1秒／0红0skip（四文件＋model_pool_redirects／l1_transport_requests，含TLS），`logs/R3350_targeted.log`。最终清理unused imports后隐藏桌面共享令牌内三轮同六文件195/195／50.739秒／0skip稳定绿，stable_result.json及`logs/R3350_stable_detail.log`；生产和覆盖率JSON无改，不重复测量。

## 消费者与CI恢复点

单一串行runner job `pwsh-2bae87b3362645c9`，本地validate.py：三轮稳定后，官方smoke_test._affected_test_plan对api_endpoints／qwen_setup／seedream_api／tts_api／local_video选出的64模块精确消费者清单，已完整exit0；1034条／336.3秒／0红，既有bundled缺失skip1，GUI_DEFERRED=0，`logs/R3350_consumers.log:1323–1340`，外层338.818秒。直接run_selftests无smoke900秒外壳，不遗留超时孤儿。测试文件自身官方affected精确为四文件，已被65条定向覆盖；生产不改仍额外核完整适配器直接消费者。随后官方local_ci.py exit完整exit0／188.018秒：默认8核心+probe=9/9、静态28/28（30.695秒）、架构532/532（156.000秒），失败集合空，数量与前轮相同；`logs/R3350_ci_exit_detail.log:23–36,686–690`。validate runner已完整采集exit0，finally精确恢复状态页SHA18e751…，git diff状态页为空；未遗留本树Python测试进程。测试-only且覆盖率基线原字节不变，不重复测量。

## 唯一冻结完整诊断

冻结前auto status明确后台触发False，full/auto锁为空；相关Python PID为空，前序runner已完全结束且状态恢复。仅本地投影3351并冻结源码／全部tests／维护JSON／架构运行规则／状态，1591文件、freeze SHA256 `a523b44699458fc0c70e30782538460621ea98029198ea5af7e8348752e2a2ca`；唯一`run_selftests.py --all --safe --allow-dirty-diagnostic`已启动job `pwsh-7ef3485a4bd149b1`，日志`logs/R3350_full_safe_diagnostic.log`。本地full_checkpoint.json及freeze_before.json已落盘，receipt前SHA `fe024bde7b97cdd7e72794774fd9e0b0c511ecd0c6c41f3560f315f20555837e`。full.py运行期不改冻结文件，结束比对before/after、保留skip逐项和GUI_DEFERRED统计，finally恢复状态原字节。只记录公共receipt前后SHA，不写／恢复其内容；NO_RECEIPT不当作正式干净收据。

## 完整结果、唯一剩余红与下一轮入口

job `pwsh-7ef3485a4bd149b1`已完整采集exit1：8712条／722.9秒，735测试文件／996工作单元／唯一test_script_composer红（外层730.924秒），`logs/R3350_full_safe_diagnostic.log:3191–3219`。四传输文件在full全部实际绿；所有735文件均有结果行，本轮适配器消费者64/64、前轮模型池消费者233/233实际完成，missing=[]，本地final_audit.json保存逐项比对，不把执行完整冒作整套全绿。

- 实际skip恰5（日志3203–3208）：aigc_lint缺bundled feed/scripts两项、core缺bundled preset一项、隐藏桌面托盘宿主两项，与前轮完全相同，无新增skip；全文GUI_DEFERRED=0。
- 1591份freeze before/after逐文件一致、changed_files=[]；全量后状态finally恢复前完成核验，恢复后其它冻结文件再验无漂移、status_equal_head=true。相对R3327冻结多3是本轮同时纳入.pyw，非新增生产源码。原四测试断言保留、生产与维护JSON均零diff。
- receipt前后SHA均 `fe024bde7b97cdd7e72794774fd9e0b0c511ecd0c6c41f3560f315f20555837e`；NO_RECEIPT原文两处（9／3219行），不写正式绿收据、分层基线或增量台账，未修改／恢复公共receipt。

唯一原栈：`test_script_composer.ScriptComposerTests.test_microphone_without_key_explains_in_status`，原测试287行`assertIn('DASHSCOPE_API_KEY', d.status.get())`，实际`还缺必填：故事梗概、故事题材、故事角色、故事集数、单集时间、交付形态`（日志3212–3217）。该文件与HEAD字节一致，未改／未额外跑UI或full。

仅只读核查出的下一轮候选：SharedInput._toggle_voice（desktop_shared_input880–886）调用VoiceInput.toggle，后者读取speech_api.missing_reason后直接_say缺密钥并return（ui/desktop_voice_input69–82）；IdeaSendGateMixin.refresh_idea_send_state注册250ms回调，_apply_idea_send_state在31–47行重新status.set必填hint。同测试文件254–258在前一个语音错误场景已注明此回调可能覆盖status，并after_cancel pending；缺key场景278–288尚无同样fixture隔离。此为有代码支持的时序候选，不是已做受控probe或已证生产根因。下一轮最小官方复现：`run_selftests.py -k script_composer --serial`（隐藏桌面和共享GUI令牌由官方运行器管理）；随后可受控记录250ms回调与voice状态顺序，保留原缺密钥／不应开麦／按钮样式断言。

lead明确裁定本轮不扩UI，以R3350-FAIL独立检查点收尾，下一独立轮收口语音状态，不重跑full／消费者。功能分支不提交project_status；本树原SHA256 `18e751efa23415c26d57e39f67aa822ebb5793e7230e22e0e5a21e5168031ace` 已精确恢复，git diff为空且未暂存。不合master、不push、不代用户删除或重装。

## 提交与回滚边界

仅暂存四测试、本结果、官方机器证据；日志／临时脚本／状态页／用户数据不暂存，基线不动。FAIL前缀的dev工具不自动attach，显式调用官方round_evidence.write_evidence＋stamp_result，以实际最小暂存新增行scan和六文件真实测试生成证据；不伪造merge-ci-exit或full绿。官方证据job `pwsh-8c11dcb355084a50`已采集exit0：实际六文件65条、0红，credential_scan.hits=[]、judge=[true,true]，tasks_round/evidence/R3350.json及官方stamp头真实生成，证据摘要与commit_base=d122caf0保留。原始定向输出由官方接口capture后只返回统计，不伪称有额外完整详情日志；本轮21.1秒六文件原始日志及三稳定日志另已完整保留。随后正常dev.py commit -m R3350-FAIL门禁提交。提交hash以Git回执及lead下一交付补记，避免自引用额外提交。

回滚仅revert本轮提交恢复旧fixture，不影响生产及模型池事务修复。整体任务书、正式干净收据与用户本人重装尚未完成，不标TASK_COMPLETE。
