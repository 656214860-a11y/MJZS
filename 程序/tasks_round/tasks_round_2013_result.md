# R2013 launch_comfy 测试 mock 同步（测试同步轮）

来源：`HANDOFF_20261024_J6.md` 队列第 3 项。日期：2026-10-25。基线：`codex/wip-R2012` @ 458edf97。

轮次类型：测试同步轮（只改测试 mock，生产代码零改动）。三套基线：默认冒烟 8/8；架构门禁未重跑（只动一个用例文件，无新模块／登记变化）；覆盖率基线不变。债务：`--all --safe` 欠账 +1。

## 改动

- `tests/test_desktop_settings_callers.py`：R1995 起 `launch_comfy` 经注入的 `self.media_page_services.comfy_executable`／`file_dialog` 取程序路径与选择框，测试仍给模块级 `comfy_executable`／`FileDialog` 打桩，`Mock` 版 app 的这两项返回的是 Mock（非 None），走不到选择框分支，所以 `launch_comfy` 三条用例红。把两处桩改挂到 `app.media_page_services.comfy_executable`／`file_dialog`（共 2 处 × 2 行），形状不变（`dialog.return_value.open_file`）。

## 验证（本轮实测，经 gui_hidden）

- `-k desktop_settings_callers`：3 条全绿（此前 3 条红）。
- `-k comfy media_page`：40 条全绿。
- 默认 `smoke_test.py`：8 项通过。未跑 `--all --safe`，欠账 +1。
- **断言未动**：只改 mock 的挂载位置；全部 `assert*` 行原样。

## 回滚

还原 `tests/test_desktop_settings_callers.py`。
