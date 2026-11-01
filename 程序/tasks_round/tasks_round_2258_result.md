# R2258 结果：test_leak_teardown 页面切换测试不再被开机招呼云朵误判为泄漏（测试稳定性轮）

## 三问
- 轮次类型：缺陷轮（§3，测试自身的时序缺陷）。用户「先查全量红」的第二处。
- 测试和三个基线：改前经 gui_hidden 单跑 `tests.test_leak_teardown` 3 次红 2 次（`round 3 still grows children: 4 != 5`）；改后连跑 4 次全绿。断言未动，只在每轮开始收回开机招呼定时器。其余基线沿用 R2250（定向与 --architecture）；本轮只改一份测试，未再跑 --architecture。
- `project_status.md` 欠账：未增减。

## 根因
- 一次性的开机招呼（`pet_ui_voice.greet`，窗口可见且启动页不忙时才触发）会建一个 `BaseDialog` 云朵。机器慢时一轮要 15 秒，招呼恰好落进第 2／3 轮，窗口子项 4→5，被误判为页面切换泄漏。不是应用泄漏。
- 后台全量最后一次 HEAD 564e2e2 只剩这一项红；之前的随机红来自 R2250 修掉的 None 缓存键。

## 改动
- `tests/test_leak_teardown.py`：`_measure` 每轮开始 `pet.cancel_greet()`，断言未动。
