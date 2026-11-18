# R3302：WebSocket 协议测试关闭帧发布同步修复
<!-- round-evidence: {"commit_base": "f34f4491", "credential_hits": 0, "evidence_sha256": "a149852079a2d4c3", "exit": 0, "failed": 0, "passed": 66, "round": 3302, "tests": "run_selftests.py -k platform_tools speech_api http_client http_boundary"} -->

- 轮次类型：§3.2 修复轮；定位测试 fixture 线程同步根因，生产协议模块保持不变。
- 测试与三个基线：原用例1000次实红7次，保留HEAD原版另1000次6红；受控事件同栈红→修后绿，修后1000/1000稳定绿。直接协议/HTTP/语音消费者66/66，默认8核心+probe=9/9，affected31/31，架构532/532。唯一冻结完整safe diagnostic8626条/731.0秒/skip5/2个范围外UI红、exit1；1560冻结文件全不变，明确NO_RECEIPT，未冒称全量绿或正式收据。
- 欠账：WebSocket历史红已根因修复并稳定绿；完整safe新见2个范围外UI红，由lead下一独立整合会话取证，不扩大本轮。用户本人真实删除／重装尚未执行，任务书整体未完成。

## 起点与范围

工作树dsh-6187d0c7-f35d，分支codex/skill-residue-governance，起点HEAD=`f34f4491d13bc9c2ab5d2e60a0404d8761ab9131`（补记R3301 merge hash，双父e56f42fc与master40200330）。开工status干净，master=`4020033013d980b10ecef98baed110b45fdad06a`，HEAD...master=7/0。已读AGENTS、runbook相关领号/提交/修复/全量规则、原任务书已确认决策、R3301/R3299结果，加载diagnosing-bugs、minimal-diff-fix、scoped-tests、tech-writer。

实际dev.py claim领R3302，scope contract/platform_tools.py与tests/test_platform_tools.py另53活跃分支无重叠；两目标与master无diff。无对应队列项不冒领。发现其它树dsh-5158b800-34ae全量PID42360/50640在跑，已告知lead；不抢全量/GUI锁，仅先做非GUI单项诊断。不修改其它工作树，不合master、不代用户删除/重装。

## 复现与根因检查点

程序cwd、共享Python -B、PYTHONUTF8=1、PYTHONPATH=tests;程序；原命令`python -B -m unittest test_platform_tools.WebSocketTests.test_handshake_text_fragments_ping_and_close -v`首次1/1绿。有界1000次原封不动重复，1.742秒，7 errors/0 failures/0 skip，全部同栈`:403 frames['close'] KeyError: 'close'`；UTF8日志logs/R3302_original_repeat.log，job pwsh-deaab5f802b046fa已采集exit1。

本地受控探针在服务端read_frame真实收到opcode8后，以Event暂停返回，从而暂停共享frames['close']发布；Event只在真实Thread.join边界释放，未加sleep或重试。原测试必现1 error，同栈KeyError，日志logs/R3302_controlled_red.log。线帧证据为pong=(10,6869,true)、text=(1,e4bda0e5a5bd,true)、close=(8,空,true)。证明客户端已真实发送带掩码close，失败发生在服务端读完到字典赋值之间的合法调度窗口。生产recv_text收到close→close发送应答→返回None不承担等待测试服务端字典发布职责；原fixture只在addCleanup里join，断言先于join。

最小修复仅tests/test_platform_tools.py（+5/-3）：fixture显式交回服务线程，在协议断言前join(5)并断言线程确已结束，拒绝握手用例适配解包。原协议断言与原cleanup全部保留；生产无需改动。相同受控探针1/1绿，logs/R3302_controlled_green.log，真实线上帧证据相同；修后1000/1000、0skip、1.906秒，logs/R3302_repeat_green.log。临时探针位于common-dir/round-local-evidence/R3302，不在程序递归生产范围。

首次1000次7红日志在随后同名稳定性调用时被覆盖（该次原始7红完整输出已由read工具取证）；已从HEAD导出未经修改原测试到本地证据目录，独立再跑1000次，实红6次同栈，1.817秒，完整保留logs/R3302_original_repeat_red_preserved.log。两轮实红均非重试至绿，修前共2000次13红；修后独立1000次0红。受控red日志未被覆盖。

## 适用回归检查点

官方run_selftests.py -k platform_tools speech_api http_client http_boundary --serial：66/66、10.3秒、0skip，job pwsh-431a83ca40664bc9已采集exit0，logs/R3302_direct_consumers.log。仅测试fixture改动，无生产控制流变化，不重测/调低生产覆盖率基线。

状态页先按功能树约定备份HEAD原字节SHA256=94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e，本地仅投影当前轮次3303=M3302+1，提交前恢复，不暂存。第一次按文字误将smoke调用为不支持的--probe，工具exit2且未跑测试，logs/R3302_smoke_probe.log；已核实默认smoke内置隐藏桌面probe，改用真实默认入口，未改程序代码。后续默认smoke/affected/architecture串行执行job pwsh-33f290ca56d6483e，已采集exit0；默认8核心+probe=9/9、0.158秒，affected31/31、0skip（包装4.075秒），架构532/532、0skip、214.083秒（包装214.642秒）。命令、exit、用时及UTF8日志路径保存common-dir/round-local-evidence/R3302/checks.json。先等待既有GUI锁，不抢锁不重启。

2026-11-18 08:19冻结前复核：HEAD仍f34f4491，master仍40200330，无运行中run_selftests/smoke/gui_hidden PID，共享full-safe-selftest.lock与gui-selftest.lock已自然释放。最终测试diff +5/-3，生产及两个覆盖率/分层基线diff为空、git diff --check通过。唯一冻结完整safe已于08:19:39+0800启动，job pwsh-9dc5d742ba3d44fc，外层Python PID50052；命令`python -B run_selftests.py --all --safe --allow-dirty-diagnostic`，UTF8日志logs/R3302_full_safe_diagnostic.log。冻结1560文件，其中1506个tracked Python（程序cwd1505份+仓库根1份），另54个维护基线JSON及状态页。文件哈希/真实命令/PID/日志/exit落common-dir/round-local-evidence/R3302/full_run.json和freeze_before/after.json；完整运行期不改源码、测试、基线和状态投影。若中断先查PID/日志/JSON，不盲重跑。

08:22只读发现master已继续推进，HEAD...master由7/0变7/15，已告知lead并收到明确保持冻结指令。当前全量仅证明f34f4491+R3302测试修复，不冒称当前master整合树通过；不为追master中断有效全量。后续合并冲突及最新主干验收由独立轮/lead统筹。

## 唯一完整安全全量结果

job pwsh-9dc5d742ba3d44fc已采集exit1；全量8626条、731.0秒，外层739.442秒，2个文件各1红，skip5。运行后freeze_before/after对1560文件完全一致，changed_files=[]、all_frozen_unchanged=true，期间源码/测试/基线/状态投影未动。日志明确NO_RECEIPT，不写真实绿凭据、分层基线或增量台账。WebSocket原项所属test_platform_tools三个分组4+16+11条均绿；不把模块通过误称整个full绿。

UTF8原始日志logs/R3302_full_safe_diagnostic.log:3100汇总、3112–3117 skip、3119–3136两项完整栈：

1. test_model_manager_actions.SpeechSettingsTests.test_fields_show_settings_and_missing_key：tests/test_model_manager_actions.py:118 `self.assertGreater(scroll.form.winfo_reqheight(), scroll.canvas.winfo_height())`，AssertionError:1154 not greater than1154。
2. test_ui_motion_perf.EasedScrollTests.test_clamped_at_both_ends_and_reverse_returns：tests/test_ui_motion_perf.py:95 `self.assertAlmostEqual(canvas.yview()[0], 0.0, places=3)`，AssertionError:0.001 !=0.0 within3 places (0.001 difference)。

5项实际skip逐项对照tests/skip_reasons.py、维护记录/skip台账.json：test_aigc_lint两项unmounted feed/scripts、test_core一项stage_profile均REQUIRES_BUNDLED_SKILL；test_desktop_tray的TrayIconTests.setUpClass与最小化循环均PLATFORM_NO_TRAY_HOST（台账R1850整类同条件）。与R3299既有5项一致，无新增skip，无GUI_DEFERRED。

完整失败集合与栈已立即报告lead；lead明确R3302-FAIL最小收尾，不再full、不扩修UI。speech1154==viewport不自动推断生产错误，更不修改断言造绿；需下一独立会话依最终几何契约取证。全量结束master为71393d999ee7a5fb46d01c855e7d9f6e8c23bc95（HEAD...master=7/15），只读目标差异显示speech UI/测试与本树存在差异，motion两文件无差异；本轮不整合、不修改他树。

状态页已恢复HEAD原字节3278，SHA256=94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e，git diff --exit-code HEAD -- project_status.md exit0，不暂存。恢复前再检1560冻结完全一致，恢复后仅状态页按明确约定撤回本地投影；测试与生产/基线仍不变。git diff --check通过。

## 失败检查点提交

依lead明确裁定，仅提交tests/test_platform_tools.py、本轮结果与官方tasks_round/evidence/R3302.json；日志、状态页、临时探针、用户数据不入库。FAIL前缀不匹配提交工具ROUND_MESSAGE_RE，不依赖--tests自动attach；已对最终最小暂存区用官方round_evidence.py 3302 -k platform_tools speech_api http_client http_boundary真实运行并扫描，job pwsh-9641695b7e024e5a已采集exit0，UTF8日志logs/R3302_official_evidence.log；官方R3302.json commit_base=f34f4491、passed66/failed0/exit0、credential_scan.ran=true/hits=[]、generated_at=2026-11-18T08:33:21。随后官方stamp_result写机器头，并复扫最终暂存新增行0命中，统一dev.py commit -m R3302-FAIL收尾。定向证据不替代完整全量结果；结果文件提交前冻结，自身hash由lead引用所在提交或下轮补记，避免自引用额外提交。本轮不声明任务书完成、不push、不合master。
