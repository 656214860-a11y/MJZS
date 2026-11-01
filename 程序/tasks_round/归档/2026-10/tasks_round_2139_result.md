# R2139 结果：剧本准备页语音输入改为实时听写（边说边出字，qwen3-asr-flash-realtime）（功能轮）REQ-S01-71／DES-S01-71

## 三问
- 轮次类型：功能轮（§3）。REQ-S01-71 是有意变更的契约：从「录完再识别」改为「开麦后边说边写」。
- 测试和三个基线：都在本 worktree、本轮改动后的树上运行。
  - `run_selftests.py -k script_composer speech_api platform_tools writing_page`（经 gui_hidden）：43 条全过。
  - 默认冒烟：失败 0 项。
  - 架构门禁 `--architecture`：410 项全过。worktree 缺 `维护记录/基准历史.json`，运行前从主检出临时拷入，跑完已删除，未提交。
  - `--affected` 选中 0 条（按已提交基线比对），相关测试已由上面的 `-k` 覆盖。
  - 全量 `--all --safe` 本轮未运行。
  - 实连验证：用主检出模型池里的 `DASHSCOPE_API_KEY` 和合成语音推流，四句全部识别正确；错误密钥得到「密钥无效或没有开通 qwen3-asr-flash-realtime（HTTP 401）」，文字里不含密钥。
- `project_status.md` 欠账：没有减少，也没有新增。本分支不提交 project_status.md，由合并轮在 master 上同步。

## 为什么改
用户反馈 R2136 的录音＋识别「要点击结束后才能翻译，延迟很大」，要求：打开麦克风开关后直接说话，文字自动写进输入框，关闭开关即结束。

## 改动
- `platform_tools.py`（L0）
  - `MicrophoneRecorder` 新增 `on_chunk`：给了就每 0.1 秒把这一块 PCM 交给它，不再攒整段；`seconds` 改按已录字节数计。不给时行为不变。
  - 新增零依赖 WebSocket 客户端：`open_websocket()`（握手校验 `Sec-WebSocket-Accept`，非 101 抛带 `status` 的 `WebSocketRefused`）和 `WebSocket`（`send_text` 加锁发带掩码文本帧，`recv_text` 拼分片、自动回 pong、对端关闭返回 None）。
- `speech_api.py`（L2）：批量 `transcribe` 换成 `RealtimeSession`。
  - 默认 `wss://dashscope.aliyuncs.com/api-ws/v1/realtime`、`qwen3-asr-flash-realtime`、`silence_ms` 400、`max_seconds` 600、`timeout` 15；仍可由 `data/语音识别.json` 覆盖。
  - 连接后发 `session.update`（pcm、16 kHz、server_vad），写线程推 `input_audio_buffer.append`，`finish()` 后发 `session.finish`；读线程产出 `partial`／`final`／`error`，最后总有 `closed`。
  - 401/403、其他拒绝、连不上、服务端 error 都转成中文原因，不含密钥。
- `desktop_writing_page.py`：`VoiceInput` 改为实时听写。
  - 打开：建会话，以 `on_chunk=session.send` 开麦，按钮高亮，输入框获得焦点。
  - 每句一对左／右重力 mark，中间结果以浅色 `voice_partial` tag 写在光标处并随结果替换，定稿后变正常颜色，下一句接在后面，光标跟着新字走。
  - 关闭：停录、`finish()`，等最后一句定稿和 `closed`，超过 `timeout` 秒则取消。
  - 开麦 3 秒仍无声音时状态栏提示检查麦克风隐私设置；出错只在状态栏说明。
  - 会话代次仍由本输入框自己的 `BackgroundTaskLifecycle` 登记（AGENTS.md 第 30 条）。
- 文档：S01 的 REQ／DES-S01-71、`配置说明.md` 语音识别一节、`architecture.md` L2 说明。`architecture.md` 里 `speech_api` 那句原本重复了两遍，一并改成一句。
- 台账 `维护记录/架构统一基数.json` 第四项：旧锚点 `transcribe:json.loads:…` 换成 `RealtimeSession._handle:json.loads:66e0763f09fb6123:1`，仍按网络响应解析 exempt，数量不变。

## 测试契约变更（断言未动）
- `test_speech_api`：批量接口已删除，原两条 `transcribe` 测试改为测 `RealtimeSession` 的推流、事件和失败原因；「失败给中文原因且不含密钥」「没配密钥指向 DASHSCOPE_API_KEY」的断言保留。
- `test_script_composer`：`test_microphone_records_then_inserts_recognized_text` 改为 `test_microphone_dictates_live_into_input`，按新契约测边说边写、关麦收尾、第二次打开可用、无声提示、出错复原、录满自动关麦、无麦克风；按钮位置、高亮样式、焦点断言照旧。`test_microphone_without_key_explains_in_status` 未改。
- `test_platform_tools`：新增流式录音和 WebSocket（本机测试服务器）共 3 条，原有断言未动。
