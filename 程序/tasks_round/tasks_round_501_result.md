# R501 修复轮（含全量基线验证）：默认创意示例字段契约

## 结论

- 已修复发行包内置默认创意示例与 `IDEA_FIELDS` 不一致造成的 UI 边界回归。
- 安全全量回归 3,230/3,230 通过，零失败文件。

## 变更与边界

- `默认创意示例.md` 补齐首个必填字段 `故事集数: 100 集`；示例字段顺序现与编辑器字段表一致。
- 修复仅影响软件随附示例文本，不读取、写入或迁移用户项目数据。
- 原失败为 `UiEdgeTests.test_the_brief_example_never_lands_in_the_project`：示例缺失字段时被误判为用户输入无效；同一测试同时保证示例不会被写入项目。

## 验证

- 精确回归：`tests.test_ui_edges.UiEdgeTests.test_the_brief_example_never_lands_in_the_project`，1/1 通过（1.190 秒）。
- 完整安全回归：`python run_selftests.py --all --safe`，3,230/3,230 通过，855.9 秒，0 个失败文件；增量台账已刷新。
- 默认冒烟：`python smoke_test.py`，8/8 通过。

## 后续

- 架构门禁数量未变，保持 90/90 基线；继续按照 R461 未完成优化清单选择可独立验证的条目。
