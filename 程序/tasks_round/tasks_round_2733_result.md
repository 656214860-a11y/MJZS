# R2733 结果：T8.3 启动耗时趋势收口（黄金文件让位并行车道）
<!-- round-evidence: {"commit_base": "ec62c7cc", "credential_hits": 0, "evidence_sha256": "2576b70efb904d76", "exit": 0, "failed": 0, "passed": 9, "round": 2733, "tests": "run_selftests.py -k benchmark_trend"} -->

1. 轮次类型：功能轮（测试基建与 CI 告警默认类型；无产品行为变更、无契约变更）。
2. 测试：跑了。默认冒烟 8/8；定向全绿（明细见下）；架构门禁 466 条中本轮引入的
   1 条棘轮债已登记修复，其余 3 条失败为工作树环境性既有问题（见「架构门禁」节）。
   未跑 `--all --safe` 全量（分支轮不累计欠账，凭据口径见 runbook §4）。
3. 欠账：`project_status.md` 状态页欠账未变（仅 master 车道可提交状态页，
   轮次头由合并轮同步）；本轮无遗留欠账。

## 范围说明：黄金文件部分让位 R2702

- 本轮原计划交付 T8.2 黄金文件＋T8.3 趋势两个子项。黄金文件实现完成并
  全绿后，`dev.py commit` 的跨树范围扫描拦下 `tests/test_golden_outputs.py`
  与活跃分支 `codex/wip-R2702` 的 add/add 撞名。
- 核查 `codex/wip-R2702`（428045bf，基于更新的 a684ab97）：该车道已交付
  T8.2 黄金文件且覆盖更全（14 件基线、13 用例，含 asset_prompt_rules／
  shot_batches／storyboard_contract／字幕 SRT·ASS·校准报告／分镜批次表）。
- 处置：撤下本车道的黄金文件实现（test_golden_outputs.py＋tests/golden/
  9 件），保留趋势部分；两套黄金基建不并存（规则 28 一个动作一个入口）。
  本车道黄金实现曾独立验证同一批渲染口径（prompt_templates／
  subtitle_timing／animatic_service.shots_of），结论一致，可作 R2702 的
  交叉证据；其测试文件已注明「行尾按 \n 比较」，无需本车道 .gitattributes
  配合（已一并回退，保持最小改动）。

## T8.3 启动耗时趋势（写入＋CI 告警）

- `scripts/benchmark_trend.py` 新增启动耗时通道：common-dir
  `startup-perf-history.jsonl`（与 `full-safe-receipts.json` 同目录同模式，
  跨工作树共享；追加写＋60 条封顶）。`record_startup_perf(seconds, branch)`
  尽力归档、失败只提示不阻断；`startup_trend_report` 只同 branch
  （empty_project／first_day／same_day）互比，基线取此前最多 5 条中位，
  回退阈值与全量同为 ×1.25，只告警恒退 0。
- `tests/test_desktop_startup_perf.py` 三个计时用例在断言通过后记录实测秒数
  （empty_project／first_day／same_day）；`tests/test_benchmark_trend.py`
  新增 5 条用例覆盖读写、封顶、同分支告警与样本不足口径。
- 与任务书「写入 benchmark_history」的口径说明：`维护记录/基准历史.json`
  是离线基准归档且被 gitignore（含本机指纹），测试期写入会污染工作树且
  跨树不可比；CI 趋势数据改走 common-dir 运行时文件，与全量凭据同一权威
  位置，语义等价于「benchmark history」。
- `local_ci.py` 无需改动：其尾部已调用 `benchmark_trend.py`，启动段随
  main() 一并输出。
- `维护记录/架构统一基数.json` 第四项新增 exempt 登记 1 条：
  `load_startup_rows` 逐行解析 JSONL（追加式日志，file_cache 只读整文档
  JSON），与 skills `_load_jsonl` 同类豁免。

## 验证记录（本工作树 swe2-t8-gt，分支 codex/t8-golden-trend）

- 红→绿：benchmark_trend 新用例首跑 5 红（AttributeError）→ 实现 → 9 绿；
  （黄金文件红→绿过程见上节，已随撤下作废，不计入本轮交付。）
- `smoke_test.py`：8/8 通过。
- `run_selftests.py -k golden_outputs benchmark_trend subtitles prompt_templates
  animatic_service subtitle_export`：95 条全绿（golden_outputs 为撤下前
  的本车道版本；benchmark_trend/subtitles/prompt_templates/animatic/
  subtitle_export 各文件结论不受影响）。
- `run_selftests.py -k subtitle`：88 条全绿（含 test_subtitle_calibration、
  test_audio_subtitle_scope）。
- `run_selftests.py -k desktop_startup_perf`：14 条全绿（经 GUI 队列；
  期间实测写入 startup-perf-history.jsonl：empty_project 0.508s、
  first_day 0.758s、same_day 1.102s）。
- `scripts/dev.py arch`：466 条，失败 4 项——
  - `test_bare_json_load_debt…`：本轮新增 `load_startup_rows` 的逐行
    `json.loads` 未登记，已按 exempt 登记，单测复跑 4/4 绿；
  - 其余 3 条与本轮无关的环境性失败：`基准历史.json` 被 gitignore
    （干净工作树本无此文件）、`screenplay-gate-engine.md` 为本机未跟踪
    文件、`test_round_number_continuous` 因分支落后于 master 轮次簿记
    （本工作树最新结果 2681、状态页 2684，合并时由 master 车道对齐）。
- `scripts/dev.py lint`：ruff All checks passed；mypy 本机未安装
  （环境限制，非代码问题）。

## 改动清单

- `程序/scripts/benchmark_trend.py`：启动耗时历史读写、同分支趋势告警。
- `程序/tests/test_benchmark_trend.py`：+5 用例。
- `程序/tests/test_desktop_startup_perf.py`：3 处计时记录接入。
- `程序/维护记录/架构统一基数.json`：第四项 exempt 登记 1 条。
- `程序/tasks_round/tasks_round_2733_result.md`：本文件。
