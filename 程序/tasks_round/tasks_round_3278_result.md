# R3278：SKILL预算第三轮——真实分项与完整API请求终检
<!-- round-evidence: {"commit_base": "cd0302b2", "credential_hits": 0, "evidence_sha256": "153b2cb8af6a79fe", "exit": 0, "failed": 0, "passed": 40, "round": 3278, "tests": "run_selftests.py -k writing_context_budget_guard writing_api_output_budget skill_context_budget_prestage"} -->

## 三问

- 类型：§3.2 修复轮。R3274（cd0302b2）结束后自动启动第三轮新子会话 round3-finalguard，中央实际领号R3278。
- 测试：新guard14条先红后绿14/14；最终关联集122/122、0跳过、117.1秒，exit0（green-final.log）；公共六技能冻结探针通过，资源补充40/40，默认冒烟9/9。架构后台运行与后续master同步的临时冲突窗口重叠，读取过冲突标记而报AST错误，不能作为稳定候选的验收结果，最终静止候选须重新完整运行；本轮未跑安全全量。
- 欠账：第四轮CLI/直连双路线受控E2E、完整安全全量、最终master合并与任务完成文件仍未完成。

## 本轮范围

第三轮目标：冻结字符超限报错使用真实 skills 分项；完整 API 请求每轮复用同次安全窗口预算，显式窗口优先/前缀回退/未知拒发，覆盖system、历史、工具与实际输出预留；同步REQ-S01-31等文档。写入范围由子会话负责 writing_api、freeze末端分项和相关测试/需求文档，父代理不并发写相同文件。

## 公共技能组合复核追加缺口

父代理以固定pin的六份公共技能包、合成制作锁、直接注入128K模型记录复核；没有读取用户项目、生产模型池、私有配置或密钥，没有实发网络。发现第二轮未覆盖的一处资源提示重复：README各语种引用相同LICENSE/NOTICE，预留按path一份，实际每处重复发送，导致后续README_ZH提示无预算而拒发。原始失败见common-dir `task-logs/R3278-round3/public-six-freeze.log`。

最小修复仅针对有pending预算的冻结：同一资源路径hint发送一次，闭包仍逐项记录resource；后续引用不能再次预留已经发送资源，防幽灵预算。不改变无预算CLI旧行为，不改资源访问权限。

可重复回归：在临时目录构建两技能共享LICENSE，断言一hint/两closure；另验证后续子引用不重预留已发送资源。红17条中1红（重复2次），修后prestage18+deep11+closure11共40/40、0跳过，原始日志 `resource-red.log` / `resource-green.log`。

修后公共六技能探针 `public-six-green.log`：loaded=6、chars=99285、estimated_tokens=93215、inline_budget=93440、skipped=4、degraded=True，逐一断言六份parse正文完整包含。此证据仅代表冻结阶段；不得据此宣称实际网络请求/全部引用/完整技能已执行。

## 验证与后续

环境保持PYTHONUTF8=1、PYTHONIOENCODING=utf-8、进程PATH加入D:/Tools/ffmpeg/bin；随附Python，runner隐藏桌面规则不变。

最终第三轮红绿、默认冒烟和提交结果待提交前补齐。Git `R3278:` 为提交回执；下一轮将启动新子会话验证原始命令CLI终点及独立API桩传输，且修迁包造成的engine路径parent误用。

接续检查点：第三轮初次新测试12/12绿；指定宽集116条中6红集中在旧输出额度夹具：fake m无窗口，以及32768输出+约93K冻结+6400余量确实越128K。子会话仅补合成fixture的显式窗口（其中200K用于隔离既有输出额度断言），不降低实际输出或弱化业务断言，正在同组复测。独立审查追加 model override 绕过窗口绑定 P1：chosen大窗却_call(model=小窗/未知)真实payload会换模型；必须拒 model_snapshot_mismatch（chat/stream/raw与RPM均0），空model固定chosen，已交第三轮先红后绿。父代理负责resource独占文件并已40/40；其余writing_api+workflow_settings+S01+guard测试由第三轮独占。新master056f882f已合UI，本树尚未同步；第三轮提交后合最新master，保存L1 wait_for_rpm credential和S01双方内容。最终测试PATH加入D:/Tools/ffmpeg/bin；主树无全量锁，上一全量GBK/缺媒体工具失败不可复用。第四轮子会话只能在第三轮结束后启动，任务是CLI与HTTP两条合成E2E，修desktop_shared_send165 parent→parents[1]域包路径，不能把slash CLI宣称HTTP。目标goal仍active，未完成不得结束。
