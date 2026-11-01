# R896 UI 统一入口：资产不确定提交确认

- `asset_batch` 的不确定提交结果确认改由 `ask_confirmation()` 处理，并标注为危险确认。
- 文案保留“云端模型会再次计费”的风险说明，取消则只跳过不确定资产。
- 验证：`py_compile asset_batch.py` 与 `git diff --check` 通过。
- 其他历史直接确认调用仍待迁移，路线图未完成。
