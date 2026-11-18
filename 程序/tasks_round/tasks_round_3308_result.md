# R3308：启动关键期遗留临时文件递归扫描最小修复
<!-- round-evidence: {"commit_base": "5405e063", "credential_hits": 0, "evidence_sha256": "d053410cc9fead0a", "exit": 0, "failed": 0, "passed": 230, "round": 3308, "tests": "run_selftests.py -k test_core desktop_startup_perf l1_bounded_growth_r3269 exit_maintenance force_quit test_storage test_timers stage_command_contract"} -->

- 类型：§3.2 独立修复轮；只处理启动递归扫描，不混语音或 motion。
- 测试与三个基线：原零walk与1秒断言不变；关键三组×3为9/9绿，最终相关定向230条绿（既有skip1）、默认8核心＋probe=9/9、静态28/28、受影响架构25/25绿。此前完整97文件2118条唯旧fixture1红，补后相关定向闭环；完整架构532条唯旧分支快照1红，官方真实重测后相关门禁闭环，不冒称同次全套全绿。完整safe本轮按用户指令未跑。
- 欠账：启动递归扫描以退出维护最小接线修复；两个UI红项、正式full-safe及用户本人删除／重装仍未完成，任务书整体未完成。

## 起点与范围

工作树 `dsh-6187d0c7-f35d`，分支 `codex/skill-residue-governance`；起点干净、MERGE_HEAD 空。补记上一轮双父失败检查点 `5405e063a97efb751ec524d2ca542d96a088b70a`（R3305-FAIL，功能父78f58597／master父71393d99）。只读核对最新 master `72caf20b`，`infra/temporary_sweep.py`、`desktop.py`、`ui/desktop_project_pages.py` 无精确修复差异；本轮不整合主干其它49文件。

已读 AGENTS、runbook §3/4/12–16、R3305结果、原任务书确认决策；加载 diagnosing-bugs、minimal-diff-fix、scoped-tests。dev.py claim 实领3308；实际路径 scope 与另53活跃分支无重叠。无匹配队列项，不冒领。功能分支不提交 project_status，验收必要时本地投影后恢复HEAD原字节。

## 根因、先红及被撤回候选

- 原红命令：`run_selftests.py -k desktop_startup_perf l1_bounded_growth_r3269 --serial`，job `pwsh-ee4d5382f81f433d` 已结束exit1。35条／426.4秒（约400秒为共享GUI排队）、0skip；零扫描1!=0原栈为 `temporary_sweep.work:51 → sweep_stale_temporary_files:31 → os.walk`。同文件同日续开1秒断言另红，完整输出在 `logs/R3308_red.log`，已报lead，不臆定根因。
- 低扰动探针只在内存收集事件、测试后输出。原schedule1072.4ms、walk1075.7ms时paused=true/settled=false；resume1364.0ms之后才settled=true（`logs/R3308_timing_red.log`）。原1秒用例在该探针未复现，不声称确定性或已找出独立根因。
- 首候选把线程放到现有项目维护idle：新增交互边界测试先红（建页尚未完成／paused=true／settled=false），生命周期4条先红2条。候选定向65条64绿，但原零walk仍1红；继续测得resume1299.8ms、walk1301.1ms、交互观察点1369.0ms才返回。Tk会在同一次update中排空idle，只有settled标记不构成可交互证据。此不足候选已撤回，`ui/desktop_project_pages.py`及`tests/test_stage_wiring.py`恢复HEAD原内容，不混入最终差异。

## 已否证的tick候选（已撤回）

- `desktop.load`不再立即启动线程，只把本次实际root记录到一个待办槽；重复load覆盖旧待办，load(None)清除，路径校验失败不碰原项目。
- `ui/desktop_automation_tick`复用已有首帧恢复后的150ms周期tick，在未暂停且未关闭时消费一次；先清空待办再启动，root不符拒绝迟到项目，线程启动异常不反复派发。没有新调度器、sleep或任意delay，原项目维护行为不改。
- `infra/temporary_sweep.py`算法原字节不动，清扫范围、24小时TTL、名称正则、删除入口、followlinks=False及目录链接剪枝保持。新增TTL等号严格边界与链接剪枝回归；原范围及真实后台线程测试继续保留。
- 新增真实Tk集成证明完整写页及after(0)响应事件均先于清扫；清扫在settled=true/paused=false时只派发一次。无Tk生命周期回归覆盖暂停、重复消费、切换、取消、关闭、最新待办、启动异常和恢复失败／空项目。未选项目不清扫程序目录；清扫范围仍是已打开项目，用户未选项目时不存在合法清扫root，不扩大到程序或项目库。
- 最终低扰动真实线程探针 `logs/R3308_live_timing.log`：交互predicate3978.3ms已返回，首tick约4044ms，真实walk4046.7ms；在原零扫描观察区间之外，且清理功能确实继续执行。与仅标记settled有实质区别。

## 实际验证与进行中检查点

所有命令使用随附Python -B、PYTHONUTF8=1、PYTHONIOENCODING=utf-8、FFmpeg前置、PYTHONPATH tests;程序、程序cwd；Tk统一隐藏桌面及共享令牌。早期PowerShell Tee日志确为UTF16，结束后已无损转为UTF8，后续子进程直接UTF8文件句柄。原始行为输出完整保留，未修改测试通过数。

- 最终定向 `run_selftests.py -k desktop_startup_perf l1_bounded_growth_r3269 project_recovery stage_wiring --serial`，job `pwsh-210f904e115549cc` exit0，66/66／24.4秒／0skip，原零扫描、1秒断言不变。日志 `logs/R3308_tick_targeted.log`。
- 时序探针job `pwsh-b48430d44330461c` exit0，4个行为／真实清扫目标全绿；仅测试夹具临时目录，不碰真实用户数据。临时.py全部放git-dir/round-local-evidence/R3308，不进入程序生产扫描。
- 唯一官方affected计划来自smoke_test._affected_test_plan(['desktop','desktop_automation_tick','temporary_sweep'])，实际95文件；直接运行该官方生成的全部筛选词，无smoke外层900秒包装，消费者不漏。验收job `pwsh-8dd21fae379f4480` 正在执行affected→默认冒烟→架构，不重复启动、不抢其它树令牌或full锁。该runner默认冒烟误加不支持的--probe，lead已指出；保留其exit2，结束后只补正确默认命令及STATIC_GATE_TESTS，不把CLI错计为业务测试红或通过。
- 冻结源码1509文件，摘要 `8aa4b25c5ac74c18c4492d8c84ca7f290449604eed8b0dd297fd5bc9ba3b2582`。状态本地投影3309=M3308+1，finally恢复HEAD原字节SHA256 `94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`，最终不暂存状态页。

## 完整验收否证与退出契约裁定

唯一affected自然完整结束2094条／704.2秒／3skip，仅startup文件2红：原1秒断言及零walk均复现（logs/R3308_affected_hidden.log:1547–1566）；无scope外UI红。原tick在负载下仍可同次update被执行，前述短定向/局部probe不能称稳定修复。架构532条／186.815秒／1红，候选引入Desktop共享状态45>44，未改ratchet豁免；撤回tick候选及相应临时测试，禁止用更多延迟碰绿。源码冻结DRIFT[]，finally状态页恢复原SHA94c8999d，git diff状态页为空。默认误命令exit2如实保留。

lead明确授权采用已有退出维护链：清扫触发契约有意改为“窗口销毁后的退出维护”，不再承诺打开项目时立即清扫。复用exit_maintenance→storage_maintenance现有无窗子进程，不新增launcher/调度器；显式传本实例曾成功打开root的去重快照，兼容旧调用默认空；不递归搜盘、不从其它配置扩大范围、不碰workspace维护的用户项目禁区。原清扫算法/TTL/命名/链接规则保持。后续先红后绿覆盖外部root、forced、重复close和退出真实清扫，重新相关affected/架构/正确默认smoke；不重复完整safe。

## 退出方案实际验证检查点

- 新接口先红：exit_maintenance正常／forced显式roots参数不支持（TypeError）、storage argv不支持（TypeError）、真实外部临时文件仍存在（AssertionError）、finish_close未传快照（KeyError）；均为新增行为精确红，原日志未掩盖。一次测试类名误写DesktopQuitTests导致loader错误，已纠正QuitTests后实测快照KeyError，不计为行为红。
- 生产最终路径：Desktop初始化及load单一写者set，既有项目列表只表登记状态，不能替代“本实例曾打开”事实；新增set必要且生命周期限本实例。Lifecycle只读tuple快照，不给set赋值、不跨类共享写者；shared-state原门禁4/4绿，无改上限或动态setattr绕闸。
- finish_close在销毁前快照、销毁后复用exit_maintenance；只有非空roots才加可选参数，旧默认调用及mock补丁面仍兼容。仅storage收到显式路径，logs/workspace原接口原顺序不动。参数经现有launch_background列表argv，无shell；maintenance main在原有3秒等待之后按去重显式roots调用原sweep，未增等待，未改工作区清理边界。
- test_force_quit18/18绿（含新增正常／强退快照不可变、已有重复关闭及调度顺序）；真实维护进程独立probe exit0／3.12秒：显式外部项目25h临时文件删除、新鲜文件和未打开目录文件保留。原清扫函数不变，仅纠正旧schedule doc“后台线程豁免启动”的错误描述。
- 退出方案定向job `pwsh-756f27682e3644e7` 完整84条／412.2秒（约400秒GUI排队），原零walk与1秒绿；唯一红为新增外部项目夹具缺config.json被open_studio合法拒绝。已仅补fixture `{}` 配置，完整原日志 `logs/R3308_exit_targeted_fixture_red.log` 保留，不改生产或断言。
- 最终fixture后重新冻结1509源码文件，摘要 `d6380b7f006861fcdccaff7b216ba6df6e663a19b78d90968e3ed0ee7b92e0d1`。最终验收job `pwsh-99ffe5808797454e` 正在跑：原零walk／原1秒／roots切换去重三组各3次，失败即停；通过后唯一官方affected97files→正确默认smoke（无--probe参数，自带probe）→静态28→架构→force18→真实维护进程。官方完整清单与命令JSON放git-dir/round-local-evidence/R3308/affected_exit_plan.json，未含known语音或motion红；不扩大修复范围。

## 退出方案完整验收与必要补测

- `pwsh-99ffe5808797454e` 已完整结束。关键三组×3为9/9绿；官方97文件affected2118条／605.1秒／3项既有skip，仅旧core夹具1红（`logs/R3308_exit_affected_hidden.log:1743–1753`）：test_script_stage_project_loads_without_storyboard_json通过__new__绕过构造，缺少新增roots集合。startup15条全绿；不把该次affected写成全绿。
- 正确默认smoke exit0（8核心＋自动probe），静态28条绿；架构532条／195.859秒仅分支快照1红，storage_maintenance分母171旧值与当前175不符；shared-state等531条绿。force18/18绿，真实进程probe再次exit0／3.17秒。状态finally恢复SHA94c8999d；源码freeze再验DRIFT[]。
- lead批准：本次仅补test_core旧夹具roots=set()初始化，原断言不动，生产不加getattr吞状态；scope新增test_core及分支基线无重叠。搜查20处Desktop.__new__，只有这一处直接调用load缺构造；stage_command_contract与timers仅用其专属方法，仍纳入最后定向。
- lead批准按官方branch_coverage_report读取原JSON全部登记targets真实重测写JSON，不手调171→175、不降floor；其它模块快照变化照实保留。最后补全core、原startup、exit/storage/force/L1及同类夹具定向、默认／静态及分支／层级／共享状态／覆盖率／轮次架构门禁。此前97全套唯夹具红的事实仍保留，不重复耗时大套件。
- 官方测量入口纠错：job `pwsh-f2b533f4167a4925` 因误用不支持的--summary在解析阶段exit2，未跑测试／未写JSON，原日志 `R3308_final_branch_cli_error.log`；核实--quiet后第二次发现官方工具不自包装Tk，主动中止job `pwsh-d97b526f71de4178`，查相关PID均结束、JSON无diff，状态恢复原字节。中断日志保留，不计通过／失败。最终job `pwsh-88c34ce45e384794` 经gui_hidden＋官方共享令牌执行相同84登记目标，全阶段exit0。
- 官方真实分支测量1535条／191.395秒／既有aigc_lint skip2，85模块1335/2432，JSON由官方直接写入（日志 `logs/R3308_final_branch_measure_detail.log:133,333–334`）。下限文件原字节不动；相对旧JSON仅storage_maintenance93/171→95/175、diagnostic_capture1/8→2/8、file_index74/93→75/93三项变化，全部照实保留，不择优拼接。
- 最终相关定向 `run_selftests.py -k test_core desktop_startup_perf l1_bounded_growth_r3269 exit_maintenance force_quit test_storage test_timers stage_command_contract --serial`，230条／64.0秒／0红，既有bundled缺失skip1，startup15条全绿；日志 `logs/R3308_final_targeted_hidden.log:137–154`。官方默认smoke9/9、静态28/28、受影响架构25/25（分支下限、层级、共享状态、覆盖率、轮次）全绿；命令／exit／耗时详git-dir/round-local-evidence/R3308/final_followup.json。
- lead明确允许复用完整97文件唯fixture红和532架构唯旧快照红证据，最小补后只跑相关消费者／架构，不再次重跑97或full。最终生产相对完整97测量未变，仅test_core构造fixture初始化及官方基线JSON同步；无冻结期源码漂移，状态finally恢复HEAD原SHA94c8999d且git diff状态页为空。

## 提交与后续

正常 `R3308:` 独立修复提交，使用dev.py commit --tests生成真实目标证据与新增行凭据扫描；提交hash以本轮Git回执及lead交付汇总为准。只暂存本轮5生产文件、6测试文件、官方分支基线和本结果文件，日志／临时脚本／状态页／用户数据不暂存。未合入master，未push，未代用户删除或重装。

回滚：revert本轮提交即可恢复原项目打开时后台清扫；任务触发时机有意从打开项目改为窗口销毁后现有无窗维护，不改变清扫TTL／命名／链接／删除入口。本实例roots快照覆盖成功打开过的外部项目且去重；没有选择项目则不扩大清扫root。强退仍走storage、重复close不重复finish，销毁后维护不读Tk。

完整safe本轮未运行，不存在本树正式full receipt，不把dirty diagnostic或定向凭据冒称full验收。下一轮由lead新会话独立处理已知语音和motion；三个已知项修完冻结后再唯一完整safe。用户本人删除／重装未执行，不标任务书整体TASK_COMPLETE。
