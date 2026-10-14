# R1430 结果：视频与配音逐笔用量写入请求台账（路线图 C 收尾）

- 轮次类型：§3.3 功能轮（小）。工作位置：独立工作树分支 `codex/r1430-ledger`（主目录另一任务有未提交改动）。
- 范围：`pet_llm.py`（新增 `record_request`）、`engine.py`（`record_video_usage`，在 `publish_downloaded_video` 成功落盘后调用）、`tts_api.py`（`run_lines` 增 `on_line` 回调）、`stage_execution_service.py`（`run_tts_lines` 传入项目并记账）、`desktop.py`（传 `project`）、`tests/test_request_recording.py`（5 项）、`tests/test_video.py`（FakeStudio 补方法并断言）、`维护记录/架构统一基数.json`（stage_execution_service 3 个 json.loads 登记点行号 +8，未放宽规则）。

## 内容

- `record_request(project, request_id, kind, amount, note, mode)`：预留＋结算＋保存，用固定 request_id，重复调用幂等；任何 OSError／ValueError／TypeError 都吞掉并返回 None，不影响主流程。
- 视频：每个下载成功的版本记 1 次（kind=videos）和镜头标称时长秒数（kind=seconds，mode=estimated，时长未知则不记秒）。
- 配音：每行成功发布后记 1 次（kind=requests），id 含集、行号和文本哈希；同一行重跑不重复记。
- 用量总览（R1429）读到的请求台账由此开始有内容。

## 未覆盖

- 生图：调用点没有项目句柄，需改签名，单独一轮。
- 秒数是镜头标称值，不是供应商结算值（已标 estimated）。

## 测试

- Linux 副本（Python 3.12，非随附解释器）：`test_request_recording` 5 项通过；架构目录 341 项通过。
- 相关模块（test_tts、test_audio_role_binding、test_video 等 366 项）对比未改动副本：失败 22 个均在未改动副本上同样出现（`msvcrt`、`LOCALAPPDATA` 等 Linux 专有原因），本轮唯一新增失败（test_video FakeStudio 缺 `record_video_usage`）已修。
- 未运行：随附解释器冒烟、全量（欠账 1430−1420=10 轮，待 Windows 补跑）、真实 TTS／视频任务上的实机记账。
