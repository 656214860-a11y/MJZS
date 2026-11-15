# R2549 结果
<!-- round-evidence: {"commit_base": "4c0a54dd", "credential_hits": 0, "evidence_sha256": "7dda55b7cc5483c8", "exit": 0, "failed": 0, "passed": 28, "round": 2549, "tests": "run_selftests.py -k test_move_guard rule_guard_map commit_round agent_doc_budget"} -->

1. 轮次类型：功能轮（工程闸门清单后续：规则 26 登记守卫、规则 16 补守卫）。
2. 测试：定向 `test_test_move_guard`、`test_rule_guard_map`、`test_commit_round`、`test_agent_doc_budget` 全绿；证据文件 `tasks_round/evidence/R2549.json`。断言未动。
3. 欠账：无新增；暂无守卫的规则从 5 条降到 3 条（25、30a、32）。

## 改动

- 规则 26：登记守卫 `test_rule_guard_map.py`（新增 §2.3 规则不登记守卫即红），`UNGUARDED_CEILING` 收紧为 {25, 30a, 32}。
- 规则 16：`scripts/test_move_audit.py` 核对暂存区或提交——测试文件新增／删除，或新旧内容除 import 行外有差异都不通过；`dev.py commit` 在提交信息含「测试搬家」时自动核对；`tests/architecture/test_test_move_guard.py` 用临时仓库覆盖纯移动、只改 import、改断言、增删测试、非测试文件和历史提交。
- 历史上没有标题含「测试搬家」的提交，实时扫描目前为空集，守卫从下一次搬家轮开始起作用。
- 判定口径：只有提交首行以「R<n>: 测试搬家」开头才算搬家轮（正文提到不算）；测试文件判定排除 scripts／skills／维护记录 下的 test_ 前缀辅助脚本。首次提交曾被自己的守卫拒绝（提交说明里写了「补测试搬家守卫」），据此把口径从“含关键词”收紧为“首行开头”。
