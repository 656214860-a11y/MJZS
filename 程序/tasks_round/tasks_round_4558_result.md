# R4558 模型管理页 DSH 风格重构、多路线故障转移与 R4556 设置内嵌融合（REQ-UI-MODEL-PAGE-2）
<!-- round-evidence: {"commit_base": "59e70ff15", "credential_hits": 0, "evidence_sha256": "6ce4e72c4439be1f", "exit": 0, "failed": 0, "passed": 270, "round": 4558, "tests": "run_selftests.py -k test_model_routes test_settings_models_redesign test_model_manager_actions test_ui_batch7_settings_models test_pet_settings test_model_pool test_model_probe_layers test_model_failure_route test_model_gateway_robustness test_model_delete_presets test_model_delete_stays_deleted"} -->

## 三问

1. **本轮属于 §3 哪种类型？**
   功能轮（3.1）：经用户确认按推荐路径将 `codex/wip-r4558` 叠放至 `R4555 → R4556 → R4557`（`59e70ff15`）之上，先更新 `docs/specs/05_UIUX与交互规范.md`（`REQ-UI-MODEL-PAGE-2`）、`docs/adr/0011-model-probe-availability.md`、`architecture.md`、`docs/process/外部依赖清单.md`、`docs/process/外发内容清单.md` 与 `runbook.md` §11，再实现 L1 多路线基础设施，并将新版 DSH 主从多路线界面完整融合进 R4556 的设置窗右侧内嵌宿主（`manager_page`）、独立弹窗（`open_manager`）、左上角「语音识别」分段与 5+ 主流预设可编辑下拉框。
2. **测试跑了吗、三个基线过了吗？**
   - **默认冒烟基线**：`smoke_test.py` **9/9 通过**（8 项默认检查 + 隐藏桌面自检，退出码 0）。
   - **完整架构门禁**：`smoke_test.py --architecture` 在合并树上实测 **711/711 全绿**（修复 `detect_program` 参数签名后复测 36 项受影响架构门禁全绿）。
   - **全栈受影响回归**：覆盖 R4555–R4558 共 16 组测试套件（含 `test_settings_models_redesign` 10/10、`test_close_button_unify`、`test_sanhu_pointer_avatar_menu`、`test_model_routes` 15/15、`test_pet_ui` 642/642、`test_model_manager_actions`、`test_ui_batch7_settings_models`、`test_pet_settings`、`test_model_pool`、`test_model_probe_layers`、`test_model_failure_route`、`test_model_gateway_robustness`、`test_model_delete_presets`、`test_model_delete_stays_deleted`、`test_ui_theme`、`test_button_consistency`）全部通过，**0 失败、0 跳过**；行覆盖率基线重测 18 组 236 条通过（184/702），L0/L1 分支覆盖率基线重测 146 组 2476 条通过（104 实体 1879/3250，`model_routes.py` 建立下限 `25.0%`）。
   - **全量回归凭据（`full-safe-receipts.json`）**：本轮在功能分支 `codex/wip-r4558` 执行，未运行 `--all --safe`；权威记录为 `last_full_safe_all_round: 4264`（2026-10-03），合入主干前应按 §5 补跑完整安全全量。
3. **欠账少了吗？**
   是：`层间合规清单.json` `LR-07` 从 `176` 下调至 `175`；消除 `ui/pet_models_tabs.py` 对 API 根地址的重复硬编码（统一从 `infra/model_routes.py` 单一真源派生）；修复了阻断分支覆盖率刷新的两处既有测试隔离问题（`test_platform_tools.py` 清空 `_TLS_CACHE`、`test_page_paint_metric.py` 补用 `_wait_for_paint`）；新增 `model_routes.py` 分支覆盖下限 `25.0%` 且未下调任何历史下限。

---

## 一、与 R4555–R4557 并行栈的融合

- 完整保留 `R4555`（5 处统一关闭 `×` 按钮）、`R4556`（设置左栏 8 枚专属图标、无复用码位、`pet_settings_ui.py` 与 `speech_settings_ui.py` 零改动兼容）及 `R4557`（三虎左下指向、三模式日夜头像与右键菜单）。
- `pet_models_ui.manager_page(frame, pet, win=win)` 在设置窗右侧直接渲染新版 DSH 主从多路线视图（左栏 240px 卡片＋右栏自上而下路线配置），内嵌顶栏提供次按钮「保存当前」，设置窗底栏主按钮「保存」经 `seam['save']()` 统一保存当前模型或语音识别设置并关闭，切页/关窗受 `leave_page` / `is_dirty` 脏守卫保护。
- 独立窗口 `pet_models_ui.open_manager(pet)` 保持向后兼容（1180×820，左栏 320px，顶栏右置主按钮「保存」写入并留页，移除旧底栏）。
- 左上角四段切换 `API | Desktop | CLI | 语音识别`（取消独立「语音识别…」按钮），切到「语音识别」原地展示语音面板并接通脏守卫与保存。
- 全部 12 个非密钥单行表单项升级为 5+ 项主流预设的可编辑 `EditablePresetBox`（随调用方式与 API 模态联动刷新）；API Key 保持 `PasswordInput(mask='*', show='*')`（C12 红线无下拉）。

## 二、核心代码与文档变更

- **文档与登记**：`docs/specs/05_UIUX与交互规范.md`（§15 `REQ-UI-MODEL-PAGE-2`）、`docs/adr/0011-model-probe-availability.md`、`architecture.md`、`docs/process/外部依赖清单.md`、`docs/process/外发内容清单.md`、`runbook.md`（§11）、`docs/records/会话接续记录.md`。
- **L1 多路线基础设施**：新增 `infra/model_routes.py`（9 项服务商预设、旧单路线兼容与主路线镜像双写、按路线隔离 DPAPI 密钥、探测元数据持久化与 `config_version` 失效、`GET /models` 拉取、`execute_route_chat`/`stream` 故障转移）；增强 `infra/model_pool.py`、`infra/model_router.py`。
- **L4 DSH 主从与内嵌视图**：新增 `ui/pet_models_cards.py`（`CompactLineInput`、`EditablePresetBox`、`CollapsibleSection`、`ModelCardList`、`RouteCard`、`open_remote_model_picker`）；重构 `ui/pet_models_tabs.py`、`ui/pet_models_ui.py`；扩充 `ui/ui_theme.py` 日/夜间语义样式。
- **架构门禁与基线**：`tests/architecture/_layers.py`、`tests/architecture/test_shared_state_ratchet.py`、`维护记录/覆盖率基线.json`、`维护记录/分支覆盖率基线.json`、`维护记录/分支覆盖率下限.json`、`维护记录/层间合规清单.json`。
- **测试**：新增 `tests/test_model_routes.py`（15 条，含内嵌设置窗多路线闭环）；同步 `tests/test_settings_models_redesign.py`、`tests/test_model_manager_actions.py`、`tests/test_ui_batch7_settings_models.py`、`tests/test_pet_settings.py`、`tests/test_pet_ui.py`；修复 `tests/test_platform_tools.py`、`tests/test_page_paint_metric.py` 测试隔离。

## 三、提交记录

- 分支：`codex/wip-r4558`（叠放于 `59e70ff15` R4557 之上，未 `git push`，未改 `project_status.md`）。
- 经 `scripts/dev.py commit` 生成轮次证据 `tasks_round/evidence/R4558.json` 并随本提交入库。
