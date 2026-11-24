# R4389 结果：S04 分镜预演重做需求与详细设计规格（REQ-S04-70…99 / DES-S04-20…25）
<!-- round-evidence: {"commit_base": "67fd96c99", "credential_hits": 0, "evidence_sha256": "1bfa36d09fe4c715", "exit": 0, "failed": 0, "passed": 47, "round": 4389, "tests": "run_selftests.py -k test_stage_doc_sections test_agent_doc_budget test_requirement_traceability test_design_coverage test_req_s04_anchors"} -->

## 开头三问

1. **本轮类型**：纯文档规格轮（需求设计角色，车道 `codex/s04-animatic-spec`，基准 `67fd96c99` R4388）。按 2026-11-25 用户需求对齐五项裁决（参考库分类配图、逐镜临时 TTS 与三轨声音、锁定回写 S03 时长并备份历史版本、可插拔草图生成器接口、少按钮新布局）更新 `程序/docs/stages/S04_分镜预演.md`，并改判 REQ-S04-62 与「非目标」中时长回写边界。未改任何 `.py`、测试文件与守卫常量。
2. **测试与基线**：文档与 S04 锚定五件套（`run_selftests.py -k test_stage_doc_sections test_agent_doc_budget test_requirement_traceability test_design_coverage test_req_s04_anchors`）47 条全绿（2.1 秒、0 红、跳过 0、退出码 0）；`smoke_test.py --architecture` 708 条 OK（276.5 秒、0 红）。默认冒烟与全量未跑（纯文档规格轮）。
3. **欠账**：无新增欠账。新增 REQ-S04-70…99 与 DES-S04-20…25 均标 `⬜`，已拆分为 5 张独立 W2 实现卡（`S04-REF-LIBRARY`、`S04-AUDIO-TRACKS`、`S04-SKETCH-BACKENDS`、`S04-TIMELINE-LOCK`、`S04-PAGE-REDESIGN`）入队。

## 缺陷复现方式

纯文档规格轮，不改产品代码与测试断言；新测试先红后绿由 5 张 W2 实现卡逐卡执行并由验收复核 `verify --red-check`。

## 改了哪几处（文件:行号）

`程序/docs/stages/S04_分镜预演.md`：
- 第 52 行：更新 **REQ-S04-62** 状态为 `🟡`，注明 2026-11-25 用户改判——媒体成果仍不上游/下游消费，但锁定时的逐镜时长按 REQ-S04-90 回写 S03 已采用分镜。
- 第 54–108 行：新增「2026-11-25 重做：参考库、逐镜声音、时间线与锁定」节，定义 **REQ-S04-70…73**（参考库）、**REQ-S04-74…77**（三轨临时声音）、**REQ-S04-78/79**（可插拔草图生成器与导入替换）、**REQ-S04-80…85**（时间线、单镜版本、版本化视频与 S03 变更重建）、**REQ-S04-90/91**（锁定与原子时长回写事务）、**REQ-S04-95…99**（少按钮新布局与功能入口保真）。
- 第 110–115 行：同步「非目标（明确不做）」第四条，明确预演不改分镜内容、唯一例外是锁定时按 REQ-S04-90 回写逐镜时长。
- 第 151–171 行：新增 2026-11-25 重做设计表与 **DES-S04-20…25**，明确 4 个纯 L2 模块零新增同层边（回调由 L3 注入）、`artifact_schema` 登记 `animatic_timeline`、`animatic_manifest` 保留 `schema_version: 1` 扩展兼容、L4 新页面 `ui/animatic_page.py` 复用 `asset_thumbs`／`shared_input.set_stage_action`／`set_status_segment` 且零新增弹窗。
- 第 187–193 行：更新「测试锚定」表，按 STR006 匹配源码同名测试文件或复用既有测试文件，不引入孤立测试。

## 验证输出摘要

- 定向文档与 S04 锚定五件套：`共 47 条用例，2.1 秒；0 个文件有红`，`ALL TESTS PASSED`。
- 架构门禁 `smoke_test.py --architecture`：`Ran 708 tests in 276.451s`，`OK`，`✅ 架构治理测试：tests/architecture`。
- 提交与 commit hash：见本次 `dev.py commit` 生成记录；未 push。
