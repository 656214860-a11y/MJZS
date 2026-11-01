# R2201 结果：seedream、qwen 测试连接与 stage_flow.follow 改用共享件（结构治理轮）

## 三问
- 轮次类型：结构治理轮（§3.3）。不加功能，涉及 3 个模块（`seedream_settings`、`qwen_setup`、`stage_flow`），同步 `architecture.md`。续 R2195。
- 来源：本会话 /code-review 全项目扫描第 10 条（摘录见 R2195 结果报告）：「seedream_settings.py:100 的 probe 与 tts_settings 几乎逐行相同……qwen_setup.check 也各写一套『后台线程写列表、定时轮询回 Tk』。stage_flow.follow 还另外手写了 tk_timers.repeat 已有的 after/Destroy 取消逻辑。」本轮把共用件接到这三处；`desktop_account_page._account_background` 不在范围。
- 轮次号：开工不领号，提交前一刻领 R2201。
- 测试和三个基线：worktree `happy-jennings-48da69`，经 gui_hidden。
  - `run_selftests.py -k follow_buttons test_stage_flow seedream qwen test_ui_edges`：193 条全过。`-k follow_buttons background_probe --serial`：10 条全过。
  - `smoke_test.py --affected seedream_settings qwen_setup stage_flow`：8 项通过、1 项红（定向自检 110 个文件 1357 条，红的是 `test_ui_edges.BriefTintTests.test_the_users_own_words_show_up_on_the_display`，上次存下的创意没显示在展示框）。
    - 该用例与本轮改动的模块无关，且在 R2195 的 `--affected` 里同样出现过一次、原样重跑又过；单独跑（上一条 193 条）、去掉本轮文件按同组 `--serial` 跑（206 条）都过。判断为在整组高负载下偶发（时序），**未追查根因，也未重跑到绿**，本轮不改该用例；留作观察项。
  - `--architecture`：411 条红 1 条，即 `test_round_baselines.test_round_number_continuous`（2153 != 2202），分支新增结果报告所致，合并轮登记后转绿。
  - 全量 `--all --safe` 本轮未手动运行，由提交后钩子后台补跑。真机未手动核对。
- `project_status.md` 欠账：没有减少，也没有新增。

## 改动
- `seedream_settings.py`：`probe` 改用 `api_endpoints.probe_message` 与 `tk_timers.run_in_background`，净减 13 行，文案不变。
- `qwen_setup.py`：`check` 改用 `run_in_background`（`probe(cfg)` 原样）。此前 `probe` 若抛异常，状态栏会一直停在「正在验证连接…」；现在走 `on_error`，显示「连接失败，请检查网络、根地址和 API Key。」。去掉不再用的 `threading` 导入。
- `stage_flow.py`：`follow` 改成「先 `apply_text` 一次，再 `tk_timers.repeat(widget, interval, …)`」，不再手写 `after`／`after_cancel`／`<Destroy>` 绑定，净减 24 行。返回值由内部 `tick` 改为 `stop`，8 处调用方都没用返回值。新增对 L1 `tk_timers` 的导入（该模块不 import Tk，`stage_flow` 仍保持无 Tk）。
- `architecture.md`：维护边界新增一条。不改层级、不新增模块与登记项。

## 测试
- 新增 `tests/test_follow_buttons.py`（3 条，真 Tk）：按钮字与置灰跟着阶段状态走（挂上时立刻刷一次）；按钮拆掉后 `after info` 为空，定时器已撤；`stop()` 能提前结束刷新。原先没有测 `follow` 的用例。
- 行为保持：`test_ui_edges` 里的 `test_seedream_probe_reports_reachable`、`test_tts_probe_reports_connection_failure` 守着探测文案，断言未动。本轮是抽取，没有「修复前红」。

## 用户需做
重启应用后生效。
