# R2164 结果：初步分镜删除已勾选分镜后列表不刷新、报 WinError 2（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3.2）。用户报初步分镜页删除分镜稿后，表格仍显示已删除的行，状态栏提示「分镜目录结果已过期，将在下次文件变动后重试：[WinError 2] 系统找不到指定的文件」。无对应队列 ID。
- 测试和三个基线：在 worktree 分支 `claude/deleted-storyboard-deletion-error-8a1400` 上运行（经 gui_hidden）。
  - `run_selftests.py -k storyboard page_cache`：ALL TESTS PASSED。
  - `smoke_test.py --affected storyboard_page_controller`：9/9 通过。
  - 默认冒烟：8/8 通过。
  - `--architecture`、全量 `--all --safe` 本轮未运行（单模块改动，未跨层）；全量原写「由提交后钩子后台补跑」，实际没有触发（worktree 没有 `运行环境/Python`，钩子跳过）；已在 R2173 合并轮更正，改由合并提交后的后台补跑。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 复现
1. 初步分镜页勾选若干分镜稿，点「删除选中分镜」确认。
2. 文件已移入回收站，但表格仍显示这些行，状态栏报 WinError 2；再刷新也一样。

## 根因
`recycle_files` 已把磁盘 `ui_settings.json` 的勾选去掉，但 `StoryboardPageController.selections`（内存勾选）仍含已删路径。`apply_catalogs` 为「已勾选但扫描没扫到」的分镜补行时调用 `path.stat()`，文件已不存在而抛 `FileNotFoundError`，表格重绘前就中断。后台监听刷新同样走这段，因此一直停在旧状态。资源管理器里直接删掉已勾选分镜也会触发。

## 改动
- `storyboard_page_controller.py`：补行前只保留仍存在的勾选文件（`path.is_file()`）。

## 测试
- 新增 `tests/test_storyboard_page_controller.py::test_refresh_after_selected_board_is_deleted_drops_it_instead_of_failing`。修复前失败：`FileNotFoundError: [WinError 2] 系统找不到指定的文件。`（`storyboard_page_controller.py` line 78 `path.stat()`）；修复后通过。
- 已有测试断言未动。

## 提交
见本轮提交（R2164）。

## 用户需做
重启应用后生效。
