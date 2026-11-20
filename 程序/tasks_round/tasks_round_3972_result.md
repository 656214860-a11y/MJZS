# R3972 结果：L4-U0 界面层只读盘点
<!-- round-evidence: {"commit_base": "4968a665", "credential_hits": 0, "evidence_sha256": "868cd7a6d8f90f6a", "exit": 0, "failed": 0, "passed": 0, "round": 3972, "tests": "docs-only"} -->

## 三问

- **本轮属于哪种类型？** 只读诊断轮（AGENTS.md §3.5）。交付物只有 `tasks_round/L4界面层盘点报告.md` 与本结果文件，未改任何 `.py`/`.pyw`。
- **测试跑了吗、三个基线过了吗？** 只读轮不跑测试（§5「只读诊断默认不跑测试」）。默认冒烟基线 8/8：未运行。架构门禁：未运行。全量回归：未运行。本轮验证手段是隐藏桌面实测（`ui_probe.py` 三档窗口、`nav_click_probe.py` 真实侧栏回调），不是测试套件。
- **欠账少了吗？** 未变。本卡是盘点，产出供 U5–U10 使用的清单与两项核实结论；任务书 §2.5「四页打不开」由「待核实」变为「核实属实」；§2.4 末行 43px 之谜已定位根因。

## 交付

`tasks_round/L4界面层盘点报告.md`，各清单条数：

| 清单 | 条数 | 说明 |
| --- | --- | --- |
| A 弹窗 | 226 | DIALOG 60 / ASK 52 / NOTIFYFN 74 / DISPATCH 30 / FILEDLG 6 / FLYOUT 2 / TOPLEVEL 2；每条带 文件:行号、入口、调用者、L4-D4 归类与建议 |
| B 报错显示入口 | 失败级 72（全部显示调用点 516） | 四类来源统计：describe() 0、其他编码 0、手写 35、异常原文 32、上游透传 5；`status.set` 392 条级别未定另注 |
| C 提示文字 | 232 | 样式名取值与次数（Muted.TLabel 66、DescriptionBlock 41、内联裸 Label ≈85 等）；同文双显实锤 1 处（`ui/desktop_media_pages.py:726`+`:728`） |
| D 逐页边距 | 13 页 | 全部共用外框；能建出的页内容框与输入框卡片左右边缘实测差 0px；08/09/12/13 空项目建不出标「未核实」 |
| 核实1 | 4 页 | 真实侧栏回调下 08/09/12/13 异常照样发生但被 `go()` 吞进状态栏，`callback_exceptions: 0` |
| 核实2 | 1 项 | 视频页 `status_bar.pack_forget()`（`ui/desktop_page_nav.py:271–275`）释放 23+20=43px，`input_dock` 锚底（`desktop.py:312`）随之下移 43px |

## 盘点用的命令（均只读）

```powershell
# 领号
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B 维护记录\基准脚本\round_claim.py next   # → 3972
# 清单A/B/C：AST 扫描（脚本在 %TEMP%\l4_tools\，不进工作树）
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -X utf8 -B "$env:TEMP\l4_tools\scan_popups2.py" > popups_scan2.txt
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -X utf8 -B "$env:TEMP\l4_tools\scan_errors.py" > errors_scan.txt
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -X utf8 -B "$env:TEMP\l4_tools\scan_hints.py" > hints_scan.txt
# 清单D 实测 + 核实1：隐藏桌面
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B scripts\gui_hidden.py "$env:TEMP\l4_tools\u0.log" . -- 'D:\漫剧制作助手\运行环境\Python\python.exe' -X utf8 -B "$env:TEMP\l4_tools\ui_probe.py" . "$env:TEMP\l4_tools\out_u0"
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -B scripts\gui_hidden.py "$env:TEMP\l4_tools\nav_click.log" . -- 'D:\漫剧制作助手\运行环境\Python\python.exe' -X utf8 -B "$env:TEMP\l4_tools\nav_click_probe.py" .
# error_codes 用量
Select-String -Path *.py,ui\*.py,contract\*.py,infra\*.py -Pattern 'error_codes|describe\('
```

## 验收命令结果

- `git status --short`：提交前仅 `tasks_round/L4界面层盘点报告.md` 与本文件（新增未跟踪）。
- `git diff --stat $(git merge-base master HEAD) -- "*.py" "*.pyw"`：空输出（本车道相对分叉点零代码改动）。

## 提交

- 提交号：见下（提交后回填）。
