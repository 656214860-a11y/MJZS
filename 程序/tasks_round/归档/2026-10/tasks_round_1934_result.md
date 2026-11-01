# R1934 结果：test_asset_gating 的 ffmpeg 路径改走统一入口

轮次类型：修复轮（测试资产整改）。分支 claude/affectionate-goldstine-5e7003。

## 改动
- `tests/test_asset_gating.py`：`FFMPEG`／`FFPROBE` 由写死的 `D:/Tools/ffmpeg/bin/...` 改为 `integrations.tool_path(名称, 旧路径)`，本机 PATH 有就用，没有退回旧路径。两个值只写进项目配置，测试不调用，故无需 skip。断言未动。

## 阶段 1 其余项的结论
- 宽松断言抽样：`assertTrue(len(..))`／`assertGreater(len(..),0)` 仅 2 处，均为防循环断言空转的合理守卫，未改。其他形态未逐个核查。
- `Desktop(root=PROGRAM)`：13 个文件 101 处，无证据表明多数读本机账号态，未做全量隔离；发现随登录态变红的用例再逐个处理（参照 R1920 的 GATE_ENFORCED mock）。

## 验证
- `run_selftests.py -k asset_gating`（经 gui_hidden）：ALL TESTS PASSED。
- 未运行：`smoke_test.py`、`--architecture`、`--all --safe`。
