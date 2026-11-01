# Round 227 结果：桌面分镜后台服务直连

## 改动文件

- `desktop.py`
- `tests/test_pet_ui.py`

## 改动摘要

桌面后台链直接调用分镜目录与选择服务，`storyboard_files` 仅保留页面显示入口。测试 mock 目标随契约迁移，断言保持不变。

## 验证结果

- 结构剧本定点回归与分层校验：3/3 通过。
- 默认 `smoke_test.py`：8/8 通过。
