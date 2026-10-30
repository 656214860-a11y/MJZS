# R2112 结果：剧本准备页附件卡片移到麦克风右侧、麦克风改用系统听写（功能轮）

## 需求
- REQ-S01-71（新增）：工具行从左到右为「+」、麦克风、附件卡片、发送／终止；卡片按上传顺序从左往右，放不下换行，无附件不占位。麦克风改为听写开关：系统自带 System.Speech 中文听写，逐句插入光标处，听写中按钮主色高亮，再点或页面关闭即停止；失败只在状态栏说明。占位提示「＋」不显示，改为「输入想法，Enter 发送，点 + 上传附件」。
- REQ-S01-62／63 的卡片位置描述、REQ-S01-67 标注被 REQ-S01-71 取代；DES-S01-67 撤下 Win+H 方案，新增 DES-S01-71；锚定表加 REQ-S01-71 行。
- 用户原话第 3 点为空，未处理。

## 原因
- 用户机器（Windows 11 Enterprise LTSC 2024）上 Win+H 调不起语音输入；本机已装 zh-CN SAPI 识别器，`SetInputToDefaultAudioDevice()` 可打开麦克风，故改走 SAPI。

## 改动文件
- `platform_tools.py`：删 `start_voice_typing()`，新增 `VoiceDictation`（隐藏 PowerShell `-EncodedCommand`，READY／TEXT／ERR 行协议，读线程入队，`terminate_process_tree` 停止，脚本每轮核对父进程 PID）。
- `desktop_writing_page.py`：新增模块级 `VoiceInput`（toggle／poll／stop，`<Destroy>` 时停止）；`idea_uploaded_panel` 改建在工具行内；占位提示文案。`_WritingPage` 仍为 600 行。
- `desktop_idea_chat.py`：卡片面板 `pack(side='left', fill='x', expand=True)`；文件名右侧按 × 实际宽度留位（原固定 `SPACING['lg']` 时 × 压住文件名末字）。
- `ui_tokens.py`：`VOICE_POLL_MS = 150`。
- `docs/stages/S01_剧本准备.md`：见上。

## 测试
- 新增：`test_platform_tools.VoiceDictationTests` 两条（行协议转事件与停止；非 Windows 不起进程）；`test_script_composer.test_microphone_toggles_dictation_and_inserts_text`（替换原 Win+H 用例：开关、高亮、插字、失败提示、error 事件停止）。
- 契约有意变更、同步断言（断言未弱化）：`test_idea_chat` 「附件卡片在输入区上方」改为「在输入区下方、麦克风右侧、发送键左侧」；`test_ui_edges` 占位提示文案。

## 验证（本轮运行）
- `run_selftests -k platform_tools ui_edges`：137 条全通过。
- `run_selftests -k script_composer idea_chat desktop_compact_layout req_s01_anchors`：165 条全通过；改卡片留位后 `-k script_composer idea_chat` 157 条全通过。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：剩 1 项既有红 `test_performance_history_is_declared_as_historical_only`（基准历史.json 未入库），非本轮引入。
- 本机真机：`VoiceDictation().start()` 起进程收到 READY，`stop()` 后进程结束（无人说话，未验证识别文字）。
- 隐藏桌面截图确认三张卡片按上传顺序排在麦克风右侧、文件名完整。

## 未验证
- 实际说话的中文识别效果需用户试用；SAPI 中文听写准确度一般，不如微信语音输入。
