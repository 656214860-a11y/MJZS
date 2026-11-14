# R2496 结果：修复用户气泡正文左对齐与 SKILL 提示行被截断

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）——两处用户可见的显示缺陷：①用户气泡内文字右对齐，不符阅读习惯；②气泡下方「SKILL／时间」提示行被内容框裁掉。第②项同时是用户明确要求的 UI 契约变更（REQ-S01-65），按 §2.4 同轮同步文档与测试预期。

2. **测试跑了吗、三个基线过了吗？**
   - **定向（先红后绿）**：`run_selftests.py -k test_idea_chat test_req_s01_anchors` → 改前 **165 条、5 个文件有红**（红因＝本轮新断言指向旧行为）；改后 **165 条、0 个文件有红、ALL TESTS PASSED**（113–115 秒）。
   - **默认冒烟**：`smoke_test.py` → **8/8 通过**（基线 8/8，本轮无变化）。
   - **架构门禁**：`smoke_test.py --architecture` → **420 条、3 红**（`test_performance_history_is_declared_as_historical_only`、`test_class_size_does_not_grow`「desktop_idea_chat.py::IdeaChatMixin 765 行 > 上限 748」、`test_bare_json_load_debt_is_a_nonincreasing_subset`「api_endpoints.py json.loads 未登记」）。**已用未改动基线复跑对照**：同一台机器、同一工作树、把本轮 4 个文件全部 stash 后重跑 → **同样 420 条、同样这 3 红**。三条均为既有欠账，非本轮引入；本轮未触碰 `desktop_idea_chat.py`、`api_endpoints.py`、`AGENTS.md`。
   - **受影响模块门禁**：`smoke_test.py --affected idea_chat` → 509 条、4 个文件有红（`test_writing_api` 全部 24 条，另 4 项通过）。同样以 stash 后的干净基线复跑 `-k test_writing_api` → **71 条、4 个文件有红、24 条红**，与本轮改动前逐条一致。该文件失败属既有环境问题（缺 `preparation_stage`／`preparation_path` 键、`WritingCancelledError` 未抛出等），非本轮引入。
   - **全量**：未运行（不命中 §5 触发条件：未改启动路径、Tk 控件生命周期、删除语义、层级登记表）。
   - **隐藏桌面实机验收**：经 `工作流任务/gui_hidden.py` 建真 `Desktop` 渲染一条带 3 项 SKILL 页脚的用户消息，读回真实 Tk 属性：`bubble_0.justify=left`、`bubble_0_meta.justify=left`、`bubble_0_time` 为 `justify=left / wrap=word / lmargin1=14`，页脚全文 `SKILL：已勾选 3 项，本次已加载 3 项（写作规则、分镜拆解、剪辑节奏）  11-14 23:51` 的**逐字符 `bbox` 缺失数为 0**；同轮抓图 `r2496_after.png`（1056×800）确认左对齐与整句可见。

3. **`project_status.md` 的欠账少了吗？**
   未减少（本轮是显示层修复）。无新增欠账。上文 3 条架构红与 `test_writing_api` 24 条红在基线上已存在，按 §8.6「范围不扩张」只登记影响、不在本轮修复；`project_status.md` 仅 master 可写，本轮不触碰。

## 根因

两处都在 `程序/desktop_idea_bubbles.py` 的 `add_bubble`：

1. **文字右对齐**：`align='right' if mine else 'left'` 同时喂给正文 tag 和署名 tag（R2297 引入）。用户气泡本身靠 `bubble_margins()` 的左边距贴右，对齐方式另设并不参与分列，右对齐纯属多余且不符阅读习惯。
2. **页脚被裁**：R2421 把页脚 tag 设成 `wrap='none'`，同时沿用 `lmargin1/2=left`。用户气泡的 `left`＝对话区宽度 − 气泡宽（实测 838px 宽时 `left=305`、920px 时 `left=700`），右侧可用宽度只剩一个气泡那么宽；`wrap='none'` 又不换行，超出部分被 Text 直接裁掉。真 Tk 探针实测：920px 宽、53 字页脚、`wrap='none'` 时 **34/53 字无 bbox**。

## 修复（最小改动）

- `add_bubble`：`align` 固定为 `'left'`（正文与署名统一左对齐）；左右分列仍由 `bubble_margins` 的边距决定，用户气泡仍贴右。
- `add_bubble` 页脚 tag：`lmargin1=lmargin2=BUBBLE_GAP`（贴对话区左沿）、`rmargin=BUBBLE_GAP`、`justify='left'`、**`wrap='word'`**（撤销 `wrap='none'`）；仍不铺底色、不加 `BUBBLE_PAD`（留在底框外）。
- `refit_bubbles`：按 tag 三分支——正文补 `BUBBLE_PAD`、页脚钉 `BUBBLE_GAP`、模型名／图标／展开行贴本条气泡左边沿。避免窗口缩放时页脚回落到用户气泡的 `left`。
- 三处注释同步更正（分列只由边距决定、页脚为何必须换行）。

**未改**：`bubble_margins` 逻辑、`BUBBLE_GAP/PAD/FILL` 等 token、页脚内容与插入顺序、`bubble_<n>_toggle` 的右对齐、`bubble_<n>_actions` 图标行。

## 改动文件

- `程序/desktop_idea_bubbles.py`（唯一生产代码改动，+19/−11）
- `程序/docs/stages/S01_剧本准备.md`（REQ-S01-65、DES-S01-65 同步新契约）
- `程序/tests/test_idea_chat.py`：
  - 949／1752 行两处 `('right', …)` → `('left', …)`（用户气泡正文左对齐）。
  - 页脚三条断言改为 `lmargin1=lmargin2=BUBBLE_GAP`、`wrap='word'`、不铺底色。
  - **新增** `test_long_skill_footer_is_fully_visible_and_user_bubble_text_is_left_aligned`：真 Tk、造 3 项 SKILL 页脚，逐字符 `bbox` 断言零裁切 ＋ 正文／署名 `justify='left'` ＋ 用户气泡仍比模型气泡更靠右。docstring 标 `REQ-S01-65`。
  - 新增 `import desktop_idea_chat`（页脚断言用 `BUBBLE_GAP`）。
- `程序/tests/test_req_s01_anchors.py`：`IdeaBubbleAnchorTests` 补一条契约断言（正文与署名一律 `justify='left'`）。既有 lmargin／宽度／分列几何断言**全部保留未动**。

## 测试契约变更说明（§2.4）

`('right', …)` → `('left', …)` 与页脚 `wrap='none'` → `wrap='word'`、`lmargin=left` → `BUBBLE_GAP` 属**用户明确要求的 UI 契约变更**，按 §2.4 同步定位与预期；未弱化、未删除任何断言，分列／宽度／底色／选区优先级／图标行／展开控件相关的既有断言全部原样保留。

## 环境说明（如实记录）

本轮工作树的 4 个 gitlink 目录（`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`skills/01 剧本准备SKILL/编剧技能集`、`reference/HoLLMwood`）检出时**为空**，而主工作树有内容，导致 `workflow_settings` 抛「SKILL 引用缺失」而无法运行界面用例。已从主工作树按目录原样复制补齐（gitlink 目录，不影响 `git status`，暂存清单未含其中任何文件）。这是工作树环境补齐，不是产品改动。

## 未运行项

- `run_selftests.py --all --safe`（全量安全回归）：未运行，不命中 §5 触发条件。
- 3 条既有架构红与 `test_writing_api` 24 条既有红：已用干净基线对照证明与本轮无关，未修复（§8.6 范围不扩张）。

## 提交

- 轮次类型：修复轮；经 `dev.py claim`（`round_claim.py` 封装）领取 **R2496**（并行车道持续推进中央计数器，按规则 27 每次提交前重领，最终号 R2496）；队列无对应 ID（`maintenance-queue.json` 57 条全部 completed）。
- 本轮已提交：分支 `codex/wip-R2496`，提交标题 `R2496: 修复用户气泡正文左对齐与 SKILL 提示行被截断`（5 个文件、+133/−21；不写死 hash，避免 amend 后失真，查 `git log --oneline -1`）。仅本工作树分支，**未合入 master、未 push**；`project_status.md` 按规则 41 只在合入后由 master 补记。
