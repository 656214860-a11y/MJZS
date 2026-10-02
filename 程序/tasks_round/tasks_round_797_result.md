# R797 结果｜覆盖率审计契约轮

日期：2026-10-02

## 完成内容

- 审计 21、24、26 均以冻结谓词实际命中与台账 `pending` 双向集合相等校验；并拒绝跨审计段重复的 `(file:point)`。
- 清理三条死账归属：`api_endpoints.py:47` 仅归网络审计 26；`model_pool.py:538` 与 `model_pool.py:566` 保留记录并标为模型路由网络白名单 `exempt`。审计 21 的实际点位也修正为 `asset_thumbs.py:516`。
- 审计 24 收窄为插件／阶段处理器注册路径；原 27 条固定字面量普通模块延迟加载均保留为具理由的 `exempt`，pending 从 27 降至 0。
- 判据文档、扫描器与台账的真候选／pending 数字已一致：21=6、24=0、26=1。
- 新增每三轮必须有一次 `--all --safe` 通过记录的算式门禁；本轮全量通过后将 `last_full_safe_all_round` 更新为 797。

## 验证

- `smoke_test.py`：8/8，0 失败。
- `run_selftests.py -k coverage_audit_ratchet round_baselines agents_md --safe`：18 条，0 红。
- `smoke_test.py --architecture`：166/166，0 失败（33.408 秒）。
- `run_selftests.py --all --safe`：3,587 条，0 个文件有红（955.4 秒）。

## 边界

- 未修改任何产品 `.py`，未迁移 service；架构路线图的 66/24 保持不动。
- 未删除台账历史记录，未扩大白名单来消除 pending。
