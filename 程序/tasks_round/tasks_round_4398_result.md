# R4398 结果：S04-REF-LIBRARY 分镜预演参考库（REQ-S04-70~73）
<!-- round-evidence: {"commit_base": "67fd96c99", "credential_hits": 0, "evidence_sha256": "352082513c54cd66", "exit": 0, "failed": 0, "passed": 43, "round": 4398, "tests": "run_selftests.py -k animatic_references req_s04_anchors animatic_service"} -->

## 开头三问

1. **本轮类型**：功能轮（§3.1）。卡面 S04-REF-LIBRARY（波次 W2，车道 `codex/s04-ref-library`，基准 `67fd96c9`）：为分镜预演建共享参考库——导入图按文件名自动归 角色/场景/风格 子目录（同名既是角色又是场景时归角色），每镜按 characters/location 自动配图，旧根目录未分类图只读兼容不搬动，支持单图改类／改名。本卡为续跑接管：上一会话已完成全部功能代码与 17 条先红后绿新测试、定向 43/43 绿、架构门禁绿；本会话只补覆盖率基线机械刷新、runbook §11 数字同步、复跑两条验收命令、领号与提交，未动已实现代码。
2. **测试与三个基线**：`run_selftests.py -k animatic_references req_s04_anchors animatic_service` 43 条 0 红、退出码 0；`smoke_test.py --architecture` 708 条 OK、退出码 0。默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面验收未列）。
3. **欠账少了吗**：少了。REQ-S04-70~73 落地并全绿，覆盖率基线与 runbook §11 口径随新模块同步；未登记新欠账。

## 缺陷复现方式（先红证据）

上一会话按先红后绿执行：新测试 `tests/test_animatic_references.py` 先提交时 `domain.animatic_references` 尚不存在，定向命令 `run_selftests.py -k animatic_references req_s04_anchors animatic_service` 结果为 **1 红 / 26 绿**，失败原因为 `ModuleNotFoundError`（测试文件导入 `domain.animatic_references` 失败，按文件计 1 红；其余两个测试文件 13+13=26 条绿）。该原始输出属上一会话记录（卡面续跑说明转述），本会话接手时产品代码已就位，未复核改前原始输出。

## 改了哪几处（文件:行号）

**上一会话完成（本会话核对后全部保留）**：

- `程序/domain/animatic_references.py`（新，114 行，L2 纯函数）：常量 `CATEGORIES=('角色','场景','风格')`、`UNCATEGORIZED='未分类'`、`IMAGE_SUFFIXES`、`MAX_IMAGE_BYTES=20MB`（`animatic_references.py:7-10`）；`normalize_name` NFKC→去扩展名→首个 `_`/`-` 前段（:13-16）；`classify` 角色优先于场景、否则归风格（:19-28）；`library` 扫读目录分四类、库根与旧目录图归未分类、按路径去重（:31-46）；`refs_for_shot` 命中角色图＋场景图＋全部风格图，全空退回未分类（:49-71）；`import_plan` 校验后缀与大小、sha256 内容去重、同名 `名(2)` 编号（:74-103, :106-114）。
- `程序/orchestrator/stage_animatic_gateways.py:175-240`（+66）：四个 L3 网关——`animatic_reference_library`（库视图，读目录经 `shared_reference_read_dirs`）、`import_animatic_reference_library`（导入计划→越界校验→`publish_stage_bundle` 原子发布）、`refs_for_animatic_shot`（按镜配图）、`reclassify_animatic_reference`（单图改类／改名：源目标均在库内校验、`publish_stage_bytes` 原子写新路径、旧文件经 `storage_maintenance.recycle_paths` 退役）。
- `程序/stage_execution_service.py:33`：re-export 行并入 `animatic_reference_library`、`import_animatic_reference_library`、`reclassify_animatic_reference`、`refs_for_animatic_shot`。
- `程序/tests/test_animatic_references.py`（新，256 行，17 条）：`NormalizeAndClassifyTests` 3 条、`ImportPlanTests` 7 条、`LibraryAndShotRefsTests` 3 条、`GatewayTests` 2 条、`ReclassifyTests` 2 条；只用临时目录，不开 Tk。
- `程序/tests/architecture/_layers.py:46`：`animatic_references` 登记入 L2。
- `程序/维护记录/架构统一基数.json`：`entity_paths` 增加 `animatic_references`（:6）、`exempt_count` 56→57（:103）、`exempt_items` 追加 `animatic_references`（:160）。

**本会话完成**：

- `程序/维护记录/覆盖率基线.json`：`scripts\coverage_report.py` 对原 15 个核心定向目标机械刷新，`tests_ok=true`，`modules_total` 682→683（新增 `domain/animatic_references.py`）、`modules_covered` 133 不变、未触达 549→550（文件末尾 :4120-4121）。
- `程序/runbook.md:181,183,186`（仅 §11）：682→683、549→550、引例「542 个模块覆盖率 0」→550、「整仓覆盖率 19.7%」→19.5%（133/683），刷新说明改指 `domain/animatic_references.py`；其他章节未动。
- 本文件 `程序/tasks_round/tasks_round_4398_result.md`。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git status --porcelain`（接手） | 0 | 仅 6 个允许文件改动（4 改 2 新） |
| `git log -1 --format=%h` | 0 | `67fd96c99`（＝卡面基准 67fd96c9） |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/s04-ref-library` |
| `scripts\coverage_report.py`（15 个定向目标，`--json 维护记录/覆盖率基线.json`） | 0 | `Ran 195 tests ... OK`，`模块被覆盖：133/683`，基线已写入 |
| `run_selftests.py -k animatic_references req_s04_anchors animatic_service` | 0 | 43 条 0 红，`ALL TESTS PASSED` |
| `smoke_test.py --architecture` | 0 | `Ran 708 tests in 253.759s` `OK` `✅ 架构治理测试` |
| `scripts\dev.py claim` | 0 | 轮次号 `4398` |

定向输出尾部原文：

```
共 43 条用例，11.0 秒；0 个文件有红
最慢 3 路工作单元：
  test_req_s04_anchors         10.3 秒 / 13 条
  test_animatic_service         8.1 秒 / 13 条
  test_animatic_references      5.5 秒 / 17 条
实际跳过 0 条用例：本机没有任何登记位被跳过

ALL TESTS PASSED
```

架构输出尾部原文：

```
Ran 708 tests in 253.759s

✅ 架构治理测试：tests/architecture
OK
```

## 未验证项

- 未跑默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe`（卡面未列命令）。
- 「先红 1 红/26 绿 ModuleNotFoundError」为上一会话记录转述，本会话未复核改前原始输出；改后 43/43 与 708/708 为本会话实测。
- 未在真实可见桌面人工点验（本轮无 UI 改动；覆盖路径为纯函数与原子写网关）。
- 覆盖率基线为 15 组定向用例的定向测量，非整仓覆盖率（口径见 runbook §11）。

## 卡外发现（只记录不顺手修）

- runbook §11 引例旧文「542 个模块覆盖率 0」与正文 549 长期不一致（疑为更早基线残留），本轮按授权范围一并对齐为 550。
- 覆盖率刷新输出中 `request_ledger.py:154 已忽略 OSError: [Errno 28] diagnostic disk full` 与 `unit_of_work 恢复失败（第 1 项）：PermissionError` 为用例内负路径预期日志，非环境问题；本机磁盘余量未核实。

## 提交

- 车道 `codex/s04-ref-library`，领号 R4398；本文件随 `dev.py commit` 同批提交，证据 `tasks_round/evidence/R4398.json` 由提交工具生成；commit hash 见完成报告。
