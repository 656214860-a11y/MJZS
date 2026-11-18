# ADR-0003 十三阶段流水线固定顺序

- 状态：已接受
- 日期：2026-11-19（补记；决策早于记录日）
- 层级 / 阶段：L3 / 全局
- 取代／被取代：—

## 背景与问题

产品是 13 个制作阶段的固定流水线（剧本准备→剧本结构→初步分镜→分镜预演→资产管理→连贯性清单→分镜定稿→首帧管理→白模预演→视频生成→配音与字幕→后期剪辑→质检与交付）。阶段顺序、显示名、目录与依赖若由各模块各自硬编码，会出现编号漂移（历史上 `02_assets` 旧标识、R1124 前 `04资产管理` 旧编号）与多源不一致；用户与 SKILL 预设也按固定顺序消费阶段。

## 考虑过的选项

- **A. 阶段顺序硬编码在各消费模块**：多源登记必然漂移，已被编号漂移史证伪。
- **B. 固定顺序以 `pet_bus.STAGES`／`STAGE_NAMES` 为唯一权威，数据依赖走 `stage_flow.DEPENDS`，业务前置走 SG 门禁**（现行方案，见 `architecture.md` §4、`AGENTS.md` §2.2）。
- **C. 阶段可配置、可任意跳过**：未采纳——流水线顺序是产品契约，跳过由门禁与人工路径控制，不由顺序本身放开。

## 决定

13 阶段顺序唯一权威为 `pet_bus.STAGES`／`STAGE_NAMES`；阶段目录契约由 `stage_layout.validate_stage_contract()` 守卫；阶段间数据依赖声明在 `stage_flow.DEPENDS`；业务前置（如「先完成并采用初步分镜」）由 SG 门禁表达；手动、自动、三虎启动统一走 `stage_handler_registry.start()`（§2.3 规则 17）。新增或调整阶段必须同步 `pet_bus`、`stage_layout`、`stage_parallel.CONFIG`、`docs/stages/` 与架构门禁清单。

## 后果（含不可破坏的约束）

- 阶段 ID 与顺序不可随意增删或重排；`stage_layout.validate_stage_contract()` 是硬闸。
- 门禁 SG-A…SG-05 及各阶段完成核验（`stage_completion_service`）构成顺序的执行面，模型文字与界面提示不算完成证据（§2.3 规则 20）。
- 旧目录只读兼容、新写入走 `stage_path_service`（§2.3 规则 19）。
