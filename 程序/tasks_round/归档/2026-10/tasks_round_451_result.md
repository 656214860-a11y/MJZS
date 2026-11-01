# R451 验证/基线轮结果

## 改动

- `tests/test_row_targets.py` 将首帧删除验收从已废弃的 `frames/回收站` 改为权威的项目全局回收站，仍精确断言 SH001 被回收、SH002 未被移动。

## 验证

- 首次 `run_selftests.py --all --safe`：3,143 条中仅该旧路径断言失败。
- 修正后定向：17/17 通过。
- `smoke_test.py --architecture`：60/60 通过。
- `smoke_test.py`：8/8 通过。
- `python run_selftests.py --all --safe`：3,143/3,143 通过，799.5 秒，0 个文件有红。

## 边界

- 未改生产代码、用户数据或主界面“齿轮 → 设置”入口。
