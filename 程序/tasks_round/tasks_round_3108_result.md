# R3108 结构治理轮结果（A3 规则文本 v2）
<!-- round-evidence: {"commit_base": "845313e7", "credential_hits": 0, "evidence_sha256": "310b54d138317271", "exit": 0, "failed": 0, "passed": 0, "round": 3108, "tests": "docs-only"} -->

- 轮次类型：结构治理轮（任务书 A3；只改规则文本，不改代码）
- 三问：①类型＝结构治理轮；②测试未跑——纯文档轮，文档轮不跑 smoke／selftest，基线不适用；③欠账未变
- 交付：`runbook.md` §12「并行硬规则」上限 2→20；新增「高并发治理」段——lanes.json 登记、合并请求队列＋专职合并车道、role:gui 车道、租约心跳、MERGE_HEAD 超龄只提示不自动 abort，逐项标注对应落地轮（B1/B2/B3）；ahead>10 口径注明按源码提交计（B3 落地）
- 依据：任务书 v2 §2 D1/D5、§4 高并发规则草案；AGENTS.md 无车道上限条款（grep 核实），16KB 预算不触碰；CLAUDE.md／根 AGENTS.md 无引用需同步
- 提交：分支 `codex/gov-v2`，`dev.py commit` 后回填；合入 master 走正常合并轮
