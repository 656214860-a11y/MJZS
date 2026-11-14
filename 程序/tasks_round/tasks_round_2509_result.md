# R2509 结果：结构治理轮——拆出创意附件 Mixin，消掉 IdeaChatMixin 类行数欠账

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3·执行）——按「一行一法一聚簇」原则，把 `IdeaChatMixin` 里自成一事的创意附件聚簇（5 个方法）原样迁出到新 Mixin，使该类从 769 行降到 665 行，退出类行数棘轮欠账（原先 748 上限仍被 769 超限）。方法体逐字不改，`self` 语义不变。

2. **测试跑了吗、三个基线过了吗？**
   - **架构门禁 `smoke_test.py --architecture`**：**420/420 全绿（exit 0）**。本轮前是 420 条 3 红（`test_performance_history_is_declared_as_historical_only` 缺本机 `基准历史.json`、`test_class_size_does_not_grow` 的 IdeaChatMixin 769 超限、`test_bare_json_load_debt_is_a_nonincreasing_subset` 的 json.loads 未登记）；本轮把 IdeaChatMixin 降到 665 消除其红，`基准历史.json` 从主树补齐（本机 gitignore 数据，非源码），json.loads 那条由并行车道 R2504 已修。
   - **定向**：`-k test_idea_chat test_script_composer test_idea_inline_brief test_idea_history_first_paint` → **202 条、0 红、ALL TESTS PASSED**。
   - **默认冒烟**：**8/8 通过**。
   - **全量**：未运行（本轮只改 L4 拆分＋架构登记，不命中 §5 触发条件）。
   - **迁出方法逐字核对**：`update_idea_attachment_status`／`refresh_uploaded_idea_attachments`／`choose_idea_attachments`／`poll_idea_attachment_preparation` 四方法体与 master 原版逐字一致（23/45/13/15 行），`insert_idea_reference` 8 行方法体与 master 原版一致（见文件行 113–120）。

3. **`project_status.md` 的欠账少了吗？**
   减少了架构门禁的 1 条欠账（`test_class_size_does_not_grow` 的 IdeaChatMixin 超限）；`test_bare_json_load_debt` 那条由 R2504 已清。**未解决**的欠账：`test_writing_api` 24 条红（见下）。

## 改动清单

- `程序/desktop_idea_attachments.py`（**新增**，L4）：`IdeaAttachmentsMixin` 承载 5 个附件方法，从 `desktop_idea_chat.IdeaChatMixin` 原样迁出。
- `程序/desktop_idea_chat.py`：删 105 行（附件方法块＋尾部空行）、加 2 行（`from desktop_idea_attachments import IdeaAttachmentsMixin` ＋ 基类追加）；`IdeaChatMixin` 769→665 行，模块 1111→985 行。
- `程序/architecture.md`：新增 R2505 条目，记录迁出方法清单、行数变化、登记表同步。
- `程序/runbook.md`：覆盖率基线模块数 363→364（新模块纳入）。
- `程序/维护记录/覆盖率基线.json`：重跑 `scripts/coverage_report.py` 刷新（modules_total 363→364，覆盖 59 个不变）。
- 架构登记表（`tests/architecture/`）：
  - `_layers.py`：`desktop_idea_attachments` 登记 L4。
  - `_scan.py`：`DESKTOP_PARTS` 增补 `desktop_idea_attachments.py`。
  - `test_complexity_ratchet.py`：`IdeaChatMixin` 类行数登记 748→665（实际 665）。
  - `test_module_size_ratchet.py`：删除 `desktop_idea_chat.py: 1111`（已降到 985，不超限）。
  - `test_shared_state_ratchet.py`：新增 `'IdeaChatMixin': 2`（加第三个 Mixin 基类后实测 2 个共享属性 `_idea_view_after_jobs`／`_idea_view_generation`）。

## 范围外欠账（如实记录，未在本轮修复）

`test_writing_api` 24 条红根因已定位：`pipeline-script-preparation.skill.md` 经 R2450 的递归完整内联后冻结正文达 **158,405 字符**（≈8 万 token），加系统提示后越过 128k 上下文预算，`writing_api.reply()` 在 `context_budget_exceeded` 下直接返回 `ok=False`，根本不发模型请求，于是断言 `result['ok']`／`preparation_stage` 等全红。这属**产品语义**问题（SKILL 内联口径 vs 上下文预算冲突），不是纯机械欠账，涉及「哪些引用该内联、哪些该按锁跳过／降级」的取舍，需你拍板，故不并入本轮。

## 提交

- 轮次类型：结构治理轮（执行）；经 `dev.py claim` 领取 R2509。
