# R4439 · FIX-S11-E9 导出 SRT 按逐句配音实测时长校准
<!-- round-evidence: {"commit_base": "b565161b5", "credential_hits": 0, "evidence_sha256": "48950ed86d10267e", "exit": 0, "failed": 0, "passed": 74, "round": 4439, "tests": "run_selftests.py -k subtitle_export subtitle_calibration media_page_controller"} -->

## 三问

- 本轮类型：§3.2 修复轮（先定位根因：L3 `export_stage_srt` 未传 `audio`，永远按句长估算；只改根因所在模块 `stage_execution_service.py` 与状态文案 `media_page_controller.py`）。
- 测试跑了吗：跑了。改前定向红 8 条（原文见下）；改后 `run_selftests.py -k subtitle_export subtitle_calibration media_page_controller copy_rules` 92 条全绿（退出码 0）；`smoke_test.py --architecture` 708 条全绿（退出码 0，失败集合为空）。默认冒烟基线 8/8 与全量回归未跑（卡面验收未列，未运行；车道分支不累计全量轮次）。
- 欠账少了吗：消除 AUD-US05 审查报告 E-9（REQ-S11-22「给了真实音频就按它校准」）；未新增欠账。卡外发现记录于文末。

## 缺陷复现方式

`stage_execution_service.export_stage_srt`（改前 `stage_execution_service.py:192-198`）只调 `export_srt(project, episode, publish=publish_stage_text)`，从未传 `audio`——逐句配音成品明明落在 `音频/配音分句/<批次>/`（`ui/desktop_audio_direct.py:61`），导出字幕仍一律按句长权重估算。修复后先查当前集最近一批逐句配音清单（`批次.json` 的 `episode` 与 `domain/tts_api.py:672` 写入口径一致，`时间轴.json` 为逐句清单），用 FFprobe 实测已生成音频时长，按 (shot_id, text) 出现顺序配对后传给 `export_srt(..., audio=...)`；无成品、对不上或未配置 FFprobe 时安全退回估算并如实写 `audio_skip_reason`。

复现：新增 `tests/test_subtitle_export_service.py::StageSrtLineAudioTests` 六条与 `tests/test_media_page_controller.py::SubtitleStatusTests` 两条——全成品按实测校准、部分成品 mixed、无批次退回估算、有成品无 FFprobe 带原因退回、跨集不误配、无 episode 字段旧批次可沿用；状态文案区分「已校准 N 句／还有 M 句未校准」并附跳过原因。改前 8 条红，红因即缺陷本身。

## 改前红（8 条，原文节选）

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k subtitle_export subtitle_calibration media_page_controller`（退出码 1；共 74 条，8 红）

```
### test_media_page_controller（2 条红）

===== test_audio_skip_reason_is_explained_and_short =====
AssertionError: '未配置 FFprobe' not found in '字幕时间暂按句长估算，还有 2 句未按实际配音校准，导出前请先听校。'

===== test_mixed_mode_reports_calibrated_and_pending =====
AssertionError: '已按实际配音校准 2 句' not found in '字幕时间暂按镜头时长估算，还有 1 句未按实际配音校准，导出前请先听校。'

### test_subtitle_export_service（6 条红）

===== test_export_uses_measured_line_durations =====
TypeError: export_stage_srt() got an unexpected keyword argument 'probe_duration'

===== test_finished_lines_without_ffprobe_fall_back_with_reason =====
KeyError: 'audio_skip_reason'

===== test_legacy_batch_without_episode_still_applies / test_no_line_batch_keeps_length_estimate / test_other_episode_batch_is_not_mismatched / test_partial_finished_lines_export_mixed_report =====
TypeError: export_stage_srt() got an unexpected keyword argument 'probe_duration'
```

## 改动（文件:行号）

- `程序/stage_execution_service.py:192-196`：新增 `_episode_audio_token`，集标识取 `episode_id`，老数据退回 `id`／`episode`（与 `ui/desktop_audio_direct.py:63` 写入口径一致）。
- `程序/stage_execution_service.py:199-218`：新增 `_line_audio_batch`，`audio(project)/'配音分句'` 下按目录名倒序扫 `*/批次.json`（`file_cache.read_json`，坏清单跳过）；集标识命中的最新批次优先，否则只认无 episode 字段的旧批次，不跨集误配。
- `程序/stage_execution_service.py:221-233`：新增 `_line_manifest`，逐句清单读 `时间轴.json`，兼容 `lines`／`items`／`entries` 键封装。
- `程序/stage_execution_service.py:236-248`：新增 `_line_audio_paths`，筛 `domain.tts_api.line_done` 成品条目，按 (shot_id, text) 出现顺序一一消费配对（同镜同文本按次序，不重复用同一条），经 `_line_file_path` 定位文件。
- `程序/stage_execution_service.py:251-273`：新增 `_ffprobe_measurer`，读 `<项目>/config.json`（`file_cache.read_json`）后经 `platform_tools.tool_path('ffprobe', configured=...)` 解析；`agent.media.probe` 读 `format.duration`。
- `程序/stage_execution_service.py:276-300`：新增 `_resolve_line_audio_durations`：无批次、无对白、无成品配对 → `(None, None)` 保持原估算；有成品但没 FFprobe → `(None, '未配置 FFprobe')`；否则逐句实测（单句失败记 None 不中断），返回与 `timed_entries` 同序的时长列表。
- `程序/stage_execution_service.py:303-315`：`export_stage_srt(project, episode, *, probe_duration=None)` 增加仅关键字参数，两参调用完全兼容；`export_srt(..., audio=durations)`；`result.ok` 且有跳过原因时写 `report['audio_skip_reason']` 与 `report['source']['audio_skip_reason']`。
- `程序/orchestrator/media_page_controller.py:146-153`：`subtitle_status` 的 pending 分支：`mode=='mixed'` 且有 audio 时报「已按实际配音校准 %d 句，还有 %d 句未按实际配音校准，导出前请先听校。」；`audio_skip_reason` 非空时句中插「（原因）」；无原因时与原逐字一致。
- `程序/tests/test_subtitle_export_service.py:169-283`：新增 `StageSrtLineAudioTests` 六条（含 `import json`）。
- `程序/tests/test_media_page_controller.py:137-150`：新增 mixed 双句数文案与 skip_reason 文案两条（长度按 copy_rules 非空白 ≤45 字口径断言）。

## 验收命令与退出码

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k subtitle_export subtitle_calibration media_page_controller copy_rules` → 退出码 0

```
共 92 条用例，7.5 秒；0 个文件有红
最慢 8 路工作单元：
  test_copy_rules               4.2 秒 / 18 条
  test_subtitle_export_service#1    1.9 秒 / 6 条
  test_subtitle_export_service#2    0.9 秒 / 15 条
  test_subtitle_calibration#1    0.0 秒 / 16 条
  architecture.test_subtitle_export_publication_boundary    0.0 秒 / 3 条
  test_media_page_controller#1    0.0 秒 / 16 条
  test_media_page_controller#2    0.0 秒 / 8 条
  test_subtitle_calibration#2    0.0 秒 / 10 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：15.7 秒

ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0

```
----------------------------------------------------------------------
Ran 708 tests in 273.659s

OK
✅ 架构治理测试：tests/architecture
```

## 未验证

- `probe_duration` 注入缝以外的真实 FFprobe 链路未跑（本机测试不打桩真实 FFmpeg）；`agent.media.probe` 的 `format.duration` 解析与 `tool_path` 兜底逻辑按既有实现复用，真机可用性未实测。
- `字幕校准.json`（`export_calibration` 另写一份报告）不含 `audio_skip_reason`，卡面只要求写入返回报告；如需落盘该字段另行裁决。
- 旧编号目录 `10配音与字幕`（`stage_path_service.LEGACY_NUMBERED` 只读回退）下的历史逐句批次不扫描，卡面口径为 `audio(project)` 当前目录；运行态是否存在该形态未核实。
- 默认冒烟 `python smoke_test.py` 未单独跑（卡面未列）。
- `git status` 收尾核对在提交后记录。

## 待文档同步

- `程序/docs/stages/S11_配音与字幕.md`：REQ-S11-22 可同步——`export_stage_srt` 现按「当前集最近一批逐句配音成品 × FFprobe 实测时长」校准字幕，跳过原因写 `audio_skip_reason`；UX-S11-67 文案在 mixed 时改为「已按实际配音校准 N 句，还有 M 句未按实际配音校准」，缺 FFprobe 时附「（未配置 FFprobe）」。本卡不改阶段文档（禁止事项）。

## 卡外发现（只记录，不修）

- `desktop_script_pages.py:551` 的直连导出另有「对白时间暂按句长估算」状态文案，与 `subtitle_status` 口径相近但不同源；未要求统一，只记录。
- `批次.json` 的 `lines` 字段是句数（int）不是清单；逐句清单权威在 `时间轴.json`，卡面「兼容 lines/items/entries 键」已按 `时间轴.json` 封装字典兜底实现。

## 回滚

`git revert` 本轮提交。
