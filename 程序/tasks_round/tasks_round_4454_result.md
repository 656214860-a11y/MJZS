# R4454：SANHU-FIX-1B 返工：同步 test_stage_command_contract S-15-1 契约与 pet_poll_policy 防御加固
<!-- round-evidence: {"commit_base": "bd1587d77", "credential_hits": 0, "evidence_sha256": "1c88cf4b03a5b375", "exit": 0, "failed": 0, "passed": 191, "round": 4454, "tests": "run_selftests.py -k stage_command_contract sanhu_mode pet_agent desktop_automation_service copy_rules"} -->

- **轮次类型**：§3.2 修复轮（任务卡 `SANHU-FIX-1B` 第 1 轮返工，紧接分支 HEAD `bd1587d77`／原 R4447 `c3503cc83`）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 默认冒烟基线：`smoke_test.py` 通过 9/9（隐藏桌面探针 + 8/8 冒烟项，exit 0）。
  - 架构门禁：`smoke_test.py --architecture` 通过 708/708（0 失败，exit 0，与 R4447 708/708 持平）。
  - 定向自检：`run_selftests.py -k stage_command_contract sanhu_mode pet_agent desktop_automation_service copy_rules` 通过 191/191（0 失败，exit 0）。
  - 全量 `--all --safe`：未在本分支返工轮运行（按卡面验收口径，留待合入出口核验）。
- **欠账少了吗**：少了。清零独立复核实测出的 1 项 P1 阻断回归（`tests/test_stage_command_contract.py` 仍断言 S-15-1 改前静默吞错行为），并收紧 `ui/pet_poll_policy.py` 两处 P2 防御边界且补齐对应测试；未新增门禁欠账或放宽任何基线。
- **车道**：`codex/sanhu-fix-1b`（基准 `bd1587d77`），不合入、不 push。

## 改前先红原文

### 1. P1 阻断回归（改前 `run_selftests.py -k stage_command_contract`，exit 1）

```text
共 29 条用例，1.8 秒；1 个文件有红
### test_stage_command_contract（1 条红）

===== test_poll_switch_runs_once_before_wake_even_after_handled_error (test_stage_command_contract.DesktopBridgeActionTests.test_poll_switch_runs_once_before_wake_even_after_handled_error) (failure=OSError('write failed')) =====
Traceback (most recent call last):
  File "程序/tests/test_stage_command_contract.py", line 235, in test_poll_switch_runs_once_before_wake_even_after_handled_error
    self.assertIn(expected, self.host.pet_start('assets'))
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: '已经在跑' not found in '阶段未派发：write failed'
```

### 2. P2 防御加固先红（先增测、改 `ui/pet_poll_policy.py` 前 `run_selftests.py -k sanhu_mode`，exit 1）

```text
共 25 条用例，1.7 秒；1 个文件有红
### test_sanhu_mode（1 条红）

===== test_policy_defends_none_granted_and_non_paid_grants (test_sanhu_mode.SanhuSemiPollTests.test_policy_defends_none_granted_and_non_paid_grants) =====
Traceback (most recent call last):
  File "程序/tests/test_sanhu_mode.py", line 363, in test_policy_defends_none_granted_and_non_paid_grants
    self.assertFalse(pet_poll_policy.allowed('semi', 'manual', 'assets', granted=None))
                     ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "程序/ui/pet_poll_policy.py", line 47, in allowed
    return bool(aliases & {str(g).strip() for g in granted}
                                                   ^^^^^^^
TypeError: 'NoneType' object is not iterable
```

## 有意契约变更与改动明细（AGENTS §2.4）

1. **`程序/tests/test_stage_command_contract.py`（P1 契约同步，+20/-6）**
   - **契约变化说明**：R4447（SANHU-FIX-1B / S-15-1）有意将 `ui/desktop_pet_bridge.py:_execute_unattended_stage` 中 `UNATTENDED_SWITCH_SETTERS` 抛 `(OSError, ValueError, KeyError, TypeError)` 时的旧行为（静默吞错、继续调用 `pet_advance` 并谎报「已自动开始」或「已经在跑」）替换为显式失败回报 `'阶段未派发：' + str(exc)` 且中止唤醒，以便 `PetStagesMixin.start_stage` 发出 `stage.failed`。
   - **同步做法**（不弱化、不删除、不跳过，用例数 +1）：将原 `DesktopBridgeActionTests.test_poll_switch_runs_once_before_wake_even_after_handled_error` 拆分为两条语义准确的方法：
     - `test_poll_switch_runs_once_before_wake`：验证正常写开关分支（`failure=None`）在 `awakened='advanced'`（返回含 `'已自动开始'`）与 `awakened=''`（返回含 `'已经在跑'`）两种状态下，开关写入均先于 `pet_advance('assets')` 执行一次、`begin_run('assets')` 调一次、`_emit` 未调用。
     - `test_poll_switch_write_failure_stops_wake_and_reports_undispatched`：验证写开关抛 `OSError('write failed')` 时严格返回 `'阶段未派发：write failed'`、`setter` 仅调一次、`pet_advance.assert_not_called()`、`begin_run('assets')` 调一次、`_emit` 未调用。
2. **`程序/ui/pet_poll_policy.py`（P2 防御加固，+4/-3）**
   - `allowed(..., granted=())`：先做 `granted_items = tuple(granted or ())`，容忍 `granted=None`（及单次迭代器），不再抛 `TypeError`。
   - `grant_paid(host, stage)`：判断由 `if name:` 收紧为 `if name in PAID_SEMI_VARS:`，防止将 `NEVER_SEMI_VARS`／`FREE_SEMI_VARS` 或未知阶段名写入 `_auto_granted` 集合。
3. **`程序/tests/test_sanhu_mode.py`（P2 防御回归用例，+12/-0）**
   - 新增 `SanhuSemiPollTests.test_policy_defends_none_granted_and_non_paid_grants`：验证 `pet_poll_policy.allowed('semi', 'manual', 'assets', granted=None)` 返回 `False` 且不抛 `TypeError`；对 `'auto_submit'`／`'auto_review'`／`'final'`／`'unknown_stage'` 调用 `grant_paid` 均不污染 `pet_poll_policy.grants(self.pet)`，仅付费阶段 `'assets'` 写入 `{'auto_asset_var'}`。

## 改后验收命令退出码与输出尾部

### 1. 定向回归（exit 0）

命令：`run_selftests.py -k stage_command_contract sanhu_mode pet_agent desktop_automation_service copy_rules`（目录 `程序`）

```text
共 191 条用例，10.1 秒；0 个文件有红
最慢 10 路工作单元：
  test_copy_rules               4.7 秒 / 18 条
  test_sanhu_mode#2             1.0 秒 / 12 条
  test_sanhu_mode#3             0.7 秒 / 8 条
  test_desktop_automation_service    0.6 秒 / 15 条
  test_stage_command_contract#1    0.6 秒 / 13 条
  test_pet_agent_error_wiring    0.5 秒 / 10 条
  test_sanhu_mode#1             0.3 秒 / 5 条
  test_pet_agent#1              0.1 秒 / 16 条
  test_pet_agent#2              0.1 秒 / 15 条
  test_stage_command_contract#2    0.1 秒 / 16 条
实际跳过 0 条用例：本机没有任何登记位被跳过
最近 5 轮自检中位基线：10.7 秒

ALL TESTS PASSED
```

### 2. 架构门禁（exit 0）

命令：`smoke_test.py --architecture`（目录 `程序`）

```text
----------------------------------------------------------------------
Ran 708 tests in 379.561s

OK
✅ 架构治理测试：tests/architecture
```

### 3. 默认冒烟（exit 0）

命令：`smoke_test.py`（目录 `程序`）

```text
✅ 隐藏桌面可用（scripts/gui_hidden.py --probe）
...
==================================================
通过：9 项
失败：0 项
==================================================

✅ 冒烟测试通过，可以进入下一轮
```

## 待文档同步

本返工卡禁止修改阶段文档与 `project_status.md`，以下文档位置待后续文档同步轮更新半自动档轮询放行口径：

- `程序/docs/stages/S07_分镜定稿.md:35`（`REQ-S07-31`）：仍表述“仅当用户在定稿页显式勾选（`should_auto_run('final')`）”，待补充半自动档下 `final` 属 `FREE_SEMI_VARS` 免费轮询组、走手动控制面时仍放行。
- `程序/docs/stages/S12_后期剪辑.md:243`（`UX-S12-72`）：当前仅列“自动模式（全自动档）”下的 `poll_auto_edit`／`poll_auto_handoff`，待补充半自动档下 `edit`／`delivery` 免费轮询组放行说明。
- 其余涉及 `should_auto_run` 的免费／付费轮询组阶段文档（如 `auto_adopt`、`keyframe`、`previs`、`assets`、`video` 对应节）建议同批核对同步。
- `程序/project_status.md`：按 runbook §12 分支轮不改，由合并轮统一推进。

## 未验证项与卡外发现

- **未验证项**：全量 `run_selftests.py --all --safe` 未在本返工轮执行（卡面验收清单未要求）。
- **卡外发现**：工作树当前基准 HEAD 为 `bd1587d77`（原 R4447 `c3503cc83` 变基至 master `1abd6d878` 后的提交，改动内容一致），本轮直接在其上新增独立修复轮提交，未执行 reset／rebase／amend。
