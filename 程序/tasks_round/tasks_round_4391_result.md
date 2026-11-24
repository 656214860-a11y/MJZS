# R4391 结果：FIX-S11-LOW 配音与字幕四条小缺陷合卡修复
<!-- round-evidence: {"commit_base": "67fd96c99", "credential_hits": 0, "evidence_sha256": "d983cb16d66d9bee", "exit": 0, "failed": 0, "passed": 126, "round": 4391, "tests": "run_selftests.py -k stage_completion tts offline_asr_setup"} -->

## 开头三问

1. **本轮类型**：修复轮（§3.2），任务卡 FIX-S11-LOW，波次 W2，车道 `codex/fix-s11-low`，基准 `67fd96c9`。合修三条缺陷（E-12 两处提示、E-14 清单坏条目报错、E-16 取消连子进程一起结束），只改卡面允许文件。
2. **测试与基线**：定向命令改前 126 条用例 4 条红（全部是新增复现测试，红因即缺陷本身）；改后 126 条 0 红、`ALL TESTS PASSED`、退出码 0（条数 = 改前 122 + 新增 4）。`smoke_test.py --architecture`：708 条 OK、退出码 0。默认冒烟与全量未跑（卡面未列）。
3. **欠账**：本轮无新欠账。改前红的 4 条全部转绿；两处既有测试只为对齐新取消口径补了桩（断言原样），未弱化、删除或 skip 任何既有断言。

## 缺陷复现方式与改前红（原文）

改前同一条定向命令（`run_selftests.py -k stage_completion tts offline_asr_setup`）共 126 条用例、3 个文件有红，红的就是新增复现测试：

- `test_offline_asr_setup.RunnerTests.test_cancel_terminates_the_whole_process_tree`（E-16）：`AssertionError: Expected 'terminate_process_tree' to be called once. Called 0 times.` —— `OfflineSetupRunner.cancel()` 直接 `proc.kill()`（offline_asr_setup.py:172），与同文件超时分支 `platform_tools.terminate_process_tree(proc)`（:256）做法不一致，安装器的子进程不随取消结束。
- `test_tts.TtsBatchResumeTests.test_manifest_non_object_entry_names_file_and_index`（E-14）：`AssertionError: ValueError not raised` —— 时间轴清单混入非对象条目（第 2 项为字符串）时，`batch_cost_preview` 与 `run_lines` 都不报错。审查基准 f624a5fc 上此处是 `manifest[index - 1].get(...)` 抛 AttributeError；R4346 引入 `_line_verdicts` 的 isinstance 防护后缺陷转为「静默跳过坏条目、对应句子照旧重新付费合成」，卡面要求报出清单文件与项号。
- `test_stage_completion_service.MediaCompletionTests.test_missing_ffprobe_prompt_names_the_config_entry`（E-12）：`AssertionError: 'config.json' not found in '请先配置 FFprobe，再校验媒体成果'` —— 提示没写去哪配。
- `test_stage_completion_service.MediaCompletionTests.test_import_without_media_tools_prompt_names_the_config_entry`（E-12）：`AssertionError: 'config.json' not found in '请先配置 FFmpeg 和 FFprobe，再导入媒体文件'` —— 同上。

## 设置入口核实依据（E-12，照实写、不猜）

- FFmpeg/FFprobe 可执行文件路径写在**项目 config.json** 的 `ffmpeg`/`ffprobe` 键：`orchestrator/stage_gate_gateways.py:30-33`（`media_import_publisher` 读 `<项目>/config.json`）、`orchestrator/stage_completion_service.py:102-103`（`prepare_media_completion` 同源）；`environment_check.py:137` 既有文案「安装 FFmpeg 后在 config.json 填写「ffprobe」」、`infra/diagnostic_capture.py:298`「在项目 config.json 配置「ffmpeg」「ffprobe」可执行文件路径」同口径。
- 核对入口：`ui/pet_settings_ui.py:31`（`HUB_TITLE = '设置'`）、:114（`DEV_TITLE = '开发信息'`）、:758-770（开发信息页的「环境自检」按钮跑 `environment_check.run_checks_with_versions()`）。
- 界面内没有项目 config.json 的 ffmpeg/ffprobe 编辑控件（`app.py:1355` 的「FFmpeg程序／FFprobe程序」标签写的是云端视频工作集 `cloud_video/*/config.json`，不是导入链路读的项目 config.json），故提示写「在项目 config.json 填写」＋「设置 → 开发信息 → 环境自检」可核对。

## 改了哪几处（文件:行号）

- `程序/agent/media.py:106-108`：`MediaValidationError` 前半句「请先配置 FFmpeg 和 FFprobe，再导入媒体文件」原样，续上「在项目 config.json 填写「ffmpeg」「ffprobe」路径，「设置 → 开发信息 → 环境自检」可核对」。
- `程序/orchestrator/stage_completion_service.py:105-107`：`ValueError` 前半句「请先配置 FFprobe，再校验媒体成果」原样，续上「在项目 config.json 填写「ffprobe」路径，「设置 → 开发信息 → 环境自检」可核对」。
- `程序/domain/tts_api.py`：新增 `_require_object_entries`（536-542）——时间轴清单逐条必须是对象，坏条目抛 `ValueError('逐句配音清单 <folder>/时间轴.json 第 N 项不是对象，请核对或删除该批次目录')`，只报错不修清单；在 `batch_cost_preview`（574）与 `run_lines`（670）读到清单后、写任何文件前调用，两处同口径。
- `程序/domain/offline_asr_setup.py:172`：`cancel()` 里 `proc.kill()` 改为 `platform_tools.terminate_process_tree(proc)`，与超时分支（256）同一出口；`except OSError` 兜底原样。

## 测试变更

- `程序/tests/test_stage_completion_service.py`：+2 条（570-594）——缺 FFprobe 校验提示、缺 FFmpeg/FFprobe 导入提示，均断言保留前半句且含 `config.json` 与 `环境自检`。
- `程序/tests/test_tts.py`：+1 条（591-612）——清单第 2 项为字符串时 `batch_cost_preview` 与 `run_lines` 都抛 ValueError，文案含 `时间轴.json`、`第 2 项`、`不是对象`；并断言 `generate` 未被调用（坏清单不再静默续跑扣费）。
- `程序/tests/test_offline_asr_setup.py`：+1 条（291-301）——桩住 `platform_tools.terminate_process_tree` 断言 `cancel()` 以当前 proc 调用一次；另两个既存用例（`test_cancel_emits_cancelled_and_keeps_resumable_state` 254-257、`test_start_twice_is_rejected` 286-288）按 §2.4「契约有意变更可同步 mock」给替身补 `terminate_process_tree → proc.kill()` 桩（FakeProc 无 `pid`，真实实现在 Windows 会走 `taskkill /PID`），断言逐字未动。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git status --porcelain`（开工） | 0 | 无输出 |
| `git log -1 --format=%h` | 0 | `67fd96c99` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/fix-s11-low` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_completion tts offline_asr_setup`（改前） | 1 | 126 条用例 3 个文件共 4 条红（原因原文见上节） |
| 同上（改后） | 0 | 「共 126 条用例，9.4 秒；0 个文件有红」「实际跳过 0 条用例」「ALL TESTS PASSED」 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 708 tests in 289.470s` `OK` `✅ 架构治理测试：tests/architecture` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 轮次 4391 |

## 未验证项

- 未在真实 Desktop／Tk 窗口里点「导入配音／逐句配音／下载离线语音包」：三处修复都发生在服务层异常文案与进程出口，UI 透传链路未改。
- E-16 未跑真实子进程树取消（测试按要求桩住 `terminate_process_tree` 断言调用口径；该函数本身在平台进程边界测试中已有覆盖）。
- 未跑默认冒烟与全量 `run_selftests.py --all --safe`（卡面未列）。

## 待文档同步（DOC-S11 车道）

- `docs/stages/S11_配音与字幕.md` 相关条目如需引这两句提示，新文案为：「请先配置 FFmpeg 和 FFprobe，再导入媒体文件；在项目 config.json 填写「ffmpeg」「ffprobe」路径，「设置 → 开发信息 → 环境自检」可核对」、「请先配置 FFprobe，再校验媒体成果；在项目 config.json 填写「ffprobe」路径，「设置 → 开发信息 → 环境自检」可核对」；IF-S11-63/IF-S13-07/IF-S13-60、UX-S13-69 现引旧句。
- 时间轴清单新报错文案：「逐句配音清单 <批次目录>/时间轴.json 第 N 项不是对象，请核对或删除该批次目录」（`batch_cost_preview`／`run_lines` 在清单含非对象条目时抛出）。

## 卡外发现（只记录不顺手修）

- `domain/tts_api.py` 的 `pending_lines`、`unknown_line_indexes`、`release_unknown` 也读时间轴清单，非对象条目仍按既有口径静默跳过（卡在范围外；`release_unknown` 对非 dict 条目本就跳过不处理）。
- `unknown_release_prompt` 两次读清单之间若文件被改坏，`manifest[index - 1]` 仍可能取到非 dict——属既有时序边界，未动。

## 被拒绝的命令

- `Get-ChildItem -Recurse -Filter "*AUD-US05*" ...`、`Get-ChildItem -Name "D:\漫剧制作助手\.agent-tmp" ...`、`Get-ChildItem tests -Filter "test_*.py" | Where-Object ...`、`Get-ChildItem scripts -Name`（枚举目录类命令）：各被拒一次，未重试，改用 `find_file_by_name`／`grep` 工具完成同等定位。
- 卡面所列定向命令、架构门禁、`dev.py claim`、`dev.py commit` 均未被拒。

## 提交

- 车道 `codex/fix-s11-low`，领号 R4391；提交命令与哈希见交付报告。
