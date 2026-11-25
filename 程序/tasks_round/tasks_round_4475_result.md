# R4475 结果：RESIDUE-CLEAN-A3 归档 tasks_round 散落旧证据（纯移动零删除）
<!-- round-evidence: {"commit_base": "68b75c964", "credential_hits": 0, "evidence_sha256": "e4686a81ea6dd021", "exit": 0, "failed": 0, "passed": 8, "round": 4475, "tests": "run_selftests.py -k taskbook_closure"} -->

## 开头三问

- 本轮属于哪种类型：结构治理轮·机械安全归档（`历史残留清理任务书.md` §二「清理轮 A」的 A3；任务卡 RESIDUE-CLEAN-A3，波次 W3，车道 `codex/residue-clean-a3`，基准 `68b75c964`）。未改任何 `.py`/`.pyw`/测试/`docs/`。
- 测试跑了吗、三个基线：本卡为纯 `git mv` 归档零代码改动，卡面要求的三条验收命令全部实跑——`run_selftests.py -k taskbook_closure` 退出 0（8 条全过）；`smoke_test.py` 退出 0（通过 9 项、失败 0 项）；`smoke_test.py --architecture` 退出 0（708 条 / 294.7 秒全过）。
- 欠账少了吗：少了——`tasks_round/` 根下 25 项无活跃引用的散落旧证据移入 `归档/2026-11_历史文档/`，A3 勾选并登记完成记录；17 项仍被引用的文件原样保留且逐条列明引用方，不算新增欠账。

## 核查口径与数量说明

- 枚举口径：`git ls-files 程序/tasks_round`（退出码 0，4505 条），取 `tasks_round/` **根层**（不含任何子目录）中排除 `tasks_round_*_result.md` 与 `*任务书.md` 的跟踪文件。
- **实得 42 项**（卡面写「49 项」为预估数；按同一口径逐项枚举无遗漏）：非 `t` 开头散落 34 项＋`tasks_round_*` 非结果散落 8 项。其中含 `source_priority_result.md` 这类名含 result 但非轮次结果文件的散落证据。
- 「活跃引用」判定口径：文件名经全树检索，命中方属于**代码、测试、工程文档（`docs/`、`维护记录/`、`runbook.md` 等）、活跃 `*任务书.md`、`project_status.md`、`任务完成/`** 者计为活跃，文件原地保留；以下命中**不计**为活跃引用：① `归档/` 内的命中（已归档文档间的死引用）；② 被移文件自指或互指；③ 历史 `tasks_round_*_result.md` 里的纯文字提及（已收尾轮次的历史记录，非活跃依赖，且文件仍在仓库内仅变更路径）；④ `历史残留清理任务书.md` §F 表第 70 行——它是本卡候选清单的出处本身。
- 方法：每个文件名用 ripgrep 对工作树全量检索，逐项分「无活跃引用→git mv」／「仍被引用→原地保留」两类；git mv 后复查全部 25 个文件名，非归档命中仅剩上述不计类，确认无漏判。

## 仍被引用判定表（17 项，原地保留）

| 文件 | 活跃引用位置（文件:行号） |
|---|---|
| `A1回退交接单.md` | `tasks_round/架构地基加固任务书.md:748`（A1 回退修正行，交接单见该文件） |
| `L2跨层依赖需求单.md` | `tasks_round/L2领域服务层优化任务书.md:261`；`tasks_round/tasks_round_3272_result.md:28` |
| `L4界面层盘点报告.md` | `tasks_round/错误代码统一任务书.md:5,56,96,235,373,376`；`tasks_round/工程文档细化任务书.md:636`；`tasks_round/L4界面层优化任务书.md:4,57,215`；`tasks_round/专题八出错与恢复盘点报告.md:18,56,132`；`tasks_round/专题九账户会员设置模型管理盘点报告.md:56` |
| `L5入口层诊断报告.md` | `tasks_round/L5入口层优化任务书.md:6,153,531`；`tasks_round/错误代码统一任务书.md:5,96`；`tasks_round/工程文档细化任务书.md:636`；`tasks_round/专题八出错与恢复盘点报告.md:29,31,43,57,67,131` |
| `R3276_残留SKILL无法删除_诊断报告.md` | `tasks_round/残留SKILL治理任务书.md:4,117`（前置诊断链接与交付物清单） |
| `R3818_测试ID变更.json` | `tasks_round/任务完成/总控机制删除·任务完成.md:10,68`；`tasks_round/tasks_round_3818_result.md:40,65` |
| `R3818_退役资源清单.txt` | `tasks_round/任务完成/总控机制删除·任务完成.md:10`；`tasks_round/tasks_round_3818_result.md:15` |
| `SKILL请求上下文预算诊断报告_20261118.md` | `tasks_round/SKILL请求上下文预算修复任务书.md:3`（任务书唯一来源链接）；`tasks_round/tasks_round_3289_result.md:8` |
| `全量持续红归因报告.md` | `tasks_round/减红第二步任务书.md:161,185`（允许修改文件与提交命令行）；`docs/records/会话接续记录.md:114` |
| `地基加固_跨车道交接单.md` | `tasks_round/任务完成/L2领域服务层优化·任务完成.md:91`（他车道遗留物处置登记） |
| `成熟依赖并发任务评估_20261117.md` | `tasks_round/引入成熟框架与工作树规范任务书.md:59`；`tasks_round/任务完成/引入成熟框架与工作树规范·任务完成.md:103` |
| `桌面与云服务验收台账.md` | `tasks_round/任务完成/桌面与云服务架构及全链路验收·任务完成.md:4`；`tasks_round_3707/3739/3749/3759/3842/3854_result.md` 多轮持续登记 |
| `错误代码体系盘点报告.md` | `tasks_round/错误代码统一任务书.md:265,275`（允许修改文件与提交命令行）；`docs/records/会话接续记录.md:114` |
| `tasks_round_1198_cleanup_audit.md` | `tasks_round/死代码与无效功能任务书.md:66`（J1–J8 状态行）；`project_status.md:82`；`维护记录/状态历史归档.md:369-370` |
| `tasks_round_1198_cleanup_sources.tsv` | `tasks_round/tasks_round_1198_cleanup_audit.md:8`（保留项正文链接「调用索引」） |
| `tasks_round_182_closure_report.md` | `维护记录/状态历史归档.md:370` |
| `tasks_round_182_optimization_checklist.md` | `维护记录/状态历史归档.md:369` |

## git mv 清单（25 项无活跃引用 → `tasks_round/归档/2026-11_历史文档/`）

`git status --porcelain` 实测全部为 `R`、零 `D`；目标目录无同名覆盖（清单逐项比对过）。分 7 批 `git mv` 执行，均退出 0：

| 源文件（tasks_round/ 根下） | 性质 |
|---|---|
| `BLOCKING_REPORT_R3199.md` | R3199 阻塞报告（被移 `HANDOFF_R3199_to_R3200.md` 引用，同批归档；非归档命中仅 §F 表） |
| `HANDOFF_R3199_to_R3200.md` | R3199→R3200 交接单（非归档命中仅 §F 表与自指） |
| `MODERN_2_busy.png`、`MODERN_3_narrow.png` | R1786 主窗口截图（命中仅 `归档/2026-10/tasks_round_1786_result.md`） |
| `R1446_name_audit.md` | R1446 命名审计附件（命中仅 `归档/2026-10/tasks_round_1446_result.md` 与历史 result 提及） |
| `R3820_architecture_final.txt`、`R3820_directed_final.txt`、`R3820_deleted_skill_files.txt`、`R3820_reference_inventory.txt` | R3820/R3831 日志与清单（命中仅 R3820/R3831 结果文件的历史记录） |
| `UIMOD_after.png`、`UIMOD_before.png` | UIMOD 对比截图（同上 R1786 归档结果） |
| `source_priority_result.md` | 来源优先级一次性结果（非任务书轮次结果文件） |
| `tasks_round_1786_diagnosis.md` | R1786 诊断草稿（命中仅其归档结果文件） |
| `tasks_round_182_optimization_backlog.md` | R182 积压清单（命中仅历史 result 提及） |
| `tasks_round_857_script_panel.png`、`tasks_round_857_video_panel.png` | R857 面板截图 |
| `全量测试优化执行记录.md`、`全量测试优化计划.md` | 已收口的全量优化计划（互指，同批归档） |
| `六层架构收口_A0基线复核.md` | A0 基线复核（命中仅 `tasks_round_3402_result.md` 历史记录） |
| `成熟依赖整体交付汇报_20261118.md` | 交付汇报（命中仅 `tasks_round_3260_result.md` 历史记录；其引用的《成熟依赖并发任务评估_20261117.md》仍在根下保留，见判定表） |
| `接续摘要_20260930_0215.md`、`接续摘要_20260930_1951.md`、`接续摘要_20261001_1623.md`、`接续摘要_20261002_1534.md` | 2026-09/10 会话接续摘要×4 |
| `重构批次ABCD总报告.md` | 重构批次总报告（命中仅 `归档/2026-10/tasks_round_1843_result.md`） |

## `任务完成/` 与 `evidence/` 零改动核实

- `git status --porcelain` 输出中**无任何** `任务完成/` 或 `evidence/` 路径条目；25 条变更全部是 `tasks_round/… → tasks_round/归档/2026-11_历史文档/…` 的 `R` rename。
- `git ls-files 程序/tasks_round/任务完成` 枚举 22 个文件（含 `README.md` 与 21 份 `·任务完成.md`），本轮未读改、未移动，数量与清单均与开工时一致。
- `evidence/` 本轮未被手动改动；仅提交门禁自身会新增 `evidence/R4475.json`（卡面接口契约第 2 条允许的例外）。

## 命令与退出码

工作目录：未注明时为仓库根 `residue-clean-a3`；`PY` 指 `..\..\..\..\运行环境\Python\python.exe`，执行目录 `程序`。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/residue-clean-a3` |
| `git status --porcelain`（开工） | 0 | 无输出（干净） |
| `git log -1 --format=%h` | 0 | `68b75c964`（基准一致） |
| `git ls-files 程序/tasks_round` | 0 | 4505 条；根层散落枚举 42 项（见口径节） |
| 各文件名 ripgrep 全树检索 ×42 | — | 判定表见上；25 项无活跃引用 |
| `git mv <src> 程序/tasks_round/归档/2026-11_历史文档/`（7 批 25 项） | 0 | 全部成功，无同名覆盖 |
| `git status --porcelain`（移动后） | 0 | 25 条全 `R`、零 `D`；`任务完成/`、`evidence/` 无条目 |
| `PY -B run_selftests.py -k taskbook_closure` | 0 | 8 条 / 0.9 秒，ALL TESTS PASSED |
| `PY -B smoke_test.py` | 0 | 通过 9 项、失败 0 项 |
| `PY -B smoke_test.py --architecture` | 0 | 708 条 / 294.709 秒，OK |
| `PY -B scripts\dev.py claim` | 0 | 领到轮次 4475 |
| `git log -1 --format=%ci` | 0 | `2026-11-25 15:34:58 +0800`（完成记录落款依据） |

验收命令尾部原文：

```text
# run_selftests.py -k taskbook_closure
共 8 条用例，0.9 秒；0 个文件有红
ALL TESTS PASSED

# smoke_test.py
==================================================
通过：9 项
失败：0 项
==================================================
✅ 冒烟测试通过，可以进入下一轮

# smoke_test.py --architecture
----------------------------------------------------------------------
Ran 708 tests in 294.709s
OK
✅ 架构治理测试：tests/architecture
```

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `程序/tasks_round/历史残留清理任务书.md` | §二 A3 勾选并附 R4475 执行记录；「完成记录」节登记 R4475；B/C/D/E 计划项未动 |
| `程序/tasks_round/tasks_round_4475_result.md` | 本文件（新增） |
| `程序/tasks_round/归档/2026-11_历史文档/` | 接收上表 25 项 `git mv` rename，无新增无删除 |

未改：任何 `.py`/`.pyw`、测试、`docs/`、`project_status.md`、`任务完成/`（22 件原样）、`evidence/`、根下 41 份 `*任务书.md`、全部 `tasks_round_*_result.md`、其余目录。

## 未覆盖项（未运行／未验证）

- 数量口径差：卡面写「49 项」，按卡面枚举口径实得 **42 项**（34 非 t 散落＋8 个 `tasks_round_*` 非结果）；已全量枚举逐项判定，判定完整性不受该预估差影响，差异如实记录供验收核对。
- 历史 `tasks_round_*_result.md` 中被移文件名的纯文字提及（如 R3820/R3831 结果里的日志名、R1786 归档结果里的截图名）未改写成新路径——按口径它们属历史记录而非活跃引用；文件仍在仓库内，`归档/` 相对路径可追。若验收口径要求同步改史，需另行授权。
- 未跑全量 `--all --safe`：本卡零 `.py` 改动，卡面验收仅列三条且全过；`--tests taskbook_closure` 随提交门禁复跑。
- 未 push、未 merge、未动主工作区、未动 `.agents/`、hooks 与其他在途车道文件。
