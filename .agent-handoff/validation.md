# 验证证据

## R1069

静态检查：11 份入口/接力文档链接有效、标记唯一、无模板占位符；diff --check 通过。
在 程序/ 执行 ../运行环境/Python/python.exe -B -m unittest tests.architecture.test_agents_md tests.test_round_claim：23/23，10.982 秒。
同一解释器执行 -B smoke_test.py：8/8，0 失败；默认模式未启动独立架构门禁。
仅文档改动；全量凭据轮次 1067 至本轮 1069 差 2，按既有周期不重复全量。
最终结果见 [R1069](../程序/tasks_round/tasks_round_1069_result.md)。

## 历史基线（不是当前树验收）

- R1068 主树全量：干净提交 1b36059d5e7c8036b50cbf8118d41b3d0aa2ed84，3994 条通过。
- 凭据 tree=8466f0109fe30c54a31d1ea8890e5b05843553d6，round=1067，at=2026-10-05T08:20:53。
- R1068 收尾：冒烟 8/8，test_agents_md + test_round_claim 23/23。
- R1068 隔离副本：批量删除定向 90/90、冒烟 8/8、架构 309/309；不是生产删除或逐候选独立证明。
