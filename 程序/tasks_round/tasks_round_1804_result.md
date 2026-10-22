# R1804：结构治理轮——拆 pet_cloud.Cloud 的定位几何方法集（批次 B-1）

1. 本轮类型：§3 结构治理轮（方法体零改动的搬迁，不改行为）。

2. 测试与基线：
   - 迁移由脚本完成，迁移前脚本先断言：被迁代码引用的模块级名字只来自“可原样复制的导入”或“同批一起迁出的常量／函数”，不会与 pet_cloud 成环（R1624 的坑）。
   - 迁移后逐项对照迁移前快照：`pet_cloud` 模块公开名 134 个零缺失（只多一个 `CloudPlaceMixin`）、`Cloud` 的 117 个成员零丢失、所有大写常量值逐个相同、`Cloud.__mro__ == [Cloud, CloudTimingMixin, CloudHintMixin, CloudPlaceMixin, object]`。
   - 架构门禁 384 条 + `pet_cloud*`／`pet_ui`／`leak_teardown`／`line_endings`／`coverage` 相关共 1029 条：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新，合入时三方合并采用 master 的头）外全绿。未实机点击云朵（GUI 实机项仍待人工）。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| 新增 `pet_cloud_place.py`（476 行，L4） | `CloudPlaceMixin`：贴片矩形／脸颊／锚点／窗口矩形／屏幕余量／翻转／避让三虎／原点／尾巴尖与多边形／定位窗口等 28 个方法；随方法迁出 21 个定位常量（`TAIL`、`MARGIN`、`PET_GAP`、`MAX_GAP`、`TIP_IN`、`MIN_BODY`／`MAX_BODY`／`MAX_BODY_DOWN` 等）与 `shape_root`、`shape_min_body`、`SHAPE_MIN_BODY` |
| `pet_cloud.py` | 1812→1357 行；`class Cloud(CloudTimingMixin, CloudHintMixin, CloudPlaceMixin)`；被迁出的 23 个名字按原名转发，`pet_cloud.TAIL` 等外部引用不变 |
| `tests/architecture/_layers.py`、`architecture.md` | L4 登记 `pet_cloud_place` |
| `test_module_size_ratchet.py` | `pet_cloud.py` 已降到 1500 以内，删除登记（登记表现为空） |
| `test_complexity_ratchet.py` | `Cloud` 类上限 1524→1115（实测 1100） |
| `维护记录/覆盖率基线.json`、`runbook.md` §11 | 按 runbook 重跑工具刷新：297 个生产模块，50 个有行覆盖，8 组目标用例全通过 |

## 诚实边界
搬迁没有改任何方法体，所以没有补等价测试，证据是 AST 前置断言、快照对照与既有 1029 条用例；Tk 实机观感未验。
