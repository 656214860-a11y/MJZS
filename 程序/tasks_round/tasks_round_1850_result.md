# R1850 结果：修隐藏桌面下的 13 条全量红（修复轮）

断言未动。

## 根因与处理
1. **产品缺陷（10 条：test_ui_edges 5、test_video_ui.PromptBoxHeightTests 4、test_asset_detail 1）**
   `desktop_layout_resize.ResizeCoalescer.drag_active` 在 `GetCursorPos` 失败时返回“未知”，`schedule` 就把重排推迟到静默期后。非交互桌面（隐藏测试桌面，实机上锁屏/远程断开同理）读不到光标，于是提示词框高度、页面滚动区、表格列宽等程序化重排全被推迟，同步量尺寸的用例看到的是旧值。
   修法：左键读得到且没按着时直接判“不在拖”，不再依赖光标。左键都没按就不可能在拖边框，原有判定不受影响。
2. **根目录登记漏项（test_root_layout）**：`BLOCKED_ISSUES.md`、`handoff-full-safe.md` 已跟踪但没登记，补进 `ALLOWED` 并写明用途。
3. **环境能力缺失（test_desktop_tray 3 条）**：隐藏桌面没有资源管理器任务栏，`Shell_NotifyIconW` 返回 E_FAIL（WinError -2147467259）。新增 `skip_reasons.PLATFORM_NO_TRAY_HOST`；测试按本线程桌面名判断，不是 `Default` 才跳过（读不到桌面名就照常跑）。`skip台账.json` 已登记。

## 验证（本轮实跑，隐藏桌面）
- `run_selftests.py -k ui_edges video_ui asset_detail resize layout`：全过
- `run_selftests.py -k desktop_tray skip_hygiene root_layout`：全过，托盘 2 处登记跳过
- 托盘用例在默认交互桌面上的实跑，本轮没有做（钩子禁止在用户屏幕上开 Tk 窗口）。

## 未结
- test_perf_baseline 冷启动偶发超时、test_distribution_selfcheck 干净树复验：见提交后的全量结果。

## 全量凭据（R1852 补记）
`scripts/auto_full_safe.py --run`，HEAD 77f4cd4a（R1850），隐藏桌面，干净分离工作树 `.wt/ci`：
**共 6390 条用例，1182.2 秒，0 个文件有红，ALL TESTS PASSED**，凭据已写入 `full-safe-receipts.json`。
- 实际跳过 3 条：test_desktop_tray 2 处（PLATFORM_NO_TRAY_HOST，本轮登记）、test_core.test_stage_profile_wrong_preset_rejected（原有）。
- test_perf_baseline 9 条本次全过（冷启动未超时；偶发性仍可能出现，未改阈值）。
- test_distribution_selfcheck 3 条在干净树里全过，R1848 的修复复验成立。
- 旁注：手动在新建 `git worktree` 里跑全量会因嵌套 SKILL 仓库（gitlink、无 .gitmodules）为空而红一片，须用 `auto_full_safe.py --run`，它会拷入嵌套仓库。
