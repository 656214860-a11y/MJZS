# R743 契约轮｜22/24/25/26 覆盖率审计入账

本轮冻结 21、22、24、25、26 的报告模式判据与金丝雀；扫描范围和白名单硬编码于 `tests/architecture/test_coverage_audit_ratchet.py`，不从台账读取。22、25 沿既有门禁且本轮无真实命中，未建立零基数段落；24 入账 27 条裸动态导入 pending，26 入账 `api_endpoints.py:47` 1 条 pending。新增断言保证 24／26 的真实命中均已入账。

验证：默认冒烟 8/8；聚焦 `unification_ratchet` 2 条／0 红。R743−last_full_safe_all_round(R741)=2＜3，故按规则不跑完整安全全量。架构冒烟命令已执行但未保留可用摘要，不能作为独立通过凭据。
