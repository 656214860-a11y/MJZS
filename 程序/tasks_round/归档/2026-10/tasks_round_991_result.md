# R991 结果：全量凭据单权威

- 本轮继续认领 `reliability-loss-guard`，仅完成其中“凭据单权威”子项；WIP 守卫、行尾声明与 SG-02 至 SG-05 真机探针仍未收口，队列项保持 claimed。
- 三项测试基线：定向 `tests.test_selftests tests.architecture.test_round_baselines` 47/0；默认冒烟 8/8；架构门禁 279/0。干净树完整安全全量 3821/0、300.063 秒，receipt round 991。

## 交付与归一

- 删除受跟踪 `维护记录/测试分层基线.json` 中的 `last_full_safe_all_round` 与 `full_safe_verified_trees`；它只保留分层运行基线。
- `run_selftests.load_layer_document()` 先移除旧台账可能残留的同名字段，只从 `<common-dir>/full-safe-receipts.json` 派生；缺少或无效 receipts 时明确归零，绝不回退到跟踪台账。
- 新增遗留回归：即使台账伪装有 R868 / stale tree，而 common-dir 无 receipt，读取结果仍为 round 0、空树列表。
- `程序/AGENTS.md` 明定 receipts 是唯一权威，并标明验证树记录写入 common-dir。旧账面 R868（受跟踪基线残留）与曾出现的 R963（历史写树记录）均不参与欠账判定；本轮开始后欠账只读 common-dir receipts 当前真绿记录。

## 边界

- 未改动 `test_asset_gating`、`test_pet_settings`、用户项目、`程序/data`、`程序/private`、日志或运行数据；未新增 `.bak_*`，未作 renormalize。
- 提交：`eb83265 R991: centralize full-safe receipt authority`（本结果补记后将 amend；随后再次在最终内容树刷新 receipt）。
