# R526 结构治理轮：R525 I/J/K 架构登记与文档漂移整改

## 轮次结论

- 本轮是结构治理轮（子场景：执行），来源为 `tasks_round/tasks_round_525_result.md` 的 I/J/K；仅改分层登记、测试归属与权威文档，不改产品运行行为或用户项目数据。
- 测试：附件服务单测 1/1、`tests.test_idea_chat`、架构门禁 93/93 与默认冒烟 8/8 均通过。历史全量安全基线仍为 3,230/3,230，未伪造为本轮结果。
- `project_status.md` 的欠账未减少：R182 结构专项与白模真机授权待办不在本轮范围；R525 发现的登记/文档漂移项已闭环。

## 实施条目

1. I1/J2：检查 `skill_panel.py` 直接导入 Tk、创建配置面板并维护窗口状态，裁定其属于 L4 UI；将 `tests/architecture/_layers.py` 的错误 L3 登记移至 L4。未发现 L3 反向导入 `skill_panel`。
2. I2/J1：将 `idea_attachments` 登记为 L2，并在 `tests/architecture/test_layers.py` 新增专用断言，确认其已登记且不依赖更高层；通用分层扫描因此开始覆盖该服务。
3. J2：依据 `skill_registry.py` 的递归扫描事实，校对 `architecture.md` 的实际阶段目录：`01 剧本准备SKILL`、`02剧本整理SKILL`、`03初步分镜SKILL`、`04资产管理SKILL`、`05连贯性SKILL`、`06分镜定稿SKILL`、`07首帧管理SKILL`、`08白模预演SKILL`、`09视频生成SKILL`、`10配音字幕SKILL`、`11后期剪辑SKILL`、`12质检交付SKILL`；并将 `idea_attachments` 写入 `PROJECT_MAP.md`。
4. J3：将 `AGENTS.md` 第 2.5 节的旧全量数 3,205 更正为 3,230；当前验证基线段落保留为未来更新的单一说明位置。
5. K2/K3：把只覆盖 `idea_attachments.prepare()` 的测试原样从 `tests/test_idea_chat.py` 移到新增 `tests/test_idea_attachments.py`；保留前者的桌面选档、状态刷新与发送集成覆盖。测试改动仅因模块职责迁移，原断言未弱化、未删除。

## 文件范围

- `tests/architecture/_layers.py`
- `tests/architecture/test_layers.py`
- `tests/test_idea_chat.py`
- `tests/test_idea_attachments.py`
- `architecture.md`
- `PROJECT_MAP.md`
- `AGENTS.md`
- `project_status.md`

## 验证与自审

- 已通过：`D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_idea_attachments`（1/1）；`D:\漫剧制作助手\运行环境\Python\python.exe -m unittest -q tests.test_idea_chat`（静默成功退出）。
- 已通过：`D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`（93/93）；`D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`（8/8）。
- 自审：只改 R525 指定的登记、文档和测试归属；未新增越界依赖，未修改用户数据；本轮涉及的文档路径均与实际阶段目录一致。
