# R1809：结构治理轮——切 Desktop.show 的换页前置段（批次 C-3）

1. 本轮类型：§3 结构治理轮（切分不改行为）。

2. 测试与基线：
   - 数据流脚本切分：`show` 的前 61 条语句（取消待办导航、记录页码与滚动位置、资产子路由复位、视频模式偏好、清掉旧内容、刷新导航高亮）切成 `_show_reset_page(index, video_mode)`，返回 `scroll_offset`、`page_cache` 给 `show` 剩下的 90 行使用；两个装饰器（`timed('page.show')`、`_page_paint_timed`）仍包在 `show` 上，计时口径不变。
   - 架构门禁 384 条 + `desktop`／`navigation`／`page_cache`／`scroll`／`video_ui`／`project_home`／`sidebar` 相关共 533 条（含 GUI）：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿；默认冒烟 8/8。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| `desktop.Desktop.show` | 152→91 行；拆出 `_show_reset_page`（61 行） |
| `test_function_size_ratchet.py` | 删 `desktop.py::show` 登记 |
| `test_complexity_ratchet.py` | `Desktop` 类上限 1297→1302 |
| `test_cloud_video_settings_boundary.py` | 视频模式偏好委托检查的方法集合加入 `_show_reset_page`（偏好发布代码随之搬了家）；**断言未动** |
