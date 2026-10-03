# R840 结果：覆盖率审计 20 缓存失效

- `local_video_settings_service` 的工作流原子替换、配置发布及两条回滚路径均通过 L3 网关注入并调用 `file_cache.published`；不改变配置内容、文件位置或失败语义。
- 新增冻结扫描：L3 JSON `replace_file` 后必须在同函数调用缓存失效；金丝雀验证漏发事件会被拒绝。
- 审计 20 的判据文档、台账 pending 与生产扫描同为 0；`stage_execution_service` 三条既有内存 JSON 校验仅因新增注入行发生位置漂移，台账已同步，未改变其豁免结论。

## 验证

- `run_selftests.py -k 'unification_ratchet asset_gating local_video_settings_service coverage_audit_ratchet' --safe`：28 条／0 红。
- `run_selftests.py --all --safe`：3667 条／0 红（965.1 秒）；按三轮全量门禁，`last_full_safe_all_round` 已推进至 R840。
- `python smoke_test.py`：8/8 通过；`python smoke_test.py --architecture`：222/222 通过（85.260 秒）。
