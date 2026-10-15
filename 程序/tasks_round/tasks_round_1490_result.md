# R1490 结构治理轮：拆分 desktop.py 步骤 2（创意对话与 Agent 派发方法迁出）

1. **本轮类型？** 结构治理轮（只搬代码，不改逻辑）。
2. **测试与基线？** 默认冒烟 8/8；架构门禁全绿（首次 9 项红，均为“被检代码换了文件／行号／缺登记”，处理见下，断言未动）；idea_chat／attachment／bubble／desktop／pet_ui／writing 等相关自检通过；全量见提交后运行。
3. **是否欠账？** 改了层级登记表（风险路径），提交后须全量转绿。

## 改动

- 新增 `desktop_idea_chat.py`（L4）：`IdeaChatMixin` 原样承载 60 个方法共 1295 行——气泡的显示／折叠／复制／编辑／菜单以外的全部方法、创意附件、语义简报、`show_conversation`、`send_message`（165 行）、`submit_idea_api_request`、`open_flow_agent`（205 行）、`interrupt_script_agent` 等；同时迁入只被它们使用的常量与辅助：`IDEA_FIELDS`、`DRAFT_MARK／HINT`、`BUBBLE_*`、`script_raw_saved_notice`、`model_error_display`，`desktop` 里重新导入测试仍在用的名字（`IDEA_FIELDS`、`BUBBLE_FLOOR／MAX_RATIO`、`script_raw_saved_notice`、`model_error_display`）。
- `Desktop(IdeaChatMixin, AutoFlowsMixin)`；`desktop.py` 7241 → 5906 行（累计自 7820 降 1914 行）。
- **留在 `desktop.py` 的 6 个方法**：`delete_all_bubble_messages`／`delete_uploaded_idea_attachment`（用 `confirm`）、`open_bubble_menu`／`open_idea_paste_menu`／`show_idea_reference_menu`（用 `ContextMenu`）、`open_uploaded_idea_attachment`（用 `open_path`）——测试按 `desktop.confirm／ContextMenu／open_path` 打补丁，迁走会让补丁失效。
- 依赖核对：迁出方法的模块级名字逐个解析并按原来源导入；新模块无未使用导入；`desktop` 删掉迁出后不再使用的 `FormDialog／bubble_timestamp／collapse_preview` 导入。

## 架构门禁的调整（断言未动）

- 新增 `tests/architecture/_scan.py` 的 `desktop_text()／parse_desktop()`（合并 `desktop.py` 与两个 Mixin 模块），`test_busy_state_boundary`（5 处）、`test_file_dialog_boundary`（2 处）、`test_project_context_boundary`、`test_writing_publication_boundary` 改读它们——这些门禁检查的是 Desktop 的行为，不该因为方法分了文件而“消失”。以后拆分同样沿用，不再直接读 `desktop.py`。
- `_layers.py` 登记 `desktop_idea_chat`（L4）；`test_module_size_ratchet`：`desktop.py` 上限 7300 → 6000；TODO 注释快照按原分类对应更新；`architecture.md`、`PROJECT_MAP.md` 同步。

## 有意没做

- 没有把这些方法改写成 L3 服务：它们与 Tk 控件、`self` 状态紧耦合；纯决策部分早已在 L3 `idea_chat_controller`。步骤 3（页面构建拆成 `*_page_ui.py`）风险更高，另行成轮。

## 提交

已提交，见 git log 标题 `R1490:`。

## 补记：全量暴露的第二批（已并入本提交）

- **真实缺陷**：留在 `desktop.py` 里的 `text_width` 用到 `BUBBLE_LINE`，该常量随块迁走而未重新导入——运行到气泡量字宽就会 `NameError`。`test_static_names` 在全量里抓到；`desktop` 补上 `BUBBLE_LINE` 的重新导入。教训：迁常量时要对“留下的代码”也做自由名扫描，不只看迁出的方法。
- **读 `desktop.py` 源码的测试**：`test_codex_paste_diagnostics`（2）、`test_codex_skill_sync`、`test_model_call_error_kind`、`test_qwen_adapter`、`test_request_freeze_entries` 同样改读 `desktop_text()`（断言未动）；`test_request_freeze_entries` 里按“下一个 def”截取方法体的地方，因 `open_flow_agent` 现为 Mixin 文件最后一个方法，补了无下一个 def 的兜底。
- 先前只跑了架构门禁和 `-k` 子集，没发现这批；以后拆分先 `grep -rl "desktop.py" tests` 找全读源码的测试。
