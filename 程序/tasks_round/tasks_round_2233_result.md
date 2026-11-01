# R2233 结果：模型池配置覆盖前留快照（U10 后半，功能轮）

## 三问
- 轮次类型：功能轮。用户「现在做」U10 的模型池切换快照。
- 测试：新增 `tests/test_model_pool_snapshot.py` 4 条全过；`run_selftests.py -k model_pool pet_ui_settings skill_panel_support` ALL PASSED。未跑冒烟、架构、全量。改前红未另跑：`SNAPSHOT_KEEP` 与快照行为改前不存在。
- `project_status.md` 欠账：无变化。

## 改动
- `model_pool.store`（模型池写盘唯一入口，pet_ui_settings 三处与 skill_panel_support 都经它）覆盖前把旧 `配置/宠物/配置.json` 复制到 `程序/data/config_snapshots/pool_<时间>_<毫秒>.json`，只留最近 20 份；快照失败只记日志，不拦保存。
- 队列 U10 勾选。

## 注意
- 快照含旧配置原文（密钥另存加密库，配置里不含密钥，`data/` 已被 Git 忽略）。
