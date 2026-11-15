# R2600 结果：SWE-2 优化清单 T5——静默异常核销首批（3 模块）
<!-- round-evidence: {"commit_base": "4ee740d0", "credential_hits": 0, "evidence_sha256": "9da370bbf8495e9a", "exit": 0, "failed": 0, "passed": 101, "round": 2600, "tests": "run_selftests.py -k test_selftests test_auto_full_safe test_swallowed_cleanup architecture.test_silent_exception_ratchet"} -->

1. 轮次类型：结构治理轮（§3.3，最多 3 个模块，本轮改 run_selftests、smoke_test、scripts/auto_full_safe）。
2. 三个基线：默认冒烟 8/8；`--affected run_selftests smoke_test auto_full_safe` 9/9；架构门禁 466/466（改前基线同 466——首轮 2 红均为新工作树环境缺口：gitignored `维护记录/基准历史.json` 与 4 个未初始化 gitlink 技能包，从主工作区补齐后全绿）。全量未触发（欠账口径见 runbook §4）。
3. 欠账：静默异常棘轮登记位 14→11（实站点 15→11，含扫描面外已修复的 auto_full_safe:462），`scripts/` 纳入扫描面。

## 全树盘点（AST，与棘轮同口径＋旁证）

- `except Exception: pass`（棘轮口径）生产+agent+scripts 共 15 处，本轮全部核对分类；裸 `except:` 0 处（R2555 门禁已禁）；窄异常 `except X: pass` 245 处属预期控制流，任务书口径外，只记录。
- 范围外只记录：`tests/` 约 90 处（测试夹具/teardown 惯例）、`维护记录/基准脚本/` 4 处（一次性基准脚本）、`except Exception:` 带非 pass 体 824 处（有日志或返回值，不算静默）。

## 三类标注与处置

| 站点 | 分类 | 处置 |
| --- | --- | --- |
| `run_selftests.py` 1268（worker 清理） | 应记录 | 改 `app_logging.swallowed('清理缩略图工作单元')` |
| `run_selftests.py` 1016（Tk 窗口下沉） | 应记录 | 改 `app_logging.swallowed('测试窗口下沉')` |
| `smoke_test.py` 186（Tk 根销毁收尾） | 应记录 | 改 `app_logging.swallowed('销毁 Tk 根')` |
| `scripts/auto_full_safe.py` 462（--notice 附加提示） | 应记录 | 改 `app_logging.swallowed('--notice 附加提示')`，此前在棘轮扫描面外 |
| `app_logging.py` ×10 | 可忽略·基建 | 日志基建自身不能递归记日志，保留登记位 |
| `agent/volcengine.py` ×1 | 可忽略·边界 | agent 子包零依赖（全包不引 app_logging），错误路径随后仍 `raise ArkRejected`，保留登记位 |
| 应上抛 | 无 | 无站点隐藏真实失败契约 |

## 先红后绿

- 新增断言改动前失败：`test_cleanup_failure_leaves_swallowed_trace`、`test_notice_failure_leaves_swallowed_trace`、`test_widget_check_destroy_failure_leaves_trace` 均报 `0 not greater than 0`。
- 转换后全绿；棘轮 `test_allowlist_has_no_stale_entries` 在下调登记前先红、下调后绿（证明真实消减非只改数字）。

## 断言与范围说明

- 断言未动：既有 `test_notice_flag_prints_and_never_fails`、`test_cleanup_resets_thumbnail_worker` 原样保留。
- 新增 `tests/test_swallowed_cleanup.py`（函数内 `import tkinter`，`gui_test_module` 自动归入 gui 车道）。
- `agent/volcengine.py` 未转：`agent/` 全包不引 app_logging，引入会越过既有依赖边界，留登记位。
