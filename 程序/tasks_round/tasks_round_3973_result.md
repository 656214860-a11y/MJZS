# tasks_round_3973_result — L5-E0 入口层只读诊断
<!-- round-evidence: {"commit_base": "489153d5", "credential_hits": 0, "evidence_sha256": "4dd9055ef4ffdbe3", "exit": 0, "failed": 0, "passed": 0, "round": 3973, "tests": "docs-only"} -->

## 三问

1. **本轮属于哪种类型**：§3.5 只读诊断轮（任务卡 L5-E0）。只新增诊断报告与本结果文件，未改任何 `.py`／`.pyw`／测试／配置。
2. **测试跑了吗、三个基线各是什么结果**：未跑。只读诊断轮按 AGENTS.md §5「只读诊断默认不跑测试」与本卡「不运行全量测试」执行：默认冒烟未运行；架构门禁未运行；全量未运行（欠账口径以 `full-safe-receipts.json` 为准，本轮不产生新欠账）。
3. **欠账少了吗**：是。任务书 §2.2 的七条待证假设全部给出结论与证据（H4/H7 证伪），§3 缺陷清单可待主控补卡。

## 交付物

- `程序/tasks_round/L5入口层诊断报告.md`（新增，唯一交付物）
- 本文件（新增）
- `程序/tasks_round/evidence/R3973.json`（提交工具生成）

## 各表条数

- 调用链：主链 16 步（S1–S16，含 S11a–e 子步）；另附 `desktop_launcher.launch()`、`h3_launcher.pyw`、`开发者工具/*.cmd` 三条旁链
- 启动失败路径表：18 行（F1–F18）
- 退出路径表：正常路径 13 步（E1–E13）；未覆盖项 8 行（§3.2）
- 覆盖表：8 个测试文件逐一标注覆盖步骤；无测试步骤单独列出
- 文档漂移：12 行（4 处实质不一致，其余无冲突或仅元数据）

## 七条假设结论

| 假设 | 结论 |
| --- | --- |
| L5-H1 | 部分属实：多数失败有 MessageBox＋根目录启动错误.log；残余盲区=解释器自身坏（未核实）、try 前 6 行、except 二次失败、老实例卡死时二次双击无反馈、mainloop 内异常 .pyw 路径无用户提示 |
| L5-H2 | 属实：启动文案不经 `contract/error_codes`；自检自有 kind 码，外层 except 无码 |
| L5-H3 | 部分属实：不在 `LAYERS` 表，但 `test_dynamic_import_registry` 以 layer=5 并入审计，另有三处测试覆盖；无端到端启动测试 |
| L5-H4 | 不属实（字面）：`desktop_launcher` 顶部不导入 `desktop`（延迟至 `launch()` 内 :38）；部分属实（意图）：顶部已载 tkinter＋ui_widgets，launcher 路径无启动画面 |
| L5-H5 | 部分属实：E1–E13 覆盖充分；缺口=`executors.shutdown()` 零调用方、非当前项目进程靠 Job Object 兜底、退出清扫 detached 不等待、daemon 线程无 join |
| L5-H6 | 属实（代码可证）：二次启动 `SetEvent`+`sys.exit(0)`，老实例 200ms 轮询抬窗；老实例卡死场景未实机 |
| L5-H7 | 不属实：启动链路不调用 `app_shortcut`，无 PowerShell 检查；`ensure/main` 仅手动或安装流程触发 |

## 复现与验证边界

- 本轮未实际启动程序、未调用 `desktop_launcher.launch()`、未调用 `app_shortcut` 改系统函数；符合任务卡复现约束加严版。
- 标注「未核实」项的复现办法已写进报告 F1/F5 行与 §8。

## 验收命令

- `git status --short`（提交前）：仅 `?? tasks_round/L5入口层诊断报告.md`、`?? tasks_round/tasks_round_3973_result.md`
- `git diff --stat $(git merge-base master HEAD) -- "*.py" "*.pyw"`：空（本车道相对分叉点 `4968a665` 无代码改动）

## 提交

- 已提交：`489153d5`（含本文件与证据文件 `evidence/R3973.json`）；本条 hash 由后续补记提交写入
- 提交后 `git status --short`：空
