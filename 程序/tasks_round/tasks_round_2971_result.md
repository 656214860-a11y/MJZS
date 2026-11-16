# R2971 结果：功能轮——共享输入框 ✦／＋ 图标下拉面板（Slash 命令菜单风格）
<!-- round-evidence: {"commit_base": "5cbd3319", "credential_hits": 0, "evidence_sha256": "f90df5e1afa28e71", "exit": 0, "failed": 0, "passed": 806, "round": 2971, "tests": "run_selftests.py -k test_shared_input_ui test_shared_input_stages test_stage_reasoning test_skills test_skill_command test_pet_ui"} -->

## 三问

1. **轮次类型**：功能轮（§3.1）。用户任务书：输入框的 skill 图标与添加图标改为与「/」补全同款的下拉面板（不再弹窗）；模型下拉器的「+ 添加模型…」与 skill 图标的导入入口收口进「＋」下拉；技能名只显示安装包原始 `name`（不映射别名、不拼 displayName、去 "skill" 字样）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 **8/8**；`smoke_test.py --architecture` 架构门禁当轮实测 **470/470 全绿**；`--affected desktop_shared_input desktop_shared_menus stage_model_picker` 定向 794 条仅 2 红（`test_skills` 注册表计数 72≠73，环境性欠账见下）；定向 `test_shared_input_ui` 18 条、`test_shared_input_stages` 23 条、`test_stage_reasoning` 18 条、`test_skill_command` 12 条、`test_pet_ui` 全片、`test_ui_edges_pages` 中与本改动相关断言所在片段均绿。
3. **欠账少了吗**：是（就本轮范围）。`desktop_shared_input.py` 旧 `BaseDialog` 技能浮层与 `stage_model_picker.py` 的 `ADD_MODEL_LABEL` 尾项及死分支删除；覆盖率基线按新模块重测刷新（534→535 模块）；`test_skills` 技能计数欠账由 71→72（补齐三个 gitlink 技能子仓物化），剩 1 个缺口属不可用子仓，见「范围外记录」。

## 需求与设计（文档先行，§2.7）

- `docs/stages/S01_剧本准备.md` 新增 **REQ-S01-90／DES-S01-90**（共享输入框 ✦／＋ 下拉面板契约），修订 REQ-S01-82／DES-S01-82 尾句（「+ 添加模型…」迁移去向），追溯表登记四个测试文件。
- `architecture.md` R2893 段、`PROJECT_MAP.md` 阶段配置行同步新模块与交互口径。

## 实现

- 新增 L4 `desktop_shared_menus.py`（210 行）：`AnchoredPanel`（`background_card` 底＋`border_input_hover` 1px 描边的 `place` 浮层，与 `CompletionPopup.place` 同一锚定几何——下缘悬输入盒上沿、同宽左对齐、顶出屏幕贴顶）；`SkillPickPanel`（≤12 行，当前阶段技能在前；`IconLoader.check_indicator` 勾选＝本阶段默认、点击行插入 `/name `、悬停说明卡；无项目时不出勾选框）；`AddMenuPanel`（「添加附件」→`open_attachments`、「添加模型…」→`SharedStageInput.open_model_manager`→`StageModelPicker.open_model_manager`→`pet_models_ui.open_manager`、「添加技能…」面板内下钻「‹ 返回／从仓库导入／本地安装」→`skill_import_service` 同一管线）。
- `desktop_shared_input.py`（820 行）：✦ command 改 `open_skill_list`→`_show_panel(skill_panel)`，＋ command 由 `open_attachments` 改 `open_add_menu`；两面板互斥、整窗 `<Button-1>` 外点监听（随输入框 `<Destroy>` 解绑）、Esc/失焦/切页/输入 `/` 经 `close_completion`/`_hide_panels` 收起；`_skill_name` 对 `Skill` 对象取 `.name`、字典取 `name`、字符串原样（不再 `str(item)` 出 `Skill(name @ stage)` repr）；`_skill_display` 只回 `name`；`_skill_description` 改读 `Skill.description` 属性（原 `getById(str(item))` 对 repr 永远 miss，悬停说明卡此前恒为兜底文案——顺手修正）；`_pick_skill` 聚焦改 `mark_set`（本机 Tk 9.0 无 `Text.icursor`）。
- `stage_model_picker.py`：删 `ADD_MODEL_LABEL` 常量、菜单尾项与 `choose_model` 死分支；`open_model_manager` 保留为「＋」下拉的唯一调用口。
- `tests/architecture/_layers.py`：`desktop_shared_menus` 登记 L4。

## 测试与契约变更（§2.4）

- `test_shared_input_ui.py` +5 条新契约（原始 name 展示与插入、面板开合/Esc/切页、＋菜单三项与技能下钻、互斥与外点、输入 `/` 收面板）；合成鼠标事件按 `test_cell_menu` 惯例 `deiconify`＋控件中心坐标投递（Tk 9.0 下 `event_generate('<Button-1>')` 默认 when 不投递）。
- `test_shared_input_stages.py`：✦／＋ 悬停提示首词断言同步新文案（`添加附件`→`添加`）。
- `test_stage_reasoning.py`：模型菜单尾项断言由「末项＝+ 添加模型…」改为「菜单不含添加模型项」。
- `test_skills.py`：`test_add_menu_model_entry_opens_the_manager_and_reverts` 改为经共享输入框「＋」下拉验证模型管理入口（菜单断言跳过无 `-label` 的分隔线项）；新增 `_walk_widgets` 辅助。
- `维护记录/覆盖率基线.json`：新增模块后按 `scripts/coverage_report.py` 同口径重测（97 条目标用例全过，535 模块/71 覆盖）；`runbook.md` §11 基线数字同步（534/463→535/464）。

## 验证记录

- `run_selftests.py -k test_shared_input_ui test_shared_input_stages test_skill_command`：53 条全绿（首轮 3 红为测试合成事件姿势问题，修正后复跑全绿）。
- `smoke_test.py --affected desktop_shared_input desktop_shared_menus stage_model_picker`：794 条，2 红＝`test_skills` 两条注册表计数（72≠73，环境性，见下）。
- `smoke_test.py`：8/8；`smoke_test.py --architecture`：470/470。
- 环境修复（与 R2966 同法）：本工作树物化三个 gitlink 技能子仓（`reference/HoLLMwood`、`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/编剧技能集`，含 `.git`）并同步未跟踪运行时文件 `维护记录/基准历史.json`——均不入库（gitlink 内容与 gitignore 文件不产生提交）。

## 范围外记录（不代修）

- `test_skills` 两条计数断言 `count()==73` 实测 72：缺口在 gitlink `skills/01 剧本准备SKILL/剧本制作`（commit `6c3d7399`），该子仓内容本机任何工作树/主工作区均无物化、仓库无 `.gitmodules` 可查，R2966 已记同类环境欠账；断言未动。
- `test_ui_edges_pages` 两条红（`video_navigation` 跨父级 pack、`script_structure_info_label` justify）为本分支基线（merge-base `25a12c5`）落后 master 的既有回归，master R2966 已修复，合入后自愈；断言未动。
- 分支 `polished-maxwell` 仅有一个 Cascade snapshot 提交，功能改动全部在 `codex/wip-R2971`。
