# R4161 结果：UX-C4-TESTS 底部状态栏补三条用例
<!-- round-evidence: {"commit_base": "d8d10a5b", "credential_hits": 0, "evidence_sha256": "cb60719355fccb81", "exit": 0, "failed": 0, "passed": 22, "round": 4161, "tests": "run_selftests.py -k ui_status_bar"} -->

## 开头三问

（一）本轮属于哪种类型：测试轮（只补用例，不改产品代码），任务卡 `W6B-UX-C4-TESTS`、分支 `codex/ux-status-bar-tests`、来源是 UX-C4（R4091）只读复核留下的建议。

（二）测试跑了吗、三个基线：定向测试三遍各 22 条、ALL TESTS PASSED、退出码 0；静态检查 `Ran 47 tests`、`OK`；架构门禁 `Ran 700 tests in 215.574s`、`OK`、失败集合为空；默认冒烟没单独跑；全量自测没跑；新增 3 条用例、没有修改或删除现有用例。

（三）欠账少了吗：补上了复核建议里的三条用例；无新增欠账。

## 改了哪些文件

- `tests/test_ui_status_bar.py`：文件头加 `import _tkinter`；在 `StatusBarLayoutTests` 末尾追加 `spin` 与三条用例（重摆自停、悬停文字跟随、不带 width 更新回到按文字定宽）。改后 390 行。新增用例不建应用主窗口（Desktop），用的是 `StatusBarLayoutTests` 自己建的 Tk 窗口。
- `git diff --numstat` 原文：`57	0	程序/tests/test_ui_status_bar.py`

## 命令与结果

| 命令 | 退出码 | 结果行 |
| --- | --- | --- |
| `run_selftests.py -k ui_status_bar`（第 1 遍） | 0 | 共 22 条用例；ALL TESTS PASSED |
| `run_selftests.py -k ui_status_bar`（第 2 遍） | 0 | 共 22 条用例；ALL TESTS PASSED |
| `run_selftests.py -k ui_status_bar`（第 3 遍） | 0 | 共 22 条用例；ALL TESTS PASSED |
| 静态检查（卡面第 7 步那一条 unittest） | 0 | Ran 47 tests in 38.655s / OK |
| `smoke_test.py --architecture` | 0 | Ran 700 tests in 215.574s / OK |

## 如实说明

无。这三条用例改前就是绿的、本轮没有做反向验证（反向验证由写卡窗口做过）。

## 未覆盖项

真实应用窗口里没试；全量没跑。
