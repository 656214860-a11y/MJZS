# R4221 · DOC-LOST-RECOVER 丢失需求清单转 REQ/DES
<!-- round-evidence: {"commit_base": "ab54369a", "credential_hits": 0, "evidence_sha256": "ac14d1d8ed789f1e", "exit": 0, "failed": 0, "passed": 0, "round": 4221, "tests": "docs-only"} -->

本轮类型：纯文档轮（卡面指定；不改产品代码与测试）。
三问：本轮属需求登记类文档变更；测试跑了卡面指定的 `smoke_test.py --architecture`，700 条全绿；无新增欠账，纯文档不产生欠账。

## 补了哪些条目（文件：标题）

- `docs/stages/S01_剧本准备.md` §需求／§设计／测试锚定表：新增 REQ-S01-111 至 REQ-S01-116、DES-S01-111 至 DES-S01-116（全部 ⬜ 未实现、卡面已入队）
  - REQ-S01-111（LOST-04 → FEAT-SCRIPT-FILES）：剧本准备四文档生成链改造，去「已确认」前缀、可同时或逐个生成、被采用作后续参考
  - REQ-S01-112（LOST-06 → UX-CHAT-INPUT-EXTRAS）：聊天输入面板「自动接入」「快捷答复」、发送键重设计
  - REQ-S01-113（LOST-09 → UX-CHAT-INPUT-EXTRAS）：其他页面 ✦／＋ 图标不可用，与剧本准备页一致
  - REQ-S01-114（HALF-02 → UX-CHAT-INPUT-EXTRAS）：占位提示「@引用文件，/快捷指令和 skill」核对
  - REQ-S01-115（HALF-03 → UX-S03-SEND）：图标勾选只作三虎自动执行、手动输入只调自选 skill 的边界核对
  - REQ-S01-116（HALF-01 → NAMING-INVENTORY）：应用输出文档统一命名「类型＋provider＋年月日」（跨阶段契约，因 `script_contract` 命名权威落点在本文档 DES-S01-20 而登记于此）
- `docs/specs/05_UIUX与交互规范.md` §12「丢失需求登记（2026-11-23，DOC-LOST-RECOVER）」：新增 UXR-01 至 UXR-07
  - UXR-01（LOST-01 → UX-SIDEBAR-PROJECT）：左侧阶段栏二级图标与项目图标合并
  - UXR-02（LOST-02 → UX-THEME-SIMPLE）：L4／L5 主题简约化，保留日／夜间模式
  - UXR-03（LOST-03 → UX-L5-DIALOGS）：L5 启动层弹窗与登录／会员界面简约重设计
  - UXR-04（LOST-05 → UX-MODEL-PAGE）：模型管理页默认选项与按钮布局
  - UXR-05（LOST-08 → UX-C1）：右侧项目文件图标去重与素材库／回收站图标重设计
  - UXR-06（LOST-07 → SANHU-FRAMEWORK-EVAL）：三虎桌面智能宠物框架评估
  - UXR-07（LOST-10 → DOC-PREVIEW-GUIDE）：用户亲眼验证修改效果的流程说明
- `docs/records/对话需求追溯.md`：新增 13 行（LOST-01..10、HALF-01..03），每行含来源时间、需求摘要、去向 REQ/DES 或 UXR、状态与拆分卡名
- `docs/requirements/产品需求规格.md`：本轮最终未改动。曾试加 REQ-APP-06/07/08，被架构门禁 `test_design_coverage` 拦下——新增 REQ-APP 必须在 `docs/specs/README.md` §4 覆盖映射表补行，而该文件不在允许修改清单内；改放 UXR／REQ-S01 落点后门禁转绿，PRD 恢复原样

## 门禁

- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（工作目录 `程序`）
  - 首跑：退出码 1，`Ran 700 tests in 311.309s`，`FAILED (failures=1)`；唯一失败 `tests.architecture.test_design_coverage.DesignCoverageTests.test_every_app_requirement_has_a_landing_place`，断言 `Lists differ: ['REQ-APP-06', 'REQ-APP-07', 'REQ-APP-08'] != []`（PRD 的 REQ-APP 需求没有设计落点）
  - 改后复跑：退出码 0，`Ran 700 tests in 286.177s`，`OK`；`✅ 架构治理测试：tests/architecture`
- 默认冒烟、全量自测：卡面未要求，未跑

## 没验证的地方

- 各「半落地」缺口的代码现状（占位文案、skill 勾选边界、非剧本文件命名规则）只按清单描述登记，未逐行核对实现代码——留给对应编码卡。
- UXR-05（LOST-08）与 UX-C1 的细节重合度未逐条核对，条目内已标「细节待核对」。
- `git diff --check` 属验收角色复跑，执行者未运行。

## 提交

- 轮次：`4221`
- 提交说明：`R4221: DOC-LOST-RECOVER 丢失需求清单转 REQ/DES`
- 文件：`docs/stages/S01_剧本准备.md`、`docs/specs/05_UIUX与交互规范.md`、`docs/records/对话需求追溯.md`、`tasks_round/tasks_round_4221_result.md`（`产品需求规格.md` 经 PRD 回退后与基线一致，不入提交清单；commit hash 见完成报告）
