# R2136 结果：剧本准备页语音输入改为录音＋云端识别（qwen3-asr-flash），识别服务可配置（功能轮）REQ-S01-71／DES-S01-71

- 本轮先领到 R2128；提交时中央轮次已到 R2133，重新领号；R2134 又被其他会话抢先，最终用 R2136，R2128、R2134 未使用。

## 三问
- 轮次类型：功能轮（§3）。REQ-S01-71 是有意变更的契约。
- 测试和三个基线：都跑了，均在本 worktree、本轮改动后的树上运行。
  - 默认冒烟 8/8。
  - 架构门禁 410 项全过（见下文关于 `基准历史.json` 的说明）。
  - 全量 `--all --safe` 本轮未运行。
- `project_status.md` 欠账：没有减少，也没有新增。本分支不提交 project_status.md，由合并轮在 master 上同步。

## 为什么改
- R2112 的 `VoiceDictation` 走 Windows SAPI 离线听写，中文识别率低。用户报告点麦克风后只出现「语音输入已结束。」，没有文字。
- 桌面微信的做法是先录音，再交云端识别。本轮照这个思路实现：
  - 录音：`platform_tools.MicrophoneRecorder` 经 winmm waveIn 录 16 kHz 单声道 16 位 PCM。
  - 识别：`speech_api.transcribe` 把录音以 WAV data URI 内联，POST 到阿里云百炼 OpenAI 兼容接口的 `/chat/completions`，默认模型 `qwen3-asr-flash`。

## 改动
- `platform_tools.py`（L0）
  - 删除 `VoiceDictation` 和 SAPI 脚本。
  - 新增 `MicrophoneRecorder`：后台线程收集 PCM，录满 `max_seconds` 自动结束，`stop()` 交回 WAV 和峰值。
  - 无设备、设备被占用、非 Windows 时返回中文原因。
  - 新增 `wav_bytes()`：随附解释器没有 `wave` 模块，WAV 头用 struct 手写。
- `speech_api.py`（新建，L2）
  - 内置默认值可由 `data/语音识别.json` 覆盖：`base_url`、`model`、`key_env`、`language`、`max_seconds`、`timeout`。这就是预留的语音模型配置接口。升级时 `data` 目录保留，换服务不用改代码。
  - 密钥只按变量名从 `model_pool.named_key` 读取，不写进设置文件、日志或异常文字。
  - 服务地址必须是 HTTPS，本机地址允许 HTTP。出站请求只经 `platform_tools.open_https`。
- `desktop_writing_page.py`：`VoiceInput` 改为 idle → recording → transcribing 三态。
  - 录音时状态栏显示秒数和音量条。
  - 静音（峰值低于 300）和短于 0.5 秒的录音不发云端，状态栏指向麦克风隐私设置。
  - 识别不走 `Desktop.async_()`，因为新票号会作废正在运行的剧本请求。改用本输入框自己的 `BackgroundTaskLifecycle` 登记代次（AGENTS.md 第 30 条），页面销毁时停录并取消，迟到结果不进界面。
- 文档
  - `docs/stages/S01_剧本准备.md`：更新 REQ-S01-71、DES-S01-71，追溯表加入 `test_speech_api`。
  - `architecture.md`：L2 列表加入 speech_api。
  - `配置说明.md`：新增「语音识别（剧本准备页麦克风）」一节。
  - `runbook.md` §11：覆盖基线的模块数从 329 改为 330。
- 门禁登记
  - `tests/architecture/_layers.py`：speech_api 登记为 L2。
  - `维护记录/架构统一基数.json`：
    - 第一项：speech_api 列入 exempt_items（与 tts_api 同类），exempt_count 从 44 改为 45。
    - 第四项：`speech_api.py:transcribe` 的 `json.loads` 解析的是 HTTP 响应体，按既有「网络响应解析」先例登记为 exempt。
  - `维护记录/覆盖率基线.json`：用原有的 8 组定向用例重跑 `scripts/coverage_report.py` 刷新。结果 50/330，目标用例全通过。

## 测试契约变更（断言未动）
- `tests/test_platform_tools.py`：旧的 `VoiceDictation` 测试随功能一起撤下，换成 `MicrophoneRecorderTests`，共 3 条：
  - 录满上限后返回合法 WAV。
  - 提前 stop。
  - 无设备、设备被占用、非 Windows。
- `tests/test_script_composer.py`：旧的听写测试换成 2 条：
  - 录音后插入识别文字；静音不发云端；录满自动识别；开麦失败显示原因。
  - 缺少密钥时只在状态栏说明。
- `tests/test_speech_api.py`（新建）：3 条，覆盖默认值与用户覆盖、请求格式、错误不泄露密钥、缺少密钥、拒绝 HTTP 地址。
- 其余既有测试的断言未改动。

## 验证（本轮运行）
- `run_selftests.py -k test_script_composer test_platform_tools test_speech_api test_idea_chat test_desktop_automation_service`：全部通过，经 gui_hidden.py 运行。
- `smoke_test.py --affected platform_tools desktop_writing_page speech_api`：通过。
- `smoke_test.py`：8/8。
- `smoke_test.py --architecture`：410 项 OK。
  - 改前失败集合：覆盖基线 2 项、service_return_contract 1 项、统一基数第四项 1 项，以及 test_agents_md 的 1 个 ERROR。
  - test_agents_md 报错是因为缺 `维护记录/基准历史.json`。这个文件被 .gitignore 忽略，只存在于主检出，worktree 里本来就没有，与本轮改动无关。跑门禁时临时拷入，跑完已删除。在主检出合并时不会出现这一项。
- 真机实测
  - 在本机麦克风上录音成功，录满自动停和手动停都正常。
  - 真实 DashScope 接口端到端识别成功：一段朗读录音返回「今天天气很好，我们去公园散步。」。

## 未验证
- 全量 `--all --safe`：本轮未运行。
- 没有在重启后的真实应用里由用户本人说话做完整流程实测。

## 回滚
- 回退本提交即可。`data/语音识别.json` 是可选文件，不存在时使用内置默认值。
