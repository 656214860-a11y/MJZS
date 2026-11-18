# R3389：CPU参考计时量化修复与固定候选完整性能验收
<!-- round-evidence: {"commit_base": "39ed022e", "credential_hits": 0, "evidence_sha256": "3407e0756a2bc093", "exit": 0, "failed": 0, "passed": 28, "round": 3389, "tests": "run_selftests.py -k perf_baseline perf_measurement desktop_startup_perf"} -->

- 类型：§3.7 性能／资源轮；只处理 R3360 实测性能阻断，最终仅改测试计量helper与行为回归，生产源码不变。
- 测试与三个基线：受控原实现红→校准绿；最终CI默认9／静态28／架构532全绿；唯一完整诊断8909条／941.9s／0红，原性能与启动消费者均实际执行；158消费者全覆盖，skip5逐项登记，冻结4611项零漂移。三组稳定验证曾2绿1缩略图红与首次CI缺资源红均保留，不用后续绿抹除。
- 欠账：本固定候选完整性能诊断已绿，但NO_RECEIPT，正式干净主干收据仍由lead处理；用户本人删除与重装仍manual pending，不声明任务书整体完成。

## 固定输入与正规认领

- 旧树 `codex/skill-master-final` HEAD `39ed022ecee371dd5ae5094e96a41dbb8ef7008f` 为真实 R3360-FAIL 双父检查点；现补记最终提交 SHA。
- 旧树正常 `scripts/dev.py claim` 实际拒绝：ahead 16 个源码提交 >10。按用户预授权核对新路径与分支均不存在后，从固定 `9e3d1924b0595544242566809f594d962ec48154` 创建 `codex/skill-performance-final`，工作树 `D:\漫剧制作助手\.agents\worktrees\skill-performance-final`。
- 新树正常 claim 领取 R3389；dev scope 计划性能测试／计量行为回归／diagnostic_capture／selfcheck／启动性能测试／本结果与同名完成文件，无重叠。随后 `git merge --ff-only 39ed022ecee371dd5ae5094e96a41dbb8ef7008f` 精确承接；不追随 master、不改旧树／主树／历史。
- 不降低 ratio10、50ms、1500ms 等正式门槛，不减少实际资产／自检工作，不移除逐资产安全 resolve，不改 gate／record／rebase，不合 master、不 push、不代用户删除或重装。
- 既有父候选各2组和候选一次 cProfile 不重复；只对尚未证实的计时量化和50ms调用成本补受控证据。

## 计量根因与受控红绿

- `timer-selfcheck-result.json`：`time.get_clock_info('process_time')` 报 GetProcessTimes／100ns，但连续24个实际正增量全部15,625,000ns。原1m参考工作单样本CPU31.25ms／墙45.1654ms，32份连续工作归一CPU41.9922ms／墙42.9386ms；其后真实速度变化，所有样本保留，不能拿长窗频率变化当作量化误差证据。
- 唯一实现改动位于 `tests/test_perf_baseline.py::machine_speed_ms`：每样本连续8份完全相同的原1m算术循环，CPU总量除8；仍3样本取最快、原1m单位、页面3样本／CPU比值10、300真实资产与安全resolve不变。无负载补偿、重试、sleep、跳过或挑组。
- 行为回归直接调用正式helper，注入15.625ms量化时钟和可计数参考工作；5种真实速度（2／15.625／44／88／160ms）×64等分相位，固定速度模型绝对误差界≤1.953125ms。44ms参考／343.75ms页面真实比7.8125，旧短窗最小31.25造成ratio11假红；旧实现官方定向实测exit1，归一后官方3条exit0。另加3种速度顺序保留最快策略，真实500／44超预算仍拒绝。后续正式三组已执行新增4条均绿。
- 界限：上述误差界仅适用于固定速度／量化模型，不覆盖采样期间真实CPU频率变化。44ms时参考相对误差界4.439%，阈值附近仍可能有量化误判；没有声称完全消除此范围，也没有按机器负载提高分母。8份使原量化误差界收敛至1/8，代价是每组参考工作8倍；正式页面工作不减。

## 自检50ms分解

- 保持生产与自检测试原样。依赖同测试预热后真实入口16.4665ms；一次profile7ms。所有default／startup检查、严重性、固定路径I/O均保留。
- 逐项有界3次：主程序root 10.7419／2.3592／3.0837ms，真实临时项目配置与requirements文件11.7453／4.6109／3.1861ms；`record_selfcheck`在官方同环境DRAMA_SUPPRESS_DIAGNOSTICS=1下确实避写。最大主root工具检查5.8102ms、临时ledger检查7.0484ms；证据不足以安全改生产或解释旧75.9062ms，未将其宣称已证环境问题。

## 固定三组正式性能验证

- 事先固定3组 `run_selftests.py -k perf_baseline perf_measurement desktop_startup_perf`，均隐藏桌面＋跨树GUI锁；每组28条／零skip，全部结果保留、不追加整组重跑。
- 第1组28绿／37.5s，第2组28绿／40.3s；第3组42.3s唯一新红 `test_the_thumbnail_stays_off_the_interface_thread:396`，六张真实1024PNG缩略图当前UI调用平均94.2512667ms > 原25ms。
- 三组资产CPU比值、冷首帧1500ms、自检50ms和计量行为4条均绿；缩略图新红未豁免。CI/full尚未启动。已向lead报告，按授权只做一次低扰动原缩略图单项分解以定位worker启动／cache I/O／同步解码，保持六张／平均／25ms不变。

## 缩略图新红的有界诊断

- 唯一一次低扰动原单项trace使用真实六张1024PNG、原平均／25ms断言、隐藏桌面＋官方GUI锁，排队后自然结束。六次cold wall为24.3536／13.4211／12.5460／10.9982／10.2697／11.4671ms，均返回PhotoImage占位且pending逐项1→6；首worker启动9.1198ms，后续启动检查约0.00xms，任务save约5–7ms，磁盘命中5.7619ms。进入前worker=null／pending0／cache0且仅MainThread；诊断结束仅回收自身worker，reaped=true。
- 本trace单项绿不能覆盖第三组94.251ms红；未证调度负载根因，也未观测同步解码或旧线程／队列等待。现有行为测试 `test_asset_thumbs` 已检验build爆炸时UI仍只排队／返回占位、后台不可用不回退同步解码；本轮未削弱这些契约。
- 尚无有证且足够安全的最小业务优化；不为指标删除fsync／改缓存持久语义。已将全部三组和trace证据报告lead，请其裁定新阻断后续；CI／freeze full尚未启动，禁止用新一组绿掩盖旧红。

## 出口CI与新树测试资源预检

- 首次正式CI PID26212自然exit1／244.86s：默认9、静态28绿；架构532条唯一ERROR是 `test_agents_md:188` 读取被Git忽略的 `维护记录/基准历史.json` 缺失；无源码／性能新红。原完整日志已归档 `ci-first-red-detail.log`，状态finally原SHA20b1恢复。
- 按既有 `auto_full_safe.IGNORED_INPUTS` 口径，仅从固定旧候选树逐字补齐该历史输入，源／目标SHA256均 `5b0451c27a364b79dd430ca10889a407f2382ceec023aad6d7bd68f6b4946c24`，不暂存、不修改gate。`run_selftests.py -k agents_md` 实际非零条目执行exit0；其后唯一CI修复复验PID70752，原红不抹除。
- 新树三个gitlink目录原为空，按后台全量同资源策略从只读主树复制固定pin的干净嵌套仓库，逐文件SHA manifest源目标一致：HoLLMwood 10文件／`3ef9f995992edcbf514bed591a54b900b7502f11`，剧本锻造24文件／`6c3d73994f456b696de536c86602b4022824a535`，编剧技能集91文件／`357d1348ccaa1ab75f2f51ef7c90a7f00a686c76`；三个索引指针与普通跟踪159份AIGC完全不改。资源不暂存。
- 正式默认注册表实扫73项；随附FFmpeg／Git OpenSSL真实可执行。语法尺寸预检helper文件439行／行为测试70行，生产源码变更0，158消费者源missing=[]。无新依赖，不重测两覆盖基线。
- lead裁定：不扩生产／不删fsync／不再trace或重复3组，CI绿后冻结最终候选唯一完整诊断；缩略图在最终full必须按原25ms执行通过，若再红则保留完整证据报告，不追加直到碰绿。

## 冻结前正式CI最终结果

- 夹具恢复定向非零执行通过；CI修复复验PID70752于19:44自然exit0，默认9／静态28／架构532全部通过，架构304.721s。主状态页finally恢复原SHA20b1。首次CI资源红和固定3组缩略图红均保留，不被本次覆盖。
- 最终修改只有计量helper测试文件、直接调用helper的行为回归、本轮结果及同名任务完成文件；生产源码／requirements／两个覆盖维护基线不变。
- 下一阶段冻结包括所有受控source/tests/md/维护JSON/状态投影及补齐的历史输入和三个嵌套包正文；唯一完整安全诊断使用 `--all --safe --allow-dirty-diagnostic --gui-wait 3600`，真实NO_RECEIPT，不冒正式主干收据。冻结期间不改任何受测文件，结束再记结果。

## 唯一完整诊断与最终审计

- 固定输入 `39ed022ecee371dd5ae5094e96a41dbb8ef7008f`；2026-11-18T19:45:00.2345092+08:00 Start-Process持久wrapper PID71120，20:00:58自然退出。实际argv为 `run_selftests.py --all --safe --allow-dirty-diagnostic --gui-wait 3600`，官方已解析并运行，未重启／追加第二次全量。
- 官方8909条／941.9s／744测试文件／1011工作单元／0文件红；wrapper958.229s／exit0。原 `test_perf_baseline` 7条、`test_desktop_startup_perf`17条及新增 `test_perf_measurement`4条全部实际执行通过；缩略图原六张平均<25ms、磁盘<20ms、冷首帧1500ms、自检50ms、页面ratio10均保持原断言。未插桩最终用例，不编造通过项未打印的具体毫秒值。
- 冻结4611项，包括本轮结果／同名完成文件在内的全部source/tests/md、维护JSON、状态投影、历史夹具及嵌套包正文；SHA256 `ef0dac5fabd45f64da02be5e6eef5604ccf251c0281056a8ed2054f19b28ddef`。before→after changed=[]，finally恢复状态后除预期状态恢复外post_restore_drift=[]。结果与完成文件仅在自然结束且审计完成后补最终事实。
- `final_audit.py` 实际exit0：158直接与显式消费者missing=[]，计量／原性能／启动性能都执行；实际skip5逐项匹配323条skip台账，unregistered=[]；GUI_DEFERRED0。
- NO_RECEIPT2；公共 `full-safe-receipts.json` 前后SHA均 `fe024bde7b97cdd7e72794774fd9e0b0c511ecd0c6c41f3560f315f20555837e`，未冒正式收据；状态页finally恢复原SHA `20b1af1c0336184c5f8d53e052307edc1a8ccf27c2740cc85569a167e7df061a`。AIGC相对ee67ca06无差异，requirements相对固定候选无差异。
- 三组中的94.251ms红未证根因，本次完整用例绿只证明本次候选验收通过，不宣称消除所有环境瞬态；未为此改生产／降阈／删持久化／追加full直到绿。

## 交付与剩余边界

- 本轮计量缺陷已证因、先红后绿、正式完整诊断通过；下一步正常 `dev.py commit -m R3389: ... --tests perf_baseline perf_measurement desktop_startup_perf`，仅暂存两个测试文件、本结果、同名任务完成文件及官方机器证据，源码／基线／状态／日志／本地资源／用户数据不暂存。
- 提交SHA以真实Git回执／交付审计为准，不为自引用另开提交。正式主干合并／完整绿收据由lead处理；本轮不合master、不push、不代用户删除或重装，任务书整体不标TASK_COMPLETE。
