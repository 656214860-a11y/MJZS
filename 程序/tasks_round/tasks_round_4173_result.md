# R4173 结果：PAW-TEST——猫爪位置用例量几何前先处理窗口事件
<!-- round-evidence: {"commit_base": "12ce348b", "credential_hits": 0, "evidence_sha256": "28d86db66cd1b694", "exit": 0, "failed": 0, "passed": 613, "round": 4173, "tests": "run_selftests.py -k pet_ui"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。卡 PAW-TEST（波次 W2），车道 `codex/pet-paw-test`，基准 `12ce348b`。缺陷：`PawTests.test_the_paws_and_the_patch_never_overlap` 在 `deiconify()`＋`update_idletasks()` 之后直接读 `winfo_rootx()`／`winfo_width()` 等窗口几何，但没有 `update()` 处理窗口事件——dock 的 `<Configure>` 绑定的 `_align_paws` 重排与窗口管理器的映射／位置通知都还压在事件队列里，量到的是未映射部件的旧坐标（`paws.winfo_rootx()` 返回 0）。修法按卡面：只在用例里补 `self.win.update()`（与 `GeometryTests.show_at`、`CaptionTests.test_the_caption_clears_the_patch` 同一写法），断言一字未动，产品代码零改动。
- （二）测试跑了吗、三个基线：跑了。定向命令（`gui_hidden.py` 包 `unittest tests.test_pet_ui.PawTests`）改前 7 条用例 1 红（原因见下），改后同命令 7 条全绿、退出码 0；架构门禁 `smoke_test.py --architecture`「Ran 700 tests in 252.668s」「OK」，退出码 0。默认冒烟与全量自测本卡未要求，未跑。
- （三）欠账：无新增、无减少。本轮只动测试文件一行，产品代码零改动。

## 缺陷复现（改前红）

产品与测试均未改时先跑定向命令：7 条用例 1 红，红的正是卡面缺陷——量几何前没处理窗口事件：

- `test_the_paws_and_the_patch_never_overlap`：`AssertionError: 0 not greater than 44 : 猫爪列在头像右侧，矩形不相交`。`self.pet.paws.winfo_rootx()` 返回 0：`deiconify()` 之后事件未派发，部件尚未完成映射与重排，读到的不是落定后的屏幕坐标。

改前输出尾部原文：

```
...F...
======================================================================
FAIL: test_the_paws_and_the_patch_never_overlap (tests.test_pet_ui.PawTests.test_the_paws_and_the_patch_never_overlap)
头像在底栏左列、猫爪列在右沿：视觉与命中区都不压头像；小字在头像正下方。
----------------------------------------------------------------------
Traceback (most recent call last):
  File "D:\漫剧制作助手\.agents\worktrees\pet-paw-test\程序\tests\test_pet_ui.py", line 4912, in test_the_paws_and_the_patch_never_overlap
    self.assertGreater(self.pet.paws.winfo_rootx(), avatar_right,
                       '猫爪列在头像右侧，矩形不相交')
AssertionError: 0 not greater than 44 : 猫爪列在头像右侧，矩形不相交

----------------------------------------------------------------------
Ran 7 tests in 0.776s

FAILED (failures=1)
```

（行号 4912 为改前行号；补行后该断言在 4913 行。）

## 改了哪些文件（文件:行号）

- `程序/tests/test_pet_ui.py:4906`：`test_the_paws_and_the_patch_never_overlap` 在 `self.win.update_idletasks()` 后补 `self.win.update()`，先处理窗口事件再量几何；断言未动。`git diff --numstat`：`1	0	程序/tests/test_pet_ui.py`。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `set "PYTHONPATH=tests" & ..\..\..\..\运行环境\Python\python.exe -B scripts\gui_hidden.py "%TEMP%\cpa-verify-gui.log" . -- ..\..\..\..\运行环境\Python\python.exe -B -m unittest tests.test_pet_ui.PawTests`（改前，产品与测试均未改） | 退出码 1；「Ran 7 tests in 0.776s」「FAILED (failures=1)」，红因见上 |
| 同上（改后） | 退出码 0；尾部原文：`.......`／`Ran 7 tests in 0.588s`／`OK` |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 退出码 0；尾部原文：`Ran 700 tests in 252.668s`／`OK`／`✅ 架构治理测试：tests/architecture` |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 退出码 0，轮次 4173 |

注：卡面验收命令是 cmd 写法（`set "PYTHONPATH=tests" & ...`、`%TEMP%`），本机执行 shell 为 PowerShell 5.1，按等价方式执行：`PYTHONPATH=tests` 经进程环境变量传入（对子进程同样生效），`%TEMP%` 写作 `$env:TEMP`，传给 `python.exe` 的全部参数原样未改。

## 如实说明

- （一）卡面模板写「先写测试复现缺陷……再改产品」，但允许修改清单只有 `程序/tests/test_pet_ui.py`，且卡面目标明确「只改测试夹具，断言不动」：缺陷本身在用例里（量几何前漏处理窗口事件），不存在可改的产品文件。复现证据即该用例改前的红；「改产品」一步落实为给该用例补 `self.win.update()`。
- （二）`test_the_paws_sit_at_the_dock_right_edge` 同属猫爪位置用例但窗口全程 `withdraw()`、不断言屏幕坐标，其 `place_info` 对 `_cluster_layout` 的比对与 dock 宽度自洽，改前改后均绿，未动。
- （三）`PawTests` 其余 6 条用例改前即绿，与本缺陷无关，未动。
- （四）被拒绝的命令：无。未使用 git add／git commit／push／merge／stash／checkout 等禁止命令；未运行卡面以外的命令。

## 未覆盖项

- 未跑默认冒烟、未跑全量自测（卡面只要求定向命令与 `smoke_test.py --architecture`）。
- 未在真实桌面窗口里手工点过猫爪；验证限于隐藏桌面上的 `PawTests` 7 条用例与架构门禁。
- `self.win.update()` 补在 `update_idletasks()` 之后，与本文件 `GeometryTests.show_at`、`CaptionTests` 的既有次序一致；未验证其它含 Tk 用例文件是否存在同类漏 `update()`（范围外，只记录不顺手修）。
