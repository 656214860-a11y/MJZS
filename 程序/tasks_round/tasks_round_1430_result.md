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


## 补记：Windows 全量回归发现并修复 xml.sax 回归（原计划 R1431，并入本轮）
- 触发：在 Windows 随附解释器上跑 `run_selftests.py --all --safe`（5044 条用例，668.6 秒，31 个文件有红）。

#### 根因

R1427 的 `edit_export.py` 使用 `xml.sax.saxutils`，而随附的精简解释器已裁掉 `xml.sax`（只保留 etree 与解析器）。`engine._encode` 在成片合成后调用 `publish_edit_lists`，其内部 import 失败，导致 `assemble` 在真实环境里直接异常。Linux 完整 Python 上不可见，所以 R1427 当时未发现；`test_stdlib_closure`、`test_integration` 在 Windows 上正确拦下。

#### 修复

- `edit_export.py`：自带 `escape`／`quoteattr`，不再引用 `xml.sax`；与 `saxutils` 对 `& < > " ' \n \t` 及中文逐一比对输出一致。
- `tests/test_environment_check.py`：`check_comfy` 的「未找到」断言依赖真实机器上有没有 ComfyUI，现把 `comfy_runtime.executable` 打桩，不再依赖本机环境。

#### 全量中其余红的归类（未改）

- 写作／创意系列（`test_writing_*`、`test_idea_*`、`test_skills`、`test_workflow`、`test_cancellation_status`、`architecture.test_skill_reference_injection`、`test_script_contract`）：独立工作树里没有未入库的 `程序/skills` 目录，报"SKILL 引用缺失"。属验收环境缺资源，不是代码问题，需在含 skills 的主目录验证。
- `architecture.test_round_baselines`：分支上状态页头仍写 1430，结果文件已到 1430；状态页在 master 上已更新为 1431，分支不改状态页。
- `test_idea_chat#7`：并行池 180 秒无进展被回收，待在主目录复跑确认是否为既有慢用例。
- 日志里的 `tcl ... unknown encoding "cp1252"` 是随附解释器在中文路径下读 Tk 包索引的噪声，非本轮引入（未验证是否一直存在）。

#### Windows 测试

- Linux 副本：`test_edit_export`、`test_environment_check` 通过。
- Windows 重跑受影响的 4 个模块见下一条提交说明；全量需含 skills 的树才能完整验证。
