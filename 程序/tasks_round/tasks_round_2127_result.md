# R2127 结果：合入 codex/wip-R2126 到 master（合并轮）

## 合入内容
- R2126（d6488319）：模型管理 Provider 下拉按大小写去重（保留内建 `anthropic`），「保存这条」移到左侧「删除这条」之后，原「关闭」改为主按钮「保存并关闭」（保存成功才关窗）。
- `git merge --no-ff`，无冲突。合并前暂存区无他人文件。断言未动（R2126 内的契约有意变更见其结果文件）。

## 验证（本轮运行，master，经 gui_hidden）
- `run_selftests -k model_manager_actions ui_batch7 pet_settings pet_models`：74 条，全通过。
- `smoke_test.py`：通过。

## 未验证
- 未跑架构门禁与全量（后台全量由 post-commit 自动补跑）；未在真机界面截图。
