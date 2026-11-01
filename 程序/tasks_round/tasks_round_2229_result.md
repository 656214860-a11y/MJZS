# R2229 结果：U2／U3／U10 小机制（功能轮）

## 三问
- 轮次类型：功能轮。用户「继续 U2/U3/U10」。
- 测试：`unittest tests.test_release_bindings tests.test_distribution_build` 16 条全过（本轮新增 4 条；新测试依赖的 `RELEASE_STEPS`／`_git_binding`／`snapshot` 改前不存在，改前必红，未另跑旧版对照）。未跑冒烟、全量。
- `project_status.md` 欠账：无变化（分支不写状态页）。

## 改动
- U2：`scripts/local_ci.py` 新增 `release` 模式 = `exit` 全部步骤 + `distribution_selfcheck.py`；`exit` 不变。发布检查单第 4 步改指向它。
- U3：`distribution_build.build` 的 `分发清单.json` 新增 `commit`（HEAD 完整哈希）与 `round`（HEAD 标题 `R<N>:`），读不到留空不阻断。
- U10（一半）：`migrate_workflow_presets --apply` 回写前把各项目 `skill_config.json` 复制到 `程序/data/config_snapshots/`。**模型池切换的快照未做**，队列项保持未勾。
- 文档：发布检查单 §1、§4，优化待办队列 U2／U3 勾选、U10 注明。

## 未做／已知
- `test_distribution_selfcheck` 在含未跟踪目录的工作树里的存量红未处理，故 `release` 在脏树上可能红。
- 快照目录无清理策略。
