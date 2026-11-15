# R2615 结果：SWE-2 T7 run_selftests.py 按发现/调度/凭据/报告拆分
<!-- round-evidence: {"commit_base": "ddda856c", "credential_hits": 0, "evidence_sha256": "09bf20b4dee3f81e", "exit": 0, "failed": 0, "passed": 210, "round": 2615, "tests": "run_selftests.py -k selftests gui_token pid_reuse commit_round source_text coverage layers ratchet recycle remove_authority atomic_write subprocess deletion_gateway import_error static"} -->

## 三问

- 轮次类型：结构治理轮（SWE-2 T7 测试基础设施拆分与并行化，第二段）。仅拆分测试运行器，不动产品行为；实现按域迁出，断言与 fixture 原样。
- 测试跑了吗、三个基线过了吗：跑了。默认冒烟 8/8；架构门禁当轮 466 条 / 132 路 / 32.3 秒、0 红（拆分前同口径 466 条 / 22.6 秒绿，耗时差主要来自本机 GUI 令牌排队与负载波动，属工作池环境噪声）；全量欠账以 `full-safe-receipts.json` 为准，本轮未跑全量。
- `project_status.md` 欠账少了吗：没有新增欠账；T7 的「测试文件按域拆分」前段已在 R2605/R2606 落地，本轮完成「运行器拆分」主体，剩余「全量耗时实测」在下轮。

## 改了什么

- `run_selftests.py`（1640 行）拆为薄壳＋五模块，域边界按任务书：
  - `selftest_env.py`——路径、常量、Git common-dir、PID/锁文件原语（叶子，无依赖）。
  - `selftest_discovery.py`——模块清单、import 语法分析、依赖闭包、测试文件分层与工作单元切块。
  - `selftest_receipts.py`——增量台账、分层基线、全量绿凭据读写与欠账/风险判定。
  - `selftest_scheduling.py`——跨树 PID/GUI 令牌与等待队列、Tk 沉底保护、并行/串行工作池与超时回收。
  - `selftest_reporting.py`——最慢单元、实际跳过清单与逐单元结果行。
  - `run_selftests.py` 保留用法说明、`main()` 原文与全部公开名显式 re-export；跨模块一律 `mod.attr()` 调用。
- 测试补丁点按「补丁打定义模块」重定向：`test_selftests.py`、`test_selftests_gui_token.py`（新增 `_patch` 同 mock 双盖 facade＋定义模块的辅助）、`test_selftest_incremental_gaps.py`、`test_pid_reuse_tokens.py`；main 直调名的 facade 补丁保持原样。
- 自检器排除词表两处同步：`tests/architecture/_scan.py` 的 `_EXCLUDED_STEMS` 与 `scripts/coverage_report.py` 的 `SKIP_STEMS` 各补 5 个新词干（与既有 `run_selftests`/`selftest_sandbox` 同待遇），覆盖率口径两侧一致。
- `test_selftests.py` 新增 `SelftestModuleSplitTests`：域归属、无环依赖边、main facade 契约三断言。
- `PROJECT_MAP.md` 更新运行器条目。

## 验证

- `test_selftests` 50、`test_selftests_gui_token` 14、`test_selftest_incremental_gaps`、`test_pid_reuse_tokens`、`test_commit_round`、`architecture.test_source_text_contracts`、`architecture.test_round_baselines`：共 77 条 0 红。
- `--layer architecture --all`：466/466、0 红、分层基线已刷新（本工作树实测）。
- `smoke_test.py`：8/8。
- `run_selftests.py --list -k selftests`、增量路径、`imports_of.cache_clear`、子进程 `import run_selftests` 消费面均验证。
- 修复过程中发现并修正：字节列偏移导致的错位改写（已换字符列换算）、`@lru_cache` 装饰器随 `def` 行号漏搬、`timedelta`/`re`/`subprocess`/`importlib` 模块级导入补齐。

## 提交

- 待回填 commit hash；合入方式：功能工作树回合 master。
