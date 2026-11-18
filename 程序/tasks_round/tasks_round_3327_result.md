# R3327-FAIL：模型池旧快照跨进程回滚修复与固定候选真实验收
<!-- round-evidence: {"commit_base": "e4dc1e09", "credential_hits": 0, "evidence_sha256": "87fc06b61d2287f2", "exit": 0, "failed": 0, "passed": 115, "round": 3327, "tests": "run_selftests.py -k l1_lost_update model_pool model_delete_stays_deleted l1_transport_requests"} -->

- 类型：§3.2 独立修复轮，仅模型池发布契约及回归；整表分支基线与固定候选验收随本轮完成。
- 测试与三个基线：受控原红／修后稳定21/21绿，最终提取后9方法全绿；最终官方line131条／11组全绿、branch1542条／84组／skip2全绿真写JSON；TLS＋跳转guard14条绿；完整consumer15子链356条／0skip绿（smoke900排队超时仍保留）。默认smoke9/9、静态28/28、架构532/532全绿。唯一冻结full8711条／832.5s／4文件12失败子场景／skip5，exit1；233消费者全部实际完成，未漏跑，不能称完整候选全绿。
- 欠账：本轮模型池确定性问题已闭环；完整候选新增4文件传输验收红，lead裁定本轮独立FAIL检查点，下一独立会话处理，不扩范围。正式干净收据、master合入及用户本人删除／重装未完成，不标TASK_COMPLETE。

## 固定输入、领号与检查点

核验旧树skill-release-integration干净、MERGE_HEAD空，HEAD `e4dc1e091e446f4dae7b9070d1ad89f3c9c1fe78`（补记R3321-FAIL），父为72caf20b与c34f5c36；原`dev.py claim` exit2报ahead12>10，未改工具／历史／伪record。lead裁定正规新修复树skill-modelpool-final，分支codex/skill-modelpool-final：从固定`72caf20b22ebce33593e8f5bc0e85264b0f721be`新建，正常dev.py claim实际领3327；scope infra/model_pool.py、tests/test_l1_lost_update.py、分支基线与另56活跃分支无重叠。随后`git merge --ff-only e4dc1e091e446f4dae7b9070d1ad89f3c9c1fe78`精确快进到固定候选，不新增merge、不追master；旧树和原功能树不动。

已读AGENTS、runbook相关领号／提交／验证规则、R3321／3317／3308、原任务书确认决策；加载diagnosing-bugs、minimal-diff-fix、scoped-tests、tdd。解释器主树随附Python -B，PYTHONUTF8=1／PYTHONIOENCODING=utf-8／PYTHONPATH tests+程序。现有Git usr/bin/openssl.exe已实测OpenSSL3.5.4，无安装；全部后续PATH带Git usr/bin及主树FFmpeg。仅复用既有两个阶段gitlink包工作内容（不复制.git）及ignored基准历史到新树，用户数据不入库。

### 11:50 原红排队恢复点（非冻结）

历史恢复点（该job已结束，初版备份已被最终提取版替代，不可再用于恢复）：唯一原红job `pwsh-cbabbd1b27124651`，git-dir/round-local-evidence/R3327/prove_red.py临时用HEAD原版跑最终新增回归，finally恢复当时修复备份。当时原版SHA256 `1ee8317f536cfd9dd3e5ec48e8af87f37105867eca6ec289c8a06f1ed1c32e81`；修复备份绝对路径 `D:\漫剧制作助手\.git\worktrees\skill-modelpool-final\round-local-evidence\R3327\fixed_model_pool.bin`，SHA256 `9e8a270de3bdefde1f4141cc137c6d9ee3ed204390e435c98ff92ada9d6a9045`。若进程异常中断：先核相关PID与该job已退出，再用该备份原字节恢复本树`程序/infra/model_pool.py`，验SHA等于修复值，才跑后续测试。正常finally已实现同一恢复。

该链通过gui_hidden+官方acquire_gui_lock排队，日志logs/R3327_final_tests_original_red.log；auto全量在.wt/ci已运行，GUI占用PID50044自11:47:08，本树不抢令牌／不重复开任务。本树仅该链，未启动consumer/测量/full，当前不是冻结期。最初controlled_red先因新树logs目录缺失未启动，创建目录后实际原红；remove测试误期望models空而既有pool会补内置desktop，已纠正为assertNotIn(old)，该误fixture不当有效红证据。

## 根因、修复与已获证据

根因：外部raw→编辑→store旧全量dict不在单一事务内；record_health的_update虽锁内重读，之后store仍可发布旧dict，删除新健康字段或回滚旧条目。读取模型池与配置的全部store/raw消费者后，仅改根因infra/model_pool.py：raw的兼容dict内存快照保留深拷贝基准及显式赋值标记，copy/upsert/remove/with_tasks保留；store在既有跨进程publication.access锁内读取最新值，仅发布快照改动／显式赋值／删除的顶层字段。models仍整体替换，不合并删除项；普通dict完整替换，dict(snapshot)显式退出增量语义。元信息不落JSON。初版_update调用内部_store；因模块大小硬门禁经lead裁定改为下述最终必要提取，最终_update将plain dict交回store，plain分支只快照／save不再_update，有限调用；原坏配置拒写与锁、缓存发布入口保持。

本轮不声称解决两个编辑者同时整体替换models的同字段冲突；保留既有last-write语义，不扩消费者／不改健康度字段内容。显式health={}／None／del／update与models={}、模型删除tombstone、原health有无、深层就地模型修改与copy、任务配置更新和普通dict完整替换均行为回归。无sleep、无吞错、无同进程锁替代跨进程锁；原并发测试全部断言保留。

最终新增测试对HEAD原生产重新实跑：job pwsh-cbabbd1b27124651已完整采集exit0（其内部要求红命令exit1）；日志logs/R3327_final_tests_original_red.log中10个health先写后旧store场景确定KeyError/model_health或old!=new，反向／显式清空等为绿。finally修复恢复SHA9e8a270d…，独立Get-FileHash再核且红链PID空后才继续。修后首次7方法15.850s绿；最终稳定3轮各7方法／12.304、14.306、14.811秒，全绿0skip，stable_result.json落盘；每轮含20组受控真实双子进程顺序与赋值操作组合及显式语义，不靠随机重复碰绿。

唯一后续串行job pwsh-1465250d73264e11（无外层超时），git-dir/round-local-evidence/R3327/validate.py：

- 官方branch：双父原JSON登记targets并集84组，gui_hidden＋官方acquire_gui_lock后直接branch_coverage_report.py --quiet --json，1540条／242.906s／0红／既有aigc_lint skip2，85模块1344/2450，工具真实写JSON（logs/R3327_branch_detail.log:159–161、359–360）。R3321临时master父快照已被本候选真测完整替换，无手填／拼接；所有测量变化照实保留。分支下限SHA256仍74b34c38ec72cd7720c25d18a7bfb8a0f186aec41c1f2b58155ac3e41fc646ba，两父原下限不降；行基线无改动，不无因重跑。
- 真TLS：run_selftests.py -k l1_transport_requests --serial，9条／7.5s／0红0skip／exit0，真实openssl自签证书测试绿，logs/R3327_transport.log；不改生产传输／测试／断言，无stub或安装。
- affected真实计划只有15文件，不冒称全部消费者；另外AST静态导入列模型池30个直接生产消费者及其233个关联测试，consumer_plan.json本地落盘。lead裁定用冻结full逐项补核全部233，若实际漏跑再补漏项，不额外重复218文件，不改smoke工具。

状态页只本地投影3328供架构核验；validate.py finally恢复HEAD原字节SHA18e751efa23415c26d57e39f67aa822ebb5793e7230e22e0e5a21e5168031ace，不暂存。全绿后才启动冻结完整diagnostic，启动前重查auto/full锁与PID。

## 固定主干传输变更对应的消费者 fixture 适配

首个affected完整收齐：15文件／356方法／885.3s／0skip，唯一test_model_pool_redirects红34个子场景；完整原栈保存在logs/R3327_affected_red_detail.log:134–373。30个重定向子场景len(seen)=0非1、两个成功响应False、两个UA访问seen[0]为IndexError；其余消费者本次绿。部分Tk销毁after错误日志照实保留，不当新增失败集合。最初消息中的340为未核日志的估值，正式口径仅356方法，不把34个subTest加进方法总数。job pwsh-1465250d73264e11已exit1，状态finally恢复，CI/full均未启动。

实际根因：固定父72caf20b已将api_endpoints._http_opener收敛至RequestsJsonOpener，而旧fixture只patch urllib HTTP/HTTPS handler；新入口还在selftest_env的DRAMA_SUPPRESS_NETWORK=1时提前offline，因此无模拟发送记录。不能据provider.invalid推测外网到达。lead授权本轮仅适配此model_pool消费者测试边界；dev.py scope tests/test_model_pool_redirects.py与另56活跃分支无重叠。所有原重定向301/302/303/307/308×同源／跨源／降级目标、请求次数、Authorization／X-api-key、UA、正文／流式返回断言原样保留。

fixture仅迁移到requests.adapters.HTTPAdapter.send：捕获真实PreparedRequest头，构造真实requests.Response＋urllib3 HTTPResponse，交生产opener实际执行3xx判定、read／stream／close，不直接伪造最终API结果；模拟send覆盖全部请求，非预期URL硬fail，DNS和socket硬fail保护禁止未模拟网络。局部受控环境按照test_l1_transport_requests惯例临时设DRAMA_SUPPRESS_NETWORK=0，异常也恢复，不改selftest_env／生产开关。第一次迁移未局部解除offline时13方法仍唯一fixture34子场景红，TLS9绿，停止未跑affected/CI；禁DNS最小探针确认无selftest_env时真实两条返回都seen1成功，结果redirect_probe.json落盘，随后仅补局部环境条件。

job pwsh-b57077a367074731复验redirect+TLS13方法／0skip／0红／exit0（10.416s外层）。随后affected外壳因900秒内部期限在GUI等待时exit1（901.777s外层）；非GUI已全绿，GUI尚排队854s，CI/full未启动、状态恢复。不是外层job超时，也不把它改称绿。精确核出本方残留gui_hidden PID51448／run_selftests PID26508仍活跃，不改运行中文件／不重启；一次原生进程句柄等待收集器job pwsh-5dff7cfa86484f21自然取得两PID exit0，原子链完整15文件356条／1342.1s／0红0skip，原始归档logs/R3327_affected_final_orphan_detail.log:136、148及orphan_exit.json。smoke900超时与真实完整子链绿分列，后续不重复15文件。

链结束后仅测试fixture收尾：Response.close在DNS/socket/send guard内finally，环境patch最后进入首先退出；新增直接调用getaddrinfo与connect并assertRaises的guard自证。job pwsh-b359438a1885408b官方相关小组14方法／8.6s／0红0skip／exit0，保留所有原断言；未改生产传输模块。

## 模块行数硬门禁与必要最小提取

CI前官方module_size_ratchet实测model_pool1163>1117唯一红（2方法1红）；不抬cap、不把内存逻辑塞进职责不同的config_snapshot磁盘备份。lead授权最小必要新L1实体infra/config_patch.py，先搜无等价，再scope新模块／_layers／architecture／两基线／下限／runbook，与另56分支无重叠。纯内存ConfigSnapshot深基准／显式赋值／copy／update／apply_to共34行，无IO；model_pool只保留锁／重读／save与适配，三构建器用copy保留编辑基准。store(snapshot)→_update(bound apply_to)→store(plain dict)是有限调用，plain分支不再_update，沿用publication.access的跨进程重入锁。20组受控双真实子进程及坏配置拒写测试在最终结构再跑，超时会直接失败，不仅口头宣称无死锁。

第一次提取预检model_pool1118>1117唯一红，收拢受影响_update说明1行后最终1117=既有cap，未删无关注释或压缩业务逻辑。静态8组＋新helper2方法共30条／24.188s／0红，job pwsh-bb8f283425084894 exit0（初次shell末尾diff掩盖unittest失败的exit0不当绿；以实际FAILED与复验OK为准）。新helper测试直接覆盖深基准、顶层修改／删除／新增／None、空快照、copy＋显式相同空值及JSON无元信息，测试仍位于tests/test_l1_lost_update.py。

层级_layers与architecture已登记config_patch L1。必要新增实体使原655/85模块口径改变，因此重新官方真实测量，不无因重复：唯一job pwsh-8e2c4be6cccc497e已完整exit0，measure_final.py依次受控9方法／11.535s全绿、行覆盖父并集10组＋本回归1组共131条／58.307s全绿，87/656真实写；分支父并集84组共1542条／219.426s／既有skip2全绿，86模块1347/2451真实写。日志logs/R3327_measure_final_detail.log:27、32、122–123、248–250、449–450。新config_patch4/4=100%，按现行floor首次实测向下取整规则新增100.0；旧floors逐项与HEAD相同，旧note不改。手册真实同步656/87/569/11与86，未手填JSON测量值。新L1 helper同时受covered/point结构和floor棘轮保护。

依赖等待器job pwsh-c01b23f82ba54e57在测量进程成功结束后才同步新floor／手册并串行启动官方local_ci.py exit，完整exit0／220.259s：默认8核心＋probe=9/9、静态28条／25.033s、完整架构532条／194.091s，全绿，logs/R3327_ci_final_detail.log:23、33、686、690，ci_final_result.json落盘。状态恢复HEAD原SHA18e751…；各阶段状态投影发生在freeze前，运行中未改源测试。原15完整消费者证据不重复，最终full逐项核对233消费者。

## 唯一冻结 full 检查点

CI后完整核查本树无测试残留，存在他树auto/full活动链57404→51172→4988；common-dir full-safe-selftest.lock及auto-full-safe锁存在。只读核PID，等待该链自然结束，不删他树锁／不force／不另开full。下一步等待器在其结束并复核两锁均无后，启动git-dir/round-local-evidence/R3327/full.py。该脚本先本地投影状态3328，再冻结tracked＋未跟踪新增源码、全部tests、维护JSON（含两基线／floor）、architecture／runbook／规则／状态等；唯一命令run_selftests.py --all --safe --allow-dirty-diagnostic。日志logs/R3327_full_safe_diagnostic.log，开始／结束freeze与结果JSON本地落盘，运行期不改冻结文件，结束比对后finally恢复状态原字节。不写正式收据，正式干净候选与master收据仍由lead统筹。

## 完整冻结诊断结果与下一轮精确交接

job pwsh-aee2325141354063已完整采集exit1，full_result.json：8711条／832.5s／4文件红（共12失败子场景），735测试文件／996工作单元；外层842.119s。日志logs/R3327_full_safe_diagnostic.log:17–20、3181。原样保留本次完整失败，不用旧R3317的8694绿替代，也不重跑full碰绿。

- 冻结1588文件，freeze SHA256 `4d8c5810a0207d6a96c217efcb3b279a0569ff8071661b34efd1579fbbb27d11`；before/after逐文件完全一致、changed_files=[]。全量结束后仅状态finally恢复HEAD原SHA18e751…；额外final_checks.json再核其它冻结文件无变化、状态逐字等HEAD。源码／测试／维护JSON／手册在运行期零写。
- 实际skip5与此前相同（日志3193–3198）：aigc_lint缺bundled feed/scripts两项、core缺bundled preset一项、隐藏桌面托盘宿主两项；无新增skip，全文GUI_DEFERRED=0。
- consumer_full_audit.json列233/233实际完成文件（按运行器结果行，不依赖串行才有的“开始”标记），missing_consumers=[]。完整执行不等于全部绿色，4文件红如表保留。未额外重复218文件。
- NO_RECEIPT原文在日志15、3339：不写绿凭据、分层基线或增量台账。common-dir共享收据前SHA85d49e4ae5ffead5a9f37fe41876e909d197f3394004d1d2848a4dcff7d9f49a，后SHAfe024bde7b97cdd7e72794774fd9e0b0c511ecd0c6c41f3560f315f20555837e，写时13:29:13；只读JSON最新正式记录仍R3293／2026-11-18T06:29:33／tree b9a0607080796c4b3bc7cdae0f11a605899e4e45，无R3327。只保存旧SHA未保存旧字节，不能证明具体变动来源，结论为共享收据被其它未知写者更新；不恢复／修改。运行器443–460的no_receipt分支跳过save_layer/save_full/save_cache；红分支虽调用invalidate，但本轮dirty使content_tree()返回空（selftest_receipts.py:82–91），未调用其写入。不能将共享摘要变化归为本轮绿收据。

四文件完整栈位于同日志3200–3334，以下仅经读取证实的入口事实与后续候选，不把无快照栈本身当作“绝无关联”的证明；这四测试与platform_tools／api_endpoints／qwen_setup／seedream_api逐字与固定输入e4dc1e09相同，final_checks.json记录SHA。完整栈均未进入本轮raw/store/ConfigSnapshot，当前未见快照语义关联；相关模型池受控/helper/full均绿。

| 失败文件／子场景 | 原断言与完整栈位置 | 已证 seam 与下一步最小复现候选 |
| --- | --- | --- |
| test_api_cache_usage／1 | StreamUsageTests.test_stream_requests_usage_and_reads_the_final_usage_chunk，seen[0] IndexError（3202–3207） | 测试113–127只patch urllib.HTTPSHandler，真实model_pool.http_stream→api_endpoints._http_opener→RequestsJsonOpener；候选为旧fixture拦截失效／offline提前分支。最小run_selftests.py -k api_cache_usage --serial。正文usage／cached_tokens／finish_reason原断言保留。 |
| test_model_gateway_robustness／2 | StreamLifecycleTests两个完成事件用例，ok False与完成事件不在network suppressed（3212–3224） | 测试43–56同样只patch旧HTTPSHandler，platform_tools.py:645–646在自检offline时提前拒绝；候选仅迁发送fixture并维持禁网guard，不预先改生产。最小run_selftests.py -k model_gateway_robustness --serial。 |
| test_shared_adapter_infrastructure／1 | NoRedirectSharedTests.test_every_adapter_uses_the_one_implementation，seedream_api.no_redirect AttributeError（3229–3234） | 测试20–22按函数身份要求三个适配器no_redirect；seedream_api.py:122–129已直接走RequestsJsonOpener，无no_redirect导出。后续应按真实共享传输行为核契约，不能为测试新增生产无用兼容。最小run_selftests.py -k shared_adapter_infrastructure --serial。 |
| test_latent_defects_r2175／8 | QwenProbeTests五redirect及两个消息断言、ResponseFailureKindTests.test_a_read_timeout_is_a_network_failure transport!=timeout（3239–3334） | Qwen测试126–130只patch旧HTTP/HTTPSHandler→qwen_setup.probe:99→model_pool.http_transport；read_timeout真loopback socket在测试84–90经默认入口且未局部解除offline。最小run_selftests.py -k latent_defects_r2175 --serial。需分别证明fixture／offline前置与真实读超时分类，不混为已证生产缺陷。 |

lead明确裁定R3327-FAIL独立收尾，本轮不扩四文件或传输生产模块，下一独立会话据此收口。无新回归被隐藏，完整候选仍失败；用户本人删除／重装、任务完成文件、master正式合入与干净全量收据仍未完成。

## 提交边界

正常dev.py FAIL检查点提交，仅本轮模型池／必要helper、两测试、层级／架构／手册、两份官方真测基线与只增新项floor、本结果／机器证据。状态页、日志、临时探针、用户数据、包工作内容均不暂存；四红文件与传输生产无改动。FAIL前缀工具不自动attach，显式官方round_evidence.write_evidence＋stamp_result，以实际暂存新增行凭据扫描和真实model_pool/helper/redirect/TLS定向生成证据，不伪造merge-ci-exit绿。提交hash由Git回执及lead交付补记，避免自引用额外提交。不合master、不push、不代用户删除或重装。

显式官方证据job pwsh-a122b2bdc9ff4d41已完整exit0：run_selftests.py -k l1_lost_update model_pool model_delete_stays_deleted l1_transport_requests，7文件／12工作单元／115条／14.0s／0红0skip（logs/R3327_official_targeted_detail.log:3、17、29、33）。实际暂存新增行扫描0命中，judge=[true,true]；证据tasks_round/evidence/R3327.json与官方stamp头真实生成，不把该定向绿冒充full绿。dev.py commit仍使用R3327-FAIL前缀正常门禁提交，结果保持完整4红检查点。
