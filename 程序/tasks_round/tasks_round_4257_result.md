# R4257 FIX-AUD-US03-SG01：SG-01 资产门禁与清单口径不一致（修复轮）
<!-- round-evidence: {"commit_base": "79fa309b", "credential_hits": 0, "evidence_sha256": "909068c243acb48e", "exit": 0, "failed": 0, "passed": 76, "round": 4257, "tests": "run_selftests.py -k stage_parallel stage_gate_modes asset_plan"} -->

## 三问
- 轮次类型：§3.2 修复轮（卡面 FIX-AUD-US03-SG01，波次 W2，车道 `codex/fix-aud-us03-sg01`，基准 `79fa309b`）。
- 测试跑了吗、三个基线过了吗：跑了卡面指定验收。定向 `run_selftests.py -k stage_parallel stage_gate_modes asset_plan` 改前 1 条红、改后 76 条全绿退出码 0；`smoke_test.py --architecture` 700 条全绿退出码 0。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求，且禁止运行卡面未写的命令）。
- 欠账少了吗：少了「SG-01 与资产页口径不一致」这条审查欠账（AUD-US03 D1）；无新增欠账。

## 范围与缺陷
- 开工三查：`git status --porcelain` 无输出、`git log -1 --format=%h` 输出 `79fa309b`、分支 `codex/fix-aud-us03-sg01`。
- 缺陷：`orchestrator/stage_parallel.py` 的 `assets_locked` 遍历 `assets/资产清单/assets.json` 全量条目做「没导入图片／未锁定锚点／无锚点字符串」检查，不过滤 `requires_asset=false`（背景人物、普通道具）；资产页 `domain/asset_plan._sync_plan` 的 rows 在 `domain/asset_plan.py:180` 用 `contract.prop_assets.requires_asset` 把这类条目过滤掉，用户在资产页看不到也删不掉它们 → SG-01 永久挡住进入连贯性（审查 AUD-US03 D1，验收窗口 `stage_parallel.py:688-745` 与 `asset_plan.py:170-200`，经读码核实：`assets_locked` 改前无 `requires_asset` 引用）。
- 只改门禁侧，与卡面一致。

## 缺陷复现
新增测试 `tests/test_stage_parallel.py::GateTests.test_hidden_assets_do_not_block_the_continuity_step`：夹具用 `make_minimal_project`，清单里 CHAR_001 全到位（库内真实图片文件＋`locked`＋`character_anchor`），CHAR_009 `requires_asset=false` 背景人物与 PROP_009 `requires_asset=false` 普通道具均无图无锁无锚点。改前 `evaluate(proj,'continuity')['ok']` 为 False（这两条不可见条目被算成「没到位」，问题文本含 CHAR_009／PROP_009），改后为 True 且 `blocked_stages` 为空。

## 改前红（退出码 1，1 条红 / 共 76 条）
命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_parallel stage_gate_modes asset_plan`（工作目录 `程序`）

```text
  test_stage_parallel#2         13 条     2.7 秒  ✗ 1
共 76 条用例，784.9 秒；1 个文件有红
```

红因原文（与缺陷一致）：

```text
### test_stage_parallel（1 条红）

===== test_hidden_assets_do_not_block_the_continuity_step (test_stage_parallel.GateTests.test_hidden_assets_do_not_block_the_continuity_step) =====
Traceback (most recent call last):
  File "...\tests\test_stage_parallel.py", line 410, in test_hidden_assets_do_not_block_the_continuity_step
    self.assertTrue(result['ok'])
AssertionError: False is not true
```

（首轮在跨树 GUI 令牌处排队约 720 秒属运行器正常等待，与断言无关。）

## 改动内容（文件:行号）
- `orchestrator/stage_parallel.py:693`：`assets_locked` 函数内补 `from contract.prop_assets import requires_asset`（沿用本文件函数级 import 风格；L3→L0 同向，与 `:787` `contract.shot_batches` 先例一致）。
- `orchestrator/stage_parallel.py:708-709`：`rows` 先按 `requires_asset` 过滤，再做 missing／未锁定／无锚点／touched 统计，与 `domain/asset_plan.py:180` rows 同口径；非 dict 条目保留，仍按旧行为计入「没导入图片」，不放宽对畸形数据的拦截。
- `tests/test_stage_parallel.py:392-413`：新增上述回归测试（临时目录夹具，无 Tk、不触用户项目库）。

## 验证命令与结果
Python 命令工作目录均为 `程序`，逐条单独执行。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_parallel stage_gate_modes asset_plan`（改前）：退出码 1（1 条红，见上）。
2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_parallel stage_gate_modes asset_plan`（改后）：退出码 0，尾部原文：
   ```text
   共 76 条用例，2.1 秒；0 个文件有红
   实际跳过 0 条用例：本机没有任何登记位被跳过
   增量台账已刷新：...\.git\selftest-incremental.json
   最近 5 轮自检中位基线：9.1 秒

   ALL TESTS PASSED
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：退出码 0，尾部原文：
   ```text
   ----------------------------------------------------------------------
   Ran 700 tests in 254.526s

   OK
   ✅ 架构治理测试：tests/architecture
   ```
4. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4257`。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4257: FIX-AUD-US03-SG01 修复" orchestrator/stage_parallel.py tests/test_stage_parallel.py tasks_round/tasks_round_4257_result.md --tests stage_parallel stage_gate_modes asset_plan`（文件参数按 `程序` 相对路径给出；`--tests` 为 `nargs='*'` 须放在文件参数之后；改了 `.py` 须带 `--tests` 生成 `tasks_round/evidence/R4257.json`，否则证据门禁判「未跑定向测试」拒绝）。
- 提交哈希以完成报告与证据回执为准，不在本文件自引用。

## 未验证项 / 未核实
- 全量 `run_selftests.py --all --safe` 与默认冒烟未跑（卡面验收未要求且禁止运行卡面未写的命令）。
- 定向范围外直接引用 `assets_locked` 的测试：`tests/test_assets_scope.py`（5 处直接调用）、`test_continuity_scope.py:33`、`test_req_s07_anchors.py:531`——经读码核对，其夹具条目均无 `requires_asset=false`、后两处仅核对门禁注册表（id/from/to/check 名），行为不受影响；未实测（不在卡面命令内）。
- 未合入、未 push；合入由合并车道按正式流程处理。

## 被拒绝的命令（原文，均未重试，改用文件检索工具完成）
- `Get-ChildItem -Name <工作树>\程序\tests\ | Select-String -Pattern "stage"`（列测试目录）
- `Get-ChildItem "<工作树>\程序\tasks_round" -Filter "tasks_round_42*_result.md" | Sort-Object Name -Descending | Select-Object -First 3 -ExpandProperty Name`（找结果文件模板）
