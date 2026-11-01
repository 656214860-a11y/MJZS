# R1451 结果

> 说明：本轮在车道分支 `codex/wip-R1448` 开发，号源已被并行任务占用，合并时正式记为 R1451。验收复测补充：真实项目「摄影侠」副本上 02→03 来回的进入页绘制耗时中位数，02：约 360→约 190 ms，03：约 360→约 180 ms；点击返回时间（同步耗时）由 60–190 ms 降到 1–13 ms；首次进入 03 约 510→约 420 ms。验收时的相关测试（page_cache、script_workspace_service、compact_layout、core、startup_perf、ui_edges、idea_chat）全部通过。
本轮类型：修复轮（性能）＋界面。
测试跑了吗：已尝试规定入口，并执行直接 unittest 与增量验证；非全绿验收，详见下文。
欠账变化：B/C 已修复并通过几何测试；A 部分改善，03 的 40% 门槛未达，完整真实项目及 04–13 对比仍欠账。

## A：证据与改动
- 原前提需修正：03 原本已有整页缓存；02 未缓存，离开 02 仍会销毁控件。
- 本轮修改前 profile：go_page 183ms、show 159ms、update 231ms；destroy 43 次累计 754ms。
- destroy 是递归包含时间，不能当作独立墙钟耗时相加；对应整次绘制 414ms。
- 修改后一次 profile：show 约 5ms，气泡播报/重排仍约 81ms，故增加 150ms 导航稳定期，取消过期播报。
- 连续 go_page 使用 after_idle 合并，只建最后一次请求；即时更新高亮，直接 show/关闭窗口取消挂起导航。
- 02 使用独立容器缓存，文件内容签名及采用来源变化失效；同页刷新、直接 show、换项目沿用重建。
- 03 沿用文件监听；缓存命中直接切换目标容器，避免先映射公共空框。
- 环境：Windows、指定 Python、同一 .probe_tmp 部分副本，探针调用顺序及 profile 开关前后一致。
- 原始项目 05资产管理目录读取被拒绝，完整 copytree 失败；下表不是完整真实项目验收，未借用历史基线。

| 绘制完成时间 ms | 本轮修改前 | 最终修改后 | 变化 |
| --- | ---: | ---: | ---: |
| 首次01 | 1444 | 1404 | -2.8% |
| 首次02 | 399 | 420 | +5.3% |
| 首次03 | 510 | 479 | -6.1% |
| 首次04 | 232 | 122 | -47.4% |
| 首次05（资产目录缺失） | 667 | 468 | -29.8% |
| 快速02（三次中位数） | 382 | 194 | -49.2% |
| 快速03（三次中位数） | 155 | 101 | -34.8%，未达40% |

- 快速原始样本：02 前418/382/351、后202/194/124；03 前414/155/135、后190/101/92。
- 日志：`.probe_tmp/before-partial.log`、`final-partial.log`；两次探针 errors 均为空。
- 04–13 仍走公共容器销毁/重建；本轮只对全部导航请求合并，未贸然缓存带门禁和会话的页面。
- 扩展探针修改前04–08绘制为2178/6906/7085/6868/4839ms，存在明显环境波动，不与上表混用。
- 扩展探针在09的 white_model_service.environment_summary → file_cache.probe_writable → tempfile.mkstemp 挂起，已停止；09–13及其它页15%门槛未验证。

## B/C：界面
- 项目树按展开后可见分组/项目行数计算，最少3行、上限取可用高度；取消树行拉伸，余量放导航下方。
- reload、分组打开/关闭、窗口尺寸变化均合并重算；新建/删除/移动项目沿用 reload。
- 齿轮按标题与图标请求尺寸计算垂直中线，不写死位置像素。
- 几何测试4条完成：缩放、按钮可见、树内容增删/折叠展开、标题齿轮中线，误差±2px。

## 验证与未完成
- 解释器统一为 `D:\漫剧制作助手\运行环境\Python\python.exe -B`；未跑全量或 smoke --gate。
- 规定入口：`程序/run_selftests.py --serial -k test_script_workspace_service test_core test_desktop_startup_perf test_desktop_compact_layout test_page_cache test_ui_edges`，卡在共享GUI令牌；加 `--gui-wait 0` 仍卡住，已停止，不能记为通过。
- 共享锁位于工作树外；未修改锁、未修改自检入口。另有其它工作树GUI进程，本轮性能不构成隔离环境凭据。
- 直接 `-m unittest test_script_workspace_service`：21条通过，见 `.probe_tmp/service-tests.log`。
- 直接 `-m unittest test_core test_desktop_startup_perf test_desktop_compact_layout test_page_cache test_ui_edges`：按有序进度核对，core126通过/1跳过、startup14通过、compact4通过、cache9通过/1错误。
- cache错误为新增夹具缺自然剧本文档（IndexError），补足夹具后单项通过，见 `cache-fixed.log`；未弱化断言。
- 最后增量运行 cache 的 nav_back、same_page_refresh、navigation_cancels_old_stage_announcement：3条通过，见 `cache-final-tests.log`。
- ui_edges 完成2条后停在 BatchContinuationTests.test_adopt_skips_adopted_without_confirm，长时间无进展后停止；未整卷重跑，尚未完成。
- 直接GUI测试日志有 invalid command name ...speak 噪声；缓存测试增加 cancel_timers 清理，未宣称消除全套噪声。
- 最终限制：A未完整验收（03不足40%、源目录不可读、04–13未完成）；规定测试入口与ui_edges未完成，需可读完整项目/隔离GUI环境后补验。
- 未提交、合并、推送、切分支；未改 project_status 或共享接力文件；临时证据仅在 .probe_tmp，无清理删除操作。
