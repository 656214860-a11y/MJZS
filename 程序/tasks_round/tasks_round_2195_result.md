# R2195 结果：设置弹窗「测试连接」的后台线程与探测文案收口（结构治理轮）

## 三问
- 轮次类型：结构治理轮（§3.3）。不加功能，涉及 3 个模块（`tk_timers`、`api_endpoints`、`tts_settings`），同步 `architecture.md`。
- 来源：本会话 /code-review 全项目扫描第 10 条（`tts_settings.py:77`）。摘录：「tts_settings.probe 与 seedream_settings.py:100 的 probe 几乎逐行相同……qwen_setup.check 和 desktop_account_page 也各写一套『后台线程写列表、定时轮询回 Tk』。stage_flow.follow 还另外手写了 tk_timers.repeat 已有的 after/Destroy 取消逻辑。已出现过『跨线程设置 Tk 变量导致状态栏卡在正在检测』（两处注释原样复制），这类修复必须逐个弹窗重复打补丁。可抽成一个 tk_timers.run_in_background(widget, work, on_done)，探测文案归到 api_endpoints；follow 改用 tk_timers.repeat。」
  - 本轮：抽出共用件，`tts_settings` 先接入。`seedream_settings`、`qwen_setup`、`stage_flow.follow` 由下一轮接入（每轮不超过 3 个模块）。`desktop_account_page._account_background` 不在范围。
- 轮次号：开工不领号，提交前一刻领 R2195。
- 测试和三个基线：worktree `happy-jennings-48da69`，经 gui_hidden。
  - `run_selftests.py -k background_probe tts_setting test_timers`：全过；`-k test_ui_edges background_probe tts_setting`：122 条全过。
  - `smoke_test.py --affected tk_timers api_endpoints tts_settings`：
    - 第一次 1 项红：`test_ui_edges.BriefTintTests.test_the_users_own_words_show_up_on_the_display`（上次存下的创意没显示在展示框）。该用例不碰本轮改动的任何模块；去掉本轮新增文件、只跑同一组 `--serial` 的 5 个测试文件（206 条）全过；原样重跑 `--affected` 后 9 项全过（定向自检 18 个文件 222 条，0 个文件有红）。判断为偶发（时序），未追查根因，本轮不改该用例。
    - 另有一次真红是我自己的：`probe_message` 起初多带了 `timeout` 参数，`test_ui_edges` 里把 `probe_endpoint` 换成 `lambda url:` 的用例报「连接失败：TypeError」。去掉该参数（调用方本来就不传）后转绿，用例未动。
  - `--architecture`：411 条红 1 条，即 `test_round_baselines.test_round_number_continuous`（2153 != 2196）。分支新增结果报告，合并轮登记后转绿。
  - 全量 `--all --safe` 本轮未手动运行，由提交后钩子后台补跑。真机未手动核对。
- `project_status.md` 欠账：没有减少，也没有新增。

## 改动
- `tk_timers.py`（L1）：新增 `run_in_background(widget, work, on_done, on_error, interval=150)`。后台线程跑 `work()`，结果只写普通列表（跨线程设置 Tk 变量会抛 RuntimeError、状态栏会卡在「正在检测」），Tk 线程里轮询，成功交 `on_done(值)`、抛异常交 `on_error(异常)`，各一次；窗口销毁后不再回调。沿用 `repeat()` 的轮询与销毁取消。`on_error` 必填：原 `qwen_setup.check` 的 `probe` 一旦抛异常，状态栏永远停在「正在验证连接…」。
- `api_endpoints.py`（L2）：新增 `probe_message(base_url)`，文案与原三份一致：401／403／404 → 「接口可达（HTTP n，需密钥）」；其余可达 → 「接口可达（HTTP n）」；否则 「连接失败：」＋错误（缺省「未知错误」）。探测抛异常交调用方。
- `tts_settings.py`：`probe` 改用二者，净减 17 行；界面文案不变，探测异常仍报「连接失败：异常类名」。
- `architecture.md`：维护边界新增一条，写明来源、新接口和后续轮次。不改层级、不新增模块与登记项。

## 测试
- 新增 `tests/test_background_probe.py`（7 条）：
  - `probe_message`：三个密钥墙状态码、普通可达、不可达带错误文本和缺省文本、探测异常原样抛出。
  - `run_in_background`：用真 Tk 窗口，结果在主线程交一次且不重复、工作在另一线程；异常走 `on_error`；窗口销毁后不回调。
  - 本轮是纯抽取（行为保持），共用件是新增接口，修改前不存在，所以没有「修复前红」；行为保持由原有 `test_ui_edges` 的 `test_tts_probe_reports_connection_failure`、`test_seedream_probe_reports_reachable` 守着，断言未动。

## 用户需做
重启应用后生效。
