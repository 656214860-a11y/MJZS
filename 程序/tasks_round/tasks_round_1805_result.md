# R1805：性能轮——资产清单发布包内容没变就不再落盘（`asset_plan._publish_plan_bundle`）

1. 本轮类型：§3 性能轮。起因：用户反馈全量测试太重；逐用例采样发现 `test_ui_edges` 最重的用例大头不是 `Desktop` 构造，而是无人值守轮询每个节拍都重写资产清单。

2. 测试跑了吗、三个基线过了吗：
   - 先红后绿：新增 `AssetPlanRepublishTests` 3 条，改动前 `test_identical_bundle_is_not_written_again` 红（`{'json': 6, 'text': 2} != {'json': 3, 'text': 1}`），另两条守护旧行为；改后 `-k test_asset_plan` 7 条 0 红。
   - 受影响冒烟 `smoke_test.py --affected asset_plan`：9/9（含默认冒烟 8/8；定向 7 个文件 75 条 0 红）。
   - `test_ui_edges` 整文件 115 条 OK；`-k asset_plan_publication asset_auto_batch asset_batch unattended` 28 条 0 红。
   - 完整安全全量：本轮未手动跑，由合入后后台补跑。

3. 本轮改源码 +1（`asset_plan.py`）。

## 诊断证据（改动前，`test_unattended_chain_runs_asset_final_keyframe_in_order`）

- 用例 42 秒；`_publish_plan_bundle` 被调用 **397 次**，只落在同一个文件夹，**内容只有 4 种**，仅发布就占 9.9 秒（每次写 4 个文件，每个都 `fsync` 再回读复核）。
- 主线程调用栈采样（随附解释器没有 `cProfile`，用 `sys._current_frames` 每 50 毫秒采样）：`_sync_plan` 累计 32%，叶子热点为 `ntpath.realpath`、`core.save_text`、`publication.access`。
- 对照：`Desktop` 构造只要 0.14~0.38 秒，不是瓶颈；全量日志里 `test_ui_edges` 的 1063 秒是 8 路并行争用放大的，串行实测 281 秒。

## 修复

- `_bundle_is_current(...)`：四份文件都在，且解析后的内容（`==`）与待发布内容全部相同，才返回真；任何一份缺失、读不出、JSON 损坏（`ValueError`）或内容不同都按“不是最新”处理。
- `_publish_plan_bundle` 在读取旧字节、写入之前先判断，相同就直接返回；其余路径（整包重发、失败整体回滚）原样不动。

## 实测收益（诚实边界）

- 同一用例：发布耗时 **9.9→0.9 秒**，落盘调用 397 次→4 次；用例总耗时 42→33 秒。
- `test_ui_edges` 整文件前后 281 秒→314 秒：**没有变快**。两次测量之间别的会话在占用 CPU，噪声大于这一个用例省下的 9 秒；本轮不声称整文件提速。生产里无人值守补资产期间每个节拍的磁盘写入和 `fsync` 消失，是确定的行为变化。

## 后续（仅记录）

- 同一用例剩下的 33 秒里，`_sync_plan` 每个节拍仍整套重算并反复 `realpath`／`resolve`（397 次），可按输入签名缓存。
- 其余重用例的时间在 Tk 排版（`update`／`update_idletasks`）、真实可见窗口与 `settle` 轮询睡眠，不在本轮范围。

## 提交

- 已提交，commit hash 见 git log `R1805:`。
