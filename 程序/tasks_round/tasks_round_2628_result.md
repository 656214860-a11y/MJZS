# R2628 结果：SWE-2 T8.1——L0 契约层变异测试抽样工具＋弱断言补强
<!-- round-evidence: {"commit_base": "2da8074e", "credential_hits": 0, "evidence_sha256": "48350e84b1aecd4e", "exit": 0, "failed": 0, "passed": 44, "round": 2628, "tests": "run_selftests.py -k mutation_sample shot_batches artifact_schema"} -->

1. 轮次类型：验证基线轮（开发期工具＋测试补强；不硬门禁、不进发布包）。
2. 测试：定向 `mutation_sample/shot_batches/artifact_schema` 全绿；冒烟 8/8；
   coverage 门禁 11/11。全量欠账仍由 master 既有红项主导，本轮未触发全量门槛。
3. 欠账：T8 剩 8.2 黄金文件／8.3 趋势／8.4 覆盖率下限；T9、T10 未动。

## 交付

- `scripts/mutation_sample.py`：8 个机械变异位点（artifact_schema×3、shot_batches×5），
  子进程 sys.modules 注入变异体后跑对应测试文件；`--json` 出机读结果。
- `docs/review/变异测试抽样_T8.md`：首跑 6 杀/2 存活 → 补 2 条测试后 8 杀/0 存活。
- `tests/test_shot_batches.py` 新增 2 条（杀存活变异体）：批次秒数恰等于上限仍属本批；
  normalize 非 dict 输入回默认值。
- `tests/test_mutation_sample.py`：位点表防腐（每个位点源内唯一命中＋变异产物校验）。

## 同轮不并说明

- 我方 R2620/R2625（wip-R2625）与他车道 T7.2/R2626 重复，按防重复规则不合并，分支留作备选。
