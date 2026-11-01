# Round 226 结果：桌面无人值守资产服务直连

## 改动文件

- `desktop.py`
- `tests/test_ui_edges.py`

## 改动摘要

桌面无人值守资产链直接调用 L2 `asset_batch_service`，不再经由资产页面模块。测试 mock 目标随契约迁移，断言保持不变。

## 验证结果

- 资产自动批处理与分层校验：7/7 通过。
- UI 定点回归：1/1 通过。
- 默认 `smoke_test.py`：8/8 通过。
