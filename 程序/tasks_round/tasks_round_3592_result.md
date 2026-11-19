# R3592 结果文件 — 同步主干并稳定候选验收
<!-- round-evidence: {"commit_base": "d5fad8fe", "credential_hits": 0, "evidence_sha256": "4e43d24d69de045f", "exit": 0, "failed": 0, "passed": 111, "round": 3592, "tests": "run_selftests.py -k l1_lost_update l1_transport_requests model_pool"} -->

## 三问

1. 本轮为验收修复轮。候选第二次全量执行 9000 条，首跑两项失败已消失，新增红项为模型池文件行数上限及文件面板后台索引定时等待。
2. 已同步当前 master 的模型池顶层补丁方案，用它替代本分支的独立修复并保留确定性回归。文件面板、模型池、严格读写与 HTTPS 定向 205/205；行覆盖率 155 条、分支覆盖率 1781 条均无失败，模块体积与两类覆盖率门禁 12/12。
3. 保留模块行数上限和 GUI 行为断言。两处文件面板检查改为等待实际事件或待验行就绪，再验证收起后的丢弃和四类剧本文档的菜单行为。
