# R2416 结果：提交未提交的对话气泡改版＋DRY 去重，并修复其功能缺陷与尺寸门禁越线

## 三个必答（§7）

- **轮次类型**：功能轮（§3.1，含修复）——本轮承接 master 上未提交的一段用户 WIP：对话气泡正文改为「浅灰外框＋淡底＋内边距」（REQ-S01-65 行为变更，已同步 REQ/DES 文档），并对多份重复字符串做 DRY 去重。WIP 本身带两处功能/门禁缺陷，本轮一并修复后才提交。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 定向 `run_selftests.py -k idea_chat script_composer`：**173 条 0 红**（含气泡改版相关全部用例）。
  - 定向 `-k pet_settings`：58 条，**仅 2 条红**，为 R2398 页签化遗留 `KeyError: 'ChatGPT Desktop · Codex'`（R2413 已登记为既有欠账，与本轮无关）。
  - 架构 `smoke_test.py --architecture`：**416 条，仅 1 红** = R2413 欠完整安全全量（后台 post-commit 自动补跑，非本轮范围）。模块/函数/复杂度尺寸棘轮全部绿。
  - 全量：未跑（不命中 §5 强制全量条件；沙箱无法派生工作进程）。
- **project_status.md 的欠账少了吗**：无新增欠账；R2398 页签化 2 条列表测试迁移欠账仍遗留。

## 本轮内容

### 一、承接的用户 WIP（master 未提交改动）

1. **对话气泡视觉改版**（REQ-S01-65）：`desktop_idea_bubbles.py` 正文 tag 由「无底色」改为 `BUBBLE_FILL`（`COLORS['surface_hover']`）淡底＋1px `solid` 描边＋左右 `BUBBLE_PAD` 内边距；`_bubble_rows` 每项加 `framed` 位，`refit_bubbles` 据此只给正文 tag 补内边距；页脚 `bubble_<n>_time` 改 `justify='left'`＋`wrap='none'`。
2. **DRY 字符串去重**（提升为模块级常量）：`desktop_account_page.AGE_CONFIRM_TEXT`、`desktop_automation_service.QUEUE_FULL_TEXT`、`desktop_idea_chat.QUEUEING_STATUS_TEXT`、`desktop_master_update.UPDATE_TITLE`、`pet_ui_settings.AUTOSTART_NOTICE`、`desktop_idea_bubbles.BUBBLE_FILL`，以及 `pet_models_ui.MANAGER_BUTTON` 改名「API 统一配置」→「模型配置」。
3. **文档与测试同步**：`docs/stages/S01_剧本准备.md` REQ-S01-65/DES-S01-65 改写；`tests/test_idea_chat.py`、`tests/test_script_composer.py`、`tests/test_req_s01_anchors.py` 断言同步。

### 二、本轮对 WIP 的修复（先红后绿）

1. **功能缺陷**：`desktop_idea_bubbles.add_bubble` 在 `example = index == 'example'` 赋值**之前**就用 `not example` 写入 `_bubble_rows`，导致 `UnboundLocalError`，气泡页面完全打不开。修复：把 `example` 赋值上移到 append 之前（`test_idea_chat`/`test_script_composer` 先红后绿）。
2. **尺寸门禁越线 ①**：`pet_agent.py` 的 `OPEN_PROGRESS_PANEL` 去重净增 2 行（注释＋常量），1182→1184 超模块上限 1182（`test_module_size_ratchet`，只许下降）。该 2 用字符串去重是净行数增加，故还原为内联字符串，回到 1182。
3. **尺寸门禁越线 ②**：`desktop_media_pages.py::MediaPagesMixin` 的 `configure_video_api` 内嵌函数净增 2 行，890→892 超类上限 890（`test_complexity_ratchet`）。同理还原为 2 处内联 `self.button(...)`，回到 890。

## 改动文件

- `desktop_idea_bubbles.py`（气泡改版＋修复 UnboundLocalError）
- `desktop_idea_chat.py`、`desktop_account_page.py`、`desktop_automation_service.py`、`desktop_master_update.py`、`pet_ui_settings.py`、`pet_models_ui.py`（DRY 去重）
- `docs/stages/S01_剧本准备.md`（REQ/DES-S01-65 改写）
- `tests/test_idea_chat.py`、`tests/test_script_composer.py`、`tests/test_req_s01_anchors.py`（断言同步）

## 遗留欠账

- R2398 页签化 2 条列表测试迁移欠账（`KeyError: 'ChatGPT Desktop · Codex'`）仍遗留。
- R2413 欠一次完整安全全量，由 post-commit 钩子后台自动补跑（见 `程序/logs/auto_full_safe.log`）。

## 提交

- 已提交：是。commit hash 见 git log。
- 提交信息：`R2416: 提交气泡改版＋DRY去重，并修复功能缺陷与尺寸门禁越线`。
