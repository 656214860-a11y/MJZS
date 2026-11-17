# R3218：接续成熟依赖任务，强制新建工作分支命名
<!-- round-evidence: {"commit_base": "a2281abc", "credential_hits": 0, "evidence_sha256": "4e466c863d08daff", "exit": 0, "failed": 0, "passed": 29, "round": 3218, "tests": "run_selftests.py -k round_claim dev_entry agent_doc_budget"} -->

## 三问

1. 类型：结构治理轮；用户指定命名规范子场景，生产工具改动限 round_claim.py，不包含 HTTP 迁移。
2. 测试：默认冒烟实际 9/9，隐藏桌面自探针通过；定向 round_claim/dev_entry/agent_doc_budget 29/29；HTTP 与依赖基线 14/14。完整架构 486 条，3 failures + 1 error（482 条无失败），改前 a2281abc 独立检出复跑同 4 项均复现。全量未运行，本轮不构成发布验收。
3. 欠账：没有把架构红灯标绿。新增命名行为有坏/好样本和红绿证据；既有架构问题保留待合入/发布前处理。

## 接续事实

- 主干基线 d29e1e83；当前功能分支 codex/whitelist-framework。
- 并发车道已完成 R3215（504f53bf），本分支 cherry-pick 为 a2281abc。旧 R3199 政策不重做，不冒用旧编号提交。
- stash push 实测 No local changes to save，没有应用旧 stash。
- 中央 round_claim.py next 已领取 R3218。没有对应中央队列 ID，不认领别人的任务。
- 本轮新增正式《引入成熟框架与工作树规范任务书》，撤销旧“75%”“节省98%”等未经测量的结论。HTTP、可分发副本和发布全量均未完成。

## 改动

- round_claim.py：新建分支名匹配 codex/[a-z0-9]+(?:-[a-z0-9]+)*；next --branch 经 dev.py claim 原入口透传，非法名在切分支/领号/登记前返回2；新自动默认 codex/wip-r<N>；已有codex（含legacy wip-R号）不改名；旧非codex脏树自动停泊后刷新轮次归属和lane登记。
- tests/test_round_claim.py：加入真实入口参数转发、新名坏/好样本、legacy保留、默认命名和最终归属测试。原断言未弱化。
- AGENTS §34a 与 runbook §12：短规则＋细则；明确手工 Git 不调用 claim，agent 必须使用合规名称，不追溯重命名现有车道。

## 红绿与验证

新增4方法最初14 failures；默认停泊归属补断言再红（old-task != codex/wip-r1）；修正后 child unittest round_claim/dev_entry 24条通过，父以正式 runner 运行 round_claim/dev_entry/agent_doc_budget 29条通过。

正式命令（工作目录本树 程序；PYTHONUTF8=1/PYTHONIOENCODING=utf-8；随附主树解释器）：

- run_selftests.py -k round_claim dev_entry agent_doc_budget：29条，0红，21.0秒。
- run_selftests.py -k http_client dependency_whitelist：14条，0红，0.7秒。
- smoke_test.py：9/9，隐藏桌面可用。
- smoke_test.py --architecture：486条，179.023秒，3 failures/1 error。

曾误传 smoke_test.py --probe，入口不支持，返回1；改用默认 smoke 后其内部 scripts/gui_hidden.py --probe 自动成功。未修改运行器来隐藏失败。

完整架构失败集合：

1. test_agents_md.test_performance_history_is_declared_as_historical_only：维护记录/基准历史.json 不存在。
2. test_round_baselines.test_round_number_continuous：状态头与已收录结果不连续。
3. test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references：基线技能引用不匹配。
4. test_unification_ratchet.test_bare_json_load_debt_is_a_nonincreasing_subset：既有裸JSON扫描登记不匹配。

在 D:/漫剧制作助手/.agents/worktrees/verify-whitelist-baseline 的未修改 a2281abc 上用 -m unittest 点名以上四项，4.670秒，同样 EFFF，证明确为本轮命名改动前已存在。未通过扩大白名单/删断言抹平。测试后该临时检出可经验证干净再回收。

## 后续与提交

HTTP 实际签名 method-first，默认仍 urllib；需按任务书下一轮真正迁移，不能以随包 requests 安装完成代替。分发检查发现普通环境可见用户site，须 -I 验证；共享运行环境不再安装新包，使用隔离构建副本。

提交：使用 scripts/dev.py commit 标准入口，成功hash由 git log 与 evidence/R3218.json 核验；结果文件不预填成功。主干状态页本分支不写，合入车道维护。任务书整体仍执行中，无任务完成声明。
