# R3060 功能轮：桌面界面打磨——附档行内引用、项目文件停靠列、输入框外框、启动尺寸、模型选择器、输入框对齐、Fluent 图标
<!-- round-evidence: {"commit_base": "09ee3e67", "credential_hits": 0, "evidence_sha256": "e252c03bcb5071d3", "exit": 0, "failed": 0, "passed": 348, "round": 3060, "tests": "run_selftests.py -k files_panel idea_chat shared_input compact_layout script_composer ui_edges"} -->

## 三问

1. **本轮类型**：功能轮（§3.1）。用户七条桌面 UI 诉求，决策经两轮确认（Q1–Q10，任务书 `tasks_round/R3060_桌面界面打磨任务书.md`）；UI 契约有意变更，S01 需求/设计先行（REQ-S01-90 相关段同步），测试断言按新契约更新、未弱化。
2. **测试与三个基线**：
   - 默认冒烟：8/8 ✅
   - `--affected` 等价定向（136 文件 / 2541 用例，`run_selftests.py -k <affected 全集>` 并行）：**0 红** ✅（1 条登记 skip：`test_stage_profile_wrong_preset_rejected` 发行包环境位）
   - `test_files_panel` 串行 6/6 ✅（含修复后的停靠几何断言）
   - 架构门禁：随 affected 集内 `architecture.test_*` 全绿；`--all --safe` 未跑（见「合入状态」）。
3. **欠账**：无新增。`project_status.md` 轮次头仅 master 可提交，随合并轮更新。

## 需求与设计

- `docs/stages/S01_剧本准备.md`：REQ/DES 段同步新契约（附档 `@原名` 行内引用区、项目文件停靠列、输入框单层外框、模型选择器紧凑滚动）。
- 决策记录（用户拍板）：附件以上传后顶部 `@原名` 行展示（每附件一行、占位文本区顶部）；右键 `@` 行＝打开／取消引用／删除项目副本（回收站，原件不动）；文件图标右 padding `sm→xs`、内容区右 padding `xl→md`；内框线全去、聚焦外框高亮；默认高 800→900（最小 800×600 不变）；模型徽标贴模型名＋原生滚动条；共享输入框全页与画布列同宽；发送/停止/返回用 Fluent PNG（send/stop 白墨水、back 常规墨水），返回保留「返回生成方式」文字。

## 产品改动（本分支基线 R2962，已提交 codex/wip-R3060）

- `desktop.py`：`panel_area` 下分 `panel_dock`（右列）与 `stage_area`（画布＋`input_dock` 输入列）；面板打开才把 dock 打包进 panel_area——实测 Tk 在空包最后一个 slave 被 forget 后需求宽度不回缩（最小复现已验证），常驻空列会把画布永久挤窄。
- `desktop_files_panel.py`：停靠框/分隔线进 `panel_dock`；`open_panel` 先把子件装进未映射 dock 再整列打包（小窗 800×600 下需求宽度才能传进来），`collapse` 连 dock 一起 `pack_forget`。
- `desktop_shared_input.py`：附件 chip 行删除，改顶部 `@原名` 引用区（`idea_ref` tag）；Text 去内框线 `highlightthickness=0`＋`width=1`（默认 80 字符报需求宽 ≈672px，会把 stage_area 顶过最小窗可用宽、面板被挤成 1px）；外层 `tk.Frame` 环色描边（ttk 不支持 highlightthickness），聚焦切 `border_input_hover`；发送/停止换 Fluent PNG。
- `desktop_idea_attachments.py`：`_sync_idea_ref_block()` 按 `idea_attachment_paths` 重建顶部引用行；`_idea_cursor_ref_names` 防手动 `@` 插入重复进引用区；`_idea_attachment_at()` 右键命中检测（兼容无 x/y 的合成事件）；`unreference_idea_attachment()`／`remove_idea_ref_line()`。
- `desktop_idea_menus.py`：`open_idea_paste_menu` 先查 `@` 行命中→附件菜单（打开／取消引用／删除项目副本），否则走原粘贴逻辑。
- `orchestrator/idea_chat_controller.py`：`unreference_attachment(path)`——只移出本轮发送名单，项目副本保留。
- `stage_model_picker.py`：模型行去 `expand`（徽标贴模型名）、`ScrollForm(scrollbar=True)`。
- `video_navigation.py`＋`ui_icons`/`build_nav_icons.py`：新增 `send/stop/back` Fluent PNG（send/stop 卡片色墨水），`nav_icon()` 运行时加载带字形回退；返回钮换 back.png 保留文字。
- `ui_tokens.py`：`default_height` 800→900、`body_padding` 右 `xl→md`。
- 测试：`test_files_panel`/`test_desktop_compact_layout`/`test_idea_chat`/`test_script_composer`/`test_idea_inline_brief`/`test_ui_edges_pages`/`test_ui_style_engine` 按新契约更新。
- 新增：`assets/nav/{send,stop,back}.png`、`scripts/build_nav_icons.py` 登记、`tasks_round/R3060_桌面界面打磨任务书.md`。

## 验证明细

- 修复闭环记录：① `ttk.Frame` 不支持 `-highlightthickness` → 改 `tk.Frame` 环；② `tag_ranges` 空 tag TclError → `tag_names()` 守卫；③ 面板 800×600 塌 1px → 根因是 Text 默认 80 字符需求宽（672px）＋Tk 空包 reqwidth 不回缩双重问题，分别以 `width=1` 与「打开才 pack dock」解决；④ `SimpleNamespace` 无 x/y 事件 → `_idea_attachment_at` except 含 `AttributeError`。
- 几何实测（真 Tk）：1008×900 开合面板 canvas 892→698→892；800×600 canvas 684→486→684；942×632、1280×900 同绿；输入框宽＝画布列宽（含面板开合同步收窄）。
- 环境备注（不入库）：worktree 缺 `skills/00全流程SKILL/AIGC创作全流程/sd-decision-engine` 子模块内容，自主工作区复制补齐（与 R2962 结果文件同类处置）。

## 合入状态（如实）

- 分支 `codex/wip-R3060` 已提交：`4f5d32d8`（R3060 实现）→ `adcd01a5`（同步主干合并 master beea4e6b）→ `84be85ec`（合并修正）。
- master 自分支点前进至 R3081（R3016 统一状态栏、R2971–R2980 共享输入升级、R2998 图标列等），直接 merge 有 5 文件 11 处冲突，已在分支上完成同步合并并逐处核对：
  - `desktop.py`：取主干 StatusBar/UsageIndicator，共享输入框仍宿主 `input_dock`（不用 `before=status_bar`，非同级）。
  - `desktop_files_panel.py`：入口图标列 `rail` 改挂 `panel_area`（panel_dock 父级），面板打开时图标恒为内容区最右竖条；`_pack_button` 取主干 rail 列版；`_fit_script_width` 分母由 `script_box.master`（自适应 panel_dock，循环）改 `panel_area`。
  - `desktop_idea_attachments.py`：删除旧 `insert_idea_reference`（主干 `_CandidateFlow._apply_mention` 已接管 @ 插入）。
  - `desktop_shared_input.py`：`_apply_mention` 补记 `_idea_cursor_ref_names`，光标处 @引用不进顶部引用区。
  - `desktop_page_nav.py`：共享输入框 pack 取本分支版（宿主已在 input_dock）。
  - `S01_剧本准备.md`：REQ-S01-82/62/63/71/90 与 DES-S01-82/90 双侧并集（保留主干 R2971/R2998/REQ-S01-91/92 新条目＋本分支 R3060 描述）。
  - 测试契约同步：`test_files_panel` 图标列父级断言 `canvas.master→panel_area`（§2.4 有意变更）；`test_script_composer` 失焦改用 `canvas`（`title_row` 已被 R3016 删除）。
- 合并后验证：默认冒烟 9/9 ✅；定向 17 文件 365 用例初跑 2 红（面板宽分母循环、title_row 残留）→ 修复后 `files_panel`+`script_composer` 15/15 ✅。
- **合入 master 受阻**：主工作区存在他车道在途合并（MERGE_HEAD=33de0a84／R3073，oak-cogwheel 车道，已 staged 未提交、占用轮次号 R3083），`dev.py merge` 依规则拒绝在 MERGE_HEAD 未清时运行；待其提交或中止后执行。
- `--all --safe` 全量：合入 master 前按 §5（Tk 生命周期改动）补跑。
