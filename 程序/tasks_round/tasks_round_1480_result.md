# R1480 结构治理轮：拆分 desktop.py 步骤 1（无人值守流程方法迁出）

1. **本轮类型？** 结构治理轮（只搬代码，不改逻辑）。
2. **测试与基线？** 相关定向（desktop／pet_ui／automation／auto_／asset_gating／final_page／cloud_monitor 等）全部通过；默认冒烟 8/8；架构门禁首次 4 项红，均为“被检代码换了文件／行号”，处理后通过（见下）；全量见提交后运行。
3. **是否欠账？** 改了层级登记表（风险路径），提交后须全量转绿。

## 改动

- 新增 `desktop_auto_flows.py`（L4）：`AutoFlowsMixin` 原样承载 29 个方法共 625 行——`_tick_auto_final／edit／keyframe／previs／asset／video／handoff／adopt／gates`、`poll_auto_*`、`poll_unwatched_cloud`、`_tick_cloud_monitor`、`_tick_download_inbox`、`_poll_auto_*_result`、`_drain_auto_*_result`、`kick_unattended`、`busy_production`、`final_holding`、`final_missing_assets`；常量 `UNATTENDED_NEXT／UNATTENDED_BACKOFF_FLOOR／ASSET_RETRY_LIMIT` 一并迁入，`desktop` 里重新导入（`desktop.UNATTENDED_BACKOFF_FLOOR` 等旧引用照常可用）。
- `Desktop(AutoFlowsMixin)`：继承获得全部方法，调用方与测试对 `Desktop.<方法>` 的引用不变；`desktop.py` 7820 → 7241 行。
- 依赖核对：迁出方法用到的模块级名字逐个解析（`time／queue／threading／Path／asset_resume／media_root／read／PAGE／LOGGER` 等），新模块无未使用导入；测试对 `desktop.time.monotonic` 等的 patch 作用于共享的 `time` 模块，仍然有效。

## 架构门禁的 4 处调整（断言未动）

- `test_handoff_publication_boundary`、`test_edit_publication_boundary`：被检的 `poll_auto_handoff`／自动粗剪标记调用已在新文件，只把被检文件改为 `desktop_auto_flows.py`。
- `test_module_size_ratchet`：`desktop.py` 登记上限 7850 → 7300（棘轮向下固化）。
- TODO 注释快照：迁出的注释换了文件名与行号，按原分类逐条对应更新。
- 层级登记表登记 `desktop_auto_flows`（L4）；`architecture.md`、`PROJECT_MAP.md` 同步。

## 有意没做

- 没有把这些方法改写成 L3 无 Tk 服务：它们与 `self.auto_*` 状态、状态栏、三虎播报紧耦合，强行下沉需要重新设计注入接口，风险远大于这一步的收益。后续步骤 2（Agent 派发与消息发送）、步骤 3（页面构建拆成 `*_page_ui.py`）另行成轮。

## 提交

已提交，见 git log 标题 `R1480:`。
