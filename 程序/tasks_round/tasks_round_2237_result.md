# R2237 结果：U1／U4／U8／U11／U12（功能轮）

## 三问
- 轮次类型：功能轮。用户「自动按顺序全部做完」的 P2 部分。
- 测试：新增 `test_release_snapshot`（3）、`test_release_watch`（5）全过；`run_selftests.py -k artifact_schema artifact_lineage` ALL PASSED。未跑冒烟、架构、全量。新测试针对的脚本改前不存在。
- `project_status.md` 欠账：无变化。

## 改动
- U1：核实自动触发点是 Git `post-commit` 钩子（欠账接近门禁线时后台补跑安全全量），登记进队列，不引入托管 CI。
- U4：`scripts/release_snapshot.py --snapshot`，按分发清单构建并校验，放开发目录同级 `<目录名>_升级快照`，只留最近 3 份。
- U8：同脚本 `--drill <快照>`，校验摘要＋副本解释器导入入口模块。
- U11：`artifact_schema.REGISTRY` 登记 `artifact_lineage`（`version` 1，`entries`），清单文档同步；其余产物仍待核查。
- U12：`scripts/release_watch.py`，24 小时窗口、5 次样本、连续 3 次失败告警；给 `--baseline` 才判回滚。
- 发布检查单 §2、§3 同步。

## 未做／风险
- 快照与演练只在模拟构建下测过，**未在真实安装目录上完整跑过**（工作树里没有 `运行环境`）。
- 失败占比阈值仍待用户裁定。编码失败率、累计金额对比预算未做。
- U11 其余产物未核实。
