# R1375：O48 13 阶段、文档与界面标签使用一致权威源

类型：修复/文档一致性轮（§3.2；本项「事实／建议」→ 统一阶段步号与文档对照，不改业务逻辑与门禁）。承接 R1267 清单 O48（O01—O47 已完成），本轮为清单最后一项。中央轮次 1375（`.git/round-counter.json` 的 `last_claimed=1375`）。

## 三个必答
- 本轮类型：修复/文档一致性轮（阶段步号唯一权威 + 文档对照 + 交互验收记录）。
- 测试：新增架构用例 3 条，架构 `smoke_test.py --architecture` **315/315**（312→315，只增不减）；定向 `run_selftests.py -k "video white_model project_open row_targets asset workflow ui_edges pet_ui engine storyboard local_video batch_frames critical_chains shot_assets"` **1456 条 / 386.7 秒**，仅 1 条红为既有环境相关（`test_workflow.DesktopModelPoolTests.test_stage_model_selects_the_matching_desktop_agent`，见「边界」）；交互验收 **244/244**；默认冒烟 `smoke_test.py` **8/8**。
- 欠账：O48 关闭后 R1267 清单 O01—O48 全部完成；1375 − 1374 = 1 < 5，无五轮欠账；但 O48 是路线图收口项（§5「路线图条目收口」），故收口跑一次干净 master 全量（见「全量判定」）。

## 目标（R1267 清单 O48）
- 证据：当前 `pet_bus.py`、PROJECT_MAP 是 13 阶段；`architecture.md` 部分表格/目录仍残留 12 阶段；`desktop.py`、`engine.py` 仍有旧视频/分镜步骤编号。状态与交接资料保留大量历史文字。
- 建议：从阶段注册权威生成导航编号、帮助、目录对照和报告模板；当前状态只保留最新事实/有效凭据/阻塞，历史归档并链接。补全 DPI/键盘焦点/Enter 与按钮一致性等交互检查，禁用控件说明原因。
- 验收：所有 13 阶段顺序、编号、路径一致；用户从提示可找到对应页；缩放/键盘交互有实际验收记录。文档压缩另开授权轮，不在诊断中覆盖历史。

## 实现

### 1. 阶段步号唯一权威：`pet_bus.stage_step(stage)`
- `pet_bus.py`（L0）新增 `stage_step(stage)`：按 `STAGES` 顺序返回两位步号（如 `第03步`），未知阶段返回空串；与阶段目录编号、导航页 `PAGES`（`f'{index:02d}  {stage_name}'`）同源。
- 13 个生产模块改由它生成文案里的步骤号，不再手写：`app.py`、`asset_context.py`、`asset_detail.py`、`batch_frames_tool/batch_frames.py`、`desktop.py`、`engine.py`、`local_video.py`、`storyboard_files.py`、`storyboard_selection.py`、`video_navigation.py`、`white_model.py`、`white_model_ref.py`、`agent/shot_assets.py`。
- 纠正的旧编号（R1124 前的 12 阶段口径）：分镜 02→**03**、资产 03→**05**、定稿 04→**07**、首帧 05→**08**、白模 06→**09**、视频 07→**10**；共 24 处用户可见文案（含 `desktop.py` 的注释与文档串）。

### 2. 文档对照（唯一权威 13 阶段）
- `architecture.md` §4「三虎 Agent 的阶段定义」表：12 行错位（`script_structure` 标 01、缺 `animatic`）→ **13 行**，序号 01—13、ID、中文名逐行＝`pet_bus.STAGES`／`stage_name`。
- `architecture.md` §5「并行配置」表：12 行（缺 `animatic`）→ **13 行**，补 `animatic｜batch｜3｜是｜2 次，转人工`（按 `stage_parallel.CONFIG`）。
- `architecture.md` §8「各阶段输入输出」表：12 行（缺分镜预演）→ **13 行**。
- `README.md`：第 61 期（v0.8）历史目录树小节顶部加一行「历史记录」提示，指回 `PROJECT_MAP.md`「13 阶段目录与交付契约」与 `pet_bus.STAGES`；**不改历史正文**（文档压缩另开授权轮）。

### 3. 交互一致性验收记录（缩放／键盘／禁用）
- `tests/test_asset_detail.py`：`tk scaling` 1.0／1.5／2.0 三档下五处描述区仍保留长文本与 token 风格；缩放隔离用例恢复共享 `tk scaling`；按钮 `takefocus=1`、`tk_focusPrev().tk_focusNext()` 回到自身、`<Return>` 触发；放大弹窗 `focus_get()` 落在关闭键、关闭后焦点回到触发键、返回后焦点回到「← 返回资产管理」。
- `tests/test_idea_chat.py`／`tests/test_ui_edges.py`：输入区 `<Return>` 直接发送（不需要点按钮）、点击提示聚焦真实输入、提示文案含 `enter/发送`。
- `tests/test_ui_theme.py`／`tests/test_ui_widgets_inputs.py`／`tests/test_video_ui.py`：token 主题、输入控件与视频页标签一致。
- 合计 **244/244 绿**（见「测试」）。

## 契约变化
- 用户可见文案（有意变更）：阶段步号改由权威现算并纠正旧号，见上；未改任何页面顺序、业务逻辑、门禁、路径或分层。
- 测试契约同步（保留断言强度，只改期望值／名称）：
  - `tests/architecture/test_agents_md.py` 新增 3 条：§4 阶段表逐行同源、§5 并行表逐行同源、生产文案「第N步」只许来自 `pet_bus.stage_step`（资产子步骤白名单外）。
  - `tests/test_ui_edges.py`：断言 `第04步`→`第07步`，用例更名 `test_final_storyboard_hint_points_to_step04`→`..._step07`（同步 `维护记录/skip台账.json`）。
  - `tests/test_video.py`（`第05步`→`第08步`）、`tests/test_white_model_ref.py`（`第06步`→`第09步`）、`tests/test_project_open.py`（`第 2 步`→`第03步`）、`tests/test_video_ui.py`（`请先在第2步采用`→`请先在第03步采用`）、`tests/test_workflow.py`／`test_row_targets.py`／`test_asset_gating.py`／`test_pet_ui.py` 的样例与 docstring 同步。
- 登记平移：`维护记录/架构统一基数.json` 第四项 `batch_frames_tool/batch_frames.py` 的 `point` 13→14、77→78（import 行 +1）；`维护记录/TODO注释快照_20261003.json` `asset_detail.py` line 350→351（同上）。
- 资产子步骤编号（固定角色＝第 1 步／场景道具＝第 2 步／图片＝第 3 步，见 `asset_prompt_rules.py`／`asset_reference_prompts.py`／`asset_batch_service.py`）属另一套口径，**未改**，并在新门禁里列为白名单。

## 测试
- 架构 `smoke_test.py --architecture`：**315/315、0 红**（原 312/312；+3 为新用例；`tests/architecture/_layers.py` 未改，§5 清单未变）。
- 定向 `run_selftests.py -k "..."`：**1456 条 / 386.7 秒**，仅 1 红为既有环境相关（见「边界」）。
- 交互验收：`tests.test_asset_detail tests.test_ui_theme tests.test_ui_widgets_inputs tests.test_idea_chat tests.test_video_ui` **244/244、0 红**。
- 默认冒烟 `smoke_test.py`：**8/8**。
- 新增 `skipTest`：无。

## 边界
- 未重排页面、未改业务逻辑／门禁／路径／分层；只改用户可见文案与文档对照。
- 文档压缩（状态页与交接历史归档）按清单「另开授权轮」，本轮不动历史正文，只在 README 历史小节加一行指向当前权威的提示。
- **既有环境相关红（非本轮回退）**：`tests/test_workflow.py::DesktopModelPoolTests::test_stage_model_selects_the_matching_desktop_agent` 断言 `effective_model(proj,'writing').startswith('Claude Code')`。主树未跟踪的 `程序/配置/宠物/配置.json` 把 `claude-desktop` 的标签改成了「Claude Desktop」（出厂池是「Claude Code」），故只在主树红。该文件被 `.gitignore` 排除、不在 git 索引内；在无此用户配置的干净全量工作树 `o07-fullsafe-master` 单跑该用例为绿。未改该用例、未动用户配置。
- 未实测物理多屏/系统 DPI 缩放（无该硬件环境），缩放验收走 Tk `tk scaling` 的程序化三档。

## 全量判定
- 1375 − last_full_safe_all_round(1374) = 1 < 5；但 O48 为 R1267 路线图收口项，§5 规定「路线图条目收口」须跑 `run_selftests.py --all --safe`，故收口跑全量。
- 复用检查：`.git/full-safe-receipts.json` 最近绿凭据 round=1374、tree=4778c99e…（7 日内，＝当前 `HEAD:程序`）；但本轮改了生产代码与文档，内容树将变，不能复用。
- 全量结果：在干净 master 谱系工作树 `o07-fullsafe-master`（`git worktree list` 里 HEAD 指向 `refs/heads/master` 使 `is_master_checkout()` 为真；收口前 `git reset --hard HEAD` 到 `afcc0a4`，并把 `.agent-handoff/backlog.md` 的字节同步成仓库期望形态使 `git status --porcelain` 为空）跑 `--all --safe`：**4957/4957、0 红、715.1 秒**（首次即绿，无二次全量）。写凭据 `round=1375`、`tree=c3df6a57f58964034874777125dc038c6771b0b8`（＝`afcc0a4:程序`，与 `HEAD:程序` 一致）、`at=2026-10-12T19:33:12`、`last_full_safe_all_round=1375`。4957 − 4954 = 3 即本轮新增架构用例数；`test_desktop_startup_perf`（14 条 16.3 秒）／`test_perf_baseline`（9 条 26.5 秒）本轮均绿、无阈值抖动。

## 提交
- 本轮改动：13 个生产模块 ＋ `程序/pet_bus.py`、`程序/architecture.md`、`程序/README.md`、`程序/tests/architecture/test_agents_md.py`、8 个测试文件、`程序/维护记录/{架构统一基数.json,skip台账.json,TODO注释快照_20261003.json}`；报告与状态页、4 个接力文件。
- 内容提交：`d5de4df`（29 文件：`pet_bus.py`、13 个生产模块、`architecture.md`、`README.md`、`tests/architecture/test_agents_md.py`、8 个受影响测试、`维护记录` 三份登记；未含主树他人已暂存的 `程序/idea_chat.py`／`程序/idea_attachments.py`／`程序/配置/SKILL/预设.json`）。
- 报告与接力提交：`afcc0a4`（`tasks_round_1375_result.md`、`project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog}.md`）。
- 收尾提交：本提交把「全量结果」与「提交号」补记进报告与接力文件（沿用同一轮次 R1375，中央 `last_claimed` 仍为 1375）。
