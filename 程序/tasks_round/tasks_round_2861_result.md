# R2861 合并轮结果
<!-- round-evidence: {"commit_base": "a7ecd950", "credential_hits": 0, "evidence_sha256": "0e1d2845035c4630", "exit": 0, "failed": 0, "passed": 0, "round": 2861, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/wip-R2851` 到 master（手工解算冲突后合并）。
- 说明：codex/wip-R2851（T10 批次2：platform_tools 迁 contract/＋棘轮口径）合入 master，四文件冲突手工解算、覆盖率按合并树重测
- 冲突解算：desktop_script_pages.py 取 master 新结构；writing_quality.py 并集导入（file_cache 留顶层、service_contract 走 contract/）；runbook.md 与覆盖率基线.json 取分支口径后按合并树重测覆盖率（64/410，97 用例全过）。断言未动。
- 测试：local_ci.py exit 三档全绿（冒烟/静态/架构）；覆盖率重测 97 例 OK。未跑全量。
- 欠账：未新增；分支遗留 test_round_number_continuous 红在合并树上由领号后状态页抬头修复。
