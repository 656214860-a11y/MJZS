# R1376：UI 统一入口覆盖轮 — 忙碌态全链路（提交／取消／成功／失败／迟到结果）

类型：功能轮（§3.1，UI 统一入口：忙碌态路由到唯一 `BusyState`；不改业务逻辑、阶段、路径与分层）。中央轮次 1376（`.git/round-counter.json` 的 `last_claimed=1376`）。承接用户「UI 统一入口覆盖轮」指令，范围＝`维护记录/UI统一入口路线图_v1.md` 待收口 4 项之第 1 项「忙碌／加载态」（§二 第 7 项）。

## 三个必答
- 本轮类型：功能轮（§3.1）——UI 统一入口覆盖轮首批，忙碌态由分散的 `ttk.Progressbar.start/stop` 收口到统一 `ui_widgets.BusyState.set_busy`。
- 测试：架构 `smoke_test.py --architecture` **320/320**（原 315，只增不减；`tests/architecture/_layers.py` 与 §5 清单未改，未增删门禁文件）；定向 `run_selftests.py -k "video native asset_gating asset_batch_retention ui_widgets busy_state ui_edges"` **373 条 / 202.7 秒 / 0 文件红**；默认冒烟 `smoke_test.py` **8/8**；`py_compile app.py native_assets.py` OK。0 红。
- 欠账：1376 − 1375 = 1 < 5；未命中 §5 升级条件（未改启动路径／Tk 控件销毁重建／删除语义／层级登记表）。按用户「不因为是收尾就跑全量兜底」，本轮不跑全量。忙碌态路线图项「完成全量覆盖审计」，欠账减少。

## 范围与完成判据（路线图 §二 第 7 项，逐字）
- 完成判据：**禁用、加载、恢复及失败反馈遵循同一可取消约定。**
- 权威入口（`ui_components.md`）：`ui_widgets.BusyState` 是主后台任务的加载态入口，收尾必须用同一对象恢复；自动任务与专用中断链保留既有编排入口。
- 收口口径：生产代码里对不确定 `ttk.Progressbar` 的 `.start/.stop` 只允许出现在 `ui_widgets.py`（唯一入口），其余页面一律经 `BusyState.set_busy`。

## 实现

### 1. `app.py`（L4）：唯一 `BusyState` 实例
- 导入 `BusyState`；`App.__init__` 在 `self.task_progress=ttk.Progressbar(...)` 之后建 `self.busy_state=BusyState(self.progress_text,self.task_progress)`。
- `update_progress`／恢复查询／手动提交三处：`self.task_progress.stop()` → `self.busy_state.set_busy(False)`，`self.task_progress.start(15)` → `self.busy_state.set_busy(True,progress_interval=15)`（含 `'正在准备提交…'` 那处）。

### 2. `native_assets.py`（L4）：检测与制图两链路共用一个 `BusyState`
- 导入 `BusyState`；`ProgressLabel(...)` 之后建 `busy=BusyState(progress_text,progress)`。
- 检测链路：`progress.start(15)` → `busy.set_busy(True,progress_interval=15)`；`done` 里 `progress.stop()` → `busy.set_busy(False)`。
- 制图链路：`progress.start(15);selector.state(['disabled']);shape.state(['disabled'])` → `busy.set_busy(True,controls=[selector,shape],progress_interval=15)`；`finished` 里 `progress.stop();selector.state(['!disabled']);shape.state(['!disabled'])` → `busy.set_busy(False)`（控件的禁用／恢复由同一对象承担）。

### 3. 门禁 `tests/architecture/test_busy_state_boundary.py`（重写为 7 条）
- 递归零容忍：`test_progress_start_stop_lives_only_in_busy_state`——按 AST 识别模块内绑定到 `ttk.Progressbar` 的变量名，禁止其 `.start/.stop` 直调（豁免 `ui_widgets.py`）；`test_pages_with_progress_route_through_the_shared_busy_entry`——`app.py`／`native_assets.py` 各只许一个 `BusyState` 实例且有成对 True/False 调用。
- 全链路约定：`test_desktop_submission_pairs_lifecycle_and_busy`（提交同时登记生命周期与忙碌态）；`test_desktop_result_drain_rejects_late_results_before_restoring_busy`（`_tick_async_result` 内 `background_tasks.finish` 行号 < `busy_state.set_busy(False)` 行号，且有 `if` 守卫并含 `return`——迟到／过期结果先判定再恢复，不触发 UI 回调）；`test_desktop_cancel_invalidates_ticket_and_restores_busy`（取消经 `background_tasks.cancel` 且推进 `_async_ticket` 代次后恢复忙碌态）；保留 `test_async_lifecycle_uses_busy_state_for_start_and_finish`、`test_interrupt_does_not_stop_the_progressbar_directly`。
- 反向 canary 实证：用改前的 `HEAD:程序/app.py` 跑新扫描器，命中 `(1019,'task_progress','stop')`、`(1021/1032/1252,'task_progress','start')`——门禁确能拦住旧写法。

### 4. 夹具 `tests/test_video_revision.py`：`SimpleNamespace` 补 `busy_state=BusyState(Mock(),Mock())`（原 `progress_text`／`task_progress` 保留；该文件为 CRLF，按 \r\n 原地替换，未改整文件）。

## 验证
- 架构 `smoke_test.py --architecture`：**320/320、0 红**（121.5 秒；原 315）。`tests/architecture/_layers.py` 未改，§5 门禁清单未变（本次只改现有门禁文件内容，未增删文件）。
- 定向 `run_selftests.py -k "video native asset_gating asset_batch_retention ui_widgets busy_state ui_edges"`：**373 条 / 202.7 秒 / 0 文件红**（ALL TESTS PASSED）。
- 默认冒烟 `smoke_test.py`：**8/8**；`py_compile app.py native_assets.py` OK。
- 新增 `skipTest`：无。

## 边界
- 未改业务逻辑、阶段、路径、分层与用户数据；只把加载态的开关与控件禁用／恢复收口到统一 `BusyState`。
- 「忙碌／加载态」本项以「进度条开关唯一经 `set_busy`＋全链路成对恢复」为可检查口径；`desktop.py` 的提交／逻辑取消／迟到结果拒绝沿用既有 `BackgroundTaskLifecycle`＋`busy_state` 编排（既有实现，本轮以门禁用例固化）。
- 非进度条类的局部禁用（如 `idea_send.state(['disabled'])` 等聊天／编辑态）属其他路线图项与既有交互，不在本项范围，未改。

## 全量判定
- 1376 − last_full_safe_all_round(1375) = 1 < 5；未命中 §5 升级条件（启动路径／Tk 控件销毁重建／删除语义／层级登记表均未改，`BusyState` 仅包装既有控件、不销毁重建）。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据 round=1375、tree=c3df6a57…（＝`afcc0a4:程序`），但当前 `HEAD:程序=7b07336…`（差 `project_status.md`／`tasks_round_1375_result.md` 两文件）且本轮改了生产代码与测试，内容树将变，不能复用。
- 按用户指令「测试按 §5 触发表执行，不因为是收尾就跑全量兜底」，且本项改动不属 §5 强制升级条件，**本轮不跑全量**；下一自然全量在 `本轮号 − last_full_safe_all_round ≥ 5`（即 R1380）或命中升级条件时触发。

## 提交
- 内容：`程序/app.py`、`程序/native_assets.py`、`程序/tests/architecture/test_busy_state_boundary.py`、`程序/tests/test_video_revision.py`。
- 报告与状态页：`程序/tasks_round/tasks_round_1376_result.md`、`程序/project_status.md`（轮次头改为 1377）。
- 未触碰主树他人已暂存改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪用户目录。
