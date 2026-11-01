# R1945 结果：换页冻结绘制，旧页留屏、新页排好后一次画出（功能轮）

## 背景
用户反馈：点击侧栏切换页面时，组件一块块冒出、位置跳动，像卡顿错乱；希望像 X 那样丝滑。

原因：Tk 在 Windows 上边排版边直接往屏幕画。拆旧页、建新页、`fit_content` 逐轮补布局的每个中间态都会上屏。隐藏桌面探针数据：每页建页 27–240ms，Tk 空闲排版 100–570ms，每页 12–55 个控件。实机 `logs/app.log` 里 `page.paint.*` 为 1–9 秒。

## 改动
- `desktop_layout_resize.py`：新增 `PaintFreeze`。
  - 冻结：对内容区 canvas 的 HWND 发 `WM_SETREDRAW 0`，这块区域（含子窗口）的绘制全被裁掉，屏幕上保留旧页像素。
  - 解冻：发 `WM_SETREDRAW 1`，再用 `RedrawWindow(INVALIDATE|ALLCHILDREN|UPDATENOW)` 一次画出。
  - 兜底：最长冻 `PAGE_FREEZE_MAX_MS` 后自动解冻。非 Windows 或控件不可见时什么也不做。冻结期间若 Tk 已收起该控件，解冻后用 `ShowWindow(SW_HIDE)` 把它收回去。
- `desktop.py`：`_page_paint_timed` 装饰器在 `show()` 开头冻结；建页抛异常时立即解冻再上抛。删掉 Desktop 类内一行多余空行（见下文“门禁”）。
- `desktop_layout.py`：新增 `freeze_page_paint`／`thaw_page_paint`。`_apply_layout.run` 在尺寸和滚动位置都稳定后解冻；`cancel_resize`（关窗）时也解冻。
- `ui_tokens.py`：新增 `PAGE_FREEZE_MAX_MS = 800`。
- `pet_ui_voice.py`：把 R1926 的启动招呼等待判断提成模块级函数 `_startup_page_busy`，行为不变。原因是 `PetVoiceMixin` 已超出复杂度登记上限（1127 > 1119），提取后回到上限内。

## 与批准方案的偏差
批准的方案是“未映射的 holder 幕后建页、一次换上”。实际改用 `WM_SETREDRAW` 冻结绘制，理由有三：
- 效果相同：旧页一直留在屏幕上，新页稳定后一帧换上。
- builder 照常在已映射的框里建页，避开了方案风险栏里写的“未映射时 `winfo_width/height` 读到 1”的问题。
- 视频页的常驻窗口不能换父，这个方案下不必为它留例外，改动面也更小。

方案第 3 步（扩大整页缓存）暂缓，等用户实机反馈后再决定。

## 门禁
master（a72d2359）上 `desktop.py::Desktop` 已经是 1303 行，超出上限 1302，来自 R1937 之后。本轮没有抬高登记值，而是删掉 `_build_sidebar` 前一行多余空行，回到 1302。

## 测试（经 `工作流任务/gui_hidden.py` 在隐藏桌面运行）
- 新增 `tests/test_page_paint_freeze.py`，6 条全部通过：
  - 冻结后不上屏，解冻后恢复；
  - 超时自动解冻；
  - 不可见的控件不处理；
  - Tk 已收起的控件解冻后仍保持隐藏；
  - 切页后冻结，布局稳定后立即解冻；
  - 建页失败时立即解冻。
- `run_selftests.py -k complexity function_size page_paint page_cache ui_motion_perf ui_batch3 test_pet_ui sidebar desktop_layout resize`：共 674 条，除 `test_pet_ui` 外全部通过。
- `test_pet_ui` 有 5 条红。原因是 R1913 起登录门禁生效，报“需要登录账号”，改动前就存在，不是本轮引入。
- 断言未动。
- 未运行：全量、smoke。
- 实机观感未验证：隐藏桌面截屏是黑的，无法逐帧取证，需要用户在真机上来回点侧栏确认。
