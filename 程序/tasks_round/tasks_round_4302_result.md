# R4302 FIX-PERF-ASSET-LOAD：资产页打开 CPU 倍数用例分诊与采样修正
<!-- round-evidence: {"commit_base": "755c7e9d0", "credential_hits": 0, "evidence_sha256": "de34ac3770aef7da", "exit": 0, "failed": 0, "passed": 12, "round": 4302, "tests": "run_selftests.py -k perf_baseline"} -->

## 三问
- 轮次类型：性能门禁修复轮（卡面 FIX-PERF-ASSET-LOAD / 波次 W2）。分诊结论：**负载敏感**，按需求设计卡面第 3 条只改采样口径，不动 `PAGE_OPEN_CPU_RATIO`／`PAGE_OPEN_LIMIT`／参考活任何阈值。
- 测试跑了吗、三个基线过了吗：跑了卡面两条验收，均退出码 0（`run_selftests.py -k perf_baseline` 12 条全绿、`smoke_test.py --architecture` 701 条全绿，见下）。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求）。
- 欠账少了吗：消除资产页打开用例在并行车道争用下的误报；无新增欠账。

## 分诊结论与数据
结论：**负载敏感**（非真实回退），走卡面设计第 3 步。

分诊方法：给用例挂临时取证（已在提交前撤掉），把每次 `(墙上ms, CPUms)`、参考活与比值追加写 `tasks_round/evidence/perf_asset_load_triage.jsonl`（已随本提交入库）。本机按卡面说明始终有其他车道并行跑测试，「空载」条件不成立，以下如实记为「当前负载下」；当时具体有哪些车道在跑**未核实**（进程枚举类命令被拒，见文末）。

当前负载下三遍（`run_selftests.py -k perf_baseline`，未改产品）：

| 时刻 | CPU 样本 ms | 参考活 ms | 最快比值 | 结果 |
|---|---|---|---|---|
| 13:29:23 | 781.2 / 312.5 / 312.5 | 39.1 | 8.0 | 过 |
| 13:31:01 | 859.4 / 390.6 / 328.1 | 41.0 | 8.0 | 过（同趟 `test_p95_local_ops` 红，见卡外发现） |
| 13:33:00 | 1296.9 / 593.8 / 546.9 | 41.0 | **13.333** | **红——缺陷复现** |

重载一遍（同时跑 `smoke_test.py --architecture`；卡面示例 `-k pet_ui` 全是 Tk 用例，会被跨树 GUI 令牌串行排队、测不到并发，故改用非 Tk 的架构门禁制造真 CPU 争用）：

| 时刻 | CPU 样本 ms | 参考活 ms | 最快比值 | 结果 |
|---|---|---|---|---|
| 13:35:17 | 828.1 / 312.5 / 359.4 | 37.1 | 8.421 | 过 |

改后实测（修复代码、架构门禁并发中，取证桩记录）：rounds=1，CPU 859.4 / 328.1 / 343.8，参考活 39.1，最快比值 **8.4**，过。

判负载敏感的依据：
1. 同一份代码四次采样比值 8.0 / 8.0 / 13.3 / 8.4，红绿随并行争用波动，不是恒定超线；红的那次三次采样 CPU 全部偏高（1296.9 / 593.8 / 546.9），是约 2 秒级的持续争用而非单次尖刺。
2. 资产页打开 CPU 绝对值 312–550 ms 与 `test_perf_baseline.py:64-66` 注释口径「满速 ~0.35 s」一致，没有新增耗时的证据；cProfile 对比未做（判为非回退后不需要）。
3. 参考活实测 37–41 ms，低于注释口径 ~80 ms（本机当前更快＋REL-07 的八份均值量化修正），同样工作量下比值结构性偏高，10 倍线余量本就只剩约 25%。
4. 旁证：`tasks_round_4289_result.md` 已记录同一用例在并行车道下抖动红 12.19–12.4（限 10），并建议「后续性能卡评估加重试」——本卡即该建议的落地。

## 缺陷复现 / 改前红
分诊第 3 遍（13:33:00）在未改产品状态下复现卡面红，原文：

```text
AssertionError: 13.333333333333334 not less than 10.0 : 资产页打开最快 546.9 ms CPU＝参考活（41.0 ms）的 13.3 倍（限 10.0 倍）；墙上 最快 534.6／中位 649.5 ms（参考线 1200）；三次 (墙上, CPU)=[(1068.5, 1296.9), (649.5, 593.8), (534.6, 546.9)]
```

先红后绿（采样桩，`collect_page_open_samples` 先按旧语义只采一轮 3 次）：

```text
===== test_page_open_sampling_recovers_when_a_later_round_is_quiet =====
AssertionError: 1 != 2
===== test_page_open_sampling_still_fails_when_every_round_is_over =====
AssertionError: 1 != 4
```

共 2 条红，原因一致：采样函数没有「超线再采」能力——正是卡面缺陷（单次/单轮争用顶线即红）。改成超线最多再采 3 轮后同两条转绿。

## 改了哪几处（均在 `程序/tests/test_perf_baseline.py`）
- `:170-171` 新增 `PAGE_OPEN_SAMPLE_ROUNDS = 3`（每轮采样次数）、`PAGE_OPEN_EXTRA_ROUNDS = 3`（超线最多再采轮数）。
- `:174-188` 新增 `collect_page_open_samples(sample_once, speed_ms)`：每轮采 3 次；全程最快 CPU ÷ 参考活仍 ≥ `PAGE_OPEN_CPU_RATIO` 时再采一轮，最多加采 `PAGE_OPEN_EXTRA_ROUNDS` 轮（合计至多 4 轮 12 次），返回 `(samples, cpu, ratio, rounds)`。
- `:191-204` 新增 `assert_page_open_within_limit(case, ...)`：判定仍是 `ratio < PAGE_OPEN_CPU_RATIO`；断言文案写明「共采 N 轮×3 次（首轮最快超线时最多再采 3 轮，取全程最快）」，采样次数上限进文案。
- `:416-424` `test_the_asset_page_opens_under_the_limit` 改走上述两函数；`PAGE_OPEN_CPU_RATIO=10`、`PAGE_OPEN_LIMIT=1200`、`machine_speed_ms()` 均未动。
- `:426-448` 新增两条桩用例：`test_page_open_sampling_recovers_when_a_later_round_is_quiet`（第一轮超线、之后低于线 → 通过，断言 rounds=2、样本 6 条）、`test_page_open_sampling_still_fails_when_every_round_is_over`（全程超线 → 仍红，报出 15.0 倍与 4 轮）。
- `程序/perf_baseline.py` 未建未改：该文件在允许清单里但仓库中不存在，改动全部落在允许清单内的测试文件，未新建产品模块。

## 验证命令与结果
Python 命令工作目录均为 `程序`，逐条单独执行（PowerShell）。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k perf_baseline`
   - 改前（桩测试红态）：退出码 1，12 条中 2 条红（见上）。
   - 改后最终代码（与架构门禁并发跑）：退出码 0，尾部原文：
     ```text
       test_perf_baseline            12 条    88.5 秒
     共 12 条用例，89.4 秒；0 个文件有红
     最慢 1 路工作单元：
       test_perf_baseline           88.5 秒 / 12 条
     实际跳过 0 条用例：本机没有任何登记位被跳过
     增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
     最近 5 轮自检中位基线：83.9 秒
     ALL TESTS PASSED
     ```
   - 条数核对：改前 10 条 → 改后 12 条（+2 条新桩用例），其余用例原样通过。
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：退出码 0，尾部原文：
   ```text
   ----------------------------------------------------------------------
   Ran 701 tests in 215.717s
   OK
   ✅ 架构治理测试：tests/architecture
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4302`。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4302: FIX-PERF-ASSET-LOAD 修复" tests/test_perf_baseline.py tasks_round/tasks_round_4302_result.md tasks_round/evidence/perf_asset_load_triage.jsonl --tests perf_baseline`（文件参数按 `程序` 目录相对路径；`--tests` 放文件参数之后）。
- 提交哈希以完成报告与 `tasks_round/evidence/R4302.json` 回执为准，不在本文件自引用。
- 回滚：`git revert` 本提交。

## 未验证项 / 未核实
- 本机始终有其他车道并行，未获得真空载对照；若某时段争用持续超过全部 12 次采样（约 7–9 秒墙钟）仍可能红——这是设计内行为（持续真退化仍应拦）。
- 改后真实采样只观察到 rounds=1 的通过路径（首轮即在线内）；再采路径由两条桩用例覆盖，未在真实争用下触发过超线再采。
- 当时并行车道的具体清单未核实（进程枚举命令被拒）。
- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面验收未要求）。
- 未合入、未 push。

## 卡外发现（只记录，未顺手修）
- `test_p95_local_ops_stays_within_baseline` 在并行争用下红过一次（分诊第 2 遍）：`open_project P95 571.9 ms 超基线 361.6 ms 的 20%（限 433.9 ms）`。同为负载敏感型抖动（P95 对争用更敏感），不在本卡允许范围，建议另卡评估采样口径。
- 既有注释（`test_perf_baseline.py:61-66`）记载的参考活口径 ~80 ms 与本机实测 37–41 ms 差约一倍，比值门槛的实际余量比设计时更薄；是否需要重标定口径留给后续性能卡，本卡按禁令不动阈值。

## 被拒绝的命令（原文）
- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k perf_baseline`（首次在 bash 会话执行，反斜杠被转义成 `........运行环境Pythonpython.exe: command not found`，退出码 127；改用 PowerShell 后正常）
- `ls "D:\漫剧制作助手\.agents\worktrees\fix-perf-asset-load\程序"`（工具调用被拒，改用文件名 glob）
- `git ls-files | findstr /I "perf_baseline"`（管道被拒）
- `git show e3309b43:"程序/docs/records/会话接续记录.md" | Select-Object -Last 80`（管道被拒，改用 read 工具）
- `(Get-Content -Encoding UTF8 "...会话接续记录.md" | Measure-Object -Line).Lines`（管道被拒）
- `Test-Path "D:\漫剧制作助手\运行环境\Python\python.exe"`、`Get-Process python ...`、`Start-Sleep -Seconds 20`（探测类命令被拒，改用卡面指定命令与文件工具）
