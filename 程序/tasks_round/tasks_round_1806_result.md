# R1806：结构治理轮——拆 desktop_idea_chat.IdeaChatMixin 的气泡方法集（批次 B-2）

1. 本轮类型：§3 结构治理轮（方法体零改动的搬迁，不改行为）。

2. 测试与基线：
   - 迁移脚本先断言被迁代码引用的模块级名字只来自可原样复制的导入或同批迁出的常量，不与原模块成环。
   - 迁移后对照迁移前快照：`desktop_idea_chat` 模块公开名 40 个零缺失（只多 `IdeaBubblesMixin`）、`IdeaChatMixin` 59 个成员零丢失、大写常量值逐个相同（`desktop.py` 与 `test_req_s01_anchors` 依赖的 `BUBBLE_*` 照旧可从原模块取）、`MRO == [IdeaChatMixin, IdeaDeferredMixin, IdeaBubblesMixin, object]`，`import desktop` 通过。
   - 架构门禁 384 条 + `idea_chat`／`req_s01`／`ui_edges`／`desktop_compact`／`desktop_idea`／`bubble`／`writing_restart` 相关共 676 条：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿。未实机点气泡（GUI 实机项仍待人工）。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| 新增 `desktop_idea_bubbles.py`（400 行，L4） | `IdeaBubblesMixin`：气泡排版（`refit_bubbles`／`bubble_font`／`bubble_margins`…）、折叠与选取复制、点击与删除恢复、编辑守卫与提交（`guard_bubble_edit_*`／`start_bubble_edit`／`finish_bubble_edit`）、`add_bubble`、思考气泡共 25 个方法（两段不相邻的区间，中间的附档方法留在原处）＋ 9 个 `BUBBLE_*` 常量 |
| `desktop_idea_chat.py` | 1500→1116 行；`IdeaChatMixin(IdeaDeferredMixin, IdeaBubblesMixin)`；`BUBBLE_*` 按原名转发（`BUBBLE_TIME_FONT` 在 `show_conversation` 里仍被用到） |
| `_layers.py`、`_scan.py`（`DESKTOP_PARTS`）、`architecture.md` | 登记新模块 |
| `test_complexity_ratchet.py` | `IdeaChatMixin` 类上限 1392→1031（实测 1016） |
| `覆盖率基线.json`、`runbook.md` §11 | 重跑工具刷新：298 个生产模块，50 个有行覆盖，8 组目标用例全通过 |

## 诚实边界
搬迁没改任何方法体，所以未补等价测试，证据是前置断言、快照对照与既有 676 条用例；Tk 实机观感未验。
