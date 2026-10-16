# 当前验证索引

## 最近正式全量
R1605：HEAD e59e5136e2992ae18832d05083ab56bb75416242，5346项、410个测试文件、0红，测试615.7秒/执行器631秒。common-dir/full-safe-receipts.json 为权威。

## R1607（O9）
- 定向：tests/test_seedream_direct.py 22项通过（新增4项溯源断言，含记录不含 api_key）。
- 架构门禁：`python -B smoke_test.py --architecture` 345项、165.697秒、OK。日志 程序/outputs/r1607-architecture.log。
- 默认冒烟：8项通过。日志 程序/outputs/r1607-smoke.log。
- 本轮未跑全量，不冒称同树全量。

## R1606（O8）
- 合入 a013e75；架构345项、164.456秒、OK；默认冒烟8项通过。日志 程序/outputs/r1606-architecture-fixed.log、r1606-smoke.log。
- 旧工作树 .wt/architecture-assessment 的 2 项失败（轮次号、注释快照行号）已在本轮修复并合入。

## 未执行
8项真实验收（质量、真实恢复、商用审核、实际成本、真实预算、人工替代、实机导出、新手体验）仍按用户延期处理，不由模拟或全量测试替代。历史索引见 [归档](archive.md)。
