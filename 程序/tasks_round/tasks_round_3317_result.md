# R3317：最终两项 UI 验收的真实 Tk 根因修复
<!-- round-evidence: {"commit_base": "395304ee", "credential_hits": 0, "evidence_sha256": "8d72946d87de78d8", "exit": 0, "failed": 0, "passed": 105, "round": 3317, "tests": "run_selftests.py -k model_manager_actions ui_motion_perf test_selftests selftests_gui_token"} -->

- 类型：§3.2 独立修复轮；范围仅语音表单验收与 eased scroll 边界。
- 测试与三个基线：两项根因先红后绿；稳定140/140、直接消费者105/105、默认8核心＋probe=9/9、静态28/28、完整架构532/532。唯一冻结完整safe diagnostic8694条／856.1秒／skip5／0红、exit0；1586冻结文件全部一致。明确NO_RECEIPT，不冒称正式干净全量收据。
- 欠账：两项UI验收红已闭环，生产不变；正式干净整合树全量凭据及用户本人删除／重装仍由lead统筹，任务书整体未完成。

## 起点、授权与边界

工作树 dsh-6187d0c7-f35d，分支 codex/skill-residue-governance，起点干净、MERGE_HEAD空；补记上一轮提交 `395304ee9d686d59b6a56ac62956f219c9ee09ed`（R3308）。只读核对master `72caf20b`：motion目标无差异，speech主干版本缺本树短屏／Tab覆盖，不盲目整合或回退。本轮dev.py claim实领3317，scope四UI相关路径与另54活跃分支无重叠；无匹配队列项，不冒领。

已读AGENTS、runbook相关规则、R3308/3305/3302/3290与原任务书确认决策；加载diagnosing-bugs、minimal-diff-fix、ui-ux-pro-max、scoped-tests。真Tk使用gui_hidden和跨树GUI令牌。程序cwd、共享Python -B、PYTHONUTF8=1、FFmpeg PATH、PYTHONPATH=tests及程序；临时探针仅git-dir/round-local-evidence/R3317，日志UTF8不暂存。不合master、不push、不代用户删除重装；功能分支不提交状态页，必要投影后finally恢复HEAD原字节。

## 复现检查点

- 原命令 `run_selftests.py -k model_manager_actions ui_motion_perf --serial`，job pwsh-e8fc6c5fcb174dab 已采集exit1。日志 `logs/R3317_original.log`：39条／10.5秒／0skip，speech原118行1154 not greater than1154，motion27条本次绿。不能把单次绿当原motion问题消失。
- 隐藏桌面几何／逐帧与有界重复探针job pwsh-fb56c8959a0442e7已采集exit0，日志 `logs/R3317_probe.log`，脚本位于git-dir/round-local-evidence/R3317/probe.py。当前真实屏1080×1920、DPI95.916、scaling1.332；默认窗口991×1227=request，viewport950×1154=form、yview(0,1)，按钮真实屏幕y为1209..1246。600高时viewport527、yview(.5433276,1)，按钮y为582..619；默认及短窗是否在窗内均由原生rooty几何断言验证。默认不需滚动合法，短窗仍必须可滚达。
- motion 20次原逐帧记录与30次原封不动用例全绿，仅说明本次无自然复现。真实canvas border=highlight=0、region2000高；顶端最后几帧为8→4→2→1→0px，原0.001精确对应尚余2px，非合法inset顶点。
- 受控时序探针job pwsh-e0961fc4da2c41e3已采集exit0，`logs/R3317_motion_timing.log`：只把原请求16ms的Tk定时回调实际交付延至60ms，不mock几何。3/3在原.6s采样同栈红0.001，canvasy2、running=true；继续泵原回调至.6686–.6713s则顶点0且idle。证明根因是测试未等待完成，非生产clamp错误。
- 永久回归先保持原.6秒泵、增加正常16ms与受控64ms两个子场景，job pwsh-bbd558eb73b64b77已采集exit1，39条／12.0秒／0skip；speech修后12绿，motion64ms场景原places=3断言仍0.001红（`logs/R3317_controlled_red.log:22–27`）。随后仅测试改成按running有界3秒泵真实事件，明确idle且不得越过deadline，原上下界places=3不变；无新增sleep、不改生产、不缩字体或放宽误差。
- speech仅在默认内容／屏内／固定按钮检查后显式600高再执行原Greater／滚条等断言，原独立短屏Tab／所有输入控件焦点／鼠标滚动测试保持。两个根因和test-only修复均获lead明确认可。
- 初次修后两模块job pwsh-b8b1f49a3e494db8已采集exit0，39条／0skip；最终又补deadline末帧不得超时断言。最终稳定重复job pwsh-80cf5f2fdf0f4eba已采集exit0，日志 `logs/R3317_stable.log`：100次motion（每次16/64ms双场景）＋默认speech20次＋短屏Tab20次，140/140／274.595秒／0skip。最终测试SHA256：speech `73b2b525b4ff35b751531c74f3e46ee265095a10ca2fa8b738e12b7197ffa725`，motion `b2542a2758cadef5edcf178645b878457fbc113878e3fa4869069840508f77c6`；生产／基线无改动。消费者及官方CI job pwsh-dbca30a43dc14ecb已采集exit0，runner为git-dir/round-local-evidence/R3317/validate.py，结果落validation.json。官方affected选4文件105条／104.4秒（含GUI排队）／0红0skip，日志 `logs/R3317_affected_hidden.log:25–39`；smoke affected总10项全绿。官方local_ci exit 216.884秒，默认8核心＋probe=9/9、静态28/28／25.520秒、架构532/532／190.445秒，失败集合空，数量与上轮532相同；`logs/R3317_ci_exit_detail.log:23–36,686–690`。状态投影3318后finally精确恢复原SHA94c8999d，git diff HEAD状态页为空。本轮生产不变，未重测或更改覆盖率基线。

## 后续验证与提交

根因、最小测试修复、稳定重复与消费者／默认／架构已全绿。采用tech-writer工程留痕规则记录真实边界，不把定向或诊断写成正式收据。

唯一完整 `run_selftests.py --all --safe --allow-dirty-diagnostic` 已启动job `pwsh-2f6d4c61575143fe`，UTF8日志 `logs/R3317_full_safe_diagnostic.log`。启动前相关Python PID及full/auto锁为空，auto status无后台在跑。git-dir/round-local-evidence/R3317/full.py先投影3318，再冻结1586文件（所有tracked源码.py／tests全目录／维护JSON／架构与运行规则／状态）；freeze SHA256 `e55717fde8a46381dab03b36f2c9a3b22bc80a04dc67689784d4d3f25e3b51e9`，freeze_before.json已落盘。完整运行期间不改任何冻结文件，结束比对freeze_after.json后finally恢复状态原字节；receipt_before SHA256 `85d49e4ae5ffead5a9f37fe41876e909d197f3394004d1d2848a4dcff7d9f49a`。结果落full_result.json；job已完整结束并采集exit0，外层865.004秒。

## 完整诊断结果与最终边界

- 完整734文件／995工作单元，8694条／856.1秒／0红；`logs/R3317_full_safe_diagnostic.log:3062,3082`。speech12条、motion16+11条、startup15条、历史table15条本次均绿（日志2429、2775–2777、3004、3068）。本轮未新增测试方法计数，受控回调为同一方法subTest；相对R3302的8626增长来自R3305整合及R3308已有测试，不冒称本轮新增68条。
- 实际skip5逐项与R3302及台账一致（日志3074–3079）：aigc_lint未挂载feed/scripts两项，core错误preset一项，均REQUIRES_BUNDLED_SKILL；TrayIconTests.setUpClass及TrayMinimizeCycleTests最小化一项均PLATFORM_NO_TRAY_HOST。无新增skip；全文GUI_DEFERRED计数0。
- 1586份before/after逐文件一致，changed_files=[]，all_frozen_unchanged=true；全量后状态恢复前比对完成。receipt前后SHA均 `85d49e4ae5ffead5a9f37fe41876e909d197f3394004d1d2848a4dcff7d9f49a`，未写正式绿凭据、分层基线或增量台账；NO_RECEIPT原文在日志7与3080行。finally恢复状态原SHA `94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`；恢复后除该授权状态撤回外冻结文件再次无漂移，git diff HEAD状态页为空。
- 全量后预提交核验git diff --check通过；status仅两测试及本结果；暂存区为空，MERGE_HEAD不存在。核验命令末尾git rev-parse -q --verify MERGE_HEAD返回1是预期空合并状态，不是测试失败。

## 提交

采用正常 `dev.py commit -m "R3317: 修正语音短窗与滚动完成验收 REQ-S01-71 DES-S01-71" --tests model_manager_actions ui_motion_perf test_selftests selftests_gui_token` 生成真实官方定向证据及新增行凭据扫描，只暂存两测试、本结果、自动tasks_round/evidence/R3317.json。原始日志／临时脚本／状态页／用户数据不暂存，覆盖基线不改。提交hash由本轮Git回执及lead下一交付补记，避免自引用额外提交。

回滚仅revert本轮即恢复原测试夹具，不影响生产。未合master、未push、未代用户删除或重装；任务完成文件、正式干净整合树凭据与master合入由lead下一独立会话统筹，不标任务书整体TASK_COMPLETE。
