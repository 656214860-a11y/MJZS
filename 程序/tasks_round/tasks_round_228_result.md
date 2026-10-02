# Round 228 结果：桌面资产状态服务直连

## 改动文件

- `desktop.py`
- `tests/test_ui_edges.py`

## 改动摘要

桌面层的资产就绪、异常资产与原始输出清理查询直接依赖 L2 `asset_batch_state_service`。测试 mock 目标随契约迁移，断言保持不变。

## 验证结果

- 资产与分层校验：63/63 通过。
- UI 定点回归：1/1 通过。
- 默认 `smoke_test.py`：8/8 通过。
