# R821 结果：资产计划发布器注入

## 完成项

- `asset_plan.publish_plan_bundle()` 与 `update_planned()` 不再自行取得底层发布函数，必须由 L3 注入 JSON、文本、字节与临时文件清理发布器；缺失时明确拒绝。
- `asset_resume.note_round()` 同样改为接收 L3 发布器。桌面、资产详情、批处理、引用导入、分镜采纳／定稿等调用链均经 `stage_execution_service` 编排，不改变资产格式、事务回滚或授权语义。
- 架构统一第 3 项已将 `asset_plan.py:publish_plan_bundle`、`asset_plan.py:update_planned`、`asset_resume.py:note_round` 三条记录标为 migrated，pending 由 11 降至 8；新增边界门禁拒绝 L2 直接导入发布函数，并确认 L3 组装网关。

## 实测

```text
python smoke_test.py
通过：8 项；失败：0 项

python smoke_test.py --architecture
214 条，0 红

python run_selftests.py -k asset_plan_publication_boundary asset_plan asset_resume workflow assets confirm_gates_json_boundary no_circular_import --safe
194 条用例，0 个文件有红
ALL TESTS PASSED
```

## 结论

本轮为结构治理轮，不改产品行为。距 R820 已完成的完整安全全量仅一轮，未触发“三轮一次”的全量算式门禁；`last_full_safe_all_round` 保持 R820。历史 `.bak_*` 与升级备份保持不动，回滚点由 Git 提交承担。
