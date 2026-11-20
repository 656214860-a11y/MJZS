# 工程文档入口

本目录是开发者查阅需求、设计、流程与证据的唯一导航入口。根目录保留的标准入口/既有权威仅链接到此导航，不复制第二份正文。文档移动/合并记录见 [迁移台账](records/文档迁移台账.md)；机器目录协议见 [governance](../governance/README.md)。

## 按任务查阅

| 任务 | 唯一入口 |
|---|---|
| 产品范围、用户故事、验收 | [产品需求规格](requirements/产品需求规格.md) |
| 系统实现设计 | [七册设计规格](specs/README.md) |
| 账户、会员与API完整契约 | [07 §7.9](specs/07_业务域规格.md#79-账户与会员完整设计) |
| 阶段需求和设计 | stages/S01–S13，对应下表 |
| 架构决策 | [ADR索引](adr/README.md) |
| 目录规则及CI结构检查 | [目录协议](../governance/README.md) |
| 发布、验收与恢复流程 | [发布检查单](process/发布检查单.md)、[联调出口基线](process/联调测试出口基线.md)、[安装更新与恢复](review/安装更新与恢复方案_A15.md)、[运维手册](../runbook.md) |
| 版权/计费等独立契约 | [生成失败](contracts/生成服务失败处理契约.md)、[模型预算](contracts/模型金额预算.md)、[不可破坏契约](contracts/已知坑与不可破坏契约.md) |
| 练习与人工替代 | [雨夜修伞](../resources/examples/rainy_umbrella/开始练习.md)、[失败处理](process/制作失败与人工替代.md)、[旧版编剧指南](guides/编剧功能说明.md) |
| 文档登记及迁移证据 | [登记表](records/工程文档登记表.md)、[账户逐项映射](records/账户设计条款迁移映射.md)、[对话需求追溯](records/对话需求追溯.md) |

## 按职责归档

requirements放需求，不放实现；specs放现行设计；stages保留REQ/DES；adr只记录取舍；process放可执行流程；guides面向用户；contracts放独立现行契约；records存非权威证据和历史。review保留高风险路径时序评审，不能仅因在review就视作当前验收通过。轮次任务及结果留在tasks_round；维护历史留维护记录，本轮不重写历史。

标准根入口仍各司其职：[架构](../architecture.md)、[项目地图](../PROJECT_MAP.md)、[UI取值](../design_tokens.md)、[UI组件](../ui_components.md)、[数据字典](../data_model.md)、[任务状态](../task_states.md)、[安全](../SECURITY.md)、[变更日志](../CHANGELOG.md)。没有职责不创建空目录，不新建同主题日期副本。

## 阶段条款

每阶段只有一份需求/设计正文，直接修改，不复制版本：`REQ-Sxx-nn → DES-Sxx-nn → 测试`。编号删除不复用。状态区分已实现、部分实现、未实现、待裁决；历史测试数字不是当前凭据。全局分层以architecture和AGENTS唯一权威表为准。

| 阶段 | 文件 |
|---|---|
| S01 | [剧本准备](stages/S01_剧本准备.md) |
| S02 | [剧本结构](stages/S02_剧本结构.md) |
| S03 | [初步分镜](stages/S03_初步分镜.md) |
| S04 | [分镜预演](stages/S04_分镜预演.md) |
| S05 | [资产管理](stages/S05_资产管理.md) |
| S06 | [连贯性清单](stages/S06_连贯性清单.md) |
| S07 | [分镜定稿](stages/S07_分镜定稿.md) |
| S08 | [首帧管理](stages/S08_首帧管理.md) |
| S09 | [白模预演](stages/S09_白模预演.md) |
| S10 | [视频生成](stages/S10_视频生成.md) |
| S11 | [配音与字幕](stages/S11_配音与字幕.md) |
| S12 | [后期剪辑](stages/S12_后期剪辑.md) |
| S13 | [质检与交付](stages/S13_质检与交付.md) |

## 新增或移动文档

先确认唯一主题与owner，再选职责目录；在登记表登记，跑doc_registry与结构检查、链接检查。移动前列所有消费者，移动后修当前引用/代码/测试/分发；历史路径由迁移台账追溯，不留第二份权威正文。示例JSON与媒体属于resources而非开发docs，分发计划必须验证它们仍在包中。
