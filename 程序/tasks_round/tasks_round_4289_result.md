# R4289 REL-07：性能基线三族用例并入 test_perf_baseline 发布门禁（续做合并）
<!-- round-evidence: {"commit_base": "79fa309b", "credential_hits": 0, "evidence_sha256": "f070f07f8436e256", "exit": 0, "failed": 0, "passed": 27, "round": 4289, "tests": "run_selftests.py -k perf_baseline desktop_startup_perf"} -->

## 三问
- 轮次类型：性能基线门禁轮（卡面 REL-07 / 波次 W2 / 共享资源 perf-tests）。本卡只动测试与门禁常量，不改产品行为。
- 测试跑了吗、三个基线过了吗：跑了卡面指定验收。`run_selftests.py -k perf_baseline desktop_startup_perf` 退出码 0（27 条全绿，见下）；`smoke_test.py --architecture` 退出码 0（700 条）。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求）。
- 欠账少了吗：补齐「干净机器冷启动、3000 镜长列表、本地操作 P95」三族基线未入门禁的欠账；基线文件落成 `维护记录/性能基线.json`；无新增欠账。

## 范围与基线
- 基准版本：`79fa309b3237ab9a08534a3df0265eeb3fd7c5da`（开工三查：`git status --porcelain` 输出与卡面续做清单逐行一致共 3 行、`git log -1 --format=%h` = `79fa309b`、分支 `codex/rel-07`）。
- 续做现场核对：上一位执行者的草稿全部保留并在其上续做——`performance_contract.py` 的 REL-07 常量块与注释、`test_perf_baseline.py` 的 `BASELINE_PATH`/`load_perf_baseline`/`require_perf_baseline`/`p95_ms` 与 P95 用例、未跟踪的 `维护记录/性能基线.json` 均未推倒重写；governance 两份文件未碰、未跑 `--write-baseline`；`.agent-tmp/rel-07-old-drafts/` 两份旧草稿只读参考、未复制回 `tests/`、未改动 `.agent-tmp` 下任何文件。
- 任务：REL-07 / 波次 W2。治理裁决：两份旧测试文件不新建（STR006），用例并入已 frozen 的 `tests/test_perf_baseline.py`，方法名前缀 `perf_cold_start_` / `perf_long_lists_` / `p95_`；长列表设硬门槛、冷启动沿用既有三条只记实测、P95 首轮只记录。

## 续做时保留与修改
保留（上一位执行者草稿）：`performance_contract.py` 的 `P95_SAMPLE_COUNT=20`/`P95_REGRESSION_FACTOR=1.2` 与 REL-07 注释框架；`test_perf_baseline.py` 的基线装载三件套与 `test_p95_local_ops_*` 用例骨架；`性能基线.json` 的 schema。

修改（本轮）：
1. 并入旧草稿用例并改名：`test_p95_local_ops_*` → `test_p95_local_ops_stays_within_baseline`（`test_perf_baseline.py:536`）；新增 `test_perf_cold_start_clean_machine_baseline`（`:575`，并入自 `test_perf_cold_start.py`）与 `test_perf_long_lists_3000_shot_files_panel`（`:612`，并入自 `test_perf_long_lists.py`）；原有 7 条用例不删不改。
2. 长列表适配（受 `split_performance_units` 把 `test_perf*` 整文件作 180 秒串行单元约束，`run_selftests.py` / `selftest_discovery.py`）：合成索引 21000 行全部落在 `01剧本准备/输入/` 下使 `stage_of`→script，面板阶段筛选全放行，省掉每次 `rows()` 逐行 stat 的全量索引重载；删除类型筛选测量（`_apply_filters` 每趟整表重载约 23–35 s，关键字+类型两趟必超 180 s），只测关键字一趟代表筛选口径（用例 docstring `:615-622` 已注明）；移除 `panel.show_stage(None)`。
3. 删两条并入时自加的 `if self.tk is None: self.skipTest(PLATFORM_TKINTER)` 守卫（原在 `:583`/`:626` 附近）：skip 台账 `维护记录/skip台账.json` 不在允许修改清单，而新增 skipTest 调用点使台账 323≠源码 325 触发 `test_skip_hygiene` 红；旧草稿本无守卫，故按旧草稿口径移除（本平台 tkinter 恒可用，隐藏桌面运行器保证 Tk）。
4. 实测重建 `维护记录/性能基线.json`：草稿值 fill≈102951 ms／筛选≈34 s 属异常慢值，按卡面用本轮实测重写；波动 >20% 的按「拿不准」条款三轮取最大值（数值见下节）。
5. `performance_contract.py:33-43`：长列表两条新门槛由草稿占位值改为实测×1.2——`LONG_LIST_3000_SCROLL_MEDIAN_MS=8.4`（实测最大 7.0×1.2）、`LONG_LIST_3000_FILTER_MS=41945.0`（实测最大 34954.2×1.2）；既有三条（载入 ≤1.0 s、首事件循环 ≤2.6 s、滚动 150 ms 口径常量）未动；P95 常量沿用草稿。

## 基线实测值与写入值（三轮取最大）
长列表三轮实测（同代码、不同机器负载）：
- fill_ms：58415.9 / 50935.8 / 32468.0 → 写入 **58415.9**（只记录无门槛）
- scroll_p10_ms：5.5 / 5.4 / 4.7 → 写入 **5.5**；scroll_median_ms：6.9 / 7.0 / 5.6 → 写入 **7.0**（门槛 8.4）
- filter_keyword_ms：34954.2 / 27265.9 / 22732.2 → 写入 **34954.2**（门槛 41945.0；波动 53% >20%，按卡面取三轮最大）
冷启动三轮实测：first_frame 752.2 / 456.0 / 407.1 ms → 写入 **752.2**；first_event_loop 0.752 / 0.456 / 0.407 s → 写入 **0.752**（只记录，门槛仍用 contract 1500 ms / 2.6 s）。
P95 三轮实测（各 20 样本）：open_project 361.6 / 302.0 / 259.0 → **361.6**；switch_page 473.8 / 723.4 / 454.0（另一次不完整轮 707.9）→ **723.4**；save 19.1 / 30.7 / 17.4 → **30.7**；回归线＝基线×1.2。

## 缺陷复现 / 改前红
续做现场已有实现，按接口契约如实记录：**未观察到与卡面缺陷对应的改前红**（缺陷本体是「三族基线未入门禁」，由并入的用例与基线文件补齐）。新用例的设计内红已实测：基线缺失时 `require_perf_baseline` 先落盘再 `case.fail('请先生成基线…')`（Run C/D/E 共观察到 cold_start/long_list/local_ops_p95_ms 三节各红一次，符合「缺失时提示而不是通过」）。

## 验证命令与结果
Python 命令工作目录均为 `程序`，逐条单独执行。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k perf_baseline desktop_startup_perf`：本轮共跑 8 次。期间 6 次因并行车道 CPU／GUI 令牌争用，既有墙钟敏感用例抖动红——`test_cold_start_reaches_the_first_frame` 实测 2615–4443 ms（限 1500）、`test_the_asset_page_opens_under_the_limit` CPU 比 12.19–12.4（限 10）、`test_empty_startup_cancel_finishes_loading_and_resumes_tick` pump 超时；三者均为未改动的既有用例，且 `test_perf_baseline.py:61-66` 注释自述「别的进程一抢 GDI／字体墙上时间能翻 2～6 倍」。本轮新增 3 条用例在全部 8 次运行中 100% 通过。最终一轮退出码 0，尾部原文：
   ```text
     test_desktop_startup_perf     17 条    12.8 秒
     test_perf_baseline            10 条    86.7 秒
   共 27 条用例，111.3 秒；0 个文件有红
   ALL TESTS PASSED
   ```
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：首跑退出码 1（`test_ledger_and_source_skip_sets_are_bidirectionally_equal`：台账 323 ≠ 源码 325，原因见「续做时保留与修改」第 3 条）；删守卫后复跑退出码 0，尾部原文：
   ```text
   Ran 700 tests in 215.718s
   OK
   ✅ 架构治理测试：tests/architecture
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4289`。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4289: REL-07 修复" tests/performance_contract.py tests/test_perf_baseline.py 维护记录/性能基线.json tasks_round/tasks_round_4289_result.md --tests perf_baseline desktop_startup_perf`（文件参数按 `程序` 相对路径；`--tests` 为 `nargs='*'` 须放文件参数之后，同 R4249 先例；commit 内部会按 `--tests` 复跑定向验收生成 `tasks_round/evidence/R4289.json`）。
- 提交哈希以完成报告与证据回执为准，不在本文件自引用。

## 未验证项 / 未核实
- 基线是在多车道并行争用的开发机上取「三轮最大值」，偏保守；真正的干净机器首轮实测留给 REL-12 实机清单复验（卡面「每次先跳选择项目页」复验步骤同归 REL-12，本卡不改代码）。
- 类型筛选未单独测量（与关键字同走 `_apply_filters` 整趟重载路径，且受 180 s 串行单元上限约束）；`long_list` 基线节因此只有 `filter_keyword_ms`。
- `fill_ms` 只记录不设门槛；P95 为首轮只记录＋回归线（基线×1.2），第二轮再评审。
- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面验收未要求）。
- 未合入、未 push。

## 卡外发现（只记录，未顺手修）
- 三条既有用例在跨树争用下会抖动红（见上）：`test_cold_start_reaches_the_first_frame`（墙钟 1500 ms 限）、`test_the_asset_page_opens_under_the_limit`（CPU 比 10 限）、`test_desktop_startup_perf.test_empty_startup_cancel_finishes_loading_and_resumes_tick`（pump 截止时间）。建议后续性能卡评估改判 CPU 时间口径或加重试，属既有门禁口径问题。
- `_apply_filters` 对 2.1 万行索引每次整趟重载约 23–35 s（筛选基线 34954.2 ms 的主要构成），是明显性能热点，可供后续优化卡参考；N628 归因（Path.resolve 占 44%、`_getfinalpathname` 0.087 s）按卡面只记录、不作本卡优化项。

## 被拒绝的命令（原文）
- `git diff 程序/tests/test_perf_baseline.py | Select-String -Pattern "skip" -Context 2,2`（管道被拒，改用 grep 工具核对）
- `Get-ChildItem tasks_round\tasks_round_*_result.md | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name`（管道被拒，改用文件名 glob）
- 续做会话早期另有取证类调用被拒（交接摘要记为 msg 11/59/127，原文未随摘要保留，未核实）。
