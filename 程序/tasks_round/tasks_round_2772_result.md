# R2772 结果：SWE-2 T8.4——L0/L1 分支覆盖率棘轮下限
<!-- round-evidence: {"commit_base": "1a3afe20", "credential_hits": 0, "evidence_sha256": "4e55dd9287e79279", "exit": 0, "failed": 0, "passed": 26, "round": 2772, "tests": "run_selftests.py -k test_branch_coverage"} -->

1. 轮次类型：验证基线轮（质量门禁工具＋基线＋棘轮；口径见 docs/review/分支覆盖率棘轮_T8.md）。
2. 测试：工具单测 22/22 绿；新架构门禁 4/4 绿；邻近门禁 test_agents_md／test_coverage_baseline 绿；test_round_baselines 当轮 1 红＝test_round_number_continuous（合并轮手工提交欠账的在途编号态，正规 merge 自愈，非本轮引入）；基线测量 64 组用例 1159 条全绿（约 92s）。
3. 欠账：T8 余 8.2 黄金文件（另一车道在跑）；T9 归档/ADR/瘦身另一车道（.wt/t9，codex/wip-R2718）正在执行，本车道不重复；T10 另一车道。

## 交付

- `scripts/branch_coverage_report.py`：决策点双结果分支覆盖度量（if/loop/try/match），
  `sys.settrace` 零第三方依赖；证据按 (文件, co_qualname) 作用域归属；单行复合语句、
  表达式短路、try/finally、break 离开循环等行粒度不可分辨项不计入分母（已写入基线 metric 与 runbook §11）。
- `维护记录/分支覆盖率基线.json`：80 个 L0/L1 模块首次定向测量——决策点 1050/2157（48.7%）。
- `维护记录/分支覆盖率下限.json`：每模块棘轮下限＝实测百分比向下取整，只许人工上调。
- `tests/architecture/test_branch_coverage_floor.py`：结构自洽／模块集合与 _layers L0/L1 相等／
  下限不回退／工具可用性四件事；architecture.md 门禁清单同轮已登记。
- `tests/test_branch_coverage_report.py`：静态判定与证据逻辑 22 条单测（含嵌套作用域隔离、
  while-True、match 落空、多 handler try）。
- `runbook.md` §11 增列分支覆盖口径；`docs/review/分支覆盖率棘轮_T8.md` 完整报告。

## 口径提醒

定向测量（64 组登记用例），不是全量套件分支覆盖率；刷新基线须显式重跑工具，
目标用例失败时工具拒绝写基线（与行覆盖基线同一纪律）。
