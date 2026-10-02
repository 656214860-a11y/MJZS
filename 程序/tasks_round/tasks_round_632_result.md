# R632 性能轮结果：剪映开始菜单扫描不再阻塞界面

- 本轮是功能轮还是整理轮？**性能轮**。执行 R630 J 节第 2 项（3.1/8.1，P1），仅将“启动剪映”的开始菜单递归扫描移入既有后台队列。
- 测试跑了吗？三个基线过了吗？**已跑相关回归、默认冒烟和架构门禁，均通过。**全量安全自检不属于本轮 L4 UI 性能改动的必需验证，未重跑；因此不声称三个基线均已重跑为绿。R631 已登记全量安全自检的既有红项。
- `project_status.md` 的欠账少了吗？**少了一项。**R630 J-2 的主线程递归扫描问题已消除；轮次台账由 632 待执行推进为 633 待执行。

## 来源、基线与目标

来源：`tasks_round/tasks_round_630_result.md` 的 J-2（3.1/8.1，P1）。

修复前，`desktop.py:5954-5966` 的 Tk 点击处理函数 `launch_editor()` 在未找到标准安装路径时，直接执行：

```python
for shortcut in root.glob('**/*剪映专业版*.lnk'):
```

该递归开始菜单扫描运行在 Tk 主线程；开始菜单内容较多时，窗口无法响应直到扫描结束。

本轮目标是保持所有剪映发现规则不变，同时使点击路径仅提交后台任务。量化契约为：未命中标准路径时，`launch_editor()` 必须调用既有 `async_()`，而不得在该调用前执行开始菜单 `glob`。

## 修改

| 文件 | 改动 |
|---|---|
| `desktop.py` | 新增 `find_editor_shortcut()`（5944 行），原样保留 APPDATA/PROGRAMDATA 两个开始菜单根、递归 `*.lnk` 匹配及跳过“卸载”的规则；`launch_editor()`（5954 行）改为通过既有 `async_()` 后台执行它。后台结果回到 Tk 线程后才打开快捷方式；未找到时仍走 `self.safe()` 的受控 `ValueError` 提示。|
| `tests/test_ui_edges.py` | 新增 `EditorStartMenuScanTests`（5281 行）：断言点击只入队、后台发现规则保持一致、扫描结果为空时仍是受控错误。|
| `project_status.md` | 仅将当前轮次推进到 633 待执行，以保持结果文件与台账连续。|

没有改变 `find_editor()` 的标准安装路径、保存的剪映路径、快捷方式过滤规则、UI 布局、配置或用户项目数据。

## 修复前后回归证据

先只加入回归测试、不改生产代码，执行：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_ui_edges.EditorStartMenuScanTests
ERROR: test_start_menu_worker_retains_the_existing_shortcut_rule
AttributeError: type object 'Desktop' has no attribute 'find_editor_shortcut'
FAIL: test_launch_editor_only_queues_the_start_menu_scan
AssertionError: unexpectedly None : 找不到标准安装路径后应把开始菜单扫描交给后台队列
Ran 2 tests in 0.155s
FAILED (failures=1, errors=1)
```

修复后执行同一目标测试：

```text
Ran 3 tests in 0.009s
OK
```

关键断言：

1. `find_editor()` 返回空时，点击仅提交 `self.find_editor_shortcut` 到 `async_()`，主线程不会调用扫描函数；
2. 后台扫描仍遍历同一两个开始菜单根，忽略名称含“卸载”的快捷方式；
3. 后台返回空结果时，仍由 `safe()` 捕获“未自动找到剪映专业版”的 `ValueError`，不产生未处理 Tk 回调异常。

## 验证

| 命令 | 结果 |
|---|---|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_ui_edges.EditorStartMenuScanTests` | 3 条，通过。|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected desktop` | 9 项通过；定向门禁 4 个文件、7 条通过。门禁尝试写增量台账时因当前环境权限被拒绝，但输出明确标注“不影响结果”。|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py` | 默认 8 项、0 失败。|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture` | 102 条通过。|

未执行全量安全自检：本轮只改 L4 UI 的线程调度与其专属回归，不涉及 L0–L3、持久化或跨层依赖；按本轮影响面选择了默认、架构、定向及目标回归。R631 已如实记录全量安全自检存在的独立红项。

## J 后续

R630 剩余 J 项应按其自身范围另立轮次处理。本轮不处理剪映发现规则、其它启动性能候选、全量自检既有红项或任何外部程序探测。

## 自审

- 只改了 R630 J-2 指定的开始菜单扫描线程归属及必要回归；没有夹带其它优化。
- 递归 `glob('**/*剪映专业版*.lnk')` 仍存在，但仅在 `find_editor_shortcut()` 的后台任务中执行；Tk 回调只入队和处理结果。
- 未修改用户项目数据、配置、密钥、技能或分发逻辑。
- 本轮实际验证均为绿；未把 R631 已有的全量红项伪装成已修复。

**[TASK_COMPLETE]**
