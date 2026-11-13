# R2391 修复轮结果

## §7 三问

1. **本轮类型**：修复轮（§3.2）——修 bug。
2. **测试跑了吗、三个基线过了吗**：
   - 定向（先红后绿）：`run_selftests.py -k writing_restart --serial` 15 条，新增 `test_labels_keep_confirmed_revision_documents` 修复前红（`labels[confirmed_file]` KeyError，revision 里已确认文档被漏掉），修复后绿。
   - 定向回归：`run_selftests.py -k writing --serial` 179 条 0 红。
   - 受影响冒烟：`smoke_test.py --affected writing_api` 422 条 0 红、9 项通过。
   - 默认冒烟：`smoke_test.py`（经 `工作流任务/gui_hidden.py` 隐藏桌面）8/8 通过。
   - 架构门禁：未单独跑（修复轮只改 L3 `writing_api.preparation_file_labels` 只读函数，非结构治理/跨层改动，§5 不要求）。
   - 全量：未跑（`writing_api.py` 不命中 §5 强制全量条件——非启动路径、非 Tk 控件生命周期、非删除语义、非层级登记表改动）。
3. **project_status.md 的欠账少了吗**：本轮不涉及 project_status 欠账条目；属中断任务（11/6 遗留）收口。

## 根因与修复

- **根因**：`writing_api.preparation_file_labels()` 处理 `revision.documents`（重写草稿）时，原逻辑 `if document.get('confirmed') is not True: labels[...] = '重写待确认'`——只有**未确认**的草稿才写标签，**已确认**的重写稿（`confirmed=True`）被整体漏掉，导致 UI 上该文件不显示任何版本标记。
- **修复**：改为与 `documents` 循环一致的三元表达式 `'已确认' if document.get('confirmed') is True else '重写待确认'`，已确认重写稿与待确认草稿都正确入标签。
- **最小改动**：仅改 `preparation_file_labels` 一处 4 行，未动其他逻辑。

## 测试资产

- `tests/test_writing_restart.py` 新增 `test_labels_keep_confirmed_revision_documents`：构造 revision 里同时含已确认稿与待确认稿，断言前者标「已确认」、后者标「重写待确认」。断言未弱化（新增用例，未改动既有断言）。

## 复现步骤

1. 项目 `preparation_state.json` 的 `revision.documents` 放入一条 `confirmed=True` 且 path 不在 `documents` 里的记录（重写已确认但尚未落回 documents 的状态）。
2. 调用 `writing_api.preparation_file_labels(project)`。
3. 修复前：该 path 不出现在返回字典；修复后：返回「已确认」。

## 提交

- 已提交：是（`codex/wip-R2391` 分支，提交信息 `R2391: 修复 preparation_file_labels 漏标 revision 已确认稿（修复轮）`）。
- commit hash：以 git log 为准（结果文件随提交 amend，避免 hash 自指）。
