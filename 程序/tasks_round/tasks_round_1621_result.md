# R1621 拆分 pet_cloud.py 为两个 L4 Mixin（Q9 第四批）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q9；`pet_cloud.py` 是 Q9 第 4 个模块）。
- 测试：架构门禁 `smoke_test.py --architecture` **354 项 OK**（181.7 秒）；默认冒烟 8/8；`pet_cloud` 相关 6 个模块 27 项 OK；覆盖率基线口径相等断言通过（49/278）。
- 欠账：本轮改源码＋新增 2 个生产模块，`project_status.md` 全量欠账计数 +1；R1619／R1620 的欠账仍未清（后台全量跑完后由 post-commit 写凭据）。

## 做了什么

`pet_cloud.py` **2137 → 1802 行**，行数棘轮登记上限 2150 → **1900**。

Q9 点名的 5 个大文件里，`pet_cloud.py` 与 `desktop.py` 都是「单个 Tk 控件类」形态，纯计算部分（`pet_cloud_text`／`_geometry`／`_shape`／`_tail`）此前已拆出，再拆只能按仓库既有 **Mixin 组合**模式（`desktop.py` 由 9 个 Mixin 组成、`pet_ui.py` 由 4 个组成）切方法集。本轮按该模式拆出两个 L4 模块：

| 新模块 | 行数 | 内容 |
| --- | --- | --- |
| `pet_cloud_timing.py` | 248 | `CloudTimingMixin`：自停／渐隐／读秒／生长 16 个方法（`read_hold`、`hold_for`、`default_hold`、`_interaction_paused`、`_interaction_changed`、`_arm_hold`、`_recheck_hold`、`_cancel_position`、`_cancel_hold`、`_cancel_fade`、`_fade_in`、`_fade_out`、`_grow_to`、`_expire`、`_window_gone`、`_parent_gone`）＋ 11 个计时参数（`ALPHA`、`FADE_*`、`GROW_*`、`HOLD_MS`、`READ_*`、`WATCH_RECHECK_MS`） |
| `pet_cloud_hint.py` | 115 | `CloudHintMixin`：提示条 8 个方法（`_focus_reply`、`_restore_hint_after_reply`、`_hint_idle`、`_sync_hint`、`_hint_show`、`_hint_schedule`、`_hint_tick`、`_hint_stop`）＋ 4 个常量（`HINT_MS`、`HINT_STEP_PX`、`HINT_X`、`REPLY_HINTS`） |

`pet_cloud.py` 改为 `class Cloud(CloudTimingMixin, CloudHintMixin)`，并把上述 **15 个常量按原名转发**（`from pet_cloud_timing import (...)`／`from pet_cloud_hint import (...)`），保持公开面与既有「迁出后按原名转发」惯例一致。

**验收校验**（脚本化，见下）：迁移前先断言两个方法集只引用「已导入名 ∪ 同批迁出的常量」，无跨模块函数／类引用；迁移后 `Cloud.__mro__ == [Cloud, CloudTimingMixin, CloudHintMixin, object]`、**118 个方法零丢失**（`hasattr` 逐名）、模块公开面零缺失（原顶层名减去 15 个已转发常量后全部 `hasattr`）、模块 docstring 仍是第一个语句。

## 同步

`tests/architecture/_layers.py` L4 登记 `pet_cloud_timing`、`pet_cloud_hint`；`architecture.md` L4 行补登；`tests/architecture/test_module_size_ratchet.py` 下调 `pet_cloud.py` 上限；`维护记录/覆盖率基线.json` 刷新（49/278）。

## 本轮自身缺陷（已修）

转发导入第一次被插到了文件**最前面**（在 `# -*- coding: utf-8 -*-` 与模块 docstring 之前），原因是插入点按「首个非导入语句即停」计算，而本文件第一个语句是 docstring。已改为「取全部顶层导入的最末行」再插入；修复后 docstring 位置与编码声明均正确。经验：给这类模块加转发导入时，插入点必须是**既有导入块之后**，不能用「首个非导入节点」。

## 诚实边界

- 本轮是**方法体零改动的搬迁**：证据是 AST 断言、`__mro__`、逐名 `hasattr`、架构门禁与定向用例；未实机点击云朵气泡（GUI 会话在本环境超时，见 R1619／R1620 说明）。
- 全量安全全量最后一次真实通过仍是 **R1605/e59e513**；R1606–R1621 未跑全量，最终定性以 post-commit 后台 `.git/auto-full-safe-result.json` 为准。