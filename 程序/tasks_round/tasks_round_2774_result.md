# R2774 结果：费用统计模块收口——今日明细 CSV 改任务书固定路径＋状态栏提示
<!-- round-evidence: {"commit_base": "a684ab97", "credential_hits": 0, "evidence_sha256": "24acf11c7e946495", "exit": 0, "failed": 0, "passed": 43, "round": 2774, "tests": "run_selftests.py -k usage"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1）——任务书 R4 验收偏差收口。R2682 已合入 master（R2696 合并轮），
   复核任务书发现「导出 CSV」实现用了 `FileDialog` 让用户自选路径，与任务书
   「写到 `<项目>/今日调用明细_YYYYMMDD.csv`（utf-8-sig）并 `self.status.set()` 提示」
   不符；本轮改回任务书口径。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过。
   - 定向 `run_selftests.py -k usage`：**43 条全绿**（`test_usage_indicator_ui` 8/8，
     其中 CSV 用例改断言固定文件名/BOM/内容/状态栏提示；`test_usage_snapshot` 9/9）。
   - 架构门禁：未跑（仅 L4 文案与导出路径收口，无契约／分层／事件变更；
     R2682 合入时已 466/466）。
   - 全量：合入 master 后由后台自动全量覆盖（R2696 合并树 7397 条、2 红均为
     合入前既有欠账：`test_round_baselines` 轮次连续性、`test_video_ui` 文案断言）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；消除一处任务书验收偏差（CSV 导出路径与通知方式）。

## 变更

- `ui_usage_detail.py`：`_export_csv` 改为直接写 `<项目>/今日调用明细_YYYYMMDD.csv`
  （UTF-8-SIG，`save_text` 原子写），成功后 `desktop.status.set('已导出今日调用明细：…')`；
  移除 `FileDialog` 自选路径；导出失败仍走 `notify`；`_tokens_text` 的「万」标注
  改任务书半角括号格式 `1,234 (0.1万)`。
- `tests/test_usage_indicator_ui.py`：`_Desktop` 补 `status` 替身；CSV 用例改走
  `_export_csv` 真实路径，断言固定文件名、BOM、三行内容与状态栏提示。

## 边界与说明

- 「余额」项：账户余额无真实数据源（`skill_budget.snapshot()` 是 Token/图/视频
  限额、非 ¥ 余额），按任务书「查不到就隐藏，绝不显示假 0」恒隐藏；UI 链路
  已就绪，待真实余额源接入即自动显示。
- 「结算后 500ms 内刷新」：`usage_updated` 事件驱动（pet_bus 队列 → 订阅回调 →
  `refresh()`），机制满足，无独立计时断言。
- 本工作树另有他人在制改动（剧本结构编辑相关 12 个脏文件），本轮只暂存本任务
  两个文件与结果文件，未触碰。
