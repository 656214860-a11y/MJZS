# R1875 结果：测试瘦身第 2 批 e（整理轮，A2 档收尾）

- 本轮类型：整理轮。只改测试，产品代码一行没动。
- 依据与做法同 R1869–R1874：先把差分测试独占的产品行补成普通行为测试，用 `Temp/audit/verify.py`（不进仓库）确认这些行被替代测试跑到，再删差分测试。

| 删掉的差分测试 | 独占行 | 替代测试 |
|---|---|---|
| test_asset_batch_window_equivalence | 94 | 新文件 `tests/test_asset_batch_window.py`（真 Desktop + `test_ui_edges.make_populated_project`，后台入口只记账）：ComfyUI 方式打开后类别勾选可切换、“保存设置”写入 `ui_settings.json`、“云模型设置”弹出 Comfy 账户窗且只显示脱敏密钥、开始与停止按钮可点；资产工作流方式打开原生控件与账号窗口；Skill 方式不显示批量生成与停止按钮 |
| test_script_structure_page_equivalence | 0 | 无独占行，直接删除（原先只因 asset_batch_window 差分测试借用它的 `_open_app` 而保留） |

- verify.py：asset_batch_window 94 行 0 漏。
- 一并删除 `tests/window_diff_support.py`、`tests/page_diff_support.py`：这两个是差分测试专用的对照辅助模块，差分测试删完后仓库里已没有任何引用。
- skip 台账：删去 `test_script_structure_page_equivalence` 的 1 条登记；`test_asset_batch_window_equivalence` 那条改指新用例 `tests/test_asset_batch_window.py` 的 `AssetBatchWindowTests.setUp`（同样是 `PLATFORM_TKINTER` 跳过位）。
- 断言未动：现有用例的断言一条没改，只新增用例。
- 轮次号：本轮领到 1875。
- 验证：test_asset_batch_window 3/3 在隐藏桌面通过。冒烟通过（隐藏桌面）。架构门禁 394 条只红 `test_round_baselines.test_round_number_continuous`，原因同前几轮：`project_status.md` 按约定只在 master 上改，合入时补齐。
- 进度：A2 档 17 个全部做完，`tests/` 下已没有 `*_equivalence.py`。下一步跑全量 `--all --safe`。
