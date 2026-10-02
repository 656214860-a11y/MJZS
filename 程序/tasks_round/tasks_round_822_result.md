# R822 结果：设置、角色日志与旧目录归位发布器注入

## 完成项

- `desktop_settings_service.publish_desktop_settings()` 必须接收 L3 JSON 发布器；桌面四个既有设置写入点均改经 `stage_execution_service.publish_desktop_preferences()`。
- `hollmwood_roles._write_log()` 不再直接导入文本写入函数；L3 `writing_api.hollmwood_gateway()` 向四角色运行链注入日志发布器，空正文重试、错误诊断与正常角色日志的格式不变。
- `legacy_adoption_service.record_legacy_adoption()` 的目录创建和 JSON 发布由 L3 `legacy_adoption_gateway()` 注入，桌面继续显示原有的审计失败提示。
- 架构统一第 3 项的三条记录均已迁移，pending 由 8 降至 5；新增 HOLLMWOOD 日志边界门禁。

## 实测

```text
python smoke_test.py
通过：8 项；失败：0 项

python smoke_test.py --architecture
215 条，0 红

python run_selftests.py -k desktop_settings_service legacy_adoption_service hollmwood_roles writing_api core desktop_settings_boundary legacy_adoption_boundary --safe
168 条用例，0 个文件有红
ALL TESTS PASSED

python -m unittest tests.architecture.test_hollmwood_log_publication_boundary tests.architecture.test_no_circular_import tests.architecture.test_layers
6 条，0 红
```

## 结论

本轮只收紧发布边界，不改变设置值、日志内容、目录位置或失败提示。距 R820 完整安全全量仅两轮，未触发三轮全量算式门禁，`last_full_safe_all_round` 保持 R820。
