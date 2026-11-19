# R3400：固定主干接收残留SKILL治理候选
<!-- round-evidence: {"commit_base": "00ff7962", "credential_hits": 0, "evidence_sha256": "4d6ce6b62f29af1e", "exit": 0, "failed": 0, "passed": 0, "round": 3400, "tests": "merge-ci-exit"} -->

- 类型：§3.2 固定输入整合修复轮；本轮唯一接收树从主干固定 00ff7962f303dd089055d81e5df5c1c239c09155 接收固定候选 abacc9263d5bb23fdeae2f1c4c6217f2eaa887d6，不追随后续 ref。
- 测试与三个基线：静态预检58绿，最终传输143绿、UI115绿，官方行12组146条／分支90组1757条测量绿，出口CI默认9／静态28／架构532绿；最终第二次冻结完整诊断9018条／1091.7秒／0红，消费者158无漏、skip5逐项台账、冻结4649项零漂移、GUI_DEFERRED0。NO_RECEIPT，不冒正式收据。
- 欠账：本固定接收树技术验收全绿，正式最新主干末差异及干净收据由lead接收；用户本人回收／重装／共享输入框调用仍 manual pending，任务书整体不标 TASK_COMPLETE。

## 正规认领与固定接收路径

主树 master 固定 00ff7962，tracked clean、MERGE_HEAD 空；四份无关未跟踪任务书草稿不动。主树正式 round_claim.py next 实测 exit2：把四草稿判脏拒绝领号；next --help 只有 --branch，无 --allow-master。未绕 dirty／owner、不私调内部函数、不伪 record、不隐藏草稿。

lead 明确裁定唯一固定接收树 D:\漫剧制作助手\.agents\worktrees\skill-master-receive／codex/skill-master-receive，路径与分支先核不存在，从固定 00ff7962 建树；正常 scripts/dev.py claim 领取 R3400，scope 无重叠。随后 git merge --no-ff --no-commit abacc926，11 文件冲突现场保留。官方主树 merge_round.py 只检查 tracked 改动，CI 后既有入口自领号；草稿路径与候选树无碰撞。验证过程中只读发现主树已由他人正规推进至 3a97b184cedc1fffeea2ac148e9507e4341fe429（R3403，L0 K2，较固定主干16文件差异）。lead 裁定本接收树保持固定输入，完成提交后交lead处理最新主干末差异；本轮不自行追 ref、不再直接主树 merge。

## 冲突与双边语义

11 文件：architecture.md、desktop.py、runbook.md、tests/architecture/test_service_return_contract.py、tests/test_api_cache_usage.py、tests/test_latent_defects_r2175.py、tests/test_model_gateway_robustness.py、tests/test_model_pool_redirects.py、tests/test_secret_status_diagnostics.py、维护记录/分支覆盖率基线.json、维护记录/覆盖率基线.json。

每文件保留 stage2／stage3 与原冲突字节，使用逐行冲突块解析，无 DOTALL 贪婪正则。56 个改动 Python AST 通过、冲突 marker0；双方尾部与函数名审计中仅预期启动延迟清扫 helper、两个 send fixture 名及内置禁用契约旧测试名变化。内置禁用契约由 R3279 明确改为可禁用／可启用／原文件保留，删除启用和禁用两态仍拦截。

保留 master 安全启动／自检／READY／CLOSED／DEGRADED 预算与 TTS request_bytes（64MiB／120s）；保留候选 opened roots 登记、销毁前 tuple 快照、销毁后独立退出维护显式 --temporary-project、外部根／forced／重复 close、原 TTL／命名／link／workspace 边界。多 root 清扫统计一次诊断，不因诊断失败阻断其他维护。

架构、_layers、统一基数、ServiceResult 采用方保留 residue＋voice_ai 及双方实体与 pending；L1 config_patch 与 master unit_of_work／business_log／idempotency，L2 domain_events 均保留。全部共同旧 branch floor 不降，新增 config_patch100／business_log0／idempotency0／unit_of_work32。两份测量 JSON 不拼接测量值，最终已由官方真实重测目标并集：line12／branch90。

## 真实失败与最终版本复验

第一定向组自然结束 exit1，17 文件／27 单元，原完整输出留存。6 个红 subcase 分属两个文件：cache 读取 seen[0].body 时 urllib.Request 无 body；latent Qwen redirect 的301／302／303／307／308读取 request.url 时同对象无 url。该组中 cache fixture 在该文件已执行后、其余 GUI 排队期间修改，故明确作为混合版本诊断，不称最终版全绿。后续在该组结束后修改 latent fixture。

修复仅将两处 fixture seen.append(包装urllib.Request) 改为 seen.append(真实PreparedRequest)，不改任何业务 assert、生产返回结构或 HTTP 功能。HTTPAdapter.send 全模拟、真实 Response／HTTPResponse、DNS／socket 硬失败、guard 内 finally Response.close、局部网络与 NO_PROXY=* 均保留；loopback 精确端口真实 socket 例外与有界 join 不变。最终版相关 Requests／传输组实际99条、UI组115条通过，均非0匹配。补充组142条／33.2秒唯一红为 test_shared_adapter_infrastructure 原身份断言仍要求已迁移的 tts_api.no_redirect。真实 master TTS 已统一 request_bytes；经 lead 确认，仅将测试的 urllib 身份列表保留 local_video 并新增 TTS request_bytes 身份，下面301／302／303／307／308 × 三适配器真实传输拒跳行为、auth／body／次数1／close 与硬guard断言全留，补局部 NO_PROXY=*。生产零改；最终 shared／TTS／Requests 小组后自动串接两官方基线，所有失败原栈保留。

补齐三份精确注册 pin 的只读嵌套资源（manifest 相等），及已冻结历史基准 JSON；不改资源正文、不暂存资源副本、不碰用户配置。AIGC 对 ee67ca06 零 diff；requirements 无新增。原状态页 SHA256 ddf06ad16c702c4c0683815bf3f9f37aba14f914ffb5e3bbc87388169053d077，在测试状态投影 finally 恢复；不提交功能树状态页。

## 持久证据与接续

本地证据位于共享 Git common-dir 的 round-local-evidence/R3400；不在程序/logs 放临时脚本。包含原冲突三输入、预检、语义审计、定向原日志、PID 与退出 JSON；长任务 Start-Process 持久运行，不依赖当前工具等待。接收提交SHA以实际Git回执及交付审计为准，不为自引用另起提交。

## 官方真实覆盖率与最终传输

最终 shared／TTS／Requests 143条／10.4秒／0红、0skip；真实request_bytes透传spy实际断言120秒／64MiB，五status×三适配器15拒跳行为及原auth/body/count1/close/硬guard保留。此前no_redirect旧身份红及错误模块属性identity红均独立原栈保留，不以最终绿抹除。

官方行覆盖12组146条全绿，生产模块663／覆盖93／未触达570；分支90组全部绿，L0/L1实体95，决策点覆盖1534/2750。两JSON均官方工具真实重测写入，未拼测量数据、未改floor；执行方式为隐藏桌面＋正规跨树GUI锁。具体时间／命令见本轮本地measurement-result.json。

官方local_ci.py exit实际退出0，完整原日志ci.log；默认／静态／架构计数以日志实值为准。接下来唯一完整安全诊断冻结全部source/tests/md/维护JSON/状态投影与历史资源，NO_RECEIPT；冻结期间不修改，结束后再补事实。

## 第一次完整诊断真实失败与契约同步

唯一full1实际9016条／985.5秒／750文件／1019单元／2文件2红，4649冻结项零漂移、原状态恢复、NO_RECEIPT2／公共receipt不变。完整只读审计158消费者missing=[]、原性能7／计量4／启动17实际执行，skip5逐项323台账、无未登记、GUI_DEFERRED0。首轮完整原log／freeze／audit归档full-attempt1，失败不被后续绿覆盖。

两测试与固定master00ff原字节相同：源码guard仍数旧engine调用字符串2，但REQ/DES-S10-22已将Studio.auto_edit_ready与L3edit_ready_for_project共用edit_ready_rows→adopted_edit_version；只改test_ui_edges_guards，AST验证assemble→adopted、auto_edit_ready→内核、内核→adopted、L3核验→内核，四处逐一替换绕路坏样本都被检测，旧approved_versions重复逻辑禁止断言保留。

队列链StageQueue.get_nowait→pet.drain→_complete_if_verified→emit_verified_completion→completion_evidence受REQ-S13-20／22／54与DES-S13-54约束。原test_pet_ui只有成功文字而无项目产物，合法暂停；仅原队列接缝_tick_once期间局部注入completion_evidence(True,空详情)并assert_called_once真实root／delivery／video_ready，真实事件出口不mock，原completed与状态文本断言保留。新增真实临时空项目不mock核验，成功文字必须paused且不得completed。生产代码零改。

原两红及相关核验定向实际[14, 76]条通过，再次精确guard／队列接缝稳定通过；随后复核官方CI，再运行经lead授权的第二次完整冻结诊断。requirements对固定00ff零diff；相39ed仅master dev-requirements注释变化，不是新增依赖。

CI2首次静态门禁真实红：新增真实空项目Tk回归含PLATFORM_TKINTER skip但漏登台账，323≠324。只按邻例新增该测试唯一台账项，旧323项不改；官方skip_hygiene3条通过。324是登记数，本次实际skip另以完整log为准。此前新增测试一次误查状态栏而非本次paused事件text，14条1红原栈保留；最终事件切片版14＋76＋精确5条均通过，不反复追加到绿。

最终官方CI2已实际exit0（以ci2-final-result.json子退出及ci2-final.log为准，不采用wrapper退出码），重新冻结最终源／测试／元数据／md／维护JSON／状态投影。接下来授权full2只运行一次，运行期间零改，结束后再记真实结果。

## 原始失败保留与最终第二次完整诊断

分支测量第一次1757条／299.493秒／skip2唯一desktop行尾红：冲突写入归一LF违反原CRLF契约，官方拒写基线。仅恢复desktop原CRLF，规范化LF后内容逐字等价、964行、无CRCRLF／孤CR，原line_endings16条绿。其余11冲突文件行尾逐一核；branch90重测1757条／实际工具289.660秒绿，line146已绿且语义不变不重复。两次shared fixture错误（旧no_redirect、错误模块属性identity）与最早6subcase接口红全部留原栈，最终改为真实request_bytes透传spy，不是假返回。

两次出口CI默认9／静态28／架构532全部全绿，第一次架构269.230秒，最终ci2.log保留实际时长。第一次9016条两红原栈已归档，契约同步后第二次完整安全诊断 argv为 `run_selftests.py --all --safe --allow-dirty-diagnostic --gui-wait 3600`；官方9018条／1091.7秒／0文件红，wrapper PID19776、起止与退出JSON为真实持久证据。冻结前后changed=[]，恢复后drift=[]，原状态恢复=True；冻结4649项SHA256 `4510572d809146ab84b6cfda0d44576d3b2fcceacd9cf4b95648f893cb4dc340`。

消费者158直接与显式清单missing=[]；原性能／启动性能／新增计量均实际执行。skip5逐项匹配本树324项台账，未登记=[]、GUI_DEFERRED=0、NO_RECEIPT=2。公共receipt前后相同=True，不伪造正式clean收据。候选历史三组94.251ms缩略图瞬态红仍只作历史事实，不宣称消除所有瞬态。

实际skip逐项原输出：

```text
  test_aigc_lint           test_unmounted_feed_validate_raises_toolerror_not_traceback (test_aigc_lint.SkillToolsWiringTests.test_unmounted_feed_validate_raises_toolerror_not_traceback) ← 需实机复验：发行包未包含受测 bundled skill；打包产物具备该技能后应恢复执行
  test_aigc_lint           test_unmounted_scripts_return_friendly_dict_not_raise (test_aigc_lint.BridgeContractTests.test_unmounted_scripts_return_friendly_dict_not_raise) ← 需实机复验：发行包未包含受测 bundled skill；打包产物具备该技能后应恢复执行
  test_core                test_stage_profile_wrong_preset_rejected (test_core.ValidateProfileTests.test_stage_profile_wrong_preset_rejected) ← 需实机复验：发行包未包含受测 bundled skill；打包产物具备该技能后应恢复执行
  test_desktop_tray        setUpClass (test_desktop_tray.TrayIconTests) ← 平台限制：当前进程不在有资源管理器任务栏的交互桌面（如隐藏测试桌面），Shell_NotifyIcon 无宿主；在默认交互桌面运行时应恢复执行
  test_desktop_tray        test_minimize_and_click_tray_cycles_without_crash (test_desktop_tray.TrayMinimizeCycleTests.test_minimize_and_click_tray_cycles_without_crash) ← 平台限制：当前进程不在有资源管理器任务栏的交互桌面（如隐藏测试桌面），Shell_NotifyIcon 无宿主；在默认交互桌面运行时应恢复执行
```

## 交付边界与状态记录原始核对

主树期间推进3a97b184，lead已明确本轮只交固定接收提交，最新主干26文件末差异与正式clean收据由lead后续接收。本轮不追ref、不主树merge、不push、不代用户回收／重装；manual pending仍在，不标整体TASK_COMPLETE。原master状态页ddf06逐字保留，不暂存。两父原R行集合相同；双方历史并集2507提交由双父合并全部保留，最终交付审计另核真实新HEAD。

合并后runbook§13两条原命令以接收HEAD验证，原始输出不得以说明代替；本次状态页无改动，第一条应空，第二条应为以下固定父并集（提交后再次实测）：

```text
$ git diff 00ff7962..HEAD -- 程序/project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'
$ git show HEAD:程序/project_status.md | grep -oE '^R[0-9]+' | sort -u
R1036
R1265
R1440
R1507
R1691
R1693
R2912
```
