# R1751：性能轮——拖动调整窗口大小时合并重排，松手后一次排好（RESIZE）

## 三个必答问题

1. **轮次类型**：性能轮（§3.7，RESIZE 任务书续做）。
2. **测试跑了吗、三个基线过了吗**：窄关键词跑了；`smoke_test.py`、`--architecture`、全量按续做任务书要求**未运行**（由调度方验收时跑）。见下方“实际命令计数”。
3. **`project_status.md` 欠账少了吗**：未改 `project_status.md`（执行方不领号、不改状态页），本轮欠账以本文件为准。

## 改动清单（文件:函数）

- **新增 `desktop_layout_resize.py`**：`_NativeProbe`（只读 Win32：`GetWindowRect`／`GetCursorPos`／`GetAsyncKeyState`／`GetSystemMetrics`）、`ResizeCoalescer`（拖动判定、静默补做、可重复 `cancel`）。
- **`desktop_layout.py`（LayoutMixin）**：新增 `_join_resize`、`cancel_resize`、`watch_window_resize`、`_on_resize_configure`；改 `fit_content`（带 event 才合并，主动调用仍立即）、`_apply_layout`（原 `fit_content` 主体）、`_layout_all`（松手补做：内容＋侧栏＋表头）、`_relayout`、`schedule_sidebar_fit`（顺带刷新表头）；`on_window_map` 先 `flush()` 再立即重排。
- **`desktop.py`**：`__init__` 把原 `content`／`canvas` 的 `<Configure> → fit_content` 两条绑定收成 `watch_window_resize(win)`；`cancel_timers` 调 `cancel_resize()`。净行数 1418（HEAD 1419，未增加）。
- **`app.py`**：`App.__init__` 增加 `resize_scheduler=None` 默认值；`fit_page_heights` 先询问合并器（拿不到就照旧立即）。
- **`desktop_media_pages.py`**：创建视频页后把 `Desktop.resize_scheduler` 交给 `App`，页面级文字框重排共用同一判定。
- **`desktop_writing_page.py`**：`fit_talk`、`fit_talk_container` 拖动期间并入整页补做。
- **`ui_tokens.py`**：`DESKTOP_LAYOUT` 新增 `resize_quiet_ms=128`、`resize_edge_px=4`（唯一规格来源，无魔法数字）。
- **新增 `tests/test_window_resize_coalescing.py`**：真 Tk，5 条用例。
- **删除探针垃圾**：`tests/` 下 `_tmp_*.py`／`_probe_*.py` 共 24 个（先 `ls` 核对后删除；未动其他文件）。
- **`tests/architecture/_layers.py`**：把 `desktop_layout_resize` 登记到 L4，紧跟 `desktop_layout` 同行（`_register(4, …)`）；模块导入为 `sys`／`tkinter`／`app_logging`（L1）／`ui_tokens`（L1），不违反分层方向。
- **`维护记录/覆盖率基线.json`**：用工具 `scripts/coverage_report.py` 按基线原 8 组目标重跑刷新，模块总数 289→290，新增 `desktop_layout_resize.py`（covered 0／total 161／0.0%）；工具同时按当前树重算了 13 个模块的可执行行数（其中 `app.py`、`desktop_layout.py`、`desktop_media_pages.py`、`desktop_writing_page.py` 属本轮 RESIZE 改动，另 9 个为刷新前基线陈旧行数）。
- **`runbook.md` §11**：基线刷新后 `modules_total`／未覆盖模块数由 289／239 同步为 290／240，否则 `test_runbook_states_the_directed_measurement_caliber` 红。

## 先红证据

续做开始时（前两次会话留下的代码）跑 `tests/test_window_resize_coalescing.py`：**4 红 1 绿**，其中合并器 `_fire_once` 因调试行引用未定义变量 `drag` 抛 `UnboundLocalError: cannot access local variable 'drag'`，静默补做永不执行；另有调试代码向 `D:/repo-meta/fire_err.txt` 追加日志、重复写 traceback，已全部移除。原始“改前 HEAD 红”输出**未保留**（按任务书不用回滚补验；调度方可用变异法补验）。

## 拖动判定与处理者清单

**判定方式**：顶层窗口矩形（`GetWindowRect`）四条边各取系统边框＋内补边宽度形成命中圈，光标在圈内且左键按着（`GetAsyncKeyState`）才算拖动。标题栏在命中圈内侧，不算上边框；最大化直接判否。移动窗口也发 `<Configure>`，主窗口事件用宽高变化过滤，不会因移动逐帧重排。

**降级**：非 Windows、`ctypes` 初始化失败、拿不到窗口句柄／光标／按键时 `drag_active()` 返回 `None`，合并器退化为“纯静默窗口合并”（连续尺寸变化合成一次、静默后补做），不抛异常、不卡死；`after_cancel` 与 TclError 均已兜底。

**纳入（拖动期间合并，松手静默后补做）**
- `desktop.py:187/188/197` 侧栏／侧栏画布／项目树 `<Configure> → schedule_sidebar_fit`（现经 `_join_resize`）。
- `desktop.py:220` 内容框 `<Configure> → align_header` 保留立即；但 `desktop.py:1072` 各页 holder `<Configure> → fit_content` 会在事件路径上被合并。
- 主窗口／页面画布／内容框（原 `desktop.py:220/222` 两条 `fit_content` 绑定）统一为 `desktop_layout.py:30` 的 `_on_resize_configure`。
- `app.py:233` 视频页 `fit_page_heights`（经 `desktop_media_pages.py` 接入同一合并器）。
- `desktop_writing_page.py:307`（气泡 `refit_bubbles` 内部经盒宽变化触发 `fit_talk`）、`:405` 对话容器、`:408` 创意框。

**有意不纳入（保持立即）**
- `desktop.py:195/196/198` `align_header` 与 `:207/208` 表头换行：只做几次 `place`／`wraplength` 赋值，不量整页、不进 idle 队列；补做时 `_layout_all` 会再对齐一次。
- `responsive_ui._bind_debounced_configure`（表格列宽）：本身已按 `after_idle`＋宽度去重；且拖动期间内容框宽度被冻结，列宽不会逐帧变化。
- `app.py:231/272`、`desktop_writing_page.py:307` 等页内子控件 Configure：拖动期间内容框宽度不更新，内层尺寸事件不会连续发生；页面切换、输入等非拖动路径照旧立即。
- `show()` 内主动 `fit_content()`（`desktop.py` 切页）：不带事件，保持立即。

## 实际命令计数（均为窄关键词，未跑全量／架构门禁）

- `python -B tests/test_window_resize_coalescing.py`：**5 条通过**（末次 22.6 秒）。
- `run_selftests.py -k window_resize`：5 条，0 文件红，16.7 秒，`ALL TESTS PASSED`。
- `run_selftests.py -k window_resize responsive desktop_startup_perf page_paint_metric`：25 条（含架构 `test_responsive_layout_contract` 2 条），0 文件红，45.0 秒，`ALL TESTS PASSED`。
- `run_selftests.py -k desktop_layout responsive_ui desktop_startup_perf page_paint_metric perf_baseline`：27 条，**1 个文件红（test_perf_baseline 1 条，见下）**，64.0 秒。`desktop_layout`／`responsive_ui` 关键字未匹配到独立测试文件。
- `run_selftests.py -k perf_baseline`：9 条，仍是同 1 条红；另一次运行缩略图用例曾红一次、复跑转绿。
- `python -B scripts/coverage_report.py tests.test_money_invariants tests.test_request_ledger tests.test_keyframe_lifecycle_service tests.test_video_lifecycle_service tests.test_persistent_task_queue tests.test_lifecycle tests.test_publication_recovery tests.test_claim_queue_gateway --json 维护记录/覆盖率基线.json`：**模块被覆盖 50/290，目标用例全通过**，已写入基线。
- `run_selftests.py -k layers coverage_baseline window_resize`（架构登记返工）：**31 条，0 文件红，20.1 秒，`ALL TESTS PASSED`**；命中 `architecture.test_layers` 5 条、`architecture.test_coverage_baseline` 5 条、`test_model_probe_layers` 16 条、`test_window_resize_coalescing` 5 条。首次运行时同关键词 1 红（`test_runbook_states_the_directed_measurement_caliber`：runbook §11 仍写 289／239），同步 runbook 后复跑全绿。未跑全量与 `--architecture` 全集（按任务书要求，由调度方验收）。
- `python -B smoke_test.py`（架构登记返工）：**通过 8 项，失败 0 项**。

**既有红，非本轮引入**：`test_perf_baseline.PerfBaseline.test_page_switch_does_not_force_the_tk_idle_loop` 断言 `inspect.getsource(Desktop.show)` 含 `self.fit_content()`，但 HEAD 上 `show` 已有 `@_page_paint_timed`，`getsource` 返回 wrapper；`git show HEAD:程序/desktop.py` 第 1086 行可见该装饰器，且本轮 diff 未触碰 `show`。缩略图用例的偶发红对应 TEMP 缩略图缓存里已存在 `.none` 空白标记（当时统计 1053 个），与 `asset_thumbs` 未改动的代码路径一致，复跑转绿。

## 断言未动声明

`tests/test_perf_baseline.py` 及所有既有测试**未修改**。新增 `tests/test_window_resize_coalescing.py` 的 5 条断言未弱化；仅把 `setUp` 中对旧探针 `probe.client_rect` 的保存／恢复删掉（新探针改用窗口外框矩形，该属性已不存在），属测试夹具适配，不影响断言内容。本次架构登记返工未修改任何测试文件（`_layers.py` 仅追加一行登记）。

## 需裁决事项

1. **拖动过程中画面实际是什么样**：本轮**没有做实机鼠标拖动目测**（测试用几何变化模拟）。按实现推断：拖动期间画布内容窗口停留在改前宽度——放大时右侧／底部露出画布背景（空白），缩小时右侧被裁掉；窗口边框与画布背景仍随 Windows“拖动时显示窗口内容”逐帧重绘，只是页面内容不再重排。松手约 128ms 后一次排好。请用户实机确认视觉是否可接受。
2. **要做到“纯外框”还需要什么**：需要接管 `WM_ENTERSIZEMOVE`／`WM_EXITSIZEMOVE`（用 `SetWindowLongPtrW` 子类化 Tk 顶层窗口过程），在进入拖动时隐藏内容窗口（或画自绘橡皮筋边框），退出时恢复并只排一次。风险：替换 Tk 的 WndProc 可能破坏 Tk 内部消息处理；ctypes 回调要保活，否则崩溃；与 Tk 的模态 sizing loop、DPI／多显示器、最大化还原存在交互；失败时可能卡死窗口。属本轮范围外，未实施；也不得改系统“拖动时显示窗口内容”设置。
3. **基线刷新的顺带行数变化**：工具按当前树重算，除新增 `desktop_layout_resize.py` 外，另有 9 个与本轮无关的模块 `total` 被刷新（`app_logging`／`asset_contract`／`pet_models_ui`／`pet_ui_stages`／`recon_service`／`skill_tools`／`storyboard_catalog_service`／`storyboard_selection`／`ui_widgets`，属刷新前基线陈旧）。基线文件 diff 为 25 增 19 删；未手改基线。若要求 diff 严格只含新增项，需要一次独立的基线刷新轮。

## 独立验收（Claude，最新 master R1750 之上的干净验收树）

- **执行链（如实）**：codex group/group-4 两次各用满 3600s 总时限未留结果文件；转 Qoder DeepSeek-Flash 续做（09:20 起，约 11 分钟写出结果文件），之后又派一次 Qoder 做架构登记返工（09:50–09:54）。同一车道先后经三批执行方之手，前两批留下约 25 个 `tests/_tmp_probe*.py`／`_probe_*.py` 调试垃圾与一处 `UnboundLocalError`，第三批已清理 24 个，本次提交核对车道与主树均无残留。
- **补丁**：车道基于 39b3c7f6，主树已在 R1750；车道 diff 对 R1750 `git apply --check` 干净通过，再应用到主树，未使用 `commit_batch.sh LANE=`。desktop.py 1421→1420 行，未增加。
- **窄测试（验收树）**：`run_selftests -k window_resize responsive desktop_startup_perf page_paint_metric perf_baseline pid_reuse` 共 40 条，93.4 秒，0 文件红（其中 perf_baseline 9 条含 R1749 修好的旧红）；返工后 `-k layers coverage_baseline window_resize runbook` 31 条 29.9 秒 0 红；冒烟通过。
- **变异验证**：把 `desktop_layout._on_resize_configure`／`schedule_sidebar_fit` 的 `_join_resize` 判定改成恒不合并，新测试 5 条中 3 条变红（continuous_drag、drag_without_release、quit_event），还原后恢复。执行方没留改前红输出，这是调度方补验。
- **架构门禁**：首次 `--architecture` 红 3+2：3 条为新模块未登记（`test_layers` 与 2 条 `test_coverage_baseline`），属本批遗漏，已派返工补登记并同步 runbook §11；2 条（`test_agents_md` 缺被 git 忽略的 `基准历史.json`、`test_skill_reference_injection` 缺本机 SKILL 参考文件）为全新工作树缺本机文件所致，主树 `run_selftests -k test_agents_md skill_reference_injection` 24 条 0 红。返工后验收树 `--architecture` 375 条仅剩这 2 条环境红。「欠一次完整安全全量」属后台补跑项。
- **覆盖率基线**：工具刷新时顺带重算了 13 个模块的可执行行数，其中 4 个属本批改动，9 个是刷新前就陈旧的行数，均为工具产出，非手改。
- **需用户知悉**：①拖动时画面是「内容不重排、露出空白或被裁」，不是「只显示外框」，执行方未做实机目测，请实机确认；②要做到纯外框需子类化 Tk 顶层窗口过程接管 WM_ENTERSIZEMOVE／WM_EXITSIZEMOVE，有破坏 Tk 消息处理、回调保活、DPI／多显示器交互、卡死窗口的风险，本批未做，待用户裁决。
- 断言未动；未新增 skip。
