# R1926 修复轮结果：启动画面封顶、三虎招呼推迟、去掉右下角 Sizegrip

## 实测依据
- 真实记录 `splash_total` 约 4.8 秒，`desktop_shell_ready` 仅 0.65 秒：画面显得长，是因为它在等「剧本准备」页在背后建完（`page.paint.script` 真实记录 1.2～3.5 秒），不是动画本身慢。
- 隐藏桌面采样：揭开后三虎开机招呼（`greet`）与窗口摆位（`ready`）各有一次约 2.2～2.4 秒卡在 `update_idletasks`（页面版面计算）。隐藏桌面整体偏慢，未能原样复现真机落点，此项是推断。

## 改动
- `ui_tokens.SPLASH_MAX_SECONDS = 2.5`，`Splash.wait` 的 `timeout` 默认取它（原 15 秒）：画面最长盖 2.5 秒，超时强制揭开，页面在原位接着建。
- 三虎开机招呼等启动页就绪：`desktop.py` 初始化 `win._desktop_startup_settled=False`，`desktop_automation_tick._resume_tick_after_first_paint` 置真；`pet_ui_voice.greet` 在定时触发且未就绪时改期，上限 `pet_ui_support.GREET_SETTLE_POLLS=40` 拍（约 18 秒），避免招呼永远不来。假宿主无该属性时默认视为就绪，原用例不受影响。
- 去掉 `desktop.py` 的 `ttk.Sizegrip`：它由 Tk 逐像素实时改窗口大小、内容跟着重排，与另三个角（系统边框缩放）表现不一致；右下角也走系统边框。
- 新增测试：`test_pet_ui` 两条（招呼等启动页就绪、等满上限后仍冒）、`test_splash_timing` 一条（封顶默认值）。

## 验证
- 经 gui_hidden 跑 `-k pet_ui splash startup_perf launcher token_boundary desktop_compact`：634 条，新增 3 条通过；`startup_perf` 单跑 14 条全绿。
- `test_pet_ui` 有 5 条红（`test_a_step_without_an_unattended_poll_starts_nothing` 等，提示「需要登录账号」）：在干净 master 上同样 5 条红，属 R1913 闸门默认打开后遗留，**非本轮引入**，未处理，待另起修复轮。断言未动。
- 真实启动：隐藏桌面运行 `启动漫剧制作助手.pyw` 14 秒，无启动错误，`splash_total` 2.1 秒（该工作树无续开项目，不含剧本页建页）。
- 未验证：有续开项目时揭开后卡顿是否消除、Sizegrip 去掉后的右下角手感，均需用户实机确认；未跑全量与架构全门禁。

## 回滚
`git revert` 本轮提交。
