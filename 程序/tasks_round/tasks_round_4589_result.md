# R4589 开发结果
<!-- round-evidence: {"commit_base": "7d3ee614e", "credential_hits": 0, "evidence_sha256": "0bb84e95dadbb118", "exit": 0, "failed": 0, "passed": 289, "round": 4589, "tests": "run_selftests.py -k test_skill_repo_import test_skill_archive_import test_skill_remote_import test_skill_user_layer test_skill_security test_skill_lifecycle test_round_gate test_script_contract test_stage_flow_summary test_workflow_writing_stages"} -->

## 三问回答

1. **本轮属于 §3 哪种类型？**
   功能轮（含跨页面按钮/右键菜单统一布局规则落地与内置残余 SKILL 清理迁移）。需求与设计先行同步至 `docs/process/用户沟通与要求标准.md`（规则 22a）、`docs/specs/05_UIUX与交互规范.md`（§17 `REQ-UI-UNIFY-1`、§18 `REQ-UI-SKILL-PAGE-1`）、`docs/stages/S01_剧本准备.md`（`REQ-S01-77/80/120`、`DES-S01-120`）及 `docs/records/对话需求追溯.md`。
2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟：`python -B smoke_test.py` 通过（**9/9**，含隐藏桌面探针）。
   - 全量架构门禁：变基前 `smoke_test.py --architecture` **709/709**；变基至 `master` `7d3ee614e`（`R4608`）后重跑 708/709（唯一 1 项为双侧合入使 `ProjectFilesPanel` 达 602>600 行，抽离模块级 `_append_delete_command` 压回上限内后 `test_complexity_ratchet`／`test_coverage_baseline`／`test_static_hygiene`／`test_static_names` **23/23** 全绿）。
   - 三项基线同步并通过门禁：目录结构基线（`governance/structure.json` + `structure-baseline.json`，`check_structure.py --check` `ok=true` 零新增违规）、外部包哈希基线（`维护记录/外部技能包哈希.json`）、分层/架构统一基数（`维护记录/测试分层基线.json` `skill_registry_count=0`、`维护记录/架构统一基数.json`）、行覆盖率基线（变基后重跑 `scripts/coverage_report.py` 实测 **239/239** 通过、**191/708** 覆盖，`runbook.md` §11 同步）。
   - 定向功能与隐藏桌面 GUI 回归全绿：变基后隐藏桌面实测 **394/394** 通过（`test_pet_skills_manage` 22/22、`test_cell_menu` 40/40、`test_files_panel_stages` 19/19 分片、`test_animatic_page` 7/7 分片、`test_skill_repo_import` 16/16、`test_model_picker_draft_keep` 12/12）；其余定向组 `test_skills`（135/135）、`test_idea_chat` 全组（185/185）、`test_skill_archive_import`（70/70）、`test_skill_remote_import`（73/73）、`test_skill_user_layer`（11/11）、`test_skill_security`（14/14）、`test_skill_lifecycle`（22/22）、`test_script_contract`（66/66）、`test_stage_flow`（61/61）、S01–S13 阶段范围与需求锚点及 UI 回归全绿；真实克隆 174 文件 `manju-laoli-skill` 仓库实测整包导入 `00 总包SKILL`、L0 主入口排序、跨阶段继承、二次更新与整包卸载闭环通过。
   - 安全全量（`run_selftests.py --all --safe`）：功能分支未运行，合入 `master` 时按 §5 补跑。
3. **欠账少了吗？**
   减少了残余内置 SKILL 历史债（清理 67 份废弃内置 `.skill.md`、4 份根目录旧包、2 个子模块引用与 9 条 `架构统一基数.json` 旧豁免项），`test_text_component_boundary` 下调 `desktop_idea_bubbles.py` 至 0；覆盖率基线随新增 L4 模块 `ui/pet_skills_views.py` 与变基合入刷新为 **708 模块 / 191 覆盖**。

---

## 本轮改动清单（五条主线）

### 1. S01 切换模型零刷新与 DSH 单一连续对话流（`REQ-S01-120`）
- 修改 `ui/desktop_script_pages.py`、`ui/desktop_idea_bubbles.py`、`ui/desktop_idea_chat.py`、`ui/desktop_idea_menus.py`、`domain/idea_chat.py`、`domain/idea_transcript.py`。
- 隐藏顶部按模型切页签栏（`idea_model_bar`），取消按模型过滤对话气泡；在模型选择器中切换模型仅更新配置与下次发送目标，不再重建或刷新聊天区气泡；每条回复气泡保留各自模型署名，用量摘要倒序取最近含用量/预算记录。

### 2. 复合总包自动识别与 `00 总包SKILL` 体系
- 修改 `orchestrator/skill_project_layer.py`、`orchestrator/skill_package_meta.py`、`orchestrator/skill_registry.py`、`orchestrator/stage_config.py`、`orchestrator/stage_flow.py`、`orchestrator/workflow_settings.py`、`ui/skill_import_service.py`、`ui/skill_archive.py`、`ui/skill_remote_service.py`、`ui/skill_lifecycle_service.py`。
- 新增 `SUITE_STAGE = 'suite'`（`00 总包SKILL`），支持仓库/URL/ZIP/本地目录导入时自动识别无根 `SKILL.md`、无 `stage` 字段的多子技能总控套件（如 `manju-laoli-skill`），整包落盘 `data/skills/00 总包SKILL/<规范名>/`、自动探测 L0 主入口（如 `short-drama-director`）、台账原子记 1 行、支持整包更新与整包回收卸载。
- `Registry.getForStage(stage)` 与 `stage_config` 自动把 `00 总包SKILL` 跨 01–13 阶段继承且支持单阶段独立开关；修复阶段容器目录含 ≥2 个子包时被误判为复合套装的边界缺陷，以及未安装 SKILL 的阶段被 `stage_flow.unchecked()` 误跳过的缺陷。

### 3. 彻底清理残余内置 SKILL 与用户层迁移
- 从 `程序/skills/` 清理全部 67 个内置 `*.skill.md`（13 个 `pipeline-*` + 54 个阶段技能）、4 个根目录遗留外部包、`skills-lock.json` 与 2 个技能子模块（同步 `.gitmodules`），仅保留干净的 `00 总包SKILL` + `01`–`13` 空目录骨架（`.gitkeep`）与 `templates/`。
- 原内置第三方包已迁入受忽略的用户层 `程序/data/skills/`（不入库）。
- 在 `skill_project_layer.RETIRED_BUILTIN_SKILL_IDS` 保留 67 个已退役内置 ID 只读兼容名单：旧项目 `skill_config.json` / `预设.json` 中的退役内置 ID 静默跳过不阻断发送，而用户自装但未加载/被删除的 SKILL 仍照常阻断。
- 更新 `contract/script_manifest_schema.py`（5 类 manifest 产出者统一为显式 `stage:*`，保留 `LEGACY_STAGE_PRODUCERS` 只读兼容）、`orchestrator/script_skill_report.py`、`配置/SKILL/预设.json`、`维护记录/基准脚本/round_gate.py`。

### 4. SKILL 管理页 DSH 重构（`REQ-UI-SKILL-PAGE-1`）与阶段配置面板总包支持
- 新增 L4 模块 `ui/pet_skills_views.py`（已登记 `tests/architecture/_layers.py`），重构 `pet_skills_manage.py` 与 `ui/pet_skill_tree.py`，同步 `ui/pet_settings_ui.py`。
- 支持设置窗内嵌（`skills_page`）与独立窗口（`open_manager` `1120×760`）双入口：顶部作用域分段（全部 / 项目版 / 全局版）＋右上统一全局操作栏（`+ 导入 SKILL`、`检查更新`、`体检`、`刷新`、动态 `残留包管理…`）；左侧固定宽阶段目录（全部阶段 / `00 总包` / `01`–`13`）带实时数量徽章；右侧顶部 `CompactLineInput` 搜索栏（`Ctrl+F` / `Esc`）＋两级树（技能包 → 子技能，`00 总包` 首位标示 `L0 主入口`）＋6 段标准右键菜单＋下方可折叠完整 Markdown 预览与原地编辑器（`agent.core.save_text` 原子写入与未保存脏守卫）。
- 导入弹窗收敛为单层直达界面（目标阶段默认跟左侧目录联动、统一地址输入直达提交 + 本地快捷 `文件` / `文件夹` / `ZIP`）。
- 更新 `ui/skill_panel.py`（修复空阶段跳过操作栏导致 `external_package_hint` 缺失的缺陷并支持 `getForStage`）与 `ui/skill_panel_support.py`（总包带 `（总包）` 标识）。

### 5. 长期交互规范（`REQ-UI-UNIFY-1`）与全项目按钮/右键菜单盘点对齐
- 写入 `docs/process/用户沟通与要求标准.md` 规则 22a 与 `docs/specs/05_UIUX与交互规范.md` §17：同类操作按钮固定位置（弹窗底栏次按钮左/主按钮右；危险操作右端分隔）、右键菜单统一 6 段顺序且危险操作置底加分隔线。
- 统一对齐：`ui/desktop_files_panel.py`、`ui/desktop_idea_menus.py`、`ui/desktop_asset_pages.py`、`ui/desktop_storyboard_page.py`、`ui/cell_menu.py`、`app.py`、`ui/script_reading.py`、`ui/skill_panel.py`、`ui/skill_panel_workflow.py`、`ui/tts_settings.py`、`ui/qwen_setup_dialog.py`、`ui/ui_stage_popups.py`、`ui/ui_usage_detail.py`、`ui/task_center_ui.py`。

---

## 提交状态与合入说明

- **提交状态**：已变基至 `master` `7d3ee614e`（`R4608`，包含 `codex/s04-workbench-spec` 与 `codex/master-regression-repair`），活跃车道冲突检查归零，经 `scripts/dev.py commit` 提交至分支 `codex/dsh-skill-ui-cleanup`（证据文件 `tasks_round/evidence/R4589.json`，结果头由提交脚本自动落印 `round-evidence`），未 `git push`。
- **隔离边界**：未触碰、未暂存 `.agent-tmp/`（工作树根部历史留存）、`程序/data/`（受忽略的用户层，含迁移后的 6 个第三方 SKILL 包）与 `程序/project_status.md`（按规则仅在 `master` 更新）。
- **合入与生效步骤**：
  1. 合入 `master` 前按 `AGENTS.md` §5 补跑安全全量（`run_selftests.py --all --safe`），随后在主工作区经 `scripts/dev.py merge codex/dsh-skill-ui-cleanup` 合入；
  2. 合入后彻底退出并重启桌面应用，验证 S01 切换模型无刷新、SKILL 管理页 DSH 布局与原地编辑，以及从仓库导入 `manju-laoli-skill` 自动归入 `00 总包`。
