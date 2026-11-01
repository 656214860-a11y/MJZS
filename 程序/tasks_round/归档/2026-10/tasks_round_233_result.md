# Round 233 结果：三虎结构剧本同步服务直连

## 改动文件

- `pet_ui.py`
- `tests/test_pet_ui.py`

## 改动摘要

三虎自动链直接调用 `storyboard_selection.sync_structured_script()`。测试 mock 目标随服务契约迁移，断言保持不变。

## 验证结果

- 桌面三虎接缝与分层校验：20/20 通过。
- 默认 `smoke_test.py`：8/8 通过。
