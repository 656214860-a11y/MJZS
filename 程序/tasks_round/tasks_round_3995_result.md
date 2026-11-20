# R3995 结果文件：DOC-T8A 专题八「出错与恢复」盘点
<!-- round-evidence: {"commit_base": "8ca777e9", "credential_hits": 0, "evidence_sha256": "b8ff6426e4734009", "exit": 0, "failed": 0, "passed": 0, "round": 3995, "tests": "docs-only"} -->

## 三问

1. **本轮类型**：只读诊断轮（§3.5）。不改任何 `.py`/`.pyw`、不搬目录、不删文件；新增盘点报告与本结果文件两个 `.md`。
2. **测试跑了吗、三个基线**：只跑任务卡验收命令 `python -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v`，54 条全过（架构门禁当轮实际数 54，失败集合为空；输出末尾 `{"ok": true, "finding_count": 0}`）。默认冒烟基线不适用（只读诊断轮默认不跑测试，本卡未要求）；全量基线不适用（本卡未要求，欠账口径以 `full-safe-receipts.json` 为准，本轮不产生新欠账）。
3. **欠账少了吗**：无关。只读盘点不消账也不欠新账；盘点报告 §5 列了 5 个待主控决策的问题。

## 改动文件

- `tasks_round/专题八出错与恢复盘点报告.md`（新增）：六块结构——范围、事实表 30 行（每行带 `文件:行号`）、现有文档写到哪了、文档和代码对不上的地方 4 条、给主控的问题建议 5 条（含可选方案与建议）、读过的文件清单。
- `tasks_round/tasks_round_3995_result.md`（新增，本文件）。

## 验收命令结果

- `python -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v`：Ran 54 tests，OK，`{"ok": true, "finding_count": 0}`。
- `git status --short` / `git diff --stat`：除上述两个新增 `.md` 外无其他改动；`.py`/`.pyw` 与既有文档零改动。

## 未核实项（不猜）

- `pythonw.exe` 本体损坏时用户看到什么（L5 报告 F1 同样标「未核实，需要启动复现」）。
- 老实例主线程卡死时二次双击的表现（L5 报告 F5：代码可证、未实机复现）。
- 托盘线程关闭时是否 join（L5 报告 §3.2 标未核实）。

## 盘点要点摘要

- 出错显示共 5 类出口（状态栏常驻消息、页内 `set_error`、宠物气泡 VERDICTS、模态弹窗、Win32 MessageBox），失败级调用点 72 条，`error_codes.describe()` 界面 0 处使用。
- 日志集中 `程序/logs/`，`app_logging.redact` 是唯一脱敏实现；诊断导出白名单不含 `app.log`（报告问题 1）。
- 启动 FATAL 弹 MessageBox 后退出；崩溃预算满 3 次弹安全启动；在途任务、unknown 台账、发布事务、`.corrupt` 侧车各有恢复路径。
- 用户恢复入口集中在项目首页按钮排（恢复回收站、重建索引、导出诊断、运行状况）＋视频页「恢复任务编号」＋设置页「环境自检」＋自检旗标文件。
