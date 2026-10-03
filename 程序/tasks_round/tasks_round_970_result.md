# R970 工作树台账机械化与孤儿抢救

- 类型：结构治理轮（执行），来源：用户任务书 B，第 1—3 项。只改协作基础设施，不改生产行为。
- 抢救已先行独立完成：2032378dbae24023d03faa0e5f4afce05ddc1485 从 detached 固定到 codex/R884-orphan-783b 并切换 783b 树；前后 HEAD 不变，脏内容保留。旧 839752c 引用未动。其他树已有包含分支，没有新增未保护孤儿。详细前后凭据见维护记录/工作树精简台账.md。
- 三个基线：默认冒烟 **8/8**；架构 **279/279**（93.139 秒）；最近已验证完整安全全量为 R968 **3808 条/0 红/385.210 秒**，内容树变化后不能冒用，该轮最终全量以 common-dir/full-safe-receipts.json 的 round=970 实测记录为准。
- 定向：`run_selftests.py -k worktree_ledger round_claim selftests queue` **66 条/0 红/17.7 秒**；新旧两个基础设施模块直接 unittest **18/18**。新增 8 条断言用例，不删除或弱化旧断言。

## 现场机械守卫

真实临时 Git 仓库创建两个 worktree，一个 detached、一个有分支且 ahead=0；分别断言 BLOCK / RECYCLE，独有分支提交 KEEP、孤儿 BLOCK，48 小时边界、活跃/过期租约、脏树、残差管理项和链接不跟随。
CLI 测试复制脚本到临时 detached 树并在子目录启动 `next`：返回非零（2），stderr 含 `detached HEAD` 与 `git switch -c codex/R1-main`；共享计数器不存在。执行该 switch 命令后重试，返回 0，领取 1。
台账 CLI 实际输出 JSON/表格和 --plan，运行后目录仍在、Git status 不变；不自动执行 remove/prune。

## 边界及残差

- R859 e370 内层仍为空目录；d2cc 只剩空外层；B1 已不存在；R820 留有指向主树运行环境的 junction，需人工处理链接本身，不能递归删目标；c924 内层为空。未执行任何删除，两个历史 patch 保留为证据。
- 活跃队列租约缺少树关联字段时保守 KEEP，并以 JSON unmapped 标示；不能凭缺字段假定无活动。
- AGENTS 第 27 条按 writing-for-agents 技能把分支存活规则和领取动作放在同处；behind>20 须 rebase 或归档、ahead=0 当日回收，但删除仍需用户逐条确认。
- 未改生产 .py、test_asset_gating、test_pet_settings、配置/data/private、日志或用户项目；无备份文件，无全量暂存。

## 最终凭据及提交

为满足干净树且 HEAD 不变的全量门禁，先以 `R970-FAIL: checkpoint` 保存候选；匹配内容树全量真绿后，才以不改内容树的 `R970: close` 成功标记收口。未达到前均是 [TASK_FAILED]，不可凭这份候选报告推定完成。
全量命令 `run_selftests.py --all --safe --force`；忽略的输出 `.r970_full.out/.err`，机器凭据 common-dir/full-safe-receipts.json 的 round=970。要求起止 HEAD 相同，主树干净、0 红、无 GUI_DEFERRED。
提交 hash 的无自引用权威取法：`git log -1 --format=%H --grep='^R970-FAIL: checkpoint'` 定位实现；`git log -1 --format=%H --grep='^R970: close'` 定位验收。抢救引用不在此代码提交内；起始基准 hash 为 848ee84f0967104980bae46cdbfca7a98942d28d。
只有成功标记存在且 round=970 实测凭据匹配 `HEAD:程序` 时为 [TASK_COMPLETE]。任何失败保留 FAIL，不隐藏欠账。最终数值由真实工具输出及收尾答复给出。
