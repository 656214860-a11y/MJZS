# Round 216 结果：自动采用分镜心跳职责拆分

## 改动文件

- `desktop.py`

## 改动摘要

将 `Desktop._tick_once()` 中自动采用分镜的短周期检查收拢为 `_tick_auto_adopt()`；调用位置、5 秒节流和错误提示不变。

## 验证结果

- `py_compile desktop.py`：通过。
- 自动采用 UI 回归：1/1 通过。
- 默认 `smoke_test.py`：8/8 通过。
