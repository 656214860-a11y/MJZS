# R2126 结果：模型管理 Provider 去重、「保存这条」左移、「关闭」改「保存并关闭」（功能轮）

## 需求（用户原话）
模型管理 → Provider 里 anthropic 重复；按钮「保存这条」左移；按钮「关闭」功能更新为「保存并关闭」。

## 原因
Provider 下拉 = 内建项（`model_pool.PROVIDERS`，含小写 `anthropic`）＋已存模型的厂商名。本机 CLI／桌面记录的厂商名由 `model_pool.provider_name()` 给出 `Anthropic`，原去重按大小写敏感比较，于是两条并列。

## 改动（`pet_models_ui.py`）
- `_ModelManager.load_rows`：Provider 下拉按 `casefold` 去重，保留内建项；已存厂商名之间也按大小写去重。选中旧记录时原本就按 `PROVIDER_LABELS.get(vendor.casefold())` 回填为内建项，显示一致。
- 底部按钮：「保存这条」改为次按钮，放在左侧「删除这条」之后；原「关闭」改为主按钮「保存并关闭」贴最右。
- 新增 `save_and_close()`：没选中条目且模型 ID 为空时直接关窗；否则调 `save_one()`，保存成功才关窗，失败留在窗口并在提示行显示原因。Esc 与窗口右上角 × 仍是不保存直接关。

## 测试
- 新增 `tests/test_model_manager_actions.py`（5 条）：下拉无大小写重复且保留内建 `anthropic`；按钮左右次序与无「关闭」；空表单不保存直接关；保存失败不关窗并提示；保存成功后关窗。
- 契约有意变更：`tests/test_ui_batch7_settings_models.py` 的 `test_model_manager_save_is_right_of_close` 改为 `test_model_manager_save_and_close_is_rightmost_primary`（保存并关闭在保存这条右边、主按钮样式）；最小尺寸用例的「关闭」改「保存并关闭」。可见性与不掉出底边的断言未动。

## 验证（本轮运行，经 gui_hidden）
- `run_selftests -k model_manager_actions ui_batch7 pet_settings pet_ui pet_models`：680 条，首次 1 红为新测试夹具缺字段（已改用 `model_pool.record` 构造），复跑 `-k model_manager_actions ui_batch7` 19 条全通过。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：410 条，剩 1 项既有红 `test_performance_history_is_declared_as_historical_only`（worktree 下基准历史.json 未入库），非本轮引入。

## 未验证
- 未在真机界面截图确认按钮排布；排布由几何断言覆盖。
