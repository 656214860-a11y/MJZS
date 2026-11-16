# R2937 结果：T10 包化——orchestrator/（L3 编排层）第二批 14 个控制器模块迁移
<!-- round-evidence: {"commit_base": "b1f4ad2d", "credential_hits": 0, "evidence_sha256": "8746babd0ac0408a", "exit": 0, "failed": 0, "passed": 638, "round": 2937, "tests": "run_selftests.py -k controller account idea_chat storyboard_final storyboard_page subtitle_export white_model workflow_context page_navigation recycle editing media_page asset_page asset_batch keyframe_page writing_api stage_execution"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --architecture` 架构门禁复测 **470/470 全绿**（首轮 6 红全部定位修复后二轮一遍过）；定向 57 个测试文件 638 条用例全绿；覆盖率基线重测 **502 模块／70 覆盖**。
3. **欠账少了吗**：是。T10 包化推进 orchestrator 第二批：`orchestrator/` 实体由 13 → 27 个，顶层 `*_controller.py` 族全部入包（14 个别名门面保留扁平名）。剩余 L3 重模块（stage_execution_service、writing_api、skill_orchestrator、stage_config、stage_parallel、workflow_settings、skill_registry 等约 31 个）、L4 大模块（desktop/pet_ui/ui_widgets/app）与 `app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | 14 个 L3 控制器 `git mv` 入 `orchestrator/`：account_controller、asset_batch_controller、asset_page_controller、editing_page_controller、idea_chat_controller、keyframe_page_controller、media_page_controller、page_navigation_controller、recycle_recovery_controller、storyboard_final_controller、storyboard_page_controller、subtitle_export_controller、white_model_persistence_controller、workflow_context_controller。入选口径：`_layers.py` 登记 L3、静态+动态扇出低、文件内聚的控制器簇；stage_execution_service/writing_api/skill_orchestrator 等重枢纽留待后续批次。 |
| 别名门面 ×14 | 顶层同名 `.py` 为 `sys.modules[__name__] = orchestrator.<名>` 别名门面；测试扁平名、`mock.patch("flat....")` 补丁面与私有模块状态全部保持（14/14 `ALL ALIAS OK` 导入冒烟验证）。 |
| 消费方 import | 18 个生产文件改包路径导入：desktop 及 desktop_* 页面族（account/asset/idea_bubbles/idea_chat/idea_deferred/lifecycle/media/project/storyboard_page/page_nav/auto_flows）、asset_batch、skill_tools、stage_execution_service、storyboard_files、white_model、writing_api。`import X` 形式统一补 `as X` 保绑定名（沿用 R2935 教训）。 |
| 动态字符串引用 | `desktop_idea_chat.py:107/113` 两处 `getattr(self, 'idea_chat_controller', None)` 为 Desktop 实例属性访问（控制器实例挂载点），非模块名导入，实体迁移后属性名不变，无需改写；idea_chat 定向用例全绿佐证。 |
| 架构测试包感知 | `_scan.py` 新增 `entity_file()` 解析实体真实路径；7 个边界测试文件（migrated_ui/final_bundle/storyboard_edit/storyboard_final_selection/subtitle_export_publication/idea_attachment_publication/writing_publication）的 ImportFrom/Import 断言放宽为「扁平名或包名均可、类名必须命中」，语义断言原样。 |
| 棘轮台账 | `架构统一基数.json`：`storyboard_final_controller.py:FinalStoryboardController.save_edited:json.loads` 条目路径改 `orchestrator/storyboard_final_controller.py`，分值与 exempt 理由不动；曾误触发整文件 CRLF 归一化，已 `git restore` 后仅重放目标条目。 |
| 基线与文档 | `覆盖率基线.json` 重测 **502 模块／70 覆盖**（488+14 实体）；`runbook.md` §11 同步（502/70/432）；`architecture.md` orchestrator 目录树 13→27；`PROJECT_MAP.md`、`distribution_manifest.md`（`程序/orchestrator/**` glob 已覆盖，无需改）同步。 |

## 验证记录

- `smoke_test.py`（主工作区解释器）：8/8 通过。
- `smoke_test.py --architecture`：首轮 6 红 → 修复后 **470/470 全绿**（当轮实测）。
- 定向：`run_selftests.py -k <25 个关键词>` → 57 个测试文件 **638 条用例 0 红**（含 14 个控制器专属测试、account/idea_chat/storyboard/subtitle_export/white_model/recycle/editing/media_page/asset_page/asset_batch/keyframe_page/writing_api/stage_execution 消费方族）。
- 导入冒烟：14 个 `orchestrator.*` 实体 + 14 个扁平门面全部可导入，全部别名一致，无循环导入。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行）。

## 过程损耗（如实）

- 功能工作树缺测试环境件：`维护记录/基准历史.json`（gitignored，已从主工作区复制恢复）、pinned 外部技能仓（按 `skill_package_pins.py` 钉住 commit 检出，`--check` 3 包 0 问题）——均属环境补齐，非产品改动。
- 首轮架构 6 红根因：①基准历史缺失（环境）②覆盖率基线未同步（502 vs 登记 488）③技能引用测试缺嵌套检出（环境）④⑤两个边界测试硬编码扁平 `ImportFrom` 名（已包感知化）⑥棘轮台账旧路径命中（已改包路径）。全部最小修复后二轮 470/470。
- `架构统一基数.json` 编辑时整文件被重写为 LF 造成数千行假 diff，`git restore` 回滚后仅重放单条目，避免无关 churn。

## 下一步（T10 后续批次）

- 剩余 L3 约 31 个：stage_execution_service、writing_api、skill_orchestrator、stage_config、stage_parallel、workflow_settings、skill_registry 等重枢纽，宜按「一个枢纽＋其私有簇」分批，扇出分析先行。
- L4 大模块 desktop/pet_ui/ui_widgets/app 与顶层前缀族（pet_bus、desktop_settings 等）逐批同法迁移；`_scan.py` 包感知与 `import X as X` 规则直接复用。
- `app.py`、`pet_cloud.py`（实体已在 ui/）、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
- 全部实体入包后另立清理轮移除顶层别名门面（需单独授权）。
