# R4160 结果：SKILL 导入面板两处修复（FIX-AUD-SKILL-PANEL-IMPORT）
<!-- round-evidence: {"commit_base": "6997ae43", "credential_hits": 0, "evidence_sha256": "5bbb84d562920375", "exit": 0, "failed": 0, "passed": 44, "round": 4160, "tests": "run_selftests.py -k skill_import skill_panel"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 W7-FIX-AUD-SKILL-PANEL-IMPORT（波次 W2）；缺陷来自只读审查 AUD-SKILL D5/D6——(1) 「检查更新」在界面线程同步 clone/下载，多远程行时界面卡死；(2) 文件对话框「全部文件」可导入任意扩展名，提示新增成功但注册表只扫 `*.skill.md`，列表永远不出现。车道 `codex/fix-aud-skill-panel`，基准 `6997ae43`。

（二）测试与三个基线：`run_selftests.py -k skill_import skill_panel` 改前（产品未改、新用例已写）44 条中 2 红，改后同命令 44 条全过、退出码 0；`smoke_test.py --architecture` 700 条全过、退出码 0。默认冒烟与全量未跑。

（三）欠账：无新增。`check_skill_updates` 在无 `async_queued`/`async_` 的轻量替身下降级为同步执行（与 `skill_panel.translate_note` 同一回退口径），真实 Desktop 恒走后台队列。

## 缺陷复现

- D5/D6-1（界面卡死）：Mock 面板挂 `async_queued` 替身（fn 上工作线程、done 回调用方线程），`check_updates` 记线程号。改前 `desktop.submitted == []`——体检从不提交后台队列，`check_updates` 在调用线程同步执行。
- D5/D6-2（任意扩展名）：`notes.txt` 写入合法 SKILL 清单内容走 `add_skill_from_file`，改前 `result` 为导入成功的目标路径（文件被复制进阶段目录、状态行报「已新增 SKILL」），注册表只扫 `*.skill.md` 故永不显示。

## 改了哪些文件

- `ui/skill_panel_import.py:219-265`：`check_skill_updates` 把体检（`check_updates`＋`ledger_items`，含远程克隆与下载探针）收进 `_work()`，经 `desktop.async_queued`（无则 `async_`，再无则同步回退）提交后台；`_done` 在界面线程处理结果——异常仍落状态行「SKILL 更新检查失败：…」（原文案不变），面板已销毁时不再回调。
- `ui/skill_import_service.py:121-123`：`plan_import` 对 `kind=='manifest'` 且文件名不以 `.skill.md` 结尾的来源抛 `ImportBlocked`（「不是 SKILL 清单：单文件只接受 *.skill.md（整包入口是 SKILL.md）」），复制前硬拒、不进确认框；`SKILL.md`/README 包入口与仓库／压缩包候选口径不受影响。
- `tests/test_skill_import_validation.py`：新增 `SkillImportAuditFixTests` 三条用例与 `_QueuedDesktop` 替身（不建 Tk/Desktop，只用临时目录）；导入行加 `threading`、`SKILL_TEMPLATE`。
- 本结果文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 开工三查 | 干净；`6997ae43`；`codex/fix-aud-skill-panel` |
| 定向（改前） | 退出码 1；44 条，2 红（见下） |
| 定向（改后） | 退出码 0；44 条；`ALL TESTS PASSED` |
| `smoke_test.py --architecture` | 退出码 0；`Ran 700 tests in 240.115s`；`OK` |
| `scripts\dev.py claim` | 先领 4159；R4159 提交被回执机制拒绝后改领 4160（见下） |

轮次号变更说明：首次 `dev.py commit` 误把文件参数写成 `程序/` 前缀（相对仓库根而非 `程序/` 工作目录），`git add` 报 pathspec 不存在；但提交回执 `R4159.json` 已先落盘且 identity 绑定那组错误路径，之后任何等价路径写法都被 `commit_retry` 判「轮次已归属其他工作树、分支或命令参数」拒绝。按车道机制重新领号为 4160，本结果文件由 `tasks_round_4159_result.md` 改名而来，内容未变。两次被拒命令原文见完成报告。

改前红的条数与原因（原文，临时目录路径已脱敏）：

```
===== test_check_updates_probes_on_background_thread =====
AssertionError: [] is not true : 体检应提交到桌面后台队列而不是界面线程同步跑
===== test_non_skill_manifest_is_rejected_before_copy =====
AssertionError: WindowsPath('<临时目录>/target/01剧本准备SKILL/notes.txt') is not None
```

改后定向命令输出尾部原文：

```
共 44 条用例，5.8 秒；0 个文件有红
最慢 7 路工作单元：
  test_skill_panel_dropdown_layout    2.7 秒 / 12 条
  test_skill_import_validation#2    1.5 秒 / 12 条
  test_skill_panel_layout_fit    0.8 秒 / 3 条
  test_skill_import_validation#1    0.5 秒 / 12 条
  test_skill_panel_imported     0.5 秒 / 2 条
  test_skill_panel_production_locks    0.2 秒 / 1 条
  test_skill_panel_long_list    0.0 秒 / 2 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：<仓库>/.git/selftest-incremental.json
最近 5 轮自检中位基线：26.9 秒

ALL TESTS PASSED
```

改后架构门禁输出尾部原文：

```
----------------------------------------------------------------------
Ran 700 tests in 240.115s

OK
✅ 架构治理测试：tests/architecture
```

## 没有验证的地方

- 真实 Desktop 的 `async_queued` 排队／取消／迟到结果路径未做真机验证（新用例只用替身验证「提交后台＋done 回界面线程＋异常落状态行」）；队列语义沿用 `BackgroundTaskLifecycle` 既有实现。
- 「检查更新」结果窗（`show_skill_updates` 非空待更新列表）的 Tk 几何未在本轮新测；既有 `PanelUpdateCheckTests`（test_skill_update_check.py，不在本次 -k 范围）未跑。
- `desktop_shared_input._import_skill_local` 同一「全部文件」入口经 `plan_import` 一并获得拒绝文案，未单独跑其测试文件。
- 台账 `program` 取 `__file__.parent`（`程序/ui`）与 `.parents[1]`（`程序/`）并存的既有口径未动，未核实是否为独立缺陷。
