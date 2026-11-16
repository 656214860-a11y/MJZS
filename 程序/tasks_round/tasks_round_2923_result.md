# R2923 功能轮：共享输入框与剧本准备页 UI 重做
<!-- round-evidence: {"commit_base": "926abd2d", "credential_hits": 0, "evidence_sha256": "25c8997458726e4d", "exit": 0, "failed": 0, "passed": 221, "round": 2923, "tests": "run_selftests.py -k test_idea_chat test_script_composer test_idea_send_gate test_ui_writing_recon test_ui_edges_pages test_desktop_compact_layout"} -->

## 三问

1. **本轮类型**：功能轮（§3.1）。用户明确要求重做共享输入框与剧本准备页，属有意 UI 契约变更（§2.4），测试定位与预期同步，断言不弱化、不删除行为覆盖。
2. **测试与三个基线**：
   - 默认冒烟基线：**8/8** ✅（`python smoke_test.py`）
   - 架构门禁：**470/470** ✅（`python smoke_test.py --architecture`，141.6s，改前后一致）
   - 定向回归：`run_selftests.py -k test_idea_chat test_script_composer test_idea_send_gate test_ui_writing_recon test_ui_edges_pages test_desktop_compact_layout` → **共 221 条用例，0 红** ✅
   - 全量：未跑（累计未达 5 个改源码轮次阈值；欠账口径见 runbook §4）。
3. **欠账**：本轮不新增欠账。`project_status.md` 轮次头（当前 2917）随 master 合并轮更新为 2924（仅 master 可提交），worktree 不提交该项目。

## 用户需求（5 点，逐条落实）

1. 剧本准备页下方项目文件框删除 → 改为左侧竖向排列文件框（工作目录列表右侧、聊天输入框左侧）。
2. 删除按钮：发送／刷新／添加剧本／剧本目录／质检报告／阶段配置（含采风）。
3. 输入框移动到底部固定，切换页面也显示共享输入框；其它页面已有的另一个输入框删除。
4. 模型选择器放入输入框内、发送按钮左侧，无外框（仿 DSH）。
5. 增加 skill 图标（✦）放入输入框，点击弹列表、悬停显示说明（仿 Devin）；保留附件 ＋ 与语音 🎤 图标。

## 产品改动

- `desktop_writing_page.py`：删除 composer 卡片／输入行／页脚按钮（发送、刷新、添加剧本、剧本目录、质检报告、采风、阶段配置）；输入框=共享框 Text；附件卡片行挂共享框 `attachment_panel`；文件表由横向四列改为左侧竖向列表（每类带小标题）；`on_modified` 不再对共享 Text 按内容撑高（固定行数、框内滚动）。
- `desktop_shared_input.py`：输入盒内新增附件卡片行 `attachment_panel`；`_toggle_voice` 首击即开麦（惰性创建 VoiceInput 后立即 toggle）。
- `desktop_shared_send.py`：新增 `_voice` 接线与 `on_voice` 宿主回调。
- `desktop_idea_attachments.py`：附件卡片行 pack 由 `side='left'` 改 `side='top'`（挂进共享框输入行下方）。
- `desktop_idea_send_gate.py`：`_apply_idea_send_state` 改为委托 `update_script_interrupt_button`（发送键唯一状态入口）。
- `desktop_script_pages.py`：`update_script_interrupt_button` 改为驱动共享框 `send_button`（运行中=终止、空闲=按简报必填置灰，REQ-S01-62／86 行为保留）。
- `desktop_page_nav.py`：`_sync_shared_input` 剧本准备页也显示共享栏（仅非阶段页隐藏）。

## 测试契约变更（§2.4）

删除 UI（动作栏、composer、静态占位提示、采风、阶段配置按钮）相关断言改为「不存在」断言；输入框断言改为「就是共享实例、固定 `TEXT_ROWS['sm']` 行数」；文件表断言由「横向并排」改为「左侧竖向堆叠、按分类顺序自上而下」；发送／终止／置灰断言改为驱动 `shared_input.send_button`；语音断言改走 `shared_input.voice_button` + `desktop.shared_voice`。

受影响测试文件：`tests/test_idea_chat.py`、`tests/test_script_composer.py`、`tests/test_idea_send_gate.py`、`tests/test_ui_writing_recon.py`、`tests/test_ui_edges_pages.py`、`tests/test_desktop_compact_layout.py`。

## 验证与回归证据

- `python smoke_test.py` → 8/8 ✅
- `python smoke_test.py --architecture` → 470/470 ✅
- 定向回归 6 个测试文件 → 221 条用例，0 红 ✅
- 契约变更后的回归证据：删除按钮/动作栏/composer/占位提示的测试由「存在性断言」改写为「不存在断言」；文件表横向→竖向、输入框独立实例→共享实例、发送键入口从 `idea_send`/`idea_submit`→`shared_input.send_button`，语音入口从 `idea_voice_button`/`idea_voice_input`→`shared_input.voice_button`/`shared_voice`，均锚定用户 5 点需求，未弱化既有行为（REQ-S01-62 发送/终止合一、REQ-S01-86 必填置灰、REQ-S01-71 附件卡片、REQ-S01-46 采风显隐删除）。
