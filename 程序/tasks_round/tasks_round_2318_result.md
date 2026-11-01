# R2318 剧本准备页模型目录条结果

- 轮次类型：功能轮（UI），AGENTS.md §3.1。
- 需求／设计：REQ-S01-77、DES-S01-77（`docs/stages/S01_剧本准备.md` 已同步）。
- 未提交：本工作树任务由调度方提交，本轮未 `git commit`、未领号。

## 三个必答

1. **本轮类型**：功能轮（UI）。
2. **测试跑了吗、三个基线过了吗**：
   - 默认冒烟：实跑通过 **8/8**（`smoke_test.py`，经 `工作流任务/gui_hidden.py` 隐藏桌面）。
   - 架构门禁：本轮未做跨层／结构治理改动，按风险跑定向子集 `run_selftests.py -k ratchet requirement_traceability layers`，**56 条 / 0 红**（含模块行数、复杂度、共享状态三个棘轮 + 需求锚定 + 分层）。完整 `--architecture` 未整跑。
   - 全量回归：未运行（任务书未要求，全量凭据由合并到 master 的调度方处理）。
3. **欠账少了吗**：本轮不新增欠账；未触碰历史欠账条目，未把历史绿色凭据当作本轮结果。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `idea_chat_controller.py` | 新增 `ALL_MODELS` 常量与纯函数 `model_bar_items`（去重、按最早 `at` 排序）、`model_bar_selection`（默认当前模型、无记录回落「全部」） |
| `desktop_idea_bubbles.py` | 新增 `build_idea_model_bar`／`render_idea_model_bar`／`_fit_idea_model_bar`（横向可滚动标签条）、`set_idea_model_filter`／`select_idea_model`／`idea_view_rows`（选中态唯一写入口 + 按选中键解析显示行）；气泡复制／回退／删除改按 `_idea_view_rows` 定位 |
| `desktop_idea_chat.py` | `show_conversation` 改调 `idea_view_rows`；`send_message` 发送后同步目录条选中态 |
| `desktop_script_pages.py` | `refresh_script_chat_for_selected_model` 配置确认后同步目录条选中态 |
| `desktop_writing_page.py` | `_build_dialog` 在聊天气泡框上方建目录条（先隐藏） |
| `docs/stages/S01_剧本准备.md` | 新增 REQ-S01-77、DES-S01-77 与测试锚定行 |
| `tests/test_idea_chat_presentation.py` | 新增 `ModelBarTests`（纯函数去重／排序／选中回落） |
| `tests/test_idea_chat.py` | 新增 `ModelBarUITests`（真 Tk：标签列表、点击筛选、高亮、≤1 模型／空项目隐藏） |

## 测试命令与实际结果

- `& '..\运行环境\Python\python.exe' -B run_selftests.py -k idea_chat`（经 gui_hidden）：**共 162 条用例，0 个文件有红**。
- `& '..\运行环境\Python\python.exe' -B run_selftests.py -k ui_edges`（经 gui_hidden）：**共 115 条用例，0 个文件有红**。
- `& '..\运行环境\Python\python.exe' -B run_selftests.py -k ratchet requirement_traceability layers`：**共 56 条用例，0 个文件有红**。
- `& '..\运行环境\Python\python.exe' -B smoke_test.py`（经 gui_hidden）：**通过 8 项 / 失败 0 项**。

先红后绿记录：初版 `show_conversation` 用 `idea_chat.load(model='')`（合并行含去重）直接按标签过滤，导致既有用例 `test_clear_screen_is_scoped_and_preserves_new_identical_messages` 红（重复消息被合并去重后计数 0≠1）；改回「具体模型走 `idea_chat.load(model=selected)`（保留 L2 旧版迁移与重复消息语义）、「全部」才用合并行」后转绿。初版共享状态棘轮红（`Desktop: 50 个多写者属性 > 上限 48`），把 `_idea_model_filter`／`_idea_model_filter_root` 收口到 `IdeaBubblesMixin.set_idea_model_filter` 单一写入口后转绿。

## 断言未动声明

未弱化、删除或跳过任何既有断言；未改测试迁就实现。上述两次红灯均通过改**实现**修复，既有断言保持原样。新增测试的 docstring 锚定 `REQ-S01-77`，`test_requirement_traceability` 通过。

## 未验证项

- 完整 `run_selftests.py --all --safe` 全量回归未运行（工作树任务，未要求）。
- 完整 `--architecture` 全部门禁未整跑；只跑了与本轮改动直接相关的棘轮、需求锚定、分层子集。
- 真实模型／桌面 Agent 端到端未运行；目录条的真实多模型外观与横向滚动溢出只在隐藏桌面真 Tk 用例中验证了「列表／点击筛选／高亮／隐藏」路径，未做真人视觉验收。
