# R1681 修复轮：拆分 `desktop_writing_page.py::writing` 布局调度闭包，消除行数棘轮超限

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮。根因：`tests/architecture/test_function_size_ratchet.py` 第 16 行登记 `('desktop_writing_page.py', 'writing'): 577`，而该函数实测 588 行（超 11 行），门禁红。判定为函数体积超限，需做纯行为保持的拆分（棘轮只许缩小，禁止上调上限）。
2. **测试跑了吗？三个基线过了吗？** 定向 `-k function_size_ratchet`：修前 1 红（`writing 588 行 > 上限 577`）、修后 2/2 全绿；定向 `-k writing` 15 文件 / 155 条全绿；`--layer architecture --all` 368 条，唯一红为 `test_round_baselines.test_full_safe_all_is_required_after_eight_source_rounds`（R1680 欠全量，后台自动补跑机制负责，与本轮无关）；默认冒烟 8/8。未跑安全全量。
3. **project_status.md 的欠账少了吗？** 不变（本轮为源码轮，全量欠账 +1；其余欠账条目不涉及增减）。

## A 改动

- `desktop_writing_page.py`：把 `writing` 方法内原 338–374 行（37 行）的布局修正调度闭包（`layout_job`／`cancel_layout_job`／`schedule_layout`）原样提取为同文件模块级私有函数 `_build_layout_scheduler(win)`（47 行），`writing` 588→554 行。仅把闭包引用的 `self.win` 改为入参 `win`，闭包行为、事件绑定 `<Destroy>`、`schedule_layout(...)` 调用顺序、对外可见变量名均未变；未新增文件、未新增 import 层级。
- `tests/architecture/test_function_size_ratchet.py`：`('desktop_writing_page.py', 'writing')` 上限 577→554。断言未动；上限未上调（下调，577→554）；提取了原 338–374 行为 `_build_layout_scheduler`。

## C 待用户裁决

无。

## 提交

见提交信息 `R1681:`。
